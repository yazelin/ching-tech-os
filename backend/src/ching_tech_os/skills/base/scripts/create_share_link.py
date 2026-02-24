#!/usr/bin/env python3
"""標準化分享連結參數，交由 MCP fallback 執行。"""

import json
import sys


def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        print(json.dumps({"success": False, "error": "invalid_input: 無效的 JSON 輸入"}, ensure_ascii=False))
        return 1

    if not isinstance(payload, dict):
        print(json.dumps({"success": False, "error": "input 必須是 JSON 物件"}, ensure_ascii=False))
        return 1

    if "resource_type" not in payload or "resource_id" not in payload:
        print(json.dumps({"success": False, "error": "缺少 resource_type/resource_id"}, ensure_ascii=False))
        return 1

    payload.setdefault("expires_in", "24h")
    print(json.dumps({
        "success": False,
        "error": "fallback_required",
        "normalized_input": payload,
    }, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
