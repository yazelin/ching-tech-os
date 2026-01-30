# add-circuits-mount

## Summary
新增 NAS 線路圖掛載點（`/mnt/nas/circuits` ← `//NAS_HOST/擎添線路圖/圖檔`，唯讀），並將其納入 `shared://` 搜尋範圍。同時重構搜尋架構，將搜尋來源從單一路徑改為多來源清單，為未來依使用者權限控制搜尋範圍預留擴充點。

## Motivation
- 線路圖檔案目前無法透過 AI 搜尋工具找到，使用者需手動到檔案管理器瀏覽
- 未來需要依據使用者權限控制可搜尋的 NAS 範圍（例如某些人只能搜 projects、某些人可搜 circuits）

## Scope
1. **基礎設施**：新增 systemd mount unit、環境變數、config 設定
2. **搜尋擴展**：`search_nas_files` 改為多來源搜尋，結果路徑帶來源前綴（`shared://projects/...`、`shared://circuits/...`）
3. **路徑解析**：`path_manager` 支援 `shared://` 子路徑對應到不同掛載點
4. **權限預留**：搜尋來源清單設計為可依使用者權限過濾（本次不實作權限邏輯）

## Out of Scope
- 使用者權限控制的實際實作（僅預留架構）
- 前端 UI 變更
- 檔案管理器的 circuits 瀏覽功能
