"""測試共用 fixtures

提供 mock database、mock Line SDK 等共用設定。
"""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest


# pytest-asyncio 設定
@pytest.fixture(scope="session")
def event_loop():
    """建立共用的 event loop"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================
# Mock 資料
# ============================================================

TEST_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
TEST_USER_UUID = UUID("00000000-0000-0000-0000-000000000010")
TEST_GROUP_UUID = UUID("00000000-0000-0000-0000-000000000020")
TEST_LINE_USER_ID = "U1234567890abcdef"
TEST_LINE_GROUP_ID = "C1234567890abcdef"
TEST_CTOS_USER_ID = 1


@dataclass
class MockToolCall:
    """模擬 Claude tool_call 物件"""
    name: str
    input: dict
    output: str | None


@pytest.fixture
def mock_tool_call():
    """建立 MockToolCall 的工廠函式"""
    def _create(name: str, input_data: dict = None, output: str = None):
        return MockToolCall(name=name, input=input_data or {}, output=output)
    return _create


@pytest.fixture
def mock_db_connection():
    """Mock 資料庫連線"""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()

    class MockContextManager:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, *args):
            pass

    return conn, MockContextManager()
