#!/usr/bin/env python3
"""非同步研究任務啟動：搜尋 + 擷取 + 統整。"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import shutil
import socket
import sys
import time
import uuid as uuid_module
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import httpx

# 參數限制
MAX_QUERY_LENGTH = 500
MAX_RESULTS_LIMIT = 10
MAX_FETCH_LIMIT = 6
MAX_SEED_URLS = 10

DEFAULT_MAX_RESULTS = 5
DEFAULT_MAX_FETCH = 4

HTTP_TIMEOUT_SEC = 15
MAX_RAW_HTML_CHARS = 300_000
MAX_SNIPPET_CHARS = 260

USER_AGENT = "ChingTechOS-ResearchSkill/1.0"
BRAVE_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
DEFAULT_RESEARCH_MODEL = "claude-opus"
DEFAULT_CLAUDE_WORKER_TIMEOUT_SEC = 1200
DEFAULT_LOCAL_SYNTHESIS_TIMEOUT_SEC = 240
RESEARCH_RETENTION_DAYS = 7
MAX_RESEARCH_WORKERS = 1
QUEUE_WAIT_TIMEOUT_SEC = 120
QUEUE_POLL_INTERVAL_SEC = 2
MAX_TOOL_TRACE_ITEMS = 80

_SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style|noscript).*?>.*?</\1>")
_TAG_RE = re.compile(r"(?is)<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_BRAVE_PUBLIC_ANCHOR_RE = re.compile(
    r'<a[^>]+href="(?P<href>https?://[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_URL_RE = re.compile(r"https?://[^\s\]\)\"'<>]+", re.IGNORECASE)


def _parse_stdin_json_object() -> tuple[dict | None, str | None]:
    """解析 stdin JSON 物件，回傳 (payload, error_message)。"""
    raw = sys.stdin.read().strip()
    if not raw:
        return {}, None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None, "invalid_input: 無效的 JSON 輸入"
    if not isinstance(payload, dict):
        return None, "invalid_input: input 必須是 JSON 物件"
    return payload, None


def _get_research_base_dir() -> Path:
    """取得研究任務的儲存目錄。"""
    try:
        from ching_tech_os.config import settings

        ctos_mount = settings.ctos_mount_path
    except ImportError:
        ctos_mount = os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")
    return Path(ctos_mount) / "linebot" / "research"


def _write_status(status_path: Path, data: dict) -> None:
    """寫入狀態檔（atomic write）。"""
    data["updated_at"] = datetime.now().isoformat()
    tmp_path = status_path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(status_path)


def _clamp_int(value: object, default: int, min_value: int, max_value: int) -> int:
    """將輸入轉為整數並限制範圍。"""
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, parsed))


def _is_private_host(hostname: str) -> bool:
    """檢查主機名稱是否解析到私有/保留 IP 位址（防止 SSRF）。"""
    try:
        # 先檢查是否直接是 IP 位址
        addr = ipaddress.ip_address(hostname)
        return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved
    except ValueError:
        pass

    # 解析域名為 IP 並檢查
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _family, _type, _proto, _canonname, sockaddr in infos:
            ip_str = sockaddr[0]
            addr = ipaddress.ip_address(ip_str)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return True
    except (socket.gaierror, OSError):
        # 無法解析的域名視為安全（後續 HTTP 請求會自行失敗）
        pass

    return False


def _normalize_url(url: str) -> str:
    """正規化 URL，僅允許 http/https，並阻擋私有/內部網路位址。"""
    text = (url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https"):
        return ""
    if not parsed.netloc:
        return ""
    # SSRF 防護：阻擋私有/保留 IP 位址
    hostname = parsed.hostname or ""
    if _is_private_host(hostname):
        return ""
    return text


def _truncate(text: str, limit: int) -> str:
    """截斷文字。"""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _strip_html(html_text: str) -> str:
    """移除 HTML 標籤並壓縮空白。"""
    no_script = _SCRIPT_STYLE_RE.sub(" ", html_text)
    plain = _TAG_RE.sub(" ", no_script)
    plain = unescape(plain)
    return _WHITESPACE_RE.sub(" ", plain).strip()


def _collect_related_topics(related_topics: list, collector: list[dict]) -> None:
    """展開 DuckDuckGo RelatedTopics。"""
    for item in related_topics:
        if not isinstance(item, dict):
            continue
        nested = item.get("Topics")
        if isinstance(nested, list):
            _collect_related_topics(nested, collector)
            continue

        url = item.get("FirstURL")
        text = item.get("Text")
        if isinstance(url, str) and isinstance(text, str):
            collector.append(
                {
                    "title": _truncate(text, 120),
                    "url": url,
                    "snippet": _truncate(text, 180),
                }
            )


def _dedupe_sources(candidates: list[dict], max_results: int) -> list[dict]:
    """來源去重與標準化。"""
    deduped: list[dict] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = _normalize_url(str(item.get("url", "")))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(
            {
                "title": str(item.get("title", "來源")),
                "url": normalized,
                "snippet": _truncate(str(item.get("snippet", "")), 180),
            }
        )
        if len(deduped) >= max_results:
            break
    return deduped


def _extract_urls(text: str) -> list[str]:
    """從文字中提取並正規化 URL。"""
    if not text:
        return []
    urls: list[str] = []
    for raw in _URL_RE.findall(text):
        normalized = _normalize_url(raw.rstrip(".,;:!?)"))
        if normalized:
            urls.append(normalized)
    return urls


def _iter_dated_job_dirs(base_dir: Path) -> list[Path]:
    """列出 research 根目錄下的日期資料夾。"""
    if not base_dir.exists():
        return []
    dirs: list[Path] = []
    for child in base_dir.iterdir():
        if not child.is_dir():
            continue
        try:
            datetime.strptime(child.name, "%Y-%m-%d")
        except ValueError:
            continue
        dirs.append(child)
    return sorted(dirs)


def _cleanup_old_research_dirs(base_dir: Path, retention_days: int = RESEARCH_RETENTION_DAYS) -> None:
    """清理超過保留天數的 research 暫存資料夾。"""
    cutoff = datetime.now().date() - timedelta(days=retention_days)
    for dated_dir in _iter_dated_job_dirs(base_dir):
        try:
            folder_date = datetime.strptime(dated_dir.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if folder_date > cutoff:
            continue
        try:
            shutil.rmtree(dated_dir, ignore_errors=True)
        except OSError:
            continue


def _write_json_file(path: Path, payload: dict | list) -> None:
    """寫入 JSON 檔案（UTF-8）。"""
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _count_active_jobs(base_dir: Path, exclude_job_id: str = "") -> int:
    """統計目前 queued/running 的任務數。"""
    active = 0
    for dated_dir in _iter_dated_job_dirs(base_dir):
        for status_file in dated_dir.glob("*/status.json"):
            try:
                data = json.loads(status_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if str(data.get("job_id") or "") == exclude_job_id:
                continue
            if str(data.get("status") or "").strip() in {"queued", "running"}:
                active += 1
    return active


def _wait_for_worker_slot(base_dir: Path, status_path: Path, job_id: str) -> None:
    """等待 worker slot，避免同時大量研究任務互相拖累。"""
    started_at = time.time()
    while True:
        active_jobs = _count_active_jobs(base_dir, exclude_job_id=job_id)
        if active_jobs < MAX_RESEARCH_WORKERS:
            return

        status_data = {
            "job_id": job_id,
            "status": "queued",
            "status_label": "排隊中",
            "stage": "queue",
            "stage_label": "等待執行資源",
            "progress": 0,
            "queue_size": active_jobs,
            "updated_at": datetime.now().isoformat(),
        }
        _write_json_file(status_path, status_data)

        if time.time() - started_at >= QUEUE_WAIT_TIMEOUT_SEC:
            # 超過等待上限仍進入執行，避免永久卡住。
            return
        time.sleep(QUEUE_POLL_INTERVAL_SEC)


def _is_job_canceled(status_path: Path) -> bool:
    """檢查任務是否已被外部標記為 canceled。"""
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return str(payload.get("status") or "").strip() == "canceled"


def _get_research_claude_timeout_sec() -> int:
    """取得 research worker 的 Claude timeout（秒）。"""
    env_raw = os.environ.get("RESEARCH_CLAUDE_TIMEOUT_SEC")
    if env_raw is not None:
        try:
            parsed = int(env_raw)
            return max(120, min(3600, parsed))
        except ValueError:
            pass

    try:
        from ching_tech_os.config import settings

        parsed = int(getattr(settings, "research_claude_timeout_sec", DEFAULT_CLAUDE_WORKER_TIMEOUT_SEC))
        return max(120, min(3600, parsed))
    except (ImportError, TypeError, ValueError):
        return DEFAULT_CLAUDE_WORKER_TIMEOUT_SEC


def _get_research_claude_model() -> str:
    """取得 research worker 使用的 Claude 模型。"""
    env_model = (os.environ.get("RESEARCH_CLAUDE_MODEL") or "").strip()
    if env_model:
        return env_model

    try:
        from ching_tech_os.config import settings

        configured = str(getattr(settings, "research_claude_model", DEFAULT_RESEARCH_MODEL)).strip()
        return configured or DEFAULT_RESEARCH_MODEL
    except (ImportError, TypeError, ValueError):
        return DEFAULT_RESEARCH_MODEL


def _get_brave_api_key() -> str:
    """取得 Brave Search API key。"""
    try:
        from ching_tech_os.config import settings

        api_key = settings.brave_search_api_key
    except ImportError:
        api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
    return (api_key or "").strip()


def _search_brave(
    client: httpx.Client,
    query: str,
    max_results: int,
    api_key: str,
) -> list[dict]:
    """使用 Brave Search API 取得候選來源。"""
    response = client.get(
        BRAVE_SEARCH_ENDPOINT,
        params={
            "q": query,
            "count": max_results,
        },
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        },
    )
    response.raise_for_status()
    data = response.json()

    candidates: list[dict] = []
    raw_results: list[dict] = []
    if isinstance(data, dict):
        web_payload = data.get("web")
        if isinstance(web_payload, dict) and isinstance(web_payload.get("results"), list):
            raw_results = web_payload["results"]
        elif isinstance(data.get("results"), list):
            raw_results = data["results"]

    for item in raw_results:
        if not isinstance(item, dict):
            continue
        description = item.get("description")
        if not isinstance(description, str):
            description = ""
        extra_snippets = item.get("extra_snippets")
        if isinstance(extra_snippets, list):
            parts = [part.strip() for part in extra_snippets if isinstance(part, str) and part.strip()]
            if parts and not description:
                description = " ".join(parts[:2])
        candidates.append(
            {
                "title": _truncate(str(item.get("title") or item.get("url") or "來源"), 120),
                "url": str(item.get("url") or ""),
                "snippet": _truncate(description, 180),
            }
        )

    return _dedupe_sources(candidates, max_results=max_results)


def _search_brave_public(
    client: httpx.Client,
    query: str,
    max_results: int,
) -> list[dict]:
    """使用 Brave 公開搜尋頁（無 API key 備援）。"""
    response = client.get(
        "https://search.brave.com/search",
        params={
            "q": query,
            "source": "web",
        },
    )
    response.raise_for_status()

    html = response.text[:MAX_RAW_HTML_CHARS]
    candidates: list[dict] = []
    for match in _BRAVE_PUBLIC_ANCHOR_RE.finditer(html):
        href = unescape(match.group("href") or "")
        if "search.brave.com" in href:
            continue
        title = _strip_html(match.group("title") or "")
        if len(title) < 3:
            continue
        candidates.append(
            {
                "title": _truncate(title, 120),
                "url": href,
                "snippet": "",
            }
        )
        if len(candidates) >= max_results * 5:
            break
    return _dedupe_sources(candidates, max_results=max_results)


def _build_ddg_retry_queries(query: str) -> list[str]:
    """產生 DuckDuckGo 重試查詢（長查詢逐步縮短）。"""
    normalized = _WHITESPACE_RE.sub(" ", query or "").strip()
    if not normalized:
        return []

    queries: list[str] = [normalized]
    tokens = [token for token in normalized.split(" ") if token]

    if len(tokens) > 10:
        queries.append(" ".join(tokens[:10]))

    compact_tokens: list[str] = []
    for token in tokens:
        compact = re.sub(r"[^A-Za-z0-9._-]+", "", token)
        if compact:
            compact_tokens.append(compact)
    if compact_tokens:
        queries.append(" ".join(compact_tokens[:6]))

    deduped: list[str] = []
    seen: set[str] = set()
    for text in queries:
        candidate = text[:MAX_QUERY_LENGTH].strip()
        key = candidate.lower()
        if not candidate or key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped[:3]


def _search_with_provider_fallback(
    client: httpx.Client,
    query: str,
    max_results: int,
) -> tuple[list[dict], str, list[dict]]:
    """依 provider 優先序搜尋（Brave -> DuckDuckGo）。"""
    provider_trace: list[dict] = []
    brave_api_key = _get_brave_api_key()

    if brave_api_key:
        try:
            brave_results = _search_brave(
                client,
                query=query,
                max_results=max_results,
                api_key=brave_api_key,
            )
            if brave_results:
                provider_trace.append(
                    {"provider": "brave", "status": "ok", "result_count": len(brave_results)}
                )
                return brave_results, "brave", provider_trace
            provider_trace.append(
                {"provider": "brave", "status": "empty", "reason": "no_results"}
            )
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            provider_trace.append(
                {"provider": "brave", "status": "failed", "reason": _truncate(str(exc), 180)}
            )
    else:
        provider_trace.append(
            {"provider": "brave", "status": "skipped", "reason": "missing_api_key"}
        )

    ddg_queries = _build_ddg_retry_queries(query)
    for attempt, ddg_query in enumerate(ddg_queries, start=1):
        try:
            ddg_results = _search_duckduckgo(client, ddg_query, max_results=max_results)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            provider_trace.append(
                {
                    "provider": "duckduckgo",
                    "status": "failed",
                    "attempt": attempt,
                    "query": _truncate(ddg_query, 80),
                    "reason": _truncate(str(exc), 180),
                }
            )
            continue

        if ddg_results:
            provider_trace.append(
                {
                    "provider": "duckduckgo",
                    "status": "ok",
                    "attempt": attempt,
                    "query": _truncate(ddg_query, 80),
                    "result_count": len(ddg_results),
                }
            )
            return ddg_results, "duckduckgo", provider_trace

        provider_trace.append(
            {
                "provider": "duckduckgo",
                "status": "empty",
                "attempt": attempt,
                "query": _truncate(ddg_query, 80),
                "reason": "no_results",
            }
        )

    if not ddg_queries:
        provider_trace.append(
            {"provider": "duckduckgo", "status": "skipped", "reason": "invalid_query"}
        )

    for attempt, brave_query in enumerate(ddg_queries, start=1):
        try:
            brave_public_results = _search_brave_public(
                client,
                query=brave_query,
                max_results=max_results,
            )
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            provider_trace.append(
                {
                    "provider": "brave_public",
                    "status": "failed",
                    "attempt": attempt,
                    "query": _truncate(brave_query, 80),
                    "reason": _truncate(str(exc), 180),
                }
            )
            continue

        if brave_public_results:
            provider_trace.append(
                {
                    "provider": "brave_public",
                    "status": "ok",
                    "attempt": attempt,
                    "query": _truncate(brave_query, 80),
                    "result_count": len(brave_public_results),
                }
            )
            return brave_public_results, "brave_public", provider_trace

        provider_trace.append(
            {
                "provider": "brave_public",
                "status": "empty",
                "attempt": attempt,
                "query": _truncate(brave_query, 80),
                "reason": "no_results",
            }
        )

    return [], "duckduckgo", provider_trace


def _search_duckduckgo(client: httpx.Client, query: str, max_results: int) -> list[dict]:
    """使用 DuckDuckGo Instant Answer API 取得候選來源。"""
    response = client.get(
        "https://api.duckduckgo.com/",
        params={
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        },
    )
    response.raise_for_status()
    data = response.json()

    candidates: list[dict] = []

    if isinstance(data, dict):
        abstract_url = data.get("AbstractURL")
        abstract_text = data.get("AbstractText")
        heading = data.get("Heading")
        if isinstance(abstract_url, str) and isinstance(abstract_text, str):
            candidates.append(
                {
                    "title": _truncate(heading or abstract_text, 120),
                    "url": abstract_url,
                    "snippet": _truncate(abstract_text, 180),
                }
            )

        related_topics = data.get("RelatedTopics")
        if isinstance(related_topics, list):
            _collect_related_topics(related_topics, candidates)

    return _dedupe_sources(candidates, max_results=max_results)


def _fetch_source(client: httpx.Client, source: dict) -> dict:
    """抓取單一來源內容。"""
    title = str(source.get("title") or source.get("url") or "來源")
    url = str(source.get("url") or "")
    if not url:
        return {
            "title": title,
            "url": "",
            "fetch_status": "failed",
            "error": "來源 URL 為空",
            "snippet": "",
            "content": "",
        }

    try:
        response = client.get(url)
        response.raise_for_status()

        raw_text = response.text[:MAX_RAW_HTML_CHARS]
        content_type = (response.headers.get("content-type") or "").lower()
        if "html" in content_type or "<html" in raw_text[:500].lower():
            normalized_text = _strip_html(raw_text)
        else:
            normalized_text = _WHITESPACE_RE.sub(" ", raw_text).strip()

        if not normalized_text:
            raise RuntimeError("來源內容為空")

        return {
            "title": title,
            "url": url,
            "fetch_status": "ok",
            "error": None,
            "snippet": _truncate(normalized_text, MAX_SNIPPET_CHARS),
            "content": normalized_text,
        }
    except (httpx.HTTPError, RuntimeError) as exc:
        return {
            "title": title,
            "url": url,
            "fetch_status": "failed",
            "error": str(exc),
            "snippet": "",
            "content": "",
        }


def _build_final_summary(query: str, fetched_results: list[dict]) -> str:
    """根據已擷取內容產生最終統整。"""
    ok_results = [item for item in fetched_results if item.get("fetch_status") == "ok" and item.get("content")]
    failed_results = [item for item in fetched_results if item.get("fetch_status") != "ok"]

    if not ok_results:
        failed_count = len(failed_results)
        if failed_count:
            return f"針對「{query}」目前未取得可用內容，共有 {failed_count} 個來源擷取失敗。"
        return f"針對「{query}」目前未取得可用內容。"

    lines = [
        "## 一句話結論",
        f"針對「{query}」已完成多來源擷取，以下為可驗證的重點整理與待確認事項。",
        "",
        "## 核心重點",
    ]
    for idx, item in enumerate(ok_results[:5], start=1):
        lines.append(f"{idx}. **{item['title']}**：{_truncate(item['content'], 240)}")

    lines.extend(["", "## 風險與待確認事項"])
    if failed_results:
        lines.append(f"- 另有 {len(failed_results)} 個來源擷取失敗，建議後續補抓或人工查核。")
        for item in failed_results[:3]:
            lines.append(
                f"- 失敗來源：{item.get('title') or item.get('url') or '來源'}（{item.get('error') or '未知錯誤'}）"
            )
    else:
        lines.append("- 目前所有已選來源皆成功擷取。")

    lines.extend(
        [
            "",
            "## 建議下一步",
            "- 針對上方重點逐項比對官方文件或規格書。",
            "- 將可驗證資訊寫入知識庫，並保留來源 URL 以便追蹤。",
        ]
    )

    return "\n".join(lines).strip()


def _write_result_markdown(
    result_path: Path,
    query: str,
    final_summary: str,
    fetched_results: list[dict],
) -> None:
    """寫入研究結果 markdown。"""
    lines = [
        f"# 研究結果：{query}",
        "",
        f"> 產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 統整摘要",
        "",
        final_summary,
        "",
        "## 來源",
        "",
    ]

    for idx, item in enumerate(fetched_results, start=1):
        title = item.get("title") or item.get("url") or "來源"
        url = item.get("url") or ""
        status = item.get("fetch_status")
        lines.append(f"{idx}. [{title}]({url})" if url else f"{idx}. {title}")
        if status != "ok":
            lines.append(f"   - 擷取失敗：{item.get('error') or '未知錯誤'}")
        elif item.get("snippet"):
            lines.append(f"   - 摘要：{item['snippet']}")
        lines.append("")

    result_path.write_text("\n".join(lines), encoding="utf-8")


def _upsert_source(
    sources_by_url: dict[str, dict],
    *,
    url: str,
    title: str = "",
    snippet: str = "",
    origin: str = "",
) -> None:
    """合併來源資訊（以 URL 去重）。"""
    normalized = _normalize_url(url)
    if not normalized:
        return

    existing = sources_by_url.get(normalized)
    if existing is None:
        existing = {
            "title": title or (urlparse(normalized).netloc or normalized),
            "url": normalized,
            "snippet": _truncate(snippet, 420) if snippet else "",
            "origins": [origin] if origin else [],
        }
        sources_by_url[normalized] = existing
        return

    if title and (not existing.get("title") or existing.get("title") == normalized):
        existing["title"] = title
    if snippet:
        current = str(existing.get("snippet") or "")
        if len(snippet) > len(current):
            existing["snippet"] = _truncate(snippet, 420)
    if origin:
        origins = existing.get("origins") or []
        if origin not in origins:
            existing["origins"] = origins + [origin]


def _build_deep_research_prompt(query: str, seed_urls: list[str], min_sources: int) -> str:
    """建立深度研究 prompt。"""
    seed_url_block = "\n".join(f"- {url}" for url in seed_urls[:MAX_SEED_URLS]).strip()
    lines = [
        "你是資深產業研究員，請使用 WebSearch + WebFetch 完成「可交付的深度研究報告」。",
        f"研究主題：{query}",
        "",
        "研究要求（必須全部滿足）：",
        f"1) 至少引用 {min_sources} 個可追溯來源 URL，且至少 3 個是官方/一手來源。",
        "2) 若資料不足，必須主動再搜尋補齊，不可只給簡短摘要。",
        "3) 必須同時涵蓋：產品定位、型號/規格、功能差異、應用場景、價格/採購線索、風險與不確定性。",
        "4) 找不到的資訊要明確標示「未查得」，並說明已嘗試的方向。",
        "5) 僅輸出繁體中文 markdown，不要輸出其它對話。",
        "",
        "輸出格式（固定章節）：",
        "## 一句話結論",
        "## 核心重點（5-8 點）",
        "## 詳細研究",
        "### 產品與定位",
        "### 規格與功能比較",
        "### 使用場景與導入價值",
        "### 價格/供應與採購建議",
        "### 風險與待確認事項",
        "## 建議下一步",
        "## 參考來源（編號清單）",
    ]
    if seed_url_block:
        lines.extend(["", "請優先參考以下指定來源：", seed_url_block])
    return "\n".join(lines).strip()


def _build_local_synthesis_prompt(query: str, fetched_results: list[dict]) -> str:
    """把 fallback 擷取結果整理成可供 Claude 二次統整的 prompt。"""
    source_blocks: list[str] = []
    for idx, item in enumerate(fetched_results[:6], start=1):
        if item.get("fetch_status") != "ok":
            continue
        content = _truncate(str(item.get("content") or ""), 2200)
        if not content:
            continue
        source_blocks.append(
            "\n".join(
                [
                    f"[來源 {idx}] {item.get('title') or '來源'}",
                    f"URL: {item.get('url') or 'N/A'}",
                    f"摘錄: {content}",
                ]
            )
        )

    source_text = "\n\n".join(source_blocks).strip()
    if not source_text:
        raise RuntimeError("缺少可供統整的來源內容")

    return "\n".join(
        [
            "請根據下列已擷取的來源內容，產出完整且可讀的研究報告。",
            f"研究主題：{query}",
            "",
            "要求：",
            "- 報告要具體，不可只列一句總結。",
            "- 必須交代：產品定位、規格差異、使用情境、價格/採購線索、風險與不確定性。",
            "- 找不到的資料明確標示「未查得」。",
            "- 以繁體中文 markdown 回覆。",
            "",
            "輸出章節：",
            "## 一句話結論",
            "## 核心重點",
            "## 詳細研究",
            "## 風險與待補資訊",
            "## 建議下一步",
            "## 參考來源",
            "",
            "來源資料：",
            source_text,
        ]
    ).strip()


async def _call_claude_local_synthesis(query: str, fetched_results: list[dict]) -> str:
    """使用 Claude 對 fallback 來源做二次深度統整。"""
    from ching_tech_os.services.claude_agent import call_claude

    prompt = _build_local_synthesis_prompt(query=query, fetched_results=fetched_results)
    timeout_sec = max(
        120,
        min(DEFAULT_LOCAL_SYNTHESIS_TIMEOUT_SEC, _get_research_claude_timeout_sec() // 3),
    )
    response = await call_claude(
        prompt=prompt,
        model=_get_research_claude_model(),
        timeout=timeout_sec,
    )
    if response.success is not True:
        raise RuntimeError(str(response.error or "local synthesis failed"))
    summary = str(response.message or "").strip()
    if not summary:
        raise RuntimeError("local synthesis empty response")
    return summary


def _run_claude_local_synthesis(query: str, fetched_results: list[dict]) -> str:
    """同步包裝器：fallback 統整時呼叫 Claude。"""
    return asyncio.run(_call_claude_local_synthesis(query=query, fetched_results=fetched_results))


async def _call_claude_research(
    query: str,
    seed_urls: list[str],
    max_results: int,
    timeout_sec: int,
) -> tuple[str, list[dict], list[dict]]:
    """在背景 worker 內呼叫 Claude 進行 web research。"""
    from ching_tech_os.services.claude_agent import call_claude

    model_name = _get_research_claude_model()
    prompt = _build_deep_research_prompt(
        query=query,
        seed_urls=seed_urls,
        min_sources=max(4, max_results),
    )

    response = await call_claude(
        prompt=prompt,
        model=model_name,
        tools=["WebSearch", "WebFetch"],
        timeout=timeout_sec,
    )

    tool_trace: list[dict] = []
    sources_by_url: dict[str, dict] = {}

    for tool_call in (response.tool_calls or [])[:MAX_TOOL_TRACE_ITEMS]:
        tool_name = str(getattr(tool_call, "name", "") or "")
        tool_input = getattr(tool_call, "input", {}) or {}
        output_text = str(getattr(tool_call, "output", "") or "")
        tool_trace.append(
            {
                "tool": tool_name,
                "input": tool_input,
                "output_preview": _truncate(output_text, 1200),
            }
        )

        input_url = _normalize_url(str(tool_input.get("url") or ""))
        if input_url:
            source_title = urlparse(input_url).netloc or input_url
            source_snippet = _truncate(output_text, 420) if tool_name == "WebFetch" else ""
            _upsert_source(
                sources_by_url,
                url=input_url,
                title=source_title,
                snippet=source_snippet,
                origin=tool_name.lower() or "tool",
            )

        for url in _extract_urls(output_text):
            _upsert_source(
                sources_by_url,
                url=url,
                title=urlparse(url).netloc or url,
                snippet=_truncate(output_text, 260),
                origin=tool_name.lower() or "tool",
            )

    for url in _extract_urls(str(response.message or "")):
        _upsert_source(
            sources_by_url,
            url=url,
            title=urlparse(url).netloc or url,
            snippet="",
            origin="final_message",
        )

    for seed_url in seed_urls:
        _upsert_source(
            sources_by_url,
            url=seed_url,
            title=urlparse(seed_url).netloc or seed_url,
            snippet="",
            origin="seed_url",
        )

    if response.success is not True:
        raise RuntimeError(str(response.error or "Claude 研究流程失敗"))

    final_summary = str(response.message or "").strip()
    if not final_summary:
        raise RuntimeError("Claude 研究流程未回傳摘要")
    if len(final_summary) < 280:
        final_summary = (
            final_summary
            + "\n\n## 補充說明\n"
            + "- 本回覆內容偏短，建議以來源清單做進一步人工複核。"
            + "\n- 已保留工具軌跡與來源摘要供後續追查。"
        )

    collected_sources = list(sources_by_url.values())
    if not collected_sources:
        raise RuntimeError("Claude 研究流程未回傳可追溯來源")
    if len(collected_sources) > max_results:
        # 保留前段來源，同時允許略多於 max_results 以提高可追溯性
        collected_sources = collected_sources[: max_results + 3]

    return final_summary, collected_sources, tool_trace


def _run_claude_research(
    query: str,
    seed_urls: list[str],
    max_results: int,
    timeout_sec: int,
) -> tuple[str, list[dict], list[dict]]:
    """同步包裝器：在 worker 內執行 Claude research。"""
    return asyncio.run(
        _call_claude_research(
            query=query,
            seed_urls=seed_urls,
            max_results=max_results,
            timeout_sec=timeout_sec,
        )
    )


def _do_research(
    base_dir: Path,
    job_dir: Path,
    status_path: Path,
    job_id: str,
    query: str,
    seed_urls: list[str],
    max_results: int,
    max_fetch: int,
) -> None:
    """背景程序主流程：優先走 Claude web tools，失敗再 fallback。"""
    _wait_for_worker_slot(base_dir=base_dir, status_path=status_path, job_id=job_id)
    if _is_job_canceled(status_path):
        _write_status(
            status_path,
            {
                "job_id": job_id,
                "status": "canceled",
                "status_label": "已取消",
                "stage": "canceled",
                "stage_label": "任務已取消",
                "progress": 0,
                "query": query,
                "search_provider": "none",
                "provider_trace": [],
                "sources": [],
                "partial_results": [],
                "final_summary": "",
                "error": None,
            },
        )
        return

    now = datetime.now().isoformat()
    status_data = {
        "job_id": job_id,
        "status": "running",
        "status_label": "執行中",
        "stage": "claude_research",
        "stage_label": "Claude Web 研究",
        "progress": 10,
        "query": query,
        "search_provider": "claude_webtools",
        "provider_trace": [],
        "sources": [],
        "partial_results": [],
        "final_summary": "",
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    _write_status(status_path, status_data)

    claude_timeout_sec = _get_research_claude_timeout_sec()
    claude_model = _get_research_claude_model()
    provider_trace: list[dict] = [
        {
            "provider": "claude_webtools",
            "status": "running",
            "model": claude_model,
            "timeout_sec": claude_timeout_sec,
        }
    ]

    try:
        final_summary, sources, tool_trace = _run_claude_research(
            query=query,
            seed_urls=seed_urls,
            max_results=max_results,
            timeout_sec=claude_timeout_sec,
        )
        result_path = job_dir / "result.md"
        sources_path = job_dir / "sources.json"
        tool_trace_path = job_dir / "tool_trace.json"

        fetched_results = [
            {
                "title": item.get("title") or item.get("url") or "來源",
                "url": item.get("url") or "",
                "fetch_status": "ok",
                "snippet": _truncate(str(item.get("snippet") or ""), MAX_SNIPPET_CHARS),
            }
            for item in sources
        ]
        _write_result_markdown(
            result_path=result_path,
            query=query,
            final_summary=final_summary,
            fetched_results=fetched_results,
        )
        _write_json_file(sources_path, sources)
        _write_json_file(tool_trace_path, tool_trace)

        date_str = job_dir.parent.name
        provider_trace[0]["status"] = "ok"
        provider_trace[0]["tool_call_count"] = len(tool_trace)
        provider_trace[0]["source_count"] = len(sources)
        _write_status(
            status_path,
            {
                **status_data,
                "status": "completed",
                "status_label": "完成",
                "stage": "completed",
                "stage_label": "完成",
                "progress": 100,
                "provider_trace": provider_trace,
                "sources": sources,
                "partial_results": fetched_results,
                "final_summary": final_summary,
                "error": None,
                "result_file_path": str(result_path),
                "sources_file_path": str(sources_path),
                "tool_trace_file_path": str(tool_trace_path),
                "result_ctos_path": f"ctos://linebot/research/{date_str}/{job_id}/result.md",
                "sources_ctos_path": f"ctos://linebot/research/{date_str}/{job_id}/sources.json",
                "tool_trace_ctos_path": f"ctos://linebot/research/{date_str}/{job_id}/tool_trace.json",
                "knowledge_ready": True,
                "updated_at": datetime.now().isoformat(),
            },
        )
        return
    except (RuntimeError, ValueError, OSError) as exc:
        provider_trace[0]["status"] = "failed"
        provider_trace[0]["reason"] = _truncate(str(exc), 200)
        _write_status(
            status_path,
            {
                **status_data,
                "status": "running",
                "status_label": "執行中",
                "stage": "fallback",
                "stage_label": "降級為內建備援流程",
                "progress": 12,
                "provider_trace": provider_trace,
                "updated_at": datetime.now().isoformat(),
            },
        )

    _do_research_local_pipeline(
        job_dir=job_dir,
        status_path=status_path,
        job_id=job_id,
        query=query,
        seed_urls=seed_urls,
        max_results=max_results,
        max_fetch=max_fetch,
        pre_provider_trace=provider_trace,
    )


def _do_research_local_pipeline(
    job_dir: Path,
    status_path: Path,
    job_id: str,
    query: str,
    seed_urls: list[str],
    max_results: int,
    max_fetch: int,
    pre_provider_trace: list[dict] | None = None,
) -> None:
    """背景程序：執行研究流程。"""
    if _is_job_canceled(status_path):
        _write_status(
            status_path,
            {
                "job_id": job_id,
                "status": "canceled",
                "status_label": "已取消",
                "stage": "canceled",
                "stage_label": "任務已取消",
                "progress": 0,
                "query": query,
                "search_provider": "none",
                "provider_trace": pre_provider_trace or [],
                "sources": [],
                "partial_results": [],
                "final_summary": "",
                "error": None,
            },
        )
        return

    base_provider_trace = list(pre_provider_trace or [])
    status_data = {
        "job_id": job_id,
        "status": "running",
        "status_label": "執行中",
        "stage": "searching",
        "stage_label": "搜尋來源",
        "progress": 0,
        "query": query,
        "search_provider": "none",
        "provider_trace": base_provider_trace,
        "sources": [],
        "partial_results": [],
        "final_summary": "",
        "error": None,
        "created_at": datetime.now().isoformat(),
    }
    _write_status(status_path, status_data)

    try:
        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(timeout=HTTP_TIMEOUT_SEC, follow_redirects=True, headers=headers) as client:
            # 1) 搜尋來源
            status_data["status"] = "running"
            status_data["status_label"] = "執行中"
            status_data["stage"] = "searching"
            status_data["stage_label"] = "搜尋來源"
            status_data["progress"] = 15
            _write_status(status_path, status_data)

            candidate_sources: list[dict] = []
            seen: set[str] = set()

            for idx, url in enumerate(seed_urls[:MAX_SEED_URLS], start=1):
                if url in seen:
                    continue
                seen.add(url)
                candidate_sources.append(
                    {
                        "title": f"指定來源 {idx}",
                        "url": url,
                        "snippet": "",
                    }
                )

            if len(candidate_sources) < max_results:
                search_results, search_provider, provider_trace = _search_with_provider_fallback(
                    client,
                    query=query,
                    max_results=max_results,
                )
                status_data["search_provider"] = search_provider
                status_data["provider_trace"] = base_provider_trace + provider_trace
                for item in search_results:
                    normalized_url = _normalize_url(str(item.get("url", "")))
                    if not normalized_url or normalized_url in seen:
                        continue
                    seen.add(normalized_url)
                    candidate_sources.append(
                        {
                            "title": str(item.get("title", "來源")),
                            "url": normalized_url,
                            "snippet": str(item.get("snippet", "")),
                        }
                    )
                    if len(candidate_sources) >= max_results:
                        break
            else:
                status_data["search_provider"] = "seed_urls"
                status_data["provider_trace"] = base_provider_trace

            if not candidate_sources:
                diagnostics = []
                for item in status_data.get("provider_trace", []):
                    if not isinstance(item, dict):
                        continue
                    provider = str(item.get("provider") or "")
                    reason = str(item.get("reason") or "")
                    status = str(item.get("status") or "")
                    if provider and reason:
                        diagnostics.append(f"{provider}:{status}:{reason}")
                    elif provider and status:
                        diagnostics.append(f"{provider}:{status}")
                if diagnostics:
                    raise RuntimeError(f"找不到可用的研究來源（{'; '.join(diagnostics[:3])}）")
                raise RuntimeError("找不到可用的研究來源")

            status_data["sources"] = candidate_sources
            status_data["progress"] = 30
            _write_status(status_path, status_data)

            # 2) 擷取內容
            status_data["status"] = "running"
            status_data["status_label"] = "執行中"
            status_data["stage"] = "fetching"
            status_data["stage_label"] = "擷取來源內容"
            status_data["progress"] = 35
            _write_status(status_path, status_data)

            to_fetch = candidate_sources[: max(1, max_fetch)]
            total_fetch = len(to_fetch)
            fetched_results: list[dict] = []

            for idx, source in enumerate(to_fetch, start=1):
                if _is_job_canceled(status_path):
                    _write_status(
                        status_path,
                        {
                            **status_data,
                            "status": "canceled",
                            "status_label": "已取消",
                            "stage": "canceled",
                            "stage_label": "任務已取消",
                            "progress": status_data.get("progress", 0),
                            "updated_at": datetime.now().isoformat(),
                        },
                    )
                    return
                fetched = _fetch_source(client, source)
                fetched_results.append(fetched)
                status_data["partial_results"] = [
                    {
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "fetch_status": item.get("fetch_status"),
                        "snippet": item.get("snippet", ""),
                        "error": item.get("error"),
                    }
                    for item in fetched_results
                ]
                status_data["progress"] = min(85, 35 + int(idx / total_fetch * 50))
                _write_status(status_path, status_data)

            # 3) 統整結果
            status_data["status"] = "running"
            status_data["status_label"] = "執行中"
            status_data["stage"] = "synthesizing"
            status_data["stage_label"] = "統整研究結果"
            status_data["progress"] = 90
            _write_status(status_path, status_data)

            synthesis_trace = {
                "provider": "local_synthesis_claude",
                "status": "running",
                "model": _get_research_claude_model(),
            }
            status_data["provider_trace"] = list(status_data.get("provider_trace") or []) + [synthesis_trace]
            _write_status(status_path, status_data)

            try:
                final_summary = _run_claude_local_synthesis(query=query, fetched_results=fetched_results)
                synthesis_trace["status"] = "ok"
            except (RuntimeError, ValueError, OSError) as exc:
                synthesis_trace["status"] = "failed"
                synthesis_trace["reason"] = _truncate(str(exc), 180)
                final_summary = _build_final_summary(query, fetched_results)

            result_path = job_dir / "result.md"
            sources_path = job_dir / "sources.json"
            tool_trace_path = job_dir / "tool_trace.json"
            sources_payload = [
                {
                    "title": item.get("title") or "來源",
                    "url": item.get("url") or "",
                    "snippet": item.get("snippet") or "",
                    "fetch_status": item.get("fetch_status") or "failed",
                    "error": item.get("error"),
                    "content_excerpt": _truncate(str(item.get("content") or ""), 1000),
                    "content_chars": len(str(item.get("content") or "")),
                }
                for item in fetched_results
            ]
            _write_json_file(sources_path, sources_payload)
            _write_json_file(
                tool_trace_path,
                [
                    {
                        "phase": "fetch",
                        "url": item.get("url") or "",
                        "status": item.get("fetch_status") or "failed",
                        "error": item.get("error"),
                    }
                    for item in fetched_results
                ],
            )
            _write_result_markdown(
                result_path=result_path,
                query=query,
                final_summary=final_summary,
                fetched_results=fetched_results,
            )

            date_str = job_dir.parent.name
            status_data["status"] = "completed"
            status_data["status_label"] = "完成"
            status_data["stage"] = "completed"
            status_data["stage_label"] = "完成"
            status_data["progress"] = 100
            status_data["provider_trace"] = list(status_data.get("provider_trace") or [])
            status_data["final_summary"] = final_summary
            status_data["error"] = None
            status_data["result_file_path"] = str(result_path)
            status_data["sources_file_path"] = str(sources_path)
            status_data["tool_trace_file_path"] = str(tool_trace_path)
            status_data["result_ctos_path"] = f"ctos://linebot/research/{date_str}/{job_id}/result.md"
            status_data["sources_ctos_path"] = f"ctos://linebot/research/{date_str}/{job_id}/sources.json"
            status_data["tool_trace_ctos_path"] = f"ctos://linebot/research/{date_str}/{job_id}/tool_trace.json"
            _write_status(status_path, status_data)
    except (httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
        status_data["status"] = "failed"
        status_data["status_label"] = "失敗"
        status_data["stage"] = "failed"
        status_data["stage_label"] = "失敗"
        status_data["error"] = str(exc)
        status_data["progress"] = status_data.get("progress", 0)
        _write_status(status_path, status_data)


def main() -> int:
    payload, error = _parse_stdin_json_object()
    if error:
        print(json.dumps({"success": False, "error": error}, ensure_ascii=False))
        return 1
    payload = payload or {}

    query = str(payload.get("query", "")).strip()
    if not query:
        print(json.dumps({"success": False, "error": "缺少 query 參數"}, ensure_ascii=False))
        return 1
    if len(query) > MAX_QUERY_LENGTH:
        print(
            json.dumps(
                {"success": False, "error": f"query 長度不可超過 {MAX_QUERY_LENGTH} 字元"},
                ensure_ascii=False,
            )
        )
        return 1

    seed_urls_raw = payload.get("urls") or []
    if not isinstance(seed_urls_raw, list):
        print(json.dumps({"success": False, "error": "urls 必須是陣列"}, ensure_ascii=False))
        return 1

    seed_urls: list[str] = []
    for raw_url in seed_urls_raw[:MAX_SEED_URLS]:
        if not isinstance(raw_url, str):
            continue
        normalized = _normalize_url(raw_url)
        if normalized:
            seed_urls.append(normalized)

    max_results = _clamp_int(payload.get("max_results"), DEFAULT_MAX_RESULTS, 1, MAX_RESULTS_LIMIT)
    max_fetch = _clamp_int(payload.get("max_fetch"), DEFAULT_MAX_FETCH, 1, MAX_FETCH_LIMIT)

    if not hasattr(os, "fork"):
        print(json.dumps({"success": False, "error": "目前環境不支援背景程序"}, ensure_ascii=False))
        return 1

    job_id = uuid_module.uuid4().hex[:8]
    date_str = datetime.now().strftime("%Y-%m-%d")
    base_dir = _get_research_base_dir()
    _cleanup_old_research_dirs(base_dir=base_dir, retention_days=RESEARCH_RETENTION_DAYS)
    job_dir = base_dir / date_str / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    status_path = job_dir / "status.json"
    _write_status(
        status_path,
        {
            "job_id": job_id,
            "status": "queued",
            "status_label": "排隊中",
            "stage": "queued",
            "stage_label": "等待背景程序啟動",
            "progress": 0,
            "query": query,
            "search_provider": "none",
            "provider_trace": [],
            "sources": [],
            "partial_results": [],
            "final_summary": "",
            "error": None,
            "created_at": datetime.now().isoformat(),
        },
    )

    pid = os.fork()
    if pid > 0:
        print(
            json.dumps(
                {
                    "success": True,
                    "job_id": job_id,
                    "status": "queued",
                    "message": "研究任務已啟動，請使用 check-research 查詢進度",
                },
                ensure_ascii=False,
            )
        )
        return 0

    try:
        os.setsid()
        devnull = os.open(os.devnull, os.O_RDWR)
        os.dup2(devnull, 0)
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        os.close(devnull)
        sys.stdin = open(os.devnull, "r")
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")

        _do_research(
            base_dir=base_dir,
            job_dir=job_dir,
            status_path=status_path,
            job_id=job_id,
            query=query,
            seed_urls=seed_urls,
            max_results=max_results,
            max_fetch=max_fetch,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        _write_status(
            status_path,
            {
                "job_id": job_id,
                "status": "failed",
                "status_label": "失敗",
                "progress": 0,
                "query": query,
                "sources": [],
                "partial_results": [],
                "final_summary": "",
                "error": str(exc),
                "created_at": datetime.now().isoformat(),
            },
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
