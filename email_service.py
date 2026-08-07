import os
import smtplib
import logging
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

def _send_smtp_email(recipient_email: str, subject: str, html_content: str):
    """Internal: Sends email via SMTP in a background thread. Non-blocking."""
    mail_server = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    mail_port = int(os.environ.get("MAIL_PORT", 587))
    mail_username = os.environ.get("MAIL_USERNAME")
    mail_password = os.environ.get("MAIL_PASSWORD")
    sender_email = os.environ.get("MAIL_DEFAULT_SENDER", mail_username or "noreply@smartreco.com")

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(mail_server, mail_port, timeout=8) as server:
            server.starttls()
            server.login(mail_username, mail_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())

        logger.info(f"Direct SMTP Email sent successfully to {recipient_email}")
    except Exception as e:
        logger.error(f"Failed to send direct SMTP email to {recipient_email}: {e}")


def send_otp_email(recipient_email: str, recipient_name: str, otp_code: str) -> bool:
    """
    Sends a 6-digit OTP email directly to the recipient's inbox via SMTP.
    Email is sent in a BACKGROUND THREAD so the user is not blocked.
    """
    mail_username = os.environ.get("MAIL_USERNAME")
    mail_password = os.environ.get("MAIL_PASSWORD")

    subject = f"SmartReco — Your 6-Digit Verification OTP: {otp_code}"
    
    html_content = f"""
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

    if mail_username and mail_password:
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
        return False
