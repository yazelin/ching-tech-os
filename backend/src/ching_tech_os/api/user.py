"""使用者 API"""

from fastapi import APIRouter, Depends, HTTPException, status

from ..models.auth import SessionData
from ..models.user import UserInfo, UpdateUserRequest
from ..services.user import get_user_by_username, update_user_display_name
from .auth import get_current_session

router = APIRouter(prefix="/api/user", tags=["user"])


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
