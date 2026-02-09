# Spec: ClawHub REST API 替換

## Purpose
將 ClawHub 整合從 CLI 子程序改為直接打 REST API，提升搜尋體驗與可靠性。

### Requirement: ClawHubClient class
系統 SHALL 提供 `ClawHubClient` class，使用 `httpx.AsyncClient` 與 ClawHub REST API 溝通。
- Base URL: `https://clawhub.ai/api/v1`
- 不允許 redirect follow（SSRF 防護）
- 連線 timeout 5s，讀取 timeout 30s，下載 timeout 60s

#### Scenario: 搜尋 skills
WHEN 使用者在 ClawHub tab 輸入搜尋關鍵字
THEN 系統呼叫 `GET /search?q={query}&limit=20`
AND 回傳結果包含 slug, displayName, summary, version, score, updatedAt
AND 前端顯示搜尋結果卡片（含作者、版本、描述、相關度）

#### Scenario: 取得 skill 詳情
WHEN 使用者點擊「預覽」按鈕
THEN 系統呼叫 `GET /skills/{slug}`
AND 回傳結果包含 owner（handle, displayName, image）、stats、latestVersion、changelog
AND 同時呼叫 `GET /download?slug={slug}&version={version}` 取得 SKILL.md 內容（從 ZIP 解壓）
AND 前端右側面板顯示完整 metadata + SKILL.md 內容

#### Scenario: 安裝 skill
WHEN 管理員點擊「安裝」按鈕
THEN 系統呼叫 `GET /download?slug={slug}&version={version}` 下載 ZIP
AND 驗證 ZIP 大小不超過 10MB
AND 解壓時驗證每個 entry path 不含 `..`（zip slip 防護）
AND 解壓到 `skills/{slug}/` 目錄
AND 寫入 `_meta.json`（slug, version, source: "clawhub", installed_at, owner）
AND 呼叫 `SkillManager.reload()` 熱載入
AND 若 skill 宣告必填 ENV，自動開啟 ENV 設定精靈

### Requirement: 移除 CLI 依賴
系統 SHALL 移除 `_run_clawhub` helper function。
系統 SHALL 更新 `install-service.sh`，移除 `clawhub` CLI 安裝步驟（加註解保留備用）。
系統 SHALL 在 `pyproject.toml` 新增 `httpx` 依賴。

### Requirement: 前端搜尋結果升級
前端搜尋結果卡片 SHALL 顯示以下資訊：
- Skill 名稱（displayName）
- 作者（owner handle）
- 描述（summary，截斷 2 行）
- 版本號
- 相關度百分比
- 更新時間（相對時間，如「3 天前」）

#### Scenario: 搜尋結果無作者
WHEN ClawHub API 回傳的 skill 沒有 owner 資訊
THEN 前端顯示「未知作者」

### Requirement: 快取策略
系統 SHOULD 對搜尋結果快取 5 分鐘（TTL），減少重複請求。
系統 SHOULD 對 skill 詳情快取 1 小時。

### Requirement: _meta.json 格式
安裝的 skill 目錄 SHALL 包含 `_meta.json`：
```json
{
  "slug": "nanobanana-pro-fallback",
  "version": "0.4.4",
  "source": "clawhub",
  "installed_at": "2026-02-10T01:00:00Z",
  "owner": "yazelin"
}
```
內建 skill（無 `_meta.json`）SHALL 被視為 `builtin` 來源。
