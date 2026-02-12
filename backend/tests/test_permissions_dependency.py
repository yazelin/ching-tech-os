"""permissions dependency 測試。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from ching_tech_os.services import permissions


@pytest.mark.asyncio
async def test_require_app_permission_checker(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = permissions.require_app_permission("file-manager")

    admin = SimpleNamespace(role="admin", app_permissions=None)
    assert await checker(session=admin) is admin

    allowed = SimpleNamespace(role="user", app_permissions={"file-manager": True})
    assert await checker(session=allowed) is allowed

    monkeypatch.setattr(permissions, "has_app_permission", lambda *_args, **_kwargs: True)
    computed = SimpleNamespace(role="user", app_permissions=None)
    assert await checker(session=computed) is computed

    monkeypatch.setattr(permissions, "has_app_permission", lambda *_args, **_kwargs: False)
    denied = SimpleNamespace(role="user", app_permissions={"file-manager": False})
    with pytest.raises(HTTPException) as e:
        await checker(session=denied)
    assert e.value.status_code == 403
