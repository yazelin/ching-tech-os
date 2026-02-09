## Tasks

### Phase 1: 後端 CRUD + 重載
- [x] `SkillManager.update_skill_metadata(name, requires_app, allowed_tools, mcp_servers)` — 寫回 SKILL.md frontmatter
- [x] `SkillManager.remove_skill(name)` — 刪除 skill 目錄
- [x] `SkillManager.reload_skills()` — 公開方法，清除 `_loaded` 重新掃描
- [x] `PUT /api/skills/{name}` — 接收 JSON body `{requires_app, allowed_tools, mcp_servers}`
- [x] `DELETE /api/skills/{name}` — 移除 skill
- [x] `POST /api/skills/reload` — 觸發重載
- [x] 本地驗證：update（寫回+重載）、reload 通過

### Phase 2: ClawHub 整合
- [x] 研究 clawhub CLI output 格式（search、install）
- [x] `POST /api/skills/hub/search` — 呼叫 `clawhub search`，解析結果回傳 JSON
- [x] `POST /api/skills/hub/install` — 呼叫 `clawhub install`，再呼叫 `import_openclaw_skill()`
- [x] install.sh 加入 clawhub 安裝步驟（`npm i -g clawhub` 或等效）
- [x] 錯誤處理：clawhub 未安裝(503)、逾時(504)、名稱衝突(409)、安裝失敗(502)

### Phase 3: 前端 UI
- [x] 已安裝 tab 加「編輯」按鈕 → 打開 modal
- [x] 編輯 modal：requires_app 輸入、allowed-tools chip 編輯、mcp_servers chip 編輯
- [x] 已安裝 tab 加「移除」按鈕 → 確認 dialog（僅非 native）
- [x] 新增「ClawHub 搜尋」tab
- [x] 搜尋結果列表 + 「安裝」按鈕
- [x] 安裝後自動切回已安裝 tab，highlight 新 skill
- [x] 來源標記（native 藍 / openclaw 綠 / 其他灰）
- [x] 檔案瀏覽：點擊 references/scripts/assets 列表展開內容
- [x] 重載按鈕（列表上方 + 詳情頁右上角）

### Phase 4: 進階（未來）
- [ ] Skill 版本追蹤（記錄安裝版本，比對 ClawHub 最新版）
- [ ] Skill 更新提醒（heartbeat 檢查）
- [ ] Skill 啟用/停用 toggle（不刪除，只是暫停）
- [ ] Skill 依賴管理（A skill 需要 B skill）
