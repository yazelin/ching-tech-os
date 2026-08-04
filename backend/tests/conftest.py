"""測試共用 fixtures

提供 mock database、mock Line SDK 等共用設定。
"""

import asyncio
import os
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

# 測試環境固定啟用所有模組，避免測試結果受 .env 的 ENABLED_MODULES 影響
os.environ.setdefault("ENABLED_MODULES", "*")


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


@dataclass(frozen=True)
class ProviderContractSpec:
    """Claude 與未來 Codex provider 共用的測試契約。"""

    claude_request_fields: frozenset[str]
    ai_request_fields: frozenset[str]
    response_fields: frozenset[str]
    routing_metadata_fields: frozenset[str]
    tool_start_fields: frozenset[str]
    tool_end_fields: frozenset[str]
    partial_result_fields: frozenset[str]


@pytest.fixture
def provider_contract_spec() -> ProviderContractSpec:
    """提供 provider contract 的唯一測試定義，供 Claude/Codex 套用同一組斷言。"""
    claude_request_fields = frozenset({
        "prompt",
        "model",
        "history",
        "system_prompt",
        "timeout",
        "tools",
        "tool_call_limits",
        "on_tool_start",
        "on_tool_end",
        "required_mcp_servers",
        "ctos_user_id",
        "extra_mcp_env",
    })
    response_fields = frozenset({
        "success",
        "message",
        "error",
        "tool_calls",
        "input_tokens",
        "output_tokens",
        "tool_timings",
    })
    return ProviderContractSpec(
        claude_request_fields=claude_request_fields,
        ai_request_fields=claude_request_fields | {"routing_context"},
        response_fields=response_fields,
        routing_metadata_fields=frozenset({
            "provider",
            "actual_model",
            "route_reason",
            "provider_started",
            "usage_snapshot",
        }),
        tool_start_fields=frozenset({"tool_call_id", "name", "input"}),
        tool_end_fields=frozenset({
            "tool_call_id",
            "name",
            "status",
            "output",
            "duration_ms",
        }),
        partial_result_fields=response_fields,
    )


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
