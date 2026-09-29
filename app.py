"""
NjiaMauzo Afrika — Flask Backend
================================
Serves index.html + Contact Seller API + product/payment stubs.

Run:
  pip install flask flask-cors
  python app.py

Open: http://127.0.0.1:5000
Admin login: username only; no admin password is required
"""

from flask import Flask, request, jsonify, send_from_directory, session, redirect
from flask_cors import CORS
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
import uuid
import threading
import time
import os
import secrets
import base64
import json
import urllib.request
import urllib.error
import urllib.parse
import sqlite3
import hashlib
import math
import re
from functools import wraps

BASE_DIR = Path(__file__).resolve().parent
# static_folder=None: hatuoneshi folder nzima ya app (ambayo ina app.py,
# requirements.txt n.k.) kwa HTTP moja kwa moja. Faili za umma pekee
# (mfano logo.png) zinatolewa kupitia /static/<path:filename> chini.
app = Flask(__name__, static_folder=None)
app.secret_key = (
    os.environ.get("FLASK_SECRET_KEY")
    or os.environ.get("SECRET_KEY")
    or secrets.token_hex(32)
)
CORS(app, supports_credentials=True)

from mjueyesu_api import mjueyesu_bp
app.register_blueprint(mjueyesu_bp)

# Usalama wa session (admin + watumiaji)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "1").strip() not in ("0", "false", "False", ""),
    PERMANENT_SESSION_LIFETIME=int(os.environ.get("ADMIN_SESSION_HOURS", "8")) * 3600,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB uploads
)

CONTACT_SESSIONS = {}
SESSION_LOCK = threading.Lock()
SESSION_TTL = 600

SAMPLE_PRODUCTS = [
    {
        "id": 1,
        "title": "Mahindi",
        "description": "Mahindi safi ya Mbeya — gunia 50kg",
        "seller_id": "s1",
        "seller_name": "Safari Exports",
        "seller_phone": "07131709570",
        "seller_whatsapp": "07131709570",
        "seller_email": "safariexport.mbeya@biashara.tz",
        "seller_telegram": "@safariexport_tz",
        "seller_facebook": "facebook.com/safariexport.tz",
        "seller_instagram": "instagram.com/safariexport_tz",
        "location": "Mbeya",
        "real_price": 16066,
        "unit": "kg",
        "transport_cost": 10210,
        "transport_note": "Estimated travel time from Mbeya to your location (subject to change)",
        "likes": 12,
        "image": "https://images.unsplash.com/photo-1464226184884-fa280b87c399?w=500&h=360&fit=crop",
        "emoji": "🌽",
        "color": "#0b7d45",
        "featured": True,
    },
    {
        "id": 2,
        "title": "Ufuta",
        "description": "Ufuta wa Ruvuma — tani",
        "seller_id": "s2",
        "seller_name": "Ruvuma Agro",
        "seller_phone": "0755248789",
        "seller_whatsapp": "0755248789",
        "seller_email": "ruvuma.agro@biashara.tz",
        "seller_telegram": "@ruvumaagro",
        "seller_facebook": "",
        "seller_instagram": "",
        "location": "Ruvuma",
        "real_price": 4500,
        "unit": "kg",
        "transport_cost": 8500,
        "transport_note": "Makadirio ya usafiri hadi eneo lako",
        "likes": 8,
        "image": "https://images.unsplash.com/photo-1599599810769-bcde5a160d32?w=500&h=360&fit=crop",
        "emoji": "🫒",
        "color": "#0b7d45",
        "featured": False,
    },
    {
        "id": 3,
        "title": "Kahawa",
        "description": "Kahawa Arabica ya Arusha",
        "seller_id": "s3",
        "seller_name": "Arusha Coffee Co",
        "seller_phone": "0688123456",
        "seller_whatsapp": "0688123456",
        "seller_email": "info@arushacoffee.tz",
        "seller_telegram": "",
        "seller_facebook": "facebook.com/arushacoffee",
        "seller_instagram": "instagram.com/arushacoffee",
        "location": "Arusha",
        "real_price": 12000,
        "unit": "kg",
        "transport_cost": 6000,
        "transport_note": "Makadirio ya usafiri hadi eneo lako",
        "likes": 21,
        "image": "https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=500&h=360&fit=crop",
        "emoji": "☕",
        "color": "#0b7d45",
        "featured": True,
    },
    {
        "id": 4,
        "title": "Mpunga",
        "description": "Mpunga wa Mbarali/Mwanza — daraja la kwanza",
        "seller_id": "s4",
        "seller_name": "Mwanza Rice Traders",
        "seller_phone": "0712345678",
        "seller_whatsapp": "0712345678",
        "seller_email": "info@mwanzarice.tz",
        "seller_telegram": "",
        "seller_facebook": "",
        "seller_instagram": "",
        "location": "Mwanza",
        "real_price": 2600,
        "unit": "kg",
        "transport_cost": 7000,
        "transport_note": "Makadirio ya usafiri hadi eneo lako",
        "likes": 5,
        "image": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500&h=360&fit=crop",
        "emoji": "🌾",
        "color": "#0b7d45",
        "featured": False,
    },
    {
        "id": 5,
        "title": "Korosho",
        "description": "Korosho ghafi ya Mtwara — kiwango cha kuuza nje",
        "seller_id": "s5",
        "seller_name": "Mtwara Cashew Co",
        "seller_phone": "0765123456",
        "seller_whatsapp": "0765123456",
        "seller_email": "sales@mtwaracashew.tz",
        "seller_telegram": "",
        "seller_facebook": "facebook.com/mtwaracashew",
        "seller_instagram": "",
        "location": "Mtwara",
        "real_price": 3200,
        "unit": "kg",
        "transport_cost": 9500,
        "transport_note": "Makadirio ya usafiri hadi eneo lako",
        "likes": 14,
        "image": "https://images.unsplash.com/photo-1567892737950-30c4db37cd89?w=500&h=360&fit=crop",
        "emoji": "🌰",
        "color": "#0b7d45",
        "featured": True,
    },
    {
        "id": 6,
        "title": "Alizeti",
        "description": "Mbegu za alizeti za Singida — kwa mafuta",
        "seller_id": "s6",
        "seller_name": "Singida Sunflower Ltd",
        "seller_phone": "0678901234",
        "seller_whatsapp": "0678901234",
        "seller_email": "",
        "seller_telegram": "",
        "seller_facebook": "",
        "seller_instagram": "",
        "location": "Singida",
        "real_price": 2100,
        "unit": "kg",
        "transport_cost": 6500,
        "transport_note": "Makadirio ya usafiri hadi eneo lako",
        "likes": 7,
        "image": "https://images.unsplash.com/photo-1597848212624-a19eb35e2651?w=500&h=360&fit=crop",
        "emoji": "🌻",
        "color": "#0b7d45",
        "featured": False,
    },
    {
        "id": 7,
        "title": "Maharage",
        "description": "Maharage mekundu ya Mbeya — gunia 90kg",
        "seller_id": "s7",
        "seller_name": "Mbeya Beans Traders",
        "seller_phone": "0789012345",
        "seller_whatsapp": "0789012345",
        "seller_email": "",
        "seller_telegram": "",
        "seller_facebook": "",
        "seller_instagram": "",
        "location": "Mbeya",
        "real_price": 3400,
        "unit": "kg",
        "transport_cost": 8200,
        "transport_note": "Makadirio ya usafiri hadi eneo lako",
        "likes": 9,
        "image": "https://images.unsplash.com/photo-1515543904379-3d757afe72e4?w=500&h=360&fit=crop",
        "emoji": "🫘",
        "color": "#0b7d45",
        "featured": False,
    },
    {
        "id": 8,
        "title": "Vitunguu",
        "description": "Vitunguu vya Singida — vibichi na vikavu",
        "seller_id": "s8",
        "seller_name": "Singida Onion Suppliers",
        "seller_phone": "0623456789",
        "seller_whatsapp": "0623456789",
        "seller_email": "",
        "seller_telegram": "",
        "seller_facebook": "",
        "seller_instagram": "",
        "location": "Singida",
        "real_price": 1800,
        "unit": "kg",
        "transport_cost": 5500,
        "transport_note": "Makadirio ya usafiri hadi eneo lako",
        "likes": 4,
        "image": "https://images.unsplash.com/photo-1508747703725-719777637510?w=500&h=360&fit=crop",
        "emoji": "🧅",
        "color": "#0b7d45",
        "featured": False,
    },
    {
        "id": 9,
        "title": "Ndizi",
        "description": "Ndizi mbivu na mbichi za Kagera — jumla",
        "seller_id": "s9",
        "seller_name": "Kagera Banana Growers",
        "seller_phone": "0745678901",
        "seller_whatsapp": "0745678901",
        "seller_email": "",
        "seller_telegram": "",
        "seller_facebook": "",
        "seller_instagram": "",
        "location": "Kagera",
        "real_price": 1200,
        "unit": "mkungu",
        "transport_cost": 6000,
        "transport_note": "Makadirio ya usafiri hadi eneo lako",
        "likes": 11,
        "image": "https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=500&h=360&fit=crop",
        "emoji": "🍌",
        "color": "#0b7d45",
        "featured": True,
    },
]

# ================= SECURITY / SABBATH =================
# Passwords MUST be configured as Render Environment Variables.
# Admin access:
# During the temporary 60-hour window, Admin Room opens without username/password.
# After the window, the normal username + password are required again.
ADMIN_USER = os.environ.get("ADMIN_USER", "SUKUMANJIA").strip()
ADMIN_PASS = os.environ.get("ADMIN_PASS", "NjiaMauzo.sukuma@76").strip()
# Default window lasts 60h for this release.
# Override with ADMIN_TEMP_OPEN_UNTIL on Render if deployment happens later.
ADMIN_TEMP_OPEN_UNTIL = os.environ.get(
    "ADMIN_TEMP_OPEN_UNTIL", "2026-08-27T04:30:00Z"
).strip()
SABBATH_TZ = os.environ.get("SABBATH_TZ", "Africa/Nairobi").strip()
# Tanzania has no single sunset time. Use a configurable reference point.
# Default: Dodoma (central Tanzania). Override SABBATH_LAT/LON on Render for
# the exact city/area whose sunset should control the lock.
SABBATH_LAT = float(os.environ.get("SABBATH_LAT", "-6.1630"))
SABBATH_LON = float(os.environ.get("SABBATH_LON", "35.7516"))
SABBATH_SUNSET_ZENITH = 90.8333

def _solar_sunset_utc(day, latitude, longitude):
    """NOAA-style sunset calculation; returns UTC datetime or None."""
    n = day.timetuple().tm_yday
    lng_hour = longitude / 15.0
    t = n + ((18 - lng_hour) / 24.0)
    M = (0.9856 * t) - 3.289
    L = M + (1.916 * math.sin(math.radians(M))) + (0.020 * math.sin(math.radians(2*M))) + 282.634
    L %= 360
    RA = math.degrees(math.atan(0.91764 * math.tan(math.radians(L)))) % 360
    Lq, RAq = math.floor(L/90)*90, math.floor(RA/90)*90
    RA = (RA + (Lq - RAq)) / 15.0
    sin_dec = 0.39782 * math.sin(math.radians(L))
    cos_dec = math.cos(math.asin(sin_dec))
    cos_h = (math.cos(math.radians(SABBATH_SUNSET_ZENITH)) - sin_dec * math.sin(math.radians(latitude))) / (cos_dec * math.cos(math.radians(latitude)))
    if cos_h > 1 or cos_h < -1:
        return None
    H = math.degrees(math.acos(cos_h)) / 15.0
    T = H + RA - (0.06571 * t) - 6.622
    utc_hour = (T - lng_hour) % 24
    hours = int(utc_hour)
    minutes = int((utc_hour - hours) * 60)
    seconds = int(round((((utc_hour - hours) * 60) - minutes) * 60))
    if seconds >= 60:
        minutes += 1; seconds -= 60
    if minutes >= 60:
        hours = (hours + 1) % 24; minutes -= 60
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(hours=hours, minutes=minutes, seconds=seconds)

