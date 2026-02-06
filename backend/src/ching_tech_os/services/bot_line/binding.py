"""Line Bot 用戶綁定與存取控制"""

import logging
import random
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from ...database import get_connection

logger = logging.getLogger("linebot")


async def generate_binding_code(
    user_id: int,
    platform_type: str = "line",
) -> tuple[str, datetime]:
    """
    產生 6 位數字綁定驗證碼

    Args:
        user_id: CTOS 用戶 ID
        platform_type: 平台類型（line, telegram）

    Returns:
        (驗證碼, 過期時間)
    """
    # 產生 6 位數字驗證碼
    code = f"{random.randint(0, 999999):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    async with get_connection() as conn:
        # 清除該用戶之前未使用的驗證碼
        await conn.execute(
            """
            DELETE FROM bot_binding_codes
            WHERE user_id = $1 AND used_at IS NULL
            """,
            user_id,
        )

        # 建立新驗證碼
        await conn.execute(
            """
            INSERT INTO bot_binding_codes (user_id, code, expires_at, platform_type)
            VALUES ($1, $2, $3, $4)
            """,
            user_id,
            code,
            expires_at,
            platform_type,
        )

    logger.info(f"已產生綁定驗證碼: user_id={user_id}")
    return code, expires_at


async def verify_binding_code(
    line_user_uuid: UUID,
    code: str,
) -> tuple[bool, str]:
    """
    驗證綁定驗證碼並完成綁定

    Args:
        line_user_uuid: Line 用戶內部 UUID
        code: 驗證碼

    Returns:
        (是否成功, 訊息)
    """
    async with get_connection() as conn:
        # 查詢驗證碼
        code_row = await conn.fetchrow(
            """
            SELECT id, user_id
            FROM bot_binding_codes
            WHERE code = $1
              AND used_at IS NULL
              AND expires_at > NOW()
            """,
            code,
        )

        if not code_row:
            return False, "驗證碼無效或已過期"

        code_id = code_row["id"]
        ctos_user_id = code_row["user_id"]

        # 取得 Line 用戶的 platform_user_id 和 platform_type
        line_user_row = await conn.fetchrow(
            "SELECT platform_user_id, display_name, platform_type FROM bot_users WHERE id = $1",
            line_user_uuid,
        )
        if not line_user_row:
            return False, "找不到 Line 用戶記錄"

        user_platform_type = line_user_row["platform_type"] or "line"

        # 檢查此 Line 用戶是否已綁定其他 CTOS 帳號
        if await conn.fetchrow(
            "SELECT id FROM bot_users WHERE id = $1 AND user_id IS NOT NULL",
            line_user_uuid,
        ):
            existing_user = await conn.fetchrow(
                "SELECT user_id FROM bot_users WHERE id = $1",
                line_user_uuid,
            )
            if existing_user and existing_user["user_id"] != ctos_user_id:
                return False, "此 Line 帳號已綁定其他 CTOS 帳號"

        # 檢查該 CTOS 用戶是否已綁定同平台的其他帳號
        existing_line = await conn.fetchrow(
            """
            SELECT id FROM bot_users
            WHERE user_id = $1 AND platform_type = $2 AND id != $3
            """,
            ctos_user_id,
            user_platform_type,
            line_user_uuid,
        )
        if existing_line:
            platform_label = "Telegram" if user_platform_type == "telegram" else "Line"
            return False, f"此 CTOS 帳號已綁定其他 {platform_label} 帳號"

        # 執行綁定
        await conn.execute(
            """
            UPDATE bot_users
            SET user_id = $2, updated_at = NOW()
            WHERE id = $1
            """,
            line_user_uuid,
            ctos_user_id,
        )

        # 標記驗證碼已使用
        await conn.execute(
            """
            UPDATE bot_binding_codes
            SET used_at = NOW(), used_by_bot_user_id = $2
            WHERE id = $1
            """,
            code_id,
            line_user_uuid,
        )

        logger.info(f"綁定成功: line_user={line_user_uuid}, ctos_user={ctos_user_id}")
        return True, "綁定成功！您現在可以使用 Line Bot 了。"


