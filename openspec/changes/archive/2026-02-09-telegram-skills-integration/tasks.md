## 1. 補齊 Skills YAML 工具定義

- [x] 1.1 更新 `skills/inventory/skill.yaml`：補齊完整 ERPNext 工具（對齊 handler 硬編碼的 27 個工具中庫存相關的部分）
- [x] 1.2 更新 `skills/project/skill.yaml`：補齊完整 ERPNext 專案管理工具
- [x] 1.3 更新 `skills/printer/skill.yaml`：加入 `mcp__printer__print_test_page`
- [x] 1.4 更新 `skills/base/skill.yaml`：加入 `Read` 工具
- [x] 1.5 更新 `skills/ai_assistant/skill.yaml`：加入 `mcp__nanobanana__restore_image`
- [x] 1.6 驗證所有 skill YAML 的工具列表合併後，涵蓋目前硬編碼的所有工具

## 2. 新增 `get_tools_for_user()` 共用函式

- [x] 2.1 在 `bot/agents.py` 新增 `get_tools_for_user(app_permissions)` 函式，從 SkillManager 取得工具名稱列表
- [x] 2.2 加入 fallback 機制：SkillManager 失敗時回傳硬編碼工具列表
- [x] 2.3 在 `linebot_agents.py` 匯出 `get_tools_for_user` 供平台 handler 使用

## 3. 重構 Telegram handler

- [x] 3.1 修改 `bot_telegram/handler.py`：移除硬編碼的 nanobanana_tools、printer_tools、erpnext_tools
- [x] 3.2 改用 `get_tools_for_user(app_permissions)` 產生外部 MCP 工具白名單
- [x] 3.3 保留 `get_mcp_tool_names()` + `get_mcp_tools_for_user()` 取得內建 MCP 工具

## 4. 同步重構 Line bot handler

- [x] 4.1 修改 `linebot_ai.py`：移除硬編碼的 nanobanana_tools、printer_tools、erpnext_tools
- [x] 4.2 改用 `get_tools_for_user(app_permissions)` 產生外部 MCP 工具白名單

## 5. 驗證

- [x] 5.1 重啟服務，確認 SkillManager 載入日誌正確（共載入 7 個 skills）
- [x] 5.2 透過 Telegram 發送訊息測試 AI 回覆正常
- [x] 5.3 確認 AI logs 記錄的 allowed_tools 內容正確
