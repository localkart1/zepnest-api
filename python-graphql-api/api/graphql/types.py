import graphene

# Existing types — aligned with production ``users`` (user_id, first_name, last_name, …)
class UserType(graphene.ObjectType):
    id = graphene.Int(description="Primary key; same as userId (users.user_id)")
    user_id = graphene.Int()
    email = graphene.String()
    first_name = graphene.String()
    last_name = graphene.String()
    phone = graphene.String()
    user_type = graphene.String()
    loyalty_points = graphene.Int()
    is_active = graphene.Boolean()
    created_at = graphene.String()
    updated_at = graphene.String()
    name = graphene.String(description="Combined first + last name (legacy convenience)")
    posts = graphene.List(lambda: PostType)

    def resolve_id(self, info):
        return self.user_id

    def resolve_name(self, info):
        parts = [self.first_name or "", self.last_name or ""]
        return " ".join(p for p in parts if p).strip() or None

    def resolve_created_at(self, info):
        if self.created_at is None:
            return None
        return self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else str(self.created_at)

    def resolve_updated_at(self, info):
        u = getattr(self, "updated_at", None)
        if u is None:
            return None
        return u.isoformat() if hasattr(u, "isoformat") else str(u)

    def resolve_posts(self, info):
        return self.posts

class PostType(graphene.ObjectType):
    id = graphene.Int()
    title = graphene.String()
    content = graphene.String()
    user_id = graphene.Int()
    author = graphene.Field(UserType)
    created_at = graphene.String()
    updated_at = graphene.String()

    def resolve_author(self, info):
        return self.author

