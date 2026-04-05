from datetime import datetime

from api import db


class CartItem(db.Model):
    """Mobile cart line: one row per user + service (quantity aggregated)."""

    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    service_id = db.Column(db.Integer, nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    notes = db.Column(db.Text, nullable=True)
    voice_url = db.Column(db.Text, nullable=True)
    video_url = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "service_id", name="uq_cart_items_user_service"),)
