#!/usr/bin/env python3
"""標準化 PDF 轉圖參數，交由 MCP fallback 執行。"""

import json
import sys


def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        print(json.dumps({"success": False, "error": "invalid_input: 無效的 JSON 輸入"}, ensure_ascii=False))
        return 1

    if not isinstance(payload, dict):
        print(json.dumps({"success": False, "error": "invalid_input: input 必須是 JSON 物件"}, ensure_ascii=False))
        return 1

    if "pdf_path" not in payload:
        print(json.dumps({"success": False, "error": "缺少 pdf_path"}, ensure_ascii=False))
        return 1

    payload.setdefault("pages", "all")
    payload.setdefault("output_format", "png")
    print(json.dumps({
        "success": False,
        "error": "fallback_required",
        "normalized_input": payload,
    }, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
