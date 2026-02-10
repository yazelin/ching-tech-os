"""SkillHub index client (ClawHub-compatible API).

Uses index.json to discover skills and download packages.
Feature flag: SKILLHUB_ENABLED
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from fastapi import Request
import httpx

logger = logging.getLogger(__name__)

# ZIP 檔案大小限制：10MB
_MAX_ZIP_SIZE = 10 * 1024 * 1024
# 解壓後總大小上限：50MB
_MAX_EXTRACTED_SIZE = 50 * 1024 * 1024
# 解壓後檔案數量上限
_MAX_EXTRACTED_FILES = 200

# 共用的 slug 驗證 regex
VALID_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")

_DEFAULT_INDEX_SOURCE = "https://raw.githubusercontent.com/yazelin/ching-tech-os-skillhub/main/index.json"


def validate_slug(slug: str) -> bool:
    """驗證 slug 格式（共用）"""
    return bool(VALID_SLUG_RE.match(slug)) and len(slug) <= 100


def skillhub_enabled() -> bool:
    """檢查 SkillHub feature flag"""
    return os.getenv("SKILLHUB_ENABLED", "").lower() in ("1", "true", "yes", "on")


class SkillHubError(Exception):
    """SkillHub API 錯誤"""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class SkillHubDisabledError(SkillHubError):
    """SkillHub 未啟用"""


class SkillHubClient:
    """SkillHub index client（ClawHub API 相容）"""

    def __init__(self, base_url: str | None = None):
        if not skillhub_enabled():
            raise SkillHubDisabledError("SkillHub 未啟用（請設定 SKILLHUB_ENABLED=true）")

        env_source = os.getenv("SKILLHUB_INDEX_URL") or os.getenv("SKILLHUB_INDEX_PATH")
        self._index_source = base_url or env_source or _DEFAULT_INDEX_SOURCE
        self._index: dict | None = None
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0),
            follow_redirects=False,  # SSRF 防護
        )

    async def close(self) -> None:
        """關閉 HTTP 客戶端"""
        await self._client.aclose()

    async def _load_index(self, source: str | None = None) -> dict:
        """讀取 index.json（URL 或本地檔案）"""
        source = source or self._index_source
        if not source:
            raise SkillHubError("未提供 index 來源")

        try:
            if source.startswith("http://") or source.startswith("https://"):
                resp = await self._client.get(source)
                resp.raise_for_status()
                data = resp.json()
            else:
                path = Path(source)
                if not path.exists():
                    raise SkillHubError(f"Index 檔案不存在: {source}")
                data = json.loads(path.read_text(encoding="utf-8"))

            if isinstance(data, list):
                skills = data
            elif isinstance(data, dict):
                if isinstance(data.get("skills"), list):
                    skills = data["skills"]
                elif isinstance(data.get("items"), list):
                    skills = data["items"]
                elif isinstance(data.get("packages"), list):
                    skills = data["packages"]
                else:
                    skills = next((v for v in data.values() if isinstance(v, list)), [])
            else:
                raise SkillHubError("Index JSON 必須是物件或列表")

            index_map: dict[str, dict] = {}
            for item in skills:
                try:
                    if not isinstance(item, dict):
                        logger.debug("略過非物件 index 項目: %r", item)
                        continue
                    slug = item.get("slug") or item.get("name")
                    version = item.get("version") or item.get("latest")
                    url = item.get("download_url") or item.get("url") or item.get("package_url")
                    sha256 = item.get("sha256") or item.get("hash")
                    if not slug or not url or not version:
                        logger.debug("略過缺少 slug/url/version 的項目: %s", item)
                        continue
                    index_map[slug] = {
                        "slug": slug,
                        "version": version,
                        "download_url": url,
                        "sha256": sha256,
                        "title": item.get("name") or item.get("title"),
                        "description": item.get("description"),
                        "author": item.get("author") or item.get("owner"),
                        "tags": item.get("tags") or [],
                        "source": item.get("source") or "skillhub",
                        "raw": item,
                    }
                except Exception:
                    logger.exception("解析 index 項目失敗: %s", item)

            self._index = {"source": source, "items": index_map}
            logger.info("已載入 SkillHub index: %d skills, source=%s", len(index_map), source)
            return self._index
        except httpx.HTTPStatusError as e:
            raise SkillHubError(
                f"讀取 index 失敗: HTTP {e.response.status_code}",
                status_code=e.response.status_code,
            )
        except httpx.HTTPError as e:
            raise SkillHubError(f"讀取 index 失敗: {e}")
        except json.JSONDecodeError as e:
            raise SkillHubError(f"解析 index JSON 失敗: {e}")

    async def _ensure_index(self) -> None:
        if self._index is None:
            await self._load_index()

    async def _get_entry(self, slug: str) -> dict:
        await self._ensure_index()
        entry = self._index["items"].get(slug) if self._index else None
        if not entry:
            raise SkillHubError(f"Skill '{slug}' 不存在", status_code=404)
        return entry

    async def search(self, query: str, limit: int = 20) -> list[dict]:
        """搜尋 SkillHub skills（從 index）"""
        await self._ensure_index()
        q = (query or "").strip().lower()
        items = list(self._index["items"].values()) if self._index else []
        if not q:
            return items[:limit]

        results: list[dict] = []
        for entry in items:
            hay = " ".join(
                filter(None, [
                    entry.get("slug", ""),
                    entry.get("title", ""),
                    entry.get("description", ""),
                ])
            ).lower()
            if q in hay:
                results.append(entry)
            if len(results) >= limit:
                break
        return results

    async def get_skill(self, slug: str) -> dict:
        """取得 skill 詳細資訊（對齊 ClawHub 回傳格式）"""
        entry = await self._get_entry(slug)
        latest = {
            "version": entry.get("version", ""),
            "download_url": entry.get("download_url", ""),
            "sha256": entry.get("sha256"),
        }
        skill = {
            "slug": entry.get("slug"),
            "name": entry.get("title") or entry.get("slug"),
            "description": entry.get("description") or "",
            "tags": entry.get("tags") or [],
            "source": entry.get("source") or "skillhub",
        }
        owner = {"handle": entry.get("author") or ""}
        return {
            "skill": skill,
            "owner": owner,
            "latestVersion": latest,
        }

    async def _download_to_temp(self, url: str) -> Path:
        tmp_path: Path | None = None
        success = False
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
                tmp_path = Path(tmp_file.name)
                size = 0
                async with self._client.stream(
                    "GET",
                    url,
                    timeout=httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=5.0),
                ) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_bytes():
                        tmp_file.write(chunk)
                        size += len(chunk)
                        if size > _MAX_ZIP_SIZE:
                            raise SkillHubError(
                                f"ZIP 檔案過大: {size} bytes（上限 {_MAX_ZIP_SIZE} bytes）"
                            )
            success = True
            return tmp_path
        except httpx.HTTPStatusError as e:
            raise SkillHubError(
                f"下載失敗: HTTP {e.response.status_code}",
                status_code=e.response.status_code,
            )
        except httpx.HTTPError as e:
            raise SkillHubError(f"下載失敗: {e}")
        finally:
            if not success and tmp_path and tmp_path.exists():
                tmp_path.unlink()

    async def download_zip(self, slug: str, version: str) -> Path:
        """下載 skill ZIP 檔案到暫存檔"""
        entry = await self._get_entry(slug)
        entry_version = entry.get("version") or ""
        if version and entry_version and version != entry_version:
            raise SkillHubError(
                f"Skill '{slug}' 版本不存在: {version}",
                status_code=404,
            )
        url = entry.get("download_url")
        if not url:
            raise SkillHubError(f"Skill '{slug}' 缺少下載連結")
        return await self._download_to_temp(url)

    @staticmethod
    def _verify_sha256(path: Path, expected: str | None) -> None:
        if not expected:
            logger.warning("Index 未提供 sha256，略過驗證: %s", path)
            return
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        actual = h.hexdigest()
        if actual.lower() != expected.lower():
            raise SkillHubError(f"SHA256 不符: expected {expected}, got {actual}")

    @staticmethod
    def _safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
        dest_dir.mkdir(parents=True, exist_ok=True)
        resolved_dest = dest_dir.resolve()

        with zipfile.ZipFile(zip_path) as zf:
            total_size = sum(info.file_size for info in zf.infolist() if not info.is_dir())
            file_count = sum(1 for info in zf.infolist() if not info.is_dir())
            if total_size > _MAX_EXTRACTED_SIZE:
                raise SkillHubError(
                    f"ZIP 解壓後過大: {total_size} bytes（上限 {_MAX_EXTRACTED_SIZE} bytes）"
                )
            if file_count > _MAX_EXTRACTED_FILES:
                raise SkillHubError(
                    f"ZIP 檔案數量過多: {file_count}（上限 {_MAX_EXTRACTED_FILES}）"
                )

            for info in zf.infolist():
                if info.is_dir():
                    continue
                target_path = (dest_dir / info.filename).resolve()
                if not target_path.is_relative_to(resolved_dest):
                    raise SkillHubError(f"Zip slip 攻擊偵測: {info.filename}")
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    async def download_and_extract(
        self,
        slug: str,
        version: str,
        dest_dir: Path,
    ) -> dict:
        """下載並解壓 skill 到目標目錄"""
        entry = await self._get_entry(slug)
        zip_path = await self.download_zip(slug, version)
        try:
            self._verify_sha256(zip_path, entry.get("sha256"))
            self._safe_extract_zip(zip_path, dest_dir)
        finally:
            if zip_path.exists():
                zip_path.unlink()

        logger.info(f"已解壓 skill: {slug}@{version} → {dest_dir}")
        return {"slug": slug, "version": version, "path": str(dest_dir)}

    async def extract_file_from_zip(
        self,
        slug: str,
        version: str,
        filename: str,
        *,
        zip_data: bytes | None = None,
    ) -> str | None:
        """從 ZIP 中提取單一檔案內容（不解壓到磁碟）"""
        zip_path: Path | None = None
        try:
            if zip_data is not None:
                zf_source = io.BytesIO(zip_data)
                zf = zipfile.ZipFile(zf_source)
            else:
                zip_path = await self.download_zip(slug, version)
                zf = zipfile.ZipFile(zip_path)

            with zf:
                if filename in zf.namelist():
                    info = zf.getinfo(filename)
                else:
                    info = next(
                        (i for i in zf.infolist()
                         if not i.is_dir() and Path(i.filename).name == filename),
                        None,
                    )

                if info:
                    if info.file_size > 10 * 1024 * 1024:
                        raise SkillHubError(f"檔案過大: {info.file_size} bytes")
                    return zf.read(info).decode("utf-8", errors="replace")

            return None
        finally:
            if zip_path and zip_path.exists():
                zip_path.unlink()

    @staticmethod
    def write_meta(
        dest: Path,
        slug: str,
        version: str,
        owner: str | None = None,
    ) -> None:
        """寫入 _meta.json 到 skill 目錄（委派給共用函式）"""
        from .hub_meta import write_meta
        write_meta(dest, slug, version, source="skillhub", owner=owner)

    @staticmethod
    def read_meta(skill_dir: Path) -> dict | None:
        """讀取 skill 目錄中的 _meta.json（委派給共用函式）"""
        from .hub_meta import read_meta
        return read_meta(skill_dir)


def get_skillhub_client_di(request: Request) -> SkillHubClient:
    """FastAPI 依賴注入：從 app.state 取得 SkillHubClient"""
    if not skillhub_enabled():
        raise SkillHubDisabledError("SkillHub 未啟用")
    client = getattr(request.app.state, "skillhub_client", None)
    if client is None:
        client = SkillHubClient()
        request.app.state.skillhub_client = client
    return client


