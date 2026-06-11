"""permissions dependency 測試。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from ching_tech_os.services import permissions


def _request(method: str = "GET") -> SimpleNamespace:
    """checker 只使用 request.method，以 SimpleNamespace 模擬即可"""
    return SimpleNamespace(method=method)


@pytest.mark.asyncio
async def test_require_app_permission_checker(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = permissions.require_app_permission("file-manager")

    admin = SimpleNamespace(role="admin", app_permissions=None, read_only=False)
    assert await checker(request=_request(), session=admin) is admin

    allowed = SimpleNamespace(
        role="user", app_permissions={"file-manager": True}, read_only=False
    )
    assert await checker(request=_request(), session=allowed) is allowed

    monkeypatch.setattr(permissions, "has_app_permission", lambda *_args, **_kwargs: True)
    computed = SimpleNamespace(role="user", app_permissions=None, read_only=False)
    assert await checker(request=_request(), session=computed) is computed

    monkeypatch.setattr(permissions, "has_app_permission", lambda *_args, **_kwargs: False)
    denied = SimpleNamespace(
        role="user", app_permissions={"file-manager": False}, read_only=False
    )
    with pytest.raises(HTTPException) as e:
        await checker(request=_request(), session=denied)
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_require_app_permission_read_only_token() -> None:
    """唯讀 PAT：寫入操作一律 403，讀取放行"""
    checker = permissions.require_app_permission("knowledge-base")

    readonly = SimpleNamespace(
        role="user", app_permissions={"knowledge-base": True}, read_only=True
    )

    # 讀取放行
    assert await checker(request=_request("GET"), session=readonly) is readonly

    # 寫入拒絕
    for method in ("POST", "PUT", "DELETE", "PATCH"):
        with pytest.raises(HTTPException) as e:
            await checker(request=_request(method), session=readonly)
        assert e.value.status_code == 403

    # 非唯讀的 session 寫入不受影響（admin）
    admin = SimpleNamespace(role="admin", app_permissions=None, read_only=False)
    assert await checker(request=_request("POST"), session=admin) is admin
