"""
Canonical list of PostgreSQL tables and columns referenced by raw SQL in:

- ``api/rest/routes.py`` — admin/web REST API (prefix ``/api``)
- ``api/mobile/routes.py`` — mobile API (prefix ``/mobile``)

Run ``scripts/validate_api_db_schema.py`` against your DATABASE_URL to verify the live
database includes these objects. GraphQL uses separate SQLAlchemy models and is not
covered here.

Column names match the queries (typically snake_case). If your DB uses different
names, align the DB or update the queries and this contract together.
"""

from __future__ import annotations

# --- Web REST (/api) — api/rest/routes.py ---
API_REST_TABLE_COLUMNS: dict[str, frozenset[str]] = {
    "users": frozenset(
        {
            "user_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "user_type",
            "loyalty_points",
            "is_active",
            "created_at",
            "updated_at",
            "password_hash",
            "internal_notes",
        }
    ),
    "technician_profiles": frozenset(
        {
            "technician_id",
            "user_id",
            "specialization",
            "experience_years",
            "bio",
            "hourly_rate",
            "certification",
            "rating",
            "total_reviews",
            "status",
            "created_at",
        }
    ),
    "bookings": frozenset(
        {
            "booking_id",
            "booking_number",
            "customer_id",
            "technician_id",
            "service_address",
            "status",
            "subtotal",
            "discount_amount",
            "loyalty_points_used",
            "loyalty_discount",
            "total_amount",
            "loyalty_points_earned",
            "is_subscription_booking",
            "customer_notes",
            "created_at",
            "updated_at",
            "area_id",
        }
    ),
    "booking_items": frozenset(
        {
            "id",
            "booking_id",
            "service_id",
            "quantity",
            "unit_price",
            "total_price",
            "voice_url",
            "video_url",
            "image_url",
            "notes",
            "created_at",
            "updated_at",
        }
    ),
    "addresses": frozenset(
        {
            "id",
            "user_id",
            "label",
            "line1",
            "line2",
            "city",
            "state",
            "zip_code",
            "country",
            "address_type",
            "is_default",
            "created_at",
            "updated_at",
        }
    ),
    "service_areas": frozenset({"area_id", "zipcode", "city"}),
    "categories": frozenset(
        {
            "id",
            "name",
            "description",
            "icon",
            "is_active",
            "created_at",
            "updated_at",
        }
    ),
    "sub_categories": frozenset(
        {
            "id",
            "category_id",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        }
    ),
    "price_mappings": frozenset(
        {
            "id",
            "category_id",
            "sub_category_id",
            "service_name",
            "service_type",
            "base_price",
            "gst_percentage",
            "total_price",
            "unit",
            "is_active",
            "created_at",
            "updated_at",
        }
    ),
    "services": frozenset(
        {
            "service_id",
            "name",
            "description",
            "base_price",
            "estimated_duration_mins",
            "category",
            "category_id",
            "image_url",
            "is_active",
            "loyalty_points_earned",
            "created_at",
            "updated_at",
        }
    ),
    "service_addons": frozenset(
        {"addon_id", "service_id", "name", "description", "price", "is_active", "created_at"}
    ),
    "service_warranties": frozenset(
        {
            "warranty_id",
            "service_id",
            "name",
            "description",
            "duration_days",
            "coverage_details",
            "exclusions",
            "is_active",
            "created_at",
        }
    ),
    "service_packages": frozenset(
        {
            "package_id",
            "name",
            "description",
            "package_price",
            "discount_percentage",
            "image_url",
            "is_active",
            "loyalty_points_earned",
            "valid_from",
            "valid_until",
            "created_at",
        }
    ),
    "subscription_plans": frozenset(
        {
            "plan_id",
            "name",
            "description",
            "billing_cycle",
            "price",
            "service_credits",
            "discount_percentage",
            "priority_booking",
            "free_inspection",
            "benefits",
            "is_active",
            "created_at",
        }
    ),
    "user_subscriptions": frozenset(
        {
            "subscription_id",
            "user_id",
            "plan_id",
            "start_date",
            "end_date",
            "next_billing_date",
            "status",
            "credits_remaining",
            "credits_used",
            "created_at",
            "updated_at",
        }
    ),
    "payments": frozenset(
        {
            "payment_id",
            "booking_id",
            "amount",
            "payment_method",
            "status",
            "transaction_id",
            "payment_date",
            "created_at",
        }
    ),
    "reviews": frozenset(
        {
            "review_id",
            "booking_id",
            "customer_id",
            "technician_id",
            "rating",
            "title",
            "review_text",
            "is_active",
            "created_at",
            "updated_at",
        }
    ),
    "audit_logs": frozenset(
        {
            "id",
            "occurred_at",
            "actor_user_id",
            "actor_type",
            "action",
            "table_name",
            "http_method",
            "request_path",
            "endpoint",
            "remote_addr",
            "user_agent",
            "sql_text",
            "sql_params",
            "request_query",
            "request_body",
        }
    ),
}

