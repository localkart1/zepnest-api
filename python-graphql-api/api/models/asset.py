from api import db
from datetime import datetime

class Asset(db.Model):
    __tablename__ = 'assets'

    id = db.Column(db.Integer, primary_key=True)
    asset_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.String(120), nullable=False)
    customer_name = db.Column(db.String(120), nullable=False)
    customer_email = db.Column(db.String(120), nullable=False)
    asset_name = db.Column(db.String(255), nullable=False)
    asset_category = db.Column(db.String(120), nullable=False)
    asset_brand = db.Column(db.String(120))
    asset_model = db.Column(db.String(120))
    serial_number = db.Column(db.String(120), unique=True, nullable=False)
    location = db.Column(db.String(255))
    purchase_date = db.Column(db.DateTime)
    warranty_expiry_date = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='active')  # active, inactive, decommissioned
    description = db.Column(db.Text)
    specifications = db.Column(db.Text)  # JSON stored as text
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    warranty_records = db.relationship('WarrantyTracking', backref='asset', lazy=True, cascade='all, delete-orphan')
    service_mappings = db.relationship('AssetServiceMapping', backref='asset', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Asset {self.asset_number}>'

class AssetRegistry(db.Model):
    __tablename__ = 'asset_registry'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    registration_number = db.Column(db.String(50), unique=True, nullable=False)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='registered')  # registered, pending, rejected
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    asset = db.relationship('Asset', backref='registry', lazy=True)

    def __repr__(self):
        return f'<AssetRegistry {self.registration_number}>'

class WarrantyTracking(db.Model):
    __tablename__ = 'warranty_tracking'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    warranty_type = db.Column(db.String(50), nullable=False)  # manufacturer, extended, amc
    warranty_start_date = db.Column(db.DateTime, nullable=False)
    warranty_end_date = db.Column(db.DateTime, nullable=False)
    coverage_details = db.Column(db.Text)
    warranty_provider = db.Column(db.String(120))
    claim_limit = db.Column(db.Float)
    claims_made = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<WarrantyTracking {self.id}>'

class AssetServiceMapping(db.Model):
    __tablename__ = 'asset_service_mapping'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    service_category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    service_sub_category_id = db.Column(db.Integer, db.ForeignKey('sub_categories.id'), nullable=True)
    recommended_service_interval = db.Column(db.Integer)  # in days or months
    last_service_date = db.Column(db.DateTime)
    next_service_date = db.Column(db.DateTime)
    service_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    service_category = db.relationship('Category')
    service_sub_category = db.relationship('SubCategory')

    def __repr__(self):
        return f'<AssetServiceMapping {self.id}>'
