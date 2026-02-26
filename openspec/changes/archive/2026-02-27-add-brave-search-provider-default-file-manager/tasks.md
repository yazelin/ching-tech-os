## 1. 權限預設調整

- [x] 1.1 找出未綁定/預設權限的生效入口（`get_effective_app_permissions` 與相關權限檢查）
- [x] 1.2 將 `file-manager` 納入預設可用 App 權限
- [x] 1.3 補齊測試：未綁定使用者與找不到使用者紀錄時，`file-manager` 預設為啟用

## 2. Brave 搜尋 provider 導入

- [x] 2.1 在 `research-skill` 抽離搜尋 provider 邏輯（Brave + 既有 provider）
- [x] 2.2 新增 Brave Search API 呼叫實作（header、query、結果正規化）
- [x] 2.3 實作 provider fallback 鏈（Brave 失敗或無結果時回退）
- [x] 2.4 在狀態輸出中保留 provider 使用與 fallback 診斷資訊
- [x] 2.5 補齊 provider 單元測試（Brave 成功、Brave 失敗回退、無 key 回退）

## 3. 設定與環境變數

- [x] 3.1 在設定層加入 `BRAVE_SEARCH_API_KEY` 欄位
- [x] 3.2 更新 `.env.example`（加入 Brave API key 與用途註解）
- [x] 3.3 在研究 skill 文件補上 Brave 申請與設定說明

## 4. Bot 路由與回覆一致性

- [x] 4.1 確認研究型任務在可用情境優先呼叫 `start-research`
- [x] 4.2 避免「權限不足 -> 直接改走 WebSearch/WebFetch」成為預設行為
- [x] 4.3 補齊回歸測試：帶/不帶 `ctos_user_id` 的 research-skill 呼叫行為

## 5. 驗證與交付

- [x] 5.1 執行 `npm run build`
- [x] 5.2 執行 backend 相關測試（permissions / skill_routing / linebot_ai / research-skill）
- [x] 5.3 更新 OpenSpec tasks 完成狀態
- [x] 5.4 commit、push、建立 PR（附上 Brave 申請網址與環境設定說明）
