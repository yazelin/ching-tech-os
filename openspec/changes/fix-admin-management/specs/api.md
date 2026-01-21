# API 規格：管理員管理功能修復

## 新增 API

### GET /api/admin/tenants/{tenant_id}/users

列出指定租戶內的所有使用者。

**權限**: 僅平台管理員

**Path Parameters**:
| 參數 | 類型 | 說明 |
|------|------|------|
| tenant_id | UUID | 租戶 ID |

**Query Parameters**:
| 參數 | 類型 | 預設 | 說明 |
|------|------|------|------|
| include_inactive | bool | false | 是否包含已停用的使用者 |

**Response** (200):
```json
{
  "users": [
    {
      "id": 1,
      "username": "jay",
      "display_name": "Jay Chen",
      "role": "user",
      "is_admin": false
    },
    {
      "id": 2,
      "username": "alice",
      "display_name": "Alice Wang",
      "role": "tenant_admin",
      "is_admin": true
    }
  ]
}
```

**Error Responses**:
- 403: 非平台管理員
- 404: 租戶不存在

---

## 修改 API

### DELETE /api/admin/tenants/{tenant_id}/admins/{user_id}

移除租戶管理員。

**權限**: 僅平台管理員

**Path Parameters**:
| 參數 | 類型 | 說明 |
|------|------|------|
| tenant_id | UUID | 租戶 ID |
| user_id | int | 使用者 ID |

**Query Parameters** (新增):
| 參數 | 類型 | 預設 | 說明 |
|------|------|------|------|
| delete_user | bool | false | 是否同時刪除使用者帳號 |

**Response** (200):
```json
{
  "success": true,
  "message": "已移除管理員"
}
```

或（當 delete_user=true）:
```json
{
  "success": true,
  "message": "已移除管理員並刪除帳號"
}
```

**Error Responses**:
- 403: 非平台管理員
- 404: 租戶或管理員不存在

---

## 資料模型

### TenantUserBrief

```python
class TenantUserBrief(BaseModel):
    """租戶使用者簡要資訊"""
    id: int
    username: str
    display_name: str | None
    role: str  # user, tenant_admin
    is_admin: bool  # 是否已是此租戶的管理員
```

### TenantUserListResponse

```python
class TenantUserListResponse(BaseModel):
    """租戶使用者列表回應"""
    users: list[TenantUserBrief]
```
