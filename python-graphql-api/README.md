# ZepNest API

Flask backend with **REST** (`/api`) aligned to the admin portal contract, **mobile REST** (`/mobile`), and **GraphQL** (`/graphql`). The **web and mobile** layers use **raw SQL** against your **PostgreSQL** tables; the expected tables and columns are listed in `api/db_schema_contract.py` and checked by `scripts/validate_api_db_schema.py`.

## Requirements

- Python 3.12+
- PostgreSQL (connection via `DATABASE_URL`)

## Quick start

```bash
cd python-graphql-api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

One-command bootstrap:

```bash
./scripts/bootstrap.sh
```

Create `.env` from `.env.example` and set `DATABASE_URL`, `DB_SCHEMA`, `SECRET_KEY`, `PORT`.

```bash
python3 main.py
```

Default base URL: `http://localhost:5002`

---

## REST API (`/api`)

All paths below are relative to the server origin. Example: `GET http://localhost:5002/api/customers`.

### Web auth

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/register` | Email/password signup (stores `users.password_hash`) |
| `POST` | `/api/auth/login` | Email/password login |
| `GET` | `/api/auth/me` | Current web user (`Authorization: Bearer <token>`) |

---

### Pagination & filters (list endpoints)

Many list routes accept query parameters:

| Parameter | Description |
|-----------|-------------|
| `page` | Page number (default `1`) |
| `limit` | Page size (default `10`) |
| `search` | Text search (field varies by resource) |
| `status` | Filter by status where applicable |

Paginated responses typically use this shape:

```json
{
  "items": [],
  "data": [],
  "total": 0,
  "page": 1,
  "limit": 10,
  "totalPages": 0
}
```

Notes:
- Most legacy list endpoints include both `items` and `data` (same list) for compatibility.
- `GET /api/customers` returns `items` (primary) and does **not** include legacy `data`.

---

### Customers

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/customers` | List customers (`user_type = customer`) |
| `GET` | `/api/customers/:id` | Get one customer |
| `POST` | `/api/customers` | Create customer |
| `PUT` | `/api/customers/:id` | Update customer |
| `DELETE` | `/api/customers/:id` | Delete customer |

---

### Technicians

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/technicians` | List technicians |
| `GET` | `/api/technicians/:id` | Get one technician |
| `POST` | `/api/technicians` | Create technician |
| `PUT` | `/api/technicians/:id` | Update technician |
| `DELETE` | `/api/technicians/:id` | Delete technician |

---

### Assets

There is no dedicated `assets` table in the current schema. List/get return a **derived** view from bookings/service areas. Create/update/delete return `501` with an explanatory message.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/assets` | List (derived) |
| `GET` | `/api/assets/:id` | Get (`id` may use `ast-<bookingId>` style) |
| `POST` | `/api/assets` | Not supported (`501`) |
| `PUT` | `/api/assets/:id` | Not supported (`501`) |
| `DELETE` | `/api/assets/:id` | Not supported (`501`) |

---

### Orders (bookings)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/orders` | List orders |
| `GET` | `/api/orders/:id` | Get one order |
| `POST` | `/api/orders` | Create booking |
| `PUT` | `/api/orders/:id` | Update booking |
| `DELETE` | `/api/orders/:id` | Delete booking |
| `POST` | `/api/orders/assign/:orderId` | Assign technician (`body`: `{ "technicianId" }`) |
| `POST` | `/api/orders/escalate/:orderId` | Escalate (`body`: `{ "reason", ... }`) |

`POST /api/orders` supports multiple items:
- Preferred: `bookingItems` array (`serviceId`, optional `quantity`, optional `unitPrice`)
- Compatibility: `serviceIds` / `serviceId`

Booking items are persisted in `booking_items` with FK to `bookings`.

---

### Services & catalog

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/services` | List services |
| `GET` | `/api/services/:id` | Get one service |
| `POST` | `/api/services` | Create service |
| `PUT` | `/api/services/:id` | Update service |
| `DELETE` | `/api/services/:id` | Delete service |
| `GET` | `/api/services/categories` | Distinct categories from `services.category` |
| `GET` | `/api/services/addons` | Query: `?serviceId=` optional |
| `GET` | `/api/services/warranties` | Query: `?serviceId=` optional |
| `GET` | `/api/services/packages` | Service packages |

---

### Subscriptions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/subscriptions/plans` | List subscription plans |
| `POST` | `/api/subscriptions/plans` | Create plan |
| `PUT` | `/api/subscriptions/plans/:id` | Update plan |
| `GET` | `/api/subscriptions/user` | User subscriptions (paginated) |
| `GET` | `/api/subscriptions/amc` | AMC-oriented plans (derived from plans) |
| `GET` | `/api/subscriptions/user-amc` | User AMC subscriptions (paginated, derived) |

---

