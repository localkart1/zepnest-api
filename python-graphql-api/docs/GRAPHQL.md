# GraphQL — HTTP request formats and examples

GraphQL is served at **`POST /graphql`** (and **`GET /graphql`** opens GraphiQL in the browser).

**Field names:** Graphene exposes GraphQL fields in **camelCase** (e.g. `billingCycle`, `createdAt`, `createUser`). If a field is rejected, run the introspection queries in §2 or use GraphiQL’s autocomplete.

> **Note:** Core GraphQL types are aligned with the same **PostgreSQL** tables as **`/api`** REST: **`users`**, **`bookings`**, **`technician_profiles`**, **`subscription_plans`**, **`user_subscriptions`**, **`escalations`**, **`compliance_records`**, etc. (see `api/models/*`). Legacy GraphQL field names (e.g. ticket vs booking) are mapped in resolvers. For contract details or edge cases, still refer to REST responses and `api/rest/routes.py`.

---

## 1. HTTP request format

**URL:** `http://localhost:<PORT>/graphql` (default port from `PORT` in `.env`, often `5002`).

**Method:** `POST`

**Headers:**

```http
Content-Type: application/json
```

**Body (JSON):**

| Field | Required | Description |
|-------|----------|-------------|
| `query` | Yes | GraphQL document string |
| `variables` | No | JSON object for `$variable` placeholders |
| `operationName` | No | Name of the operation to run (useful when `query` contains multiple operations) |

**Example (minimal):**

```json
{
  "query": "query { users { id name email } }"
}
```

**Example (with variables):**

```json
{
  "query": "mutation CreateUser($name: String!, $email: String!) { createUser(name: $name, email: $email) { success message user { id name email } } }",
  "variables": {
    "name": "Jane",
    "email": "jane@example.com"
  },
  "operationName": null
}
```

**cURL:**

```bash
curl -s -X POST "http://localhost:5002/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query":"query { users { id name email } }"}'
```

**Successful response shape:**

```json
{
  "data": { ... }
}
```

**Errors:**

```json
{
  "data": null,
  "errors": [{ "message": "..." }]
}
```

---

## 2. Discover the schema (introspection)

You can ask for types and fields (many clients use a full introspection query; GraphiQL does this automatically).

**Query type and available fields:**

```graphql
query {
  __schema {
    queryType { name }
    mutationType { name }
  }
}
```

**List root query fields:**

```graphql
query {
  __type(name: "Query") {
    fields {
      name
      args {
        name
        type { name kind ofType { name kind } }
      }
    }
  }
}
```

**List root mutation fields:**

```graphql
query {
  __type(name: "Mutation") {
    fields {
      name
      args {
        name
        type { name kind ofType { name kind } }
      }
    }
  }
}
```

---

## 3. Schema alignment (PostgreSQL / REST)

| GraphQL area | Table(s) | Notes |
|--------------|----------|--------|
| `tickets`, `orders`, `serviceBookings`, … | **`bookings`** | One row type for both “ticket” and “service booking” GraphQL types. PK exposed as `id` → `booking_id`. `ticketNumber` ↔ `booking_number`, `issueDescription` / notes ↔ `customer_notes`, `assignedTo` ↔ `technician_id`. |
| `technicians`, … | **`technician_profiles`** + **`users`** | `id` is `technician_id`. `name`, `email`, `phone`, `firstName` / `lastName` come from the linked **`users`** row. `techniciansPaginated` search matches user name, email, phone, and specialization. |
| `subscriptionPlans`, … | **`subscription_plans`** | GraphQL **`features`** maps to column **`benefits`**. `id` ↔ `plan_id`. |
| `subscriptions`, `createSubscription`, … | **`user_subscriptions`** | `customerId` (query/mutation) must be a **numeric string** for **`users.user_id`**. |
| `amcPlans`, `amcSubscriptions`, `createAmcPlan`, … | Same as plans + subscriptions | AMC rows are plans whose **`name`** matches **`%amc%`** (case-insensitive), same idea as REST `/api/subscriptions/amc`. `createAmcPlan` inserts into **`subscription_plans`** and ensures the name contains **`AMC`**. `amcSubscriptionsByAsset` returns **`[]`** (subscriptions are not tied to an asset column in this schema). |
| `escalations`, `escalateOrder`, … | **`escalations`** | FK is **`booking_id`** (GraphQL may still expose **`ticketId`** as an alias). |
| `complianceRecords`, … | **`compliance_records`** | **`technicianId`** → **`technician_profiles.technician_id`**. |

