# API status codes reference

This document summarizes **typical HTTP status codes** returned by the python-graphql-api. Exact behavior depends on request body, DB state, and schema (e.g. missing tables).

## Live health: full API GET probe

On a **running** server (same logic as `scripts/api_sanity_probe.py`):

| URL | Response |
|-----|----------|
| `GET /` | Quick liveness: `{"status":"ok","message":"API is running"}` |
| `GET /?full=1` or `GET /?apis=1` | Full probe JSON (`get_results`, `summary`, `issues`, `mutating_routes_not_probed`) |
| `GET /health/apis` | Same JSON as `/?full=1` (no query string needed) |

If any GET route returns **5xx** or raises, `summary.healthy` is `false` and `issues` lists them.

## Automated GET probe (writes files)

Run from the repo root:

```bash
.venv/bin/python scripts/api_sanity_probe.py
```

This performs **GET-only** requests (no POST/DELETE) and rolls back the DB session after each call. It writes:

- `docs/api_sanity_report.json`
- `docs/api_sanity_report.md`

Use that report for **observed** status codes on your database (e.g. `404` when id `1` does not exist). On some DBs, a route may return **500** if its SQL does not match your schema (example: `GET /api/dashboard/stats` if `booking_status_enum` has no `escalated` value).

## Global error handling

| Code | When |
|------|------|
| **500** | Unhandled exception → `{"message": "Internal server error"}` (see `api/__init__.py`). |

## Web auth — `/api/auth`

| Endpoint | Method | Typical codes |
|----------|--------|----------------|
| `/api/auth/register` | POST | **201** created; **400** validation; **409** email exists; **500** registration failed |
| `/api/auth/login` | POST | **200** token; **400** missing fields; **401** bad credentials |
| `/api/auth/me` | GET | **200**; **401** missing/invalid Bearer |

## Mobile — `/mobile`

| Endpoint | Method | Typical codes |
|----------|--------|----------------|
| `/mobile/auth/request-otp` | POST | **200** OTP sent/generated; **400** invalid phone; **502** SMS provider failure |
| `/mobile/auth/verify-otp` | POST | **200** JWT; **400** missing/invalid/expired OTP; **401** wrong OTP |
| `/mobile/home` | GET | **200** categories (optional `zipCode` query; Bearer optional for PIN from default address) |
| `/mobile/catalog/subcategories` | GET | **200** array; **400** missing or non-numeric `categoryId` |
| `/mobile/profile` | GET | **200**; **401**; **404** user missing |
| `/mobile/profile` | PATCH | **200**; **401** |
| `/mobile/addresses` | GET | **200** |
| `/mobile/addresses` | POST | **201**; **400** |
| `/mobile/addresses` | PUT | **200** batch; **400** |
| `/mobile/addresses/{id}` | PUT | **200**; **400**; **404** |
| `/mobile/addresses/{id}` | DELETE | **204**; **404** |
| `/mobile/cart` | GET | **200**; **401**; **501** `cart_items` missing |
| `/mobile/cart` | DELETE | **200**; **401**; **501** |
| `/mobile/cart/items` | POST | **200**; **400**; **404** service; **501** table missing; **500** rare re-fetch failure |
| `/mobile/cart/items/{id}` | PUT | **200**; **400**; **404**; **501** |
| `/mobile/cart/items/{id}` | DELETE | **200**; **404**; **501** |
| `/mobile/bookings` | GET | **200** |
| `/mobile/bookings` | POST | **201**; **400**; **404** services; **501** cart table if `fromCart` |
| `/mobile/bookings/{id}` | GET | **200**; **404**; **401** |
| `/mobile/uploads/presign` | POST | **200** presigned URL; **400** bad `kind`; **502** S3 error; **503** S3 not configured |

## REST — `/api` (selection)

Most list/detail endpoints return **200** with JSON, **404** when an id does not exist, **400** on validation errors, **409** on conflicts, **501** when a feature is not implemented or a required table is missing (e.g. some asset endpoints).

Full REST surface is described in `api/rest/openapi.yaml` and merged `openapi.json`.

## OpenAPI / JSON spec

- `GET /openapi.json` — combined Web + Mobile (**200** or **404** if file not built).
- `GET /api/openapi.yaml` — web YAML (**200**).
- `GET /api/docs` — Swagger UI (**200**).
