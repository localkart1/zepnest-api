from datetime import datetime

from api import db


class Address(db.Model):
    """Common user address table for all user types (customers, technicians, admins)."""

    __tablename__ = "addresses"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    label = db.Column(db.String(64), nullable=True)
    line1 = db.Column(db.String(255), nullable=False)
    line2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    zip_code = db.Column(db.String(20), nullable=True)
    country = db.Column(db.String(80), nullable=True, default="India")
    address_type = db.Column(db.String(32), nullable=True, default="home")
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    door_no = db.Column(db.String(128), nullable=True)
    building_name = db.Column(db.String(255), nullable=True)
    street = db.Column(db.String(255), nullable=True)
    area = db.Column(db.String(255), nullable=True)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column("long", db.Float, nullable=True)
    phone_no = db.Column(db.String(32), nullable=True)
    name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

