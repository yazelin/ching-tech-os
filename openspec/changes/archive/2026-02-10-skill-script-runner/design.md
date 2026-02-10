# Design — Skill Script Runner

## 設計決策

**路 3（通用 tool）**：一個 `run_skill_script` tool 搞定所有 script，不為每個 script 註冊獨立 tool。

理由：
- 實作量最小（一個 MCP tool + 一個 runner 類別）
- 跟 OpenClaw 的 `{baseDir}/scripts/` 模式相容
- 權限控制在 tool 內部做二次檢查（skill → app → user）

## 架構

```
MCP Tool: run_skill_script(skill, script, input)
  │
  ├─ 1. 權限檢查（user 有沒有此 skill）
  ├─ 2. 路徑驗證（script 存在、在 skill 目錄下）
  ├─ 3. ScriptRunner.execute()
  │     ├─ 組裝 command（python3/bash/uv run）
  │     ├─ 注入環境變數
  │     └─ subprocess 執行 + timeout + capture
  └─ 4. 回傳結果
```

## 權限模型

```
Tool 白名單層：run_skill_script（有任何 script skill 就加入）
        ↓
Tool 內部檢查：使用者有沒有此 skill 的權限（requires_app → user apps）
        ↓
路徑檢查：script 存在且在 skill/scripts/ 下
        ↓
執行
```

## 檔案變更

| 檔案 | 變更 |
|------|------|
| `skills/script_runner.py` | **新增** ScriptRunner 類別（execute, list_scripts） |
| `services/mcp/skill_script_tools.py` | **新增** `run_skill_script` MCP tool |
| `skills/__init__.py` | SkillManager 新增 `has_scripts()`, `get_script_path()`, `get_scripts_info()` |
| `services/bot/agents.py` | prompt 注入 script skill 使用說明 |
| `api/skills.py` | Skill 詳情 API 已有 `scripts` 欄位（Phase 3 可擴充） |

## MCP Tool 定義

```python
@mcp_tool
def run_skill_script(skill: str, script: str, input: str = "") -> str:
    """
    執行 skill 的 script。
    
    Args:
        skill: skill 名稱（例如 "weather"）
        script: script 檔名不含副檔名（例如 "get_forecast"）
        input: 傳給 script 的輸入（字串，script 自行解析）
    """
```

## Script 執行方式

根據副檔名決定執行器：
- `.py` → `uv run {script_path}` 或 `python3 {script_path}`（優先 uv）
- `.sh` → `bash {script_path}`
- 其他 → 不支援，回傳錯誤

參數傳遞：`input` 字串透過 stdin 傳入 script。

## Prompt 注入

有 script 的 skill，在 prompt 中加入說明：

```
【Script Tools】
以下 skill 提供可執行的 script，使用 run_skill_script 工具呼叫：

weather:
  - get_forecast: 取得天氣預報
  用法：run_skill_script(skill="weather", script="get_forecast", input="Taipei")

ai-ppt-generator:
  - generate_ppt: 用百度 API 生成 PPT
  用法：run_skill_script(skill="ai-ppt-generator", script="generate_ppt", input="經濟報告")
```

描述來源（優先順序）：
1. SKILL.md body 中的說明（{baseDir} 替換為 skill 路徑）
2. Script 檔頭的 docstring
3. 預設：`Execute {script} from {skill}`

## 執行環境

```bash
# 工作目錄
/tmp/skill-runner/{session_id}/

# 環境變數（自動注入）
SKILL_NAME=weather
SKILL_DIR=/path/to/skills/weather
SKILL_ASSETS_DIR=/path/to/skills/weather/assets

# 從 .env 繼承（需 SKILL.md metadata.openclaw.requires.env 宣告）
WEATHER_API_KEY=xxx
```

## 安全邊界

- subprocess 執行，不共享主進程記憶體
- timeout 預設 30 秒，可由 SKILL.md 覆蓋
- 工作目錄在 /tmp，不能寫回 skill 目錄
- 只繼承明確宣告的環境變數
- skill name + script name 都做路徑穿越驗證
- 二次權限檢查：tool 白名單 + skill 權限
