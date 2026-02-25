#!/usr/bin/env python3
"""查詢研究任務進度與結果。"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

STALE_TIMEOUT_MINUTES = 20
SEARCH_DAYS = 7

RUNNING_STATUSES = {"starting", "searching", "fetching", "synthesizing"}
STATUS_LABELS = {
    "starting": "啟動中",
    "searching": "搜尋中",
    "fetching": "擷取中",
    "synthesizing": "統整中",
    "completed": "完成",
    "failed": "失敗",
}


def _parse_stdin_json_object() -> tuple[dict | None, str | None]:
    """解析 stdin JSON 物件，回傳 (payload, error_message)。"""
    raw = sys.stdin.read().strip()
    if not raw:
        return {}, None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None, "invalid_input: 無效的 JSON 輸入"
    if not isinstance(payload, dict):
        return None, "invalid_input: input 必須是 JSON 物件"
    return payload, None


def _get_research_base_dir() -> Path:
    """取得研究任務儲存目錄。"""
    try:
        from ching_tech_os.config import settings

        ctos_mount = settings.ctos_mount_path
    except ImportError:
        ctos_mount = os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")
    return Path(ctos_mount) / "linebot" / "research"


def _write_status(status_path: Path, status_data: dict) -> None:
    """寫回狀態檔（atomic write）。"""
    status_data["updated_at"] = datetime.now().isoformat()
    tmp_path = status_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(status_data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(status_path)


def _find_status_file(job_id: str) -> Path | None:
    """搜尋 job 對應的 status.json（最近 N 天）。"""
    base_dir = _get_research_base_dir()
    if not base_dir.exists():
        return None

    resolved_base = base_dir.resolve()
    day_count = 0
    for date_dir in sorted(base_dir.iterdir(), reverse=True):
        if not date_dir.is_dir() or len(date_dir.name) != 10:
            continue
        day_count += 1
        if day_count > SEARCH_DAYS:
            break

        status_path = date_dir / job_id / "status.json"
        try:
            status_path.resolve().relative_to(resolved_base)
        except ValueError:
            continue
        if status_path.exists():
            return status_path
    return None


def _mark_stale_if_needed(status_path: Path, status_data: dict) -> dict:
    """若任務長時間無更新，標記為 failed。"""
    status = str(status_data.get("status") or "")
    if status not in RUNNING_STATUSES:
        return status_data

    updated_at = status_data.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at:
        return status_data

    try:
        elapsed = (datetime.now() - datetime.fromisoformat(updated_at)).total_seconds()
    except ValueError:
        return status_data

    if elapsed <= STALE_TIMEOUT_MINUTES * 60:
        return status_data

    status_data["status"] = "failed"
    status_data["status_label"] = "失敗"
    status_data["error"] = f"研究逾時（超過 {STALE_TIMEOUT_MINUTES} 分鐘無進度）"
    _write_status(status_path, status_data)
    return status_data


def main() -> int:
    payload, error = _parse_stdin_json_object()
    if error:
        print(json.dumps({"success": False, "error": error}, ensure_ascii=False))
        return 1
    payload = payload or {}

    job_id = str(payload.get("job_id", "")).strip()
    if not job_id:
        print(json.dumps({"success": False, "error": "缺少 job_id 參數"}, ensure_ascii=False))
        return 1
    if not job_id.isalnum() or len(job_id) != 8:
        print(json.dumps({"success": False, "error": "無效的 job_id 格式"}, ensure_ascii=False))
        return 1

    status_path = _find_status_file(job_id)
    if not status_path:
        print(json.dumps({"success": False, "error": "找不到研究任務"}, ensure_ascii=False))
        return 1

    try:
        status_data = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"success": False, "error": f"無法讀取狀態檔：{exc}"}, ensure_ascii=False))
        return 1

    if not isinstance(status_data, dict):
        print(json.dumps({"success": False, "error": "狀態檔格式錯誤"}, ensure_ascii=False))
        return 1

    status_data = _mark_stale_if_needed(status_path, status_data)
    status = str(status_data.get("status") or "unknown")

    result = {
        "success": True,
        "job_id": status_data.get("job_id", job_id),
        "status": status,
        "status_label": status_data.get("status_label") or STATUS_LABELS.get(status, status),
        "progress": status_data.get("progress", 0),
        "query": status_data.get("query", ""),
        "search_provider": status_data.get("search_provider", "none"),
        "provider_trace": status_data.get("provider_trace", []),
        "sources": status_data.get("sources", []),
        "partial_results": status_data.get("partial_results", []),
        "error": status_data.get("error"),
    }

    if status == "completed":
        result["final_summary"] = status_data.get("final_summary", "")
        result["result_ctos_path"] = status_data.get("result_ctos_path", "")
        result["result_file_path"] = status_data.get("result_file_path", "")

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
