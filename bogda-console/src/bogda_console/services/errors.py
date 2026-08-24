from __future__ import annotations

from bogda_console.contracts.models import ApiErrorCode, ApiErrorDetails


class ServiceError(Exception):
    def __init__(
        self,
        code: ApiErrorCode | str,
        message: str,
        *,
        source: str,
        retryable: bool,
        status_code: int = 500,
        details: ApiErrorDetails | None = None,
    ) -> None:
        super().__init__(message)
        self.code = ApiErrorCode(code)
        self.source = source
        self.retryable = retryable
        self.status_code = status_code
        self.details = details


class SourceUnavailable(ServiceError):
    pass
