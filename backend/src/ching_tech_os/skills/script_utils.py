"""Skill scripts 共用工具。"""

from __future__ import annotations

import json
import sys


def parse_stdin_json_object() -> tuple[dict | None, str | None]:
    """解析 stdin JSON 物件，回傳 (payload, error_message)。"""
    raw = sys.stdin.read().strip()
    if not raw:
        return {}, None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None, "invalid_input: 無效的 JSON 輸入"

    if not isinstance(payload, dict):
        return None, "invalid_input: input 必須是 JSON 物件"

    return payload, None
