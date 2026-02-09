#!/bin/bash

# Ching Tech OS 服務卸載腳本
# 用法: sudo ./scripts/uninstall-service.sh

set -e

SERVICE_NAME="ching-tech-os"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
NAS_CREDENTIALS_FILE="/etc/nas-credentials"
NAS_MOUNT_BASE="/mnt/nas"

# 掛載設定
MOUNT_CTOS_UNIT="mnt-nas-ctos.mount"
MOUNT_CTOS_PATH="${NAS_MOUNT_BASE}/ctos"
MOUNT_PROJECTS_UNIT="mnt-nas-projects.mount"
MOUNT_PROJECTS_PATH="${NAS_MOUNT_BASE}/projects"
MOUNT_CIRCUITS_UNIT="mnt-nas-circuits.mount"
MOUNT_CIRCUITS_PATH="${NAS_MOUNT_BASE}/circuits"
# 舊的掛載（向後相容）
MOUNT_OLD_UNIT="mnt-nas.mount"

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

# 清理 ctos 掛載
if systemctl is-active --quiet ${MOUNT_CTOS_UNIT}; then
    echo "停止 ctos 掛載..."
    systemctl stop ${MOUNT_CTOS_UNIT}
fi
if systemctl is-enabled --quiet ${MOUNT_CTOS_UNIT} 2>/dev/null; then
    echo "停用 ctos 掛載..."
    systemctl disable ${MOUNT_CTOS_UNIT}
fi
if [ -f "/etc/systemd/system/${MOUNT_CTOS_UNIT}" ]; then
    echo "刪除 ctos mount unit 檔案..."
    rm -f /etc/systemd/system/${MOUNT_CTOS_UNIT}
fi

# 清理 projects 掛載
if systemctl is-active --quiet ${MOUNT_PROJECTS_UNIT}; then
    echo "停止 projects 掛載..."
    systemctl stop ${MOUNT_PROJECTS_UNIT}
fi
if systemctl is-enabled --quiet ${MOUNT_PROJECTS_UNIT} 2>/dev/null; then
    echo "停用 projects 掛載..."
    systemctl disable ${MOUNT_PROJECTS_UNIT}
fi
if [ -f "/etc/systemd/system/${MOUNT_PROJECTS_UNIT}" ]; then
    echo "刪除 projects mount unit 檔案..."
    rm -f /etc/systemd/system/${MOUNT_PROJECTS_UNIT}
fi

# 清理 circuits 掛載
if systemctl is-active --quiet ${MOUNT_CIRCUITS_UNIT}; then
    echo "停止 circuits 掛載..."
    systemctl stop ${MOUNT_CIRCUITS_UNIT}
fi
if systemctl is-enabled --quiet ${MOUNT_CIRCUITS_UNIT} 2>/dev/null; then
    echo "停用 circuits 掛載..."
    systemctl disable ${MOUNT_CIRCUITS_UNIT}
fi
if [ -f "/etc/systemd/system/${MOUNT_CIRCUITS_UNIT}" ]; then
    echo "刪除 circuits mount unit 檔案..."
    rm -f /etc/systemd/system/${MOUNT_CIRCUITS_UNIT}
fi

# 清理舊的單一掛載（向後相容）
if systemctl is-active --quiet ${MOUNT_OLD_UNIT} 2>/dev/null; then
    echo "停止舊的 NAS 掛載..."
    systemctl stop ${MOUNT_OLD_UNIT}
fi
if systemctl is-enabled --quiet ${MOUNT_OLD_UNIT} 2>/dev/null; then
    echo "停用舊的 NAS 掛載..."
    systemctl disable ${MOUNT_OLD_UNIT}
fi
if [ -f "/etc/systemd/system/${MOUNT_OLD_UNIT}" ]; then
    echo "刪除舊的 mount unit 檔案..."
    rm -f /etc/systemd/system/${MOUNT_OLD_UNIT}
fi

# 刪除 NAS 憑證檔案
if [ -f "${NAS_CREDENTIALS_FILE}" ]; then
    echo "刪除 NAS 憑證檔案..."
    rm -f ${NAS_CREDENTIALS_FILE}
fi

# 刪除掛載點目錄（如果為空）
if [ -d "${MOUNT_CTOS_PATH}" ] && [ -z "$(ls -A ${MOUNT_CTOS_PATH} 2>/dev/null)" ]; then
    echo "刪除 ctos 掛載點目錄..."
    rmdir ${MOUNT_CTOS_PATH} 2>/dev/null || true
fi
if [ -d "${MOUNT_PROJECTS_PATH}" ] && [ -z "$(ls -A ${MOUNT_PROJECTS_PATH} 2>/dev/null)" ]; then
    echo "刪除 projects 掛載點目錄..."
    rmdir ${MOUNT_PROJECTS_PATH} 2>/dev/null || true
fi
if [ -d "${MOUNT_CIRCUITS_PATH}" ] && [ -z "$(ls -A ${MOUNT_CIRCUITS_PATH} 2>/dev/null)" ]; then
    echo "刪除 circuits 掛載點目錄..."
    rmdir ${MOUNT_CIRCUITS_PATH} 2>/dev/null || true
fi
if [ -d "${NAS_MOUNT_BASE}" ] && [ -z "$(ls -A ${NAS_MOUNT_BASE} 2>/dev/null)" ]; then
    echo "刪除 NAS 掛載基礎目錄..."
    rmdir ${NAS_MOUNT_BASE} 2>/dev/null || true
fi

# ===================
# 移除 ClawHub CLI
# ===================
if command -v clawhub &>/dev/null; then
    echo "移除 clawhub CLI..."
    npm uninstall -g clawhub 2>/dev/null || true
    echo "clawhub 已移除"
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
