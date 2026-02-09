# Design — Skill Script Runner

## 架構

```
SkillManager
  ├─ load_skills()           # 現有：掃描 SKILL.md
  ├─ _scan_scripts(skill)    # 新增：掃描 scripts/，產生 ScriptTool 列表
  └─ get_tool_names()        # 修改：合併 MCP tools + script tools

ScriptToolRunner（新增）
  ├─ register(skill, scripts)  # 註冊 script tools
  ├─ execute(tool_name, args)  # 執行 script
  ├─ get_tool_schema(tool)     # 產生 JSON schema
  └─ _parse_description(path)  # 從 docstring 提取描述

linebot_ai.py
  └─ _handle_tool_call()     # 修改：skill__ 前綴 → ScriptToolRunner
                             #        mcp__ 前綴 → MCP client（不變）
```

## 檔案變更

| 檔案 | 變更 |
|------|------|
| `skills/__init__.py` | SkillManager 新增 `_scan_scripts()`、`script_tools` 屬性 |
| `skills/script_runner.py` | **新增** ScriptToolRunner 類別 |
| `services/linebot_ai.py` | `_handle_tool_call()` 加入 `skill__` 路由 |
| `services/linebot_agents.py` | `generate_tools_prompt()` 加入 script tool 說明 |
| `api/skills.py` | Skill 詳情 API 加入 `script_tools` 欄位 |

## Tool 命名規則

```
skill__{skill_name}__{script_stem}

範例：
  scripts/get_forecast.py  →  skill__weather__get_forecast
  scripts/generate_ppt.py  →  skill__ai-ppt-generator__generate_ppt
```

## Script 參數傳遞

優先順序：
1. SKILL.md frontmatter 的 `scripts.{name}.args` 定義 → CLI args（`--city Taipei`）
2. 無定義時 → stdin JSON（`{"city": "Taipei"}`）

## 執行環境

```bash
# 工作目錄
/tmp/skill-runner/{session_id}/

# 環境變數
SKILL_NAME=weather
SKILL_DIR=/path/to/skills/weather
SKILL_ASSETS_DIR=/path/to/skills/weather/assets
# + SKILL.md 宣告的 .env 變數
```

## 安全邊界

- subprocess 執行，不共享記憶體
- timeout 預設 30 秒
- 工作目錄在 /tmp，不能寫回 skill 目錄
- 只繼承明確宣告的環境變數
