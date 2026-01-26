"""Claude CLI Agent 服務

使用 asyncio.subprocess 非同步呼叫 Claude CLI。
自己管理對話歷史，不依賴 CLI session。
"""

import asyncio
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..config import settings
from . import ai_manager


# Claude CLI 超時設定（秒）
DEFAULT_TIMEOUT = 180  # 延長至 3 分鐘，以支援複雜搜尋任務

# 工作目錄（使用獨立目錄，避免讀取專案的 CLAUDE.md）
WORKING_DIR = "/tmp/ching-tech-os-cli"
os.makedirs(WORKING_DIR, exist_ok=True)

# 複製 MCP 配置到工作目錄
PROJECT_ROOT = settings.project_root
_mcp_src = os.path.join(PROJECT_ROOT, ".mcp.json")
_mcp_dst = os.path.join(WORKING_DIR, ".mcp.json")
if os.path.exists(_mcp_src):
    shutil.copy2(_mcp_src, _mcp_dst)

# 設定 nanobanana 輸出目錄（symlink 到 NAS，讓生成的圖片可以透過 Line Bot 發送）
_nas_ai_images_dir = f"{settings.linebot_local_path}/ai-images"
_nanobanana_output_link = os.path.join(WORKING_DIR, "nanobanana-output")

# 建立 NAS 目錄（如果不存在）
if os.path.exists(settings.linebot_local_path):
    os.makedirs(_nas_ai_images_dir, exist_ok=True)

    # 建立 symlink（如果不存在或指向錯誤位置）
    if os.path.islink(_nanobanana_output_link):
        # 檢查是否指向正確位置
        if os.readlink(_nanobanana_output_link) != _nas_ai_images_dir:
            os.remove(_nanobanana_output_link)
            os.symlink(_nas_ai_images_dir, _nanobanana_output_link)
    elif os.path.exists(_nanobanana_output_link):
        # 是普通目錄，移除後建立 symlink
        shutil.rmtree(_nanobanana_output_link)
        os.symlink(_nas_ai_images_dir, _nanobanana_output_link)
    else:
        # 不存在，直接建立 symlink
        os.symlink(_nas_ai_images_dir, _nanobanana_output_link)


def _find_claude_path() -> str:
    """尋找 Claude CLI 路徑"""
    # 先嘗試 PATH 中的 claude
    claude_in_path = shutil.which("claude")
    if claude_in_path:
        return claude_in_path

    # 嘗試常見的 NVM 安裝路徑
    home = os.path.expanduser("~")
    nvm_paths = [
        f"{home}/.nvm/versions/node/v24.11.1/bin/claude",
        f"{home}/.nvm/versions/node/v22.11.0/bin/claude",
        f"{home}/.nvm/versions/node/v20.18.0/bin/claude",
    ]

    for path in nvm_paths:
        if os.path.exists(path):
            return path

    # 找不到就用預設
    return "claude"


# Claude CLI 路徑
CLAUDE_PATH = _find_claude_path()

# 模型對應表（前端名稱 → CLI 模型名稱）
MODEL_MAP = {
    "claude-opus": "opus",
    "claude-sonnet": "sonnet",
    "claude-haiku": "haiku",
}


@dataclass
class ToolCall:
    """工具調用記錄"""

    id: str  # tool_use_id
    name: str  # 工具名稱
    input: dict  # 輸入參數
    output: Optional[str] = None  # 輸出結果


@dataclass
class ClaudeResponse:
    """Claude CLI 回應"""

    success: bool
    message: str
    error: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    tool_timings: list[dict] = field(default_factory=list)  # [{name, duration_ms}]


async def get_prompt_content(prompt_name: str) -> str | None:
    """從資料庫取得 prompt 內容"""
    prompt = await ai_manager.get_prompt_by_name(prompt_name)
    if prompt is None:
        return None
    return prompt.get("content")


