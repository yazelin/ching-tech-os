# 帳號模型（NAS／平台雙模式登入）與 CORS 實作計劃

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 後端支援「NAS 帳號」與「平台帳號」兩種登入方式、平台帳號可綁定 NAS 帳號，並讓新前端 os.ching-tech.com 能跨網域打 API。

**Architecture:** `users` 表新增 `nas_username` 作為 NAS 綁定欄位（既有帳號回填等於 `username`）。登入請求加 `method` 欄位，預設 `nas` 讓舊前端完全不變；`nas` 走 SMB 驗證後依 `nas_username` 找人或自動建帳號，`local` 只驗密碼雜湊。Session 載入時順帶查出 `nas_username`，檔案類 API 的 SMB 憑證改用它。CORS 由環境變數追加 origin。

**Tech Stack:** FastAPI、asyncpg（raw SQL）、Alembic、pytest + pytest-asyncio、httpx ASGITransport。

**Spec:** `docs/superpowers/specs/2026-09-10-ctos-web-react-frontend-design.md` 第四節「後端改動」的帳號模型與 CORS 兩段。專案模組、前端、ERPNext 匯出不在本計劃。

## Global Constraints

- 舊前端登入一行不改：`LoginRequest.method` 預設 `"nas"`，行為與現在完全相同。
- 登入失敗一律回「帳號或密碼錯誤」，不區分帳號不存在與密碼錯。
- PAT（`ctos_pat_` 前綴）行為不變。
- 所有 SQL 走 `get_connection()` 的 asyncpg 連線，`$1` 參數化，不字串拼接。
- 測試照 repo 慣例：`monkeypatch.setattr(<module>, "get_connection", ...)` 隔離 DB；路由測試用 `httpx.AsyncClient(transport=ASGITransport(app=app))`。
- CI coverage 門檻 85%（`.github/workflows/backend-tests.yml`）；新程式碼要有測試。
- 所有指令在 `backend/` 目錄下以 `uv run` 執行。
- Commit 訊息正體中文，結尾附 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`。
- 每個 task 一個 commit；全部做完開一個 PR，設 auto-merge。

## 檔案地圖

| 檔案 | 動作 | 責任 |
|------|------|------|
| `backend/migrations/versions/026_add_users_nas_username.py` | 新增 | `users.nas_username` 欄位與回填 |
| `backend/src/ching_tech_os/services/user.py` | 修改 | `upsert_user` 寫入 nas_username；`get_user_for_auth` 多選一欄；新增 `get_user_by_nas_username`、`set_nas_username` |
| `backend/src/ching_tech_os/models/auth.py` | 修改 | `LoginRequest.method`、`SessionData.nas_username` |
| `backend/src/ching_tech_os/models/user.py` | 修改 | `UserInfo.nas_username`、`NasBindingRequest`、`NasBindingResponse` |
| `backend/src/ching_tech_os/api/auth.py` | 修改 | 登入分流 |
| `backend/src/ching_tech_os/services/session.py` | 修改 | 載入 session 時查 nas_username |
| `backend/src/ching_tech_os/api/nas.py`、`api/files.py` | 修改 | SMB fallback 用 nas_username |
| `backend/src/ching_tech_os/api/user.py` | 修改 | `/me` 回 nas_username；新增綁定／解綁端點 |
| `backend/src/ching_tech_os/config.py` | 修改 | `CORS_EXTRA_ORIGINS` |
| `backend/.env.example`、`docs/backend.md`、`README.md` | 修改 | 文件 |
| `backend/tests/test_user_service_smoke.py`、`test_auth_api_module.py`、`test_session.py`、`test_api_nas_module.py`、`test_api_user_routes.py`、新增 `test_config_cors.py` | 測試 |

---

### Task 1: Migration — `users.nas_username`

**Files:**
- Create: `backend/migrations/versions/026_add_users_nas_username.py`

**Interfaces:**
- Produces: 欄位 `users.nas_username VARCHAR(100) NULL UNIQUE`，既有列全部 `nas_username = username`。

- [ ] **Step 1: 確認目前 head 是 025**

Run: `cd backend && uv run alembic heads`
Expected: 輸出含 `025`

- [ ] **Step 2: 寫 migration**

```python
"""users 加 nas_username（NAS 帳號綁定）

平台帳號與 NAS 帳號脫鉤：username 是平台識別，nas_username 是綁定的 NAS 帳號。
既有帳號全部源自 NAS 登入，回填 nas_username = username。

Revision ID: 026
"""

from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("nas_username", sa.String(100), nullable=True))
    op.execute("UPDATE users SET nas_username = username WHERE nas_username IS NULL")
    op.create_unique_constraint("uq_users_nas_username", "users", ["nas_username"])


def downgrade() -> None:
    op.drop_constraint("uq_users_nas_username", "users", type_="unique")
    op.drop_column("users", "nas_username")