def _sabbath_window(now=None):
    """Friday sunset -> Saturday sunset in SABBATH_TZ."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(SABBATH_TZ)
    now = now or datetime.now(tz)
    d = now.date()
    # Candidate Friday and Saturday sunsets surrounding the current moment.
    friday = d - timedelta(days=(d.weekday() - 4) % 7)
    sat = friday + timedelta(days=1)
    fri_utc = _solar_sunset_utc(friday, SABBATH_LAT, SABBATH_LON)
    sat_utc = _solar_sunset_utc(sat, SABBATH_LAT, SABBATH_LON)
    if not fri_utc or not sat_utc:
        return False, None, None, now
    start = fri_utc.astimezone(tz)
    end = sat_utc.astimezone(tz)
    active = start <= now < end
    return active, start, end, now

def _is_sabbath():
    try:
        return _sabbath_window()[0]
    except Exception:
        return False

def _sabbath_guard():
    if _is_sabbath() and not session.get("is_admin"):
        return jsonify({"success":False,"sabbath":True,"message":"Leo ni Sabato. Huduma zimefungwa kwa muda wa Sabato. Eneo la matangazo linaendelea kuwa wazi."}),403
    return None

ADMIN_MAX_ATTEMPTS = int(os.environ.get("ADMIN_MAX_ATTEMPTS", "5"))
ADMIN_LOCK_SECONDS = int(os.environ.get("ADMIN_LOCK_SECONDS", "900"))  # dakika 15
ADMIN_LOGIN_ATTEMPTS = {}  # ip -> {count, locked_until}
ADMIN_ATTEMPTS_LOCK = threading.Lock()


def _client_ip():
    forwarded = request.headers.get("X-Forwarded-For") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


# ===== ADMIN ROOM: banned/blocked users =====
# Watumiaji wanaozuiwa na admin (kwa namba ya simu, session uid, au IP).
# Hii itatumika pia na usajili wa namba za simu (chat/majadiliano) ujao.
BANNED_LOCK = threading.Lock()
BANNED_STORE = {}  # identifier(lower) -> {"identifier","reason","banned_at","by"}


def _ban_identifiers_for_request():
    """Vitambulisho vinavyowezekana vya mgeni wa sasa: session uid, phone (ikiwa ipo), IP."""
    ids = []
    uid = session.get("uid")
    if uid:
        ids.append(str(uid))
    phone = session.get("phone")
    if phone:
        ids.append(str(phone))
    ids.append(_client_ip())
    return [i.strip().lower() for i in ids if i]


def _is_banned_identifier(identifier: str) -> bool:
    if not identifier:
        return False
    with BANNED_LOCK:
        return identifier.strip().lower() in BANNED_STORE


def _is_banned_request() -> bool:
    if session.get("is_admin"):
        return False
    for ident in _ban_identifiers_for_request():
        if _is_banned_identifier(ident):
            return True
    return False


def _admin_is_locked(ip: str):
    with ADMIN_ATTEMPTS_LOCK:
        row = ADMIN_LOGIN_ATTEMPTS.get(ip) or {}
        until = row.get("locked_until") or 0
        if until and time.time() < until:
            return True, int(until - time.time())
        if until and time.time() >= until:
            ADMIN_LOGIN_ATTEMPTS.pop(ip, None)
        return False, 0


def _admin_register_fail(ip: str):
    with ADMIN_ATTEMPTS_LOCK:
        row = ADMIN_LOGIN_ATTEMPTS.get(ip) or {"count": 0, "locked_until": 0}
        row["count"] = int(row.get("count") or 0) + 1
        if row["count"] >= ADMIN_MAX_ATTEMPTS:
            row["locked_until"] = time.time() + ADMIN_LOCK_SECONDS
            row["count"] = 0
        ADMIN_LOGIN_ATTEMPTS[ip] = row
        return row


def _admin_clear_attempts(ip: str):
    with ADMIN_ATTEMPTS_LOCK:
        ADMIN_LOGIN_ATTEMPTS.pop(ip, None)


# ===== Ulinzi wa jumla: rate limiting kwa endpoints nyeti (login/register) =====
_RATE_LIMIT_STORE = {}
_RATE_LIMIT_LOCK = threading.Lock()

def _rate_limited(key_prefix: str, max_attempts: int = 8, window_seconds: int = 300):
    """True ikiwa IP hii imezidi kikomo cha majaribio ndani ya dirisha la muda."""
    ip = _client_ip()
    key = f"{key_prefix}:{ip}"
    now = time.time()
    with _RATE_LIMIT_LOCK:
        row = _RATE_LIMIT_STORE.get(key) or {"hits": [], "blocked_until": 0}
        if row["blocked_until"] and now < row["blocked_until"]:
            return True
        row["hits"] = [t for t in row["hits"] if now - t < window_seconds]
        row["hits"].append(now)
        if len(row["hits"]) > max_attempts:
            row["blocked_until"] = now + window_seconds
            _RATE_LIMIT_STORE[key] = row
            return True
        _RATE_LIMIT_STORE[key] = row
        return False


def rate_limit(key_prefix, max_attempts=8, window_seconds=300):
    """Decorator: zuia matumizi mabaya (brute force) kwenye endpoint nyeti."""
    def _decorator(fn):
        @wraps(fn)
        def _wrapped(*args, **kwargs):
            if _rate_limited(key_prefix, max_attempts, window_seconds):
                return jsonify({
                    "success": False,
                    "message": "Majaribio mengi sana. Jaribu tena baada ya muda mfupi."
                }), 429
            return fn(*args, **kwargs)
        return _wrapped
    return _decorator


def _require_admin():
    """Rudisha (ok, response). response si None ikiwa si admin."""
    if not session.get("is_admin"):
        return False, (jsonify({"success": False, "message": "Si admin. Ingia tena."}), 403)
    return True, None


def _require_csrf():
    """Angalia CSRF kwa POST/PUT/DELETE za admin (header au body)."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True, None
    token = (
        request.headers.get("X-CSRF-Token")
        or request.headers.get("X-CSRFToken")
        or (request.get_json(silent=True) or {}).get("csrf_token")
        or request.form.get("csrf_token")
    )
    expected = session.get("csrf")
    if not expected or not token or not secrets.compare_digest(str(token), str(expected)):
        return False, (jsonify({"success": False, "message": "CSRF token si sahihi. Refresh ukurasa."}), 403)
    return True, None
SERVICE_FEE_TZS = 3000
ACCESS_DURATION_SEC = 10 * 60  # dakika 10 baada ya malipo — huduma za kawaida

# ---------- M-Pesa STK Push (Safaricom Daraja API) ----------
# Weka credentials kwenye environment variables (usiweke siri kwenye msimbo):
#   MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET, MPESA_SHORTCODE,
#   MPESA_PASSKEY, MPESA_CALLBACK_URL, MPESA_ENV=sandbox|production
# Bila credentials → DEMO MODE (STK inasimuliwa kwa majaribio).
MPESA_CONSUMER_KEY = os.environ.get("MPESA_CONSUMER_KEY", "").strip()
MPESA_CONSUMER_SECRET = os.environ.get("MPESA_CONSUMER_SECRET", "").strip()
MPESA_SHORTCODE = os.environ.get("MPESA_SHORTCODE", "174379").strip()  # sandbox default
MPESA_PASSKEY = os.environ.get(
    "MPESA_PASSKEY",
    "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919",  # sandbox passkey ya umma
).strip()
MPESA_CALLBACK_URL = os.environ.get(
    "MPESA_CALLBACK_URL",
    "",  # e.g. https://yourdomain.com/api/payment/mpesa/callback
).strip()
MPESA_ENV = (os.environ.get("MPESA_ENV") or "sandbox").strip().lower()
MPESA_ACCOUNT_REF = os.environ.get("MPESA_ACCOUNT_REF", "NjiaMauzo")
MPESA_DEMO_MODE = not (MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET)

_MPESA_TOKEN_CACHE = {"token": None, "expires": 0}


def _mpesa_base_url():
    if MPESA_ENV == "production":
        return "https://api.safaricom.co.ke"
    return "https://sandbox.safaricom.co.ke"


def _mpesa_http_json(url, method="GET", data=None, headers=None, timeout=30):
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(err_body) if err_body else {}
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed
    except Exception as e:
        return 0, {"error": str(e)}


def _mpesa_access_token():
    """OAuth token kutoka Daraja (cached)."""
    now = time.time()
    if _MPESA_TOKEN_CACHE["token"] and _MPESA_TOKEN_CACHE["expires"] > now + 30:
        return _MPESA_TOKEN_CACHE["token"]
    if MPESA_DEMO_MODE:
        return "DEMO_TOKEN"
    url = _mpesa_base_url() + "/oauth/v1/generate?grant_type=client_credentials"
    auth = base64.b64encode(
        f"{MPESA_CONSUMER_KEY}:{MPESA_CONSUMER_SECRET}".encode()
    ).decode()
    status, data = _mpesa_http_json(
        url, method="GET", headers={"Authorization": f"Basic {auth}"}
    )
    token = (data or {}).get("access_token")
    if not token:
        raise RuntimeError(f"M-Pesa token imeshindikana ({status}): {data}")
    expires_in = int(data.get("expires_in") or 3599)
    _MPESA_TOKEN_CACHE["token"] = token
    _MPESA_TOKEN_CACHE["expires"] = now + expires_in
    return token


def _normalize_msisdn(phone: str, country: str = "Kenya") -> str:
    """2547XXXXXXXX (Kenya) au 2557XXXXXXXX (Tanzania). STK Push ya Daraja = Kenya."""
    p = "".join(c for c in (phone or "") if c.isdigit())
    if not p:
        return ""
    if p.startswith("0") and len(p) == 10:
        # Kenya default for Safaricom STK
        if country == "Tanzania":
            return "255" + p[1:]
        return "254" + p[1:]
    if p.startswith("7") and len(p) == 9:
        return ("255" if country == "Tanzania" else "254") + p
    if p.startswith("254") or p.startswith("255"):
        return p
    return p


def _mpesa_password_timestamp():
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    raw = f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{ts}"
    pwd = base64.b64encode(raw.encode()).decode()
    return pwd, ts