**Query behavior:**

- **`ordersPaginated`** / ticket search: filters on **`booking_number`**, customer fields via join to **`users`**, and **`customer_notes`**.
- **`ticketsByPriority`**: matches **`[priority=<value>]`** inside **`customer_notes`** (as set by `createTicket` when priority is passed).
- **`ticketsByTechnician`**: filters **`technician_id`** (argument `assignedTo`).
- **`serviceBookingsByAsset`**: matches **`customer_notes`** containing **`asset_id=<id>`** (as embedded by `createServiceBooking`).
- **`serviceBookingsByStatus`**: filters booking **`status`** (argument `serviceStatus`).

---

## 4. Sample queries

Field names in GraphQL are **camelCase** (e.g. `techniciansPaginated`, `subCategoriesByCategory`).

### Users & posts

`User` matches the production **`users`** table: `userId` / `id` (both map to `user_id`), `firstName`, `lastName`, `email`, `phone`, `userType`, `loyaltyPoints`, `isActive`, `createdAt`, `updatedAt`. The `name` field is a convenience string (`firstName` + `lastName`). Legacy `createUser(name: …)` is still supported by splitting `name` into first/last when `firstName`/`lastName` are omitted.

```graphql
query {
  users {
    id
    userId
    firstName
    lastName
    name
    email
    phone
    userType
    loyaltyPoints
    isActive
    createdAt
    updatedAt
  }
}
```

```graphql
query GetUser($id: Int!) {
  user(id: $id) {
    id
    firstName
    lastName
    email
    phone
    posts {
      id
      title
    }
  }
}
```

**Variables:** `{ "id": 1 }`

### Technicians (paginated)

```graphql
query TechniciansPage($page: Int, $limit: Int, $search: String, $status: String) {
  techniciansPaginated(page: $page, limit: $limit, search: $search, status: $status) {
    total
    page
    limit
    items {
      id
      name
      email
      specialization
      status
    }
  }
}
```

**Variables:** `{ "page": 1, "limit": 10, "search": "", "status": null }`

Search runs against the technician’s **`users`** first/last name, email, phone, and **`specialization`** (not a single `name` column on `technician_profiles`).

### Categories

```graphql
query {
  categories {
    id
    name
    description
    isActive
  }
}
```

### Subscription plans

```graphql
query {
  subscriptionPlans {
    id
    name
    billingCycle
    price
    features
    isActive
    createdAt
  }
}
```

`features` is the GraphQL name for the DB column **`benefits`**.

### Subscriptions & AMC (queries)

```graphql
query {
  subscriptions {
    id
    subscriptionNumber
    customerId
    planId
    status
    startDate
    endDate
    plan {
      id
      name
      price
    }
  }
}
```

`customerId` is a string form of **`users.user_id`**.

```graphql
query {
  amcPlans {
    id
    name
    annualCost
    coverageType
    isActive
  }
}
```

AMC plans are **`subscription_plans`** rows whose **`name`** matches **`%amc%`**.

```graphql
query {
  amcSubscriptions {
    id
    amcNumber
    customerId
    status
    plan {
      id
      name
    }
  }
}
```

### Assets (paginated)

```graphql
query AssetsPage($page: Int, $limit: Int) {
  assetsPaginated(page: $page, limit: $limit) {
    total
    items {
      id
      assetName
      assetCategory
      status
    }
  }
}
```

---

## 5. Sample mutations

Mutations use **camelCase** names: `createUser`, `createTechnician`, `assignTechnicianToOrder`, etc.

### User

