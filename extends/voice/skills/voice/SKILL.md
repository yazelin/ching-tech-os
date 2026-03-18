---
name: voice
description: Bot 語音訊息處理（STT 語音轉文字 + TTS 文字轉語音）
allowed-tools: "mcp__ching-tech-os__text_to_speech"
metadata:
  ctos:
    requires_app: voice
    mcp_servers: ""
  contributes:
    app:
      id: voice
      name: 語音訊息
      icon: mdi-microphone
    permissions:
      voice:
        default: true
        display_name: 語音訊息
---

# 語音訊息功能

Bot 語音訊息處理模組：

- **STT（語音轉文字）**：用戶發送語音訊息時，自動轉錄為文字並送入 AI 對話
- **TTS（文字轉語音）**：AI 可透過 `text_to_speech` 工具主動生成語音回覆

## 支援平台
- Line Bot：M4A 音訊
- Telegram Bot：OGG/Opus 語音訊息

## 轉錄策略
- 短音訊（≤ 60 秒）：同步轉錄（faster-whisper base 模型）
- 長音訊（> 60 秒）：非同步轉錄（media-transcription skill）

## TTS 語音
- 引擎：支援 Edge TTS / Google Cloud TTS / Gemini Native Audio（透過 TTS_ENGINE 環境變數切換）
- 預設語音：zh-TW-HsiaoChenNeural（台灣女聲）
- 語音設定支援階層式繼承（系統 → Agent → 群組 → 使用者）
