"""
Web login: email + password against ``users.password_hash`` (Werkzeug hashes).

JWT access tokens use ``typ: web_user`` (distinct from mobile OTP tokens).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from jwt.exceptions import InvalidTokenError
from flask import Blueprint, g, jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from api import db
from api.models.user import User

web_auth_bp = Blueprint("web_auth", __name__, url_prefix="/api/auth")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-key")
WEB_JWT_EXPIRES_HOURS = int(os.getenv("WEB_JWT_EXPIRES_HOURS", "24"))


def _normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def _json_body() -> dict:
    """
    Parse JSON request body. Uses ``force=True`` so a JSON body is accepted even when
    ``Content-Type`` is missing or not ``application/json`` (some HTTP clients omit it).
    """
    data = request.get_json(force=True, silent=True)
    return data if isinstance(data, dict) else {}


def _issue_web_token(user_id: int, email: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=WEB_JWT_EXPIRES_HOURS)
    payload = {
        "sub": str(user_id),
        "email": email,
        "typ": "web_user",
        "exp": exp,
        "iat": now,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _decode_web_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except InvalidTokenError:
        return None
    if payload.get("typ") != "web_user":
        return None
    return payload


def require_web_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = None
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        if not token:
            return jsonify({"message": "Missing Authorization Bearer token"}), 401
        payload = _decode_web_token(token)
        if not payload:
            return jsonify({"message": "Invalid or expired token"}), 401
        try:
            g.web_user_id = int(payload["sub"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"message": "Invalid token subject"}), 401
        g.web_user_email = payload.get("email")
        return f(*args, **kwargs)

    return decorated


def _user_by_email(email: str):
    return User.query.filter(func.lower(User.email) == email).first()


@web_auth_bp.post("/register")
def register():
    data = _json_body()
    email = _normalize_email(data.get("email"))
    password = data.get("password") or ""
    first_name = (data.get("firstName") or data.get("first_name") or "").strip() or None
    last_name = (data.get("lastName") or data.get("last_name") or "").strip() or None

    if not email or "@" not in email:
        return jsonify({"message": "Valid email is required"}), 400
    if len(password) < 8:
        return jsonify({"message": "Password must be at least 8 characters"}), 400
    if len(password) > 256:
        return jsonify({"message": "Password is too long"}), 400

    if _user_by_email(email):
        return jsonify({"message": "Email already registered"}), 409

    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        user_type="customer",
        loyalty_points=0,
        is_active=True,
    )
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Email already registered"}), 409
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Registration failed"}), 500

    token = _issue_web_token(user.user_id, user.email)
    return (
        jsonify(
            {
                "accessToken": token,
                "expiresInHours": WEB_JWT_EXPIRES_HOURS,
                "user": {
                    "id": user.user_id,
                    "email": user.email,
                    "firstName": user.first_name or "",
                    "lastName": user.last_name or "",
                    "userType": user.user_type,
                },
            }
        ),
        201,
    )


@web_auth_bp.post("/login")
def login():
    data = _json_body()
    email = _normalize_email(data.get("email"))
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    user = _user_by_email(email)
    if not user or not user.is_active:
        return jsonify({"message": "Invalid email or password"}), 401
    if not user.check_password(password):
        return jsonify({"message": "Invalid email or password"}), 401

    token = _issue_web_token(user.user_id, user.email)
    return jsonify(
        {
            "accessToken": token,
            "expiresInHours": WEB_JWT_EXPIRES_HOURS,
            "user": {
                "id": user.user_id,
                "email": user.email,
                "firstName": user.first_name or "",
                "lastName": user.last_name or "",
                "userType": user.user_type,
            },
        }
    )


@web_auth_bp.get("/me")
@require_web_auth
def me():
    user = db.session.get(User, g.web_user_id)
    if not user or not user.is_active:
        return jsonify({"message": "User not found"}), 401
    return jsonify(
        {
            "user": {
                "id": user.user_id,
                "email": user.email,
                "firstName": user.first_name or "",
                "lastName": user.last_name or "",
                "userType": user.user_type,
            }
        }
    )
