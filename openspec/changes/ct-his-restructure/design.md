## Context

ct-his（ching-tech-his）目前是 CTOS 的 git submodule，掛載於 `extends/his/`。內容僅有一份 54KB 的 README 知識報告和 `archive/` 下的分析腳本（Python 回診率/藥品分析、PowerShell 資料收集），沒有任何可被 CTOS 主系統載入的程式碼。

杰膚美皮膚科是第一個使用 ct-his 的客戶。目前已完成 HIS 資料分析，LINE 衛教 Bot 的平台功能也已在 CTOS 中實作完成（受限模式、Agent 分流、頻率限制等），但 ct-his 本身尚未模組化，無法被主系統動態載入。

本次重構僅涉及 ct-his submodule 內部的目錄結構調整，不修改 CTOS 主系統程式碼。主系統整合（SkillManager 掃描 extends/）將在後續 change 進行。

## Goals / Non-Goals

**Goals:**
- 建立清晰的 ct-his 目錄結構，區分通用引擎（core/）與客戶設定（clients/）
- 定義 config.yaml 客戶設定檔格式，支援多客戶部署
- 建立 SKILL.md，為後續被 CTOS SkillManager 載入做好準備
- 建立 core/mcp_tools.py 工具骨架（函式簽名，尚未完整實作）
- 遷移現有分析腳本至客戶目錄
- 建立 jfmskin-full Agent prompt（完整模式）
- 匯出現有 jfmskin-edu Agent prompt 到版控

**Non-Goals:**
- 不修改 CTOS 主系統的 modules.py 或 SkillManager（下一個 change）
- 不實作完整的 HIS runtime 功能（DBF 即時讀取、預約查詢 API）
- 不處理 CTOS 多租戶部署機制
- 不建立 HIS 前端管理介面

## Decisions

### D1: 客戶設定放 ct-his 內部，不獨立 submodule

**選擇**：`clients/{client_code}/` 資料夾

**替代方案**：
- 每個客戶一個獨立 submodule → 管理成本過高，客戶資料夾只是設定檔不是程式碼
- 客戶設定放 CTOS 主系統 → 耦合太緊，ct-his 應自包含

**理由**：ct-his 已是 private repo，客戶設定（連線資訊、Agent prompt、功能開關）與 HIS 引擎高度相關，放在同一個 repo 統一管理最合理。新增客戶只需複製 `_template/` 資料夾。

### D2: 用 SKILL.md contributes 做模組宣告（而非自定義格式）

**選擇**：遵循 CTOS 現有的 Skill contributes 規範

**替代方案**：
- 在 modules.py 新增 `EXTENDS_MODULES` 硬編碼 → 不夠彈性
- 自定義 `module.yaml` 格式 → 增加認知負擔

**理由**：CTOS 已有完整的 Skill → ModuleInfo 轉換管道（`_build_skill_module()`），SKILL.md 支援 `contributes.mcp_tools`、`contributes.scheduler`、`contributes.app`，完全滿足 ct-his 的需求。後續只需讓 SkillManager 多掃描 `extends/` 路徑即可。

### D3: config.yaml 格式用 YAML 而非環境變數

**選擇**：結構化的 YAML 設定檔 + 環境變數補充敏感資訊

**替代方案**：
- 純環境變數 → 扁平結構難以表達嵌套設定（features 開關、agents 對應等）
- JSON → 不支援註解，對人類不友善

**理由**：YAML 支援註解和嵌套結構，適合作為客戶部署的設定範本。敏感資訊（密碼、token）不放 YAML 中，改用環境變數引用，兼顧安全與可讀性。

### D4: Agent prompt 以 .md 檔案版控，部署時 seed 進 DB

**選擇**：`clients/{client_code}/agents/*.md` 作為 source of truth

**替代方案**：
- 只在 DB 管理 prompt → 無版本歷史，難以跨環境同步
- 在 migrations 中維護 prompt → 不適合客戶級別的設定

**理由**：Agent prompt 是客戶特定的核心設定，需要版控追蹤變更歷史。目前 jfmskin-edu 的 prompt 已在 DB 中，匯出到檔案後兩邊保持一致。未來部署新客戶時，seed 腳本會從檔案讀取並寫入 DB。

### D5: core/ 先建骨架，不做完整實作

**選擇**：函式簽名 + docstring + `raise NotImplementedError`

**理由**：本次重構目標是建立結構，runtime 功能（DBF 連線、資料查詢）需要在有測試環境後逐步實作。先定義介面讓後續開發有明確的契約。

## Risks / Trade-offs

**[config.yaml 與環境變數的同步]** → 部署時需確保 config.yaml 的 `connection` 設定與實際環境變數一致。透過 `.env.example` 範本和部署檢查清單降低風險。

**[Agent prompt 檔案與 DB 的一致性]** → 兩處來源可能不同步。建立 seed 機制：部署時從檔案更新 DB，但允許在 DB 中微調（DB 為 runtime 來源）。

**[SKILL.md 尚未被主系統掃描]** → 本次建立的 SKILL.md 暫時不會被載入，需等後續 change 完成 SkillManager 擴展。這是預期行為，不影響本次重構。

**[分析腳本搬移後路徑變更]** → 腳本中可能有硬編碼的相對路徑。搬移時不修改內容，若有路徑問題在使用時再調整。

## Open Questions

- **HIS_CLIENT 環境變數的使用時機**：runtime 時如何決定載入哪個客戶的 config.yaml？初步設計用 `HIS_CLIENT=jfmskin` 環境變數，但需在下一個 change（主系統整合）時確定載入流程。
- **Agent prompt seed 機制**：是在 CTOS 啟動時自動 seed（if not exists），還是提供手動指令？待後續 change 設計。
