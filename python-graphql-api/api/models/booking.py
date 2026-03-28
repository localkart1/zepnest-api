from datetime import datetime

from api import db
from api.booking_status import DEFAULT_BOOKING_STATUS


class Booking(db.Model):
    """
    Maps to ``bookings`` (orders / service requests; same as REST).
    GraphQL ``Ticket`` and ``ServiceBooking`` types both use this model; extra
    attributes are compatibility helpers (some are not persisted columns).
    """

    __tablename__ = "bookings"

    booking_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    booking_number = db.Column(db.String(64), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    technician_id = db.Column(db.Integer, db.ForeignKey("technician_profiles.technician_id"), nullable=True)
    service_address = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=True, default=DEFAULT_BOOKING_STATUS)
    subtotal = db.Column(db.Float, nullable=True, default=0)
    discount_amount = db.Column(db.Float, nullable=True, default=0)
    loyalty_points_used = db.Column(db.Integer, nullable=True, default=0)
    loyalty_discount = db.Column(db.Float, nullable=True, default=0)
    total_amount = db.Column(db.Float, nullable=True, default=0)
    loyalty_points_earned = db.Column(db.Integer, nullable=True, default=0)
    is_subscription_booking = db.Column(db.Boolean, nullable=True, default=False)
    customer_notes = db.Column(db.Text, nullable=True)
    area_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship("User", foreign_keys=[customer_id], backref="booking_rows")
    technician = db.relationship("Technician", foreign_keys=[technician_id], backref="bookings")

    @property
    def assigned_technician(self):
        return self.technician

    @property
    def resolution_notes(self):
        return self.customer_notes or ""

    @resolution_notes.setter
    def resolution_notes(self, value):
        self.customer_notes = value

    # --- GraphQL legacy: Ticket / ServiceBooking field aliases (not all are DB columns) ---

    @property
    def id(self):
        return self.booking_id

    @property
    def ticket_number(self):
        return self.booking_number

    @ticket_number.setter
    def ticket_number(self, value):
        self.booking_number = value

    @property
    def issue_description(self):
        return self.customer_notes or ""

    @issue_description.setter
    def issue_description(self, value):
        self.customer_notes = value

    @property
    def assigned_to(self):
        return self.technician_id

    @assigned_to.setter
    def assigned_to(self, value):
        self.technician_id = value

    @property
    def customer_name(self):
        if self.customer:
            fn = self.customer.first_name or ""
            ln = self.customer.last_name or ""
            return f"{fn} {ln}".strip() or None
        return None

    @property
    def customer_email(self):
        return self.customer.email if self.customer else None

    @property
    def customer_phone(self):
        return self.customer.phone if self.customer else None

    @property
    def priority(self):
        return "medium"

    @property
    def category_id(self):
        return None

    @property
    def asset_id(self):
        return None

    @property
    def service_type(self):
        return None

    @property
    def scheduled_date(self):
        return self.created_at

    @property
    def scheduled_time_slot(self):
        return None

    @property
    def service_status(self):
        return self.status

    @service_status.setter
    def service_status(self, value):
        self.status = value

    def __repr__(self):
        return f"<Booking {self.booking_id} {self.booking_number}>"
