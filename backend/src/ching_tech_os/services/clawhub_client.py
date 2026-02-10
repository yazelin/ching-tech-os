"""ClawHub REST API 客戶端

使用 httpx 非同步客戶端與 ClawHub REST API 溝通，
取代舊有的 clawhub CLI 子程序呼叫。
"""

import io
import json
import logging
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
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


def validate_slug(slug: str) -> bool:
    """驗證 slug 格式（共用）"""
    return bool(VALID_SLUG_RE.match(slug)) and len(slug) <= 100


class ClawHubError(Exception):
    """ClawHub API 錯誤"""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


_DEFAULT_BASE_URL = "https://clawhub.ai/api/v1"


class ClawHubClient:
    """ClawHub REST API 非同步客戶端"""

    def __init__(self, base_url: str | None = None):
        self._base_url = base_url or _DEFAULT_BASE_URL
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0),
            follow_redirects=False,  # SSRF 防護
        )

    async def close(self) -> None:
        """關閉 HTTP 客戶端"""
        await self._client.aclose()

    async def search(self, query: str, limit: int = 20) -> list[dict]:
        """搜尋 ClawHub skills

        Args:
            query: 搜尋關鍵字
            limit: 最大結果數量

        Returns:
            搜尋結果列表
        """
        try:
            resp = await self._client.get(
                "/search",
                params={"q": query.strip(), "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])
        except httpx.HTTPStatusError as e:
            raise ClawHubError(
                f"搜尋失敗: HTTP {e.response.status_code}",
                status_code=e.response.status_code,
            )
        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
            raise ClawHubError(f"搜尋失敗: {e}")

    async def get_skill(self, slug: str) -> dict:
        """取得 skill 詳細資訊

        Args:
            slug: skill 的 slug 識別碼

        Returns:
            包含 skill, owner, latestVersion 的字典
        """
        try:
            resp = await self._client.get(f"/skills/{slug}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ClawHubError(
                    f"Skill '{slug}' 不存在",
                    status_code=404,
                )
            raise ClawHubError(
                f"取得 skill 詳情失敗: HTTP {e.response.status_code}",
                status_code=e.response.status_code,
            )
        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
            raise ClawHubError(f"取得 skill 詳情失敗: {e}")

    async def download_zip(self, slug: str, version: str) -> Path:
        """下載 skill ZIP 檔案到暫存檔

        Args:
            slug: skill slug
            version: 版本號

        Returns:
            暫存 ZIP 檔案路徑

        Raises:
            ClawHubError: 下載失敗或檔案過大
        """
        tmp_path: Path | None = None
        success = False
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
                tmp_path = Path(tmp_file.name)
                size = 0
                async with self._client.stream(
                    "GET", "/download",
                    params={"slug": slug, "version": version},
                    timeout=httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=5.0),
                ) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_bytes():
                        tmp_file.write(chunk)
                        size += len(chunk)
                        if size > _MAX_ZIP_SIZE:
                            raise ClawHubError(
                                f"ZIP 檔案過大: {size} bytes（上限 {_MAX_ZIP_SIZE} bytes）"
                            )
            success = True
            return tmp_path
        except httpx.HTTPStatusError as e:
            raise ClawHubError(
                f"下載失敗: HTTP {e.response.status_code}",
                status_code=e.response.status_code,
            )
        except httpx.HTTPError as e:
            raise ClawHubError(f"下載失敗: {e}")
        finally:
            if not success and tmp_path and tmp_path.exists():
                tmp_path.unlink()

    async def download_and_extract(
        self,
        slug: str,
        version: str,
        dest_dir: Path,
    ) -> dict:
        """下載並解壓 skill 到目標目錄

        包含 zip slip 防護和大小限制。

        Args:
            slug: skill slug
            version: 版本號
            dest_dir: 目標目錄

        Returns:
            包含 slug, version, path 的字典
        """
        zip_path = await self.download_zip(slug, version)

        # 解壓並防護 zip slip + ZIP bomb
        dest_dir.mkdir(parents=True, exist_ok=True)
        resolved_dest = dest_dir.resolve()

        try:
            with zipfile.ZipFile(zip_path) as zf:
                # ZIP bomb 防護：先檢查解壓後總大小和檔案數
                total_size = sum(info.file_size for info in zf.infolist() if not info.is_dir())
                file_count = sum(1 for info in zf.infolist() if not info.is_dir())
                if total_size > _MAX_EXTRACTED_SIZE:
                    raise ClawHubError(
                        f"ZIP 解壓後過大: {total_size} bytes（上限 {_MAX_EXTRACTED_SIZE} bytes）"
                    )
                if file_count > _MAX_EXTRACTED_FILES:
                    raise ClawHubError(
                        f"ZIP 檔案數量過多: {file_count}（上限 {_MAX_EXTRACTED_FILES}）"
                    )

                for info in zf.infolist():
                    if info.is_dir():
                        continue

                    # Zip slip 防護：確保解壓路徑在目標目錄內
                    target_path = (dest_dir / info.filename).resolve()
                    if not target_path.is_relative_to(resolved_dest):
                        raise ClawHubError(
                            f"Zip slip 攻擊偵測: {info.filename}"
                        )

                    # 建立父目錄
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    # 解壓檔案
                    with zf.open(info) as src, open(target_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        finally:
            if zip_path.exists():
                zip_path.unlink()

        logger.info(f"已解壓 skill: {slug}@{version} → {dest_dir}")
        return {"slug": slug, "version": version, "path": str(dest_dir)}

    async def extract_file_from_zip(
        self, slug: str, version: str, filename: str,
        *, zip_data: bytes | None = None,
    ) -> str | None:
        """從 ZIP 中提取單一檔案內容（不解壓到磁碟）

        Args:
            slug: skill slug
            version: 版本號
            filename: 要提取的檔案名稱（如 "SKILL.md"）
            zip_data: 已下載的 ZIP bytes（避免重複下載）

        Returns:
            檔案內容字串，或 None（檔案不存在）
        """
        zip_path: Path | None = None
        try:
            if zip_data is not None:
                zf_source = io.BytesIO(zip_data)
                zf = zipfile.ZipFile(zf_source)
            else:
                zip_path = await self.download_zip(slug, version)
                zf = zipfile.ZipFile(zip_path)

            with zf:
                # 優先尋找根目錄下的檔案
                if filename in zf.namelist():
                    info = zf.getinfo(filename)
                else:
                    # 若根目錄找不到，再搜尋 basename 匹配（支援有前綴目錄的 ZIP）
                    info = next(
                        (i for i in zf.infolist()
                         if not i.is_dir() and Path(i.filename).name == filename),
                        None,
                    )

                if info:
                    if info.file_size > 10 * 1024 * 1024:  # 10MB limit
                        raise ClawHubError(f"檔案過大: {info.file_size} bytes")
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
        """寫入 _meta.json 到 skill 目錄

        Args:
            dest: skill 目錄
            slug: skill slug
            version: 版本號
            owner: 擁有者 handle
        """
        meta = {
            "slug": slug,
            "version": version,
            "source": "clawhub",
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "owner": owner or "",
        }
        meta_path = dest / "_meta.json"
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"寫入 _meta.json: {meta_path}")

    @staticmethod
    def read_meta(skill_dir: Path) -> dict | None:
        """讀取 skill 目錄中的 _meta.json

        Args:
            skill_dir: skill 目錄

        Returns:
            _meta.json 內容字典，或 None（檔案不存在）
        """
        meta_path = skill_dir / "_meta.json"
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"讀取 _meta.json 失敗: {meta_path}: {e}")
            return None


def get_clawhub_client_di(request: Request) -> ClawHubClient:
    """FastAPI 依賴注入：從 app.state 取得 ClawHubClient"""
    return request.app.state.clawhub_client
