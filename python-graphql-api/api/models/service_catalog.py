from api import db
from datetime import datetime

class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(255))  # URL or icon identifier
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sub_categories = db.relationship('SubCategory', backref='category', lazy=True, cascade='all, delete-orphan')
    price_mappings = db.relationship('PriceMapping', backref='category', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Category {self.name}>'

class SubCategory(db.Model):
    __tablename__ = 'sub_categories'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    price_mappings = db.relationship('PriceMapping', backref='sub_category', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (db.UniqueConstraint('category_id', 'name', name='unique_category_subcategory'),)

    def __repr__(self):
        return f'<SubCategory {self.name}>'

class PriceMapping(db.Model):
    __tablename__ = 'price_mappings'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    sub_category_id = db.Column(db.Integer, db.ForeignKey('sub_categories.id'), nullable=True)
    service_name = db.Column(db.String(255), nullable=False)
    service_type = db.Column(db.String(50), nullable=False)  # labor, parts, service
    base_price = db.Column(db.Float, nullable=False)
    gst_percentage = db.Column(db.Float, default=18.0)
    total_price = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(50), default='per service')  # per service, per hour, per item
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PriceMapping {self.service_name}>'
