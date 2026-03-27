"""
AWS S3 configuration (env-driven). Used for presigned PUT URLs for mobile voice/video uploads.

Set AWS_S3_BUCKET (and optionally keys/region) in .env when ready.
"""

from __future__ import annotations

import os
import uuid
from urllib.parse import quote

import boto3
from botocore.config import Config

AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "").strip()
AWS_S3_REGION = os.getenv("AWS_S3_REGION", "us-east-1").strip() or "us-east-1"
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL", "").strip() or None
AWS_S3_PUBLIC_BASE_URL = os.getenv("AWS_S3_PUBLIC_BASE_URL", "").strip() or None

_voice = os.getenv("AWS_S3_VOICE_PREFIX", "mobile/voice/").strip()
_video = os.getenv("AWS_S3_VIDEO_PREFIX", "mobile/video/").strip()
AWS_S3_VOICE_PREFIX = _voice if _voice else "mobile/voice/"
AWS_S3_VIDEO_PREFIX = _video if _video else "mobile/video/"

AWS_S3_PRESIGN_EXPIRES = int(os.getenv("AWS_S3_PRESIGN_EXPIRES", "3600"))

_style = os.getenv("AWS_S3_ADDRESSING_STYLE", "auto").strip() or "auto"


def is_s3_configured() -> bool:
    """True when bucket is set; credentials can come from env or IAM default chain."""
    return bool(AWS_S3_BUCKET)


def _boto_config() -> Config | None:
    if _style not in ("path", "virtual", "auto"):
        return None
    return Config(s3={"addressing_style": _style})


def get_s3_client():
    session = boto3.session.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID") or None,
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY") or None,
        aws_session_token=os.getenv("AWS_SESSION_TOKEN") or None,
        region_name=AWS_S3_REGION,
    )
    cfg = _boto_config()
    return session.client("s3", endpoint_url=AWS_S3_ENDPOINT_URL, config=cfg)


def _normalize_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    return prefix if prefix.endswith("/") else prefix + "/"


def build_object_key(kind: str, file_extension: str) -> str:
    ext = "".join(c for c in file_extension.lower() if c.isalnum())[:8] or "bin"
    uid = str(uuid.uuid4())
    prefix = _normalize_prefix(AWS_S3_VOICE_PREFIX if kind == "voice" else AWS_S3_VIDEO_PREFIX)
    return f"{prefix}{uid}.{ext}"


def build_file_url(object_key: str) -> str:
    """HTTPS URL clients can store on the booking after upload."""
    if AWS_S3_PUBLIC_BASE_URL:
        return f"{AWS_S3_PUBLIC_BASE_URL.rstrip('/')}/{quote(object_key, safe='/')}"
    if AWS_S3_ENDPOINT_URL:
        base = AWS_S3_ENDPOINT_URL.rstrip("/")
        return f"{base}/{AWS_S3_BUCKET}/{quote(object_key, safe='/')}"
    return f"https://{AWS_S3_BUCKET}.s3.{AWS_S3_REGION}.amazonaws.com/{quote(object_key, safe='/')}"


def generate_presigned_put_url(
    *,
    object_key: str,
    content_type: str,
    expires_in: int | None = None,
) -> str:
    client = get_s3_client()
    exp = expires_in if expires_in is not None else AWS_S3_PRESIGN_EXPIRES
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": AWS_S3_BUCKET,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=exp,
        HttpMethod="PUT",
    )
