#!/usr/bin/env bash
# Daily backup of CTOS knowledge base — two-way, by 正本位置:
#   條目/index/小附件 正本在本機 data/knowledge/ → 推到 NAS
#   大附件(>=1MB)   正本在 NAS knowledge/attachments/ → 拉回本機第二份
# 詳見 kb-161 1.5
set -euo pipefail
SRC=/home/ct/SDD/ching-tech-os/data/knowledge/
DST=/mnt/nas/ctos/knowledge/
LOG=/home/ct/logs/backup-knowledge.log

mkdir -p "$(dirname "$LOG")"

if ! mountpoint -q /mnt/nas/ctos; then
  echo "$(date -Iseconds) [ERROR] /mnt/nas/ctos not mounted" >> "$LOG"
  exit 1
fi

# 正向：本機正本 → NAS。attachments/ 的正本在 NAS，必須 exclude，
# 否則 --delete 會把 NAS 上的大附件整批刪光（2026-07-16 事故，26 個附件）。
# 容許 exit code 24（vanished source files）：後端寫入中的暫存檔消失不算失敗
rsync -av --delete --exclude='.git' --exclude='attachments/' "$SRC" "$DST" >> "$LOG" 2>&1 || [ $? -eq 24 ]

# 反向：NAS 大附件 → 本機第二份。不帶 --delete（只進不出），
# NAS 端誤刪時本機這份不會跟著消失，可反向救援
if [ -d "${DST%/}/attachments" ]; then
  rsync -av "${DST%/}/attachments/" "${SRC%/}/attachments/" >> "$LOG" 2>&1 || [ $? -eq 24 ]
fi
echo "$(date -Iseconds) [OK] rsync done" >> "$LOG"

# 每週日多打一份 tar.gz 到圖書館（保留 90 天；不含大附件，
# 否則 1GB+ × 13 週會吃掉數十 GB 圖書館空間）
if [ "$(date +%u)" = "7" ]; then
  if ! mountpoint -q /mnt/nas/library; then
    # library 沒掛載時絕不能 mkdir -p——會在本機根目錄建同名路徑,tar 塞爆本機碟
    echo "$(date -Iseconds) [ERROR] /mnt/nas/library not mounted, skip weekly tar" >> "$LOG"
  else
    TAR_DIR=/mnt/nas/library/handover-snapshots
    mkdir -p "$TAR_DIR"
    tar czf "$TAR_DIR/knowledge-$(date +%Y%m%d).tar.gz" --exclude='knowledge/attachments' -C /home/ct/SDD/ching-tech-os/data knowledge/
    find "$TAR_DIR" -name "knowledge-*.tar.gz" -mtime +90 -delete
  fi
fi
