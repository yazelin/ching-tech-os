# 租戶 NAS 隔離

## 概述

讓每個租戶的檔案儲存（知識庫、專案附件、Line Bot 檔案）能夠隔離，支援：
1. 租戶自訂 NAS：租戶可設定自己的 NAS 連線資訊
2. 子目錄隔離：使用系統 NAS 的租戶，檔案存放在 `/tenants/{tenant_code}/` 子目錄下

## 設計原則

類似 Line Bot 設定的模式：
- 租戶有自己的設定 → 用自己的
- 租戶沒有設定 → 用系統的（但資料隔離）

## 現有架構分析

### 已有的租戶路徑支援（✅ 已實作但未使用）

程式碼中已經有租戶路徑的支援，但目前沒有正確傳遞 `tenant_id`：

**path_manager.py**:
```python
def get_tenant_base_path(self, tenant_id: str | None = None) -> str:
    tid = tenant_id or DEFAULT_TENANT_ID
    return f"{self._settings.ctos_mount_path}/tenants/{tid}"

def to_filesystem(self, path: str, tenant_id: str | None = None) -> str:
    # CTOS zone 支援租戶隔離
    if parsed.zone == StorageZone.CTOS and tenant_id:
        return f"{self._settings.ctos_mount_path}/tenants/{tenant_id}/{parsed.path}"
```

**local_file.py**:
```python
def create_knowledge_file_service(tenant_id: str | None = None) -> LocalFileService:
    if tenant_id:
        base_path = f"{settings.ctos_mount_path}/tenants/{tenant_id}/knowledge"
    else:
        base_path = settings.knowledge_local_path  # 舊路徑
```

### 問題：tenant_id 沒有被傳遞

`knowledge.py:994` 和其他地方呼叫時沒有傳入 tenant_id：
```python
# 目前的呼叫方式（缺少 tenant_id）
file_service = create_knowledge_file_service()  # ❌ 沒有 tenant_id

# 應該改為
file_service = create_knowledge_file_service(tenant_id)  # ✅
```

### 架構挑戰：系統 NAS vs 自訂 NAS

| 模式 | 存取方式 | 服務類別 |
|------|----------|----------|
| 系統 NAS + 子目錄 | 本機掛載 `/mnt/nas/ctos/tenants/{id}/` | LocalFileService |
| 租戶自訂 NAS | SMB 動態連線 | SMBService |

這是架構上的重大差異：
- `LocalFileService` 使用本機路徑操作
- `SMBService` 使用 SMB 協定動態連線

## 資料結構

### tenants.settings 擴充

```json
{
  "line_channel_id": "...",
  "line_channel_secret": "...",
  "line_channel_access_token": "...",
  "nas": {
    "host": "192.168.1.100",
    "port": 445,
    "username": "tenant_user",
    "password": "encrypted_password",
    "share": "TenantShare",
    "base_path": ""
  }
}
```

如果 `nas` 為 `null` 或未設定，使用系統 NAS + 子目錄隔離。

## 路徑結構

### 使用系統 NAS 的租戶

```
/mnt/nas/ctos/
├── tenants/
│   ├── 00000000-0000-0000-0000-000000000000/  # 預設租戶
│   │   ├── knowledge/     # 知識庫附件
│   │   ├── projects/      # 專案附件
│   │   ├── linebot/       # Line Bot 檔案
│   │   └── ai-generated/  # AI 生成檔案
│   ├── {tenant-uuid-a}/   # 租戶 A
│   │   ├── knowledge/
│   │   ├── projects/
│   │   ├── linebot/
│   │   └── ai-generated/
│   └── {tenant-uuid-b}/   # 租戶 B
│       └── ...
└── ... (舊檔案，需遷移)
```

### 使用自訂 NAS 的租戶

租戶自訂 NAS 的根目錄結構：
```
/TenantShare/
├── knowledge/
├── projects/
├── linebot/
└── ai-generated/
```

## 實作策略

### 階段一：先修正現有的 tenant_id 傳遞（基礎）

在實作自訂 NAS 功能前，先確保現有的租戶路徑支援正確運作：

1. 修改所有服務呼叫，正確傳遞 `tenant_id`
2. 建立租戶目錄結構
3. 測試系統 NAS + 子目錄隔離

### 階段二：實作自訂 NAS（進階）

1. 新增 TenantNASService，抽象化檔案存取
2. 根據租戶設定選擇 LocalFileService 或 SMBService
3. 實作連線池管理（避免頻繁建立 SMB 連線）

## TenantNASService 設計

