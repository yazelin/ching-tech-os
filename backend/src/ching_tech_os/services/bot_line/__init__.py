"""Line Bot 平台實作

將 Line Messaging API 的操作封裝為子模組，
同時保留 Line 專屬功能（群組管理、綁定、NAS 路徑等）。

子模組：
- adapter: LineBotAdapter（實作 BotAdapter Protocol）
- client: Line API 客戶端
- webhook: Webhook 簽章驗證
- user_manager: 用戶管理
- group_manager: 群組管理
- message_store: 訊息儲存
- messaging: 訊息發送
- file_handler: 檔案處理
- trigger: AI 觸發判斷與對話管理
- binding: 用戶綁定與存取控制
- admin: 管理查詢功能
- memory: 記憶管理
- constants: 常數定義
"""

# === constants ===
from .constants import (
    FILE_TYPE_EXTENSIONS,
    MIME_TO_EXTENSION,
    MENTION_KEY,
    MENTION_PLACEHOLDER,
)

# === client ===
from .client import (
    get_line_config,
    get_webhook_parser,
    get_messaging_api,
)

# === webhook ===
from .webhook import (
    verify_signature,
    verify_webhook_signature,
)

# === user_manager ===
from .user_manager import (
    get_line_user_record,
    get_or_create_user,
    update_user_friend_status,
    get_user_profile,
    get_group_member_profile,
)

# === group_manager ===
from .group_manager import (
    get_or_create_group,
    get_group_profile,
    handle_join_event,
    handle_leave_event,
    get_line_group_external_id,
)

# === message_store ===
from .message_store import (
    save_message,
    mark_message_ai_processed,
    get_or_create_bot_user,
    save_bot_response,
    get_message_content_by_line_message_id,
)

# === messaging ===
from .messaging import (
    reply_text,
    create_text_message_with_mention,
    reply_messages,
    push_text,
    push_image,
    push_messages,
)

# === file_handler ===
from .file_handler import (
    save_file_record,
    download_and_save_file,
    download_line_content,
    generate_nas_path,
    guess_mime_type,
    save_to_nas,
    read_file_from_nas,
    delete_file,
    list_files,
    get_file_by_id,
    get_temp_image_path,
    ensure_temp_image,
    get_image_info_by_line_message_id,
    get_temp_file_path,
    ensure_temp_file,
    get_file_info_by_line_message_id,
    # Re-export from bot.media
    is_readable_file,
    is_legacy_office_file,
    is_document_file,
    MAX_READABLE_FILE_SIZE,
    TEMP_IMAGE_DIR,
    TEMP_FILE_DIR,
    READABLE_FILE_EXTENSIONS,
    LEGACY_OFFICE_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
)

# === trigger ===
from .trigger import (
    should_trigger_ai,
    is_bot_message,
    reset_conversation,
    is_reset_command,
)

# === binding ===
from .binding import (
    generate_binding_code,
    verify_binding_code,
    unbind_line_user,
    get_binding_status,
    is_binding_code_format,
    check_line_access,
)

# === admin ===
from .admin import (
    list_groups,
    list_messages,
    list_users,
    get_group_by_id,
    get_user_by_id,
    bind_group_to_project,
    unbind_group_from_project,
    delete_group,
    update_group_settings,
    list_users_with_binding,
)

# === memory ===
from .memory import (
    list_group_memories,
    list_user_memories,
    create_group_memory,
    create_user_memory,
    update_memory,
    delete_memory,
    get_line_user_by_ctos_user,
    get_active_group_memories,
    get_active_user_memories,
)

__all__ = [
    # constants
    "FILE_TYPE_EXTENSIONS",
    "MIME_TO_EXTENSION",
    "MENTION_KEY",
    "MENTION_PLACEHOLDER",
    # client
    "get_line_config",
    "get_webhook_parser",
    "get_messaging_api",
    # webhook
    "verify_signature",
    "verify_webhook_signature",
    # user_manager
    "get_line_user_record",
    "get_or_create_user",
    "update_user_friend_status",
    "get_user_profile",
    "get_group_member_profile",
    # group_manager
    "get_or_create_group",
    "get_group_profile",
    "handle_join_event",
    "handle_leave_event",
    "get_line_group_external_id",
    # message_store
    "save_message",
    "mark_message_ai_processed",
    "get_or_create_bot_user",
    "save_bot_response",
    "get_message_content_by_line_message_id",
    # messaging
    "reply_text",
    "create_text_message_with_mention",
    "reply_messages",
    "push_text",
    "push_image",
    "push_messages",
    # file_handler
    "save_file_record",
    "download_and_save_file",
    "download_line_content",
    "generate_nas_path",
    "guess_mime_type",
    "save_to_nas",
    "read_file_from_nas",
    "delete_file",
    "list_files",
    "get_file_by_id",
    "get_temp_image_path",
    "ensure_temp_image",
    "get_image_info_by_line_message_id",
    "get_temp_file_path",
    "ensure_temp_file",
    "get_file_info_by_line_message_id",
    "is_readable_file",
    "is_legacy_office_file",
    "is_document_file",
    "MAX_READABLE_FILE_SIZE",
    "TEMP_IMAGE_DIR",
    "TEMP_FILE_DIR",
    "READABLE_FILE_EXTENSIONS",
    "LEGACY_OFFICE_EXTENSIONS",
    "DOCUMENT_EXTENSIONS",
    # trigger
    "should_trigger_ai",
    "is_bot_message",
    "reset_conversation",
    "is_reset_command",
    # binding
    "generate_binding_code",
    "verify_binding_code",
    "unbind_line_user",
    "get_binding_status",
    "is_binding_code_format",
    "check_line_access",
    # admin
    "list_groups",
    "list_messages",
    "list_users",
    "get_group_by_id",
    "get_user_by_id",
    "bind_group_to_project",
    "unbind_group_from_project",
    "delete_group",
    "update_group_settings",
    "list_users_with_binding",
    # memory
    "list_group_memories",
    "list_user_memories",
    "create_group_memory",
    "create_user_memory",
    "update_memory",
    "delete_memory",
    "get_line_user_by_ctos_user",
    "get_active_group_memories",
    "get_active_user_memories",
]
