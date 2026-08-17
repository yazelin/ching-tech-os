"""Codex ACP provider。

此模組只在 Router 已選定 Codex 後啟動 subprocess。所有工具權限均以
``mcp__server__tool`` canonical identity 精確比對，任何不完整事件都拒絕。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from acp.schema import EnvVariable

from ..config import settings
from .ai_provider import AIResponse, DEFAULT_TIMEOUT, ToolCall, ToolNotifyCallback
from .claude_agent import (
    _build_mcp_servers,
    _clean_overgenerated_response,
    _cleanup_session_workdir,
    _create_session_workdir,
    compose_prompt_with_history,
)
from .codex_acp import CodexAcpClient

logger = logging.getLogger(__name__)

_SECURITY_PROMPT = """
安全限制（由 ching-tech-os framework 強制執行）：
- 工作區為唯讀；禁止 terminal、shell、檔案寫入及原生圖片工具。
- 只能呼叫本次明確提供且允許的 MCP 工具。
- 圖片只能透過允許的 ching-tech-os/nanobanana MCP 工具產生。
""".strip()


class CodexCircuitBreaker:
    """只針對 provider 基礎設施失敗開路的輕量 circuit breaker。"""

    def __init__(
        self,
        failure_threshold: int,
        cooldown_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(0.1, cooldown_seconds)
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    def allows_request(self) -> bool:
        if self._opened_at is None:
            return True
        if self._clock() - self._opened_at >= self.cooldown_seconds:
            self._opened_at = None
            self._failures = 0
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = self._clock()

    def status(self) -> dict[str, Any]:
        """不改變內部狀態的安全狀態輸出。"""
        is_open = (
            self._opened_at is not None
            and self._clock() - self._opened_at < self.cooldown_seconds
        )
        return {
            "state": "open" if is_open else "closed",
            "consecutive_failures": self._failures,
        }


def _resolve_executable(value: str) -> str | None:
    """接受明確路徑或 PATH command，且只回傳可執行檔。"""
    candidate = Path(value).expanduser()
    if candidate.is_absolute() or candidate.parent != Path("."):
        return str(candidate) if candidate.is_file() and os.access(candidate, os.X_OK) else None
    resolved = shutil.which(value)
    return resolved if resolved and os.access(resolved, os.X_OK) else None


def _allowed_identities(tools: list[str] | None) -> set[tuple[str, str]]:
    """只接受完整 ``mcp__server__tool`` 名稱；短名稱一律不推測。"""
    identities: set[tuple[str, str]] = set()
    for value in tools or []:
        normalized = str(value).strip().lower()
        if not normalized.startswith("mcp__"):
            continue
        remainder = normalized[5:]
        server, separator, tool = remainder.partition("__")
        if separator and server and tool:
            identities.add((server, tool))
    return identities


def _canonical_identity(title: str, raw_input: dict[str, Any]) -> tuple[str, str] | None:
    """ACP title 與 raw server/tool 必須同時存在且完全一致。"""
    server = str(raw_input.get("server", "")).strip().lower()
    tool = str(raw_input.get("tool", "")).strip().lower()
    normalized_title = str(title).strip().lower()
    if not server or not tool or normalized_title != f"mcp.{server}.{tool}":
        return None
    return server, tool


def _canonical_tool_name(identity: tuple[str, str]) -> str:
    return f"mcp__{identity[0]}__{identity[1]}"


def _permission_option(options: list[dict], *, allow: bool) -> str:
    target = "allow" if allow else "reject"
    for option in options:
        if target in str(option.get("kind", "")).lower():
            return str(option.get("id", target))
    return target


def _safe_error_category(exc: BaseException) -> str:
    text = str(exc).lower()
    if isinstance(exc, FileNotFoundError):
        return "binary_missing"
    if "auth" in text or "login" in text or "unauthorized" in text:
        return "auth_error"
    if "mcp" in text and ("start" in text or "connect" in text):
        return "mcp_startup_error"
    if "overload" in text or "rate limit" in text or "429" in text:
        return "overload"
    if "protocol" in text or "jsonrpc" in text or "initialize" in text:
        return "protocol_error"
    return "execution_error"


class CodexProvider:
    """符合 ``AIProvider`` 的隔離式 Codex ACP adapter。"""

    provider_name = "codex"

    def __init__(
        self,
        *,
        client_factory: Callable[..., CodexAcpClient] = CodexAcpClient,
        adapter_path: str | None = None,
        codex_path: str | None = None,
        model: str | None = None,
        max_concurrency: int | None = None,
        queue_timeout: float | None = None,
        circuit_breaker: CodexCircuitBreaker | None = None,
    ) -> None:
        self._client_factory = client_factory
        self.adapter_path = adapter_path or settings.codex_acp_bin_path
        self.codex_path = codex_path or settings.codex_bin_path
        self.model = settings.codex_model if model is None else model
        concurrency = max_concurrency or settings.codex_max_concurrency
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self.queue_timeout = queue_timeout or settings.codex_queue_timeout_seconds
        self.circuit_breaker = circuit_breaker or CodexCircuitBreaker(
            settings.codex_circuit_failure_threshold,
            settings.codex_circuit_cooldown_seconds,
        )

    async def is_ready(self) -> bool:
        return bool(
            self.circuit_breaker.allows_request()
            and _resolve_executable(self.adapter_path)
            and _resolve_executable(self.codex_path)
        )

    async def status(self) -> dict[str, Any]:
        """readiness 與 circuit 的安全狀態輸出；不含路徑外的環境或 credentials。"""
        adapter_ok = _resolve_executable(self.adapter_path) is not None
        codex_ok = _resolve_executable(self.codex_path) is not None
        circuit = self.circuit_breaker.status()
        return {
            "ready": bool(adapter_ok and codex_ok and circuit["state"] == "closed"),
            "adapter_binary": adapter_ok,
            "codex_binary": codex_ok,
            "circuit": circuit,
        }

    def _client_env(self, codex_binary: str) -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            {
                "CODEX_PATH": codex_binary,
                # 明確固定 auth storage，避免 systemd 環境下 HOME 不確定時讀錯 credentials
                "CODEX_HOME": settings.codex_home,
                "INITIAL_AGENT_MODE": "read-only",
                "NO_BROWSER": "1",
                "CODEX_CONFIG": json.dumps(
                    {
                        "features": {"multi_agent": False},
                        "sandbox_mode": "read-only",
                        "approval_policy": "on-request",
                    }
                ),
            }
        )
        return env

    async def call(
        self,
        prompt: str,
        model: str = "sonnet",
        history: list[dict] | None = None,
        system_prompt: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        tools: list[str] | None = None,
        tool_call_limits: dict[str, int] | None = None,
        on_tool_start: ToolNotifyCallback | None = None,
        on_tool_end: ToolNotifyCallback | None = None,
        required_mcp_servers: set[str] | None = None,
        ctos_user_id: int | None = None,
        extra_mcp_env: dict[str, str] | None = None,
    ) -> AIResponse:
        del model  # Claude 的 workload role 不可直接當成 Codex model slug。
        queue_started = time.monotonic()
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(), timeout=self.queue_timeout
            )
        except TimeoutError:
            logger.warning(
                "codex_queue_timeout queue_wait_ms=%d circuit=%s",
                int((time.monotonic() - queue_started) * 1000),
                self.circuit_breaker.status()["state"],
            )
            return AIResponse(
                success=False,
                message="",
                error="Codex 暫時忙碌（queue_timeout）",
                provider="codex",
                provider_started=False,
            )
        queue_wait_ms = int((time.monotonic() - queue_started) * 1000)

        try:
            response = await self._call_acp(
                prompt=prompt,
                history=history,
                system_prompt=system_prompt,
                timeout=timeout,
                tools=tools,
                tool_call_limits=tool_call_limits,
                on_tool_start=on_tool_start,
                on_tool_end=on_tool_end,
                required_mcp_servers=required_mcp_servers,
                ctos_user_id=ctos_user_id,
                extra_mcp_env=extra_mcp_env,
            )
            logger.info(
                "codex_call success=%s queue_wait_ms=%d circuit=%s",
                response.success,
                queue_wait_ms,
                self.circuit_breaker.status()["state"],
            )
            return response
        finally:
            self._semaphore.release()

    async def _call_acp(
        self,
        *,
        prompt: str,
        history: list[dict] | None,
        system_prompt: str | None,
        timeout: int,
        tools: list[str] | None,
        tool_call_limits: dict[str, int] | None,
        on_tool_start: ToolNotifyCallback | None,
        on_tool_end: ToolNotifyCallback | None,
        required_mcp_servers: set[str] | None,
        ctos_user_id: int | None,
        extra_mcp_env: dict[str, str] | None,
    ) -> AIResponse:
        adapter_binary = _resolve_executable(self.adapter_path)
        codex_binary = _resolve_executable(self.codex_path)
        if not adapter_binary or not codex_binary:
            self.circuit_breaker.record_failure()
            return AIResponse(
                success=False,
                message="",
                error="Codex 無法啟動（binary_missing）",
                provider="codex",
                provider_started=False,
            )

        session_dir = _create_session_workdir()
        try:
            allowed = _allowed_identities(tools)
            allowed_servers = {server for server, _tool in allowed}
            effective_servers = (
                set(required_mcp_servers) & allowed_servers
                if required_mcp_servers is not None
                else allowed_servers
            )
            mcp_servers = (
                _build_mcp_servers(session_dir, effective_servers) if tools else []
            )
            if mcp_servers and (ctos_user_id is not None or extra_mcp_env):
                for server in mcp_servers:
                    if server.name != "ching-tech-os" or not hasattr(server, "env"):
                        continue
                    if ctos_user_id is not None:
                        server.env.append(
                            EnvVariable(name="CTOS_USER_ID", value=str(ctos_user_id))
                        )
                    for key, value in (extra_mcp_env or {}).items():
                        server.env.append(
                            EnvVariable(name=str(key), value=str(value))
                        )
                    break

            client = self._client_factory(
                command=adapter_binary,
                cwd=session_dir,
                env=self._client_env(codex_binary),
                mcp_servers=mcp_servers,
            )
            if hasattr(client, "stderr_max_bytes"):
                client.stderr_max_bytes = settings.codex_stderr_max_bytes
        except Exception:
            self.circuit_breaker.record_failure()
            _cleanup_session_workdir(session_dir)
            logger.warning("Codex provider 初始化失敗，category=execution_error")
            return AIResponse(
                success=False,
                message="",
                error="Codex 請求失敗（execution_error）",
                provider="codex",
                provider_started=False,
            )

        limits = self._build_tool_limits(allowed, tool_call_limits)
        counts: dict[str, int] = {}
        pending: dict[str, tuple[str, dict[str, Any]]] = {}
        active: dict[str, tuple[str, float, dict[str, Any]]] = {}
        approved: set[str] = set()
        tool_calls: list[ToolCall] = []
        tool_timings: list[dict] = []
        permission_lock = asyncio.Lock()
        security_violation: str | None = None
        provider_started = False

        async def safe_notify(callback: ToolNotifyCallback | None, name: str, data: dict) -> None:
            if callback is None:
                return
            try:
                await callback(name, data)
            except Exception:
                logger.warning("Codex 工具通知 callback 失敗", exc_info=False)

        @client.on_tool_start
        async def handle_tool_start(tool_id: str, title: str, raw_input: dict) -> None:
            nonlocal security_violation
            identity = _canonical_identity(title, raw_input)
            if identity is None:
                security_violation = "non_canonical_tool"
                return
            pending[tool_id] = (_canonical_tool_name(identity), dict(raw_input))

        @client.on_permission
        async def handle_permission(title: str, raw_input: dict, options: list[dict]) -> str:
            nonlocal security_violation
            identity = _canonical_identity(title, raw_input)
            tool_id = str(raw_input.get("_acp_tool_call_id", ""))
            async with permission_lock:
                if identity is None or identity not in allowed or not tool_id:
                    security_violation = "permission_denied"
                    return _permission_option(options, allow=False)
                tool_name = _canonical_tool_name(identity)
                pending_entry = pending.get(tool_id)
                if pending_entry is None or pending_entry[0] != tool_name:
                    security_violation = "identity_mismatch"
                    return _permission_option(options, allow=False)
                limit = limits.get(tool_name)
                current = counts.get(tool_name, 0)
                if limit is not None and current >= limit:
                    return _permission_option(options, allow=False)
                counts[tool_name] = current + 1
                approved.add(tool_id)
                active[tool_id] = (tool_name, time.monotonic(), pending_entry[1])
            # 只記工具名稱，輸入參數可能含使用者資料，不進 log
            logger.info("codex_tool_started name=%s", tool_name)
            await safe_notify(on_tool_start, tool_name, pending_entry[1])
            return _permission_option(options, allow=True)

        @client.on_tool_end
        async def handle_tool_end(tool_id: str, status: str, raw_output: Any) -> None:
            nonlocal security_violation
            pending.pop(tool_id, None)
            item = active.pop(tool_id, None)
            if tool_id not in approved or item is None:
                if str(status).lower() == "completed":
                    security_violation = "unapproved_tool_completed"
                return
            approved.discard(tool_id)
            tool_name, started_at, tool_input = item
            duration_ms = int((time.monotonic() - started_at) * 1000)
            output = "" if raw_output is None else str(raw_output)
            tool_calls.append(ToolCall(tool_id, tool_name, tool_input, output))
            timing = {"name": tool_name, "duration_ms": duration_ms}
            tool_timings.append(timing)
            logger.info(
                "codex_tool_completed name=%s status=%s duration_ms=%d",
                tool_name,
                status,
                duration_ms,
            )
            await safe_notify(
                on_tool_end,
                tool_name,
                {"duration_ms": duration_ms, "output": output, "status": status},
            )

        @client.on_terminal_create
        async def deny_terminal(_command: str, _cwd: str) -> bool:
            nonlocal security_violation
            security_violation = "terminal_denied"
            return False

        @client.on_file_write
        async def deny_file_write(_path: str, _content: str) -> bool:
            nonlocal security_violation
            security_violation = "file_write_denied"
            return False

        full_prompt = compose_prompt_with_history(history, prompt) if history else prompt
        prompt_parts = [_SECURITY_PROMPT]
        if system_prompt:
            prompt_parts.extend(["系統指示：", system_prompt])
        prompt_parts.extend(["使用者請求：", full_prompt])

        try:
            async def run() -> str:
                nonlocal provider_started
                await client.connect()
                provider_started = True
                if self.model:
                    await client.set_model(self.model)
                await client.new_session()
                return await client.prompt("\n\n".join(prompt_parts))

            text = await asyncio.wait_for(run(), timeout=max(0.1, timeout))
            if security_violation:
                return self._failure_response(
                    client, "security_violation", provider_started, tool_calls, tool_timings
                )
            self.circuit_breaker.record_success()
            return AIResponse(
                success=True,
                message=_clean_overgenerated_response(text),
                tool_calls=tool_calls,
                input_tokens=getattr(client, "input_tokens", None),
                output_tokens=getattr(client, "output_tokens", None),
                tool_timings=tool_timings,
                provider="codex",
                actual_model=getattr(client, "model_name", None) or self.model or None,
                provider_started=provider_started,
            )
        except TimeoutError:
            self.circuit_breaker.record_failure()
            try:
                await client.cancel()
            except Exception:
                logger.debug("Codex cancel 失敗", exc_info=False)
            return self._failure_response(
                client, "timeout", provider_started, tool_calls, tool_timings
            )
        except Exception as exc:
            # fail closed:任何未預期例外（含 acp RequestError）都轉安全失敗，
            # 不得向 caller 拋出原始訊息，且必須記入 circuit breaker
            category = _safe_error_category(exc)
            self.circuit_breaker.record_failure()
            logger.warning("Codex provider 失敗，category=%s", category)
            return self._failure_response(
                client, category, provider_started, tool_calls, tool_timings
            )
        finally:
            try:
                try:
                    await asyncio.wait_for(client.disconnect(), timeout=8)
                except Exception:
                    logger.warning("Codex client cleanup 未正常完成", exc_info=False)
            finally:
                _cleanup_session_workdir(session_dir)

    @staticmethod
    def _failure_response(
        client: Any,
        category: str,
        provider_started: bool,
        tool_calls: list[ToolCall],
        tool_timings: list[dict],
    ) -> AIResponse:
        return AIResponse(
            success=False,
            message=_clean_overgenerated_response(getattr(client, "_text_buffer", "")),
            error=f"Codex 請求失敗（{category}）",
            tool_calls=tool_calls,
            input_tokens=getattr(client, "input_tokens", None),
            output_tokens=getattr(client, "output_tokens", None),
            tool_timings=tool_timings,
            provider="codex",
            actual_model=getattr(client, "model_name", None),
            provider_started=provider_started,
        )

    @staticmethod
    def _build_tool_limits(
        allowed: set[tuple[str, str]],
        overrides: dict[str, int] | None,
    ) -> dict[str, int]:
        names = {_canonical_tool_name(identity) for identity in allowed}
        limits: dict[str, int] = {}
        image_defaults = {
            "mcp__nanobanana__generate_image": settings.nanobanana_max_calls_per_request,
            "mcp__nanobanana__edit_image": settings.nanobanana_max_calls_per_request,
            "mcp__nanobanana__restore_image": settings.nanobanana_max_calls_per_request,
            "mcp__ching-tech-os__codex_image_tool": settings.codex_image_max_calls_per_request,
        }
        for name, limit in image_defaults.items():
            if name in names and int(limit) > 0:
                limits[name] = int(limit)
        for raw_name, raw_limit in (overrides or {}).items():
            name = str(raw_name).strip().lower()
            if name not in names:
                continue
            try:
                limit = int(raw_limit)
            except (TypeError, ValueError):
                continue
            if limit <= 0:
                limits.pop(name, None)
            else:
                limits[name] = limit
        return limits


codex_provider = CodexProvider()


async def call_codex(**provider_kwargs: Any) -> AIResponse:
    """供測試與明確 provider caller 使用的 singleton 包裝。"""
    return await codex_provider.call(**provider_kwargs)