```python
class TenantNASService:
    """租戶 NAS 服務

    統一處理系統 NAS 和自訂 NAS 的檔案操作。
    """

    async def get_file_service(self, tenant_id: str) -> FileServiceProtocol:
        """取得租戶的檔案服務

        Returns:
            LocalFileService（系統 NAS）或 SMBService（自訂 NAS）
        """
        nas_config = await self.get_nas_config(tenant_id)

        if nas_config is None:
            # 使用系統 NAS + 租戶子目錄
            return LocalFileService(
                base_path=f"{settings.ctos_mount_path}/tenants/{tenant_id}"
            )
        else:
            # 使用租戶自訂 NAS
            return SMBService(
                host=nas_config.host,
                share=nas_config.share,
                username=nas_config.username,
                password=decrypt(nas_config.password),
            )

    async def get_nas_config(self, tenant_id: str) -> NASConfig | None:
        """取得租戶的 NAS 設定"""
        # 從 tenants.settings.nas 讀取
        pass

    async def ensure_tenant_directories(self, tenant_id: str) -> None:
        """確保租戶目錄存在"""
        pass
```

### FileServiceProtocol

為了讓 LocalFileService 和 SMBService 可以互換，需要定義統一介面：

```python
from typing import Protocol

class FileServiceProtocol(Protocol):
    def read_file(self, path: str) -> bytes: ...
    def write_file(self, path: str, data: bytes) -> None: ...
    def delete_file(self, path: str) -> None: ...
    def exists(self, path: str) -> bool: ...
    def list_directory(self, path: str) -> list[dict]: ...
```

## API 變更

### 租戶管理 API

新增 NAS 設定相關 API：

```
GET /api/platform/tenants/{id}/nas-settings
  - 取得租戶 NAS 設定（密碼不回傳）

PUT /api/platform/tenants/{id}/nas-settings
  - 更新租戶 NAS 設定

POST /api/platform/tenants/{id}/nas-settings/test
  - 測試 NAS 連線

DELETE /api/platform/tenants/{id}/nas-settings
  - 清除自訂設定（回到使用系統 NAS）
```

## 服務層變更

### 現有服務修改

需要修改以下服務，正確傳遞 `tenant_id`：

**knowledge.py**:
- `upload_attachment()` - 傳遞 tenant_id 到 file service
- `delete_attachment()` - 傳遞 tenant_id
- `copy_linebot_attachment_to_knowledge()` - 傳遞 tenant_id

**linebot.py**:
- `save_file_to_nas()` - 使用租戶路徑儲存檔案
- 檔案路徑格式需要變更

**project.py** (如有附件功能):
- 使用租戶路徑

**mcp_server.py**:
- MCP 工具需要從 context 取得 tenant_id
- 傳遞給相關服務

## 安全考量

1. **密碼加密**：租戶 NAS 密碼需加密儲存
   - 使用 Fernet 對稱加密
   - 金鑰從環境變數 `ENCRYPTION_KEY` 取得

2. **路徑驗證**：防止路徑穿越攻擊
   - 已有 `validate_tenant_path()` 方法

3. **權限檢查**：確保只有平台管理員可修改 NAS 設定

4. **SMB 連線安全**：
   - 連線逾時設定
   - 連線池管理避免資源洩漏

## 資料遷移

### 現有檔案遷移

對於使用系統 NAS 的現有租戶，需要將檔案遷移到子目錄：

1. 建立 `/tenants/{tenant_id}/` 目錄結構
2. 遷移知識庫附件
3. 遷移專案附件
4. 遷移 Line Bot 檔案
5. 更新資料庫中的檔案路徑

### 資料庫遷移

**需要更新的表格**:
- `line_files.nas_path` - 目前是 `ai-images/...`，需要加入租戶路徑
- `project_attachments.storage_path` - 確認格式
- `knowledge 附件` - 儲存在 Markdown frontmatter 中

## 相容性

- 現有的「檔案管理器」功能不受影響（使用者自己輸入帳密）
- 系統功能（知識庫、專案、Line Bot）會自動使用租戶隔離的路徑
- 單租戶模式繼續使用預設租戶路徑

## 風險與注意事項

1. **SMB 連線效能**：自訂 NAS 需要動態 SMB 連線，可能影響效能
   - 考慮連線池
   - 考慮快取

2. **錯誤處理**：自訂 NAS 連線失敗時的處理
   - 友善的錯誤訊息
   - 不影響其他租戶

3. **遷移風險**：現有檔案遷移需要謹慎
   - 建議先備份
   - 可選擇停機遷移
