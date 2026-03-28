import graphene
from flask import Blueprint, request, jsonify
from sqlalchemy import or_
from sqlalchemy.exc import ProgrammingError

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
    EscalationType, ComplianceRecordType, PaginatedTechnicianType, PaginatedAssetType, PaginatedOrderType
)
from api.graphql.catalog_fallback import (
    category_from_services_by_graphql_id,
    is_missing_relation_error,
    run_or_empty_list,
    run_or_none_price_mapping,
    run_or_none_subcategory,
    run_or_services_categories,
)
from api.graphql.mutations import (
    CreateUser, UpdateUser, DeleteUser, CreatePost,
    CreateTechnician, UpdateTechnician, DeleteTechnician,
    CreateCategory, UpdateCategory, DeleteCategory,
    CreateSubCategory, UpdateSubCategory,
    CreatePriceMapping, UpdatePriceMapping,
    CreateSubscriptionPlan, UpdateSubscriptionPlan,
    CreateAMCPlan,
    CreateSubscription,
    CreateAsset, UpdateAsset,
    CreateTicket, UpdateTicket,
    CreateEscalation,
    CreateServiceBooking, UpdateServiceBooking,
    CreateWarrantyTracking,
    CreateComplianceRecord,
    AssignTechnicianToOrder, EscalateOrder
)

