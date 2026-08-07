import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from models import db, User, Event, Recommendation, DigestLog
from agent.workflow import recommendation_engine

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

def process_user_proactive_digest(user):
    """
    Analyzes user-wise behavioral data, executes agent recommendation engine,
    and generates a compact, highly personalized HTML email digest for the given user.
    """
    # Fetch recent user events in last 24 hours
    since_time = datetime.utcnow() - timedelta(hours=24)
    recent_events = Event.query.filter(
        Event.user_id == user.id,
        Event.timestamp >= since_time
    ).order_by(Event.timestamp.desc()).all()

    if not recent_events:
        # Fallback to latest events overall for this user
        recent_events = Event.query.filter_by(user_id=user.id).order_by(Event.timestamp.desc()).limit(15).all()

    event_dicts = [e.to_dict() for e in recent_events]
    session_id = recent_events[0].session_id if recent_events else f"sched_{user.id}"

    try:
        # Execute Recommendation Engine with user-specific events
        result = recommendation_engine.run(
            user_id=user.id,
            session_id=session_id,
            events=event_dicts,
            trigger_reason="proactive_personalized_digest"
        )

        narrative = result['narrative']
        recommended_products = result['recommended_products']
        prod_ids = [p['id'] for p in recommended_products]
        top_cat = result.get('metadata', {}).get('top_category', 'Software Engineering')

        # Persist recommendation record in DB
        rec = Recommendation(
            user_id=user.id,
            narrative=narrative,
            recommended_product_ids_json=str(prod_ids),
            trigger_reason="proactive_personalized_digest",
            metadata_json=str(result.get('metadata', {}))
        )
        db.session.add(rec)

        # Ultra-Compact Grid Layout (Horizontal 3-column cards for zero scrolling)
        courses_grid_html = "".join([
            f"""
            <div style="background: rgba(30, 41, 59, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 12px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; text-transform: uppercase;">
                            {p['category']}
                        </span>
                        <span style="color: #f59e0b; font-weight: 700; font-size: 12px;">★ {p['rating']}</span>
                    </div>
                    <h5 style="color: #ffffff; font-size: 13px; font-weight: 700; margin: 4px 0 6px 0; font-family: 'Outfit', sans-serif; line-height: 1.3;">{p['title']}</h5>
                    <p style="color: #94a3b8; font-size: 11px; line-height: 1.4; margin: 0 0 10px 0;">{p['description'][:75]}...</p>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 8px; margin-top: auto;">
                    <span style="color: #10b981; font-weight: 800; font-size: 15px;">${p['price']}</span>
                    <a href="/product/{p['id']}" style="background: linear-gradient(135deg, #6366f1, #4f46e5); color: #ffffff; text-decoration: none; padding: 4px 10px; border-radius: 5px; font-size: 11px; font-weight: 700; display: inline-block;">
                        View →
                    </a>
                </div>
            </div>
            """ for p in recommended_products
        ])

        html_content = f"""
        <div style="font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: #0b0f19; color: #f8fafc; padding: 18px; border-radius: 14px; border: 1px solid rgba(99, 102, 241, 0.3); width: 100%;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 10px; margin-bottom: 14px; flex-wrap: wrap; gap: 8px;">
                <h3 style="font-family: 'Outfit', sans-serif; background: linear-gradient(135deg, #6366f1, #38bdf8, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0; font-size: 18px; font-weight: 800;">
                    SmartReco Personal Learning Digest
                </h3>
                <span style="color: #94a3b8; font-size: 12px;">Curated for <strong>{user.name}</strong> • Domain: <strong style="color: #38bdf8;">{top_cat}</strong></span>
            </div>
            
            <div style="background: rgba(15, 23, 42, 0.85); border-left: 3px solid #6366f1; padding: 12px 14px; border-radius: 0 8px 8px 0; margin-bottom: 14px;">
                <p style="line-height: 1.5; color: #e2e8f0; font-size: 12.5px; margin: 0;">{narrative}</p>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; margin-bottom: 12px;">
                {courses_grid_html}
            </div>
            
            <div style="text-align: center; padding-top: 10px; border-top: 1px solid rgba(255, 255, 255, 0.08); color: #64748b; font-size: 11px;">
                Delivered automatically by SmartReco Behavioral AI Agent for <strong>{user.email}</strong>
            </div>
        </div>
        """

        # Save Digest Log in DB
        digest = DigestLog(
            user_id=user.id,
            recipient_email=user.email,
            subject=f"SmartReco Digest for {user.name}: {top_cat} Recommendations",
            content_html=html_content,
            status="sent"
        )
        db.session.add(digest)
        db.session.commit()
        logger.info(f"User-specific personalized digest sent to {user.email} for domain {top_cat}")
        return True

    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to process proactive digest for user {user.id}: {e}")
        return False

def generate_proactive_digests_job(app):
    """
    Background Cron/Scheduler Task:
    Iterates through all regular users and generates personalized email digests based on each user's data.
    """
    with app.app_context():
        logger.info("Executing scheduled proactive recommendation digest job for all users...")
        users = User.query.filter_by(role='user').all()
        for u in users:
            process_user_proactive_digest(u)

def generate_digest_for_single_user(app, user_id):
    """
    Triggers personalized email digest generation for a single user ID.
    """
    with app.app_context():
        user = User.query.get(user_id)
        if user:
            return process_user_proactive_digest(user)
        return False

def init_scheduler(app):
    """Initializes and starts the APScheduler background scheduler."""
    if not scheduler.running:
        scheduler.add_job(
            func=generate_proactive_digests_job,
            args=[app],
            trigger="interval",
            minutes=60,
            id="proactive_digest_job",
            replace_existing=True
        )
        scheduler.start()
        logger.info("APScheduler initialized: Proactive Digest Job active.")
