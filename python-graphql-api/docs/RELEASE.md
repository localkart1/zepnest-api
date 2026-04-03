# Release steps (ZepNest API on AWS EC2)

This document describes how to ship a new version of **python-graphql-api** to a single Ubuntu EC2 instance running **Gunicorn** behind **Nginx**.

---

## Roles and assumptions

- **App user on EC2:** `ubuntu`
- **App directory:** `/home/ubuntu/zepnest-api/python-graphql-api`
- **Virtualenv:** `/home/ubuntu/zepnest-api/python-graphql-api/venv`
- **Gunicorn:** binds `127.0.0.1:5002`, factory `api:create_app()`
- **Systemd unit:** `zepnest-api.service`
- **Nginx:** reverse proxy to `127.0.0.1:5002` on port **80** (and **443** if TLS is configured)
- **Config:** `.env` on the server (not committed; copy from `.env.example`)

Adjust paths if your layout differs.

---

## Before every release

1. **Merge or tag** the intended commit on your main branch (or release branch).
2. **Review `.env.example`** for any new variables; update production `.env` on EC2 if needed.
3. **Database:** if this release adds migrations or one-off SQL, run them **before** or **during** the deploy window (see `scripts/*.sql` in the repo when applicable).
4. **Communicate** a short maintenance window if you expect brief restarts.

---

## First-time server setup (once per instance)

Skip this if the instance is already configured.

1. Install packages: `python3.12-venv`, `python3-pip`, `nginx`, `git`.
2. Clone the repo under `/home/ubuntu/zepnest-api`, create `venv`, `pip install -r requirements.txt`.
3. Create `/home/ubuntu/zepnest-api/python-graphql-api/.env` from `.env.example` and set at least:
   - `FLASK_ENV=production`, `FLASK_DEBUG=False`
   - `PORT=5002`
   - `SECRET_KEY` (long random value)
   - `DATABASE_URL`, `DB_SCHEMA`, `AUTO_CREATE_TABLES=false`
   - SMS / S3 keys as required by features in use
4. Create **systemd** unit `zepnest-api.service` pointing `ExecStart` at `venv/bin/gunicorn` and `EnvironmentFile` at `.env`.
5. Configure **Nginx** `server` block: `proxy_pass http://127.0.0.1:5002;` for `/`.
6. **Security group:** allow `22` (SSH), `80` (HTTP), `443` (HTTPS if used); do not expose `5002` publicly unless intentional.
7. Optional TLS: **Certbot** with Nginx when a DNS name points to the instance.

Production process command (reference):

```bash
gunicorn -w 4 -b 127.0.0.1:5002 "api:create_app()"
```

---

## Standard release (update code on EC2)

Run on the server after SSH:

```bash
cd /home/ubuntu/zepnest-api/python-graphql-api

# 1) Get code
git fetch origin
git checkout <branch-or-tag>   # e.g. main or v1.2.0
git pull --ff-only

# 2) Dependencies
source venv/bin/activate
pip install -r requirements.txt

# 3) Optional: schema checks against DB (from project root)
# ./venv/bin/python scripts/validate_api_db_schema.py
# ./venv/bin/python scripts/compare_db_schema.py

# 4) Apply any new env vars
nano .env   # or use your secret manager / SSM workflow

# 5) Restart app
sudo systemctl restart zepnest-api
sudo systemctl status zepnest-api --no-pager
```

If you changed **only** `.env` (no code), step 2 can be skipped; still restart:

```bash
sudo systemctl restart zepnest-api
```

If you changed **only** Nginx config:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## Verification after deploy

**On the server:**

```bash
# GraphQL (POST JSON — do not use HEAD for /graphql)
curl -sS http://127.0.0.1:5002/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ __typename }"}'

# Through Nginx (port 80)
curl -sS http://127.0.0.1/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ __typename }"}'

# REST docs (browser or curl)
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5002/api/docs
```

**From your machine:** use the public DNS or IP (same paths), ensuring the security group allows **80**/**443**.

**Logs:**

```bash
sudo journalctl -u zepnest-api -n 100 --no-pager
sudo tail -n 50 /var/log/nginx/error.log
```

---

## Rollback

1. SSH to the instance.
2. Check out the previous known-good commit or tag:

   ```bash
   cd /home/ubuntu/zepnest-api/python-graphql-api
   git checkout <previous-tag-or-commit>
   ```

3. Reinstall deps if `requirements.txt` changed between versions:

   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. Restore `.env` if you changed incompatible settings.
5. Restart: `sudo systemctl restart zepnest-api`
6. Re-run the verification curls above.

---

## Postman / API clients

- Import `docs/postman/customer-journey-mobile.postman_collection.json` and set the collection **base URL** to `http://<your-public-host>` (or HTTPS).
- **GraphQL:** `POST /graphql`, body JSON `{ "query": "...", "variables": {} }`, header `Content-Type: application/json`.
- **REST:** paths under `/api`; use **Bearer** token from `POST /api/auth/login` when routes require auth.

---

## HTTPS certificate renewal (Let’s Encrypt)

If you use Certbot with Nginx, renewals are usually automatic. To confirm:

```bash
sudo certbot renew --dry-run
```

---

## Checklist (copy for each release)

- [ ] Code at intended tag/commit; `requirements.txt` installed
- [ ] `.env` updated for any new variables
- [ ] DB migrations / SQL scripts applied if required
- [ ] `zepnest-api` restarted and `status` is **active (running)**
- [ ] Nginx test passes (`sudo nginx -t`) if config changed
- [ ] Smoke test: GraphQL `__typename`, `/api/docs` reachable
- [ ] Logs clean of unexpected tracebacks after traffic sample
