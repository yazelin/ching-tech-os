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


class FileContentResponse(BaseModel):
    """檔案內容回應（用於文字檔）"""

    content: str
    mime_type: str


class DeleteRequest(BaseModel):
    """刪除請求"""

    path: str
    recursive: bool = False


class RenameRequest(BaseModel):
    """重命名請求"""

    path: str
    new_name: str


class MkdirRequest(BaseModel):
    """建立資料夾請求"""

    path: str


class OperationResponse(BaseModel):
    """操作回應"""

    success: bool
    message: str


class SearchItem(BaseModel):
    """搜尋結果項目"""

    name: str
    path: str
    type: str  # "file" or "directory"


class SearchResponse(BaseModel):
    """搜尋回應"""

    query: str
    path: str
    results: list[SearchItem]
    total: int
