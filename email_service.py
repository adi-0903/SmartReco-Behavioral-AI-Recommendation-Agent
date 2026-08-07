import os
import smtplib
import ssl
import logging
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# Track last email send result for fallback display
_last_send_results = {}

def get_send_result(email: str) -> dict:
    """Returns the last send result for an email address."""
    return _last_send_results.get(email, {})

def _build_otp_html(recipient_name: str, otp_code: str) -> str:
    """Builds the HTML email template for OTP verification."""
    return f"""
    <div style="font-family: Arial, sans-serif; background-color: #0b0f19; color: #f8fafc; padding: 30px; border-radius: 12px; max-width: 550px; margin: 0 auto; border: 1px solid #6366f1;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #6366f1; margin: 0;">SmartReco AI Platform</h2>
            <p style="color: #94a3b8; font-size: 14px;">Email Account Verification</p>
        </div>
        
        <p>Hello <strong>{recipient_name}</strong>,</p>
        <p style="color: #cbd5e1;">Thank you for registering. Please enter the 6-digit OTP code below to verify your email address and activate your account:</p>
        
        <div style="background: #1e293b; text-align: center; padding: 18px; border-radius: 8px; margin: 25px 0; border: 1px solid #38bdf8;">
            <span style="font-family: monospace; font-size: 32px; font-weight: bold; color: #38bdf8; letter-spacing: 8px;">
                {otp_code}
            </span>
        </div>
        
        <p style="color: #94a3b8; font-size: 13px;">This OTP code will expire in 10 minutes. If you did not request this verification, please ignore this email.</p>
        
        <div style="text-align: center; margin-top: 25px; padding-top: 15px; border-top: 1px solid #334155; color: #64748b; font-size: 12px;">
            SmartReco Behavioral AI Platform • Secure Authentication
        </div>
    </div>
    """

def _send_smtp_email(recipient_email: str, subject: str, html_content: str):
    """Internal: Attempts SMTP delivery with multiple strategies (TLS 587, SSL 465)."""
    mail_server = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    mail_username = os.environ.get("MAIL_USERNAME")
    mail_password = os.environ.get("MAIL_PASSWORD")
    sender_email = os.environ.get("MAIL_DEFAULT_SENDER", mail_username or "noreply@smartreco.com")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg.attach(MIMEText(html_content, "html"))

    # Strategy 1: Try STARTTLS on port 587 (works locally & many hosts)
    try:
        with smtplib.SMTP(mail_server, 587, timeout=8) as server:
            server.starttls()
            server.login(mail_username, mail_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        logger.info(f"Direct SMTP Email sent successfully to {recipient_email} (TLS 587)")
        _last_send_results[recipient_email] = {"sent": True}
        return
    except Exception as e1:
        logger.warning(f"SMTP TLS 587 failed for {recipient_email}: {e1}")

    # Strategy 2: Try SSL on port 465 (works on hosts that block 587)
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(mail_server, 465, timeout=8, context=context) as server:
            server.login(mail_username, mail_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        logger.info(f"Direct SMTP Email sent successfully to {recipient_email} (SSL 465)")
        _last_send_results[recipient_email] = {"sent": True}
        return
    except Exception as e2:
        logger.error(f"SMTP SSL 465 also failed for {recipient_email}: {e2}")
        _last_send_results[recipient_email] = {"sent": False}


def send_otp_email(recipient_email: str, recipient_name: str, otp_code: str) -> bool:
    """
    Sends a 6-digit OTP email directly to the recipient's inbox via SMTP.
    Email is sent in a BACKGROUND THREAD so the user is not blocked.
    Tries TLS (587) first, then falls back to SSL (465).
    """
    mail_username = os.environ.get("MAIL_USERNAME")
    mail_password = os.environ.get("MAIL_PASSWORD")

    subject = f"SmartReco — Your 6-Digit Verification OTP: {otp_code}"
    html_content = _build_otp_html(recipient_name, otp_code)

    if mail_username and mail_password:
        # Initialize as pending
        _last_send_results[recipient_email] = {"sent": None}
        
        # Send email in background thread — user is NOT blocked
        thread = threading.Thread(
            target=_send_smtp_email,
            args=(recipient_email, subject, html_content),
            daemon=True
        )
        thread.start()
        logger.info(f"OTP email dispatch started (background) for {recipient_email}")
        return True
    else:
        logger.info(f"[SIMULATED EMAIL] Direct OTP {otp_code} intended for {recipient_email} (Configure MAIL_USERNAME & MAIL_PASSWORD in .env for direct live inbox delivery)")
        _last_send_results[recipient_email] = {"sent": False}
        return False
