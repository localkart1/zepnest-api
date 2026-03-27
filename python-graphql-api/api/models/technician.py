from datetime import datetime

from api import db


class Technician(db.Model):
    """
    Maps to ``technician_profiles`` (same as REST ``/api``).
    Name/email/phone come from ``users`` via ``user_id``.
    """

    __tablename__ = "technician_profiles"

    technician_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, unique=True)
    specialization = db.Column(db.String(255), nullable=True)
    experience_years = db.Column(db.Integer, nullable=True, default=0)
    bio = db.Column(db.Text, nullable=True)
    hourly_rate = db.Column(db.Float, nullable=True)
    certification = db.Column(db.String(500), nullable=True)
    rating = db.Column(db.Float, nullable=True, default=0)
    total_reviews = db.Column(db.Integer, nullable=True, default=0)
    status = db.Column(db.String(50), nullable=True, default="available")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("technician_profile", uselist=False), foreign_keys=[user_id])

    @property
    def id(self):
        return self.technician_id

    @property
    def name(self):
        if self.user:
            fn = self.user.first_name or ""
            ln = self.user.last_name or ""
            return f"{fn} {ln}".strip() or None
        return None

    @property
    def certifications(self):
        return self.certification

    @property
    def tickets(self):
        return self.bookings

    def __repr__(self):
        return f"<Technician {self.technician_id} user={self.user_id}>"
