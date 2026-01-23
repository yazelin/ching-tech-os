"""專案管理 API"""

import mimetypes
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from ..models.auth import SessionData
from ..api.auth import get_current_session
from ..services.permissions import require_app_permission
from ching_tech_os.models.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectMemberCreate,
    ProjectMemberUpdate,
    ProjectMemberResponse,
    ProjectMeetingCreate,
    ProjectMeetingUpdate,
    ProjectMeetingResponse,
    ProjectMeetingListItem,
    ProjectAttachmentUpdate,
    ProjectAttachmentResponse,
    ProjectLinkCreate,
    ProjectLinkUpdate,
    ProjectLinkResponse,
    ProjectMilestoneCreate,
    ProjectMilestoneUpdate,
    ProjectMilestoneResponse,
    DeliveryScheduleCreate,
    DeliveryScheduleUpdate,
    DeliveryScheduleResponse,
)
from ching_tech_os.services.project import (
    # 專案
    list_projects,
    get_project,
    create_project,
    update_project,
    delete_project,
    # 成員
    list_members,
    create_member,
    update_member,
    delete_member,
    # 會議
    list_meetings,
    get_meeting,
    create_meeting,
    update_meeting,
    delete_meeting,
    # 附件
    list_attachments,
    upload_attachment,
    get_attachment_content,
    update_attachment,
    delete_attachment,
    # 連結
    list_links,
    create_link,
    update_link,
    delete_link,
    # 里程碑
    list_milestones,
    create_milestone,
    update_milestone,
    delete_milestone,
    # 發包/交貨
    list_deliveries,
    create_delivery,
    update_delivery,
    delete_delivery,
    # 例外
    ProjectError,
    ProjectNotFoundError,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ============================================
# 專案 CRUD
# ============================================


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="列出專案",
)
async def api_list_projects(
    status_filter: str | None = Query(None, alias="status", description="狀態過濾"),
    q: str | None = Query(None, description="關鍵字搜尋"),
    session: SessionData = Depends(require_app_permission("project-management")),
) -> ProjectListResponse:
    """列出專案"""
    try:
        return await list_projects(
            status=status_filter,
            query=q,
            tenant_id=session.tenant_id,
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="取得專案詳情",
)
async def api_get_project(
    project_id: UUID,
    session: SessionData = Depends(require_app_permission("project-management")),
) -> ProjectDetailResponse:
    """取得專案詳情（含成員、會議、附件、連結）"""
    try:
        return await get_project(project_id, tenant_id=session.tenant_id)
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"專案 {project_id} 不存在",
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立專案",
)
async def api_create_project(
    data: ProjectCreate,
    session: SessionData = Depends(require_app_permission("project-management")),
) -> ProjectResponse:
    """建立新專案"""
    try:
        return await create_project(
            data,
            created_by=session.username,
            tenant_id=session.tenant_id,
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="更新專案",
)
async def api_update_project(
    project_id: UUID,
    data: ProjectUpdate,
    session: SessionData = Depends(require_app_permission("project-management")),
) -> ProjectResponse:
    """更新專案"""
    try:
        return await update_project(project_id, data, tenant_id=session.tenant_id)
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"專案 {project_id} 不存在",
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除專案",
)
async def api_delete_project(
    project_id: UUID,
    session: SessionData = Depends(require_app_permission("project-management")),
) -> None:
    """刪除專案（包含所有關聯資料）"""
    try:
        await delete_project(project_id, tenant_id=session.tenant_id)
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"專案 {project_id} 不存在",
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================
# 專案成員
# ============================================


@router.get(
    "/{project_id}/members",
    response_model=list[ProjectMemberResponse],
    summary="列出專案成員",
)
async def api_list_members(project_id: UUID) -> list[ProjectMemberResponse]:
    """列出專案成員"""
    try:
        return await list_members(project_id)
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增專案成員",
)
async def api_create_member(
    project_id: UUID, data: ProjectMemberCreate
) -> ProjectMemberResponse:
    """新增專案成員"""
    try:
        return await create_member(project_id, data)
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"專案 {project_id} 不存在",
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put(
    "/{project_id}/members/{member_id}",
    response_model=ProjectMemberResponse,
    summary="更新專案成員",
)
async def api_update_member(
    project_id: UUID, member_id: UUID, data: ProjectMemberUpdate
) -> ProjectMemberResponse:
    """更新專案成員"""
    try:
        return await update_member(project_id, member_id, data)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{project_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除專案成員",
)
async def api_delete_member(project_id: UUID, member_id: UUID) -> None:
    """刪除專案成員"""
    try:
        await delete_member(project_id, member_id)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================
