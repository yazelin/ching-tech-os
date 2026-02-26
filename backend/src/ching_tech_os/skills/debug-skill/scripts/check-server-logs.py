#!/usr/bin/env python3
"""查詢 CTOS 伺服器日誌（journalctl -u ching-tech-os）"""

import json
import subprocess

from ching_tech_os.skills.script_utils import parse_stdin_json_object


def main() -> int:
    payload, error = parse_stdin_json_object()
    if error:
        print(json.dumps({"success": False, "error": error}, ensure_ascii=False))
        return 1
    payload = payload or {}

    lines = min(int(payload.get("lines", 50)), 500)  # 最多 500 行
    keyword = payload.get("keyword", "")

    try:
        cmd = ["journalctl", "-u", "ching-tech-os", "-n", str(lines), "--no-pager"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )

        output = result.stdout or ""
        if result.returncode != 0 and result.stderr:
            output += f"\n[stderr] {result.stderr}"

        # 關鍵字過濾
        if keyword and output:
            filtered = [
                line for line in output.splitlines()
                if keyword.lower() in line.lower()
            ]
            output = "\n".join(filtered)
            if not filtered:
                output = f"（未找到包含 '{keyword}' 的日誌行）"

        print(json.dumps({
            "success": True,
            "lines_requested": lines,
            "keyword": keyword or None,
            "output": output[:30000],  # 限制輸出大小
        }, ensure_ascii=False))
        return 0

    except subprocess.TimeoutExpired:
        print(json.dumps({"success": False, "error": "指令執行逾時"}, ensure_ascii=False))
        return 1
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
