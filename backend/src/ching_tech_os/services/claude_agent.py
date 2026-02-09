"""Claude Agent 服務（ClaudeClient in-process 版本）

使用 claude-code-acp-py 的 ClaudeClient 連接 Claude。
保持 ClaudeResponse / ToolCall 介面不變，linebot_ai.py 無需修改。
"""

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Optional

from claude_code_acp import ClaudeClient

from ..config import settings
from . import ai_manager

logger = logging.getLogger(__name__)

# Tool 進度通知 callback 型態（保持向後相容）
ToolNotifyCallback = Callable[[str, dict], Awaitable[None]]

# 超時設定（秒）
DEFAULT_TIMEOUT = 180

# 工作目錄基底（模組級只做 base，每次 call 會建立獨立子目錄）
_WORKING_DIR_BASE = os.environ.get("CHING_TECH_WORKING_DIR", "")
if not _WORKING_DIR_BASE:
    _WORKING_DIR_BASE = tempfile.mkdtemp(prefix="ching-tech-os-cli-")
os.makedirs(_WORKING_DIR_BASE, exist_ok=True)


def _create_session_workdir() -> str:
    """為每次 AI 呼叫建立隔離的工作目錄，防止跨 session 污染"""
    session_dir = tempfile.mkdtemp(prefix="session-", dir=_WORKING_DIR_BASE)

    # 設定 nanobanana 輸出目錄（symlink 到 NAS）
    nas_ai_images_dir = f"{settings.linebot_local_path}/ai-images"
    if os.path.exists(settings.linebot_local_path):
        os.makedirs(nas_ai_images_dir, exist_ok=True)
        nanobanana_link = os.path.join(session_dir, "nanobanana-output")
        os.symlink(nas_ai_images_dir, nanobanana_link)

    # 複製 .mcp.json（唯讀副本，不可被 AI 修改原檔）
    project_mcp = os.path.join(settings.project_root, ".mcp.json")
    if os.path.exists(project_mcp):
        shutil.copy2(project_mcp, os.path.join(session_dir, ".mcp.json"))

    return session_dir


def _cleanup_session_workdir(session_dir: str) -> None:
    """清理 session 工作目錄"""
    try:
        shutil.rmtree(session_dir, ignore_errors=True)
    except OSError as e:
        logger.warning(f"清理工作目錄失敗 {session_dir}: {e}")

# 模型對應表
MODEL_MAP = {
    "claude-opus": "opus",
    "claude-sonnet": "sonnet",
    "claude-haiku": "haiku",
}


# ============================================================
# 資料類別（保持不變）
# ============================================================

@dataclass
class ToolCall:
    """工具調用記錄"""
    id: str
    name: str
    input: dict
    output: Optional[str] = None


@dataclass
class ClaudeResponse:
    """Claude CLI 回應"""
    success: bool
    message: str
    error: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    tool_timings: list[dict] = field(default_factory=list)


# ============================================================
# MCP Server 設定載入
# ============================================================

def _load_mcp_servers_from_file(path: str) -> list:
    """從 .mcp.json 載入 MCP server 設定，轉為 ACP McpServerStdio 格式"""
    if not os.path.exists(path):
        return []

    try:
        from acp.schema import McpServerStdio, EnvVariable
    except ImportError:
        logger.warning("acp.schema not available, skipping MCP server loading")
        return []

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to read MCP config {path}: {e}")
        return []

    servers = []
    for name, config in data.get("mcpServers", {}).items():
        server_type = config.get("type", "stdio")
        if server_type == "stdio":
            env_vars = []
            for k, v in config.get("env", {}).items():
                env_vars.append(EnvVariable(name=k, value=v))
            servers.append(McpServerStdio(
                name=name,
                command=config.get("command", ""),
                args=config.get("args", []),
                env=env_vars,
            ))
    return servers


def _build_mcp_servers(session_dir: str) -> list:
    """從 session 工作目錄的 .mcp.json 載入 MCP servers"""
    mcp_json_path = os.path.join(session_dir, ".mcp.json")
    return _load_mcp_servers_from_file(mcp_json_path)


# ============================================================
# Prompt 組合（保持不變）
# ============================================================

