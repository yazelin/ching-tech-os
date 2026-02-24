#!/usr/bin/env python3
"""標準化分享連結參數，交由 MCP fallback 執行。"""

import json

from ching_tech_os.skills.script_utils import parse_stdin_json_object


def main() -> int:
    payload, error = parse_stdin_json_object()
    if error:
        print(json.dumps({"success": False, "error": error}, ensure_ascii=False))
        return 1
    payload = payload or {}

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
