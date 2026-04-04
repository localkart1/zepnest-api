import os
from datetime import datetime

from flask import Blueprint, Response, jsonify, request, send_file
from sqlalchemy import inspect, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.exc import IntegrityError

from api import db
from api.booking_items_compat import booking_items_pk_column
from api.booking_status import (
    ASSIGNED_BOOKING_STATUS,
    DEFAULT_BOOKING_STATUS,
    OPEN_BOOKING_STATUSES,
    PIPELINE_BOOKING_STATUSES,
    sql_in_text,
)
from api.graphql.catalog_fallback import is_missing_relation_error


rest_bp = Blueprint("rest_api", __name__, url_prefix="/api")


def _int_param(name: str, default: int) -> int:
    try:
        return int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default


def _paginate(rows, page: int, limit: int):
    total = len(rows)
    start = (page - 1) * limit
    end = start + limit
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    data = rows[start:end]
    return {"data": data, "total": total, "page": page, "limit": limit, "totalPages": total_pages}


def _addresses_by_user_ids(user_ids: list[int]) -> dict[int, list[dict]]:
    ids = [int(x) for x in user_ids if x is not None]
    if not ids:
        return {}
    placeholders = ", ".join(f":uid_{i}" for i in range(len(ids)))
    params = {f"uid_{i}": ids[i] for i in range(len(ids))}
    try:
        rows = _q(
            f"""
            SELECT user_id, id, label, line1, line2, city, state, zip_code, country, is_default
            FROM addresses
            WHERE user_id IN ({placeholders})
            ORDER BY is_default DESC, id DESC
            """,
            params,
        )
    except ProgrammingError as e:
        if not is_missing_relation_error(e):
            raise
        rows = _q(
            f"""
            SELECT user_id, id, label, line1, line2, city, state, zip_code, country, is_default
            FROM customer_addresses
            WHERE user_id IN ({placeholders})
            ORDER BY is_default DESC, id DESC
            """,
            params,
        )
    out: dict[int, list[dict]] = {}
    for r in rows:
        uid = int(r["user_id"])
        out.setdefault(uid, []).append(
            {
                "id": str(r["id"]),
                "label": r["label"] or "",
                "line1": r["line1"] or "",
                "line2": r["line2"] or "",
                "city": r["city"] or "",
                "state": r["state"] or "",
                "zipCode": r["zip_code"] or "",
                "country": r["country"] or "",
                "isDefault": bool(r["is_default"]),
            }
        )
    return out


def _q(sql: str, params=None):
    result = db.session.execute(text(sql), params or {})
    if not result.returns_rows:
        return []
    return result.mappings().all()


def _one(sql: str, params=None):
    result = db.session.execute(text(sql), params or {})
    if not result.returns_rows:
        return None
    return result.mappings().first()


def _exec(sql: str, params=None) -> None:
    db.session.execute(text(sql), params or {})


def _coerce_internal_notes_value(data: dict) -> str:
    if "internalNotes" not in data and "internal_notes" not in data:
        return ""
    v = data.get("internalNotes", data.get("internal_notes"))
    if v is None:
        return ""
    return v if isinstance(v, str) else str(v)


def _line1_from_admin_address(addr: dict) -> str:
    line1 = (addr.get("line1") or addr.get("addressLine1") or "").strip()
    if line1:
        return line1
    parts = []
    door = (addr.get("doorNo") or addr.get("door_no") or "").strip()
    if door:
        parts.append(door)
    street = (addr.get("street") or "").strip()
    if street:
        parts.append(street)
    line1 = ", ".join(parts) if len(parts) > 1 else (parts[0] if parts else "")
    lm = (addr.get("landmark") or "").strip()
    if lm:
        line1 = f"{line1}, Near {lm}" if line1 else f"Near {lm}"
    return line1


def _insert_addresses_for_customer(user_id: int, addresses) -> None:
    """Persist admin-portal style addresses (street, doorNo, zipCode, isPrimary, …)."""
    if not isinstance(addresses, list) or not addresses:
        return
    rows: list[dict] = []
    for addr in addresses:
        if not isinstance(addr, dict):
            continue
        l1 = _line1_from_admin_address(addr)
        if not l1:
            continue
        label = (addr.get("nickName") or addr.get("label") or "").strip() or "Home"
        l2 = (addr.get("line2") or addr.get("addressLine2") or "").strip() or None
        city = (addr.get("city") or "").strip() or None
        state = (addr.get("state") or "").strip() or None
        zip_c = (addr.get("zipCode") or addr.get("zip") or "").strip() or None
        country = (addr.get("country") or "India").strip() or "India"
        atype = (addr.get("addressType") or "home").strip() or "home"
        isd = bool(addr.get("isPrimary", addr.get("isDefault", False)))
        aphone = (addr.get("phone") or "").strip()
        if aphone and not l2:
            l2 = aphone
        rows.append(
            {
                "label": label[:64],
                "l1": l1[:255],
                "l2": (l2[:255] if l2 else None),
                "city": city[:100] if city else None,
                "state": state[:100] if state else None,
                "zip_c": zip_c[:20] if zip_c else None,
                "country": country[:80] if country else "India",
                "atype": atype[:32] if atype else "home",
                "isd": isd,
            }
        )
    if not rows:
        return
    if not any(r["isd"] for r in rows):
        rows[0]["isd"] = True
    for r in rows:
        params_addr = {
            "uid": user_id,
            "label": r["label"],
            "l1": r["l1"],
            "l2": r["l2"],
            "city": r["city"],
            "state": r["state"],
            "zip": r["zip_c"],
            "country": r["country"],
            "atype": r["atype"],
            "isd": r["isd"],
        }
        try:
            if r["isd"]:
                _exec("UPDATE addresses SET is_default = false WHERE user_id = :uid", {"uid": user_id})
            _exec(
                """
                INSERT INTO addresses (user_id, label, line1, line2, city, state, zip_code, country, address_type, is_default, created_at, updated_at)
                VALUES (:uid, :label, :l1, :l2, :city, :state, :zip, :country, :atype, :isd, NOW(), NOW())
                """,
                params_addr,
            )
        except ProgrammingError as e:
            if not is_missing_relation_error(e):
                raise
            ca_params = {
                "uid": user_id,
                "label": r["label"],
                "l1": r["l1"],
                "l2": r["l2"],
                "city": r["city"],
                "state": r["state"],
                "zip": r["zip_c"],
                "country": r["country"],
                "isd": r["isd"],
            }
            if r["isd"]:
                _exec("UPDATE customer_addresses SET is_default = false WHERE user_id = :uid", {"uid": user_id})
            _exec(
                """
                INSERT INTO customer_addresses (user_id, label, line1, line2, city, state, zip_code, country, is_default, created_at, updated_at)
                VALUES (:uid, :label, :l1, :l2, :city, :state, :zip, :country, :isd, NOW(), NOW())
                """,
                ca_params,
            )


def _parse_address_id(raw) -> int | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    s = str(raw).strip()
    if s.isdigit():
        i = int(s)
        return i if i > 0 else None
    return None


def _customer_addresses_table_name() -> str:
    try:
        insp = inspect(db.engine)
        if insp.has_table("addresses"):
            return "addresses"
    except Exception:
        pass
    return "customer_addresses"


def _sync_addresses_for_customer(user_id: int, addresses: list) -> None:
    """
    Full replace of customer addresses when the client sends ``addresses`` (PUT body).
    Uses ``addresses`` or ``customer_addresses`` depending on schema.
    """
    tbl = _customer_addresses_table_name()
    rows = [dict(a) for a in addresses if isinstance(a, dict)]
    if not rows:
        _exec(f"DELETE FROM {tbl} WHERE user_id = :uid", {"uid": user_id})
        return
    if not any(bool(a.get("isPrimary", a.get("isDefault", False))) for a in rows):
        rows[0] = dict(rows[0])
        rows[0]["isDefault"] = True

    keep_ids: list[int] = []
    for addr in rows:
        aid = _parse_address_id(addr.get("id"))
        existing = None
        if aid:
            existing = _one(
                f"SELECT id, line1 FROM {tbl} WHERE id = :id AND user_id = :uid",
                {"id": aid, "uid": user_id},
            )
        l1_build = _line1_from_admin_address(addr)
        l1 = (l1_build[:255] if l1_build else "") or ((existing["line1"] or "").strip() if existing else "")
        if not l1:
            continue
        l1 = l1[:255]
        label = (addr.get("nickName") or addr.get("label") or "").strip() or "Home"
        l2_raw = (addr.get("line2") or addr.get("addressLine2") or "").strip() or None
        aphone = (addr.get("phone") or "").strip()
        if aphone and not l2_raw:
            l2_raw = aphone
        l2 = l2_raw[:255] if l2_raw else None
        city = (addr.get("city") or "").strip() or None
        city = city[:100] if city else None
        state = (addr.get("state") or "").strip() or None
        state = state[:100] if state else None
        zip_c = (addr.get("zipCode") or addr.get("zip") or "").strip() or None
        zip_c = zip_c[:20] if zip_c else None
        country = ((addr.get("country") or "India").strip() or "India")[:80]
        atype = ((addr.get("addressType") or "home").strip() or "home")[:32]
        isd = bool(addr.get("isPrimary", addr.get("isDefault", False)))
        params_u = {
            "id": aid,
            "uid": user_id,
            "label": label[:64],
            "l1": l1,
            "l2": l2,
            "city": city,
            "state": state,
            "zip": zip_c,
            "country": country,
            "atype": atype,
            "isd": isd,
        }
        if existing:
            if isd:
                _exec(f"UPDATE {tbl} SET is_default = false WHERE user_id = :uid", {"uid": user_id})
            if tbl == "addresses":
                _exec(
                    """
                    UPDATE addresses SET label=:label, line1=:l1, line2=:l2, city=:city, state=:state,
                        zip_code=:zip, country=:country, address_type=:atype, is_default=:isd, updated_at = NOW()
                    WHERE id=:id AND user_id=:uid
                    """,
                    params_u,
                )
            else:
                _exec(
                    """
                    UPDATE customer_addresses SET label=:label, line1=:l1, line2=:l2, city=:city, state=:state,
                        zip_code=:zip, country=:country, is_default=:isd, updated_at = NOW()
                    WHERE id=:id AND user_id=:uid
                    """,
                    {k: params_u[k] for k in ("id", "uid", "label", "l1", "l2", "city", "state", "zip", "country", "isd")},
                )
            keep_ids.append(int(aid))
        else:
            if isd:
                _exec(f"UPDATE {tbl} SET is_default = false WHERE user_id = :uid", {"uid": user_id})
            ins_params = {
                "uid": user_id,
                "label": label[:64],
                "l1": l1,
                "l2": l2,
                "city": city,
                "state": state,
                "zip": zip_c,
                "country": country,
                "atype": atype,
                "isd": isd,
            }
            if tbl == "addresses":
                row = _one(
                    """
                    INSERT INTO addresses (user_id, label, line1, line2, city, state, zip_code, country, address_type, is_default, created_at, updated_at)
                    VALUES (:uid, :label, :l1, :l2, :city, :state, :zip, :country, :atype, :isd, NOW(), NOW())
                    RETURNING id
                    """,
                    ins_params,
                )
            else:
                row = _one(
                    """
                    INSERT INTO customer_addresses (user_id, label, line1, line2, city, state, zip_code, country, is_default, created_at, updated_at)
                    VALUES (:uid, :label, :l1, :l2, :city, :state, :zip, :country, :isd, NOW(), NOW())
                    RETURNING id
                    """,
                    {k: ins_params[k] for k in ("uid", "label", "l1", "l2", "city", "state", "zip", "country", "isd")},
                )
            if row:
                keep_ids.append(int(row["id"]))

    if not keep_ids:
        _exec(f"DELETE FROM {tbl} WHERE user_id = :uid", {"uid": user_id})
        return
    placeholders = ", ".join(f":d{i}" for i in range(len(keep_ids)))
    dparams: dict = {"uid": user_id, **{f"d{i}": keep_ids[i] for i in range(len(keep_ids))}}
    _exec(f"DELETE FROM {tbl} WHERE user_id = :uid AND id NOT IN ({placeholders})", dparams)


