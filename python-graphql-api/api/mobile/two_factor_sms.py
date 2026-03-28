"""
Send OTP SMS via 2Factor.in (https://2factor.in).

Uses POST https://2factor.in/API/V1/{api_key}/SMS/{phone}/{otp}
Documented at: https://2factor.in/API/DOCS/SMS_OTP.html
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def format_phone_for_2factor(normalized_digits: str) -> str:
    """
    2Factor India SMS expects the destination as used in their dashboard (typically 91 + 10 digits).
    ``normalized_digits`` is digits-only from ``normalize_phone`` (often 10 chars for IN mobiles).
    """
    d = (normalized_digits or "").strip()
    if not d:
        return d
    if len(d) == 10:
        return "91" + d
    if d.startswith("91") and len(d) >= 12:
        return d
    return d


def send_otp_sms(
    api_key: str,
    phone_for_provider: str,
    otp: str,
    *,
    timeout_seconds: float | None = None,
) -> tuple[bool, str]:
    """
    Returns (success, error_or_empty_message).
    On HTTP/network failure or non-Success JSON, success is False.
    """
    if not api_key or not phone_for_provider or not otp:
        return False, "missing api key, phone, or otp"

    timeout = timeout_seconds
    if timeout is None:
        timeout = float(os.getenv("SMS_2FACTOR_TIMEOUT_SECONDS", "15"))

    # Path segments: API docs use raw POST URL; keep digits-only phone and numeric OTP.
    url = f"https://2factor.in/API/V1/{api_key}/SMS/{phone_for_provider}/{otp}"
    req = urllib.request.Request(
        url,
        method="POST",
        headers={"Accept": "application/json"},
        data=b"",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            raw = str(e)
        return False, raw or f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, str(e.reason or e)
    except OSError as e:
        return False, str(e)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False, raw[:500] if raw else "invalid JSON from SMS provider"

    status = data.get("Status") or data.get("status")
    if str(status).lower() == "success":
        return True, ""

    detail = data.get("Details") or data.get("details") or data.get("Message") or raw
    return False, str(detail)[:500]
