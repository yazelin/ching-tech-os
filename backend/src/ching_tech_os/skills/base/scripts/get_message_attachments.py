#!/usr/bin/env python3
"""標準化附件查詢參數，交由 MCP fallback 執行。"""

import json

from ching_tech_os.skills.script_utils import parse_stdin_json_object


def main() -> int:
    payload, error = parse_stdin_json_object()
    if error:
        print(json.dumps({"success": False, "error": error}, ensure_ascii=False))
        return 1
    payload = payload or {}

    payload.setdefault("days", 3)
    print(json.dumps({
        "success": False,
        "error": "fallback_required",
        "normalized_input": payload,
    }, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
