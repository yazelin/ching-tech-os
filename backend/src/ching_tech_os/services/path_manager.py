"""統一路徑管理器

提供統一的路徑格式和轉換邏輯，解決目前路徑格式混亂的問題。

路徑協議：
- ctos://    → CTOS 系統檔案 (/mnt/nas/ctos/)
- shared://  → 公司專案共用區 (/mnt/nas/projects/)
- temp://    → 暫存檔案 (/tmp/ctos/)
- local://   → 本機小檔案 (應用程式 data 目錄)
- nas://     → NAS 共享（透過 SMB 存取，用於檔案管理器）

範例：
- ctos://knowledge/kb-001/file.pdf
- ctos://linebot/groups/C123/images/2026-01-05/abc.jpg
- shared://亦達光學/layout.pdf
- temp://linebot/msg123.pdf
- local://knowledge/images/kb-001-demo.png
- nas://home/photos/image.jpg （檔案管理器瀏覽的 NAS 共享）
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
import re


class StorageZone(Enum):
    """儲存區域"""
    CTOS = "ctos"        # CTOS 系統檔案
    SHARED = "shared"    # 公司專案共用區
    TEMP = "temp"        # 暫存
    LOCAL = "local"      # 本機
    NAS = "nas"          # NAS 共享（透過 SMB，用於檔案管理器）


@dataclass
class ParsedPath:
    """解析後的路徑"""
    zone: StorageZone    # 儲存區域
    path: str            # 相對路徑（不含協議前綴）
    raw: str             # 原始輸入

    def to_uri(self) -> str:
        """轉換為標準 URI 格式"""
        return f"{self.zone.value}://{self.path}"


class PathManager:
    """統一路徑管理器

    用法：
        from ching_tech_os.services.path_manager import path_manager

        # 解析路徑
        parsed = path_manager.parse("nas://knowledge/attachments/kb-001/file.pdf")
        # → ParsedPath(zone=CTOS, path="knowledge/kb-001/file.pdf")

        # 轉換為檔案系統路徑
        fs_path = path_manager.to_filesystem("ctos://knowledge/kb-001/file.pdf")
        # → "/mnt/nas/ctos/knowledge/kb-001/file.pdf"

        # 轉換為 API 路徑
        api_path = path_manager.to_api("ctos://knowledge/kb-001/file.pdf")
        # → "/api/files/ctos/knowledge/kb-001/file.pdf"
    """

    def __init__(self):
        from ..config import settings
        self._settings = settings

        # 掛載點對應
        self._zone_mounts = {
            StorageZone.CTOS: settings.ctos_mount_path,      # /mnt/nas/ctos
            StorageZone.SHARED: settings.projects_mount_path, # /mnt/nas/projects
            StorageZone.TEMP: "/tmp/ctos",
            StorageZone.LOCAL: str(Path(settings.frontend_dir).parent / "data"),
            StorageZone.NAS: None,  # NAS zone 使用 SMB，無本地掛載點
        }

        # 舊格式前綴對應（用於向後相容）
        # 這些是資料庫中可能存在的舊格式
        self._legacy_prefixes = {
            # nas:// 格式
            "nas://knowledge/attachments/": (StorageZone.CTOS, "knowledge/"),
            "nas://knowledge/": (StorageZone.CTOS, "knowledge/"),
            "nas://projects/attachments/": (StorageZone.CTOS, "attachments/"),
            "nas://projects/": (StorageZone.CTOS, "attachments/"),
            "nas://linebot/files/": (StorageZone.CTOS, "linebot/"),
            "nas://linebot/": (StorageZone.CTOS, "linebot/"),
            "nas://ching-tech-os/linebot/files/": (StorageZone.CTOS, "linebot/"),
            # 本機相對路徑
            "../assets/": (StorageZone.LOCAL, "knowledge/"),
        }

        # Line Bot 相對路徑前綴（groups/, users/ 開頭）
        self._linebot_prefixes = ("groups/", "users/", "ai-images/", "pdf-converted/")

        # 系統絕對路徑前綴（用於識別需要轉換的本地檔案路徑）
        # 注意：不包含 /home/，因為檔案管理器的 NAS 共享可能有 /home/ 目錄
        self._system_prefixes = ("/tmp/", "/mnt/")

    def parse(self, path: str) -> ParsedPath:
        """解析路徑，支援新舊格式

        Args:
            path: 輸入路徑（新格式或舊格式）

        Returns:
            ParsedPath 包含 zone 和相對路徑
        """
        if not path:
            raise ValueError("路徑不可為空")

        # 1. 新格式：{protocol}://...
        # 注意：排除 nas://，因為它在舊格式中有特殊意義（向後相容）
        # NAS zone 只用於以 / 開頭的非系統路徑（檔案管理器）
        for zone in StorageZone:
            if zone == StorageZone.NAS:
                continue  # 跳過 NAS zone，讓它在步驟 5 處理
            prefix = f"{zone.value}://"
            if path.startswith(prefix):
                return ParsedPath(
                    zone=zone,
                    path=path[len(prefix):],
                    raw=path
                )

        # 2. 舊格式：nas://... 或 ../assets/...
        for legacy_prefix, (zone, new_prefix) in self._legacy_prefixes.items():
            if path.startswith(legacy_prefix):
                relative = path[len(legacy_prefix):]
                return ParsedPath(
                    zone=zone,
                    path=f"{new_prefix}{relative}",
                    raw=path
                )

        # 3. Line Bot 相對路徑：groups/..., users/..., ai-images/...
        for prefix in self._linebot_prefixes:
            if path.startswith(prefix):
                return ParsedPath(
                    zone=StorageZone.CTOS,
                    path=f"linebot/{path}",
                    raw=path
                )

        # 4. 系統絕對路徑
        if path.startswith(self._system_prefixes):
            # /tmp/... → temp://
            if path.startswith("/tmp/"):
                relative = path[5:]  # 移除 /tmp/
                # 特殊處理 nanobanana 輸出
                if "nanobanana-output/" in relative:
                    filename = relative.split("nanobanana-output/")[-1]
                    return ParsedPath(
                        zone=StorageZone.TEMP,
                        path=f"ai-generated/{filename}",
                        raw=path
                    )
                # 特殊處理 linebot-files
                if relative.startswith("linebot-files/"):
                    return ParsedPath(
                        zone=StorageZone.TEMP,
                        path=f"linebot/{relative[14:]}",
                        raw=path
                    )
                return ParsedPath(
                    zone=StorageZone.TEMP,
                    path=relative,
                    raw=path
                )

            # /mnt/nas/ctos/... → ctos://
            if path.startswith(self._settings.ctos_mount_path):
                relative = path[len(self._settings.ctos_mount_path):].lstrip("/")
                return ParsedPath(
                    zone=StorageZone.CTOS,
                    path=relative,
                    raw=path
                )

            # /mnt/nas/projects/... → shared://
            if path.startswith(self._settings.projects_mount_path):
                relative = path[len(self._settings.projects_mount_path):].lstrip("/")
                return ParsedPath(
                    zone=StorageZone.SHARED,
                    path=relative,
                    raw=path
                )

            # 其他 /mnt/nas/... 路徑，嘗試解析
            if path.startswith(self._settings.nas_mount_path):
                relative = path[len(self._settings.nas_mount_path):].lstrip("/")
                return ParsedPath(
                    zone=StorageZone.CTOS,
                    path=relative,
                    raw=path
                )

        # 5. 以 / 開頭但不是系統路徑 → nas://（檔案管理器的 NAS 共享路徑）
        # 例如：/home/file.jpg, /公司檔案/doc.pdf, /擎添共用區/在案資料分享/xxx
        if path.startswith("/") and not path.startswith(self._system_prefixes):
            return ParsedPath(
                zone=StorageZone.NAS,
                path=path.lstrip("/"),
                raw=path
            )

        # 6. 純相對路徑（無法判斷 zone）
        # 預設放在 CTOS
        return ParsedPath(
            zone=StorageZone.CTOS,
            path=path,
            raw=path
        )

    def to_filesystem(self, path: str) -> str:
        """轉換為實際檔案系統路徑

        Args:
            path: 輸入路徑（任何格式）

        Returns:
            實際的檔案系統絕對路徑

        Raises:
            ValueError: NAS zone 無法轉換為本地路徑
        """
        parsed = self.parse(path)
        mount_path = self._zone_mounts[parsed.zone]

        # NAS zone 使用 SMB，無本地掛載點
        if mount_path is None:
            raise ValueError(f"NAS zone 路徑無法轉換為本地檔案系統路徑: {path}")

        return f"{mount_path}/{parsed.path}"

    def to_api(self, path: str) -> str:
        """轉換為前端 API 路徑

        Args:
            path: 輸入路徑（任何格式）

        Returns:
            API 路徑，如 /api/files/ctos/knowledge/kb-001/file.pdf
        """
        parsed = self.parse(path)
        return f"/api/files/{parsed.zone.value}/{parsed.path}"

    def to_storage(self, path: str) -> str:
        """轉換為資料庫儲存格式（標準化 URI）

        Args:
            path: 輸入路徑（任何格式）

        Returns:
            標準化的 URI 格式，如 ctos://knowledge/kb-001/file.pdf
        """
        parsed = self.parse(path)
        return parsed.to_uri()

    def from_legacy(self, path: str) -> str:
        """從舊格式轉換為新格式

        這是 to_storage 的別名，用於語意更清楚的場景。
        """
        return self.to_storage(path)

    def exists(self, path: str) -> bool:
        """檢查檔案是否存在

        Args:
            path: 輸入路徑（任何格式）

        Returns:
            檔案是否存在

        Note:
            NAS zone 無法直接檢查，需要透過 SMB 連線
        """
        parsed = self.parse(path)
        if parsed.zone == StorageZone.NAS:
            # NAS zone 無法直接檢查，回傳 True（由 API 層處理實際檢查）
            return True
        fs_path = self.to_filesystem(path)
        return Path(fs_path).exists()

    def get_zone(self, path: str) -> StorageZone:
        """取得路徑的儲存區域

        Args:
            path: 輸入路徑（任何格式）

        Returns:
            StorageZone enum
        """
        return self.parse(path).zone

    def is_readonly(self, path: str) -> bool:
        """檢查路徑是否為唯讀

        Args:
            path: 輸入路徑（任何格式）

        Returns:
            是否為唯讀（shared:// 和 nas:// 區域為唯讀）
        """
        zone = self.get_zone(path)
        return zone in (StorageZone.SHARED, StorageZone.NAS)


# 全域單例
path_manager = PathManager()
