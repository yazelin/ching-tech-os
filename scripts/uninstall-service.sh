#!/bin/bash

# Ching Tech OS 服務卸載腳本
# 用法: sudo ./scripts/uninstall-service.sh

set -e

SERVICE_NAME="ching-tech-os"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
MOUNT_UNIT_FILE="/etc/systemd/system/mnt-nas.mount"
NAS_CREDENTIALS_FILE="/etc/nas-credentials"
NAS_MOUNT_PATH="/mnt/nas"

# 檢查是否以 root 執行
if [ "$EUID" -ne 0 ]; then
    echo "請使用 sudo 執行此腳本"
    exit 1
fi

echo "=== 卸載 ${SERVICE_NAME} 服務 ==="

# 停止服務
if systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "停止服務..."
    systemctl stop ${SERVICE_NAME}
fi

# 停止 Docker 容器
echo "停止 Docker 容器..."
docker compose -f /home/ct/SDD/ching-tech-os/docker/docker-compose.yml down 2>/dev/null || true

# 停用服務
if systemctl is-enabled --quiet ${SERVICE_NAME} 2>/dev/null; then
    echo "停用服務..."
    systemctl disable ${SERVICE_NAME}
fi

# 刪除 service 檔案
if [ -f "${SERVICE_FILE}" ]; then
    echo "刪除 service 檔案..."
    rm -f ${SERVICE_FILE}
fi

# ===================
# 清理 NAS 掛載設定
# ===================
echo "清理 NAS 掛載設定..."

# 停止並停用 NAS 掛載
if systemctl is-active --quiet mnt-nas.mount; then
    echo "停止 NAS 掛載..."
    systemctl stop mnt-nas.mount
fi

if systemctl is-enabled --quiet mnt-nas.mount 2>/dev/null; then
    echo "停用 NAS 掛載..."
    systemctl disable mnt-nas.mount
fi

# 刪除 mount unit 檔案
if [ -f "${MOUNT_UNIT_FILE}" ]; then
    echo "刪除 mount unit 檔案..."
    rm -f ${MOUNT_UNIT_FILE}
fi

# 刪除 NAS 憑證檔案
if [ -f "${NAS_CREDENTIALS_FILE}" ]; then
    echo "刪除 NAS 憑證檔案..."
    rm -f ${NAS_CREDENTIALS_FILE}
fi

# 刪除掛載點目錄（如果為空）
if [ -d "${NAS_MOUNT_PATH}" ] && [ -z "$(ls -A ${NAS_MOUNT_PATH})" ]; then
    echo "刪除掛載點目錄..."
    rmdir ${NAS_MOUNT_PATH}
fi

# 重新載入 systemd
echo "重新載入 systemd..."
systemctl daemon-reload

echo ""
echo "=== 卸載完成 ==="
echo ""
echo "注意：資料庫資料保留在 Docker volume 中"
echo "如需完全刪除，請執行："
echo "  docker volume rm docker_postgres_data"