# 會議記錄
# ============================================


@router.get(
    "/{project_id}/meetings",
    response_model=list[ProjectMeetingListItem],
    summary="列出會議記錄",
)
async def api_list_meetings(project_id: UUID) -> list[ProjectMeetingListItem]:
    """列出會議記錄"""
    try:
        return await list_meetings(project_id)
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/{project_id}/meetings/{meeting_id}",
    response_model=ProjectMeetingResponse,
    summary="取得會議詳情",
)
async def api_get_meeting(project_id: UUID, meeting_id: UUID) -> ProjectMeetingResponse:
    """取得會議詳情"""
    try:
        return await get_meeting(project_id, meeting_id)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{project_id}/meetings",
    response_model=ProjectMeetingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增會議記錄",
)
async def api_create_meeting(
    project_id: UUID, data: ProjectMeetingCreate
) -> ProjectMeetingResponse:
    """新增會議記錄"""
    try:
        return await create_meeting(project_id, data)
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"專案 {project_id} 不存在",
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put(
    "/{project_id}/meetings/{meeting_id}",
    response_model=ProjectMeetingResponse,
    summary="更新會議記錄",
)
async def api_update_meeting(
    project_id: UUID, meeting_id: UUID, data: ProjectMeetingUpdate
) -> ProjectMeetingResponse:
    """更新會議記錄"""
    try:
        return await update_meeting(project_id, meeting_id, data)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{project_id}/meetings/{meeting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除會議記錄",
)
async def api_delete_meeting(project_id: UUID, meeting_id: UUID) -> None:
    """刪除會議記錄"""
    try:
        await delete_meeting(project_id, meeting_id)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================
# 專案附件
# ============================================


@router.get(
    "/{project_id}/attachments",
    response_model=list[ProjectAttachmentResponse],
    summary="列出專案附件",
)
async def api_list_attachments(project_id: UUID) -> list[ProjectAttachmentResponse]:
    """列出專案附件"""
    try:
        return await list_attachments(project_id)
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{project_id}/attachments",
    summary="上傳附件",
)
async def api_upload_attachment(
    project_id: UUID,
    file: UploadFile = File(...),
    description: str | None = Form(None),
) -> dict:
    """上傳附件（<1MB 存本機，>=1MB 存 NAS）"""
    try:
        content = await file.read()
        filename = file.filename or "unnamed"
        attachment = await upload_attachment(project_id, filename, content, description)
        return {
            "success": True,
            "attachment": attachment.model_dump(mode="json"),
        }
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"專案 {project_id} 不存在",
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/{project_id}/attachments/{attachment_id}/download",
    summary="下載附件",
)
async def api_download_attachment(project_id: UUID, attachment_id: UUID) -> Response:
    """下載附件"""
    try:
        content, filename = await get_attachment_content(project_id, attachment_id)
        mime_type, _ = mimetypes.guess_type(filename)
        # 使用 RFC 5987 編碼處理非 ASCII 字元
        safe_filename = quote(filename, safe="")
        return Response(
            content=content,
            media_type=mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}",
            },
        )
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/{project_id}/attachments/{attachment_id}/preview",
    summary="預覽附件",
)
async def api_preview_attachment(project_id: UUID, attachment_id: UUID) -> Response:
    """預覽附件（inline 顯示）"""
    try:
        content, filename = await get_attachment_content(project_id, attachment_id)
        mime_type, _ = mimetypes.guess_type(filename)
        # 使用 RFC 5987 編碼處理非 ASCII 字元
        safe_filename = quote(filename, safe="")
        return Response(
            content=content,
            media_type=mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{safe_filename}",
            },
        )
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.patch(
    "/{project_id}/attachments/{attachment_id}",
    response_model=ProjectAttachmentResponse,
    summary="更新附件資訊",
)
async def api_update_attachment(
    project_id: UUID, attachment_id: UUID, data: ProjectAttachmentUpdate
) -> ProjectAttachmentResponse:
    """更新附件資訊（描述）"""
    try:
        return await update_attachment(project_id, attachment_id, data)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{project_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除附件",
)
async def api_delete_attachment(project_id: UUID, attachment_id: UUID) -> None:
    """刪除附件"""
    try:
        await delete_attachment(project_id, attachment_id)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================
