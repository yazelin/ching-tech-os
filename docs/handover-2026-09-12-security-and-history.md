# 接手文件：2026-09-12 安全修補、止血分支、公開歷史清理（給下一個 session 或 yazelin）

寫於 2026-09-12 08:5x，狀態凍結在「步驟二完成、等 yazelin 點頭」。**.11 正式機自 2026-09-11 22:2x 後沒動過**（HEAD `0b982f1`，alembic 029）。

## 一、三份文件各自是什麼、給誰看、閱讀順序

| 檔案 | 內容 | 給誰 | 先後 |
|---|---|---|---|
| `docs/decision-2026-09-real-names-in-history.md` | 公開 repo 歷史裡兩個真實客戶名（A、B）值不值得清：性質、實際外部可見度、三個選項與代價、建議 | yazelin 決定「要不要」 | **第一** |
| `docs/runbook-2026-09-rewrite-history.md` | 清歷史怎麼跑：`git-filter-repo` 指令、本機驗證、force-push、下游重建、退路 | 決定要清之後照著跑 | 第二 |
| `docs/deploy-2026-09-erp-rollout.md` | 部署清單：選項 A 只部署安全修補（`hotfix/unbound-guards`）、選項 B 一次全套（migration 030–033）；含維護規則、驗證項、會打斷誰、退路 | yazelin 決定部署 | 第三 |

**相依關係**：改寫歷史會讓 2 月以後所有 commit hash 變掉 → 部署清單裡每個 hash（`0b982f1`、hotfix 的 `f1aaafb`、退路指令）全部失效，`hotfix/unbound-guards` 要重建。所以**要嘛先部署再清歷史，要嘛清完歷史照 runbook 步驟六重寫清單再部署**；不要在改寫進行中部署。清歷史不影響 migration 與資料，只影響 hash。

## 二、現在停在哪一步、為什麼

清歷史六步（監督 session 排的）：
1. 備份 — **完成**。mirror clone 229 個 ref（含 195 個 pull refs、7 個 tag），從備份 checkout 舊 commit 驗證過可還原；tarball 在 NAS `/mnt/nas/ctos/backups/git/ching-tech-os-mirror-20260912-0831.tar.gz`，sha256 前 16 碼 `ca23167631390448`（本機與 NAS 一致）。
2. 清場 — **完成**。刪了 22 支已合併／已關閉的遠端分支（清單在監督 session 對話與本機 scratchpad）；留 `main`、`hotfix/unbound-guards`、`trial`、`fix/his-submodule-url`（#171 open）、`fix/redact-bot-token-in-logs`（#172 open）；本機 worktree 與過期分支清光。
3. 改寫 — **未開始**。
4. 驗證 — 未開始。
5. force-push — 未開始。
6. 重建下游 — 未開始。

**停在這裡的原因**：force-push 是不可逆、影響外部的動作，yazelin 不在旁邊；監督 session 裁定「做到一切就緒、只差按下去」。yazelin 的原話是「公司名公開可以改嗎 清掉公開的歷史吧」，但他還沒看過決策文件裡的第三節（B 在 10 個 fork 裡收不回、GitHub 要 Support 申請才清乾淨）。**他看過之後再點頭，才進步驟三。**

## 三、兩個決定「有沒有用」的問題（已查，答案要讓 yazelin 看到）

1. **有沒有 fork、有沒有人 clone**：fork **10 個**（2026-01-08～07-06 建立，最後 push 都早於 9/12）。名字 A（9/12 引進）**不在任何 fork**——清歷史對 A 有效；名字 B（1/6 起）**10 個 fork 全部都有**——主 repo 清了收不回。clone 查不到，但 CLI 安裝指令 `uv tool install "git+https://github.com/yazelin/ching-tech-os.git#subdirectory=cli"` 會把整個 repo 含歷史 clone 進每個使用者的 uv 快取，同事也依 onboarding 文件 clone 過。GitHub 上 force-push 後舊 commit 仍可用 hash 開、`refs/pull/*` 保留，要向 GitHub Support 申請清除。
2. **.11 之外的 checkout**：這台開發機 `/home/ct/SDD/ching-tech-os`；.11 的 `~/SDD/ching-tech-os` 與 `/tmp/ching-tech-os-cli-*` 暫存；同事機器數量不明。

結論：清歷史對 A 有實際效果、對 B 幾乎只是主 repo 這一份。這兩題的答案沒讓 yazelin 看到之前，不要開始改寫。

## 四、安全修補家族的全貌（共同成因要留著）