```graphql
mutation CreateUser(
  $email: String!
  $firstName: String
  $lastName: String
  $phone: String
  $userType: String
) {
  createUser(
    email: $email
    firstName: $firstName
    lastName: $lastName
    phone: $phone
    userType: $userType
  ) {
    success
    message
    user {
      id
      userId
      firstName
      lastName
      email
      phone
      userType
    }
  }
}
```

**Variables:** `{ "email": "test@example.com", "firstName": "Test", "lastName": "User", "phone": "", "userType": "customer" }`

Legacy (single `name` split on first space):

```graphql
mutation CreateUserLegacy($email: String!, $name: String!) {
  createUser(email: $email, name: $name) {
    success
    user { id firstName lastName }
  }
}
```

```graphql
mutation UpdateUser(
  $id: Int!
  $firstName: String
  $lastName: String
  $email: String
  $phone: String
  $userType: String
  $isActive: Boolean
) {
  updateUser(
    id: $id
    firstName: $firstName
    lastName: $lastName
    email: $email
    phone: $phone
    userType: $userType
    isActive: $isActive
  ) {
    success
    message
    user {
      id
      firstName
      lastName
      email
      phone
      isActive
    }
  }
}
```

```graphql
mutation DeleteUser($id: Int!) {
  deleteUser(id: $id) {
    success
    message
  }
}
```

### Post

```graphql
mutation CreatePost($title: String!, $userId: Int!, $content: String) {
  createPost(title: $title, userId: $userId, content: $content) {
    success
    message
    post { id title }
  }
}
```

### Technician

```graphql
mutation CreateTechnician(
  $name: String!
  $email: String!
  $phone: String!
  $specialization: String!
  $experienceYears: Int
  $certifications: String
) {
  createTechnician(
    name: $name
    email: $email
    phone: $phone
    specialization: $specialization
    experienceYears: $experienceYears
    certifications: $certifications
  ) {
    success
    message
    technician { id name email }
  }
}
```

### Category / subcategory

```graphql
mutation CreateCategory($name: String!, $description: String, $icon: String) {
  createCategory(name: $name, description: $description, icon: $icon) {
    success
    message
    category { id name }
  }
}
```

```graphql
mutation CreateSubCategory($categoryId: Int!, $name: String!, $description: String) {
  createSubCategory(categoryId: $categoryId, name: $name, description: $description) {
    success
    message
    subCategory { id name }
  }
}
```

### Price mapping

```graphql
mutation CreatePriceMapping(
  $categoryId: Int!
  $serviceName: String!
  $serviceType: String!
  $basePrice: Float!
  $subCategoryId: Int
  $gstPercentage: Float
  $unit: String
) {
  createPriceMapping(
    categoryId: $categoryId
    subCategoryId: $subCategoryId
    serviceName: $serviceName
    serviceType: $serviceType
    basePrice: $basePrice
    gstPercentage: $gstPercentage
    unit: $unit
  ) {
    success
    message
    priceMapping { id serviceName totalPrice }
  }
}
```

### Subscription plan and AMC plan

```graphql
mutation CreateSubscriptionPlan(
  $name: String!
  $billingCycle: String!
  $price: Float!
  $description: String
  $discountPercentage: Float
  $features: String
  $maxUsers: Int
) {
  createSubscriptionPlan(
    name: $name
    billingCycle: $billingCycle
    price: $price
    description: $description
    discountPercentage: $discountPercentage
    features: $features
    maxUsers: $maxUsers
  ) {
    success
    message
    subscriptionPlan { id name price }
  }
}
```

```graphql
mutation CreateAmcPlan(
  $name: String!
  $coverageType: String!
  $annualCost: Float!
  $description: String
  $coverageItems: String
  $breakageCovered: Boolean
  $accidentalDamageCovered: Boolean
) {
  createAmcPlan(
    name: $name
    coverageType: $coverageType
    annualCost: $annualCost
    description: $description
    coverageItems: $coverageItems
    breakageCovered: $breakageCovered
    accidentalDamageCovered: $accidentalDamageCovered
  ) {
    success
    message
    amcPlan { id name annualCost coverageType }
  }
}
```

