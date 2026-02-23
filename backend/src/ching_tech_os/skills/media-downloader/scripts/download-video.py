#!/usr/bin/env python3
"""非同步影片下載：立即回傳 job ID，背景程序執行下載。"""

import json
import os
import sys
import time
import uuid as uuid_module
from datetime import datetime
from pathlib import Path


# 最大檔案大小 500 MB
MAX_FILESIZE_BYTES = 500 * 1024 * 1024

# 進度更新間隔
PROGRESS_UPDATE_INTERVAL_SEC = 5
PROGRESS_UPDATE_INTERVAL_PCT = 5.0


def _get_videos_base_dir() -> Path:
    """取得影片儲存基礎目錄。"""
    try:
        from ching_tech_os.config import settings
        ctos_mount = settings.ctos_mount_path
    except ImportError:
        ctos_mount = os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")
    return Path(ctos_mount) / "linebot" / "videos"


def _write_status(status_path: Path, data: dict) -> None:
    """寫入狀態檔。"""
    data["updated_at"] = datetime.now().isoformat()
    tmp_path = status_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(status_path)


def _do_download(job_dir: Path, status_path: Path, url: str, fmt: str, job_id: str) -> None:
    """背景程序：執行實際下載。"""
    import yt_dlp

    last_update_time = 0.0
    last_update_pct = 0.0
    size_exceeded = False  # flag：大小超限時由外層處理

    status_data = {
        "job_id": job_id,
        "status": "downloading",
        "progress": 0.0,
        "filename": "",
        "file_size": 0,
        "ctos_path": "",
        "error": None,
        "created_at": datetime.now().isoformat(),
    }
    _write_status(status_path, status_data)

    def progress_hook(d: dict) -> None:
        nonlocal last_update_time, last_update_pct, size_exceeded

        if d.get("status") == "downloading":
            now = time.monotonic()
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            pct = (downloaded / total * 100) if total > 0 else 0.0

            # 標記大小超限（由 yt-dlp 的 max_filesize 選項實際中止）
            if total > MAX_FILESIZE_BYTES:
                size_exceeded = True

            # 節流：每 5 秒或每 5% 更新
            time_diff = now - last_update_time
            pct_diff = pct - last_update_pct
            if time_diff >= PROGRESS_UPDATE_INTERVAL_SEC or pct_diff >= PROGRESS_UPDATE_INTERVAL_PCT:
                last_update_time = now
                last_update_pct = pct
                status_data["progress"] = round(pct, 1)
                status_data["file_size"] = downloaded
                if d.get("filename"):
                    status_data["filename"] = Path(d["filename"]).name
                _write_status(status_path, status_data)

        elif d.get("status") == "finished":
            if d.get("filename"):
                status_data["filename"] = Path(d["filename"]).name
            status_data["progress"] = 100.0

    # yt-dlp 選項
    output_template = str(job_dir / "%(title)s.%(ext)s")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
        "outtmpl": output_template,
        "progress_hooks": [progress_hook],
        "max_filesize": MAX_FILESIZE_BYTES,
    }

    # 檢查 ffmpeg 是否可用
    import shutil
    has_ffmpeg = shutil.which("ffmpeg") is not None

    # 格式選擇
    if fmt == "mp3":
        if not has_ffmpeg:
            # 無 ffmpeg 時下載最佳音訊（不轉碼）
            ydl_opts["format"] = "bestaudio/best"
        else:
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
    elif fmt == "best":
        if has_ffmpeg:
            ydl_opts["format"] = "bestvideo+bestaudio/best"
        else:
            # 無 ffmpeg 時選擇已合併的最佳格式
            ydl_opts["format"] = "best"
    else:
        # 預設 mp4
        if has_ffmpeg:
            ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            ydl_opts["merge_output_format"] = "mp4"
        else:
            # 無 ffmpeg 時選擇已合併的 mp4 格式
            ydl_opts["format"] = "best[ext=mp4]/best"

    # 追蹤 yt-dlp 回報的最終檔名
    final_filename: list[str] = []

    def postprocess_hook(d: dict) -> None:
        """追蹤後處理完成後的最終檔名。"""
        if d.get("status") == "finished" and d.get("info_dict", {}).get("filepath"):
            final_filename.append(d["info_dict"]["filepath"])

    ydl_opts["postprocessor_hooks"] = [postprocess_hook]

    # 不需要排除的輔助檔案
    _SKIP_FILES = {"status.json", "error.log"}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # 大小超限：清理並回報失敗
        if size_exceeded:
            for f in job_dir.iterdir():
                if f.is_file() and f.name not in _SKIP_FILES:
                    f.unlink(missing_ok=True)
            status_data["status"] = "failed"
            status_data["error"] = "檔案超過 500 MB 限制"
            _write_status(status_path, status_data)
            return

        # 優先使用 yt-dlp 回報的最終檔名，否則掃描目錄
        target_file = None
        if final_filename:
            candidate = Path(final_filename[-1])
            if candidate.exists():
                target_file = candidate

        if not target_file:
            downloaded_files = [
                f for f in job_dir.iterdir()
                if f.is_file() and f.name not in _SKIP_FILES
                and not f.name.endswith(".tmp") and not f.name.endswith(".part")
            ]
            if downloaded_files:
                target_file = max(downloaded_files, key=lambda f: f.stat().st_size)

        if not target_file:
            status_data["status"] = "failed"
            status_data["error"] = "下載完成但找不到檔案"
            _write_status(status_path, status_data)
            return

        file_size = target_file.stat().st_size

        # 組成 ctos:// 路徑
        date_str = job_dir.parent.name  # YYYY-MM-DD
        ctos_path = f"ctos://linebot/videos/{date_str}/{job_id}/{target_file.name}"

        status_data["status"] = "completed"
        status_data["progress"] = 100.0
        status_data["filename"] = target_file.name
        status_data["file_size"] = file_size
        status_data["ctos_path"] = ctos_path
        status_data["error"] = None
        _write_status(status_path, status_data)

    except Exception as exc:
        status_data["status"] = "failed"
        status_data["error"] = str(exc)
        _write_status(status_path, status_data)


