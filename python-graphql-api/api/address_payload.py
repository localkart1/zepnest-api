"""Normalize address fields from REST/mobile JSON into DB column values."""
from __future__ import annotations


def _opt_str(addr: dict, *keys: str, max_len: int | None = None) -> str | None:
    for k in keys:
        if k not in addr:
            continue
        v = addr.get(k)
        if v is None:
            continue
        s = str(v).strip() if not isinstance(v, str) else v.strip()
        if s:
            return s[:max_len] if max_len else s
    return None


def _opt_float(addr: dict, *keys: str) -> float | None:
    for k in keys:
        if k not in addr:
            continue
        v = addr.get(k)
        if v is None or v == "":
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def normalized_address_extra_columns(addr: dict) -> dict:
    """
    Map request body keys (camelCase or snake_case) to DB columns:
    door_no, building_name, street, area, lat, long, phone_no, name.
    """
    return {
        "door_no": _opt_str(addr, "door_no", "doorNo", max_len=128),
        "building_name": _opt_str(addr, "building_name", "buildingName", max_len=255),
        "street": _opt_str(addr, "street", max_len=255),
        "area": _opt_str(addr, "area", max_len=255),
        "lat": _opt_float(addr, "lat", "latitude"),
        "long": _opt_float(addr, "long", "lng", "longitude"),
        "phone_no": _opt_str(addr, "phone_no", "phoneNo", "phone", max_len=32),
        "name": _opt_str(addr, "name", "fullName", max_len=255),
    }


def apply_address_extra_fields_to_update(d: dict, sets: list[str], params: dict) -> None:
    """For PUT/PATCH: only set columns when the corresponding JSON key is present."""
    if "doorNo" in d or "door_no" in d:
        sets.append("door_no = :door_no")
        params["door_no"] = _opt_str(d, "door_no", "doorNo")
    if "buildingName" in d or "building_name" in d:
        sets.append("building_name = :building_name")
        params["building_name"] = _opt_str(d, "building_name", "buildingName")
    if "street" in d:
        sets.append("street = :street")
        params["street"] = _opt_str(d, "street")
    if "area" in d:
        sets.append("area = :area")
        params["area"] = _opt_str(d, "area")
    if "lat" in d or "latitude" in d:
        sets.append("lat = :lat")
        raw = d["lat"] if "lat" in d else d.get("latitude")
        if raw is None or raw == "":
            params["lat"] = None
        else:
            try:
                params["lat"] = float(raw)
            except (TypeError, ValueError):
                params["lat"] = None
    if "long" in d or "lng" in d or "longitude" in d:
        sets.append("long = :lon")
        raw = d["long"] if "long" in d else (d["lng"] if "lng" in d else d.get("longitude"))
        if raw is None or raw == "":
            params["lon"] = None
        else:
            try:
                params["lon"] = float(raw)
            except (TypeError, ValueError):
                params["lon"] = None
    if "phoneNo" in d or "phone_no" in d or "phone" in d:
        sets.append("phone_no = :phone_no")
        params["phone_no"] = _opt_str(d, "phone_no", "phoneNo", "phone")
    if "name" in d or "fullName" in d:
        sets.append("name = :aname")
        params["aname"] = _opt_str(d, "name", "fullName")


def address_extra_to_api_dict(r: dict) -> dict:
    """CamelCase JSON for address row mapping (from DB column names)."""
    lat_v = r.get("lat")
    long_v = r.get("long")
    return {
        "doorNo": r.get("door_no") or "",
        "buildingName": r.get("building_name") or "",
        "street": r.get("street") or "",
        "area": r.get("area") or "",
        "lat": lat_v if lat_v is not None else None,
        "long": long_v if long_v is not None else None,
        "phoneNo": r.get("phone_no") or "",
        "name": r.get("name") or "",
    }
