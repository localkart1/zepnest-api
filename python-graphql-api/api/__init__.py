import os
import json

from flask import Flask, jsonify, send_file, g, has_request_context, request
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from sqlalchemy import event

load_dotenv()

db = SQLAlchemy()


def _parse_bool(value: str, default: bool = False) -> bool:
    """Parse common truthy/falsey env var string values."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_engine_options(database_url: str) -> dict:
    """
    Build SQLAlchemy engine options.
    Supports Postgres schema selection via DB_SCHEMA.
    """
    engine_options = {}
    db_schema = os.getenv("DB_SCHEMA", "").strip()

    if database_url.startswith("postgresql") and db_schema:
        # Configure Postgres session search path for existing local schemas.
        engine_options["connect_args"] = {
            "options": f"-c search_path={db_schema}"
        }

    return engine_options


def _install_audit_logging(app: Flask) -> None:
    """
    Capture INSERT/UPDATE/DELETE SQL executed by this API process and write to ``audit_logs``.
    This is best-effort; if the table does not exist yet, requests must continue to work.
    """
    enabled = os.getenv("AUDIT_LOG_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
    if not enabled:
        return

    engine = db.engine
    if getattr(engine, "_audit_installed", False):
        return
    setattr(engine, "_audit_installed", True)

    @event.listens_for(engine, "after_cursor_execute")
    def _audit_dml(conn, cursor, statement, parameters, context, executemany):
        if conn.info.get("_audit_in_progress"):
            return
        if not has_request_context():
            return

        sql = (statement or "").lstrip()
        if not sql:
            return
        first = sql.split(None, 1)[0].upper() if sql.split(None, 1) else ""
        if first not in {"INSERT", "UPDATE", "DELETE"}:
            return
        if "audit_logs" in sql.lower():
            return

        low = sql.lower()
        table_name = None
        if first == "INSERT":
            marker = "insert into "
            idx = low.find(marker)
            if idx >= 0:
                table_name = low[idx + len(marker):].split("(", 1)[0].strip().split(".", 1)[-1]
        elif first == "UPDATE":
            marker = "update "
            idx = low.find(marker)
            if idx >= 0:
                table_name = low[idx + len(marker):].split(None, 1)[0].strip().split(".", 1)[-1]
        elif first == "DELETE":
            marker = "delete from "
            idx = low.find(marker)
            if idx >= 0:
                table_name = low[idx + len(marker):].split(None, 1)[0].strip().split(".", 1)[-1]

        actor_user_id = getattr(g, "web_user_id", None) or getattr(g, "mobile_user_id", None)
        actor_type = "web_user" if getattr(g, "web_user_id", None) else ("mobile_customer" if getattr(g, "mobile_user_id", None) else None)

        params_txt = json.dumps(parameters, default=str)[:8000]
        query_txt = json.dumps(request.args.to_dict(flat=False), default=str)[:4000]
        body_raw = request.get_json(silent=True) if request.mimetype == "application/json" else None
        body_txt = json.dumps(body_raw, default=str)[:8000] if body_raw is not None else None

        payload = {
            "actor_user_id": actor_user_id,
            "actor_type": actor_type,
            "action": first,
            "table_name": table_name,
            "http_method": request.method,
            "request_path": request.path,
            "endpoint": request.endpoint,
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": request.user_agent.string if request.user_agent else None,
            "sql_text": statement[:12000],
            "sql_params": params_txt,
            "request_query": query_txt,
            "request_body": body_txt,
        }

        try:
            # Use an independent DB transaction so audit failures never poison
            # the request transaction.
            with conn.engine.begin() as audit_conn:
                audit_conn.info["_audit_in_progress"] = True
                audit_conn.exec_driver_sql(
                    """
                    INSERT INTO audit_logs
                        (occurred_at, actor_user_id, actor_type, action, table_name, http_method, request_path,
                         endpoint, remote_addr, user_agent, sql_text, sql_params, request_query, request_body)
                    VALUES
                        (NOW(), :actor_user_id, :actor_type, :action, :table_name, :http_method, :request_path,
                         :endpoint, :remote_addr, :user_agent, :sql_text, :sql_params, :request_query, :request_body)
                    """,
                    payload,
                )
        except Exception:
            # Do not break API flow if audit table/insert fails.
            pass

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)

    # Configuration
    database_url = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key')
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = _build_engine_options(database_url)

    # Initialize database
    db.init_app(app)

    with app.app_context():
        # Import models
        from api.models.user import User
        from api.models.post import Post
        from api.models.technician import Technician
        from api.models.ticket import Ticket
        from api.models.service_catalog import Category, SubCategory, PriceMapping
        from api.models.subscription import SubscriptionPlan, Subscription
        from api.models.booking import Booking
        from api.models.asset import Asset, AssetRegistry, WarrantyTracking, AssetServiceMapping
        from api.models.escalation_compliance import Escalation, ComplianceRecord
        from api.models.mobile_otp import MobileOtpSession
        from api.models.customer_address import CustomerAddress
        from api.models.address import Address
        from api.models.audit_log import AuditLog

        # For Postgres integrations with existing tables, skip create_all by default.
        # You can force-enable with AUTO_CREATE_TABLES=true.
        auto_create_tables_default = not database_url.startswith("postgresql")
        auto_create_tables = _parse_bool(
            os.getenv("AUTO_CREATE_TABLES"),
            default=auto_create_tables_default
        )

        if auto_create_tables:
            db.create_all()

        _install_audit_logging(app)

        # Register GraphQL blueprint
        from api.graphql.schema import graphql_bp
        app.register_blueprint(graphql_bp)

        # Register REST compatibility routes for admin portal frontend.
        from api.rest.routes import rest_bp
        app.register_blueprint(rest_bp)

        from api.web_auth import web_auth_bp
        app.register_blueprint(web_auth_bp)

        from api.mobile.routes import mobile_bp
        app.register_blueprint(mobile_bp)

        _openapi_json = os.path.join(os.path.dirname(os.path.dirname(__file__)), "openapi.json")

        @app.get("/openapi.json")
        def serve_openapi_json():
            """Combined OpenAPI 3 spec (web `/api` + mobile `/mobile`) for Postman / Swagger import."""
            if not os.path.isfile(_openapi_json):
                return (
                    jsonify(
                        {
                            "message": "openapi.json not found. Run: python scripts/build_openapi_json.py",
                        }
                    ),
                    404,
                )
            return send_file(_openapi_json, mimetype="application/json", max_age=300)

    return app
