#!/usr/bin/env python3
"""
Probe Flask routes safely: **GET only** (no POST/PUT/PATCH/DELETE) plus rollback after each
request so the DB session is not left aborted.

Uses ``api.health_probe.run_get_api_probe`` (same logic as ``GET /health/apis``).

Writes:
  docs/api_sanity_report.json
  docs/api_sanity_report.md

Usage:

  cd python-graphql-api && .venv/bin/python scripts/api_sanity_probe.py

Env: AUDIT_LOG_ENABLED=0 (set by script)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

os.environ.setdefault("AUDIT_LOG_ENABLED", "0")

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    import main as main_mod

    from api.health_probe import run_get_api_probe

    app = main_mod.app
    with app.app_context():
        probe = run_get_api_probe(app)

    out = {
        "generated_by": "scripts/api_sanity_probe.py",
        **probe,
    }

    out_json = ROOT / "docs" / "api_sanity_report.json"
    out_md = ROOT / "docs" / "api_sanity_report.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(out, indent=2), encoding="utf-8")

    unique_get = out["get_results"]
    mut_sorted = out["mutating_routes_not_probed"]

    lines = [
        "# API sanity report (GET probe)",
        "",
        "See also **`API_STATUS_CODES.md`** (typical codes per area).",
        "",
        "Same data as **`GET /health/apis`** or **`GET /?full=1`** on the running server.",
        "",
        "Safe probe: **GET only**, rollback after each request. Mutating routes are listed but not called.",
        "",
        "## GET responses",
        "",
        "| Method | Path | HTTP status | Endpoint |",
        "|--------|------|---------------|----------|",
    ]
    for r in unique_get:
        st = r.get("status")
        err = r.get("error")
        if err:
            st_disp = "ERR"
        else:
            st_disp = str(st)
        lines.append(
            f"| GET | `{r['path']}` | {st_disp} | `{r.get('endpoint', '')}` |"
        )
    lines.extend(
        [
            "",
            "## Routes without GET (not probed)",
            "",
            "| Method | Path | Endpoint |",
            "|--------|------|----------|",
        ]
    )
    for r in mut_sorted:
        lines.append(
            f"| {r['method']} | `{r['path']}` | `{r.get('endpoint', '')}` |"
        )
    lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {out_json} ({len(unique_get)} GET rows, {len(mut_sorted)} mutating listed)")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
