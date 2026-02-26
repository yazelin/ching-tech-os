#!/usr/bin/env python3
"""查詢資料庫狀態（連線數、主要資料表行數、資料庫大小）"""

import json
import subprocess

from ching_tech_os.skills.script_utils import parse_stdin_json_object


def _run_sql(sql: str, timeout: int = 10) -> str:
    """執行 SQL 並回傳結果"""
    result = subprocess.run(
        [
            "docker", "exec", "ching-tech-os-db",
            "psql", "-U", "ching_tech", "-d", "ching_tech_os",
            "-c", sql,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout or result.stderr or ""


def main() -> int:
    payload, error = parse_stdin_json_object()
    if error:
        print(json.dumps({"success": False, "error": error}, ensure_ascii=False))
        return 1

    try:
        sections = []

        # 1. 資料庫大小
        db_size = _run_sql(
            "SELECT pg_size_pretty(pg_database_size('ching_tech_os')) as db_size;"
        )
        sections.append(f"=== 資料庫大小 ===\n{db_size}")

        # 2. 連線數
        connections = _run_sql(
            "SELECT state, count(*) FROM pg_stat_activity "
            "WHERE datname = 'ching_tech_os' GROUP BY state ORDER BY count DESC;"
        )
        sections.append(f"=== 連線狀態 ===\n{connections}")

        # 3. 主要資料表行數
        table_counts = _run_sql(
            "SELECT relname as table_name, n_live_tup as row_count "
            "FROM pg_stat_user_tables "
            "WHERE schemaname = 'public' "
            "ORDER BY n_live_tup DESC LIMIT 20;"
        )
        sections.append(f"=== 資料表行數（前 20）===\n{table_counts}")

        # 4. 資料表大小
        table_sizes = _run_sql(
            "SELECT tablename, "
            "pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) as size "
            "FROM pg_tables WHERE schemaname = 'public' "
            "ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC LIMIT 10;"
        )
        sections.append(f"=== 資料表大小（前 10）===\n{table_sizes}")

        output = "\n".join(sections)

        print(json.dumps({
            "success": True,
            "output": output[:30000],
        }, ensure_ascii=False))
        return 0

    except subprocess.TimeoutExpired:
        print(json.dumps({"success": False, "error": "指令執行逾時"}, ensure_ascii=False))
        return 1
    except Exception:
        print(json.dumps({"success": False, "error": "查詢資料庫狀態失敗"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
