"""
NjiaMauzo Afrika — Info Email Service
From: info@njiamauzo.africa

Demo mode logs emails. Production: set SMTP_* env vars.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

BASE = Path(__file__).resolve().parent
EMAILS_DIR = BASE / "emails"

# ── Identity ──────────────────────────────────────
INFO_EMAIL = os.environ.get("INFO_EMAIL", "info@njiamauzo.africa")
INFO_NAME = os.environ.get("INFO_NAME", "NjiaMauzo Afrika")
APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:5000")

# ── SMTP (production) ─────────────────────────────
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "1") == "1"


def _load_template(name: str) -> str:
    path = EMAILS_DIR / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _render(template: str, **kwargs) -> str:
    html = template
    for key, val in kwargs.items():
        html = html.replace("{{" + key + "}}", str(val if val is not None else ""))
    return html


def _send_smtp(to_email: str, subject: str, html_body: str) -> bool:
    """Send via SMTP. Returns True on success."""
    if not SMTP_HOST or not SMTP_USER:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{INFO_NAME} <{INFO_EMAIL}>"
        msg["To"] = to_email
        msg["Reply-To"] = INFO_EMAIL
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(INFO_EMAIL, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[email_service] SMTP error: {e}")
        return False


def send_info_email(to_email: str, subject: str, html_body: str, text_fallback: str = "") -> dict:
    """
    Send email from info@njiamauzo.africa.
    Demo: prints to console. Production: uses SMTP if configured.
    """
    result = {
        "ok": False,
        "from": INFO_EMAIL,
        "to": to_email,
        "subject": subject,
        "mode": "demo",
    }

    if SMTP_HOST and SMTP_USER:
        ok = _send_smtp(to_email, subject, html_body)
        result["ok"] = ok
        result["mode"] = "smtp"
        if ok:
            print(f"[email_service] ✅ Sent to {to_email}: {subject}")
        return result

    # Demo mode
    print("\n" + "=" * 60)
    print(f"📧 INFO EMAIL (demo) from {INFO_EMAIL}")
    print(f"   To     : {to_email}")
    print(f"   Subject: {subject}")
    if text_fallback:
        print(f"   Body   : {text_fallback[:200]}")
    print("=" * 60 + "\n")
    result["ok"] = True
    result["demo"] = True
    return result


# ── High-level helpers ────────────────────────────

def send_welcome_email(to_email: str, name: str) -> dict:
    html = _render(
        _load_template("welcome.html"),
        name=name,
        app_url=APP_URL,
    )
    return send_info_email(
        to_email,
        subject="🌾 Karibu NjiaMauzo Afrika — Welcome!",
        html_body=html,
        text_fallback=f"Karibu {name}! Welcome to NjiaMauzo Afrika. Open: {APP_URL}",
    )


def send_otp_email(to_email: str, code: str, purpose: str = "VERIFY") -> dict:
    purpose_labels = {
        "RESET": "Password Reset / Badilisha Nenosiri",
        "VERIFY": "Account Verification / Uthibitisho",
        "LOGIN": "Login Confirmation",
        "PAYMENT": "Payment Confirmation / Malipo",
    }
    label = purpose_labels.get(purpose, purpose)
    html = _render(
        _load_template("otp.html"),
        code=code,
        purpose=label,
    )
    return send_info_email(
        to_email,
        subject=f"🔐 NjiaMauzo OTP: {code}",
        html_body=html,
        text_fallback=f"Your NjiaMauzo OTP is {code}. Purpose: {label}. Expires in 10 minutes.",
    )


def send_password_reset_email(to_email: str, name: str, code: str) -> dict:
    html = _render(
        _load_template("password_reset.html"),
        name=name or "User",
        code=code,
    )
    return send_info_email(
        to_email,
        subject="🔑 Badilisha Nenosiri — NjiaMauzo Afrika",
        html_body=html,
        text_fallback=f"Password reset code: {code}. Expires in 10 minutes.",
    )


def send_payment_email(
    to_email: str,
    name: str,
    reference: str,
    amount,
    currency: str = "TZS",
    method: str = "MPESA",
    status: str = "VERIFIED",
) -> dict:
    html = _render(
        _load_template("payment.html"),
        name=name or "Customer",
        reference=reference,
        amount=f"{float(amount):,.0f}",
        currency=currency,
        method=method,
        status=status,
    )
    return send_info_email(
        to_email,
        subject=f"💳 Malipo {status} — {reference}",
        html_body=html,
        text_fallback=f"Payment {status}: {amount} {currency} via {method}. Ref: {reference}",
    )


def get_info_email_config() -> dict:
    return {
        "info_email": INFO_EMAIL,
        "info_name": INFO_NAME,
        "app_url": APP_URL,
        "smtp_configured": bool(SMTP_HOST and SMTP_USER),
        "templates": [p.name for p in EMAILS_DIR.glob("*.html")] if EMAILS_DIR.exists() else [],
    }
