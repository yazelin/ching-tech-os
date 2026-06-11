---
name: ctos-deploy
description: 將 ching-tech-os（CTOS）更新部署到正式機。當使用者要求「部署 CTOS」「更新正式機」「把最新版上 production」「重啟並更新 ching-tech-os 服務」時使用。涵蓋 SSH 到部署機、執行 scripts/update-service.sh、前置檢查清單、回滾方式與查日誌指令。
---

# CTOS 部署 Runbook

CTOS（ching-tech-os）以 systemd 服務 `ching-tech-os` 跑在部署機上（FastAPI + PostgreSQL，port 8088）。
更新方式：SSH 到部署機，在專案目錄執行一鍵更新腳本 `scripts/update-service.sh`。

## 部署機資訊

部署機 IP / 主機名稱**不硬編在此 skill**，以實際環境為準，依下列順序取得：

1. 使用者在對話中直接提供（最優先）
2. 環境變數或 SSH config（如 `~/.ssh/config` 內的 host alias）
3. 詢問使用者

範例（IP 僅為示意，例如 `192.168.11.11`，請以實際環境為準）：

```bash
ssh ct@<部署機IP>
cd /home/ct/SDD/ching-tech-os
```

專案目錄預設為 `/home/ct/SDD/ching-tech-os`（與 install-service.sh 的 PROJECT_DIR 一致），若部署機路徑不同以實際為準。

## 前置檢查清單（執行前必過）

- [ ] 這次要部署的 PR 都已 merge 進 `main`
- [ ] `main` 的 CI 是綠的（`gh run list --branch main --limit 5` 或看 GitHub Actions 頁面）
- [ ] 若有資料庫 migration，確認 migration 檔案已包含在要部署的 commit 中
- [ ] 確認部署時段可接受短暫服務中斷（restart 期間約數秒到數十秒）

## 標準部署流程

```bash
# 1. SSH 到部署機
ssh ct@<部署機IP>

# 2. 進入專案目錄並執行一鍵更新腳本
cd /home/ct/SDD/ching-tech-os
./scripts/update-service.sh
```

腳本會依序：顯示目前版本與 git 狀態 → `git pull --ff-only`（預設 main）→ 更新已初始化的 submodule → `uv sync --extra voice` → 前端 `npm install` + `npm run build` → `alembic upgrade head` → `sudo systemctl restart ching-tech-os` → health check（`/api/health`）→ 印出版本變化與 `git log --oneline` 更新摘要。

常用選項：

```bash
./scripts/update-service.sh --dry-run          # 先看會做什麼，不實際執行
./scripts/update-service.sh --branch <name>    # 部署指定分支（預設 main）
./scripts/update-service.sh --force            # 工作樹 dirty 時強制繼續（先弄清楚為什麼 dirty）
```

注意：

- 腳本內含 `sudo systemctl restart`，執行帳號需有 sudo 權限。
- 部署機工作樹 dirty 通常代表有人在正式機上直接改過檔案——先查清楚（`git status`、`git diff`）再決定要 stash、還原還是 `--force`。
- private submodule（如 `extends/his`、`extends/law`）在部署機沒權限時會被略過，不會中斷更新；這是預期行為。

## 部署後驗證

腳本本身會做 health check（`curl http://localhost:8088/api/health`），通過才會回報成功。額外可驗證：

```bash
systemctl is-active ching-tech-os
curl -s http://localhost:8088/api/health        # 應回 {"status":"healthy"}
journalctl -u ching-tech-os -n 30 --no-pager    # 確認啟動日誌無錯誤
```

## 回滾方式

部署後發現問題時：

1. **服務還在跑舊版（restart 失敗、新版沒起來）**：先別動。確認 `systemctl is-active ching-tech-os` 與 health check，若舊 process 仍正常服務，先查日誌找出新版失敗原因，不要急著再 restart 把還活著的舊版打掉。

2. **新版已上線但行為有問題，要退回前一版**：

```bash
cd /home/ct/SDD/ching-tech-os
git log --oneline -10                  # 找出前一版的 commit hash
git checkout <前一版hash>
./scripts/update-service.sh --force    # detached HEAD 下 git pull 會失敗是預期的；
                                       # 重點是讓依賴 / 前端 build / restart 重跑一遍
```

注意事項：

- `git checkout <hash>` 後是 detached HEAD，腳本中的 `git pull --ff-only` 會失敗——此時可以改成手動執行腳本後半段（`uv sync --extra voice` → `npm run build` → `alembic upgrade head` → `sudo systemctl restart ching-tech-os`），或先建立臨時分支再跑腳本。
- **migration 不會自動回退**：alembic 是往前升的，若新版包含 schema 變更，退回舊 code 前要先確認舊 code 與新 schema 相容；不相容時需 `uv run alembic downgrade <版本>`（高風險，動手前先備份資料庫）。
- 回滾完成後，記得回到 `main` 並修復問題後再正常部署，不要讓部署機長期停在 detached HEAD。

## 查日誌

```bash
journalctl -u ching-tech-os -n 50 --no-pager           # 最近 50 行
journalctl -u ching-tech-os -f                          # 即時追蹤
journalctl -u ching-tech-os --since "10 minutes ago"    # 特定時間範圍
journalctl -u ching-tech-os -n 100 --no-pager | grep -i error   # 過濾錯誤
```
