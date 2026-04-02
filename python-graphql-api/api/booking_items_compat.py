"""
booking_items table may use ``id`` (new scripts) or ``booking_item_id`` (legacy DBs).
Resolve the primary key column name once per process.
"""

from __future__ import annotations

from sqlalchemy import text

from api import db

_cached_pk: str | None = None


def booking_items_pk_column() -> str:
    """Return ``id`` or ``booking_item_id`` depending on the live database."""
    global _cached_pk
    if _cached_pk is not None:
        return _cached_pk
    try:
        row = (
            db.session.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'booking_items'
                      AND column_name IN ('id', 'booking_item_id')
                    ORDER BY CASE WHEN table_schema = 'public' THEN 0 ELSE 1 END,
                             CASE column_name WHEN 'id' THEN 0 ELSE 1 END
                    LIMIT 1
                    """
                )
            )
            .mappings()
            .first()
        )
        _cached_pk = row["column_name"] if row else "id"
    except Exception:
        _cached_pk = "id"
    return _cached_pk