`createAmcPlan` writes to **`subscription_plans`** (same table as subscription plans). The returned **`amcPlan`** uses the same shape as a subscription plan for key fields (`annualCost` ← `price`, `coverageType` ← `billingCycle`, etc.).

### Subscription (customer)

```graphql
mutation CreateSubscription(
  $subscriptionNumber: String!
  $customerId: String!
  $customerName: String!
  $customerEmail: String!
  $planId: Int!
  $startDate: String!
  $endDate: String!
  $totalAmount: Float!
) {
  createSubscription(
    subscriptionNumber: $subscriptionNumber
    customerId: $customerId
    customerName: $customerName
    customerEmail: $customerEmail
    planId: $planId
    startDate: $startDate
    endDate: $endDate
    totalAmount: $totalAmount
  ) {
    success
    message
    subscription { id subscriptionNumber }
  }
}
```

**`customerId`:** must parse to an integer **`users.user_id`** (existing user). The mutation creates a **`user_subscriptions`** row with `user_id`, `plan_id`, `start_date`, `end_date`, and default credits fields. Arguments such as `subscriptionNumber`, `customerName`, `customerEmail`, and `totalAmount` are accepted for API compatibility; the persisted row follows the live table (see `api/models/subscription.py`).

### Asset

```graphql
mutation CreateAsset(
  $assetNumber: String!
  $customerId: String!
  $customerName: String!
  $customerEmail: String!
  $assetName: String!
  $assetCategory: String!
  $serialNumber: String!
  $assetBrand: String
  $assetModel: String
  $location: String
) {
  createAsset(
    assetNumber: $assetNumber
    customerId: $customerId
    customerName: $customerName
    customerEmail: $customerEmail
    assetName: $assetName
    assetCategory: $assetCategory
    serialNumber: $serialNumber
    assetBrand: $assetBrand
    assetModel: $assetModel
    location: $location
  ) {
    success
    message
    asset { id assetName }
  }
}
```

### Ticket / order (assign and escalate)

Creates/updates **`bookings`** (see §3). `createTicket` resolves or creates a **`users`** row by **`customerEmail`** and stores issue text in **`customer_notes`** (with optional category/priority prefixes).

```graphql
mutation CreateTicket(
  $ticketNumber: String!
  $customerName: String!
  $customerEmail: String!
  $customerPhone: String!
  $issueDescription: String!
  $categoryId: Int
  $priority: String
) {
  createTicket(
    ticketNumber: $ticketNumber
    customerName: $customerName
    customerEmail: $customerEmail
    customerPhone: $customerPhone
    issueDescription: $issueDescription
    categoryId: $categoryId
    priority: $priority
  ) {
    success
    message
    ticket { id ticketNumber status }
  }
}
```

```graphql
mutation AssignTechnicianToOrder($orderId: Int!, $technicianId: Int!) {
  assignTechnicianToOrder(orderId: $orderId, technicianId: $technicianId) {
    success
    message
    ticket { id status assignedTo }
  }
}
```

```graphql
mutation EscalateOrder(
  $orderId: Int!
  $reason: String!
  $escalatedTo: String!
  $expectedResolutionTime: Int
) {
  escalateOrder(
    orderId: $orderId
    reason: $reason
    escalatedTo: $escalatedTo
    expectedResolutionTime: $expectedResolutionTime
  ) {
    success
    message
    ticket { id status }
    escalation { id reason }
  }
}
```

### Service booking

Also persists **`bookings`**. Extra metadata (service type, asset id, schedule) is embedded in **`customer_notes`** so **`serviceBookingsByAsset`** can filter by `asset_id=…`.

```graphql
mutation CreateServiceBooking(
  $bookingNumber: String!
  $assetId: Int!
  $customerId: String!
  $customerName: String!
  $customerEmail: String!
  $customerPhone: String!
  $serviceType: String!
  $scheduledDate: String!
  $scheduledTimeSlot: String
  $estimatedCost: Float
) {
  createServiceBooking(
    bookingNumber: $bookingNumber
    assetId: $assetId
    customerId: $customerId
    customerName: $customerName
    customerEmail: $customerEmail
    customerPhone: $customerPhone
    serviceType: $serviceType
    scheduledDate: $scheduledDate
    scheduledTimeSlot: $scheduledTimeSlot
    estimatedCost: $estimatedCost
  ) {
    success
    message
    serviceBooking { id bookingNumber }
  }
}
```

