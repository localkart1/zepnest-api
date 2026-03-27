#!/usr/bin/env python3
"""
Verify that the live database has all tables and columns required by:

- Web REST: ``api/rest/routes.py`` (``/api``)
- Mobile: ``api/mobile/routes.py`` (``/mobile``)

Uses ``api/db_schema_contract.py`` as the source of truth.

Usage:
  ./venv/bin/python scripts/validate_api_db_schema.py

Exit code 0 if aligned, 1 if gaps are found.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api import create_app, db
from api.db_schema_contract import (
    API_MOBILE_TABLE_COLUMNS,
    API_REST_TABLE_COLUMNS,
    merged_api_table_columns,
)


def main() -> int:
    app = create_app()
    merged = merged_api_table_columns()

    with app.app_context():
        inspector = inspect(db.engine)
        actual_schema = None
        db_url = db.engine.url
        print("=== API DB schema validation (Web /api + Mobile /mobile) ===")
        print(f"Database: {db_url}")
        print("")

        has_errors = False

        for table in sorted(merged.keys()):
            required = merged[table]
            tags = []
            if table in API_REST_TABLE_COLUMNS:
                tags.append("web")
            if table in API_MOBILE_TABLE_COLUMNS:
                tags.append("mobile")
            tag_str = ", ".join(tags)

            if table not in inspector.get_table_names(schema=actual_schema):
                has_errors = True
                print(f"[MISSING TABLE] {table}  [{tag_str}]")
                print(f"  Expected columns: {', '.join(sorted(required))}")
                continue

            db_cols = {c["name"] for c in inspector.get_columns(table, schema=actual_schema)}
            missing = sorted(required - db_cols)
            if missing:
                has_errors = True
                print(f"[MISSING COLUMNS] {table}  [{tag_str}]")
                for col in missing:
                    print(f"  - {col}")
                extra = sorted(db_cols - required)
                if extra:
                    print(f"  (DB has extra columns not listed in contract: {', '.join(extra[:12])}{'...' if len(extra) > 12 else ''})")
            else:
                print(f"[OK] {table}  [{tag_str}]")

        print("")
        if has_errors:
            print(
                "Result: Gaps found. Create missing tables/columns or run migrations "
                "(e.g. scripts/create_mobile_otp_table.sql, scripts/create_customer_addresses_table.sql)."
            )
            print("GraphQL is not validated here; see scripts/compare_db_schema.py for ORM vs DB.")
            return 1

        print("Result: Web and mobile API layers match the declared DB contract.")
        print("GraphQL is not validated here; see scripts/compare_db_schema.py for ORM vs DB.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