class Query(graphene.ObjectType):
    # User & Post Queries
    users = graphene.List(UserType)
    user = graphene.Field(UserType, id=graphene.Int(required=True))
    posts = graphene.List(PostType)
    post = graphene.Field(PostType, id=graphene.Int(required=True))

    # Technician Queries
    technicians = graphene.List(TechnicianType)
    technicians_paginated = graphene.Field(
        PaginatedTechnicianType,
        page=graphene.Int(default_value=1),
        limit=graphene.Int(default_value=10),
        search=graphene.String(),
        status=graphene.String()
    )
    technician = graphene.Field(TechnicianType, id=graphene.Int(required=True))
    technicians_by_status = graphene.List(TechnicianType, status=graphene.String())
    technicians_by_specialization = graphene.List(TechnicianType, specialization=graphene.String())

    # Category & SubCategory Queries
    categories = graphene.List(CategoryType)
    category = graphene.Field(CategoryType, id=graphene.Int(required=True))
    sub_categories = graphene.List(SubCategoryType)
    sub_categories_by_category = graphene.List(SubCategoryType, category_id=graphene.Int(required=True))
    sub_category = graphene.Field(SubCategoryType, id=graphene.Int(required=True))

    # Price Mapping Queries
    price_mappings = graphene.List(PriceMappingType)
    price_mappings_by_category = graphene.List(PriceMappingType, category_id=graphene.Int(required=True))
    price_mapping = graphene.Field(PriceMappingType, id=graphene.Int(required=True))

    # Subscription Plan Queries
    subscription_plans = graphene.List(SubscriptionPlanType)
    subscription_plan = graphene.Field(SubscriptionPlanType, id=graphene.Int(required=True))
    active_subscription_plans = graphene.List(SubscriptionPlanType)

    # AMC Plan Queries
    amc_plans = graphene.List(AMCPlanType)
    amc_plan = graphene.Field(AMCPlanType, id=graphene.Int(required=True))
    active_amc_plans = graphene.List(AMCPlanType)

    # Subscription Queries
    subscriptions = graphene.List(SubscriptionType)
    subscription = graphene.Field(SubscriptionType, id=graphene.Int(required=True))
    subscriptions_by_customer = graphene.List(SubscriptionType, customer_id=graphene.String(required=True))
    subscriptions_by_status = graphene.List(SubscriptionType, status=graphene.String(required=True))

    # AMC Subscription Queries
    amc_subscriptions = graphene.List(AMCSubscriptionType)
    amc_subscriptions_by_asset = graphene.List(AMCSubscriptionType, asset_id=graphene.Int(required=True))
    amc_subscriptions_by_customer = graphene.List(AMCSubscriptionType, customer_id=graphene.String(required=True))

    # Asset Queries
    assets = graphene.List(AssetType)
    assets_paginated = graphene.Field(
        PaginatedAssetType,
        page=graphene.Int(default_value=1),
        limit=graphene.Int(default_value=10),
        search=graphene.String(),
        status=graphene.String(),
        category=graphene.String(),
        zip_code=graphene.String()
    )
    asset = graphene.Field(AssetType, id=graphene.Int(required=True))
    assets_by_customer = graphene.List(AssetType, customer_id=graphene.String(required=True))
    assets_by_category = graphene.List(AssetType, asset_category=graphene.String(required=True))

    # Asset Registry Queries
    asset_registries = graphene.List(AssetRegistryType)
    asset_registry = graphene.Field(AssetRegistryType, id=graphene.Int(required=True))

    # Warranty Tracking Queries
    warranty_records = graphene.List(WarrantyTrackingType)
    warranty_by_asset = graphene.List(WarrantyTrackingType, asset_id=graphene.Int(required=True))

    # Asset Service Mapping Queries
    asset_service_mappings = graphene.List(AssetServiceMappingType)
    asset_service_mappings_by_asset = graphene.List(AssetServiceMappingType, asset_id=graphene.Int(required=True))

    # Ticket Queries
    tickets = graphene.List(TicketType)
    ticket = graphene.Field(TicketType, id=graphene.Int(required=True))
    orders = graphene.List(TicketType)
    order = graphene.Field(TicketType, id=graphene.Int(required=True))
    orders_paginated = graphene.Field(
        PaginatedOrderType,
        page=graphene.Int(default_value=1),
        limit=graphene.Int(default_value=10),
        search=graphene.String(),
        status=graphene.String()
    )
    tickets_by_status = graphene.List(TicketType, status=graphene.String(required=True))
    tickets_by_priority = graphene.List(TicketType, priority=graphene.String(required=True))
    tickets_by_technician = graphene.List(TicketType, assigned_to=graphene.Int(required=True))

    # Service Booking Queries
    service_bookings = graphene.List(ServiceBookingType)
    service_booking = graphene.Field(ServiceBookingType, id=graphene.Int(required=True))
    service_bookings_by_asset = graphene.List(ServiceBookingType, asset_id=graphene.Int(required=True))
    service_bookings_by_status = graphene.List(ServiceBookingType, service_status=graphene.String(required=True))

    # Escalation Queries
    escalations = graphene.List(EscalationType)
    escalations_by_ticket = graphene.List(EscalationType, ticket_id=graphene.Int(required=True))

    # Compliance Record Queries
    compliance_records = graphene.List(ComplianceRecordType)
    compliance_by_technician = graphene.List(ComplianceRecordType, technician_id=graphene.Int(required=True))

    # Resolvers
    def resolve_users(self, info):
        return UserModel.query.all()

    def resolve_user(self, info, id):
        return UserModel.query.get(id)

    def resolve_posts(self, info):
        return PostModel.query.all()

    def resolve_post(self, info, id):
        return PostModel.query.get(id)

    def resolve_technicians(self, info):
        return TechnicianModel.query.all()

    def resolve_technicians_paginated(self, info, page=1, limit=10, search=None, status=None):
        query = TechnicianModel.query
        if status:
            query = query.filter_by(status=status)
        if search:
            s = f"%{search}%"
            query = query.join(UserModel, TechnicianModel.user_id == UserModel.user_id).filter(
                or_(
                    UserModel.first_name.ilike(s),
                    UserModel.last_name.ilike(s),
                    UserModel.email.ilike(s),
                    UserModel.phone.ilike(s),
                    TechnicianModel.specialization.ilike(s),
                )
            )

        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()
        return PaginatedTechnicianType(items=items, total=total, page=page, limit=limit)

    def resolve_technician(self, info, id):
        return TechnicianModel.query.get(id)

    def resolve_technicians_by_status(self, info, status):
        return TechnicianModel.query.filter_by(status=status).all()

    def resolve_technicians_by_specialization(self, info, specialization):
        return TechnicianModel.query.filter_by(specialization=specialization).all()

    def resolve_categories(self, info):
        return run_or_services_categories(lambda: CategoryModel.query.all())

    def resolve_category(self, info, id):
        try:
            row = CategoryModel.query.get(id)
        except ProgrammingError as e:
            if is_missing_relation_error(e):
                return category_from_services_by_graphql_id(id)
            raise
        if row is not None:
            return row
        return category_from_services_by_graphql_id(id)

    def resolve_sub_categories(self, info):
        return run_or_empty_list(lambda: SubCategoryModel.query.all())

    def resolve_sub_categories_by_category(self, info, category_id):
        return run_or_empty_list(lambda: SubCategoryModel.query.filter_by(category_id=category_id).all())

    def resolve_sub_category(self, info, id):
        return run_or_none_subcategory(lambda: SubCategoryModel.query.get(id), id)

    def resolve_price_mappings(self, info):
        return run_or_empty_list(lambda: PriceMappingModel.query.all())

    def resolve_price_mappings_by_category(self, info, category_id):
        return run_or_empty_list(lambda: PriceMappingModel.query.filter_by(category_id=category_id).all())

    def resolve_price_mapping(self, info, id):
        return run_or_none_price_mapping(lambda: PriceMappingModel.query.get(id), id)

    def resolve_subscription_plans(self, info):
        return SubscriptionPlanModel.query.all()

    def resolve_subscription_plan(self, info, id):
        return SubscriptionPlanModel.query.get(id)

    def resolve_active_subscription_plans(self, info):
        return SubscriptionPlanModel.query.filter_by(is_active=True).all()

    def resolve_amc_plans(self, info):
        return (
            SubscriptionPlanModel.query.filter(
                SubscriptionPlanModel.name.ilike("%amc%")
            ).all()
        )

    def resolve_amc_plan(self, info, id):
        row = SubscriptionPlanModel.query.get(id)
        if row and row.name and "amc" in row.name.lower():
            return row
        return None

    def resolve_active_amc_plans(self, info):
        return (
            SubscriptionPlanModel.query.filter(
                SubscriptionPlanModel.is_active.is_(True),
                SubscriptionPlanModel.name.ilike("%amc%"),
            ).all()
        )

    def resolve_subscriptions(self, info):
        return SubscriptionModel.query.all()

    def resolve_subscription(self, info, id):
        return SubscriptionModel.query.get(id)

    def resolve_subscriptions_by_customer(self, info, customer_id):
        uid = int(str(customer_id).strip())
        return SubscriptionModel.query.filter_by(user_id=uid).all()

    def resolve_subscriptions_by_status(self, info, status):
        return SubscriptionModel.query.filter_by(status=status).all()

    def resolve_amc_subscriptions(self, info):
        q = (
            SubscriptionModel.query.join(SubscriptionPlanModel)
            .filter(SubscriptionPlanModel.name.ilike("%amc%"))
        )
        return q.all()

    def resolve_amc_subscriptions_by_asset(self, info, asset_id):
        # DB has no asset on user_subscriptions; align with REST (empty asset).
        return []

    def resolve_amc_subscriptions_by_customer(self, info, customer_id):
        uid = int(str(customer_id).strip())
        q = (
            SubscriptionModel.query.join(SubscriptionPlanModel)
            .filter(
                SubscriptionModel.user_id == uid,
                SubscriptionPlanModel.name.ilike("%amc%"),
            )
        )
        return q.all()

    def resolve_assets(self, info):
        return AssetModel.query.all()

    def resolve_assets_paginated(self, info, page=1, limit=10, search=None, status=None, category=None, zip_code=None):
        query = AssetModel.query
        if category:
            query = query.filter_by(asset_category=category)
        if search:
            s = f"%{search}%"
            query = query.filter(
                (AssetModel.customer_name.ilike(s)) |
                (AssetModel.asset_name.ilike(s)) |
                (AssetModel.asset_brand.ilike(s)) |
                (AssetModel.asset_model.ilike(s))
            )

        items = query.all()
        if status:
            is_active = status == "active"
            items = [a for a in items if (a.status == "active") == is_active]
        if zip_code:
            items = [a for a in items if a.location and zip_code in a.location]

        total = len(items)
        start = (page - 1) * limit
        paged_items = items[start:start + limit]
        return PaginatedAssetType(items=paged_items, total=total, page=page, limit=limit)

    def resolve_asset(self, info, id):
        return AssetModel.query.get(id)

    def resolve_assets_by_customer(self, info, customer_id):
        return AssetModel.query.filter_by(customer_id=customer_id).all()

    def resolve_assets_by_category(self, info, asset_category):
        return AssetModel.query.filter_by(asset_category=asset_category).all()

    def resolve_asset_registries(self, info):
        return AssetRegistryModel.query.all()

    def resolve_asset_registry(self, info, id):
        return AssetRegistryModel.query.get(id)

    def resolve_warranty_records(self, info):
        return WarrantyTrackingModel.query.all()

    def resolve_warranty_by_asset(self, info, asset_id):
        return WarrantyTrackingModel.query.filter_by(asset_id=asset_id).all()

    def resolve_asset_service_mappings(self, info):
        return AssetServiceMappingModel.query.all()

    def resolve_asset_service_mappings_by_asset(self, info, asset_id):
        return AssetServiceMappingModel.query.filter_by(asset_id=asset_id).all()

    def resolve_tickets(self, info):
        return TicketModel.query.all()

    def resolve_orders(self, info):
        return TicketModel.query.all()

    def resolve_ticket(self, info, id):
        return TicketModel.query.get(id)

    def resolve_order(self, info, id):
        return TicketModel.query.get(id)

    def resolve_orders_paginated(self, info, page=1, limit=10, search=None, status=None):
        query = TicketModel.query
        if status:
            query = query.filter_by(status=status)
        if search:
            s = f"%{search}%"
            query = query.outerjoin(
                UserModel, TicketModel.customer_id == UserModel.user_id
            ).filter(
                or_(
                    TicketModel.booking_number.ilike(s),
                    UserModel.first_name.ilike(s),
                    UserModel.last_name.ilike(s),
                    UserModel.phone.ilike(s),
                    UserModel.email.ilike(s),
                    TicketModel.customer_notes.ilike(s),
                )
            )

        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()
        return PaginatedOrderType(items=items, total=total, page=page, limit=limit)

    def resolve_tickets_by_status(self, info, status):
        return TicketModel.query.filter_by(status=status).all()

    def resolve_tickets_by_priority(self, info, priority):
        token = f"[priority={priority}]"
        return TicketModel.query.filter(
            TicketModel.customer_notes.ilike(f"%{token}%")
        ).all()

    def resolve_tickets_by_technician(self, info, assigned_to):
        return TicketModel.query.filter_by(technician_id=assigned_to).all()

    def resolve_service_bookings(self, info):
        return ServiceBookingModel.query.all()

    def resolve_service_booking(self, info, id):
        return ServiceBookingModel.query.get(id)

    def resolve_service_bookings_by_asset(self, info, asset_id):
        needle = f"asset_id={asset_id}"
        return ServiceBookingModel.query.filter(
            ServiceBookingModel.customer_notes.ilike(f"%{needle}%")
        ).all()

    def resolve_service_bookings_by_status(self, info, service_status):
        return ServiceBookingModel.query.filter_by(status=service_status).all()

    def resolve_escalations(self, info):
        return EscalationModel.query.all()

    def resolve_escalations_by_ticket(self, info, ticket_id):
        return EscalationModel.query.filter_by(ticket_id=ticket_id).all()

    def resolve_compliance_records(self, info):
        return ComplianceRecordModel.query.all()

    def resolve_compliance_by_technician(self, info, technician_id):
        return ComplianceRecordModel.query.filter_by(technician_id=technician_id).all()

