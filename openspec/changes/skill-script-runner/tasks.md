## Tasks

### Phase 1: ScriptRunner 核心 + MCP Tool
- [ ] 新增 `skills/script_runner.py` — ScriptRunner 類別
  - [ ] `execute(skill_name, script_name, input_str, env_overrides)` — subprocess 執行
  - [ ] `list_scripts(skill_name)` — 列出 skill 的所有 scripts
  - [ ] `get_script_info(skill_name, script_name)` — 取得描述（docstring 提取）
  - [ ] 執行器選擇：.py → uv run / python3、.sh → bash
  - [ ] timeout 控制（預設 30 秒）
  - [ ] 環境變數注入（SKILL_NAME, SKILL_DIR, SKILL_ASSETS_DIR）
- [ ] 新增 `services/mcp/skill_script_tools.py` — MCP tool
  - [ ] `run_skill_script(skill, script, input)` tool 定義
  - [ ] 二次權限檢查：驗證 user 有此 skill 的 requires_app 權限
  - [ ] 路徑穿越驗證（skill name + script name）
- [ ] SkillManager 擴充
  - [ ] `has_scripts(skill_name)` — 檢查 skill 是否有 scripts/
  - [ ] `get_script_path(skill_name, script_name)` — 取得 script 絕對路徑（含驗證）
  - [ ] `get_scripts_info(skill_name)` — 列出所有 script 的名稱和描述
- [ ] `run_skill_script` 加入 ching-tech-os MCP server 的 tool 列表
- [ ] 白名單邏輯：使用者有任何帶 scripts/ 的 skill → 自動加入 run_skill_script

### Phase 2: Prompt 注入 + 環境
- [ ] `linebot_agents.py` — 有 script 的 skill，prompt 加入使用說明
  - [ ] 列出 script 名稱、描述、用法範例
  - [ ] {baseDir} 替換為 skill 實際路徑
- [ ] `.env` 變數繼承（根據 SKILL.md metadata.openclaw.requires.env）
- [ ] primaryEnv 缺少時的警告 log
- [ ] 獨立工作目錄（/tmp/skill-runner/）+ 自動清理

### Phase 3: 前端 + 記錄
- [ ] `api/skills.py` — Skill 詳情加入 `script_tools` 欄位
- [ ] 前端 Skill 詳情頁顯示 script tools 列表
- [ ] script 執行結果記錄到 ai_logs（model 欄位填 "script"）
- [ ] 安裝 ClawHub skill 後，UI 自動顯示可用的 scripts
