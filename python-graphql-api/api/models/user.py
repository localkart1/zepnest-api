from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

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
    internal_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    posts = db.relationship("Post", backref="author", lazy=True)

    def set_password(self, raw_password: str) -> None:
        """Store a Werkzeug password hash (pbkdf2/scrypt per Werkzeug defaults)."""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, raw_password)

    def __repr__(self):
        return f"<User {self.user_id} {self.email}>"
