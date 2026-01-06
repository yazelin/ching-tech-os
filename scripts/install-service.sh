#!/bin/bash

# Ching Tech OS 服務安裝腳本
# 用法: sudo ./scripts/install-service.sh

set -e

SERVICE_NAME="ching-tech-os"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PROJECT_DIR="/home/ct/SDD/ching-tech-os"
BACKEND_DIR="${PROJECT_DIR}/backend"

# 檢查是否以 root 執行
if [ "$EUID" -ne 0 ]; then
    echo "請使用 sudo 執行此腳本"
    exit 1
fi

echo "=== 安裝 ${SERVICE_NAME} 服務 ==="

# 停止現有服務（如果存在）
if systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "停止現有服務..."
    systemctl stop ${SERVICE_NAME}
fi

# 建立 systemd service 檔案
echo "建立 systemd service 檔案..."
cat > ${SERVICE_FILE} << 'EOF'
[Unit]
Description=Ching Tech OS Web Desktop Service
After=network.target docker.service
Requires=docker.service

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
