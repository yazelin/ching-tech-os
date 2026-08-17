"""Codex 部署 preflight。

在部署或啟用 Codex provider 前驗證：binary path、pin 版本、service user、
auth storage、headless 環境與最小 ACP handshake。所有檢查輸出都不得包含
credentials、token 或原始錯誤內容。

CLI 用法：``uv run python -m ching_tech_os.services.codex_preflight [--skip-handshake]``
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import settings
from .codex_acp import CodexAcpClient
from .codex_agent import CodexProvider, _resolve_executable, _safe_error_category

# 版本查詢與 handshake 的預設逾時（秒）
DEFAULT_VERSION_TIMEOUT = 10.0
DEFAULT_HANDSHAKE_TIMEOUT = 30.0

VersionRunner = Callable[[str, float], Awaitable[str]]


@dataclass(frozen=True)
class PreflightCheck:
    """單項檢查結果；detail 只允許安全描述，不含敏感內容。"""

    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class PreflightReport:
    checks: tuple[PreflightCheck, ...] = ()

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": [
                {"name": check.name, "passed": check.passed, "detail": check.detail}
                for check in self.checks
            ],
        }


def expected_pinned_versions() -> dict[str, str]:
    """從專案根目錄 package.json 讀取 pin 的 adapter/runtime 版本。"""
    package_json = Path(settings.project_root) / "package.json"
    dependencies = json.loads(package_json.read_text(encoding="utf-8")).get(
        "dependencies", {}
    )
    return {
        "adapter": str(dependencies.get("@agentclientprotocol/codex-acp", "")),
        "codex": str(dependencies.get("@openai/codex", "")),
    }


async def _run_version_command(binary: str, timeout: float) -> str:
    process = await asyncio.create_subprocess_exec(
        binary,
        "--version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    return stdout.decode("utf-8", errors="replace").strip()


def _check_binary(name: str, configured_path: str) -> tuple[PreflightCheck, str | None]:
    resolved = _resolve_executable(configured_path)
    if resolved is None:
        return (
            PreflightCheck(name, False, f"binary 不可執行：{configured_path}"),
            None,
        )
    return PreflightCheck(name, True, resolved), resolved


async def _check_version(
    name: str,
    binary: str | None,
    expected_version: str,
    version_runner: VersionRunner,
    timeout: float,
) -> PreflightCheck:
    if binary is None:
        return PreflightCheck(name, False, "略過：binary 不可用")
    if not expected_version:
        return PreflightCheck(name, False, "package.json 缺少 pin 版本")
    try:
        output = await asyncio.wait_for(
            version_runner(binary, timeout), timeout=timeout
        )
    except TimeoutError:
        return PreflightCheck(name, False, "timeout")
    except Exception as exc:
        return PreflightCheck(name, False, _safe_error_category(exc))
    if expected_version in output:
        return PreflightCheck(name, True, expected_version)
    return PreflightCheck(
        name, False, f"版本不符：預期 {expected_version}，實際輸出未包含該版本"
    )


def _check_service_user() -> PreflightCheck:
    if os.geteuid() == 0:
        return PreflightCheck(
            "service_user", False, "不得以 root 執行；請使用 service user（ct）"
        )
    return PreflightCheck("service_user", True, getpass.getuser())


def _check_auth_storage() -> PreflightCheck:
    auth_path = Path(settings.codex_home) / "auth.json"
    if not auth_path.is_file():
        return PreflightCheck(
            "auth_storage", False, f"找不到 auth 檔：{auth_path}（請以 service user 執行 codex login）"
        )
    if not os.access(auth_path, os.R_OK):
        return PreflightCheck("auth_storage", False, f"auth 檔不可讀：{auth_path}")
    if auth_path.stat().st_uid != os.geteuid():
        return PreflightCheck(
            "auth_storage", False, f"auth 檔擁有者不是目前使用者：{auth_path}"
        )
    return PreflightCheck("auth_storage", True, str(auth_path))


def _check_headless_env(codex_binary: str | None) -> PreflightCheck:
    env = CodexProvider()._client_env(codex_binary or settings.codex_bin_path)
    if env.get("NO_BROWSER") != "1":
        return PreflightCheck("headless_env", False, "NO_BROWSER 未設定為 1")
    if env.get("CODEX_HOME") != settings.codex_home:
        return PreflightCheck("headless_env", False, "CODEX_HOME 未指向設定的 auth storage")
    return PreflightCheck("headless_env", True, "NO_BROWSER=1 且 CODEX_HOME 已固定")


async def _check_handshake(
    adapter_binary: str | None,
    codex_binary: str | None,
    auth_ok: bool,
    client_factory: Callable[..., Any],
    timeout: float,
) -> PreflightCheck:
    if adapter_binary is None or codex_binary is None:
        return PreflightCheck("handshake", False, "略過：binary 不可用")
    if not auth_ok:
        return PreflightCheck("handshake", False, "略過：auth storage 未就緒")

    provider = CodexProvider()
    with tempfile.TemporaryDirectory(prefix="codex-preflight-") as workdir:
        client = client_factory(
            command=adapter_binary,
            cwd=workdir,
            env=provider._client_env(codex_binary),
            mcp_servers=[],
        )
        try:
            async with asyncio.timeout(timeout):
                await client.connect()
                await client.new_session()
        except TimeoutError:
            return PreflightCheck("handshake", False, "timeout")
        except Exception as exc:
            return PreflightCheck("handshake", False, _safe_error_category(exc))
        finally:
            try:
                await asyncio.wait_for(client.disconnect(), timeout=5)
            except Exception:
                pass
    return PreflightCheck("handshake", True, "最小 session handshake 成功")


async def run_preflight(
    *,
    include_handshake: bool = True,
    client_factory: Callable[..., Any] = CodexAcpClient,
    version_runner: VersionRunner = _run_version_command,
    version_timeout: float = DEFAULT_VERSION_TIMEOUT,
    handshake_timeout: float = DEFAULT_HANDSHAKE_TIMEOUT,
) -> PreflightReport:
    """執行全部 preflight 檢查並回傳安全的結構化報告。"""
    pinned = expected_pinned_versions()

    adapter_check, adapter_binary = _check_binary(
        "adapter_binary", settings.codex_acp_bin_path
    )
    codex_check, codex_binary = _check_binary("codex_binary", settings.codex_bin_path)

    checks: list[PreflightCheck] = [adapter_check, codex_check]
    checks.append(
        await _check_version(
            "adapter_version", adapter_binary, pinned["adapter"], version_runner, version_timeout
        )
    )
    checks.append(
        await _check_version(
            "codex_version", codex_binary, pinned["codex"], version_runner, version_timeout
        )
    )
    checks.append(_check_service_user())
    auth_check = _check_auth_storage()
    checks.append(auth_check)
    checks.append(_check_headless_env(codex_binary))

    if include_handshake:
        checks.append(
            await _check_handshake(
                adapter_binary,
                codex_binary,
                auth_check.passed,
                client_factory,
                handshake_timeout,
            )
        )

    return PreflightReport(checks=tuple(checks))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Codex 部署 preflight")
    parser.add_argument(
        "--skip-handshake",
        action="store_true",
        help="只檢查 binary/版本/使用者/auth/headless，不啟動 adapter handshake",
    )
    args = parser.parse_args(argv)

    report = asyncio.run(run_preflight(include_handshake=not args.skip_handshake))
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":  # pragma: no cover - CLI 入口
    raise SystemExit(main())
