#!/usr/bin/env python3
"""綜合系統健康檢查 - 一次跑完所有診斷項目，回傳摘要報告"""

import json
import subprocess

from ching_tech_os.skills.script_utils import parse_stdin_json_object


def _run_cmd(cmd: list[str], timeout: int = 10) -> tuple[str, bool]:
    """執行指令，回傳 (輸出, 是否成功)"""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        output = (result.stdout or "") + (result.stderr or "")
        return output.strip(), result.returncode == 0
    except subprocess.TimeoutExpired:
        return "（指令逾時）", False
    except Exception:
        return "（指令執行失敗）", False


def _run_sql(sql: str) -> tuple[str, bool]:
    """執行 SQL 查詢"""
    return _run_cmd([
        "docker", "exec", "ching-tech-os-db",
        "psql", "-U", "ching_tech", "-d", "ching_tech_os",
        "-t", "-c", sql,
    ])


def main() -> int:
    payload, error = parse_stdin_json_object()
    if error:
        print(json.dumps({"success": False, "error": error}, ensure_ascii=False))
        return 1

    checks = []
    overall_status = "正常"

    # 1. CTOS 服務狀態
    output, ok = _run_cmd(["systemctl", "is-active", "ching-tech-os"])
    status = "正常" if ok and "active" in output else "異常"
    checks.append({"name": "CTOS 服務", "status": status, "detail": output[:200]})
    if status == "異常":
        overall_status = "嚴重"

    # 2. CTOS 最近錯誤日誌（僅查 24 小時內）
    output, ok = _run_cmd([
        "journalctl", "-u", "ching-tech-os", "-n", "20",
        "--no-pager", "-p", "err", "--since", "24 hours ago",
    ])
    # journalctl 沒有錯誤時會輸出 "-- No entries --"，需排除
    stripped = output.strip()
    if not stripped or stripped == "-- No entries --":
        error_count = 0
    else:
        error_count = len(stripped.splitlines())
    if error_count > 10:
        status = "警告"
        if overall_status == "正常":
            overall_status = "注意"
    elif error_count > 0:
        status = "注意"
        if overall_status == "正常":
            overall_status = "注意"
    else:
        status = "正常"
    checks.append({
        "name": "CTOS 錯誤日誌（24h 內）",
        "status": status,
        "detail": f"最近 24 小時錯誤日誌：{error_count} 行\n{output[:500]}" if error_count > 0 else "最近 24 小時無錯誤日誌",
    })

    # 3. Docker 容器狀態
    output, ok = _run_cmd(["docker", "ps", "--format", "{{.Names}}: {{.Status}}"])
    container_issues = []
    for line in output.splitlines():
        if line and "Up" not in line:
            container_issues.append(line)
    if container_issues:
        status = "警告"
        if overall_status in ("正常", "注意"):
            overall_status = "警告"
    else:
        status = "正常"
    checks.append({
        "name": "Docker 容器",
        "status": status,
        "detail": output[:500] if output else "（無法查詢 Docker 狀態）",
    })

    # 4. 資料庫連線
    output, ok = _run_sql(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = 'ching_tech_os'"
    )
    db_conn_count = output.strip() if ok else "N/A"
    status = "正常"
    try:
        if ok and int(db_conn_count) > 80:
            status = "警告"
            if overall_status in ("正常", "注意"):
                overall_status = "警告"
    except ValueError:
        pass
    checks.append({
        "name": "資料庫連線數",
        "status": status,
        "detail": f"目前連線數: {db_conn_count}",
    })

    # 5. 資料庫大小
    output, ok = _run_sql(
        "SELECT pg_size_pretty(pg_database_size('ching_tech_os'))"
    )
    checks.append({
        "name": "資料庫大小",
        "status": "正常",
        "detail": f"大小: {output.strip()}" if ok else "無法查詢",
    })

    # 6. AI logs 最近失敗
    output, ok = _run_sql(
        "SELECT count(*) FROM ai_logs "
        "WHERE success = false AND created_at > NOW() - INTERVAL '1 hour'"
    )
    ai_errors = output.strip() if ok else "N/A"
    try:
        if ok and int(ai_errors) > 5:
            status = "注意"
            if overall_status == "正常":
                overall_status = "注意"
        else:
            status = "正常"
    except ValueError:
        status = "正常"
    checks.append({
        "name": "AI 失敗記錄（1 小時內）",
        "status": status,
        "detail": f"失敗次數: {ai_errors}",
    })

    # 7. Nginx 狀態（嘗試常見容器名稱）
    output, ok = _run_cmd([
        "docker", "inspect", "--format", "{{.State.Status}}", "nginx"
    ])
    if not ok:
        output, ok = _run_cmd([
            "docker", "inspect", "--format", "{{.State.Status}}", "ching-tech-os-nginx"
        ])
    nginx_status = output.strip() if ok else "未知"
    status = "正常" if nginx_status == "running" else "異常"
    if status == "異常" and overall_status != "嚴重":
        overall_status = "警告"
    checks.append({
        "name": "Nginx",
        "status": status,
        "detail": f"容器狀態: {nginx_status}",
    })

    # 組裝報告
    report_lines = [f"整體狀態: {overall_status}", ""]
    for check in checks:
        icon = {"正常": "✅", "注意": "⚠️", "警告": "🔶", "異常": "❌"}.get(
            check["status"], "❓"
        )
        report_lines.append(f"{icon} {check['name']}: {check['status']}")
        if check.get("detail"):
            # 縮排細節
            for detail_line in check["detail"].splitlines()[:5]:
                report_lines.append(f"   {detail_line}")
        report_lines.append("")

    print(json.dumps({
        "success": True,
        "overall_status": overall_status,
        "checks_count": len(checks),
        "output": "\n".join(report_lines)[:30000],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
