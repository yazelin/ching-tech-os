#!/usr/bin/env python3
"""查詢 Nginx 日誌（docker logs ching-tech-os-nginx）"""

import json
import subprocess

from ching_tech_os.skills.script_utils import parse_stdin_json_object

# 允許的 log_type 白名單
_VALID_LOG_TYPES = {"access", "error"}


def _safe_int(value, default: int, min_val: int = 1, max_val: int = 500) -> int:
    """安全的整數轉換，帶範圍限制"""
    try:
        return max(min_val, min(int(value), max_val))
    except (ValueError, TypeError):
        return default


def main() -> int:
    payload, error = parse_stdin_json_object()
    if error:
        print(json.dumps({"success": False, "error": error}, ensure_ascii=False))
        return 1
    payload = payload or {}

    lines = _safe_int(payload.get("lines", 50), default=50, max_val=500)
    log_type = payload.get("type", "error")
    # 白名單驗證：非法值預設為 error
    if log_type not in _VALID_LOG_TYPES:
        log_type = "error"

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
        else:
            output = result.stderr or "（無 error log）"

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
    except Exception:
        print(json.dumps({"success": False, "error": "查詢 Nginx 日誌失敗"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