async def get_prompt_content(prompt_name: str) -> str | None:
    """從資料庫取得 prompt 內容"""
    prompt = await ai_manager.get_prompt_by_name(prompt_name)
    if prompt is None:
        return None
    return prompt.get("content")


def compose_prompt_with_history(
    history: list[dict], new_message: str, max_messages: int = 40
) -> str:
    """組合對話歷史和新訊息成完整 prompt（保持不變）"""
    recent_history = history[-max_messages:] if len(history) > max_messages else history
    parts = []

    if recent_history:
        parts.append("對話歷史：")
        parts.append("")
        for msg in recent_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            sender = msg.get("sender")
            if msg.get("is_summary"):
                continue
            if sender:
                # 清理 sender 名稱，防止 prompt injection
                safe_sender = sender.replace("\n", " ").replace("\r", " ")[:50]
                parts.append(f"{role}[{safe_sender}]: {content}")
            else:
                parts.append(f"{role}: {content}")
        parts.append("")

    parts.append(new_message)
    return "\n".join(parts)


def _clean_overgenerated_response(text: str) -> str:
    """清理 AI 過度生成的對話預測（保持不變）"""
    if not text:
        return text
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("user:") or stripped.startswith("user["):
            break
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).rstrip()


# ============================================================
# 核心 AI 呼叫
# ============================================================

