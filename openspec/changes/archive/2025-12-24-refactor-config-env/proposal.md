# Change: Config 環境變數重構與敏感資料清理

## Why
目前 `config.py` 大部分設定都是硬編碼的，包含敏感資料如密碼、NAS 連線資訊等。這違反安全最佳實踐：
1. 敏感資料不應該提交到版本控制
2. 不同環境（開發/測試/生產）需要不同設定
3. Git 歷史中已存在敏感資料，未來若公開 repo 會有安全風險

需要：
1. 將所有敏感和環境相關的設定移到 `.env` 檔案
2. 清理 Git 歷史中的敏感資料

## What Changes
- **重構 config.py**：所有設定改用 `os.getenv()` 讀取
- **更新 .env**：新增所有必要的環境變數
- **新增 .env.example**：提供範例設定檔（不含敏感值）
- **新增管理員設定**：`ADMIN_USERNAME` 環境變數
- **清理 Git 歷史**：使用 `git filter-repo` 移除歷史中的敏感資料

## Impact
- Affected specs: `backend-auth`
- Affected code:
  - `backend/src/ching_tech_os/config.py` - 主要修改
  - `.env` - 新增環境變數
  - `.env.example` - 新增範例檔
- Git 歷史會被重寫，需要 force push

## Design Decisions

### 環境變數分類

**必須在 .env（敏感/環境相關）：**
```env
# 管理員帳號
ADMIN_USERNAME=yazelin

# 資料庫
DB_HOST=localhost
DB_PORT=5432
DB_USER=ching_tech
DB_PASSWORD=your_password
DB_NAME=ching_tech_os

# NAS 設定
NAS_HOST=192.168.11.50
NAS_PORT=445
NAS_USER=your_user
NAS_PASSWORD=your_password
NAS_SHARE=擎添開發

# Line Bot
LINE_CHANNEL_SECRET=your_secret
LINE_CHANNEL_ACCESS_TOKEN=your_token

# Session
SESSION_TTL_HOURS=8

# 路徑設定（可選，有預設值）
FRONTEND_DIR=/home/ct/SDD/ching-tech-os/frontend
KNOWLEDGE_NAS_PATH=ching-tech-os/knowledge
PROJECT_NAS_PATH=ching-tech-os/projects
LINEBOT_NAS_PATH=ching-tech-os/linebot/files
PROJECT_ATTACHMENTS_PATH=/home/ct/SDD/ching-tech-os/data/projects/attachments
```

**保留在 config（應用常數）：**
```python
# Bot 觸發名稱列表
line_bot_trigger_names = [...]

# CORS 來源
cors_origins = [...]
```

### Git 歷史清理方式

使用 `git filter-repo` 替換敏感字串：

```bash
# 建立替換規則檔案
cat > /tmp/replacements.txt << 'EOF'
Ct36274806==>REMOVED_PASSWORD
ching_tech_dev==>REMOVED_PASSWORD
728c8715da2cff5cc8f3cfc282d0888f==>REMOVED_SECRET
eV8ka/8k5KpE3r4R+uOGf/kwt9Ekm2USNa/X5A9XPNy0Qt54vepp12bg9L2HqsWWwe9rE0oMAAlLpPG/7zLwIwnyM5iIP0hrhIhF2z7GaPL7nFL7C9PmGYJ6i3d7fEb70HPsEjZGI4HT5/RH+OOATAdB04t89/1O/w1cDnyilFU===>REMOVED_TOKEN
EOF

# 執行替換
git filter-repo --replace-text /tmp/replacements.txt --force
```

## Migration
1. 備份目前的 .env
2. 更新 .env 加入所有環境變數
3. 修改 config.py 使用 os.getenv()
4. 建立 .env.example
5. 執行 git filter-repo 清理歷史
6. Force push 到 GitHub
7. 測試應用程式正常運作
