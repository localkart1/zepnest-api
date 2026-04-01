# Zepnest API Sample Requests and Responses

Base URL (local): `http://localhost:5002`

## Auth

### POST `/api/auth/register`
Request:
```json
{"email":"testuser@gmail.com","password":"Test@1234","firstName":"Test","lastName":"User"}
```
Response `201`:
```json
{"accessToken":"<jwt>","expiresInHours":24,"user":{"id":101,"email":"testuser@gmail.com","firstName":"Test","lastName":"User","role":"customer","userType":"customer"}}
```

### POST `/api/auth/login`
Request:
```json
{"email":"testuser@gmail.com","password":"Test@1234"}
```
Response `200`:
```json
{"accessToken":"<jwt>","expiresInHours":24,"user":{"id":101,"email":"testuser@gmail.com","firstName":"Test","lastName":"User","role":"customer","userType":"customer"}}
```

### GET `/api/auth/me`
Headers: `Authorization: Bearer <jwt>`
Response `200`:
```json
{"user":{"id":101,"email":"testuser@gmail.com","firstName":"Test","lastName":"User","role":"customer","userType":"customer"}}
```

## Customers

### GET `/api/customers?page=1&limit=10&search=&status=active&sortBy=createdAt&sortOrder=desc`
Response `200`:
```json
{"items":[{"id":"101","firstName":"Test","lastName":"User","email":"testuser@gmail.com","phone":"9876543210","addresses":[{"id":"1","label":"Home","line1":"12 MG Road","city":"Bengaluru","state":"Karnataka","zipCode":"560001","country":"India","isDefault":true}],"status":"active"}],"total":1,"page":1,"limit":10,"totalPages":1}
```

### POST `/api/customers`
Request:
```json
{"email":"new@example.com","phone":"9876500000","firstName":"New","lastName":"Customer"}
```
Response `201`:
```json
{"id":"102","firstName":"New","lastName":"Customer","email":"new@example.com","phone":"9876500000","status":"active"}
```

### GET `/api/customers/{customer_id}`
Response `200`:
```json
{"id":"101","firstName":"Test","lastName":"User","email":"testuser@gmail.com","phone":"9876543210","addresses":[{"id":"1","label":"Home","line1":"12 MG Road","city":"Bengaluru","state":"Karnataka","zipCode":"560001","country":"India","isDefault":true}],"status":"active"}
```

### PUT `/api/customers/{customer_id}`
Request:
```json
{"firstName":"Updated","phone":"9876543211"}
```
Response `200`: same shape as `GET /api/customers/{customer_id}`

### DELETE `/api/customers/{customer_id}`
Response `204` (no body)

## Technicians

### GET `/api/technicians?page=1&limit=10&search=&status=available`
Response `200`:
```json
{"data":[{"id":"11","firstName":"Tech","lastName":"One","email":"tech@example.com","phone":"9000000001","specialization":["AC Repair"],"experience":5,"status":"available","addresses":[{"id":"3","label":"Work","line1":"Service Hub","city":"Bengaluru","isDefault":true}]}],"items":[{"id":"11"}],"total":1,"page":1,"limit":10,"totalPages":1}
```

### POST `/api/technicians`
Request:
```json
{"firstName":"Tech","lastName":"Two","email":"tech2@example.com","phone":"9000000002","specialization":["Electrical"],"experience":4,"status":"available"}
```
Response `201`:
```json
{"id":"12","firstName":"Tech","lastName":"Two","email":"tech2@example.com","phone":"9000000002","status":"available"}
```

### GET `/api/technicians/{technician_id}`
Response `200`:
```json
{"id":"11","firstName":"Tech","lastName":"One","email":"tech@example.com","phone":"9000000001","specialization":["AC Repair"],"experience":5,"status":"available"}
```

### PUT `/api/technicians/{technician_id}`
Request:
```json
{"status":"busy","experience":6}
```
Response `200`: same shape as `GET /api/technicians/{technician_id}`

### DELETE `/api/technicians/{technician_id}`
Response `204`

## Assets

### GET `/api/assets?page=1&limit=10`
Response `200`: paginated derived asset records.

### GET `/api/assets/{asset_id}`
Response `200`: single derived asset record.

### POST/PUT/DELETE `/api/assets...`
Response `501` in current schema mode.

## Orders

### GET `/api/orders?page=1&limit=10&status=pending&customerId=101`
Response `200`:
```json
{"data":[{"id":"5001","orderNo":"ORD-5001","customerId":"101","customerName":"Test User","status":"pending","totalAmount":1200,"bookingItems":[{"id":"1","serviceId":1,"serviceName":"AC Service","quantity":1,"unitPrice":1200,"totalPrice":1200}]}],"items":[{"id":"5001"}],"total":1,"page":1,"limit":10,"totalPages":1}
```

