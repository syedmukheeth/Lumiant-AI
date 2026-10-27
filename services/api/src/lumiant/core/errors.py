"""Safe error model: clients get a code, a human message and the request id — never internals."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from lumiant.core.logging import request_id_var

log = logging.getLogger("lumiant.errors")


class AppError(Exception):
    """An error whose code and message are safe to show to the client."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class NotAuthenticatedError(AppError):
    def __init__(self, message: str = "Sign in to continue.") -> None:
        super().__init__("not_authenticated", message, 401)


class ForbiddenError(AppError):
    def __init__(self, code: str = "forbidden", message: str = "You do not have access to this.") -> None:
        super().__init__(code, message, 403)


class NotFoundError(AppError):
    def __init__(self, code: str = "not_found", message: str = "Not found.") -> None:
        super().__init__(code, message, 404)


def error_body(code: str, message: str, details: list[dict[str, object]] | None = None) -> dict[str, object]:
    error: dict[str, object] = {"code": code, "message": message, "request_id": request_id_var.get()}
    if details:
        error["details"] = details
    return {"error": error}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Echo only the location and a generic message; never the submitted value.
        details: list[dict[str, object]] = [
            {"loc": [str(p) for p in err.get("loc", ())], "type": str(err.get("type", "invalid"))}
            for err in exc.errors()[:20]
        ]
        return JSONResponse(error_body("invalid_request", "The request is not valid.", details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        message = "Not found." if exc.status_code == 404 else "Request not allowed."
        return JSONResponse(error_body(code, message), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", extra={"error_type": type(exc).__name__})
        return JSONResponse(
            error_body("internal_error", "Something went wrong. Quote the request id when reporting it."),
            status_code=500,
        )