async def call_claude(
    prompt: str,
    model: str = "sonnet",
    history: list[dict] | None = None,
    system_prompt: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    tools: list[str] | None = None,
    on_tool_start: ToolNotifyCallback | None = None,
    on_tool_end: ToolNotifyCallback | None = None,
) -> ClaudeResponse:
    """非同步呼叫 Claude（透過 ClaudeClient in-process）

    介面與舊版完全相同，linebot_ai.py 不需修改。

    Args:
        prompt: 使用者訊息
        model: 模型名稱（opus, sonnet, haiku）
        history: 對話歷史（可選）
        system_prompt: System prompt 內容（可選）
        timeout: 超時秒數
        tools: 允許使用的工具列表（可選）
        on_tool_start: 工具開始回調
        on_tool_end: 工具結束回調

    Returns:
        ClaudeResponse: 包含成功狀態、回應訊息、工具調用記錄和 token 統計
    """
    cli_model = MODEL_MAP.get(model, model)

    # 組合完整 prompt（包含歷史）
    if history:
        full_prompt = compose_prompt_with_history(history, prompt)
    else:
        full_prompt = prompt

    # 建立隔離的工作目錄（per-session，防止跨 session 攻擊）
    session_dir = _create_session_workdir()

    # 決定是否需要 MCP servers
    # 如果 tools 為空，不載入 MCP（避免不必要的啟動開銷）
    mcp_servers = _build_mcp_servers(session_dir) if tools else []

    # 收集回應資料
    tool_calls: list[ToolCall] = []
    tool_timings: list[dict] = []
    _active_tools: dict[str, tuple[str, float, dict]] = {}  # tool_call_id -> (name, start_time, input)

    start_time = time.time()

    # 建立 ClaudeClient（in-process，不走 subprocess）
    client = ClaudeClient(
        cwd=session_dir,
        mcp_servers=mcp_servers,
        system_prompt=system_prompt,
    )

    @client.on_tool_start
    async def handle_tool_start(tool_id: str, title: str, raw_input: dict):
        _active_tools[tool_id] = (title, time.time(), raw_input)
        if on_tool_start:
            try:
                await on_tool_start(title, raw_input)
            except (TypeError, ValueError, RuntimeError) as e:
                logger.warning(f"on_tool_start callback 失敗: {e}")

    @client.on_tool_end
    async def handle_tool_end(tool_id: str, status: str, raw_output: Any):
        tool_info = _active_tools.pop(tool_id, None)
        if tool_info is not None:
            tool_name, tool_start, tool_input = tool_info
        else:
            tool_name = ""
            tool_start = start_time
            tool_input = {}
        duration_ms = int((time.time() - tool_start) * 1000)

        output_str = str(raw_output) if raw_output else ""
        tool_calls.append(ToolCall(
            id=tool_id,
            name=tool_name,
            input=tool_input,
            output=output_str,
        ))
        tool_timings.append({"name": tool_name, "duration_ms": duration_ms})

        if on_tool_end:
            try:
                await on_tool_end(tool_name, {
                    "duration_ms": duration_ms,
                    "output": output_str,
                })
            except (TypeError, ValueError, RuntimeError) as e:
                logger.warning(f"on_tool_end callback 失敗: {e}")

    # 白名單模式 — 只允許已知安全的 MCP 工具，拒絕所有其他工具
    _ALLOWED_TOOLS = set(t.lower() for t in (tools or []))

    @client.on_permission
    async def handle_permission(name: str, raw_input: dict) -> bool:
        if name.lower() not in _ALLOWED_TOOLS:
            logger.warning(f"Permission DENIED for tool: {name} (not in whitelist)")
            return False
        return True

    try:
        # 啟動 session
        await client.start_session()

        # 設定模型（透過 session，避免環境變數並發污染）
        if cli_model and cli_model != "sonnet":
            try:
                await client.agent.set_session_model(
                    model_id=cli_model,
                    session_id=client.session_id,
                )
                logger.info(f"設定模型: {cli_model}")
            except (ValueError, RuntimeError, AttributeError) as e:
                logger.warning(f"設定模型失敗: {e}")

        # 設定 bypassPermissions
        await client.set_mode("bypassPermissions")

        # 送出 prompt（帶超時）
        try:
            text_response = await asyncio.wait_for(
                client.query(full_prompt),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"call_claude TIMEOUT after {timeout}s, collected {len(tool_calls)} tool calls")

            text_buffer = _clean_overgenerated_response(
                getattr(client, "_text_buffer", "")
            )

            error_msg = f"請求超時（{timeout} 秒）"
            if _active_tools:
                pending_names = [name for name, _, _ in _active_tools.values()]
                error_msg += f"，執行中的工具：{', '.join(pending_names)}"

            return ClaudeResponse(
                success=False,
                message=text_buffer,
                error=error_msg,
                tool_calls=tool_calls,
                input_tokens=getattr(client, "input_tokens", None),
                output_tokens=getattr(client, "output_tokens", None),
                tool_timings=tool_timings,
            )

        # 清理 text
        text_response = _clean_overgenerated_response(text_response)

        if tool_timings:
            print(f"[claude_agent] Tool 執行時間:")
            for t in tool_timings:
                print(f"  - {t['name']}: {t['duration_ms']}ms")

        return ClaudeResponse(
            success=True,
            message=text_response,
            tool_calls=tool_calls,
            input_tokens=getattr(client, "input_tokens", None),
            output_tokens=getattr(client, "output_tokens", None),
            tool_timings=tool_timings,
        )

    except (ConnectionError, OSError, RuntimeError, asyncio.CancelledError) as e:
        logger.error(f"call_claude 錯誤: {e}", exc_info=True)
        fallback_message = getattr(client, "_text_buffer", "")
        return ClaudeResponse(
            success=False,
            message=fallback_message,
            error=f"呼叫 Claude 時發生錯誤: {str(e)}",
            tool_calls=tool_calls,
            tool_timings=tool_timings,
        )
    finally:
        # 清理 per-session 工作目錄
        _cleanup_session_workdir(session_dir)


async def call_claude_for_summary(
    messages_to_compress: list[dict],
    timeout: int = DEFAULT_TIMEOUT,
) -> ClaudeResponse:
    """呼叫 Claude 壓縮對話歷史（保持不變）"""
    summarizer_prompt = await get_prompt_content("summarizer")
    if not summarizer_prompt:
        return ClaudeResponse(
            success=False,
            message="",
            error="找不到 summarizer prompt",
        )

    conversation_parts = []
    for msg in messages_to_compress:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        conversation_parts.append(f"{role}: {content}")

    conversation_text = "\n".join(conversation_parts)

    full_prompt = f"""請將以下對話歷史壓縮成摘要：

---
{conversation_text}
---

請依照指定格式輸出摘要。"""

    return await call_claude(
        prompt=full_prompt,
        model="haiku",
        system_prompt=summarizer_prompt,
        timeout=timeout,
    )
