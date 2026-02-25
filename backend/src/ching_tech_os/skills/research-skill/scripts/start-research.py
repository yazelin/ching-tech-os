#!/usr/bin/env python3
"""非同步研究任務啟動：搜尋 + 擷取 + 統整。"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import sys
import uuid as uuid_module
from datetime import datetime
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

_SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style|noscript).*?>.*?</\1>")
_TAG_RE = re.compile(r"(?is)<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


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

    try:
        ddg_results = _search_duckduckgo(client, query, max_results=max_results)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        provider_trace.append(
            {"provider": "duckduckgo", "status": "failed", "reason": _truncate(str(exc), 180)}
        )
        return [], "none", provider_trace

    if ddg_results:
        provider_trace.append(
            {"provider": "duckduckgo", "status": "ok", "result_count": len(ddg_results)}
        )
        return ddg_results, "duckduckgo", provider_trace

    provider_trace.append(
        {"provider": "duckduckgo", "status": "empty", "reason": "no_results"}
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

    lines = [f"研究主題：{query}", "", "重點整理："]
    for idx, item in enumerate(ok_results[:4], start=1):
        lines.append(f"{idx}. {item['title']}")
        lines.append(f"   {_truncate(item['content'], 320)}")

    if failed_results:
        lines.append("")
        lines.append(f"備註：另有 {len(failed_results)} 個來源擷取失敗。")

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


def _do_research(
    job_dir: Path,
    status_path: Path,
    job_id: str,
    query: str,
    seed_urls: list[str],
    max_results: int,
    max_fetch: int,
) -> None:
    """背景程序：執行研究流程。"""
    status_data = {
        "job_id": job_id,
        "status": "starting",
        "status_label": "啟動中",
        "progress": 0,
        "query": query,
        "search_provider": "none",
        "provider_trace": [],
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
            status_data["status"] = "searching"
            status_data["status_label"] = "搜尋中"
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
                status_data["provider_trace"] = provider_trace
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
                status_data["provider_trace"] = []

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
            status_data["status"] = "fetching"
            status_data["status_label"] = "擷取中"
            status_data["progress"] = 35
            _write_status(status_path, status_data)

            to_fetch = candidate_sources[: max(1, max_fetch)]
            total_fetch = len(to_fetch)
            fetched_results: list[dict] = []

            for idx, source in enumerate(to_fetch, start=1):
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
            status_data["status"] = "synthesizing"
            status_data["status_label"] = "統整中"
            status_data["progress"] = 90
            _write_status(status_path, status_data)

            final_summary = _build_final_summary(query, fetched_results)
            result_path = job_dir / "result.md"
            _write_result_markdown(
                result_path=result_path,
                query=query,
                final_summary=final_summary,
                fetched_results=fetched_results,
            )

            date_str = job_dir.parent.name
            status_data["status"] = "completed"
            status_data["status_label"] = "完成"
            status_data["progress"] = 100
            status_data["final_summary"] = final_summary
            status_data["error"] = None
            status_data["result_file_path"] = str(result_path)
            status_data["result_ctos_path"] = f"ctos://linebot/research/{date_str}/{job_id}/result.md"
            _write_status(status_path, status_data)
    except (httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
        status_data["status"] = "failed"
        status_data["status_label"] = "失敗"
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
    job_dir = base_dir / date_str / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    status_path = job_dir / "status.json"
    _write_status(
        status_path,
        {
            "job_id": job_id,
            "status": "starting",
            "status_label": "啟動中",
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
                    "status": "started",
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