```

- [ ] **Step 3: 本機資料庫套用並驗證**

Run: `cd backend && uv run alembic upgrade head && uv run alembic current`
Expected: `026 (head)`

Run（需本機 Postgres，docker-compose 有起）：
`docker compose -f ../docker/docker-compose.yml exec -T postgres psql -U ctos -d ctos -c "SELECT COUNT(*) AS total, COUNT(nas_username) AS bound FROM users;"`
Expected: `total` 等於 `bound`

- [ ] **Step 4: 驗 downgrade 再 upgrade 都過**

Run: `cd backend && uv run alembic downgrade 025 && uv run alembic upgrade head`
Expected: 無錯誤

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/026_add_users_nas_username.py
git commit -m "feat(db): users 加 nas_username，既有帳號回填等於 username

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: user service — nas_username 讀寫

**Files:**
- Modify: `backend/src/ching_tech_os/services/user.py:8-33`（`upsert_user`）、`:60-81`（`get_user_for_auth`）、檔尾新增兩函式
- Test: `backend/tests/test_user_service_smoke.py`

**Interfaces:**
- Produces:
  - `upsert_user(username: str) -> int`：INSERT 時同時寫 `nas_username = username`；username 衝突時若該列 `nas_username` 為 NULL 則補上。
  - `get_user_for_auth(username) -> dict | None`：回傳 dict 多一個 `nas_username` 鍵。
  - `get_user_by_nas_username(nas_username: str) -> dict | None`：欄位同 `get_user_for_auth`。
  - `set_nas_username(user_id: int, nas_username: str | None) -> None`：寫入或清空；若 nas_username 已被別的帳號綁走，raise `ValueError("此 NAS 帳號已綁定其他使用者")`。

- [ ] **Step 1: 寫失敗的測試**

在 `backend/tests/test_user_service_smoke.py` 末尾加：

```python
@pytest.mark.asyncio
async def test_nas_username_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = SimpleNamespace(
        fetchrow=AsyncMock(side_effect=[
            {"id": 7},                                  # upsert_user
            {"id": 8, "username": "p", "nas_username": "n"},  # get_user_by_nas_username
            None,                                        # get_user_by_nas_username miss
            {"id": 9, "nas_username": "n", "password_hash": None},  # get_user_for_auth
        ]),
        execute=AsyncMock(side_effect=["UPDATE 1", Exception("duplicate key value violates unique constraint")]),
    )
    _patch_conn(monkeypatch, conn)

    assert await user_service.upsert_user("n") == 7
    insert_sql, *insert_args = conn.fetchrow.call_args_list[0][0]
    assert "nas_username" in insert_sql and insert_args[0] == "n"

    assert (await user_service.get_user_by_nas_username("n"))["id"] == 8
    assert await user_service.get_user_by_nas_username("x") is None
    assert (await user_service.get_user_for_auth("p"))["nas_username"] == "n"

    await user_service.set_nas_username(9, "n2")
    with pytest.raises(ValueError):
        await user_service.set_nas_username(9, "taken")
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd backend && uv run pytest tests/test_user_service_smoke.py::test_nas_username_helpers -v`
Expected: FAIL，`AttributeError: ... has no attribute 'get_user_by_nas_username'`

- [ ] **Step 3: 實作**

`upsert_user` 的 SQL 改成：

```python
        result = await conn.fetchrow(
            """
            INSERT INTO users (username, nas_username, last_login_at)
            VALUES ($1, $1, $2)
            ON CONFLICT (username) DO UPDATE
            SET last_login_at = $2,
                nas_username = COALESCE(users.nas_username, EXCLUDED.nas_username)
            RETURNING id
            """,
            username,
            datetime.now(),
        )
```

`get_user_for_auth` 的 SELECT 欄位加 `nas_username`：

```python
            SELECT id, username, display_name, role, nas_username,
                   password_hash, must_change_password, is_active, preferences
            FROM users
            WHERE username = $1
```

檔尾新增：

```python
async def get_user_by_nas_username(nas_username: str) -> dict | None:
    """依綁定的 NAS 帳號取得使用者（欄位同 get_user_for_auth）"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, username, display_name, role, nas_username,
                   password_hash, must_change_password, is_active, preferences
            FROM users
            WHERE nas_username = $1
            """,
            nas_username,
        )
        return dict(row) if row else None


async def set_nas_username(user_id: int, nas_username: str | None) -> None:
    """綁定或解綁（None）NAS 帳號

    Raises:
        ValueError: nas_username 已綁定其他使用者
    """
    async with get_connection() as conn:
        try:
            await conn.execute(
                "UPDATE users SET nas_username = $2 WHERE id = $1",
                user_id,
                nas_username,
            )
        except Exception as e:
            if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
                raise ValueError("此 NAS 帳號已綁定其他使用者")
            raise
```

- [ ] **Step 4: 跑測試確認通過，並跑整檔**

Run: `cd backend && uv run pytest tests/test_user_service_smoke.py -v`
Expected: 全部 PASS（原本 `test_user_basic_queries` 的 upsert 斷言仍成立，它只看回傳值）

- [ ] **Step 5: Commit**

```bash
git add backend/src/ching_tech_os/services/user.py backend/tests/test_user_service_smoke.py
git commit -m "feat(user): nas_username 讀寫——upsert 自動綁定、依 NAS 帳號查人、綁定與解綁

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: 資料模型 — `LoginRequest.method`、`SessionData.nas_username`、`UserInfo.nas_username`

