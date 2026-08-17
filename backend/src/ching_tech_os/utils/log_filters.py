"""httpx 日誌過濾:擋掉 Telegram 輪詢雜訊,並遮蔽 URL 裡的 bot token。

**為什麼需要這支**

python-telegram-bot 透過 httpx 長輪詢 `getUpdates`,每 ~30 秒一筆。
2026-08-17 實測近 24 小時:本服務 log 共 2992 行,其中 2851 行(95.3%)
是這個輪詢,而且每一行都把 bot token 明文寫進 /var/log/syslog 與
systemd journal——那兩處 `ct` 讀得到,一旦有人把 log 貼進 issue 或支援單,
token 就跟著出去了。

**為什麼是掛 filter,不是把 httpx 調成 WARNING**

httpx 在本專案有 12 個模組在用(clawhub、skillhub、presentation、
claude_usage、codex_image、media_tools ...)。調等級會連帶失去那些模組的
「打去哪、回什麼碼」紀錄,那是除錯時真正要看的東西。掛 filter 可以只精準
拿掉輪詢雜訊,其餘完整保留。

**範圍限制**

filter 掛在 `httpx` logger 上,只涵蓋 httpx 發出的紀錄。若日後有別的
函式庫也把 token 印出來,需要另外處理(logging 的 filter 不會沿著
propagate 往上套用到子 logger 的紀錄)。
"""

import logging
import re

# Telegram bot token 形如 bot123456789:AAxxxxxxxx-yyyy
_TOKEN_RE = re.compile(r"bot\d+:[A-Za-z0-9_-]+")
_REDACTED = "bot***"

# 長輪詢端點:內容重複且無診斷價值,整筆丟棄
_POLLING_MARKER = "getUpdates"


class TelegramTokenFilter(logging.Filter):
    """丟掉輪詢雜訊,並把其餘紀錄裡的 bot token 遮蔽掉。"""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()

        if _POLLING_MARKER in message:
            return False

        if _TOKEN_RE.search(message):
            # 直接改寫成已格式化的字串,並清掉 args——否則之後再
            # getMessage() 會拿含 % 佔位符的新 msg 去套舊 args 而爆掉
            record.msg = _TOKEN_RE.sub(_REDACTED, message)
            record.args = ()

        return True


def install_log_filters() -> None:
    """把過濾器掛到 httpx logger 上。重複呼叫是安全的。"""
    logger = logging.getLogger("httpx")

    # uvicorn --reload 會重複 import,掛兩次會讓每筆紀錄被過濾兩輪
    if any(isinstance(f, TelegramTokenFilter) for f in logger.filters):
        return

    logger.addFilter(TelegramTokenFilter())
