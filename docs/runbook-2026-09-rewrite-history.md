# Runbook：清掉公開歷史裡的真實客戶名（步驟三～六，等 yazelin 點頭才跑）

前提：步驟一（mirror 備份，NAS `/mnt/nas/ctos/backups/git/ching-tech-os-mirror-20260912-0831.tar.gz`，sha256 前 16 碼 `ca23167631390448`）與步驟二（刪掉 22 支已合併／已關閉的遠端分支、清本機 worktree）已於 2026-09-12 完成。判斷材料見 `docs/decision-2026-09-real-names-in-history.md`。**這份文件不含真實名稱**；替換表放本機 `~/rewrite/replacements.txt`（內容由監督 session 對話或 `.superpowers/sdd/real-names-cleanup/report.md` 取得，不進版控）。

工具：`git-filter-repo`（`uv tool install git-filter-repo`，已裝在開發機，版本 `a40bce548d2c`），git 2.43。**不要用 `git filter-branch`。**

## 影響範圍先講清楚

- 2026-01-06 之後（B）與 2026-09-12 之後（A）**所有 commit hash 都會變**；tag 7 個一起改寫。
- 改寫後：`docs/deploy-2026-09-erp-rollout.md` 裡每個 hash 失效；`hotfix/unbound-guards` 要重建；.11 與開發機要重拉；open PR #171、#172 的 head 分支要重推；同事與 CLI 使用者的本機副本要重 clone。
- GitHub 上舊 commit 仍可用 hash 開、`refs/pull/*` 仍在 → 步驟六要向 GitHub Support 申請清除，否則只做半套。
- B 在 10 個 fork 裡，改寫收不回。

## 步驟三：改寫（在開發機的新目錄做，不碰現有 checkout）

```bash
mkdir -p ~/rewrite && cd ~/rewrite
git clone --mirror https://github.com/yazelin/ching-tech-os.git rewrite.git
cd rewrite.git
git for-each-ref | wc -l            # 預期 ≈ 6 個分支 + 7 個 tag + refs/pull/*（改寫不會動 refs/pull，那些由 GitHub 管）
# 替換表格式（每行一組，literal 比對）：
#   <名稱A全稱>==>丙丁科技
#   <名稱A簡稱>==>丙丁
#   <名稱A英文>==>Bingding
#   <名稱B全稱>==>甲乙光學
#   <名稱B簡稱>==>甲乙
#   全形／半形變形各一行；有「股份有限公司」尾綴的先列長的再列短的
git filter-repo --replace-text ~/rewrite/replacements.txt --refs --all
# 預期輸出：Parsed N commits … New history written in X seconds; 沒有 error
```
`--replace-text` 同時改 blob 內容與 commit 訊息。filter-repo 跑完會移除 `origin` remote（刻意的，防止誤推）。

## 步驟四：本機驗證（全部要過才准推）

```bash
cd ~/rewrite/rewrite.git
# 1. 兩個名字在全歷史 0 命中（含變形，逐行跑替換表左邊的每個字串）
for t in $(cut -d'=' -f1 ~/rewrite/replacements.txt); do printf "%s: " "$t"; git log --all -S"$t" --oneline | wc -l; done   # 全部 0
git grep -c "<名稱A簡稱>" $(git rev-list --all) 2>/dev/null | wc -l     # 0
# 2. commit 數與分支結構不變
git rev-list --all --count                                              # 與備份 mirror 的數字相同
git for-each-ref --format='%(refname)' refs/heads refs/tags | sort      # 與備份相同的分支與 tag 名
# 3. 隨機抽三個 commit 比對內容差異只有替換字串
OLD=~/rewrite/backup-verify   # 從 NAS tarball 解出來的 mirror 再 clone
for c in <舊hash1> <舊hash2> <舊hash3>; do
  NEW=$(git log --all --format=%H --grep="$(git -C $OLD log -1 --format=%s $c)" | head -1)
  diff <(git -C $OLD show $c --stat --format=) <(git show $NEW --stat --format=)   # 只該差在含真名的檔案
done
# 4. 全套測試在改寫後的 main 上照樣綠
git clone ~/rewrite/rewrite.git ~/rewrite/check && cd ~/rewrite/check/backend && uv sync --extra voice && uv run pytest -q --deselect tests/test_single_tenant.py | tail -1
```
任何一項不對：**不推**，刪掉 `~/rewrite`，回報。

