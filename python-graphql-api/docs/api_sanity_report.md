# API sanity report (GET probe)

See also **`API_STATUS_CODES.md`** (typical codes per area).

Same data as **`GET /health/apis`** or **`GET /?full=1`** on the running server.

Safe probe: **GET only**, rollback after each request. Mutating routes are listed but not called.

## GET responses

| Method | Path | HTTP status | Endpoint |
|--------|------|---------------|----------|
| GET | `/` | 200 | `graphql.health_check` |
| GET | `/api/assets` | 200 | `rest_api.list_assets` |
| GET | `/api/assets/1` | 404 | `rest_api.get_asset` |
| GET | `/api/auth/me` | 401 | `web_auth.me` |
| GET | `/api/catalog/subcategories` | 400 | `rest_api.catalog_subcategories` |
| GET | `/api/customers` | 200 | `rest_api.list_customers` |
| GET | `/api/customers/1` | 404 | `rest_api.get_customer` |
| GET | `/api/dashboard/stats` | 500 | `rest_api.dashboard_stats` |
| GET | `/api/docs` | 200 | `rest_api.swagger_ui` |
| GET | `/api/enumerations/service-categories` | 200 | `rest_api.enum_service_categories` |
| GET | `/api/enumerations/specializations` | 200 | `rest_api.enum_specializations` |
| GET | `/api/enumerations/time-slots` | 200 | `rest_api.enum_time_slots` |
| GET | `/api/enumerations/zip-codes` | 200 | `rest_api.enum_zip_codes` |
| GET | `/api/openapi.yaml` | 200 | `rest_api.serve_openapi_yaml` |
| GET | `/api/orders` | 200 | `rest_api.list_orders` |
| GET | `/api/orders/1` | 404 | `rest_api.get_order` |
| GET | `/api/payments` | 200 | `rest_api.payments` |
| GET | `/api/payments/1` | 404 | `rest_api.payment_by_id` |
| GET | `/api/payments/payouts` | 200 | `rest_api.payouts` |
| GET | `/api/payments/refunds` | 200 | `rest_api.refunds` |
| GET | `/api/reviews` | 200 | `rest_api.list_reviews` |
| GET | `/api/reviews/1` | 404 | `rest_api.get_review` |
| GET | `/api/services` | 200 | `rest_api.list_services` |
| GET | `/api/services/1` | 200 | `rest_api.get_service` |
| GET | `/api/services/addons` | 200 | `rest_api.service_addons` |
| GET | `/api/services/categories` | 200 | `rest_api.service_categories` |
| GET | `/api/services/packages` | 200 | `rest_api.service_packages` |
| GET | `/api/services/warranties` | 200 | `rest_api.service_warranties` |
| GET | `/api/settings/roles` | 200 | `rest_api.settings_roles` |
| GET | `/api/subscriptions/amc` | 200 | `rest_api.amc_plans` |
| GET | `/api/subscriptions/plans` | 200 | `rest_api.subscription_plans` |
| GET | `/api/subscriptions/user` | 200 | `rest_api.user_subscriptions` |
| GET | `/api/subscriptions/user-amc` | 200 | `rest_api.user_amc` |
| GET | `/api/technicians` | 200 | `rest_api.list_technicians` |
| GET | `/api/technicians/1` | 200 | `rest_api.get_technician` |
| GET | `/graphql` | 200 | `graphql.graphql_view` |
| GET | `/health/apis` | 200 | `graphql.health_apis` |
| GET | `/mobile/addresses` | 401 | `mobile_api.list_addresses` |
| GET | `/mobile/bookings` | 401 | `mobile_api.list_mobile_bookings` |
| GET | `/mobile/bookings/1` | 401 | `mobile_api.get_mobile_booking` |
| GET | `/mobile/cart` | 401 | `mobile_api.get_cart` |
| GET | `/mobile/catalog/subcategories` | 400 | `mobile_api.mobile_catalog_subcategories` |
| GET | `/mobile/home` | 200 | `mobile_api.mobile_home` |
| GET | `/mobile/profile` | 401 | `mobile_api.get_profile` |
| GET | `/openapi.json` | 200 | `serve_openapi_json` |

## Routes without GET (not probed)

| Method | Path | Endpoint |
|--------|------|----------|
| POST | `/api/addresses` | `rest_api.batch_create_address_rows` |
| PUT | `/api/addresses` | `rest_api.batch_update_address_rows` |
| PUT | `/api/addresses/1` | `rest_api.update_address_row` |
| POST | `/api/assets` | `rest_api.create_asset` |
| DELETE | `/api/assets/1` | `rest_api.delete_asset` |
| PUT | `/api/assets/1` | `rest_api.update_asset` |
| POST | `/api/auth/login` | `web_auth.login` |
| POST | `/api/auth/register` | `web_auth.register` |
| PUT | `/api/catalog/categories/1` | `rest_api.update_category` |
| PUT | `/api/catalog/subcategories/1` | `rest_api.update_sub_category` |
| POST | `/api/customers` | `rest_api.create_customer` |
| DELETE | `/api/customers/1` | `rest_api.delete_customer` |
| PUT | `/api/customers/1` | `rest_api.update_customer` |
| POST | `/api/orders` | `rest_api.create_order` |
| DELETE | `/api/orders/1` | `rest_api.delete_order` |
| PUT | `/api/orders/1` | `rest_api.update_order` |
| POST | `/api/orders/assign/1` | `rest_api.assign_order` |
| POST | `/api/orders/escalate/1` | `rest_api.escalate_order` |
| PUT | `/api/payments/refunds/1` | `rest_api.process_refund` |
| POST | `/api/reviews` | `rest_api.create_review` |
| DELETE | `/api/reviews/1` | `rest_api.delete_review` |
| PUT | `/api/reviews/1` | `rest_api.update_review` |
| POST | `/api/services` | `rest_api.create_service` |
| DELETE | `/api/services/1` | `rest_api.delete_service` |
| PUT | `/api/services/1` | `rest_api.update_service` |
| POST | `/api/subscriptions/plans` | `rest_api.create_subscription_plan` |
| PUT | `/api/subscriptions/plans/1` | `rest_api.update_subscription_plan` |
| POST | `/api/technicians` | `rest_api.create_technician` |
| DELETE | `/api/technicians/1` | `rest_api.delete_technician` |
| PUT | `/api/technicians/1` | `rest_api.update_technician` |
| POST | `/mobile/addresses` | `mobile_api.create_address` |
| PUT | `/mobile/addresses` | `mobile_api.batch_update_addresses` |
| DELETE | `/mobile/addresses/1` | `mobile_api.delete_address` |
| PUT | `/mobile/addresses/1` | `mobile_api.update_address` |
| POST | `/mobile/auth/request-otp` | `mobile_api.request_otp` |
| POST | `/mobile/auth/verify-otp` | `mobile_api.verify_otp` |
| POST | `/mobile/bookings` | `mobile_api.create_mobile_booking` |
| DELETE | `/mobile/cart` | `mobile_api.clear_cart_endpoint` |
| POST | `/mobile/cart/items` | `mobile_api.add_or_update_cart_item` |
| DELETE | `/mobile/cart/items/1` | `mobile_api.delete_cart_item` |
| PUT | `/mobile/cart/items/1` | `mobile_api.update_cart_item` |
| PATCH | `/mobile/profile` | `mobile_api.patch_profile` |
| POST | `/mobile/uploads/presign` | `mobile_api.presign_s3_upload` |
