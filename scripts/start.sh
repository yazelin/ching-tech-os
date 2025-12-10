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

# 啟動 PostgreSQL
start_db() {
    log_info "啟動 PostgreSQL..."
    cd "$PROJECT_ROOT/docker"
    if docker compose ps | grep -q "ching-tech-os-db.*running"; then
        log_info "PostgreSQL 已在運行中"
    else
        docker compose up -d
        log_info "等待 PostgreSQL 就緒..."
        sleep 3
    fi
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

    echo ""
    log_info "應用程式: http://localhost:8088"
    log_info "API 文件: http://localhost:8088/docs"
    echo ""
    uv run uvicorn ching_tech_os.main:app --host 0.0.0.0 --port 8088 --reload
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
    echo "  dev      啟動開發環境 (PostgreSQL + 後端 with hot-reload)"
    echo "  db       只啟動 PostgreSQL"
    echo "  stop     停止所有服務"
    echo "  help     顯示此說明"
}

# 主程式
case "${1:-}" in
    dev)
        start_dev
        ;;
    db)
        start_db
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