def compose_prompt_with_history(
    history: list[dict], new_message: str, max_messages: int = 40
) -> str:
    """組合對話歷史和新訊息成完整 prompt

    Args:
        history: 對話歷史 [{"role": "user/assistant", "content": "..."}]
        new_message: 新的使用者訊息
        max_messages: 最多保留的歷史訊息數量

    Returns:
        組合後的完整 prompt
    """
    # 截斷舊訊息（保留最近的）
    recent_history = history[-max_messages:] if len(history) > max_messages else history

    # 組合歷史
    parts = []

    if recent_history:
        parts.append("對話歷史：")
        parts.append("")
        for msg in recent_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            sender = msg.get("sender")  # 發送者名稱（群組對話用）
            # 跳過摘要訊息（它會在 system prompt 中處理）
            if msg.get("is_summary"):
                continue
            # 格式：user[發送者]: 內容 或 user: 內容（無發送者時）
            if sender:
                parts.append(f"{role}[{sender}]: {content}")
            else:
                parts.append(f"{role}: {content}")
        parts.append("")

    # 加入新訊息（sender 資訊已包含在 new_message 參數中，由呼叫端處理）
    parts.append(new_message)

    return "\n".join(parts)


@dataclass
class ToolTiming:
    """Tool 執行時間記錄"""
    name: str
    started_at: float
    finished_at: float | None = None

    @property
    def duration_ms(self) -> int | None:
        if self.finished_at:
            return int((self.finished_at - self.started_at) * 1000)
        return None


@dataclass
class ParseResult:
    """stream-json 解析結果"""
    text: str
    tool_calls: list[ToolCall]
    input_tokens: int | None
    output_tokens: int | None
    tool_timings: list[ToolTiming]
    pending_tools: dict[str, ToolTiming]  # 尚未完成的 tools


def _clean_overgenerated_response(text: str) -> str:
    """清理 AI 過度生成的對話預測

    Claude 模型在對話格式下，有時會繼續預測後續的用戶訊息，
    導致回應中混入虛構的對話內容，例如：

        AI 的正常回應...
        user: 用戶名: 虛構的訊息
        user: [回覆...] 更多虛構內容

    這個函數會截斷這些多餘的內容。

    Args:
        text: AI 的原始回應文字

    Returns:
        清理後的回應文字
    """
    if not text:
        return text

    # 按行分割
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        # 檢測 AI 過度生成的對話行
        # 這些行通常以 "user:" 或 "user[" 開頭（可能有前導空白）
        stripped = line.strip()
        if stripped.startswith("user:") or stripped.startswith("user["):
            # 發現過度生成，停止收集
            break
        cleaned_lines.append(line)

    # 重新組合，移除尾端多餘的空行
    result = "\n".join(cleaned_lines).rstrip()
    return result


def _parse_stream_json_with_timing(
    lines_with_time: list[tuple[float, str]]
) -> ParseResult:
    """解析 stream-json 輸出（含時間戳記）

    Args:
        lines_with_time: [(timestamp, line), ...] 每行附帶讀取時間

    Returns:
        ParseResult: 包含解析結果和 tool 時間統計
    """
    result_text = ""
    tool_calls: list[ToolCall] = []
    input_tokens: int | None = None
    output_tokens: int | None = None

    # 暫存 tool_use，等待配對 tool_result
    pending_tools: dict[str, ToolCall] = {}
    # tool 時間記錄
    tool_timings: dict[str, ToolTiming] = {}

    for timestamp, line in lines_with_time:
        if not line.strip():
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type")

        if event_type == "assistant":
            # 解析 assistant 訊息中的 content
            message = event.get("message", {})
            contents = message.get("content", [])
            for content in contents:
                content_type = content.get("type")
                if content_type == "tool_use":
                    # 記錄工具調用開始
                    tool_id = content.get("id", "")
                    tool_name = content.get("name", "")
                    tool_call = ToolCall(
                        id=tool_id,
                        name=tool_name,
                        input=content.get("input", {}),
                    )
                    pending_tools[tool_id] = tool_call
                    tool_timings[tool_id] = ToolTiming(
                        name=tool_name,
                        started_at=timestamp,
                    )
                elif content_type == "text":
                    # 累積文字回應（可能有多段）
                    text = content.get("text", "")
                    if text:
                        if result_text:
                            result_text += "\n"
                        result_text += text

        elif event_type == "user":
            # 解析 user 訊息中的 tool_result
            message = event.get("message", {})
            contents = message.get("content", [])
            for content in contents:
                if content.get("type") == "tool_result":
                    tool_id = content.get("tool_use_id", "")
                    if tool_id in pending_tools:
                        # 配對工具輸出，記錄完成時間
                        pending_tools[tool_id].output = content.get("content", "")
                        tool_calls.append(pending_tools.pop(tool_id))
                        if tool_id in tool_timings:
                            tool_timings[tool_id].finished_at = timestamp

        elif event_type == "result":
            # 最終結果，包含 usage 統計
            if not result_text and event.get("result"):
                result_text = event.get("result", "")

            # 計算 token 統計（包含 cache tokens）
            usage = event.get("usage", {})
            base_input = usage.get("input_tokens") or 0
            cache_creation = usage.get("cache_creation_input_tokens") or 0
            cache_read = usage.get("cache_read_input_tokens") or 0
            input_tokens = base_input + cache_creation + cache_read
            output_tokens = usage.get("output_tokens")

    # 將未配對的 tool_use 也加入（可能沒有 result）
    for tool in pending_tools.values():
        tool_calls.append(tool)

    # 分離已完成和未完成的 tool timings
    completed_timings = [t for t in tool_timings.values() if t.finished_at]
    pending_timings = {k: v for k, v in tool_timings.items() if not v.finished_at}

    # 清理 AI 過度生成的對話預測
    # AI 有時會在回應中繼續預測後續的 user 訊息
    # 這會導致 raw_response 中混入虛構的對話內容
    result_text = _clean_overgenerated_response(result_text)

    return ParseResult(
        text=result_text,
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tool_timings=completed_timings,
        pending_tools=pending_timings,
    )


