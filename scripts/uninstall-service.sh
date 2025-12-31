#!/bin/bash

# Ching Tech OS 服務卸載腳本
# 用法: sudo ./scripts/uninstall-service.sh

set -e

SERVICE_NAME="ching-tech-os"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

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

# 重新載入 systemd
echo "重新載入 systemd..."
systemctl daemon-reload

echo ""
echo "=== 卸載完成 ==="
echo ""
echo "注意：資料庫資料保留在 Docker volume 中"
echo "如需完全刪除，請執行："
echo "  docker volume rm docker_postgres_data"
