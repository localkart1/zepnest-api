from datetime import datetime

from api import db


class AuditLog(db.Model):
    """DB-level change log for DML statements executed by this API process."""

    __tablename__ = "audit_logs"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    occurred_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    actor_user_id = db.Column(db.Integer, nullable=True, index=True)
    actor_type = db.Column(db.String(32), nullable=True)
    action = db.Column(db.String(16), nullable=False)  # INSERT/UPDATE/DELETE
    table_name = db.Column(db.String(128), nullable=True, index=True)
    http_method = db.Column(db.String(10), nullable=True)
    request_path = db.Column(db.String(255), nullable=True)
    endpoint = db.Column(db.String(128), nullable=True)
    remote_addr = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    sql_text = db.Column(db.Text, nullable=False)
    sql_params = db.Column(db.Text, nullable=True)
    request_query = db.Column(db.Text, nullable=True)
    request_body = db.Column(db.Text, nullable=True)

