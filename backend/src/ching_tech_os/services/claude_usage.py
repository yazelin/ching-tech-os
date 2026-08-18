"""Claude OAuth 用量快照與背景刷新服務。

Router 只讀取記憶體快照；credentials 與 HTTP 都不在使用者請求路徑執行。
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

USAGE_API_URL = "https://api.anthropic.com/api/oauth/usage"
# 連續失敗退避上限（秒）；避免 token 過期時整夜以固定頻率撞 401/429
_MAX_BACKOFF_SECONDS = 1800.0
_ANTHROPIC_BETA = "claude-code-20250219"
_USER_AGENT = "claude-code/0.2.29"

UsageState = Literal["unknown", "fresh", "stale", "error"]


class UsagePayloadError(ValueError):
    """Usage API payload 格式錯誤。"""


class UsageRefreshError(RuntimeError):
    """不包含 credentials 或 response body 的安全錯誤分類。"""


@dataclass(frozen=True)
class UsageValues:
    """已正規化為 0–1 的 usage 數值。"""

    five_hour: float
    seven_day: float
    utilization: float


@dataclass(frozen=True)
class UsageSnapshot:
    """Router 可安全讀取的 Claude 用量快照。"""

    state: UsageState = "unknown"
    utilization: float | None = None
    five_hour: float | None = None
    seven_day: float | None = None
    fetched_at: datetime | None = None
    last_attempt_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0

    def as_metadata(self) -> dict[str, Any]:
        """轉成不含 credentials 的 response metadata。"""
        return {
            "state": self.state,
            "utilization": self.utilization,
            "five_hour": self.five_hour,
            "seven_day": self.seven_day,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "last_attempt_at": (
                self.last_attempt_at.isoformat() if self.last_attempt_at else None
            ),
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
        }


def _normalize_utilization(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UsagePayloadError("utilization 必須是數字")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0 or numeric > 100:
        raise UsagePayloadError("utilization 超出 0–100 範圍")
    return numeric / 100 if numeric > 1 else numeric


def parse_usage_payload(payload: Any) -> UsageValues:
    """解析 5h/7d payload，並相容 0–1 與 0–100 格式。"""
    if not isinstance(payload, dict):
        raise UsagePayloadError("usage payload 必須是物件")
    try:
        five_hour_raw = payload["five_hour"]["utilization"]
        seven_day_raw = payload["seven_day"]["utilization"]
    except (KeyError, TypeError) as exc:
        raise UsagePayloadError("usage payload 缺少必要欄位") from exc

    five_hour = _normalize_utilization(five_hour_raw)
    seven_day = _normalize_utilization(seven_day_raw)
    return UsageValues(
        five_hour=five_hour,
        seven_day=seven_day,
        utilization=max(five_hour, seven_day),
    )


class ClaudeUsageMonitor:
    """以 single-flight 刷新並保存 Claude OAuth 用量。"""

    def __init__(
        self,
        *,
        credentials_path: str | Path | None = None,
        refresh_ttl_seconds: float | None = None,
        max_stale_seconds: float | None = None,
        refresh_interval_seconds: float | None = None,
        http_timeout_seconds: float | None = None,
        startup_timeout_seconds: float | None = None,
        fetcher: Callable[[], Awaitable[dict]] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.credentials_path = Path(
            credentials_path or settings.claude_usage_credentials_path
        ).expanduser()
        self.refresh_ttl_seconds = float(
            refresh_ttl_seconds
            if refresh_ttl_seconds is not None
            else settings.claude_usage_refresh_ttl_seconds
        )
        self.max_stale_seconds = float(
            max_stale_seconds
            if max_stale_seconds is not None
            else settings.claude_usage_max_stale_seconds
        )
        self.refresh_interval_seconds = float(
            refresh_interval_seconds
            if refresh_interval_seconds is not None
            else settings.claude_usage_refresh_interval_seconds
        )
        self.http_timeout_seconds = float(
            http_timeout_seconds
            if http_timeout_seconds is not None
            else settings.claude_usage_http_timeout_seconds
        )
        self.startup_timeout_seconds = float(
            startup_timeout_seconds
            if startup_timeout_seconds is not None
            else settings.claude_usage_startup_timeout_seconds
        )
        self._clock = clock or (lambda: datetime.now(UTC))
        self._fetcher = fetcher or self._fetch_payload
        self._snapshot = UsageSnapshot()
        self._refresh_lock = asyncio.Lock()
        self._background_task: asyncio.Task | None = None
        self._nudge_task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._background_task and not self._background_task.done())

    def _age_seconds(self, now: datetime) -> float | None:
        if self._snapshot.fetched_at is None:
            return None
        return max(0.0, (now - self._snapshot.fetched_at).total_seconds())

    def snapshot(self) -> UsageSnapshot:
        """依目前時間計算 fresh/stale/error，不觸發 I/O。"""
        now = self._clock()
        age = self._age_seconds(now)
        if age is None:
            state: UsageState = (
                "error" if self._snapshot.last_attempt_at is not None else "unknown"
            )
        elif age <= self.refresh_ttl_seconds:
            state = "fresh"
        elif age <= self.max_stale_seconds:
            state = "stale"
        else:
            state = "error"
        return replace(self._snapshot, state=state)

    def _cache_is_fresh(self) -> bool:
        return self.snapshot().state == "fresh"

    def _record_failure(self, category: str, attempted_at: datetime) -> UsageSnapshot:
        self._snapshot = replace(
            self._snapshot,
            last_attempt_at=attempted_at,
            last_error=category,
            consecutive_failures=self._snapshot.consecutive_failures + 1,
        )
        safe_snapshot = self.snapshot()
        logger.warning(
            "Claude usage refresh 失敗: category=%s failures=%d",
            category,
            safe_snapshot.consecutive_failures,
        )
        return safe_snapshot

    async def refresh(self, *, force: bool = False) -> UsageSnapshot:
        """刷新快照；同時間只允許一個外部請求。"""
        if not force and self._cache_is_fresh():
            return self.snapshot()

        async with self._refresh_lock:
            if not force and self._cache_is_fresh():
                return self.snapshot()
            attempted_at = self._clock()
            try:
                payload = await self._fetcher()
                values = parse_usage_payload(payload)
            except asyncio.CancelledError:
                raise
            except UsageRefreshError as exc:
                return self._record_failure(str(exc), attempted_at)
            except UsagePayloadError:
                return self._record_failure("invalid_response", attempted_at)
            except Exception:
                return self._record_failure("unexpected_error", attempted_at)

            self._snapshot = UsageSnapshot(
                state="fresh",
                utilization=values.utilization,
                five_hour=values.five_hour,
                seven_day=values.seven_day,
                fetched_at=attempted_at,
                last_attempt_at=attempted_at,
            )
            logger.info(
                "Claude usage refresh 成功: 5h=%.1f%% 7d=%.1f%% max=%.1f%%",
                values.five_hour * 100,
                values.seven_day * 100,
                values.utilization * 100,
            )
            return self.snapshot()

    def _load_access_token(self) -> str:
        try:
            raw = self.credentials_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise UsageRefreshError("credentials_missing") from exc
        except OSError as exc:
            raise UsageRefreshError("credentials_unreadable") from exc
        try:
            credentials = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise UsageRefreshError("credentials_invalid") from exc
        if not isinstance(credentials, dict):
            raise UsageRefreshError("credentials_invalid")
        oauth = credentials.get("claudeAiOauth")
        if not isinstance(oauth, dict):
            oauth = {}
        token = oauth.get("accessToken")
        if not isinstance(token, str) or not token.strip():
            raise UsageRefreshError("credentials_token_missing")
        return token.strip()

    async def _fetch_payload(self) -> dict:
        token = self._load_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "anthropic-beta": _ANTHROPIC_BETA,
            "User-Agent": _USER_AGENT,
        }
        try:
            async with httpx.AsyncClient(timeout=self.http_timeout_seconds) as client:
                response = await client.get(USAGE_API_URL, headers=headers)
        except httpx.RequestError as exc:
            raise UsageRefreshError("network_error") from exc

        if response.status_code != 200:
            category = (
                "http_5xx" if response.status_code >= 500 else f"http_{response.status_code}"
            )
            raise UsageRefreshError(category)
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise UsageRefreshError("invalid_response") from exc
        if not isinstance(payload, dict):
            raise UsageRefreshError("invalid_response")
        return payload

    def _next_refresh_delay(self) -> float:
        """連續失敗時指數退避，避免以固定頻率去撞 401/429（上限 30 分鐘）。"""
        failures = self._snapshot.consecutive_failures
        if failures <= 0:
            return self.refresh_interval_seconds
        return min(
            self.refresh_interval_seconds * (2 ** min(failures, 10)),
            _MAX_BACKOFF_SECONDS,
        )

    def nudge_after_success(self) -> None:
        """真實 AI 請求成功後呼叫：快照已退化時非同步觸發一次 refresh。

        AI 請求成功代表 CLI 剛刷新過 OAuth token，此時 refresh 幾乎必然成功，
        不必等退避後的下一個週期。不阻塞 caller、single-flight、fresh 時 no-op。
        """
        if not self.is_running:
            return
        degraded = (
            self.snapshot().state != "fresh"
            or self._snapshot.consecutive_failures > 0
        )
        if not degraded:
            return
        if self._nudge_task and not self._nudge_task.done():
            return
        self._nudge_task = asyncio.create_task(
            self.refresh(force=True),
            name="claude-usage-nudge",
        )

    async def _refresh_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._next_refresh_delay())
                await self.refresh(force=True)
        except asyncio.CancelledError:
            raise

    async def start(self) -> None:
        """短 timeout 初次刷新；任何失敗都不阻止服務啟動。"""
        if self.is_running:
            return
        try:
            await asyncio.wait_for(
                self.refresh(force=True),
                timeout=self.startup_timeout_seconds,
            )
        except TimeoutError:
            self._record_failure("startup_timeout", self._clock())
        self._background_task = asyncio.create_task(
            self._refresh_loop(),
            name="claude-usage-monitor",
        )

    async def stop(self) -> None:
        task = self._background_task
        self._background_task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


claude_usage_monitor = ClaudeUsageMonitor()
