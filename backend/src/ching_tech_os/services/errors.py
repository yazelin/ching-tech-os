"""統一錯誤層級

所有服務層錯誤的基底類別，搭配 FastAPI 全域 exception handler 使用。
既有的領域錯誤（KnowledgeError、SMBError 等）可漸進改為繼承 ServiceError。
"""


class ServiceError(Exception):
    """服務層基底錯誤

    Attributes:
        message: 人類可讀的錯誤訊息
        code: 機器可讀的錯誤代碼（如 NOT_FOUND、PERMISSION_DENIED）
        status_code: HTTP 狀態碼（用於全域 exception handler）
    """

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(ServiceError):
    """資源不存在"""

    def __init__(self, resource: str, identifier: str | None = None):
        detail = f"{resource} 不存在"
        if identifier:
            detail = f"{resource} 不存在: {identifier}"
        super().__init__(detail, "NOT_FOUND", 404)


class PermissionDeniedError(ServiceError):
    """權限不足"""

    def __init__(self, message: str = "權限不足"):
        super().__init__(message, "PERMISSION_DENIED", 403)


class ValidationError(ServiceError):
    """驗證錯誤"""

    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR", 422)


class ExternalServiceError(ServiceError):
    """外部服務錯誤"""

    def __init__(self, service: str, message: str):
        super().__init__(f"{service}: {message}", "EXTERNAL_ERROR", 502)


class ConflictError(ServiceError):
    """資源衝突（重複等）"""

    def __init__(self, message: str):
        super().__init__(message, "CONFLICT", 409)
