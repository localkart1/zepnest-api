from datetime import datetime

from api import db


class Payment(db.Model):
    """Maps to ``payments`` (same as REST ``/api/payments``)."""

    __tablename__ = "payments"

    payment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.booking_id"), nullable=True)
    amount = db.Column(db.Float, nullable=True, default=0)
    payment_method = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    transaction_id = db.Column(db.String(255), nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    booking = db.relationship("Booking", backref="payments")

    def __repr__(self):
        return f"<Payment {self.payment_id}>"
