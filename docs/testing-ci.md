# 開發機安裝與高測試率 CI 指引

本文件用於標準化本機與 GitHub Actions 的測試流程，讓提交到 repo 時能自動驗證後端測試與 coverage。

## 1. 開發機安裝（本機）

### 系統需求
- Python 3.11+
- Node.js 20+
- Docker / Docker Compose
- `uv`

### 專案依賴安裝

```bash
# repo 根目錄
npm ci

# 前端依賴（目前由根目錄 `scripts/build-frontend.mjs` 以 esbuild 打包）
cd frontend && npm ci && cd ..

# 後端（含 dev 依賴）
cd backend && uv sync && cd ..
```

## 2. 本機測試流程

### 快速檢查（建議每次 push 前）

```bash
npm run ci:check
```

此指令會執行：
1. `npm run build`
2. `npm run test:backend:cov`

### 分步執行

```bash
# 前端建置
npm run build

# 後端全量測試
npm run test:backend

# 後端 coverage 測試（門檻 81%）
npm run test:backend:cov

# 下一階門檻預檢（82%，不作為目前 CI Gate）
npm run test:backend:cov:next
```

### 單一測試（快速迭代）

```bash
cd backend

# 單一測試檔
uv run pytest tests/test_bot_api_routes.py -v

# 單一測試案例
uv run pytest tests/test_bot_api_routes.py::test_bot_groups_returns_200 -v

# 關鍵字篩選
uv run pytest -k permissions -v
```

## 3. GitHub CI/CD 測試流程

已新增 workflow：`.github/workflows/backend-tests.yml`

### 觸發時機
- push 到 `main`
- pull request 到 `main`
- 手動 `workflow_dispatch`

### CI 會做的事
1. 建立 Python 3.11 + uv 環境
2. `uv sync` 安裝後端依賴
3. 執行 pytest + coverage：
   - `--cov=src/ching_tech_os`
   - `--cov-fail-under=81`
   - 產生 `coverage.xml`、`htmlcov/`、`pytest-report.xml`
4. 上傳測試報告 artifacts（供下載檢查）

> 既有 `lighthouse.yml` 會繼續處理前端 Lighthouse 品質檢查。

## 4. 提高測試率的落地規則

### Coverage 門檻拉升節奏（Step-by-step）
- **目前 CI Gate**：81%
- **下一階預檢**：82%（使用 `npm run test:backend:cov:next`）
- **建議拉升規則**：當 `cov:next` 在主分支連續穩定通過後，再把 CI Gate 提升到同等門檻（每次 +1%）。

### 後端 API / Service 變更
- 新增或修改 API 路由時，至少補對應 `backend/tests/` 測試（成功與錯誤情境）。
- 權限相關邏輯需至少涵蓋：
  - 允許情境（admin/有權限）
  - 拒絕情境（一般 user/無權限）

### MCP 工具變更
- 新工具放在 `backend/src/ching_tech_os/services/mcp/`。
- 測試需涵蓋權限檢查與錯誤路徑。
- 涉及 DB 的工具需先 `await ensure_db_connection()`（依專案既有慣例）。

### 回歸測試策略
- 修 bug 時，先補能重現 bug 的測試，再修程式，避免回歸。
- 合併前至少跑一次 `npm run ci:check`。

## 5. Push 後確認 CI

```bash
git push origin <branch-name>
gh run list --limit 5
gh run watch
```

若 workflow 失敗，先在本機重跑：

```bash
npm run ci:check
```

確認修正後再重新 push。
