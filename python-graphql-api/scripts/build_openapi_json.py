#!/usr/bin/env python3
"""
Merge `api/rest/openapi.yaml` (web /api) with Mobile (/mobile) paths and write `openapi.json`.

Usage (from project root):
  python scripts/build_openapi_json.py

Requires: PyYAML (see requirements.txt)
"""

from __future__ import annotations

import json
import os
import sys

try:
    import yaml
except ImportError:
    print("Install PyYAML: pip install PyYAML", file=sys.stderr)
    sys.exit(1)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB_OPENAPI = os.path.join(ROOT, "api", "rest", "openapi.yaml")
OUT_JSON = os.path.join(ROOT, "openapi.json")

MOBILE_PATHS = {
    "/mobile/auth/request-otp": {
        "post": {
            "tags": ["Mobile — Auth"],
            "summary": "Request OTP (SMS via 2Factor when configured)",
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["phone"],
                            "properties": {
                                "phone": {
                                    "type": "string",
                                    "description": "Indian mobile; 10 digits or with country code",
                                    "example": "9876543210",
                                }
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "OTP generated or sent",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/MobileRequestOtpResponse"}
                        }
                    },
                },
                "400": {"$ref": "#/components/responses/BadRequest"},
                "502": {"description": "SMS provider failure"},
            },
        }
    },
    "/mobile/auth/verify-otp": {
        "post": {
            "tags": ["Mobile — Auth"],
            "summary": "Verify OTP and issue JWT",
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["phone", "otp"],
                            "properties": {
                                "phone": {"type": "string"},
                                "otp": {"type": "string", "example": "123456"},
                                "firstName": {"type": "string"},
                                "lastName": {"type": "string"},
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Returns accessToken (Bearer)",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/MobileVerifyOtpResponse"}
                        }
                    },
                },
                "400": {"$ref": "#/components/responses/BadRequest"},
                "401": {"description": "Invalid OTP"},
            },
        }
    },
    "/mobile/home": {
        "get": {
            "tags": ["Mobile — Home"],
            "summary": "Home categories with services (and subCategories when available)",
            "responses": {"200": {"description": "OK"}},
        }
    },
    "/mobile/catalog/subcategories": {
        "get": {
            "tags": ["Mobile — Catalog"],
            "summary": "Subcategories for a category",
            "parameters": [
                {
                    "name": "categoryId",
                    "in": "query",
                    "required": True,
                    "schema": {"type": "integer"},
                }
            ],
            "responses": {"200": {"description": "OK"}},
        }
    },
    "/mobile/cart": {
        "get": {
            "tags": ["Mobile — Cart"],
            "summary": "List cart lines for the logged-in customer",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {"description": "items, itemCount, subtotal"},
                "501": {"description": "cart_items table missing"},
            },
        },
        "delete": {
            "tags": ["Mobile — Cart"],
            "summary": "Clear all cart lines",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {"description": "OK"},
                "501": {"description": "cart_items table missing"},
            },
        },
    },
    "/mobile/cart/items": {
        "post": {
            "tags": ["Mobile — Cart"],
            "summary": "Add or upsert a cart line (one row per service per user)",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["serviceId"],
                            "properties": {
                                "serviceId": {"type": "integer"},
                                "quantity": {"type": "integer"},
                                "notes": {"type": "string"},
                                "voiceNoteUrl": {"type": "string"},
                                "videoUrl": {"type": "string"},
                                "imageUrl": {"type": "string"},
                            },
                        }
                    }
                }
            },
            "responses": {
                "200": {"description": "OK"},
                "400": {"$ref": "#/components/responses/BadRequest"},
                "501": {"description": "cart_items table missing"},
            },
        },
    },
    "/mobile/cart/items/{cart_item_id}": {
        "parameters": [
            {
                "name": "cart_item_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
            }
        ],
        "put": {
            "tags": ["Mobile — Cart"],
            "summary": "Update a cart line (quantity and/or notes/media)",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {"description": "OK"},
                "404": {"$ref": "#/components/responses/NotFound"},
                "501": {"description": "cart_items table missing"},
            },
        },
        "delete": {
            "tags": ["Mobile — Cart"],
            "summary": "Remove one cart line",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {"description": "OK"},
                "404": {"$ref": "#/components/responses/NotFound"},
                "501": {"description": "cart_items table missing"},
            },
        },
    },
    "/mobile/bookings": {
        "get": {
            "tags": ["Mobile — Bookings"],
            "summary": "List current customer's bookings",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20}},
            ],
            "responses": {"200": {"description": "OK"}},
        },
        "post": {
            "tags": ["Mobile — Bookings"],
            "summary": "Create booking (multi-service + optional media URLs). Set fromCart true to use persisted cart lines.",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/MobileBookingCreate"}
                    }
                }
            },
            "responses": {
                "201": {"description": "Created"},
                "400": {"$ref": "#/components/responses/BadRequest"},
                "501": {"description": "cart_items table missing when fromCart is true"},
            },
        },
    },
    "/mobile/bookings/{booking_id}": {
        "parameters": [
            {
                "name": "booking_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
            }
        ],
        "get": {
            "tags": ["Mobile — Bookings"],
            "summary": "Get booking by id",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {"description": "OK"},
                "404": {"$ref": "#/components/responses/NotFound"},
            },
        },
    },
    "/mobile/profile": {
        "get": {
            "tags": ["Mobile — Profile"],
            "summary": "Customer profile + addresses",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "OK"}},
        },
        "patch": {
            "tags": ["Mobile — Profile"],
            "summary": "Update profile fields",
            "description": "You can pass `address` (or `defaultAddress`) object to upsert the user's default address in the common `addresses` table.",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "firstName": {"type": "string"},
                                "lastName": {"type": "string"},
                                "email": {"type": "string"},
                                "address": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "line1": {"type": "string"},
                                        "line2": {"type": "string"},
                                        "city": {"type": "string"},
                                        "state": {"type": "string"},
                                        "zipCode": {"type": "string"},
                                        "country": {"type": "string"},
                                        "addressType": {"type": "string"},
                                    },
                                },
                                "defaultAddress": {"type": "object"},
                            },
                        }
                    }
                }
            },
            "responses": {"200": {"description": "OK"}},
        },
    },
    "/mobile/addresses": {
        "get": {
            "tags": ["Mobile — Addresses"],
            "summary": "List saved addresses",
            "description": "Response includes `addresses` (array) and legacy `data` (same array).",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "OK"}},
        },
        "post": {
            "tags": ["Mobile — Addresses"],
            "summary": "Create one or more addresses",
            "description": "Send a single address object, or `{ \"addresses\": [ {...}, ... ] }` to create many at once.",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "addresses": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                    "description": "When set, batch create; each item is a full address payload (line1 required).",
                                },
                                "label": {"type": "string"},
                                "line1": {"type": "string"},
                                "line2": {"type": "string"},
                                "city": {"type": "string"},
                                "state": {"type": "string"},
                                "zipCode": {"type": "string"},
                                "country": {"type": "string"},
                                "addressType": {"type": "string"},
                                "isDefault": {"type": "boolean"},
                            },
                        }
                    }
                }
            },
            "responses": {"201": {"description": "Created (single object or { addresses: [...] })"}},
        },
        "put": {
            "tags": ["Mobile — Addresses"],
            "summary": "Batch update addresses",
            "description": "Body `{ \"addresses\": [ { \"id\": <int>, ...fields }, ... ] }`. Each item must include `id`.",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["addresses"],
                            "properties": {
                                "addresses": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                }
                            },
                        }
                    }
                }
            },
            "responses": {"200": {"description": "OK"}},
        },
    },
    "/mobile/addresses/{address_id}": {
        "parameters": [
            {
                "name": "address_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
            }
        ],
        "put": {
            "tags": ["Mobile — Addresses"],
            "summary": "Update address",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "OK"}},
        },
        "delete": {
            "tags": ["Mobile — Addresses"],
            "summary": "Delete address",
            "security": [{"bearerAuth": []}],
            "responses": {"204": {"description": "No content"}},
        },
    },
    "/mobile/uploads/presign": {
        "post": {
            "tags": ["Mobile — Uploads"],
            "summary": "Presigned S3 PUT for voice/video (then use fileUrl in booking)",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["kind"],
                            "properties": {
                                "kind": {"type": "string", "enum": ["voice", "video"]},
                                "fileExtension": {"type": "string"},
                                "contentType": {"type": "string"},
                            },
                        }
                    }
                }
            },
            "responses": {
                "200": {"description": "uploadUrl, fileUrl, etc."},
                "400": {"$ref": "#/components/responses/BadRequest"},
                "503": {"description": "S3 not configured"},
            },
        }
    },
}


