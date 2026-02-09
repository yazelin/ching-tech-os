## Tasks

### Phase 1: ScriptRunner 核心 + MCP Tool ✅ (PR #49)
- [x] `skills/script_runner.py` — ScriptRunner 類別
- [x] `services/mcp/skill_script_tools.py` — `run_skill_script` MCP tool
- [x] SkillManager 擴充（has_scripts, get_script_path, get_scripts_info, skills_dir）
- [x] MCP server tool 註冊
- [x] 白名單邏輯

### Phase 2: Prompt 注入 + 環境 ✅ (PR #49 Gemini review 過程中完成)
- [x] `services/bot/agents.py` — Script Tools prompt 注入（名稱+描述）
- [x] `get_skill_env_overrides()` — .env 變數繼承（requires.env + primaryEnv）
- [x] ENV_BLOCKLIST 安全限制
- [x] primaryEnv 缺少時警告 log
- [x] 獨立工作目錄（TemporaryDirectory + 自動清理）

### Phase 3: 前端 + 記錄
- [ ] `api/skills.py` — Skill 詳情 API 加入 `script_tools` 欄位
- [ ] 前端 Skill 詳情頁顯示 script tools 列表（名稱、描述、用法）
- [ ] script 執行結果記錄到 ai_logs（model="script"）
- [ ] 安裝 ClawHub skill 後，UI 自動顯示可用的 scripts

### Phase 4: 進階（未排程）
- [ ] 多 agent backend 支援（SKILL.md metadata.ctos.agent 欄位）
- [ ] Script 執行記錄前端查看（ai_logs 篩選 model="script"）
