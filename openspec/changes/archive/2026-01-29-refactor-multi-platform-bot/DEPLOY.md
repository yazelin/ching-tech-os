# 正式機部署步驟

## 前置條件
- 正式機 alembic_version 目前為 `014`（舊編號系統）
- 新的 migration 檔案從 `001` 開始重編

## 部署步驟

### 1. 停止服務
```bash
sudo systemctl stop ching-tech-os
```

### 2. 更新程式碼
```bash
cd /path/to/ching-tech-os
git pull
```

### 3. 對齊 Alembic 版本（不執行任何 SQL）
```bash
cd backend
uv run alembic stamp 004
```
> 這只是告訴 alembic 目前 schema 等於 004，不會改動任何表格或資料。

### 4. 執行 Migration（005: 表格重命名 + 時間格式統一）
```bash
uv run alembic upgrade head
```
> 005 做的事：
> - 7 個 `line_*` 表格重命名為 `bot_*`
> - 5 個主表加入 `platform_type` 欄位（預設 'line'）
> - 13 個 timestamp 欄位統一為 with time zone
> - **所有資料保留，不會遺失**

### 5. 驗證
```bash
# 確認版本
uv run alembic current
# 應顯示: 005 (head)

# 確認表格已改名
docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -c "\dt bot_*"
# 應看到 7 個 bot_* 表格

# 確認沒有殘留的 line_* 表格
docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -c "\dt line_*"
# 應顯示 "Did not find any relation"
```

### 6. 啟動服務
```bash
sudo systemctl start ching-tech-os
```

## 回滾（如需要）
```bash
cd backend
uv run alembic downgrade 004
# bot_* 會改回 line_*，platform_type 欄位會被移除
# 資料不受影響
```