def _booking_items_by_booking_ids(booking_ids: list[int]) -> dict[int, list[dict]]:
    ids = [int(x) for x in booking_ids if x is not None]
    if not ids:
        return {}
    placeholders = ", ".join(f":bid_{i}" for i in range(len(ids)))
    params = {f"bid_{i}": ids[i] for i in range(len(ids))}
    pk = booking_items_pk_column()
    try:
        rows = _q(
            f"""
            SELECT bi.{pk} AS id, bi.booking_id, bi.service_id, bi.quantity, bi.unit_price, bi.total_price,
                   bi.voice_url, bi.video_url, bi.image_url, bi.notes,
                   s.name AS service_name, s.description AS service_description
            FROM booking_items bi
            LEFT JOIN services s ON s.service_id = bi.service_id
            WHERE bi.booking_id IN ({placeholders})
            ORDER BY bi.{pk} ASC
            """,
            params,
        )
    except ProgrammingError as e:
        if is_missing_relation_error(e):
            return {}
        raise
    out: dict[int, list[dict]] = {}
    for r in rows:
        bid = int(r["booking_id"])
        out.setdefault(bid, []).append(
            {
                "id": str(r["id"]),
                "serviceId": int(r["service_id"]),
                "serviceName": r["service_name"] or "",
                "description": r["service_description"] or "",
                "quantity": int(r["quantity"] or 1),
                "unitPrice": float(r["unit_price"] or 0),
                "totalPrice": float(r["total_price"] or 0),
                "voiceUrl": r.get("voice_url") or None,
                "videoUrl": r.get("video_url") or None,
                "imageUrl": r.get("image_url") or None,
                "notes": r.get("notes") or "",
            }
        )
    return out


def _collect_order_item_service_ids(payload: dict) -> list[int]:
    out: list[int] = []
    booking_items = payload.get("bookingItems")
    if isinstance(booking_items, list):
        for it in booking_items:
            if not isinstance(it, dict):
                continue
            sid = it.get("serviceId")
            if sid is None:
                sid = it.get("service_id")
            try:
                out.append(int(sid))
            except (TypeError, ValueError):
                continue
    if out:
        # Preserve order, dedupe.
        seen = set()
        uniq = []
        for x in out:
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        return uniq
    service_ids = payload.get("serviceIds")
    if isinstance(service_ids, list):
        tmp = []
        for sid in service_ids:
            try:
                tmp.append(int(sid))
            except (TypeError, ValueError):
                continue
        seen = set()
        uniq = []
        for x in tmp:
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        return uniq
    sid = payload.get("serviceId")
    try:
        return [int(sid)] if sid is not None else []
    except (TypeError, ValueError):
        return []


def _resolve_category_for_service_write(d: dict) -> tuple:
    """
    Pick (category_id, category_label) for services rows from JSON:
    - categoryId: numeric id or, for legacy clients, category name string
    - category: display name / fallback
    """
    cat_id_raw = d.get("categoryId") if "categoryId" in d else d.get("category_id")
    cat_name_raw = d.get("category")
    if cat_id_raw is not None and str(cat_id_raw).strip() != "":
        s = str(cat_id_raw).strip()
        if s.isdigit():
            row = _one("SELECT id, name FROM categories WHERE id = :id", {"id": int(s)})
            if row:
                return row["id"], row["name"]
        row = _one("SELECT id, name FROM categories WHERE name = :n", {"n": s})
        if row:
            return row["id"], row["name"]
    if cat_name_raw is not None and str(cat_name_raw).strip() != "":
        n = str(cat_name_raw).strip()
        row = _one("SELECT id, name FROM categories WHERE name = :n", {"n": n})
        if row:
            return row["id"], row["name"]
        return None, n
    row = _one("SELECT id, name FROM categories WHERE name = 'General'", {})
    if row:
        return row["id"], row["name"]
    return None, "General"


@rest_bp.get("/customers")
def list_customers():
    page = _int_param("page", 1)
    limit = _int_param("limit", 10)
    search = request.args.get("search", "").strip()
    status = request.args.get("status")
    customer_user_type = request.args.get("customerUserType")
    sort_by_raw = (request.args.get("sortBy") or request.args.get("sortField") or "createdAt").strip()
    sort_order = (request.args.get("sortOrder") or "desc").strip().lower()
    sort_by_map = {
        "id": "user_id",
        "createdat": "created_at",
        "updatedat": "updated_at",
        "firstname": "first_name",
        "lastname": "last_name",
        "email": "email",
        "phone": "phone",
    }
    sort_by = sort_by_map.get(sort_by_raw.replace("_", "").lower(), "created_at")
    sort_dir = "ASC" if sort_order == "asc" else "DESC"

    rows = _q(
        """
        SELECT user_id, first_name, last_name, email, phone, user_type, loyalty_points, is_active, internal_notes, created_at, updated_at
        FROM users
        WHERE user_type = 'customer'
          AND (:status IS NULL OR (:status='active' AND is_active=true) OR (:status='inactive' AND is_active=false))
          AND (:customer_user_type IS NULL OR user_type = :customer_user_type)
          AND (:search = '' OR LOWER(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')) LIKE LOWER(:like_search)
               OR LOWER(COALESCE(email,'')) LIKE LOWER(:like_search) OR COALESCE(phone,'') LIKE :like_search)
        ORDER BY """ + sort_by + " " + sort_dir + """, user_id DESC
        """,
        {"status": status, "customer_user_type": customer_user_type, "search": search, "like_search": f"%{search}%"},
    )
    addresses = _addresses_by_user_ids([int(r["user_id"]) for r in rows])
    mapped = [
        {
            "id": str(r["user_id"]),
            "firstName": r["first_name"] or "",
            "lastName": r["last_name"] or "",
            "email": r["email"],
            "phone": r["phone"] or "",
            "addresses": addresses.get(int(r["user_id"]), []),
            "status": "active" if r["is_active"] else "inactive",
            "tags": [],
            "customerUserType": "subscription",
            "internalNotes": r.get("internal_notes") or "",
            "lifetimeValue": 0,
            "hasSubscription": False,
            "hasAmc": False,
            "outstandingAmount": 0,
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
            "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
        for r in rows
    ]
    return jsonify(_paginate(mapped, page, limit))


@rest_bp.get("/customers/<int:customer_id>")
def get_customer(customer_id: int):
    r = _one(
        """
        SELECT user_id, first_name, last_name, email, phone, is_active, internal_notes, created_at, updated_at
        FROM users WHERE user_id=:id AND user_type='customer'
        """,
        {"id": customer_id},
    )
    if not r:
        return jsonify({"message": "Customer not found"}), 404
    addresses = _addresses_by_user_ids([int(r["user_id"])])
    return jsonify(
        {
            "id": str(r["user_id"]),
            "firstName": r["first_name"] or "",
            "lastName": r["last_name"] or "",
            "email": r["email"],
            "phone": r["phone"] or "",
            "addresses": addresses.get(int(r["user_id"]), []),
            "status": "active" if r["is_active"] else "inactive",
            "tags": [],
            "customerUserType": "subscription",
            "internalNotes": r.get("internal_notes") or "",
            "lifetimeValue": 0,
            "hasSubscription": False,
            "hasAmc": False,
            "outstandingAmount": 0,
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
            "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
    )


@rest_bp.post("/customers")
def create_customer():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not email and not phone:
        return jsonify({"message": "email or phone is required"}), 400
    is_active = (data.get("status") or "active").strip().lower() != "inactive"
    try:
        row = _one(
            """
            INSERT INTO users (email, password_hash, phone, first_name, last_name, user_type, loyalty_points, is_active, internal_notes, created_at, updated_at)
            VALUES (:email, '', :phone, :first_name, :last_name, 'customer', 0, :is_active, :internal_notes, NOW(), NOW())
            RETURNING user_id, first_name, last_name, email, phone, is_active, created_at, updated_at
            """,
            {
                "email": email,
                "phone": phone,
                "first_name": (data.get("firstName") or "").strip(),
                "last_name": (data.get("lastName") or "").strip(),
                "is_active": is_active,
                "internal_notes": _coerce_internal_notes_value(data),
            },
        )
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "A customer with this email or phone already exists"}), 409
    uid = int(row["user_id"])
    try:
        _insert_addresses_for_customer(uid, data.get("addresses"))
    except Exception:
        db.session.rollback()
        raise
    db.session.commit()
    body = get_customer(uid)
    return jsonify(body.get_json()), 201


@rest_bp.put("/customers/<int:customer_id>")
def update_customer(customer_id: int):
    data = request.get_json(silent=True) or {}
    if not _one("SELECT user_id FROM users WHERE user_id = :id AND user_type = 'customer'", {"id": customer_id}):
        return jsonify({"message": "Customer not found"}), 404

    set_parts: list[str] = []
    params: dict = {"id": customer_id}
    if "firstName" in data:
        set_parts.append("first_name = :fn")
        params["fn"] = (data.get("firstName") or "").strip()
    if "lastName" in data:
        set_parts.append("last_name = :ln")
        params["ln"] = (data.get("lastName") or "").strip()
    if "email" in data:
        set_parts.append("email = :em")
        params["em"] = (data.get("email") or "").strip()
    if "phone" in data:
        set_parts.append("phone = :ph")
        params["ph"] = (data.get("phone") or "").strip()
    if "status" in data:
        set_parts.append("is_active = :ia")
        params["ia"] = (data.get("status") or "active").strip().lower() != "inactive"
    if "internalNotes" in data or "internal_notes" in data:
        set_parts.append("internal_notes = :inotes")
        v = data.get("internalNotes", data.get("internal_notes"))
        params["inotes"] = "" if v is None else (v if isinstance(v, str) else str(v))
    if "loyaltyPoints" in data or "loyalty_points" in data:
        lp = data.get("loyaltyPoints", data.get("loyalty_points"))
        try:
            params["lp"] = int(lp)
        except (TypeError, ValueError):
            return jsonify({"message": "loyaltyPoints must be an integer"}), 400
        set_parts.append("loyalty_points = :lp")

    try:
        if set_parts:
            set_parts.append("updated_at = NOW()")
            _exec(
                f"UPDATE users SET {', '.join(set_parts)} WHERE user_id = :id AND user_type = 'customer'",
                params,
            )
        elif "addresses" in data and isinstance(data.get("addresses"), list):
            _exec(
                "UPDATE users SET updated_at = NOW() WHERE user_id = :id AND user_type = 'customer'",
                {"id": customer_id},
            )

        if "addresses" in data and isinstance(data.get("addresses"), list):
            _sync_addresses_for_customer(customer_id, data["addresses"])
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "A customer with this email or phone already exists"}), 409

    db.session.commit()
    return get_customer(customer_id)


@rest_bp.delete("/customers/<int:customer_id>")
def delete_customer(customer_id: int):
    _q("DELETE FROM users WHERE user_id=:id AND user_type='customer'", {"id": customer_id})
    db.session.commit()
    return "", 204


