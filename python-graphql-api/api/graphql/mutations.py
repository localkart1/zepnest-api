from datetime import datetime

import graphene
from api import db
from api.models.user import User as UserModel
from api.models.post import Post as PostModel
from api.models.technician import Technician as TechnicianModel
from api.models.booking import Booking as TicketModel
from api.models.booking import Booking as ServiceBookingModel
from api.models.service_catalog import Category as CategoryModel, SubCategory as SubCategoryModel, PriceMapping as PriceMappingModel
from api.models.subscription import SubscriptionPlan as SubscriptionPlanModel, Subscription as SubscriptionModel
from api.models.asset import Asset as AssetModel, AssetRegistry as AssetRegistryModel, WarrantyTracking as WarrantyTrackingModel, AssetServiceMapping as AssetServiceMappingModel
from api.models.escalation_compliance import Escalation as EscalationModel, ComplianceRecord as ComplianceRecordModel
from api.graphql.types import (
    UserType, PostType, TechnicianType, TicketType, CategoryType, SubCategoryType,
    PriceMappingType, SubscriptionPlanType, AMCPlanType, SubscriptionType, AMCSubscriptionType,
    AssetType, AssetRegistryType, WarrantyTrackingType, AssetServiceMappingType, ServiceBookingType,
    EscalationType, ComplianceRecordType,
)


def _parse_iso_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)

