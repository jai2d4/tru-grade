"""Structured logging and per-request correlation IDs — app/core/logging_config.py."""
from __future__ import annotations

import io
import json
import logging

from fastapi.testclient import TestClient

from app.core.logging_config import _JsonFormatter, _RequestIdFilter, configure_logging, get_request_id
from backend.main import app


def test_configure_logging_emits_valid_single_line_json():
    configure_logging()
    root = logging.getLogger()
    original_stream = root.handlers[0].stream
    stream = io.StringIO()
    root.handlers[0].stream = stream
    try:
        logging.getLogger("tru.test").info("hello world")
    finally:
        root.handlers[0].stream = original_stream

    line = stream.getvalue().strip()
    payload = json.loads(line)  # raises if it's not one valid JSON object
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "tru.test"
    assert "timestamp" in payload


def test_json_formatter_includes_request_id_only_when_set():
    handler_filter = _RequestIdFilter()
    formatter = _JsonFormatter()

    record = logging.LogRecord("tru.test", logging.INFO, __file__, 1, "no request in flight", (), None)
    handler_filter.filter(record)  # request_id defaults to None outside a request
    payload = json.loads(formatter.format(record))
    assert "request_id" not in payload


def test_json_formatter_passes_through_extra_fields_and_never_crashes_on_unserializable_ones():
    formatter = _JsonFormatter()
    record = logging.LogRecord("tru.test", logging.INFO, __file__, 1, "request completed", (), None)
    record.method = "GET"
    record.status_code = 200
    record.weird = object()  # not JSON-serializable — must degrade to str(), not raise

    payload = json.loads(formatter.format(record))
    assert payload["method"] == "GET"
    assert payload["status_code"] == 200
    assert isinstance(payload["weird"], str)


def test_every_response_carries_a_request_id_header():
    # /api/health/live is deliberately public — no API key needed either way.
    with TestClient(app) as client:
        response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_incoming_request_id_is_echoed_back_unchanged():
    with TestClient(app) as client:
        response = client.get("/api/health/live", headers={"X-Request-ID": "caller-supplied-id-123"})

    assert response.headers["X-Request-ID"] == "caller-supplied-id-123"


def test_get_request_id_is_none_outside_a_request():
    assert get_request_id() is None
