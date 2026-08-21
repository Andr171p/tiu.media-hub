from fastapi import status


class AppError(Exception):
    """Базовое исключение для создания иерархии ошибок."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_SERVER_ERROR"

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: int | str | None = None,
    ) -> None:
        if status_code:
            self.status_code = status_code
        if error_code:
            self.error_code = error_code

        super().__init__(message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND_ERROR"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT_ERROR"
