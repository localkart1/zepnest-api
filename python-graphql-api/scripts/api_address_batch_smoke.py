#!/usr/bin/env python3
"""Smoke test address batch REST + mobile (requires same .env as web roundtrip)."""
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

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
os.environ["AUDIT_LOG_ENABLED"] = "0"


def _req(c, method: str, path: str, *, json_body=None, headers=None, query: str = ""):
    url = path + query
    hdrs = {**(headers or {})}
    kw: dict = {"headers": hdrs}
    if json_body is not None:
        kw["json"] = json_body
        hdrs.setdefault("Content-Type", "application/json")
    return getattr(c, method.lower())(url, **kw)


def main() -> int:
    import main as main_mod

    app = main_mod.app
    uid = uuid.uuid4().hex[:12]
    password = os.getenv("WEB_API_ROUNDTRIP_PASSWORD", "RoundtripTest!8")
    reg_email = os.getenv("WEB_API_ROUNDTRIP_EMAIL", f"addr.batch.{uid}@example.test")
    rows: list[tuple[str, str, str, int, str]] = []

    with app.app_context():
        with app.test_client() as c:
            _req(
                c,
                "post",
                "/api/auth/register",
                json_body={
                    "email": reg_email,
                    "password": password,
                    "firstName": "Addr",
                    "lastName": "Batch",
                },
            )
            r = _req(
                c,
                "post",
                "/api/auth/login",
                json_body={"email": reg_email, "password": password},
            )
            rows.append(("Web", "POST", "/api/auth/login", r.status_code, ""))
            if r.status_code != 200:
                print(json.dumps({"login": r.status_code, "body": r.get_data(as_text=True)[:400]}))
                return 1
            token = (r.get_json() or {}).get("accessToken")
            auth = {"Authorization": f"Bearer {token}"}

            cust_email = f"batch.cust.{uid}@example.test"
            r = _req(
                c,
                "post",
                "/api/customers",
                json_body={
                    "firstName": "B",
                    "lastName": uid,
                    "email": cust_email,
                    "phone": f"7{uid[:9]}".ljust(10, "0")[:15],
                    "status": "active",
                    "addresses": [
                        {
                            "line1": "Seed Line",
                            "city": "Chennai",
                            "zipCode": "600001",
                            "isPrimary": True,
                        }
                    ],
                },
                headers=auth,
            )
            rows.append(("Web", "POST", "/api/customers (seed)", r.status_code, ""))
            if r.status_code != 201:
                print(r.get_data(as_text=True)[:500])
                return 1
            customer_id = int((r.get_json() or {}).get("id"))

            r = _req(
                c,
                "post",
                "/api/addresses",
                json_body={
                    "userId": customer_id,
                    "addresses": [
                        {
                            "line1": "Batch A St",
                            "city": "Chennai",
                            "zipCode": "600010",
                            "isPrimary": True,
                        },
                        {
                            "line1": "Batch B St",
                            "city": "Chennai",
                            "zipCode": "600011",
                            "buildingName": "Tower X",
                            "isPrimary": False,
                        },
                    ],
                },
                headers=auth,
            )
            rows.append(("Web", "POST", "/api/addresses", r.status_code, "batch create"))
            j = r.get_json() or {}
            addrs = j.get("addresses") or []
            aid1 = int(str(addrs[0]["id"])) if len(addrs) > 0 else None
            aid2 = int(str(addrs[1]["id"])) if len(addrs) > 1 else None
            if r.status_code != 201 or aid1 is None or aid2 is None:
                print(json.dumps({"err": "batch create", "code": r.status_code, "j": j}, indent=2)[:800])
                return 1

            r = _req(
                c,
                "put",
                "/api/addresses",
                json_body={
                    "addresses": [
                        {"id": aid1, "zipCode": "600099"},
                        {"id": aid2, "area": "Velachery"},
                    ]
                },
                headers=auth,
            )
            rows.append(("Web", "PUT", "/api/addresses", r.status_code, "batch update"))

            r = _req(
                c,
                "put",
                f"/api/addresses/{aid1}",
                json_body={"zipCode": "600100"},
                headers=auth,
            )
            rows.append(("Web", "PUT", f"/api/addresses/{aid1}", r.status_code, "single update"))

            # Mobile: request-otp + verify-otp minimal then addresses
            phone = f"9{uid[:9]}".ljust(10, "0")[:10]
            r = _req(c, "post", "/mobile/auth/request-otp", json_body={"phone": phone})
            note = "SMS provider / env (502 common if 2Factor not configured)"
            if r.status_code == 200:
                note = ""
            rows.append(("Mobile", "POST", "/mobile/auth/request-otp", r.status_code, note))

            otp = None
            if r.status_code == 200:
                dbg = (r.get_json() or {}).get("debugOtp")
                if dbg:
                    otp = str(dbg).strip()

            if otp:
                r = _req(
                    c,
                    "post",
                    "/mobile/auth/verify-otp",
                    json_body={
                        "phone": phone,
                        "otp": otp,
                        "firstName": "Mob",
                        "lastName": "Test",
                    },
                )
                rows.append(("Mobile", "POST", "/mobile/auth/verify-otp", r.status_code, ""))
                mob_token = (r.get_json() or {}).get("accessToken")
                if r.status_code == 200 and mob_token:
                    mauth = {"Authorization": f"Bearer {mob_token}"}
                    r = _req(c, "get", "/mobile/addresses", headers=mauth)
                    rows.append(("Mobile", "GET", "/mobile/addresses", r.status_code, "list"))
                    r = _req(
                        c,
                        "post",
                        "/mobile/addresses",
                        json_body={
                            "addresses": [
                                {
                                    "line1": "Mob Batch 1",
                                    "city": "Bengaluru",
                                    "zipCode": "560001",
                                    "isDefault": False,
                                }
                            ]
                        },
                        headers=mauth,
                    )
                    rows.append(("Mobile", "POST", "/mobile/addresses", r.status_code, "batch create"))
                    mj = r.get_json() or {}
                    mids = mj.get("addresses") or []
                    mid = int(str(mids[0]["id"])) if mids else None
                    if mid:
                        r = _req(
                            c,
                            "put",
                            "/mobile/addresses",
                            json_body={"addresses": [{"id": mid, "line2": "Batch upd"}]},
                            headers=mauth,
                        )
                        rows.append(("Mobile", "PUT", "/mobile/addresses", r.status_code, "batch update"))
            else:
                rows.append(("Mobile", "-", "(OTP debug skipped — set MOBILE_OTP_DEBUG or use real OTP)", 0, ""))

    print(json.dumps({"results": [{"layer": a, "method": b, "path": c, "status": d, "note": e} for a, b, c, d, e in rows]}, indent=2))
    http_500 = [x for x in rows if x[3] == 500]
    if http_500:
        print("FAIL: HTTP 500:", http_500, file=sys.stderr)
        return 1
    # verify expected 2xx for web address rows
    for x in rows:
        if x[0] == "Web" and "/api/addresses" in x[2] and x[3] not in (200, 201):
            print("FAIL web address:", x, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
