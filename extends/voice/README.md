# extends/voice — Bot 語音訊息模組

Bot 語音訊息 STT（語音轉文字）+ TTS（文字轉語音）功能。

## 依賴

- `faster-whisper`（已在主 repo pyproject.toml）
- `edge-tts`（pyproject.toml optional dependency `voice`）

## 安裝

```bash
cd backend && uv pip install edge-tts
```

## 檔案結構

- `voice_stt.py` — STT 服務（同步/非同步轉錄）
- `voice_tts.py` — TTS 服務（Edge TTS）
- `voice_startup.py` — 模組啟動/關閉
- `tts_router.py` — TTS 音檔下載 API
- `contributes.yaml` — 生命週期 + router 宣告
- `skills/voice/SKILL.md` — AI Skill 定義
