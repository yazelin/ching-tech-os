"""Claude CLI Agent 服務

使用 asyncio.subprocess 非同步呼叫 Claude CLI，
參考 jaba 專案的完整回應模式。
"""

import asyncio
from dataclasses import dataclass
from typing import Optional


# Claude CLI 超時設定（秒）
DEFAULT_TIMEOUT = 120

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


async def call_claude(
    prompt: str,
    session_id: str,
    model: str = "sonnet",
    timeout: int = DEFAULT_TIMEOUT,
) -> ClaudeResponse:
    """非同步呼叫 Claude CLI

    Args:
        prompt: 使用者訊息
        session_id: 對話 session ID（UUID）
        model: 模型名稱（opus, sonnet, haiku）
        timeout: 超時秒數

    Returns:
        ClaudeResponse: 包含成功狀態和回應訊息
    """
    # 轉換模型名稱
    cli_model = MODEL_MAP.get(model, model)

    # 建立 Claude CLI 命令
    cmd = [
        "claude",
        "-p", prompt,
        "--session-id", session_id,
        "--model", cli_model,
    ]

    try:
        # 建立非同步子程序
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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
