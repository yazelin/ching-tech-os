---
name: ctos-kb
description: 透過 ctos CLI 遠端存取 ching-tech-os（CTOS）的公司資料：知識庫（kb-NNN）、圖書館、NAS 掛載區（專案圖面 projects / 線路圖 circuits）、ERPNext（物料/庫存/BOM）。當使用者提到 kb-NNN、要查知識庫/圖書館/圖面/線路圖、查料號/庫存/BOM，或說「我要開發 kb-XXX 的功能」需要背景資料時使用。
---

# CTOS 資料存取（知識庫 / 圖書館 / NAS / ERP）

CTOS 知識庫條目以 `kb-NNN` 編號（如 kb-182），存放在部署機上，透過 `ctos` CLI 以 HTTP API 遠端讀取。

## 前置確認

```bash
ctos --version    # 沒裝：見 cli/README.md（uv tool install）
ctos whoami       # 沒登入或 token 過期：請使用者執行 ctos login（互動式，需帳密，Claude 不能代跑）
```

`ctos login` 需要互動輸入帳號密碼，請使用者自己在終端機執行（在 Claude Code 中可用 `! ctos login`）。

## 常用指令

```bash
# 讀取單一條目（人類可讀格式；--json 完整欄位；--content-only 只要 Markdown 內文）
ctos kb get kb-182
ctos kb get kb-182 --json

# 全文搜尋（空白分隔關鍵字 = AND；ripgrep 後端）
ctos kb search "AI 升級"
ctos kb search 補助 --scope global --topic CTOS

# 附件
ctos kb attachments kb-182                  # 列出
ctos kb attachments kb-182 --download tmp/  # 全部下載到 tmp/

# 圖書館（規格書、型錄、教育訓練等原始檔案）
ctos lib ls                  # 根目錄分類
ctos lib ls 技術文件          # 瀏覽子目錄
ctos lib get 技術文件/規格書.pdf --out tmp/

# 寫入（需可寫 token：使用者要先 ctos login --read-write）
ctos kb add --title "標題" --file note.md --scope global --topic 主題
ctos kb update kb-123 --content "新內容" --topic 新主題

# NAS 掛載區（專案圖面、線路圖）
ctos files ls                          # 列出來源：projects / circuits / library
ctos files ls projects/某專案          # 瀏覽專案資料
ctos files get circuits/某機台/線路圖.pdf --out tmp/

# ERPNext（物料 / 庫存 / BOM，唯讀）
ctos erp find 馬達                     # 關鍵字搜尋物料（料號+品名）
ctos erp item <料號>                   # 明細（單位、採購價、交期）
ctos erp stock <料號>                  # 各倉庫存（含保留/在途）
ctos erp boms <料號> / ctos erp bom <BOM名>
```

## 開發工作流（使用者說「我要開發 kb-182 的某功能」時）

1. `ctos kb get kb-182` 取得條目全文與附件清單
2. 從內容提取關鍵字，`ctos kb search` 找相關條目（規格、決策記錄、先前討論）
3. 需要規格書 / 型錄時 `ctos lib ls` 瀏覽圖書館
4. 有 docx / pdf 附件時下載後再讀（docx 可用 officecli 或 python-docx 解析）
5. 彙整背景後才開始規劃實作

## 注意事項

- **scope 權限**：`scope: personal` 的條目只有 owner 看得到，API 回 404 不代表條目不存在。請使用者確認該條目是否為 global / project scope，或請 owner 調整。
- token 預設唯讀且只有 knowledge-base scope，效期 180 天。401 錯誤＝token 過期，請使用者重新 `ctos login`；用唯讀 token 跑 `kb add`/`kb update` 會收到 403 與換發指引（`ctos login --read-write`，互動式，要使用者自己跑）。
- 寫入的 scope 規則：預設 personal（只有作者讀得到）；團隊共用要 `--scope global`（需 global_write 權限）或 `--scope project`（需 --project-id）。開發完把決策/心得寫回知識庫時，先問使用者要哪種 scope。
- 搜尋結果的 `snippet` 是 ripgrep 匹配片段，要全文請再 `kb get`。
- 服務網址等設定存於 `~/.ctos/config.json`，可用環境變數 `CTOS_URL` / `CTOS_TOKEN` 覆寫（CI / 自動化情境）。
- `erp` 指令需要 token scope 含 `inventory-management`（0.1.5 起 login 預設涵蓋）；收到「無物料管理功能權限」403 時請使用者重新 `ctos login`（舊 token scope 不含）。
- ERP 全部唯讀、走 CTOS proxy，ERPNext 憑證不在個人機器上——不要嘗試直連 ERPNext。
