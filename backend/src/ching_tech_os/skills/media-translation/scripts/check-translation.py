"""查詢翻譯進度與狀態。"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

STALE_TIMEOUT_MINUTES = 30

STATUS_LABELS = {
    "starting": "準備中",
    "reading": "讀取來源中",
    "translating": "翻譯中",
    "completed": "完成",
    "failed": "失敗",
}


def _get_ctos_mount_path() -> str:
    return os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")


def _find_status_file(job_id: str) -> Path | None:
    """搜尋最近 7 天的日期目錄找 status.json"""
    base = Path(_get_ctos_mount_path()) / "linebot" / "translations"
    if not base.exists():
        return None

    resolved_base = base.resolve()
    today = datetime.now()

    for days_ago in range(7):
        date_str = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        date_dir = base / date_str
        if not date_dir.is_dir():
            continue
        status_path = date_dir / job_id / "status.json"
        if not status_path.exists():
            continue
        # 路徑安全驗證
        try:
            status_path.resolve().relative_to(resolved_base)
        except ValueError:
            continue
        return status_path

    return None


def main() -> int:
    payload = json.loads(sys.stdin.read())
    job_id = payload.get("job_id", "").strip()

    if not job_id or not job_id.isalnum() or len(job_id) != 8:
        print(json.dumps({
            "success": False,
            "error": "無效的 job_id（需為 8 位英數字元）",
        }, ensure_ascii=False))
        return 1

    status_path = _find_status_file(job_id)
    if not status_path:
        print(json.dumps({
            "success": False,
            "error": f"找不到翻譯任務：{job_id}",
        }, ensure_ascii=False))
        return 1

    try:
        status_data = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"讀取狀態失敗：{e}",
        }, ensure_ascii=False))
        return 1

    status = status_data.get("status", "unknown")

    # 逾時判定
    if status in ("starting", "reading", "translating"):
        updated_at = status_data.get("updated_at", "")
        if updated_at:
            try:
                last_update = datetime.fromisoformat(updated_at)
                elapsed = (datetime.now() - last_update).total_seconds()
                if elapsed > STALE_TIMEOUT_MINUTES * 60:
                    status_data["status"] = "failed"
                    status_data["error"] = f"逾時：超過 {STALE_TIMEOUT_MINUTES} 分鐘無更新"
                    status = "failed"
            except Exception:
                pass

    status_label = STATUS_LABELS.get(status, status)
    result = {
        "success": True,
        "job_id": job_id,
        "status": status,
        "status_label": status_label,
        "progress": status_data.get("progress", ""),
        "target_language": status_data.get("target_language", ""),
        "model": status_data.get("model", ""),
        "source_filename": status_data.get("source_filename", ""),
        "warnings": status_data.get("warnings", []),
        "error": status_data.get("error"),
    }

    if status == "completed":
        ctos_path = status_data.get("ctos_path", "")
        result["ctos_path"] = ctos_path

        # 解析 file_path（絕對路徑）
        output_path = status_data.get("output_path", "")
        if output_path and Path(output_path).exists():
            result["file_path"] = output_path
        elif ctos_path:
            # 從 ctos_path 推算
            ctos_mount = _get_ctos_mount_path()
            if ctos_path.startswith("ctos://"):
                fs_path = Path(ctos_mount) / ctos_path[len("ctos://"):]
                if fs_path.exists():
                    result["file_path"] = str(fs_path)

    if status == "failed":
        result["error"] = status_data.get("error", "未知錯誤")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
