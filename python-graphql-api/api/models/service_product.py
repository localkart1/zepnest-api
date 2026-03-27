from datetime import datetime

from api import db


class Service(db.Model):
    """Maps to ``services`` (catalog; same as REST ``/api/services``)."""

    __tablename__ = "services"

    service_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    base_price = db.Column(db.Float, nullable=True, default=0)
    estimated_duration_mins = db.Column(db.Integer, nullable=True)
    category = db.Column(db.String(120), nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    loyalty_points_earned = db.Column(db.Integer, nullable=True, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Service {self.service_id} {self.name}>"
