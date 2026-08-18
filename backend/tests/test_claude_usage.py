"""Claude OAuth usage monitor 的資料、安全與生命週期測試。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from ching_tech_os.services import claude_usage


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 4, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.mark.parametrize(
    ("payload", "five_hour", "seven_day", "utilization"),
    [
        (
            {"five_hour": {"utilization": 0.42}, "seven_day": {"utilization": 0.91}},
            0.42,
            0.91,
            0.91,
        ),
        (
            {"five_hour": {"utilization": 42}, "seven_day": {"utilization": 91}},
            0.42,
            0.91,
            0.91,
        ),
        (
            {"five_hour": {"utilization": 0}, "seven_day": {"utilization": 100}},
            0.0,
            1.0,
            1.0,
        ),
        (
            {"five_hour": {"utilization": 1}, "seven_day": {"utilization": 0.5}},
            1.0,
            0.5,
            1.0,
        ),
    ],
)
def test_parse_usage_payload_accepts_ratio_and_percentage(
    payload: dict,
    five_hour: float,
    seven_day: float,
    utilization: float,
) -> None:
    result = claude_usage.parse_usage_payload(payload)

    assert result.five_hour == five_hour
    assert result.seven_day == seven_day
    assert result.utilization == utilization


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"five_hour": {}, "seven_day": {"utilization": 0.5}},
        {"five_hour": {"utilization": "oops"}, "seven_day": {"utilization": 0.5}},
        {"five_hour": {"utilization": True}, "seven_day": {"utilization": 0.5}},
        {"five_hour": {"utilization": -0.1}, "seven_day": {"utilization": 0.5}},
        {"five_hour": {"utilization": 101}, "seven_day": {"utilization": 0.5}},
        {"five_hour": {"utilization": float("nan")}, "seven_day": {"utilization": 0.5}},
        {"five_hour": {"utilization": 0.5}, "seven_day": {"utilization": float("inf")}},
    ],
)
def test_parse_usage_payload_rejects_malformed_or_out_of_range(payload) -> None:
    with pytest.raises(claude_usage.UsagePayloadError):
        claude_usage.parse_usage_payload(payload)


@pytest.mark.asyncio
async def test_monitor_snapshot_transitions_unknown_fresh_stale_error() -> None:
    clock = _Clock()

    async def fetcher() -> dict:
        return {
            "five_hour": {"utilization": 0.25},
            "seven_day": {"utilization": 0.75},
        }

    monitor = claude_usage.ClaudeUsageMonitor(
        fetcher=fetcher,
        clock=clock,
        refresh_ttl_seconds=60,
        max_stale_seconds=300,
    )

    assert monitor.snapshot().state == "unknown"
    fresh = await monitor.refresh()
    assert fresh.state == "fresh"
    assert fresh.fetched_at == clock.now
    assert fresh.last_attempt_at == clock.now
    assert fresh.last_error is None
    assert fresh.consecutive_failures == 0

    clock.advance(61)
    assert monitor.snapshot().state == "stale"

    clock.advance(240)
    expired = monitor.snapshot()
    assert expired.state == "error"
    assert expired.utilization == 0.75


@pytest.mark.asyncio
async def test_monitor_preserves_last_good_snapshot_and_recovers() -> None:
    clock = _Clock()
    results: list[dict | Exception] = [
        {"five_hour": {"utilization": 0.4}, "seven_day": {"utilization": 0.7}},
        claude_usage.UsageRefreshError("network_error"),
        {"five_hour": {"utilization": 0.2}, "seven_day": {"utilization": 0.3}},
    ]

    async def fetcher() -> dict:
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monitor = claude_usage.ClaudeUsageMonitor(
        fetcher=fetcher,
        clock=clock,
        refresh_ttl_seconds=60,
        max_stale_seconds=300,
    )

    first = await monitor.refresh(force=True)
    clock.advance(61)
    failed = await monitor.refresh(force=True)
    assert failed.state == "stale"
    assert failed.utilization == first.utilization == 0.7
    assert failed.last_error == "network_error"
    assert failed.consecutive_failures == 1

    clock.advance(1)
    recovered = await monitor.refresh(force=True)
    assert recovered.state == "fresh"
    assert recovered.utilization == 0.3
    assert recovered.last_error is None
    assert recovered.consecutive_failures == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "category"),
    [
        ({"five_hour": {}, "seven_day": {}}, "invalid_response"),
        (RuntimeError("secret-unexpected-detail"), "unexpected_error"),
    ],
)
async def test_monitor_categorizes_invalid_and_unexpected_fetcher_results(
    result,
    category: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def fetcher() -> dict:
        if isinstance(result, Exception):
            raise result
        return result

    monitor = claude_usage.ClaudeUsageMonitor(fetcher=fetcher)
    caplog.set_level("WARNING", logger=claude_usage.__name__)

    snapshot = await monitor.refresh(force=True)

    assert snapshot.last_error == category
    assert "secret-unexpected-detail" not in caplog.text


@pytest.mark.asyncio
async def test_monitor_refresh_is_single_flight_and_uses_ttl_cache() -> None:
    clock = _Clock()
    started = asyncio.Event()
    release = asyncio.Event()
    call_count = 0

    async def fetcher() -> dict:
        nonlocal call_count
        call_count += 1
        started.set()
        await release.wait()
        return {"five_hour": {"utilization": 0.1}, "seven_day": {"utilization": 0.2}}

    monitor = claude_usage.ClaudeUsageMonitor(
        fetcher=fetcher,
        clock=clock,
        refresh_ttl_seconds=60,
        max_stale_seconds=300,
    )
    tasks = [asyncio.create_task(monitor.refresh()) for _ in range(3)]
    await started.wait()
    release.set()
    snapshots = await asyncio.gather(*tasks)

    assert call_count == 1
    assert {snapshot.utilization for snapshot in snapshots} == {0.2}
    assert (await monitor.refresh()).utilization == 0.2
    assert call_count == 1


class _Response:
    def __init__(self, status_code: int, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _Client:
    def __init__(self, response=None, error: Exception | None = None, **_kwargs) -> None:
        self.response = response
        self.error = error
        self.headers = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, _url: str, *, headers: dict):
        self.headers = headers
        if self.error:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_http_success_refreshes_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    credential = tmp_path / "credentials.json"
    credential.write_text(
        '{"claudeAiOauth": {"accessToken": "success-secret-token"}}',
        encoding="utf-8",
    )
    client = _Client(
        _Response(
            200,
            payload={
                "five_hour": {"utilization": 25},
                "seven_day": {"utilization": 0.8},
            },
        )
    )
    monkeypatch.setattr(claude_usage.httpx, "AsyncClient", lambda **kwargs: client)

    snapshot = await claude_usage.ClaudeUsageMonitor(
        credentials_path=credential
    ).refresh(force=True)

    assert snapshot.state == "fresh"
    assert snapshot.five_hour == 0.25
    assert snapshot.seven_day == 0.8
    assert snapshot.utilization == 0.8


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "category"),
    [(401, "http_401"), (429, "http_429"), (500, "http_5xx")],
)
async def test_http_failures_are_categorized_without_response_body_in_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    caplog: pytest.LogCaptureFixture,
    status_code: int,
    category: str,
) -> None:
    credential = tmp_path / "credentials.json"
    credential.write_text(
        '{"claudeAiOauth": {"accessToken": "super-secret-token"}}',
        encoding="utf-8",
    )
    client = _Client(_Response(status_code, text="secret-response-body"))
    monkeypatch.setattr(claude_usage.httpx, "AsyncClient", lambda **kwargs: client)
    monitor = claude_usage.ClaudeUsageMonitor(credentials_path=credential)
    caplog.set_level("WARNING", logger=claude_usage.__name__)

    snapshot = await monitor.refresh(force=True)

    assert snapshot.state == "error"
    assert snapshot.last_error == category
    assert "secret-response-body" not in caplog.text
    assert "super-secret-token" not in caplog.text
    assert client.headers["Authorization"] == "Bearer super-secret-token"


@pytest.mark.asyncio
async def test_missing_credentials_and_network_error_are_safely_reported(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    missing = claude_usage.ClaudeUsageMonitor(
        credentials_path=tmp_path / "missing.json"
    )
    caplog.set_level("WARNING", logger=claude_usage.__name__)
    snapshot = await missing.refresh(force=True)
    assert snapshot.last_error == "credentials_missing"

    credential = tmp_path / "credentials.json"
    credential.write_text(
        '{"claudeAiOauth": {"accessToken": "another-secret-token"}}',
        encoding="utf-8",
    )
    request = httpx.Request("GET", claude_usage.USAGE_API_URL)
    client = _Client(error=httpx.ReadTimeout("secret-network-detail", request=request))
    monkeypatch.setattr(claude_usage.httpx, "AsyncClient", lambda **kwargs: client)
    network = claude_usage.ClaudeUsageMonitor(credentials_path=credential)

    snapshot = await network.refresh(force=True)

    assert snapshot.last_error == "network_error"
    assert "secret-network-detail" not in caplog.text
    assert "another-secret-token" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("credential_content", "category"),
    [
        ("not-json", "credentials_invalid"),
        ("[]", "credentials_invalid"),
        ("{}", "credentials_token_missing"),
        ('{"claudeAiOauth": {"accessToken": ""}}', "credentials_token_missing"),
    ],
)
async def test_invalid_credentials_are_categorized(
    tmp_path,
    credential_content: str,
    category: str,
) -> None:
    credential = tmp_path / "credentials.json"
    credential.write_text(credential_content, encoding="utf-8")
    monitor = claude_usage.ClaudeUsageMonitor(credentials_path=credential)

    snapshot = await monitor.refresh(force=True)

    assert snapshot.last_error == category


@pytest.mark.asyncio
async def test_unreadable_credentials_are_categorized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    def _raise_permission_error(_self: Path, **_kwargs):
        raise PermissionError("secret-path-detail")

    monkeypatch.setattr(Path, "read_text", _raise_permission_error)
    monitor = claude_usage.ClaudeUsageMonitor(
        credentials_path=tmp_path / "credentials.json"
    )

    snapshot = await monitor.refresh(force=True)

    assert snapshot.last_error == "credentials_unreadable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [ValueError("secret-json-detail"), [], None],
)
async def test_http_200_invalid_json_is_safe_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    caplog: pytest.LogCaptureFixture,
    payload,
) -> None:
    credential = tmp_path / "credentials.json"
    credential.write_text(
        '{"claudeAiOauth": {"accessToken": "secret-json-token"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        claude_usage.httpx,
        "AsyncClient",
        lambda **kwargs: _Client(_Response(200, payload=payload)),
    )
    caplog.set_level("WARNING", logger=claude_usage.__name__)

    snapshot = await claude_usage.ClaudeUsageMonitor(
        credentials_path=credential
    ).refresh(force=True)

    assert snapshot.last_error == "invalid_response"
    assert "secret-json-detail" not in caplog.text
    assert "secret-json-token" not in caplog.text


@pytest.mark.asyncio
async def test_monitor_start_timeout_does_not_block_and_stop_cleans_task() -> None:
    blocker = asyncio.Event()

    async def fetcher() -> dict:
        await blocker.wait()
        return {"five_hour": {"utilization": 0.1}, "seven_day": {"utilization": 0.2}}

    monitor = claude_usage.ClaudeUsageMonitor(
        fetcher=fetcher,
        startup_timeout_seconds=0.01,
        refresh_interval_seconds=3600,
    )

    await monitor.start()
    assert monitor.is_running
    assert monitor.snapshot().last_error == "startup_timeout"

    await monitor.start()
    await asyncio.sleep(0)

    await monitor.stop()
    assert not monitor.is_running
    await monitor.stop()


# ── backoff 與成功後快速恢復(canary 觀察期發現的 429 hammering 改進) ──


def test_next_refresh_delay_backs_off_exponentially() -> None:
    monitor = claude_usage.ClaudeUsageMonitor(refresh_interval_seconds=60)
    # 無失敗 → 正常間隔
    assert monitor._next_refresh_delay() == 60
    # 連續失敗 → 指數退避,上限 1800 秒
    monitor._snapshot = claude_usage.UsageSnapshot(consecutive_failures=1)
    assert monitor._next_refresh_delay() == 120
    monitor._snapshot = claude_usage.UsageSnapshot(consecutive_failures=3)
    assert monitor._next_refresh_delay() == 480
    monitor._snapshot = claude_usage.UsageSnapshot(consecutive_failures=10)
    assert monitor._next_refresh_delay() == 1800
    monitor._snapshot = claude_usage.UsageSnapshot(consecutive_failures=500)
    assert monitor._next_refresh_delay() == 1800


@pytest.mark.asyncio
async def test_nudge_after_success_refreshes_degraded_snapshot() -> None:
    calls = {"count": 0}

    async def fetcher() -> dict:
        calls["count"] += 1
        return {"five_hour": {"utilization": 10}, "seven_day": {"utilization": 20}}

    monitor = claude_usage.ClaudeUsageMonitor(fetcher=fetcher)
    # monitor 未啟動 → no-op
    monitor.nudge_after_success()
    await asyncio.sleep(0)
    assert calls["count"] == 0

    await monitor.start()
    try:
        baseline = calls["count"]
        # 快照 fresh → 不觸發
        monitor.nudge_after_success()
        await asyncio.sleep(0.05)
        assert calls["count"] == baseline

        # 模擬退化(連續失敗)→ nudge 觸發一次 refresh
        monitor._snapshot = claude_usage.UsageSnapshot(consecutive_failures=3)
        monitor.nudge_after_success()
        # 連續 nudge 不會疊加多個 task
        monitor.nudge_after_success()
        await asyncio.sleep(0.05)
        assert calls["count"] == baseline + 1
        assert monitor.snapshot().state == "fresh"
    finally:
        await monitor.stop()
