import json
import secrets
import enum
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class ABTestVariant(enum.Enum):
    CONTROL = "control"
    HYBRID_RERANK = "hybrid_rerank"
    COLLABORATIVE = "collaborative"
    DIVERSITY_BOOST = "diversity_boost"

class FeedbackType(enum.Enum):
    IMPLICIT_CLICK = "implicit_click"
    IMPLICIT_DWELL = "implicit_dwell"
    IMPLICIT_ENROLL = "implicit_enroll"
    EXPLICIT_LIKE = "explicit_like"
    EXPLICIT_DISLIKE = "explicit_dislike"
    EXPLICIT_NOT_RELEVANT = "explicit_not_relevant"

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


# =============================================================================
# NEW MODELS FOR ADVANCED RECOMMENDATION SYSTEM
# =============================================================================

class UserFeedback(db.Model):
    """Explicit and implicit feedback for recommendation learning."""
    __tablename__ = 'user_feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    feedback_type = db.Column(db.String(50), nullable=False, index=True)  # FeedbackType enum
    value = db.Column(db.Float, default=1.0)  # -1.0 to 1.0 for explicit, duration for implicit
    context_json = db.Column(db.Text, nullable=True)  # Additional context
    session_id = db.Column(db.String(100), nullable=True, index=True)
    recommendation_id = db.Column(db.Integer, db.ForeignKey('recommendations.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    user = db.relationship('User', backref='feedback')
    product = db.relationship('Product', backref='feedback')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'product_id': self.product_id,
            'feedback_type': self.feedback_type,
            'value': self.value,
            'context': json.loads(self.context_json) if self.context_json else {},
            'session_id': self.session_id,
            'recommendation_id': self.recommendation_id,
            'created_at': self.created_at.isoformat()
        }


class ABTestAssignment(db.Model):
    """A/B test variant assignments for users."""
    __tablename__ = 'ab_test_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    experiment_name = db.Column(db.String(100), nullable=False, index=True)
    variant = db.Column(db.String(50), nullable=False)  # ABTestVariant enum
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='ab_assignments')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'experiment_name', name='unique_user_experiment'),)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'experiment_name': self.experiment_name,
            'variant': self.variant,
            'assigned_at': self.assigned_at.isoformat()
        }


class UserProfile(db.Model):
    """Extended user profile for collaborative filtering and cold-start."""
    __tablename__ = 'user_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    
    # Onboarding quiz responses
    quiz_responses_json = db.Column(db.Text, nullable=True)  # {interest_areas, skill_level, goals, time_commitment}
    
    # Learned preferences (updated incrementally)
    category_affinity_json = db.Column(db.Text, nullable=True)  # {category: weight}
    topic_affinity_json = db.Column(db.Text, nullable=True)  # {topic: weight}
    skill_level = db.Column(db.String(20), default='beginner')  # beginner, intermediate, advanced
    learning_goals_json = db.Column(db.Text, nullable=True)  # List of goal strings
    
    # Collaborative filtering vectors
    user_vector_json = db.Column(db.Text, nullable=True)  # Latent factor vector
    vector_updated_at = db.Column(db.DateTime, nullable=True)
    
    # Engagement metrics
    total_events = db.Column(db.Integer, default=0)
    total_recommendations_shown = db.Column(db.Integer, default=0)
    total_clicks = db.Column(db.Integer, default=0)
    total_enrollments = db.Column(db.Integer, default=0)
    ctr = db.Column(db.Float, default=0.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('profile', uselist=False))

    def get_quiz_responses(self):
        try:
            return json.loads(self.quiz_responses_json) if self.quiz_responses_json else {}
        except Exception:
            return {}

    def get_category_affinity(self):
        try:
            return json.loads(self.category_affinity_json) if self.category_affinity_json else {}
        except Exception:
            return {}

    def get_topic_affinity(self):
        try:
            return json.loads(self.topic_affinity_json) if self.topic_affinity_json else {}
        except Exception:
            return {}

    def get_learning_goals(self):
        try:
            return json.loads(self.learning_goals_json) if self.learning_goals_json else []
        except Exception:
            return []

    def get_user_vector(self):
        try:
            return json.loads(self.user_vector_json) if self.user_vector_json else []
        except Exception:
            return []

    def set_user_vector(self, vector: list):
        self.user_vector_json = json.dumps(vector)
        self.vector_updated_at = datetime.utcnow()

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'quiz_responses': self.get_quiz_responses(),
            'category_affinity': self.get_category_affinity(),
            'topic_affinity': self.get_topic_affinity(),
            'skill_level': self.skill_level,
            'learning_goals': self.get_learning_goals(),
            'engagement': {
                'total_events': self.total_events,
                'recommendations_shown': self.total_recommendations_shown,
                'clicks': self.total_clicks,
                'enrollments': self.total_enrollments,
                'ctr': self.ctr
            },
            'has_vector': bool(self.user_vector_json),
            'vector_updated_at': self.vector_updated_at.isoformat() if self.vector_updated_at else None
        }