**Files:**
- Modify: `backend/src/ching_tech_os/models/auth.py:19-24`、`:41-60`
- Modify: `backend/src/ching_tech_os/models/user.py:14-30`、檔尾

**Interfaces:**
- Produces:
  - `LoginRequest.method: Literal["nas", "local"] = "nas"`
  - `SessionData.nas_username: str | None = None`
  - `UserInfo.nas_username: str | None = None`
  - `NasBindingRequest(nas_username: str, password: str)`
  - `NasBindingResponse(success: bool, nas_username: str | None)`

- [ ] **Step 1: 改 `models/auth.py`**

檔頭 import 加 `from typing import Literal`。

```python
class LoginRequest(BaseModel):
    """登入請求"""

    username: str
    password: str
    device: DeviceInfo | None = None
    # nas：SMB 驗證（預設，舊前端不帶此欄位）；local：平台帳號密碼
    method: Literal["nas", "local"] = "nas"
```

`SessionData` 在 `read_only` 之後加：

```python
    # 綁定的 NAS 帳號；SMB 操作用它，None 表示未綁定
    nas_username: str | None = None
```

- [ ] **Step 2: 改 `models/user.py`**

`UserInfo` 在 `has_password` 之後加：

```python
    # 綁定的 NAS 帳號（None 表示未綁定）
    nas_username: str | None = None
```

檔尾加：

```python
class NasBindingRequest(BaseModel):
    """綁定 NAS 帳號請求：以 NAS 帳密驗證後寫入 nas_username"""

    nas_username: str
    password: str


class NasBindingResponse(BaseModel):
    """綁定／解綁 NAS 帳號回應"""

    success: bool
    nas_username: str | None = None
```

- [ ] **Step 3: 驗既有測試不受影響**

Run: `cd backend && uv run pytest tests/test_session.py tests/test_auth_api_module.py tests/test_api_user_routes.py -q`
Expected: 全部 PASS（都是加預設值的欄位）

- [ ] **Step 4: Commit**

```bash
git add backend/src/ching_tech_os/models/auth.py backend/src/ching_tech_os/models/user.py
git commit -m "feat(models): 登入加 method 欄位，session 與使用者資訊帶 nas_username

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: 登入分流 — `nas` 與 `local`

**Files:**
- Modify: `backend/src/ching_tech_os/api/auth.py:22`（import）、`:242-243`（查使用者）、`:262-310`（認證分支）、`:362-374`（建帳號）
- Test: `backend/tests/test_auth_api_module.py`

**Interfaces:**
- Consumes: Task 2 的 `get_user_by_nas_username`、`upsert_user`；Task 3 的 `LoginRequest.method`。
- Produces: `POST /api/auth/login` 行為：
  - `method="nas"`：`settings.enable_nas_auth` 為 False 直接回失敗。SMB 驗 `request.username`／`request.password`；成功後 `user_data = get_user_by_nas_username(request.username)`，沒有就 `upsert_user(request.username)`。session 存 SMB 密碼。
  - `method="local"`：`user_data = get_user_for_auth(request.username)`；必須有 `password_hash` 且 `verify_password` 通過，否則失敗；不 fallback SMB。session 不存密碼。
  - 停用帳號檢查兩種方式都做。

- [ ] **Step 1: 寫失敗的測試**

在 `backend/tests/test_auth_api_module.py` 末尾加：

```python
@pytest.mark.asyncio
async def test_login_local_method_never_touches_smb(monkeypatch: pytest.MonkeyPatch) -> None:
    """local：只驗密碼；沒密碼的帳號不會 fallback 去問 NAS。"""
    req = _request({"user-agent": "pytest-agent"})
    monkeypatch.setattr(auth, "resolve_ip_location", lambda _ip: None)
    monkeypatch.setattr(auth, "parse_device_info", lambda _ua: None)
    monkeypatch.setattr(auth, "record_login", AsyncMock(return_value=1))
    monkeypatch.setattr(auth, "log_message", AsyncMock(return_value=1))
    monkeypatch.setattr(auth, "emit_new_message", AsyncMock())
    monkeypatch.setattr(auth, "emit_unread_count", AsyncMock())
    monkeypatch.setattr(auth.settings, "enable_nas_auth", True)
    smb = AsyncMock(return_value=None)
    monkeypatch.setattr(auth, "run_in_smb_pool", smb)
    create = AsyncMock(return_value="tok")
    monkeypatch.setattr(auth.session_manager, "create_session", create)
    monkeypatch.setattr(auth, "get_user_role", AsyncMock(return_value="user"))
    monkeypatch.setattr(permissions_service, "get_user_app_permissions_sync", lambda _r, _u: {})
    monkeypatch.setattr(auth, "update_last_login", AsyncMock())

    # 沒有密碼的帳號用 local 登入 → 失敗，且 SMB 沒被呼叫
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value={
        "id": 1, "password_hash": None, "is_active": True, "nas_username": "u1",
    }))
    res = await auth.login(LoginRequest(username="u1", password="p", method="local"), req)
    assert res.success is False and res.error == "帳號或密碼錯誤"
    smb.assert_not_called()

    # 有密碼且正確 → 成功，session 不存密碼
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value={
        "id": 1, "password_hash": "h", "is_active": True, "must_change_password": False,
        "preferences": {}, "nas_username": None,
    }))
    monkeypatch.setattr(auth, "verify_password", lambda _pw, _h: True)
    res = await auth.login(LoginRequest(username="u1", password="p", method="local"), req)
    assert res.success is True and res.token == "tok"
    assert create.call_args[0][1] == ""  # session_password


