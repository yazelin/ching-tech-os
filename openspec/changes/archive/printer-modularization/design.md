# Design: Printer 整合模組化

## 架構決策

### D1: MCP server 合併放在 `claude_agent.py` 而非 `main.py`

合併邏輯放在 `_create_session_workdir()`（每次 AI session 建立時執行），而非應用啟動時。

理由：
- 與現有的 `.mcp.json` copy 邏輯同一處，改動集中
- `main.py` 的 `_start_extends_modules()` 只處理 lifespan，職責不同
- 合併結果寫入 `/tmp/session-xxx/.mcp.json`，是 session 級別的操作

### D2: contributes.yaml 掃描結果快取

每次 AI session 都重新掃描 `extends/*/contributes.yaml` 是多餘的（檔案不會在運行中改變）。

方案：模組級快取，啟動時掃描一次，後續 session 直接使用快取的 dict。

```python
# 模組級快取（None = 尚未載入）
_extends_mcp_servers: dict[str, dict] | None = None

def _load_extends_mcp_servers() -> dict[str, dict]:
    """掃描 extends/*/contributes.yaml，提取 mcp_servers 設定。
    結果快取，只在首次呼叫時掃描。"""
    global _extends_mcp_servers
    if _extends_mcp_servers is not None:
        return _extends_mcp_servers
    # ... 掃描邏輯 ...
```

### D3: extends/printer 的 Skill 載入不需額外工作

SkillManager 已有 `extends/*/skills/` 掃描邏輯（`__init__.py:308-312`），搬過去的 SKILL.md 會自動被載入，無需修改 SkillManager。

### D4: `prepare_print_file` 留在主系統的 ching-tech-os MCP server

`prepare_print_file` 做的是路徑轉換和 Office 轉 PDF，這些依賴主系統的 NAS 掛載和 LibreOffice。它不是 printer MCP server 的工具，而是 ching-tech-os server 的工具，只是碰巧服務於列印流程。搬出去反而會增加依賴複雜度。

### D5: permissions.py 中的 printer 權限保留

App 權限定義（`"printer": True`）和工具權限映射（`"prepare_print_file": "printer"`）留在主系統。這是主系統的權限框架，不隨模組搬遷。Printer 模組不啟用時，權限定義存在但無害（沒有對應的 Skill 和 MCP server）。

## 實作方式

### MCP 合併流程

```
_create_session_workdir()
│
├─ 1. 建立 session 目錄 + nanobanana symlink（不變）
│
├─ 2. 讀取 .mcp.json 基底
│     base = json.load(project_root/.mcp.json)
│     若不存在 → base = {"mcpServers": {}}
│
├─ 3. 合併 extends MCP servers
│     extends_servers = _load_extends_mcp_servers()  # 快取
│     for name, config in extends_servers.items():
│         if name not in base["mcpServers"]:  # 核心優先
│             base["mcpServers"][name] = config
│
├─ 4. 寫入 session .mcp.json
│     json.dump(base, session_dir/.mcp.json)
│
└─ return session_dir
```

### _load_extends_mcp_servers 實作

```python
def _load_extends_mcp_servers() -> dict[str, dict]:
    global _extends_mcp_servers
    if _extends_mcp_servers is not None:
        return _extends_mcp_servers

    result = {}
    extends_dir = Path(settings.extends_dir)
    if not extends_dir.is_dir():
        _extends_mcp_servers = result
        return result

    for contrib_path in sorted(extends_dir.glob("*/contributes.yaml")):
        try:
            config = yaml.safe_load(contrib_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("extends/%s contributes.yaml 解析失敗: %s",
                          contrib_path.parent.name, e)
            continue

        mcp_servers = config.get("mcp_servers") if isinstance(config, dict) else None
        if not isinstance(mcp_servers, dict):
            continue

        for name, server_cfg in mcp_servers.items():
            if not isinstance(server_cfg, dict):
                continue
            # ${PROJECT_ROOT} 變數替換
            resolved = _resolve_mcp_env_vars(server_cfg)
            result[name] = resolved

    _extends_mcp_servers = result
    if result:
        logger.info("extends MCP servers: %s", ", ".join(result.keys()))
    return result
```

### 變數替換

`contributes.yaml` 中的 `${PROJECT_ROOT}` 替換為 `settings.project_root`，複用 `main.py` 中 `_resolve_kwargs` 的相同模式。替換範圍限定在 `args` 陣列和 `env` dict 的 value 中。

### extends/printer/contributes.yaml

```yaml
# printer 模組對主系統的貢獻宣告
# MCP server 設定：主系統建立 AI session 時自動合併
mcp_servers:
  printer:
    command: uvx
    args: [printer-mcp]
```

Printer 不需要 lifespan hook（無 startup/shutdown 邏輯）。

## 修改檔案清單

| 檔案 | 動作 | 說明 |
|------|------|------|
| `services/claude_agent.py` | 修改 | `_create_session_workdir()` 改為合併式寫入，新增 `_load_extends_mcp_servers()` |
| `services/bot/agents.py` | 修改 | 移除 `PRINTER_TOOLS_PROMPT`、`APP_PROMPT_MAPPING["printer"]`、`_FALLBACK_TOOLS["printer"]` |
| `modules.py` | 修改 | `docs-tools.app_ids` 移除 `"printer"` |
| `.mcp.json.example` | 修改 | 移除 printer server 設定 |
| `skills/printer/SKILL.md` | 刪除 | 搬到 extends |
| `extends/printer/contributes.yaml` | 新增 | MCP server 宣告 |
| `extends/printer/skills/printer/SKILL.md` | 新增 | 從 backend 搬過來 |
