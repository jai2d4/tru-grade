"""Structured (JSON) application logging with per-request correlation IDs.

Plain-text log lines are fine to read in a terminal but hard for any real
log pipeline (Render's own log search, or an external tool like a
self-hosted ops dashboard) to filter, correlate, or alert on. This makes
every line this app itself emits a single JSON object, and ties every line
emitted during one request to that request's own id via a contextvar — so
"everything that happened on this request" becomes a filter, not a hunt
through timestamps. Uvicorn's own access/error logs are untouched (they
already set `propagate=False`, so they never double up with this handler);
`RequestIDMiddleware` below is the real replacement for the per-request
access line, with a request id and timing uvicorn's own line doesn't have.
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attribute names logging.LogRecord already assigns — never overwrite one of
# these with a caller's `extra=` field, and never re-emit it as if it were
# application data.
_RESERVED_LOG_RECORD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
    "message",
    "asctime",
}

access_logger = logging.getLogger("tru.access")


def get_request_id() -> str | None:
    return _request_id_var.get()


class _RequestIdFilter(logging.Filter):
    """Stamps whatever request is currently in flight onto every record —
    including ones logged deep inside a route handler, not just the
    middleware's own access line."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Anything passed via logger.info(..., extra={...}) rides along too.
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_ATTRS or key in payload or key == "request_id":
                continue
            try:
                json.dumps(value)
            except TypeError:
                value = str(value)
            payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(level: int | str = logging.INFO) -> None:
    """Idempotent — safe to call more than once (module re-imports in tests).
    Only touches the root logger's own handler; uvicorn's loggers keep their
    own handlers and formatting untouched."""
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(_RequestIdFilter())
    root.handlers = [handler]
    root.setLevel(level)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Reads X-Request-ID from the caller (so a request can be traced across
    services that also set it) or mints one, makes it available to every
    logger for the duration of the request, echoes it back on the response,
    and logs one structured line per request with method/path/status/timing
    — the real, queryable replacement for a plain-text access log."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = _request_id_var.set(request_id)
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.monotonic() - started) * 1000, 1)
            access_logger.exception(
                "request failed",
                extra={"method": request.method, "path": request.url.path, "duration_ms": duration_ms},
            )
            raise
        else:
            duration_ms = round((time.monotonic() - started) * 1000, 1)
            response.headers["X-Request-ID"] = request_id
            access_logger.info(
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        finally:
            _request_id_var.reset(token)
