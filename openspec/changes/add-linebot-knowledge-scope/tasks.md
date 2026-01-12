## 1. 後端模型與服務更新

- [ ] 1.1 更新 `models/knowledge.py` 新增 project_id 欄位
- [ ] 1.2 更新 `services/knowledge.py` 的 create_knowledge 支援 project_id
- [ ] 1.3 更新 `index.json` 結構支援 project_id

## 2. 權限系統更新

- [ ] 2.1 更新 `services/permissions.py` 新增專案知識權限檢查函數
- [ ] 2.2 新增函數檢查用戶是否為專案成員
- [ ] 2.3 修改 `check_knowledge_permission` 支援 scope=project 和 global 權限覆蓋

## 3. MCP 工具更新

- [ ] 3.1 更新 `add_note` 新增 line_group_id、line_user_id、ctos_user_id 參數
- [ ] 3.2 更新 `add_note_with_attachments` 新增對話脈絡參數
- [ ] 3.3 實作根據對話來源自動判斷 scope 的邏輯
- [ ] 3.4 查詢群組綁定的專案 ID

## 4. API 權限檢查更新

- [ ] 4.1 更新 `api/knowledge.py` 的更新/刪除 API 權限檢查
- [ ] 4.2 支援專案成員編輯專案知識
- [ ] 4.3 支援全域權限用戶編輯任何知識

## 5. Line Bot Agent Prompt 更新

- [ ] 5.1 更新 `linebot_agents.py` 的 prompt 說明 add_note 新參數
- [ ] 5.2 建立 migration 更新資料庫中的 prompt

## 6. 測試與驗證

- [ ] 6.1 測試個人聊天建立知識（scope=personal）
- [ ] 6.2 測試綁定專案的群組建立知識（scope=project）
- [ ] 6.3 測試未綁定專案的群組建立知識
- [ ] 6.4 測試專案成員編輯專案知識
- [ ] 6.5 測試管理員/全域權限用戶編輯任意知識