### POST `/api/orders`
Request:
```json
{"customerId":101,"address":"12 MG Road","status":"pending","bookingItems":[{"serviceId":1,"quantity":1,"voiceUrl":"https://cdn/app/voice-1.m4a","videoUrl":"https://cdn/app/video-1.mp4","imageUrl":"https://cdn/app/img-1.jpg","notes":"customer prefers morning slot"},{"serviceId":2,"quantity":2,"unitPrice":300}]}
```
Response `201`:
```json
{"message":"Customer request has been booked successfully","id":"5001","orderNo":"ORD-5001","status":"pending"}
```

### GET `/api/orders/{order_id}`
Response `200`:
```json
{"id":"5001","orderNo":"ORD-5001","customerId":"101","status":"pending","technicianId":null,"totalAmount":1800,"bookingItems":[{"id":"1","serviceId":1,"serviceName":"AC Service","quantity":1,"unitPrice":1200,"totalPrice":1200,"notes":"customer prefers morning slot"},{"id":"2","serviceId":2,"serviceName":"Gas Refill","quantity":2,"unitPrice":300,"totalPrice":600,"notes":""}]}
```

### PUT `/api/orders/{order_id}`
Request:
```json
{"status":"in_progress","technicianId":11,"customerNotes":"On the way"}
```
Response `200`: same shape as `GET /api/orders/{order_id}`

### DELETE `/api/orders/{order_id}`
Response `204`

### POST `/api/orders/assign/{order_id}`
Request:
```json
{"technicianId":11}
```
Response `200`: updated order object.

### POST `/api/orders/escalate/{order_id}`
Request:
```json
{"reason":"SLA breached"}
```
Response `200`: updated order object (`status: escalated`).

## Services and Catalog

### GET `/api/services?page=1&limit=10&search=ac&status=active`
Response `200`: paginated services list.

### POST `/api/services`
Request:
```json
{"name":"New Service","description":"Desc","basePrice":499,"estimatedDurationMins":45,"categoryId":1,"isActive":true}
```
Response `201`: created service object.

### GET `/api/services/{service_id}` / PUT / DELETE
- `GET` returns service
- `PUT` request example: `{"name":"Updated","basePrice":599}`
- `DELETE` returns `204`

### GET `/api/services/categories`
Response `200`: list of categories with subcategories.

### GET `/api/catalog/subcategories?categoryId=1`
Response `200`: list of subcategories.

### GET `/api/services/addons?serviceId=1`
Response `200`: list of add-ons.

### GET `/api/services/warranties?serviceId=1`
Response `200`: list of warranties.

### GET `/api/services/packages`
Response `200`: list of service packages.

## Subscriptions

### GET `/api/subscriptions/plans`
Response `200`: list of plans.

### POST `/api/subscriptions/plans`
Request:
```json
{"name":"Gold Plan","billingCycle":"monthly","price":999,"discountPercentage":10,"benefits":"Priority support"}
```
Response `201`: created plan object.

### PUT `/api/subscriptions/plans/{plan_id}`
Request:
```json
{"price":1099,"isActive":true}
```
Response `200`: updated plan.

### GET `/api/subscriptions/user?userId=101`
Response `200`: list of user subscriptions.

### GET `/api/subscriptions/amc`
Response `200`: list of AMC plans.

### GET `/api/subscriptions/user-amc?userId=101`
Response `200`: list of user AMC subscriptions.

## Enumerations and Dashboard

### GET `/api/enumerations/specializations`
Response `200`: list of specialization strings.

### GET `/api/enumerations/service-categories`
Response `200`: list of service categories.

### GET `/api/enumerations/zip-codes`
Response `200`: list of zip codes.

### GET `/api/enumerations/time-slots`
Response `200`:
```json
[{"id":"1","timeSlot":"07:30 - 08:00","active":"Y"},{"id":"2","timeSlot":"08:00 - 08:30","active":"Y"}]
```

### GET `/api/dashboard/stats`
Response `200`:
```json
{"totalCustomers":120,"activeTechnicians":30,"openOrders":14,"revenue":250000}
```

## Payments

### GET `/api/payments?page=1&limit=10&status=paid`
Response `200`: paginated payments.

### GET `/api/payments/{payment_id}`
Response `200`: payment detail.

### GET `/api/payments/payouts`
Response `200`: payouts list.

### GET `/api/payments/refunds`
Response `200`: refunds list.

### PUT `/api/payments/refunds/{refund_id}`
Request:
```json
{"status":"approved","processedBy":"finance_admin"}
```
Response `200`:
```json
{"id":"ref-10","status":"approved","processedBy":"finance_admin","message":"Refund status updated"}
```

## Reviews

### GET `/api/reviews?page=1&limit=10&status=active&bookingId=5001`
Response `200`: paginated reviews list.

