"""
HTTP access-style logging: method, path, query, status, duration, redacted payload preview.

On 4xx/5xx, logs at WARNING with ``event=request_error``, full ``query_string``, larger
``query`` JSON, and a short ``response_body_preview`` when the body is text-like.

Enable/disable with ``REQUEST_LOG_ENABLED`` (default: on). Never logs raw secrets.
"""

from __future__ import annotations

import json
import os
import re
import time

from flask import Flask, current_app, g, request

# Substrings matched against normalized dict keys (lowercase, no underscores).
_SENSITIVE_KEY_PARTS: frozenset[str] = frozenset(
    {
        "password",
        "secret",
        "token",
        "accesstoken",
        "refreshtoken",
        "authorization",
        "otp",
        "apikey",
        "apisecret",
        "creditcard",
        "cardnumber",
        "cvv",
        "ssn",
    }
)


def _norm_key(k: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (k or "").lower())


def _is_sensitive_key(key: str) -> bool:
    n = _norm_key(key)
    if not n:
        return False
    for part in _SENSITIVE_KEY_PARTS:
        if part in n:
            return True
    return False


def _sanitize(obj, depth: int = 0):
    if depth > 12:
        return "…"
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _is_sensitive_key(str(k)):
                out[k] = "[redacted]"
            else:
                out[k] = _sanitize(v, depth + 1)
        return out
    if isinstance(obj, list):
        return [_sanitize(x, depth + 1) for x in obj[:100]]
    return obj


def _parse_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def install_request_access_logging(app: Flask) -> None:
    if not _parse_bool("REQUEST_LOG_ENABLED", True):
        return

    body_max = int(os.getenv("REQUEST_LOG_BODY_MAX", "4000"))
    err_query_max = int(os.getenv("REQUEST_LOG_ERROR_QUERY_MAX", "8000"))
    err_response_max = int(os.getenv("REQUEST_LOG_ERROR_RESPONSE_MAX", "800"))
    skip_paths = {p.strip() for p in (os.getenv("REQUEST_LOG_SKIP_PATHS") or "").split(",") if p.strip()}

    @app.before_request
    def _request_log_capture():
        if request.path in skip_paths:
            return
        g._request_log_start = time.perf_counter()
        g._request_log_payload = None
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return
        try:
            if request.is_json:
                raw = request.get_json(silent=True)
                if raw is not None:
                    g._request_log_payload = _sanitize(raw)
            elif request.form:
                g._request_log_payload = _sanitize(request.form.to_dict())
            elif request.content_length and request.content_length > 0:
                text = request.get_data(as_text=True)
                if text:
                    g._request_log_payload = (text[:body_max] + ("…" if len(text) > body_max else ""))
        except Exception:
            g._request_log_payload = "[payload unreadable]"

    @app.after_request
    def _request_log_emit(response):
        if request.path in skip_paths:
            return response
        start = getattr(g, "_request_log_start", None)
        if start is None:
            return response

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        q = request.args.to_dict(flat=False)
        is_error = response.status_code >= 400
        q_max = err_query_max if is_error else 2000
        query_preview = json.dumps(q, default=str)[:q_max] if q else None
        # Raw query string for errors (easy to grep / copy)
        query_string = request.query_string.decode("utf-8", errors="replace") if request.query_string else ""

        auth_hdr = request.headers.get("Authorization")
        if auth_hdr:
            auth_out = "Bearer ***" if auth_hdr.lower().startswith("bearer ") else "[redacted]"
        else:
            auth_out = None

        payload = getattr(g, "_request_log_payload", None)
        if isinstance(payload, (dict, list)):
            try:
                payload_str = json.dumps(payload, ensure_ascii=False, default=str)
            except Exception:
                payload_str = str(payload)
        elif payload is not None:
            payload_str = str(payload)
        else:
            payload_str = None
        if payload_str is not None and len(payload_str) > body_max:
            payload_str = payload_str[:body_max] + "…"

        response_preview = None
        if is_error:
            try:
                ct = (response.content_type or "").lower()
                if (
                    not ct
                    or "json" in ct
                    or "text" in ct
                    or "xml" in ct
                    or "html" in ct
                ):
                    raw = response.get_data(as_text=True)
                    if raw:
                        response_preview = raw[:err_response_max]
                        if len(raw) > err_response_max:
                            response_preview += "…"
            except Exception:
                response_preview = "[response body unreadable]"

        record = {
            "event": "request_error" if is_error else "request",
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "query": query_preview,
            "remote": request.headers.get("X-Forwarded-For", request.remote_addr),
            "auth": auth_out,
            "payload": payload_str,
        }
        if is_error:
            if len(query_string) > err_query_max:
                record["query_string"] = query_string[:err_query_max] + "…"
            else:
                record["query_string"] = query_string
            if response_preview is not None:
                record["response_body_preview"] = response_preview

        line = json.dumps(record, ensure_ascii=False, default=str)
        if is_error:
            current_app.logger.warning("%s", line)
        else:
            current_app.logger.info("%s", line)
        return response
