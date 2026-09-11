"""專案模組 API

權限：
- 全部端點先過 require_app_permission("project-management")
- 建立、刪除專案：管理員
- 編輯主檔／成員／里程碑／任務：管理員或該專案成員（require_project_editor）
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..models.auth import SessionData
from ..models.project import (
    MilestoneCreate,
    MilestoneResponse,
    MilestoneUpdate,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectMemberCreate,
    ProjectMemberResponse,
    ProjectSummaryResponse,
    ProjectUpdate,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from ..services import project as project_service
from ..services.permissions import is_project_member, require_app_permission
from .auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])

# 讀取：登入且有 project-management app 權限即可
require_project_access = require_app_permission("project-management")


def _reject_bad_reference(exc: Exception) -> HTTPException:
    """把 service 的外鍵驗證例外翻成 HTTP 錯誤"""
    if isinstance(exc, project_service.UserNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="使用者不存在"
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="里程碑不屬於此專案"
    )


_REFERENCE_ERRORS = (
    project_service.UserNotFoundError,
    project_service.MilestoneNotInProjectError,
)


async def require_project_editor(
    project_id: UUID,
    session: SessionData = Depends(require_project_access),
) -> SessionData:
    """編輯權限：admin 一律過，否則必須是該專案成員"""
    if not await project_service.project_exists(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="專案不存在",
        )
    if session.role == "admin":
        return session
    if await is_project_member(session.user_id, str(project_id)):
        return session
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="只有專案成員能編輯",
    )


# ============================================================
# 專案清單與建立
# ============================================================


@router.get("", response_model=ProjectListResponse, summary="專案清單")
async def list_projects(
    status_filter: str | None = Query(None, alias="status", description="狀態過濾"),
    q: str | None = Query(None, description="名稱／客戶模糊搜尋"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: SessionData = Depends(require_project_access),
) -> ProjectListResponse:
    """專案清單，item 含進度、成員數、逾期里程碑數"""
    result = await project_service.list_projects(
        status=status_filter, q=q, page=page, page_size=page_size
    )
    return ProjectListResponse(**result)


@router.post(
    "",
    response_model=ProjectDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立專案",
)
async def create_project(
    body: ProjectCreate,
    session: SessionData = Depends(require_admin),
    _perm: SessionData = Depends(require_project_access),
) -> ProjectDetailResponse:
    """建立專案（管理員）；有指定負責人時自動加成員"""
    try:
        row = await project_service.create_project(
            body.model_dump(), created_by=session.user_id
        )
    except _REFERENCE_ERRORS as e:
        raise _reject_bad_reference(e)
    detail = await project_service.get_project_detail(row["id"])
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="專案不存在"
        )
    return ProjectDetailResponse(**detail)


# ── /summary 必須宣告在 /{project_id} 之前，否則被吃成 id ──


@router.get("/summary", response_model=ProjectSummaryResponse, summary="dashboard 摘要")
async def get_summary(
    session: SessionData = Depends(require_project_access),
) -> ProjectSummaryResponse:
    """進行中專案數與逾期里程碑清單（依到期日升冪，最多 20 筆）"""
    return ProjectSummaryResponse(**await project_service.get_summary())


# ============================================================
# 專案明細
# ============================================================


@router.get("/{project_id}", response_model=ProjectDetailResponse, summary="專案明細")
async def get_project(
    project_id: UUID,
    session: SessionData = Depends(require_project_access),
) -> ProjectDetailResponse:
    """專案明細：主檔＋進度＋成員＋里程碑＋任務＋綁定群組＋知識條目數"""
    detail = await project_service.get_project_detail(project_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="專案不存在"
        )
    return ProjectDetailResponse(**detail)


@router.put("/{project_id}", response_model=ProjectDetailResponse, summary="更新專案")
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    session: SessionData = Depends(require_project_editor),
) -> ProjectDetailResponse:
    """更新主檔；改 owner_id 時自動補成員"""
    try:
        updated = await project_service.update_project(
            project_id, body.model_dump(exclude_unset=True)
        )
    except _REFERENCE_ERRORS as e:
        raise _reject_bad_reference(e)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="專案不存在"
        )
    detail = await project_service.get_project_detail(project_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="專案不存在"
        )
    return ProjectDetailResponse(**detail)


@router.delete("/{project_id}", summary="刪除專案")
async def delete_project(
    project_id: UUID,
    session: SessionData = Depends(require_admin),
    _perm: SessionData = Depends(require_project_access),
) -> dict:
    """刪除專案（管理員）；先把 bot_groups.project_id 設回 NULL"""
    deleted = await project_service.delete_project(project_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="專案不存在"
        )
    return {"success": True}


# ============================================================
# 成員
# ============================================================


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="加入成員",
)
async def add_member(
    project_id: UUID,
    body: ProjectMemberCreate,
    session: SessionData = Depends(require_project_editor),
) -> ProjectMemberResponse:
    """加入專案成員"""
    member = await project_service.add_member(project_id, body.user_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="使用者不存在"
        )
    return ProjectMemberResponse(**member)


@router.delete("/{project_id}/members/{user_id}", summary="移除成員")
async def remove_member(
    project_id: UUID,
    user_id: int,
    session: SessionData = Depends(require_project_editor),
) -> dict:
    """移除專案成員；負責人不能移除"""
    result = await project_service.remove_member(project_id, user_id)
    if result == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="負責人不能移除"
        )
    if result == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="成員不存在"
        )
    return {"success": True}


# ============================================================
# 里程碑
# ============================================================


@router.post(
    "/{project_id}/milestones",
    response_model=MilestoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立里程碑",
)
async def create_milestone(
    project_id: UUID,
    body: MilestoneCreate,
    session: SessionData = Depends(require_project_editor),
) -> MilestoneResponse:
    """建立里程碑"""
    row = await project_service.create_milestone(project_id, body.model_dump())
    return MilestoneResponse(**row)


@router.put(
    "/{project_id}/milestones/{milestone_id}",
    response_model=MilestoneResponse,
    summary="更新里程碑",
)
async def update_milestone(
    project_id: UUID,
    milestone_id: UUID,
    body: MilestoneUpdate,
    session: SessionData = Depends(require_project_editor),
) -> MilestoneResponse:
    """更新里程碑"""
    row = await project_service.update_milestone(
        project_id, milestone_id, body.model_dump(exclude_unset=True)
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="里程碑不存在"
        )
    return MilestoneResponse(**row)


@router.delete("/{project_id}/milestones/{milestone_id}", summary="刪除里程碑")
async def delete_milestone(
    project_id: UUID,
    milestone_id: UUID,
    session: SessionData = Depends(require_project_editor),
) -> dict:
    """刪除里程碑"""
    if not await project_service.delete_milestone(project_id, milestone_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="里程碑不存在"
        )
    return {"success": True}


# ============================================================
# 任務
# ============================================================


@router.post(
    "/{project_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立任務",
)
async def create_task(
    project_id: UUID,
    body: TaskCreate,
    session: SessionData = Depends(require_project_editor),
) -> TaskResponse:
    """建立任務"""
    try:
        row = await project_service.create_task(project_id, body.model_dump())
    except _REFERENCE_ERRORS as e:
        raise _reject_bad_reference(e)
    return TaskResponse(**row)


@router.put(
    "/{project_id}/tasks/{task_id}",
    response_model=TaskResponse,
    summary="更新任務",
)
async def update_task(
    project_id: UUID,
    task_id: UUID,
    body: TaskUpdate,
    session: SessionData = Depends(require_project_editor),
) -> TaskResponse:
    """更新任務"""
    try:
        row = await project_service.update_task(
            project_id, task_id, body.model_dump(exclude_unset=True)
        )
    except _REFERENCE_ERRORS as e:
        raise _reject_bad_reference(e)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="任務不存在"
        )
    return TaskResponse(**row)


@router.delete("/{project_id}/tasks/{task_id}", summary="刪除任務")
async def delete_task(
    project_id: UUID,
    task_id: UUID,
    session: SessionData = Depends(require_project_editor),
) -> dict:
    """刪除任務"""
    if not await project_service.delete_task(project_id, task_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="任務不存在"
        )
    return {"success": True}