@pytest.mark.asyncio
async def test_login_nas_method_binds_by_nas_username(monkeypatch: pytest.MonkeyPatch) -> None:
    """nas：SMB 驗過後依 nas_username 找人；找不到就自動建帳號。"""
    req = _request({"user-agent": "pytest-agent"})
    monkeypatch.setattr(auth, "resolve_ip_location", lambda _ip: None)
    monkeypatch.setattr(auth, "parse_device_info", lambda _ua: None)
    monkeypatch.setattr(auth, "record_login", AsyncMock(return_value=1))
    monkeypatch.setattr(auth, "log_message", AsyncMock(return_value=1))
    monkeypatch.setattr(auth, "emit_new_message", AsyncMock())
    monkeypatch.setattr(auth, "emit_unread_count", AsyncMock())
    monkeypatch.setattr(auth.settings, "enable_nas_auth", True)
    monkeypatch.setattr(auth, "run_in_smb_pool", AsyncMock(return_value=None))
    create = AsyncMock(return_value="tok")
    monkeypatch.setattr(auth.session_manager, "create_session", create)
    monkeypatch.setattr(auth, "get_user_role", AsyncMock(return_value="user"))
    monkeypatch.setattr(permissions_service, "get_user_app_permissions_sync", lambda _r, _u: {})
    monkeypatch.setattr(auth, "update_last_login", AsyncMock())
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(side_effect=AssertionError("nas 不該查 username")))

    # 平台帳號 alice 綁了 NAS 帳號 nas-a：用 nas-a 登入，session 的 username 是 alice
    monkeypatch.setattr(auth, "get_user_by_nas_username", AsyncMock(return_value={
        "id": 3, "username": "alice", "nas_username": "nas-a", "password_hash": "h",
        "is_active": True, "preferences": {},
    }))
    res = await auth.login(LoginRequest(username="nas-a", password="p", method="nas"), req)
    assert res.success is True and res.username == "alice"
    assert create.call_args[0][0] == "alice"
    assert create.call_args[0][1] == "p"  # SMB 密碼要留在 session

    # 沒綁過的 NAS 帳號 → upsert_user 自動建
    monkeypatch.setattr(auth, "get_user_by_nas_username", AsyncMock(return_value=None))
    upsert = AsyncMock(return_value=10)
    monkeypatch.setattr(auth, "upsert_user", upsert)
    res = await auth.login(LoginRequest(username="new-nas", password="p", method="nas"), req)
    assert res.success is True
    upsert.assert_awaited_once_with("new-nas")

    # NAS 驗證關閉 → nas 方式直接失敗
    monkeypatch.setattr(auth.settings, "enable_nas_auth", False)
    res = await auth.login(LoginRequest(username="new-nas", password="p", method="nas"), req)
    assert res.success is False
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd backend && uv run pytest tests/test_auth_api_module.py -k "local_method or nas_method" -v`
Expected: FAIL（`get_user_by_nas_username` 不在 `auth` 模組、或 `res.username` 不是 alice）

- [ ] **Step 3: 實作分流**

import 那行改成：

```python
from ..services.user import (
    upsert_user,
    get_user_by_username,
    get_user_for_auth,
    get_user_by_nas_username,
    update_last_login,
    get_user_role,
)
```

把 `# 先嘗試從資料庫查找使用者` 到 `if not auth_success:` 之前那整段（查使用者、停用檢查、認證邏輯）改成下面這樣。停用檢查那段（record_login + log_message + return）**保留原樣**，只是位置往後挪到查完使用者之後：

```python
    auth_success = False
    use_password_auth = request.method == "local"
    must_change_password = False
    user_data = None

    if request.method == "local":
        # 平台帳號：只驗密碼雜湊，不 fallback SMB
        user_data = await get_user_for_auth(request.username)
        if user_data and not user_data.get("is_active", True):
            return await _reject_inactive(request, user_data, ip_address, user_agent, geo, device_info)
        if user_data and user_data.get("password_hash") and verify_password(
            request.password, user_data["password_hash"]
        ):
            auth_success = True
            must_change_password = user_data.get("must_change_password", False)
    else:
        # NAS 帳號：SMB 驗證，再依綁定找平台帳號
        if not settings.enable_nas_auth:
            return LoginResponse(success=False, error="NAS 登入未啟用")
        user_data = await get_user_by_nas_username(request.username)
        if user_data and not user_data.get("is_active", True):
            return await _reject_inactive(request, user_data, ip_address, user_agent, geo, device_info)
        smb = create_smb_service(request.username, request.password)
        try:
            await run_in_smb_pool(smb.test_auth)
            auth_success = True
        except SMBAuthError:
            auth_success = False
        except SMBConnectionError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="無法連線至檔案伺服器",
            )
```