class Mutation(graphene.ObjectType):
    # User & Post mutations
    create_user = CreateUser.Field()
    update_user = UpdateUser.Field()
    delete_user = DeleteUser.Field()
    create_post = CreatePost.Field()

    # Technician mutations
    create_technician = CreateTechnician.Field()
    update_technician = UpdateTechnician.Field()
    delete_technician = DeleteTechnician.Field()

    # Category & SubCategory mutations
    create_category = CreateCategory.Field()
    update_category = UpdateCategory.Field()
    delete_category = DeleteCategory.Field()
    create_sub_category = CreateSubCategory.Field()
    update_sub_category = UpdateSubCategory.Field()

    # Price Mapping mutations
    create_price_mapping = CreatePriceMapping.Field()
    update_price_mapping = UpdatePriceMapping.Field()

    # Subscription Plan mutations
    create_subscription_plan = CreateSubscriptionPlan.Field()
    update_subscription_plan = UpdateSubscriptionPlan.Field()

    # AMC Plan mutations
    create_amc_plan = CreateAMCPlan.Field()

    # Subscription mutations
    create_subscription = CreateSubscription.Field()

    # Asset mutations
    create_asset = CreateAsset.Field()
    update_asset = UpdateAsset.Field()

    # Ticket mutations
    create_ticket = CreateTicket.Field()
    update_ticket = UpdateTicket.Field()
    assign_technician_to_order = AssignTechnicianToOrder.Field()
    escalate_order = EscalateOrder.Field()

    # Escalation mutations
    create_escalation = CreateEscalation.Field()

    # Service Booking mutations
    create_service_booking = CreateServiceBooking.Field()
    update_service_booking = UpdateServiceBooking.Field()

    # Warranty Tracking mutations
    create_warranty_tracking = CreateWarrantyTracking.Field()

    # Compliance Record mutations
    create_compliance_record = CreateComplianceRecord.Field()

