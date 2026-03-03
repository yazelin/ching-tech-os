#!/usr/bin/env python3
"""非同步音訊/影片轉錄：立即回傳 job ID，背景程序執行轉錄。"""

import json
import os
import shutil
import subprocess
import sys
import time
import uuid as uuid_module
from datetime import datetime
from pathlib import Path


# 支援的檔案格式
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".flac"}
SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

# Whisper 模型選項
VALID_MODELS = {"base", "small", "medium", "large-v3"}
DEFAULT_MODEL = "small"


def _get_ctos_mount_path() -> str:
    """取得 CTOS 掛載路徑。"""
    try:
        from ching_tech_os.config import settings
        return settings.ctos_mount_path
    except ImportError:
        return os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")


def _get_transcriptions_base_dir() -> Path:
    """取得轉錄暫存基礎目錄。"""
    return Path(_get_ctos_mount_path()) / "linebot" / "transcriptions"


# 允許的掛載路徑前綴（路徑穿越防護白名單）
_ALLOWED_MOUNT_PREFIXES: list[str] | None = None


def _get_allowed_mount_prefixes() -> list[str]:
    """取得允許的掛載路徑前綴列表。"""
    global _ALLOWED_MOUNT_PREFIXES
    if _ALLOWED_MOUNT_PREFIXES is not None:
        return _ALLOWED_MOUNT_PREFIXES
    try:
        from ching_tech_os.config import settings
        _ALLOWED_MOUNT_PREFIXES = [
            str(Path(p).resolve())
            for p in [
                settings.ctos_mount_path,
                settings.library_mount_path,
                settings.projects_mount_path,
                settings.circuits_mount_path,
            ]
            if p
        ]
    except ImportError:
        _ALLOWED_MOUNT_PREFIXES = [
            str(Path(os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")).resolve()),
        ]
    return _ALLOWED_MOUNT_PREFIXES


def _resolve_source_path(source_path: str) -> Path | None:
    """將來源路徑（ctos://、shared:// 等）解析為實際檔案路徑。

    使用 PathManager 統一解析，支援所有路徑格式，並以白名單防護路徑穿越。
    """
    try:
        from ching_tech_os.services.path_manager import path_manager
        fs_path = path_manager.to_filesystem(source_path)
    except (ValueError, ImportError):
        return None

    # 路徑穿越防護：確保解析後的路徑在允許的掛載點下
    resolved = str(Path(fs_path).resolve())
    allowed = _get_allowed_mount_prefixes()
    if not any(resolved.startswith(prefix) for prefix in allowed):
        return None

    return Path(fs_path)


def _trigger_proactive_push(job_id: str, skill: str) -> None:
    """通知內部端點觸發主動推送（靜默失敗）"""
    try:
        import urllib.request
        data = json.dumps({"job_id": job_id, "skill": skill}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8088/api/internal/proactive-push",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def _write_status(status_path: Path, data: dict) -> None:
    """寫入狀態檔（atomic write）。"""
    data["updated_at"] = datetime.now().isoformat()
    tmp_path = status_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(status_path)


def _format_duration(seconds: float) -> str:
    """格式化秒數為 HH:MM:SS。"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _format_timestamp(seconds: float) -> str:
    """格式化秒數為 [MM:SS] 或 [HH:MM:SS] 時間戳。"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"
    return f"[{minutes:02d}:{secs:02d}]"


def _do_transcribe(
    job_dir: Path,
    status_path: Path,
    source_file: Path,
    source_ctos_path: str,
    model_name: str,
    job_id: str,
    caller_context: dict | None = None,
) -> None:
    """背景程序：執行實際轉錄。"""
    status_data: dict = {
        "job_id": job_id,
        "status": "started",
        "source_path": source_ctos_path,
        "model": model_name,
        "error": None,
        "created_at": datetime.now().isoformat(),
    }
    if caller_context:
        status_data["caller_context"] = caller_context

    audio_path = None

    try:
        # 步驟 1：提取音軌（影片才需要）
        ext = source_file.suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            status_data["status"] = "extracting_audio"
            _write_status(status_path, status_data)

            audio_path = job_dir / "audio.wav"
            result = subprocess.run(
                [
                    "ffmpeg", "-i", str(source_file),
                    "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                    "-y", str(audio_path),
                ],
                capture_output=True,
                text=True,
                timeout=600,  # 10 分鐘逾時
            )
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg 音軌提取失敗：{result.stderr[:500]}")
            if not audio_path.exists():
                raise RuntimeError("ffmpeg 未產生音訊檔")
            transcribe_input = str(audio_path)
        else:
            # 純音訊檔直接使用
            transcribe_input = str(source_file)

        # 步驟 2：載入 Whisper 模型並轉錄
        status_data["status"] = "transcribing"
        _write_status(status_path, status_data)

        from faster_whisper import WhisperModel

        # 自動偵測裝置
        device = "cpu"
        compute_type = "int8"
        if shutil.which("nvidia-smi"):
            device = "cuda"
            compute_type = "float16"

        model = WhisperModel(model_name, device=device, compute_type=compute_type)
        segments, info = model.transcribe(transcribe_input, language="zh")

        # 步驟 3：收集 segments 並轉換繁體
        try:
            from opencc import OpenCC
            converter = OpenCC("s2twp")
        except ImportError:
            converter = None

        transcript_segments = []
        full_text_parts = []
        last_status_update = time.monotonic()
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            # 定期更新狀態檔以防止 check-transcription 判定逾時
            if time.monotonic() - last_status_update > 30:
                _write_status(status_path, status_data)
                last_status_update = time.monotonic()
            # 簡轉繁
            if converter:
                text = converter.convert(text)
            transcript_segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": text,
            })
            full_text_parts.append(text)

        # 步驟 4：產生 transcript.md
        duration = info.duration
        duration_formatted = _format_duration(duration)
        source_filename = source_file.name

        md_lines = [
            f"# 逐字稿：{source_filename}",
            "",
            f"> 來源：{source_ctos_path}",
            f"> 轉錄時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"> 模型：whisper-{model_name}",
            f"> 時長：{duration_formatted}",
            "",
            "---",
            "",
        ]

        for seg in transcript_segments:
            timestamp = _format_timestamp(seg["start"])
            md_lines.append(f"{timestamp} {seg['text']}")
            md_lines.append("")

        transcript_path = job_dir / "transcript.md"
        transcript_path.write_text("\n".join(md_lines), encoding="utf-8")

        # 步驟 5：清理暫存音軌
        if audio_path and audio_path.exists():
            audio_path.unlink()

        # 步驟 6：更新狀態為完成
        date_str = job_dir.parent.name
        ctos_path = f"ctos://linebot/transcriptions/{date_str}/{job_id}/transcript.md"
        full_text = "".join(full_text_parts)
        preview = full_text[:500] + ("..." if len(full_text) > 500 else "")

        status_data["status"] = "completed"
        status_data["ctos_path"] = ctos_path
        status_data["duration"] = round(duration, 1)
        status_data["duration_formatted"] = duration_formatted
        status_data["transcript_preview"] = preview
        status_data["error"] = None
        _write_status(status_path, status_data)
        _trigger_proactive_push(job_id, "media-transcription")

    except Exception as exc:
        status_data["status"] = "failed"
        status_data["error"] = str(exc)
        _write_status(status_path, status_data)
        # 清理暫存
        if audio_path and audio_path.exists():
            try:
                audio_path.unlink()
            except Exception:
                pass


def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"無效的輸入：{exc}"}, ensure_ascii=False))
        return 1

    source_path = payload.get("source_path", "").strip()
    if not source_path:
        print(json.dumps({"success": False, "error": "缺少 source_path 參數"}, ensure_ascii=False))
        return 1

    # 解析來源路徑（支援 ctos://、shared:// 等格式）
    source_file = _resolve_source_path(source_path)
    if source_file is None:
        print(json.dumps({"success": False, "error": f"無法解析來源路徑：{source_path}"}, ensure_ascii=False))
        return 1

    if not source_file.exists():
        print(json.dumps({"success": False, "error": f"來源檔案不存在：{source_path}"}, ensure_ascii=False))
        return 1

    # 檢查格式
    ext = source_file.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        print(json.dumps({"success": False, "error": f"不支援的檔案格式：{ext}，支援：{supported}"}, ensure_ascii=False))
        return 1

    # 模型選擇
    model_name = payload.get("model", DEFAULT_MODEL).strip().lower()
    if model_name not in VALID_MODELS:
        print(json.dumps({"success": False, "error": f"不支援的模型：{model_name}，可用：{', '.join(sorted(VALID_MODELS))}"}, ensure_ascii=False))
        return 1

    caller_context = payload.get("caller_context") or None

    # 建立暫存目錄
    job_id = uuid_module.uuid4().hex[:8]
    date_str = datetime.now().strftime("%Y-%m-%d")
    base_dir = _get_transcriptions_base_dir()
    job_dir = base_dir / date_str / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    status_path = job_dir / "status.json"

    # 寫入初始狀態
    initial_status: dict = {
        "job_id": job_id,
        "status": "started",
        "source_path": source_path,
        "model": model_name,
        "ctos_path": "",
        "duration": 0,
        "duration_formatted": "",
        "transcript_preview": "",
        "error": None,
        "created_at": datetime.now().isoformat(),
    }
    if caller_context:
        initial_status["caller_context"] = caller_context
    _write_status(status_path, initial_status)

    # Fork 背景程序
    pid = os.fork()

    if pid > 0:
        # 父程序：立即回傳 job ID
        print(json.dumps({
            "success": True,
            "job_id": job_id,
            "status": "started",
            "message": f"轉錄已啟動（模型：{model_name}），使用 check-transcription 查詢進度",
        }, ensure_ascii=False))
        return 0
    else:
        # 子程序：執行轉錄
        try:
            os.setsid()
            # 切換 cwd 到 job 目錄（script_runner 的 TemporaryDirectory 會在父程序結束後刪除，
            # 若 cwd 被刪除會導致 ctranslate2/oneMKL 載入 .so 時 FATAL ERROR）
            os.chdir(str(job_dir))
            # 將 stdout/stderr 導向 job 目錄的 worker.log，方便除錯
            log_file = job_dir / "worker.log"
            log_fd = os.open(str(log_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            devnull_fd = os.open(os.devnull, os.O_RDONLY)
            os.dup2(devnull_fd, 0)
            os.dup2(log_fd, 1)
            os.dup2(log_fd, 2)
            os.close(devnull_fd)
            os.close(log_fd)
            sys.stdin = open(os.devnull, "r")
            sys.stdout = os.fdopen(1, "w")
            sys.stderr = os.fdopen(2, "w")

            print(f"[{datetime.now().isoformat()}] 子程序啟動 PID={os.getpid()}", flush=True)
            _do_transcribe(job_dir, status_path, source_file, source_path, model_name, job_id, caller_context)
            print(f"[{datetime.now().isoformat()}] 轉錄完成", flush=True)
        except Exception as e:
            try:
                import traceback
                tb = traceback.format_exc()
                print(f"[{datetime.now().isoformat()}] 背景轉錄失敗: {e}\n{tb}", flush=True)
                error_log = job_dir / "error.log"
                error_log.write_text(
                    f"[{datetime.now().isoformat()}] 背景轉錄失敗: {e}\n{tb}\n",
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
