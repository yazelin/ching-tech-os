#!/usr/bin/env python3
"""查詢 AI 對話記錄（ai_logs 資料表）"""

import json
import subprocess

from ching_tech_os.skills.script_utils import parse_stdin_json_object


def main() -> int:
    payload, error = parse_stdin_json_object()
    if error:
        print(json.dumps({"success": False, "error": error}, ensure_ascii=False))
        return 1
    payload = payload or {}

    limit = min(int(payload.get("limit", 10)), 50)  # 最多 50 筆
    errors_only = payload.get("errors_only", False)

    # 建構 SQL 查詢
    where_clause = "WHERE success = false" if errors_only else ""
    sql = (
        f"SELECT id, context_type, model, success, duration_ms, "
        f"error_message, created_at "
        f"FROM ai_logs {where_clause} "
        f"ORDER BY created_at DESC LIMIT {limit}"
    )

    try:
        cmd = [
            "docker", "exec", "ching-tech-os-db",
            "psql", "-U", "ching_tech", "-d", "ching_tech_os",
            "-c", sql,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )

        output = result.stdout or ""
        if result.returncode != 0 and result.stderr:
            output += f"\n[stderr] {result.stderr}"

        print(json.dumps({
            "success": True,
            "limit": limit,
            "errors_only": errors_only,
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
