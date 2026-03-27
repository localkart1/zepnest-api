#!/usr/bin/env python3
"""
Compare SQLAlchemy model metadata with the configured live database schema.

For raw-SQL **web + mobile REST** APIs (`/api`, `/mobile`), use instead:
  ./venv/bin/python scripts/validate_api_db_schema.py

Usage:
  ./venv/bin/python scripts/compare_db_schema.py
"""

import sys
from pathlib import Path
from collections import defaultdict

from sqlalchemy import inspect

# Ensure project root is importable when running from scripts/.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api import create_app, db


def _model_tables():
    """Return declared model tables grouped by schema."""
    grouped = defaultdict(list)
    for table in db.Model.metadata.tables.values():
        schema = table.schema or "default"
        grouped[schema].append(table)
    return grouped


def main() -> int:
    app = create_app()

    with app.app_context():
        inspector = inspect(db.engine)
        report_has_diff = False

        print("=== DB Schema Compare ===")
        print(f"Connected DB: {db.engine.url}")
        print("")

        for schema, tables in sorted(_model_tables().items()):
            actual_schema = None if schema == "default" else schema
            print(f"[Schema: {schema}]")

            db_tables = set(inspector.get_table_names(schema=actual_schema))
            model_tables = set(t.name for t in tables)

            missing_in_db = sorted(model_tables - db_tables)
            extra_in_db = sorted(db_tables - model_tables)

            if missing_in_db:
                report_has_diff = True
                print("  Missing tables in DB:")
                for table_name in missing_in_db:
                    print(f"    - {table_name}")

            if extra_in_db:
                print("  Extra tables in DB (not in current models):")
                for table_name in extra_in_db:
                    print(f"    - {table_name}")

            for table in sorted(tables, key=lambda t: t.name):
                if table.name not in db_tables:
                    continue

                model_cols = set(col.name for col in table.columns)
                db_cols = set(col["name"] for col in inspector.get_columns(table.name, schema=actual_schema))

                missing_cols = sorted(model_cols - db_cols)
                extra_cols = sorted(db_cols - model_cols)

                if missing_cols or extra_cols:
                    report_has_diff = True
                    print(f"  Table: {table.name}")
                    if missing_cols:
                        print("    Missing columns in DB:")
                        for col in missing_cols:
                            print(f"      - {col}")
                    if extra_cols:
                        print("    Extra columns in DB:")
                        for col in extra_cols:
                            print(f"      - {col}")

            print("")

        if report_has_diff:
            print("Result: Differences detected.")
            return 1

        print("Result: Models and DB schema are aligned.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
