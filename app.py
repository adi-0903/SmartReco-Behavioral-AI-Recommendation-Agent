import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session

from config import Config
from models import db, User, Product, Event, Recommendation, DigestLog, Enrollment
from vector_store import vector_store
from agent.workflow import recommendation_engine
from agent.observability import get_all_traces, get_trace_by_id
from scheduler import init_scheduler, generate_proactive_digests_job
from seed_data import seed_database
from email_service import send_otp_email

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
        confirm_password = request.form.get('confirm_password', '')
        role = 'user'  # All self-registered public accounts default to Learner User

        if confirm_password and password != confirm_password:
            flash("Passwords do not match. Please enter matching passwords.", "error")
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if existing_user.is_verified:
                flash("An account with that email already exists.", "error")
                return redirect(url_for('register'))
            else:
                user = existing_user
                user.name = name
                user.set_password(password)
        else:
            user = User(email=email, name=name, role=role)
            user.set_password(password)
            db.session.add(user)

        otp_code = user.generate_otp()
        db.session.commit()

        # Send direct OTP email to recipient inbox
        sent = send_otp_email(user.email, user.name, otp_code)

        session['pending_user_id'] = user.id
        if sent:
            flash(f"📩 6-Digit Email Verification OTP sent directly to {user.email}!", "success")
        else:
            flash(f"📩 6-Digit Verification OTP code generated for {user.email}!", "success")
            
        return redirect(url_for('verify_otp'))

    return render_template('register.html', current_user=get_current_user())

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    pending_id = session.get('pending_user_id')
    if not pending_id:
        flash("No pending verification session. Please sign up or log in.", "error")
        return redirect(url_for('register'))

    user = db.session.get(User, pending_id)
    if not user:
        session.pop('pending_user_id', None)
        return redirect(url_for('register'))

    if request.method == 'POST':
        otp_input = request.form.get('otp_code', '').strip()
        if user.verify_otp(otp_input):
            db.session.commit()
            session['user_id'] = user.id
            session.pop('pending_user_id', None)
            flash(f"🎉 Email verified successfully! Welcome to SmartReco, {user.name}!", "success")
            return redirect(url_for('index'))
        else:
            flash("❌ Invalid OTP code. Please enter the correct 6-digit passcode.", "error")

    return render_template(
        'verify_otp.html',
        unverified_email=user.email,
        demo_otp=user.otp_code,
        current_user=get_current_user()
    )

@app.route('/resend_otp', methods=['POST'])
def resend_otp():
    pending_id = session.get('pending_user_id')
    if not pending_id:
        flash("No pending verification session found.", "error")
        return redirect(url_for('register'))

    user = db.session.get(User, pending_id)
    if user:
        new_otp = user.generate_otp()
        db.session.commit()
        sent = send_otp_email(user.email, user.name, new_otp)
        if sent:
            flash(f"🔄 New 6-Digit OTP code sent directly to {user.email}!", "success")
        else:
            flash(f"🔄 New 6-Digit OTP code generated for {user.email}!", "success")

    return redirect(url_for('verify_otp'))

@app.route('/profile')
def profile():
    user = get_current_user()
    if not user:
        flash("Please log in to view your profile.", "error")
        return redirect(url_for('login'))

    user_enrollments = Enrollment.query.filter_by(user_id=user.id).order_by(Enrollment.enrolled_at.desc()).all()
    return render_template(
        'profile.html',
        current_user=user,
        enrollments=user_enrollments
    )

@app.route('/enroll/<int:product_id>', methods=['POST'])
def enroll_course(product_id):
    user = get_current_user()
    if not user:
        flash("Please log in to enroll in masterclasses.", "error")
        return redirect(url_for('login'))

    product = Product.query.get_or_404(product_id)
    existing_enr = Enrollment.query.filter_by(user_id=user.id, product_id=product.id).first()
    
    if not existing_enr:
        enr = Enrollment(user_id=user.id, product_id=product.id)
        db.session.add(enr)
        db.session.commit()
        flash(f"🎉 Successfully enrolled in '{product.title}'! Access it anytime in your profile.", "success")
    else:
        flash(f"You are already enrolled in '{product.title}'.", "info")

    return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