def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"無效的輸入：{exc}"}, ensure_ascii=False))
        return 1

    url = payload.get("url", "").strip()
    if not url:
        print(json.dumps({"success": False, "error": "缺少 url 參數"}, ensure_ascii=False))
        return 1

    fmt = payload.get("format", "mp4").strip().lower()
    if fmt not in ("mp4", "mp3", "best"):
        print(json.dumps({"success": False, "error": f"不支援的格式：{fmt}，可用：mp4、mp3、best"}, ensure_ascii=False))
        return 1

    # 建立儲存目錄
    job_id = uuid_module.uuid4().hex[:8]
    date_str = datetime.now().strftime("%Y-%m-%d")
    base_dir = _get_videos_base_dir()
    job_dir = base_dir / date_str / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    status_path = job_dir / "status.json"

    # 寫入初始狀態
    _write_status(status_path, {
        "job_id": job_id,
        "status": "starting",
        "progress": 0.0,
        "filename": "",
        "file_size": 0,
        "ctos_path": "",
        "error": None,
        "url": url,
        "format": fmt,
        "created_at": datetime.now().isoformat(),
    })

    # Fork 背景程序
    pid = os.fork()

    if pid > 0:
        # 父程序：立即回傳 job ID
        print(json.dumps({
            "success": True,
            "job_id": job_id,
            "status": "started",
            "message": f"下載已啟動（格式：{fmt}），使用 check-download 查詢進度",
        }, ensure_ascii=False))
        return 0
    else:
        # 子程序：執行下載
        try:
            # 脫離父程序的 session
            os.setsid()
            # 重導向 stdio 到 /dev/null（先 dup2 再重設 Python 物件）
            devnull = os.open(os.devnull, os.O_RDWR)
            os.dup2(devnull, 0)
            os.dup2(devnull, 1)
            os.dup2(devnull, 2)
            os.close(devnull)
            sys.stdin = open(os.devnull, "r")
            sys.stdout = open(os.devnull, "w")
            sys.stderr = open(os.devnull, "w")

            _do_download(job_dir, status_path, url, fmt, job_id)
        except Exception as e:
            # 寫入錯誤日誌以便除錯
            try:
                error_log = job_dir / "error.log"
                error_log.write_text(
                    f"[{datetime.now().isoformat()}] 背景下載失敗: {e}\n",
                    encoding="utf-8",
                )
                _write_status(status_path, {
                    "job_id": job_id,
                    "status": "failed",
                    "error": str(e),
                    "created_at": datetime.now().isoformat(),
                })
            except Exception:
                pass
        finally:
            os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