把原本停用檢查那段抽成模組層級的 helper（內容照搬原本的 record_login、log_message、回傳）：

```python
async def _reject_inactive(request, user_data, ip_address, user_agent, geo, device_info) -> LoginResponse:
    """停用帳號的登入嘗試也要留紀錄：有人在試離職員工的帳號時管理員才看得到"""
    try:
        await record_login(
            username=request.username,
            success=False,
            ip_address=ip_address,
            user_id=user_data["id"],
            failure_reason="帳號已停用",
            user_agent=user_agent,
            geo=geo,
            device=device_info,
        )
        await log_message(
            severity=MessageSeverity.WARNING,
            source=MessageSource.SECURITY,
            title=f"停用帳號登入嘗試：{request.username}",
            content=f"來自 {ip_address} 的登入嘗試被拒（帳號已停用）",
            category="auth",
            metadata={"ip": ip_address, "username": request.username},
        )
    except Exception:
        pass
    return LoginResponse(success=False, error="此帳號已被停用")
```

（原本停用分支的 `content`／`metadata` 若與上面不同，以原碼為準照搬，不要改字。）

認證成功後那段：

```python
    if user_data:
        user_id = user_data["id"]
        await update_last_login(user_id)
    else:
        # NAS 驗過但平台沒這個人：建帳號並綁定 nas_username（見 upsert_user）
        try:
            user_id = await upsert_user(request.username)
        except Exception as e:
            ...（原碼不變）
```

`create_session` 與 `LoginResponse` 的 username 改用平台帳號：

```python
    platform_username = user_data["username"] if user_data else request.username
    token = await session_manager.create_session(
        platform_username,
        session_password,
        user_id=user_id,
        role=user_role,
        app_permissions=app_permissions,
    )
```

後面 `record_login(username=...)`、`log_message` 標題、以及最後 `LoginResponse(username=...)` 都改用 `platform_username`。`auth_method` 字串維持 `"密碼"`／`"SMB"`。

- [ ] **Step 4: 跑整檔測試**

Run: `cd backend && uv run pytest tests/test_auth_api_module.py -v`
Expected: 全部 PASS。原本 `test_login_paths` 的密碼認證段以 `method` 預設 `nas` 呼叫，會走 SMB 分支而非密碼分支：把該測試裡「密碼認證成功」「帳號停用」「密碼錯誤」三段的 `LoginRequest` 加上 `method="local"`，並把 `get_user_for_auth` 的 mock 改為 `get_user_by_nas_username`（SMB 段）。改完後全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/src/ching_tech_os/api/auth.py backend/tests/test_auth_api_module.py
git commit -m "feat(auth): 登入分 nas/local 兩種方式——nas 依綁定找平台帳號，local 只驗密碼

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Session 載入帶 nas_username

**Files:**
- Modify: `backend/src/ching_tech_os/services/session.py:128-155`
- Test: `backend/tests/test_session.py`

**Interfaces:**
- Consumes: Task 3 的 `SessionData.nas_username`。
- Produces: `session_manager.get_session(token)` 回傳的 `SessionData.nas_username` 等於該 user 目前的 `users.nas_username`。

- [ ] **Step 1: 寫失敗的測試**

在 `tests/test_session.py` 的 `TestSessionManagerGet` class 加一個方法：

```python
    @pytest.mark.asyncio
    async def test_db_row_carries_nas_username(self, session_manager):
        """session 載入時要順帶查出綁定的 NAS 帳號"""
        now = datetime.now()
        row = {
            "username": "alice",
            "password_enc": "",
            "nas_host": "10.0.0.3",
            "user_id": 3,
            "created_at": now,
            "expires_at": now,
            "role": "user",
            "app_permissions": {},
            "nas_username": "nas-a",
        }
        conn, cm = _make_mock_connection()
        conn.fetchrow = AsyncMock(return_value=row)

        with patch("ching_tech_os.services.session.get_connection", return_value=cm):
            result = await session_manager.get_session("t")

        assert result.nas_username == "nas-a"
        assert "nas_username" in conn.fetchrow.call_args[0][0]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd backend && uv run pytest tests/test_session.py -k nas_username -v`
Expected: FAIL，`result.nas_username` 是 None

- [ ] **Step 3: 實作**

SQL 改成（RETURNING 裡用子查詢，不用改 sessions 表）：

```python
            row = await conn.fetchrow(
                """
                UPDATE sessions SET last_accessed_at = NOW()
                WHERE token = $1 AND expires_at > NOW()
                RETURNING username, password_enc, nas_host, user_id,
                          created_at, expires_at, role, app_permissions,
                          (SELECT u.nas_username FROM users u WHERE u.id = sessions.user_id) AS nas_username
                """,
                token,
            )
```

`SessionData(...)` 建構加一行：

```python
            nas_username=row["nas_username"],
```

`test_session.py` 裡其他既有的 `row = {...}` 都補上 `"nas_username": None`，否則 KeyError。

- [ ] **Step 4: 跑整檔**

