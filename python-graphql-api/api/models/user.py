from datetime import datetime

from api import db


class User(db.Model):
    """
    Aligns with production ``users`` (same shape as REST ``/api`` raw SQL).
    Primary key is ``user_id``, not ``id``.
    """

    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=True, default="")
    phone = db.Column(db.String(32), nullable=True)
    first_name = db.Column(db.String(120), nullable=True)
    last_name = db.Column(db.String(120), nullable=True)
    user_type = db.Column(db.String(32), nullable=False, default="customer")
    loyalty_points = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    posts = db.relationship("Post", backref="author", lazy=True)

    def __repr__(self):
        return f"<User {self.user_id} {self.email}>"
