"""NAS 檔案相關 MCP 工具

包含：search_nas_files, get_nas_file_info, read_document, send_nas_file, prepare_file_message
"""

import asyncio
from datetime import datetime
from uuid import UUID

from .server import mcp, logger, ensure_db_connection, check_mcp_tool_permission, to_taipei_time, TAIPEI_TZ
from ...database import get_connection

# Line ImageMessage 支援的圖片格式
_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
# Line ImageMessage 限制 10MB
_MAX_IMAGE_SIZE = 10 * 1024 * 1024


def _format_file_size(size_bytes: int) -> str:
    """格式化檔案大小為人類可讀的字串"""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f}MB"
    return f"{size_bytes / 1024:.1f}KB"


def _build_file_message_info(
    file_name: str,
    file_size: int,
    download_url: str,
    fallback_url: str | None = None,
    extra_fields: dict | None = None,
    is_knowledge: bool = False,
) -> tuple[dict, str]:
    """
    建立檔案訊息資訊

    Args:
        file_name: 檔案名稱
        file_size: 檔案大小（bytes）
        download_url: 下載 URL（圖片用）
        fallback_url: 備用 URL（非圖片檔案用，如果為 None 則使用 download_url）
        extra_fields: 額外欄位（如 nas_path, kb_path）
        is_knowledge: 是否為知識庫附件

    Returns:
        (file_info, hint) 元組
    """
    file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    is_image = file_ext in _IMAGE_EXTENSIONS
    size_str = _format_file_size(file_size)
    prefix = "知識庫" if is_knowledge else ""

    if is_image and file_size <= _MAX_IMAGE_SIZE:
        file_info = {
            "type": "image",
            "url": download_url,
            "name": file_name,
        }
        hint = f"已準備好{prefix}圖片 {file_name}，會顯示在回覆中"
    else:
        file_info = {
            "type": "file",
            "url": fallback_url or download_url,
            "download_url": download_url,
            "name": file_name,
            "size": size_str,
        }
        hint = f"已準備好{prefix}檔案 {file_name}（{size_str}），會以連結形式顯示"

    # 加入額外欄位
    if extra_fields:
        file_info.update(extra_fields)

    return file_info, hint


def _get_knowledge_paths():
    """取得知識庫路徑（內部輔助函數）"""
    from ...config import settings
    from pathlib import Path
    base_path = Path(settings.knowledge_data_path)
    entries_path = base_path / "entries"
    assets_path = base_path / "assets"
    index_path = base_path / "index.json"
    return base_path, entries_path, assets_path, index_path