### Warranty and compliance

Date arguments (`warrantyStartDate`, `warrantyEndDate`, `issuedDate`, `expiryDate`) should be **ISO-8601** strings (e.g. `2026-03-28T`…); the server parses them to datetimes.

```graphql
mutation CreateWarrantyTracking(
  $assetId: Int!
  $warrantyType: String!
  $warrantyStartDate: String!
  $warrantyEndDate: String!
  $coverageDetails: String
  $warrantyProvider: String
  $claimLimit: Float
) {
  createWarrantyTracking(
    assetId: $assetId
    warrantyType: $warrantyType
    warrantyStartDate: $warrantyStartDate
    warrantyEndDate: $warrantyEndDate
    coverageDetails: $coverageDetails
    warrantyProvider: $warrantyProvider
    claimLimit: $claimLimit
  ) {
    success
    message
    warranty { id }
  }
}
```

```graphql
mutation CreateComplianceRecord(
  $technicianId: Int!
  $complianceType: String!
  $issuedDate: String!
  $description: String
  $expiryDate: String
  $certificationDocument: String
) {
  createComplianceRecord(
    technicianId: $technicianId
    complianceType: $complianceType
    issuedDate: $issuedDate
    description: $description
    expiryDate: $expiryDate
    certificationDocument: $certificationDocument
  ) {
    success
    message
    complianceRecord { id }
  }
}
```

---

## 6. Operation index (from `api/graphql/schema.py`)

**Queries:** `users`, `user`, `posts`, `post`, `technicians`, `techniciansPaginated`, `technician`, `techniciansByStatus`, `techniciansBySpecialization`, `categories`, `category`, `subCategories`, `subCategoriesByCategory`, `subCategory`, `priceMappings`, `priceMappingsByCategory`, `priceMapping`, `subscriptionPlans`, `subscriptionPlan`, `activeSubscriptionPlans`, `amcPlans`, `amcPlan`, `activeAmcPlans`, `subscriptions`, `subscription`, `subscriptionsByCustomer`, `subscriptionsByStatus`, `amcSubscriptions`, `amcSubscriptionsByAsset`, `amcSubscriptionsByCustomer`, `assets`, `assetsPaginated`, `asset`, `assetsByCustomer`, `assetsByCategory`, `assetRegistries`, `assetRegistry`, `warrantyRecords`, `warrantyByAsset`, `assetServiceMappings`, `assetServiceMappingsByAsset`, `tickets`, `ticket`, `orders`, `order`, `ordersPaginated`, `ticketsByStatus`, `ticketsByPriority`, `ticketsByTechnician`, `serviceBookings`, `serviceBooking`, `serviceBookingsByAsset`, `serviceBookingsByStatus`, `escalations`, `escalationsByTicket`, `complianceRecords`, `complianceByTechnician`.

**Mutations:** `createUser`, `updateUser`, `deleteUser`, `createPost`, `createTechnician`, `updateTechnician`, `deleteTechnician`, `createCategory`, `updateCategory`, `deleteCategory`, `createSubCategory`, `updateSubCategory`, `createPriceMapping`, `updatePriceMapping`, `createSubscriptionPlan`, `updateSubscriptionPlan`, `createAmcPlan`, `createSubscription`, `createAsset`, `updateAsset`, `createTicket`, `updateTicket`, `assignTechnicianToOrder`, `escalateOrder`, `createEscalation`, `createServiceBooking`, `updateServiceBooking`, `createWarrantyTracking`, `createComplianceRecord`.

---

## 7. GraphiQL

Open **`GET /graphql`** in a browser for an interactive IDE. It sends the same JSON body to **`POST /graphql`** as shown above.
