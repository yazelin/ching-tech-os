"""Coverage step-up 測試

針對低風險核心模組補齊單元測試，支援 coverage 門檻逐步提升。
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ching_tech_os.api import config_public
from ching_tech_os.services import errors
from ching_tech_os.services.hub_meta import read_meta, write_meta
from ching_tech_os.services.workers import thread_pool


@pytest.mark.asyncio
async def test_config_public_health_endpoint() -> None:
    """公開配置 health endpoint 應回傳 ok"""
    app = FastAPI()
    app.include_router(config_public.router)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/config/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_service_error_hierarchy_and_fields() -> None:
    """各 ServiceError 子類別應帶正確 code/status/message"""
    base = errors.ServiceError("boom")
    assert base.message == "boom"
    assert base.code == "INTERNAL_ERROR"
    assert base.status_code == 500
    assert str(base) == "boom"

    not_found = errors.NotFoundError("專案", "P-001")
    assert not_found.code == "NOT_FOUND"
    assert not_found.status_code == 404
    assert not_found.message == "專案 不存在: P-001"

    not_found_no_id = errors.NotFoundError("知識")
    assert not_found_no_id.message == "知識 不存在"

    denied = errors.PermissionDeniedError()
    assert denied.code == "PERMISSION_DENIED"
    assert denied.status_code == 403
    assert denied.message == "權限不足"

    validation = errors.ValidationError("欄位錯誤")
    assert validation.code == "VALIDATION_ERROR"
    assert validation.status_code == 422

    external = errors.ExternalServiceError("NAS", "連線失敗")
    assert external.code == "EXTERNAL_ERROR"
    assert external.status_code == 502
    assert external.message == "NAS: 連線失敗"

    conflict = errors.ConflictError("資料重複")
    assert conflict.code == "CONFLICT"
    assert conflict.status_code == 409


def test_hub_meta_write_and_read(tmp_path) -> None:
    """應可寫入並讀回 _meta.json"""
    write_meta(
        dest=tmp_path,
        slug="demo-skill",
        version="1.2.3",
        source="clawhub",
        owner="ct",
    )

    meta_path = tmp_path / "_meta.json"
    assert meta_path.exists()

    raw = json.loads(meta_path.read_text(encoding="utf-8"))
    assert raw["slug"] == "demo-skill"
    assert raw["version"] == "1.2.3"
    assert raw["source"] == "clawhub"
    assert raw["owner"] == "ct"
    assert "installed_at" in raw

    parsed = read_meta(tmp_path)
    assert parsed is not None
    assert parsed["slug"] == "demo-skill"


def test_hub_meta_read_meta_edge_cases(tmp_path) -> None:
    """不存在或格式錯誤時應回傳 None"""
    assert read_meta(tmp_path / "missing") is None

    broken_dir = tmp_path / "broken"
    broken_dir.mkdir(parents=True, exist_ok=True)
    (broken_dir / "_meta.json").write_text("{broken json", encoding="utf-8")
    assert read_meta(broken_dir) is None


@pytest.mark.asyncio
async def test_thread_pool_run_with_kwargs_and_no_args() -> None:
    """執行緒池 helper 應支援 kwargs 與無參數 callable"""

    def add(a: int, b: int = 0) -> int:
        return a + b

    def ping() -> str:
        return "pong"

    smb_result = await thread_pool.run_in_smb_pool(add, 2, b=3)
    doc_result = await thread_pool.run_in_doc_pool(ping)

    assert smb_result == 5
    assert doc_result == "pong"


def test_thread_pool_shutdown_pools_calls_non_blocking(monkeypatch) -> None:
    """shutdown_pools 應以 wait=False 關閉兩個 pool"""

    class DummyPool:
        def __init__(self) -> None:
            self.wait_values: list[bool] = []

        def shutdown(self, wait: bool = False) -> None:
            self.wait_values.append(wait)

    smb_dummy = DummyPool()
    doc_dummy = DummyPool()
    monkeypatch.setattr(thread_pool, "_smb_pool", smb_dummy)
    monkeypatch.setattr(thread_pool, "_doc_pool", doc_dummy)

    thread_pool.shutdown_pools()

    assert smb_dummy.wait_values == [False]
    assert doc_dummy.wait_values == [False]
