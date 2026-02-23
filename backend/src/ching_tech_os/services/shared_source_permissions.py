"""shared:// 子來源權限輔助函數。"""

from __future__ import annotations

import json

from ..database import get_connection

SHARED_SOURCE_ACCESS_DENIED_MESSAGE = "權限不足：無法存取此 shared 來源"


class SharedSourceAccessDeniedError(ValueError):
    """當存取 shared 來源權限不足時拋出的例外。"""

    def __init__(self, message: str = SHARED_SOURCE_ACCESS_DENIED_MESSAGE):
        super().__init__(message)


def _normalize_preferences(raw_preferences: dict | str | None) -> dict:
    """正規化使用者 preferences。"""
    if raw_preferences is None:
        return {}
    if isinstance(raw_preferences, dict):
        return raw_preferences
    if isinstance(raw_preferences, str):
        try:
            parsed = json.loads(raw_preferences)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _extract_shared_source_permissions(preferences: dict | None) -> dict[str, bool] | None:
    """從 preferences 提取 shared 子來源權限設定。"""
    if not isinstance(preferences, dict):
        return None

    permissions = preferences.get("permissions")
    if not isinstance(permissions, dict):
        return None

    # 新格式：permissions.shared_sources.{source}=bool
    shared_sources = permissions.get("shared_sources")
    if isinstance(shared_sources, dict):
        return {str(k): bool(v) for k, v in shared_sources.items()}

    # 舊格式相容：permissions.shared.{source}=bool
    legacy_shared = permissions.get("shared")
    if isinstance(legacy_shared, dict):
        return {str(k): bool(v) for k, v in legacy_shared.items()}

    return None


def filter_shared_mounts_by_permissions(
    shared_mounts: dict[str, str],
    source_permissions: dict[str, bool] | None,
) -> dict[str, str]:
    """依來源權限過濾 shared 掛載點。"""
    if source_permissions is None:
        from .permissions import DEFAULT_SHARED_SOURCE_PERMISSIONS
        source_permissions = DEFAULT_SHARED_SOURCE_PERMISSIONS
    return {
        source: mount_path
        for source, mount_path in shared_mounts.items()
        if source_permissions.get(source, False)
    }


def resolve_shared_source_mount(
    shared_mounts: dict[str, str],
    source_name: str,
    source_permissions: dict[str, bool] | None = None,
) -> str:
    """解析並驗證 shared 子來源掛載點。"""
    if source_name not in shared_mounts:
        raise ValueError(f"未知的 shared 子來源：{source_name}")

    allowed_mounts = filter_shared_mounts_by_permissions(shared_mounts, source_permissions)
    if source_name not in allowed_mounts:
        raise SharedSourceAccessDeniedError()

    return shared_mounts[source_name]


async def get_allowed_shared_mounts_for_user(
    shared_mounts: dict[str, str],
    ctos_user_id: int | None,
) -> dict[str, str]:
    """依使用者設定取得可用的 shared 掛載點。"""
    if ctos_user_id is None:
        return {}

    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT role, preferences FROM users WHERE id = $1",
            ctos_user_id,
        )

    if not row:
        return {}

    if (row["role"] or "user") == "admin":
        return dict(shared_mounts)

    preferences = _normalize_preferences(row["preferences"])
    source_permissions = _extract_shared_source_permissions(preferences)
    return filter_shared_mounts_by_permissions(shared_mounts, source_permissions)