@mcp.tool()
async def search_nas_files(
    keywords: str,
    file_types: str | None = None,
    limit: int = 100,
    ctos_user_id: int | None = None,
) -> str:
    """
    搜尋 NAS 共享檔案

    Args:
        keywords: 搜尋關鍵字，多個關鍵字用逗號分隔（AND 匹配，大小寫不敏感）
        file_types: 檔案類型過濾，多個類型用逗號分隔（如：pdf,xlsx,dwg）
        limit: 最大回傳數量，預設 100
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("search_nas_files", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    # 此工具搜尋的是公司共用區，不是租戶隔離區
    # 公司共用檔案
    from pathlib import Path
    from ...config import settings

    # 搜尋來源定義（shared zone 的子來源）
    # TODO: 未來可依使用者權限過濾可搜尋的來源
    search_sources = {
        "projects": Path(settings.projects_mount_path),
        "circuits": Path(settings.circuits_mount_path),
    }

    # 過濾出實際存在的掛載點
    available_sources = {
        name: path for name, path in search_sources.items() if path.exists()
    }
    if not available_sources:
        return "錯誤：沒有可用的搜尋來源掛載點"

    # 解析關鍵字（大小寫不敏感）
    keyword_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    if not keyword_list:
        return "錯誤：請提供至少一個關鍵字"

    # 解析檔案類型
    type_list = []
    if file_types:
        type_list = [t.strip().lower().lstrip(".") for t in file_types.split(",") if t.strip()]

    # 清理關鍵字中的 find glob 特殊字元（避免非預期匹配）
    import re
    def _sanitize_for_find(s: str) -> str:
        return re.sub(r'[\[\]?*\\]', '', s)
    keyword_list = [_sanitize_for_find(kw) for kw in keyword_list]
    keyword_list = [kw for kw in keyword_list if kw]  # 移除清理後變空的關鍵字
    if not keyword_list:
        return "錯誤：請提供有效的關鍵字"

    # 兩階段搜尋：先淺層找目錄，再深入匹配的目錄搜尋檔案
    # 使用 asyncio subprocess 避免阻塞 event loop
    source_paths = [str(p) for p in available_sources.values()]
    source_name_map = {str(p): name for name, p in available_sources.items()}

    async def _run_find(args: list[str], timeout: int = 30) -> str:
        """非同步執行 find 指令"""
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode("utf-8", errors="replace").strip()
        except (asyncio.TimeoutError, OSError):
            if proc:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            return ""

    async def _find_matching_dirs(max_depth: int) -> list[str]:
        """用 find 在淺層找出名稱匹配任一關鍵字的目錄"""
        # 對每個 source × keyword 平行執行 find
        tasks = []
        for source in source_paths:
            for kw in keyword_list:
                args = ["find", source, "-maxdepth", str(max_depth), "-type", "d", "-iname", f"*{kw}*"]
                tasks.append(_run_find(args, timeout=30))

        results = await asyncio.gather(*tasks)
        dirs = set()
        for output in results:
            for line in output.split("\n"):
                if line:
                    dirs.add(line)
        return sorted(dirs)

    async def _search_in_dirs(dirs: list[str]) -> list[dict]:
        """在指定目錄中用 find 搜尋符合條件的檔案"""
        if not dirs:
            return []

        args = ["find"] + dirs + ["-type", "f"]
        # 關鍵字過濾（所有關鍵字都要匹配路徑）
        for kw in keyword_list:
            args.extend(["-ipath", f"*{kw}*"])
        # 檔案類型過濾
        if type_list:
            args.append("(")
            for i, t in enumerate(type_list):
                if i > 0:
                    args.append("-o")
                args.extend(["-iname", f"*.{t}"])
            args.append(")")

        output = await _run_find(args, timeout=120)
        if not output:
            return []

        files = []
        seen = set()
        for line in output.split("\n"):
            if not line or line in seen:
                continue
            seen.add(line)

            fp = Path(line)
            # 判斷屬於哪個來源
            source_name = None
            source_path = None
            for sp, sn in source_name_map.items():
                if line.startswith(sp):
                    source_name = sn
                    source_path = sp
                    break
            if not source_name:
                continue

            rel_path_str = line[len(source_path):].lstrip("/")

            try:
                stat = fp.stat()
                size = stat.st_size
                modified = datetime.fromtimestamp(stat.st_mtime)
            except OSError:
                size = 0
                modified = None

            files.append({
                "path": f"shared://{source_name}/{rel_path_str}",
                "name": fp.name,
                "size": size,
                "modified": modified,
            })
            if len(files) >= limit:
                break

        return files

    matched_files = []
    try:
        # 階段 1：淺層 2 層目錄匹配
        matched_dirs = await _find_matching_dirs(max_depth=2)
        matched_files = await _search_in_dirs(matched_dirs)

        # 階段 2：沒找到結果，擴展到 3 層
        if not matched_files:
            matched_dirs = await _find_matching_dirs(max_depth=3)
            matched_files = await _search_in_dirs(matched_dirs)

        # 階段 3：仍沒結果，全掃檔名（關鍵字可能只出現在檔名中，不在目錄名）
        if not matched_files:
            matched_files = await _search_in_dirs(source_paths)

    except PermissionError:
        return "錯誤：沒有權限存取檔案系統"
    except Exception as e:
        return f"搜尋時發生錯誤：{str(e)}"

    if not matched_files:
        type_hint = f"（類型：{file_types}）" if file_types else ""
        return f"找不到符合「{keywords}」的檔案{type_hint}"

    # 格式化輸出
    output = [f"找到 {len(matched_files)} 個檔案：\n"]
    for f in matched_files:
        size_str = ""
        if f["size"]:
            if f["size"] >= 1024 * 1024:
                size_str = f" ({f['size'] / 1024 / 1024:.1f} MB)"
            elif f["size"] >= 1024:
                size_str = f" ({f['size'] / 1024:.1f} KB)"

        output.append(f"📄 {f['path']}{size_str}")

    if len(matched_files) >= limit:
        output.append(f"\n（已達上限 {limit} 筆，可能還有更多結果）")

    output.append("\n提示：使用 get_nas_file_info 取得詳細資訊，或 create_share_link 產生下載連結")
    return "\n".join(output)


@mcp.tool()
async def get_nas_file_info(
    file_path: str,
    ctos_user_id: int | None = None,
) -> str:
    """
    取得 NAS 檔案詳細資訊

    Args:
        file_path: 檔案路徑（相對於 /mnt/nas/projects 或完整路徑）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("get_nas_file_info", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    from pathlib import Path
    from ..share import validate_nas_file_path, NasFileNotFoundError, NasFileAccessDenied

    # 統一使用 validate_nas_file_path 進行路徑驗證（支援 shared://projects/...、shared://circuits/... 等）
    try:
        full_path = validate_nas_file_path(file_path)
    except NasFileNotFoundError as e:
        return f"錯誤：{e}"
    except NasFileAccessDenied as e:
        return f"錯誤：{e}"

    # 取得檔案資訊
    try:
        stat = full_path.stat()
        size = stat.st_size
        modified = datetime.fromtimestamp(stat.st_mtime)
    except OSError as e:
        return f"錯誤：無法讀取檔案資訊 - {e}"

    # 格式化大小
    if size >= 1024 * 1024:
        size_str = f"{size / 1024 / 1024:.2f} MB"
    elif size >= 1024:
        size_str = f"{size / 1024:.2f} KB"
    else:
        size_str = f"{size} bytes"

    # 判斷檔案類型
    suffix = full_path.suffix.lower()
    type_map = {
        ".pdf": "PDF 文件",
        ".doc": "Word 文件",
        ".docx": "Word 文件",
        ".xls": "Excel 試算表",
        ".xlsx": "Excel 試算表",
        ".ppt": "PowerPoint 簡報",
        ".pptx": "PowerPoint 簡報",
        ".png": "PNG 圖片",
        ".jpg": "JPEG 圖片",
        ".jpeg": "JPEG 圖片",
        ".gif": "GIF 圖片",
        ".dwg": "AutoCAD 圖檔",
        ".dxf": "AutoCAD 交換檔",
        ".zip": "ZIP 壓縮檔",
        ".rar": "RAR 壓縮檔",
        ".txt": "文字檔",
        ".csv": "CSV 檔案",
    }
    file_type = type_map.get(suffix, f"{suffix} 檔案")

    return f"""📄 **{full_path.name}**

類型：{file_type}
大小：{size_str}
修改時間：{modified.strftime('%Y-%m-%d %H:%M:%S')}
完整路徑：{str(full_path)}

可用操作：
- create_share_link(resource_type="nas_file", resource_id="{str(full_path)}") 產生下載連結
- read_document(file_path="{str(full_path)}") 讀取文件內容（Word/Excel/PowerPoint/PDF）"""


@mcp.tool()
async def read_document(
    file_path: str,
    max_chars: int = 50000,
    ctos_user_id: int | None = None,
) -> str:
    """
    讀取文件內容（支援 Word、Excel、PowerPoint、PDF）

    將文件轉換為純文字，讓 AI 可以分析、總結或查詢內容。

    Args:
        file_path: NAS 檔案路徑（nas:// 格式、相對路徑或完整路徑）
        max_chars: 最大字元數限制，預設 50000
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("read_document", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    # 支援 CTOS zone 和 SHARED zone
    from pathlib import Path
    from ...config import settings
    from .. import document_reader
    from ..path_manager import path_manager, StorageZone

    # 使用 PathManager 解析路徑
    # 支援：nas://..., ctos://..., shared://..., /專案A/..., groups/... 等格式
    try:
        parsed = path_manager.parse(file_path)
    except ValueError as e:
        return f"錯誤：{e}"

    # 取得實際檔案系統路徑
    resolved_path = path_manager.to_filesystem(file_path)
    full_path = Path(resolved_path)

    # 安全檢查：只允許 CTOS 和 SHARED 區域（不允許 TEMP/LOCAL）
    if parsed.zone not in (StorageZone.CTOS, StorageZone.SHARED):
        return f"錯誤：不允許存取 {parsed.zone.value}:// 區域的檔案"

    # 安全檢查：確保路徑在 /mnt/nas/ 下
    nas_path = Path(settings.nas_mount_path)
    try:
        full_path = full_path.resolve()
        resolved_nas = str(nas_path.resolve())
        if not str(full_path).startswith(resolved_nas):
            return "錯誤：不允許存取此路徑"
    except Exception:
        return "錯誤：無效的路徑"

    if not full_path.exists():
        return f"錯誤：檔案不存在 - {file_path}"

    if not full_path.is_file():
        return f"錯誤：路徑不是檔案 - {file_path}"

    # 檢查是否為支援的文件格式
    suffix = full_path.suffix.lower()
    if suffix not in document_reader.SUPPORTED_EXTENSIONS:
        if suffix in document_reader.LEGACY_EXTENSIONS:
            return f"錯誤：不支援舊版格式 {suffix}，請轉存為新版格式（.docx/.xlsx/.pptx）"
        return f"錯誤：不支援的檔案格式 {suffix}。支援的格式：{', '.join(document_reader.SUPPORTED_EXTENSIONS)}"

    # 解析文件
    try:
        from ..workers import run_in_doc_pool
        result = await run_in_doc_pool(document_reader.extract_text, str(full_path))

        # 截斷過長的內容
        text = result.text
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[內容已截斷，原文共 {len(text)} 字元]"

        # 建立回應
        response = f"📄 **{full_path.name}**\n"
        response += f"格式：{result.format.upper()}\n"
        if result.page_count:
            label = "工作表數" if result.format == "xlsx" else "頁數"
            response += f"{label}：{result.page_count}\n"
        if result.truncated:
            response += "⚠️ 內容已截斷\n"
        if result.error:
            response += f"⚠️ 注意：{result.error}\n"
        response += "\n---\n\n"
        response += text

        return response

    except document_reader.FileTooLargeError as e:
        return f"錯誤：{e}"
    except document_reader.PasswordProtectedError:
        return "錯誤：此文件有密碼保護，無法讀取"
    except document_reader.CorruptedFileError as e:
        return f"錯誤：文件損壞 - {e}"
    except document_reader.UnsupportedFormatError as e:
        return f"錯誤：{e}"
    except Exception as e:
        logger.error(f"read_document 錯誤: {e}")
        return f"錯誤：讀取文件失敗 - {e}"


@mcp.tool()
async def send_nas_file(
    file_path: str,
    line_user_id: str | None = None,
    line_group_id: str | None = None,
    telegram_chat_id: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    直接發送 NAS 檔案給用戶。圖片會直接顯示在對話中，其他檔案會發送下載連結。

    Args:
        file_path: NAS 檔案的完整路徑（從 search_nas_files 取得）
        line_user_id: Line 用戶 ID（個人對話時使用，從【對話識別】取得）
        line_group_id: Line 群組的內部 UUID（群組對話時使用，從【對話識別】取得）
        telegram_chat_id: Telegram chat ID（從【對話識別】取得）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）

    注意：
    - 圖片（jpg/jpeg/png/gif/webp）< 10MB 會直接顯示
    - 其他檔案會發送下載連結
    - 必須提供 line_user_id、line_group_id 或 telegram_chat_id 其中之一
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("send_nas_file", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    from pathlib import Path
    from ..share import (
        create_share_link as _create_share_link,
        validate_nas_file_path,
        ShareError,
        NasFileNotFoundError,
        NasFileAccessDenied,
    )
    from ...models.share import ShareLinkCreate

    # 驗證必要參數
    if not line_user_id and not line_group_id and not telegram_chat_id:
        return "錯誤：請從【對話識別】區塊取得 line_user_id、line_group_id 或 telegram_chat_id"

    # 驗證檔案路徑
    try:
        full_path = validate_nas_file_path(file_path)
    except NasFileNotFoundError as e:
        return f"錯誤：{e}"
    except NasFileAccessDenied as e:
        return f"錯誤：{e}"

    # 取得檔案資訊
    file_name = full_path.name
    file_size = full_path.stat().st_size
    file_ext = full_path.suffix.lower().lstrip(".")

    # 判斷是否為圖片
    image_extensions = {"jpg", "jpeg", "png", "gif", "webp"}
    is_image = file_ext in image_extensions

    # 圖片大小限制 10MB
    max_image_size = 10 * 1024 * 1024

    # 產生分享連結
    try:
        data = ShareLinkCreate(
            resource_type="nas_file",
            resource_id=file_path,
            expires_in="24h",
        )
        result = await _create_share_link(data, "linebot")
    except Exception as e:
        return f"建立分享連結失敗：{e}"

    download_url = result.full_url.replace("/s/", "/api/public/") + "/download"
    size_str = f"{file_size / 1024 / 1024:.1f}MB" if file_size >= 1024 * 1024 else f"{file_size / 1024:.1f}KB"

    # === Telegram 發送 ===
    if telegram_chat_id:
        from ..bot_telegram.adapter import TelegramBotAdapter
        from ...config import settings as _settings
        if not _settings.telegram_bot_token:
            return "❌ Telegram Bot 未設定"
        try:
            adapter = TelegramBotAdapter(token=_settings.telegram_bot_token)
            if is_image and file_size <= max_image_size:
                await adapter.send_image(telegram_chat_id, download_url)
                return f"已發送圖片：{file_name}"
            else:
                await adapter.send_file(telegram_chat_id, download_url, file_name)
                return f"已發送檔案：{file_name}（{size_str}）"
        except Exception as e:
            # fallback 到連結
            try:
                await adapter.send_text(
                    telegram_chat_id,
                    f"📎 {file_name}（{size_str}）\n{result.full_url}\n⏰ 連結 24 小時內有效",
                )
                return f"檔案直接發送失敗（{e}），已改發連結：{file_name}"
            except Exception as e2:
                return f"無法直接發送（{e2}），以下是下載連結：\n{result.full_url}\n（24 小時內有效）"

    # === Line 發送 ===
    from ..bot_line import push_image, push_text

    # 決定發送目標（優先使用群組 ID）
    # line_group_id 是內部 UUID，需要轉換為 Line group ID
    target_id = None
    if line_group_id:
        # 查詢 Line group ID
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT platform_group_id FROM bot_groups WHERE id = $1",
                UUID(line_group_id),
            )
            if row:
                target_id = row["platform_group_id"]
            else:
                return f"錯誤：找不到群組 {line_group_id}"
    elif line_user_id:
        target_id = line_user_id

    if not target_id:
        return "錯誤：無法確定發送目標"

    # 發送訊息
    try:
        if is_image and file_size <= max_image_size:
            # 小圖片：直接發送 ImageMessage
            message_id, error = await push_image(target_id, download_url)
            if message_id:
                return f"已發送圖片：{file_name}"
            else:
                # 發送圖片失敗，fallback 到連結
                fallback_msg = f"📎 {file_name}\n{result.full_url}\n⏰ 連結 24 小時內有效"
                fallback_id, fallback_error = await push_text(target_id, fallback_msg)
                if fallback_id:
                    return f"圖片發送失敗（{error}），已改發連結：{file_name}"
                else:
                    return f"無法直接發送（{fallback_error}），以下是下載連結：\n{result.full_url}\n（24 小時內有效）"
        else:
            # 其他檔案或大圖片：發送連結
            message = f"📎 {file_name}（{size_str}）\n{result.full_url}\n⏰ 連結 24 小時內有效"
            message_id, error = await push_text(target_id, message)
            if message_id:
                return f"已發送檔案連結：{file_name}"
            else:
                return f"無法直接發送（{error}），以下是下載連結：\n{result.full_url}\n（24 小時內有效）"
    except Exception as e:
        return f"發送訊息失敗：{e}，連結：{result.full_url}"


@mcp.tool()
async def prepare_file_message(
    file_path: str,
    ctos_user_id: int | None = None,
) -> str:
    """
    準備檔案訊息供 Line Bot 回覆。圖片會直接顯示在回覆中，其他檔案會以連結形式呈現。

    Args:
        file_path: 檔案路徑，支援以下格式：
            - NAS 檔案路徑（從 search_nas_files 取得）
            - 知識庫附件路徑（從 get_knowledge_attachments 取得的 attachment.path）
              例如：local://knowledge/assets/images/kb-001-demo.png
                   ctos://knowledge/attachments/kb-001/file.pdf
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）

    Returns:
        包含檔案訊息標記的字串，系統會自動處理並在回覆中顯示圖片或連結
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("prepare_file_message", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    import json
    import re
    from pathlib import Path
    from urllib.parse import quote
    from ..share import (
        create_share_link as _create_share_link,
        validate_nas_file_path,
        ShareError,
        NasFileNotFoundError,
        NasFileAccessDenied,
    )
    from ..path_manager import path_manager, StorageZone
    from ...models.share import ShareLinkCreate
    from ...config import settings

    # 檢測是否為知識庫附件路徑（local:// 或含有 knowledge 的 ctos://）
    is_knowledge_attachment = (
        file_path.startswith("local://knowledge/") or
        file_path.startswith("ctos://knowledge/") or
        file_path.startswith("nas://knowledge/")
    )

    if is_knowledge_attachment:
        # ===== 知識庫附件處理 =====
        # 使用 path_manager 解析路徑
        try:
            parsed = path_manager.parse(file_path)
            fs_path = Path(path_manager.to_filesystem(file_path))
        except ValueError as e:
            return f"錯誤：無法解析路徑 - {e}"

        if not fs_path.exists():
            return f"錯誤：檔案不存在 - {fs_path.name}"

        # 從檔名或路徑中提取 kb_id
        # 本機附件格式：local://knowledge/assets/images/{kb_id}-{filename}
        # NAS 附件格式：ctos://knowledge/attachments/{kb_id}/{filename}
        file_name = fs_path.name
        kb_id = None

        if parsed.zone == StorageZone.LOCAL:
            # 本機附件：從檔名提取 kb_id（格式：{kb_id}-{filename}）
            match = re.match(r"^(kb-\d+)-", file_name)
            if match:
                kb_id = match.group(1)
        else:
            # NAS 附件：從路徑提取 kb_id（格式：knowledge/attachments/{kb_id}/...）
            path_match = re.search(r"knowledge/attachments/(kb-\d+)/", parsed.path)
            if path_match:
                kb_id = path_match.group(1)

        if not kb_id:
            return f"錯誤：無法從路徑中識別知識庫 ID - {file_path}"

        # 取得檔案資訊
        file_size = fs_path.stat().st_size

        # 為知識文章建立分享連結
        try:
            data = ShareLinkCreate(
                resource_type="knowledge",
                resource_id=kb_id,
                expires_in="24h",
            )
            result = await _create_share_link(data, "linebot")
        except Exception as e:
            return f"建立分享連結失敗：{e}"

        # 組合附件下載 URL
        # 格式：/api/public/{token}/attachments/{encoded_path}
        encoded_path = quote(file_path, safe="")
        download_url = f"{settings.public_url}/api/public/{result.token}/attachments/{encoded_path}"

        # 使用輔助函式組合檔案訊息
        file_info, hint = _build_file_message_info(
            file_name=file_name,
            file_size=file_size,
            download_url=download_url,
            extra_fields={"kb_path": file_path},
            is_knowledge=True,
        )

    else:
        # ===== NAS 檔案處理 =====
        # 驗證檔案路徑
        try:
            full_path = validate_nas_file_path(file_path)
        except NasFileNotFoundError as e:
            return f"錯誤：{e}"
        except NasFileAccessDenied as e:
            return f"錯誤：{e}"

        # 取得檔案資訊
        file_name = full_path.name
        file_size = full_path.stat().st_size

        # 產生分享連結
        try:
            data = ShareLinkCreate(
                resource_type="nas_file",
                resource_id=file_path,
                expires_in="24h",
            )
            result = await _create_share_link(data, "linebot")
        except Exception as e:
            return f"建立分享連結失敗：{e}"

        # 下載連結需要加上 /download（圖片用）
        download_url = result.full_url.replace("/s/", "/api/public/") + "/download"

        # 計算相對於 linebot_local_path 的路徑（用於存 bot_files）
        linebot_base = settings.linebot_local_path
        full_path_str = str(full_path)
        if full_path_str.startswith(linebot_base):
            relative_nas_path = full_path_str[len(linebot_base):].lstrip("/")
        else:
            relative_nas_path = full_path_str  # 其他路徑保持原樣

        # 使用輔助函式組合檔案訊息
        file_info, hint = _build_file_message_info(
            file_name=file_name,
            file_size=file_size,
            download_url=download_url,
            fallback_url=result.full_url,  # 非圖片檔案使用分享連結頁面
            extra_fields={"nas_path": relative_nas_path},
            is_knowledge=False,
        )

    # 回傳標記（linebot_ai.py 會解析這個標記）
    marker = f"[FILE_MESSAGE:{json.dumps(file_info, ensure_ascii=False)}]"

    return f"{hint}\n{marker}"