@rest_bp.get("/technicians")
def list_technicians():
    page = _int_param("page", 1)
    limit = _int_param("limit", 10)
    search = request.args.get("search", "").strip()
    status = request.args.get("status")
    rows = _q(
        """
        SELECT tp.technician_id, u.user_id, u.first_name, u.last_name, u.email, u.phone, tp.specialization, tp.status,
               tp.experience_years, tp.certification, tp.rating, tp.total_reviews, tp.created_at
        FROM technician_profiles tp
        JOIN users u ON u.user_id = tp.user_id
        WHERE (:status IS NULL OR tp.status = :status)
          AND (:search = '' OR LOWER(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) LIKE LOWER(:like_search)
               OR LOWER(COALESCE(tp.specialization,'')) LIKE LOWER(:like_search)
               OR LOWER(COALESCE(u.email,'')) LIKE LOWER(:like_search))
        ORDER BY tp.technician_id DESC
        """,
        {"status": status, "search": search, "like_search": f"%{search}%"},
    )
    addresses = _addresses_by_user_ids([int(r["user_id"]) for r in rows])
    mapped = [
        {
            "id": str(r["technician_id"]),
            "firstName": r["first_name"] or "",
            "lastName": r["last_name"] or "",
            "email": r["email"],
            "phone": r["phone"] or "",
            "specialization": [r["specialization"]] if r["specialization"] else [],
            "experience": r["experience_years"] or 0,
            "status": r["status"] or "available",
            "addresses": addresses.get(int(r["user_id"]), []),
            "rating": float(r["rating"] or 0),
            "totalReviews": r["total_reviews"] or 0,
            "certifications": [r["certification"]] if r["certification"] else [],
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    return jsonify(_paginate(mapped, page, limit))


@rest_bp.get("/technicians/<int:technician_id>")
def get_technician(technician_id: int):
    r = _one(
        """
        SELECT tp.technician_id, u.first_name, u.last_name, u.email, u.phone, tp.specialization, tp.status,
               tp.experience_years, tp.certification, tp.rating, tp.total_reviews, tp.created_at
        FROM technician_profiles tp JOIN users u ON u.user_id=tp.user_id
        WHERE tp.technician_id=:id
        """,
        {"id": technician_id},
    )
    if not r:
        return jsonify({"message": "Technician not found"}), 404
    return jsonify({"id": str(r["technician_id"]), "firstName": r["first_name"] or "", "lastName": r["last_name"] or "", "email": r["email"], "phone": r["phone"] or "", "specialization": [r["specialization"]] if r["specialization"] else [], "experience": r["experience_years"] or 0, "status": r["status"] or "available"})


@rest_bp.post("/technicians")
def create_technician():
    d = request.get_json(silent=True) or {}
    user = _one(
        """
        INSERT INTO users (email, password_hash, phone, first_name, last_name, user_type, loyalty_points, is_active, created_at, updated_at)
        VALUES (:email, '', :phone, :first_name, :last_name, 'technician', 0, true, NOW(), NOW())
        RETURNING user_id, first_name, last_name, email, phone
        """,
        {"email": d.get("email", ""), "phone": d.get("phone", ""), "first_name": d.get("firstName", ""), "last_name": d.get("lastName", "")},
    )
    tech = _one(
        """
        INSERT INTO technician_profiles (user_id, specialization, experience_years, bio, hourly_rate, certification, rating, total_reviews, status, created_at)
        VALUES (:uid, :specialization, :experience, :bio, :hourly_rate, :certification, 0, 0, :status, NOW())
        RETURNING technician_id, status, experience_years
        """,
        {
            "uid": user["user_id"],
            "specialization": ", ".join(d.get("specialization", [])) if isinstance(d.get("specialization"), list) else d.get("specialization", ""),
            "experience": d.get("experience", 0),
            "bio": d.get("bio"),
            "hourly_rate": d.get("hourlyRate"),
            "certification": ", ".join(d.get("certifications", [])) if isinstance(d.get("certifications"), list) else d.get("certifications", ""),
            "status": d.get("status", "available"),
        },
    )
    db.session.commit()
    return jsonify({"id": str(tech["technician_id"]), "firstName": user["first_name"], "lastName": user["last_name"], "email": user["email"], "phone": user["phone"], "status": tech["status"], "experience": tech["experience_years"]}), 201


@rest_bp.put("/technicians/<int:technician_id>")
def update_technician(technician_id: int):
    d = request.get_json(silent=True) or {}
    if not _one("SELECT 1 AS ok FROM technician_profiles WHERE technician_id = :id", {"id": technician_id}):
        return jsonify({"message": "Technician not found"}), 404
    _q(
        """
        UPDATE users u
        SET first_name = COALESCE(:first_name, u.first_name),
            last_name = COALESCE(:last_name, u.last_name),
            email = COALESCE(:email, u.email),
            phone = COALESCE(:phone, u.phone),
            loyalty_points = COALESCE(:loyalty_points, u.loyalty_points),
            updated_at = NOW()
        FROM technician_profiles tp
        WHERE tp.technician_id = :id AND u.user_id = tp.user_id
        """,
        {
            "id": technician_id,
            "first_name": d.get("firstName"),
            "last_name": d.get("lastName"),
            "email": d.get("email"),
            "phone": d.get("phone"),
            "loyalty_points": d.get("loyaltyPoints") if "loyaltyPoints" in d else (d.get("loyalty_points") if "loyalty_points" in d else None),
        },
    )
    if "internalNotes" in d or "internal_notes" in d:
        v = d.get("internalNotes", d.get("internal_notes"))
        inotes = "" if v is None else (v if isinstance(v, str) else str(v))
        _exec(
            """
            UPDATE users u SET internal_notes = :inotes, updated_at = NOW()
            FROM technician_profiles tp
            WHERE tp.technician_id = :id AND u.user_id = tp.user_id
            """,
            {"id": technician_id, "inotes": inotes},
        )
    spec = d.get("specialization")
    if isinstance(spec, list):
        spec = ", ".join(str(x) for x in spec if x is not None and str(x).strip()) or None
    cert = d.get("certifications", d.get("certification"))
    if isinstance(cert, list):
        cert = ", ".join(str(x) for x in cert if x is not None and str(x).strip()) or None
    hr = None
    if "hourlyRate" in d or "hourly_rate" in d:
        hv = d.get("hourlyRate", d.get("hourly_rate"))
        try:
            hr = float(hv) if hv is not None and str(hv).strip() != "" else None
        except (TypeError, ValueError):
            return jsonify({"message": "hourlyRate must be a number"}), 400
    trt = None
    if "rating" in d:
        try:
            trt = float(d["rating"])
        except (TypeError, ValueError):
            return jsonify({"message": "rating must be a number"}), 400
    trev = None
    if "totalReviews" in d or "total_reviews" in d:
        try:
            trev = int(d.get("totalReviews", d.get("total_reviews")))
        except (TypeError, ValueError):
            return jsonify({"message": "totalReviews must be an integer"}), 400
    _q(
        """
        UPDATE technician_profiles
        SET specialization = COALESCE(:specialization, specialization),
            experience_years = COALESCE(:experience, experience_years),
            status = COALESCE(:status, status),
            certification = COALESCE(:certification, certification),
            bio = COALESCE(:bio, bio),
            hourly_rate = COALESCE(:hourly_rate, hourly_rate),
            rating = COALESCE(:rating, rating),
            total_reviews = COALESCE(:total_reviews, total_reviews)
        WHERE technician_id=:id
        """,
        {
            "id": technician_id,
            "specialization": spec if "specialization" in d else None,
            "experience": d.get("experience") if "experience" in d else (d.get("experienceYears") if "experienceYears" in d else None),
            "status": d.get("status") if "status" in d else None,
            "certification": cert if ("certifications" in d or "certification" in d) else None,
            "bio": d.get("bio") if "bio" in d else None,
            "hourly_rate": hr if ("hourlyRate" in d or "hourly_rate" in d) else None,
            "rating": trt if "rating" in d else None,
            "total_reviews": trev if ("totalReviews" in d or "total_reviews" in d) else None,
        },
    )
    db.session.commit()
    return get_technician(technician_id)


@rest_bp.delete("/technicians/<int:technician_id>")
def delete_technician(technician_id: int):
    user = _one("SELECT user_id FROM technician_profiles WHERE technician_id=:id", {"id": technician_id})
    if not user:
        return jsonify({"message": "Technician not found"}), 404
    _q("DELETE FROM technician_profiles WHERE technician_id=:id", {"id": technician_id})
    _q("DELETE FROM users WHERE user_id=:uid", {"uid": user["user_id"]})
    db.session.commit()
    return "", 204


@rest_bp.get("/assets")
def list_assets():
    # Derived view from bookings + users + service_areas (no dedicated assets table in DB).
    page = _int_param("page", 1)
    limit = _int_param("limit", 10)
    search = request.args.get("search", "").strip()
    rows = _q(
        """
        SELECT b.booking_id, b.booking_number, b.customer_id, b.service_address, b.created_at, b.updated_at,
               u.first_name, u.last_name, sa.city, sa.zipcode
        FROM bookings b
        LEFT JOIN users u ON u.user_id = b.customer_id
        LEFT JOIN service_areas sa ON sa.area_id = b.area_id
        WHERE (:search='' OR LOWER(COALESCE(b.booking_number,'')) LIKE LOWER(:like_search)
               OR LOWER(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) LIKE LOWER(:like_search))
        ORDER BY b.booking_id DESC
        """,
        {"search": search, "like_search": f"%{search}%"},
    )
    mapped = [
        {
            "id": f"ast-{r['booking_id']}",
            "customerId": str(r["customer_id"]) if r["customer_id"] else "",
            "customerName": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "assetType": "other",
            "brand": "",
            "model": "",
            "installationDate": r["created_at"].isoformat() if r["created_at"] else None,
            "address": r["service_address"] or "",
            "city": r["city"] or "",
            "zipCode": r["zipcode"] or "",
            "warranties": [],
            "amcStatus": "none",
            "isActive": True,
            "serviceHistory": [{"orderId": str(r["booking_id"]), "date": r["created_at"].isoformat() if r["created_at"] else None, "service": "", "technicianName": "", "notes": ""}],
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
            "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
        for r in rows
    ]
    return jsonify(_paginate(mapped, page, limit))


@rest_bp.get("/assets/<asset_id>")
def get_asset(asset_id: str):
    try:
        booking_id = int(str(asset_id).replace("ast-", ""))
    except ValueError:
        return jsonify({"message": "Asset not found"}), 404
    row = _one("SELECT booking_id, booking_number, customer_id, service_address, created_at, updated_at FROM bookings WHERE booking_id=:id", {"id": booking_id})
    if not row:
        return jsonify({"message": "Asset not found"}), 404
    return jsonify({"id": f"ast-{row['booking_id']}", "customerId": str(row["customer_id"]) if row["customer_id"] else "", "assetType": "other", "brand": "", "model": "", "installationDate": row["created_at"].isoformat() if row["created_at"] else None, "address": row["service_address"] or "", "city": "", "zipCode": "", "warranties": [], "amcStatus": "none", "isActive": True, "serviceHistory": [], "createdAt": row["created_at"].isoformat() if row["created_at"] else None, "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None})


@rest_bp.post("/assets")
def create_asset():
    return jsonify({"message": "Assets are derived from bookings in current schema"}), 501


@rest_bp.put("/assets/<asset_id>")
def update_asset(asset_id: str):
    return jsonify({"message": "Assets are derived from bookings in current schema"}), 501


@rest_bp.delete("/assets/<asset_id>")
def delete_asset(asset_id: str):
    return jsonify({"message": "Assets are derived from bookings in current schema"}), 501


@rest_bp.get("/orders")
def list_orders():
    page = _int_param("page", 1)
    limit = _int_param("limit", 10)
    search = request.args.get("search", "").strip()
    status = request.args.get("status")
    customer_id_raw = request.args.get("customerId")
    if customer_id_raw is None:
        customer_id_raw = request.args.get("customer_id")
    customer_id = None
    if customer_id_raw is not None and str(customer_id_raw).strip() != "":
        try:
            customer_id = int(str(customer_id_raw).strip())
        except (TypeError, ValueError):
            return jsonify({"message": "customerId must be an integer"}), 400
    rows = _q(
        """
        SELECT b.booking_id, b.booking_number, b.customer_id, b.status, b.total_amount, b.created_at, b.updated_at, b.technician_id,
               u.first_name, u.last_name, u.phone
        FROM bookings b
        LEFT JOIN users u ON u.user_id = b.customer_id
        WHERE (:status IS NULL OR b.status=:status)
          AND (:customer_id IS NULL OR b.customer_id = :customer_id)
          AND (:search='' OR LOWER(COALESCE(b.booking_number,'')) LIKE LOWER(:like_search)
               OR LOWER(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) LIKE LOWER(:like_search)
               OR COALESCE(u.phone,'') LIKE :like_search)
        ORDER BY b.booking_id DESC
        """,
        {"status": status, "customer_id": customer_id, "search": search, "like_search": f"%{search}%"},
    )
    mapped = [
        {
            "id": str(r["booking_id"]),
            "orderNo": r["booking_number"],
            "customerId": str(r["customer_id"]) if r["customer_id"] else "",
            "customerName": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "phone": r["phone"] or "",
            "status": r["status"],
            "priority": "medium",
            "service": "",
            "technicianId": str(r["technician_id"]) if r["technician_id"] else None,
            "totalAmount": float(r["total_amount"] or 0),
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
            "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
        for r in rows
    ]
    by_booking = _booking_items_by_booking_ids([int(r["booking_id"]) for r in rows])
    for m in mapped:
        m["bookingItems"] = by_booking.get(int(m["id"]), [])
    return jsonify(_paginate(mapped, page, limit))


@rest_bp.get("/orders/<int:order_id>")
def get_order(order_id: int):
    row = _one("SELECT booking_id, booking_number, customer_id, status, technician_id, total_amount, created_at, updated_at FROM bookings WHERE booking_id=:id", {"id": order_id})
    if not row:
        return jsonify({"message": "Order not found"}), 404
    items = _booking_items_by_booking_ids([int(row["booking_id"])]).get(int(row["booking_id"]), [])
    return jsonify({"id": str(row["booking_id"]), "orderNo": row["booking_number"], "customerId": str(row["customer_id"]) if row["customer_id"] else "", "status": row["status"], "technicianId": str(row["technician_id"]) if row["technician_id"] else None, "totalAmount": float(row["total_amount"] or 0), "bookingItems": items, "createdAt": row["created_at"].isoformat() if row["created_at"] else None, "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None})


@rest_bp.post("/orders")
def create_order():
    d = request.get_json(silent=True) or {}
    raw_customer = d.get("customerId")
    if raw_customer is None or (isinstance(raw_customer, str) and not str(raw_customer).strip()):
        raw_customer = d.get("customer_id")
    if raw_customer is None or (isinstance(raw_customer, str) and not str(raw_customer).strip()):
        return jsonify(
            {"message": "customerId is required (users.user_id). Send JSON key customerId or customer_id."}
        ), 400
    try:
        customer_id = int(str(raw_customer).strip())
    except (TypeError, ValueError):
        return jsonify({"message": "customerId must be an integer"}), 400

    if not _one("SELECT 1 AS ok FROM users WHERE user_id = :id", {"id": customer_id}):
        return jsonify({"message": "customerId does not match an existing user"}), 404

    raw_tech = d.get("technicianId")
    if raw_tech is None or (isinstance(raw_tech, str) and not str(raw_tech).strip()):
        raw_tech = d.get("technician_id")
    technician_id = None
    if raw_tech is not None and str(raw_tech).strip() != "":
        try:
            technician_id = int(str(raw_tech).strip())
        except (TypeError, ValueError):
            return jsonify({"message": "technicianId must be an integer"}), 400

    item_service_ids = _collect_order_item_service_ids(d)
    service_rows = []
    by_sid = {}
    if item_service_ids:
        ph = ",".join([f":s{i}" for i in range(len(item_service_ids))])
        sparams = {f"s{i}": item_service_ids[i] for i in range(len(item_service_ids))}
        service_rows = _q(
            f"SELECT service_id, base_price, name, description FROM services WHERE service_id IN ({ph})",
            sparams,
        )
        by_sid = {int(r["service_id"]): r for r in service_rows}
        if len(by_sid) != len(item_service_ids):
            return jsonify({"message": "One or more serviceIds were not found"}), 404

    number = d.get("orderNo") or f"ORD-{int(datetime.utcnow().timestamp())}"
    row = _one(
        """
        INSERT INTO bookings (booking_number, customer_id, technician_id, service_address, status, subtotal, discount_amount,
                              loyalty_points_used, loyalty_discount, total_amount, loyalty_points_earned, is_subscription_booking,
                              customer_notes, created_at, updated_at)
        VALUES (:n,:c,:t,:a,:s,:sub,:dis,:lp,:ld,:tot,:lpe,:isb,:cn,NOW(),NOW())
        RETURNING booking_id, booking_number, status, technician_id, total_amount, created_at, updated_at
        """,
        {
            "n": number,
            "c": customer_id,
            "t": technician_id,
            "a": d.get("address"),
            "s": d.get("status") or DEFAULT_BOOKING_STATUS,
            "sub": d.get("subtotal", 0),
            "dis": d.get("discountAmount", 0),
            "lp": d.get("loyaltyPointsUsed", 0),
            "ld": 0,
            "tot": d.get("totalAmount", 0),
            "lpe": d.get("loyaltyPointsEarned", 0),
            "isb": d.get("isSubscriptionBooking", False),
            "cn": d.get("customerNotes"),
        },
    )
    if item_service_ids:
        booking_items_raw = d.get("bookingItems") if isinstance(d.get("bookingItems"), list) else None
        if booking_items_raw:
            for it in booking_items_raw:
                if not isinstance(it, dict):
                    continue
                try:
                    sid = int(it.get("serviceId", it.get("service_id")))
                except (TypeError, ValueError):
                    continue
                if sid not in by_sid:
                    continue
                qty = it.get("quantity", 1)
                try:
                    qty = int(qty)
                except (TypeError, ValueError):
                    qty = 1
                if qty < 1:
                    qty = 1
                unit = it.get("unitPrice")
                try:
                    unit = float(unit) if unit is not None else float(by_sid[sid]["base_price"] or 0)
                except (TypeError, ValueError):
                    unit = float(by_sid[sid]["base_price"] or 0)
                total_price = round(unit * qty, 2)
                voice_url = (it.get("voiceUrl") or it.get("voiceNoteUrl") or "").strip() or None
                video_url = (it.get("videoUrl") or "").strip() or None
                image_url = (it.get("imageUrl") or "").strip() or None
                notes = (it.get("notes") or it.get("customerNotes") or d.get("customerNotes") or "").strip() or None
                _q(
                    """
                    INSERT INTO booking_items (booking_id, service_id, quantity, unit_price, total_price, voice_url, video_url, image_url, notes, created_at, updated_at)
                    VALUES (:bid, :sid, :qty, :unit, :tot, :voice_url, :video_url, :image_url, :notes, NOW(), NOW())
                    """,
                    {"bid": row["booking_id"], "sid": sid, "qty": qty, "unit": unit, "tot": total_price, "voice_url": voice_url, "video_url": video_url, "image_url": image_url, "notes": notes},
                )
        else:
            for sid in item_service_ids:
                unit = float(by_sid[sid]["base_price"] or 0)
                notes = (d.get("customerNotes") or "").strip() or None
                _q(
                    """
                    INSERT INTO booking_items (booking_id, service_id, quantity, unit_price, total_price, voice_url, video_url, image_url, notes, created_at, updated_at)
                    VALUES (:bid, :sid, 1, :unit, :tot, NULL, NULL, NULL, :notes, NOW(), NOW())
                    """,
                    {"bid": row["booking_id"], "sid": sid, "unit": unit, "tot": unit, "notes": notes},
                )

    db.session.commit()
    return (
        jsonify(
            {
                "message": "Customer request has been booked successfully",
                "id": str(row["booking_id"]),
                "orderNo": row["booking_number"],
                "status": row["status"],
            }
        ),
        201,
    )


@rest_bp.put("/orders/<int:order_id>")
def update_order(order_id: int):
    d = request.get_json(silent=True) or {}
    if not _one("SELECT 1 AS ok FROM bookings WHERE booking_id = :id", {"id": order_id}):
        return jsonify({"message": "Order not found"}), 404

    sets: list[str] = []
    params: dict = {"id": order_id}

    def _fk_user(uid: int) -> bool:
        return bool(_one("SELECT 1 AS ok FROM users WHERE user_id = :id", {"id": uid}))

    def _fk_tech(tid: int) -> bool:
        return bool(_one("SELECT 1 AS ok FROM technician_profiles WHERE technician_id = :id", {"id": tid}))

    if "orderNo" in d or "booking_number" in d:
        v = d.get("orderNo", d.get("booking_number"))
        sets.append("booking_number = :booking_number")
        params["booking_number"] = str(v) if v is not None else ""
    if "customerId" in d or "customer_id" in d:
        raw = d.get("customerId", d.get("customer_id"))
        if raw is None or (isinstance(raw, str) and not str(raw).strip()):
            sets.append("customer_id = NULL")
        else:
            try:
                cid = int(str(raw).strip())
            except (TypeError, ValueError):
                return jsonify({"message": "customerId must be an integer"}), 400
            if not _fk_user(cid):
                return jsonify({"message": "customerId does not match an existing user"}), 404
            sets.append("customer_id = :customer_id")
            params["customer_id"] = cid
    if "technicianId" in d or "technician_id" in d:
        raw = d.get("technicianId", d.get("technician_id"))
        if raw is None or (isinstance(raw, str) and not str(raw).strip()):
            sets.append("technician_id = NULL")
        else:
            try:
                tid = int(str(raw).strip())
            except (TypeError, ValueError):
                return jsonify({"message": "technicianId must be an integer"}), 400
            if not _fk_tech(tid):
                return jsonify({"message": "technicianId does not match an existing technician"}), 404
            sets.append("technician_id = :technician_id")
            params["technician_id"] = tid
    if "status" in d:
        sets.append("status = :bstatus")
        params["bstatus"] = d.get("status")
    if "address" in d or "serviceAddress" in d or "service_address" in d:
        sets.append("service_address = :svc_addr")
        params["svc_addr"] = d.get("address", d.get("serviceAddress", d.get("service_address")))
    if "subtotal" in d:
        try:
            params["subtotal"] = float(d["subtotal"])
        except (TypeError, ValueError):
            return jsonify({"message": "subtotal must be a number"}), 400
        sets.append("subtotal = :subtotal")
    if "discountAmount" in d or "discount_amount" in d:
        try:
            params["discount_amount"] = float(d.get("discountAmount", d.get("discount_amount")))
        except (TypeError, ValueError):
            return jsonify({"message": "discountAmount must be a number"}), 400
        sets.append("discount_amount = :discount_amount")
    if "loyaltyPointsUsed" in d or "loyalty_points_used" in d:
        try:
            params["loyalty_points_used"] = int(d.get("loyaltyPointsUsed", d.get("loyalty_points_used")))
        except (TypeError, ValueError):
            return jsonify({"message": "loyaltyPointsUsed must be an integer"}), 400
        sets.append("loyalty_points_used = :loyalty_points_used")
    if "loyaltyDiscount" in d or "loyalty_discount" in d:
        try:
            params["loyalty_discount"] = float(d.get("loyaltyDiscount", d.get("loyalty_discount")))
        except (TypeError, ValueError):
            return jsonify({"message": "loyaltyDiscount must be a number"}), 400
        sets.append("loyalty_discount = :loyalty_discount")
    if "totalAmount" in d or "total_amount" in d:
        try:
            params["total_amount"] = float(d.get("totalAmount", d.get("total_amount")))
        except (TypeError, ValueError):
            return jsonify({"message": "totalAmount must be a number"}), 400
        sets.append("total_amount = :total_amount")
    if "loyaltyPointsEarned" in d or "loyalty_points_earned" in d:
        try:
            params["loyalty_points_earned"] = int(d.get("loyaltyPointsEarned", d.get("loyalty_points_earned")))
        except (TypeError, ValueError):
            return jsonify({"message": "loyaltyPointsEarned must be an integer"}), 400
        sets.append("loyalty_points_earned = :loyalty_points_earned")
    if "isSubscriptionBooking" in d or "is_subscription_booking" in d:
        v = d.get("isSubscriptionBooking", d.get("is_subscription_booking"))
        params["is_sub_book"] = bool(v)
        sets.append("is_subscription_booking = :is_sub_book")
    if "customerNotes" in d or "customer_notes" in d:
        sets.append("customer_notes = :cust_notes")
        params["cust_notes"] = d.get("customerNotes", d.get("customer_notes"))
    if "areaId" in d or "area_id" in d:
        raw = d.get("areaId", d.get("area_id"))
        if raw is None or (isinstance(raw, str) and not str(raw).strip()):
            sets.append("area_id = NULL")
        else:
            try:
                aid = int(str(raw).strip())
            except (TypeError, ValueError):
                return jsonify({"message": "areaId must be an integer"}), 400
            sets.append("area_id = :area_id")
            params["area_id"] = aid

    if sets:
        sets.append("updated_at = NOW()")
        _exec(f"UPDATE bookings SET {', '.join(sets)} WHERE booking_id = :id", params)
    db.session.commit()
    return get_order(order_id)


@rest_bp.delete("/orders/<int:order_id>")
def delete_order(order_id: int):
    _q("DELETE FROM booking_items WHERE booking_id=:id", {"id": order_id})
    _q("DELETE FROM bookings WHERE booking_id=:id", {"id": order_id})
    db.session.commit()
    return "", 204


@rest_bp.post("/orders/assign/<int:order_id>")
def assign_order(order_id: int):
    d = request.get_json(silent=True) or {}
    open_in = sql_in_text(OPEN_BOOKING_STATUSES)
    _q(
        f"""
        UPDATE bookings SET technician_id=:t,
            status=CASE WHEN status::text IN ({open_in}) THEN :assigned ELSE status END,
            updated_at=NOW() WHERE booking_id=:id
        """,
        {"id": order_id, "t": d.get("technicianId"), "assigned": ASSIGNED_BOOKING_STATUS},
    )
    db.session.commit()
    return get_order(order_id)


@rest_bp.post("/orders/escalate/<int:order_id>")
def escalate_order(order_id: int):
    d = request.get_json(silent=True) or {}
    _q("UPDATE bookings SET status='escalated', customer_notes=COALESCE(customer_notes,'') || ' | ESCALATION: ' || :reason, updated_at=NOW() WHERE booking_id=:id", {"id": order_id, "reason": d.get("reason", "Escalated")})
    db.session.commit()
    return get_order(order_id)


@rest_bp.get("/services")
def list_services():
    page = _int_param("page", 1)
    limit = _int_param("limit", 10)
    search = request.args.get("search", "").strip()
    status = request.args.get("status")
    category = request.args.get("category")
    try:
        rows = _q(
            """
            SELECT s.service_id, s.name, s.description, s.base_price, s.estimated_duration_mins,
                   COALESCE(cat.name, s.category) AS category,
                   s.category_id, s.image_url, s.is_active, s.loyalty_points_earned, s.created_at, s.updated_at
            FROM services s
            LEFT JOIN categories cat ON cat.id = s.category_id
            WHERE (:status IS NULL OR (:status='active' AND s.is_active=true) OR (:status='inactive' AND s.is_active=false))
              AND (:category IS NULL OR COALESCE(cat.name, s.category) = :category
                   OR (s.category_id IS NOT NULL AND CAST(s.category_id AS VARCHAR) = :category)
                   OR s.category = :category)
              AND (:search='' OR LOWER(s.name) LIKE LOWER(:like_search) OR LOWER(COALESCE(s.description,'')) LIKE LOWER(:like_search))
            ORDER BY s.service_id DESC
            """,
            {"status": status, "category": category, "search": search, "like_search": f"%{search}%"},
        )
    except ProgrammingError as e:
        if not is_missing_relation_error(e):
            raise
        rows = _q(
            """
            SELECT service_id, name, description, base_price, estimated_duration_mins, category,
                   NULL::integer AS category_id, image_url, is_active, loyalty_points_earned, created_at, updated_at
            FROM services
            WHERE (:status IS NULL OR (:status='active' AND is_active=true) OR (:status='inactive' AND is_active=false))
              AND (:category IS NULL OR category=:category)
              AND (:search='' OR LOWER(name) LIKE LOWER(:like_search) OR LOWER(COALESCE(description,'')) LIKE LOWER(:like_search))
            ORDER BY service_id DESC
            """,
            {"status": status, "category": category, "search": search, "like_search": f"%{search}%"},
        )
    mapped = [
        {
            "id": str(r["service_id"]),
            "name": r["name"],
            "description": r["description"] or "",
            "basePrice": float(r["base_price"] or 0),
            "estimatedDurationMins": r["estimated_duration_mins"] or 0,
            "category": r["category"],
            "categoryId": str(r["category_id"]) if r.get("category_id") is not None else (r["category"] or ""),
            "imageUrl": r["image_url"],
            "isActive": bool(r["is_active"]),
            "loyaltyPointsEarned": r["loyalty_points_earned"] or 0,
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
            "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
        for r in rows
    ]
    return jsonify(_paginate(mapped, page, limit))


@rest_bp.get("/services/<int:service_id>")
def get_service(service_id: int):
    try:
        r = _one(
            """
            SELECT s.service_id, s.name, s.description, s.base_price, s.estimated_duration_mins,
                   s.category, s.category_id, s.image_url, s.is_active,
                   COALESCE(cat.name, s.category) AS display_category
            FROM services s
            LEFT JOIN categories cat ON cat.id = s.category_id
            WHERE s.service_id = :id
            """,
            {"id": service_id},
        )
    except ProgrammingError as e:
        if not is_missing_relation_error(e):
            raise
        r = _one("SELECT * FROM services WHERE service_id=:id", {"id": service_id})
        if r:
            r = dict(r)
            r["display_category"] = r.get("category")
    if not r:
        return jsonify({"message": "Service not found"}), 404
    disp = r.get("display_category") or r.get("category") or ""
    cid = r.get("category_id")
    return jsonify(
        {
            "id": str(r["service_id"]),
            "name": r["name"],
            "description": r["description"] or "",
            "basePrice": float(r["base_price"] or 0),
            "estimatedDurationMins": r["estimated_duration_mins"] or 0,
            "category": disp,
            "categoryId": str(cid) if cid is not None else disp,
            "isActive": bool(r["is_active"]),
        }
    )


@rest_bp.post("/services")
def create_service():
    d = request.get_json(silent=True) or {}
    try:
        cid, cname = _resolve_category_for_service_write(d)
    except ProgrammingError as e:
        if is_missing_relation_error(e):
            cid, cname = None, d.get("category") or d.get("categoryId") or "General"
        else:
            raise
    params = {
        "name": d.get("name", ""),
        "description": d.get("description", ""),
        "base_price": d.get("basePrice", 0),
        "duration": d.get("estimatedDurationMins", 60),
        "category": cname,
        "category_id": cid,
        "image_url": d.get("imageUrl"),
        "is_active": d.get("isActive", True),
        "points": d.get("loyaltyPointsEarned", 0),
    }
    try:
        row = _one(
            """
            INSERT INTO services (name, description, base_price, estimated_duration_mins, category, category_id, image_url, is_active, loyalty_points_earned, created_at, updated_at)
            VALUES (:name,:description,:base_price,:duration,:category,:category_id,:image_url,:is_active,:points,NOW(),NOW())
            RETURNING service_id, name, description, base_price, estimated_duration_mins, category, category_id, is_active, created_at, updated_at
            """,
            params,
        )
    except ProgrammingError as e:
        if not is_missing_relation_error(e):
            raise
        row = _one(
            """
            INSERT INTO services (name, description, base_price, estimated_duration_mins, category, image_url, is_active, loyalty_points_earned, created_at, updated_at)
            VALUES (:name,:description,:base_price,:duration,:category,:image_url,:is_active,:points,NOW(),NOW())
            RETURNING service_id, name, description, base_price, estimated_duration_mins, category, is_active, created_at, updated_at
            """,
            {k: v for k, v in params.items() if k != "category_id"},
        )
    db.session.commit()
    return jsonify(
        {
            "id": str(row["service_id"]),
            "name": row["name"],
            "description": row["description"] or "",
            "basePrice": float(row["base_price"] or 0),
            "estimatedDurationMins": row["estimated_duration_mins"] or 0,
            "category": row["category"],
            "categoryId": str(row["category_id"]) if row.get("category_id") is not None else row["category"],
            "isActive": bool(row["is_active"]),
        }
    ), 201


@rest_bp.put("/services/<int:service_id>")
def update_service(service_id: int):
    d = request.get_json(silent=True) or {}
    if not _one("SELECT 1 AS ok FROM services WHERE service_id = :id", {"id": service_id}):
        return jsonify({"message": "Service not found"}), 404

    d_body = dict(d)
    if "categoryId" in d_body or "category_id" in d_body:
        rv = d_body["categoryId"] if "categoryId" in d_body else d_body.get("category_id")
        if rv is None or (isinstance(rv, str) and not str(rv).strip()):
            try:
                _exec("UPDATE services SET category_id = NULL, updated_at = NOW() WHERE service_id = :id", {"id": service_id})
            except ProgrammingError as e:
                if not is_missing_relation_error(e):
                    raise
            d_body.pop("categoryId", None)
            d_body.pop("category_id", None)

    cid, cname = None, None
    if any(k in d_body for k in ("category", "categoryId", "category_id")):
        try:
            cid, cname = _resolve_category_for_service_write(d_body)
        except ProgrammingError as e:
            if is_missing_relation_error(e):
                cid, cname = None, d_body.get("category") or d_body.get("categoryId")
            else:
                raise
    bind = {
        "id": service_id,
        "name": d.get("name"),
        "description": d.get("description"),
        "base_price": d.get("basePrice"),
        "duration": d.get("estimatedDurationMins"),
        "category": cname,
        "category_id": cid,
        "image_url": d.get("imageUrl"),
        "is_active": d.get("isActive"),
        "points": d.get("loyaltyPointsEarned"),
    }
    try:
        db.session.execute(
            text(
                """
                UPDATE services
                SET name = COALESCE(:name, name),
                    description = COALESCE(:description, description),
                    base_price = COALESCE(:base_price, base_price),
                    estimated_duration_mins = COALESCE(:duration, estimated_duration_mins),
                    category = COALESCE(:category, category),
                    category_id = COALESCE(:category_id, category_id),
                    image_url = COALESCE(:image_url, image_url),
                    is_active = COALESCE(:is_active, is_active),
                    loyalty_points_earned = COALESCE(:points, loyalty_points_earned),
                    updated_at = NOW()
                WHERE service_id=:id
                """
            ),
            bind,
        )
    except ProgrammingError as e:
        if not is_missing_relation_error(e):
            raise
        db.session.execute(
            text(
                """
                UPDATE services
                SET name = COALESCE(:name, name),
                    description = COALESCE(:description, description),
                    base_price = COALESCE(:base_price, base_price),
                    estimated_duration_mins = COALESCE(:duration, estimated_duration_mins),
                    category = COALESCE(:category, category),
                    image_url = COALESCE(:image_url, image_url),
                    is_active = COALESCE(:is_active, is_active),
                    loyalty_points_earned = COALESCE(:points, loyalty_points_earned),
                    updated_at = NOW()
                WHERE service_id=:id
                """
            ),
            {k: v for k, v in bind.items() if k != "category_id"},
        )
    db.session.commit()
    return get_service(service_id)


@rest_bp.delete("/services/<int:service_id>")
def delete_service(service_id: int):
    _q("DELETE FROM services WHERE service_id=:id", {"id": service_id})
    db.session.commit()
    return "", 204


@rest_bp.get("/services/categories")
def service_categories():
    try:
        rows = _q(
            """
            SELECT id, name, COALESCE(description, '') AS description, is_active
            FROM categories
            WHERE is_active = true
            ORDER BY name
            """
        )
    except ProgrammingError as e:
        if is_missing_relation_error(e):
            rows = []
        else:
            raise
    if rows:
        try:
            sub_rows = _q(
                """
                SELECT id, category_id, name, COALESCE(description, '') AS description, is_active
                FROM sub_categories
                WHERE is_active = true
                ORDER BY category_id, name
                """
            )
        except ProgrammingError as e:
            if is_missing_relation_error(e):
                sub_rows = []
            else:
                raise
        by_parent: dict[int, list] = {}
        for s in sub_rows:
            by_parent.setdefault(s["category_id"], []).append(
                {
                    "id": str(s["id"]),
                    "categoryId": str(s["category_id"]),
                    "name": s["name"],
                    "description": s["description"] or "",
                    "isActive": bool(s["is_active"]),
                }
            )
        return jsonify(
            [
                {
                    "id": str(r["id"]),
                    "name": r["name"],
                    "description": r["description"] or "",
                    "isActive": bool(r["is_active"]),
                    "enabledZipCodes": [],
                    "subCategories": by_parent.get(r["id"], []),
                }
                for r in rows
            ]
        )
    legacy = _q("SELECT DISTINCT category AS name FROM services WHERE category IS NOT NULL ORDER BY category")
    return jsonify(
        [
            {
                "id": r["name"],
                "name": r["name"],
                "description": "",
                "isActive": True,
                "enabledZipCodes": [],
                "subCategories": [],
            }
            for r in legacy
        ]
    )


@rest_bp.get("/catalog/subcategories")
def catalog_subcategories():
    """Subcategories for a parent category: ?categoryId=<int> (required)."""
    raw = request.args.get("categoryId") or request.args.get("category_id")
    if not raw or not str(raw).strip().isdigit():
        return jsonify({"message": "categoryId is required"}), 400
    cid = int(raw)
    try:
        rows = _q(
            """
            SELECT id, category_id, name, COALESCE(description, '') AS description, is_active
            FROM sub_categories
            WHERE category_id = :cid AND is_active = true
            ORDER BY name
            """,
            {"cid": cid},
        )
    except ProgrammingError as e:
        if is_missing_relation_error(e):
            return jsonify([])
        raise
    return jsonify(
        [
            {
                "id": str(r["id"]),
                "categoryId": str(r["category_id"]),
                "name": r["name"],
                "description": r["description"] or "",
                "isActive": bool(r["is_active"]),
            }
            for r in rows
        ]
    )


@rest_bp.put("/addresses/<int:address_id>")
def update_address_row(address_id: int):
    """Update a single row in ``addresses`` or ``customer_addresses`` (all writable columns)."""
    d = request.get_json(silent=True) or {}
    tbl: str | None = None
    row = None
    try:
        row = _one("SELECT id, user_id FROM addresses WHERE id = :id", {"id": address_id})
    except ProgrammingError as e:
        if not is_missing_relation_error(e):
            raise
    if row:
        tbl = "addresses"
    else:
        try:
            row = _one("SELECT id, user_id FROM customer_addresses WHERE id = :id", {"id": address_id})
        except ProgrammingError as e:
            if not is_missing_relation_error(e):
                raise
            return jsonify({"message": "Address storage table not available"}), 501
        if row:
            tbl = "customer_addresses"
    if not tbl or not row:
        return jsonify({"message": "Address not found"}), 404

    uid = int(row["user_id"])
    sets: list[str] = []
    params: dict = {"id": address_id}

    if "label" in d or "nickName" in d:
        sets.append("label = :alabel")
        params["alabel"] = (d.get("label") or d.get("nickName") or "").strip() or "Home"
    if "line1" in d or "addressLine1" in d or "street" in d:
        v = d.get("line1") or d.get("addressLine1") or d.get("street")
        sets.append("line1 = :al1")
        params["al1"] = (v or "").strip() or ""
    if "line2" in d or "addressLine2" in d:
        sets.append("line2 = :al2")
        v = d.get("line2", d.get("addressLine2"))
        params["al2"] = (v or "").strip() or None
    if "city" in d:
        sets.append("city = :acity")
        params["acity"] = (d.get("city") or "").strip() or None
    if "state" in d:
        sets.append("state = :astate")
        params["astate"] = (d.get("state") or "").strip() or None
    if "zipCode" in d or "zip" in d:
        sets.append("zip_code = :azip")
        v = d.get("zipCode", d.get("zip"))
        params["azip"] = (str(v).strip() if v is not None else "") or None
    if "country" in d:
        sets.append("country = :actry")
        params["actry"] = (d.get("country") or "India").strip() or "India"
    if tbl == "addresses" and ("addressType" in d or "address_type" in d):
        sets.append("address_type = :aatype")
        params["aatype"] = ((d.get("addressType") or d.get("address_type") or "home") or "").strip() or "home"
    if "isDefault" in d or "isPrimary" in d or "is_default" in d:
        isd = bool(d.get("isDefault", d.get("isPrimary", d.get("is_default", False))))
        if isd:
            _exec(f"UPDATE {tbl} SET is_default = false WHERE user_id = :uid", {"uid": uid})
        sets.append("is_default = :aisd")
        params["aisd"] = isd

    if not sets:
        return jsonify({"message": "No updatable fields in body"}), 400
    if "al1" in params and (params["al1"] is None or str(params["al1"]).strip() == ""):
        return jsonify({"message": "line1 cannot be empty"}), 400

    sets.append("updated_at = NOW()")
    try:
        _exec(f"UPDATE {tbl} SET {', '.join(sets)} WHERE id = :id", params)
    except ProgrammingError as e:
        if is_missing_relation_error(e):
            return jsonify({"message": "Address storage table not available"}), 501
        raise
    db.session.commit()
    return jsonify({"id": str(address_id), "message": "Address updated"})


@rest_bp.put("/catalog/categories/<int:category_id>")
def update_category(category_id: int):
    d = request.get_json(silent=True) or {}
    if not _one("SELECT 1 AS ok FROM categories WHERE id = :id", {"id": category_id}):
        return jsonify({"message": "Category not found"}), 404
    sets: list[str] = []
    params: dict = {"id": category_id}
    if "name" in d:
        sets.append("name = :cname")
        params["cname"] = d.get("name")
    if "description" in d:
        sets.append("description = :cdesc")
        params["cdesc"] = d.get("description")
    if "icon" in d:
        sets.append("icon = :cicon")
        params["cicon"] = d.get("icon")
    if "isActive" in d or "is_active" in d:
        sets.append("is_active = :cactive")
        params["cactive"] = bool(d.get("isActive", d.get("is_active")))
    if not sets:
        return jsonify({"message": "No updatable fields in body"}), 400
    sets.append("updated_at = NOW()")
    try:
        _exec(f"UPDATE categories SET {', '.join(sets)} WHERE id = :id", params)
    except ProgrammingError as e:
        if is_missing_relation_error(e):
            return jsonify({"message": "categories table not available"}), 501
        raise
    db.session.commit()
    return jsonify({"id": str(category_id), "message": "Category updated"})


@rest_bp.put("/catalog/subcategories/<int:sub_category_id>")
def update_sub_category(sub_category_id: int):
    d = request.get_json(silent=True) or {}
    if not _one("SELECT 1 AS ok FROM sub_categories WHERE id = :id", {"id": sub_category_id}):
        return jsonify({"message": "Subcategory not found"}), 404
    sets: list[str] = []
    params: dict = {"id": sub_category_id}
    if "categoryId" in d or "category_id" in d:
        raw = d.get("categoryId", d.get("category_id"))
        try:
            cid = int(str(raw).strip())
        except (TypeError, ValueError):
            return jsonify({"message": "categoryId must be an integer"}), 400
        if not _one("SELECT 1 AS ok FROM categories WHERE id = :id", {"id": cid}):
            return jsonify({"message": "categoryId does not match an existing category"}), 404
        sets.append("category_id = :scat")
        params["scat"] = cid
    if "name" in d:
        sets.append("name = :sname")
        params["sname"] = d.get("name")
    if "description" in d:
        sets.append("description = :sdesc")
        params["sdesc"] = d.get("description")
    if "isActive" in d or "is_active" in d:
        sets.append("is_active = :sactive")
        params["sactive"] = bool(d.get("isActive", d.get("is_active")))
    if not sets:
        return jsonify({"message": "No updatable fields in body"}), 400
    sets.append("updated_at = NOW()")
    try:
        _exec(f"UPDATE sub_categories SET {', '.join(sets)} WHERE id = :id", params)
    except ProgrammingError as e:
        if is_missing_relation_error(e):
            return jsonify({"message": "sub_categories table not available"}), 501
        raise
    db.session.commit()
    return jsonify({"id": str(sub_category_id), "message": "Subcategory updated"})


@rest_bp.get("/services/addons")
def service_addons():
    service_id = request.args.get("serviceId")
    rows = _q("SELECT addon_id, service_id, name, description, price, is_active, created_at FROM service_addons WHERE (:sid IS NULL OR service_id=:sid)", {"sid": service_id})
    return jsonify([{"id": str(r["addon_id"]), "serviceId": str(r["service_id"]), "name": r["name"], "description": r["description"], "price": float(r["price"] or 0), "isActive": bool(r["is_active"]), "createdAt": r["created_at"].isoformat() if r["created_at"] else None} for r in rows])


@rest_bp.get("/services/warranties")
def service_warranties():
    service_id = request.args.get("serviceId")
    rows = _q("SELECT warranty_id, service_id, name, description, duration_days, coverage_details, exclusions, is_active, created_at FROM service_warranties WHERE (:sid IS NULL OR service_id=:sid)", {"sid": service_id})
    return jsonify([{"id": str(r["warranty_id"]), "serviceId": str(r["service_id"]), "name": r["name"], "description": r["description"], "durationDays": r["duration_days"], "coverageDetails": r["coverage_details"], "exclusions": r["exclusions"], "isActive": bool(r["is_active"]), "createdAt": r["created_at"].isoformat() if r["created_at"] else None} for r in rows])


@rest_bp.get("/services/packages")
def service_packages():
    rows = _q("SELECT package_id, name, description, package_price, discount_percentage, image_url, is_active, loyalty_points_earned, valid_from, valid_until, created_at FROM service_packages ORDER BY package_id DESC")
    return jsonify([{"id": str(r["package_id"]), "name": r["name"], "description": r["description"], "packagePrice": float(r["package_price"] or 0), "discountPercentage": float(r["discount_percentage"] or 0), "imageUrl": r["image_url"], "isActive": bool(r["is_active"]), "loyaltyPointsEarned": r["loyalty_points_earned"] or 0, "validFrom": r["valid_from"].isoformat() if r["valid_from"] else None, "validUntil": r["valid_until"].isoformat() if r["valid_until"] else None, "services": [], "createdAt": r["created_at"].isoformat() if r["created_at"] else None} for r in rows])


@rest_bp.get("/subscriptions/plans")
def subscription_plans():
    rows = _q("SELECT plan_id, name, description, billing_cycle, price, service_credits, discount_percentage, priority_booking, free_inspection, benefits, is_active, created_at FROM subscription_plans ORDER BY plan_id DESC")
    return jsonify([{"id": str(r["plan_id"]), "name": r["name"], "description": r["description"] or "", "billingCycle": r["billing_cycle"], "price": float(r["price"] or 0), "serviceCredits": r["service_credits"] or 0, "discountPercentage": float(r["discount_percentage"] or 0), "priorityBooking": bool(r["priority_booking"]), "freeInspection": bool(r["free_inspection"]), "benefits": r["benefits"] or "", "isActive": bool(r["is_active"]), "autoRenew": True, "includedServices": [], "createdAt": r["created_at"].isoformat() if r["created_at"] else None} for r in rows])


@rest_bp.post("/subscriptions/plans")
def create_subscription_plan():
    d = request.get_json(silent=True) or {}
    row = _one(
        """
        INSERT INTO subscription_plans (name, description, billing_cycle, price, service_credits, discount_percentage, priority_booking, free_inspection, benefits, is_active, created_at)
        VALUES (:name,:description,:billing,:price,:credits,:discount,:priority,:free_inspection,:benefits,:is_active,NOW())
        RETURNING plan_id, name, description, billing_cycle, price, service_credits, discount_percentage, priority_booking, free_inspection, benefits, is_active, created_at
        """,
        {
            "name": d.get("name", ""),
            "description": d.get("description", ""),
            "billing": d.get("billingCycle", "monthly"),
            "price": d.get("price", 0),
            "credits": d.get("serviceCredits", 0),
            "discount": d.get("discountPercentage", 0),
            "priority": 1 if d.get("priorityBooking", False) else 0,
            "free_inspection": d.get("freeInspection", False),
            "benefits": d.get("benefits", ""),
            "is_active": d.get("isActive", True),
        },
    )
    db.session.commit()
    return jsonify({"id": str(row["plan_id"]), "name": row["name"], "description": row["description"] or "", "billingCycle": row["billing_cycle"], "price": float(row["price"] or 0), "serviceCredits": row["service_credits"] or 0, "discountPercentage": float(row["discount_percentage"] or 0), "priorityBooking": bool(row["priority_booking"]), "freeInspection": bool(row["free_inspection"]), "benefits": row["benefits"] or "", "isActive": bool(row["is_active"]), "createdAt": row["created_at"].isoformat() if row["created_at"] else None}), 201


@rest_bp.put("/subscriptions/plans/<int:plan_id>")
def update_subscription_plan(plan_id: int):
    d = request.get_json(silent=True) or {}
    _q(
        """
        UPDATE subscription_plans
        SET name=COALESCE(:name,name),
            description=COALESCE(:description,description),
            billing_cycle=COALESCE(:billing,billing_cycle),
            price=COALESCE(:price,price),
            service_credits=COALESCE(:credits,service_credits),
            discount_percentage=COALESCE(:discount,discount_percentage),
            priority_booking=COALESCE(:priority,priority_booking),
            free_inspection=COALESCE(:free_inspection,free_inspection),
            benefits=COALESCE(:benefits,benefits),
            is_active=COALESCE(:is_active,is_active)
        WHERE plan_id=:id
        """,
        {
            "id": plan_id,
            "name": d.get("name"),
            "description": d.get("description"),
            "billing": d.get("billingCycle"),
            "price": d.get("price"),
            "credits": d.get("serviceCredits"),
            "discount": d.get("discountPercentage"),
            "priority": (1 if d.get("priorityBooking") else 0) if "priorityBooking" in d else None,
            "free_inspection": d.get("freeInspection"),
            "benefits": d.get("benefits"),
            "is_active": d.get("isActive"),
        },
    )
    db.session.commit()
    return jsonify({"message": "Subscription plan updated"})


@rest_bp.get("/subscriptions/user")
def user_subscriptions():
    page = _int_param("page", 1)
    limit = _int_param("limit", 10)
    search = request.args.get("search", "").strip()
    status = request.args.get("status")
    rows = _q(
        """
        SELECT us.subscription_id, us.user_id, us.plan_id, us.start_date, us.end_date, us.next_billing_date, us.status,
               us.credits_remaining, us.credits_used, us.created_at, us.updated_at,
               u.first_name, u.last_name, sp.name AS plan_name
        FROM user_subscriptions us
        LEFT JOIN users u ON u.user_id = us.user_id
        LEFT JOIN subscription_plans sp ON sp.plan_id = us.plan_id
        WHERE (:status IS NULL OR us.status=:status)
          AND (:search='' OR LOWER(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) LIKE LOWER(:like_search)
               OR LOWER(COALESCE(sp.name,'')) LIKE LOWER(:like_search))
        ORDER BY us.subscription_id DESC
        """,
        {"status": status, "search": search, "like_search": f"%{search}%"},
    )
    mapped = [{"id": str(r["subscription_id"]), "userId": str(r["user_id"]), "customerName": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(), "planId": str(r["plan_id"]), "planName": r["plan_name"] or "", "startDate": r["start_date"].isoformat() if r["start_date"] else None, "endDate": r["end_date"].isoformat() if r["end_date"] else None, "nextBillingDate": r["next_billing_date"].isoformat() if r["next_billing_date"] else None, "status": r["status"], "creditsRemaining": r["credits_remaining"] or 0, "creditsUsed": r["credits_used"] or 0, "createdAt": r["created_at"].isoformat() if r["created_at"] else None, "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None} for r in rows]
    return jsonify(_paginate(mapped, page, limit))


@rest_bp.get("/subscriptions/amc")
def amc_plans():
    rows = _q(
        """
        SELECT plan_id, name, description, price, is_active, created_at
        FROM subscription_plans
        WHERE LOWER(name) LIKE '%amc%'
        ORDER BY plan_id DESC
        """
    )
    return jsonify([{"id": f"amc-{r['plan_id']}", "name": r["name"], "description": r["description"] or "", "assetType": "other", "price": float(r["price"] or 0), "durationMonths": 12, "preventiveServiceCount": 0, "preventiveSchedule": "", "reminderDaysBefore": 7, "isActive": bool(r["is_active"]), "createdAt": r["created_at"].isoformat() if r["created_at"] else None} for r in rows])


@rest_bp.get("/subscriptions/user-amc")
def user_amc():
    page = _int_param("page", 1)
    limit = _int_param("limit", 10)
    rows = _q(
        """
        SELECT us.subscription_id, us.user_id, us.plan_id, us.start_date, us.end_date, us.status, us.created_at,
               u.first_name, u.last_name, sp.name
        FROM user_subscriptions us
        LEFT JOIN users u ON u.user_id = us.user_id
        LEFT JOIN subscription_plans sp ON sp.plan_id = us.plan_id
        WHERE LOWER(COALESCE(sp.name,'')) LIKE '%amc%'
        ORDER BY us.subscription_id DESC
        """
    )
    mapped = [{"id": f"uamc-{r['subscription_id']}", "userId": str(r["user_id"]), "customerName": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(), "amcPlanId": f"amc-{r['plan_id']}", "amcPlanName": r["name"] or "", "assetId": "", "assetName": "", "startDate": r["start_date"].isoformat() if r["start_date"] else None, "endDate": r["end_date"].isoformat() if r["end_date"] else None, "status": r["status"], "servicesUsed": 0, "servicesRemaining": 0, "createdAt": r["created_at"].isoformat() if r["created_at"] else None} for r in rows]
    return jsonify(_paginate(mapped, page, limit))


@rest_bp.get("/enumerations/specializations")
def enum_specializations():
    rows = _q("SELECT DISTINCT specialization FROM technician_profiles WHERE specialization IS NOT NULL ORDER BY specialization")
    return jsonify([{"value": r["specialization"], "label": r["specialization"]} for r in rows])


@rest_bp.get("/enumerations/service-categories")
def enum_service_categories():
    try:
        rows = _q("SELECT id, name FROM categories WHERE is_active = true ORDER BY name")
    except ProgrammingError as e:
        if is_missing_relation_error(e):
            rows = []
        else:
            raise
    if rows:
        return jsonify([{"value": str(r["id"]), "label": r["name"]} for r in rows])
    legacy = _q("SELECT DISTINCT category AS name FROM services WHERE category IS NOT NULL ORDER BY category")
    return jsonify([{"value": r["name"], "label": r["name"]} for r in legacy])


@rest_bp.get("/enumerations/zip-codes")
def enum_zip_codes():
    rows = _q("SELECT DISTINCT zipcode FROM service_areas WHERE zipcode IS NOT NULL ORDER BY zipcode")
    return jsonify([{"value": r["zipcode"], "label": r["zipcode"]} for r in rows])


@rest_bp.get("/enumerations/time-slots")
def enum_time_slots():
    rows = _q(
        """
        SELECT id, time_slot, active
        FROM time_slot_master
        WHERE active = 'Y'
        ORDER BY id ASC
        """
    )
    return jsonify(
        [
            {
                "id": str(r["id"]),
                "timeSlot": r["time_slot"],
                "active": r["active"],
            }
            for r in rows
        ]
    )


@rest_bp.get("/dashboard/stats")
def dashboard_stats():
    c = _one("SELECT COUNT(*) AS c FROM users WHERE user_type='customer'")["c"]
    t = _one("SELECT COUNT(*) AS c FROM technician_profiles")["c"]
    at = _one("SELECT COUNT(*) AS c FROM technician_profiles WHERE status='available'")["c"]
    o = _one("SELECT COUNT(*) AS c FROM bookings")["c"]
    pipe_in = sql_in_text(PIPELINE_BOOKING_STATUSES)
    po = _one(f"SELECT COUNT(*) AS c FROM bookings WHERE status::text IN ({pipe_in})")["c"]
    esc = _one("SELECT COUNT(*) AS c FROM bookings WHERE status='escalated'")["c"]
    rev = float(_one("SELECT COALESCE(SUM(amount),0) AS c FROM payments WHERE status='completed'")["c"] or 0)
    asub = _one("SELECT COUNT(*) AS c FROM user_subscriptions WHERE status='active'")["c"]
    return jsonify({"totalCustomers": c, "totalTechnicians": t, "activeTechnicians": at, "pendingOrders": po, "totalOrders": o, "totalRevenue": rev, "activeSubscriptions": asub, "totalAssets": 0, "slaCompliancePercent": 0, "pendingEscalations": esc, "recentCustomers": [], "recentTechnicians": [], "recentOrders": [], "customerGrowth": 0, "technicianGrowth": 0, "revenueGrowth": 0})


@rest_bp.get("/payments")
def payments():
    page = _int_param("page", 1)
    limit = _int_param("limit", 10)
    status = request.args.get("status")
    search = request.args.get("search", "").strip()
    rows = _q(
        """
        SELECT p.payment_id, p.booking_id, p.amount, p.payment_method, p.status, p.transaction_id, p.payment_date, p.created_at,
               b.booking_number, u.first_name, u.last_name
        FROM payments p
        LEFT JOIN bookings b ON b.booking_id = p.booking_id
        LEFT JOIN users u ON u.user_id = b.customer_id
        WHERE (:status IS NULL OR p.status=:status)
          AND (:search='' OR LOWER(COALESCE(b.booking_number,'')) LIKE LOWER(:like_search)
               OR LOWER(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) LIKE LOWER(:like_search)
               OR LOWER(COALESCE(p.transaction_id,'')) LIKE LOWER(:like_search))
        ORDER BY p.payment_id DESC
        """,
        {"status": status, "search": search, "like_search": f"%{search}%"},
    )
    mapped = [{"id": str(r["payment_id"]), "orderId": str(r["booking_id"]), "orderNo": r["booking_number"] or "", "customerName": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(), "amount": float(r["amount"] or 0), "paymentMethod": r["payment_method"], "status": r["status"], "transactionId": r["transaction_id"], "paymentDate": r["payment_date"].isoformat() if r["payment_date"] else None, "createdAt": r["created_at"].isoformat() if r["created_at"] else None} for r in rows]
    return jsonify(_paginate(mapped, page, limit))


@rest_bp.get("/payments/<payment_id>")
def payment_by_id(payment_id: str):
    try:
        pid = int(str(payment_id).replace("pay-", ""))
    except ValueError:
        return jsonify({"message": "Payment not found"}), 404
    r = _one("SELECT payment_id, booking_id, amount, payment_method, status, transaction_id, payment_date, created_at FROM payments WHERE payment_id=:id", {"id": pid})
    if not r:
        return jsonify({"message": "Payment not found"}), 404
    return jsonify({"id": f"pay-{r['payment_id']}", "orderId": str(r["booking_id"]), "orderNo": "", "customerName": "", "amount": float(r["amount"] or 0), "paymentMethod": r["payment_method"], "status": r["status"], "transactionId": r["transaction_id"], "paymentDate": r["payment_date"].isoformat() if r["payment_date"] else None, "createdAt": r["created_at"].isoformat() if r["created_at"] else None})


@rest_bp.get("/payments/payouts")
def payouts():
    page = _int_param("page", 1)
    limit = _int_param("limit", 10)
    status = request.args.get("status")
    search = request.args.get("search", "").strip()
    rows = _q(
        """
        SELECT p.payment_id, p.booking_id, p.amount, p.status, p.created_at,
               b.booking_number, tp.technician_id, u.first_name, u.last_name
        FROM payments p
        JOIN bookings b ON b.booking_id = p.booking_id
        LEFT JOIN technician_profiles tp ON tp.technician_id = b.technician_id
        LEFT JOIN users u ON u.user_id = tp.user_id
        WHERE (:status IS NULL OR p.status=:status)
          AND (:search='' OR LOWER(COALESCE(b.booking_number,'')) LIKE LOWER(:like_search)
               OR LOWER(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) LIKE LOWER(:like_search))
        ORDER BY p.payment_id DESC
        """,
        {"status": status, "search": search, "like_search": f"%{search}%"},
    )
    mapped = []
    for r in rows:
        amount = float(r["amount"] or 0)
        commission = round(amount * 0.15, 2)
        mapped.append({
            "id": f"po-{r['payment_id']}",
            "technicianId": str(r["technician_id"]) if r["technician_id"] else "",
            "technicianName": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "orderId": str(r["booking_id"]),
            "orderNo": r["booking_number"] or "",
            "amount": amount,
            "commissionAmount": commission,
            "netPayout": round(amount - commission, 2),
            "status": "paid" if r["status"] == "completed" else "pending",
            "paidAt": r["created_at"].isoformat() if r["status"] == "completed" and r["created_at"] else None,
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        })
    return jsonify(_paginate(mapped, page, limit))


@rest_bp.get("/payments/refunds")
def refunds():
    page = _int_param("page", 1)
    limit = _int_param("limit", 10)
    status = request.args.get("status")
    search = request.args.get("search", "").strip()
    rows = _q(
        """
        SELECT p.payment_id, p.booking_id, p.amount, p.status, p.created_at, b.booking_number,
               u.first_name, u.last_name
        FROM payments p
        LEFT JOIN bookings b ON b.booking_id = p.booking_id
        LEFT JOIN users u ON u.user_id = b.customer_id
        WHERE p.status IN ('refunded','failed')
          AND (:status IS NULL OR p.status=:status)
          AND (:search='' OR LOWER(COALESCE(b.booking_number,'')) LIKE LOWER(:like_search)
               OR LOWER(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) LIKE LOWER(:like_search))
        ORDER BY p.payment_id DESC
        """,
        {"status": status, "search": search, "like_search": f"%{search}%"},
    )
    mapped = [{
        "id": f"ref-{r['payment_id']}",
        "paymentId": f"pay-{r['payment_id']}",
        "orderId": str(r["booking_id"]) if r["booking_id"] else "",
        "orderNo": r["booking_number"] or "",
        "customerName": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
        "amount": float(r["amount"] or 0),
        "reason": "Auto-generated from payment status",
        "status": "processed" if r["status"] == "refunded" else "pending",
        "processedBy": "system" if r["status"] == "refunded" else None,
        "processedAt": r["created_at"].isoformat() if r["status"] == "refunded" and r["created_at"] else None,
        "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
    } for r in rows]
    return jsonify(_paginate(mapped, page, limit))


@rest_bp.put("/payments/refunds/<refund_id>")
def process_refund(refund_id: str):
    data = request.get_json(silent=True) or {}
    try:
        pid = int(str(refund_id).replace("ref-", ""))
    except ValueError:
        return jsonify({"message": "Invalid refund id"}), 400
    target_status = "refunded" if data.get("status") == "approved" else "failed"
    _q("UPDATE payments SET status=:status WHERE payment_id=:id", {"status": target_status, "id": pid})
    db.session.commit()
    return jsonify({"id": refund_id, "status": data.get("status", "approved"), "processedBy": data.get("processedBy"), "message": "Refund status updated"})


@rest_bp.get("/reviews")
def list_reviews():
    page = _int_param("page", 1)
    limit = _int_param("limit", 10)
    search = request.args.get("search", "").strip()
    status = request.args.get("status")
    booking_id = request.args.get("bookingId") or request.args.get("booking_id")
    customer_id = request.args.get("customerId") or request.args.get("customer_id")
    technician_id = request.args.get("technicianId") or request.args.get("technician_id")
    rows = _q(
        """
        SELECT review_id, booking_id, customer_id, technician_id, rating, title, review_text, is_active, created_at, updated_at
        FROM reviews
        WHERE (:status IS NULL OR (:status='active' AND is_active=true) OR (:status='inactive' AND is_active=false))
          AND (:booking_id IS NULL OR booking_id = CAST(:booking_id AS INTEGER))
          AND (:customer_id IS NULL OR customer_id = CAST(:customer_id AS INTEGER))
          AND (:technician_id IS NULL OR technician_id = CAST(:technician_id AS INTEGER))
          AND (:search='' OR LOWER(COALESCE(title,'')) LIKE LOWER(:like_search) OR LOWER(COALESCE(review_text,'')) LIKE LOWER(:like_search))
        ORDER BY review_id DESC
        """,
        {
            "status": status,
            "booking_id": booking_id,
            "customer_id": customer_id,
            "technician_id": technician_id,
            "search": search,
            "like_search": f"%{search}%",
        },
    )
    mapped = [
        {
            "id": str(r["review_id"]),
            "bookingId": str(r["booking_id"]) if r["booking_id"] is not None else "",
            "customerId": str(r["customer_id"]) if r["customer_id"] is not None else "",
            "technicianId": str(r["technician_id"]) if r["technician_id"] is not None else "",
            "rating": int(r["rating"] or 0),
            "title": r["title"] or "",
            "review": r["review_text"] or "",
            "status": "active" if r["is_active"] else "inactive",
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
            "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
        for r in rows
    ]
    return jsonify(_paginate(mapped, page, limit))


@rest_bp.get("/reviews/<int:review_id>")
def get_review(review_id: int):
    r = _one(
        """
        SELECT review_id, booking_id, customer_id, technician_id, rating, title, review_text, is_active, created_at, updated_at
        FROM reviews WHERE review_id = :id
        """,
        {"id": review_id},
    )
    if not r:
        return jsonify({"message": "Review not found"}), 404
    return jsonify(
        {
            "id": str(r["review_id"]),
            "bookingId": str(r["booking_id"]) if r["booking_id"] is not None else "",
            "customerId": str(r["customer_id"]) if r["customer_id"] is not None else "",
            "technicianId": str(r["technician_id"]) if r["technician_id"] is not None else "",
            "rating": int(r["rating"] or 0),
            "title": r["title"] or "",
            "review": r["review_text"] or "",
            "status": "active" if r["is_active"] else "inactive",
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
            "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
    )


@rest_bp.post("/reviews")
def create_review():
    d = request.get_json(silent=True) or {}
    try:
        rating = int(d.get("rating", 0))
    except (TypeError, ValueError):
        return jsonify({"message": "rating must be an integer"}), 400
    if rating < 1 or rating > 5:
        return jsonify({"message": "rating must be between 1 and 5"}), 400

    booking_id = d.get("bookingId") or d.get("booking_id")
    customer_id = d.get("customerId") or d.get("customer_id")
    technician_id = d.get("technicianId") or d.get("technician_id")

    def _parse_optional_int(raw, name: str):
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return None, None
        try:
            return int(str(raw).strip()), None
        except (TypeError, ValueError):
            return None, f"{name} must be an integer"

    booking_id, err = _parse_optional_int(booking_id, "bookingId")
    if err:
        return jsonify({"message": err}), 400
    customer_id, err = _parse_optional_int(customer_id, "customerId")
    if err:
        return jsonify({"message": err}), 400
    technician_id, err = _parse_optional_int(technician_id, "technicianId")
    if err:
        return jsonify({"message": err}), 400

    if booking_id is not None and not _one("SELECT 1 AS ok FROM bookings WHERE booking_id = :id", {"id": booking_id}):
        return jsonify({"message": "bookingId does not match an existing booking"}), 404
    if customer_id is not None and not _one("SELECT 1 AS ok FROM users WHERE user_id = :id", {"id": customer_id}):
        return jsonify({"message": "customerId does not match an existing user"}), 404
    if technician_id is not None and not _one("SELECT 1 AS ok FROM technician_profiles WHERE technician_id = :id", {"id": technician_id}):
        return jsonify({"message": "technicianId does not match an existing technician"}), 404

    try:
        row = _one(
            """
            INSERT INTO reviews (booking_id, customer_id, technician_id, rating, title, review_text, is_active, created_at, updated_at)
            VALUES (:booking_id, :customer_id, :technician_id, :rating, :title, :review_text, :is_active, NOW(), NOW())
            RETURNING review_id, booking_id, customer_id, technician_id, rating, title, review_text, is_active, created_at, updated_at
            """,
            {
                "booking_id": booking_id,
                "customer_id": customer_id,
                "technician_id": technician_id,
                "rating": rating,
                "title": d.get("title"),
                "review_text": d.get("review") or d.get("reviewText"),
                "is_active": False if d.get("status") == "inactive" else True,
            },
        )
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Invalid review references (booking/customer/technician)"}), 400
    db.session.commit()
    return jsonify({"id": str(row["review_id"]), "message": "Review created"}), 201


@rest_bp.put("/reviews/<int:review_id>")
def update_review(review_id: int):
    d = request.get_json(silent=True) or {}
    if not _one("SELECT 1 AS ok FROM reviews WHERE review_id = :id", {"id": review_id}):
        return jsonify({"message": "Review not found"}), 404

    sets: list[str] = []
    params: dict = {"id": review_id}

    if "bookingId" in d or "booking_id" in d:
        raw = d.get("bookingId", d.get("booking_id"))
        if raw is None or (isinstance(raw, str) and not str(raw).strip()):
            sets.append("booking_id = NULL")
        else:
            try:
                bid = int(str(raw).strip())
            except (TypeError, ValueError):
                return jsonify({"message": "bookingId must be an integer"}), 400
            if not _one("SELECT 1 AS ok FROM bookings WHERE booking_id = :id", {"id": bid}):
                return jsonify({"message": "bookingId does not match an existing booking"}), 404
            sets.append("booking_id = :rv_bid")
            params["rv_bid"] = bid
    if "customerId" in d or "customer_id" in d:
        raw = d.get("customerId", d.get("customer_id"))
        if raw is None or (isinstance(raw, str) and not str(raw).strip()):
            sets.append("customer_id = NULL")
        else:
            try:
                cid = int(str(raw).strip())
            except (TypeError, ValueError):
                return jsonify({"message": "customerId must be an integer"}), 400
            if not _one("SELECT 1 AS ok FROM users WHERE user_id = :id", {"id": cid}):
                return jsonify({"message": "customerId does not match an existing user"}), 404
            sets.append("customer_id = :rv_cid")
            params["rv_cid"] = cid
    if "technicianId" in d or "technician_id" in d:
        raw = d.get("technicianId", d.get("technician_id"))
        if raw is None or (isinstance(raw, str) and not str(raw).strip()):
            sets.append("technician_id = NULL")
        else:
            try:
                tid = int(str(raw).strip())
            except (TypeError, ValueError):
                return jsonify({"message": "technicianId must be an integer"}), 400
            if not _one("SELECT 1 AS ok FROM technician_profiles WHERE technician_id = :id", {"id": tid}):
                return jsonify({"message": "technicianId does not match an existing technician"}), 404
            sets.append("technician_id = :rv_tid")
            params["rv_tid"] = tid
    if "rating" in d:
        try:
            rating = int(d["rating"])
        except (TypeError, ValueError):
            return jsonify({"message": "rating must be an integer"}), 400
        if rating < 1 or rating > 5:
            return jsonify({"message": "rating must be between 1 and 5"}), 400
        sets.append("rating = :rv_rating")
        params["rv_rating"] = rating
    if "title" in d:
        sets.append("title = :rv_title")
        params["rv_title"] = d.get("title")
    if "review" in d or "reviewText" in d:
        sets.append("review_text = :rv_text")
        params["rv_text"] = d.get("review", d.get("reviewText"))
    if "status" in d:
        sets.append("is_active = :rv_active")
        params["rv_active"] = False if d.get("status") == "inactive" else True

    if sets:
        sets.append("updated_at = NOW()")
        _exec(f"UPDATE reviews SET {', '.join(sets)} WHERE review_id = :id", params)
    db.session.commit()
    return get_review(review_id)


@rest_bp.delete("/reviews/<int:review_id>")
def delete_review(review_id: int):
    _q("DELETE FROM reviews WHERE review_id = :id", {"id": review_id})
    db.session.commit()
    return "", 204


@rest_bp.get("/settings/roles")
def settings_roles():
    return jsonify(
        [
            {"id": "role-1", "role": "super_admin", "label": "Super Admin", "description": "Full access", "permissions": []},
            {"id": "role-2", "role": "zip_manager", "label": "ZIP Manager", "description": "Zone operations", "permissions": []},
            {"id": "role-3", "role": "finance_admin", "label": "Finance Admin", "description": "Payments and payouts", "permissions": []},
            {"id": "role-4", "role": "support_executive", "label": "Support Executive", "description": "Customer support", "permissions": []},
            {"id": "role-5", "role": "technician_supervisor", "label": "Technician Supervisor", "description": "Technician oversight", "permissions": []},
        ]
    )


_REST_DIR = os.path.dirname(os.path.abspath(__file__))
_OPENAPI_PATH = os.path.join(_REST_DIR, "openapi.yaml")

_SWAGGER_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Zepnest REST API — Swagger UI</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css" crossorigin="anonymous" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js" crossorigin="anonymous"></script>
  <script>
    window.onload = function () {
      SwaggerUIBundle({
        url: "/api/openapi.yaml",
        dom_id: "#swagger-ui",
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis],
      });
    };
  </script>
</body>
</html>"""


@rest_bp.get("/docs")
def swagger_ui():
    """Interactive OpenAPI (Swagger UI) for this REST blueprint."""
    return Response(_SWAGGER_UI_HTML, mimetype="text/html; charset=utf-8")


@rest_bp.get("/openapi.yaml")
def serve_openapi_yaml():
    """OpenAPI 3.0 document (YAML) for `/api/*` routes."""
    return send_file(_OPENAPI_PATH, mimetype="application/yaml", max_age=3600)