Run: `cd backend && uv run pytest tests/test_session.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/ching_tech_os/services/session.py backend/tests/test_session.py
git commit -m "feat(session): 載入 session 時查出綁定的 nas_username

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: SMB fallback 改用 nas_username

**Files:**
- Modify: `backend/src/ching_tech_os/api/nas.py:183-187`、`:349-353`；`backend/src/ching_tech_os/api/files.py:115-119`
- Test: `backend/tests/test_api_nas_module.py`

**Interfaces:**
- Consumes: `SessionData.nas_username`。
- Produces: 三處 `create_smb_service(username=session.nas_username or session.username, ...)`。

- [ ] **Step 1: 寫失敗的測試**

在 `tests/test_api_nas_module.py` 末尾加（`_session`／`nas_api` 的命名照該檔既有 helper；若該檔沒有建 SessionData 的 helper，直接照 `test_api_user_routes.py` 的 `_admin_session` 寫一個）：

```python
def test_get_nas_connection_uses_bound_nas_username(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime
    from ching_tech_os.models.auth import SessionData
    import ching_tech_os.api.nas as nas_api

    captured = {}

    def fake_create(username, password, host=None, **_kw):
        captured["username"] = username
        return object()

    monkeypatch.setattr(nas_api, "create_smb_service", fake_create)
    now = datetime.now()
    session = SessionData(
        username="alice", password="pw", nas_host="h", user_id=1,
        created_at=now, expires_at=now, nas_username="nas-a",
    )
    nas_api.get_nas_connection(x_nas_token=None, session=session)
    assert captured["username"] == "nas-a"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd backend && uv run pytest tests/test_api_nas_module.py -k bound_nas_username -v`
Expected: FAIL，`captured["username"] == "alice"`

- [ ] **Step 3: 實作**

三處 fallback 的 `username=session.username` 全改成：

```python
            username=session.nas_username or session.username,
```

- [ ] **Step 4: 跑相關測試**

Run: `cd backend && uv run pytest tests/test_api_nas_module.py tests/test_api_files*.py -q`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/ching_tech_os/api/nas.py backend/src/ching_tech_os/api/files.py backend/tests/test_api_nas_module.py
git commit -m "fix(nas): SMB fallback 改用綁定的 nas_username，平台帳號名稱與 NAS 帳號可不同

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: `/me` 回 nas_username；綁定與解綁端點

**Files:**
- Modify: `backend/src/ching_tech_os/api/user.py:106-141`（`get_current_user`）、`router` 新增兩個端點
- Modify: `backend/src/ching_tech_os/services/user.py:35-58`（`get_user_by_username` SELECT 加 `nas_username`）
- Test: `backend/tests/test_api_user_routes.py`

**Interfaces:**
- Consumes: Task 2 `set_nas_username`；Task 3 `NasBindingRequest`、`NasBindingResponse`；`services.smb.create_smb_service`、`services.workers.run_in_smb_pool`。
- Produces:
  - `GET /api/user/me` 多 `nas_username`。
  - `POST /api/user/me/nas-binding` body `{nas_username, password}` → SMB 驗證失敗 401；被別人綁走 409；成功 `{success: true, nas_username}`。
  - `DELETE /api/user/me/nas-binding` → `{success: true, nas_username: null}`。

- [ ] **Step 1: 寫失敗的測試**

在 `tests/test_api_user_routes.py` 末尾加（`app` fixture 與 `_admin_session` 沿用該檔既有的；若該檔的 app 只掛 `admin_router`，測試裡自行建一個掛 `user_api.router` 的 app）：

```python
def _user_session(user_id: int = 5) -> SessionData:
    now = datetime.now(timezone.utc)
    return SessionData(
        username="alice", password="", nas_host="localhost", user_id=user_id,
        created_at=now, expires_at=now, role="user",
    )


@pytest.fixture
def user_app():
    from ching_tech_os.api.auth import get_current_session
    app = FastAPI()
    app.include_router(user_api.router)
    app.dependency_overrides[get_current_session] = lambda: _user_session()
    return app


@pytest.mark.asyncio
async def test_me_includes_nas_username(user_app, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(user_api, "get_user_by_username", AsyncMock(return_value=_user_row(
        id=5, username="alice", nas_username="nas-a",
    )))
    async with AsyncClient(transport=ASGITransport(app=user_app), base_url="http://t") as c:
        r = await c.get("/api/user/me")
    assert r.status_code == 200 and r.json()["nas_username"] == "nas-a"


@pytest.mark.asyncio
async def test_bind_nas_paths(user_app, monkeypatch: pytest.MonkeyPatch) -> None:
    from ching_tech_os.services.smb import SMBAuthError

    set_nas = AsyncMock()
    monkeypatch.setattr(user_api, "set_nas_username", set_nas)
    monkeypatch.setattr(user_api, "create_smb_service", lambda u, p: object())

    async with AsyncClient(transport=ASGITransport(app=user_app), base_url="http://t") as c:
        # NAS 帳密錯 → 401，不寫入
        monkeypatch.setattr(user_api, "run_in_smb_pool", AsyncMock(side_effect=SMBAuthError("bad")))
        r = await c.post("/api/user/me/nas-binding", json={"nas_username": "nas-a", "password": "x"})
        assert r.status_code == 401
        set_nas.assert_not_called()

        # 驗過 → 寫入
        monkeypatch.setattr(user_api, "run_in_smb_pool", AsyncMock(return_value=None))
        r = await c.post("/api/user/me/nas-binding", json={"nas_username": "nas-a", "password": "x"})
        assert r.status_code == 200 and r.json() == {"success": True, "nas_username": "nas-a"}
        set_nas.assert_awaited_with(5, "nas-a")

        # 被別人綁走 → 409
        monkeypatch.setattr(user_api, "set_nas_username", AsyncMock(side_effect=ValueError("taken")))
        r = await c.post("/api/user/me/nas-binding", json={"nas_username": "nas-a", "password": "x"})
        assert r.status_code == 409

        # 解綁
        unbind = AsyncMock()
        monkeypatch.setattr(user_api, "set_nas_username", unbind)
        r = await c.delete("/api/user/me/nas-binding")
        assert r.status_code == 200 and r.json() == {"success": True, "nas_username": None}
        unbind.assert_awaited_with(5, None)
```

`_user_row` 若不接受 `nas_username` 關鍵字（它用 `**overrides` 更新 dict，應該可以），就直接組 dict。

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd backend && uv run pytest tests/test_api_user_routes.py -k "nas" -v`
Expected: FAIL（404 或 `nas_username` 不在回應）

- [ ] **Step 3: 實作**

`services/user.py` 的 `get_user_by_username` SELECT 欄位加 `nas_username`（照 `get_user_by_id` 的欄位清單加在 `role` 後面）。

`api/user.py` 檔頭 import 加：

```python
from ..models.user import NasBindingRequest, NasBindingResponse
from ..services.user import set_nas_username
from ..services.smb import create_smb_service, SMBAuthError, SMBConnectionError
from ..services.workers import run_in_smb_pool
```

`get_current_user` 的 `UserInfo(...)` 加 `nas_username=user.get("nas_username"),`。

在 `update_current_user` 之後加兩個端點：

```python
@router.post("/me/nas-binding", response_model=NasBindingResponse)
async def bind_nas_account(
    request: NasBindingRequest,
    session: SessionData = Depends(get_current_session),
) -> NasBindingResponse:
    """以 NAS 帳密驗證後，把 NAS 帳號綁到目前登入的平台帳號"""
    smb = create_smb_service(request.nas_username, request.password)
    try:
        await run_in_smb_pool(smb.test_auth)
    except SMBAuthError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="NAS 帳號或密碼錯誤")
    except SMBConnectionError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="無法連線至檔案伺服器")
    try:
        await set_nas_username(session.user_id, request.nas_username)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    # ponytail: 綁定後 session 快取裡的 nas_username 要等重新登入才更新；要即時就在這裡清該 token 的 cache
    return NasBindingResponse(success=True, nas_username=request.nas_username)


@router.delete("/me/nas-binding", response_model=NasBindingResponse)
async def unbind_nas_account(
    session: SessionData = Depends(get_current_session),
) -> NasBindingResponse:
    """解除 NAS 帳號綁定"""
    await set_nas_username(session.user_id, None)
    return NasBindingResponse(success=True, nas_username=None)
```

- [ ] **Step 4: 跑整檔與 user 相關測試**

Run: `cd backend && uv run pytest tests/test_api_user_routes.py tests/test_api_user_module.py tests/test_user_service_smoke.py -q`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/ching_tech_os/api/user.py backend/src/ching_tech_os/services/user.py backend/tests/test_api_user_routes.py
git commit -m "feat(user): /me 回 nas_username；新增 NAS 帳號綁定與解綁端點

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: CORS 追加 origin 的環境變數

**Files:**
- Modify: `backend/src/ching_tech_os/config.py:445-458`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_config_cors.py`（新增）

**Interfaces:**
- Produces: 環境變數 `CORS_EXTRA_ORIGINS`（逗號分隔）內容附加到 `settings.cors_origins`。`main.py` 不用改。

- [ ] **Step 1: 寫失敗的測試**

```python
"""CORS_EXTRA_ORIGINS 解析。"""

import importlib


def test_cors_extra_origins_appended(monkeypatch):
    monkeypatch.setenv("CORS_EXTRA_ORIGINS", "https://os.ching-tech.com, http://localhost:5173 ,")
    import ching_tech_os.config as config
    importlib.reload(config)
    origins = config.settings.cors_origins
    assert "https://os.ching-tech.com" in origins
    assert "http://localhost:5173" in origins
    assert "" not in origins
    assert "http://localhost:8080" in origins  # 原本的沒被蓋掉
    monkeypatch.delenv("CORS_EXTRA_ORIGINS")
    importlib.reload(config)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd backend && uv run pytest tests/test_config_cors.py -v`
Expected: FAIL，`os.ching-tech.com` 不在清單

- [ ] **Step 3: 實作**

`config.py` 那段改成：

```python
    # CORS 設定
    # credentials=True 時不能用 "*"
    # 額外 origin 由 CORS_EXTRA_ORIGINS 逗號分隔追加（新前端 os.ching-tech.com 走這裡）
    cors_origins: list[str] = [
        "http://localhost:8080",
        "http://localhost:8088",
        "http://0.0.0.0:8080",
        "http://0.0.0.0:8088",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8088",
        # MD2PPT/MD2DOC 外部應用程式
        "https://md-2-ppt-evolution.vercel.app",
        "https://md-2-doc-evolution.vercel.app",
    ] + [o.strip() for o in _get_env("CORS_EXTRA_ORIGINS", "").split(",") if o.strip()]
```

`backend/.env.example` 加：

```
# 額外允許的 CORS origin（逗號分隔）。新前端 os.ching-tech.com 與本機 Vite dev server 放這裡
CORS_EXTRA_ORIGINS=https://os.ching-tech.com,http://localhost:5173
```

- [ ] **Step 4: 跑測試**

Run: `cd backend && uv run pytest tests/test_config_cors.py tests/test_api_config_public.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/ching_tech_os/config.py backend/.env.example backend/tests/test_config_cors.py
git commit -m "feat(config): CORS_EXTRA_ORIGINS 追加允許的 origin，給 os.ching-tech.com 用

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: 文件、全套測試、PR

**Files:**
- Modify: `docs/backend.md`（環境變數表、認證段）、`README.md`（近期架構更新）

- [ ] **Step 1: `docs/backend.md`**

環境變數表 `ENABLE_NAS_AUTH` 那列之後加：

```
| CORS_EXTRA_ORIGINS | （空） | 額外允許的 CORS origin，逗號分隔（新前端 os.ching-tech.com） |
```

認證相關段落（搜尋「SMB 認證」）補一段：

```markdown
#### 登入方式（2026-09）

`POST /api/auth/login` 的 `method` 欄位：

- `nas`（預設，舊前端不帶此欄位）：以 NAS 帳密做 SMB 驗證，依 `users.nas_username` 找平台帳號，找不到就自動建立並綁定。session 保留 SMB 密碼供檔案操作。
- `local`：平台帳號密碼，只驗 `password_hash`，不 fallback 到 NAS。session 不存密碼，檔案功能要另外連線 NAS。

平台帳號可在 `POST /api/user/me/nas-binding` 以 NAS 帳密驗證後綁定 NAS 帳號，`DELETE` 解綁。`GET /api/user/me` 回 `nas_username`。
```

- [ ] **Step 2: `README.md`**

「近期架構更新」最上面加一節：

```markdown
### 2026-09

- **雙模式登入**：登入可選 NAS 帳號（SMB 驗證，自動建帳號）或平台帳號（管理員建立、只驗密碼）。平台帳號可綁定 NAS 帳號與 LINE。`users.nas_username` 為綁定欄位。
- **CORS_EXTRA_ORIGINS**：給獨立部署的新前端（os.ching-tech.com）用。
```

- [ ] **Step 3: 全套測試與 coverage**

Run: `cd backend && uv run pytest --cov=src/ching_tech_os --cov-report=term-missing:skip-covered --cov-fail-under=85 -q`
Expected: 全綠，coverage 不低於 85%

- [ ] **Step 4: 舊前端冒煙（本機起後端）**

Run: `cd backend && uv run uvicorn ching_tech_os.main:app --port 8080` 另開終端：

```bash
curl -s -X POST localhost:8080/api/auth/login -H 'content-type: application/json' \
  -d '{"username":"<你的 NAS 帳號>","password":"<密碼>"}' | python3 -m json.tool
```
Expected: `success: true`，且不帶 `method` 走的是 SMB（後端 log 顯示 SMB 認證）。再用瀏覽器開 localhost:8080 舊登入頁登入一次。

- [ ] **Step 5: Commit 與 PR**

```bash
git add docs/backend.md README.md
git commit -m "docs: 雙模式登入與 CORS_EXTRA_ORIGINS 說明

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin HEAD
gh pr create --title "feat(auth): NAS／平台雙模式登入、NAS 帳號綁定、CORS_EXTRA_ORIGINS" --body "..."
gh pr merge --auto --merge
```

PR body 附驗證清單：pytest 全綠與 coverage 數字、alembic upgrade/downgrade 各跑一次、舊前端不帶 method 登入成功、curl `method=local` 對無密碼帳號回失敗。

- [ ] **Step 6: 部署到正式機**

合併後在 .11 跑 `scripts/update-service.sh`（它會跑 `alembic upgrade head`）。`.env` 加 `CORS_EXTRA_ORIGINS=https://os.ching-tech.com,http://localhost:5173`。部署完：

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X OPTIONS https://ching-tech.ddns.net/ctos/api/user/me \
  -H "Origin: https://os.ching-tech.com" -H "Access-Control-Request-Method: GET"
```
Expected: 200，回應標頭含 `access-control-allow-origin: https://os.ching-tech.com`。再用舊桌面登入一次確認不受影響。

---

## 明確不做（本計劃）

- 檔案 API 對未連 NAS 的 session 已回 401 加 `X-NAS-Required` 標頭，前端據此提示即可；不另加 403。
- LINE 綁定沿用現有 `/api/user/binding/*`，不動。
- 前端登入頁的分頁屬 ctos-web 計劃。
- 管理員替別人設定 nas_username：等有需求再加。
