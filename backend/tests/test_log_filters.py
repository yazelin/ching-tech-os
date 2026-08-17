"""httpx 日誌過濾器測試。

為什麼要有這支:bot token 會跟著 httpx 的 request log 明文進 /var/log/syslog
與 systemd journal。過濾器一旦壞掉是「安靜地壞」——log 看起來正常,token 卻在外面,
所以遮蔽行為必須有測試釘住。
"""

import logging

import pytest

from ching_tech_os.utils.log_filters import (
    TelegramTokenFilter,
    install_log_filters,
)

TOKEN = "8294724422:AAFpygE0ijqqpdzhz5TGPvUf8HdJsN6Xxh8"


def _record(msg: str, *args) -> logging.LogRecord:
    return logging.LogRecord(
        name="httpx", level=logging.INFO, pathname=__file__,
        lineno=1, msg=msg, args=args, exc_info=None,
    )


class TestTelegramTokenFilter:
    def test_丟掉_getUpdates_輪詢雜訊(self):
        """長輪詢每 30 秒一筆、內容重複,佔 log 量 95%,直接丟。"""
        rec = _record(
            f'HTTP Request: POST https://api.telegram.org/bot{TOKEN}/getUpdates "HTTP/1.1 200 OK"'
        )
        assert TelegramTokenFilter().filter(rec) is False

    def test_其他_telegram_請求保留但遮蔽_token(self):
        """sendMessage 這類是有診斷價值的,要留下來,但 token 得遮掉。"""
        rec = _record(
            f'HTTP Request: POST https://api.telegram.org/bot{TOKEN}/sendMessage "HTTP/1.1 200 OK"'
        )
        assert TelegramTokenFilter().filter(rec) is True
        out = rec.getMessage()
        assert TOKEN not in out
        assert "bot***" in out
        # 其餘資訊(打去哪、回什麼碼)必須完整保留,否則就失去除錯價值
        assert "sendMessage" in out
        assert "200 OK" in out

    def test_無關的請求原封不動(self):
        """clawhub / skillhub / codex_image 等模組的紀錄不能被動到。"""
        msg = 'HTTP Request: GET https://clawhub.example/api/v1/items "HTTP/1.1 200 OK"'
        rec = _record(msg)
        assert TelegramTokenFilter().filter(rec) is True
        assert rec.getMessage() == msg

    def test_token_夾在_args_裡也要遮掉(self):
        """logger.info("%s", url) 這種寫法,token 在 args 不在 msg。"""
        rec = _record("HTTP Request: %s", f"https://api.telegram.org/bot{TOKEN}/sendPhoto")
        assert TelegramTokenFilter().filter(rec) is True
        assert TOKEN not in rec.getMessage()
        assert "bot***" in rec.getMessage()

    def test_遮蔽後仍可安全格式化(self):
        """遮蔽時若沒清掉 args,後續 getMessage() 會炸 TypeError。"""
        rec = _record("HTTP Request: %s", f"https://api.telegram.org/bot{TOKEN}/sendPhoto")
        TelegramTokenFilter().filter(rec)
        rec.getMessage()  # 再叫一次不能爆
        rec.getMessage()


class TestInstall:
    @pytest.fixture(autouse=True)
    def _清掉_httpx_logger_上的_filter(self):
        logger = logging.getLogger("httpx")
        before = list(logger.filters)
        logger.filters.clear()
        yield
        logger.filters[:] = before

    def test_掛上去之後_httpx_logger_有過濾器(self):
        install_log_filters()
        logger = logging.getLogger("httpx")
        assert any(isinstance(f, TelegramTokenFilter) for f in logger.filters)

    def test_重複呼叫不會重複掛(self):
        """uvicorn --reload 會重複 import,掛兩次會讓每筆紀錄被過濾兩輪。"""
        install_log_filters()
        install_log_filters()
        logger = logging.getLogger("httpx")
        assert sum(isinstance(f, TelegramTokenFilter) for f in logger.filters) == 1
