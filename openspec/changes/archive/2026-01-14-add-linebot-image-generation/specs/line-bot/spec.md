## ADDED Requirements

### Requirement: AI 圖片生成
Line Bot 個人 AI 助手 SHALL 支援根據用戶文字描述生成圖片。

#### Scenario: 用戶請求生成圖片
- **WHEN** 用戶發送「畫一隻貓」或類似的圖片生成請求
- **THEN** AI 呼叫 `mcp__nanobanana__generate_image` 生成圖片
- **AND** AI 呼叫 `prepare_file_message` 準備圖片訊息
- **AND** 圖片透過 Line Bot 發送給用戶

#### Scenario: 圖片生成使用英文 prompt
- **WHEN** AI 處理圖片生成請求
- **THEN** AI 將用戶的中文描述轉換為英文 prompt
- **BECAUSE** nanobanana 使用英文 prompt 效果較佳

#### Scenario: 圖片生成後自動發送
- **WHEN** AI 呼叫 `generate_image` 成功生成圖片
- **AND** AI 回應中沒有包含對應的 `[FILE_MESSAGE:...]` 標記
- **THEN** 系統自動呼叫 `prepare_file_message` 並補上 FILE_MESSAGE 標記
- **BECAUSE** 確保用戶一定能收到生成的圖片，不依賴 AI 是否正確呼叫 prepare_file_message

#### Scenario: AI 已處理圖片則不重複發送
- **WHEN** AI 呼叫 `generate_image` 成功生成圖片
- **AND** AI 回應中已包含對應的 `[FILE_MESSAGE:...]` 標記
- **THEN** 系統跳過自動處理，不重複發送圖片

### Requirement: nanobanana 輸出路徑
系統 SHALL 自動設定 nanobanana 輸出路徑到 NAS 目錄，讓生成的圖片可透過 Line Bot 發送。

#### Scenario: 自動建立 symlink
- **WHEN** Claude Agent 啟動時
- **THEN** 系統檢查並建立 `/tmp/ching-tech-os-cli/nanobanana-output` symlink
- **AND** symlink 指向 `/mnt/nas/ctos/linebot/files/ai-images`

#### Scenario: NAS 目錄不存在時自動建立
- **WHEN** `/mnt/nas/ctos/linebot/files/ai-images` 目錄不存在
- **AND** NAS 掛載點 `/mnt/nas/ctos/linebot/files` 存在
- **THEN** 系統自動建立 `ai-images` 目錄
