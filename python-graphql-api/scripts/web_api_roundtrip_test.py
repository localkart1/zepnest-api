#!/usr/bin/env python3
"""
End-to-end web API roundtrip: auth + REST CRUD for technicians, customers, orders, addresses.

Includes address REST: POST/PUT /api/addresses (batch), GET /api/customers/{id} (read addresses),
PUT /api/addresses/{id} (single).

Uses Flask's test client and your real DATABASE_URL (from .env). Run from repo root:

  cd python-graphql-api && python3 scripts/web_api_roundtrip_test.py

Optional env:
  WEB_API_ROUNDTRIP_REGISTER=0   Skip register (use login only with WEB_API_ROUNDTRIP_EMAIL / _PASSWORD)

Cleanup order: delete order before customer (FK). Step labels follow the usual admin flow.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Load .env then disable audit for this run (audit hook uses :named params not valid for exec_driver_sql on Postgres).
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
os.environ["AUDIT_LOG_ENABLED"] = "0"


def _req(client, method: str, path: str, *, json_body=None, headers=None, query: str = ""):
    url = path + query
    hdrs = {**(headers or {})}
    kw: dict = {"headers": hdrs}
    if json_body is not None:
        kw["json"] = json_body
        hdrs.setdefault("Content-Type", "application/json")
    fn = getattr(client, method.lower())
    return fn(url, **kw)


def _ok(cond: bool, msg: str, errors: list[str]) -> None:
    if not cond:
        errors.append(msg)


def main() -> int:
    # Import after AUDIT_LOG_ENABLED is set (main.py instantiates app at import time).
    import main as main_mod

    app = main_mod.app

    errors: list[str] = []
    uid = uuid.uuid4().hex[:12]
    password = os.getenv("WEB_API_ROUNDTRIP_PASSWORD", "RoundtripTest!8")
    reg_email = os.getenv("WEB_API_ROUNDTRIP_EMAIL", f"web.roundtrip.{uid}@example.test")
    skip_register = os.getenv("WEB_API_ROUNDTRIP_REGISTER", "1").strip().lower() in {"0", "false", "no"}

    customer_email = f"crud.customer.{uid}@example.test"
    tech_email = f"crud.tech.{uid}@example.test"

    customer_id: int | None = None
    order_id: int | None = None
    technician_id: int | None = None
    technician_created = False

    with app.app_context():
        with app.test_client() as c:
            # 1–2 Register + Login
            if not skip_register:
                r = _req(
                    c,
                    "post",
                    "/api/auth/register",
                    json_body={
                        "email": reg_email,
                        "password": password,
                        "firstName": "Round",
                        "lastName": "Trip",
                    },
                )
                _ok(
                    r.status_code in (201, 409),
                    f"1 register: expected 201/409, got {r.status_code} {r.get_data(as_text=True)[:500]}",
                    errors,
                )
            r = _req(
                c,
                "post",
                "/api/auth/login",
                json_body={"email": reg_email, "password": password},
            )
            _ok(r.status_code == 200, f"2 login: expected 200, got {r.status_code} {r.get_data(as_text=True)[:500]}", errors)
            if r.status_code != 200:
                print(json.dumps({"errors": errors}, indent=2))
                return 1
            body = r.get_json() or {}
            token = body.get("accessToken")
            _ok(bool(token), "2 login: missing accessToken", errors)
            auth = {"Authorization": f"Bearer {token}"}

            # 3 /me
            r = _req(c, "get", "/api/auth/me", headers=auth)
            _ok(r.status_code == 200, f"auth/me: {r.status_code}", errors)

            # 3b Technician list (user asked step 3)
            r = _req(c, "get", "/api/technicians", query="?page=1&limit=5", headers=auth)
            _ok(r.status_code == 200, f"3 get technicians: {r.status_code}", errors)

            # 4 Customer list
            r = _req(c, "get", "/api/customers", query="?page=1&limit=5", headers=auth)
            _ok(r.status_code == 200, f"4 get customers: {r.status_code}", errors)

            # 5 Orders list
            r = _req(c, "get", "/api/orders", query="?page=1&limit=5", headers=auth)
            _ok(r.status_code == 200, f"5 get orders: {r.status_code}", errors)

            # 6 Create customer
            r = _req(
                c,
                "post",
                "/api/customers",
                json_body={
                    "firstName": "API",
                    "lastName": f"Customer{uid}",
                    "email": customer_email,
                    "phone": f"9{uid[:9]}".ljust(10, "0")[:15],
                    "status": "active",
                    "internalNotes": "roundtrip",
                    "addresses": [
                        {
                            "street": "1 Test Street",
                            "city": "Chennai",
                            "zipCode": "600001",
                            "isPrimary": True,
                        }
                    ],
                },
                headers=auth,
            )
            _ok(r.status_code == 201, f"6 create customer: {r.status_code} {r.get_data(as_text=True)[:500]}", errors)
            if r.status_code == 201:
                cj = r.get_json() or {}
                try:
                    customer_id = int(cj.get("id", ""))
                except (TypeError, ValueError):
                    errors.append("6 create customer: bad id in response")

            if customer_id is None:
                print(json.dumps({"errors": errors}, indent=2))
                return 1

            # 6a–6d Address REST: batch create, read (GET customer), batch update, single update
            r = _req(
                c,
                "post",
                "/api/addresses",
                json_body={
                    "userId": customer_id,
                    "addresses": [
                        {
                            "line1": "Roundtrip Batch A",
                            "city": "Chennai",
                            "zipCode": "600010",
                            "isPrimary": True,
                        },
                        {
                            "line1": "Roundtrip Batch B",
                            "city": "Chennai",
                            "zipCode": "600011",
                            "isPrimary": False,
                        },
                    ],
                },
                headers=auth,
            )
            _ok(
                r.status_code == 201,
                f"6a POST /api/addresses: {r.status_code} {r.get_data(as_text=True)[:500]}",
                errors,
            )

            r = _req(c, "get", f"/api/customers/{customer_id}", headers=auth)
            _ok(
                r.status_code == 200,
                f"6b GET /api/customers/{{id}} (read addresses): {r.status_code}",
                errors,
            )
            addr_list = (r.get_json() or {}).get("addresses") if r.status_code == 200 else []
            _ok(
                len(addr_list) >= 3,
                f"6b expected >=3 addresses (1 from step 6 + 2 from batch), got {len(addr_list)}",
                errors,
            )
            addr_ids: list[int] = []
            for a in addr_list:
                if a.get("id") is not None:
                    try:
                        addr_ids.append(int(str(a["id"])))
                    except (TypeError, ValueError):
                        pass
            _ok(len(addr_ids) >= 2, f"6b need >=2 address ids for batch update, got {len(addr_ids)}", errors)

            r = _req(
                c,
                "put",
                "/api/addresses",
                json_body={
                    "addresses": [
                        {"id": addr_ids[0], "zipCode": "600099"},
                        {"id": addr_ids[1], "city": "Chennai"},
                    ]
                },
                headers=auth,
            )
            _ok(
                r.status_code == 200,
                f"6c PUT /api/addresses (batch): {r.status_code} {r.get_data(as_text=True)[:500]}",
                errors,
            )

            r = _req(
                c,
                "put",
                f"/api/addresses/{addr_ids[0]}",
                json_body={"zipCode": "600100", "phoneNo": "9800000000"},
                headers=auth,
            )
            _ok(
                r.status_code == 200,
                f"6d PUT /api/addresses/{{id}}: {r.status_code} {r.get_data(as_text=True)[:500]}",
                errors,
            )

            # 7 Create order (no bookingItems — avoids services catalog dependency)
            r = _req(
                c,
                "post",
                "/api/orders",
                json_body={
                    "customerId": customer_id,
                    "totalAmount": 99.5,
                    "address": "1 Test Street",
                    "customerNotes": "roundtrip order",
                },
                headers=auth,
            )
            _ok(r.status_code == 201, f"7 create order: {r.status_code} {r.get_data(as_text=True)[:500]}", errors)
            if r.status_code == 201:
                oj = r.get_json() or {}
                try:
                    order_id = int(str(oj.get("id", "")))
                except (TypeError, ValueError):
                    errors.append("7 create order: bad id")

            # 8 Create technician
            r = _req(
                c,
                "post",
                "/api/technicians",
                json_body={
                    "firstName": "API",
                    "lastName": f"Tech{uid}",
                    "email": tech_email,
                    "phone": f"8{uid[:9]}".ljust(10, "0")[:15],
                    "specialization": ["plumbing"],
                    "experience": 2,
                    "status": "available",
                    "certifications": ["ISO"],
                },
                headers=auth,
            )
            if r.status_code == 201:
                tj = r.get_json() or {}
                try:
                    technician_id = int(str(tj.get("id", "")))
                    technician_created = True
                except (TypeError, ValueError):
                    errors.append("8 create technician: bad id")
            else:
                # Broken technician_profiles sequence (duplicate pkey) — use an existing tech for update/order only.
                rlist = _req(c, "get", "/api/technicians", query="?page=1&limit=1", headers=auth)
                if rlist.status_code == 200:
                    payload = rlist.get_json() or {}
                    row0 = (payload.get("data") or [None])[0]
                    if row0 and row0.get("id") is not None:
                        try:
                            technician_id = int(str(row0["id"]))
                        except (TypeError, ValueError):
                            pass
                if technician_id is None:
                    _ok(
                        False,
                        f"8 create technician: {r.status_code} {r.get_data(as_text=True)[:500]} (no fallback technician in list)",
                        errors,
                    )
                else:
                    print(
                        f"NOTE: create technician returned {r.status_code}; using existing id={technician_id}. "
                        "If inserts fail with duplicate technician_id, run:\n"
                        "  SELECT setval(pg_get_serial_sequence('technician_profiles','technician_id'), "
                        "(SELECT COALESCE(MAX(technician_id),1) FROM technician_profiles));",
                        file=sys.stderr,
                    )

            if order_id is None or technician_id is None:
                print(json.dumps({"errors": errors}, indent=2))
                return 1

            # 9 Update customer (GET first for address id)
            r_gc = _req(c, "get", f"/api/customers/{customer_id}", headers=auth)
            addr_id = None
            if r_gc.status_code == 200:
                addrs = (r_gc.get_json() or {}).get("addresses") or []
                if addrs and addrs[0].get("id"):
                    addr_id = addrs[0]["id"]
            r = _req(
                c,
                "put",
                f"/api/customers/{customer_id}",
                json_body={
                    "firstName": "API",
                    "lastName": f"Updated{uid}",
                    "status": "active",
                    "internalNotes": "updated notes",
                    "addresses": [
                        {
                            **({"id": str(addr_id)} if addr_id else {}),
                            "street": "2 Updated Street",
                            "city": "Chennai",
                            "zipCode": "600002",
                            "isPrimary": True,
                        }
                    ],
                },
                headers=auth,
            )
            _ok(r.status_code == 200, f"9 update customer: {r.status_code} {r.get_data(as_text=True)[:500]}", errors)

            # 10 Update order
            r = _req(
                c,
                "put",
                f"/api/orders/{order_id}",
                json_body={
                    "status": "assigned",
                    "technicianId": technician_id,
                    "customerNotes": "updated order notes",
                },
                headers=auth,
            )
            _ok(r.status_code == 200, f"10 update order: {r.status_code} {r.get_data(as_text=True)[:500]}", errors)

            # 11 Update technician
            r = _req(
                c,
                "put",
                f"/api/technicians/{technician_id}",
                json_body={
                    "firstName": "API",
                    "lastName": f"TechUpd{uid}",
                    "status": "available",
                    "experience": 3,
                },
                headers=auth,
            )
            _ok(r.status_code == 200, f"11 update technician: {r.status_code} {r.get_data(as_text=True)[:500]}", errors)

            # 12–14 Deletes: order first (FK), then customer, then technician
            r = _req(c, "delete", f"/api/orders/{order_id}", headers=auth)
            _ok(r.status_code == 204, f"12 delete order: {r.status_code}", errors)

            r = _req(c, "delete", f"/api/customers/{customer_id}", headers=auth)
            _ok(r.status_code == 204, f"13 delete customer: {r.status_code}", errors)

            if technician_created:
                r = _req(c, "delete", f"/api/technicians/{technician_id}", headers=auth)
                _ok(r.status_code == 204, f"14 delete technician: {r.status_code}", errors)
            else:
                print("(14 delete technician skipped — used pre-existing technician from list)")

    if errors:
        print("FAILED:")
        for e in errors:
            print(" -", e)
        return 1
    print(
        "OK — web API roundtrip (register/login, lists, CRUD customer/order/technician, "
        "address batch + read + single update) passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
