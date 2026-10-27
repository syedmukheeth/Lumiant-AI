"""Per-request id, timing, access log and security headers."""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from lumiant.core.logging import request_id_var, tenant_id_var, user_id_var

log = logging.getLogger("lumiant.request")

_INBOUND_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
# The interactive API docs need scripts/styles from the FastAPI bundle; they are disabled in production.
_DOCS_PATHS = ("/api/docs", "/api/openapi.json")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        inbound = request.headers.get("x-request-id", "")
        request_id = inbound if _INBOUND_ID.match(inbound) else uuid.uuid4().hex
        tokens = (request_id_var.set(request_id), user_id_var.set(None), tenant_id_var.set(None))
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": duration_ms,
                },
            )
            request_id_var.reset(tokens[0])
            user_id_var.reset(tokens[1])
            tenant_id_var.reset(tokens[2])
        response.headers["X-Request-ID"] = request_id
        for name, value in SECURITY_HEADERS.items():
            if name == "Content-Security-Policy" and request.url.path.startswith(_DOCS_PATHS):
                continue
            response.headers.setdefault(name, value)
        return response