# Technician Type
class TechnicianType(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    first_name = graphene.String()
    last_name = graphene.String()
    email = graphene.String()
    phone = graphene.String()
    specialization = graphene.String()
    status = graphene.String()
    experience_years = graphene.Int()
    experience = graphene.Int()
    certifications = graphene.String()
    created_at = graphene.String()
    updated_at = graphene.String()

    def resolve_name(self, info):
        u = getattr(self, "user", None)
        if u:
            parts = [u.first_name or "", u.last_name or ""]
            return " ".join(p for p in parts if p).strip() or None
        return getattr(self, "name", None)

    def resolve_first_name(self, info):
        u = getattr(self, "user", None)
        return (u.first_name if u else None) or None

    def resolve_last_name(self, info):
        u = getattr(self, "user", None)
        return (u.last_name if u else None) or ""

    def resolve_email(self, info):
        u = getattr(self, "user", None)
        return u.email if u else None

    def resolve_phone(self, info):
        u = getattr(self, "user", None)
        return u.phone if u else None

    def resolve_experience(self, info):
        return self.experience_years

# Category Type
class CategoryType(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    description = graphene.String()
    icon = graphene.String()
    is_active = graphene.Boolean()
    created_at = graphene.String()
    updated_at = graphene.String()
    sub_categories = graphene.List(lambda: SubCategoryType)

    def resolve_sub_categories(self, info):
        return self.sub_categories

# SubCategory Type
class SubCategoryType(graphene.ObjectType):
    id = graphene.Int()
    category_id = graphene.Int()
    name = graphene.String()
    description = graphene.String()
    is_active = graphene.Boolean()
    created_at = graphene.String()
    updated_at = graphene.String()
    category = graphene.Field(CategoryType)

    def resolve_category(self, info):
        return self.category

# PriceMapping Type
class PriceMappingType(graphene.ObjectType):
    id = graphene.Int()
    category_id = graphene.Int()
    sub_category_id = graphene.Int()
    service_name = graphene.String()
    service_type = graphene.String()
    base_price = graphene.Float()
    gst_percentage = graphene.Float()
    total_price = graphene.Float()
    unit = graphene.String()
    is_active = graphene.Boolean()
    created_at = graphene.String()
    updated_at = graphene.String()

# SubscriptionPlan Type
class SubscriptionPlanType(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    description = graphene.String()
    billing_cycle = graphene.String()
    price = graphene.Float()
    discount_percentage = graphene.Float()
    features = graphene.String()
    max_users = graphene.Int()
    is_active = graphene.Boolean()
    created_at = graphene.String()
    updated_at = graphene.String()

    def resolve_id(self, info):
        return getattr(self, "plan_id", None) or getattr(self, "id", None)

    def resolve_features(self, info):
        return getattr(self, "benefits", None) or getattr(self, "features", None)

    def resolve_created_at(self, info):
        c = getattr(self, "created_at", None)
        if c is None:
            return None
        return c.isoformat() if hasattr(c, "isoformat") else str(c)

    def resolve_updated_at(self, info):
        u = getattr(self, "updated_at", None)
        if u is None:
            return None
        return u.isoformat() if hasattr(u, "isoformat") else str(u)

# AMCPlan Type
class AMCPlanType(graphene.ObjectType):
    """Exposes ``subscription_plans`` rows whose name matches AMC (same filter as REST)."""

    id = graphene.Int()
    name = graphene.String()
    description = graphene.String()
    coverage_type = graphene.String()
    annual_cost = graphene.Float()
    coverage_items = graphene.String()
    is_active = graphene.Boolean()
    breakage_covered = graphene.Boolean()
    accidental_damage_covered = graphene.Boolean()
    created_at = graphene.String()
    updated_at = graphene.String()

    def resolve_id(self, info):
        return getattr(self, "plan_id", None) or getattr(self, "id", None)

    def resolve_coverage_type(self, info):
        return self.billing_cycle

    def resolve_annual_cost(self, info):
        return float(self.price or 0)

    def resolve_coverage_items(self, info):
        return self.benefits

    def resolve_breakage_covered(self, info):
        b = (self.benefits or "") + (self.description or "")
        return "breakage=True" in b or "breakage=true" in b

    def resolve_accidental_damage_covered(self, info):
        b = (self.benefits or "") + (self.description or "")
        return "accidental=True" in b or "accidental=true" in b

    def resolve_created_at(self, info):
        c = getattr(self, "created_at", None)
        if c is None:
            return None
        return c.isoformat() if hasattr(c, "isoformat") else str(c)

    def resolve_updated_at(self, info):
        u = getattr(self, "updated_at", None)
        if u is None:
            return None
        return u.isoformat() if hasattr(u, "isoformat") else str(u)

# Subscription Type
class SubscriptionType(graphene.ObjectType):
    id = graphene.Int()
    subscription_number = graphene.String()
    customer_id = graphene.String()
    customer_name = graphene.String()
    customer_email = graphene.String()
    plan_id = graphene.Int()
    start_date = graphene.String()
    end_date = graphene.String()
    status = graphene.String()
    total_amount = graphene.Float()
    paid_amount = graphene.Float()
    currency = graphene.String()
    renewal_date = graphene.String()
    created_at = graphene.String()
    plan = graphene.Field(SubscriptionPlanType)

    def resolve_id(self, info):
        return getattr(self, "subscription_id", None) or getattr(self, "id", None)

    def resolve_start_date(self, info):
        d = getattr(self, "start_date", None)
        if d is None:
            return None
        return d.isoformat() if hasattr(d, "isoformat") else str(d)

    def resolve_end_date(self, info):
        d = getattr(self, "end_date", None)
        if d is None:
            return None
        return d.isoformat() if hasattr(d, "isoformat") else str(d)

    def resolve_renewal_date(self, info):
        d = getattr(self, "next_billing_date", None)
        if d is None:
            return None
        return d.isoformat() if hasattr(d, "isoformat") else str(d)

    def resolve_created_at(self, info):
        c = getattr(self, "created_at", None)
        if c is None:
            return None
        return c.isoformat() if hasattr(c, "isoformat") else str(c)

    def resolve_plan(self, info):
        return self.plan

# AMCSubscription Type
class AMCSubscriptionType(graphene.ObjectType):
    """Maps ``user_subscriptions`` joined to AMC-style ``subscription_plans`` (name ILIKE '%amc%')."""

    id = graphene.Int()
    amc_number = graphene.String()
    customer_id = graphene.String()
    customer_name = graphene.String()
    customer_email = graphene.String()
    asset_id = graphene.Int()
    plan_id = graphene.Int()
    start_date = graphene.String()
    end_date = graphene.String()
    status = graphene.String()
    total_amount = graphene.Float()
    paid_amount = graphene.Float()
    currency = graphene.String()
    service_calls_limit = graphene.Int()
    service_calls_used = graphene.Int()
    renewal_date = graphene.String()
    created_at = graphene.String()
    plan = graphene.Field(AMCPlanType)

    def resolve_id(self, info):
        return getattr(self, "subscription_id", None) or getattr(self, "id", None)

    def resolve_amc_number(self, info):
        return self.subscription_number

    def resolve_asset_id(self, info):
        return None

    def resolve_start_date(self, info):
        d = getattr(self, "start_date", None)
        if d is None:
            return None
        return d.isoformat() if hasattr(d, "isoformat") else str(d)

    def resolve_end_date(self, info):
        d = getattr(self, "end_date", None)
        if d is None:
            return None
        return d.isoformat() if hasattr(d, "isoformat") else str(d)

    def resolve_renewal_date(self, info):
        d = getattr(self, "next_billing_date", None)
        if d is None:
            return None
        return d.isoformat() if hasattr(d, "isoformat") else str(d)

    def resolve_created_at(self, info):
        c = getattr(self, "created_at", None)
        if c is None:
            return None
        return c.isoformat() if hasattr(c, "isoformat") else str(c)

    def resolve_service_calls_limit(self, info):
        p = getattr(self, "plan", None)
        return p.service_credits if p else None

    def resolve_service_calls_used(self, info):
        return getattr(self, "credits_used", None)

    def resolve_plan(self, info):
        return self.plan

# Asset Type
class AssetType(graphene.ObjectType):
    id = graphene.Int()
    asset_number = graphene.String()
    customer_id = graphene.String()
    customer_name = graphene.String()
    customer_email = graphene.String()
    asset_name = graphene.String()
    asset_type = graphene.String()
    asset_category = graphene.String()
    brand = graphene.String()
    asset_brand = graphene.String()
    model = graphene.String()
    asset_model = graphene.String()
    serial_number = graphene.String()
    location = graphene.String()
    installation_date = graphene.String()
    purchase_date = graphene.String()
    warranty_expiry_date = graphene.String()
    status = graphene.String()
    is_active = graphene.Boolean()
    description = graphene.String()
    specifications = graphene.String()
    created_at = graphene.String()
    updated_at = graphene.String()

    def resolve_asset_type(self, info):
        return self.asset_category

    def resolve_brand(self, info):
        return self.asset_brand

    def resolve_model(self, info):
        return self.asset_model

    def resolve_installation_date(self, info):
        return self.purchase_date

    def resolve_is_active(self, info):
        return self.status == "active"

# AssetRegistry Type
class AssetRegistryType(graphene.ObjectType):
    id = graphene.Int()
    asset_id = graphene.Int()
    registration_number = graphene.String()
    registration_date = graphene.String()
    status = graphene.String()
    notes = graphene.String()
    created_at = graphene.String()
    asset = graphene.Field(AssetType)

    def resolve_asset(self, info):
        return self.asset

# WarrantyTracking Type
class WarrantyTrackingType(graphene.ObjectType):
    id = graphene.Int()
    asset_id = graphene.Int()
    warranty_type = graphene.String()
    warranty_start_date = graphene.String()
    warranty_end_date = graphene.String()
    coverage_details = graphene.String()
    warranty_provider = graphene.String()
    claim_limit = graphene.Float()
    claims_made = graphene.Int()
    is_active = graphene.Boolean()
    created_at = graphene.String()
    updated_at = graphene.String()

# AssetServiceMapping Type
class AssetServiceMappingType(graphene.ObjectType):
    id = graphene.Int()
    asset_id = graphene.Int()
    service_category_id = graphene.Int()
    service_sub_category_id = graphene.Int()
    recommended_service_interval = graphene.Int()
    last_service_date = graphene.String()
    next_service_date = graphene.String()
    service_count = graphene.Int()
    status = graphene.String()
    created_at = graphene.String()
    updated_at = graphene.String()

# ServiceBooking Type
class ServiceBookingType(graphene.ObjectType):
    id = graphene.Int()
    booking_number = graphene.String()
    asset_id = graphene.Int()
    customer_id = graphene.String()
    customer_name = graphene.String()
    customer_email = graphene.String()
    customer_phone = graphene.String()
    service_type = graphene.String()
    scheduled_date = graphene.String()
    scheduled_time_slot = graphene.String()
    service_status = graphene.String()
    estimated_cost = graphene.Float()
    actual_cost = graphene.Float()
    technician_id = graphene.Int()
    service_notes = graphene.String()
    completion_date = graphene.String()
    customer_rating = graphene.Int()
    customer_feedback = graphene.String()
    created_at = graphene.String()
    updated_at = graphene.String()

    def resolve_id(self, info):
        return getattr(self, "booking_id", None) or getattr(self, "id", None)

    def resolve_customer_id(self, info):
        cid = getattr(self, "customer_id", None)
        return str(cid) if cid is not None else ""

    def resolve_scheduled_date(self, info):
        d = getattr(self, "created_at", None)
        if d is None:
            return None
        return d.isoformat() if hasattr(d, "isoformat") else str(d)

    def resolve_service_notes(self, info):
        return getattr(self, "customer_notes", None)

    def resolve_estimated_cost(self, info):
        return getattr(self, "total_amount", None)

# Ticket Type
class TicketType(graphene.ObjectType):
    id = graphene.Int()
    order_no = graphene.String()
    ticket_number = graphene.String()
    customer_name = graphene.String()
    customer_email = graphene.String()
    phone = graphene.String()
    customer_phone = graphene.String()
    service = graphene.String()
    issue_description = graphene.String()
    status = graphene.String()
    priority = graphene.String()
    assigned_to = graphene.Int()
    asset_id = graphene.Int()
    category_id = graphene.Int()
    sub_category_id = graphene.Int()
    resolution_notes = graphene.String()
    escalation_reason = graphene.String()
    estimated_resolution_time = graphene.Int()
    actual_resolution_time = graphene.Int()
    resolution_date = graphene.String()
    created_at = graphene.String()
    updated_at = graphene.String()
    technician = graphene.Field(TechnicianType)
    asset = graphene.Field(AssetType)

    def resolve_id(self, info):
        return getattr(self, "booking_id", None) or getattr(self, "id", None)

    def resolve_assigned_to(self, info):
        return getattr(self, "technician_id", None)

    def resolve_order_no(self, info):
        return self.ticket_number

    def resolve_phone(self, info):
        return self.customer_phone

    def resolve_service(self, info):
        return self.issue_description

    def resolve_technician(self, info):
        return self.assigned_technician

    def resolve_asset(self, info):
        return self.asset

# Escalation Type
class EscalationType(graphene.ObjectType):
    id = graphene.Int()
    ticket_id = graphene.Int()
    escalation_level = graphene.Int()
    reason = graphene.String()
    escalated_to = graphene.String()
    escalation_date = graphene.String()
    expected_resolution_time = graphene.Int()
    status = graphene.String()
    resolution_notes = graphene.String()
    resolved_date = graphene.String()
    created_at = graphene.String()
    updated_at = graphene.String()

    def resolve_ticket_id(self, info):
        return getattr(self, "booking_id", None)

    def resolve_escalation_level(self, info):
        return 1

    def resolve_escalation_date(self, info):
        c = getattr(self, "created_at", None)
        if c is None:
            return None
        return c.isoformat() if hasattr(c, "isoformat") else str(c)

    def resolve_status(self, info):
        return "open"

    def resolve_resolution_notes(self, info):
        return None

    def resolve_resolved_date(self, info):
        return None

# ComplianceRecord Type
class ComplianceRecordType(graphene.ObjectType):
    id = graphene.Int()
    technician_id = graphene.Int()
    compliance_type = graphene.String()
    description = graphene.String()
    status = graphene.String()
    expiry_date = graphene.String()
    certification_document = graphene.String()
    issued_date = graphene.String()
    created_at = graphene.String()
    updated_at = graphene.String()

    def resolve_status(self, info):
        return "approved"

    def resolve_issued_date(self, info):
        d = getattr(self, "issued_date", None)
        if d is None:
            return None
        return d.isoformat() if hasattr(d, "isoformat") else str(d)

    def resolve_expiry_date(self, info):
        d = getattr(self, "expiry_date", None)
        if d is None:
            return None
        return d.isoformat() if hasattr(d, "isoformat") else str(d)


class PaginatedTechnicianType(graphene.ObjectType):
    items = graphene.List(TechnicianType)
    total = graphene.Int()
    page = graphene.Int()
    limit = graphene.Int()


class PaginatedAssetType(graphene.ObjectType):
    items = graphene.List(AssetType)
    total = graphene.Int()
    page = graphene.Int()
    limit = graphene.Int()


class PaginatedOrderType(graphene.ObjectType):
    items = graphene.List(TicketType)
    total = graphene.Int()
    page = graphene.Int()
    limit = graphene.Int()
