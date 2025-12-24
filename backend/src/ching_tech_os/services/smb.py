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
    FilePipePrinterAccessMask,
    FileInformationClass,
    ImpersonationLevel,
    ShareAccess,
)
# 高階 API（用於 rename、delete、search 等操作）
from smbclient import (
    register_session,
    rename as smb_rename,
    remove as smb_remove,
    rmdir as smb_rmdir,
    listdir as smb_listdir,
    stat as smb_stat,
    walk as smb_walk,
)
import fnmatch
import stat as stat_module

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

        使用 smbclient 命令動態列出 NAS 上所有可用的共享資料夾。

        Returns:
            共享資料夾列表，每個項目包含 name 和 type
        """
        import subprocess

        shares = []
        try:
            # 使用 smbclient -L 列出共享（比 smbprotocol 更完整）
            result = subprocess.run(
                [
                    "smbclient",
                    "-L",
                    f"//{self.host}",
                    "-U",
                    f"{self.username}%{self.password}",
                    "-g",  # 機器可讀格式：type|name|comment
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                raise SMBError(f"無法列出共享：{result.stderr}")

            # 解析輸出格式：Disk|sharename|comment
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) >= 2:
                    share_type = parts[0].lower()
                    share_name = parts[1]
                    # 只列出 Disk 類型，跳過 IPC$ 等
                    if share_type == "disk" and not share_name.endswith("$"):
                        shares.append({"name": share_name, "type": "disk"})

        except subprocess.TimeoutExpired:
            raise SMBError("列出共享資料夾逾時")
        except FileNotFoundError:
            raise SMBError("系統未安裝 smbclient，請安裝 samba-client 套件")
        except Exception as e:
            if isinstance(e, SMBError):
                raise
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
                name_raw = entry["file_name"].get_value()
                # Handle both string and bytes (UTF-16-LE encoded)
                if isinstance(name_raw, bytes):
                    name = name_raw.decode("utf-16-le").rstrip("\x00")
                else:
                    name = str(name_raw)
                if name in (".", ".."):
                    continue

                attributes = entry["file_attributes"].get_value()
                is_directory = bool(attributes & FileAttributes.FILE_ATTRIBUTE_DIRECTORY)

                # 取得檔案大小和修改時間
                try:
                    size = entry["end_of_file"].get_value()
                except (KeyError, AttributeError):
                    size = 0

                # 修改時間
                try:
                    last_write = entry["last_write_time"].get_value()
                    # smbprotocol 可能返回 datetime 或 FILETIME 整數
                    if isinstance(last_write, datetime):
                        modified = last_write
                    elif isinstance(last_write, int) and last_write > 0:
                        # FILETIME 是從 1601-01-01 開始的 100 奈秒單位
                        seconds = (last_write - 116444736000000000) / 10000000
                        modified = datetime.fromtimestamp(seconds)
                    else:
                        modified = None
                except (KeyError, AttributeError, ValueError, OSError):
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

    def read_file(self, share_name: str, path: str) -> bytes:
        """讀取檔案內容

        Args:
            share_name: 共享資料夾名稱
            path: 檔案路徑（相對於共享根目錄）

        Returns:
            檔案內容（bytes）
        """
        if self._session is None:
            raise SMBError("尚未認證")

        tree = None
        try:
            tree = TreeConnect(self._session, rf"\\{self.host}\{share_name}")
            tree.connect()

            # 正規化路徑
            file_path = path.strip("/").replace("/", "\\")

            file_open = Open(tree, file_path)
            file_open.create(
                ImpersonationLevel.Impersonation,
                FilePipePrinterAccessMask.FILE_READ_DATA | FilePipePrinterAccessMask.FILE_READ_ATTRIBUTES,
                FileAttributes.FILE_ATTRIBUTE_NORMAL,
                ShareAccess.FILE_SHARE_READ,
                CreateDisposition.FILE_OPEN,
                CreateOptions.FILE_NON_DIRECTORY_FILE,
            )

            # 讀取檔案內容（分段讀取以避免 SMB credit 限制）
            file_size = file_open.end_of_file
            chunk_size = 65536  # 64KB per read
            chunks = []
            offset = 0

            while offset < file_size:
                read_size = min(chunk_size, file_size - offset)
                chunk = file_open.read(offset, read_size)
                chunks.append(chunk)
                offset += read_size

            file_open.close()

            return b"".join(chunks)

        except Exception as e:
            error_msg = str(e).lower()
            if "access" in error_msg or "denied" in error_msg:
                raise SMBError("無權限讀取此檔案") from e
            if "not found" in error_msg or "no such" in error_msg:
                raise SMBError("檔案不存在") from e
            raise SMBError(f"讀取檔案失敗：{e}") from e
        finally:
            if tree is not None:
                try:
                    tree.disconnect()
                except Exception:
                    pass

    def write_file(self, share_name: str, path: str, data: bytes) -> None:
        """寫入檔案內容（支援大檔案分塊寫入）

        Args:
            share_name: 共享資料夾名稱
            path: 檔案路徑（相對於共享根目錄）
            data: 檔案內容
        """
        if self._session is None:
            raise SMBError("尚未認證")

        tree = None
        try:
            tree = TreeConnect(self._session, rf"\\{self.host}\{share_name}")
            tree.connect()

            # 正規化路徑
            file_path = path.strip("/").replace("/", "\\")

            file_open = Open(tree, file_path)
            file_open.create(
                ImpersonationLevel.Impersonation,
                FilePipePrinterAccessMask.FILE_WRITE_DATA | FilePipePrinterAccessMask.FILE_WRITE_ATTRIBUTES,
                FileAttributes.FILE_ATTRIBUTE_NORMAL,
                ShareAccess.FILE_SHARE_WRITE,
                CreateDisposition.FILE_OVERWRITE_IF,  # 覆寫或建立
                CreateOptions.FILE_NON_DIRECTORY_FILE,
            )

            # 分塊寫入（SMB 最大寫入大小約 8MB，使用 4MB 確保安全）
            chunk_size = 4 * 1024 * 1024  # 4MB
            offset = 0
            while offset < len(data):
                chunk = data[offset:offset + chunk_size]
                file_open.write(chunk, offset)
                offset += len(chunk)

            file_open.close()

        except Exception as e:
            error_msg = str(e).lower()
            if "access" in error_msg or "denied" in error_msg:
                raise SMBError("無權限寫入此檔案") from e
            raise SMBError(f"寫入檔案失敗：{e}") from e
        finally:
            if tree is not None:
                try:
                    tree.disconnect()
                except Exception:
                    pass

    def delete_item(self, share_name: str, path: str, recursive: bool = False) -> None:
        """刪除檔案或資料夾（使用高階 API）

        Args:
            share_name: 共享資料夾名稱
            path: 檔案/資料夾路徑
            recursive: 是否遞迴刪除（用於非空資料夾）
        """
        if self._session is None:
            raise SMBError("尚未認證")

        # 註冊 session（高階 API 使用）
        register_session(self.host, username=self.username, password=self.password)

        # 建立 UNC 路徑
        item_path = path.strip("/").replace("/", "\\")
        unc_path = rf"\\{self.host}\{share_name}\{item_path}"

        try:
            # 使用 stat 判斷是檔案還是資料夾
            import stat
            file_stat = smb_stat(unc_path)
            is_directory = stat.S_ISDIR(file_stat.st_mode)

            if is_directory:
                if recursive:
                    # 遞迴刪除資料夾內容
                    self._delete_directory_recursive_high_level(share_name, item_path)
                else:
                    # 嘗試直接刪除（如果是空資料夾）
                    smb_rmdir(unc_path)
            else:
                # 刪除檔案
                smb_remove(unc_path)

        except FileNotFoundError:
            raise SMBError("檔案或資料夾不存在")
        except OSError as e:
            error_msg = str(e).lower()
            if "access" in error_msg or "denied" in error_msg or "permission" in error_msg:
                raise SMBError("無權限刪除此項目") from e
            if "not empty" in error_msg or "directory not empty" in error_msg:
                raise SMBError("資料夾不是空的，請使用遞迴刪除") from e
            raise SMBError(f"刪除失敗：{e}") from e
        except Exception as e:
            raise SMBError(f"刪除失敗：{e}") from e

    def _delete_directory_recursive_high_level(self, share_name: str, dir_path: str) -> None:
        """遞迴刪除資料夾（使用高階 API）"""
        import stat
        unc_base = rf"\\{self.host}\{share_name}"
        unc_path = rf"{unc_base}\{dir_path}"

        # 列出目錄內容並刪除
        for item_name in smb_listdir(unc_path):
            if item_name in (".", ".."):
                continue
            item_unc = rf"{unc_path}\{item_name}"
            item_stat = smb_stat(item_unc)

            if stat.S_ISDIR(item_stat.st_mode):
                # 遞迴刪除子資料夾
                sub_path = rf"{dir_path}\{item_name}"
                self._delete_directory_recursive_high_level(share_name, sub_path)
            else:
                # 刪除檔案
                smb_remove(item_unc)

        # 刪除空資料夾
        smb_rmdir(unc_path)

    def rename_item(self, share_name: str, old_path: str, new_name: str) -> None:
        """重命名檔案或資料夾（使用高階 API）

        Args:
            share_name: 共享資料夾名稱
            old_path: 原始路徑
            new_name: 新名稱（只是名稱，不含路徑）
        """
        if self._session is None:
            raise SMBError("尚未認證")

        # 註冊 session（高階 API 使用）
        register_session(self.host, username=self.username, password=self.password)

        # 正規化路徑
        old_path_normalized = old_path.strip("/").replace("/", "\\")

        # 計算新路徑（同一資料夾下）
        if "\\" in old_path_normalized:
            parent_dir = old_path_normalized.rsplit("\\", 1)[0]
            new_path_normalized = f"{parent_dir}\\{new_name}"
        else:
            new_path_normalized = new_name

        # 建立 UNC 路徑
        old_unc = rf"\\{self.host}\{share_name}\{old_path_normalized}"
        new_unc = rf"\\{self.host}\{share_name}\{new_path_normalized}"

        try:
            smb_rename(old_unc, new_unc)
        except FileNotFoundError:
            raise SMBError("檔案或資料夾不存在")
        except FileExistsError:
            raise SMBError("目標名稱已存在")
        except OSError as e:
            error_msg = str(e).lower()
            if "access" in error_msg or "denied" in error_msg or "permission" in error_msg:
                raise SMBError("無權限重命名此項目") from e
            if "exist" in error_msg:
                raise SMBError("目標名稱已存在") from e
            raise SMBError(f"重命名失敗：{e}") from e
        except Exception as e:
            raise SMBError(f"重命名失敗：{e}") from e

    def create_directory(self, share_name: str, path: str) -> None:
        """建立資料夾

        Args:
            share_name: 共享資料夾名稱
            path: 資料夾路徑
        """
        if self._session is None:
            raise SMBError("尚未認證")

        tree = None
        try:
            tree = TreeConnect(self._session, rf"\\{self.host}\{share_name}")
            tree.connect()

            # 正規化路徑
            dir_path = path.strip("/").replace("/", "\\")

            dir_open = Open(tree, dir_path)
            dir_open.create(
                ImpersonationLevel.Impersonation,
                DirectoryAccessMask.FILE_ADD_SUBDIRECTORY,
                FileAttributes.FILE_ATTRIBUTE_DIRECTORY,
                ShareAccess.FILE_SHARE_READ,
                CreateDisposition.FILE_CREATE,  # 只建立新的
                CreateOptions.FILE_DIRECTORY_FILE,
            )
            dir_open.close()

        except Exception as e:
            error_msg = str(e).lower()
            if "access" in error_msg or "denied" in error_msg:
                raise SMBError("無權限建立資料夾") from e
            if "exist" in error_msg:
                raise SMBError("資料夾已存在") from e
            raise SMBError(f"建立資料夾失敗：{e}") from e
        finally:
            if tree is not None:
                try:
                    tree.disconnect()
                except Exception:
                    pass

    def search_files(
        self,
        share_name: str,
        path: str,
        query: str,
        max_depth: int = 3,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """搜尋檔案和資料夾

        Args:
            share_name: 共享資料夾名稱
            path: 起始搜尋路徑
            query: 搜尋關鍵字（支援萬用字元 * 和 ?）
            max_depth: 最大搜尋深度（預設 3 層）
            max_results: 最大結果數量（預設 100）

        Returns:
            符合條件的檔案/資料夾列表
        """
        if self._session is None:
            raise SMBError("尚未認證")

        # 註冊 session（高階 API 使用）
        register_session(self.host, username=self.username, password=self.password)

        # 建立 UNC 路徑
        path_normalized = path.strip("/").replace("/", "\\")
        if path_normalized:
            unc_root = rf"\\{self.host}\{share_name}\{path_normalized}"
            base_path = path_normalized
        else:
            unc_root = rf"\\{self.host}\{share_name}"
            base_path = ""

        # 如果 query 不包含萬用字元，自動加上 *query*
        if "*" not in query and "?" not in query:
            query = f"*{query}*"

        results: list[dict[str, Any]] = []

        try:
            for dirpath, dirnames, filenames in smb_walk(unc_root):
                # 計算當前深度
                rel_dir = dirpath.replace(unc_root, "").strip("\\")
                current_depth = len(rel_dir.split("\\")) if rel_dir else 0

                if current_depth > max_depth:
                    # 清空 dirnames 以停止往下遍歷
                    dirnames.clear()
                    continue

                # 計算相對路徑前綴
                if base_path and rel_dir:
                    path_prefix = f"{base_path}\\{rel_dir}"
                elif rel_dir:
                    path_prefix = rel_dir
                else:
                    path_prefix = base_path

                # 搜尋資料夾
                for dirname in dirnames:
                    if fnmatch.fnmatch(dirname.lower(), query.lower()):
                        item_path = f"{path_prefix}\\{dirname}" if path_prefix else dirname
                        results.append({
                            "name": dirname,
                            "path": "/" + item_path.replace("\\", "/"),
                            "type": "directory",
                        })
                        if len(results) >= max_results:
                            return results

                # 搜尋檔案
                for filename in filenames:
                    if fnmatch.fnmatch(filename.lower(), query.lower()):
                        item_path = f"{path_prefix}\\{filename}" if path_prefix else filename
                        results.append({
                            "name": filename,
                            "path": "/" + item_path.replace("\\", "/"),
                            "type": "file",
                        })
                        if len(results) >= max_results:
                            return results

        except FileNotFoundError:
            raise SMBError("搜尋路徑不存在")
        except Exception as e:
            raise SMBError(f"搜尋失敗：{e}") from e

        return results


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
