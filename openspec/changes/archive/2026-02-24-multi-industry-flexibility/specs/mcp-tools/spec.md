## ADDED Requirements

### Requirement: MCP 工具條件載入機制
`services/mcp/__init__.py` SHALL 依啟用模組動態載入 MCP 工具子模組，取代目前的靜態全量 import。

#### Scenario: 內建模組 MCP 工具條件載入
- **WHEN** 內建模組啟用且 `ModuleInfo` 包含 `mcp_module`
- **THEN** SHALL 使用 `importlib` 動態載入該 MCP 工具子模組

#### Scenario: 停用模組的 MCP 工具不載入
- **WHEN** 內建模組停用（如 `file-manager` 停用）
- **THEN** 對應的 `nas_tools.py` SHALL 不被 import，其工具不註冊到 MCP Server

#### Scenario: Skill MCP 工具載入
- **WHEN** Skill 的 `contributes.mcp_tools` 指定了 Python 檔案
- **THEN** SHALL 從 Skill 安裝目錄載入該檔案中以 `@mcp.tool()` 註冊的工具

#### Scenario: 載入失敗 graceful 降級
- **WHEN** MCP 工具子模組載入失敗（import error 或語法錯誤）
- **THEN** SHALL log warning 並跳過，其他模組的工具 SHALL 正常運作