### POST `/api/reviews`
Request:
```json
{"bookingId":5001,"customerId":101,"technicianId":11,"rating":5,"title":"Great service","review":"Very professional and on time","status":"active"}
```
Response `201`:
```json
{"id":"1","message":"Review created"}
```

### GET `/api/reviews/{review_id}`
Response `200`:
```json
{"id":"1","bookingId":"5001","customerId":"101","technicianId":"11","rating":5,"title":"Great service","review":"Very professional and on time","status":"active","createdAt":"2026-04-01T10:00:00","updatedAt":"2026-04-01T10:00:00"}
```

### PUT `/api/reviews/{review_id}`
Request:
```json
{"rating":4,"review":"Good service","status":"active"}
```
Response `200`: same shape as `GET /api/reviews/{review_id}`.

### DELETE `/api/reviews/{review_id}`
Response `204`

## Settings

### GET `/api/settings/roles`
Response `200`: static roles list.

## Mobile Auth and Home

### POST `/mobile/auth/request-otp`
Request:
```json
{"phone":"9876543210"}
```
Response `200`:
```json
{"message":"OTP sent","expiresInSeconds":300,"phone":"9876543210","smsSent":true}
```

### POST `/mobile/auth/verify-otp`
Request:
```json
{"phone":"9876543210","otp":"123456","firstName":"Test","lastName":"User"}
```
Response `200`:
```json
{"accessToken":"<mobile-jwt>","tokenType":"Bearer","expiresInSeconds":604800,"user":{"id":"101","firstName":"Test","lastName":"User","phone":"9876543210"}}
```

### GET `/mobile/home`
Headers: `Authorization: Bearer <mobile-jwt>`
Response `200`: categories with services.

### GET `/mobile/catalog/subcategories?categoryId=1`
Response `200`: subcategory list.

## Mobile Bookings

### POST `/mobile/bookings`
Headers: `Authorization: Bearer <mobile-jwt>`
Request:
```json
{"serviceAddress":"12 MG Road","serviceIds":[1,2],"description":"Need quick service","voiceNoteUrl":"https://.../voice.m4a","videoUrl":"https://.../video.mp4","imageUrl":"https://.../image.jpg"}
```
Response `201`:
```json
{"id":"7001","bookingNumber":"MB-...","status":"pending","serviceAddress":"12 MG Road","totalAmount":1500,"services":[{"id":"1","serviceId":1,"name":"AC Service","quantity":1,"unitPrice":1200,"totalPrice":1200},{"id":"2","serviceId":2,"name":"Gas Refill","quantity":1,"unitPrice":300,"totalPrice":300}]}
```

### GET `/mobile/bookings?page=1&limit=20`
Response `200`: paginated booking list.

### GET `/mobile/bookings/{booking_id}`
Response `200`: single booking detail.

## Mobile Profile and Addresses

### GET `/mobile/profile`
Response `200`:
```json
{"user":{"id":"101","firstName":"Test","lastName":"User","email":"testuser@gmail.com","phone":"9876543210"},"addresses":[{"id":1,"label":"Home","line1":"12 MG Road","city":"Bengaluru","zipCode":"560001","isDefault":true}],"defaultAddress":{"id":1}}
```

### PATCH `/mobile/profile`
Request:
```json
{"firstName":"Updated","email":"updated@example.com","address":{"label":"Home","line1":"12 MG Road","city":"Bengaluru","state":"Karnataka","zipCode":"560001","country":"India","addressType":"home"}}
```
Response `200`: same shape as `GET /mobile/profile` (address upserted).

### GET `/mobile/addresses`
Response `200`:
```json
{"data":[{"id":1,"label":"Home","line1":"12 MG Road","line2":"","city":"Bengaluru","state":"Karnataka","zipCode":"560001","country":"India","isDefault":true}]}
```

### POST `/mobile/addresses`
Request:
```json
{"label":"Work","line1":"Manyata Tech Park","city":"Bengaluru","state":"Karnataka","zipCode":"560045","country":"India","addressType":"work","isDefault":false}
```
Response `201`: created address object.

### PUT `/mobile/addresses/{address_id}`
Request:
```json
{"line2":"Tower A","isDefault":true}
```
Response `200`: updated address object.

### DELETE `/mobile/addresses/{address_id}`
Response `204`

## Mobile Uploads

### POST `/mobile/uploads/presign`
Request:
```json
{"kind":"voice","fileExtension":"m4a","contentType":"audio/mp4"}
```
Response `200`:
```json
{"uploadUrl":"https://...","fileUrl":"https://...","method":"PUT","expiresIn":3600}
```

## GraphQL

GraphQL samples are already documented in:
- `docs/graphql-samples.graphql` (all queries and mutations)
- `docs/GRAPHQL.md` (request format + examples)

