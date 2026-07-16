# 知識庫儲存與備份

> 動備份腳本或知識庫目錄結構前，先讀這份。核心原則：**兩邊各有正本，備份方向相反，誰都不能對對方的正本帶 `--delete`。**

## 儲存分裂（by 設計）

| 內容 | 正本位置 | 寫入者 |
|------|----------|--------|
| 條目 md / index.json / 小附件（<1MB，`assets/`） | `.11 本機 ~/SDD/ching-tech-os/data/knowledge/` | 後端 `knowledge.py`（entries 走本機路徑） |
| 大附件（>=1MB，`attachments/kb-XXX/`） | NAS `/mnt/nas/ctos/knowledge/attachments/` | 後端 `upload_attachment()`（經 `create_knowledge_file_service()`，root = `CTOS_MOUNT_PATH/knowledge`） |

## 每日備份（systemd timer `backup-knowledge.timer`，03:00）

腳本：`/home/ct/scripts/backup-knowledge-to-nas.sh`（repo 存底：`scripts/backup-knowledge-to-nas.sh`，改完要同步部署到 `~/scripts/`）

1. **正向** 本機 → NAS：`rsync --delete --exclude='.git' --exclude='attachments/'`
   `--exclude='attachments/'` 是保命符，見下方事故。
2. **反向** NAS → 本機：`rsync`（**不帶** `--delete`，只進不出）把 `attachments/` 拉回本機第二份。
   NAS 誤刪時本機這份不會跟著消失，可反向救援。
3. 週日 tar.gz 到 `/mnt/nas/library/handover-snapshots/`（90 天輪替，`--exclude='knowledge/attachments'` 避免圖書館被數十 GB 塞爆）。

結果：完整知識庫在 NAS 和 .11 本機各一份。本機的 `data/knowledge/` 整棵都在 .gitignore，不進 git。

## 2026-07-16 事故（為什麼有這些 exclude）

正向 rsync 原本沒有 exclude `attachments/`，而本機正本沒有這個目錄，於是每晚 `--delete` 把 NAS 上的大附件整批掃掉——自 2026-03 起累計刪了 26 個附件（kb-043 STEP 圖檔、kb-050~062 錄音、kb-103/104 影片、kb-120/182/183/192 PDF、kb-216 影片）。

救援：25 個從 LINE bot 收檔區（`/mnt/nas/ctos/linebot/files/`，檔名帶 LINE 訊息 ID 可比對）copy 回來；kb-040 的 AI 生成圖無源可救，附件紀錄已自條目移除。

教訓：
- LINE 上傳的附件天然有第二份（收檔區）；**AI 生成的附件只有 `attachments/` 一份**，反向備份就是為它們加的。
- 修 rsync 規則後一定要 `rsync -n` 乾跑驗證 deleting 清單再上線。

相關：kb-161 §1.5（移交 SOP 的備份段落）、`docs/smb-nas-architecture.md`
