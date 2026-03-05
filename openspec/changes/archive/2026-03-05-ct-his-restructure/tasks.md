## 1. 頂層目錄結構建立

- [x] 1.1 在 ct-his 根目錄建立 `core/`、`core/services/`、`clients/`、`clients/_template/`、`clients/jfmskin/` 目錄結構
- [x] 1.2 建立 `core/__init__.py`
- [x] 1.3 更新 ct-his 的 `README.md`，說明新的目錄結構與用途

## 2. core/ 通用 HIS 引擎骨架

- [x] 2.1 建立 `core/services/dbf_reader.py` — DBF 讀取引擎骨架（cp950 編碼、民國年日期轉換函式簽名 + docstring + NotImplementedError）
- [x] 2.2 建立 `core/services/vision_his.py` — 展望 HIS API 抽象層骨架（病患查詢、掛號紀錄、處方查詢、預約查詢函式簽名）
- [x] 2.3 建立 `core/services/__init__.py`
- [x] 2.4 建立 `core/models.py` — 共用 Pydantic 資料模型（Patient、Appointment、Prescription 等骨架）
- [x] 2.5 建立 `core/mcp_tools.py` — HIS MCP 工具定義（查預約、查病患、查處方的函式簽名）

## 3. SKILL.md 模組宣告

- [x] 3.1 在 ct-his 根目錄建立 `SKILL.md`，包含 frontmatter 的 contributes 定義（mcp_tools 指向 `core/mcp_tools.py`）

## 4. 客戶範本

- [x] 4.1 建立 `clients/_template/config.yaml` — 範本設定檔（所有欄位帶 YAML 註解：client、his、connection、agents、features、rate_limit）
- [x] 4.2 建立 `clients/_template/agents/` 目錄與空的 Agent prompt 範本檔
- [x] 4.3 建立 `clients/_template/README.md` — 新客戶部署檢查清單

## 5. 杰膚美客戶設定

- [x] 5.1 建立 `clients/jfmskin/config.yaml` — 杰膚美部署設定（填入已知資訊：Tailscale IP、展望 HIS、功能開關等）
- [x] 5.2 從 DB 匯出現有 `jfmskin-edu` Agent 的 system prompt，存為 `clients/jfmskin/agents/jfmskin-edu.md`
- [x] 5.3 建立 `clients/jfmskin/agents/jfmskin-full.md` — 杰膚美完整模式 Agent prompt（包含 HIS 工具使用說明）
- [x] 5.4 建立 `clients/jfmskin/deploy/.env.example` — 杰膚美部署環境變數範本
- [x] 5.5 建立 `clients/jfmskin/deploy/notes.md` — 部署筆記（硬體、網路、帳號資訊整理）

## 6. 現有腳本遷移

- [x] 6.1 將 `archive/analysis/*.py`（3 個分析腳本）搬移至 `clients/jfmskin/analysis/`
- [x] 6.2 將 `archive/*.ps1`（PowerShell 診所腳本）搬移至 `clients/jfmskin/deploy/scripts/`
- [x] 6.3 確認搬移後 `archive/` 目錄可清空（或保留 README 說明已遷移）

## 7. 驗證

- [x] 7.1 確認 ct-his 目錄結構符合 spec 定義
- [x] 7.2 確認 SKILL.md 的 frontmatter 可被 CTOS 的 `parse_skill_md()` 正確解析（手動測試）
- [x] 7.3 git commit 並 push ct-his submodule，更新主 repo 的 submodule 指向
