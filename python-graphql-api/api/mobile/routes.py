"""
Mobile app API: OTP auth, home (categories + services), bookings (multi-service + media),
profile, addresses.
Uses existing users / services / bookings tables; OTP in mobile_otp_sessions;
addresses in customer_addresses.

Voice notes and video: store the files in AWS S3 (or compatible storage). This API only
persists HTTPS URLs (voiceNoteUrl, videoUrl) on the booking — binaries are not uploaded here.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from jwt.exceptions import InvalidTokenError
from flask import Blueprint, g, jsonify, request
from sqlalchemy import text

from api import db
from api.models.mobile_otp import MobileOtpSession
from api import s3_config

mobile_bp = Blueprint("mobile_api", __name__, url_prefix="/mobile")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-key")
OTP_TTL_SECONDS = int(os.getenv("MOBILE_OTP_TTL_SECONDS", "300"))
JWT_EXPIRES_HOURS = int(os.getenv("MOBILE_JWT_EXPIRES_HOURS", "168"))
MOBILE_OTP_DEBUG = os.getenv("MOBILE_OTP_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

MOBILE_JSON_PREFIX = "[mobile-json]"


def _q(sql: str, params=None):
    return db.session.execute(text(sql), params or {}).mappings().all()


def _one(sql: str, params=None):
    return db.session.execute(text(sql), params or {}).mappings().first()


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone.strip())
    if not digits:
        return None
    if len(digits) == 10:
        return digits
    if len(digits) > 10:
        return digits[-10:]
    return digits


def _otp_hash(phone: str, otp: str) -> str:
    raw = f"{SECRET_KEY}:{phone}:{otp}".encode()
    return hashlib.sha256(raw).hexdigest()


def _issue_token(user_id: int, phone: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=JWT_EXPIRES_HOURS)
    payload = {
        "sub": str(user_id),
        "phone": phone,
        "typ": "mobile_customer",
        "exp": exp,
        "iat": now,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except InvalidTokenError:
        return None


def require_mobile_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = None
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        if not token:
            return jsonify({"message": "Missing Authorization Bearer token"}), 401
        payload = _decode_token(token)
        if not payload or payload.get("typ") != "mobile_customer":
            return jsonify({"message": "Invalid or expired token"}), 401
        try:
            g.mobile_user_id = int(payload["sub"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"message": "Invalid token subject"}), 401
        g.mobile_phone = payload.get("phone")
        return f(*args, **kwargs)

    return decorated


def _get_or_create_customer(phone: str, first_name: str = "", last_name: str = "") -> dict:
    row = _one(
        """
        SELECT user_id, first_name, last_name, email, phone, is_active, created_at
        FROM users WHERE phone = :phone AND user_type = 'customer'
        """,
        {"phone": phone},
    )
    if row:
        return dict(row)
    email = f"{phone}@mobile.local"
    row = _one(
        """
        INSERT INTO users (email, password_hash, phone, first_name, last_name, user_type, loyalty_points, is_active, created_at, updated_at)
        VALUES (:email, '', :phone, :fn, :ln, 'customer', 0, true, NOW(), NOW())
        RETURNING user_id, first_name, last_name, email, phone, is_active, created_at
        """,
        {"email": email, "phone": phone, "fn": first_name or "User", "ln": last_name or ""},
    )
    db.session.commit()
    return dict(row)


def _parse_mobile_json_notes(notes: str | None) -> dict | None:
    if not notes:
        return None
    s = notes.strip()
    if not s.startswith(MOBILE_JSON_PREFIX):
        return None
    raw = s[len(MOBILE_JSON_PREFIX) :].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _parse_legacy_service_id(notes: str | None) -> str | None:
    if not notes:
        return None
    m = re.search(r"\[mobile\]\s*serviceId=(\d+)", notes)
    return m.group(1) if m else None


def _resolve_services_for_booking(notes: str | None) -> tuple[list[dict], str]:
    """Returns (services list, display note text for legacy free-text)."""
    payload = _parse_mobile_json_notes(notes)
    if payload:
        out = []
        for sid in payload.get("serviceIds") or []:
            try:
                i = int(sid)
            except (TypeError, ValueError):
                continue
            srow = _one("SELECT service_id, name, description, base_price FROM services WHERE service_id = :id", {"id": i})
            if srow:
                out.append(
                    {
                        "id": str(srow["service_id"]),
                        "name": srow["name"],
                        "description": srow["description"] or "",
                        "basePrice": float(srow["base_price"] or 0),
                    }
                )
        return out, ""

    legacy_id = _parse_legacy_service_id(notes)
    if legacy_id:
        srow = _one("SELECT service_id, name, description, base_price FROM services WHERE service_id = :id", {"id": int(legacy_id)})
        if srow:
            return (
                [
                    {
                        "id": str(srow["service_id"]),
                        "name": srow["name"],
                        "description": srow["description"] or "",
                        "basePrice": float(srow["base_price"] or 0),
                    }
                ],
                "",
            )

    note_display = ""
    if notes:
        parts = notes.split("|", 1)
        note_display = parts[-1].strip() if len(parts) > 1 else ""
    return [], note_display


def _booking_to_response(r: dict) -> dict:
    """Map bookings row + customer_notes to API object."""
    notes = r.get("customer_notes")
    payload = _parse_mobile_json_notes(notes)
    services, legacy_note = _resolve_services_for_booking(notes)

    if payload:
        desc = (payload.get("description") or "").strip()
        voice = (payload.get("voiceNoteUrl") or payload.get("voiceUrl") or "").strip()
        video = (payload.get("videoUrl") or "").strip()
        extra = (payload.get("customerNotes") or "").strip()
        return {
            "id": str(r["booking_id"]),
            "bookingNumber": r["booking_number"],
            "status": r["status"],
            "serviceAddress": r["service_address"] or "",
            "totalAmount": float(r["total_amount"] or 0),
            "description": desc,
            "voiceNoteUrl": voice or None,
            "videoUrl": video or None,
            "customerNotes": extra,
            "services": services,
            "createdAt": r["created_at"].isoformat() if r.get("created_at") else None,
            "updatedAt": r["updated_at"].isoformat() if r.get("updated_at") else None,
        }

    single = services[0] if len(services) == 1 else None
    return {
        "id": str(r["booking_id"]),
        "bookingNumber": r["booking_number"],
        "status": r["status"],
        "serviceAddress": r["service_address"] or "",
        "totalAmount": float(r["total_amount"] or 0),
        "description": "",
        "voiceNoteUrl": None,
        "videoUrl": None,
        "customerNotes": legacy_note,
        "services": services if services else None,
        "service": single,
        "createdAt": r["created_at"].isoformat() if r.get("created_at") else None,
        "updatedAt": r["updated_at"].isoformat() if r.get("updated_at") else None,
    }


def _collect_service_ids(data: dict) -> list[int]:
    ids: list[int] = []
    raw_list = data.get("serviceIds") or data.get("services")
    if isinstance(raw_list, list):
        for x in raw_list:
            if x is None:
                continue
            try:
                ids.append(int(x))
            except (TypeError, ValueError):
                continue
    sid = data.get("serviceId")
    if sid is not None and not ids:
        try:
            ids.append(int(sid))
        except (TypeError, ValueError):
            pass
    seen = set()
    out = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


@mobile_bp.post("/auth/request-otp")
def request_otp():
    data = request.get_json(silent=True) or {}
    phone = normalize_phone(data.get("phone"))
    if not phone:
        return jsonify({"message": "Valid phone number is required"}), 400

    otp = f"{secrets.randbelow(900000) + 100000}"
    expires_at = datetime.utcnow() + timedelta(seconds=OTP_TTL_SECONDS)
    _q(
        "UPDATE mobile_otp_sessions SET consumed = true WHERE phone = :phone AND consumed = false",
        {"phone": phone},
    )
    sess = MobileOtpSession(
        phone=phone,
        otp_hash=_otp_hash(phone, otp),
        expires_at=expires_at,
        consumed=False,
    )
    db.session.add(sess)
    db.session.commit()

    body = {
        "message": "OTP sent",
        "expiresInSeconds": OTP_TTL_SECONDS,
        "phone": phone,
    }
    if MOBILE_OTP_DEBUG:
        body["debugOtp"] = otp
    return jsonify(body), 200


@mobile_bp.post("/auth/verify-otp")
def verify_otp():
    data = request.get_json(silent=True) or {}
    phone = normalize_phone(data.get("phone"))
    otp = (data.get("otp") or "").strip()
    if not phone or not otp:
        return jsonify({"message": "phone and otp are required"}), 400

    row = _one(
        """
        SELECT id, otp_hash, expires_at, consumed FROM mobile_otp_sessions
        WHERE phone = :phone AND consumed = false
        ORDER BY id DESC LIMIT 1
        """,
        {"phone": phone},
    )
    if not row:
        return jsonify({"message": "No active OTP for this number"}), 400
    if row["consumed"]:
        return jsonify({"message": "OTP already used"}), 400
    if row["expires_at"] and row["expires_at"] < datetime.utcnow():
        return jsonify({"message": "OTP expired"}), 400
    if row["otp_hash"] != _otp_hash(phone, otp):
        return jsonify({"message": "Invalid OTP"}), 401

    _one(
        "UPDATE mobile_otp_sessions SET consumed = true WHERE id = :id",
        {"id": row["id"]},
    )
    db.session.commit()

    fn = (data.get("firstName") or "").strip()
    ln = (data.get("lastName") or "").strip()
    user = _get_or_create_customer(phone, fn, ln)
    if fn or ln:
        _q(
            """
            UPDATE users SET first_name = COALESCE(NULLIF(:fn,''), first_name),
                last_name = COALESCE(NULLIF(:ln,''), last_name), updated_at = NOW()
            WHERE user_id = :uid
            """,
            {"uid": user["user_id"], "fn": fn, "ln": ln},
        )
        db.session.commit()

    token = _issue_token(user["user_id"], phone)
    return jsonify(
        {
            "accessToken": token,
            "tokenType": "Bearer",
            "expiresInSeconds": JWT_EXPIRES_HOURS * 3600,
            "user": {
                "id": str(user["user_id"]),
                "phone": user["phone"],
                "firstName": user.get("first_name") or "",
                "lastName": user.get("last_name") or "",
                "email": user.get("email") or "",
            },
        }
    ), 200


@mobile_bp.get("/home")
def mobile_home():
    cat_rows = _q(
        """
        SELECT DISTINCT category AS name
        FROM services
        WHERE is_active = true AND category IS NOT NULL AND TRIM(category) <> ''
        ORDER BY category
        """
    )
    svc_rows = _q(
        """
        SELECT service_id, name, description, base_price, estimated_duration_mins, category, image_url, is_active
        FROM services
        WHERE is_active = true
        ORDER BY category NULLS LAST, service_id DESC
        """
    )
    by_cat: dict[str, list] = {}
    for r in svc_rows:
        c = r["category"] or "General"
        by_cat.setdefault(c, []).append(
            {
                "id": str(r["service_id"]),
                "name": r["name"],
                "description": r["description"] or "",
                "basePrice": float(r["base_price"] or 0),
                "estimatedDurationMins": r["estimated_duration_mins"] or 0,
                "category": c,
                "imageUrl": r["image_url"],
            }
        )
    categories = []
    for r in cat_rows:
        name = r["name"]
        categories.append(
            {
                "id": name,
                "name": name,
                "services": by_cat.get(name, [])[:12],
            }
        )
    return jsonify({"categories": categories}), 200


@mobile_bp.post("/bookings")
@require_mobile_auth
def create_mobile_booking():
    data = request.get_json(silent=True) or {}
    address = (data.get("serviceAddress") or data.get("address") or "").strip()
    if not address:
        return jsonify({"message": "serviceAddress is required"}), 400

    service_ids = _collect_service_ids(data)
    if not service_ids:
        return jsonify({"message": "At least one service is required (serviceId or serviceIds)"}), 400

    ph = ",".join([f":s{i}" for i in range(len(service_ids))])
    sparams = {f"s{i}": service_ids[i] for i in range(len(service_ids))}
    rows_svcs = _q(
        f"SELECT service_id, name, base_price FROM services WHERE service_id IN ({ph}) AND is_active = true",
        sparams,
    )
    if len(rows_svcs) != len(service_ids):
        return jsonify({"message": "One or more services were not found or inactive"}), 404

    by_id = {r["service_id"]: r for r in rows_svcs}
    ordered = [by_id[i] for i in service_ids if i in by_id]
    total = sum(float(r["base_price"] or 0) for r in ordered)

    # voiceNoteUrl / videoUrl: client uploads to S3 first, then passes HTTPS URLs here.
    description = (data.get("description") or "").strip()
    voice = (data.get("voiceNoteUrl") or data.get("voiceUrl") or "").strip()
    video = (data.get("videoUrl") or "").strip()
    extra_notes = (data.get("customerNotes") or data.get("notes") or "").strip()

    payload = {
        "serviceIds": service_ids,
        "description": description,
        "voiceNoteUrl": voice,
        "videoUrl": video,
        "customerNotes": extra_notes,
    }
    notes_text = MOBILE_JSON_PREFIX + json.dumps(payload, ensure_ascii=False)

    number = f"MB-{int(datetime.utcnow().timestamp())}-{secrets.token_hex(2)}"
    row = _one(
        """
        INSERT INTO bookings (booking_number, customer_id, technician_id, service_address, status, subtotal, discount_amount,
            loyalty_points_used, loyalty_discount, total_amount, loyalty_points_earned, is_subscription_booking,
            customer_notes, created_at, updated_at)
        VALUES (:n, :c, NULL, :a, 'new', :sub, 0, 0, 0, :tot, 0, false, :cn, NOW(), NOW())
        RETURNING booking_id, booking_number, status, total_amount, service_address, customer_notes, created_at, updated_at
        """,
        {"n": number, "c": g.mobile_user_id, "a": address, "sub": total, "tot": total, "cn": notes_text},
    )
    db.session.commit()
    rdict = dict(row)
    body = _booking_to_response(rdict)
    return jsonify(body), 201


@mobile_bp.get("/bookings")
@require_mobile_auth
def list_mobile_bookings():
    page = int(request.args.get("page", 1) or 1)
    limit = min(int(request.args.get("limit", 20) or 20), 100)
    offset = (page - 1) * limit

    rows = _q(
        """
        SELECT b.booking_id, b.booking_number, b.status, b.service_address, b.total_amount, b.customer_notes,
               b.created_at, b.updated_at
        FROM bookings b
        WHERE b.customer_id = :cid
        ORDER BY b.booking_id DESC
        LIMIT :lim OFFSET :off
        """,
        {"cid": g.mobile_user_id, "lim": limit, "off": offset},
    )
    out = [_booking_to_response(dict(r)) for r in rows]

    total_row = _one(
        "SELECT COUNT(*) AS c FROM bookings WHERE customer_id = :cid",
        {"cid": g.mobile_user_id},
    )
    total = int(total_row["c"] or 0) if total_row else 0
    total_pages = (total + limit - 1) // limit if limit else 0
    return jsonify(
        {
            "data": out,
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
        }
    ), 200


@mobile_bp.get("/bookings/<int:booking_id>")
@require_mobile_auth
def get_mobile_booking(booking_id: int):
    r = _one(
        """
        SELECT b.booking_id, b.booking_number, b.status, b.service_address, b.total_amount, b.customer_notes,
               b.created_at, b.updated_at
        FROM bookings b
        WHERE b.booking_id = :id AND b.customer_id = :cid
        """,
        {"id": booking_id, "cid": g.mobile_user_id},
    )
    if not r:
        return jsonify({"message": "Booking not found"}), 404
    return jsonify(_booking_to_response(dict(r))), 200


def _address_row_to_dict(r) -> dict:
    return {
        "id": r["id"],
        "label": r["label"] or "",
        "line1": r["line1"] or "",
        "line2": r["line2"] or "",
        "city": r["city"] or "",
        "state": r["state"] or "",
        "zipCode": r["zip_code"] or "",
        "country": r["country"] or "",
        "isDefault": bool(r["is_default"]),
        "createdAt": r["created_at"].isoformat() if r.get("created_at") else None,
        "updatedAt": r["updated_at"].isoformat() if r.get("updated_at") else None,
    }


@mobile_bp.get("/profile")
@require_mobile_auth
def get_profile():
    u = _one(
        """
        SELECT user_id, first_name, last_name, email, phone, loyalty_points, is_active, created_at, updated_at
        FROM users WHERE user_id = :id AND user_type = 'customer'
        """,
        {"id": g.mobile_user_id},
    )
    if not u:
        return jsonify({"message": "User not found"}), 404
    addrs = _q(
        """
        SELECT id, label, line1, line2, city, state, zip_code, country, is_default, created_at, updated_at
        FROM customer_addresses WHERE user_id = :uid ORDER BY is_default DESC, id DESC
        """,
        {"uid": g.mobile_user_id},
    )
    default_addr = None
    addr_list = []
    for a in addrs:
        d = _address_row_to_dict(dict(a))
        addr_list.append(d)
        if d["isDefault"] and default_addr is None:
            default_addr = d
    return jsonify(
        {
            "user": {
                "id": str(u["user_id"]),
                "firstName": u["first_name"] or "",
                "lastName": u["last_name"] or "",
                "email": u["email"] or "",
                "phone": u["phone"] or "",
                "loyaltyPoints": u["loyalty_points"] or 0,
                "isActive": bool(u["is_active"]),
                "createdAt": u["created_at"].isoformat() if u.get("created_at") else None,
                "updatedAt": u["updated_at"].isoformat() if u.get("updated_at") else None,
            },
            "addresses": addr_list,
            "defaultAddress": default_addr,
        }
    ), 200


@mobile_bp.patch("/profile")
@require_mobile_auth
def patch_profile():
    data = request.get_json(silent=True) or {}
    fn = data.get("firstName")
    ln = data.get("lastName")
    email = data.get("email")
    _q(
        """
        UPDATE users SET
            first_name = COALESCE(:fn, first_name),
            last_name = COALESCE(:ln, last_name),
            email = COALESCE(:email, email),
            updated_at = NOW()
        WHERE user_id = :id AND user_type = 'customer'
        """,
        {"id": g.mobile_user_id, "fn": fn, "ln": ln, "email": email},
    )
    db.session.commit()
    return get_profile()


@mobile_bp.get("/addresses")
@require_mobile_auth
def list_addresses():
    addrs = _q(
        """
        SELECT id, label, line1, line2, city, state, zip_code, country, is_default, created_at, updated_at
        FROM customer_addresses WHERE user_id = :uid ORDER BY is_default DESC, id DESC
        """,
        {"uid": g.mobile_user_id},
    )
    return jsonify({"data": [_address_row_to_dict(dict(a)) for a in addrs]}), 200


@mobile_bp.post("/addresses")
@require_mobile_auth
def create_address():
    data = request.get_json(silent=True) or {}
    line1 = (data.get("line1") or data.get("addressLine1") or "").strip()
    if not line1:
        return jsonify({"message": "line1 is required"}), 400
    is_def = bool(data.get("isDefault"))
    if is_def:
        _q("UPDATE customer_addresses SET is_default = false WHERE user_id = :uid", {"uid": g.mobile_user_id})
    row = _one(
        """
        INSERT INTO customer_addresses (user_id, label, line1, line2, city, state, zip_code, country, is_default, created_at, updated_at)
        VALUES (:uid, :label, :l1, :l2, :city, :state, :zip, :country, :isd, NOW(), NOW())
        RETURNING id, label, line1, line2, city, state, zip_code, country, is_default, created_at, updated_at
        """,
        {
            "uid": g.mobile_user_id,
            "label": (data.get("label") or "Home").strip() or "Home",
            "l1": line1,
            "l2": (data.get("line2") or data.get("addressLine2") or "").strip() or None,
            "city": (data.get("city") or "").strip() or None,
            "state": (data.get("state") or "").strip() or None,
            "zip": (data.get("zipCode") or data.get("zip") or "").strip() or None,
            "country": (data.get("country") or "India").strip() or "India",
            "isd": is_def,
        },
    )
    db.session.commit()
    return jsonify(_address_row_to_dict(dict(row))), 201


@mobile_bp.put("/addresses/<int:address_id>")
@require_mobile_auth
def update_address(address_id: int):
    owner = _one(
        "SELECT id FROM customer_addresses WHERE id = :id AND user_id = :uid",
        {"id": address_id, "uid": g.mobile_user_id},
    )
    if not owner:
        return jsonify({"message": "Address not found"}), 404

    data = request.get_json(silent=True) or {}
    is_def = data.get("isDefault")
    if is_def is True:
        _q(
            "UPDATE customer_addresses SET is_default = false WHERE user_id = :uid AND id != :aid",
            {"uid": g.mobile_user_id, "aid": address_id},
        )

    _q(
        """
        UPDATE customer_addresses SET
            label = COALESCE(:label, label),
            line1 = COALESCE(:l1, line1),
            line2 = COALESCE(:l2, line2),
            city = COALESCE(:city, city),
            state = COALESCE(:state, state),
            zip_code = COALESCE(:zip, zip_code),
            country = COALESCE(:country, country),
            is_default = COALESCE(:isd, is_default),
            updated_at = NOW()
        WHERE id = :id AND user_id = :uid
        """,
        {
            "id": address_id,
            "uid": g.mobile_user_id,
            "label": data.get("label"),
            "l1": data.get("line1") or data.get("addressLine1"),
            "l2": data.get("line2") or data.get("addressLine2"),
            "city": data.get("city"),
            "state": data.get("state"),
            "zip": data.get("zipCode") or data.get("zip"),
            "country": data.get("country"),
            "isd": is_def if isinstance(is_def, bool) else None,
        },
    )
    db.session.commit()
    row = _one(
        """
        SELECT id, label, line1, line2, city, state, zip_code, country, is_default, created_at, updated_at
        FROM customer_addresses WHERE id = :id
        """,
        {"id": address_id},
    )
    return jsonify(_address_row_to_dict(dict(row))), 200


@mobile_bp.delete("/addresses/<int:address_id>")
@require_mobile_auth
def delete_address(address_id: int):
    r = _one(
        "DELETE FROM customer_addresses WHERE id = :id AND user_id = :uid RETURNING id",
        {"id": address_id, "uid": g.mobile_user_id},
    )
    if not r:
        return jsonify({"message": "Address not found"}), 404
    db.session.commit()
    return "", 204


_DEFAULT_VOICE_TYPES = {
    "m4a": "audio/mp4",
    "mp3": "audio/mpeg",
    "aac": "audio/aac",
    "wav": "audio/wav",
    "webm": "audio/webm",
}
_DEFAULT_VIDEO_TYPES = {
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "webm": "video/webm",
    "m4v": "video/x-m4v",
}


@mobile_bp.post("/uploads/presign")
@require_mobile_auth
def presign_s3_upload():
    """
    Returns a presigned PUT URL for uploading voice or video to S3.
    Client PUTs the file to uploadUrl, then uses fileUrl in POST /mobile/bookings.
    """
    if not s3_config.is_s3_configured():
        return (
            jsonify(
                {
                    "message": "S3 is not configured. Set AWS_S3_BUCKET (and credentials) in the environment.",
                }
            ),
            503,
        )

    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or data.get("type") or "").strip().lower()
    if kind not in ("voice", "video"):
        return jsonify({"message": 'kind must be "voice" or "video"'}), 400

    ext = (data.get("fileExtension") or data.get("extension") or "bin").strip().lower().lstrip(".")
    content_type = (data.get("contentType") or data.get("mimeType") or "").strip()
    if not content_type:
        defaults = _DEFAULT_VOICE_TYPES if kind == "voice" else _DEFAULT_VIDEO_TYPES
        content_type = defaults.get(ext, "application/octet-stream")

    object_key = s3_config.build_object_key(kind, ext)
    try:
        upload_url = s3_config.generate_presigned_put_url(
            object_key=object_key,
            content_type=content_type,
        )
    except Exception as e:
        return jsonify({"message": "Failed to create presigned URL", "detail": str(e)}), 502

    return (
        jsonify(
            {
                "uploadUrl": upload_url,
                "method": "PUT",
                "headers": {"Content-Type": content_type},
                "objectKey": object_key,
                "fileUrl": s3_config.build_file_url(object_key),
                "expiresInSeconds": s3_config.AWS_S3_PRESIGN_EXPIRES,
            }
        ),
        200,
    )