class ProductSimilarity(db.Model):
    """Precomputed item-item similarities for collaborative filtering."""
    __tablename__ = 'product_similarities'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    similar_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    similarity_score = db.Column(db.Float, nullable=False)
    similarity_type = db.Column(db.String(50), nullable=False)  # content, collaborative, hybrid
    computed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', foreign_keys=[product_id], backref='similarities')
    similar_product = db.relationship('Product', foreign_keys=[similar_product_id])
    
    __table_args__ = (db.UniqueConstraint('product_id', 'similar_product_id', 'similarity_type', name='unique_product_similarity'),)

    def to_dict(self):
        return {
            'product_id': self.product_id,
            'similar_product_id': self.similar_product_id,
            'similarity_score': self.similarity_score,
            'similarity_type': self.similarity_type,
            'computed_at': self.computed_at.isoformat()
        }


class RecommendationImpression(db.Model):
    """Track recommendation impressions for CTR calculation and learning."""
    __tablename__ = 'recommendation_impressions'
    
    id = db.Column(db.Integer, primary_key=True)
    recommendation_id = db.Column(db.Integer, db.ForeignKey('recommendations.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_ids_json = db.Column(db.Text, nullable=False)  # JSON list of shown product IDs
    positions_json = db.Column(db.Text, nullable=True)  # JSON list of positions
    experiment_variant = db.Column(db.String(50), nullable=True)
    shown_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    clicked_product_id = db.Column(db.Integer, nullable=True)  # Which product was clicked (if any)
    click_position = db.Column(db.Integer, nullable=True)
    clicked_at = db.Column(db.DateTime, nullable=True)
    
    recommendation = db.relationship('Recommendation', backref='impressions')
    user = db.relationship('User', backref='reco_impressions')

    def get_product_ids(self):
        try:
            return json.loads(self.product_ids_json)
        except Exception:
            return []

    def to_dict(self):
        return {
            'id': self.id,
            'recommendation_id': self.recommendation_id,
            'user_id': self.user_id,
            'product_ids': self.get_product_ids(),
            'experiment_variant': self.experiment_variant,
            'shown_at': self.shown_at.isoformat(),
            'clicked_product_id': self.clicked_product_id,
            'click_position': self.click_position,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None
        }


class RankingModel(db.Model):
    """Stored LightGBM ranking model metadata."""
    __tablename__ = 'ranking_models'
    
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(50), nullable=False, unique=True)
    model_path = db.Column(db.String(500), nullable=False)
    feature_names_json = db.Column(db.Text, nullable=False)
    metrics_json = db.Column(db.Text, nullable=True)  # NDCG, MRR, etc.
    training_samples = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    activated_at = db.Column(db.DateTime, nullable=True)

    def get_feature_names(self):
        try:
            return json.loads(self.feature_names_json)
        except Exception:
            return []

    def get_metrics(self):
        try:
            return json.loads(self.metrics_json) if self.metrics_json else {}
        except Exception:
            return {}

    def to_dict(self):
        return {
            'id': self.id,
            'version': self.version,
            'model_path': self.model_path,
            'feature_names': self.get_feature_names(),
            'metrics': self.get_metrics(),
            'training_samples': self.training_samples,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'activated_at': self.activated_at.isoformat() if self.activated_at else None
        }
