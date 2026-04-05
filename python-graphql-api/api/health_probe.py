"""
GET-only API probe (safe: no mutating requests). Used by ``GET /?full=1`` and ``GET /health/apis``.

Shared with ``scripts/api_sanity_probe.py`` for file reports.
"""
from __future__ import annotations

import re
from typing import Any

from api import db


def concrete_path(rule_str: str) -> str:
    s = rule_str
    if not s.startswith("/"):
        s = "/" + s
    return re.sub(r"<(?:[^:>]+:)?[^>]+>", "1", s)


def run_get_api_probe(app) -> dict[str, Any]:
    """
    Issue GET for every registered route that supports GET (placeholder path params = ``1``).
    Rolls back the SQLAlchemy session after each request.

    Returns a dict with ``get_results``, ``mutating_routes_not_probed``, ``summary``.
    """
    rows: list[dict] = []
    mutating: list[dict] = []

    with app.app_context():
        with app.test_client() as client:
            for rule in app.url_map.iter_rules():
                if rule.endpoint == "static":
                    continue
                path = rule.rule if rule.rule.startswith("/") else "/" + rule.rule
                conc = concrete_path(path)
                methods = sorted(rule.methods - {"OPTIONS", "HEAD"})

                if "GET" in methods:
                    try:
                        r = client.get(conc)
                        status = r.status_code
                    except Exception as e:
                        rows.append(
                            {
                                "method": "GET",
                                "path": conc,
                                "status": None,
                                "error": str(e)[:300],
                                "endpoint": rule.endpoint,
                            }
                        )
                        db.session.rollback()
                        continue
                    rows.append(
                        {
                            "method": "GET",
                            "path": conc,
                            "status": status,
                            "endpoint": rule.endpoint,
                        }
                    )
                    db.session.rollback()
                else:
                    for m in methods:
                        mutating.append(
                            {
                                "method": m,
                                "path": conc,
                                "endpoint": rule.endpoint,
                                "note": "not probed (mutating / use integration test)",
                            }
                        )

    seen: set[tuple[str, str]] = set()
    unique_get: list[dict] = []
    for r in rows:
        key = (r["method"], r["path"])
        if key in seen:
            continue
        seen.add(key)
        unique_get.append(r)
    unique_get.sort(key=lambda x: (x["path"], x["method"]))

    mut_sorted = sorted(mutating, key=lambda x: (x["path"], x["method"]))

    http_5xx = [
        x
        for x in unique_get
        if x.get("status") is not None and x["status"] >= 500
        or x.get("error")
    ]

    summary = {
        "probe": "GET-only; db.session.rollback() after each request",
        "get_routes_checked": len(unique_get),
        "get_routes_http_5xx_or_error": len(http_5xx),
        "mutating_routes_listed": len(mut_sorted),
        "healthy": len(http_5xx) == 0,
    }

    return {
        "get_results": unique_get,
        "mutating_routes_not_probed": mut_sorted,
        "summary": summary,
    }