def change_password():
    user = get_current_user()
    if not user:
        flash("Please log in to change password.", "error")
        return redirect(url_for('login'))

    current_pwd = request.form.get('current_password', '')
    new_pwd = request.form.get('new_password', '')
    confirm_new_pwd = request.form.get('confirm_new_password', '')

    if not user.check_password(current_pwd):
        flash("Current password is incorrect.", "error")
        return redirect(url_for('profile'))

    if new_pwd != confirm_new_pwd:
        flash("New password and confirmation password do not match.", "error")
        return redirect(url_for('profile'))

    user.set_password(new_pwd)
    db.session.commit()
    flash("🔒 Password updated successfully!", "success")
    return redirect(url_for('profile'))

@app.route('/assistant')
def ai_assistant():
    """Dedicated Full-Page AI Coding & Learning Studio Workstation."""
    return render_template('ai_assistant.html')

@app.route('/api/chat', methods=['POST'])
def api_chat():
    import httpx
    data = request.get_json() or {}
    user_msg = data.get('message', '').strip()
    if not user_msg:
        return jsonify({'reply': 'Please enter a valid question or topic!'})

    current_user = get_current_user()

    # 1. Track chat query in user behavioral stream
    session_id = session.get('session_id', 'sess_chat_anonymous')
    user_id = current_user.id if current_user else None
    
    chat_event = Event(
        user_id=user_id,
        session_id=session_id,
        event_type='search',
        target_id=user_msg[:100],
        details_json=json.dumps({'query': user_msg, 'source': 'chatbot_widget'}),
        duration_ms=0
    )
    db.session.add(chat_event)
    db.session.commit()

    # 2. Check for Greetings & Conversational Intent
    clean_msg = user_msg.lower().strip('!,.? ')
    user_name = current_user.name if current_user else 'Learner'
    
    greetings = {'hi', 'hello', 'hey', 'greetings', 'hi there', 'hello there', 'who are you', 'what can you do', 'help'}
    if clean_msg in greetings:
        reply = (
            f"Hello {user_name}! 👋 I am your **SmartReco AI Advisor** powered by NVIDIA Llama-3.1 AI.\n\n"
            "I can assist you with:\n"
            "• 🎓 **Masterclass Recommendations & Career Roadmaps**\n"
            "• 💻 **Live Coding, Code Snippets & Syntax Debugging**\n"
            "• 🛠️ **Technical Issue Solving & System Architecture**\n\n"
            "What topic or skill would you like to explore today?"
        )
        return jsonify({'reply': reply, 'matched_products': []})

    # 3. RAG Semantic Search over 31 Masterclasses
    vector_matches = vector_store.semantic_search(query_text=user_msg, top_k=3)
    matched_prods = []
    for match in vector_matches:
        p = Product.query.get(match['product_id'])
        if p:
            matched_prods.append(p)

    context_courses = [
        f"Title: {p.title}\nCategory: {p.category}\nPrice: ${p.price}\nRating: ★ {p.rating}\nDescription: {p.description}"
        for p in matched_prods
    ]
    context_str = "\n\n".join(context_courses) if context_courses else "No specific course matches found."

    # 4. Call NVIDIA NIM API (Fast Llama-3.1 8B Model, 5s timeout)
    nvidia_key = app.config.get('NVIDIA_API_KEY') or os.environ.get('NVIDIA_API_KEY')
    nvidia_url = app.config.get('NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com/v1')
    
    reply = None
    if nvidia_key:
        try:
            system_prompt = (
                "You are SmartReco AI Advisor powered by NVIDIA Llama 3.1 AI.\n"
                "Provide helpful, concise, articulate, and accurate answers to the user.\n"
                "If answering tech/career questions or code requests, use markdown formatting and code blocks.\n"
                f"=== RETRIEVED MASTERCLASSES CONTEXT ===\n{context_str}\n================================="
            )
            headers = {"Authorization": f"Bearer {nvidia_key}", "Content-Type": "application/json"}
            payload = {
                "model": "meta/llama-3.1-8b-instruct",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ],
                "temperature": 0.7,
                "max_tokens": 350
            }
            resp = httpx.post(f"{nvidia_url}/chat/completions", headers=headers, json=payload, timeout=5.0)
            if resp.status_code == 200:
                reply = resp.json()['choices'][0]['message']['content'].strip()
                logger.info(f"NVIDIA NIM AI Response generated successfully for query '{user_msg}'")
        except Exception as e:
            logger.warning(f"NVIDIA NIM call timeout/error: {e}")

    # 5. Smart Intent Synthesizer Fallback (Guarantees Instant, High-Quality Answers)
    if not reply:
        top_titles = [f"• **{p.title}** (${p.price}, {p.category})" for p in matched_prods[:3]] if matched_prods else []
        
        # Future/Trending Tech Intent
        if any(kw in clean_msg for kw in ['future', 'beneficial', 'must learn', 'technology', 'technologies', 'trend', 'best to learn']):
            reply = (
                "Here are the top high-demand, future-proof technologies essential to master right now:\n\n"
                "1. 🤖 **Generative AI & Agentic Workflows** (LLMs, LangGraph, RAG Architecture)\n"
                "2. 🛡️ **Cybersecurity & Threat Hunting** (Ethical Hacking, DevSecOps)\n"
                "3. 🌐 **Fullstack Next.js & Microservices** (TypeScript, FastAPI, Docker)\n"
                "4. 📊 **Big Data Pipelines & MLOps** (PyTorch, Spark, BigQuery)\n"
                "5. ☁️ **Cloud Native DevOps** (Kubernetes, Terraform, AWS)\n\n"
                "Top Recommended Masterclasses from our catalog:\n\n"
                + "\n".join(top_titles)
            )
        # Python / Coding Intent
        elif any(kw in clean_msg for kw in ['binary search', 'search algorithm', 'code']):
            reply = (
                "Here is a clean Python implementation for **Binary Search**:\n\n"
                "```python\n"
                "def binary_search(arr, target):\n"
                "    left, right = 0, len(arr) - 1\n"
                "    while left <= right:\n"
                "        mid = (left + right) // 2\n"
                "        if arr[mid] == target:\n"
                "            return mid  # Target found at index mid\n"
                "        elif arr[mid] < target:\n"
                "            left = mid + 1\n"
                "        else:\n"
                "            right = mid - 1\n"
                "    return -1  # Target not found\n"
                "```\n\n"
                "**Time Complexity**: O(log N) • **Space Complexity**: O(1)\n\n"
                "Recommended Masterclass:\n"
                + (top_titles[0] if top_titles else "• **Scalable Relational & NoSQL Database Engineering**")
            )
        elif matched_prods:
            reply = (
                f"Great question! Based on '{user_msg}', here are top masterclasses recommended for you:\n\n"
                + "\n".join(top_titles)
                + "\n\nClick on any masterclass in the catalog to view details and enroll!"
            )
        else:
            reply = f"I searched our catalog for '{user_msg}'. Explore our 31 masterclasses across Generative AI, Cybersecurity, Fullstack Web Dev, Data Science, and DevOps!"

    return jsonify({'reply': reply, 'matched_products': [p.to_dict() for p in matched_prods]})

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
        flash("Admin permissions required to access control panel.", "error")
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
        flash("Admin permissions required.", "error")
        return redirect(url_for('login'))

    product_id = request.form.get('product_id', '').strip()
    title = request.form.get('title', '').strip()
    category = request.form.get('category', '').strip()
    description = request.form.get('description', '').strip()
    price = float(request.form.get('price', 0.0))
    rating = float(request.form.get('rating', 4.8))
    tags = request.form.get('tags', '').strip()

    if product_id and product_id.isdigit():
        # Update existing product in SQL Database
        product = Product.query.get(int(product_id))
        if product:
            product.title = title
            product.category = category
            product.description = description
            product.price = price
            product.rating = rating
            product.tags = tags
            product.updated_at = datetime.utcnow()
            db.session.commit()
            flash(f"Success: Product #{product.id} ('{product.title}') updated in SQL Database.", "success")
        else:
            flash(f"Error: Product #{product_id} not found.", "error")
            return redirect(url_for('admin_catalog'))
    else:
        # Create new product in SQL Database
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
        flash(f"Success: New Product #{product.id} ('{product.title}') created in SQL Database.", "success")

    # DUAL-WRITE OPERATION: Synchronize immediately to ChromaDB Vector Store
    vector_success = vector_store.add_or_update_product(product.to_dict())
    if vector_success:
        flash("Dual-Write SUCCESS: Product embedding updated in Vector DB.", "success")
    else:
        flash("Warning: SQL write succeeded but Vector DB dual-write failed.", "error")

    return redirect(url_for('admin_catalog'))