## 步驟五：推上去（不可逆）

```bash
cd ~/rewrite/rewrite.git
git remote add origin https://github.com/yazelin/ching-tech-os.git
git push --force --all origin      # 分支：main、hotfix/unbound-guards、trial、fix/his-submodule-url、fix/redact-bot-token-in-logs、docs/*
git push --force --tags origin     # 7 個 tag
# 不要 --mirror：refs/pull/* 推不上去會報錯，而且會刪掉遠端上你本機沒有的 ref
```
GitHub 的 branch protection 若擋 force-push，先到 Settings → Branches 暫時關掉 main 的保護，推完開回來。

推完立刻：
```bash
gh pr list --state open        # #171、#172 應仍 open，head 指到新 commit
gh run list --limit 3          # CI 會對 main 新 head 跑一次，要綠
```

## 步驟六：重建下游

1. **開發機**：`cd /home/ct/SDD && mv ching-tech-os ching-tech-os.old && git clone --recurse-submodules https://github.com/yazelin/ching-tech-os.git`（`.env`、`data/` 從舊目錄搬回），確認後刪 `.old`。
2. **.11（正式機，選重啟時一起做）**：
   ```bash
   cd ~/SDD/ching-tech-os && git fetch origin
   git status --short              # 必須乾淨（extends/his 的 submodule 指標例外）
   OLD=$(git rev-parse HEAD)       # 0b982f1 或當時的部署 commit
   NEW=$(git log origin/main --format=%H --grep="$(git log -1 --format=%s $OLD)" | head -1)   # 用 commit 訊息找對應的新 hash
   git reset --hard $NEW && git log --oneline -1
   ```
   不需要重啟、不需要 migration（內容同一份，只有 hash 變）。若 .11 當時已部署到 main 最新，就 `git reset --hard origin/main`。
3. **hotfix/unbound-guards**：從新的 .11 基底重切、cherry-pick 對應的四支（用 commit 訊息找新 hash）、重跑全套、force-push 分支。
4. **部署清單** `docs/deploy-2026-09-erp-rollout.md`：所有 hash 換新（現況表、選項 A 指令、退路的 `git checkout <舊基底>`），更新「最後更新」段；照維護規則自讀第 5、6 節。
5. **GitHub Support**：到 https://support.github.com 提「remove cached views / dangling commits after history rewrite」，附 repo 名與要清除的舊 commit hash 清單（從備份 mirror 用 `git log --all -S` 列出）。
6. **fork 擁有者**：10 個 fork 只有 B；發 issue 或 email 請求刪除 fork（不保證），清單用 `gh api repos/yazelin/ching-tech-os/forks --jq '.[].full_name'`。
7. **通知同事**：本機 clone 要 `git fetch && git reset --hard origin/main`（或重 clone）；`ctos` CLI 重裝：`uv tool install --reinstall "git+https://github.com/yazelin/ching-tech-os.git#subdirectory=cli"`。
8. **最後確認**：`gh search code "<名稱A簡稱>" --repo yazelin/ching-tech-os`、同樣查 B → 0；隔天再查一次（索引有延遲）；在 GitHub 網頁用舊 hash 開 commit 頁面，Support 處理完後應為 404。

## 退路

- 步驟三／四階段：刪 `~/rewrite`，什麼都沒動。
- 步驟五推完想反悔：從 NAS tarball 解出 mirror，`git push --force --all` 與 `--tags` 推回舊歷史（refs/pull 不用推）；下游依步驟六反向處理。舊歷史被 Support 清掉之後就不能這樣退。
