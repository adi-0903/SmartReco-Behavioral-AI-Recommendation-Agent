import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session

from config import Config
from models import db, User, Product, Event, Recommendation, DigestLog
from vector_store import vector_store
from agent.workflow import recommendation_engine
from agent.observability import get_all_traces, get_trace_by_id
from scheduler import init_scheduler, generate_proactive_digests_job
from seed_data import seed_database

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

# Session helper functions
def get_current_user():
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None

def is_admin():
    user = get_current_user()
    return user and user.role == 'admin'

@app.before_request
def setup_app_context():
    # Ensure tables exist and seed data on first request
    if not getattr(app, '_db_initialized', False):
        db.create_all()
        try:
            seed_database()
        except Exception as e:
            logger.error(f"Error during DB seeding: {e}")
        try:
            init_scheduler(app)
        except Exception as e:
            logger.error(f"Error initializing scheduler: {e}")
        app._db_initialized = True

# --- MARKETPLACE & CATALOG ROUTES ---

@app.route('/')
def index():
    current_user = get_current_user()
    search_query = request.args.get('q', '').strip()
    selected_category = request.args.get('cat', 'All').strip()

    # Query products from SQL database
    query = Product.query
    if selected_category and selected_category != 'All':
        query = query.filter_by(category=selected_category)
    if search_query:
        query = query.filter(
            (Product.title.like(f"%{search_query}%")) |
            (Product.description.like(f"%{search_query}%")) |
            (Product.tags.like(f"%{search_query}%"))
        )
    products = query.order_by(Product.id.desc()).all()

    # Retrieve or generate recommendation for user
    recommendation = None
    recommended_products = []

    user_id = current_user.id if current_user else None
    if user_id:
        # Check latest stored recommendation
        rec_record = Recommendation.query.filter_by(user_id=user_id).order_by(Recommendation.created_at.desc()).first()
        
        # If no recommendation exists or if events updated, generate recommendation
        if not rec_record:
            user_events = Event.query.filter_by(user_id=user_id).order_by(Event.timestamp.desc()).limit(15).all()
            event_dicts = [e.to_dict() for e in user_events]
            session_id = session.get('session_id', 'sess_default')
            
            try:
                res = recommendation_engine.run(user_id, session_id, event_dicts, trigger_reason="initial_visit")
                rec_record = Recommendation(
                    user_id=user_id,
                    narrative=res['narrative'],
                    recommended_product_ids_json=str(res['recommended_product_ids']),
                    trigger_reason="initial_visit",
                    metadata_json=json.dumps(res.get('metadata', {}))
                )
                db.session.add(rec_record)
                db.session.commit()
            except Exception as e:
                logger.error(f"Failed to generate initial recommendation: {e}")

        if rec_record:
            recommendation = rec_record.to_dict()
            rec_product_ids = rec_record.get_product_ids()
            if rec_product_ids:
                recommended_products = [Product.query.get(pid).to_dict() for pid in rec_product_ids if Product.query.get(pid)]

    # Fetch unique categories for filter UI
    categories = [c[0] for c in db.session.query(Product.category).distinct().all()]

    return render_template(
        'index.html',
        products=[p.to_dict() for p in products],
        recommendation=recommendation,
        recommended_products=recommended_products,
        categories=categories,
        selected_category=selected_category,
        search_query=search_query,
        current_user=current_user
    )

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    current_user = get_current_user()
    product = Product.query.get_or_404(product_id)
    
    # Vector DB Semantic Search for Similar Products
    similar_vector_matches = vector_store.semantic_search(
        query_text=f"{product.title} {product.category} {product.description}",
        top_k=4
    )
    
    similar_products = []
    for match in similar_vector_matches:
        if match['product_id'] != product.id:
            p = Product.query.get(match['product_id'])
            if p:
                p_dict = p.to_dict()
                p_dict['similarity_score'] = match['similarity_score']
                similar_products.append(p_dict)

    return render_template(
        'product_detail.html',
        product=product.to_dict(),
        similar_products=similar_products[:3],
        current_user=current_user
    )

# --- AUTHENTICATION ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash(f"Welcome back, {user.name}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid email address or password.", "error")

    return render_template('login.html', current_user=get_current_user())

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'user')

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return redirect(url_for('register'))

        user = User(email=email, name=name, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        session['user_id'] = user.id
        flash("Account created successfully!", "success")
        return redirect(url_for('index'))

    return render_template('register.html', current_user=get_current_user())

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('index'))

# --- EVENT TRACKING API ---

@app.route('/api/events/batch', methods=['POST'])
def track_events_batch():
    """Non-blocking API endpoint receiving batched frontend behavioral events."""
    data = request.get_json(silent=True) or {}
    events_list = data.get('events', [])
    current_user = get_current_user()

    if not events_list:
        return jsonify({'status': 'ignored', 'count': 0})

    saved_count = 0
    for ev in events_list:
        try:
            event_obj = Event(
                user_id=current_user.id if current_user else None,
                session_id=ev.get('session_id', 'sess_anon'),
                event_type=ev.get('event_type', 'unknown'),
                target_id=str(ev.get('target_id')) if ev.get('target_id') else None,
                details_json=json.dumps(ev.get('details', {})),
                duration_ms=ev.get('duration_ms', 0)
            )
            db.session.add(event_obj)
            saved_count += 1
        except Exception as e:
            logger.error(f"Error parsing tracked event: {e}")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to commit events batch: {e}")

    return jsonify({'status': 'success', 'saved_count': saved_count})

