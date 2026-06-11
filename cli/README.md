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

### 非互動環境登入

`ctos login` 預設互動輸入帳密，**沒有終端機輸入的環境**（CI、Claude Code 的 `!` 指令等）請改用：

```bash
CTOS_PASSWORD=<密碼> ctos login --url https://ching-tech.ddns.net/ctos --username <帳號>
```

密碼只從環境變數讀取、不接受命令列參數（避免留在 shell history 與 process list）。

## 指令一覽

| 指令 | 說明 |
|------|------|
| `ctos login [--url URL] [--username 帳號] [--name 名稱] [--expires-days N] [--scope APP]... [--read-write]` | 登入並換發 API token |
| `ctos logout` | 清除本機 token（伺服器端 token 需另行撤銷） |
| `ctos whoami` | 顯示目前身份與 token 資訊 |
| `ctos token list` | 列出自己的 API token（需重新輸入帳密） |
| `ctos token revoke <id>` | 撤銷 API token（需重新輸入帳密） |
| `ctos kb get <kb-id> [--json] [--content-only]` | 讀取知識條目 |
| `ctos kb search <關鍵字> [--scope] [--type] [--category] [--project] [--topic]... [--json]` | 全文搜尋 |
| `ctos kb attachments <kb-id> [--download [目錄]]` | 列出 / 下載附件 |
| `ctos kb add --title T (--content C \| --file F) [--scope] [--topic]...` | 新增知識條目（需可寫 token） |
| `ctos kb update <kb-id> [--title] [--content \| --file] [--scope] [--topic]...` | 更新知識條目（需可寫 token） |
| `ctos lib ls [子路徑] [--json]` | 瀏覽圖書館目錄 |
| `ctos lib get <路徑> [--out 檔名或目錄]` | 下載圖書館檔案 |
| `ctos files ls [來源/子路徑] [--json]` | 瀏覽 NAS 掛載區（projects / circuits / library；不給路徑列出來源） |
| `ctos files get <來源/路徑> [--out]` | 下載 NAS 掛載區檔案（如 `circuits/某機台/線路圖.pdf`） |
| `ctos erp find <關鍵字>` | ERPNext 物料搜尋（比對料號與品名） |
| `ctos erp item <料號>` | 物料明細（單位、採購價、交期） |
| `ctos erp stock <料號> [--warehouse]` | 各倉庫存（含保留/在途） |
| `ctos erp boms <料號>` / `ctos erp bom <BOM名>` | BOM 清單與明細 |

ERP 查詢需要 token scope 含 `inventory-management`（0.1.5 起 `ctos login` 預設已涵蓋；
舊 token 要用 erp 指令請重新 `ctos login`）。全部唯讀，走 CTOS 的 `/api/erp` proxy，
ERPNext 憑證只存在伺服器端，不會發到個人機器。

## 環境變數

| 變數 | 說明 |
|------|------|
| `CTOS_URL` | 覆寫服務網址 |
| `CTOS_TOKEN` | 覆寫 API token（CI / 自動化用） |
| `CTOS_PASSWORD` | 非互動登入用密碼（只在 `ctos login` / `ctos token` 時讀取） |
| `CTOS_CONFIG` | 覆寫設定檔路徑（預設 `~/.ctos/config.json`） |

## 寫入知識庫

`kb add` / `kb update` 需要**可寫 token**（預設換發的是唯讀）：

```bash
ctos login --read-write                       # 重新換發可寫 token
ctos kb add --title "部署踩雷記錄" --file note.md --scope global --topic 部署
echo "內容" | ctos kb add --title "標題" --file -   # 從 stdin
```

權限規則（伺服器端強制）：

- `--scope personal`（預設）：自動掛 owner，只有自己讀得到
- `--scope global`：需要 `global_write` 權限（請管理者在後台開），全員可讀
- `--scope project`：需 `--project-id`，專案成員可編輯
- 更新別人的條目：需要是 owner，或具 `global_write`，或 admin

## 安全說明

- token 預設唯讀（伺服器端強制：非 GET 請求一律 403）、scope 只含 knowledge-base
- 用唯讀 token 跑寫入指令會收到引導訊息（提示 `ctos login --read-write`）
- token 外洩時：`ctos token revoke <id>`，或請管理者把帳號停用
- `scope: personal` 的知識條目只有 owner 本人讀得到
