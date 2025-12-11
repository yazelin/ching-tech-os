"""使用者 API"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..models.auth import SessionData
from ..models.user import UserInfo, UpdateUserRequest
from ..services.user import (
    get_user_by_username,
    update_user_display_name,
    get_user_preferences,
    update_user_preferences,
)
from .auth import get_current_session

router = APIRouter(prefix="/api/user", tags=["user"])


# === 偏好設定相關模型 ===


class PreferencesResponse(BaseModel):
    """偏好設定回應"""

    theme: str = "dark"


class PreferencesUpdateRequest(BaseModel):
    """偏好設定更新請求"""

    theme: str | None = None


class PreferencesUpdateResponse(BaseModel):
    """偏好設定更新回應"""

    success: bool
    preferences: PreferencesResponse


@router.get("/me", response_model=UserInfo)
async def get_current_user(
    session: SessionData = Depends(get_current_session),
) -> UserInfo:
    """取得目前登入使用者的資訊"""
    user = await get_user_by_username(session.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )
    return UserInfo(**user)


@router.patch("/me", response_model=UserInfo)
async def update_current_user(
    request: UpdateUserRequest,
    session: SessionData = Depends(get_current_session),
) -> UserInfo:
    """更新目前登入使用者的資訊"""
    if request.display_name is not None:
        user = await update_user_display_name(session.username, request.display_name)
    else:
        user = await get_user_by_username(session.username)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )
    return UserInfo(**user)


# === 偏好設定 API ===


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    session: SessionData = Depends(get_current_session),
) -> PreferencesResponse:
    """取得使用者偏好設定"""
    if session.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="使用者資料不完整",
        )

    preferences = await get_user_preferences(session.user_id)
    return PreferencesResponse(theme=preferences.get("theme", "dark"))


@router.put("/preferences", response_model=PreferencesUpdateResponse)
async def update_preferences(
    request: PreferencesUpdateRequest,
    session: SessionData = Depends(get_current_session),
) -> PreferencesUpdateResponse:
    """更新使用者偏好設定"""
    if session.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="使用者資料不完整",
        )

    # 只更新有提供的欄位
    update_data = {}
    if request.theme is not None:
        if request.theme not in ("dark", "light"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="無效的主題值，必須為 'dark' 或 'light'",
            )
        update_data["theme"] = request.theme

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未提供任何更新欄位",
        )

    preferences = await update_user_preferences(session.user_id, update_data)
    return PreferencesUpdateResponse(
        success=True,
        preferences=PreferencesResponse(theme=preferences.get("theme", "dark")),
    )
