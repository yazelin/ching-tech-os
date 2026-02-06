"""本機檔案服務

透過 NAS 掛載路徑存取檔案，取代系統功能中的 SMB 連線。
僅用於知識庫、專案、Line Bot 等系統功能，檔案總管仍使用 SMBService。
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import settings


class LocalFileError(Exception):
    """本機檔案操作錯誤"""
    pass


class LocalFileService:
    """本機檔案服務

    提供透過 NAS 掛載路徑存取檔案的功能。
    """

    def __init__(self, base_path: str):
        """初始化服務

        Args:
            base_path: 基礎路徑（如 /mnt/nas/ching-tech-os/knowledge）
        """
        self.base_path = Path(base_path)

    def _full_path(self, path: str) -> Path:
        """取得完整路徑"""
        # 移除開頭的斜線
        clean_path = path.lstrip("/")
        return self.base_path / clean_path

    def _ensure_mount(self) -> None:
        """確保 NAS 已掛載

        檢查 base_path 是否在某個已掛載的 NAS 路徑下。
        支援多個掛載點的架構（如 /mnt/nas/ctos 和 /mnt/nas/projects）。
        """
        # 檢查 base_path 或其父目錄是否為掛載點
        path = self.base_path
        while path != Path("/"):
            if path.is_mount():
                return  # 找到掛載點，確認已掛載
            path = path.parent

        # 沒有找到掛載點，檢查目錄是否存在且可存取
        if not self.base_path.exists():
            raise LocalFileError(f"NAS 路徑不存在：{self.base_path}")

        # 嘗試列出目錄內容來確認可存取
        try:
            list(self.base_path.iterdir())
        except PermissionError:
            raise LocalFileError(f"無法存取 NAS 路徑：{self.base_path}")

    def read_file(self, path: str) -> bytes:
        """讀取檔案內容

        Args:
            path: 檔案路徑（相對於 base_path）

        Returns:
            檔案內容（bytes）
        """
        self._ensure_mount()
        full_path = self._full_path(path)

        try:
            with open(full_path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            raise LocalFileError(f"檔案不存在：{path}")
        except PermissionError:
            raise LocalFileError(f"無權限讀取檔案：{path}")
        except IOError as e:
            raise LocalFileError(f"讀取檔案失敗：{e}")

    def write_file(self, path: str, data: bytes) -> None:
        """寫入檔案內容

        Args:
            path: 檔案路徑（相對於 base_path）
            data: 檔案內容
        """
        self._ensure_mount()
        full_path = self._full_path(path)

        try:
            # 確保目錄存在
            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, "wb") as f:
                f.write(data)
        except PermissionError:
            raise LocalFileError(f"無權限寫入檔案：{path}")
        except IOError as e:
            raise LocalFileError(f"寫入檔案失敗：{e}")

    def delete_file(self, path: str) -> None:
        """刪除檔案

        Args:
            path: 檔案路徑（相對於 base_path）
        """
        self._ensure_mount()
        full_path = self._full_path(path)

        try:
            if full_path.is_file():
                full_path.unlink()
            elif full_path.is_dir():
                raise LocalFileError(f"路徑是目錄，請使用 delete_directory：{path}")
            else:
                raise LocalFileError(f"檔案不存在：{path}")
        except PermissionError:
            raise LocalFileError(f"無權限刪除檔案：{path}")
        except IOError as e:
            raise LocalFileError(f"刪除檔案失敗：{e}")

    def delete_directory(self, path: str, recursive: bool = False) -> None:
        """刪除目錄

        Args:
            path: 目錄路徑（相對於 base_path）
            recursive: 是否遞迴刪除
        """
        self._ensure_mount()
        full_path = self._full_path(path)

        try:
            if not full_path.is_dir():
                raise LocalFileError(f"目錄不存在：{path}")

            if recursive:
                shutil.rmtree(full_path)
            else:
                full_path.rmdir()  # 只能刪除空目錄
        except OSError as e:
            if "not empty" in str(e).lower():
                raise LocalFileError(f"目錄不是空的，請使用 recursive=True：{path}")
            raise LocalFileError(f"刪除目錄失敗：{e}")
        except PermissionError:
            raise LocalFileError(f"無權限刪除目錄：{path}")

    def create_directory(self, path: str) -> None:
        """建立目錄

        Args:
            path: 目錄路徑（相對於 base_path）
        """
        self._ensure_mount()
        full_path = self._full_path(path)

        try:
            full_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise LocalFileError(f"無權限建立目錄：{path}")
        except IOError as e:
            raise LocalFileError(f"建立目錄失敗：{e}")

    def exists(self, path: str) -> bool:
        """檢查路徑是否存在

        Args:
            path: 檔案或目錄路徑（相對於 base_path）

        Returns:
            是否存在
        """
        self._ensure_mount()
        return self._full_path(path).exists()

    def is_file(self, path: str) -> bool:
        """檢查是否為檔案

        Args:
            path: 路徑（相對於 base_path）

        Returns:
            是否為檔案
        """
        self._ensure_mount()
        return self._full_path(path).is_file()

    def is_directory(self, path: str) -> bool:
        """檢查是否為目錄

        Args:
            path: 路徑（相對於 base_path）

        Returns:
            是否為目錄
        """
        self._ensure_mount()
        return self._full_path(path).is_dir()

    def list_directory(self, path: str = "") -> list[dict[str, Any]]:
        """列出目錄內容

        Args:
            path: 目錄路徑（相對於 base_path）

        Returns:
            檔案/目錄列表
        """
        self._ensure_mount()
        full_path = self._full_path(path) if path else self.base_path

        if not full_path.is_dir():
            raise LocalFileError(f"目錄不存在：{path}")

        items = []
        try:
            for item in full_path.iterdir():
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": stat.st_size if item.is_file() else None,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
        except PermissionError:
            raise LocalFileError(f"無權限存取目錄：{path}")

        return items

    def copy_file(self, src_path: str, dest_path: str) -> None:
        """複製檔案

        Args:
            src_path: 來源路徑（相對於 base_path）
            dest_path: 目標路徑（相對於 base_path）
        """
        self._ensure_mount()
        src_full = self._full_path(src_path)
        dest_full = self._full_path(dest_path)

        try:
            # 確保目標目錄存在
            dest_full.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_full, dest_full)
        except FileNotFoundError:
            raise LocalFileError(f"來源檔案不存在：{src_path}")
        except PermissionError:
            raise LocalFileError(f"無權限複製檔案")
        except IOError as e:
            raise LocalFileError(f"複製檔案失敗：{e}")

    def move_file(self, src_path: str, dest_path: str) -> None:
        """移動檔案

        Args:
            src_path: 來源路徑（相對於 base_path）
            dest_path: 目標路徑（相對於 base_path）
        """
        self._ensure_mount()
        src_full = self._full_path(src_path)
        dest_full = self._full_path(dest_path)

        try:
            # 確保目標目錄存在
            dest_full.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_full), str(dest_full))
        except FileNotFoundError:
            raise LocalFileError(f"來源檔案不存在：{src_path}")
        except PermissionError:
            raise LocalFileError(f"無權限移動檔案")
        except IOError as e:
            raise LocalFileError(f"移動檔案失敗：{e}")

    def get_full_path(self, path: str) -> str:
        """取得完整路徑字串

        Args:
            path: 相對路徑

        Returns:
            完整路徑字串
        """
        return str(self._full_path(path))


# 便利函式：建立各功能的服務實例


def create_knowledge_file_service() -> LocalFileService:
    """建立知識庫檔案服務

    Returns:
        LocalFileService 實例
    """
    return LocalFileService(settings.knowledge_local_path)


def create_project_file_service() -> LocalFileService:
    """建立專案檔案服務

    Returns:
        LocalFileService 實例
    """
    return LocalFileService(settings.project_local_path)


def create_linebot_file_service() -> LocalFileService:
    """建立 Line Bot 檔案服務

    Returns:
        LocalFileService 實例
    """
    return LocalFileService(settings.linebot_local_path)


def create_attachments_file_service() -> LocalFileService:
    """建立附件檔案服務

    Returns:
        LocalFileService 實例
    """
    base_path = f"{settings.ctos_mount_path}/attachments"
    return LocalFileService(base_path)


def create_ai_generated_file_service() -> LocalFileService:
    """建立 AI 生成檔案服務

    Returns:
        LocalFileService 實例
    """
    base_path = f"{settings.ctos_mount_path}/ai-generated"
    return LocalFileService(base_path)
