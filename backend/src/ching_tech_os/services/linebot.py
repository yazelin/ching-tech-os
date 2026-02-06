"""向後相容模組 — 請改用 services.bot_line

此檔案僅用於過渡期，所有功能已遷移至 services/bot_line/ 子模組。
新程式碼請直接 import from services.bot_line。
"""

# Re-export 所有公開 API，保持向後相容
from .bot_line import *  # noqa: F401,F403
