"""
GraphQL category/subcategory fallbacks when normalized tables
(``categories``, ``sub_categories``, ``price_mappings``) are not present.

Production DB uses ``services.category`` (text) per ``api/db_schema_contract.py``.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from api import db


def is_missing_relation_error(exc: Exception) -> bool:
    orig = getattr(exc, "orig", None) or exc
    s = str(orig).lower()
    return (
        "undefinedtable" in s
        or "undefinedcolumn" in s
        or "does not exist" in s
        or "no such table" in s
    )


def stable_category_id(name: str) -> int:
    """Deterministic positive int from category label (for GraphQL ``id``)."""
    h = hashlib.md5(name.strip().encode("utf-8")).hexdigest()
    return int(h[:8], 16) % (2**31 - 1) or 1


def categories_from_services_table() -> list[SimpleNamespace]:
    rows = db.session.execute(
        text(
            """
            SELECT DISTINCT TRIM(category) AS name
            FROM services
            WHERE category IS NOT NULL AND TRIM(category) <> ''
            ORDER BY 1
            """
        )
    ).mappings().all()
    out: list[SimpleNamespace] = []
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        out.append(
            SimpleNamespace(
                id=stable_category_id(name),
                name=name,
                description=None,
                icon=None,
                is_active=True,
                created_at=None,
                updated_at=None,
                sub_categories=[],
            )
        )
    return out


def category_from_services_by_graphql_id(cat_id: int) -> SimpleNamespace | None:
    for obj in categories_from_services_table():
        if obj.id == cat_id:
            return obj
    return None


def run_or_empty_list(query_fn):
    """Run a SQLAlchemy query; return [] if the underlying table is missing."""
    try:
        return query_fn()
    except ProgrammingError as e:
        if is_missing_relation_error(e):
            return []
        raise


def run_or_services_categories(query_fn):
    try:
        return query_fn()
    except ProgrammingError as e:
        if is_missing_relation_error(e):
            return categories_from_services_table()
        raise


def run_or_none_subcategory(query_fn, sid: int):
    try:
        return query_fn()
    except ProgrammingError as e:
        if is_missing_relation_error(e):
            return None
        raise


def run_or_none_price_mapping(query_fn, mid: int):
    try:
        return query_fn()
    except ProgrammingError as e:
        if is_missing_relation_error(e):
            return None
        raise
