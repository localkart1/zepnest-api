from datetime import datetime

from api import db


class MobileOtpSession(db.Model):
    """Stores hashed OTP challenges for mobile phone login (table: mobile_otp_sessions)."""

    __tablename__ = "mobile_otp_sessions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    phone = db.Column(db.String(32), nullable=False, index=True)
    otp_hash = db.Column(db.String(128), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