### Enumerations

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/enumerations/specializations` | From `technician_profiles` |
| `GET` | `/api/enumerations/service-categories` | From `services` |
| `GET` | `/api/enumerations/zip-codes` | From `service_areas` |
| `GET` | `/api/enumerations/time-slots` | Active slots from `time_slot_master` |

---

### Dashboard

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/dashboard/stats` | Aggregated counts and metrics |

---

### Payments

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/payments` | List payments |
| `GET` | `/api/payments/:id` | Get payment (`id` numeric or `pay-<id>`) |
| `GET` | `/api/payments/payouts` | Derived technician payouts |
| `GET` | `/api/payments/refunds` | Derived refunds from payment rows |
| `PUT` | `/api/payments/refunds/:id` | Update refund workflow (`id` like `ref-<paymentId>`) |

---

### Settings

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/settings/roles` | Static role metadata for admin UI |

---

## Mobile API (`/mobile`)

OTP (`/mobile/auth/*`), home categories (`GET /mobile/home`), bookings (`/mobile/bookings`), profile (`GET`/`PATCH /mobile/profile`), addresses (`/mobile/addresses`). Authenticated routes use `Authorization: Bearer <accessToken>`.

Address storage is in common `addresses` table (fallback read/write to `customer_addresses` for older DBs).
`PATCH /mobile/profile` can upsert default address by sending `address` (or `defaultAddress`) object.

### Voice note and video storage (AWS S3)

**Voice notes and video must be stored in Amazon S3** (or compatible object storage with HTTPS URLs). Configure **`AWS_S3_*`** in `.env` (see `.env.example`). This API does **not** accept raw multipart uploads on the booking endpoint.

**Recommended flow**

1. **`POST /mobile/uploads/presign`** (Bearer auth) — body: `{ "kind": "voice" | "video", "fileExtension": "m4a" }`, optional `contentType`. Returns `uploadUrl` (presigned **PUT**), `fileUrl` (use on the booking), `headers`, `expiresInSeconds`.
2. Client **PUT**s the file bytes to `uploadUrl` with the given `Content-Type`.
3. **`POST /mobile/bookings`** — include `voiceNoteUrl` / `videoUrl` from the presign response (`fileUrl`).

Only the URLs are stored in the database; binaries live in S3.

---

## GraphQL

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/graphql` | GraphiQL UI |
| `POST` | `/graphql` | Execute operations (JSON body) |

**Request body (JSON):** `{ "query": "<GraphQL string>", "variables": { ... }, "operationName": "..." }` — `variables` and `operationName` are optional.

**Examples:** see **[docs/GRAPHQL.md](docs/GRAPHQL.md)** for HTTP/cURL templates, introspection queries, and sample queries/mutations.

GraphQL maps to **SQLAlchemy models** in `api/models/`, not the raw-SQL Postgres layer used by **`/api`** and **`/mobile`**. For production data aligned with your live schema, prefer **REST**; use GraphQL after models match the DB (`scripts/compare_db_schema.py`).

---

## Configuration

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLAlchemy URL, e.g. `postgresql://user:pass@host:5432/dbname` |
| `DB_SCHEMA` | Postgres `search_path` (e.g. `public`) |
| `AUTO_CREATE_TABLES` | `false` recommended for existing databases |
| `SECRET_KEY` | Flask secret |
| `PORT` | Server port (default `5002`) |
| `AWS_S3_BUCKET` | Required for mobile presigned uploads; region/credentials via standard AWS env vars |
| `AWS_S3_REGION` | S3 region (default `us-east-1`) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Optional if the host uses an IAM role |
| `AWS_S3_ENDPOINT_URL` | Optional (MinIO, LocalStack) |
| `AWS_S3_PUBLIC_BASE_URL` | Optional CloudFront / CDN base for `fileUrl` |
| `AWS_S3_VOICE_PREFIX` / `AWS_S3_VIDEO_PREFIX` | Object key prefixes (defaults under `mobile/voice/` and `mobile/video/`) |
| `AWS_S3_PRESIGN_EXPIRES` | Presigned PUT lifetime in seconds (default `3600`) |

---

## Schema check (development)

**Web + mobile REST vs live DB** — verifies that `api/rest/routes.py` and `api/mobile/routes.py` have the tables/columns they expect:

```bash
./venv/bin/python scripts/validate_api_db_schema.py
```

**ORM models vs live DB** (GraphQL / SQLAlchemy models, not the raw-SQL REST layer):

```bash
./venv/bin/python scripts/compare_db_schema.py
```

---

## SQL setup scripts

Run as needed on PostgreSQL:

- `scripts/create_mobile_otp_table.sql`
- `scripts/create_audit_logs_table.sql`
- `scripts/create_booking_items_table.sql`
- `scripts/create_addresses_table.sql`
- `scripts/create_time_slot_master_table.sql`

---

## Production

```bash
gunicorn -w 4 -b 0.0.0.0:5002 "api:create_app()"
```

**EC2 deploy, systemd, Nginx, verification, and rollback:** see [docs/RELEASE.md](docs/RELEASE.md).

## License

MIT
