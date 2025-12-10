"""NAS 相關資料模型"""

from pydantic import BaseModel


class ShareInfo(BaseModel):
    """共享資料夾資訊"""

    name: str
    type: str = "disk"


class SharesResponse(BaseModel):
    """共享資料夾列表回應"""

    shares: list[ShareInfo]


class FileItem(BaseModel):
    """檔案/資料夾項目"""

    name: str
    type: str  # "file" or "directory"
    size: int | None = None
    modified: str | None = None


class BrowseResponse(BaseModel):
    """瀏覽資料夾回應"""

    path: str
    items: list[FileItem]