**共同成因**：這套 MCP／REST 權限設計假設「呼叫者是已綁定 CTOS 帳號的自己人」，但 LINE／Telegram bot 對外開放，未綁定者一路走得進來；而且很多 REST 端點只驗登入不驗 app 權限（舊桌面靠前端擋點擊）。今天撞出來的七個：

| issue | 洞 | 修法 PR |
|---|---|---|
| #201 | 未綁定者讀員工成員清單、專案任務、廠商聯絡人、NAS 檔案內容 | #206：`APPS_REQUIRE_BOUND_USER`（專案、往來對象、物料、檔案管理）一律拒絕 |
| #207 | 未綁定者匿名寫進全域知識庫（scope=global、owner=None） | #212：`add_note`／`add_note_with_attachments` 未綁定拒絕 |
| #204 | 記憶工具身分靠模型帶入的 id，宣稱是誰就是誰 | #212：`build_bot_mcp_env()` 注入群組／使用者 id，`resolve_bot_identity()` 覆寫參數 |
| #205 | 分享連結不驗資源存取權 | #216：`check_resource_access()`，兩支分享工具對到 `share-manager`、未綁定拒絕 |
| #217 | 內部讀得到＝可以發到網際網路（read 判斷太寬＋share-manager 預設開） | #219：`share-manager` 預設 False；REST 建連結端點掛權限 |
| nas 那條（#219 review 追加） | `send_nas_file`／`prepare_file_message` 間接建公開連結只掛 file-manager | #219：建連結前也要 `share-manager` |
| 矩陣 | 74 支工具逐一標「未綁定可否呼叫、是否寫入、身分來源」 | #212：`docs/mcp-tool-access-matrix.md`，由 `backend/scripts/gen_tool_access_matrix.py` 產生，測試釘住不漂移 |

**教訓（已寫進記憶）**：修一個洞時「沿用既有的 read 判斷」前要先看那判斷有多寬（#217 就是從 #216 繼承來的）；公開／外送類動作預設 False 由管理員逐人開；REST 與 MCP 要一起查。

`hotfix/unbound-guards`（`f1aaafb`）= .11 的 `0b982f1` ＋ #206 #212 #216 #219，無 migration，全套 1921 passed、90.24%；可單獨部署，指令在部署清單選項 A。

## 五、還開著的 issue

| # | 是什麼 | 等級 |
|---|---|---|
| #199 | 舊桌面 Agent 設定的 skill 編輯器不認 `requires_app` 清單，存檔會把 erp skill 弄消失 | 低，功能缺陷 |
| #200 | 專案模組沒有 audit（REST 與 MCP 寫入都沒紀錄） | 中，可見性缺口 |
| #209 | 六支工具（`add_note`、`search_knowledge`、`send_nas_file`、`get_message_attachments`、`summarize_chat`…）仍吃模型帶入的 line id，已綁定者也可冒充跨群組讀寫 | **高**，同家族，修法同 #204 |
| #210 | 18 支工具完全沒走權限檢查（含 `prepare_print_file` 未綁定可送印）；網頁聊天路徑沒注入身分 | **高**，同家族的系統性收尾 |
| #211 | `add_attachments_to_knowledge` 呼叫不存在的函式，附件描述靜默失敗 | 低，既有 bug |
| #218 | bot 建的分享連結 `created_by=linebot`，使用者看不到也撤不掉 | 中，外洩時撤不掉 |
| #220 | docs/security.md 環境變數表把 `SESSION_TTL_HOURS` 寫錯名 | 低，文件 |

## 六、名字 A 是本 session 引進的；規則已加

名字 A 是 2026-09-12 我（Claude，本 session）寫 ERP 規格（commit `4e845b4`）時拿真實客戶當範例，之後 #192 的測試與 docstring 沿用；不是舊資料。名字 B 是 1 月就在的路徑範例。工作樹已在 PR #222 全部換成杜撰名（反向掃描 7828 個變形 0 命中）；歷史處理見第一、二節。

防再犯：`CLAUDE.md` 與 `AGENTS.md`（#223）、ctos-web `CLAUDE.md`（#19）都加了「真實客戶／廠商資料不得進 repo，含規格、測試資料、commit 訊息；範例用杜撰名；動資料相關程式碼要反向掃描」。反向掃描腳本 `sweep_real_names.py` 目前在本機 scratchpad，依賴備份路徑；放進 repo 前要改吃參數（待辦）。

## 七、其他今天的線（已收）

ERP 八支：#187 規格、#190 備份、#192 後端、#194、#196、#197 匯入腳本、#198 bot 切換、#202 專案工具全部合併 main；ctos-web #15～#18 全部上 Pages。剩 PR 8 停用 ERPNext（部署與匯入之後、要授權）。
