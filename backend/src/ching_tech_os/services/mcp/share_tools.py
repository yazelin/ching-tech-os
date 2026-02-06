"""分享連結相關 MCP 工具

包含：create_share_link, share_knowledge_attachment
"""

from .server import mcp, logger, ensure_db_connection, to_taipei_time
from ...database import get_connection


@mcp.tool()
async def create_share_link(
    resource_type: str,
    resource_id: str,
    expires_in: str | None = "24h",
) -> str:
    """
    建立公開分享連結，讓沒有帳號的人也能查看知識庫或下載檔案

    Args:
        resource_type: 資源類型，可選：
            - knowledge: 知識庫
            - nas_file: NAS 檔案（路徑）
        resource_id: 資源 ID（如 kb-001 或 NAS 檔案路徑）
        expires_in: 有效期限，可選 1h、24h、7d、null（永久），預設 24h

    注意：專案分享功能已遷移至 ERPNext，請直接在 ERPNext 系統操作。
    """
    await ensure_db_connection()

    from ..share import (
        create_share_link as _create_share_link,
        ShareError,
        ResourceNotFoundError,
    )
    from ...models.share import ShareLinkCreate

    # 驗證資源類型（專案相關類型已移除，遷移至 ERPNext）
    valid_types = ("knowledge", "nas_file")
    if resource_type not in valid_types:
        if resource_type in ("project", "project_attachment"):
            return "錯誤：專案分享功能已遷移至 ERPNext，請直接在 ERPNext 系統操作：http://ct.erp"
        return f"錯誤：資源類型必須是 {', '.join(valid_types)}，收到：{resource_type}"

    # 驗證有效期限
    valid_expires = {"1h", "24h", "7d", "null", None}
    if expires_in not in valid_expires:
        return f"錯誤：有效期限必須是 1h、24h、7d 或 null（永久），收到：{expires_in}"

    try:
        data = ShareLinkCreate(
            resource_type=resource_type,
            resource_id=resource_id,
            expires_in=expires_in,
        )
        # 使用 system 作為建立者（Line Bot 代理建立）
        result = await _create_share_link(data, "linebot")

        # 轉換為台北時區顯示
        if result.expires_at:
            expires_taipei = to_taipei_time(result.expires_at)
            expires_text = f"有效至 {expires_taipei.strftime('%Y-%m-%d %H:%M')}"
        else:
            expires_text = "永久有效"

        return f"""分享連結已建立！

📎 連結：{result.full_url}
📄 資源：{result.resource_title}
⏰ {expires_text}

可以直接把連結傳給需要查看的人。"""

    except ResourceNotFoundError as e:
        return f"錯誤：找不到資源 - {e}"
    except ShareError as e:
        return f"錯誤：{e}"
    except Exception as e:
        return f"建立分享連結時發生錯誤：{e}"


@mcp.tool()
async def share_knowledge_attachment(
    kb_id: str,
    attachment_idx: int,
    expires_in: str | None = "24h",
) -> str:
    """
    分享知識庫附件（適用於 .md2ppt 或 .md2doc 檔案）

    此工具會：
    1. 讀取知識庫附件內容
    2. 建立分享連結
    3. 根據檔案類型產生對應的前端 URL

    Args:
        kb_id: 知識庫 ID（如 kb-001）
        attachment_idx: 附件索引（從 0 開始，依照知識庫中的附件順序）
        expires_in: 有效期限，可選 1h、24h、7d、null（永久），預設 24h

    Returns:
        分享連結資訊，包含密碼
    """
    await ensure_db_connection()

    from pathlib import Path
    from ..knowledge import get_knowledge, get_nas_attachment, KnowledgeNotFoundError, KnowledgeError
    from ..share import (
        create_share_link as _create_share_link,
        ShareError,
    )
    from ...models.share import ShareLinkCreate
    from ..path_manager import path_manager, StorageZone

    # 驗證有效期限
    valid_expires = {"1h", "24h", "7d", "null", None}
    if expires_in not in valid_expires:
        return f"錯誤：有效期限必須是 1h、24h、7d 或 null（永久），收到：{expires_in}"

    try:
        # 取得知識庫
        knowledge = get_knowledge(kb_id)

        # 檢查附件索引
        if attachment_idx < 0 or attachment_idx >= len(knowledge.attachments):
            return f"錯誤：附件索引 {attachment_idx} 超出範圍，知識 {kb_id} 共有 {len(knowledge.attachments)} 個附件"

        attachment = knowledge.attachments[attachment_idx]
        attachment_path = attachment.path
        filename = Path(attachment_path).name

        # 判斷檔案類型
        ext = Path(filename).suffix.lower()
        if ext not in (".md2ppt", ".md2doc"):
            return f"錯誤：此工具僅支援 .md2ppt 或 .md2doc 檔案，收到：{filename}"

        # 讀取附件內容
        parsed = path_manager.parse(attachment_path)
        if parsed.zone == StorageZone.CTOS and parsed.path.startswith("knowledge/"):
            # CTOS 區的知識庫檔案
            nas_path = parsed.path.replace("knowledge/", "", 1)
            content = get_nas_attachment(nas_path).decode('utf-8')
        elif parsed.zone == StorageZone.LOCAL:
            # 本機檔案
            from .nas_tools import _get_knowledge_paths
            _, _, assets_path, _ = _get_knowledge_paths()
            file_name_only = parsed.path.split("/")[-1]
            local_path = assets_path / "images" / file_name_only
            content = local_path.read_text(encoding='utf-8')
        else:
            return f"錯誤：不支援的附件路徑格式：{attachment_path}"

        # 建立分享連結（使用 content 類型）
        data = ShareLinkCreate(
            resource_type="content",
            resource_id="",
            content=content,
            content_type="text/markdown",
            filename=filename,
            expires_in=expires_in,
        )
        result = await _create_share_link(data, "linebot")

        # 根據檔案類型產生前端 URL
        from ...config import settings
        if ext == ".md2ppt":
            app_url = f"{settings.md2ppt_url}/?shareToken={result.token}"
            app_name = "MD2PPT"
        else:  # .md2doc
            app_url = f"{settings.md2doc_url}/?shareToken={result.token}"
            app_name = "MD2DOC"

        # 轉換為台北時區顯示
        if result.expires_at:
            expires_taipei = to_taipei_time(result.expires_at)
            expires_text = f"有效至 {expires_taipei.strftime('%Y-%m-%d %H:%M')}"
        else:
            expires_text = "永久有效"

        return f"""已建立 {app_name} 分享連結！

📎 連結：{app_url}
🔑 密碼：{result.password}
📄 檔案：{filename}
⏰ {expires_text}

請將連結和密碼一起傳給需要查看的人。"""

    except KnowledgeNotFoundError as e:
        return f"錯誤：{e}"
    except KnowledgeError as e:
        return f"錯誤：{e}"
    except ShareError as e:
        return f"錯誤：{e}"
    except Exception as e:
        return f"建立分享連結時發生錯誤：{e}"
