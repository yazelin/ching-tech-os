"""SMB 連線服務"""

import uuid
from datetime import datetime
from typing import Any

from smbprotocol.connection import Connection
from smbprotocol.session import Session
from smbprotocol.tree import TreeConnect
from smbprotocol.file_info import FileAttributes
from smbprotocol.open import (
    Open,
    CreateDisposition,
    CreateOptions,
    DirectoryAccessMask,
    FileInformationClass,
    ImpersonationLevel,
    ShareAccess,
)

from ..config import settings


class SMBError(Exception):
    """SMB 操作錯誤"""

    pass


class SMBAuthError(SMBError):
    """SMB 認證錯誤"""

    pass


class SMBConnectionError(SMBError):
    """SMB 連線錯誤"""

    pass


class SMBService:
    """SMB 服務

    提供 NAS SMB 操作功能，包括認證、列出共享資料夾、瀏覽資料夾等。
    """

    def __init__(
        self, host: str, username: str, password: str, port: int | None = None
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port = port or settings.nas_port
        self._connection: Connection | None = None
        self._session: Session | None = None

    def _connect(self) -> None:
        """建立 SMB 連線"""
        try:
            self._connection = Connection(uuid.uuid4(), self.host, self.port)
            self._connection.connect()
        except Exception as e:
            raise SMBConnectionError(f"無法連線至檔案伺服器 {self.host}") from e

    def _authenticate(self) -> None:
        """進行 SMB 認證"""
        if self._connection is None:
            raise SMBConnectionError("尚未建立連線")

        try:
            self._session = Session(self._connection, self.username, self.password)
            self._session.connect()
        except Exception as e:
            error_msg = str(e).lower()
            if "logon" in error_msg or "password" in error_msg or "auth" in error_msg:
                raise SMBAuthError("帳號或密碼錯誤") from e
            raise SMBError(f"認證失敗：{e}") from e

    def _disconnect(self) -> None:
        """關閉 SMB 連線"""
        if self._session is not None:
            try:
                self._session.disconnect()
            except Exception:
                pass
            self._session = None

        if self._connection is not None:
            try:
                self._connection.disconnect()
            except Exception:
                pass
            self._connection = None

    def __enter__(self):
        self._connect()
        self._authenticate()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._disconnect()
        return False

    def test_auth(self) -> bool:
        """測試認證是否成功

        Returns:
            True 表示認證成功
        """
        try:
            self._connect()
            self._authenticate()
            return True
        finally:
            self._disconnect()

    def list_shares(self) -> list[dict[str, str]]:
        """列出共享資料夾

        Returns:
            共享資料夾列表，每個項目包含 name 和 type
        """
        if self._session is None:
            raise SMBError("尚未認證")

        shares = []
        try:
            # 連接到 IPC$ 來列出共享
            tree = TreeConnect(self._session, rf"\\{self.host}\IPC$")
            tree.connect()

            # 使用 srvsvc 介面列出共享
            # 由於 smbprotocol 沒有直接的方式，我們使用較簡單的方法
            # 嘗試連接已知的共享名稱或使用其他方式
            tree.disconnect()

            # 改用另一種方式：嘗試常見的共享名稱
            common_shares = ["home", "homes", "public", "共用資料夾", "公用資料夾"]
            for share_name in common_shares:
                try:
                    test_tree = TreeConnect(
                        self._session, rf"\\{self.host}\{share_name}"
                    )
                    test_tree.connect()
                    shares.append({"name": share_name, "type": "disk"})
                    test_tree.disconnect()
                except Exception:
                    pass

        except Exception as e:
            raise SMBError(f"列出共享資料夾失敗：{e}") from e

        return shares

    def browse_directory(self, share_name: str, path: str = "") -> list[dict[str, Any]]:
        """瀏覽資料夾內容

        Args:
            share_name: 共享資料夾名稱
            path: 資料夾路徑（相對於共享根目錄）

        Returns:
            檔案/資料夾列表
        """
        if self._session is None:
            raise SMBError("尚未認證")

        items = []
        tree = None

        try:
            tree = TreeConnect(self._session, rf"\\{self.host}\{share_name}")
            tree.connect()

            # 正規化路徑
            dir_path = path.strip("/").replace("/", "\\") if path else ""

            dir_open = Open(tree, dir_path or "")
            dir_open.create(
                ImpersonationLevel.Impersonation,
                DirectoryAccessMask.FILE_LIST_DIRECTORY
                | DirectoryAccessMask.FILE_READ_ATTRIBUTES,
                FileAttributes.FILE_ATTRIBUTE_DIRECTORY,
                ShareAccess.FILE_SHARE_READ,
                CreateDisposition.FILE_OPEN,
                CreateOptions.FILE_DIRECTORY_FILE,
            )

            # 列出目錄內容
            entries = dir_open.query_directory(
                "*", FileInformationClass.FILE_ID_BOTH_DIRECTORY_INFORMATION
            )

            for entry in entries:
                name = entry["file_name"].get_value()
                if name in (".", ".."):
                    continue

                attributes = entry["file_attributes"].get_value()
                is_directory = bool(attributes & FileAttributes.FILE_ATTRIBUTE_DIRECTORY)

                # 取得檔案大小和修改時間
                size = entry.get("end_of_file", {})
                if hasattr(size, "get_value"):
                    size = size.get_value()
                else:
                    size = 0

                # 修改時間
                change_time = entry.get("last_write_time", {})
                if hasattr(change_time, "get_value"):
                    # SMB 時間戳是 Windows FILETIME 格式
                    filetime = change_time.get_value()
                    # 轉換為 datetime
                    if filetime > 0:
                        # FILETIME 是從 1601-01-01 開始的 100 奈秒單位
                        seconds = (filetime - 116444736000000000) / 10000000
                        try:
                            modified = datetime.fromtimestamp(seconds)
                        except (ValueError, OSError):
                            modified = None
                    else:
                        modified = None
                else:
                    modified = None

                items.append(
                    {
                        "name": name,
                        "type": "directory" if is_directory else "file",
                        "size": size if not is_directory else None,
                        "modified": modified.isoformat() if modified else None,
                    }
                )

            dir_open.close()

        except Exception as e:
            error_msg = str(e).lower()
            if "access" in error_msg or "denied" in error_msg:
                raise SMBError("無權限存取此資料夾") from e
            raise SMBError(f"瀏覽資料夾失敗：{e}") from e
        finally:
            if tree is not None:
                try:
                    tree.disconnect()
                except Exception:
                    pass

        return items


def create_smb_service(
    username: str, password: str, host: str | None = None
) -> SMBService:
    """建立 SMB 服務實例

    Args:
        username: 使用者帳號
        password: 使用者密碼
        host: NAS 主機位址（預設使用設定檔的值）

    Returns:
        SMBService 實例
    """
    return SMBService(
        host=host or settings.nas_host,
        username=username,
        password=password,
    )
