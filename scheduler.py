import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from models import db, User, Event, Recommendation, DigestLog
from agent.workflow import recommendation_engine

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

def generate_proactive_digests_job(app):
    """
    Background Cron/Scheduler Task:
    Scans users with recent behavioral activity, runs recommendation engine,
    and generates/delivers personalized HTML recommendation digests.
    """
    with app.app_context():
        logger.info("Executing scheduled proactive recommendation digest job...")
        
        # Fetch non-admin users
        users = User.query.filter_by(role='user').all()
        if not users:
            logger.info("No active regular users found for proactive digest.")
            return

        for user in users:
            # Check user events in last 24 hours
            since_time = datetime.utcnow() - timedelta(hours=24)
            recent_events = Event.query.filter(
                Event.user_id == user.id,
                Event.timestamp >= since_time
            ).order_by(Event.timestamp.desc()).all()

            if not recent_events:
                # If no recent events, get the latest events overall
                recent_events = Event.query.filter_by(user_id=user.id).order_by(Event.timestamp.desc()).limit(10).all()

            event_dicts = [e.to_dict() for e in recent_events]
            session_id = recent_events[0].session_id if recent_events else f"sched_{user.id}"

            try:
                # Execute Recommendation Engine
                result = recommendation_engine.run(
                    user_id=user.id,
                    session_id=session_id,
                    events=event_dicts,
                    trigger_reason="scheduled_daily_digest"
                )

                narrative = result['narrative']
                recommended_products = result['recommended_products']
                prod_ids = [p['id'] for p in recommended_products]

                # Create persistent Recommendation record
                rec = Recommendation(
                    user_id=user.id,
                    narrative=narrative,
                    recommended_product_ids_json=str(prod_ids),
                    trigger_reason="scheduled_daily_digest",
                    metadata_json=str(result.get('metadata', {}))
                )
                db.session.add(rec)

                # Format HTML Digest Email
                courses_html = "".join([
                    f"""
                    <div style="background:#1e293b; padding:15px; border-radius:8px; margin-bottom:12px; border:1px solid #334155;">
                        <h4 style="color:#38bdf8; margin:0 0 5px 0;">{p['title']}</h4>
                        <p style="color:#94a3b8; font-size:13px; margin:0 0 8px 0;">{p['description'][:120]}...</p>
                        <div style="display:flex; justify-to-content:space-between; align-items:center;">
                            <span style="color:#f59e0b; font-weight:bold;">★ {p['rating']}</span>
                            <span style="color:#10b981; font-weight:bold;">${p['price']}</span>
                        </div>
                    </div>
                    """ for p in recommended_products
                ])

                html_content = f"""
                <div style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 25px; border-radius: 12px; max-width: 600px;">
                    <div style="text-align: center; border-bottom: 1px solid #334155; padding-bottom: 15px; margin-bottom: 20px;">
                        <h2 style="color: #6366f1; margin: 0;">SmartReco Personal Daily Learning Digest</h2>
                        <p style="color: #94a3b8; font-size: 14px;">Tailored insights based on your recent activity</p>
                    </div>
                    
                    <div style="background: #1e293b; padding: 18px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #6366f1;">
                        <h3 style="color: #818cf8; margin-top: 0;">Why These Picks For You</h3>
                        <p style="line-height: 1.6; color: #e2e8f0;">{narrative}</p>
                    </div>
                    
                    <h3 style="color: #f8fafc;">Recommended Courses For Your Journey</h3>
                    {courses_html}
                    
                    <div style="text-align: center; margin-top: 25px; padding-top: 15px; border-top: 1px solid #334155; color: #64748b; font-size: 12px;">
                        Sent automatically by SmartReco Behavioral AI Agent • <a href="#" style="color:#38bdf8;">Manage Preferences</a>
                    </div>
                </div>
                """

                # Save Digest Log to DB
                digest = DigestLog(
                    user_id=user.id,
                    recipient_email=user.email,
                    subject=f"SmartReco Digest: Personalized Recommendations for {user.name}",
                    content_html=html_content,
                    status="sent"
                )
                db.session.add(digest)
                db.session.commit()
                logger.info(f"Proactive digest sent successfully to user {user.email}")

            except Exception as e:
                db.session.rollback()
                logger.error(f"Failed to generate proactive digest for user {user.id}: {e}")

def init_scheduler(app):
    """Initializes and starts the APScheduler background scheduler."""
    if not scheduler.running:
        # Schedule job to run every 60 minutes
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