def main() -> None:
    with open(WEB_OPENAPI, encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    doc.setdefault("info", {})["title"] = "Zepnest API (Web + Mobile)"
    desc = doc["info"].get("description") or ""
    doc["info"]["description"] = (
        desc
        + "\n\n**Mobile** routes are under `/mobile` (JWT Bearer after verify-otp). "
        "GraphQL at `/graphql` is not included."
    )

    tags = doc.setdefault("tags", [])
    extra_tags = [
        {"name": "Mobile — Auth"},
        {"name": "Mobile — Home"},
        {"name": "Mobile — Catalog"},
        {"name": "Mobile — Cart"},
        {"name": "Mobile — Bookings"},
        {"name": "Mobile — Profile"},
        {"name": "Mobile — Addresses"},
        {"name": "Mobile — Uploads"},
    ]
    existing = {t["name"] for t in tags if isinstance(t, dict) and "name" in t}
    for t in extra_tags:
        if t["name"] not in existing:
            tags.append(t)

    paths = doc.setdefault("paths", {})
    for path, item in MOBILE_PATHS.items():
        if path in paths:
            raise SystemExit(f"Path collision: {path}")
        paths[path] = item

    comp = doc.setdefault("components", {})
    comp.setdefault("securitySchemes", {})["bearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": (
            "JWT in `Authorization: Bearer <token>`. **Mobile:** `accessToken` from "
            "`POST /mobile/auth/verify-otp` (`typ: mobile_customer`). **Web:** `accessToken` from "
            "`POST /api/auth/login` or `/api/auth/register` (`typ: web_user`)."
        ),
    }
    schemas = comp.setdefault("schemas", {})
    schemas["MobileRequestOtpResponse"] = {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "expiresInSeconds": {"type": "integer"},
            "phone": {"type": "string"},
            "smsSent": {"type": "boolean"},
            "smsSkipReason": {"type": "string"},
            "debugOtp": {"type": "string", "description": "Only if MOBILE_OTP_DEBUG=true"},
        },
    }
    schemas["MobileVerifyOtpResponse"] = {
        "type": "object",
        "properties": {
            "accessToken": {"type": "string"},
            "tokenType": {"type": "string", "example": "Bearer"},
            "expiresInSeconds": {"type": "integer"},
            "user": {"type": "object"},
        },
    }
    schemas["MobileBookingCreate"] = {
        "type": "object",
        "required": ["serviceAddress"],
        "properties": {
            "serviceAddress": {"type": "string"},
            "address": {"type": "string"},
            "fromCart": {
                "type": "boolean",
                "description": "If true, line items come from POST /mobile/cart/items; serviceId(s) not required",
            },
            "useCart": {"type": "boolean", "description": "Alias of fromCart"},
            "from_cart": {"type": "boolean", "description": "Alias of fromCart"},
            "serviceId": {"type": "integer"},
            "serviceIds": {"type": "array", "items": {"type": "integer"}},
            "description": {"type": "string"},
            "voiceNoteUrl": {"type": "string"},
            "videoUrl": {"type": "string"},
            "imageUrl": {"type": "string"},
            "customerNotes": {"type": "string"},
        },
    }

    with open(OUT_JSON, "w", encoding="utf-8") as out:
        json.dump(doc, out, indent=2, ensure_ascii=False)

    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
