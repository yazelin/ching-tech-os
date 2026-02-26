#!/usr/bin/env python3
"""查詢 Nginx 日誌（docker logs ching-tech-os-nginx）"""

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
    log_type = payload.get("type", "error")  # "access" 或 "error"

    try:
        # docker logs 的 stdout = access log, stderr = error log
        cmd = ["docker", "logs", "--tail", str(lines), "ching-tech-os-nginx"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )

        if log_type == "access":
            output = result.stdout or "（無 access log）"
        elif log_type == "error":
            output = result.stderr or "（無 error log）"
        else:
            # 兩者都顯示
            output = ""
            if result.stdout:
                output += f"=== Access Log ===\n{result.stdout}\n"
            if result.stderr:
                output += f"=== Error Log ===\n{result.stderr}\n"
            if not output:
                output = "（無日誌）"

        print(json.dumps({
            "success": True,
            "lines_requested": lines,
            "type": log_type,
            "output": output[:30000],
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
