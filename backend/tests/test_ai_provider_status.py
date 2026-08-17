"""Provider readiness 與 circuit 狀態輸出測試（6.4）。

狀態輸出只允許安全欄位，不得包含 credentials、token 或原始錯誤內容。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException, status as http_status
from httpx import ASGITransport, AsyncClient

from ching_tech_os.config import settings
from ching_tech_os.services import ai_router as ai_router_service
from ching_tech_os.services.claude_usage import UsageSnapshot, claude_usage_monitor
from ching_tech_os.services.codex_agent import CodexCircuitBreaker, CodexProvider


# ── CodexCircuitBreaker.status() ─────────────────────────────


def test_circuit_status_closed_initially() -> None:
    breaker = CodexCircuitBreaker(3, 60.0)
    assert breaker.status() == {"state": "closed", "consecutive_failures": 0}


def test_circuit_status_open_after_threshold_and_recovers() -> None:
    clock_value = [0.0]
    breaker = CodexCircuitBreaker(2, 10.0, clock=lambda: clock_value[0])
    breaker.record_failure()
    assert breaker.status()["state"] == "closed"
    breaker.record_failure()
    assert breaker.status() == {"state": "open", "consecutive_failures": 2}

    # status() 不得改變 circuit 內部狀態
    assert breaker.status()["state"] == "open"

    clock_value[0] = 11.0
    assert breaker.status()["state"] == "closed"


# ── CodexProvider.status() ───────────────────────────────────


@pytest.mark.asyncio
async def test_codex_provider_status_missing_binaries(tmp_path) -> None:
    provider = CodexProvider(
        adapter_path=str(tmp_path / "missing-acp"),
        codex_path=str(tmp_path / "missing-codex"),
    )
    result = await provider.status()
    assert result["ready"] is False
    assert result["adapter_binary"] is False
    assert result["codex_binary"] is False
    assert result["circuit"]["state"] == "closed"


@pytest.mark.asyncio
async def test_codex_provider_status_ready(tmp_path) -> None:
    adapter = tmp_path / "codex-acp"
    adapter.write_text("#!/bin/sh\n", encoding="utf-8")
    adapter.chmod(0o755)
    codex = tmp_path / "codex"
    codex.write_text("#!/bin/sh\n", encoding="utf-8")
    codex.chmod(0o755)

    provider = CodexProvider(adapter_path=str(adapter), codex_path=str(codex))
    result = await provider.status()
    assert result["ready"] is True
    # 輸出只允許固定的安全欄位
    assert set(result) == {"ready", "adapter_binary", "codex_binary", "circuit"}
    assert set(result["circuit"]) == {"state", "consecutive_failures"}


@pytest.mark.asyncio
async def test_codex_provider_status_circuit_open_blocks_ready(tmp_path) -> None:
    adapter = tmp_path / "codex-acp"
    adapter.write_text("#!/bin/sh\n", encoding="utf-8")
    adapter.chmod(0o755)
    breaker = CodexCircuitBreaker(1, 60.0)
    breaker.record_failure()
    provider = CodexProvider(
        adapter_path=str(adapter), codex_path=str(adapter), circuit_breaker=breaker
    )
    result = await provider.status()
    assert result["ready"] is False
    assert result["circuit"]["state"] == "open"


# ── ai_router.provider_status() ──────────────────────────────


@pytest.mark.asyncio
async def test_router_provider_status_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_codex_status() -> dict:
        return {
            "ready": False,
            "adapter_binary": True,
            "codex_binary": True,
            "circuit": {"state": "open", "consecutive_failures": 3},
        }

    monkeypatch.setattr(
        ai_router_service.codex_provider, "status", fake_codex_status
    )
    monkeypatch.setattr(settings, "ai_provider_mode", "auto")
    monkeypatch.setattr(
        claude_usage_monitor,
        "snapshot",
        lambda: UsageSnapshot(state="fresh", utilization=0.42),
    )

    result = await ai_router_service.provider_status()
    assert result["mode"] == "auto"
    assert result["providers"]["claude"] == {"ready": True}
    assert result["providers"]["codex"]["circuit"]["state"] == "open"
    assert result["usage"]["state"] == "fresh"
    assert result["usage"]["utilization"] == 0.42
    # 不得洩漏 credentials 類欄位
    dumped = json.dumps(result)
    for needle in ("token", "credential", "password", "secret"):
        assert needle not in dumped.lower()


# ── GET /api/ai/providers/status ─────────────────────────────


def _admin_session():
    from ching_tech_os.models.auth import SessionData

    return SessionData(
        username="admin",
        password="xxx",
        nas_host="localhost",
        user_id=1,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
        role="admin",
    )


@pytest.mark.asyncio
async def test_provider_status_endpoint_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    from ching_tech_os.api import ai_management
    from ching_tech_os.api.auth import require_admin

    async def fake_status() -> dict:
        return {"mode": "claude", "providers": {}, "usage": {}}

    monkeypatch.setattr(ai_management.ai_router_service, "provider_status", fake_status)

    app = FastAPI()
    app.include_router(ai_management.router)
    app.dependency_overrides[require_admin] = lambda: _admin_session()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/ai/providers/status")
    assert response.status_code == 200
    assert response.json() == {"mode": "claude", "providers": {}, "usage": {}}


@pytest.mark.asyncio
async def test_provider_status_endpoint_requires_admin() -> None:
    from ching_tech_os.api import ai_management
    from ching_tech_os.api.auth import require_admin

    app = FastAPI()
    app.include_router(ai_management.router)

    async def _deny():
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN, detail="需要管理員權限"
        )

    app.dependency_overrides[require_admin] = _deny

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/ai/providers/status")
    assert response.status_code == 403
