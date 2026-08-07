import json
import secrets
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'user' or 'admin'
    otp_code = db.Column(db.String(6), nullable=True)
    is_verified = db.Column(db.Boolean, default=True)  # Admin & pre-seeded users verified by default
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    events = db.relationship('Event', backref='user', lazy=True, cascade="all, delete-orphan")
    recommendations = db.relationship('Recommendation', backref='user', lazy=True, cascade="all, delete-orphan")
    digests = db.relationship('DigestLog', backref='user', lazy=True, cascade="all, delete-orphan")
    enrollments = db.relationship('Enrollment', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_otp(self):
        """Generates a secure 6-digit OTP code for email verification."""
        self.otp_code = f"{secrets.randbelow(900000) + 100000}"
        self.is_verified = False
        return self.otp_code

    def verify_otp(self, input_otp):
        """Verifies the user-entered 6-digit OTP code."""
        if self.otp_code and self.otp_code.strip() == str(input_otp).strip():
            self.is_verified = True
            self.otp_code = None
            return True
        return False
        
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'role': self.role,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat()
        }

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'product_id': self.product_id,
            'product': self.product.to_dict() if self.product else None,
            'enrolled_at': self.enrolled_at.isoformat()
        }

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    tags = db.Column(db.String(250), nullable=True)  # comma separated
    rating = db.Column(db.Float, default=4.8)
    image_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'price': self.price,
            'tags': [t.strip() for t in self.tags.split(',')] if self.tags else [],
            'rating': self.rating,
            'image_url': self.image_url or f"https://picsum.photos/seed/prod_{self.id}/400/250",
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Event(db.Model):
    __tablename__ = 'events'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True) # e.g. page_view, product_view, search, dwell_time, click_recommendation
    target_id = db.Column(db.String(100), nullable=True) # e.g. product_id or category name
    details_json = db.Column(db.Text, nullable=True)
    duration_ms = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def get_details(self):
        try:
            return json.loads(self.details_json) if self.details_json else {}
        except Exception:
            return {}

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'event_type': self.event_type,
            'target_id': self.target_id,
            'details': self.get_details(),
            'duration_ms': self.duration_ms,
            'timestamp': self.timestamp.isoformat()
        }

class Recommendation(db.Model):
    __tablename__ = 'recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    narrative = db.Column(db.Text, nullable=False)
    recommended_product_ids_json = db.Column(db.Text, nullable=False) # JSON list of product IDs
    trigger_reason = db.Column(db.String(200), nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_product_ids(self):
        try:
            return json.loads(self.recommended_product_ids_json)
        except Exception:
            return []

    def get_metadata(self):
        try:
            return json.loads(self.metadata_json) if self.metadata_json else {}
        except Exception:
            return {}

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'narrative': self.narrative,
            'product_ids': self.get_product_ids(),
            'trigger_reason': self.trigger_reason,
            'metadata': self.get_metadata(),
            'created_at': self.created_at.isoformat()
        }

class DigestLog(db.Model):
    __tablename__ = 'digest_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    recipient_email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    content_html = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='sent')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'recipient_email': self.recipient_email,
            'subject': self.subject,
            'content_html': self.content_html,
            'sent_at': self.sent_at.isoformat(),
            'status': self.status
        }
