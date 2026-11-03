"""One JSON object per request on stdout: greppable, parseable, no secrets.

Kubernetes/Docker collect stdout, so this is the whole logging story for v0.
Authorization headers, cookies and bodies are never logged.
"""
from __future__ import annotations

import json
import sys
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Errors on the way in are still worth a line; these are the fields we allow.
_SAFE_HEADERS = ("user-agent",)


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            record = {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": duration_ms,
                "client": getattr(request.client, "host", None),
            }
            for header in _SAFE_HEADERS:
                if header in request.headers:
                    record[header.replace("-", "_")] = request.headers[header][:80]
            print(json.dumps(record, ensure_ascii=False), flush=True, file=sys.stdout)
        response.headers["X-Request-Id"] = request_id
        return response