schema = graphene.Schema(query=Query, mutation=Mutation)

# Create Blueprint for GraphQL
graphql_bp = Blueprint('graphql', __name__)

@graphql_bp.route('/graphql', methods=['GET', 'POST'])
def graphql_view():
    if request.method == 'GET':
        return graphiql_interface()

    data = request.get_json()
    if not data:
        return jsonify({'errors': [{'message': 'No query provided'}]}), 400

    result = schema.execute(
        data.get('query'),
        variable_values=data.get('variables'),
        operation_name=data.get('operationName')
    )

    response = {'data': result.data}
    if result.errors:
        response['errors'] = [{'message': str(error)} for error in result.errors]

    return jsonify(response)

@graphql_bp.route('/', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'API is running'})

def graphiql_interface():
    """Return GraphiQL HTML interface"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>GraphiQL</title>
        <style>
            body {
                height: 100vh;
                margin: 0;
                width: 100%;
                overflow: hidden;
                font-family: Arial, sans-serif;
            }
            #graphiql {
                height: 100vh;
            }
        </style>
        <script
            crossorigin
            src="https://unpkg.com/react@17/umd/react.production.min.js"
        ></script>
        <script
            crossorigin
            src="https://unpkg.com/react-dom@17/umd/react-dom.production.min.js"
        ></script>
        <link rel="stylesheet" href="https://unpkg.com/graphiql@2.4.0/graphiql.min.css" />
    </head>
    <body>
        <div id="graphiql">Loading...</div>
        <script
            src="https://unpkg.com/graphiql@2.4.0/graphiql.min.js"
            type="application/javascript"
        ></script>
        <script>
            React.createElement(GraphiQL, { fetcher: graphQLFetcher }),
            document.getElementById('graphiql'),
        );

        function graphQLFetcher(graphQLParams) {
            return fetch('/graphql', {
                method: 'post',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(graphQLParams),
            }).then(response => response.json());
        }

        var root = ReactDOM.createRoot(document.getElementById('graphiql'));
        root.render(
            React.createElement(GraphiQL, {
                fetcher: graphQLFetcher,
                defaultQuery: '# Welcome to GraphiQL\\n# Try a query:\\n\\nquery {\\n  users {\\n    id\\n    firstName\\n    lastName\\n    email\\n    phone\\n    userType\\n  }\\n}'
            })
        );
    </script>
    </body>
    </html>
    '''
