from datetime import datetime

from sqlalchemy.orm import synonym

from api import db


class Escalation(db.Model):
    __tablename__ = "escalations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    booking_id = db.Column("booking_id", db.Integer, db.ForeignKey("bookings.booking_id"), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    escalated_to = db.Column(db.String(120), nullable=False)
    expected_resolution_time = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    booking = db.relationship("Booking", foreign_keys=[booking_id], backref="escalation_rows")
    ticket_id = synonym("booking_id")

    def __repr__(self):
        return f"<Escalation {self.id} booking={self.booking_id}>"


class ComplianceRecord(db.Model):
    __tablename__ = "compliance_records"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    technician_id = db.Column(db.Integer, db.ForeignKey("technician_profiles.technician_id"), nullable=False)
    compliance_type = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    issued_date = db.Column(db.DateTime, nullable=False)
    expiry_date = db.Column(db.DateTime, nullable=True)
    certification_document = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    technician = db.relationship("Technician", backref="compliance_records")

    @property
    def status(self):
        return "approved"

    def __repr__(self):
        return f"<ComplianceRecord {self.id}>"
