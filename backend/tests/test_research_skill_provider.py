"""research-skill provider 搜尋與並行合併測試。"""

from __future__ import annotations

import importlib.util
import json
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


def test_provider_includes_brave_api_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """Brave API 有 key 時應回傳結果。"""
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
    # 讓 brave_public 不回傳結果，確認 brave API 結果有被納入
    monkeypatch.setattr(module, "_search_brave_public", lambda *_a, **_kw: [])
    client = httpx.Client(transport=httpx.MockTransport(handler))
    results, provider, trace = module._search_with_provider_fallback(client, "cupola360", 5)

    assert "brave" in provider
    assert captured_headers["token"] == "brave-test-key"
    assert any(r["url"] == "https://example.com/cupola360" for r in results)
    assert any(t["provider"] == "brave" and t["status"] == "ok" for t in trace)


def test_provider_brave_public_used_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """沒有 Brave API key 時，應使用 Brave Public。"""
    module = _load_start_research_module()

    monkeypatch.setattr(module, "_get_brave_api_key", lambda: "")
    monkeypatch.setattr(
        module,
        "_search_brave_public",
        lambda *_a, **_kw: [
            {"title": "Brave Public Result", "url": "https://cupola360.com", "snippet": ""}
        ],
    )

    results, provider, trace = module._search_with_provider_fallback(None, "cupola360", 5)

    assert "brave_public" in provider
    assert results[0]["url"] == "https://cupola360.com"
    assert any(t["provider"] == "brave" and t["status"] == "skipped" for t in trace)
    assert any(t["provider"] == "brave_public" and t["status"] == "ok" for t in trace)


def test_provider_merges_brave_api_and_public(monkeypatch: pytest.MonkeyPatch) -> None:
    """Brave API 和 Public 都有結果時，應合併去重。"""
    module = _load_start_research_module()

    monkeypatch.setattr(module, "_get_brave_api_key", lambda: "brave-test-key")
    monkeypatch.setattr(
        module,
        "_search_brave",
        lambda *_a, **_kw: [
            {"title": "API Result", "url": "https://example.com/a", "snippet": "from api"},
        ],
    )
    monkeypatch.setattr(
        module,
        "_search_brave_public",
        lambda *_a, **_kw: [
            {"title": "Public Result", "url": "https://example.com/b", "snippet": "from public"},
            # 與 API 重複的 URL，應被去重
            {"title": "API Result Dup", "url": "https://example.com/a", "snippet": "dup"},
        ],
    )

    results, provider, trace = module._search_with_provider_fallback(None, "cupola360", 10)

    assert "brave+brave_public" == provider
    urls = [r["url"] for r in results]
    assert "https://example.com/a" in urls
    assert "https://example.com/b" in urls
    # 去重後應只有 2 個
    assert len(results) == 2


def test_provider_returns_none_when_all_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """所有 provider 都失敗時回傳空結果。"""
    module = _load_start_research_module()

    monkeypatch.setattr(module, "_get_brave_api_key", lambda: "brave-test-key")
    monkeypatch.setattr(
        module,
        "_search_brave",
        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("brave down")),
    )
    monkeypatch.setattr(
        module,
        "_search_brave_public",
        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("public down")),
    )

    results, provider, trace = module._search_with_provider_fallback(None, "cupola360", 5)

    assert results == []
    assert provider == "none"
    assert any(t["provider"] == "brave" and t["status"] == "failed" for t in trace)
    assert any(t["provider"] == "brave_public" and t["status"] == "failed" for t in trace)


def test_provider_brave_public_retries_with_shorter_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """Brave Public 在第一個查詢失敗時會嘗試縮短的查詢。"""
    module = _load_start_research_module()
    calls: list[str] = []

    monkeypatch.setattr(module, "_get_brave_api_key", lambda: "")
    monkeypatch.setattr(
        module,
        "_build_retry_queries",
        lambda _query: ["very long query that fails", "short query"],
    )

    def fake_brave_public(_client, query: str, max_results: int):
        calls.append(query)
        if len(calls) == 1:
            return []
        return [{"title": "Retry hit", "url": "https://example.com/retry", "snippet": "ok"}]

    monkeypatch.setattr(module, "_search_brave_public", fake_brave_public)

    results, provider, trace = module._search_with_provider_fallback(None, "q", 5)

    assert "brave_public" in provider
    assert results[0]["url"] == "https://example.com/retry"
    assert len(calls) == 2


def test_build_retry_queries_generates_compact_variants() -> None:
    """_build_retry_queries 應產生多個查詢變體。"""
    module = _load_start_research_module()
    queries = module._build_retry_queries(
        "Cupola360 camera complete product lineup specifications RX1000P RX1000F AST1220 AST1230 AST1235 RRM software platform ASPEED Technology"
    )
    assert len(queries) >= 2
    assert queries[0].startswith("Cupola360 camera")
    assert len(set(q.lower() for q in queries)) == len(queries)


