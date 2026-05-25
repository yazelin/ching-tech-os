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

# 分段轉錄設定（防止長音訊 OOM）
CHUNK_DURATION_THRESHOLD = 1800  # 超過 30 分鐘使用分段轉錄
CHUNK_SIZE_SECONDS = 600  # 每段 10 分鐘

# Groq API 設定
GROQ_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3"
GROQ_TIMEOUT = 120.0  # 異步轉錄可能是長音訊，給更多時間
GROQ_MAX_FILE_SIZE = 25 * 1024 * 1024  # 免費 tier 上限 25MB


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


def _try_groq_transcribe(file_path: str) -> dict | None:
    """嘗試使用 Groq Whisper API 轉錄，失敗回傳 None。

    Returns:
        {"text": str, "segments": [{"start", "end", "text"}], "duration": float} 或 None
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        import httpx
    except ImportError:
        return None

    path = Path(file_path)
    if not path.exists():
        return None

    # 檔案大小檢查（免費 tier 上限 25MB）
    file_size = path.stat().st_size
    if file_size > GROQ_MAX_FILE_SIZE:
        print(f"[Groq] 檔案 {file_size / 1024 / 1024:.1f}MB 超過上限 25MB，跳過", flush=True)
        return None

    try:
        with open(file_path, "rb") as f:
            response = httpx.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (path.name, f, "audio/mpeg")},
                data={
                    "model": GROQ_MODEL,
                    "language": "zh",
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": "segment",
                    "temperature": "0.0",
                },
                timeout=GROQ_TIMEOUT,
            )

        if response.status_code == 429:
            print(f"[Groq] rate limit，fallback 到本機轉錄", flush=True)
            return None

        if response.status_code != 200:
            print(f"[Groq] API 錯誤 (HTTP {response.status_code}): {response.text[:200]}", flush=True)
            return None

        result = response.json()
        text = result.get("text", "").strip()
        segments = result.get("segments", [])
        duration = result.get("duration", 0.0)

        print(f"[Groq] 轉錄完成：{len(segments)} 個 segments，時長 {duration:.1f} 秒", flush=True)

        return {
            "text": text,
            "segments": [
                {
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                    "text": seg.get("text", "").strip(),
                }
                for seg in segments
                if seg.get("text", "").strip()
            ],
            "duration": duration,
        }

    except Exception as e:
        print(f"[Groq] 轉錄失敗: {e}，fallback 到本機", flush=True)
        return None


def _get_audio_duration(file_path: str) -> float | None:
    """使用 ffprobe 取得音訊/影片時長（秒）。"""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def _extract_chunk(source_file: str, output_path: str, start: float, duration: float) -> bool:
    """從來源檔案擷取指定時間範圍的音訊片段（WAV 16kHz mono）。"""
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-ss", str(start), "-i", source_file,
                "-t", str(duration),
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                "-y", output_path,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0 and Path(output_path).exists()
    except Exception:
        return False


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
        # 步驟 1：判斷是否需要提取音軌
        ext = source_file.suffix.lower()
        is_video = ext in VIDEO_EXTENSIONS

        # 先取得時長，決定後續策略
        total_dur = _get_audio_duration(str(source_file))
        need_chunked = (
            total_dur is not None
            and total_dur > CHUNK_DURATION_THRESHOLD
        )

        if is_video and not need_chunked:
            # 短影片：提取完整音軌（與原邏輯相同）
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
        elif is_video:
            # 長影片：跳過全檔提取，後續由分段轉錄直接從影片逐段擷取
            transcribe_input = str(source_file)
        else:
            # 純音訊檔直接使用
            transcribe_input = str(source_file)

        # 步驟 2：轉錄（Groq API 優先，fallback 本機 faster-whisper）
        status_data["status"] = "transcribing"
        _write_status(status_path, status_data)

        try:
            from opencc import OpenCC
            converter = OpenCC("s2twp")
        except ImportError:
            converter = None

        transcript_segments = []
        full_text_parts = []
        duration = 0.0
        used_engine = "local"

        # 嘗試 Groq API
        groq_result = _try_groq_transcribe(transcribe_input)
        if groq_result is not None:
            used_engine = "groq"
            duration = groq_result["duration"]
            for seg in groq_result["segments"]:
                text = seg["text"]
                if converter:
                    text = converter.convert(text)
                transcript_segments.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": text,
                })
                full_text_parts.append(text)
        else:
            # Fallback：本機 faster-whisper
            from faster_whisper import WhisperModel

            device = "cpu"
            compute_type = "int8"
            if shutil.which("nvidia-smi"):
                device = "cuda"
                compute_type = "float16"

            if need_chunked:
                # 分段轉錄：逐段擷取音訊，避免一次載入整個長音訊導致 OOM
                print(f"音訊時長 {total_dur:.0f} 秒，使用分段轉錄（每段 {CHUNK_SIZE_SECONDS} 秒）", flush=True)
                duration = total_dur

                model = WhisperModel(model_name, device=device, compute_type=compute_type)
                chunk_index = 0
                offset = 0.0

                while offset < total_dur:
                    chunk_path = str(job_dir / f"chunk_{chunk_index}.wav")
                    chunk_len = min(CHUNK_SIZE_SECONDS, total_dur - offset)

                    print(f"擷取分段 {chunk_index}: {_format_duration(offset)} ~ {_format_duration(offset + chunk_len)}", flush=True)
                    if not _extract_chunk(transcribe_input, chunk_path, offset, chunk_len):
                        print(f"分段 {chunk_index} 擷取失敗，跳過", flush=True)
                        offset += CHUNK_SIZE_SECONDS
                        chunk_index += 1
                        continue

                    # 轉錄此分段
                    segments, _info = model.transcribe(chunk_path, language="zh")
                    for segment in segments:
                        text = segment.text.strip()
                        if not text:
                            continue
                        if converter:
                            text = converter.convert(text)
                        transcript_segments.append({
                            "start": segment.start + offset,
                            "end": segment.end + offset,
                            "text": text,
                        })
                        full_text_parts.append(text)

                    # 刪除已處理的分段檔案，釋放磁碟空間
                    try:
                        Path(chunk_path).unlink()
                    except Exception:
                        pass

                    # 更新狀態
                    progress_pct = min(int((offset + chunk_len) / total_dur * 100), 99)
                    status_data["progress"] = progress_pct
                    _write_status(status_path, status_data)

                    offset += CHUNK_SIZE_SECONDS
                    chunk_index += 1

                del model
            else:
                # 短音訊：直接一次轉錄
                model = WhisperModel(model_name, device=device, compute_type=compute_type)
                segments, info = model.transcribe(transcribe_input, language="zh")

                last_status_update = time.monotonic()
                for segment in segments:
                    text = segment.text.strip()
                    if not text:
                        continue
                    # 定期更新狀態檔以防止 check-transcription 判定逾時
                    if time.monotonic() - last_status_update > 30:
                        _write_status(status_path, status_data)
                        last_status_update = time.monotonic()
                    if converter:
                        text = converter.convert(text)
                    transcript_segments.append({
                        "start": segment.start,
                        "end": segment.end,
                        "text": text,
                    })
                    full_text_parts.append(text)
                duration = info.duration
                del model

        # 步驟 4：產生 transcript.md
        duration_formatted = _format_duration(duration)
        source_filename = source_file.name
        engine_label = f"groq-{GROQ_MODEL}" if used_engine == "groq" else f"whisper-{model_name}"

        md_lines = [
            f"# 逐字稿：{source_filename}",
            "",
            f"> 來源：{source_ctos_path}",
            f"> 轉錄時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"> 模型：{engine_label}",
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

        # 步驟 5：清理暫存音軌（原步驟 5）
        if audio_path and audio_path.exists():
            audio_path.unlink()

        # 步驟 6：更新狀態為完成（原步驟 6）
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