# ==================== USER & POST MUTATIONS ====================
class CreateUser(graphene.Mutation):
    class Arguments:
        email = graphene.String(required=True)
        first_name = graphene.String()
        last_name = graphene.String()
        name = graphene.String()
        phone = graphene.String()
        user_type = graphene.String()

    user = graphene.Field(UserType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, email, first_name=None, last_name=None, name=None, phone=None, user_type=None):
        fn = (first_name or "").strip()
        ln = (last_name or "").strip()
        if not fn and not ln and name:
            parts = name.strip().split(None, 1)
            fn = parts[0] if parts else ""
            ln = parts[1] if len(parts) > 1 else ""
        try:
            user = UserModel(
                email=email,
                first_name=fn or None,
                last_name=ln or None,
                phone=(phone or "").strip() or "",
                user_type=(user_type or "customer").strip() or "customer",
                password_hash="",
                loyalty_points=0,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
            return CreateUser(user=user, success=True, message="User created successfully")
        except Exception as e:
            db.session.rollback()
            return CreateUser(user=None, success=False, message=str(e))


class UpdateUser(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        first_name = graphene.String()
        last_name = graphene.String()
        email = graphene.String()
        phone = graphene.String()
        user_type = graphene.String()
        is_active = graphene.Boolean()

    user = graphene.Field(UserType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id, first_name=None, last_name=None, email=None, phone=None, user_type=None, is_active=None):
        try:
            user = UserModel.query.get(id)
            if not user:
                return UpdateUser(user=None, success=False, message="User not found")
            if first_name is not None:
                user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            if email is not None:
                user.email = email
            if phone is not None:
                user.phone = phone
            if user_type is not None:
                user.user_type = user_type
            if is_active is not None:
                user.is_active = is_active
            db.session.commit()
            return UpdateUser(user=user, success=True, message="User updated")
        except Exception as e:
            db.session.rollback()
            return UpdateUser(user=None, success=False, message=str(e))

class DeleteUser(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id):
        try:
            user = UserModel.query.get(id)
            if not user:
                return DeleteUser(success=False, message="User not found")
            db.session.delete(user)
            db.session.commit()
            return DeleteUser(success=True, message="User deleted")
        except Exception as e:
            db.session.rollback()
            return DeleteUser(success=False, message=str(e))

class CreatePost(graphene.Mutation):
    class Arguments:
        title = graphene.String(required=True)
        content = graphene.String()
        user_id = graphene.Int(required=True)

    post = graphene.Field(PostType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, title, user_id, content=None):
        try:
            post = PostModel(title=title, content=content, user_id=user_id)
            db.session.add(post)
            db.session.commit()
            return CreatePost(post=post, success=True, message="Post created successfully")
        except Exception as e:
            db.session.rollback()
            return CreatePost(post=None, success=False, message=str(e))

# ==================== TECHNICIAN MUTATIONS ====================
class CreateTechnician(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        email = graphene.String(required=True)
        phone = graphene.String(required=True)
        specialization = graphene.String(required=True)
        experience_years = graphene.Int()
        certifications = graphene.String()

    technician = graphene.Field(TechnicianType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, name, email, phone, specialization, experience_years=0, certifications=None):
        try:
            parts = name.strip().split(None, 1)
            fn = parts[0] if parts else "Technician"
            ln = parts[1] if len(parts) > 1 else ""
            user = UserModel(
                email=email,
                phone=phone or "",
                first_name=fn,
                last_name=ln,
                user_type="technician",
                password_hash="",
                loyalty_points=0,
                is_active=True,
            )
            db.session.add(user)
            db.session.flush()
            technician = TechnicianModel(
                user_id=user.user_id,
                specialization=specialization,
                experience_years=experience_years or 0,
                certification=certifications,
                status="available",
            )
            db.session.add(technician)
            db.session.commit()
            return CreateTechnician(technician=technician, success=True, message="Technician created successfully")
        except Exception as e:
            db.session.rollback()
            return CreateTechnician(technician=None, success=False, message=str(e))


class UpdateTechnician(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        name = graphene.String()
        email = graphene.String()
        phone = graphene.String()
        specialization = graphene.String()
        status = graphene.String()
        experience_years = graphene.Int()
        certifications = graphene.String()

    technician = graphene.Field(TechnicianType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id, **kwargs):
        try:
            technician = TechnicianModel.query.get(id)
            if not technician:
                return UpdateTechnician(technician=None, success=False, message="Technician not found")
            if kwargs.get("name"):
                parts = kwargs.pop("name").strip().split(None, 1)
                if technician.user:
                    technician.user.first_name = parts[0] if parts else ""
                    technician.user.last_name = parts[1] if len(parts) > 1 else ""
            if kwargs.get("email") is not None and technician.user:
                technician.user.email = kwargs.pop("email")
            if kwargs.get("phone") is not None and technician.user:
                technician.user.phone = kwargs.pop("phone")
            if kwargs.get("certifications") is not None:
                technician.certification = kwargs.pop("certifications")
            for key, value in list(kwargs.items()):
                if value is not None and hasattr(technician, key):
                    setattr(technician, key, value)
            db.session.commit()
            return UpdateTechnician(technician=technician, success=True, message="Technician updated")
        except Exception as e:
            db.session.rollback()
            return UpdateTechnician(technician=None, success=False, message=str(e))


class DeleteTechnician(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id):
        try:
            technician = TechnicianModel.query.get(id)
            if not technician:
                return DeleteTechnician(success=False, message="Technician not found")
            uid = technician.user_id
            db.session.delete(technician)
            db.session.flush()
            u = UserModel.query.get(uid)
            if u:
                db.session.delete(u)
            db.session.commit()
            return DeleteTechnician(success=True, message="Technician deleted")
        except Exception as e:
            db.session.rollback()
            return DeleteTechnician(success=False, message=str(e))

# ==================== CATEGORY MUTATIONS ====================
class CreateCategory(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        description = graphene.String()
        icon = graphene.String()

    category = graphene.Field(CategoryType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, name, description=None, icon=None):
        try:
            category = CategoryModel(name=name, description=description, icon=icon)
            db.session.add(category)
            db.session.commit()
            return CreateCategory(category=category, success=True, message="Category created successfully")
        except Exception as e:
            db.session.rollback()
            return CreateCategory(category=None, success=False, message=str(e))

class UpdateCategory(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        name = graphene.String()
        description = graphene.String()
        icon = graphene.String()
        is_active = graphene.Boolean()

    category = graphene.Field(CategoryType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id, **kwargs):
        try:
            category = CategoryModel.query.get(id)
            if not category:
                return UpdateCategory(category=None, success=False, message="Category not found")
            for key, value in kwargs.items():
                if value is not None:
                    setattr(category, key, value)
            db.session.commit()
            return UpdateCategory(category=category, success=True, message="Category updated")
        except Exception as e:
            db.session.rollback()
            return UpdateCategory(category=None, success=False, message=str(e))

class DeleteCategory(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id):
        try:
            category = CategoryModel.query.get(id)
            if not category:
                return DeleteCategory(success=False, message="Category not found")
            db.session.delete(category)
            db.session.commit()
            return DeleteCategory(success=True, message="Category deleted")
        except Exception as e:
            db.session.rollback()
            return DeleteCategory(success=False, message=str(e))

# ==================== SUB-CATEGORY MUTATIONS ====================
class CreateSubCategory(graphene.Mutation):
    class Arguments:
        category_id = graphene.Int(required=True)
        name = graphene.String(required=True)
        description = graphene.String()

    sub_category = graphene.Field(SubCategoryType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, category_id, name, description=None):
        try:
            sub_category = SubCategoryModel(category_id=category_id, name=name, description=description)
            db.session.add(sub_category)
            db.session.commit()
            return CreateSubCategory(sub_category=sub_category, success=True, message="SubCategory created successfully")
        except Exception as e:
            db.session.rollback()
            return CreateSubCategory(sub_category=None, success=False, message=str(e))

class UpdateSubCategory(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        name = graphene.String()
        description = graphene.String()
        is_active = graphene.Boolean()

    sub_category = graphene.Field(SubCategoryType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id, **kwargs):
        try:
            sub_category = SubCategoryModel.query.get(id)
            if not sub_category:
                return UpdateSubCategory(sub_category=None, success=False, message="SubCategory not found")
            for key, value in kwargs.items():
                if value is not None:
                    setattr(sub_category, key, value)
            db.session.commit()
            return UpdateSubCategory(sub_category=sub_category, success=True, message="SubCategory updated")
        except Exception as e:
            db.session.rollback()
            return UpdateSubCategory(sub_category=None, success=False, message=str(e))

# ==================== PRICE MAPPING MUTATIONS ====================
class CreatePriceMapping(graphene.Mutation):
    class Arguments:
        category_id = graphene.Int(required=True)
        sub_category_id = graphene.Int()
        service_name = graphene.String(required=True)
        service_type = graphene.String(required=True)
        base_price = graphene.Float(required=True)
        gst_percentage = graphene.Float()
        unit = graphene.String()

    price_mapping = graphene.Field(PriceMappingType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, category_id, service_name, service_type, base_price,
               sub_category_id=None, gst_percentage=18.0, unit="per service"):
        try:
            total_price = base_price * (1 + gst_percentage / 100)
            price_mapping = PriceMappingModel(
                category_id=category_id, sub_category_id=sub_category_id,
                service_name=service_name, service_type=service_type,
                base_price=base_price, gst_percentage=gst_percentage,
                total_price=total_price, unit=unit
            )
            db.session.add(price_mapping)
            db.session.commit()
            return CreatePriceMapping(price_mapping=price_mapping, success=True, message="Price mapping created successfully")
        except Exception as e:
            db.session.rollback()
            return CreatePriceMapping(price_mapping=None, success=False, message=str(e))

class UpdatePriceMapping(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        service_name = graphene.String()
        base_price = graphene.Float()
        gst_percentage = graphene.Float()
        is_active = graphene.Boolean()

    price_mapping = graphene.Field(PriceMappingType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id, **kwargs):
        try:
            price_mapping = PriceMappingModel.query.get(id)
            if not price_mapping:
                return UpdatePriceMapping(price_mapping=None, success=False, message="Price mapping not found")

            for key, value in kwargs.items():
                if value is not None:
                    if key in ['base_price', 'gst_percentage']:
                        setattr(price_mapping, key, value)
                    else:
                        setattr(price_mapping, key, value)

            # Recalculate total_price if base_price or gst_percentage changed
            if 'base_price' in kwargs or 'gst_percentage' in kwargs:
                price_mapping.total_price = price_mapping.base_price * (1 + price_mapping.gst_percentage / 100)

            db.session.commit()
            return UpdatePriceMapping(price_mapping=price_mapping, success=True, message="Price mapping updated")
        except Exception as e:
            db.session.rollback()
            return UpdatePriceMapping(price_mapping=None, success=False, message=str(e))

# ==================== SUBSCRIPTION PLAN MUTATIONS ====================
class CreateSubscriptionPlan(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        description = graphene.String()
        billing_cycle = graphene.String(required=True)
        price = graphene.Float(required=True)
        discount_percentage = graphene.Float()
        features = graphene.String()
        max_users = graphene.Int()

    subscription_plan = graphene.Field(SubscriptionPlanType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, name, billing_cycle, price, description=None,
               discount_percentage=0, features=None, max_users=None):
        try:
            plan = SubscriptionPlanModel(
                name=name,
                description=description,
                billing_cycle=billing_cycle,
                price=price,
                discount_percentage=discount_percentage or 0,
                benefits=features or "",
                service_credits=0,
                priority_booking=False,
                free_inspection=False,
                is_active=True,
            )
            db.session.add(plan)
            db.session.commit()
            return CreateSubscriptionPlan(subscription_plan=plan, success=True, message="Subscription plan created successfully")
        except Exception as e:
            db.session.rollback()
            return CreateSubscriptionPlan(subscription_plan=None, success=False, message=str(e))

class UpdateSubscriptionPlan(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        name = graphene.String()
        price = graphene.Float()
        discount_percentage = graphene.Float()
        is_active = graphene.Boolean()

    subscription_plan = graphene.Field(SubscriptionPlanType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id, **kwargs):
        try:
            plan = SubscriptionPlanModel.query.get(id)
            if not plan:
                return UpdateSubscriptionPlan(subscription_plan=None, success=False, message="Plan not found")
            for key, value in kwargs.items():
                if value is not None:
                    setattr(plan, key, value)
            db.session.commit()
            return UpdateSubscriptionPlan(subscription_plan=plan, success=True, message="Plan updated")
        except Exception as e:
            db.session.rollback()
            return UpdateSubscriptionPlan(subscription_plan=None, success=False, message=str(e))

# ==================== AMC PLAN MUTATIONS ====================
class CreateAMCPlan(graphene.Mutation):
    """Creates a row in ``subscription_plans`` (same table as subscription plans; AMC-style fields mapped)."""

    class Arguments:
        name = graphene.String(required=True)
        description = graphene.String()
        coverage_type = graphene.String(required=True)
        annual_cost = graphene.Float(required=True)
        coverage_items = graphene.String()
        breakage_covered = graphene.Boolean()
        accidental_damage_covered = graphene.Boolean()

    amc_plan = graphene.Field(SubscriptionPlanType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, name, coverage_type, annual_cost, description=None,
               coverage_items=None, breakage_covered=False, accidental_damage_covered=False):
        try:
            extra = f" coverage={coverage_type} breakage={breakage_covered} accidental={accidental_damage_covered}"
            amc_name = name if name and "amc" in name.lower() else f"{name} AMC"
            plan = SubscriptionPlanModel(
                name=amc_name,
                description=description or "",
                billing_cycle=coverage_type or "annual",
                price=annual_cost,
                benefits=(coverage_items or "") + extra,
                service_credits=0,
                discount_percentage=0,
                priority_booking=False,
                free_inspection=False,
                is_active=True,
            )
            db.session.add(plan)
            db.session.commit()
            return CreateAMCPlan(amc_plan=plan, success=True, message="AMC plan created successfully")
        except Exception as e:
            db.session.rollback()
            return CreateAMCPlan(amc_plan=None, success=False, message=str(e))

# ==================== SUBSCRIPTION MUTATIONS ====================
class CreateSubscription(graphene.Mutation):
    class Arguments:
        subscription_number = graphene.String(required=True)
        customer_id = graphene.String(required=True)
        customer_name = graphene.String(required=True)
        customer_email = graphene.String(required=True)
        plan_id = graphene.Int(required=True)
        start_date = graphene.String(required=True)
        end_date = graphene.String(required=True)
        total_amount = graphene.Float(required=True)

    subscription = graphene.Field(SubscriptionType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, subscription_number, customer_id, customer_name, customer_email,
               plan_id, start_date, end_date, total_amount):
        try:
            uid = int(str(customer_id).strip())
            subscription = SubscriptionModel(
                user_id=uid,
                plan_id=plan_id,
                start_date=_parse_iso_datetime(start_date),
                end_date=_parse_iso_datetime(end_date),
                next_billing_date=None,
                status="active",
                credits_remaining=0,
                credits_used=0,
            )
            db.session.add(subscription)
            db.session.commit()
            return CreateSubscription(subscription=subscription, success=True, message="Subscription created successfully")
        except Exception as e:
            db.session.rollback()
            return CreateSubscription(subscription=None, success=False, message=str(e))

# ==================== ASSET MUTATIONS ====================
class CreateAsset(graphene.Mutation):
    class Arguments:
        asset_number = graphene.String(required=True)
        customer_id = graphene.String(required=True)
        customer_name = graphene.String(required=True)
        customer_email = graphene.String(required=True)
        asset_name = graphene.String(required=True)
        asset_category = graphene.String(required=True)
        serial_number = graphene.String(required=True)
        asset_brand = graphene.String()
        asset_model = graphene.String()
        location = graphene.String()
        purchase_date = graphene.String()
        warranty_expiry_date = graphene.String()
        description = graphene.String()
        specifications = graphene.String()

    asset = graphene.Field(AssetType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, asset_number, customer_id, customer_name, customer_email,
               asset_name, asset_category, serial_number, **kwargs):
        try:
            asset = AssetModel(
                asset_number=asset_number, customer_id=customer_id, customer_name=customer_name,
                customer_email=customer_email, asset_name=asset_name, asset_category=asset_category,
                serial_number=serial_number, **kwargs
            )
            db.session.add(asset)
            db.session.commit()
            return CreateAsset(asset=asset, success=True, message="Asset created successfully")
        except Exception as e:
            db.session.rollback()
            return CreateAsset(asset=None, success=False, message=str(e))

class UpdateAsset(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        asset_name = graphene.String()
        location = graphene.String()
        status = graphene.String()

    asset = graphene.Field(AssetType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id, **kwargs):
        try:
            asset = AssetModel.query.get(id)
            if not asset:
                return UpdateAsset(asset=None, success=False, message="Asset not found")
            for key, value in kwargs.items():
                if value is not None:
                    setattr(asset, key, value)
            db.session.commit()
            return UpdateAsset(asset=asset, success=True, message="Asset updated")
        except Exception as e:
            db.session.rollback()
            return UpdateAsset(asset=None, success=False, message=str(e))

# ==================== TICKET MUTATIONS ====================
class CreateTicket(graphene.Mutation):
    class Arguments:
        ticket_number = graphene.String(required=True)
        customer_name = graphene.String(required=True)
        customer_email = graphene.String(required=True)
        customer_phone = graphene.String(required=True)
        issue_description = graphene.String(required=True)
        category_id = graphene.Int()
        priority = graphene.String()

    ticket = graphene.Field(TicketType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, ticket_number, customer_name, customer_email, customer_phone,
               issue_description, category_id=None, priority="medium"):
        try:
            user = UserModel.query.filter_by(email=customer_email).first()
            if not user:
                parts = (customer_name or "").strip().split(None, 1)
                fn = parts[0] if parts else ""
                ln = parts[1] if len(parts) > 1 else ""
                user = UserModel(
                    email=customer_email,
                    phone=customer_phone or "",
                    first_name=fn,
                    last_name=ln,
                    user_type="customer",
                    password_hash="",
                    loyalty_points=0,
                    is_active=True,
                )
                db.session.add(user)
                db.session.flush()
            note = issue_description or ""
            if category_id is not None:
                note = f"[categoryId={category_id}] [priority={priority}] " + note
            ticket = TicketModel(
                booking_number=ticket_number,
                customer_id=user.user_id,
                customer_notes=note,
                status="new",
                subtotal=0,
                discount_amount=0,
                total_amount=0,
                loyalty_points_used=0,
                loyalty_discount=0,
                loyalty_points_earned=0,
                is_subscription_booking=False,
            )
            db.session.add(ticket)
            db.session.commit()
            return CreateTicket(ticket=ticket, success=True, message="Ticket created successfully")
        except Exception as e:
            db.session.rollback()
            return CreateTicket(ticket=None, success=False, message=str(e))

class UpdateTicket(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        status = graphene.String()
        priority = graphene.String()
        assigned_to = graphene.Int()
        resolution_notes = graphene.String()

    ticket = graphene.Field(TicketType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id, **kwargs):
        try:
            ticket = TicketModel.query.get(id)
            if not ticket:
                return UpdateTicket(ticket=None, success=False, message="Ticket not found")
            for key, value in list(kwargs.items()):
                if value is None:
                    continue
                if key == "assigned_to":
                    ticket.technician_id = value
                elif key == "resolution_notes":
                    ticket.customer_notes = value
                elif key == "status":
                    ticket.status = value
                elif hasattr(ticket, key):
                    setattr(ticket, key, value)
            db.session.commit()
            return UpdateTicket(ticket=ticket, success=True, message="Ticket updated")
        except Exception as e:
            db.session.rollback()
            return UpdateTicket(ticket=None, success=False, message=str(e))

# ==================== ORDER COMPATIBILITY MUTATIONS ====================
class AssignTechnicianToOrder(graphene.Mutation):
    class Arguments:
        order_id = graphene.Int(required=True)
        technician_id = graphene.Int(required=True)

    ticket = graphene.Field(TicketType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, order_id, technician_id):
        try:
            ticket = TicketModel.query.get(order_id)
            if not ticket:
                return AssignTechnicianToOrder(ticket=None, success=False, message="Order not found")

            ticket.technician_id = technician_id
            if ticket.status in ("open", "new"):
                ticket.status = "assigned"
            db.session.commit()
            return AssignTechnicianToOrder(ticket=ticket, success=True, message="Technician assigned successfully")
        except Exception as e:
            db.session.rollback()
            return AssignTechnicianToOrder(ticket=None, success=False, message=str(e))


class EscalateOrder(graphene.Mutation):
    class Arguments:
        order_id = graphene.Int(required=True)
        reason = graphene.String(required=True)
        escalated_to = graphene.String(required=True)
        expected_resolution_time = graphene.Int()

    ticket = graphene.Field(TicketType)
    escalation = graphene.Field(EscalationType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, order_id, reason, escalated_to, expected_resolution_time=None):
        try:
            ticket = TicketModel.query.get(order_id)
            if not ticket:
                return EscalateOrder(ticket=None, escalation=None, success=False, message="Order not found")

            escalation = EscalationModel(
                ticket_id=order_id,
                reason=reason,
                escalated_to=escalated_to,
                expected_resolution_time=expected_resolution_time
            )
            ticket.status = "escalated"
            db.session.add(escalation)
            db.session.commit()
            return EscalateOrder(
                ticket=ticket,
                escalation=escalation,
                success=True,
                message="Order escalated successfully"
            )
        except Exception as e:
            db.session.rollback()
            return EscalateOrder(ticket=None, escalation=None, success=False, message=str(e))

# ==================== ESCALATION MUTATIONS ====================
class CreateEscalation(graphene.Mutation):
    class Arguments:
        ticket_id = graphene.Int(required=True)
        reason = graphene.String(required=True)
        escalated_to = graphene.String(required=True)
        expected_resolution_time = graphene.Int()

    escalation = graphene.Field(EscalationType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, ticket_id, reason, escalated_to, expected_resolution_time=None):
        try:
            escalation = EscalationModel(
                ticket_id=ticket_id, reason=reason, escalated_to=escalated_to,
                expected_resolution_time=expected_resolution_time
            )
            db.session.add(escalation)
            db.session.commit()
            return CreateEscalation(escalation=escalation, success=True, message="Escalation created successfully")
        except Exception as e:
            db.session.rollback()
            return CreateEscalation(escalation=None, success=False, message=str(e))

# ==================== SERVICE BOOKING MUTATIONS ====================
class CreateServiceBooking(graphene.Mutation):
    class Arguments:
        booking_number = graphene.String(required=True)
        asset_id = graphene.Int(required=True)
        customer_id = graphene.String(required=True)
        customer_name = graphene.String(required=True)
        customer_email = graphene.String(required=True)
        customer_phone = graphene.String(required=True)
        service_type = graphene.String(required=True)
        scheduled_date = graphene.String(required=True)
        scheduled_time_slot = graphene.String()
        estimated_cost = graphene.Float()

    service_booking = graphene.Field(ServiceBookingType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, booking_number, asset_id, customer_id, customer_name,
               customer_email, customer_phone, service_type, scheduled_date,
               scheduled_time_slot=None, estimated_cost=None):
        try:
            uid = int(str(customer_id).strip())
            user = UserModel.query.get(uid)
            if not user:
                parts = (customer_name or "").strip().split(None, 1)
                fn = parts[0] if parts else ""
                ln = parts[1] if len(parts) > 1 else ""
                user = UserModel(
                    email=customer_email,
                    phone=customer_phone or "",
                    first_name=fn,
                    last_name=ln,
                    user_type="customer",
                    password_hash="",
                    loyalty_points=0,
                    is_active=True,
                )
                db.session.add(user)
                db.session.flush()
                uid = user.user_id
            note = (
                f"[graphql service booking] service_type={service_type} "
                f"asset_id={asset_id} scheduled={scheduled_date} slot={scheduled_time_slot}"
            )
            tot = float(estimated_cost or 0)
            booking = ServiceBookingModel(
                booking_number=booking_number,
                customer_id=uid,
                customer_notes=note,
                status="new",
                subtotal=tot,
                total_amount=tot,
                discount_amount=0,
                loyalty_points_used=0,
                loyalty_discount=0,
                loyalty_points_earned=0,
                is_subscription_booking=False,
                service_address=customer_phone or "",
            )
            db.session.add(booking)
            db.session.commit()
            return CreateServiceBooking(service_booking=booking, success=True, message="Service booking created successfully")
        except Exception as e:
            db.session.rollback()
            return CreateServiceBooking(service_booking=None, success=False, message=str(e))

class UpdateServiceBooking(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        service_status = graphene.String()
        technician_id = graphene.Int()
        actual_cost = graphene.Float()
        service_notes = graphene.String()
        customer_rating = graphene.Int()
        customer_feedback = graphene.String()

    service_booking = graphene.Field(ServiceBookingType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id, **kwargs):
        try:
            booking = ServiceBookingModel.query.get(id)
            if not booking:
                return UpdateServiceBooking(service_booking=None, success=False, message="Booking not found")
            for key, value in list(kwargs.items()):
                if value is None:
                    continue
                if key == "service_status":
                    booking.status = value
                elif key == "technician_id":
                    booking.technician_id = value
                elif key == "service_notes":
                    booking.customer_notes = (booking.customer_notes or "") + "\n" + str(value)
                elif hasattr(booking, key):
                    setattr(booking, key, value)
            db.session.commit()
            return UpdateServiceBooking(service_booking=booking, success=True, message="Service booking updated")
        except Exception as e:
            db.session.rollback()
            return UpdateServiceBooking(service_booking=None, success=False, message=str(e))

# ==================== WARRANTY TRACKING MUTATIONS ====================
class CreateWarrantyTracking(graphene.Mutation):
    class Arguments:
        asset_id = graphene.Int(required=True)
        warranty_type = graphene.String(required=True)
        warranty_start_date = graphene.String(required=True)
        warranty_end_date = graphene.String(required=True)
        coverage_details = graphene.String()
        warranty_provider = graphene.String()
        claim_limit = graphene.Float()

    warranty = graphene.Field(WarrantyTrackingType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, asset_id, warranty_type, warranty_start_date, warranty_end_date, **kwargs):
        try:
            warranty = WarrantyTrackingModel(
                asset_id=asset_id,
                warranty_type=warranty_type,
                warranty_start_date=_parse_iso_datetime(warranty_start_date),
                warranty_end_date=_parse_iso_datetime(warranty_end_date),
                **kwargs,
            )
            db.session.add(warranty)
            db.session.commit()
            return CreateWarrantyTracking(warranty=warranty, success=True, message="Warranty tracking created successfully")
        except Exception as e:
            db.session.rollback()
            return CreateWarrantyTracking(warranty=None, success=False, message=str(e))

# ==================== COMPLIANCE RECORD MUTATIONS ====================
class CreateComplianceRecord(graphene.Mutation):
    class Arguments:
        technician_id = graphene.Int(required=True)
        compliance_type = graphene.String(required=True)
        description = graphene.String()
        issued_date = graphene.String(required=True)
        expiry_date = graphene.String()
        certification_document = graphene.String()

    compliance_record = graphene.Field(ComplianceRecordType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(
        self,
        info,
        technician_id,
        compliance_type,
        issued_date,
        description=None,
        expiry_date=None,
        certification_document=None,
    ):
        try:
            record = ComplianceRecordModel(
                technician_id=technician_id,
                compliance_type=compliance_type,
                description=description,
                issued_date=_parse_iso_datetime(issued_date),
                expiry_date=_parse_iso_datetime(expiry_date) if expiry_date else None,
                certification_document=certification_document,
            )
            db.session.add(record)
            db.session.commit()
            return CreateComplianceRecord(compliance_record=record, success=True, message="Compliance record created successfully")
        except Exception as e:
            db.session.rollback()
            return CreateComplianceRecord(compliance_record=None, success=False, message=str(e))