async def unbind_line_user(
    user_id: int,
    platform_type: str | None = None,
) -> bool:
    """
    解除 CTOS 用戶的平台綁定

    Args:
        user_id: CTOS 用戶 ID
        platform_type: 平台類型（line/telegram），None 表示解除所有平台

    Returns:
        是否成功解除綁定
    """
    async with get_connection() as conn:
        if platform_type:
            result = await conn.execute(
                """
                UPDATE bot_users
                SET user_id = NULL, updated_at = NOW()
                WHERE user_id = $1 AND platform_type = $2
                """,
                user_id,
                platform_type,
            )
        else:
            result = await conn.execute(
                """
                UPDATE bot_users
                SET user_id = NULL, updated_at = NOW()
                WHERE user_id = $1
                """,
                user_id,
            )
        # asyncpg execute 回傳格式如 "UPDATE 1"，取最後的數字
        match = re.search(r"(\d+)$", result or "")
        affected = int(match.group(1)) if match else 0
        if affected > 0:
            platform_label = platform_type or "all"
            logger.info(f"已解除綁定: ctos_user={user_id}, platform={platform_label}")
            return True
        return False


async def get_binding_status(
    user_id: int,
) -> dict:
    """
    取得 CTOS 用戶的多平台綁定狀態

    Args:
        user_id: CTOS 用戶 ID

    Returns:
        多平台綁定狀態資訊（包含 line 和 telegram）
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT lu.platform_type, lu.display_name, lu.picture_url,
                   bc.used_at as bound_at
            FROM bot_users lu
            LEFT JOIN bot_binding_codes bc ON bc.used_by_bot_user_id = lu.id
            WHERE lu.user_id = $1
            ORDER BY lu.platform_type, bc.used_at DESC NULLS LAST
            """,
            user_id,
        )

        # 建立各平台的綁定狀態
        platforms = {}
        for row in rows:
            pt = row["platform_type"] or "line"
            if pt not in platforms:
                platforms[pt] = {
                    "is_bound": True,
                    "display_name": row["display_name"],
                    "picture_url": row["picture_url"],
                    "bound_at": row["bound_at"],
                }

        def _platform_status(pt: str) -> dict:
            if pt in platforms:
                return platforms[pt]
            return {
                "is_bound": False,
                "display_name": None,
                "picture_url": None,
                "bound_at": None,
            }

        line_status = _platform_status("line")
        telegram_status = _platform_status("telegram")

        # 保持向後相容：is_bound 為任一平台已綁定
        return {
            "is_bound": line_status["is_bound"] or telegram_status["is_bound"],
            "line_display_name": line_status["display_name"],
            "line_picture_url": line_status["picture_url"],
            "bound_at": line_status["bound_at"],
            # 多平台擴充
            "line": line_status,
            "telegram": telegram_status,
        }


async def is_binding_code_format(content: str) -> bool:
    """
    檢查內容是否為驗證碼格式（6 位數字）

    Args:
        content: 訊息內容

    Returns:
        是否為驗證碼格式
    """
    return content.isdigit() and len(content) == 6


async def check_line_access(
    line_user_uuid: UUID,
    line_group_uuid: UUID | None = None,
) -> tuple[bool, str | None]:
    """
    檢查 Line 用戶是否有權限使用 Bot

    規則：
    1. Line 用戶必須綁定 CTOS 帳號
    2. 如果是群組訊息，群組必須設為 allow_ai_response = true

    Args:
        line_user_uuid: Line 用戶內部 UUID
        line_group_uuid: Line 群組內部 UUID（個人對話為 None）

    Returns:
        (是否有權限, 拒絕原因)
    """
    async with get_connection() as conn:
        # 檢查用戶綁定
        user_row = await conn.fetchrow(
            "SELECT user_id FROM bot_users WHERE id = $1",
            line_user_uuid,
        )

        if not user_row or not user_row["user_id"]:
            return False, "user_not_bound"

        # 如果是群組，檢查群組設定
        if line_group_uuid:
            group_row = await conn.fetchrow(
                "SELECT allow_ai_response FROM bot_groups WHERE id = $1",
                line_group_uuid,
            )
            if not group_row or not group_row["allow_ai_response"]:
                return False, "group_not_allowed"

        return True, None
