# Change: 新增 AI 簡報生成功能

## Why

用戶經常需要快速製作簡報，目前需要手動使用 PowerPoint 等工具，耗時且需要設計技能。透過整合 AI 簡報生成功能，用戶可以用自然語言描述需求，系統自動生成專業的 PowerPoint 簡報，大幅提升工作效率。

## What Changes

- 新增 `presentation_service.py` 後端服務，負責簡報生成邏輯
- 新增 `/api/presentation/generate` API 端點
- 新增 `generate_presentation` MCP 工具，讓 AI 助手可透過對話生成簡報
- 使用 Claude API 生成簡報大綱（透過現有 AI 整合）
- 整合 Pexels API 自動配圖
- 使用 python-pptx 生成 PowerPoint 檔案
- 簡報檔案儲存於 NAS `/mnt/nas/projects/ai-presentations/`

## Impact

- Affected specs: `mcp-tools`
- Affected code:
  - `backend/src/ching_tech_os/services/presentation_service.py`（新增）
  - `backend/src/ching_tech_os/api/presentation.py`（新增）
  - `backend/src/ching_tech_os/services/mcp_server.py`（新增工具）
  - `backend/src/ching_tech_os/main.py`（註冊路由）
  - `backend/pyproject.toml`（新增依賴）
