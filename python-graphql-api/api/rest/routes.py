from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from api import db


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
    return {"data": data, "items": data, "total": total, "page": page, "limit": limit, "totalPages": total_pages}


def _q(sql: str, params=None):
    return db.session.execute(text(sql), params or {}).mappings().all()


def _one(sql: str, params=None):
    return db.session.execute(text(sql), params or {}).mappings().first()


@rest_bp.get("/customers")
def list_customers():
    page = _int_param("page", 1)
    limit = _int_param("limit", 10)
    search = request.args.get("search", "").strip()
    status = request.args.get("status")
    customer_user_type = request.args.get("customerUserType")
    rows = _q(
        """
        SELECT user_id, first_name, last_name, email, phone, user_type, loyalty_points, is_active, created_at, updated_at
        FROM users
        WHERE user_type = 'customer'
          AND (:status IS NULL OR (:status='active' AND is_active=true) OR (:status='inactive' AND is_active=false))
          AND (:customer_user_type IS NULL OR user_type = :customer_user_type)
          AND (:search = '' OR LOWER(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')) LIKE LOWER(:like_search)
               OR LOWER(COALESCE(email,'')) LIKE LOWER(:like_search) OR COALESCE(phone,'') LIKE :like_search)
        ORDER BY user_id DESC
        """,
        {"status": status, "customer_user_type": customer_user_type, "search": search, "like_search": f"%{search}%"},
    )
    mapped = [
        {
            "id": str(r["user_id"]),
            "firstName": r["first_name"] or "",
            "lastName": r["last_name"] or "",
            "email": r["email"],
            "phone": r["phone"] or "",
            "addresses": [],
            "status": "active" if r["is_active"] else "inactive",
            "tags": [],
            "customerUserType": "subscription",
            "internalNotes": "",
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
        SELECT user_id, first_name, last_name, email, phone, is_active, created_at, updated_at
        FROM users WHERE user_id=:id AND user_type='customer'
        """,
        {"id": customer_id},
    )
    if not r:
        return jsonify({"message": "Customer not found"}), 404
    return jsonify(
        {
            "id": str(r["user_id"]),
            "firstName": r["first_name"] or "",
            "lastName": r["last_name"] or "",
            "email": r["email"],
            "phone": r["phone"] or "",
            "addresses": [],
            "status": "active" if r["is_active"] else "inactive",
            "tags": [],
            "customerUserType": "subscription",
            "internalNotes": "",
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
    row = _one(
        """
        INSERT INTO users (email, password_hash, phone, first_name, last_name, user_type, loyalty_points, is_active, created_at, updated_at)
        VALUES (:email, '', :phone, :first_name, :last_name, 'customer', 0, true, NOW(), NOW())
        RETURNING user_id, first_name, last_name, email, phone, is_active, created_at, updated_at
        """,
        {
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "first_name": data.get("firstName", ""),
            "last_name": data.get("lastName", ""),
        },
    )
    db.session.commit()
    return jsonify({"id": str(row["user_id"]), "firstName": row["first_name"], "lastName": row["last_name"], "email": row["email"], "phone": row["phone"], "status": "active"}), 201


@rest_bp.put("/customers/<int:customer_id>")
def update_customer(customer_id: int):
    data = request.get_json(silent=True) or {}
    _q(
        """
        UPDATE users
        SET first_name = COALESCE(:first_name, first_name),
            last_name = COALESCE(:last_name, last_name),
            email = COALESCE(:email, email),
            phone = COALESCE(:phone, phone),
            updated_at = NOW()
        WHERE user_id = :id AND user_type='customer'
        """,
        {"id": customer_id, "first_name": data.get("firstName"), "last_name": data.get("lastName"), "email": data.get("email"), "phone": data.get("phone")},
    )
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
        SELECT tp.technician_id, u.first_name, u.last_name, u.email, u.phone, tp.specialization, tp.status,
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
    _q(
        """
        UPDATE users u
        SET first_name = COALESCE(:first_name, u.first_name),
            last_name = COALESCE(:last_name, u.last_name),
            email = COALESCE(:email, u.email),
            phone = COALESCE(:phone, u.phone),
            updated_at = NOW()
        FROM technician_profiles tp
        WHERE tp.technician_id = :id AND u.user_id = tp.user_id
        """,
        {"id": technician_id, "first_name": d.get("firstName"), "last_name": d.get("lastName"), "email": d.get("email"), "phone": d.get("phone")},
    )
    _q(
        """
        UPDATE technician_profiles
        SET specialization = COALESCE(:specialization, specialization),
            experience_years = COALESCE(:experience, experience_years),
            status = COALESCE(:status, status),
            certification = COALESCE(:certification, certification)
        WHERE technician_id=:id
        """,
        {
            "id": technician_id,
            "specialization": ", ".join(d.get("specialization", [])) if isinstance(d.get("specialization"), list) else d.get("specialization"),
            "experience": d.get("experience"),
            "status": d.get("status"),
            "certification": ", ".join(d.get("certifications", [])) if isinstance(d.get("certifications"), list) else d.get("certifications"),
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
    rows = _q(
        """
        SELECT b.booking_id, b.booking_number, b.status, b.total_amount, b.created_at, b.updated_at, b.technician_id,
               u.first_name, u.last_name, u.phone
        FROM bookings b
        LEFT JOIN users u ON u.user_id = b.customer_id
        WHERE (:status IS NULL OR b.status=:status)
          AND (:search='' OR LOWER(COALESCE(b.booking_number,'')) LIKE LOWER(:like_search)
               OR LOWER(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) LIKE LOWER(:like_search)
               OR COALESCE(u.phone,'') LIKE :like_search)
        ORDER BY b.booking_id DESC
        """,
        {"status": status, "search": search, "like_search": f"%{search}%"},
    )
    mapped = [
        {
            "id": str(r["booking_id"]),
            "orderNo": r["booking_number"],
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
    return jsonify(_paginate(mapped, page, limit))


@rest_bp.get("/orders/<int:order_id>")
def get_order(order_id: int):
    row = _one("SELECT booking_id, booking_number, status, technician_id, total_amount, created_at, updated_at FROM bookings WHERE booking_id=:id", {"id": order_id})
    if not row:
        return jsonify({"message": "Order not found"}), 404
    return jsonify({"id": str(row["booking_id"]), "orderNo": row["booking_number"], "status": row["status"], "technicianId": str(row["technician_id"]) if row["technician_id"] else None, "totalAmount": float(row["total_amount"] or 0), "createdAt": row["created_at"].isoformat() if row["created_at"] else None, "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None})


@rest_bp.post("/orders")
def create_order():
    d = request.get_json(silent=True) or {}
    number = d.get("orderNo") or f"ORD-{int(datetime.utcnow().timestamp())}"
    row = _one(
        """
        INSERT INTO bookings (booking_number, customer_id, technician_id, service_address, status, subtotal, discount_amount,
                              loyalty_points_used, loyalty_discount, total_amount, loyalty_points_earned, is_subscription_booking,
                              customer_notes, created_at, updated_at)
        VALUES (:n,:c,:t,:a,:s,:sub,:dis,:lp,:ld,:tot,:lpe,:isb,:cn,NOW(),NOW())
        RETURNING booking_id, booking_number, status, technician_id, total_amount, created_at, updated_at
        """,
        {"n": number, "c": d.get("customerId"), "t": d.get("technicianId"), "a": d.get("address"), "s": d.get("status", "new"), "sub": d.get("subtotal", 0), "dis": d.get("discountAmount", 0), "lp": d.get("loyaltyPointsUsed", 0), "ld": 0, "tot": d.get("totalAmount", 0), "lpe": d.get("loyaltyPointsEarned", 0), "isb": d.get("isSubscriptionBooking", False), "cn": d.get("customerNotes")},
    )
    db.session.commit()
    return jsonify({"id": str(row["booking_id"]), "orderNo": row["booking_number"], "status": row["status"]}), 201


@rest_bp.put("/orders/<int:order_id>")
def update_order(order_id: int):
    d = request.get_json(silent=True) or {}
    _q("UPDATE bookings SET status=COALESCE(:s,status), technician_id=COALESCE(:t,technician_id), customer_notes=COALESCE(:n,customer_notes), updated_at=NOW() WHERE booking_id=:id", {"id": order_id, "s": d.get("status"), "t": d.get("technicianId"), "n": d.get("customerNotes")})
    db.session.commit()
    return get_order(order_id)


@rest_bp.delete("/orders/<int:order_id>")
def delete_order(order_id: int):
    _q("DELETE FROM bookings WHERE booking_id=:id", {"id": order_id})
    db.session.commit()
    return "", 204


@rest_bp.post("/orders/assign/<int:order_id>")
def assign_order(order_id: int):
    d = request.get_json(silent=True) or {}
    _q("UPDATE bookings SET technician_id=:t, status=CASE WHEN status IN ('new','open') THEN 'assigned' ELSE status END, updated_at=NOW() WHERE booking_id=:id", {"id": order_id, "t": d.get("technicianId")})
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
    rows = _q(
        """
        SELECT service_id, name, description, base_price, estimated_duration_mins, category, image_url, is_active, loyalty_points_earned, created_at, updated_at
        FROM services
        WHERE (:status IS NULL OR (:status='active' AND is_active=true) OR (:status='inactive' AND is_active=false))
          AND (:category IS NULL OR category=:category)
          AND (:search='' OR LOWER(name) LIKE LOWER(:like_search) OR LOWER(COALESCE(description,'')) LIKE LOWER(:like_search))
        ORDER BY service_id DESC
        """,
        {"status": status, "category": category, "search": search, "like_search": f"%{search}%"},
    )
    mapped = [{"id": str(r["service_id"]), "name": r["name"], "description": r["description"] or "", "basePrice": float(r["base_price"] or 0), "estimatedDurationMins": r["estimated_duration_mins"] or 0, "category": r["category"], "categoryId": r["category"], "imageUrl": r["image_url"], "isActive": bool(r["is_active"]), "loyaltyPointsEarned": r["loyalty_points_earned"] or 0, "createdAt": r["created_at"].isoformat() if r["created_at"] else None, "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None} for r in rows]
    return jsonify(_paginate(mapped, page, limit))


@rest_bp.get("/services/<int:service_id>")
def get_service(service_id: int):
    r = _one("SELECT * FROM services WHERE service_id=:id", {"id": service_id})
    if not r:
        return jsonify({"message": "Service not found"}), 404
    return jsonify({"id": str(r["service_id"]), "name": r["name"], "description": r["description"] or "", "basePrice": float(r["base_price"] or 0), "estimatedDurationMins": r["estimated_duration_mins"] or 0, "category": r["category"], "categoryId": r["category"], "isActive": bool(r["is_active"])})


@rest_bp.post("/services")
def create_service():
    d = request.get_json(silent=True) or {}
    row = _one(
        """
        INSERT INTO services (name, description, base_price, estimated_duration_mins, category, image_url, is_active, loyalty_points_earned, created_at, updated_at)
        VALUES (:name,:description,:base_price,:duration,:category,:image_url,:is_active,:points,NOW(),NOW())
        RETURNING service_id, name, description, base_price, estimated_duration_mins, category, is_active, created_at, updated_at
        """,
        {
            "name": d.get("name", ""),
            "description": d.get("description", ""),
            "base_price": d.get("basePrice", 0),
            "duration": d.get("estimatedDurationMins", 60),
            "category": d.get("category") or d.get("categoryId") or "General",
            "image_url": d.get("imageUrl"),
            "is_active": d.get("isActive", True),
            "points": d.get("loyaltyPointsEarned", 0),
        },
    )
    db.session.commit()
    return jsonify({"id": str(row["service_id"]), "name": row["name"], "description": row["description"] or "", "basePrice": float(row["base_price"] or 0), "estimatedDurationMins": row["estimated_duration_mins"] or 0, "category": row["category"], "categoryId": row["category"], "isActive": bool(row["is_active"])}), 201


@rest_bp.put("/services/<int:service_id>")
def update_service(service_id: int):
    d = request.get_json(silent=True) or {}
    _q(
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
        """,
        {
            "id": service_id,
            "name": d.get("name"),
            "description": d.get("description"),
            "base_price": d.get("basePrice"),
            "duration": d.get("estimatedDurationMins"),
            "category": d.get("category") or d.get("categoryId"),
            "image_url": d.get("imageUrl"),
            "is_active": d.get("isActive"),
            "points": d.get("loyaltyPointsEarned"),
        },
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
    rows = _q("SELECT DISTINCT category FROM services WHERE category IS NOT NULL ORDER BY category")
    return jsonify([{"id": r["category"], "name": r["category"], "description": "", "isActive": True, "enabledZipCodes": []} for r in rows])


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
    rows = _q("SELECT DISTINCT category FROM services WHERE category IS NOT NULL ORDER BY category")
    return jsonify([{"value": r["category"], "label": r["category"]} for r in rows])


@rest_bp.get("/enumerations/zip-codes")
def enum_zip_codes():
    rows = _q("SELECT DISTINCT zipcode FROM service_areas WHERE zipcode IS NOT NULL ORDER BY zipcode")
    return jsonify([{"value": r["zipcode"], "label": r["zipcode"]} for r in rows])


@rest_bp.get("/dashboard/stats")
def dashboard_stats():
    c = _one("SELECT COUNT(*) AS c FROM users WHERE user_type='customer'")["c"]
    t = _one("SELECT COUNT(*) AS c FROM technician_profiles")["c"]
    at = _one("SELECT COUNT(*) AS c FROM technician_profiles WHERE status='available'")["c"]
    o = _one("SELECT COUNT(*) AS c FROM bookings")["c"]
    po = _one("SELECT COUNT(*) AS c FROM bookings WHERE status IN ('new','under_review','assigned','in_progress')")["c"]
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
