#!/usr/bin/env bash
# ERPNext 每日備份到 NAS（停用 ERPNext 前的資料搬出，見 docs/superpowers/specs/2026-09-10-ctos-web-react-frontend-design.md 第五節）
#
# 兩層：
#   1. bench backup --with-files：完整 SQL dump ＋ 公私檔案 tar（可整站還原）
#   2. scripts/erpnext_export.py：業務 doctype 逐筆 JSON ＋ CSV（人看得懂、之後匯入新模組用）
# 輸出 /mnt/nas/ctos/erpnext-backup/<YYYYmmdd>/，保留 30 天；每月 1 日那份不刪。
# 與 backup-knowledge-to-nas.sh 同一套：mount 沒掛就不動、log 在 ~/logs。
set -euo pipefail

REPO=/home/ct/SDD/ching-tech-os
ENV_FILE="$REPO/.env"
EXPORTER="$(dirname "$(readlink -f "$0")")/erpnext_export.py"
CONTAINER=erpnext-backend-1
SITE=erp.localhost
NAS_ROOT=/mnt/nas/ctos
DST_ROOT="$NAS_ROOT/erpnext-backup"
LOG=/home/ct/logs/backup-erpnext.log
KEEP_DAYS=30

mkdir -p "$(dirname "$LOG")"
log() { echo "$(date -Iseconds) $*" >> "$LOG"; echo "$*"; }

if ! mountpoint -q "$NAS_ROOT"; then
  log "[ERROR] $NAS_ROOT not mounted"; exit 1
fi
if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  log "[ERROR] container $CONTAINER not running"; exit 1
fi

DAY=$(date +%Y%m%d)
DST="$DST_ROOT/$DAY"
mkdir -p "$DST/site" "$DST/doctypes"
rm -f "$DST/site"/*   # 同一天重跑不要堆兩份

# 1. 整站備份（在容器內產生，再複製出來；容器內的舊備份清掉，不留兩份）
docker exec "$CONTAINER" bash -c "cd /home/frappe/frappe-bench && rm -f sites/$SITE/private/backups/* && bench --site $SITE backup --with-files" >> "$LOG" 2>&1
for f in $(docker exec "$CONTAINER" bash -c "ls /home/frappe/frappe-bench/sites/$SITE/private/backups"); do
  docker cp "$CONTAINER:/home/frappe/frappe-bench/sites/$SITE/private/backups/$f" "$DST/site/$f"
done
docker exec "$CONTAINER" bash -c "rm -f /home/frappe/frappe-bench/sites/$SITE/private/backups/*"
log "[OK] bench backup → $DST/site ($(du -sh "$DST/site" | cut -f1))"

# 2. 業務 doctype JSON/CSV
if python3 "$EXPORTER" --env-file "$ENV_FILE" --out "$DST/doctypes" >> "$LOG" 2>&1; then
  log "[OK] doctype export → $DST/doctypes ($(du -sh "$DST/doctypes" | cut -f1))"
else
  log "[WARN] doctype export 有失敗項，見 $DST/doctypes/manifest.json"
fi

# NAS 是 SMB，不支援符號連結：用文字檔記最新一份
echo "$DAY" > "$DST_ROOT/LATEST"

# 3. 保留策略：30 天內全留；每月 1 日那份永久留
find "$DST_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20??????' -mtime +"$KEEP_DAYS" ! -name '??????01' -exec rm -rf {} + 2>/dev/null || true
log "[OK] done $DAY"
