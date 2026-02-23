#!/usr/bin/env python3
"""查詢影片下載進度與狀態。"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 逾時閾值：狀態檔超過 10 分鐘未更新視為失敗
STALE_TIMEOUT_MINUTES = 10


def _get_videos_base_dir() -> Path:
    """取得影片儲存基礎目錄。"""
    try:
        from ching_tech_os.config import settings
        ctos_mount = settings.ctos_mount_path
    except ImportError:
        ctos_mount = os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")
    return Path(ctos_mount) / "linebot" / "videos"


def _format_filesize(bytes_val: int | float | None) -> str:
    """將位元組格式化為可讀大小。"""
    if not bytes_val:
        return "未知"
    bytes_val = float(bytes_val)
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"


def _find_status_file(job_id: str) -> Path | None:
    """搜尋 job_id 對應的 status.json（掃描日期目錄）。"""
    base_dir = _get_videos_base_dir()
    if not base_dir.exists():
        return None

    # 先嘗試最近 7 天的目錄
    for date_dir in sorted(base_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        status_path = date_dir / job_id / "status.json"
        if status_path.exists():
            return status_path

    return None


def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"無效的輸入：{exc}"}, ensure_ascii=False))
        return 1

    job_id = payload.get("job_id", "").strip()
    if not job_id:
        print(json.dumps({"success": False, "error": "缺少 job_id 參數"}, ensure_ascii=False))
        return 1

    # 找到狀態檔
    status_path = _find_status_file(job_id)
    if not status_path:
        print(json.dumps({"success": False, "error": "找不到下載任務"}, ensure_ascii=False))
        return 1

    try:
        status_data = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"無法讀取狀態檔：{exc}"}, ensure_ascii=False))
        return 1

    # 逾時判定
    if status_data.get("status") == "downloading":
        updated_at = status_data.get("updated_at")
        if updated_at:
            try:
                last_update = datetime.fromisoformat(updated_at)
                elapsed = (datetime.now() - last_update).total_seconds()
                if elapsed > STALE_TIMEOUT_MINUTES * 60:
                    status_data["status"] = "failed"
                    status_data["error"] = f"下載逾時（超過 {STALE_TIMEOUT_MINUTES} 分鐘無進度）"
                    # 更新狀態檔
                    status_data["updated_at"] = datetime.now().isoformat()
                    status_path.write_text(
                        json.dumps(status_data, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
            except (ValueError, TypeError):
                pass

    # 格式化回傳
    result = {
        "success": True,
        "job_id": status_data.get("job_id", job_id),
        "status": status_data.get("status", "unknown"),
        "progress": status_data.get("progress", 0),
        "filename": status_data.get("filename", ""),
        "file_size": status_data.get("file_size", 0),
        "file_size_formatted": _format_filesize(status_data.get("file_size")),
        "ctos_path": status_data.get("ctos_path", ""),
        "error": status_data.get("error"),
    }

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
