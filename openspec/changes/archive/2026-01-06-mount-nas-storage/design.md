# Design: NAS 掛載方式重構

## Context
目前系統使用 Python `smbprotocol` 庫存取 NAS，每次操作需要：
1. 建立 SMB 連線
2. 認證
3. 執行檔案操作
4. 斷開連線

這種方式在系統功能（知識庫、專案、Line Bot）中效能不佳，且程式碼重複。

## Goals
- 系統功能改用 CIFS 掛載，簡化檔案操作
- 服務啟動前確保 NAS 已掛載
- 保留檔案總管的多用戶權限機制

## Non-Goals
- 不改變檔案總管的 SMB 存取方式
- 不改變登入認證機制

## Decisions

### 1. 使用 systemd mount unit（而非 fstab）
**選擇**：建立 `/etc/systemd/system/mnt-nas.mount`

**原因**：
- 可與 `ching-tech-os.service` 建立依賴關係
- 失敗時有清楚的錯誤訊息
- 易於管理（enable/disable/status）

**替代方案**：
- `/etc/fstab` - 無法確保服務啟動前掛載完成
- `ExecStartPre` 掛載 - 混在一起不好管理

### 2. 憑證檔案獨立存放
**選擇**：建立 `/etc/nas-credentials`

**原因**：
- 權限設為 600，只有 root 可讀
- 避免密碼出現在 mount unit 或 fstab 中
- 符合安全最佳實踐

### 3. 新增 LocalFileService 而非修改 SMBService
**選擇**：新增 `services/local_file.py`

**原因**：
- SMBService 仍需保留給檔案總管使用
- 本機檔案操作邏輯完全不同
- 分離關注點，程式碼更清晰

### 4. 掛載點路徑
**選擇**：`/mnt/nas`

**原因**：
- 標準 Linux 掛載慣例
- 路徑簡短易讀
- 透過環境變數 `NAS_MOUNT_PATH` 可配置

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ching-tech-os.service                     │
│                    Requires=mnt-nas.mount                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      mnt-nas.mount                           │
│                  //192.168.11.50/擎添開發                    │
│                      → /mnt/nas                              │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   knowledge.py  │ │   project.py    │ │   linebot.py    │
│ LocalFileService│ │ LocalFileService│ │ LocalFileService│
│ /mnt/nas/...    │ │ /mnt/nas/...    │ │ /mnt/nas/...    │
└─────────────────┘ └─────────────────┘ └─────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                       api/nas.py                             │
│                      SMBService                              │
│                   （用戶帳密，不變）                          │
└─────────────────────────────────────────────────────────────┘
```

## File Changes

### install-service.sh 新增內容
```bash
# 1. 建立憑證檔案
cat > /etc/nas-credentials << EOF
username=${NAS_USER}
password=${NAS_PASSWORD}
EOF
chmod 600 /etc/nas-credentials

# 2. 建立掛載點
mkdir -p /mnt/nas

# 3. 建立 mount unit
cat > /etc/systemd/system/mnt-nas.mount << EOF
[Unit]
Description=NAS CIFS Mount
After=network-online.target
Wants=network-online.target

[Mount]
What=//192.168.11.50/擎添開發
Where=/mnt/nas
Type=cifs
Options=credentials=/etc/nas-credentials,uid=1000,gid=1000,iocharset=utf8,_netdev

[Install]
WantedBy=multi-user.target
EOF

# 4. 啟用掛載
systemctl daemon-reload
systemctl enable --now mnt-nas.mount
```

### config.py 新增
```python
# NAS 掛載路徑
nas_mount_path: str = _get_env("NAS_MOUNT_PATH", "/mnt/nas")

@property
def knowledge_local_path(self) -> str:
    return f"{self.nas_mount_path}/{self.knowledge_nas_path}"

@property
def project_local_path(self) -> str:
    return f"{self.nas_mount_path}/{self.project_nas_path}"

@property
def linebot_local_path(self) -> str:
    return f"{self.nas_mount_path}/{self.line_files_nas_path}"
```

## Risks / Trade-offs

| 風險 | 緩解措施 |
|------|----------|
| 掛載失敗導致服務無法啟動 | mount unit 有 `_netdev` 選項，等待網路就緒 |
| NAS 斷線導致檔案操作失敗 | 程式碼需處理 IOError，顯示友善錯誤訊息 |
| 權限問題 | 掛載時指定 uid/gid 為運行服務的用戶 |

## Migration Plan
1. 建立 proposal 並審核
2. 實作 install/uninstall 腳本修改
3. 實作 LocalFileService
4. 逐一重構 knowledge.py、project.py、linebot.py
5. 測試各功能正常運作
6. 重新執行 install-service.sh 部署
