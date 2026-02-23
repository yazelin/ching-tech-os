#!/usr/bin/env python3
"""查詢轉錄進度與狀態。"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 逾時閾值：狀態檔超過 30 分鐘未更新視為失敗
STALE_TIMEOUT_MINUTES = 30


def _get_transcriptions_base_dir() -> Path:
    """取得轉錄暫存基礎目錄。"""
    try:
        from ching_tech_os.config import settings
        ctos_mount = settings.ctos_mount_path
    except ImportError:
        ctos_mount = os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")
    return Path(ctos_mount) / "linebot" / "transcriptions"


def _find_status_file(job_id: str) -> Path | None:
    """搜尋 job_id 對應的 status.json（僅掃描最近 7 天的日期目錄）。"""
    base_dir = _get_transcriptions_base_dir()
    if not base_dir.exists():
        return None

    resolved_base = base_dir.resolve()

    count = 0
    for date_dir in sorted(base_dir.iterdir(), reverse=True):
        if not date_dir.is_dir() or len(date_dir.name) != 10:
            continue
        count += 1
        if count > 7:
            break
        status_path = date_dir / job_id / "status.json"
        # 路徑安全驗證
        try:
            status_path.resolve().relative_to(resolved_base)
        except ValueError:
            continue
        if status_path.exists():
            return status_path

    return None


# 狀態對應的中文描述
STATUS_LABELS = {
    "started": "啟動中",
    "extracting_audio": "正在提取音軌",
    "transcribing": "正在轉錄",
    "completed": "轉錄完成",
    "failed": "轉錄失敗",
}


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

    # 驗證 job_id 格式（防止路徑穿越）
    if not job_id.isalnum() or len(job_id) != 8:
        print(json.dumps({"success": False, "error": "無效的 job_id 格式"}, ensure_ascii=False))
        return 1

    # 找到狀態檔
    status_path = _find_status_file(job_id)
    if not status_path:
        print(json.dumps({"success": False, "error": "找不到轉錄任務"}, ensure_ascii=False))
        return 1

    try:
        status_data = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"無法讀取狀態檔：{exc}"}, ensure_ascii=False))
        return 1

    status = status_data.get("status", "unknown")

    # 逾時判定（轉錄中超過 30 分鐘無進度）
    if status in ("started", "extracting_audio", "transcribing"):
        updated_at = status_data.get("updated_at")
        if updated_at:
            try:
                last_update = datetime.fromisoformat(updated_at)
                elapsed = (datetime.now() - last_update).total_seconds()
                if elapsed > STALE_TIMEOUT_MINUTES * 60:
                    status_data["status"] = "failed"
                    status_data["error"] = f"轉錄逾時（超過 {STALE_TIMEOUT_MINUTES} 分鐘無進度）"
                    status = "failed"
                    # 更新狀態檔
                    status_data["updated_at"] = datetime.now().isoformat()
                    tmp_path = status_path.with_suffix(".tmp")
                    tmp_path.write_text(
                        json.dumps(status_data, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    tmp_path.replace(status_path)
            except (ValueError, TypeError):
                pass

    # 格式化回傳
    result = {
        "success": True,
        "job_id": status_data.get("job_id", job_id),
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "source_path": status_data.get("source_path", ""),
        "model": status_data.get("model", ""),
        "error": status_data.get("error"),
    }

    # 完成時附加逐字稿資訊
    if status == "completed":
        result["ctos_path"] = status_data.get("ctos_path", "")
        result["duration"] = status_data.get("duration", 0)
        result["duration_formatted"] = status_data.get("duration_formatted", "")
        result["transcript_preview"] = status_data.get("transcript_preview", "")
        # 提供絕對路徑，讓 AI 可直接用 Read 工具讀取（不需再呼叫 get_nas_file_info）
        ctos_path = status_data.get("ctos_path", "")
        if ctos_path:
            try:
                from ching_tech_os.services.path_manager import path_manager
                result["file_path"] = path_manager.to_filesystem(ctos_path)
            except Exception:
                pass

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
