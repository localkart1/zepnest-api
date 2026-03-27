from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv

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

        # For Postgres integrations with existing tables, skip create_all by default.
        # You can force-enable with AUTO_CREATE_TABLES=true.
        auto_create_tables_default = not database_url.startswith("postgresql")
        auto_create_tables = _parse_bool(
            os.getenv("AUTO_CREATE_TABLES"),
            default=auto_create_tables_default
        )

        if auto_create_tables:
            db.create_all()

        # Register GraphQL blueprint
        from api.graphql.schema import graphql_bp
        app.register_blueprint(graphql_bp)

        # Register REST compatibility routes for admin portal frontend.
        from api.rest.routes import rest_bp
        app.register_blueprint(rest_bp)

        from api.mobile.routes import mobile_bp
        app.register_blueprint(mobile_bp)

    return app
