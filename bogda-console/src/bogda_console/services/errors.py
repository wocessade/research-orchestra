from __future__ import annotations

from bogda_console.contracts.models import ApiErrorCode


class ServiceError(Exception):
    def __init__(
        self,
        code: ApiErrorCode | str,
        message: str,
        *,
        source: str,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.code = ApiErrorCode(code)
        self.source = source
        self.retryable = retryable


class SourceUnavailable(ServiceError):
    pass
