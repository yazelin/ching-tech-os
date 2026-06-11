#!/bin/bash

# Ching Tech OS 服務一鍵更新腳本
# 在部署機上執行：拉取最新程式碼、更新依賴、建置前端、跑 migration、重啟服務、health check
# 用法: ./scripts/update-service.sh [--branch <name>] [--force] [--dry-run]
#
# 選項:
#   --branch <name>  指定要更新的分支（預設 main）
#   --force          工作樹有未提交變更時仍繼續執行
#   --dry-run        只印出會執行的步驟，不實際執行任何 git / 系統指令

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="${PROJECT_ROOT}/backend"
PYPROJECT_FILE="${BACKEND_DIR}/pyproject.toml"

# 服務設定（與 install-service.sh 一致）
SERVICE_NAME="ching-tech-os"
SERVICE_PORT="8088"

# Health check 設定（端點見 backend/src/ching_tech_os/main.py 的 GET /api/health）
HEALTH_URL="http://localhost:${SERVICE_PORT}/api/health"
HEALTH_RETRIES=10
HEALTH_INTERVAL=3

# 顏色輸出（與 start.sh 一致）
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

# ===================
# 參數解析
# ===================
BRANCH="main"
FORCE=false
DRY_RUN=false

show_usage() {
    echo "Ching Tech OS 服務一鍵更新腳本"
    echo ""
    echo "用法: $0 [--branch <name>] [--force] [--dry-run]"
    echo ""
    echo "選項:"
    echo "  --branch <name>  指定要更新的分支（預設 main）"
    echo "  --force          工作樹有未提交變更時仍繼續執行"
    echo "  --dry-run        只印出會執行的步驟，不實際執行"
    echo "  -h, --help       顯示此說明"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --branch)
            if [ $# -lt 2 ]; then
                log_error "--branch 需要指定分支名稱"
                exit 1
            fi
            BRANCH="$2"
            shift 2
            ;;
        --branch=*)
            BRANCH="${1#*=}"
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            log_error "未知參數: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
done

# ===================
# 工具路徑偵測
# ===================

# uv 路徑偵測（照 install-service.sh：~/.local/bin/uv，找不到再退回 PATH）
detect_uv() {
    UV_BIN="${HOME}/.local/bin/uv"
    if [ ! -x "${UV_BIN}" ]; then
        UV_BIN="$(command -v uv 2>/dev/null || true)"
    fi
}

# Node.js 偵測（照 install-service.sh：自動偵測 nvm 安裝的最新版本）
# 若 npm 已在 PATH 中則直接使用
detect_node() {
    NODE_BIN_DIR=""
    if command -v npm > /dev/null 2>&1; then
        return 0
    fi
    local node_version
    node_version=$(ls -1 "${HOME}/.nvm/versions/node/" 2>/dev/null | sort -V | tail -n1)
    if [ -n "${node_version}" ]; then
        NODE_BIN_DIR="${HOME}/.nvm/versions/node/${node_version}/bin"
    fi
}

# 從 backend/pyproject.toml 讀取版本號
read_version() {
    grep -E '^version *= *"' "${PYPROJECT_FILE}" | head -n1 | sed -E 's/^version *= *"([^"]+)".*/\1/'
}

detect_uv
detect_node