def _parse_stream_json(stdout: str) -> tuple[str, list[ToolCall], int | None, int | None]:
    """解析 stream-json 輸出（相容舊版介面）

    Args:
        stdout: Claude CLI 的 stream-json 輸出（多行 JSON）

    Returns:
        tuple: (最終回應文字, 工具調用列表, input_tokens, output_tokens)
    """
    # 轉換為帶時間戳的格式（用 0 作為時間戳）
    lines_with_time = [(0.0, line) for line in stdout.strip().split("\n")]
    result = _parse_stream_json_with_timing(lines_with_time)
    return result.text, result.tool_calls, result.input_tokens, result.output_tokens


async def call_claude(
    prompt: str,
    model: str = "sonnet",
    history: list[dict] | None = None,
    system_prompt: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    tools: list[str] | None = None,
) -> ClaudeResponse:
    """非同步呼叫 Claude CLI（自己管理對話歷史）

    Args:
        prompt: 使用者訊息
        model: 模型名稱（opus, sonnet, haiku）
        history: 對話歷史（可選）
        system_prompt: System prompt 內容（可選）
        timeout: 超時秒數
        tools: 允許使用的工具列表（可選，如 ["WebSearch", "WebFetch"]）

    Returns:
        ClaudeResponse: 包含成功狀態、回應訊息、工具調用記錄和 token 統計
    """
    # 轉換模型名稱
    cli_model = MODEL_MAP.get(model, model)

    # 組合完整 prompt（包含歷史）
    if history:
        full_prompt = compose_prompt_with_history(history, prompt)
    else:
        full_prompt = prompt

    # 建立 Claude CLI 命令（不使用 session）
    # 使用 stream-json 格式以獲取工具調用詳情和 token 統計
    cmd = [
        CLAUDE_PATH, "-p",
        "--model", cli_model,
        "--output-format", "stream-json",
        "--verbose",
    ]

    # 加入 system prompt
    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    # 加入工具（需要 --permission-mode bypassPermissions 來跳過互動確認）
    if tools:
        tools_str = ",".join(tools)
        cmd.extend([
            "--tools", tools_str,
            "--allowedTools", tools_str,
            "--permission-mode", "bypassPermissions"
        ])

    # prompt 放在最後（作為位置參數）
    cmd.append(full_prompt)

    # DEBUG: 輸出實際執行的命令
    print(f"[claude_agent] cmd: {cmd}")

    proc = None
    stdout_lines_with_time: list[tuple[float, str]] = []
    start_time = time.time()

    try:
        # 建立非同步子程序（使用獨立工作目錄，避免讀取專案的 CLAUDE.md）
        # 設定較大的 buffer limit（默認 64KB 可能不夠長的 JSON 行）
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=WORKING_DIR,
            limit=10 * 1024 * 1024,  # 10MB limit per line
        )

        # Streaming 讀取 stdout（邊讀邊收集，記錄時間戳）
        async def read_stdout():
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                stdout_lines_with_time.append((time.time(), line.decode("utf-8")))

        async def read_stderr():
            return await proc.stderr.read()

        # 等待完成（含超時）
        try:
            stderr_bytes = await asyncio.wait_for(
                asyncio.gather(read_stdout(), read_stderr()),
                timeout=timeout,
            )
            stderr = stderr_bytes[1].decode("utf-8").strip() if stderr_bytes[1] else ""
        except asyncio.TimeoutError:
            # 超時：終止程序，但保留已讀取的 stdout
            if proc:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()

            # 解析已讀取的部分（含時間統計）
            parse_result = _parse_stream_json_with_timing(stdout_lines_with_time)

            # 輸出診斷資訊
            elapsed = time.time() - start_time
            print(f"[claude_agent] TIMEOUT after {elapsed:.1f}s")
            print(f"[claude_agent] 已完成的 tools ({len(parse_result.tool_calls)}):")
            for timing in parse_result.tool_timings:
                print(f"  - {timing.name}: {timing.duration_ms}ms")
            if parse_result.pending_tools:
                print(f"[claude_agent] 執行中的 tools (timeout 時仍在執行):")
                for tool_id, timing in parse_result.pending_tools.items():
                    running_time = int((time.time() - timing.started_at) * 1000)
                    print(f"  - {timing.name}: 已執行 {running_time}ms (未完成)")

            # 組合錯誤訊息
            error_msg = f"請求超時（{timeout} 秒）"
            if parse_result.pending_tools:
                pending_names = [t.name for t in parse_result.pending_tools.values()]
                error_msg += f"，執行中的工具：{', '.join(pending_names)}"

            # 轉換 timing 為 dict 格式
            timings_dict = [
                {"name": t.name, "duration_ms": t.duration_ms}
                for t in parse_result.tool_timings
            ]

            return ClaudeResponse(
                success=False,
                message=parse_result.text,
                error=error_msg,
                tool_calls=parse_result.tool_calls,  # 返回已完成的 tool_calls
                input_tokens=parse_result.input_tokens,
                output_tokens=parse_result.output_tokens,
                tool_timings=timings_dict,
            )

        await proc.wait()

        # 解析 stream-json 輸出（含時間統計）
        parse_result = _parse_stream_json_with_timing(stdout_lines_with_time)

        # 輸出 tool 執行時間（debug 用）
        if parse_result.tool_timings:
            print(f"[claude_agent] Tool 執行時間:")
            for timing in parse_result.tool_timings:
                print(f"  - {timing.name}: {timing.duration_ms}ms")

        # 檢查執行結果
        if proc.returncode != 0:
            error_msg = stderr or f"Claude CLI 執行失敗 (code: {proc.returncode})"
            return ClaudeResponse(
                success=False,
                message="",
                error=error_msg,
            )

        # 轉換 timing 為 dict 格式
        timings_dict = [
            {"name": t.name, "duration_ms": t.duration_ms}
            for t in parse_result.tool_timings
        ]

        return ClaudeResponse(
            success=True,
            message=parse_result.text,
            tool_calls=parse_result.tool_calls,
            input_tokens=parse_result.input_tokens,
            output_tokens=parse_result.output_tokens,
            tool_timings=timings_dict,
        )

    except FileNotFoundError:
        # Claude CLI 未安裝
        return ClaudeResponse(
            success=False,
            message="",
            error="找不到 Claude CLI，請確認已安裝",
        )

    except Exception as e:
        # 其他錯誤
        return ClaudeResponse(
            success=False,
            message="",
            error=f"呼叫 Claude CLI 時發生錯誤: {str(e)}",
        )


async def call_claude_for_summary(
    messages_to_compress: list[dict],
    timeout: int = DEFAULT_TIMEOUT,
) -> ClaudeResponse:
    """呼叫 Claude 壓縮對話歷史

    Args:
        messages_to_compress: 需要壓縮的訊息列表
        timeout: 超時秒數

    Returns:
        ClaudeResponse: 包含壓縮後的摘要
    """
    # 從資料庫讀取 summarizer prompt
    summarizer_prompt = await get_prompt_content("summarizer")
    if not summarizer_prompt:
        return ClaudeResponse(
            success=False,
            message="",
            error="找不到 summarizer prompt",
        )

    # 組合需要壓縮的對話
    conversation_parts = []
    for msg in messages_to_compress:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        conversation_parts.append(f"{role}: {content}")

    conversation_text = "\n".join(conversation_parts)

    # 建立完整 prompt
    full_prompt = f"""請將以下對話歷史壓縮成摘要：

---
{conversation_text}
---

請依照指定格式輸出摘要。"""

    return await call_claude(
        prompt=full_prompt,
        model="haiku",  # 使用較快的模型壓縮
        system_prompt=summarizer_prompt,
        timeout=timeout,
    )
