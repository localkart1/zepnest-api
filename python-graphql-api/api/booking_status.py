"""
Booking status strings for ``bookings.status``.

If the database uses PostgreSQL enum ``booking_status_enum``, every value the API writes
must be a valid enum label. The codebase historically used ``new``, which is often
not present on enums created elsewhere — set ``BOOKING_STATUS_DEFAULT`` (and related
vars) in ``.env`` to match your database.
"""

from __future__ import annotations

import os


def _csv(name: str, default: str) -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(s.strip() for s in raw.split(",") if s.strip())


# Insert default for POST /api/orders, mobile bookings, GraphQL creates, etc.
DEFAULT_BOOKING_STATUS = os.getenv("BOOKING_STATUS_DEFAULT", "pending")

# Treated as "not assigned yet" → assign technician moves to ASSIGNED_BOOKING_STATUS.
OPEN_BOOKING_STATUSES: frozenset[str] = frozenset(
    _csv("BOOKING_STATUS_OPEN", "pending,open,under_review")
)

# Dashboard "open pipeline" count (REST stats). Labels must exist on ``booking_status_enum``.
PIPELINE_BOOKING_STATUSES: tuple[str, ...] = _csv(
    "BOOKING_STATUS_PIPELINE",
    "pending,under_review,assigned,in_progress,open",
)

ASSIGNED_BOOKING_STATUS = os.getenv("BOOKING_STATUS_ASSIGNED", "assigned")


def sql_in_text(values: tuple[str, ...] | frozenset[str]) -> str:
    """Comma-separated single-quoted literals for ``IN (...)`` (status labels are trusted config)."""
    seq = sorted(values) if isinstance(values, frozenset) else values
    return ",".join("'" + v.replace("'", "''") + "'" for v in seq)
