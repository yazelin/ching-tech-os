# ctos CLI

ching-tech-os 知識庫 / 圖書館遠端存取 CLI。讓同事在自己的開發機（Windows / macOS / Linux）上讀取 CTOS 的知識庫條目與圖書館檔案，也供 Claude Code 等 AI 工具透過 `ctos-kb` skill 使用。

純 Python 標準函式庫實作，無任何第三方依賴。

## 安裝

需要 Python 3.10+。建議用 [uv](https://docs.astral.sh/uv/)：

```bash
# 從 clone 下來的 repo 安裝
uv tool install ./cli

# 或不 clone，直接從 GitHub 安裝（需有 repo 權限）
uv tool install "git+https://github.com/yazelin/ching-tech-os.git#subdirectory=cli"

# 更新
uv tool upgrade ctos-cli
```

沒有 uv 的話 `pipx install ./cli` 也可以。

## 快速開始

```bash
# 首次設定：登入並換發長效 API token（預設唯讀、knowledge-base scope、180 天）
ctos login --url https://ching-tech.ddns.net/ctos

# 之後直接用
ctos whoami
ctos kb get kb-182
ctos kb search "AI 升級"
ctos kb attachments kb-182 --download
ctos lib ls
ctos lib get 技術文件/規格書.pdf
```

`ctos login` 會以帳號密碼登入一次，換發 PAT（personal access token）後立即登出 session；本機只保存 PAT（`~/.ctos/config.json`，權限 600），不保存密碼。

## 指令一覽

| 指令 | 說明 |
|------|------|
| `ctos login [--url URL] [--name 名稱] [--expires-days N] [--scope APP]... [--read-write]` | 登入並換發 API token |
| `ctos logout` | 清除本機 token（伺服器端 token 需另行撤銷） |
| `ctos whoami` | 顯示目前身份與 token 資訊 |
| `ctos token list` | 列出自己的 API token（需重新輸入帳密） |
| `ctos token revoke <id>` | 撤銷 API token（需重新輸入帳密） |
| `ctos kb get <kb-id> [--json] [--content-only]` | 讀取知識條目 |
| `ctos kb search <關鍵字> [--scope] [--type] [--category] [--project] [--topic]... [--json]` | 全文搜尋 |
| `ctos kb attachments <kb-id> [--download [目錄]]` | 列出 / 下載附件 |
| `ctos lib ls [子路徑] [--json]` | 瀏覽圖書館目錄 |
| `ctos lib get <路徑> [--out 檔名或目錄]` | 下載圖書館檔案 |

## 環境變數

| 變數 | 說明 |
|------|------|
| `CTOS_URL` | 覆寫服務網址 |
| `CTOS_TOKEN` | 覆寫 API token（CI / 自動化用） |
| `CTOS_CONFIG` | 覆寫設定檔路徑（預設 `~/.ctos/config.json`） |

## 安全說明

- token 預設唯讀（伺服器端強制：非 GET 請求一律 403）、scope 只含 knowledge-base
- token 外洩時：`ctos token revoke <id>`，或請管理者把帳號停用
- `scope: personal` 的知識條目只有 owner 本人讀得到