@app.route('/admin/product/delete/<int:product_id>', methods=['POST'])
def admin_delete_product(product_id):
    if not is_admin():
        flash("Admin permissions required.", "error")
        return redirect(url_for('login'))

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

# --- ADMIN POWER COMMANDS (EVENTS & TRACES CLEARING) ---

@app.route('/admin/events/clear', methods=['POST'])
def admin_clear_events():
    if not is_admin():
        flash("Admin permissions required.", "error")
        return redirect(url_for('login'))

    Event.query.delete()
    db.session.commit()
    flash("Admin Power Command: All behavioral event stream logs cleared.", "success")
    return redirect(url_for('admin_events'))

@app.route('/admin/traces/clear', methods=['POST'])
def admin_clear_traces():
    if not is_admin():
        flash("Admin permissions required.", "error")
        return redirect(url_for('login'))

    from agent.observability import AGENT_TRACES
    AGENT_TRACES.clear()
    flash("Admin Power Command: All agent execution trace logs cleared.", "success")
    return redirect(url_for('admin_traces'))

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

    # Student views their personal received email digests
    user_digests = DigestLog.query.filter_by(user_id=current_user.id).order_by(DigestLog.sent_at.desc()).all()
    return render_template('digests.html', digests=user_digests, current_user=current_user)

