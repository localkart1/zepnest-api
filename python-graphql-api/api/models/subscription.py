from datetime import datetime

from api import db


class SubscriptionPlan(db.Model):
    """Maps to ``subscription_plans`` (same as REST ``/api/subscriptions/plans``)."""

    __tablename__ = "subscription_plans"

    plan_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    billing_cycle = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0)
    service_credits = db.Column(db.Integer, nullable=True, default=0)
    discount_percentage = db.Column(db.Float, nullable=True, default=0)
    priority_booking = db.Column(db.Boolean, nullable=True, default=False)
    free_inspection = db.Column(db.Boolean, nullable=True, default=False)
    benefits = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=True, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subscriptions = db.relationship("Subscription", back_populates="plan", lazy=True)

    @property
    def id(self):
        return self.plan_id

    @property
    def features(self):
        """GraphQL legacy name; DB column is ``benefits``."""
        return self.benefits

    def __repr__(self):
        return f"<SubscriptionPlan {self.plan_id} {self.name}>"


class Subscription(db.Model):
    """Maps to ``user_subscriptions`` (same as REST)."""

    __tablename__ = "user_subscriptions"

    subscription_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("subscription_plans.plan_id"), nullable=False)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    next_billing_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), nullable=True, default="active")
    credits_remaining = db.Column(db.Integer, nullable=True, default=0)
    credits_used = db.Column(db.Integer, nullable=True, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref="subscription_rows")
    plan = db.relationship("SubscriptionPlan", back_populates="subscriptions", foreign_keys=[plan_id])

    @property
    def id(self):
        return self.subscription_id

    @property
    def subscription_number(self):
        return f"SUB-{self.subscription_id}"

    @property
    def customer_id(self):
        return str(self.user_id) if self.user_id is not None else ""

    @property
    def customer_name(self):
        if self.user:
            fn = self.user.first_name or ""
            ln = self.user.last_name or ""
            return f"{fn} {ln}".strip() or None
        return None

    @property
    def customer_email(self):
        return self.user.email if self.user else None

    @property
    def total_amount(self):
        return float(self.plan.price) if self.plan else 0.0

    @property
    def paid_amount(self):
        return 0.0

    @property
    def currency(self):
        return "INR"

    @property
    def renewal_date(self):
        return self.next_billing_date

    def __repr__(self):
        return f"<Subscription {self.subscription_id}>"