def test_provider_returns_none_for_empty_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """空白查詢應直接回傳空結果。"""
    module = _load_start_research_module()
    monkeypatch.setattr(module, "_get_brave_api_key", lambda: "")

    results, provider, trace = module._search_with_provider_fallback(None, "   ", 5)

    assert results == []
    assert provider == "none"
    assert any(t["status"] == "skipped" for t in trace)


def test_get_research_claude_timeout_sec_respects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_start_research_module()

    monkeypatch.setenv("RESEARCH_CLAUDE_TIMEOUT_SEC", "1500")
    assert module._get_research_claude_timeout_sec() == 1500

    monkeypatch.setenv("RESEARCH_CLAUDE_TIMEOUT_SEC", "99999")
    assert module._get_research_claude_timeout_sec() == 3600

    monkeypatch.setenv("RESEARCH_CLAUDE_TIMEOUT_SEC", "30")
    assert module._get_research_claude_timeout_sec() == 120


def test_get_research_claude_model_respects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_start_research_module()

    monkeypatch.setenv("RESEARCH_CLAUDE_MODEL", "claude-opus")
    assert module._get_research_claude_model() == "claude-opus"

    monkeypatch.setenv("RESEARCH_CLAUDE_MODEL", "claude-sonnet")
    assert module._get_research_claude_model() == "claude-sonnet"


def test_cleanup_old_research_dirs_removes_expired(tmp_path: Path) -> None:
    module = _load_start_research_module()

    old_dir = tmp_path / "2020-01-01" / "abcd1234"
    old_dir.mkdir(parents=True)
    (old_dir / "status.json").write_text("{}", encoding="utf-8")

    today_dir = tmp_path / module.datetime.now().strftime("%Y-%m-%d") / "efgh5678"
    today_dir.mkdir(parents=True)
    (today_dir / "status.json").write_text("{}", encoding="utf-8")

    module._cleanup_old_research_dirs(tmp_path, retention_days=7)

    assert not (tmp_path / "2020-01-01").exists()
    assert today_dir.exists()


def test_do_research_fallback_to_local_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_start_research_module()
    job_id = "abcd1234"
    date_dir = tmp_path / module.datetime.now().strftime("%Y-%m-%d")
    job_dir = date_dir / job_id
    job_dir.mkdir(parents=True)
    status_path = job_dir / "status.json"
    status_path.write_text(json.dumps({"job_id": job_id, "status": "queued"}), encoding="utf-8")

    monkeypatch.setattr(module, "_wait_for_worker_slot", lambda **_kwargs: None)
    monkeypatch.setattr(
        module,
        "_run_claude_research",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("claude down")),
    )

    captured_trace: list[dict] = []

    def fake_local(**kwargs):
        captured_trace.extend(kwargs.get("pre_provider_trace") or [])
        module._write_status(
            kwargs["status_path"],
            {
                "job_id": kwargs["job_id"],
                "status": "completed",
                "status_label": "完成",
                "progress": 100,
            },
        )

    monkeypatch.setattr(module, "_do_research_local_pipeline", fake_local)

    module._do_research(
        base_dir=tmp_path,
        job_dir=job_dir,
        status_path=status_path,
        job_id=job_id,
        query="test query",
        seed_urls=[],
        max_results=3,
        max_fetch=2,
    )

    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["status"] == "completed"
    assert captured_trace
    assert captured_trace[0]["provider"] == "claude_webtools"
    assert captured_trace[0]["status"] == "failed"


def test_do_research_claude_success_writes_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_start_research_module()
    job_id = "abcd1234"
    date_dir = tmp_path / module.datetime.now().strftime("%Y-%m-%d")
    job_dir = date_dir / job_id
    job_dir.mkdir(parents=True)
    status_path = job_dir / "status.json"
    status_path.write_text(json.dumps({"job_id": job_id, "status": "queued"}), encoding="utf-8")

    monkeypatch.setattr(module, "_wait_for_worker_slot", lambda **_kwargs: None)
    monkeypatch.setattr(
        module,
        "_run_claude_research",
        lambda **_kwargs: (
            "這是研究摘要",
            [{"title": "Example", "url": "https://example.com", "snippet": "snippet"}],
            [{"tool": "WebSearch", "input": {"query": "x"}, "output_preview": "ok"}],
        ),
    )

    module._do_research(
        base_dir=tmp_path,
        job_dir=job_dir,
        status_path=status_path,
        job_id=job_id,
        query="test query",
        seed_urls=[],
        max_results=3,
        max_fetch=2,
    )

    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["status"] == "completed"
    assert status["search_provider"] == "claude_webtools"
    assert (job_dir / "result.md").exists()
    assert (job_dir / "sources.json").exists()
    assert (job_dir / "tool_trace.json").exists()
