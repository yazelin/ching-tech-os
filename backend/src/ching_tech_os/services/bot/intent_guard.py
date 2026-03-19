"""Intent Guard（意圖守門員）

輕量前置過濾器，使用 Haiku 快速判斷用戶意圖，
決定放行或拒絕。各產業模組可自訂過濾規則。

架構：用戶訊息 → Rate Limiter → Intent Guard (Haiku) → 主 Agent (Sonnet/Opus)

設計原則：
- fail-open：Guard 失敗不阻擋正常訊息
- 只有設定了 intent_guard 規則的 Agent 才會觸發
- 全域開關 INTENT_GUARD_ENABLED + Agent 級 enabled 雙重控制
- 優先用 Anthropic SDK 直接呼叫（快），無 API Key 時 fallback 到 call_claude（慢）
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass

from ...config import settings

logger = logging.getLogger(__name__)

# Haiku 模型 ID（Anthropic SDK 用）
_HAIKU_MODEL = "claude-haiku-4-5-20251001"

# Anthropic SDK 惰性單例（有 API Key 時使用）
_client = None
# 是否有 API Key（啟動時判斷一次）
_has_api_key: bool | None = None


def _get_client():
    """取得 Anthropic AsyncClient 惰性單例

    使用 ANTHROPIC_API_KEY 環境變數。
    若無 API Key，回傳 None（由呼叫端 fallback 到 call_claude）。
    """
    global _client, _has_api_key

    if _has_api_key is None:
        _has_api_key = bool(os.getenv("ANTHROPIC_API_KEY"))

    if not _has_api_key:
        return None

    if _client is None:
        from anthropic import AsyncAnthropic
        _client = AsyncAnthropic()

    return _client


@dataclass
class IntentGuardResult:
    """意圖守門員判定結果

    action:
      - "allow": 放行，進入主 Agent
      - "reject": 拒絕，直接回覆 reject_message
      - "direct": 直接回應，不進主 Agent（由 Haiku 產生回覆）
    """

    action: str  # "allow" / "reject" / "direct"
    reason: str | None = None  # 判定原因
    reject_message: str | None = None  # reject 時回覆給用戶的訊息
    direct_response: str | None = None  # direct 時直接回覆的內容
    duration_ms: int = 0  # 處理耗時（毫秒）


def _quick_keyword_match(
    message: str, rules: dict
) -> IntentGuardResult | None:
    """關鍵字快速匹配（不需 AI）

    Args:
        message: 用戶訊息（原始文字）
        rules: intent_guard 設定

    Returns:
        匹配結果，或 None 表示需要 AI 判斷
    """
    message_lower = message.lower()

    # allow_keywords 優先：命中即放行
    allow_keywords = rules.get("allow_keywords") or []
    for kw in allow_keywords:
        if kw.lower() in message_lower:
            return IntentGuardResult(action="allow", reason=f"allow_keyword: {kw}")

    # block_keywords：命中即拒絕
    block_keywords = rules.get("block_keywords") or []
    for kw in block_keywords:
        if kw.lower() in message_lower:
            reject_message = rules.get(
                "reject_message", "抱歉，我無法回答這個問題。"
            )
            return IntentGuardResult(
                action="reject",
                reason=f"block_keyword: {kw}",
                reject_message=reject_message,
            )

    return None


def _build_guard_prompt(rules: dict, user_message: str) -> tuple[str, str]:
    """組裝 Intent Guard 的 system prompt 和 user message

    Returns:
        (system_prompt, user_prompt)
    """
    description = rules.get("description", "AI 助手")
    allowed_topics = rules.get("allowed_topics") or []
    blocked_topics = rules.get("blocked_topics") or []
    examples = rules.get("examples") or []

    # 是否啟用 direct 模式
    direct_rules = rules.get("direct_rules") or []

    system_parts = [
        f"你是一個意圖分類器，負責判斷用戶訊息是否屬於「{description}」的服務範圍。",
        "",
        "## 規則",
        "- 只回傳 JSON，不要有其他文字",
        '- 允許的訊息回傳：{{"action": "allow"}}',
        '- 不允許的訊息回傳：{{"action": "reject", "reason": "簡短原因"}}',
    ]

    if direct_rules:
        system_parts.append(
            '- 可直接回答的簡單問題回傳：{{"action": "direct", "response": "回覆內容"}}'
        )

    system_parts.extend([
        "- 禮貌問候（如「你好」「謝謝」）一律允許",
        "- 不確定時傾向允許（寧可放行也不要誤擋）",
    ])

    if allowed_topics:
        system_parts.append("")
        system_parts.append("## 允許的主題")
        for topic in allowed_topics:
            system_parts.append(f"- {topic}")

    if blocked_topics:
        system_parts.append("")
        system_parts.append("## 不允許的主題")
        for topic in blocked_topics:
            system_parts.append(f"- {topic}")

    if direct_rules:
        system_parts.append("")
        system_parts.append("## 可直接回答的情境（不需進入主 Agent）")
        for dr in direct_rules:
            system_parts.append(f"- {dr}")

    if examples:
        system_parts.append("")
        system_parts.append("## 範例")
        for ex in examples:
            action = ex.get("action", "allow")
            reason = ex.get("reason", "")
            response = ex.get("response", "")
            msg = ex.get("message", "")
            if action == "allow":
                system_parts.append(f'- 「{msg}」→ {{"action": "allow"}}')
            elif action == "direct":
                system_parts.append(
                    f'- 「{msg}」→ {{"action": "direct", "response": "{response}"}}'
                )
            else:
                system_parts.append(
                    f'- 「{msg}」→ {{"action": "reject", "reason": "{reason}"}}'
                )

    system_prompt = "\n".join(system_parts)
    user_prompt = f"用戶訊息：{user_message}"

    return system_prompt, user_prompt


def _parse_guard_response(raw_text: str) -> dict | None:
    """從 AI 回應文字中解析 JSON

    Returns:
        解析後的 dict，或 None
    """
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # 回應可能包含多餘文字，嘗試提取 JSON
    json_match = re.search(r'\{[^}]+\}', raw_text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None


def _build_result_from_parsed(
    result: dict, reject_message: str, duration_ms: int
) -> IntentGuardResult:
    """從解析後的 JSON 建構 IntentGuardResult"""
    action = result.get("action", "allow")

    if action == "reject":
        return IntentGuardResult(
            action="reject",
            reason=result.get("reason", ""),
            reject_message=reject_message,
            duration_ms=duration_ms,
        )

    if action == "direct":
        direct_resp = result.get("response", "")
        if direct_resp:
            return IntentGuardResult(
                action="direct",
                reason=result.get("reason", "direct_response"),
                direct_response=direct_resp,
                duration_ms=duration_ms,
            )
        logger.warning("Intent Guard direct 但無 response，fallback allow")

    return IntentGuardResult(
        action="allow",
        reason=result.get("reason"),
        duration_ms=duration_ms,
    )


async def _call_via_sdk(
    system_prompt: str, user_prompt: str, timeout: int
) -> str:
    """透過 Anthropic SDK 呼叫 Haiku（快，~1 秒）"""
    client = _get_client()
    response = await client.messages.create(
        model=_HAIKU_MODEL,
        max_tokens=150,
        timeout=timeout,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()


async def _call_via_cli(
    system_prompt: str, user_prompt: str, timeout: int
) -> str:
    """透過 call_claude CLI 呼叫 Haiku（慢，需啟動 session）"""
    from ..claude_agent import call_claude

    response = await call_claude(
        prompt=user_prompt,
        model="haiku",
        system_prompt=system_prompt,
        timeout=timeout,
        tools=[],
    )
    if not response.success:
        raise RuntimeError(f"call_claude failed: {response.message[:200]}")
    return response.message.strip()


async def check_intent(
    user_message: str, agent: dict | None
) -> IntentGuardResult:
    """檢查用戶意圖，決定放行或拒絕

    優先用 Anthropic SDK（需 ANTHROPIC_API_KEY），
    無 API Key 時 fallback 到 call_claude（走 CLI）。

    Args:
        user_message: 用戶訊息內容
        agent: Agent 字典（含 settings 欄位）

    Returns:
        IntentGuardResult
    """
    start_time = time.time()

    # 1. 全域開關
    if not settings.intent_guard_enabled:
        return IntentGuardResult(action="allow", reason="global_disabled")

    # 2. 檢查 Agent settings 中有無 intent_guard 設定
    if not agent:
        return IntentGuardResult(action="allow", reason="no_agent")

    agent_settings = agent.get("settings") or {}
    rules = agent_settings.get("intent_guard")
    if not rules:
        return IntentGuardResult(action="allow", reason="no_rules")

    # 3. 檢查 Agent 級 enabled
    if not rules.get("enabled", False):
        return IntentGuardResult(action="allow", reason="agent_disabled")

    # 4. 短訊息跳過
    min_length = rules.get("min_check_length", 2)
    if len(user_message.strip()) < min_length:
        return IntentGuardResult(action="allow", reason="too_short")

    # 5. 關鍵字快速匹配
    keyword_result = _quick_keyword_match(user_message, rules)
    if keyword_result is not None:
        keyword_result.duration_ms = int((time.time() - start_time) * 1000)
        return keyword_result

    # 6. 呼叫 Haiku AI 分類
    timeout = rules.get("timeout", 15)
    reject_message = rules.get("reject_message", "抱歉，我無法回答這個問題。")

    try:
        system_prompt, user_prompt = _build_guard_prompt(rules, user_message)

        # 優先用 SDK（快），無 API Key 時 fallback 到 CLI
        use_sdk = _get_client() is not None
        if use_sdk:
            raw_text = await _call_via_sdk(system_prompt, user_prompt, timeout)
            method = "sdk"
        else:
            raw_text = await _call_via_cli(system_prompt, user_prompt, timeout)
            method = "cli"

        duration_ms = int((time.time() - start_time) * 1000)

        result = _parse_guard_response(raw_text)
        if not result:
            logger.warning(
                "Intent Guard 回應非 JSON (%s): %s (duration=%dms)",
                method,
                raw_text[:200],
                duration_ms,
            )
            return IntentGuardResult(
                action="allow", reason="invalid_json", duration_ms=duration_ms
            )

        return _build_result_from_parsed(result, reject_message, duration_ms)

    except TimeoutError:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.warning("Intent Guard 超時 (duration=%dms)", duration_ms)
        return IntentGuardResult(
            action="allow", reason="timeout", duration_ms=duration_ms
        )

    except Exception:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.exception("Intent Guard 錯誤 (duration=%dms)", duration_ms)
        return IntentGuardResult(
            action="allow", reason="error", duration_ms=duration_ms
        )
