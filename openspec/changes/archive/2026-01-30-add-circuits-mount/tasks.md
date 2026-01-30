# Tasks: add-circuits-mount

## 1. 新增 circuits mount unit 與環境變數
- [x] `scripts/install-service.sh`：新增 `mnt-nas-circuits.mount`（唯讀）
- [x] `scripts/install-service.sh`：service unit 加 `Wants=mnt-nas-circuits.mount`
- [x] `.env.example`：新增 `CIRCUITS_MOUNT_PATH=/mnt/nas/circuits`
- [x] `backend/src/ching_tech_os/config.py`：新增 `circuits_mount_path`

## 2. path_manager 支援 shared 子來源（核心）
- [x] `services/path_manager.py`：新增 `_shared_mounts` 字典
- [x] 解析 `shared://projects/...` 和 `shared://circuits/...` 到對應掛載點
- [x] 舊格式 `shared://亦達光學/...` 向後相容（fallback 到 projects）
- [x] `to_filesystem()` 透過 `_resolve_shared_path()` 處理子來源路徑
- [x] 反向解析：本機路徑 `/mnt/nas/circuits/xxx` → `shared://circuits/xxx`

## 3. get_nas_file_info 改用 path_manager
- [x] `services/mcp_server.py`：移除硬寫 `projects_path`，改用 `validate_nas_file_path()`

## 4. search_nas_files 擴展為多來源搜尋
- [x] `services/mcp_server.py`：定義 `search_sources` 字典（projects + circuits）
- [x] 遍歷所有來源搜尋，結果路徑帶來源前綴
- [x] 單一來源掛載不存在時跳過
- [x] 加註 TODO 權限擴充點

## 5. 更新 AI Prompt 描述
- [x] `bot/agents.py`：`FILE_TOOLS_PROMPT` 更新
- [x] `services/linebot_agents.py`：同步更新
- [x] `migrations/versions/seed_data.sql`：更新 prompt
- [x] `migrations/versions/009_update_search_nas_files_prompt.py`：新增 migration

## 6. 更新相關文件
- [x] `.env.example`：更新掛載架構註解