def mpesa_stk_push(phone: str, amount: int, order_id: str, account_ref: str = None, description: str = None):
    """
    Anzisha Lipa Na M-Pesa Online (STK Push).
    amount: integer (KES kwa Daraja Kenya).
    Returns dict: success, checkout_request_id, merchant_request_id, message, demo
    """
    amount = max(1, int(amount))
    msisdn = _normalize_msisdn(phone, "Kenya")
    if not msisdn or len(msisdn) < 12:
        return {"success": False, "message": "Namba ya simu si sahihi (mfano 07XXXXXXXX)."}

    # DEMO MODE — hakuna credentials: simulia STK
    if MPESA_DEMO_MODE:
        checkout_id = "ws_CO_DEMO_" + secrets.token_hex(6).upper()
        merchant_id = "DEMO-" + secrets.token_hex(4).upper()
        return {
            "success": True,
            "demo": True,
            "CheckoutRequestID": checkout_id,
            "MerchantRequestID": merchant_id,
            "CustomerMessage": "Success. Request accepted for processing",
            "message": "Ombi la malipo limetumwa. Thibitisha kwenye simu yako (PIN).",
            "phone": msisdn,
            "amount": amount,
        }

    token = _mpesa_access_token()
    password, timestamp = _mpesa_password_timestamp()
    callback = MPESA_CALLBACK_URL or (
        request.url_root.rstrip("/") + "/api/payment/mpesa/callback"
        if request else ""
    )
    payload = {
        "BusinessShortCode": MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": msisdn,
        "PartyB": MPESA_SHORTCODE,
        "PhoneNumber": msisdn,
        "CallBackURL": callback or "https://example.com/api/payment/mpesa/callback",
        "AccountReference": (account_ref or MPESA_ACCOUNT_REF or order_id)[:12],
        "TransactionDesc": (description or f"NjiaMauzo {order_id}")[:13],
    }
    url = _mpesa_base_url() + "/mpesa/stkpush/v1/processrequest"
    status, data = _mpesa_http_json(
        url,
        method="POST",
        data=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if status == 200 and (data.get("ResponseCode") == "0" or data.get("CheckoutRequestID")):
        return {
            "success": True,
            "demo": False,
            "CheckoutRequestID": data.get("CheckoutRequestID"),
            "MerchantRequestID": data.get("MerchantRequestID"),
            "CustomerMessage": data.get("CustomerMessage") or "STK imetumwa",
            "message": data.get("CustomerMessage") or "Angalia simu yako — weka PIN ya M-Pesa.",
            "phone": msisdn,
            "amount": amount,
            "raw": data,
        }
    err = (
        data.get("errorMessage")
        or data.get("ResponseDescription")
        or data.get("error")
        or str(data)
    )
    return {"success": False, "message": f"STK imeshindikana: {err}", "raw": data, "http": status}


def mpesa_stk_query(checkout_request_id: str):
    """Uliza hali ya STK Push."""
    if MPESA_DEMO_MODE or (checkout_request_id or "").startswith("ws_CO_DEMO_"):
        return {
            "success": True,
            "demo": True,
            "ResultCode": "0",
            "ResultDesc": "The service request is processed successfully.",
            "message": "Malipo yamekamilika.",
        }
    token = _mpesa_access_token()
    password, timestamp = _mpesa_password_timestamp()
    payload = {
        "BusinessShortCode": MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }
    url = _mpesa_base_url() + "/mpesa/stkpushquery/v1/query"
    status, data = _mpesa_http_json(
        url,
        method="POST",
        data=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    return {
        "success": status == 200,
        "demo": False,
        "ResultCode": str(data.get("ResultCode", "")),
        "ResultDesc": data.get("ResultDesc") or data.get("errorMessage") or "",
        "raw": data,
        "http": status,
    }


# ---------- Vodacom M-Pesa Tanzania (Open API) ----------
# Portal: https://openapiportal.m-pesa.com
# Env:
#   MPESA_TZ_API_KEY, MPESA_TZ_PUBLIC_KEY (PEM au one-line),
#   MPESA_TZ_SP_CODE (Service Provider Code),
#   MPESA_TZ_ENV=sandbox|production
# Bila credentials → DEMO MODE (C2B inasimuliwa).
MPESA_TZ_API_KEY = os.environ.get("MPESA_TZ_API_KEY", "").strip()
MPESA_TZ_PUBLIC_KEY = os.environ.get("MPESA_TZ_PUBLIC_KEY", "").strip()
MPESA_TZ_SP_CODE = os.environ.get("MPESA_TZ_SP_CODE", "000000").strip()
MPESA_TZ_ENV = (os.environ.get("MPESA_TZ_ENV") or "sandbox").strip().lower()
MPESA_TZ_DEMO_MODE = not (MPESA_TZ_API_KEY and MPESA_TZ_PUBLIC_KEY)

_MPESA_TZ_SESSION = {"token": None, "expires": 0}


def _mpesa_tz_base_url():
    # Open API IPG paths (vodacomTZN)
    if MPESA_TZ_ENV == "production":
        return "https://openapi.m-pesa.com/openapi/ipg/v2/vodacomTZN"
    return "https://openapi.m-pesa.com/sandbox/ipg/v2/vodacomTZN"


def _mpesa_tz_format_public_key(raw: str) -> str:
    """Normalize public key to PEM."""
    key = (raw or "").strip()
    if not key:
        return ""
    if "BEGIN" in key:
        return key.replace("\\n", "\n")
    # one-line base64 body
    body = "".join(key.split())
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return "-----BEGIN PUBLIC KEY-----\n" + "\n".join(lines) + "\n-----END PUBLIC KEY-----"


def _mpesa_tz_encrypt_api_key(api_key: str, public_key_pem: str) -> str:
    """RSA PKCS1 v1.5 encrypt API key → base64 (Bearer token)."""
    pem = _mpesa_tz_format_public_key(public_key_pem)
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import padding as asy_padding
        from cryptography.hazmat.backends import default_backend
        pub = serialization.load_pem_public_key(pem.encode("utf-8"), backend=default_backend())
        encrypted = pub.encrypt(api_key.encode("utf-8"), asy_padding.PKCS1v15())
        return base64.b64encode(encrypted).decode("utf-8")
    except ImportError:
        pass
    try:
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_v1_5
        pub = RSA.import_key(pem)
        cipher = PKCS1_v1_5.new(pub)
        encrypted = cipher.encrypt(api_key.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")
    except ImportError:
        raise RuntimeError(
            "Vodacom TZ inahitaji cryptography au pycryptodome: "
            "pip install cryptography"
        )


def _mpesa_tz_session_token():
    """Generate / cache SessionKey token for Open API."""
    now = time.time()
    if _MPESA_TZ_SESSION["token"] and _MPESA_TZ_SESSION["expires"] > now + 60:
        return _MPESA_TZ_SESSION["token"]
    if MPESA_TZ_DEMO_MODE:
        return "DEMO_TZ_SESSION"
    bearer = _mpesa_tz_encrypt_api_key(MPESA_TZ_API_KEY, MPESA_TZ_PUBLIC_KEY)
    url = _mpesa_tz_base_url() + "/getSession/"
    status, data = _mpesa_http_json(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {bearer}",
            "Origin": "*",
        },
    )
    # Response shapes vary: output_ResponseCode, sessionId, token, etc.
    token = (
        (data or {}).get("output_SessionID")
        or (data or {}).get("sessionId")
        or (data or {}).get("token")
        or (data or {}).get("output_Response")
    )
    if isinstance(token, dict):
        token = token.get("SessionID") or token.get("sessionId")
    if not token and status == 200 and data:
        # sometimes whole body is usable
        token = data.get("output_ResponseCode") == "0" and data.get("output_SessionID")
    if not token:
        raise RuntimeError(f"Vodacom TZ session imeshindikana ({status}): {data}")
    _MPESA_TZ_SESSION["token"] = str(token)
    _MPESA_TZ_SESSION["expires"] = now + 3500  # ~1h typical
    return _MPESA_TZ_SESSION["token"]


def vodacom_tz_c2b(phone: str, amount: int, order_id: str, description: str = None):
    """
    Customer-to-Business (malipo kutoka simu ya mteja → biashara).
    amount: TZS integer
    """
    amount = max(1, int(amount))
    msisdn = _normalize_msisdn(phone, "Tanzania")
    if not msisdn.startswith("255") or len(msisdn) < 12:
        return {
            "success": False,
            "message": "Namba ya simu si sahihi. Tumia 07XXXXXXXX (Vodacom TZ).",
        }

    conversation_id = "NM" + secrets.token_hex(12)
    tx_ref = (order_id or "ORD")[:20].replace("-", "")

    if MPESA_TZ_DEMO_MODE:
        checkout_id = "TZ_DEMO_" + secrets.token_hex(6).upper()
        return {
            "success": True,
            "demo": True,
            "provider": "vodacom_tz",
            "CheckoutRequestID": checkout_id,
            "ConversationID": conversation_id,
            "TransactionReference": tx_ref,
            "message": "Ombi la malipo limetumwa. Thibitisha kwa PIN ya M-Pesa.",
            "phone": msisdn,
            "amount": amount,
            "currency": "TZS",
        }

    try:
        session_token = _mpesa_tz_session_token()
    except Exception as e:
        return {"success": False, "message": f"Session TZ: {e}"}

    payload = {
        "input_Amount": str(amount),
        "input_Country": "TZN",
        "input_Currency": "TZS",
        "input_CustomerMSISDN": msisdn,
        "input_ServiceProviderCode": MPESA_TZ_SP_CODE,
        "input_ThirdPartyConversationID": conversation_id,
        "input_TransactionReference": tx_ref,
        "input_PurchasedItemsDesc": (description or f"NjiaMauzo {order_id}")[:50],
    }
    url = _mpesa_tz_base_url() + "/c2bPayment/singleStage/"
    status, data = _mpesa_http_json(
        url,
        method="POST",
        data=payload,
        headers={
            "Authorization": f"Bearer {session_token}",
            "Origin": "*",
        },
    )
    # Success: output_ResponseCode == "INS-0" au "0"
    code = str(
        (data or {}).get("output_ResponseCode")
        or (data or {}).get("ResponseCode")
        or ""
    )
    desc = (
        (data or {}).get("output_ResponseDesc")
        or (data or {}).get("ResponseDescription")
        or (data or {}).get("output_Response")
        or ""
    )
    conv = (data or {}).get("output_ConversationID") or conversation_id
    tx = (data or {}).get("output_TransactionID") or tx_ref

    ok_codes = {"INS-0", "0", "INS0", "success"}
    if status in (200, 201) and (code in ok_codes or "success" in str(desc).lower()):
        return {
            "success": True,
            "demo": False,
            "provider": "vodacom_tz",
            "CheckoutRequestID": str(conv or tx),
            "ConversationID": str(conv),
            "TransactionReference": str(tx),
            "ResponseCode": code,
            "message": desc or "Angalia simu — thibitisha malipo kwa PIN ya M-Pesa.",
            "phone": msisdn,
            "amount": amount,
            "currency": "TZS",
            "raw": data,
        }

    err = desc or (data or {}).get("error") or str(data)
    return {
        "success": False,
        "message": f"Vodacom TZ C2B imeshindikana: {err}",
        "raw": data,
        "http": status,
    }


def vodacom_tz_query(conversation_id: str, order_id: str = None):
    """Angalia hali ya muamala (ikiwa API inaruhusu). DEMO = success baada ya muda."""
    if MPESA_TZ_DEMO_MODE or (conversation_id or "").startswith("TZ_DEMO_"):
        return {
            "success": True,
            "demo": True,
            "ResultCode": "0",
            "ResultDesc": "DEMO TZ success",
            "message": "Malipo yamekamilika.",
        }
    # Open API transaction status endpoint (varies by portal version)
    try:
        session_token = _mpesa_tz_session_token()
    except Exception as e:
        return {"success": False, "ResultCode": "1", "ResultDesc": str(e)}
    payload = {
        "input_QueryReference": conversation_id,
        "input_ServiceProviderCode": MPESA_TZ_SP_CODE,
        "input_Country": "TZN",
        "input_ThirdPartyConversationID": "Q" + secrets.token_hex(8),
    }
    url = _mpesa_tz_base_url() + "/queryTransactionStatus/"
    status, data = _mpesa_http_json(
        url,
        method="POST",
        data=payload,
        headers={"Authorization": f"Bearer {session_token}", "Origin": "*"},
    )
    code = str((data or {}).get("output_ResponseCode") or (data or {}).get("ResponseCode") or "")
    desc = (data or {}).get("output_ResponseDesc") or (data or {}).get("ResponseDescription") or ""
    return {
        "success": status == 200,
        "demo": False,
        "ResultCode": "0" if code in ("INS-0", "0") else code,
        "ResultDesc": desc,
        "raw": data,
        "http": status,
    }



# Makadirio ya ubadilishaji fedha (thamani ya TZS 1 kwa kila sarafu).
# Hizi ni makadirio ya display tu — production halisi inapaswa kutumia
# huduma ya FX (mfano exchangerate.host) badala ya namba fasta.
# Afrika Mashariki — makadirio ya FX (display). Production: FX API.
COUNTRY_CURRENCY = {
    "Tanzania": {"code": "TZS", "rate_per_tzs": 1.0, "flag": "🇹🇿", "phone_prefix": "255"},
    "Kenya": {"code": "KES", "rate_per_tzs": 0.027, "flag": "🇰🇪", "phone_prefix": "254"},
    "Uganda": {"code": "UGX", "rate_per_tzs": 1.42, "flag": "🇺🇬", "phone_prefix": "256"},
    "Rwanda": {"code": "RWF", "rate_per_tzs": 0.53, "flag": "🇷🇼", "phone_prefix": "250"},
    "Burundi": {"code": "BIF", "rate_per_tzs": 0.59, "flag": "🇧🇮", "phone_prefix": "257"},
    "South Sudan": {"code": "SSP", "rate_per_tzs": 0.055, "flag": "🇸🇸", "phone_prefix": "211"},
    "DR Congo": {"code": "CDF", "rate_per_tzs": 1.05, "flag": "🇨🇩", "phone_prefix": "243"},
    "Ethiopia": {"code": "ETB", "rate_per_tzs": 0.045, "flag": "🇪🇹", "phone_prefix": "251"},
    "Somalia": {"code": "SOS", "rate_per_tzs": 0.22, "flag": "🇸🇴", "phone_prefix": "252"},
}

# Njia za malipo kwa kila nchi (mobile money)
COUNTRY_PAYMENT_METHODS = {
    "Tanzania": ["M-Pesa", "Airtel Money", "Halotel", "Tigo Pesa", "Google Pay"],
    "Kenya": ["M-Pesa", "Airtel Money", "Google Pay"],
    "Uganda": ["MTN MoMo", "Airtel Money", "Google Pay"],
    "Rwanda": ["MTN MoMo", "Airtel Money", "Google Pay"],
    "Burundi": ["Lumicash", "Ecocash", "Google Pay"],
    "South Sudan": ["m-Gurush", "Google Pay"],
    "DR Congo": ["M-Pesa", "Airtel Money", "Orange Money", "Google Pay"],
    "Ethiopia": ["Telebirr", "Google Pay"],
    "Somalia": ["EVC Plus", "Google Pay"],
}

# Subscription plans (muda wa ufikiaji baada ya malipo)
# multiplier: bei = SERVICE_FEE_TZS * multiplier (makadirio)
SUBSCRIPTION_PLANS = {
    "once": {
        "id": "once",
        "label_sw": "Dakika 10",
        "label_en": "10 Minutes",
        "seconds": 10 * 60,
        "multiplier": 1.0,   # TZS 3,000
    },
    "1h": {
        "id": "1h",
        "label_sw": "Saa 1",
        "label_en": "1 Hour",
        "seconds": 60 * 60,
        "multiplier": 1.7,   # ≈ TZS 5,100
    },
    "daily": {
        "id": "daily",
        "label_sw": "Siku 1",
        "label_en": "1 Day",
        "seconds": 24 * 3600,
        "multiplier": 2.7,   # ≈ TZS 8,100
    },
    "weekly": {
        "id": "weekly",
        "label_sw": "Wiki 1",
        "label_en": "1 Week",
        "seconds": 7 * 24 * 3600,
        "multiplier": 8.3,   # ≈ TZS 25,000
    },
    "monthly": {
        "id": "monthly",
        "label_sw": "Mwezi 1",
        "label_en": "1 Month",
        "seconds": 30 * 24 * 3600,
        "multiplier": 23.3,  # ≈ TZS 70,000
    },
}

# ===== Featured Products / Matangazo - bei za rejea (TZS) =====
FEATURED_PRICE_TZS = {"7d": 15000, "14d": 22000, "30d": 30000}
MARQUEE_AD_PRICE_TZS = {"day": 10000, "week": 30000, "month": 50000}
ADVISORY_SESSION_PRICE_TZS = {"quick": 5000, "standard": 12000, "deep": 20000}

GOOGLE_PAY_MERCHANT_ID = os.environ.get("GOOGLE_PAY_MERCHANT_ID", "").strip()
GOOGLE_PAY_MERCHANT_NAME = os.environ.get("GOOGLE_PAY_MERCHANT_NAME", "NjiaMauzo Afrika")
GOOGLE_PAY_DEMO = not bool(os.environ.get("GOOGLE_PAY_LIVE", "").strip())


def _refresh_live_exchange_rates():
    """Pakua viwango halisi vya ubadilishaji fedha (TZS -> kila sarafu) kutoka
    huduma ya bure ya FX, na sasisha COUNTRY_CURRENCY. Ikishindikana (mfano
    hakuna internet), tunabaki na makadirio ya static yaliyowekwa hapo juu."""
    try:
        url = "https://open.er-api.com/v6/latest/TZS"
        req = urllib.request.Request(url, headers={"User-Agent": "NjiaMauzoAfrika/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        rates = payload.get("rates") or {}
        if not rates:
            return
        for country, info in COUNTRY_CURRENCY.items():
            code = info.get("code")
            if code in rates and rates[code]:
                info["rate_per_tzs"] = float(rates[code])
        global _FX_UPDATED_AT
        _FX_UPDATED_AT = datetime.utcnow().isoformat() + "Z"
    except Exception:
        pass  # tumia makadirio ya static yaliyopo


_FX_UPDATED_AT = None


def _exchange_rate_worker():
    while True:
        _refresh_live_exchange_rates()
        time.sleep(6 * 3600)  # sasisha kila masaa 6


threading.Thread(target=_exchange_rate_worker, daemon=True).start()


@app.route("/api/exchange-rates", methods=["GET"])
def api_exchange_rates():
    return jsonify({
        "success": True,
        "base": "TZS",
        "rates": {c: i["rate_per_tzs"] for c, i in COUNTRY_CURRENCY.items()},
        "updated_at": _FX_UPDATED_AT,
        "live": _FX_UPDATED_AT is not None,
    })


@app.route("/api/service/fee", methods=["GET"])
def api_service_fee():
    country = request.args.get("country", "Tanzania")
    info = COUNTRY_CURRENCY.get(country, COUNTRY_CURRENCY["Tanzania"])
    amount = round(SERVICE_FEE_TZS * info["rate_per_tzs"])
    return jsonify({
        "success": True,
        "country": country,
        "currency": info["code"],
        "base_amount_tzs": SERVICE_FEE_TZS,
        "amount": amount,
        "note": "Makadirio ya display; siyo kiwango cha benki cha wakati halisi.",
    })

# Malipo halisi: order huanza "pending" na HAIFUNGUI ufikiaji.
# Inafunguliwa TU baada ya admin kuithibitisha kupitia
# /api/service/admin-verify (baada ya kukagua uthibitisho wa malipo).
PAYMENT_ORDERS = {}
PAYMENT_LOCK = threading.Lock()


PRODUCTS_LOCK = threading.Lock()
_next_product_id = len(SAMPLE_PRODUCTS) + 1

_NEW_PRODUCT_CROPS = [
    ("Mpunga", "🌾", ["Mwanza", "Shinyanga", "Morogoro"]),
    ("Korosho", "🌰", ["Mtwara", "Lindi", "Newala"]),
    ("Alizeti", "🌻", ["Singida", "Dodoma", "Iringa"]),
    ("Maharage", "🫘", ["Mbeya", "Songwe", "Njombe"]),
    ("Karanga", "🥜", ["Tabora", "Kigoma", "Nzega"]),
    ("Viazi", "🥔", ["Njombe", "Iringa", "Mbeya"]),
    ("Vitunguu", "🧅", ["Singida", "Dodoma", "Manyara"]),
    ("Pamba", "🌱", ["Shinyanga", "Simiyu", "Mwanza"]),
]
_NEW_PRODUCT_SELLERS = [
    "Kilimo Bora Ltd", "Mavuno Fresh", "Tanzania Agro Hub", "Soko Kuu Traders",
    "Green Harvest Co", "Mkulima Mkuu", "AgriLink Tanzania", "Panda Mazao Ltd",
]


def _generate_new_product():
    global _next_product_id
    import random
    crop, emoji, locations = random.choice(_NEW_PRODUCT_CROPS)
    seller = random.choice(_NEW_PRODUCT_SELLERS)
    location = random.choice(locations)
    phone = "07" + str(random.randint(10000000, 99999999))
    with PRODUCTS_LOCK:
        pid = _next_product_id
        _next_product_id += 1
        SAMPLE_PRODUCTS.append({
            "id": pid,
            "title": crop,
            "description": f"{crop} safi kutoka {location} — kiwango cha juu, tayari kwa uuzaji.",
            "seller_id": f"auto{pid}",
            "seller_name": seller,
            "seller_phone": phone,
            "seller_whatsapp": phone,
            "seller_email": "",
            "seller_telegram": "",
            "seller_facebook": "",
            "seller_instagram": "",
            "location": location,
            "real_price": random.randint(800, 9000),
            "unit": "kg",
            "transport_cost": random.randint(3000, 15000),
            "transport_note": "Makadirio ya usafiri hadi eneo lako",
            "likes": random.randint(0, 6),
            "image": "https://images.unsplash.com/photo-1464226184884-fa280b87c399?w=500&h=360&fit=crop",
            "emoji": emoji,
            "color": "#0b7d45",
            "featured": random.random() < 0.25,
        })
        # Kikomo cha bidhaa 20.
        if len(SAMPLE_PRODUCTS) > 20:
            del SAMPLE_PRODUCTS[: len(SAMPLE_PRODUCTS) - 20]


# Anza na bidhaa 16 ili soko liwe na kiwango cha 16–20 wakati wote.
for _ in range(max(0, 16 - len(SAMPLE_PRODUCTS))):
    try:
        _generate_new_product()
    except Exception:
        pass


def _product_feed_worker():
    import random
    while True:
        # Live 24/7 — bidhaa mpya kila dakika 2.
        time.sleep(120)
        try:
            _generate_new_product()
        except Exception:
            pass


threading.Thread(target=_product_feed_worker, daemon=True).start()

# ---------- AI Searcher (automatic product discovery + bot thinking) ----------
AI_SEARCH_LOCK = threading.Lock()
AI_THINKING_LOG = []  # strings
AI_FOUND_PRODUCTS = []  # recent products discovered by AI
AI_CURRENT_THOUGHT = ""
_AI_QUERIES = [
    "mahindi Mbeya", "kahawa Arusha", "ufuta Ruvuma", "mpunga Morogoro",
    "maharage Kigoma", "alizeti Dodoma", "korosho Mtwara", "chai Iringa",
    "ndizi Kagera", "viazi Njombe", "kunde Mwanza", "kunde Tabora",
    "parachichi Kilimanjaro", "miwa Shinyanga", "karanga Singida",
]


def _ai_think(msg: str):
    global AI_CURRENT_THOUGHT
    ts = datetime.utcnow().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with AI_SEARCH_LOCK:
        AI_CURRENT_THOUGHT = msg
        AI_THINKING_LOG.append(line)
        if len(AI_THINKING_LOG) > 80:
            del AI_THINKING_LOG[: len(AI_THINKING_LOG) - 80]
    print(f"[AI-Searcher] {line}")


def _ai_search_and_ingest(query: str = None):
    """Bot thinking + generate product as if searched from market."""
    with PRODUCTS_LOCK:
        if len(SAMPLE_PRODUCTS) >= 20:
            _ai_think("Kikomo cha bidhaa 20 kimefikiwa — search itaendelea bila kuongeza listing.")
            return True
    import random
    q = query or random.choice(_AI_QUERIES)
    _ai_think(f"Inachambua swali: «{q}»…")
    time.sleep(0.3)
    _ai_think(f"Inatafuta masoko Afrika Mashariki yanayohusiana na «{q}»…")
    time.sleep(0.25)
    # reuse product generator
    before = len(SAMPLE_PRODUCTS)
    try:
        _generate_new_product()
        # optionally bias title from query first word
        with PRODUCTS_LOCK:
            if SAMPLE_PRODUCTS:
                p = SAMPLE_PRODUCTS[-1]
                parts = q.split()
                if parts and random.random() < 0.55:
                    p["title"] = parts[0].capitalize()
                    p["description"] = f"AI Searcher imepata: {q} — {p['description']}"
                snap = {
                    "id": p["id"],
                    "title": p["title"],
                    "location": p.get("location"),
                    "real_price": p.get("real_price"),
                    "emoji": p.get("emoji"),
                    "seller_name": p.get("seller_name"),
                    "query": q,
                    "found_at": datetime.utcnow().isoformat() + "Z",
                }
                with AI_SEARCH_LOCK:
                    AI_FOUND_PRODUCTS.append(snap)
                    if len(AI_FOUND_PRODUCTS) > 60:
                        del AI_FOUND_PRODUCTS[: len(AI_FOUND_PRODUCTS) - 60]
        _ai_think(
            f"Imepatikana: {snap['title']} @ {snap['location']} "
            f"(TZS {snap['real_price']:,}) — imeongezwa kwenye dashboard."
        )
    except Exception as e:
        _ai_think(f"Hitilafu wakati wa utafutaji: {e}")
    return True


def _ai_search_worker():
    import random
    time.sleep(4)
    while True:
        try:
            _ai_search_and_ingest()
        except Exception:
            pass
        time.sleep(random.randint(12, 28))


threading.Thread(target=_ai_search_worker, daemon=True).start()



def _cleanup_sessions():
    now = datetime.utcnow()
    with SESSION_LOCK:
        dead = [k for k, v in CONTACT_SESSIONS.items()
                if (now - v["created"]).total_seconds() > SESSION_TTL]
        for k in dead:
            CONTACT_SESSIONS.pop(k, None)


def _send_channel(channel, address, message):
    print(f"[NjiaMauzo] {channel.upper()} -> {address}: {message[:90]}...")
    return True


def notify_seller(data):
    msg = data.get("message") or (
        "Sisi ni NjiaMauzo Afrika, KITOVU CHA BIASHARA AFRIKA. "
        "Mteja wetu anataka kufanya BIASHARA na kampuni/na wewe. "
        "Tafadhali wasiliana naye kupitia NjiaMauzo Afrika."
    )
    results = {}
    pairs = [
        ("sms", data.get("phone")),
        ("whatsapp", data.get("whatsapp") or data.get("phone")),
        ("email", data.get("email")),
        ("telegram", data.get("telegram")),
        ("facebook", data.get("facebook")),
        ("instagram", data.get("instagram")),
    ]
    for ch, addr in pairs:
        if addr and str(addr).strip():
            results[ch] = _send_channel(ch, str(addr).strip(), msg)
    return results


def _grant_access(seconds=None):
    """Fungua ufikiaji kwa muda (default dakika 15). Admin hauna kikomo."""
    secs = int(seconds if seconds is not None else ACCESS_DURATION_SEC)
    session["unlocked"] = True
    session["unlocked_until"] = datetime.utcnow().timestamp() + secs
    return secs


def _remaining_access_seconds():
    if session.get("is_admin"):
        return 24 * 3600  # admin: siku nzima (display)
    until = session.get("unlocked_until")
    if not until:
        if session.get("unlocked"):
            # legacy: weka dirisha la dakika 10
            _grant_access()
            until = session.get("unlocked_until")
        else:
            return 0
    left = int(until - datetime.utcnow().timestamp())
    if left <= 0:
        session.pop("unlocked", None)
        session.pop("unlocked_until", None)
        return 0
    return left


def _is_unlocked():
    if session.get("is_admin"):
        return True
    return _remaining_access_seconds() > 0


def _products_for_client():
    unlocked = _is_unlocked()
    out = []
    with PRODUCTS_LOCK:
        snapshot = list(SAMPLE_PRODUCTS)
    now_iso = datetime.utcnow().isoformat() + "Z"
    for p in snapshot:
        item = dict(p)
        # Featured inayoisha muda inarudi kuwa ya kawaida kiotomatiki
        if item.get("featured") and item.get("featured_until") and item["featured_until"] < now_iso:
            item["featured"] = False
        item["full_access"] = unlocked
        if not unlocked:
            hide = ("real_price", "seller_phone", "seller_whatsapp", "seller_email",
                    "seller_telegram", "seller_facebook", "seller_instagram",
                    "transport_cost", "transport_note")
            item = {k: v for k, v in item.items() if k not in hide}
            item["full_access"] = False
            item["seller_name"] = ""
            item["location"] = ""
        out.append(item)
    # Featured kwanza, kisha likes nyingi zaidi
    out.sort(key=lambda p: (not p.get("featured", False), -(p.get("likes", 0) or 0)))
    return out


@app.route("/api/admin/products/<int:pid>/featured", methods=["POST"])
def api_admin_product_featured(pid):
    """Fanya bidhaa iwe 'Featured' (ionekane juu) kwa siku kadhaa - malipo
    ya nje (7d=TZS 15,000, 14d=TZS 22,000, 30d=TZS 30,000) yanashughulikiwa
    na admin kwa mkono kwa sasa (kama matangazo)."""
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    data = request.get_json(silent=True) or {}
    days = int(data.get("days") or 7)
    enable = data.get("enable", True) is not False
    with PRODUCTS_LOCK:
        found = False
        for p in SAMPLE_PRODUCTS:
            if p.get("id") == pid:
                p["featured"] = enable
                if enable:
                    p["featured_until"] = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"
                else:
                    p.pop("featured_until", None)
                found = True
                break
    if not found:
        return jsonify({"success": False, "message": "Bidhaa haipatikani."}), 404
    return jsonify({"success": True, "message": f"Bidhaa {'imefanywa Featured kwa siku ' + str(days) if enable else 'imeondolewa Featured'}."})


# ================= PUBLIC CONFIG / GOOGLE ADSENSE =================
ADSENSE_CLIENT_ID = os.environ.get("ADSENSE_CLIENT_ID", "").strip()
ADSENSE_SLOT_MARKET = os.environ.get("ADSENSE_SLOT_MARKET", "").strip()

@app.route("/api/public-config", methods=["GET"])
def api_public_config():
    return jsonify({
        "success": True,
        "adsense": {
            "enabled": bool(ADSENSE_CLIENT_ID),
            "client_id": ADSENSE_CLIENT_ID,
            "market_slot": ADSENSE_SLOT_MARKET,
        },
    })

# ================= VISITOR ANALYTICS =================
ANALYTICS_DB = Path(os.environ.get("ANALYTICS_DB", str(BASE_DIR / "visitor_analytics.sqlite3")))
ANALYTICS_LOCK = threading.Lock()

def _analytics_db():
    conn = sqlite3.connect(str(ANALYTICS_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visitor_id TEXT NOT NULL,
        ip_hash TEXT, user_agent TEXT, path TEXT, referrer TEXT,
        created_at TEXT NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_visits_created ON visits(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_visits_visitor ON visits(visitor_id)")
    conn.commit()
    return conn

def _hash_ip(ip):
    salt = os.environ.get("ANALYTICS_IP_SALT", "njiamauzo-analytics")
    return hashlib.sha256((salt + "|" + (ip or "unknown")).encode()).hexdigest()

def _record_visit():
    visitor_id = request.cookies.get("nm_visitor_id") or secrets.token_urlsafe(18)
    path = request.path[:500]
    referrer = (request.headers.get("Referer") or "")[:500]
    ua = (request.headers.get("User-Agent") or "")[:500]
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    with ANALYTICS_LOCK:
        conn = _analytics_db()
        conn.execute("INSERT INTO visits(visitor_id,ip_hash,user_agent,path,referrer,created_at) VALUES(?,?,?,?,?,?)",
                     (visitor_id, _hash_ip(_client_ip()), ua, path, referrer, now))
        conn.commit(); conn.close()
    return visitor_id

@app.route("/api/analytics/visit", methods=["POST"])
def api_analytics_visit():
    visitor_id = _record_visit()
    resp = jsonify({"success": True})
    resp.set_cookie("nm_visitor_id", visitor_id, max_age=60*60*24*365, httponly=True, samesite="Lax", secure=bool(os.environ.get("SESSION_COOKIE_SECURE", "").strip()))
    return resp

def _analytics_stats():
    with ANALYTICS_LOCK:
        conn = _analytics_db()
        total = conn.execute("SELECT COUNT(*) c FROM visits").fetchone()["c"]
        unique = conn.execute("SELECT COUNT(DISTINCT visitor_id) c FROM visits").fetchone()["c"]
        today = datetime.utcnow().date().isoformat()
        today_visits = conn.execute("SELECT COUNT(*) c FROM visits WHERE substr(created_at,1,10)=?", (today,)).fetchone()["c"]
        today_unique = conn.execute("SELECT COUNT(DISTINCT visitor_id) c FROM visits WHERE substr(created_at,1,10)=?", (today,)).fetchone()["c"]
        since = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
        live = conn.execute("SELECT COUNT(DISTINCT visitor_id) c FROM visits WHERE created_at>=?", (since,)).fetchone()["c"]
        pages = conn.execute("SELECT path, COUNT(*) c FROM visits GROUP BY path ORDER BY c DESC LIMIT 10").fetchall()
        daily = conn.execute("SELECT substr(created_at,1,10) d, COUNT(*) c, COUNT(DISTINCT visitor_id) u FROM visits GROUP BY d ORDER BY d DESC LIMIT 14").fetchall()
        recent = conn.execute("SELECT created_at,path,user_agent FROM visits ORDER BY id DESC LIMIT 20").fetchall()
        conn.close()
    return {
        "total_visits": total, "unique_visitors": unique, "today_visits": today_visits,
        "today_unique": today_unique, "live_5m": live,
        "top_pages": [{"path":r["path"],"views":r["c"]} for r in pages],
        "daily": [{"date":r["d"],"views":r["c"],"unique":r["u"]} for r in daily],
        "recent": [dict(r) for r in recent],
    }

def _analytics_init_discussions(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS view_discussions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_discussions_created ON view_discussions(created_at)")
    conn.commit()

@app.route("/api/admin/view-discussions", methods=["GET"])
def api_admin_view_discussions():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    with ANALYTICS_LOCK:
        conn = _analytics_db()
        _analytics_init_discussions(conn)
        rows = conn.execute(
            "SELECT id,message,created_at FROM view_discussions ORDER BY id DESC LIMIT 50"
        ).fetchall()
        conn.close()
    return jsonify({"success": True, "discussions": [dict(r) for r in rows]})

@app.route("/api/admin/view-discussions", methods=["POST"])
def api_admin_view_discussions_add():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    ok, err = _require_csrf()
    if not ok:
        return err
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()[:1000]
    if not message:
        return jsonify({"success": False, "message": "Andika ujumbe wa majadiliano."}), 400
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    with ANALYTICS_LOCK:
        conn = _analytics_db()
        _analytics_init_discussions(conn)
        conn.execute("INSERT INTO view_discussions(message,created_at) VALUES(?,?)", (message, now))
        conn.commit()
        conn.close()
    return jsonify({"success": True, "message": "Ujumbe umehifadhiwa."})

@app.route("/api/admin/analytics", methods=["GET"])
def api_admin_analytics():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    return jsonify({"success": True, **_analytics_stats()})

@app.route("/api/site-status", methods=["GET"])
def api_site_status():
    active, start, end, now = _sabbath_window()
    return jsonify({
        "success": True, "sabbath": active, "timezone": SABBATH_TZ,
        "ads_open": True,
        "services_open": (not active) or bool(session.get("is_admin")),
        "sabbath_start": start.isoformat() if start else None,
        "sabbath_end": end.isoformat() if end else None,
        "reference_lat": SABBATH_LAT, "reference_lon": SABBATH_LON,
        "message": "Huduma zimefungwa kuanzia Ijumaa baada ya jua kuzama hadi Jumamosi baada ya jua kuzama." if active else "Huduma ziko wazi.",
    })


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        return send_from_directory(str(static_dir), filename)
    return "", 404


@app.route("/api/csrf", methods=["GET"])
@app.route("/api/csrf-token", methods=["GET"])
def api_csrf():
    token = session.get("csrf") or secrets.token_hex(16)
    session["csrf"] = token
    return jsonify({"csrf_token": token, "success": True})


@app.route("/api/me", methods=["GET"])
def api_me():
    return jsonify({
        "logged_in": bool(session.get("user")),
        "user": session.get("user"),
        "is_admin": bool(session.get("is_admin")),
        "unlocked": _is_unlocked(),
    })


@app.route("/api/login", methods=["POST"])
@rate_limit("login", max_attempts=10, window_seconds=300)
def api_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if email and password:
        session["user"] = {"email": email, "name": email.split("@")[0]}
        return jsonify({"success": True, "message": "Umeingia."})
    return jsonify({"success": False, "message": "Email au nywila si sahihi."})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("user", None)
    return jsonify({"success": True})


@app.route("/api/register", methods=["POST"])
@rate_limit("register", max_attempts=8, window_seconds=600)
def api_register():
    data = request.get_json(silent=True) or {}
    if not data.get("email") or not data.get("password"):
        return jsonify({"success": False, "message": "Jaza email na nywila."})
    session["user"] = {
        "email": data.get("email"),
        "name": data.get("name") or data.get("email"),
        "phone": data.get("phone"),
    }
    return jsonify({"success": True, "message": "Umesajiliwa.", "csrf_token": session.get("csrf")})


@app.route("/api/captcha", methods=["GET"])
def api_captcha():
    a, b = 3, 7
    cid = secrets.token_hex(8)
    session[f"captcha_{cid}"] = a + b
    return jsonify({"captcha_id": cid, "question": f"{a} + {b} = ?"})



# ===== MULTI ADMIN ROOMS / LEADERSHIP =====
ADMIN_MAX_ACCOUNTS = 15
ADMIN_ROLES = {"director", "accountant", "admin", "support", "marketing", "seller"}

def _admin_accounts_db():
    conn = _analytics_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS admin_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin',
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        last_login_at TEXT
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_admin_accounts_active ON admin_accounts(active)")
    conn.commit()
    return conn

def _admin_hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 180000).hex()
    return f"pbkdf2_sha256$180000${salt}${digest}"

def _admin_check_password(password, encoded):
    try:
        alg, rounds, salt, digest = encoded.split('$', 3)
        if alg != 'pbkdf2_sha256':
            return False
        got = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), int(rounds)).hex()
        return secrets.compare_digest(got, digest)
    except Exception:
        return False

def _admin_audit(action, target='', details=''):
    try:
        conn = _analytics_db()
        conn.execute("""CREATE TABLE IF NOT EXISTS admin_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, display_name TEXT, role TEXT,
            action TEXT NOT NULL, target TEXT, details TEXT, created_at TEXT NOT NULL
        )""")
        a = session.get('admin') or {}
        conn.execute("INSERT INTO admin_audit(username,display_name,role,action,target,details,created_at) VALUES(?,?,?,?,?,?,?)",
                     (a.get('username') or session.get('admin_username'), a.get('display_name') or '', a.get('role') or '',
                      action, target, details, datetime.utcnow().isoformat()+'Z'))
        conn.commit(); conn.close()
    except Exception:
        pass

def _seed_admin_accounts():
    conn = _admin_accounts_db()
    count = conn.execute('SELECT COUNT(*) FROM admin_accounts').fetchone()[0]
    if count == 0:
        now = datetime.utcnow().isoformat()+'Z'
        seeds = [
            (os.environ.get('DIRECTOR_USERNAME','director').strip(), os.environ.get('DIRECTOR_PASSWORD','NjiaMauzoDirector2026!'), 'Mkurugenzi Mkuu', 'director'),
            (os.environ.get('ACCOUNTANT_USERNAME','accountant').strip(), os.environ.get('ACCOUNTANT_PASSWORD','NjiaMauzoMhasibu2026!'), 'Mhasibu', 'accountant'),
        ]
        for u,pw,name,role in seeds:
            conn.execute('INSERT OR IGNORE INTO admin_accounts(username,password_hash,display_name,role,active,created_at) VALUES(?,?,?,?,1,?)',
                         (u, _admin_hash_password(pw), name, role, now))
        conn.commit()
    conn.close()

_seed_admin_accounts()

def _current_admin():
    a = session.get('admin')
    if a:
        return a
    # Legacy sessions remain compatible.
    if session.get('is_admin'):
        return {'username': session.get('admin_username') or ADMIN_USER, 'display_name': (session.get('user') or {}).get('name') or 'Admin', 'role': (session.get('user') or {}).get('role') or 'admin'}
    return None

def _admin_role_allowed(*roles):
    a = _current_admin()
    return bool(a and a.get('role') in roles)

def _admin_temp_open():
    """True while the temporary 60-hour passwordless Admin Room window is active."""
    try:
        raw = ADMIN_TEMP_OPEN_UNTIL.replace("Z", "+00:00")
        until = datetime.fromisoformat(raw)
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < until.astimezone(timezone.utc)
    except Exception:
        return False

def _admin_temp_seconds_left():
    try:
        raw = ADMIN_TEMP_OPEN_UNTIL.replace("Z", "+00:00")
        until = datetime.fromisoformat(raw)
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        return max(0, int((until.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds()))
    except Exception:
        return 0

@app.route("/api/admin/access-mode", methods=["GET"])
def api_admin_access_mode():
    return jsonify({
        "success": True,
        "temporary_open": _admin_temp_open(),
        "seconds_left": _admin_temp_seconds_left(),
        "restore_username": ADMIN_USER,
        "restore_requires_password": True,
    })

@app.route("/api/admin/temp-login", methods=["POST"])
def api_admin_temp_login():
    """Fungua Admin Room bila username/password ndani ya dirisha la muda la saa 60."""
    if not _admin_temp_open():
        return jsonify({
            "ok": False,
            "success": False,
            "error": "Dirisha la kufungua Admin Room bila password limekwisha. Tumia username na password.",
            "message": "Dirisha la kufungua Admin Room bila password limekwisha. Tumia username na password.",
        }), 403

    # Temporary access ni ya chumba cha mmiliki/Mkurugenzi.
    admin = {
        "username": ADMIN_USER or "director",
        "display_name": "Mkurugenzi Mkuu",
        "role": "director",
    }

    session.clear()
    session.permanent = True
    session["is_admin"] = True
    session["unlocked"] = True
    session["unlocked_until"] = datetime.utcnow().timestamp() + 60 * 3600
    session["admin"] = admin
    session["admin_username"] = admin["username"]
    session["user"] = {
        "email": admin["username"] + "@njiamauzo.tz",
        "name": admin["display_name"],
        "role": admin["role"],
    }
    session["admin_login_at"] = datetime.utcnow().isoformat() + "Z"
    session["admin_ip"] = _client_ip()
    csrf = secrets.token_hex(24)
    session["csrf"] = csrf

    _admin_audit("temporary_passwordless_login", admin["username"], "Temporary Admin Room access - 60 hours")

    return jsonify({
        "ok": True,
        "success": True,
        "message": "Admin Room imefunguliwa bila password kwa muda wa saa 60.",
        "admin": admin,
        "admin_mode": True,
        "csrf_token": csrf,
        "seconds_left": _admin_temp_seconds_left(),
        "temporary_open": True,
    })

@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    """Login ya admin kwa account binafsi; hadi accounts 15 na kila mmoja ana role/chumba."""
    ip = _client_ip()
    locked, wait = _admin_is_locked(ip)
    if locked:
        return jsonify({"success": False, "message": f"Jaribio nyingi. Subiri sekunde {wait} kisha ujaribu tena."}), 429
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    conn = _admin_accounts_db()
    row = conn.execute('SELECT * FROM admin_accounts WHERE username=? AND active=1', (username,)).fetchone()
    conn.close()
    valid = bool(row and _admin_check_password(password, row['password_hash']))
    # Backward-compatible legacy env admin becomes director if account table is not used by an old deployment.
    legacy = bool(username and password and secrets.compare_digest(username, ADMIN_USER) and secrets.compare_digest(password, ADMIN_PASS))
    if not valid and not legacy:
        _admin_register_fail(ip)
        return jsonify({"success": False, "error": "Jina la mtumiaji au password si sahihi.", "message": "Jina la mtumiaji au password si sahihi."}), 401
    _admin_clear_attempts(ip)
    if legacy:
        admin = {'username': username, 'display_name': 'Mkurugenzi Mkuu', 'role': 'director'}
    else:
        admin = {'username': row['username'], 'display_name': row['display_name'], 'role': row['role'], 'id': row['id']}
    session.clear(); session.permanent=True
    session['is_admin']=True; session['unlocked']=True
    session['unlocked_until']=datetime.utcnow().timestamp()+int(os.environ.get('ADMIN_SESSION_HOURS','8'))*3600
    session['admin']=admin; session['admin_username']=admin['username']
    session['user']={'email': admin['username']+'@njiamauzo.tz', 'name': admin['display_name'], 'role': admin['role']}
    session['admin_login_at']=datetime.utcnow().isoformat()+'Z'; session['admin_ip']=ip
    csrf=secrets.token_hex(24); session['csrf']=csrf
    try:
        conn=_admin_accounts_db()
        conn.execute('UPDATE admin_accounts SET last_login_at=? WHERE username=?', (datetime.utcnow().isoformat()+'Z', admin['username']))
        conn.commit(); conn.close()
    except Exception: pass
    _admin_audit('login', admin['username'], 'Admin login')
    return jsonify({'ok':True,'success':True,'message':'Admin umeingia.','admin':admin,'admin_mode':True,'csrf_token':csrf})

@app.route('/api/admin/me', methods=['GET'])
def api_admin_me():
    a=_current_admin()
    if not a or not session.get('is_admin'):
        return jsonify({'ok':False,'success':False,'error':'Si admin.'}),403
    return jsonify({'ok':True,'success':True,'admin':a})

@app.route('/api/admin/accounts', methods=['GET','POST'])
def api_admin_accounts():
    if not session.get('is_admin'):
        return jsonify({'ok':False,'success':False,'error':'Si admin.'}),403
    if request.method=='GET':
        conn=_admin_accounts_db()
        rows=[dict(r) for r in conn.execute('SELECT id,username,display_name,role,active,created_at,last_login_at FROM admin_accounts ORDER BY id').fetchall()]
        conn.close()
        return jsonify({'ok':True,'success':True,'admins':rows,'limit':ADMIN_MAX_ACCOUNTS})
    if not _admin_role_allowed('director'):
        return jsonify({'ok':False,'success':False,'error':'Mkurugenzi Mkuu pekee ndiye anaweza kuunda account.'}),403
    d=request.get_json(silent=True) or {}
    username=(d.get('username') or '').strip()[:60]
    display=(d.get('display_name') or '').strip()[:120]
    password=d.get('password') or ''
    role=(d.get('role') or 'admin').strip().lower()
    if not username or not display or len(password)<10 or role not in ADMIN_ROLES:
        return jsonify({'ok':False,'success':False,'error':'Weka username, jina, role sahihi na password ya angalau herufi 10.'}),400
    conn=_admin_accounts_db()
    count=conn.execute('SELECT COUNT(*) FROM admin_accounts').fetchone()[0]
    if count>=ADMIN_MAX_ACCOUNTS:
        conn.close(); return jsonify({'ok':False,'success':False,'error':'Kikomo cha admin 15 kimefikiwa.'}),400
    try:
        conn.execute('INSERT INTO admin_accounts(username,password_hash,display_name,role,active,created_at) VALUES(?,?,?,?,1,?)',
                     (username,_admin_hash_password(password),display,role,datetime.utcnow().isoformat()+'Z'))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close(); return jsonify({'ok':False,'success':False,'error':'Username hiyo tayari ipo.'}),409
    conn.close(); _admin_audit('create_admin',username,f'role={role}')
    return jsonify({'ok':True,'success':True,'message':'Account imeundwa.','username':username})

@app.route("/api/admin/logout", methods=["POST"])
def api_admin_logout():
    session.clear()
    return jsonify({"success": True, "message": "Admin ametoka."})


@app.route("/api/admin/status", methods=["GET"])
def api_admin_status():
    return jsonify({
        "success": True,
        "is_admin": bool(session.get("is_admin")),
        "unlocked": _is_unlocked(),
        "user": session.get("user"),
        "remaining_seconds": _remaining_access_seconds(),
    })



# ================= BIDHAA ZA KAWAIDA / DUKA LA NDANI =================
ORDINARY_PRODUCT_CATEGORIES = {
    "viatu": ["kiatu","viatu","shoe","shoes","sandal","sandals","slipper","slippers","kaptula","boots"],
    "mifuko": ["mfuko","mifuko","bag","bags","handbag","backpack","purse"],
    "magauni": ["gauni","magauni","dress","dresses","gown"],
    "vitambaa": ["kitambaa","vitambaa","fabric","fabrics","kitenge","khanga","kanga"],
}
ORDINARY_PRODUCT_ALLOWED_EXT = {".jpg",".jpeg",".png",".webp",".gif"}

def _ordinary_products_db():
    conn = _analytics_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS ordinary_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT,
        category TEXT NOT NULL DEFAULT 'nyingine', price_tzs INTEGER DEFAULT 0,
        image_url TEXT, stock INTEGER DEFAULT 0, active INTEGER DEFAULT 1,
        featured INTEGER DEFAULT 0, created_at TEXT NOT NULL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ordinary_category ON ordinary_products(category)")
    conn.commit(); return conn

def _infer_ordinary_category(title, description=""):
    text=f"{title or ''} {description or ''}".lower()
    for category,words in ORDINARY_PRODUCT_CATEGORIES.items():
        if any(re.search(r"(?<!\w)"+re.escape(w)+r"(?!\w)",text) for w in words): return category
    return "nyingine"

def _seed_ordinary_demo_products():
    """Weka picha za mfano za duka mara ya kwanza tu; admin anaweza kuongeza/kufuta baadaye."""
    conn=_ordinary_products_db()
    count=conn.execute("SELECT COUNT(*) FROM ordinary_products").fetchone()[0]
    if count:
        conn.close(); return
    demo=[
        ("Mfuko wa Kike wa Kahawia", "Mfuko wa mtindo wa kila siku", "mifuko", "sample-products/example-1.jpg", 45000),
        ("Mfuko wa Kike wa Bluu", "Seti ya mifuko ya mtindo", "mifuko", "sample-products/example-2.jpg", 50000),
        ("Gauni la Kike la Kahawia", "Gauni la mtindo wa kisasa", "magauni", "sample-products/example-3.jpg", 55000),
        ("Mifuko ya Kike ya Pink", "Seti ya mifuko ya kawaida", "mifuko", "sample-products/example-4.jpg", 48000),
        ("Sandals za Rangi", "Sandals za wanawake", "viatu", "sample-products/example-5.jpg", 35000),
    ]
    now=datetime.utcnow().isoformat()+"Z"
    for title,desc,cat,img,price in demo:
        conn.execute("INSERT INTO ordinary_products(title,description,category,price_tzs,image_url,stock,active,featured,created_at) VALUES(?,?,?,?,?,?,1,0,?)",(title,desc,cat,"/static/uploads/"+img,price,10,now))
    conn.commit(); conn.close()

def _ordinary_products_list(q="", category=""):
    _seed_ordinary_demo_products()
    conn=_ordinary_products_db(); sql="SELECT * FROM ordinary_products WHERE active=1"; params=[]
    cat=(category or "").strip().lower()
    if cat in set(ORDINARY_PRODUCT_CATEGORIES)|{"nyingine"}: sql+=" AND category=?"; params.append(cat)
    rows=[dict(r) for r in conn.execute(sql+" ORDER BY featured DESC,id DESC",params).fetchall()]; conn.close()
    query=(q or "").strip().lower()
    if query:
        tokens=[t for t in re.split(r"\s+",query) if t]
        def hay(p): return " ".join([str(p.get("title","")),str(p.get("description","")),str(p.get("category",""))]).lower()
        rows=[p for p in rows if all(t in hay(p) for t in tokens)]
        rows.sort(key=lambda p: sum(3 if t in str(p.get("title","")).lower() else 1 for t in tokens if t in hay(p)), reverse=True)
    return rows

@app.route("/api/ordinary-products", methods=["GET"])
def api_ordinary_products():
    return jsonify({"success":True,"products":_ordinary_products_list(request.args.get("q") or "",request.args.get("category") or ""),"categories":[{"id":k,"label":k.capitalize()} for k in list(ORDINARY_PRODUCT_CATEGORIES)+["nyingine"]]})

@app.route("/api/admin/ordinary-products", methods=["GET","POST"])
def api_admin_ordinary_products():
    if not session.get("is_admin"): return jsonify({"success":False,"message":"Si admin."}),403
    if request.method=="GET":
        conn=_ordinary_products_db(); rows=[dict(r) for r in conn.execute("SELECT * FROM ordinary_products WHERE active=1 ORDER BY featured DESC,id DESC").fetchall()]; conn.close()
        return jsonify({"success":True,"products":rows})
    d=request.form if request.form else (request.get_json(silent=True) or {}); title=(d.get("title") or "").strip(); desc=(d.get("description") or "").strip()
    if not title: return jsonify({"success":False,"message":"Weka jina la bidhaa."}),400
    requested=(d.get("category") or "").strip().lower(); category=requested if requested in set(ORDINARY_PRODUCT_CATEGORIES)|{"nyingine"} else _infer_ordinary_category(title,desc)
    try: price=int(float(d.get("price_tzs") or 0)); stock=int(float(d.get("stock") or 0))
    except: return jsonify({"success":False,"message":"Bei au stock si sahihi."}),400
    image_url=(d.get("image_url") or "").strip(); f=request.files.get("image") if request.files else None
    if f and f.filename:
        ext=Path(f.filename).suffix.lower()
        if ext not in ORDINARY_PRODUCT_ALLOWED_EXT: return jsonify({"success":False,"message":"Picha lazima iwe JPG, PNG, WEBP au GIF."}),400
        dest=UPLOAD_DIR/"ordinary"; dest.mkdir(parents=True,exist_ok=True); fname=f"ordinary_{secrets.token_hex(8)}{ext}"; f.save(str(dest/fname)); image_url=f"/static/uploads/ordinary/{fname}"
    conn=_ordinary_products_db(); cur=conn.execute("INSERT INTO ordinary_products(title,description,category,price_tzs,image_url,stock,active,featured,created_at) VALUES(?,?,?,?,?,?,1,0,?)",(title,desc,category,price,image_url,stock,datetime.utcnow().isoformat()+"Z")); conn.commit(); pid=cur.lastrowid; conn.close()
    return jsonify({"success":True,"message":f"Bidhaa imeongezwa kwenye kundi la {category}.","product_id":pid,"category":category})

@app.route("/api/admin/ordinary-products/<int:pid>", methods=["DELETE"])
def api_admin_ordinary_product_delete(pid):
    if not session.get("is_admin"): return jsonify({"success":False,"message":"Si admin."}),403
    conn=_ordinary_products_db(); row=conn.execute("SELECT id FROM ordinary_products WHERE id=? AND active=1",(pid,)).fetchone()
    if not row: conn.close(); return jsonify({"success":False,"message":"Bidhaa haipatikani."}),404
    conn.execute("UPDATE ordinary_products SET active=0 WHERE id=?",(pid,)); conn.commit(); conn.close(); return jsonify({"success":True,"message":"Bidhaa imeondolewa."})

@app.route("/api/products", methods=["GET"])
def api_products():
    return jsonify({
        "success": True,
        "products": _products_for_client(),
        "admin_mode": bool(session.get("is_admin")),
        "unlocked": _is_unlocked(),
    })


@app.route("/api/ai-products", methods=["GET"])
def api_ai_products():
    q = (request.args.get("q") or "").lower()
    products = _products_for_client()
    if q:
        products = [p for p in products
                    if q in (p.get("title") or "").lower()
                    or q in (p.get("description") or "").lower()
                    or q in (p.get("location") or "").lower()]
    return jsonify({"success": True, "products": products, "unlocked": _is_unlocked()})


@app.route("/api/products/<int:pid>/like", methods=["POST"])
def api_like(pid):
    with PRODUCTS_LOCK:
        for p in SAMPLE_PRODUCTS:
            if p["id"] == pid:
                p["likes"] = p.get("likes", 0) + 1
                return jsonify({"success": True, "likes": p["likes"], "liked": True})
    return jsonify({"success": False}), 404


@app.route("/api/comments/<int:pid>", methods=["GET", "POST"])
def api_comments(pid):
    if request.method == "GET":
        return jsonify({"success": True, "comments": []})
    return jsonify({"success": True, "message": "Maoni yamepokewa."})


@app.route("/api/market-stats", methods=["GET"])
def api_market_stats():
    unlocked = _is_unlocked()
    with PRODUCTS_LOCK:
        snapshot = list(SAMPLE_PRODUCTS)
        total_products = len(snapshot)
        total_likes = sum(p.get("likes", 0) for p in snapshot)
        recent = [{"title": p["title"]} for p in snapshot[-12:]]
        locs = {}
        cats = {}
        for p in snapshot:
            loc = p.get("location") or "—"
            locs[loc] = locs.get(loc, 0) + 1
            title = p.get("title") or "Nyingine"
            cats.setdefault(title, []).append(p.get("real_price") or 0)
        total_locations = len([k for k in locs if k != "—"])
    categories = []
    for label, prices in list(cats.items())[:12]:
        prices = [x for x in prices if x]
        count = len(prices) or 1
        share = max(1, round(100 * count / max(1, total_products)))
        categories.append({
            "label": label,
            "count": count,
            "share": min(100, share),
            "avg_price": (round(sum(prices) / len(prices)) if prices and unlocked else None),
            "min_price": (min(prices) if prices and unlocked else None),
            "max_price": (max(prices) if prices and unlocked else None),
        })
    top_locations = [{"name": k, "count": v} for k, v in sorted(locs.items(), key=lambda x: -x[1])[:8]]
    return jsonify({
        "success": True,
        "unlocked": unlocked,
        "summary": {
            "total_products": total_products,
            "total_categories": len(categories),
            "total_locations": total_locations,
            "total_likes": total_likes,
        },
        "categories": categories,
        "recent": recent,
        "top_locations": top_locations if unlocked else [],
        "live": True,
        "remaining_seconds": _remaining_access_seconds(),
    })



ACTIVITY_LOG = [
    {"id": 1, "message": "Wahudumu wanatafuta ufuta Ruvuma...",
     "created": datetime.utcnow().isoformat() + "Z"},
    {"id": 2, "message": "Mahindi Mbeya yameongezwa sokoni.",
     "created": datetime.utcnow().isoformat() + "Z"},
]
_activity_lock = threading.Lock()
_activity_next_id = 3

_ACTIVITY_TEMPLATES = [
    "Wahudumu wanatafuta {p} eneo la {loc}...",
    "{p} kutoka {loc} yameongezwa sokoni.",
    "Bei ya {p} {loc} imethibitishwa na wahudumu.",
    "Muuzaji mpya wa {p} amejiunga kutoka {loc}.",
    "Wahudumu wanachambua soko la {p} — {loc}.",
]
_ACTIVITY_PRODUCTS = ["ufuta", "mahindi", "kahawa", "mpunga", "korosho", "alizeti"]
_ACTIVITY_LOCATIONS = ["Ruvuma", "Mbeya", "Arusha", "Dodoma", "Morogoro", "Iringa", "Tanga"]


def _generate_activity_item():
    global _activity_next_id
    import random
    template = random.choice(_ACTIVITY_TEMPLATES)
    msg = template.format(
        p=random.choice(_ACTIVITY_PRODUCTS),
        loc=random.choice(_ACTIVITY_LOCATIONS),
    )
    with _activity_lock:
        item = {
            "id": _activity_next_id,
            "message": msg,
            "created": datetime.utcnow().isoformat() + "Z",
        }
        _activity_next_id += 1
        ACTIVITY_LOG.append(item)
        if len(ACTIVITY_LOG) > 100:
            del ACTIVITY_LOG[: len(ACTIVITY_LOG) - 100]


def _activity_worker():
    import random
    while True:
        # Live feed 24/7 — update kila sekunde 1–3
        time.sleep(random.uniform(1.0, 3.0))
        try:
            _generate_activity_item()
        except Exception:
            pass


threading.Thread(target=_activity_worker, daemon=True).start()


@app.route("/api/activity", methods=["GET"])
def api_activity():
    since_id = request.args.get("since_id", 0, type=int)
    with _activity_lock:
        items = [a for a in ACTIVITY_LOG if a["id"] > since_id]
    return jsonify({
        "success": True,
        "activity": items,
    })


@app.route("/api/research", methods=["POST"])
def api_research():
    guard = _sabbath_guard()
    if guard: return guard
    unlocked = _is_unlocked()
    return jsonify({
        "success": True,
        "unlocked": unlocked,
        "summary": {"total_listings": 3, "locations_covered": 3,
                    "avg_price": 10855 if unlocked else None},
        "comparison": [
            {"location": "Mbeya", "listings": 1,
             "min_price": 16066 if unlocked else None,
             "max_price": 16066 if unlocked else None},
            {"location": "Ruvuma", "listings": 1,
             "min_price": 4500 if unlocked else None,
             "max_price": 4500 if unlocked else None},
        ],
        "sources": [{"product": "Mahindi", "location": "Mbeya",
                     "chanzo": "Safari Exports", "updated": "leo"}],
    })


@app.route("/api/automate/alerts", methods=["GET", "POST"])
@app.route("/api/automate/alerts/<int:aid>", methods=["DELETE"])
def api_alerts(aid=None):
    if request.method == "GET":
        return jsonify({"success": True, "alerts": []})
    if request.method == "POST":
        return jsonify({"success": True, "message": "Alert imewekwa."})
    return jsonify({"success": True})


ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
_BOT_HISTORY = {}  # session/ip -> list of {role, content} (fupi, kwa muktadha)
_BOT_HISTORY_LOCK = threading.Lock()


def _call_claude_bot(user_message, history):
    """Piga Anthropic API moja kwa moja (bila SDK) ili bot ijibu kwa lugha
    yoyote mteja anayoandika, kwa akili kama ChatGPT/Grok/Claude halisi."""
    if not ANTHROPIC_API_KEY:
        return None
    system_prompt = (
        "Wewe ni msaidizi wa AI wa NjiaMauzo Afrika, soko la mazao la Afrika "
        "Mashariki (Tanzania, Kenya, Uganda, Rwanda, n.k). Jibu KILA WAKATI kwa "
        "lugha ile ile mteja anayotumia (Kiswahili, Kiingereza, au lugha nyingine "
        "yoyote) — tambua lugha kiotomatiki na uendane nayo. Kuwa mfupi, wa "
        "kirafiki na wa haraka kuelewa. Bei kamili, eneo na mawasiliano ya "
        "muuzaji vinapatikana tu baada ya mteja kulipa ada ndogo ya huduma. "
        "Msaidie mteja kutafuta mazao, kulinganisha bei za soko, na kumuunganisha "
        "na muuzaji. Nambari ya WhatsApp ya huduma: 0755 248 789."
    )
    body = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 500,
        "system": system_prompt,
        "messages": history + [{"role": "user", "content": user_message}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        parts = payload.get("content") or []
        text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        return text.strip() or None
    except Exception:
        return None


@app.route("/api/bot-chat", methods=["POST"])
def api_bot_chat():
    guard = _sabbath_guard()
    if guard: return guard
    data = request.get_json(silent=True) or {}
    raw = (data.get("message") or "").strip()
    msg = raw.lower()
    thinking = []

    def think(step):
        thinking.append(step)
        _ai_think(f"Bot: {step}")

    think("Kupokea ujumbe wa mteja…")
    think(f"Kuchambua maana: «{raw[:60]}»")

    # Auto-search if looks like product query
    product_hints = ("mahindi", "kahawa", "ufuta", "mpunga", "maharage", "bei", "tafuta",
                     "ndizi", "viazi", "alizeti", "korosho", "chai", "soko", "price", "search",
                     "maize", "coffee", "rice", "beans")
    if any(h in msg for h in product_hints):
        think("Inaonekana ni utafutaji wa bidhaa — ninaanzisha AI Searcher…")
        try:
            _ai_search_and_ingest(raw[:40] or None)
            think("Matokeo yameongezwa kwenye soko / dashboard.")
        except Exception:
            think("Utafutaji wa ziada umeshindikana — nitaendelea na majibu ya msingi.")

    paid = _is_unlocked()
    with PRODUCTS_LOCK:
        n = len(SAMPLE_PRODUCTS)
        snapshot = list(SAMPLE_PRODUCTS)
        recent = [p["title"] for p in snapshot[-5:]]
    deep_results=[]
    if paid:
        tokens=[t for t in re.findall(r"[\wÀ-ÿ]+",msg) if len(t)>=2]
        ranked=[]
        for p in snapshot:
            hay=" ".join([str(p.get("title","")),str(p.get("description","")),str(p.get("location","")),str(p.get("seller_name",""))]).lower()
            ranked.append((sum(1 for t in tokens if t in hay),p))
        ranked.sort(key=lambda x:(x[0],bool(x[1].get("featured"))),reverse=True)
        full=_products_for_client(); by_id={p.get("id"):p for p in full}
        deep_results=[by_id.get(p.get("id"),p) for score,p in ranked[:20] if score>0] or full[:20]
        think(f"Deep Search ya mteja aliyelipa: {len(deep_results)} bidhaa.")

    # Jaribu bot yenye akili halisi (multi-lugha) kwanza; ikishindikana
    # (hakuna ANTHROPIC_API_KEY au tatizo la mtandao), rudi kwenye majibu
    # ya msingi ya sheria (Kiswahili) kama fallback salama.
    sess_key = session.get("uid") or _client_ip()
    with _BOT_HISTORY_LOCK:
        hist = _BOT_HISTORY.get(sess_key, [])
    smart_reply = _call_claude_bot(raw, hist) if raw else None

    if smart_reply:
        reply = smart_reply
        with _BOT_HISTORY_LOCK:
            hist = hist + [{"role": "user", "content": raw}, {"role": "assistant", "content": smart_reply}]
            _BOT_HISTORY[sess_key] = hist[-10:]  # weka muktadha mfupi tu
        think("Jibu limetayarishwa na AI (lugha yoyote).")
    elif "bei" in msg or "price" in msg:
        reply = ("Nimefikiria kuhusu bei. Bei kamili + eneo + muuzaji unapata baada ya "
                 "kulipa ada ya huduma. Bofya «KARIBU NJIAMAUZO AFRIKA». "
                 f"Kuna bidhaa {n} kwenye soko sasa.")
    elif "whatsapp" in msg or "mawasiliano" in msg:
        reply = "Wasiliana nasi WhatsApp: 0755 248 789 — tuko 24/7."
    elif any(h in msg for h in product_hints):
        reply = (f"Nimefikiria na kutafuta… Matokeo yanayohusiana yanaonekana kwenye soko. "
                 f"Bidhaa za hivi karibuni: {', '.join(recent) or '—'}. "
                 "Lipa ada ili kuona bei, eneo na muuzaji.")
    else:
        reply = ("Habari! Mimi ni AI msaidizi wa NjiaMauzo Afrika. "
                 "Naweza kutafuta mazao kiotomatiki, kulinganisha masoko, "
                 "au kukuunganisha na muuzaji baada ya malipo.")

    think("Kutayarisha jibu la mwisho…")
    return jsonify({
        "success": True, "reply": reply, "thinking": thinking, "products_live": n,
        "ai_powered": bool(smart_reply), "paid_customer": paid,
        "search_count": len(deep_results), "products": deep_results if paid else [],
    })


@app.route("/api/admin/ai-search", methods=["GET"])
def api_admin_ai_search():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    with AI_SEARCH_LOCK:
        thinking = list(AI_THINKING_LOG)
        found = list(AI_FOUND_PRODUCTS)
        current = AI_CURRENT_THOUGHT
    with PRODUCTS_LOCK:
        count = len(SAMPLE_PRODUCTS)
    return jsonify({
        "success": True,
        "thinking": thinking,
        "found_products": found,
        "current_thought": current,
        "product_count": count,
    })


@app.route("/api/admin/ai-search/run", methods=["POST"])
def api_admin_ai_search_run():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    data = request.get_json(silent=True) or {}
    q = (data.get("query") or "").strip() or None
    _ai_search_and_ingest(q)
    with AI_SEARCH_LOCK:
        current = AI_CURRENT_THOUGHT
    return jsonify({"success": True, "message": "AI search imefanyika.", "current_thought": current})


PAYPAL_EMAIL = "gsdtech20@gmail.com"
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "").strip()
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "").strip()
PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "live").strip().lower()  # "live" au "sandbox"
PAYPAL_API_BASE = "https://api-m.paypal.com" if PAYPAL_MODE == "live" else "https://api-m.sandbox.paypal.com"
# PayPal HAIKUBALI TZS moja kwa moja - tunatumia USD. Weka thamani halisi ya soko
# (TZS ngapi = USD 1) kupitia env var; default ni makadirio tu.
PAYPAL_TZS_PER_USD = float(os.environ.get("PAYPAL_TZS_PER_USD", "2600"))


def _paypal_enabled():
    return bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET)


def _tzs_to_usd(amount_tzs):
    usd = round(float(amount_tzs) / PAYPAL_TZS_PER_USD, 2)
    return max(usd, 0.5)  # PayPal haikubali chini ya ~$0.01-0.5 kwa baadhi ya akaunti


def _paypal_http(path, payload=None, method="POST", auth_basic=None, bearer=None):
    url = PAYPAL_API_BASE + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    if auth_basic:
        b64 = base64.b64encode(f"{auth_basic[0]}:{auth_basic[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {b64}")
    if bearer:
        req.add_header("Authorization", f"Bearer {bearer}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}
    except Exception as e:
        return 0, {"error": str(e)}


def _paypal_get_access_token():
    if not _paypal_enabled():
        return None
    req = urllib.request.Request(
        PAYPAL_API_BASE + "/v1/oauth2/token",
        data=b"grant_type=client_credentials", method="POST",
    )
    b64 = base64.b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}".encode()).decode()
    req.add_header("Authorization", f"Basic {b64}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("access_token")
    except Exception:
        return None


# ===== STRIPE (kadi Visa/Mastercard + Google Pay/Apple Pay kiotomatiki) =====
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "").strip()
STRIPE_API_BASE = "https://api.stripe.com/v1"


def _stripe_enabled():
    return bool(STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY)


def _stripe_request(path, form_fields, method="POST"):
    """Stripe API inatumia x-www-form-urlencoded (siyo JSON) + Basic Auth
    (secret key kama username, password tupu)."""
    body = urllib.parse.urlencode(form_fields, doseq=True).encode("utf-8")
    req = urllib.request.Request(STRIPE_API_BASE + path, data=body, method=method)
    b64 = base64.b64encode(f"{STRIPE_SECRET_KEY}:".encode()).decode()
    req.add_header("Authorization", f"Basic {b64}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {"error": {"message": "Stripe error"}}
    except Exception as e:
        return 0, {"error": {"message": str(e)}}


@app.route("/api/payment/stripe/status", methods=["GET"])
def api_stripe_status():
    return jsonify({"success": True, "enabled": _stripe_enabled(),
                     "publishable_key": STRIPE_PUBLISHABLE_KEY if _stripe_enabled() else ""})


@app.route("/api/payment/stripe/create-checkout-session", methods=["POST"])
def api_stripe_create_checkout():
    """Tengeneza Stripe Checkout Session kwa order_id ya ndani (service fee,
    advisory, au stars). Stripe Checkout inaonyesha kadi + Google Pay/Apple
    Pay kiotomatiki - hakuna extra config inayohitajika kwa Google Pay."""
    if not _stripe_enabled():
        return jsonify({"success": False, "message": "Stripe haijawekwa bado (weka funguo kwenye Render)."}), 503
    data = request.get_json(silent=True) or {}
    order_id = (data.get("order_id") or "").strip()
    amount_local = None
    kind = None
    with PAYMENT_LOCK:
        order = PAYMENT_ORDERS.get(order_id)
        if order:
            amount_local = order.get("amount")
            kind = "payment"
    if amount_local is None:
        with ADVISORY_LOCK:
            adv = ADVISORY_ORDERS.get(order_id)
            if adv:
                amount_local = adv.get("price_tzs") or adv.get("amount")
                kind = "advisory"
    if amount_local is None:
        return jsonify({"success": False, "message": "Order haipatikani."}), 404

    usd = _tzs_to_usd(amount_local)
    cents = int(round(usd * 100))
    origin = request.headers.get("Origin") or (request.scheme + "://" + request.host)
    success_url = f"{origin}/?stripe_order={order_id}&stripe_session={{CHECKOUT_SESSION_ID}}&stripe_ok=1"
    cancel_url = f"{origin}/?stripe_order={order_id}&stripe_ok=0"

    status, resp = _stripe_request("/checkout/sessions", {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][product_data][name]": "NjiaMauzo Afrika - malipo",
        "line_items[0][price_data][unit_amount]": str(cents),
        "line_items[0][quantity]": "1",
        "payment_method_types[0]": "card",
        "client_reference_id": order_id,
    })
    if status not in (200, 201):
        return jsonify({"success": False, "message": "Stripe imekataa ombi.", "detail": resp}), 502
    return jsonify({"success": True, "checkout_url": resp.get("url"), "session_id": resp.get("id"), "amount_usd": usd})


@app.route("/api/payment/stripe/verify-session", methods=["POST"])
def api_stripe_verify_session():
    """Baada ya Stripe kumrudisha mtumiaji kwenye success_url, tuthibitishe
    MOJA KWA MOJA na Stripe (server-to-server) kwamba kweli amelipa - hakuna
    kusubiri admin."""
    if not _stripe_enabled():
        return jsonify({"success": False, "message": "Stripe haijawekwa bado."}), 503
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    order_id = (data.get("order_id") or "").strip()
    if not session_id or not order_id:
        return jsonify({"success": False, "message": "Taarifa hazitoshi."}), 400

    status, resp = _stripe_request(f"/checkout/sessions/{session_id}", {}, method="GET")
    if status != 200 or resp.get("payment_status") != "paid":
        return jsonify({"success": False, "message": "Stripe haijathibitisha malipo.", "detail": resp}), 402
    if resp.get("client_reference_id") != order_id:
        return jsonify({"success": False, "message": "Order haiendani na session."}), 400

    with PAYMENT_LOCK:
        order = PAYMENT_ORDERS.get(order_id)
        if order:
            order["status"] = "verified"
            order["verified_at"] = datetime.utcnow()
            order["activated_via"] = "stripe-auto"
            _wallet_credit_from_verified_order(order)
    with ADVISORY_LOCK:
        adv = ADVISORY_ORDERS.get(order_id)
        if adv:
            adv["status"] = "verified"
            adv["verified_at"] = datetime.utcnow()
            adv["activated_via"] = "stripe-auto"

    return jsonify({"success": True, "message": "✅ Malipo ya Stripe yamethibitishwa moja kwa moja!", "order_id": order_id})


@app.route("/api/payment/paypal/status", methods=["GET"])
def api_paypal_status():
    return jsonify({"success": True, "enabled": _paypal_enabled(), "mode": PAYPAL_MODE,
                     "client_id": PAYPAL_CLIENT_ID if _paypal_enabled() else ""})


@app.route("/api/payment/paypal/create-order", methods=["POST"])
def api_paypal_create_order():
    """Anzisha PayPal Order kwa order_id ya ndani (service fee, advisory, au stars)."""
    if not _paypal_enabled():
        return jsonify({"success": False, "message": "PayPal haijawekwa bado (Client ID/Secret hazipo)."}), 503
    data = request.get_json(silent=True) or {}
    order_id = (data.get("order_id") or "").strip()
    amount_tzs = None
    with PAYMENT_LOCK:
        order = PAYMENT_ORDERS.get(order_id)
        if order:
            amount_tzs = order.get("amount")
    if amount_tzs is None:
        with ADVISORY_LOCK:
            adv = ADVISORY_ORDERS.get(order_id)
            if adv:
                amount_tzs = adv.get("price_tzs") or adv.get("amount")
    if amount_tzs is None:
        return jsonify({"success": False, "message": "Order haipatikani."}), 404
    usd = _tzs_to_usd(amount_tzs)
    token = _paypal_get_access_token()
    if not token:
        return jsonify({"success": False, "message": "Imeshindikana kuwasiliana na PayPal. Jaribu tena."}), 502
    status, resp = _paypal_http(
        "/v2/checkout/orders",
        payload={
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": order_id,
                "amount": {"currency_code": "USD", "value": f"{usd:.2f}"},
                "description": "NjiaMauzo Afrika - malipo",
            }],
        },
        bearer=token,
    )
    if status not in (200, 201):
        return jsonify({"success": False, "message": "PayPal imekataa order.", "detail": resp}), 502
    return jsonify({"success": True, "paypal_order_id": resp.get("id"), "amount_usd": usd})


@app.route("/api/payment/paypal/capture-order", methods=["POST"])
def api_paypal_capture_order():
    """Baada ya mtumiaji kukubali kwenye PayPal b