# ===================
# Dry-run 模式：只印出會做什麼，不執行任何 git / 系統指令
# ===================
if [ "${DRY_RUN}" = true ]; then
    echo "=== ${SERVICE_NAME} 更新（dry-run，不會實際執行） ==="
    echo ""
    echo "專案目錄: ${PROJECT_ROOT}"
    echo "目前版本: $(read_version)（來自 backend/pyproject.toml）"
    echo "目標分支: ${BRANCH}"
    if [ -n "${UV_BIN}" ]; then
        echo "uv 路徑:  ${UV_BIN}"
    else
        echo "uv 路徑:  （未偵測到，實際執行時會失敗）"
    fi
    if [ -n "${NODE_BIN_DIR}" ]; then
        echo "Node.js:  ${NODE_BIN_DIR}（nvm，將加入 PATH）"
    elif command -v npm > /dev/null 2>&1; then
        echo "Node.js:  使用 PATH 中的 npm"
    else
        echo "Node.js:  （未偵測到，實際執行時會失敗）"
    fi
    echo ""
    echo "將依序執行："
    echo "  1. 檢查 git 工作樹是否乾淨（dirty 時需 --force 才繼續）"
    echo "  2. git checkout ${BRANCH}（若目前不在該分支）"
    echo "  3. git pull --ff-only"
    echo "  4. git submodule sync"
    echo "     git submodule update --init -- <path>（僅針對已初始化的 submodule，"
    echo "     依 git submodule status 過濾非 - 開頭者；單一 submodule 失敗只警告不中斷）"
    echo "  5. cd backend && uv sync --extra voice（與 install-service.sh 一致，"
    echo "     避免 uv sync 移除已安裝的 voice 依賴）"
    echo "  6. npm install（根目錄與 frontend/）+ npm run build（建置前端，照 install-service.sh）"
    echo "  7. cd backend && uv run alembic upgrade head（重啟前先跑，提早暴露 migration 錯誤；"
    echo "     systemd unit 的 ExecStartPre 啟動時還會再跑一次）"
    echo "  8. sudo systemctl restart ${SERVICE_NAME}"
    echo "  9. systemctl is-active ${SERVICE_NAME} 確認服務啟動"
    echo " 10. Health check: curl ${HEALTH_URL}（最多 ${HEALTH_RETRIES} 次、間隔 ${HEALTH_INTERVAL} 秒；"
    echo "     失敗時印 journalctl -u ${SERVICE_NAME} -n 30 並 exit 1）"
    echo " 11. 印出新版本號與更新摘要（git log --oneline 舊版..新版）"
    exit 0
fi

# ===================
# 前置檢查
# ===================
if [ -z "${UV_BIN}" ]; then
    log_error "找不到 uv（已嘗試 ~/.local/bin/uv 與 PATH），請先安裝 uv"
    exit 1
fi

if ! command -v npm > /dev/null 2>&1; then
    if [ -n "${NODE_BIN_DIR}" ]; then
        export PATH="${NODE_BIN_DIR}:${PATH}"
        log_info "使用 nvm Node.js: ${NODE_BIN_DIR}"
    else
        log_error "找不到 Node.js / npm，請先安裝 nvm 並安裝 Node.js"
        exit 1
    fi
fi

cd "${PROJECT_ROOT}"

echo "=== 更新 ${SERVICE_NAME} 服務 ==="

OLD_VERSION="$(read_version)"
OLD_COMMIT="$(git rev-parse HEAD)"
log_info "目前版本: ${OLD_VERSION}（commit $(git rev-parse --short HEAD)）"

# 顯示 git 狀態，工作樹 dirty 時警告
log_info "git 狀態:"
git status --short --branch
if [ -n "$(git status --porcelain)" ]; then
    if [ "${FORCE}" = true ]; then
        log_warn "工作樹有未提交的變更，已指定 --force，繼續執行"
    else
        log_error "工作樹有未提交的變更，請先處理（commit / stash / 還原），或加 --force 強制繼續"
        exit 1
    fi
fi

# ===================
# 拉取最新程式碼
# ===================
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "${CURRENT_BRANCH}" != "${BRANCH}" ]; then
    log_info "切換分支 ${CURRENT_BRANCH} -> ${BRANCH}..."
    git checkout "${BRANCH}"
fi

log_info "拉取最新程式碼（git pull --ff-only）..."
git pull --ff-only

