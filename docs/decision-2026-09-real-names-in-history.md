# 決策材料：公開 repo 歷史裡的兩個真實客戶名（2026-09-12）

給 yazelin 一次看完。工作樹已在 PR #222 全部換成杜撰名（反向掃描 0 命中）；本文件只談 **git 歷史**怎麼辦。真實名稱本文件不寫，以 A、B 代稱（實際名稱在監督 session 的對話與本機 `.superpowers/sdd/real-names-cleanup/report.md`）。

## 一、兩個名字的性質（查 ERPNext 備份）

| | 在備份裡的身分 | 進 repo 的時間與方式 | 誰引進 |
|---|---|---|---|
| A | **客戶**（Customer，公司），另有一個專案、一位聯絡人、一個地址、一筆物料掛在它名下 | 2026-09-12，規格 `4e845b4` 起，之後 ERP 後端的測試與 docstring 沿用（14 個 commit） | **Claude（本 session）在寫 ERP 規格時拿真實客戶當範例**，不是舊資料 |
| B | **客戶**（Customer，公司），兩位聯絡人、一個地址 | 2026-01-06，`11ea630`（NAS 檔案搜尋）起，當路徑範例 `projects/B/layout.pdf` 用（10 個 commit） | 動工前就在 |

兩個都是客戶關係，等於公開了「擎添與某公司有往來」；沒有聯絡資料、電話、統編一起外流（那些只在 NAS 備份）。是否構成「客戶名單洩漏」由 yazelin 判斷：若這兩家公司名本來就在擎添的公開案例或網站上，性質就不同。

## 二、現在能從外面看到什麼（實際查到的，2026-09-12）

- **fork：10 個**（stars 32），建立於 2026-01-08 到 2026-07-06，最後 push 都早於 2026-09-12。
  - A：**不在任何 fork**。
  - B：**10 個 fork 全部都有**（都在 1/6 之後 fork）。fork 是別人的 repo，我們刪不了；主 repo 改寫或轉 private 都不影響它們。
- **clone**：查不到誰 clone 過。但 README、CLAUDE.md、cli/README 教的 `uv tool install "git+https://github.com/yazelin/ching-tech-os.git#subdirectory=cli"` 會把整個 repo 含歷史 clone 進每個 CLI 使用者的 uv 快取；`docs/dev-onboarding.md` 教同事 `git clone`。這些副本的歷史停在各自安裝那天。
- **GitHub 本身**：force-push 後舊 commit 仍可用 hash 直接開（dangling object 要向 GitHub Support 申請清除）；每個 PR 的 `refs/pull/N/head` 保留當時的 commit（mirror 備份裡有 195 個 pull refs）。不申請 Support 清除，改寫等於半套。
- **GitHub 程式碼搜尋**：兩個名字現在都查到 0，但 CJK 搜尋不可靠，不當證據。
- **issue／PR 文字**：#214 原標題含 A，已編輯移除；PR #222 描述用代稱。

## 三、三個選項與代價

| 選項 | 效果 | 代價 |
|---|---|---|
| **1. 不動**（只靠 #222 止住往後） | A、B 仍在主 repo 歷史裡；B 反正在 10 個 fork 裡 | 零 |
| **2. 改寫歷史**（git-filter-repo，所有分支與 tag，force-push） | A 從主 repo 消失（有效：沒有 fork 帶它）；B 只從主 repo 消失，fork 仍在 | 2 月以後所有 commit hash 變掉；部署清單 `docs/deploy-2026-09-erp-rollout.md` 裡每個 hash 失效要重寫；`hotfix/unbound-guards` 要重建；.11 的 checkout 要重拉（正式機，選重啟時一起做）；這台開發機重拉；兩支 open PR（#171、#172）的 head 分支重推；所有同事與 CLI 使用者的本機副本 hash 對不上要重 clone；CI 歷史紀錄指向不存在的 commit；還要向 GitHub Support 申請清 dangling objects 與 pull refs 才算清乾淨 |
| **3. repo 轉 private** | 主 repo 對外看不到；**fork 會被切離但繼續公開**，所以 B 一樣在外面 | `uv tool install git+https://…` 與 `git clone` 要改用 token 或 SSH，同事安裝流程要改（README、CLAUDE.md、dev-onboarding）；32 個 star 的公開展示消失；不用改寫歷史 |

**選項 3 對 B 沒有用、對 A 只是藏起來**；真正能拿掉 A 的只有選項 2，且要配合 Support 申請。B 兩個選項都收不回，只能接受或逐一聯絡 fork 擁有者。

## 四、建議

- A 是本 session 今天引進的，副本只有 .11、這台開發機與今天有 pull 的人，**現在改寫最便宜**；等愈久副本愈多。
- B 已在外面八個月且在 10 個 fork 裡，改寫是順手（成本相同）但效果只有主 repo；不值得為它單獨付成本。
- 若選 2：照監督 session 的六步（mirror 備份 → 清場 → filter-repo → 本機驗證 → force-push → 重建下游與清單 → GitHub 搜尋確認、通知 fork、重開 PR），每步回報。備份已做（2026-09-12 08:31 mirror，NAS `/mnt/nas/ctos/backups/git/`，sha256 前 16 碼 `ca23167631390448`）。

## 反向掃描腳本

`sweep_real_names.py`：從 ERPNext 每日備份的 Supplier／Customer／Contact／Address／Item／Project／Task 抽名稱、電話、email、地址、料號（NFKC、去流水碼前綴、去公司尾綴變形），掃 repo 全部文字檔（排除 data、extends、依賴與 build 產物），命中即非 0 exit。腳本目前在本機 scratchpad；放進 repo 前要拿掉對備份路徑的依賴（改吃參數），這條列為待辦。
