"""檔案 API 資料模型"""

from datetime import datetime

from pydantic import BaseModel


class DirectoryFile(BaseModel):
    """目錄中的檔案項目"""

    name: str
    size: int
    modified_at: datetime


class DirectoryListResponse(BaseModel):
    """目錄列表回應"""

    success: bool = True
    zone: str
    path: str
    dirs: list[str]
    files: list[DirectoryFile]
