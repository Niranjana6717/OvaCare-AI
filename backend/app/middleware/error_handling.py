"""
Global exception handling (requirement #36): the client never sees a raw
stack trace or internal exception message. Real details go to the server
log only, tagged with a request id the client also receives, so a support
conversation can correlate them without exposing internals.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("ovacare.errors")

GENERIC_MESSAGE = "Something went wrong. Please try again."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Validation errors ARE safe to return — they describe the client's
        # own input, not internal state — but are normalized to a stable shape.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Invalid input.", "errors": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        # Raised deliberately by our own code (401/403/404/409 etc.) with an
        # already-safe `detail` string — pass it through as-is.
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = str(uuid.uuid4())
        logger.exception("Unhandled exception [request_id=%s] on %s %s", request_id, request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": GENERIC_MESSAGE, "request_id": request_id},
        )