# --- RECOMMENDATION ENGINE API ---

@app.route('/api/recommendations/refresh', methods=['POST'])
def refresh_recommendations():
    """Explicitly triggers Recommendation Engine refresh for active user."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'status': 'error', 'message': 'User authentication required'}), 401

    data = request.get_json(silent=True) or {}
    session_id = data.get('session_id', 'sess_manual')

    # Fetch recent user behavioral events
    user_events = Event.query.filter_by(user_id=current_user.id).order_by(Event.timestamp.desc()).limit(20).all()
    event_dicts = [e.to_dict() for e in user_events]

    try:
        res = recommendation_engine.run(
            user_id=current_user.id,
            session_id=session_id,
            events=event_dicts,
            trigger_reason="user_manual_refresh"
        )

        rec_record = Recommendation(
            user_id=current_user.id,
            narrative=res['narrative'],
            recommended_product_ids_json=str(res['recommended_product_ids']),
            trigger_reason="user_manual_refresh",
            metadata_json=json.dumps(res.get('metadata', {}))
        )
        db.session.add(rec_record)
        db.session.commit()

        return jsonify({'status': 'success', 'recommendation': res})
    except Exception as e:
        logger.error(f"Recommendation refresh error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- ADMIN CATALOG MANAGEMENT (DUAL-WRITE) ---

@app.route('/admin/catalog')
def admin_catalog():
    if not is_admin():
        flash("Admin permissions required.", "error")
        return redirect(url_for('login'))

    products = Product.query.order_by(Product.id.desc()).all()
    vector_count = vector_store.get_total_count()

    return render_template(
        'admin_catalog.html',
        products=[p.to_dict() for p in products],
        vector_count=vector_count,
        current_user=get_current_user()
    )

@app.route('/admin/product/save', methods=['POST'])
def admin_save_product():
    if not is_admin():
        return jsonify({'status': 'unauthorized'}), 403

    product_id = request.form.get('product_id')
    title = request.form.get('title', '').strip()
    category = request.form.get('category', '').strip()
    description = request.form.get('description', '').strip()
    price = float(request.form.get('price', 0.0))
    rating = float(request.form.get('rating', 4.8))
    tags = request.form.get('tags', '').strip()

    if product_id and product_id.isdigit():
        # Update existing product
        product = Product.query.get(int(product_id))
        if product:
            product.title = title
            product.category = category
            product.description = description
            product.price = price
            product.rating = rating
            product.tags = tags
            db.session.commit()
            flash(f"Product #{product.id} updated in SQL Database.", "success")
    else:
        # Create new product
        product = Product(
            title=title,
            category=category,
            description=description,
            price=price,
            rating=rating,
            tags=tags
        )
        db.session.add(product)
        db.session.commit()
        flash(f"New product #{product.id} created in SQL Database.", "success")

    # DUAL-WRITE OPERATION: Synchronize to ChromaDB Vector Store
    vector_success = vector_store.add_or_update_product(product.to_dict())
    if vector_success:
        flash("Dual-Write SUCCESS: Vector embedding synchronized to Vector DB.", "success")
    else:
        flash("Warning: SQL write succeeded but Vector DB dual-write failed.", "error")

    return redirect(url_for('admin_catalog'))

@app.route('/admin/product/delete/<int:product_id>', methods=['POST'])
def admin_delete_product(product_id):
    if not is_admin():
        return jsonify({'status': 'unauthorized'}), 403

    product = Product.query.get_or_404(product_id)
    title = product.title
    
    # Delete from SQL DB
    db.session.delete(product)
    db.session.commit()

    # DUAL-WRITE OPERATION: Delete from Vector Store
    vector_success = vector_store.delete_product(product_id)
    if vector_success:
        flash(f"Dual-Write SUCCESS: Deleted '{title}' from SQL and Vector DB.", "success")
    else:
        flash(f"Deleted '{title}' from SQL DB.", "success")

    return redirect(url_for('admin_catalog'))

# --- ADMIN OBSERVABILITY & BEHAVIOR ROUTES ---

@app.route('/admin/events')
def admin_events():
    if not is_admin():
        flash("Admin permissions required.", "error")
        return redirect(url_for('login'))

    events = Event.query.order_by(Event.timestamp.desc()).limit(100).all()
    return render_template('admin_events.html', events=events, current_user=get_current_user())

@app.route('/admin/traces')
def admin_traces():
    if not is_admin():
        flash("Admin permissions required.", "error")
        return redirect(url_for('login'))

    traces = get_all_traces()
    return render_template('admin_agent_traces.html', traces=traces, current_user=get_current_user())

# --- PROACTIVE DELIVERY DIGESTS ---

@app.route('/digests')
def digests():
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('login'))

    digests_list = DigestLog.query.order_by(DigestLog.sent_at.desc()).all()
    return render_template('digests.html', digests=digests_list, current_user=current_user)

@app.route('/digests/trigger_now', methods=['POST'])
def trigger_digests_now():
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('login'))

    try:
        generate_proactive_digests_job(app)
        flash("⚡ Scheduled Proactive Recommendation Digest batch executed successfully!", "success")
    except Exception as e:
        flash(f"Digest batch execution failed: {e}", "error")

    return redirect(url_for('digests'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting SmartReco platform on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