# --- Mobile (/mobile) — api/mobile/routes.py ---
API_MOBILE_TABLE_COLUMNS: dict[str, frozenset[str]] = {
    "users": frozenset(
        {
            "user_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "user_type",
            "loyalty_points",
            "is_active",
            "created_at",
            "updated_at",
            "password_hash",
        }
    ),
    "categories": frozenset(
        {
            "id",
            "name",
            "description",
            "icon",
            "is_active",
            "created_at",
            "updated_at",
        }
    ),
    "sub_categories": frozenset(
        {
            "id",
            "category_id",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        }
    ),
    "services": frozenset(
        {
            "service_id",
            "name",
            "description",
            "base_price",
            "estimated_duration_mins",
            "category",
            "category_id",
            "image_url",
            "is_active",
            "created_at",
            "updated_at",
        }
    ),
    "bookings": frozenset(
        {
            "booking_id",
            "booking_number",
            "customer_id",
            "technician_id",
            "service_address",
            "status",
            "subtotal",
            "discount_amount",
            "loyalty_points_used",
            "loyalty_discount",
            "total_amount",
            "loyalty_points_earned",
            "is_subscription_booking",
            "customer_notes",
            "created_at",
            "updated_at",
        }
    ),
    "booking_items": frozenset(
        {
            "id",
            "booking_id",
            "service_id",
            "quantity",
            "unit_price",
            "total_price",
            "voice_url",
            "video_url",
            "image_url",
            "notes",
            "created_at",
            "updated_at",
        }
    ),
    "addresses": frozenset(
        {
            "id",
            "user_id",
            "label",
            "line1",
            "line2",
            "city",
            "state",
            "zip_code",
            "country",
            "address_type",
            "is_default",
            "created_at",
            "updated_at",
        }
    ),
    "mobile_otp_sessions": frozenset(
        {"id", "phone", "otp_hash", "expires_at", "consumed", "created_at"}
    ),
    "customer_addresses": frozenset(
        {
            "id",
            "user_id",
            "label",
            "line1",
            "line2",
            "city",
            "state",
            "zip_code",
            "country",
            "is_default",
            "created_at",
            "updated_at",
        }
    ),
    "audit_logs": frozenset(
        {
            "id",
            "occurred_at",
            "actor_user_id",
            "actor_type",
            "action",
            "table_name",
            "http_method",
            "request_path",
            "endpoint",
            "remote_addr",
            "user_agent",
            "sql_text",
            "sql_params",
            "request_query",
            "request_body",
        }
    ),
}


def merged_api_table_columns() -> dict[str, frozenset[str]]:
    """Union of REST + mobile required columns per table."""
    out: dict[str, set[str]] = {}
    for t, cols in API_REST_TABLE_COLUMNS.items():
        out.setdefault(t, set()).update(cols)
    for t, cols in API_MOBILE_TABLE_COLUMNS.items():
        out.setdefault(t, set()).update(cols)
    return {t: frozenset(c) for t, c in out.items()}


def table_used_by(which: str, table: str) -> bool:
    if which == "rest":
        return table in API_REST_TABLE_COLUMNS
    if which == "mobile":
        return table in API_MOBILE_TABLE_COLUMNS
    raise ValueError("which must be 'rest' or 'mobile'")