# 專案連結
# ============================================


@router.get(
    "/{project_id}/links",
    response_model=list[ProjectLinkResponse],
    summary="列出專案連結",
)
async def api_list_links(project_id: UUID) -> list[ProjectLinkResponse]:
    """列出專案連結"""
    try:
        return await list_links(project_id)
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{project_id}/links",
    response_model=ProjectLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增專案連結",
)
async def api_create_link(project_id: UUID, data: ProjectLinkCreate) -> ProjectLinkResponse:
    """新增專案連結"""
    try:
        return await create_link(project_id, data)
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"專案 {project_id} 不存在",
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put(
    "/{project_id}/links/{link_id}",
    response_model=ProjectLinkResponse,
    summary="更新專案連結",
)
async def api_update_link(
    project_id: UUID, link_id: UUID, data: ProjectLinkUpdate
) -> ProjectLinkResponse:
    """更新專案連結"""
    try:
        return await update_link(project_id, link_id, data)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{project_id}/links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除專案連結",
)
async def api_delete_link(project_id: UUID, link_id: UUID) -> None:
    """刪除專案連結"""
    try:
        await delete_link(project_id, link_id)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================
# 專案里程碑
# ============================================


@router.get(
    "/{project_id}/milestones",
    response_model=list[ProjectMilestoneResponse],
    summary="列出專案里程碑",
)
async def api_list_milestones(project_id: UUID) -> list[ProjectMilestoneResponse]:
    """列出專案里程碑"""
    try:
        return await list_milestones(project_id)
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{project_id}/milestones",
    response_model=ProjectMilestoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增專案里程碑",
)
async def api_create_milestone(
    project_id: UUID, data: ProjectMilestoneCreate
) -> ProjectMilestoneResponse:
    """新增專案里程碑"""
    try:
        return await create_milestone(project_id, data)
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"專案 {project_id} 不存在",
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put(
    "/{project_id}/milestones/{milestone_id}",
    response_model=ProjectMilestoneResponse,
    summary="更新專案里程碑",
)
async def api_update_milestone(
    project_id: UUID, milestone_id: UUID, data: ProjectMilestoneUpdate
) -> ProjectMilestoneResponse:
    """更新專案里程碑"""
    try:
        return await update_milestone(project_id, milestone_id, data)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{project_id}/milestones/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除專案里程碑",
)
async def api_delete_milestone(project_id: UUID, milestone_id: UUID) -> None:
    """刪除專案里程碑"""
    try:
        await delete_milestone(project_id, milestone_id)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================
# 專案發包/交貨期程
# ============================================


@router.get(
    "/{project_id}/deliveries",
    response_model=list[DeliveryScheduleResponse],
    summary="列出專案發包記錄",
)
async def api_list_deliveries(project_id: UUID) -> list[DeliveryScheduleResponse]:
    """列出專案發包記錄"""
    try:
        return await list_deliveries(project_id)
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{project_id}/deliveries",
    response_model=DeliveryScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增專案發包記錄",
)
async def api_create_delivery(
    project_id: UUID, data: DeliveryScheduleCreate
) -> DeliveryScheduleResponse:
    """新增專案發包記錄"""
    try:
        return await create_delivery(project_id, data)
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"專案 {project_id} 不存在",
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put(
    "/{project_id}/deliveries/{delivery_id}",
    response_model=DeliveryScheduleResponse,
    summary="更新專案發包記錄",
)
async def api_update_delivery(
    project_id: UUID, delivery_id: UUID, data: DeliveryScheduleUpdate
) -> DeliveryScheduleResponse:
    """更新專案發包記錄"""
    try:
        return await update_delivery(project_id, delivery_id, data)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{project_id}/deliveries/{delivery_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除專案發包記錄",
)
async def api_delete_delivery(project_id: UUID, delivery_id: UUID) -> None:
    """刪除專案發包記錄"""
    try:
        await delete_delivery(project_id, delivery_id)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
