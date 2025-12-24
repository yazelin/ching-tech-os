"""Claude CLI Agent 服務

使用 asyncio.subprocess 非同步呼叫 Claude CLI。
自己管理對話歷史，不依賴 CLI session。
"""

import asyncio
import os
import shutil
from dataclasses import dataclass
from typing import Optional

from . import ai_manager


# Claude CLI 超時設定（秒）
DEFAULT_TIMEOUT = 120

# 工作目錄（使用獨立目錄，避免讀取專案的 CLAUDE.md）
WORKING_DIR = "/tmp/ching-tech-os-cli"
os.makedirs(WORKING_DIR, exist_ok=True)

# 複製 MCP 配置到工作目錄
PROJECT_ROOT = "/home/ct/SDD/ching-tech-os"
_mcp_src = os.path.join(PROJECT_ROOT, ".mcp.json")
_mcp_dst = os.path.join(WORKING_DIR, ".mcp.json")
if os.path.exists(_mcp_src):
    shutil.copy2(_mcp_src, _mcp_dst)


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
class ClaudeResponse:
    """Claude CLI 回應"""

    success: bool
    message: str
    error: Optional[str] = None


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
            # 跳過摘要訊息（它會在 system prompt 中處理）
            if msg.get("is_summary"):
                continue
            parts.append(f"{role}: {content}")
        parts.append("")

    # 加入新訊息
    parts.append(f"user: {new_message}")

    return "\n".join(parts)


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
        ClaudeResponse: 包含成功狀態和回應訊息
    """
    # 轉換模型名稱
    cli_model = MODEL_MAP.get(model, model)

    # 組合完整 prompt（包含歷史）
    if history:
        full_prompt = compose_prompt_with_history(history, prompt)
    else:
        full_prompt = prompt

    # 建立 Claude CLI 命令（不使用 session）
    # 注意：-p 是獨立 flag，prompt 必須放在所有選項之後
    cmd = [CLAUDE_PATH, "-p", "--model", cli_model]

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

    try:
        # 建立非同步子程序（使用獨立工作目錄，避免讀取專案的 CLAUDE.md）
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=WORKING_DIR,
        )

        # 等待完成（含超時）
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )

        stdout = stdout_bytes.decode("utf-8").strip()
        stderr = stderr_bytes.decode("utf-8").strip()

        # 檢查執行結果
        if proc.returncode != 0:
            error_msg = stderr or f"Claude CLI 執行失敗 (code: {proc.returncode})"
            return ClaudeResponse(
                success=False,
                message="",
                error=error_msg,
            )

        return ClaudeResponse(
            success=True,
            message=stdout,
        )

    except asyncio.TimeoutError:
        # 超時處理
        return ClaudeResponse(
            success=False,
            message="",
            error=f"請求超時（{timeout} 秒）",
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
