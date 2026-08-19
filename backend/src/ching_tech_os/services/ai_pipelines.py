"""Provider-neutral 特殊 pipeline 呼叫（add-codex-pipeline-parity）。

每個 pipeline 通過 parity tests 後才由 `call_claude()` 遷移至此，
以 `call_ai()` + 專屬 RoutingContext 呼叫；canary 由設定控制，預設仍為 Claude。
"""

from __future__ import annotations

from .ai_provider import AIResponse, DEFAULT_TIMEOUT
from .ai_router import RoutingContext, call_ai
from .claude_agent import get_prompt_content


async def summarize_messages(
    messages_to_compress: list[dict],
    timeout: int = DEFAULT_TIMEOUT,
) -> AIResponse:
    """壓縮對話歷史成摘要（3.1：summary pipeline，純文字契約）。"""
    summarizer_prompt = await get_prompt_content("summarizer")
    if not summarizer_prompt:
        return AIResponse(
            success=False,
            message="",
            error="找不到 summarizer prompt",
            provider="claude",
            actual_model="haiku",
            route_reason="direct_claude",
            provider_started=False,
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

    return await call_ai(
        prompt=full_prompt,
        model="haiku",
        system_prompt=summarizer_prompt,
        timeout=timeout,
        routing_context=RoutingContext(context_type="compress"),
    )
