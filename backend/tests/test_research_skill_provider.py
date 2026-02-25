"""research-skill provider 選擇與 fallback 測試。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest


def _load_start_research_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "src/ching_tech_os/skills/research-skill/scripts/start-research.py"
    )
    spec = importlib.util.spec_from_file_location("ctos_start_research_script", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_provider_prefers_brave_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_start_research_module()
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers["token"] = request.headers.get("X-Subscription-Token", "")
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "title": "Cupola360 Camera",
                            "url": "https://example.com/cupola360",
                            "description": "產品規格與資訊",
                        }
                    ]
                }
            },
        )

    monkeypatch.setattr(module, "_get_brave_api_key", lambda: "brave-test-key")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    results, provider, trace = module._search_with_provider_fallback(client, "cupola360", 5)

    assert provider == "brave"
    assert captured_headers["token"] == "brave-test-key"
    assert results[0]["url"] == "https://example.com/cupola360"
    assert trace[0]["provider"] == "brave"
    assert trace[0]["status"] == "ok"


def test_provider_fallback_to_duckduckgo_when_brave_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_start_research_module()

    monkeypatch.setattr(module, "_get_brave_api_key", lambda: "brave-test-key")
    monkeypatch.setattr(
        module,
        "_search_brave",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("brave down")),
    )
    monkeypatch.setattr(
        module,
        "_search_duckduckgo",
        lambda *_args, **_kwargs: [
            {"title": "DDG result", "url": "https://ddg.example/result", "snippet": "fallback"}
        ],
    )

    results, provider, trace = module._search_with_provider_fallback(None, "cupola360", 5)

    assert provider == "duckduckgo"
    assert results[0]["url"] == "https://ddg.example/result"
    assert trace[0]["provider"] == "brave"
    assert trace[0]["status"] == "failed"
    assert "brave down" in trace[0]["reason"]


def test_provider_fallback_to_duckduckgo_when_brave_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_start_research_module()

    monkeypatch.setattr(module, "_get_brave_api_key", lambda: "")
    monkeypatch.setattr(
        module,
        "_search_duckduckgo",
        lambda *_args, **_kwargs: [
            {"title": "DDG result", "url": "https://ddg.example/result", "snippet": "fallback"}
        ],
    )

    results, provider, trace = module._search_with_provider_fallback(None, "cupola360", 5)

    assert provider == "duckduckgo"
    assert results[0]["url"] == "https://ddg.example/result"
    assert trace[0]["provider"] == "brave"
    assert trace[0]["status"] == "skipped"
    assert trace[0]["reason"] == "missing_api_key"


def test_duckduckgo_retries_with_shorter_query(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_start_research_module()
    calls: list[str] = []

    monkeypatch.setattr(module, "_get_brave_api_key", lambda: "")
    monkeypatch.setattr(
        module,
        "_build_ddg_retry_queries",
        lambda _query: [
            "Cupola360 camera complete product lineup specifications RX1000P RX1000F AST1220",
            "Cupola360 camera RX1000P",
        ],
    )

    def fake_search_ddg(_client, query: str, max_results: int):
        calls.append(query)
        if len(calls) == 1:
            return []
        return [{"title": "DDG retry hit", "url": "https://ddg.example/retry", "snippet": "ok"}]

    monkeypatch.setattr(module, "_search_duckduckgo", fake_search_ddg)

    results, provider, trace = module._search_with_provider_fallback(None, "q", 5)

    assert provider == "duckduckgo"
    assert results[0]["url"] == "https://ddg.example/retry"
    assert calls == [
        "Cupola360 camera complete product lineup specifications RX1000P RX1000F AST1220",
        "Cupola360 camera RX1000P",
    ]
    assert trace[1]["provider"] == "duckduckgo"
    assert trace[1]["status"] == "empty"
    assert trace[1]["attempt"] == 1
    assert trace[2]["status"] == "ok"
    assert trace[2]["attempt"] == 2


def test_build_ddg_retry_queries_generates_compact_variants() -> None:
    module = _load_start_research_module()
    queries = module._build_ddg_retry_queries(
        "Cupola360 camera complete product lineup specifications RX1000P RX1000F AST1220 AST1230 AST1235 RRM software platform ASPEED Technology"
    )
    assert len(queries) >= 2
    assert queries[0].startswith("Cupola360 camera")
    assert len(set(q.lower() for q in queries)) == len(queries)


def test_provider_fallback_to_brave_public_when_ddg_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_start_research_module()

    monkeypatch.setattr(module, "_get_brave_api_key", lambda: "")
    monkeypatch.setattr(module, "_build_ddg_retry_queries", lambda _query: ["q1"])
    monkeypatch.setattr(module, "_search_duckduckgo", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        module,
        "_search_brave_public",
        lambda *_args, **_kwargs: [
            {"title": "Brave Public", "url": "https://cupola360.com", "snippet": ""}
        ],
    )

    results, provider, trace = module._search_with_provider_fallback(None, "cupola360", 5)

    assert provider == "brave_public"
    assert results[0]["url"] == "https://cupola360.com"
    assert any(item.get("provider") == "duckduckgo" and item.get("status") == "empty" for item in trace)
    assert any(item.get("provider") == "brave_public" and item.get("status") == "ok" for item in trace)
