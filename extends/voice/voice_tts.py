"""文字轉語音（TTS）服務

支援多引擎切換：Edge TTS / Google Cloud TTS / Gemini Native Audio。
透過 TTS_ENGINE 環境變數選擇引擎（預設 edge）。
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("voice.tts")

# 預設語音角色（可透過 .env 的 TTS_VOICE 設定覆蓋）
DEFAULT_VOICE = os.environ.get("TTS_VOICE", "zh-TW-HsiaoChenNeural")

# 文字長度上限
MAX_TEXT_LENGTH = 500


# ── 資料結構 ────────────────────────────────────────────


@dataclass
class VoiceInfo:
    """語音角色資訊（統一格式）"""
    id: str          # 引擎內部語音識別碼
    name: str        # 人類可讀名稱
    gender: str      # male / female / neutral
    language: str    # 語言代碼（如 zh-TW）


@dataclass
class TTSResult:
    """TTS 結果"""
    nas_path: str | None       # 音檔 NAS 相對路徑
    file_id: str | None        # UUID4 音檔 ID
    duration_ms: int | None    # 音檔長度（毫秒）
    audio_bytes: bytes | None  # 音檔二進位（供 Telegram 直接上傳）
    error: str | None          # 錯誤訊息


# ── 引擎抽象介面 ────────────────────────────────────────


class TTSEngine(ABC):
    """TTS 引擎抽象基底類別"""

    @abstractmethod
    async def synthesize_audio(self, text: str, **params) -> bytes:
        """將文字轉為音訊 bytes（MP3 格式）

        params 由各引擎定義：
          Edge:   voice="zh-TW-HsiaoChenNeural"
          Google: voice="cmn-TW-Standard-A", speed=1.2, pitch=0
          Gemini: style="溫柔女聲"
        """

    @abstractmethod
    async def list_voices(self, language: str = "zh-TW") -> list[VoiceInfo]:
        """回傳可用語音角色清單"""

    @abstractmethod
    def get_config_schema(self) -> dict:
        """回傳設定 schema，供前端動態渲染 UI

        格式：
          {"voice": {"type": "select", "label": "語音角色", "required": true}}
          {"voice": {"type": "select"}, "speed": {"type": "slider", "min": 0.5, "max": 2.0, "default": 1.0}}
          {"style": {"type": "text", "placeholder": "溫柔女聲/專業播報員/..."}}
        """


# ── Edge TTS 引擎 ──────────────────────────────────────


class EdgeTTSEngine(TTSEngine):
    """Edge TTS 引擎（免費，使用 edge-tts 套件）"""

    async def synthesize_audio(self, text: str, **params) -> bytes:
        import edge_tts

        voice = params.get("voice", DEFAULT_VOICE)
        communicate = edge_tts.Communicate(text, voice)

        # edge-tts 只支援存檔，用暫存檔轉 bytes
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            await communicate.save(tmp_path)
            mp3_bytes = Path(tmp_path).read_bytes()
            # MP3 → M4A (AAC)，Line AudioMessage 需要 M4A 格式
            return await _mp3_to_m4a(mp3_bytes)
        finally:
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass

    async def list_voices(self, language: str = "zh-TW") -> list[VoiceInfo]:
        import edge_tts

        voices = await edge_tts.list_voices()
        result = []
        for v in voices:
            if v["Locale"].startswith(language):
                # 從 ShortName 提取名稱
                short = v["ShortName"]  # 如 zh-TW-HsiaoChenNeural
                friendly = v.get("FriendlyName", short)
                gender = v.get("Gender", "neutral").lower()
                result.append(VoiceInfo(
                    id=short,
                    name=friendly,
                    gender=gender,
                    language=v["Locale"],
                ))
        return result

    def get_config_schema(self) -> dict:
        return {
            "voice": {
                "type": "select",
                "label": "語音角色",
                "required": True,
            },
        }


# ── Google Cloud TTS 引擎（佔位）──────────────────────


class GoogleCloudTTSEngine(TTSEngine):
    """Google Cloud TTS 引擎（尚未實作）"""

    async def synthesize_audio(self, text: str, **params) -> bytes:
        raise NotImplementedError("Google Cloud TTS 引擎尚未實作")

    async def list_voices(self, language: str = "zh-TW") -> list[VoiceInfo]:
        raise NotImplementedError("Google Cloud TTS 引擎尚未實作")

    def get_config_schema(self) -> dict:
        return {
            "voice": {
                "type": "select",
                "label": "語音角色",
                "required": True,
            },
            "speed": {
                "type": "slider",
                "label": "語速",
                "min": 0.5,
                "max": 2.0,
                "step": 0.1,
                "default": 1.0,
            },
            "pitch": {
                "type": "slider",
                "label": "音調",
                "min": -10,
                "max": 10,
                "step": 1,
                "default": 0,
            },
        }


# ── Gemini Native Audio 引擎 ────────────────────────────


# Gemini TTS 預建語音清單
_GEMINI_VOICES = {
    "female": [
        ("Achernar", "Achernar（女聲）"),
        ("Aoede", "Aoede（女聲）"),
        ("Autonoe", "Autonoe（女聲）"),
        ("Callirrhoe", "Callirrhoe（女聲）"),
        ("Despina", "Despina（女聲）"),
        ("Erinome", "Erinome（女聲）"),
        ("Gacrux", "Gacrux（女聲）"),
        ("Kore", "Kore（女聲）"),
        ("Laomedeia", "Laomedeia（女聲）"),
        ("Leda", "Leda（女聲）"),
        ("Sulafat", "Sulafat（女聲）"),
        ("Zephyr", "Zephyr（女聲）"),
        ("Pulcherrima", "Pulcherrima（女聲）"),
        ("Vindemiatrix", "Vindemiatrix（女聲）"),
    ],
    "male": [
        ("Achird", "Achird（男聲）"),
        ("Algenib", "Algenib（男聲）"),
        ("Algieba", "Algieba（男聲）"),
        ("Alnilam", "Alnilam（男聲）"),
        ("Charon", "Charon（男聲）"),
        ("Enceladus", "Enceladus（男聲）"),
        ("Fenrir", "Fenrir（男聲）"),
        ("Iapetus", "Iapetus（男聲）"),
        ("Orus", "Orus（男聲）"),
        ("Puck", "Puck（男聲）"),
        ("Rasalgethi", "Rasalgethi（男聲）"),
        ("Sadachbia", "Sadachbia（男聲）"),
        ("Sadaltager", "Sadaltager（男聲）"),
        ("Schedar", "Schedar（男聲）"),
        ("Umbriel", "Umbriel（男聲）"),
        ("Zubenelgenubi", "Zubenelgenubi（男聲）"),
    ],
}


async def _pcm_to_m4a(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
    """將 PCM raw data 轉換為 M4A/AAC（Line AudioMessage 需要 M4A 格式）

    M4A (ipod) 容器需要 seekable 輸出，無法用 pipe，因此使用暫存檔。
    """
    import asyncio
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as pcm_tmp:
        pcm_tmp.write(pcm_data)
        pcm_path = pcm_tmp.name

    m4a_path = pcm_path.replace(".pcm", ".m4a")

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-f", "s16le",
            "-ar", str(sample_rate),
            "-ac", "1",
            "-i", pcm_path,
            "-codec:a", "aac",
            "-b:a", "128k",
            m4a_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg PCM→M4A 轉換失敗: {stderr.decode()[:200]}")
        return Path(m4a_path).read_bytes()
    finally:
        for p in (pcm_path, m4a_path):
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:
                pass


async def _mp3_to_m4a(mp3_data: bytes) -> bytes:
    """將 MP3 轉換為 M4A/AAC（Line AudioMessage 需要 M4A 格式）"""
    import asyncio
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_tmp:
        mp3_tmp.write(mp3_data)
        mp3_path = mp3_tmp.name

    m4a_path = mp3_path.replace(".mp3", ".m4a")

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-i", mp3_path,
            "-codec:a", "aac",
            "-b:a", "128k",
            m4a_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg MP3→M4A 轉換失敗: {stderr.decode()[:200]}")
        return Path(m4a_path).read_bytes()
    finally:
        for p in (mp3_path, m4a_path):
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:
                pass


class GeminiNativeEngine(TTSEngine):
    """Gemini Native Audio 引擎（使用 gemini-2.5-flash-preview-tts）"""

    def __init__(self):
        self._api_key = os.environ.get("GEMINI_API_KEY", "")

    async def synthesize_audio(self, text: str, **params) -> bytes:
        if not self._api_key:
            raise RuntimeError("GEMINI_API_KEY 未設定")

        from google import genai
        from google.genai import types

        voice = params.get("voice", "Kore")
        instructions = params.get("instructions", "用溫柔自然的語氣朗讀")

        client = genai.Client(api_key=self._api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=f"{instructions}: {text}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice,
                        )
                    )
                ),
            ),
        )

        # 從回應中提取 PCM 音訊
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.inline_data and part.inline_data.data:
                    pcm_data = part.inline_data.data
                    # PCM raw → M4A (AAC)
                    return await _pcm_to_m4a(pcm_data, sample_rate=24000)

        raise RuntimeError("Gemini API 未回傳音訊資料")

    async def list_voices(self, language: str = "zh-TW") -> list[VoiceInfo]:
        result = []
        for gender, voices in _GEMINI_VOICES.items():
            for voice_id, voice_name in voices:
                result.append(VoiceInfo(
                    id=voice_id,
                    name=voice_name,
                    gender=gender,
                    language="multilingual",
                ))
        return result

    def get_config_schema(self) -> dict:
        return {
            "voice": {
                "type": "select",
                "label": "語音角色",
                "required": True,
            },
            "instructions": {
                "type": "text",
                "label": "朗讀指示",
                "placeholder": "用溫柔自然的語氣朗讀",
                "default": "用溫柔自然的語氣朗讀",
            },
        }


# ── 引擎工廠 ───────────────────────────────────────────


_engine: TTSEngine | None = None


def _get_engine() -> TTSEngine:
    """取得 TTS 引擎實例（lazy singleton）"""
    global _engine
    if _engine is None:
        engine_type = os.environ.get("TTS_ENGINE", "edge")
        if engine_type == "google_cloud":
            _engine = GoogleCloudTTSEngine()
        elif engine_type == "gemini":
            _engine = GeminiNativeEngine()
        else:
            _engine = EdgeTTSEngine()
        logger.info("TTS 引擎初始化: %s", engine_type)
    return _engine


def get_engine() -> TTSEngine:
    """取得 TTS 引擎實例（公開介面）"""
    return _get_engine()


def get_available_engines() -> list[str]:
    """回傳所有可用的引擎名稱"""
    # google_cloud 需要額外啟用 Cloud TTS API 和 billing，暫時不列出
    return ["edge", "gemini"]


def get_engine_by_name(name: str) -> TTSEngine:
    """依名稱取得引擎實例（不快取，用於試聽等臨時用途）"""
    if name == "google_cloud":
        return GoogleCloudTTSEngine()
    elif name == "gemini":
        return GeminiNativeEngine()
    else:
        return EdgeTTSEngine()


# ── 共用前處理 ─────────────────────────────────────────


def _get_ctos_mount_path() -> str:
    """取得 CTOS 掛載路徑"""
    try:
        from ching_tech_os.config import settings
        return settings.ctos_mount_path
    except ImportError:
        return os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")


def _strip_markdown(text: str) -> str:
    """清除 Markdown 標記"""
    # 移除程式碼區塊
    text = re.sub(r"```[\s\S]*?```", "", text)
    # 移除行內程式碼
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 移除粗體/斜體
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # 移除標題標記
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # 移除列表標記
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.MULTILINE)
    # 移除連結
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # 移除圖片
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    # 移除水平線
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # 壓縮多餘空白
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_emojis(text: str) -> str:
    """移除 emoji 符號，避免 TTS 將 emoji 唸出來"""
    # 注意：不可使用跨越 CJK 漢字區（U+4E00-9FFF）的大範圍
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # 表情符號
        "\U0001F300-\U0001F5FF"  # 符號與象形文字
        "\U0001F680-\U0001F6FF"  # 交通與地圖
        "\U0001F1E0-\U0001F1FF"  # 國旗
        "\U0001F900-\U0001F9FF"  # 補充表情
        "\U0001FA00-\U0001FA6F"  # 棋子
        "\U0001FA70-\U0001FAFF"  # 額外符號
        "\U0001F000-\U0001F02F"  # 麻將、撲克牌
        "\U0001F0A0-\U0001F0FF"  # 撲克牌補充
        "\U0001F200-\U0001F251"  # 圈號文字符號（安全範圍，不含 CJK）
        "\U00002600-\U000027BF"  # 雜項符號 + 裝飾符號
        "\U0000FE00-\U0000FE0F"  # 變體選擇器
        "\U0000200D"             # 零寬連接符
        "\U00002B50-\U00002B55"  # 星星、圓圈等
        "\U0000231A-\U0000231B"  # 手錶/沙漏
        "\U000023E9-\U000023F3"  # 播放按鈕等
        "\U000023F8-\U000023FA"  # 暫停/錄音
        "\U0000200B-\U0000200F"  # 零寬空格等
        "\U000020E3"             # Combining Enclosing Keycap
        "\U00002934-\U00002935"  # 箭頭
        "\U000025AA-\U000025AB"  # 小方塊
        "\U000025FB-\U000025FE"  # 中方塊
        "\U00002B05-\U00002B07"  # 箭頭
        "\U00002B1B-\U00002B1C"  # 大方塊
        "\U00003030"             # 波浪號
        "\U0000303D"             # 日文符號
        "\U00003297"             # 圈祝
        "\U00003299"             # 圈秘
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


async def _get_audio_duration_ms(file_path: Path) -> int | None:
    """用 ffprobe 精確計算 MP3 duration（毫秒）"""
    import asyncio
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_entries", "format=duration",
            str(file_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            import json
            data = json.loads(stdout)
            duration = float(data["format"]["duration"])
            return int(duration * 1000)
    except Exception:
        pass
    return None


def _clean_for_tts(text: str) -> str:
    """共用前處理：清除 Markdown、emoji、截斷"""
    text = _strip_markdown(text)
    text = _strip_emojis(text)
    # 清理 emoji 移除後可能留下的多餘空格
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\n +", "\n", text)
    text = text.strip()
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH] + "...後續請參考文字訊息"
    return text


# ── 主要介面 ───────────────────────────────────────────


async def synthesize(
    text: str,
    voice: str = "",
    engine_name: str = "",
    **tts_params,
) -> TTSResult:
    """將文字轉為語音

    Args:
        text: 要轉語音的文字
        voice: 語音角色（向後相容參數，會合併到 tts_params）
        engine_name: 引擎名稱（空字串用系統預設）
        **tts_params: 引擎特定參數

    Returns:
        TTSResult
    """
    # 共用前處理
    text = _clean_for_tts(text)
    if not text:
        return TTSResult(
            nas_path=None, file_id=None, duration_ms=None,
            audio_bytes=None, error="文字內容為空",
        )

    # 合併 voice 到 params（向後相容）
    if voice and "voice" not in tts_params:
        tts_params["voice"] = voice
    # 若沒有任何 voice/style 參數，用預設值
    if "voice" not in tts_params and "style" not in tts_params:
        tts_params["voice"] = DEFAULT_VOICE

    # 選擇引擎：指定名稱 > 系統預設
    engine = get_engine_by_name(engine_name) if engine_name else _get_engine()

    try:
        # 引擎生成音訊 bytes
        audio_bytes = await engine.synthesize_audio(text, **tts_params)
    except NotImplementedError as e:
        return TTSResult(
            nas_path=None, file_id=None, duration_ms=None,
            audio_bytes=None, error=str(e),
        )
    except Exception as e:
        logger.error("TTS 生成失敗: %s", e, exc_info=True)
        return TTSResult(
            nas_path=None, file_id=None, duration_ms=None,
            audio_bytes=None, error=str(e),
        )

    # 共用後處理：存檔到 NAS
    file_id = str(uuid.uuid4())
    date_str = datetime.now().strftime("%Y-%m-%d")
    nas_rel_path = f"voice/tts/{date_str}/{file_id}.m4a"
    mount = _get_ctos_mount_path()
    abs_path = Path(mount) / nas_rel_path

    try:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(audio_bytes)

        # 精確計算 duration（透過 ffprobe）
        duration_ms = await _get_audio_duration_ms(abs_path)
        if duration_ms is None:
            # fallback 估算（MP3 ~16KB/s @ 128kbps）
            duration_ms = int(len(audio_bytes) / 16 * 1000 / 1000) if audio_bytes else None

        logger.info("TTS 生成完成: %s (%d bytes)", file_id, len(audio_bytes))

        return TTSResult(
            nas_path=nas_rel_path,
            file_id=file_id,
            duration_ms=duration_ms,
            audio_bytes=audio_bytes,
            error=None,
        )
    except Exception as e:
        logger.error("TTS 存檔失敗: %s", e, exc_info=True)
        if abs_path.exists():
            try:
                abs_path.unlink()
            except Exception:
                pass
        return TTSResult(
            nas_path=None, file_id=None, duration_ms=None,
            audio_bytes=None, error=str(e),
        )


async def synthesize_preview(
    text: str,
    engine_name: str = "",
    **params,
) -> bytes | None:
    """生成試聽音訊（不存檔到 NAS，直接回傳 bytes）

    Args:
        text: 要轉語音的文字
        engine_name: 引擎名稱（空字串用目前預設）
        **params: 引擎特定參數

    Returns:
        MP3 bytes 或 None（失敗時）
    """
    text = _clean_for_tts(text)
    if not text:
        return None

    engine = get_engine_by_name(engine_name) if engine_name else _get_engine()

    if "voice" not in params and "style" not in params:
        params["voice"] = DEFAULT_VOICE

    try:
        return await engine.synthesize_audio(text, **params)
    except Exception as e:
        logger.error("TTS 試聽生成失敗: %s", e, exc_info=True)
        return None


# ── 清理 ───────────────────────────────────────────────


def cleanup_old_files() -> None:
    """清理超過 24 小時的 TTS 暫存音檔"""
    mount = _get_ctos_mount_path()
    tts_root = Path(mount) / "voice" / "tts"

    if not tts_root.exists():
        return

    cutoff = datetime.now() - timedelta(hours=24)
    removed = 0

    for date_dir in tts_root.iterdir():
        if not date_dir.is_dir():
            continue
        try:
            dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
            if dir_date.date() >= cutoff.date():
                continue
        except ValueError:
            continue

        try:
            import shutil
            shutil.rmtree(str(date_dir))
            removed += 1
        except Exception as e:
            logger.warning("清理 TTS 目錄失敗 %s: %s", date_dir, e)

    if removed:
        logger.info("已清理 %d 個過期 TTS 目錄", removed)
