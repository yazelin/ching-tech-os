#!/bin/bash

# Ching Tech OS 服務安裝腳本
# 用法: sudo ./scripts/install-service.sh

set -e

SERVICE_NAME="ching-tech-os"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
MOUNT_UNIT_FILE="/etc/systemd/system/mnt-nas.mount"
NAS_CREDENTIALS_FILE="/etc/nas-credentials"
NAS_MOUNT_PATH="/mnt/nas"
PROJECT_DIR="/home/ct/SDD/ching-tech-os"
BACKEND_DIR="${PROJECT_DIR}/backend"
ENV_FILE="${PROJECT_DIR}/.env"

# 檢查是否以 root 執行
if [ "$EUID" -ne 0 ]; then
    echo "請使用 sudo 執行此腳本"
    exit 1
fi

echo "=== 安裝 ${SERVICE_NAME} 服務 ==="

# 從 .env 讀取 NAS 設定
if [ -f "${ENV_FILE}" ]; then
    export $(grep -E '^NAS_(HOST|USER|PASSWORD|SHARE)=' "${ENV_FILE}" | xargs)
fi

# 檢查必要的 NAS 設定
if [ -z "${NAS_HOST}" ] || [ -z "${NAS_USER}" ] || [ -z "${NAS_PASSWORD}" ] || [ -z "${NAS_SHARE}" ]; then
    echo "錯誤：缺少 NAS 設定，請確認 .env 檔案包含 NAS_HOST、NAS_USER、NAS_PASSWORD、NAS_SHARE"
    exit 1
fi

# 停止現有服務（如果存在）
if systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "停止現有服務..."
    systemctl stop ${SERVICE_NAME}
fi

# ===================
# NAS 掛載設定
# ===================
echo "設定 NAS 掛載..."

# 建立 NAS 憑證檔案
echo "建立 NAS 憑證檔案..."
cat > ${NAS_CREDENTIALS_FILE} << EOF
username=${NAS_USER}
password=${NAS_PASSWORD}
domain=WORKGROUP
EOF
chmod 600 ${NAS_CREDENTIALS_FILE}

# 建立掛載點目錄
mkdir -p ${NAS_MOUNT_PATH}

# 停止現有掛載（如果存在）
if systemctl is-active --quiet mnt-nas.mount; then
    echo "停止現有 NAS 掛載..."
    systemctl stop mnt-nas.mount
fi

# 建立 systemd mount unit
echo "建立 NAS mount unit..."
cat > ${MOUNT_UNIT_FILE} << EOF
[Unit]
Description=NAS CIFS Mount (擎添開發)
After=network-online.target
Wants=network-online.target

[Mount]
What=//${NAS_HOST}/${NAS_SHARE}
Where=${NAS_MOUNT_PATH}
Type=cifs
Options=username=${NAS_USER},password=${NAS_PASSWORD},uid=1000,gid=1000,iocharset=utf8,_netdev

[Install]
WantedBy=multi-user.target
EOF

# 啟用並啟動 NAS 掛載
echo "啟用 NAS 掛載..."
systemctl daemon-reload
systemctl enable mnt-nas.mount
systemctl start mnt-nas.mount

# 確認掛載成功
if mountpoint -q ${NAS_MOUNT_PATH}; then
    echo "NAS 掛載成功: ${NAS_MOUNT_PATH}"
else
    echo "警告：NAS 掛載可能未成功，請檢查 systemctl status mnt-nas.mount"
fi

# ===================
# 應用程式服務設定
# ===================

# 建立 systemd service 檔案
echo "建立 systemd service 檔案..."
cat > ${SERVICE_FILE} << 'EOF'
[Unit]
Description=Ching Tech OS Web Desktop Service
After=network.target docker.service mnt-nas.mount
Requires=docker.service mnt-nas.mount

[Service]
Type=simple
User=ct
Group=ct
WorkingDirectory=/home/ct/SDD/ching-tech-os/backend
EnvironmentFile=/home/ct/SDD/ching-tech-os/.env

# 確保 PATH 包含 uv、nvm node 和其他工具
Environment="PATH=/home/ct/.local/bin:/home/ct/.nvm/versions/node/v24.11.1/bin:/usr/local/bin:/usr/bin:/bin"

# 啟動前確保資料庫容器運行
ExecStartPre=/usr/bin/docker compose -f /home/ct/SDD/ching-tech-os/docker/docker-compose.yml up -d postgres
ExecStartPre=/bin/sleep 3

# 確保端口未被佔用（- 前綴表示失敗時繼續）
ExecStartPre=-/usr/bin/fuser -k 8088/tcp

# 執行資料庫遷移並啟動應用程式
ExecStartPre=/home/ct/.local/bin/uv run alembic upgrade head
ExecStart=/home/ct/.local/bin/uv run uvicorn ching_tech_os.main:socket_app --host 0.0.0.0 --port 8088

Restart=on-failure
RestartSec=10

# 日誌設定
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ching-tech-os

[Install]
WantedBy=multi-user.target
EOF

# 重新載入 systemd
echo "重新載入 systemd..."
systemctl daemon-reload

# 啟用服務
echo "啟用服務..."
systemctl enable ${SERVICE_NAME}

# 啟動服務
echo "啟動服務..."
systemctl start ${SERVICE_NAME}

# 顯示狀態
echo ""
echo "=== 安裝完成 ==="
systemctl status ${SERVICE_NAME} --no-pager

echo ""
echo "常用指令："
echo "  sudo systemctl status ${SERVICE_NAME}   # 查看狀態"
echo "  sudo systemctl restart ${SERVICE_NAME}  # 重啟服務"
echo "  sudo systemctl stop ${SERVICE_NAME}     # 停止服務"
echo "  sudo journalctl -u ${SERVICE_NAME} -f   # 查看日誌"
echo "  sudo systemctl status mnt-nas.mount     # 查看 NAS 掛載狀態"
echo ""
echo "NAS 掛載點: ${NAS_MOUNT_PATH}"