@app.route('/admin/digests')
def admin_digests():
    if not is_admin():
        flash("Admin permissions required.", "error")
        return redirect(url_for('login'))

    # Build user-wise behavioral summary data for admin portal
    regular_users = User.query.filter_by(role='user').order_by(User.id.asc()).all()
    user_summaries = []

    for u in regular_users:
        events = Event.query.filter_by(user_id=u.id).order_by(Event.timestamp.desc()).all()
        recent_searches = [e.get_details().get('query') for e in events if e.event_type == 'search' and e.get_details().get('query')][:3]
        
        # Analyze top category for this user
        cats = [e.get_details().get('category') for e in events if e.get_details().get('category')]
        top_cat = max(set(cats), key=cats.count) if cats else None
        
        user_summaries.append({
            'user': u,
            'event_count': len(events),
            'recent_searches': recent_searches,
            'top_category': top_cat
        })

    digest_logs = DigestLog.query.order_by(DigestLog.sent_at.desc()).limit(50).all()

    return render_template(
        'admin_digests.html',
        user_summaries=user_summaries,
        digest_logs=digest_logs,
        current_user=get_current_user()
    )

@app.route('/admin/digests/trigger_all', methods=['POST'])
def admin_trigger_all_digests():
    if not is_admin():
        flash("Admin permissions required.", "error")
        return redirect(url_for('login'))

    try:
        generate_proactive_digests_job(app)
        flash("⚡ 1-CLICK SUCCESS: Personalized AI Email Digests sent to ALL regular learners based on their individual behavioral demands!", "success")
    except Exception as e:
        flash(f"Digest batch execution failed: {e}", "error")

    return redirect(url_for('admin_digests'))

@app.route('/admin/digests/trigger_user/<int:user_id>', methods=['POST'])
def admin_trigger_user_digest(user_id):
    if not is_admin():
        flash("Admin permissions required.", "error")
        return redirect(url_for('login'))

    from scheduler import generate_digest_for_single_user
    user = User.query.get_or_404(user_id)
    success = generate_digest_for_single_user(app, user_id)
    if success:
        flash(f"⚡ 1-CLICK SUCCESS: Personalized AI Email Digest generated and sent to {user.name} ({user.email}) based on their specific activity!", "success")
    else:
        flash(f"Failed to generate digest for {user.name}.", "error")

    return redirect(url_for('admin_digests'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting SmartReco platform on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
