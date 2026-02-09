## Tasks

### Phase 1: Script Runner 核心
- [ ] 新增 `skills/script_runner.py` — ScriptToolRunner 類別
  - [ ] `register(skill_name, script_path, description, args, timeout)` 
  - [ ] `execute(tool_name, args_dict)` — subprocess 執行 + timeout + capture
  - [ ] `get_tool_schema(tool_name)` — 產生 JSON schema
  - [ ] `list_tools(skill_name)` — 列出某 skill 的所有 script tools
- [ ] SkillManager 整合
  - [ ] `_scan_scripts(skill)` — 掃描 scripts/ 產生 tool 列表
  - [ ] `_parse_script_description(path)` — 從 SKILL.md 或 docstring 提取描述
  - [ ] 載入時自動註冊 script tools
  - [ ] `get_tool_names()` 合併 MCP tools + script tools
- [ ] 單元測試：建立測試用 skill，驗證掃描、註冊、執行流程

### Phase 2: 環境與 Assets
- [ ] 環境變數注入（SKILL_NAME, SKILL_DIR, SKILL_ASSETS_DIR）
- [ ] `.env` 變數繼承（根據 SKILL.md requires.env 宣告）
- [ ] primaryEnv 缺少時的警告 log
- [ ] 獨立工作目錄（/tmp/skill-runner/{session_id}/）
- [ ] 工作目錄自動清理

### Phase 3: AI 整合
- [ ] `linebot_ai.py` — tool call 路由：`skill__` → ScriptToolRunner
- [ ] `linebot_agents.py` — prompt 注入 script tool 使用說明
- [ ] `ai_logs` 記錄 script 執行結果
- [ ] allowed_tools 自動包含 script tools
- [ ] 端到端測試：Line Bot / Telegram 對話 → script 執行 → 結果回傳

### Phase 4: 前端 UI
- [ ] Skill 詳情頁顯示 script tools 列表（名稱、描述、參數）
- [ ] Script tool 的執行記錄整合到 AI Logs
- [ ] 安裝 ClawHub skill 後顯示自動產生的 tools
