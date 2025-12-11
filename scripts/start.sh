#!/bin/bash

# Ching Tech OS 啟動腳本
# 用法: ./scripts/start.sh dev

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 啟動 Docker 服務 (PostgreSQL + code-server)
start_services() {
    log_info "啟動 Docker 服務..."
    cd "$PROJECT_ROOT/docker"

    # 設定 UID/GID 供 code-server 使用
    export UID=$(id -u)
    export GID=$(id -g)

    # 檢查服務狀態
    local need_start=false
    if ! docker compose ps | grep -q "ching-tech-os-db.*running"; then
        need_start=true
    fi
    if ! docker compose ps | grep -q "ching-tech-os-code.*running"; then
        need_start=true
    fi

    if [ "$need_start" = true ]; then
        docker compose up -d
        log_info "等待服務就緒..."
        sleep 3

        # 等待 code-server 就緒
        log_info "等待 code-server 就緒..."
        for i in {1..30}; do
            if curl -s http://localhost:8443 > /dev/null 2>&1; then
                log_info "code-server 已就緒"
                break
            fi
            sleep 1
        done
    else
        log_info "Docker 服務已在運行中"
    fi
}

# 相容舊的 start_db 函數
start_db() {
    start_services
}

# 啟動開發模式
start_dev() {
    start_db

    log_info "啟動服務 (開發模式)..."
    cd "$PROJECT_ROOT/backend"

    # 確保依賴已安裝
    if [ ! -d ".venv" ]; then
        log_info "安裝 Python 依賴..."
        uv sync
    fi

    # 執行資料庫 migration
    log_info "執行資料庫 migration..."
    uv run alembic upgrade head

    echo ""
    log_info "應用程式: http://localhost:8088"
    log_info "API 文件: http://localhost:8088/docs"
    log_info "程式編輯器: http://localhost:8443 (密碼: \${CODE_PASSWORD:-changeme})"
    echo ""

    # 設定終端機起始目錄為專案根目錄
    export TERMINAL_CWD="$PROJECT_ROOT"

    uv run uvicorn ching_tech_os.main:socket_app --host 0.0.0.0 --port 8088 --reload
}

# 停止所有服務
stop_all() {
    log_info "停止所有服務..."
    cd "$PROJECT_ROOT/docker"
    docker compose down
    log_info "服務已停止"
}

# 顯示使用說明
show_usage() {
    echo "Ching Tech OS 啟動腳本"
    echo ""
    echo "用法: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  dev      啟動開發環境 (PostgreSQL + code-server + 後端 with hot-reload)"
    echo "  services 只啟動 Docker 服務 (PostgreSQL + code-server)"
    echo "  db       只啟動 Docker 服務 (同 services)"
    echo "  stop     停止所有服務"
    echo "  help     顯示此說明"
}

# 主程式
case "${1:-}" in
    dev)
        start_dev
        ;;
    services|db)
        start_services
        ;;
    stop)
        stop_all
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        log_error "未知的命令: ${1:-}"
        echo ""
        show_usage
        exit 1
        ;;
esac
