## Why

ct-his（展望 HIS 整合）子模組目前只有 archive 分析腳本，沒有可被 CTOS 主系統載入的模組結構。隨著杰膚美診所即將部署 CTOS + HIS 整合方案，需要將 ct-his 重構為標準化的目錄結構，支援通用 HIS 引擎（core/）與多客戶部署設定（clients/），為後續整合進主系統的 Skill 機制做好準備。

## What Changes

- 在 ct-his 中建立 `core/` 目錄，放置通用 HIS 服務（DBF 讀取引擎、展望 HIS API 抽象層、預約管理等）
- 在 ct-his 中建立 `clients/` 目錄結構，每個客戶一個資料夾（首個客戶：`clients/jfmskin/`）
- 建立 `clients/_template/` 作為新客戶部署的範本
- 客戶資料夾包含：連線設定（config.yaml）、Agent prompt 定義、衛教知識種子、部署筆記
- 將現有的 `archive/` 分析腳本搬移至 `clients/jfmskin/analysis/`
- 在 ct-his 根目錄建立 `SKILL.md`，宣告 contributes（mcp_tools、scheduler），為下一階段主系統整合做準備
- 建立 `core/mcp_tools.py` 骨架，定義 HIS MCP 工具介面（查預約、查病患、查處方等）

## Capabilities

### New Capabilities
- `his-module-structure`: ct-his 子模組的目錄結構規範，包含 core/（通用引擎）、clients/（客戶設定）、SKILL.md（模組宣告）的組織方式與檔案格式定義
- `his-client-profile`: 客戶部署設定檔格式（config.yaml），涵蓋連線設定、功能開關、Agent 指定、頻率限制等客戶級別的配置規範

### Modified Capabilities
（無，本次變更僅在 ct-his 子模組內重構，不修改主系統程式碼）

## Impact

- **ct-his submodule**（`extends/his/`）：主要影響，目錄結構全面重構
- **主系統程式碼**：本次不修改，整合將在後續 change 進行
- **現有分析腳本**：搬移位置但不修改內容（`archive/` → `clients/jfmskin/analysis/`）
- **杰膚美 Agent**：`jfmskin-edu` prompt 從 DB 匯出到 `clients/jfmskin/agents/` 版控，DB 仍為 runtime 來源
- **依賴**：無新 Python 依賴（本次僅建立結構骨架，runtime 程式碼在後續填入）
