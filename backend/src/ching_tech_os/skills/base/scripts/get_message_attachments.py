#!/usr/bin/env python3
"""標準化附件查詢參數，交由 MCP fallback 執行。"""

import json
import sys


def main() -> int:
    raw = sys.stdin.read().strip()
    payload = {}
    if raw:
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("input 必須是 JSON 物件")
        except Exception as exc:
            print(json.dumps({"success": False, "error": f"invalid_input: {exc}"}, ensure_ascii=False))
            return 1

    payload.setdefault("days", 3)
    print(json.dumps({
        "success": False,
        "error": "fallback_required",
        "normalized_input": payload,
    }, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
