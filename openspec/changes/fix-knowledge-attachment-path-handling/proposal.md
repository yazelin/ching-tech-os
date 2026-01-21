# Change: 修正知識庫附件路徑處理

## Why

路徑統一（unified-path-manager）後，知識庫附件儲存的路徑格式為 `local://knowledge/assets/images/...`，但：
1. **公開分享 API 不支援此格式**：`share.py` 的附件 API 只認識 `local/images/...` 格式
2. **歷史資料路徑不一致**：舊資料使用 `local://knowledge/images/...`（無 `assets/`）
3. **MCP 工具無法發送知識庫附件**：AI 嘗試用錯誤路徑發送圖片

導致公開分享頁面無法下載附件，回傳「無權存取此附件」錯誤。

## What Changes

### 1. 修正 `share.py` 的附件路徑處理
- 支援 `local://knowledge/assets/images/...` 格式（新格式）
- 支援 `local://knowledge/images/...` 格式（舊格式）
- 支援 `ctos://knowledge/attachments/...` 格式（NAS 大型附件）

### 2. 新增 MCP 工具讀取知識庫附件
- 新增 `read_knowledge_attachment` 工具讓 AI 可以讀取並發送知識庫附件
- 或修正 `prepare_file_message` 支援知識庫附件路徑

### 3. 遷移舊資料路徑格式（可選）
- 將 `local://knowledge/images/...` 更新為 `local://knowledge/assets/images/...`
- 或保持向後兼容，兩種格式都支援

## Impact

- Affected specs: `knowledge-base`
- Affected code:
  - `backend/src/ching_tech_os/api/share.py` - 附件下載 API
  - `backend/src/ching_tech_os/services/mcp_server.py` - MCP 工具
  - `data/knowledge/entries/*.md` - 舊資料路徑格式（可選遷移）

## 問題重現

```
# 公開分享頁面下載附件
GET /api/public/{token}/attachments/local://knowledge/assets/images/kb-014-xxx.jpg
→ 403 {"detail": "無權存取此附件"}

# 正確的路徑格式應該被轉換
local://knowledge/assets/images/kb-014-xxx.jpg
→ local/images/kb-014-xxx.jpg
→ assets/images/kb-014-xxx.jpg（實際檔案位置）
```

## 路徑格式對照

| 儲存格式 | 實際位置 | API 期望格式 |
|---------|---------|-------------|
| `local://knowledge/assets/images/...`（新） | `data/knowledge/assets/images/...` | `local/images/...` |
| `local://knowledge/images/...`（舊） | `data/knowledge/assets/images/...` | `local/images/...` |
| `ctos://knowledge/attachments/...`（NAS） | `/mnt/nas/ctos/knowledge/attachments/...` | `attachments/{kb_id}/...` |