# ===================
# 更新 submodule（只更新已初始化的；沒權限的 private submodule 不應讓腳本整個失敗）
# ===================
log_info "更新 git submodule..."
git submodule sync
while IFS= read -r line; do
    [ -z "${line}" ] && continue
    sub_path="$(echo "${line}" | awk '{print $2}')"
    # git submodule status 中以 - 開頭代表未初始化（例如沒權限 clone 的 private repo），跳過
    if [[ "${line}" == -* ]]; then
        log_warn "略過未初始化的 submodule: ${sub_path}"
        continue
    fi
    if git submodule update --init -- "${sub_path}"; then
        log_info "submodule 已更新: ${sub_path}"
    else
        log_warn "submodule 更新失敗（不中斷）: ${sub_path}"
    fi
done < <(git submodule status)

# ===================
# 後端依賴
# ===================
# 與 install-service.sh 一致使用 --extra voice，
# 否則單純 uv sync 會把已安裝的 voice 依賴移除，語音功能會壞掉
log_info "更新後端 Python 依賴（uv sync --extra voice）..."
(cd "${BACKEND_DIR}" && "${UV_BIN}" sync --extra voice)

# ===================
# 前端建置（照 install-service.sh：npm install + npm run build）
# ===================
log_info "更新前端依賴..."
npm install
(cd "${PROJECT_ROOT}/frontend" && npm install)

log_info "建置前端..."
npm run build

# ===================
# 資料庫 migration
# ===================
# systemd unit 的 ExecStartPre 已會跑 alembic upgrade head，
# 但這裡先跑一次，讓 migration 錯誤在重啟服務前就暴露出來
log_info "執行資料庫 migration（alembic upgrade head）..."
(cd "${BACKEND_DIR}" && "${UV_BIN}" run alembic upgrade head)

# ===================
# 重啟服務
# ===================
log_info "重啟服務（sudo systemctl restart ${SERVICE_NAME}）..."
sudo systemctl restart "${SERVICE_NAME}"

if systemctl is-active --quiet "${SERVICE_NAME}"; then
    log_info "服務狀態: $(systemctl is-active "${SERVICE_NAME}")"
else
    log_error "服務未啟動（systemctl is-active: $(systemctl is-active "${SERVICE_NAME}" || true)）"
    journalctl -u "${SERVICE_NAME}" -n 30 --no-pager
    exit 1
fi

# ===================
# Health check（GET /api/health，見 backend/src/ching_tech_os/main.py）
# ===================
log_info "Health check: ${HEALTH_URL}"
HEALTH_OK=false
for i in $(seq 1 "${HEALTH_RETRIES}"); do
    if curl -sf --max-time 5 "${HEALTH_URL}" > /dev/null 2>&1; then
        HEALTH_OK=true
        break
    fi
    log_info "等待服務就緒（${i}/${HEALTH_RETRIES}）..."
    sleep "${HEALTH_INTERVAL}"
done

if [ "${HEALTH_OK}" != true ]; then
    log_error "Health check 失敗（${HEALTH_URL}），最近 30 行服務日誌："
    journalctl -u "${SERVICE_NAME}" -n 30 --no-pager
    exit 1
fi
log_info "Health check 通過"

# ===================
# 更新摘要
# ===================
NEW_VERSION="$(read_version)"
NEW_COMMIT="$(git rev-parse HEAD)"

echo ""
echo "=== 更新完成 ==="
log_info "版本: ${OLD_VERSION} -> ${NEW_VERSION}"
if [ "${OLD_COMMIT}" = "${NEW_COMMIT}" ]; then
    log_info "沒有新的 commit（已是最新版本）"
else
    log_info "更新摘要（$(git rev-parse --short "${OLD_COMMIT}")..$(git rev-parse --short "${NEW_COMMIT}")）："
    git log --oneline "${OLD_COMMIT}..${NEW_COMMIT}"
fi
echo ""
echo "常用指令："
echo "  sudo systemctl status ${SERVICE_NAME}   # 查看狀態"
echo "  sudo journalctl -u ${SERVICE_NAME} -f   # 查看日誌"
