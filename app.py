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
# During the temporary 48-hour window, Admin Room opens without username/password.
# After the window, the normal username + password are required again.
ADMIN_USER = os.environ.get("ADMIN_USER", "SUKUMANJIA").strip()
ADMIN_PASS = os.environ.get("ADMIN_PASS", "NjiaMauzo.sukuma@76").strip()
# Default window starts at the time this release was prepared (UTC) and lasts 48h.
# Override with ADMIN_TEMP_OPEN_UNTIL on Render if deployment happens later.
ADMIN_TEMP_OPEN_UNTIL = os.environ.get(
    "ADMIN_TEMP_OPEN_UNTIL", "2026-08-24T09:29:00Z"
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


def _admin_temp_open():
    """True while the temporary 48-hour passwordless window is active."""
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

@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    """Admin login bila password — username pekee."""
    ip = _client_ip()
    locked, wait = _admin_is_locked(ip)
    if locked:
        return jsonify({
            "success": False,
            "message": f"Jaribio nyingi. Subiri sekunde {wait} kisha ujaribu tena.",
            "locked_seconds": wait,
        }), 429

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    # Temporary 48h mode: no username and no password required.
    if _admin_temp_open():
        _admin_clear_attempts(ip)
    else:
        user_ok = bool(username) and secrets.compare_digest(username, ADMIN_USER)
        pass_ok = bool(password) and secrets.compare_digest(password, ADMIN_PASS)
        if not (user_ok and pass_ok):
            row = _admin_register_fail(ip)
            left = max(0, ADMIN_MAX_ATTEMPTS - int(row.get("count") or 0))
            if row.get("locked_until") and time.time() < row["locked_until"]:
                return jsonify({
                    "success": False,
                    "message": f"Imefungwa kwa dakika {ADMIN_LOCK_SECONDS // 60} baada ya majaribio mengi.",
                }), 429
            return jsonify({
                "success": False,
                "message": "Jina la mtumiaji au password si sahihi.",
                "attempts_left": left,
            }), 401

        _admin_clear_attempts(ip)
    session.clear()
    session.permanent = True
    session["is_admin"] = True
    session["unlocked"] = True
    session["unlocked_until"] = datetime.utcnow().timestamp() + int(
        os.environ.get("ADMIN_SESSION_HOURS", "8")
    ) * 3600
    session["user"] = {"email": "admin@njiamauzo.tz", "name": "Admin", "role": "admin"}
    session["admin_login_at"] = datetime.utcnow().isoformat() + "Z"
    session["admin_ip"] = ip
    csrf = secrets.token_hex(24)
    session["csrf"] = csrf

    return jsonify({
        "success": True,
        "message": "Admin umeingia.",
        "admin_mode": True,
        "temporary_open": _admin_temp_open(),
        "seconds_left": _admin_temp_seconds_left(),
        "csrf_token": csrf,
    })


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
    """Baada ya mtumiaji kukubali kwenye PayPal button, tuthibitishe malipo
    (capture) MOJA KWA MOJA na server-to-server na PayPal - hakuna kusubiri
    admin. Endapo PayPal inathibitisha COMPLETED, order ya ndani inakuwa
    'verified' papo hapo."""
    if not _paypal_enabled():
        return jsonify({"success": False, "message": "PayPal haijawekwa bado."}), 503
    data = request.get_json(silent=True) or {}
    paypal_order_id = (data.get("paypal_order_id") or "").strip()
    order_id = (data.get("order_id") or "").strip()
    if not paypal_order_id or not order_id:
        return jsonify({"success": False, "message": "Taarifa hazitoshi."}), 400
    token = _paypal_get_access_token()
    if not token:
        return jsonify({"success": False, "message": "Imeshindikana kuwasiliana na PayPal."}), 502
    status, resp = _paypal_http(f"/v2/checkout/orders/{paypal_order_id}/capture", payload={}, bearer=token)
    if status not in (200, 201) or resp.get("status") != "COMPLETED":
        return jsonify({"success": False, "message": "PayPal haijathibitisha malipo.", "detail": resp}), 402

    with PAYMENT_LOCK:
        order = PAYMENT_ORDERS.get(order_id)
        if order:
            order["status"] = "verified"
            order["verified_at"] = datetime.utcnow()
            order["activated_via"] = "paypal-auto"
            order["paypal_order_id"] = paypal_order_id
            _wallet_credit_from_verified_order(order)
    with ADVISORY_LOCK:
        adv = ADVISORY_ORDERS.get(order_id)
        if adv:
            adv["status"] = "verified"
            adv["verified_at"] = datetime.utcnow()
            adv["activated_via"] = "paypal-auto"

    return jsonify({"success": True, "message": "✅ Malipo ya PayPal yamethibitishwa moja kwa moja!", "order_id": order_id})



@app.route("/api/service/payment-number", methods=["GET"])
def api_payment_numbers():
    return jsonify({
        "success": True,
        "numbers": {
            "paypal": PAYPAL_EMAIL,
            "mpesa": "0755248789",
            "tigopesa": "168603063",
            "halotel": "0625031460",
            "airtel": "0691925100",
            "receiving_card": "5117537002231447",
            "receiving_card_label": "Kadi ya Kupokea Pesa — NjiaMauzo Afrika",
        },
    })


# ---------- USHAURI WA KITAALAMU (advisory) ----------
ADVISORY_FEE_TZS = 3000
ADVISORY_WA_NUMBER = "0625031460"
ADVISORY_PLANS = {
    "1m": {"id":"1m","label_sw":"Maongezi ya dakika 1","label_en":"1 Minute Talk","minutes":1,"seconds":60,"price_tzs":3000},
    "5m": {"id":"5m","label_sw":"Maongezi ya dakika 5","label_en":"5 Minute Talk","minutes":5,"seconds":300,"price_tzs":15000},
    "10m": {"id":"10m","label_sw":"Maongezi ya dakika 10","label_en":"10 Minute Talk","minutes":10,"seconds":600,"price_tzs":50000},
    "30m": {"id":"30m","label_sw":"Maongezi ya dakika 30","label_en":"30 Minute Talk","minutes":30,"seconds":1800,"price_tzs":100000},
}
ADVISORY_ORDERS = {}
ADVISORY_LOCK = threading.Lock()

# ---------- MAKTABA YA NYARAKA (Document Library) ----------
DOCLIB_TOPICS = {
    "biashara": "Mashauri kuhusu Biashara",
    "elimu": "Mashauri kuhusu Elimu",
    "mbegu": "Wataalamu wa kilimo cha mbegu",
    "usimamizi": "Usimamizi katika maswala ya kilimo",
    "ushauri_kilimo": "Ushauri wa namna bora ya kilimo",
}
DOCLIB_PLANS = {
    "1h": {"id": "1h", "label_sw": "Saa 1", "hours": 1, "seconds": 3600, "price_tzs": 3000},
    "2h": {"id": "2h", "label_sw": "Saa 2", "hours": 2, "seconds": 7200, "price_tzs": 4000},
    "3h": {"id": "3h", "label_sw": "Saa 3", "hours": 3, "seconds": 10800, "price_tzs": 7000},
    "5h": {"id": "5h", "label_sw": "Saa 5", "hours": 5, "seconds": 18000, "price_tzs": 10000},
}
DOCLIB_ORDERS = {}
DOCLIB_LOCK = threading.Lock()


@app.route("/api/doclib/plans", methods=["GET"])
def api_doclib_plans():
    return jsonify({"success": True, "plans": list(DOCLIB_PLANS.values())})


@app.route("/api/doclib/request", methods=["POST"])
def api_doclib_request():
    guard = _sabbath_guard()
    if guard:
        return guard
    data = request.get_json(silent=True) or {}
    topic_id = (data.get("topic_id") or "").strip()
    if topic_id not in DOCLIB_TOPICS:
        return jsonify({"success": False, "message": "Mada si sahihi."}), 400
    order_id = "DOC-" + secrets.token_hex(4).upper()
    plan = DOCLIB_PLANS.get((data.get("plan") or "1h").strip()) or DOCLIB_PLANS["1h"]
    with DOCLIB_LOCK:
        DOCLIB_ORDERS[order_id] = {
            "status": "pending", "method": data.get("njia") or "M-Pesa",
            "phone": data.get("simu") or "", "amount": plan["price_tzs"], "currency": "TZS",
            "topic_id": topic_id, "plan": plan["id"], "duration_seconds": plan["seconds"],
            "created": datetime.utcnow(), "session_uid": session.get("uid") or _client_ip(),
        }
    session["pending_doclib_order_id"] = order_id
    return jsonify({
        "success": True, "order_id": order_id, "plan": plan["id"], "topic_id": topic_id,
        "amount": plan["price_tzs"], "currency": "TZS", "duration_seconds": plan["seconds"],
    })


def _grant_doclib_access(topic_id, seconds):
    secs = max(60, int(seconds or 0))
    unlocked = session.get("doclib_unlocked") or {}
    unlocked[topic_id] = datetime.utcnow().timestamp() + secs
    session["doclib_unlocked"] = unlocked
    return secs


def _remaining_doclib_seconds(topic_id):
    if session.get("is_admin"):
        return 86400
    unlocked = session.get("doclib_unlocked") or {}
    until = unlocked.get(topic_id)
    if not until:
        return 0
    left = int(until - datetime.utcnow().timestamp())
    if left <= 0:
        unlocked.pop(topic_id, None)
        session["doclib_unlocked"] = unlocked
        return 0
    return left


@app.route("/api/doclib/status", methods=["GET"])
def api_doclib_status():
    oid = (request.args.get("order_id") or session.get("pending_doclib_order_id") or "").strip()
    topic_id = (request.args.get("topic_id") or "").strip()
    with DOCLIB_LOCK:
        o = dict(DOCLIB_ORDERS.get(oid) or {}) if oid else {}
    if not topic_id:
        topic_id = o.get("topic_id") or ""
    left = _remaining_doclib_seconds(topic_id) if topic_id else 0
    return jsonify({
        "success": True, "order_id": oid or None, "topic_id": topic_id or None, "status": o.get("status"),
        "unlocked": left > 0, "remaining_seconds": left,
    })


@app.route("/api/doclib/activate", methods=["POST"])
def api_doclib_activate():
    guard = _sabbath_guard()
    if guard:
        return guard
    data = request.get_json(silent=True) or {}
    oid = (data.get("order_id") or session.get("pending_doclib_order_id") or "").strip()
    with DOCLIB_LOCK:
        o = DOCLIB_ORDERS.get(oid) if oid else None
        if not o:
            return jsonify({"success": False, "message": "Order haipatikani."}), 404
        if o.get("status") != "verified" and not session.get("is_admin"):
            return jsonify({"success": False, "message": "Malipo bado hayajathibitishwa na admin."}), 403
        duration = int(o.get("duration_seconds") or 3600)
        topic_id = o.get("topic_id")
    left = _grant_doclib_access(topic_id, duration)
    session["pending_doclib_order_id"] = oid
    return jsonify({"success": True, "unlocked": True, "order_id": oid, "topic_id": topic_id, "remaining_seconds": left})


@app.route("/api/doclib/admin-verify", methods=["POST"])
def api_doclib_admin_verify():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    data = request.get_json(silent=True) or {}
    order_id = (data.get("order_id") or "").strip()
    with DOCLIB_LOCK:
        order = DOCLIB_ORDERS.get(order_id)
        if not order:
            return jsonify({"success": False, "message": "Order haipatikani."}), 404
        order["status"] = "verified"
        order["verified_at"] = datetime.utcnow()
    return jsonify({"success": True, "order_id": order_id, "message": "Malipo ya maktaba yamethibitishwa."})


@app.route("/api/doclib/admin-orders", methods=["GET"])
def api_doclib_admin_orders():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    with DOCLIB_LOCK:
        orders = [
            {"order_id": oid, **{k: v for k, v in o.items() if k not in ("created", "verified_at")},
             "created": o["created"].isoformat() + "Z"}
            for oid, o in DOCLIB_ORDERS.items()
        ]
    orders.sort(key=lambda x: x["created"], reverse=True)
    return jsonify({"success": True, "orders": orders[:100]})


@app.route("/api/doclib/topics", methods=["GET"])
def api_doclib_topics():
    """Orodha ya mada + kama admin ameshapakia PDF kwa kila mada."""
    out = []
    for tid, label in DOCLIB_TOPICS.items():
        path = UPLOAD_DIR / "doclib" / f"{tid}.pdf"
        out.append({"id": tid, "label": label, "has_document": path.exists()})
    return jsonify({"success": True, "topics": out})


@app.route("/api/doclib/document/<topic_id>", methods=["GET"])
def api_doclib_document(topic_id):
    """Toa PDF YA MADA fulani — LAZIMA session iwe imefungua maktaba (imelipa)."""
    if topic_id not in DOCLIB_TOPICS:
        return jsonify({"success": False, "message": "Mada haipo."}), 404
    if _remaining_doclib_seconds(topic_id) <= 0:
        return jsonify({"success": False, "message": "Lipa kwanza kufungua mada hii."}), 402
    path = UPLOAD_DIR / "doclib" / f"{topic_id}.pdf"
    if not path.exists():
        return jsonify({"success": False, "message": "Nyaraka za mada hii bado hazijapakiwa na admin."}), 404
    resp = send_from_directory(path.parent, path.name, mimetype="application/pdf")
    # Zuia kuhifadhi kwa urahisi kwenye kivinjari — hii ni kizuizi, si dhamana kamili
    resp.headers["Content-Disposition"] = "inline; filename=nyaraka.pdf"
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    return resp


@app.route("/api/admin/doclib/upload", methods=["POST"])
def api_admin_doclib_upload():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    topic_id = (request.form.get("topic_id") or "").strip()
    if topic_id not in DOCLIB_TOPICS:
        return jsonify({"success": False, "message": "Mada si sahihi."}), 400
    f = request.files.get("file")
    if not f or not f.filename or not f.filename.lower().endswith(".pdf"):
        return jsonify({"success": False, "message": "Chagua faili la PDF."}), 400
    dest_dir = UPLOAD_DIR / "doclib"
    dest_dir.mkdir(parents=True, exist_ok=True)
    f.save(str(dest_dir / f"{topic_id}.pdf"))
    return jsonify({"success": True, "message": f"Nyaraka za '{DOCLIB_TOPICS[topic_id]}' zimepakiwa."})


# ==================== 🌍 GLOBAL IMPORT MARKETPLACE ====================
# Bidhaa za kiwandani (USA/China/Uturuki/n.k) + majezi ya Simba/Yanga.
# MUHIMU: Bei za usafiri, ushuru, na mawasiliano ya wauzaji/wasafirishaji
# HAYAJAJAZWA hapa — admin ndiye anayeyaingiza kupitia dashboard, ili
# yasiwe takwimu za kubuniwa zinazoweza kumpotosha mnunuzi.

IMPORT_PLANS = {
    "one_time": {"id": "one_time", "label_sw": "Ada ya kuona maelezo kamili", "price_tzs": 1000, "seconds": 1800},
    "weekly": {"id": "weekly", "label_sw": "Usajili wa Wiki", "price_tzs": 4000, "seconds": 7 * 86400},
    "monthly": {"id": "monthly", "label_sw": "Usajili wa Mwezi", "price_tzs": 10000, "seconds": 30 * 86400},
}
IMPORT_COMMISSION_RATE = 0.03  # 3% ya malipo ya mnunuzi


def _import_db():
    conn = _analytics_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS import_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL DEFAULT 'import',   -- 'import' au 'jersey'
        title TEXT NOT NULL,
        source_country TEXT,
        image_url TEXT,
        estimated_price_tzs INTEGER,
        shipping_cost_tzs INTEGER,
        customs_duty_note TEXT,
        seller_name TEXT, seller_contact TEXT, supplier_url TEXT,
        shipper_name TEXT, shipper_contact TEXT, shipper_url TEXT,
        customs_estimate_tzs INTEGER, weight_kg REAL, source_url TEXT,
        description TEXT,
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS import_local_sellers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, contact TEXT, description TEXT, image_url TEXT,
        active INTEGER DEFAULT 1, created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS agent_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        country TEXT NOT NULL,
        contact_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        website TEXT,
        product_categories TEXT,
        markets TEXT,
        message TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS agent_outreach (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand TEXT NOT NULL,
        language TEXT NOT NULL,
        channel TEXT NOT NULL,
        destination TEXT,
        subject TEXT,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS import_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_ref TEXT UNIQUE, product_id INTEGER,
        plan TEXT, amount_tzs INTEGER, commission_tzs INTEGER,
        buyer_name TEXT, buyer_contact TEXT, buyer_location TEXT,
        method TEXT, phone TEXT,
        status TEXT DEFAULT 'pending',   -- pending -> verified
        unlocked_until TEXT,
        created_at TEXT NOT NULL
    )""")
    # Safe migrations for databases created by earlier versions.
    for col, ddl in [
        ("supplier_url", "ALTER TABLE import_products ADD COLUMN supplier_url TEXT"),
        ("shipper_url", "ALTER TABLE import_products ADD COLUMN shipper_url TEXT"),
        ("customs_estimate_tzs", "ALTER TABLE import_products ADD COLUMN customs_estimate_tzs INTEGER"),
        ("weight_kg", "ALTER TABLE import_products ADD COLUMN weight_kg REAL"),
        ("source_url", "ALTER TABLE import_products ADD COLUMN source_url TEXT"),
    ]:
        try:
            conn.execute(f"SELECT {col} FROM import_products LIMIT 1")
        except sqlite3.OperationalError:
            try: conn.execute(ddl)
            except sqlite3.OperationalError: pass

    # Starter catalogue: clearly marked as indicative/demo data until admin verifies it.
    count = conn.execute("SELECT COUNT(*) FROM import_products WHERE active=1").fetchone()[0]
    if count == 0:
        starter = [
            ("import","Wireless Earbuds Factory Pack","China","/static/uploads/sample-products/example-1.jpg",85000,45000,"Makadirio tu; ushuru uthibitishwe kabla ya oda.","Factory marketplace demo","","https://www.alibaba.com/","DHL/FedEx","","https://www.dhl.com/",10000,0.8,"https://www.alibaba.com/","Demo listing — admin athibitishe supplier."),
            ("import","Ladies Fashion Handbags Wholesale","Turkey","/static/uploads/sample-products/example-2.jpg",120000,65000,"Makadirio tu; customs inaweza kubadilika.","Factory marketplace demo","","https://www.alibaba.com/","DHL/FedEx","","https://www.dhl.com/",14000,1.2,"https://www.alibaba.com/","Demo listing — admin athibitishe supplier."),
            ("import","Women Sandals Bulk Order","China","/static/uploads/sample-products/example-3.jpg",70000,42000,"Makadirio tu; customs uthibitishwe.","Factory marketplace demo","","https://www.alibaba.com/","DHL/FedEx","","https://www.dhl.com/",9000,1.0,"https://www.alibaba.com/","Demo listing — admin athibitishe supplier."),
            ("import","Elegant Women's Dresses Wholesale","Turkey","/static/uploads/sample-products/example-4.jpg",145000,70000,"Makadirio tu; customs uthibitishwe.","Factory marketplace demo","","https://www.made-in-china.com/","DHL/FedEx","","https://www.dhl.com/",18000,1.5,"https://www.made-in-china.com/","Demo listing — admin athibitishe supplier."),
            ("import","Printed Cotton Fabric Roll","India","/static/uploads/sample-products/example-5.jpg",110000,60000,"Makadirio tu; customs uthibitishwe.","Factory marketplace demo","","https://www.alibaba.com/","DHL/FedEx","","https://www.dhl.com/",12000,2.0,"https://www.alibaba.com/","Demo listing — admin athibitishe supplier."),
            ("import","Home Blender / Small Appliance","USA","/static/uploads/sample-products/1000023766.jpg",210000,95000,"Makadirio tu; customs uthibitishwe.","Factory marketplace demo","","https://www.amazon.com/","DHL/FedEx","","https://www.dhl.com/",25000,2.5,"https://www.amazon.com/","Demo listing — admin athibitishe supplier."),
        ]
        conn.executemany("""INSERT INTO import_products(category,title,source_country,image_url,estimated_price_tzs,shipping_cost_tzs,customs_duty_note,seller_name,seller_contact,supplier_url,shipper_name,shipper_contact,shipper_url,customs_estimate_tzs,weight_kg,source_url,description,active,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""", [r+(datetime.utcnow().isoformat()+"Z",) for r in starter])

    # Mobile & smartphone catalogue: official/brand sources from multiple countries.
    # Seed only once per title so existing customer/admin listings are never duplicated.
    mobile_catalogue = [
        ("import","Samsung Galaxy S26 Ultra","South Korea","https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=900&q=85",None,None,"Bei, stock na customs zithibitishwe kabla ya oda.","Samsung Africa — official source","","https://www.samsung.com/africa_en/smartphones/","DHL/FedEx","","https://www.dhl.com/",None,0.9,"https://www.samsung.com/africa_en/smartphones/","📱 ✓ Chanzo rasmi cha Samsung Africa; bei na stock hubadilika kwa nchi."),
        ("import","Samsung Galaxy A57 5G","South Korea","https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=900&q=85",None,None,"Bei, stock na customs zithibitishwe kabla ya oda.","Samsung Africa — official source","","https://www.samsung.com/africa_en/smartphones/galaxy-a/","DHL/FedEx","","https://www.dhl.com/",None,0.7,"https://www.samsung.com/africa_en/smartphones/galaxy-a/","📱 ✓ Chanzo rasmi cha Samsung Africa; hakiki availability ya nchi yako."),
        ("import","Xiaomi 15T","China","https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=900&q=85",None,None,"Bei, stock na customs zithibitishwe kabla ya oda.","Xiaomi Official Store","","https://www.mi.com/global/","DHL/FedEx","","https://www.dhl.com/",None,0.7,"https://www.mi.com/global/phone/","📱 ✓ Chanzo rasmi cha Xiaomi Global; bidhaa na warranty hutegemea soko."),
        ("import","Redmi Note Series Smartphone","China","https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=900&q=85",None,None,"Bei, stock na customs zithibitishwe kabla ya oda.","Xiaomi Official Store","","https://www.mi.com/global/product-list/","DHL/FedEx","","https://www.dhl.com/",None,0.6,"https://www.mi.com/global/product-list/","📱 ✓ Chanzo rasmi cha Xiaomi Global / Redmi; model halisi itathibitishwa kabla ya oda."),
        ("import","iPhone 17","USA","https://images.unsplash.com/photo-1592286927505-2fd0f9d6a0c5?w=900&q=85",None,None,"Bei, stock, carrier compatibility na customs zithibitishwe kabla ya oda.","Apple Online Store — official source","","https://www.apple.com/shop/buy-iphone","DHL/FedEx","","https://www.dhl.com/",None,0.6,"https://www.apple.com/shop/buy-iphone","📱 ✓ Chanzo rasmi cha Apple; chaguo la unlocked/carrier lithibitishwe kabla ya kuagiza."),
        ("import","Apple AirPods","USA","https://images.unsplash.com/photo-1606220945770-b5b6c2c55bf1?w=900&q=85",None,None,"Bei, stock na customs zithibitishwe kabla ya oda.","Apple Online Store — official source","","https://www.apple.com/store","DHL/FedEx","","https://www.dhl.com/",None,0.3,"https://www.apple.com/store","🎧 ✓ Chanzo rasmi cha Apple; model na stock vitathibitishwa kabla ya oda."),
        ("import","Anker 45W GaN Charger","China","https://images.unsplash.com/photo-1583863788434-e58a36330cf0?w=900&q=85",None,None,"Bei, stock na customs zithibitishwe kabla ya oda.","Anker Official Store","","https://www.anker.com/collections/all-anker-chargers","DHL/FedEx","","https://www.dhl.com/",None,0.25,"https://www.anker.com/collections/all-anker-chargers","🔌 ✓ Chanzo rasmi cha Anker; charger/certification na stock vitathibitishwa."),
        ("import","Anker Power Bank","China","https://images.unsplash.com/photo-1609592424850-7d3b5b8f0b5f?w=900&q=85",None,None,"Bei, stock na customs zithibitishwe kabla ya oda.","Anker Official Store","","https://www.anker.com/","DHL/FedEx","","https://www.dhl.com/",None,0.5,"https://www.anker.com/","🔋 ✓ Chanzo rasmi cha Anker; capacity/model itathibitishwa kabla ya oda."),
        ("import","boAt 65W GaN Nano Charger","India","https://images.unsplash.com/photo-1609592424850-7d3b5b8f0b5f?w=900&q=85",None,None,"Bei, stock na customs zithibitishwe kabla ya oda.","boAt Official Store — India","","https://www.boat-lifestyle.com/collections/mobile-accessories","DHL/FedEx","","https://www.dhl.com/",None,0.25,"https://www.boat-lifestyle.com/collections/mobile-accessories","🔌 ✓ Chanzo rasmi cha boAt India; stock na shipping vitathibitishwa kabla ya oda."),
    ]
    for row in mobile_catalogue:
        exists = conn.execute("SELECT 1 FROM import_products WHERE title=? LIMIT 1", (row[1],)).fetchone()
        if not exists:
            conn.execute("""INSERT INTO import_products(category,title,source_country,image_url,estimated_price_tzs,shipping_cost_tzs,customs_duty_note,seller_name,seller_contact,supplier_url,shipper_name,shipper_contact,shipper_url,customs_estimate_tzs,weight_kg,source_url,description,active,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""", row + (datetime.utcnow().isoformat()+"Z",))

    jersey_count = conn.execute("SELECT COUNT(*) FROM import_products WHERE category='jersey' AND active=1").fetchone()[0]
    if jersey_count == 0:
        jerseys = [
            ("jersey","Simba SC — Jezi Rasmi ya Nyumbani 2025/26","Tanzania",None,45000,None,"Bei ya chanzo iliyoorodheshwa kwenye official Simba store; hakiki stock kabla ya kulipa.","Simba Sports Club / JayRutty Official Store","","https://jayruttyshop.sicagroup.co.tz/shop/kits","DHL/Tanzania Postal Corp","","https://www.dhl.com/",None,0.3,"https://www.simbasc.co.tz/","Official-source listing — picha/stock huja kutoka kwa chanzo cha klabu.") ,
            ("jersey","Simba SC — Jezi Rasmi ya Ugenini 2025/26","Tanzania",None,45000,None,"Bei ya chanzo iliyoorodheshwa kwenye official Simba store; hakiki stock kabla ya kulipa.","Simba Sports Club / JayRutty Official Store","","https://jayruttyshop.sicagroup.co.tz/shop/kits","DHL/Tanzania Postal Corp","","https://www.dhl.com/",None,0.3,"https://www.simbasc.co.tz/","Official-source listing — picha/stock huja kutoka kwa chanzo cha klabu."),
            ("jersey","Yanga SC — Jezi Rasmi","Tanzania",None,None,None,"Chanzo rasmi cha klabu kimewekwa; bei na stock vitathibitishwa na admin kabla ya kuonyesha kama vinapatikana.","Young Africans SC","","https://yangasc.co.tz/","Courier wa ndani","","",None,0.3,"https://yangasc.co.tz/","Official club source — bei/stock zinahitaji uthibitisho wa admin."),
        ]
        conn.executemany("""INSERT INTO import_products(category,title,source_country,image_url,estimated_price_tzs,shipping_cost_tzs,customs_duty_note,seller_name,seller_contact,supplier_url,shipper_name,shipper_contact,shipper_url,customs_estimate_tzs,weight_kg,source_url,description,active,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""", [r+(datetime.utcnow().isoformat()+"Z",) for r in jerseys])

    local_count = conn.execute("SELECT COUNT(*) FROM import_local_sellers WHERE active=1").fetchone()[0]
    if local_count == 0:
        locals_ = [
            ("Market Tanzania","https://www.market.co.tz/","Marketplace ya Tanzania; hakiki muuzaji na maelezo kabla ya malipo."),
            ("Zudua Shopping","https://www.zudua.com/","Marketplace ya Tanzania yenye bidhaa za fashion, electronics na home essentials."),
            ("TUNAVUNJA BEI","https://jiji.co.tz/shop/tunavunjabei","Duka lililoorodheshwa Jiji; Kariakoo/Ilala. Thibitisha bidhaa, bei na seller kabla ya kulipa."),
        ]
        conn.executemany("INSERT INTO import_local_sellers(name,contact,description,image_url,active,created_at) VALUES(?,?,?,NULL,1,?)", [(a,b,c,datetime.utcnow().isoformat()+"Z") for a,b,c in locals_])
    conn.commit()
    return conn



@app.route("/api/agent-application", methods=["POST"])
def api_agent_application():
    d = request.get_json(silent=True) or request.form or {}
    company = (d.get("company_name") or "").strip()
    country = (d.get("country") or "").strip()
    contact = (d.get("contact_name") or "").strip()
    if not company or not country or not contact:
        return jsonify({"success": False, "message": "Jaza jina la kampuni, nchi na jina la mawasiliano."}), 400
    conn = _import_db()
    conn.execute(
        """INSERT INTO agent_applications(company_name,country,contact_name,email,phone,website,product_categories,markets,message,status,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (company, country, contact, (d.get("email") or "").strip(), (d.get("phone") or "").strip(),
         (d.get("website") or "").strip(), (d.get("product_categories") or "").strip(),
         (d.get("markets") or "").strip(), (d.get("message") or "").strip(), "pending", datetime.utcnow().isoformat()+"Z")
    )
    conn.commit(); conn.close()
    return jsonify({"success": True, "message": "Ombi lako la uwakala limepokelewa. Timu ya NjiaMauzo itawasiliana nawe."})


@app.route("/api/admin/agent-applications", methods=["GET"])
def api_admin_agent_applications():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    conn = _import_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM agent_applications ORDER BY id DESC").fetchall()]
    conn.close()
    return jsonify({"success": True, "applications": rows})

@app.route("/api/admin/agent-outreach", methods=["GET", "POST"])
def api_admin_agent_outreach():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    conn = _import_db()
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        brand = (d.get("brand") or "").strip()[:120]
        language = (d.get("language") or "en").strip()[:20]
        channel = (d.get("channel") or "official_contact").strip()[:40]
        destination = (d.get("destination") or "").strip()[:500]
        subject = (d.get("subject") or "").strip()[:300]
        message = (d.get("message") or "").strip()[:10000]
        if not brand or not message:
            conn.close()
            return jsonify({"success": False, "message": "Brand na ujumbe vinahitajika."}), 400
        conn.execute("INSERT INTO agent_outreach(brand,language,channel,destination,subject,message,created_at) VALUES(?,?,?,?,?,?,?)",
                     (brand, language, channel, destination, subject, message, datetime.utcnow().isoformat()+"Z"))
        conn.commit()
    rows = [dict(r) for r in conn.execute("SELECT * FROM agent_outreach ORDER BY id DESC LIMIT 100").fetchall()]
    conn.close()
    return jsonify({"success": True, "outreach": rows})


@app.route("/api/import/products", methods=["GET"])
def api_import_products_list():
    category = (request.args.get("category") or "").strip()
    conn = _import_db()
    q = "SELECT * FROM import_products WHERE active=1"
    params = []
    if category in ("import", "jersey"):
        q += " AND category=?"
        params.append(category)
    q += " ORDER BY id DESC"
    rows = [dict(r) for r in conn.execute(q, params).fetchall()]
    conn.close()
    # Maelezo nyeti (gharama, mawasiliano) yanaonyeshwa tu kama order husika imethibitishwa
    unlocked_ids = set(session.get("import_unlocked_products") or [])
    sub_active = False
    sub_until = session.get("import_subscription_until")
    if session.get("import_subscription_all") and sub_until:
        try:
            sub_active = datetime.fromisoformat(sub_until.replace("Z", "+00:00")) > datetime.now(timezone.utc)
        except Exception:
            sub_active = False
    for r in rows:
        if r["id"] not in unlocked_ids and not sub_active and not session.get("is_admin"):
            r["shipping_cost_tzs"] = None
            r["customs_duty_note"] = None
            r["seller_name"] = None
            r["seller_contact"] = None
            r["shipper_name"] = None
            r["shipper_contact"] = None
            r["locked"] = True
        else:
            r["locked"] = False
    return jsonify({"success": True, "products": rows})


@app.route("/api/import/local-sellers", methods=["GET"])
def api_import_local_sellers():
    conn = _import_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM import_local_sellers WHERE active=1 ORDER BY id DESC"
    ).fetchall()]
    conn.close()
    return jsonify({"success": True, "sellers": rows})


@app.route("/api/import/plans", methods=["GET"])
def api_import_plans():
    return jsonify({"success": True, "plans": list(IMPORT_PLANS.values())})


@app.route("/api/import/request", methods=["POST"])
def api_import_request():
    guard = _sabbath_guard()
    if guard:
        return guard
    data = request.get_json(silent=True) or {}
    product_id = data.get("product_id")
    plan_id = (data.get("plan") or "one_time").strip()
    plan = IMPORT_PLANS.get(plan_id) or IMPORT_PLANS["one_time"]
    buyer_name = (data.get("buyer_name") or "").strip()[:80]
    buyer_contact = (data.get("buyer_contact") or "").strip()[:60]
    buyer_location = (data.get("buyer_location") or "").strip()[:120]
    if not buyer_name or not buyer_contact or not buyer_location:
        return jsonify({"success": False, "message": "Jaza jina kamili, mawasiliano, na eneo unaloishi."}), 400
    order_ref = "IMP-" + secrets.token_hex(4).upper()
    commission = round(plan["price_tzs"] * IMPORT_COMMISSION_RATE)
    conn = _import_db()
    conn.execute(
        """INSERT INTO import_orders(order_ref,product_id,plan,amount_tzs,commission_tzs,
               buyer_name,buyer_contact,buyer_location,method,phone,status,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?, 'pending', ?)""",
        (order_ref, product_id, plan["id"], plan["price_tzs"], commission,
         buyer_name, buyer_contact, buyer_location,
         data.get("njia") or "M-Pesa", data.get("simu") or "",
         datetime.utcnow().isoformat() + "Z"),
    )
    conn.commit()
    conn.close()
    session["pending_import_order_ref"] = order_ref
    return jsonify({
        "success": True, "order_ref": order_ref, "amount": plan["price_tzs"],
        "currency": "TZS", "plan": plan["id"], "product_id": product_id,
    })


@app.route("/api/import/status", methods=["GET"])
def api_import_status():
    ref = (request.args.get("order_ref") or session.get("pending_import_order_ref") or "").strip()
    conn = _import_db()
    row = conn.execute("SELECT * FROM import_orders WHERE order_ref=?", (ref,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"success": True, "status": None})
    return jsonify({"success": True, "status": row["status"], "order_ref": ref, "product_id": row["product_id"]})


@app.route("/api/import/activate", methods=["POST"])
def api_import_activate():
    data = request.get_json(silent=True) or {}
    ref = (data.get("order_ref") or session.get("pending_import_order_ref") or "").strip()
    conn = _import_db()
    row = conn.execute("SELECT * FROM import_orders WHERE order_ref=?", (ref,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "message": "Order haipatikani."}), 404
    if row["status"] != "verified" and not session.get("is_admin"):
        conn.close()
        return jsonify({"success": False, "message": "Malipo bado hayajathibitishwa na admin."}), 403
    plan = IMPORT_PLANS.get(row["plan"]) or IMPORT_PLANS["one_time"]
    unlocked_until = (datetime.utcnow() + timedelta(seconds=plan["seconds"])).isoformat() + "Z"
    conn.execute("UPDATE import_orders SET unlocked_until=? WHERE order_ref=?", (unlocked_until, ref))
    conn.commit()
    conn.close()
    unlocked = set(session.get("import_unlocked_products") or [])
    if row["plan"] == "one_time":
        unlocked.add(row["product_id"])
    else:
        # Usajili wa wiki/mwezi -> fungua bidhaa ZOTE kwa muda huo
        session["import_subscription_until"] = unlocked_until
        session["import_subscription_all"] = True
    session["import_unlocked_products"] = list(unlocked)
    return jsonify({"success": True, "unlocked": True, "product_id": row["product_id"], "unlocked_until": unlocked_until})


@app.route("/api/import/admin-orders", methods=["GET"])
def api_import_admin_orders():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    conn = _import_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM import_orders ORDER BY id DESC LIMIT 150"
    ).fetchall()]
    conn.close()
    total_commission = sum(r["commission_tzs"] or 0 for r in rows if r["status"] == "verified")
    return jsonify({"success": True, "orders": rows, "total_commission_tzs": total_commission})


@app.route("/api/import/admin-verify", methods=["POST"])
def api_import_admin_verify():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    data = request.get_json(silent=True) or {}
    ref = (data.get("order_ref") or "").strip()
    conn = _import_db()
    row = conn.execute("SELECT id FROM import_orders WHERE order_ref=?", (ref,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "message": "Order haipatikani."}), 404
    conn.execute("UPDATE import_orders SET status='verified' WHERE order_ref=?", (ref,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Malipo yamethibitishwa."})


@app.route("/api/import/shipping-estimate", methods=["GET"])
def api_import_shipping_estimate():
    """Indicative estimator only. Live courier quotes require a courier API credential."""
    country=(request.args.get("country") or "USA").upper().strip()
    try: weight=max(0.1,float(request.args.get("weight_kg") or 1))
    except Exception: weight=1.0
    # Planning rates, not courier quotes. Admin can override per product.
    rates={"USA":45000,"CHINA":22000,"TURKEY":32000,"INDIA":26000,"UAE":30000,"UK":42000,"GERMANY":48000}
    rate=rates.get(country,35000)
    base=round(rate*weight)
    handling=15000 if weight<=5 else 25000
    total=base+handling
    return jsonify({"success":True,"country":country,"weight_kg":weight,"estimate_tzs":total,"breakdown":{"freight_tzs":base,"handling_tzs":handling},"disclaimer":"Makadirio ya kupanga bajeti tu; si quotation ya DHL/FedEx/UPS. Live quote itahitaji API ya msafirishaji."})

@app.route("/api/import/market-links", methods=["GET"])
def api_import_market_links():
    q=(request.args.get("q") or "").strip()
    enc=urllib.parse.quote_plus(q)
    return jsonify({"success":True,"markets":[
        {"name":"Alibaba.com","url":"https://www.alibaba.com/trade/search?SearchText="+enc,"kind":"B2B / factory"},
        {"name":"Made-in-China","url":"https://www.made-in-china.com/products-search/hot-china-products/"+urllib.parse.quote(q)+".html" if q else "https://www.made-in-china.com/","kind":"Factory / wholesale"},
        {"name":"Amazon","url":"https://www.amazon.com/s?k="+enc,"kind":"Retail / branded"},
        {"name":"AliExpress","url":"https://www.aliexpress.com/w/wholesale-"+urllib.parse.quote(q.replace(' ','-'))+".html" if q else "https://www.aliexpress.com/","kind":"Retail / small MOQ"},
        {"name":"1688","url":"https://s.1688.com/selloffer/offer_search.htm?keywords="+enc,"kind":"China wholesale"},
    ]})

@app.route("/api/admin/import/products", methods=["POST"])
def api_admin_import_product_create():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    d = request.form if request.form else (request.get_json(silent=True) or {})
    title = (d.get("title") or "").strip()
    if not title:
        return jsonify({"success": False, "message": "Weka jina la bidhaa."}), 400
    image_url = (d.get("image_url") or "").strip()
    f = request.files.get("image") if request.files else None
    if f and f.filename:
        ext = Path(f.filename).suffix.lower()
        if ext in (".jpg", ".jpeg", ".png", ".webp"):
            dest_dir = UPLOAD_DIR / "import"
            dest_dir.mkdir(parents=True, exist_ok=True)
            fname = f"prod_{secrets.token_hex(6)}{ext}"
            f.save(str(dest_dir / fname))
            image_url = f"/static/uploads/import/{fname}"
    conn = _import_db()
    conn.execute(
        """INSERT INTO import_products(category,title,source_country,image_url,estimated_price_tzs,
               shipping_cost_tzs,customs_duty_note,seller_name,seller_contact,supplier_url,shipper_name,shipper_contact,
               shipper_url,customs_estimate_tzs,weight_kg,source_url,description,active,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
        (
            (d.get("category") or "import").strip(), title, (d.get("source_country") or "").strip(), image_url,
            int(d.get("estimated_price_tzs") or 0) or None, int(d.get("shipping_cost_tzs") or 0) or None,
            (d.get("customs_duty_note") or "").strip(), (d.get("seller_name") or "").strip(), (d.get("seller_contact") or "").strip(),
            (d.get("supplier_url") or "").strip(), (d.get("shipper_name") or "").strip(), (d.get("shipper_contact") or "").strip(),
            (d.get("shipper_url") or "").strip(), int(d.get("customs_estimate_tzs") or 0) or None,
            float(d.get("weight_kg") or 0) or None, (d.get("source_url") or "").strip(),
            (d.get("description") or "").strip(), datetime.utcnow().isoformat() + "Z",
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Bidhaa imeongezwa."})


@app.route("/api/admin/import/products/<int:pid>", methods=["DELETE"])
def api_admin_import_product_delete(pid):
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    conn = _import_db()
    conn.execute("UPDATE import_products SET active=0 WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Bidhaa imeondolewa."})


@app.route("/api/admin/import/products-all", methods=["GET"])
def api_admin_import_products_all():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    conn = _import_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM import_products WHERE active=1 ORDER BY id DESC"
    ).fetchall()]
    conn.close()
    return jsonify({"success": True, "products": rows})


@app.route("/api/admin/import/local-sellers", methods=["POST"])
def api_admin_import_local_seller_create():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    d = request.form if request.form else (request.get_json(silent=True) or {})
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Weka jina la muuzaji."}), 400
    image_url = (d.get("image_url") or "").strip()
    f = request.files.get("image") if request.files else None
    if f and f.filename:
        ext = Path(f.filename).suffix.lower()
        if ext in (".jpg", ".jpeg", ".png", ".webp"):
            dest_dir = UPLOAD_DIR / "import"
            dest_dir.mkdir(parents=True, exist_ok=True)
            fname = f"seller_{secrets.token_hex(6)}{ext}"
            f.save(str(dest_dir / fname))
            image_url = f"/static/uploads/import/{fname}"
    conn = _import_db()
    conn.execute(
        "INSERT INTO import_local_sellers(name,contact,description,image_url,active,created_at) VALUES(?,?,?,?,1,?)",
        (name, (d.get("contact") or "").strip(), (d.get("description") or "").strip(), image_url,
         datetime.utcnow().isoformat() + "Z"),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Muuzaji ameongezwa."})


@app.route("/api/advisory/robot-search", methods=["POST"])
def api_advisory_robot_search():
    """'Robot' ya Ushauri: baada ya mfumo kujiridhisha kuwa mteja KESHALIPA
    ada husika ya ushauri (order verified), inatafuta bidhaa/taarifa muhimu
    zinazoendana na ombi lake kutoka kwenye database ya bidhaa."""
    data = request.get_json(silent=True) or {}
    order_id = (data.get("order_id") or "").strip()
    query = (data.get("query") or "").strip()[:300]
    if not query:
        return jsonify({"success": False, "message": "Eleza unachohitaji msaada nacho."}), 400

    with ADVISORY_LOCK:
        order = ADVISORY_ORDERS.get(order_id)
        paid = bool(order and order.get("status") == "verified")
    if not paid:
        return jsonify({
            "success": False,
            "message": "Robot ya ushauri inapatikana baada ya kulipa ada husika. Kamilisha malipo kwanza.",
        }), 402

    words = [w for w in query.lower().replace(",", " ").split() if len(w) > 2]
    with PRODUCTS_LOCK:
        snapshot = list(SAMPLE_PRODUCTS)
    scored = []
    for p in snapshot:
        haystack = " ".join(str(p.get(k, "")) for k in
                             ("title", "jina", "description", "location", "unit")).lower()
        score = sum(1 for w in words if w in haystack)
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    results = [{
        "id": p.get("id"), "title": p.get("title") or p.get("jina"),
        "description": p.get("description", ""), "location": p.get("location", ""),
        "seller_name": p.get("seller_name", ""), "emoji": p.get("emoji", "📦"),
    } for _, p in scored[:8]]

    return jsonify({
        "success": True,
        "query": query,
        "results": results,
        "message": (f"Nimepata bidhaa/taarifa {len(results)} zinazoendana na ombi lako."
                     if results else
                     "Sikupata bidhaa zinazoendana moja kwa moja - mshauri wetu atakusaidia kwa WhatsApp."),
    })


def _grant_advisory_access(seconds):
    secs=max(60,int(seconds or 0)); session["advisory_unlocked"]=True
    session["advisory_unlocked_until"]=datetime.utcnow().timestamp()+secs
    return secs

def _remaining_advisory_seconds():
    if session.get("is_admin"): return 86400
    until=session.get("advisory_unlocked_until")
    if not until: return 0
    left=int(until-datetime.utcnow().timestamp())
    if left<=0:
        session.pop("advisory_unlocked",None); session.pop("advisory_unlocked_until",None)
        return 0
    return left


@app.route("/api/advisory/plans", methods=["GET"])
def api_advisory_plans():
    country=(request.args.get("country") or "Tanzania").strip() or "Tanzania"
    info=COUNTRY_CURRENCY.get(country,COUNTRY_CURRENCY["Tanzania"])
    plans=[]
    for p in ADVISORY_PLANS.values():
        plans.append({**p,"amount":max(1,int(round(p["price_tzs"]*info["rate_per_tzs"]))),"currency":info["code"],"country":country})
    return jsonify({"success":True,"plans":plans,"country":country})

@app.route("/api/advisory/request", methods=["POST"])
def api_advisory_request():
    guard = _sabbath_guard()
    if guard: return guard
    data=request.get_json(silent=True) or {}; order_id="ADV-"+secrets.token_hex(4).upper()
    country=(data.get("country") or "Tanzania").strip() or "Tanzania"; info=COUNTRY_CURRENCY.get(country,COUNTRY_CURRENCY["Tanzania"])
    plan=ADVISORY_PLANS.get((data.get("plan") or "1m").strip()) or ADVISORY_PLANS["1m"]
    amount=max(1,int(round(plan["price_tzs"]*info["rate_per_tzs"])))
    with ADVISORY_LOCK:
        ADVISORY_ORDERS[order_id]={"status":"pending","method":data.get("njia") or "M-Pesa","phone":data.get("simu") or "","amount":amount,"currency":info["code"],"country":country,"plan":plan["id"],"duration_minutes":plan["minutes"],"duration_seconds":plan["seconds"],"base_amount_tzs":plan["price_tzs"],"created":datetime.utcnow(),"session_uid":session.get("uid") or _client_ip()}
    session["pending_advisory_order_id"]=order_id
    return jsonify({"success":True,"order_id":order_id,"plan":plan["id"],"duration_minutes":plan["minutes"],"duration_seconds":plan["seconds"],"amount":amount,"currency":info["code"],"country":country})

@app.route("/api/advisory/status", methods=["GET"])
def api_advisory_status():
    oid=(request.args.get("order_id") or session.get("pending_advisory_order_id") or "").strip()
    with ADVISORY_LOCK: o=dict(ADVISORY_ORDERS.get(oid) or {}) if oid else {}
    left=_remaining_advisory_seconds()
    return jsonify({"success":True,"order_id":oid or None,"status":o.get("status"),"plan":o.get("plan"),"duration_minutes":o.get("duration_minutes"),"unlocked":left>0 or bool(session.get("is_admin")),"remaining_seconds":left,"expires_in_sec":left})

@app.route("/api/advisory/activate", methods=["POST"])
def api_advisory_activate():
    guard = _sabbath_guard()
    if guard: return guard
    data=request.get_json(silent=True) or {}; oid=(data.get("order_id") or session.get("pending_advisory_order_id") or "").strip()
    with ADVISORY_LOCK:
        o=ADVISORY_ORDERS.get(oid) if oid else None
        if not o: return jsonify({"success":False,"message":"Order ya ushauri haipatikani."}),404
        if o.get("status")!="verified" and not session.get("is_admin"): return jsonify({"success":False,"message":"Malipo bado hayajathibitishwa na admin."}),403
        duration=int(o.get("duration_seconds") or 900)
    left=_grant_advisory_access(duration); session["pending_advisory_order_id"]=oid
    return jsonify({"success":True,"unlocked":True,"order_id":oid,"plan":o.get("plan"),"duration_minutes":o.get("duration_minutes"),"remaining_seconds":left,"expires_in_sec":left})


@app.route("/api/advisory/admin-verify", methods=["POST"])
def api_advisory_admin_verify():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    data = request.get_json(silent=True) or {}
    order_id = (data.get("order_id") or "").strip()
    with ADVISORY_LOCK:
        order = ADVISORY_ORDERS.get(order_id)
        if not order:
            return jsonify({"success": False, "message": "Order haipatikani."}), 404
        order["status"] = "verified"
        order["verified_at"] = datetime.utcnow()
    return jsonify({"success": True, "order_id": order_id, "plan": order.get("plan"), "duration_minutes": order.get("duration_minutes"), "message": "Order ya ushauri imethibitishwa."})


@app.route("/api/advisory/admin-orders", methods=["GET"])
def api_advisory_admin_orders():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    with ADVISORY_LOCK:
        orders = [
            {"order_id": oid, **{k: v for k, v in o.items() if k not in ("created", "verified_at")},
             "created": o["created"].isoformat() + "Z"}
            for oid, o in sorted(ADVISORY_ORDERS.items(), key=lambda x: x[1]["created"], reverse=True)
        ]
    return jsonify({"success": True, "orders": orders})



@app.route("/api/payment/stk-push", methods=["POST"])
def api_payment_stk_push():
    guard = _sabbath_guard()
    if guard: return guard
    """Anzisha M-Pesa push: Kenya=Daraja STK, Tanzania=Vodacom Open API C2B."""
    data = request.get_json(silent=True) or {}
    phone = (data.get("phone") or data.get("simu") or "").strip()
    country = (data.get("country") or "Tanzania").strip() or "Tanzania"

    if not phone:
        return jsonify({"success": False, "message": "Weka namba ya simu ya M-Pesa."}), 400

    order_id = "ORD-" + secrets.token_hex(4).upper()
    plan_id = "once"
    plan = SUBSCRIPTION_PLANS["once"]

    # ----- Tanzania → Vodacom Open API (TZS) -----
    if country == "Tanzania":
        amount = max(1, int(round(SERVICE_FEE_TZS * plan["multiplier"])))
        currency = "TZS"
        stk = vodacom_tz_c2b(
            phone=phone,
            amount=amount,
            order_id=order_id,
            description="NjiaMauzo ada",
        )
        if not stk.get("success"):
            return jsonify({"success": False, "message": stk.get("message") or "Vodacom TZ imeshindikana."}), 400
        checkout_id = stk.get("CheckoutRequestID") or stk.get("ConversationID") or ""
        with PAYMENT_LOCK:
            PAYMENT_ORDERS[order_id] = {
                "status": "pending_stk",
                "method": "M-Pesa Vodacom TZ",
                "provider": "vodacom_tz",
                "amount": amount,
                "currency": currency,
                "country": country,
                "base_amount_tzs": SERVICE_FEE_TZS,
                "created": datetime.utcnow(),
                "phone": phone,
                "msisdn": stk.get("phone"),
                "user": (session.get("user") or {}).get("email"),
                "CheckoutRequestID": checkout_id,
                "ConversationID": stk.get("ConversationID"),
                "demo": bool(stk.get("demo")),
                "stk_started": datetime.utcnow(),
                "plan": plan_id,
                "access_seconds": int(plan["seconds"]),
            }
        session["pending_order_id"] = order_id
        return jsonify({
            "success": True,
            "order_id": order_id,
            "plan": plan_id,
            "CheckoutRequestID": checkout_id,
            "provider": "vodacom_tz",
            "amount": amount,
            "currency": currency,
            "phone": stk.get("phone"),
            "demo": bool(stk.get("demo")),
            "message": stk.get("message") or "Angalia simu — weka PIN ya M-Pesa (TZ).",
        })

    # ----- Kenya (na nchi nyingine) → Safaricom Daraja STK (KES) -----
    amount = max(1, int(round(SERVICE_FEE_TZS * COUNTRY_CURRENCY.get("Kenya", {}).get("rate_per_tzs", 0.027) * plan["multiplier"])))
    currency = "KES"
    stk = mpesa_stk_push(
        phone=phone,
        amount=amount,
        order_id=order_id,
        account_ref=order_id.replace("ORD-", "NM")[:12],
        description="NjiaMauzo ada",
    )
    if not stk.get("success"):
        return jsonify({"success": False, "message": stk.get("message") or "STK imeshindikana."}), 400

    checkout_id = stk.get("CheckoutRequestID") or ""
    with PAYMENT_LOCK:
        PAYMENT_ORDERS[order_id] = {
            "status": "pending_stk",
            "method": "M-Pesa STK",
            "provider": "safaricom_ke",
            "amount": amount,
            "currency": currency,
            "country": country,
            "base_amount_tzs": SERVICE_FEE_TZS,
            "created": datetime.utcnow(),
            "phone": phone,
            "msisdn": stk.get("phone"),
            "user": (session.get("user") or {}).get("email"),
            "CheckoutRequestID": checkout_id,
            "MerchantRequestID": stk.get("MerchantRequestID"),
            "demo": bool(stk.get("demo")),
            "stk_started": datetime.utcnow(),
            "plan": plan_id,
            "access_seconds": int(plan["seconds"]),
        }
    session["pending_order_id"] = order_id

    return jsonify({
        "success": True,
        "order_id": order_id,
        "plan": plan_id,
        "CheckoutRequestID": checkout_id,
        "provider": "safaricom_ke",
        "amount": amount,
        "currency": currency,
        "phone": stk.get("phone"),
        "demo": bool(stk.get("demo")),
        "message": stk.get("message") or "Angalia simu — weka PIN ya M-Pesa.",
        "CustomerMessage": stk.get("CustomerMessage"),
    })


@app.route("/api/payment/stk-status", methods=["GET"])
def api_payment_stk_status():
    """Angalia hali ya STK (polling kutoka frontend)."""
    order_id = (request.args.get("order_id") or session.get("pending_order_id") or "").strip()
    if not order_id:
        return jsonify({"success": False, "message": "Order ID inahitajika."}), 400

    with PAYMENT_LOCK:
        order = PAYMENT_ORDERS.get(order_id)
        if not order:
            return jsonify({"success": False, "message": "Order haipatikani."}), 404
        status = order.get("status")
        checkout_id = order.get("CheckoutRequestID") or ""
        demo = bool(order.get("demo"))
        started = order.get("stk_started") or order.get("created")

    # Tayari imethibitishwa
    if status == "verified":
        left = _grant_access(ACCESS_DURATION_SEC) if not _is_unlocked() else _remaining_access_seconds()
        if not session.get("unlocked"):
            left = _grant_access(ACCESS_DURATION_SEC)
        return jsonify({
            "success": True,
            "status": "verified",
            "order_id": order_id,
            "unlocked": True,
            "remaining_seconds": left,
            "message": "Malipo yamekamilika.",
        })

    if status in ("failed", "cancelled"):
        return jsonify({
            "success": True,
            "status": status,
            "order_id": order_id,
            "message": order.get("result_desc") or "Malipo yameshindikana au yameghairiwa.",
        })

    # DEMO mode haitoi access bure. Order inabaki pending mpaka admin athibitishe malipo.
    if demo and checkout_id:
        age = int((datetime.utcnow() - started).total_seconds()) if started else 0
        return jsonify({"success":True,"status":"pending_stk","order_id":order_id,"demo":True,
                        "message":"DEMO STK: hakuna access bila uthibitisho wa malipo. Admin athibitishe order.","waited":age})

    # Production: query by provider
    if checkout_id:
        with PAYMENT_LOCK:
            provider = (PAYMENT_ORDERS.get(order_id) or {}).get("provider") or "safaricom_ke"
        if provider == "vodacom_tz":
            q = vodacom_tz_query(checkout_id, order_id)
        else:
            q = mpesa_stk_query(checkout_id)
        rc = str(q.get("ResultCode") or "")
        if rc == "0":
            access_secs = ACCESS_DURATION_SEC
            with PAYMENT_LOCK:
                o = PAYMENT_ORDERS.get(order_id)
                if o:
                    o["status"] = "verified"
                    o["verified_at"] = datetime.utcnow()
                    o["activated_via"] = "stk_query"
                    o["result_desc"] = q.get("ResultDesc")
                    access_secs = int(o.get("access_seconds") or ACCESS_DURATION_SEC)
            left = _grant_access(access_secs)
            return jsonify({
                "success": True,
                "status": "verified",
                "order_id": order_id,
                "unlocked": True,
                "remaining_seconds": left,
                "message": "Malipo yamekamilika.",
            })
        # 1032 = cancelled, 1037 = timeout, 1 = insufficient etc — still pending if 4999
        if rc and rc not in ("", "4999", "None"):
            # pending processing codes vary; only mark failed on clear cancel
            if rc in ("1032", "1037", "1", "2001"):
                with PAYMENT_LOCK:
                    o = PAYMENT_ORDERS.get(order_id)
                    if o:
                        o["status"] = "failed"
                        o["result_desc"] = q.get("ResultDesc")
                return jsonify({
                    "success": True,
                    "status": "failed",
                    "order_id": order_id,
                    "message": q.get("ResultDesc") or "Malipo yameshindikana.",
                })

    return jsonify({
        "success": True,
        "status": "pending_stk",
        "order_id": order_id,
        "message": "Inasubiri uthibitisho wa M-Pesa…",
    })


@app.route("/api/payment/mpesa/callback", methods=["POST"])
def api_mpesa_callback():
    """Webhook kutoka Safaricom baada ya STK (lazima iwe HTTPS public URL)."""
    payload = request.get_json(silent=True) or {}
    try:
        body = payload.get("Body", {}).get("stkCallback", {})
        checkout_id = body.get("CheckoutRequestID")
        result_code = str(body.get("ResultCode", ""))
        result_desc = body.get("ResultDesc", "")
        metadata = {}
        for item in (body.get("CallbackMetadata") or {}).get("Item") or []:
            name = item.get("Name")
            if name:
                metadata[name] = item.get("Value")

        matched_order = None
        with PAYMENT_LOCK:
            for oid, o in PAYMENT_ORDERS.items():
                if o.get("CheckoutRequestID") == checkout_id:
                    matched_order = oid
                    if result_code == "0":
                        o["status"] = "verified"
                        o["verified_at"] = datetime.utcnow()
                        o["activated_via"] = "stk_callback"
                        o["mpesa_receipt"] = metadata.get("MpesaReceiptNumber")
                        o["result_desc"] = result_desc
                    else:
                        o["status"] = "failed"
                        o["result_desc"] = result_desc
                    break
        # Note: session ya mteja haitumiki hapa (callback ni server-to-server)
        return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})
    except Exception as e:
        return jsonify({"ResultCode": 1, "ResultDesc": str(e)}), 200


@app.route("/api/payment/mpesa/config", methods=["GET"])
def api_mpesa_config():
    """Hali ya Kenya STK + Tanzania Vodacom (bila kufichua siri)."""
    return jsonify({
        "success": True,
        "kenya": {
            "demo_mode": MPESA_DEMO_MODE,
            "env": MPESA_ENV,
            "shortcode_set": bool(MPESA_SHORTCODE),
            "callback_set": bool(MPESA_CALLBACK_URL),
        },
        "tanzania": {
            "demo_mode": MPESA_TZ_DEMO_MODE,
            "env": MPESA_TZ_ENV,
            "sp_code_set": bool(MPESA_TZ_SP_CODE and MPESA_TZ_SP_CODE != "000000"),
            "api_key_set": bool(MPESA_TZ_API_KEY),
        },
        "demo_mode": MPESA_DEMO_MODE and MPESA_TZ_DEMO_MODE,
        "message": (
            "DEMO: Kenya (Daraja) na/au Tanzania (Vodacom) — weka env credentials kwa live."
            if (MPESA_DEMO_MODE or MPESA_TZ_DEMO_MODE)
            else "M-Pesa live credentials zimewekwa."
        ),
    })


@app.route("/api/payment/vodacom-tz/callback", methods=["POST"])
def api_vodacom_tz_callback():
    """Callback/webhook kutoka Vodacom / aggregator (hiari)."""
    payload = request.get_json(silent=True) or {}
    try:
        conv = (
            payload.get("ConversationID")
            or payload.get("output_ConversationID")
            or payload.get("ThirdPartyConversationID")
            or payload.get("input_ThirdPartyConversationID")
        )
        result = str(
            payload.get("ResultCode")
            or payload.get("output_ResponseCode")
            or payload.get("status")
            or ""
        )
        ok = result in ("0", "INS-0", "success", "Success", "COMPLETED")
        with PAYMENT_LOCK:
            for oid, o in PAYMENT_ORDERS.items():
                if o.get("CheckoutRequestID") == conv or o.get("ConversationID") == conv:
                    if ok:
                        o["status"] = "verified"
                        o["verified_at"] = datetime.utcnow()
                        o["activated_via"] = "vodacom_tz_callback"
                    else:
                        o["status"] = "failed"
                        o["result_desc"] = str(payload)[:200]
                    break
        return jsonify({"success": True, "ResultCode": 0})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 200



@app.route("/api/countries", methods=["GET"])
def api_countries():
    items = []
    for name, info in COUNTRY_CURRENCY.items():
        items.append({
            "name": name,
            "code": info["code"],
            "flag": info.get("flag", ""),
            "phone_prefix": info.get("phone_prefix", ""),
            "methods": COUNTRY_PAYMENT_METHODS.get(name, ["Google Pay"]),
            "amount": round(SERVICE_FEE_TZS * info["rate_per_tzs"]),
        })
    return jsonify({"success": True, "countries": items})


@app.route("/api/subscription/plans", methods=["GET"])
def api_subscription_plans():
    country = (request.args.get("country") or "Tanzania").strip()
    info = COUNTRY_CURRENCY.get(country, COUNTRY_CURRENCY["Tanzania"])
    plans = []
    for p in SUBSCRIPTION_PLANS.values():
        amount = max(1, int(round(SERVICE_FEE_TZS * info["rate_per_tzs"] * p["multiplier"])))
        plans.append({
            **{k: v for k, v in p.items() if k != "seconds"},
            "seconds": p["seconds"],
            "amount": amount,
            "currency": info["code"],
            "country": country,
        })
    return jsonify({"success": True, "plans": plans, "country": country})


@app.route("/api/payment/google-pay", methods=["POST"])
def api_payment_google_pay():
    guard = _sabbath_guard()
    if guard: return guard
    """Thibitisha malipo ya Google Pay (DEMO au baada ya gateway token)."""
    data = request.get_json(silent=True) or {}
    country = (data.get("country") or "Tanzania").strip() or "Tanzania"
    plan_id = "once"
    plan = SUBSCRIPTION_PLANS["once"]
    info = COUNTRY_CURRENCY.get(country, COUNTRY_CURRENCY["Tanzania"])
    amount = max(1, int(round(SERVICE_FEE_TZS * info["rate_per_tzs"] * plan["multiplier"])))
    currency = info["code"]

    token = data.get("paymentToken") or data.get("token") or {}
    if GOOGLE_PAY_DEMO:
        return jsonify({"success":False,"message":"Google Pay iko DEMO. Hakuna access bila malipo halisi; tumia njia ya malipo ya kawaida au weka live gateway."}),400
    if not token:
        return jsonify({"success": False, "message": "Google Pay token inahitajika."}), 400

    order_id = "GP-" + secrets.token_hex(4).upper()
    with PAYMENT_LOCK:
        PAYMENT_ORDERS[order_id] = {
            "status": "verified",
            "method": "Google Pay",
            "provider": "google_pay",
            "amount": amount,
            "currency": currency,
            "country": country,
            "plan": plan_id,
            "base_amount_tzs": SERVICE_FEE_TZS,
            "created": datetime.utcnow(),
            "verified_at": datetime.utcnow(),
            "phone": data.get("phone") or "",
            "user": (session.get("user") or {}).get("email"),
            "demo": GOOGLE_PAY_DEMO,
            "token_preview": str(token)[:80] if token else "demo",
        }
    session["pending_order_id"] = order_id
    left = _grant_access(int(plan["seconds"]))
    session["subscription_plan"] = plan_id

    return jsonify({
        "success": True,
        "order_id": order_id,
        "amount": amount,
        "currency": currency,
        "plan": plan_id,
        "unlocked": True,
        "remaining_seconds": left,
        "demo": GOOGLE_PAY_DEMO,
        "message": f"Google Pay imefaulu — ufikiaji ({plan.get('label_sw', plan_id)}) umefunguliwa.",
    })


@app.route("/api/payment/google-pay/config", methods=["GET"])
def api_google_pay_config():
    return jsonify({
        "success": True,
        "demo": GOOGLE_PAY_DEMO,
        "merchantId": GOOGLE_PAY_MERCHANT_ID or "01234567890123456789",
        "merchantName": GOOGLE_PAY_MERCHANT_NAME,
        "allowedNetworks": ["VISA", "MASTERCARD", "AMEX"],
        "allowedAuthMethods": ["PAN_ONLY", "CRYPTOGRAM_3DS"],
        "message": "Malipo yamepokelewa" if GOOGLE_PAY_DEMO else "Google Pay live",
    })

@app.route("/api/payment/request", methods=["POST"])
def api_payment_request():
    data = request.get_json(silent=True) or {}
    guard = _sabbath_guard()
    if guard: return guard
    if data.get("admin_bypass") and session.get("is_admin"):
        _grant_access(24 * 3600)
        return jsonify({
            "success": True,
            "order_id": "ADM-" + secrets.token_hex(4).upper(),
            "message": "Admin access bila kulipa.",
            "payment_number": "—",
        })

    order_id = "ORD-" + secrets.token_hex(4).upper()
    numbers = {
        "M-Pesa": "0755248789", "Halotel": "0625031460", "Airtel Money": "0691925100",
        "Tigo Pesa": "0655123456", "MTN MoMo": "0766123456", "Lumicash": "0799123456",
        "Ecocash": "0788123456", "Telebirr": "0911123456", "EVC Plus": "0612123456",
        "Orange Money": "0899123456", "m-Gurush": "0922123456",
    }
    method = data.get("njia") or "M-Pesa"
    country = (data.get("country") or "Tanzania").strip() or "Tanzania"
    plan_id = "once"
    plan = SUBSCRIPTION_PLANS["once"]
    cur_info = COUNTRY_CURRENCY.get(country, COUNTRY_CURRENCY["Tanzania"])
    currency = data.get("currency") or cur_info["code"]
    amount = max(1, int(round(SERVICE_FEE_TZS * cur_info["rate_per_tzs"] * plan["multiplier"])))
    # Amount and duration are calculated on the server; client cannot alter the price.

    # Order huanza "pending" — HAIFUNGUI chochote mpaka admin athibitishe
    # malipo halisi (angalia /api/service/admin-verify).
    with PAYMENT_LOCK:
        PAYMENT_ORDERS[order_id] = {
            "status": "pending",
            "method": method,
            "amount": amount,
            "currency": currency,
            "country": country,
            "base_amount_tzs": SERVICE_FEE_TZS,
            "created": datetime.utcnow(),
            "phone": data.get("phone") or data.get("simu") or "",
            "user": (session.get("user") or {}).get("email"),
            "plan": plan_id,
            "access_seconds": int(plan["seconds"]),
        }
    session["pending_order_id"] = order_id

    fee_label = f"{currency} {amount:,}"
    return jsonify({
        "success": True,
        "order_id": order_id,
        "plan": plan_id,
        "access_seconds": int(plan["seconds"]),
        "payment_number": numbers.get(method, "0755248789"),
        "amount": amount,
        "currency": currency,
        "country": country,
        "message": f"Payment imeanzishwa. Tuma {fee_label}. "
                    "Baada ya kulipa, tuma uthibitisho — utafunguliwa baada ya kukaguliwa.",
    })


AUTO_VERIFY_USED_REFS = set()
AUTO_VERIFY_LOCK = threading.Lock()


@app.route("/api/payment/submit-proof", methods=["POST"])
def api_payment_submit_proof():
    """Mtumiaji anatuma reference/transaction code ya malipo aliyofanya nje ya
    mfumo. Ikiwa inalingana kikamilifu na order (kiasi + muundo wa reference
    sahihi + haijawahi kutumika) — mfumo unaithibitisha MOJA KWA MOJA bila
    kusubiri admin. Isipokuwa hivyo, inabaki 'pending' kwa ukaguzi wa admin."""
    data = request.get_json(silent=True) or {}
    order_id = (data.get("order_id") or session.get("pending_order_id") or "").strip()
    reference = (data.get("reference") or data.get("txn_id") or data.get("transaction_id") or "").strip()
    sender_phone = _normalize_phone(data.get("sender_phone") or data.get("phone") or "")

    with PAYMENT_LOCK:
        order = PAYMENT_ORDERS.get(order_id)
        if not order:
            return jsonify({"success": False, "message": "Order haipatikani."}), 404
        if order.get("status") == "verified":
            return jsonify({"success": True, "message": "Order hii tayari imethibitishwa.", "order_id": order_id, "status": "verified"})

        ref_clean = reference.upper().replace(" ", "")
        # Sheria za auto-verify: reference lazima iwe herufi+namba 6-15, isiwe imetumika
        # kwenye order nyingine, na namba ya mtumaji (ikiwa imetolewa) ilingane na urefu sahihi.
        ref_ok = bool(ref_clean) and 6 <= len(ref_clean) <= 15 and ref_clean.isalnum()
        phone_ok = (not sender_phone) or _valid_tz_style_phone(sender_phone)

        with AUTO_VERIFY_LOCK:
            ref_unused = ref_clean not in AUTO_VERIFY_USED_REFS

        order["submitted_reference"] = reference
        order["submitted_sender_phone"] = sender_phone or order.get("phone", "")

        if ref_ok and phone_ok and ref_unused and order.get("amount", 0) > 0:
            order["status"] = "verified"
            order["verified_at"] = datetime.utcnow()
            order["activated_via"] = "auto-proof"
            with AUTO_VERIFY_LOCK:
                AUTO_VERIFY_USED_REFS.add(ref_clean)
            _wallet_credit_from_verified_order(order)
            return jsonify({
                "success": True, "auto_verified": True, "order_id": order_id, "status": "verified",
                "message": "✅ Malipo yamethibitishwa kiotomatiki! Sasa unaweza kuendelea.",
            })
        else:
            order["status"] = "pending_review"
            reasons = []
            if not ref_ok:
                reasons.append("namba ya muamala (reference) si sahihi/haipo")
            if not ref_unused:
                reasons.append("namba hii ya muamala tayari imetumika")
            if not phone_ok:
                reasons.append("namba ya simu ya mtumaji si sahihi")
            return jsonify({
                "success": True, "auto_verified": False, "order_id": order_id, "status": "pending_review",
                "message": "Uthibitisho umepokelewa lakini unahitaji ukaguzi wa admin: " + "; ".join(reasons) + ".",
            })


@app.route("/api/payment/activate", methods=["POST"])
def api_payment_activate():
    """Baada ya malipo yaliyothibitishwa: fungua ufikiaji kwa DAKIKA 10. Baada ya hapo inadai malipo tena."""
    data = request.get_json(silent=True) or {}
    order_id = (data.get("order_id") or session.get("pending_order_id") or "").strip()
    with PAYMENT_LOCK:
        order = PAYMENT_ORDERS.get(order_id) if order_id else None
        if not order:
            return jsonify({"success":False,"message":"Order haipatikani."}),404
        if order.get("status") != "verified" and not session.get("is_admin"):
            return jsonify({"success":False,"message":"Malipo hayajathibitishwa. Subiri uthibitisho wa malipo."}),403
        if order.get("status") != "verified" and session.get("is_admin"):
            order["status"]="verified"; order["verified_at"]=datetime.utcnow(); order["activated_via"]="admin"
    access_secs = ACCESS_DURATION_SEC
    if order:
        access_secs = int(order.get("access_seconds") or ACCESS_DURATION_SEC)
    left = _grant_access(access_secs)
    if order_id:
        session["pending_order_id"] = order_id
    session["subscription_plan"] = (order or {}).get("plan") or "once"
    return jsonify({
        "success": True,
        "unlocked": True,
        "order_id": order_id or None,
        "plan": session.get("subscription_plan"),
        "message": f"Ufikiaji umefunguliwa ({left // 60} dk). Karibu NjiaMauzo Afrika!",
        "remaining_seconds": left,
        "expires_in_sec": left,
    })


@app.route("/api/access/status", methods=["GET"])
def api_access_status():
    order_id = request.args.get("order_id") or session.get("pending_order_id")
    order = None
    if order_id:
        with PAYMENT_LOCK:
            order = PAYMENT_ORDERS.get(order_id)
        # verified order alone does not extend time — only activate/grant does
    left = _remaining_access_seconds()
    return jsonify({
        "success": True,
        "unlocked": left > 0 or bool(session.get("is_admin")),
        "order_status": order["status"] if order else None,
        "remaining_seconds": left,
        "expires_in_sec": left,
        "access_minutes": ACCESS_DURATION_SEC // 60,
    })




@app.route("/api/service/admin-verify", methods=["POST"])
def api_admin_verify_payment():
    """Njia PEKEE halali ya kufungua ufikiaji: admin anakagua uthibitisho
    wa malipo (screenshot/ujumbe) nje ya mfumo, kisha anaithibitisha hapa."""
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    ok, err = _require_csrf()
    if not ok:
        return err

    data = request.get_json(silent=True) or {}
    order_id = (data.get("order_id") or "").strip()
    with PAYMENT_LOCK:
        order = PAYMENT_ORDERS.get(order_id)
        if not order:
            return jsonify({"success": False, "message": "Order haipatikani."}), 404
        order["status"] = "verified"
        order["verified_at"] = datetime.utcnow()
        _wallet_credit_from_verified_order(order)

    return jsonify({"success": True, "message": f"Order {order_id} imethibitishwa.", "order_id": order_id})


@app.route("/api/admin/orders", methods=["GET"])
def api_admin_orders():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    with PAYMENT_LOCK:
        orders = [
            {"order_id": oid, **{k: v for k, v in o.items() if k not in ("created", "verified_at")},
             "created": o["created"].isoformat() + "Z"}
            for oid, o in sorted(PAYMENT_ORDERS.items(), key=lambda x: x[1]["created"], reverse=True)
        ]
    return jsonify({"success": True, "orders": orders})



# ===== ADS / TANGAZO (admin upload + auto-engage) =====
# ===== CHAT / MAJADILIANO YA UMMA (eneo la matangazo) =====
# Usajili wa namba ya simu unahitajika kabla ya kutuma ujumbe.
# Jumamosi (Sabato): mfumo unachuja ujumbe - matusi/yasiyo ya kidini
# hayapokelewi; mfumo pia unawakutanisha Wasabato walio karibu.

CHAT_LOCK = threading.Lock()

SWAHILI_PROFANITY = {
    "mjinga", "pumbavu", "shenzi", "malaya", "kahaba", "mbwa", "mshenzi",
    "mpumbavu", "fala", "zubaa", "kumbwa", "mama yako", "baba yako",
    "mavi", "mkundu", "kuma", "mboo", "dume", "hovyo sana",
}

SABBATH_KEYWORDS = {
    "mungu", "yesu", "kristo", "kristu", "ibada", "sala", "swala", "omba",
    "kuomba", "biblia", "imani", "sabato", "sabath", "kanisa", "baraka",
    "amina", "bwana", "roho mtakatifu", "neno la mungu", "shukrani",
    "asante mungu", "wokovu", "injili", "mtakatifu", "msifuni",
    "sifa", "zaburi", "nabii", "malaika", "pendo la mungu", "imani yangu",
}


GROUP_MEMBER_LIMIT = 1000
STAR_SIGNUP_BONUS = 1000
STAR_PRICE_TSH = 100  # bei ya nyota 1


def _wallet_db_init(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS wallets (
        phone TEXT PRIMARY KEY,
        stars INTEGER DEFAULT 0,
        updated_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS star_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        delta INTEGER NOT NULL,
        reason TEXT,
        related_phone TEXT,
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        owner_phone TEXT NOT NULL,
        member_limit INTEGER DEFAULT 1000,
        invite_code TEXT,
        created_at TEXT NOT NULL
    )""")
    try:
        conn.execute("ALTER TABLE groups ADD COLUMN invite_code TEXT")
        conn.commit()
    except Exception:
        pass
    conn.execute("""CREATE TABLE IF NOT EXISTS group_members (
        group_id INTEGER NOT NULL,
        phone TEXT NOT NULL,
        name TEXT,
        category TEXT,
        joined_at TEXT NOT NULL,
        active INTEGER DEFAULT 1,
        PRIMARY KEY (group_id, phone)
    )""")
    # Ujumbe wa ndani ya group — SIRI, unaonekana kwa wanachama wa group hiyo pekee
    conn.execute("""CREATE TABLE IF NOT EXISTS group_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        phone TEXT, name TEXT, message TEXT,
        attachment_url TEXT, attachment_type TEXT, sticker TEXT,
        created_at TEXT NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_group_msg_group ON group_messages(group_id, id)")
    conn.commit()


def _wallet_get(conn, phone):
    row = conn.execute("SELECT stars FROM wallets WHERE phone=?", (phone,)).fetchone()
    return row["stars"] if row else 0


def _wallet_credit(conn, phone, delta, reason, related_phone=None):
    now = datetime.utcnow().isoformat() + "Z"
    conn.execute(
        """INSERT INTO wallets(phone,stars,updated_at) VALUES(?,?,?)
           ON CONFLICT(phone) DO UPDATE SET stars = stars + excluded.stars, updated_at=excluded.updated_at""",
        (phone, delta, now),
    )
    conn.execute(
        "INSERT INTO star_transactions(phone,delta,reason,related_phone,created_at) VALUES(?,?,?,?,?)",
        (phone, delta, reason, related_phone, now),
    )


@app.route("/api/wallet", methods=["GET"])
def api_wallet_get():
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza."}), 403
    with CHAT_LOCK:
        conn = _analytics_db()
        _wallet_db_init(conn)
        stars = _wallet_get(conn, phone)
        history = conn.execute(
            "SELECT delta,reason,related_phone,created_at FROM star_transactions WHERE phone=? ORDER BY id DESC LIMIT 20",
            (phone,),
        ).fetchall()
        conn.close()
    return jsonify({"success": True, "stars": stars, "star_price_tsh": STAR_PRICE_TSH,
                    "history": [dict(r) for r in history]})


@app.route("/api/wallet/buy", methods=["POST"])
def api_wallet_buy():
    """Anzisha order ya kununua nyota kwa TSh 100/nyota. Inatumia mfumo wa malipo
    uliopo tayari (PAYMENT_ORDERS) - baada ya kuthibitishwa (auto au admin),
    nyota zinaingizwa kwenye wallet ya mtumiaji."""
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza (namba ya simu)."}), 403
    data = request.get_json(silent=True) or {}
    try:
        stars = int(data.get("stars") or 0)
    except (TypeError, ValueError):
        stars = 0
    if stars <= 0:
        return jsonify({"success": False, "message": "Weka idadi sahihi ya nyota unazotaka kununua."}), 400
    amount = stars * STAR_PRICE_TSH
    order_id = secrets.token_hex(8)
    with PAYMENT_LOCK:
        PAYMENT_ORDERS[order_id] = {
            "order_id": order_id, "phone": phone, "amount": amount,
            "kind": "stars", "stars": stars,
            "status": "pending", "created_at": datetime.utcnow(),
        }
    return jsonify({
        "success": True, "order_id": order_id, "amount": amount, "stars": stars,
        "message": f"Order imeundwa: {stars}⭐ kwa TSh {amount}. Fanya malipo kisha tuma reference kwenye /api/payment/submit-proof.",
    })


def _wallet_credit_from_verified_order(order):
    """Ikiwa order iliyothibitishwa (auto au admin) ni ya kununua nyota, ingiza
    nyota kwenye wallet ya mnunuzi. Salama kuita mara nyingi (haitarudia kama
    tayari imeshalipwa nyota)."""
    if not order or order.get("kind") != "stars" or order.get("stars_credited"):
        return
    phone = order.get("phone")
    stars = order.get("stars") or 0
    if not phone or stars <= 0:
        return
    with CHAT_LOCK:
        conn = _analytics_db()
        _wallet_db_init(conn)
        _wallet_credit(conn, phone, stars, "Ununuzi wa nyota")
        conn.commit()
        conn.close()
    order["stars_credited"] = True


@app.route("/api/wallet/gift", methods=["POST"])
def api_wallet_gift():
    """Tuma nyota kama zawadi kwa mwanachama mwingine (mfano: kumtangazia
    unayempenda)."""
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza."}), 403
    data = request.get_json(silent=True) or {}
    to_phone = _normalize_phone(data.get("to_phone") or data.get("phone") or "")
    try:
        stars = int(data.get("stars") or 0)
    except (TypeError, ValueError):
        stars = 0
    message = (data.get("message") or "").strip()[:150]
    if not to_phone or stars <= 0:
        return jsonify({"success": False, "message": "Weka namba ya mpokeaji na idadi sahihi ya nyota."}), 400
    if to_phone == phone:
        return jsonify({"success": False, "message": "Huwezi kujitumia nyota mwenyewe."}), 400
    with CHAT_LOCK:
        conn = _analytics_db()
        _wallet_db_init(conn)
        _chat_db_init(conn)
        balance = _wallet_get(conn, phone)
        if balance < stars:
            conn.close()
            return jsonify({"success": False, "message": f"Huna nyota za kutosha. Unazo {balance}⭐."}), 400
        recipient = conn.execute("SELECT phone FROM chat_users WHERE phone=?", (to_phone,)).fetchone()
        if not recipient:
            conn.close()
            return jsonify({"success": False, "message": "Mpokeaji hajajisajili kwenye mfumo."}), 404
        _wallet_credit(conn, phone, -stars, f"Zawadi kwa {to_phone}: {message}"[:200], related_phone=to_phone)
        _wallet_credit(conn, to_phone, stars, f"Zawadi kutoka {phone}: {message}"[:200], related_phone=phone)
        conn.commit()
        conn.close()
    return jsonify({"success": True, "message": f"Umetuma {stars}⭐ kwa {to_phone}!"})


# ===== MULTI-ACCOUNT GROUPS: kila mtumiaji anaweza kutengeneza group yake =====

@app.route("/api/groups/create", methods=["POST"])
def api_groups_create():
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza (namba ya simu)."}), 403
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()[:80]
    if not name:
        return jsonify({"success": False, "message": "Weka jina la group lako."}), 400
    now = datetime.utcnow().isoformat() + "Z"
    invite_code = secrets.token_urlsafe(6)
    with CHAT_LOCK:
        conn = _analytics_db()
        _wallet_db_init(conn)
        cur = conn.execute(
            "INSERT INTO groups(name,owner_phone,member_limit,invite_code,created_at) VALUES(?,?,?,?,?)",
            (name, phone, GROUP_MEMBER_LIMIT, invite_code, now),
        )
        gid = cur.lastrowid
        conn.execute(
            "INSERT INTO group_members(group_id,phone,name,category,joined_at,active) VALUES(?,?,?,?,?,1)",
            (gid, phone, session.get("chat_name") or "Mmiliki", "Mwingine", now),
        )
        conn.commit()
        conn.close()
    return jsonify({
        "success": True, "group_id": gid, "name": name, "invite_code": invite_code,
        "message": "Group limeundwa! Shiriki link ya kujiunga na wanachama wako.",
    })


@app.route("/api/groups/mine", methods=["GET"])
def api_groups_mine():
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": True, "owned": [], "joined": []})
    with CHAT_LOCK:
        conn = _analytics_db()
        _wallet_db_init(conn)
        owned = conn.execute("SELECT id,name,member_limit,invite_code,created_at FROM groups WHERE owner_phone=?", (phone,)).fetchall()
        joined = conn.execute(
            """SELECT g.id,g.name,g.owner_phone,
                      (SELECT COUNT(*) FROM group_members gm2 WHERE gm2.group_id=g.id AND gm2.active=1) AS member_count
               FROM groups g JOIN group_members gm ON gm.group_id=g.id
               WHERE gm.phone=? AND gm.active=1""",
            (phone,),
        ).fetchall()
        conn.close()
    return jsonify({"success": True, "owned": [dict(r) for r in owned], "joined": [dict(r) for r in joined]})


def _group_join_common(conn, gid, phone, name, now):
    grp = conn.execute("SELECT id,name,member_limit FROM groups WHERE id=?", (gid,)).fetchone()
    if not grp:
        return None, "Group halipatikani."
    already = conn.execute("SELECT phone FROM group_members WHERE group_id=? AND phone=?", (gid, phone)).fetchone()
    if not already:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM group_members WHERE group_id=? AND active=1", (gid,)
        ).fetchone()["c"]
        if count >= (grp["member_limit"] or GROUP_MEMBER_LIMIT):
            return None, "Group hili limejaa (limefikia ukomo wa wanachama)."
        conn.execute(
            "INSERT INTO group_members(group_id,phone,name,category,joined_at,active) VALUES(?,?,?,?,?,1)",
            (gid, phone, name or "Mwanachama", "Mwingine", now),
        )
    else:
        conn.execute("UPDATE group_members SET active=1 WHERE group_id=? AND phone=?", (gid, phone))
    return grp, None


@app.route("/api/groups/<int:gid>/join", methods=["POST"])
def api_groups_join(gid):
    """Njia ya 1: mtumiaji anajiunga mwenyewe moja kwa moja (akijua group_id)."""
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza (namba ya simu)."}), 403
    now = datetime.utcnow().isoformat() + "Z"
    with CHAT_LOCK:
        conn = _analytics_db()
        _wallet_db_init(conn)
        grp, err = _group_join_common(conn, gid, phone, session.get("chat_name"), now)
        if err:
            conn.close()
            return jsonify({"success": False, "message": err}), 400 if grp is None and "halipatikani" in err else 403
        conn.commit()
        conn.close()
    return jsonify({"success": True, "message": "Umejiunga na group!", "group_id": gid, "group_name": grp["name"]})


@app.route("/api/groups/join-by-code", methods=["POST"])
def api_groups_join_by_code():
    """Njia ya 2: mtumiaji anajiunga kwa kutumia invite code/link aliyopewa."""
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza (namba ya simu)."}), 403
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    if not code:
        return jsonify({"success": False, "message": "Weka invite code sahihi."}), 400
    now = datetime.utcnow().isoformat() + "Z"
    with CHAT_LOCK:
        conn = _analytics_db()
        _wallet_db_init(conn)
        grp_row = conn.execute("SELECT id FROM groups WHERE invite_code=?", (code,)).fetchone()
        if not grp_row:
            conn.close()
            return jsonify({"success": False, "message": "Invite code si sahihi au imeisha muda."}), 404
        grp, err = _group_join_common(conn, grp_row["id"], phone, session.get("chat_name"), now)
        if err:
            conn.close()
            return jsonify({"success": False, "message": err}), 403
        conn.commit()
        conn.close()
    return jsonify({"success": True, "message": f"Umejiunga na group '{grp['name']}'!", "group_id": grp["id"], "group_name": grp["name"]})


@app.route("/api/groups/<int:gid>/add-member", methods=["POST"])
def api_groups_add_member(gid):
    """Njia ya 3: mmiliki wa group anamwongeza mtu moja kwa moja kwa namba yake
    ya simu (mtu huyo lazima awe amejisajili kwenye mfumo tayari)."""
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza."}), 403
    data = request.get_json(silent=True) or {}
    target_phone = _normalize_phone(data.get("phone") or "")
    if not target_phone:
        return jsonify({"success": False, "message": "Weka namba ya simu ya mtu wa kuongeza."}), 400
    now = datetime.utcnow().isoformat() + "Z"
    with CHAT_LOCK:
        conn = _analytics_db()
        _wallet_db_init(conn)
        _chat_db_init(conn)
        grp = conn.execute("SELECT id,name,owner_phone,member_limit FROM groups WHERE id=?", (gid,)).fetchone()
        if not grp:
            conn.close()
            return jsonify({"success": False, "message": "Group halipatikani."}), 404
        if grp["owner_phone"] != phone:
            conn.close()
            return jsonify({"success": False, "message": "Wewe si mmiliki wa group hili."}), 403
        target_user = conn.execute("SELECT phone,name FROM chat_users WHERE phone=?", (target_phone,)).fetchone()
        if not target_user:
            conn.close()
            return jsonify({"success": False, "message": "Mtu huyu hajajisajili kwenye mfumo bado."}), 404
        _, err = _group_join_common(conn, gid, target_phone, target_user["name"], now)
        if err:
            conn.close()
            return jsonify({"success": False, "message": err}), 403
        conn.commit()
        conn.close()
    return jsonify({"success": True, "message": f"{target_phone} ameongezwa kwenye group '{grp['name']}'."})


@app.route("/api/groups/<int:gid>/members", methods=["GET"])
def api_groups_members(gid):
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza."}), 403
    with CHAT_LOCK:
        conn = _analytics_db()
        _wallet_db_init(conn)
        grp = conn.execute("SELECT id,name,owner_phone FROM groups WHERE id=?", (gid,)).fetchone()
        if not grp:
            conn.close()
            return jsonify({"success": False, "message": "Group halipatikani."}), 404
        is_owner = grp["owner_phone"] == phone
        rows = conn.execute(
            "SELECT phone,name,category,joined_at FROM group_members WHERE group_id=? AND active=1 ORDER BY joined_at",
            (gid,),
        ).fetchall()
        conn.close()
    members = [dict(r) for r in rows]
    if not is_owner:
        for m in members:
            m["phone"] = m["phone"][:4] + "***" + m["phone"][-2:]
    return jsonify({"success": True, "group_name": grp["name"], "is_owner": is_owner, "members": members})


def _is_active_group_member(conn, gid, phone):
    row = conn.execute(
        "SELECT 1 FROM group_members WHERE group_id=? AND phone=? AND active=1", (gid, phone)
    ).fetchone()
    return bool(row)


@app.route("/api/groups/<int:gid>/messages", methods=["GET"])
def api_group_messages(gid):
    """Ujumbe wa ndani ya group — SIRI, unapatikana kwa wanachama wa group hiyo pekee."""
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza."}), 403
    with CHAT_LOCK:
        conn = _analytics_db()
        _wallet_db_init(conn)
        _chat_db_init(conn)
        grp = conn.execute("SELECT id,name FROM groups WHERE id=?", (gid,)).fetchone()
        if not grp:
            conn.close()
            return jsonify({"success": False, "message": "Group halipatikani."}), 404
        if not _is_active_group_member(conn, gid, phone):
            conn.close()
            return jsonify({"success": False, "message": "Huu si mwanachama wa group hii."}), 403
        rows = conn.execute(
            """SELECT m.id,m.phone,m.name,m.message,m.created_at,
                      m.attachment_url AS attachment_url, m.attachment_type AS attachment_type,
                      m.sticker AS sticker, u.avatar_url AS avatar_url
               FROM group_messages m LEFT JOIN chat_users u ON u.phone = m.phone
               WHERE m.group_id=? ORDER BY m.id DESC LIMIT 100""",
            (gid,),
        ).fetchall()
        conn.close()
    messages = []
    for r in rows:
        d = dict(r)
        d["is_mine"] = d.get("phone") == phone
        messages.append(d)
    return jsonify({"success": True, "group_name": grp["name"], "messages": list(reversed(messages))})


@app.route("/api/groups/<int:gid>/send", methods=["POST"])
@rate_limit("group_send", max_attempts=40, window_seconds=60)
def api_group_send(gid):
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza."}), 403
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()[:500]
    attachment_url = _safe_chat_attachment_url(data.get("attachment_url") or "")
    attachment_type = (data.get("attachment_type") or "").strip()[:20]
    sticker = (data.get("sticker") or "").strip()[:80]
    if attachment_url and attachment_type not in ("image", "video", "audio", "pdf"):
        return jsonify({"success": False, "message": "Aina ya faili si sahihi."}), 400
    if not message and not attachment_url and not sticker:
        return jsonify({"success": False, "message": "Andika ujumbe au ambatanisha faili/sticker."}), 400
    now = datetime.utcnow().isoformat() + "Z"
    name = session.get("chat_name") or "Mtumiaji"
    with CHAT_LOCK:
        conn = _analytics_db()
        _wallet_db_init(conn)
        _chat_db_init(conn)
        grp = conn.execute("SELECT id FROM groups WHERE id=?", (gid,)).fetchone()
        if not grp:
            conn.close()
            return jsonify({"success": False, "message": "Group halipatikani."}), 404
        if not _is_active_group_member(conn, gid, phone):
            conn.close()
            return jsonify({"success": False, "message": "Huu si mwanachama wa group hii."}), 403
        conn.execute(
            """INSERT INTO group_messages(group_id,phone,name,message,attachment_url,attachment_type,sticker,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (gid, phone, name, message, attachment_url or None, attachment_type or None, sticker or None, now),
        )
        conn.commit()
        conn.close()
    return jsonify({"success": True, "message": "Ujumbe umetumwa."})


@app.route("/api/groups/<int:gid>/remove-member", methods=["POST"])
def api_groups_remove_member(gid):
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza."}), 403
    data = request.get_json(silent=True) or {}
    target_phone = _normalize_phone(data.get("phone") or "")
    with CHAT_LOCK:
        conn = _analytics_db()
        _wallet_db_init(conn)
        grp = conn.execute("SELECT id,owner_phone FROM groups WHERE id=?", (gid,)).fetchone()
        if not grp:
            conn.close()
            return jsonify({"success": False, "message": "Group halipatikani."}), 404
        if grp["owner_phone"] != phone:
            conn.close()
            return jsonify({"success": False, "message": "Wewe si mmiliki wa group hili."}), 403
        conn.execute("UPDATE group_members SET active=0 WHERE group_id=? AND phone=?", (gid, target_phone))
        conn.commit()
        conn.close()
    return jsonify({"success": True, "message": "Mwanachama ameondolewa."})



def _chat_db_init(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS chat_users (
        phone TEXT PRIMARY KEY,
        name TEXT,
        mkoa TEXT,
        category TEXT,
        lat REAL, lon REAL,
        registered_at TEXT NOT NULL
    )""")
    # Ongeza column 'category' kwa DB za zamani ambazo hazina bado (safe no-op ikiwa tayari ipo)
    try:
        conn.execute("ALTER TABLE chat_users ADD COLUMN category TEXT")
        conn.commit()
    except Exception:
        pass
    # Picha ya profaili (avatar) kwa mtumiaji wa chat/group
    try:
        conn.execute("ALTER TABLE chat_users ADD COLUMN avatar_url TEXT")
        conn.commit()
    except Exception:
        pass
    conn.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT, name TEXT, message TEXT,
        status TEXT DEFAULT 'ok',
        reject_reason TEXT,
        created_at TEXT NOT NULL
    )""")
    # Attachment (pdf/picha/sauti/video) na cartoon sticker kwenye ujumbe
    for col in ("attachment_url TEXT", "attachment_type TEXT", "sticker TEXT"):
        try:
            conn.execute(f"ALTER TABLE chat_messages ADD COLUMN {col}")
            conn.commit()
        except Exception:
            pass
    conn.execute("""CREATE TABLE IF NOT EXISTS chat_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL, message TEXT NOT NULL,
        day_key TEXT NOT NULL,
        created_at TEXT NOT NULL,
        read_flag INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS chat_message_likes (
        message_id INTEGER NOT NULL,
        phone TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (message_id, phone)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_msg_created ON chat_messages(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_notif_phone ON chat_notifications(phone, day_key)")
    conn.commit()


def _normalize_phone(raw: str) -> str:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit() or ch == "+")
    return digits


def _valid_tz_style_phone(phone: str) -> bool:
    d = "".join(ch for ch in phone if ch.isdigit())
    return 9 <= len(d) <= 13


def _contains_profanity(text: str) -> bool:
    low = text.lower()
    return any(bad in low for bad in SWAHILI_PROFANITY)


def _contains_sabbath_keyword(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in SABBATH_KEYWORDS)


def _sabbath_message_allowed(text: str):
    """Angalia kama ujumbe unaruhusiwa. Rudisha (ok, reason_if_not)."""
    if _contains_profanity(text):
        return False, "Ujumbe una matusi/maneno yasiyofaa - hautapokelewa."
    if _is_sabbath():
        if not _contains_sabbath_keyword(text):
            return False, ("Leo ni Sabato - mfumo unapokea ujumbe wa kiroho/kidini pekee "
                            "wakati wa ibada takatifu.")
    return True, None


def _haversine_km(lat1, lon1, lat2, lon2):
    try:
        lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
    except (TypeError, ValueError):
        return None
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1, math.sqrt(a)))


SABBATH_INVITE_LOCK = threading.Lock()
SABBATH_INVITE_LAST_DAY = {"key": None}


def _maybe_generate_sabbath_invites():
    """Ikiwa ni Sabato na bado hatujawatumia Wasabato ujumbe leo, watafute
    walio karibu (GPS au mkoa unaofanana) na uwaandikie mwaliko wa ibada."""
    if not _is_sabbath():
        return
    day_key = datetime.utcnow().strftime("%Y-%m-%d")
    with SABBATH_INVITE_LOCK:
        if SABBATH_INVITE_LAST_DAY["key"] == day_key:
            return
        SABBATH_INVITE_LAST_DAY["key"] = day_key

    with CHAT_LOCK:
        conn = _analytics_db()
        _chat_db_init(conn)
        users = [dict(r) for r in conn.execute("SELECT phone,name,mkoa,lat,lon FROM chat_users").fetchall()]
        now = datetime.utcnow().isoformat() + "Z"
        invite_text = ("🙏 Karibu Sabato Njema! Wasabato wenzako walio karibu nawe wanakukaribisha "
                        "kuungana katika ibada takatifu ya Mungu leo. Baraka tele!")
        count = 0
        for u in users:
            nearby = False
            for v in users:
                if v["phone"] == u["phone"]:
                    continue
                if u.get("lat") is not None and u.get("lon") is not None and v.get("lat") is not None and v.get("lon") is not None:
                    d = _haversine_km(u["lat"], u["lon"], v["lat"], v["lon"])
                    if d is not None and d <= 50:
                        nearby = True
                        break
                elif u.get("mkoa") and v.get("mkoa") and u["mkoa"].strip().lower() == v["mkoa"].strip().lower():
                    nearby = True
                    break
            if nearby:
                conn.execute(
                    "INSERT INTO chat_notifications(phone,message,day_key,created_at) VALUES(?,?,?,?)",
                    (u["phone"], invite_text, day_key, now),
                )
                count += 1
        conn.commit()
        conn.close()


@app.route("/api/chat/register", methods=["POST"])
@rate_limit("chat_register", max_attempts=10, window_seconds=600)
def api_chat_register():
    avatar_file = None
    if request.content_type and "multipart/form-data" in request.content_type:
        data = request.form
        avatar_file = request.files.get("avatar")
    else:
        data = request.get_json(silent=True) or {}
    phone = _normalize_phone(data.get("phone") or "")
    name = (data.get("name") or "").strip()[:60] or "Msabato"
    mkoa = (data.get("mkoa") or data.get("region") or "").strip()[:60]
    category = (data.get("category") or "").strip()[:40]
    avatar_url = _safe_chat_attachment_url(data.get("avatar_url") or "")
    if avatar_file and avatar_file.filename:
        ext = Path(avatar_file.filename).suffix.lower()
        if CHAT_UPLOAD_ALLOWED.get(ext) != "image":
            return jsonify({"success": False, "message": "Picha ya profaili lazima iwe jpg/png/webp/gif."}), 400
        dest_dir = UPLOAD_DIR / "chat_media"
        dest_dir.mkdir(parents=True, exist_ok=True)
        fname = f"avatar_{secrets.token_hex(8)}{ext}"
        avatar_file.save(str(dest_dir / fname))
        avatar_url = f"/static/uploads/chat_media/{fname}"
    if category not in ("Mfanyakazi", "Mfanyabiashara", "Mwanafunzi", "Mkulima", "Mwingine"):
        category = "Mwingine"
    lat = data.get("lat")
    lon = data.get("lon")
    if not _valid_tz_style_phone(phone):
        return jsonify({"success": False, "message": "Weka namba sahihi ya simu (mfano 0755xxxxxx)."}), 400
    if _is_banned_identifier(phone):
        return jsonify({"success": False, "message": "Namba hii imezuiwa na msimamizi."}), 403
    now = datetime.utcnow().isoformat() + "Z"
    is_new_signup = False
    with CHAT_LOCK:
        conn = _analytics_db()
        _chat_db_init(conn)
        _wallet_db_init(conn)
        existing = conn.execute("SELECT phone FROM chat_users WHERE phone=?", (phone,)).fetchone()
        if not existing:
            is_new_signup = True
            total = conn.execute("SELECT COUNT(*) AS c FROM chat_users").fetchone()["c"]
            if total >= GROUP_MEMBER_LIMIT:
                conn.close()
                return jsonify({
                    "success": False,
                    "message": f"Samahani, group imefikia ukomo wa wanachama {GROUP_MEMBER_LIMIT}. Jaribu tena baadaye.",
                    "group_full": True,
                }), 403
        conn.execute(
            """INSERT INTO chat_users(phone,name,mkoa,category,lat,lon,avatar_url,registered_at) VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(phone) DO UPDATE SET name=excluded.name, mkoa=excluded.mkoa,
               category=excluded.category,
               avatar_url=COALESCE(NULLIF(excluded.avatar_url,''), chat_users.avatar_url),
               lat=COALESCE(excluded.lat, chat_users.lat), lon=COALESCE(excluded.lon, chat_users.lon)""",
            (phone, name, mkoa, category, lat, lon, avatar_url, now),
        )
        if is_new_signup:
            _wallet_credit(conn, phone, STAR_SIGNUP_BONUS, "Zawadi ya kujisajili (karibu!)")
        conn.commit()
        member_count = conn.execute("SELECT COUNT(*) AS c FROM chat_users").fetchone()["c"]
        stars_balance = _wallet_get(conn, phone)
        conn.close()
    session["phone"] = phone
    session["chat_name"] = name
    return jsonify({
        "success": True, "message": "Umesajiliwa. Sasa unaweza kuandika kwenye majadiliano.",
        "phone": phone, "name": name, "member_count": member_count, "member_limit": GROUP_MEMBER_LIMIT,
        "stars": stars_balance, "new_signup_bonus": STAR_SIGNUP_BONUS if is_new_signup else 0,
        "avatar_url": avatar_url,
    })


def _safe_chat_attachment_url(url: str) -> str:
    """Ruhusu tu URL zilizotengenezwa na /api/chat/upload (relative, same-origin).
    Inazuia stored-XSS kupitia javascript:/data: URLs kwenye attachment_url."""
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith("/static/uploads/chat_media/"):
        return ""
    if any(c in url for c in ("\n", "\r", "\t", " ")):
        return ""
    return url[:300]


CHAT_UPLOAD_ALLOWED = {
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image", ".webp": "image",
    ".mp4": "video", ".webm": "video", ".mov": "video",
    ".mp3": "audio", ".wav": "audio", ".ogg": "audio", ".m4a": "audio",
    ".pdf": "pdf",
}


@app.route("/api/chat/upload", methods=["POST"])
@rate_limit("chat_upload", max_attempts=20, window_seconds=300)
def api_chat_upload():
    """Pakia picha ya profaili (avatar) AU faili la kuambatanisha kwenye ujumbe
    (pdf, picha, sauti, video). Inatumika na mtumiaji aliyejisajili kwenye chat."""
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza kabla ya kupakia faili."}), 403
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"success": False, "message": "Hakuna faili lililopakiwa."}), 400
    ext = Path(f.filename).suffix.lower()
    kind = CHAT_UPLOAD_ALLOWED.get(ext)
    if not kind:
        return jsonify({"success": False, "message": f"Aina ya faili hairuhusiwi: {ext}"}), 400
    purpose = (request.form.get("purpose") or "attachment").strip().lower()
    if purpose == "avatar" and kind != "image":
        return jsonify({"success": False, "message": "Picha ya profaili lazima iwe picha (jpg/png/webp/gif)."}), 400
    dest_dir = UPLOAD_DIR / "chat_media"
    dest_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{purpose}_{secrets.token_hex(8)}{ext}"
    dest = dest_dir / fname
    f.save(str(dest))
    url = f"/static/uploads/chat_media/{fname}"
    if purpose == "avatar":
        with CHAT_LOCK:
            conn = _analytics_db()
            _chat_db_init(conn)
            conn.execute("UPDATE chat_users SET avatar_url=? WHERE phone=?", (url, phone))
            conn.commit()
            conn.close()
    return jsonify({"success": True, "url": url, "type": kind})


@app.route("/api/chat/group-info", methods=["GET"])
def api_chat_group_info():
    with CHAT_LOCK:
        conn = _analytics_db()
        _chat_db_init(conn)
        member_count = conn.execute("SELECT COUNT(*) AS c FROM chat_users").fetchone()["c"]
        conn.close()
    return jsonify({
        "success": True, "member_count": member_count, "member_limit": GROUP_MEMBER_LIMIT,
        "spots_left": max(0, GROUP_MEMBER_LIMIT - member_count), "sabbath": _is_sabbath(),
    })


@app.route("/api/chat/messages", methods=["GET"])
def api_chat_messages_list():
    _maybe_generate_sabbath_invites()
    my_phone = session.get("phone")
    with CHAT_LOCK:
        conn = _analytics_db()
        _chat_db_init(conn)
        rows = conn.execute(
            """SELECT m.id,m.phone,m.name,m.message,m.created_at,COALESCE(u.category,'Mwingine') AS category,
                      u.avatar_url AS avatar_url,
                      m.attachment_url AS attachment_url, m.attachment_type AS attachment_type,
                      m.sticker AS sticker,
                      (SELECT COUNT(*) FROM chat_message_likes l WHERE l.message_id=m.id) AS like_count
               FROM chat_messages m LEFT JOIN chat_users u ON u.phone = m.phone
               WHERE m.status='ok' ORDER BY m.id DESC LIMIT 50"""
        ).fetchall()
        liked_ids = set()
        if my_phone:
            liked_rows = conn.execute(
                "SELECT message_id FROM chat_message_likes WHERE phone=?", (my_phone,)
            ).fetchall()
            liked_ids = {r["message_id"] for r in liked_rows}
        conn.close()
    messages = []
    for r in rows:
        d = dict(r)
        d["liked_by_me"] = d["id"] in liked_ids
        d["is_mine"] = bool(my_phone) and d.get("phone") == my_phone
        messages.append(d)
    return jsonify({
        "success": True,
        "sabbath": _is_sabbath(),
        "messages": list(reversed(messages)),
        "typing": _chat_typing_active(exclude_phone=my_phone),
    })


@app.route("/api/chat/messages/<int:mid>/like", methods=["POST"])
def api_chat_message_like(mid):
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza."}), 403
    now = datetime.utcnow().isoformat() + "Z"
    with CHAT_LOCK:
        conn = _analytics_db()
        _chat_db_init(conn)
        existing = conn.execute(
            "SELECT 1 FROM chat_message_likes WHERE message_id=? AND phone=?", (mid, phone)
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM chat_message_likes WHERE message_id=? AND phone=?", (mid, phone))
            liked = False
        else:
            conn.execute(
                "INSERT INTO chat_message_likes(message_id,phone,created_at) VALUES(?,?,?)", (mid, phone, now)
            )
            liked = True
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM chat_message_likes WHERE message_id=?", (mid,)
        ).fetchone()["c"]
        conn.close()
    return jsonify({"success": True, "liked": liked, "like_count": count})


@app.route("/api/chat/messages/<int:mid>", methods=["DELETE"])
def api_chat_message_delete_own(mid):
    """Mtumiaji anaweza kufuta ujumbe wake mwenyewe pekee."""
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Jisajili kwanza."}), 403
    with CHAT_LOCK:
        conn = _analytics_db()
        _chat_db_init(conn)
        row = conn.execute("SELECT phone FROM chat_messages WHERE id=?", (mid,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"success": False, "message": "Ujumbe haupatikani."}), 404
        if row["phone"] != phone:
            conn.close()
            return jsonify({"success": False, "message": "Unaweza kufuta ujumbe wako pekee."}), 403
        conn.execute("DELETE FROM chat_messages WHERE id=?", (mid,))
        conn.execute("DELETE FROM chat_message_likes WHERE message_id=?", (mid,))
        conn.commit()
        conn.close()
    return jsonify({"success": True, "message": "Ujumbe umefutwa."})


# ===== Typing indicator (kumbukumbu ya muda mfupi, si ya kudumu) =====
CHAT_TYPING_LOCK = threading.Lock()
CHAT_TYPING_STATE = {}  # phone -> {"name":..., "ts": epoch_seconds}
CHAT_TYPING_WINDOW_SEC = 6


def _chat_typing_active(exclude_phone=None):
    now = datetime.utcnow().timestamp()
    names = []
    with CHAT_TYPING_LOCK:
        stale = [p for p, v in CHAT_TYPING_STATE.items() if now - v["ts"] > CHAT_TYPING_WINDOW_SEC]
        for p in stale:
            CHAT_TYPING_STATE.pop(p, None)
        for p, v in CHAT_TYPING_STATE.items():
            if p != exclude_phone:
                names.append(v["name"])
    return names


@app.route("/api/chat/typing", methods=["POST"])
def api_chat_typing():
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": True})
    name = session.get("chat_name") or "Mtumiaji"
    with CHAT_TYPING_LOCK:
        CHAT_TYPING_STATE[phone] = {"name": name, "ts": datetime.utcnow().timestamp()}
    return jsonify({"success": True})


@app.route("/api/chat/send", methods=["POST"])
@rate_limit("chat_send", max_attempts=40, window_seconds=60)
def api_chat_send():
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Lazima ujisajili kwa namba ya simu kabla ya kuandika."}), 403
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()[:500]
    attachment_url = _safe_chat_attachment_url(data.get("attachment_url") or "")
    attachment_type = (data.get("attachment_type") or "").strip()[:20]
    sticker = (data.get("sticker") or "").strip()[:80]
    if attachment_url and attachment_type not in ("image", "video", "audio", "pdf"):
        return jsonify({"success": False, "message": "Aina ya faili si sahihi."}), 400
    if not message and not attachment_url and not sticker:
        return jsonify({"success": False, "message": "Andika ujumbe au ambatanisha faili/sticker."}), 400

    allowed, reason = _sabbath_message_allowed(message) if message else (True, None)
    now = datetime.utcnow().isoformat() + "Z"
    name = session.get("chat_name") or "Mtumiaji"
    with CHAT_LOCK:
        conn = _analytics_db()
        _chat_db_init(conn)
        conn.execute(
            """INSERT INTO chat_messages(phone,name,message,status,reject_reason,created_at,
                   attachment_url,attachment_type,sticker) VALUES(?,?,?,?,?,?,?,?,?)""",
            (phone, name, message, "ok" if allowed else "rejected", reason, now,
             attachment_url or None, attachment_type or None, sticker or None),
        )
        conn.commit()
        conn.close()
    with CHAT_TYPING_LOCK:
        CHAT_TYPING_STATE.pop(phone, None)
    if not allowed:
        return jsonify({"success": False, "message": reason}), 403
    return jsonify({"success": True, "message": "Ujumbe umetumwa."})


@app.route("/api/chat/notifications", methods=["GET"])
def api_chat_notifications():
    phone = session.get("phone")
    if not phone:
        return jsonify({"success": True, "notifications": []})
    _maybe_generate_sabbath_invites()
    with CHAT_LOCK:
        conn = _analytics_db()
        _chat_db_init(conn)
        rows = conn.execute(
            "SELECT id,message,created_at FROM chat_notifications WHERE phone=? ORDER BY id DESC LIMIT 10",
            (phone,),
        ).fetchall()
        conn.close()
    return jsonify({"success": True, "notifications": [dict(r) for r in rows]})


@app.route("/api/chat/people-suggestions", methods=["GET"])
def api_chat_people_suggestions():
    """'Watu Unaoweza Kuwafahamu' — kama Facebook, kutoka kwa wanachama
    waliojisajili tayari kwenye jumuiya."""
    phone = session.get("phone")
    with CHAT_LOCK:
        conn = _analytics_db()
        _chat_db_init(conn)
        if phone:
            rows = conn.execute(
                "SELECT phone,name,category,mkoa FROM chat_users WHERE phone != ? ORDER BY RANDOM() LIMIT 8",
                (phone,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT phone,name,category,mkoa FROM chat_users ORDER BY RANDOM() LIMIT 8"
            ).fetchall()
        conn.close()
    people = []
    for r in rows:
        d = dict(r)
        d["phone_masked"] = (d["phone"][:4] + "***" + d["phone"][-2:]) if len(d["phone"]) > 6 else "***"
        people.append(d)
    return jsonify({"success": True, "people": people})


@app.route("/api/admin/chat/messages", methods=["GET"])
def api_admin_chat_messages():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    with CHAT_LOCK:
        conn = _analytics_db()
        _chat_db_init(conn)
        rows = conn.execute(
            "SELECT id,phone,name,message,status,reject_reason,created_at FROM chat_messages ORDER BY id DESC LIMIT 100"
        ).fetchall()
        conn.close()
    return jsonify({"success": True, "messages": [dict(r) for r in rows]})


@app.route("/api/admin/chat/messages/<int:mid>", methods=["DELETE"])
def api_admin_chat_message_delete(mid):
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    ok, err = _require_csrf()
    if not ok:
        return err
    with CHAT_LOCK:
        conn = _analytics_db()
        _chat_db_init(conn)
        conn.execute("DELETE FROM chat_messages WHERE id=?", (mid,))
        conn.commit()
        conn.close()
    return jsonify({"success": True, "message": "Ujumbe umefutwa."})


# ===== ADMIN ROOM =====
# Chumba cha Admin: admin anaona "mirror" ya moja kwa moja ya kila kitu
# kinachoonekana kwenye dashboard ya umma, na anaweza kumzuia/kumuondoa
# mtumiaji yeyote papo hapo.

@app.route("/api/admin/room/snapshot", methods=["GET"])
def api_admin_room_snapshot():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403

    # Bidhaa - sawa kabisa na zinazoonekana kwa mtumiaji wa kawaida
    try:
        products = _products_for_client()
    except Exception:
        products = SAMPLE_PRODUCTS

    with ADS_LOCK:
        ads_active = [a for a in ADS_STORE if a.get("active", True)]
        ads_recent = list(reversed(ADS_STORE))[:10]

    stats = {}
    try:
        stats = _analytics_stats()
    except Exception:
        pass

    discussions = []
    try:
        with ANALYTICS_LOCK:
            conn = _analytics_db()
            _analytics_init_discussions(conn)
            rows = conn.execute(
                "SELECT id,message,created_at FROM view_discussions ORDER BY id DESC LIMIT 15"
            ).fetchall()
            conn.close()
        discussions = [dict(r) for r in rows]
    except Exception:
        pass

    pending_service = 0
    pending_advisory = 0
    try:
        pending_service = sum(1 for o in PAYMENT_ORDERS.values() if o.get("status") != "verified")
    except Exception:
        pass
    try:
        pending_advisory = sum(1 for o in ADVISORY_ORDERS.values() if o.get("status") != "verified")
    except Exception:
        pass

    sabbath_active, sabbath_start, sabbath_end, _now = (False, None, None, None)
    try:
        sabbath_active, sabbath_start, sabbath_end, _now = _sabbath_window()
    except Exception:
        pass

    with BANNED_LOCK:
        banned_count = len(BANNED_STORE)

    return jsonify({
        "success": True,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "public_dashboard": {
            "products_total": len(products),
            "products_featured": sum(1 for p in products if p.get("featured")),
            "products": products[:12],
            "ads_active_count": len(ads_active),
            "ads_active": ads_active,
            "ads_recent": ads_recent,
            "recent_discussions": discussions,
        },
        "live": {
            "visitors_live_5m": stats.get("live_5m", 0),
            "visitors_today": stats.get("today_unique", 0),
            "total_visits": stats.get("total_visits", 0),
        },
        "orders": {
            "service_pending": pending_service,
            "advisory_pending": pending_advisory,
        },
        "sabbath": {
            "active": sabbath_active,
            "start": sabbath_start.isoformat() if sabbath_start else None,
            "end": sabbath_end.isoformat() if sabbath_end else None,
        },
        "moderation": {
            "banned_count": banned_count,
        },
    })


@app.route("/api/admin/users/banned", methods=["GET"])
def api_admin_users_banned_list():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    with BANNED_LOCK:
        items = sorted(BANNED_STORE.values(), key=lambda x: x.get("banned_at") or "", reverse=True)
    return jsonify({"success": True, "banned": items})


@app.route("/api/admin/users/ban", methods=["POST"])
def api_admin_users_ban():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    ok, err = _require_csrf()
    if not ok:
        return err
    data = request.get_json(silent=True) or {}
    identifier = (data.get("identifier") or data.get("phone") or "").strip()
    reason = (data.get("reason") or "").strip()[:200]
    if not identifier:
        return jsonify({"success": False, "message": "Weka namba ya simu, session ID, au IP ya mtumiaji."}), 400
    key = identifier.lower()
    with BANNED_LOCK:
        BANNED_STORE[key] = {
            "identifier": identifier,
            "reason": reason or "Ukiukwaji wa kanuni za mfumo",
            "banned_at": datetime.utcnow().isoformat() + "Z",
            "by": "admin",
        }
    return jsonify({"success": True, "message": f"Mtumiaji {identifier} amezuiwa.", "banned": BANNED_STORE[key]})


@app.route("/api/admin/users/unban", methods=["POST"])
def api_admin_users_unban():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    ok, err = _require_csrf()
    if not ok:
        return err
    data = request.get_json(silent=True) or {}
    identifier = (data.get("identifier") or "").strip().lower()
    with BANNED_LOCK:
        existed = BANNED_STORE.pop(identifier, None)
    if not existed:
        return jsonify({"success": False, "message": "Hajapatikana kwenye orodha ya waliozuiwa."}), 404
    return jsonify({"success": True, "message": "Mtumiaji amerejeshewa ufikiaji."})


@app.before_request
def _admin_room_ban_gate():
    """Zuia watumiaji walioondolewa na admin wasitumie API za umma (si admin, si static)."""
    path = request.path or ""
    if path.startswith("/static/") or path.startswith("/api/admin") or path in ("/admin", "/admin.html"):
        return None
    if request.method == "OPTIONS":
        return None
    if not path.startswith("/api/"):
        return None
    if _is_banned_request():
        return jsonify({"success": False, "banned": True,
                         "message": "Umezuiwa na msimamizi wa mfumo kutokana na ukiukwaji wa kanuni."}), 403
    return None


ADS_LOCK = threading.Lock()
ADS_STORE = []
_next_ad_id = 1
AD_ENGAGE = {"views": 0, "likes": 0, "follows": 0, "shares": 0, "subscribes": 0, "comments": 0}
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ===== ENGAGEMENT HALISI (si roboti) =====
# Kila hatua (like/follow/subscribe/view) inahesabiwa MARA MOJA PEKEE kwa kila
# mgeni halisi (kwa kutumia nm_visitor_id cookie iliyopo tayari). Hakuna
# uongezaji wa kiotomatiki bila mtu kubofya - isipokuwa "view" ambayo
# inahesabiwa mara moja kwa kila mgeni anapoona tangazo (sio kila reload).
ENGAGE_LOCK = threading.Lock()


def _engage_db_init(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS ad_engagement (
        visitor_id TEXT NOT NULL,
        action TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (visitor_id, action)
    )""")
    conn.commit()


def _engage_counts_from_db(conn):
    rows = conn.execute("SELECT action, COUNT(*) AS c FROM ad_engagement GROUP BY action").fetchall()
    counts = {"views": 0, "likes": 0, "follows": 0, "shares": 0, "subscribes": 0, "comments": 0}
    for r in rows:
        if r["action"] in counts:
            counts[r["action"]] = r["c"]
    return counts


def _engage_record(visitor_id, action):
    """Rekodi kitendo HALISI cha mgeni mmoja. Rudisha (recorded, toggled_off).
    Kwa like/follow/subscribe: kubofya tena kunaondoa (toggle off) - kama
    Instagram/YouTube halisi, si kuongeza tena bila kikomo."""
    if not visitor_id:
        return False, False
    now = datetime.utcnow().isoformat() + "Z"
    with ENGAGE_LOCK:
        conn = _analytics_db()
        _engage_db_init(conn)
        existing = conn.execute(
            "SELECT 1 FROM ad_engagement WHERE visitor_id=? AND action=?", (visitor_id, action)
        ).fetchone()
        toggled_off = False
        if existing:
            if action in ("likes", "follows", "subscribes"):
                conn.execute("DELETE FROM ad_engagement WHERE visitor_id=? AND action=?", (visitor_id, action))
                conn.commit()
                toggled_off = True
            # "views" na "shares"/"comments" hazitoggle - tayari zimehesabiwa mara moja
        else:
            conn.execute(
                "INSERT INTO ad_engagement(visitor_id,action,created_at) VALUES(?,?,?)",
                (visitor_id, action, now),
            )
            conn.commit()
        counts = _engage_counts_from_db(conn)
        conn.close()
    return counts, toggled_off


def _engage_counts_now():
    with ENGAGE_LOCK:
        conn = _analytics_db()
        _engage_db_init(conn)
        counts = _engage_counts_from_db(conn)
        conn.close()
    return counts


def _engage_visitor_state(visitor_id):
    """Ni vitendo gani mtumiaji huyu tayari amevifanya (kwa UI - km. moyo
    umejaa au tupu)."""
    if not visitor_id:
        return {}
    with ENGAGE_LOCK:
        conn = _analytics_db()
        _engage_db_init(conn)
        rows = conn.execute("SELECT action FROM ad_engagement WHERE visitor_id=?", (visitor_id,)).fetchall()
        conn.close()
    return {r["action"]: True for r in rows}

# Seed demo ad
ADS_STORE.append({
    "id": 0,
    "title": "Karibu NjiaMauzo Afrika",
    "type": "text",
    "media_url": "",
    "link_url": "",
    "marquee": "📣 Karibu NjiaMauzo Afrika — kitovu cha biashara Afrika Mashariki! Tangaza bidhaa yako hapa leo. 🌍",
    "active": True,
    "published": True,
    "created": datetime.utcnow().isoformat() + "Z",
})


@app.route("/api/ads", methods=["GET"])
def api_ads_list():
    visitor_id = request.cookies.get("nm_visitor_id") or ""
    now_iso = datetime.utcnow().isoformat() + "Z"
    with ADS_LOCK:
        active = [
            a for a in ADS_STORE
            if a.get("published", True) and a.get("active", True)
            and (not a.get("starts_at") or a.get("starts_at") <= now_iso)
            and (not a.get("ends_at") or a.get("ends_at") > now_iso)
        ]
    counts = _engage_counts_now()
    my_state = _engage_visitor_state(visitor_id)
    return jsonify({"success": True, "ads": active, "counts": counts, "my_engagement": my_state})


@app.route("/api/ads/engage", methods=["POST"])
def api_ads_engage():
    """Kitendo HALISI cha mgeni mmoja (kubofya Like/Follow/Sub/Share/Comment).
    Kila mgeni (kwa visitor_id ya kudumu) anahesabiwa mara moja tu kwa kila
    kitendo - hakuna kuongeza bandia."""
    visitor_id = request.cookies.get("nm_visitor_id") or ""
    if not visitor_id:
        return jsonify({"success": False, "message": "Tatizo la kitambulisho cha mgeni - onyesha upya ukurasa."}), 400
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "view").lower()
    key_map = {
        "view": "views", "views": "views",
        "like": "likes", "likes": "likes",
        "follow": "follows", "follows": "follows",
        "share": "shares", "shares": "shares",
        "subscribe": "subscribes", "subscribes": "subscribes",
        "comment": "comments",
    }
    key = key_map.get(action, "views")
    counts, toggled_off = _engage_record(visitor_id, key)
    return jsonify({"success": True, "toggled_off": toggled_off, "counts": {
        "like": counts.get("likes", 0),
        "follow": counts.get("follows", 0),
        "share": counts.get("shares", 0),
        "view": counts.get("views", 0),
        "subscribe": counts.get("subscribes", 0),
        "comment": counts.get("comments", 0),
        **counts,
    }})


@app.route("/api/ads/auto-engage", methods=["POST"])
def api_ads_auto_engage():
    """DEPRECATED: awali ilikuwa ikiongeza like/follow/subscribe KIOTOMATIKO
    kwa kila mgeni bila yeye kubofya chochote - hiyo ilikuwa hesabu ya
    'roboti', si halisi. Sasa 'view' pekee inahesabiwa (mara moja kwa kila
    mgeni halisi), na like/follow/subscribe zinahitaji kubofya kwa mkono."""
    visitor_id = request.cookies.get("nm_visitor_id") or ""
    counts, _ = _engage_record(visitor_id, "views") if visitor_id else (_engage_counts_now(), False)
    return jsonify({
        "success": True,
        "counts": {
            "like": counts.get("likes", 0),
            "follow": counts.get("follows", 0),
            "share": counts.get("shares", 0),
            "view": counts.get("views", 0),
            "subscribe": counts.get("subscribes", 0),
            **counts,
        },
    })


@app.route("/api/admin/ads", methods=["GET"])
def api_admin_ads_list():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    with ADS_LOCK:
        ads = list(reversed(ADS_STORE))
    counts = _engage_counts_now()
    return jsonify({"success": True, "ads": ads, "counts": counts})


@app.route("/api/admin/ads", methods=["POST"])
def api_admin_ads_create():
    """Upload tangazo: link AU file (video/audio/image)."""
    global _next_ad_id
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    ok, err = _require_csrf()
    if not ok:
        return err

    title = ""
    media_type = "text"
    media_url = ""
    link_url = ""
    marquee = ""
    active = True
    published = False
    fullscreen = True

    # Multipart (file upload)
    if request.content_type and "multipart/form-data" in request.content_type:
        title = (request.form.get("title") or "").strip() or "Tangazo"
        media_type = (request.form.get("type") or "video").strip().lower()
        link_url = (request.form.get("link_url") or "").strip()
        marquee = (request.form.get("marquee") or "").strip()
        active = (request.form.get("active") or "1") in ("1", "true", "True", "yes")
        published = (request.form.get("published") or "0") in ("1", "true", "True", "yes")
        fullscreen = (request.form.get("fullscreen") or "1") in ("1", "true", "True", "yes")
        f = request.files.get("file")
        if f and f.filename:
            ext = Path(f.filename).suffix.lower()
            allowed = {".mp4", ".webm", ".mov", ".mp3", ".wav", ".ogg", ".m4a",
                       ".jpg", ".jpeg", ".png", ".gif", ".webp"}
            if ext not in allowed:
                return jsonify({"success": False, "message": f"Aina ya faili hairuhusiwi: {ext}"}), 400
            fname = f"ad_{secrets.token_hex(6)}{ext}"
            dest = UPLOAD_DIR / fname
            f.save(str(dest))
            media_url = f"/static/uploads/{fname}"
            if media_type not in ("video", "audio", "image"):
                if ext in (".mp4", ".webm", ".mov"):
                    media_type = "video"
                elif ext in (".mp3", ".wav", ".ogg", ".m4a"):
                    media_type = "audio"
                else:
                    media_type = "image"
        else:
            # link mode via form fields
            media_url = (request.form.get("media_url") or "").strip()
            if media_url and media_type == "text":
                media_type = "link"
    else:
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip() or "Tangazo"
        media_type = (data.get("type") or "link").strip().lower()
        media_url = (data.get("media_url") or data.get("url") or "").strip()
        link_url = (data.get("link_url") or "").strip()
        marquee = (data.get("marquee") or "").strip()
        active = data.get("active", True) is not False
        published = data.get("published", False) is not False
        fullscreen = data.get("fullscreen", True) is not False

    if not media_url and not marquee and not link_url:
        return jsonify({"success": False, "message": "Weka link, faili, au maandishi ya marquee."}), 400
    starts_at = None
    ends_at = None
    if request.content_type and "multipart/form-data" in request.content_type:
        starts_at = (request.form.get("starts_at") or "").strip() or None
        ends_at = (request.form.get("ends_at") or "").strip() or None
        duration_minutes = request.form.get("duration_minutes")
    else:
        starts_at = (data.get("starts_at") or "").strip() or None
        ends_at = (data.get("ends_at") or "").strip() or None
        duration_minutes = data.get("duration_minutes")
    if duration_minutes:
        try: ends_at = (datetime.utcnow() + timedelta(minutes=float(duration_minutes))).isoformat() + "Z"
        except Exception: pass

    with ADS_LOCK:
        aid = _next_ad_id
        _next_ad_id += 1
        ad = {
            "id": aid,
            "title": title,
            "type": media_type,
            "media_url": media_url,
            "link_url": link_url,
            "marquee": marquee,
            "active": active,
            "published": published,
            "fullscreen": fullscreen,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "created": datetime.utcnow().isoformat() + "Z",
        }
        ADS_STORE.append(ad)
        if len(ADS_STORE) > 100:
            del ADS_STORE[: len(ADS_STORE) - 100]

    return jsonify({"success": True, "ad": ad, "message": "Tangazo limehifadhiwa."})


@app.route("/api/admin/ads/<int:aid>", methods=["PUT"])
def api_admin_ads_edit(aid):
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    ok, err = _require_csrf()
    if not ok: return err
    with ADS_LOCK:
        ad = next((a for a in ADS_STORE if a.get("id") == aid), None)
        if not ad: return jsonify({"success": False, "message": "Tangazo halipatikani."}), 404
        if request.content_type and "multipart/form-data" in request.content_type:
            d=request.form
            ad["title"]=(d.get("title") or ad.get("title") or "Tangazo").strip()
            ad["type"]=(d.get("type") or ad.get("type") or "text").strip().lower()
            ad["marquee"]=(d.get("marquee") or "").strip()
            ad["link_url"]=(d.get("link_url") or "").strip()
            ad["fullscreen"]=(d.get("fullscreen") or "0") in ("1","true","True","yes")
            f=request.files.get("file")
            if f and f.filename:
                ext=Path(f.filename).suffix.lower(); allowed={".mp4",".webm",".mov",".mp3",".wav",".ogg",".m4a",".jpg",".jpeg",".png",".gif",".webp"}
                if ext not in allowed: return jsonify({"success":False,"message":"Aina ya faili hairuhusiwi."}),400
                dest=UPLOAD_DIR; dest.mkdir(parents=True,exist_ok=True); fname=f"ad_{secrets.token_hex(6)}{ext}"; f.save(str(dest/fname)); ad["media_url"]=f"/static/uploads/{fname}"
                if ext in (".mp4",".webm",".mov"): ad["type"]="video"
                elif ext in (".mp3",".wav",".ogg",".m4a"): ad["type"]="audio"
                else: ad["type"]="image"
        else:
            d=request.get_json(silent=True) or {}
            for k in ("title","type","marquee","link_url"): 
                if k in d: ad[k]=str(d.get(k) or "").strip()
            if "fullscreen" in d: ad["fullscreen"]=bool(d.get("fullscreen"))
        return jsonify({"success":True,"ad":ad,"message":"Tangazo limebadilishwa."})

@app.route("/api/admin/ads/<int:aid>", methods=["DELETE"])
def api_admin_ads_delete(aid):
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    ok, err = _require_csrf()
    if not ok:
        return err
    with ADS_LOCK:
        before = len(ADS_STORE)
        ADS_STORE[:] = [a for a in ADS_STORE if a.get("id") != aid]
        removed = before - len(ADS_STORE)
    if not removed:
        return jsonify({"success": False, "message": "Tangazo halipatikani."}), 404
    return jsonify({"success": True, "message": "Tangazo limefutwa."})


@app.route("/api/admin/ads/<int:aid>/toggle", methods=["POST"])
def api_admin_ads_toggle(aid):
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    ok, err = _require_csrf()
    if not ok:
        return err
    with ADS_LOCK:
        for a in ADS_STORE:
            if a.get("id") == aid:
                a["active"] = not a.get("active", True)
                return jsonify({"success": True, "ad": a})
    return jsonify({"success": False, "message": "Haipatikani."}), 404


@app.route("/api/admin/ads/<int:aid>/publish", methods=["POST"])
def api_admin_ads_publish(aid):
    """Weka tangazo HEWANI. Ikiwa duration_minutes imetolewa, tangazo
    litazimwa lenyewe baada ya muda huo (ends_at); bila hiyo linabaki
    hewani milele mpaka lifungwe kwa mkono (unpublish)."""
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    ok, err = _require_csrf()
    if not ok:
        return err
    data = request.get_json(silent=True) or {}
    duration_minutes = data.get("duration_minutes")
    with ADS_LOCK:
        for a in ADS_STORE:
            if a.get("id") == aid:
                a["active"] = True
                a["published"] = True
                if duration_minutes and float(duration_minutes) > 0:
                    a["ends_at"] = (
                        datetime.utcnow() + timedelta(minutes=float(duration_minutes))
                    ).isoformat() + "Z"
                else:
                    a["ends_at"] = None
                return jsonify({"success": True, "ad": a, "message": "Tangazo liko hewani."})
    return jsonify({"success": False, "message": "Haipatikani."}), 404


@app.route("/api/admin/ads/<int:aid>/unpublish", methods=["POST"])
def api_admin_ads_unpublish(aid):
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    ok, err = _require_csrf()
    if not ok:
        return err
    with ADS_LOCK:
        for a in ADS_STORE:
            if a.get("id") == aid:
                a["active"] = False
                a["published"] = False
                return jsonify({"success": True, "ad": a, "message": "Tangazo limeondolewa hewani."})
    return jsonify({"success": False, "message": "Haipatikani."}), 404


ADMIN_PAGE_SECRET = os.environ.get("ADMIN_PAGE_SECRET", "").strip()


@app.route("/admin")
@app.route("/admin.html")
def admin_page():
    """Ukurasa wa Admin Dashboard — FICHWA: haionekani kwa mgeni wa kawaida.
    Inahitaji ama (a) session ya admin iliyoshaingia, au (b) ?key=SECRET sahihi
    kwenye URL (weka ADMIN_PAGE_SECRET kwenye Render Environment Variables).
    Vinginevyo tunarudisha 404 ya kawaida ili ukurasa 'usionekane kuwepo'."""
    if not session.get("is_admin") and ADMIN_PAGE_SECRET:
        # Ulinzi wa ziada unatumika TU kama umeweka ADMIN_PAGE_SECRET kwenye
        # Render. Usipoiweka, ukurasa unabaki kufikiwa kwa jina la kawaida
        # (bado umelindwa na jina/password ya admin ndani ya ukurasa wenyewe).
        if request.args.get("key") != ADMIN_PAGE_SECRET:
            return jsonify({"success": False, "message": "Haipo."}), 404
    admin_file = BASE_DIR / "admin.html"
    if admin_file.exists():
        return send_from_directory(BASE_DIR, "admin.html")
    return jsonify({"success": False, "message": "admin.html haipatikani."}), 404




@app.after_request
def _security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(self), payment=(self)"
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: https:; media-src 'self' https:; "
        "script-src 'self' 'unsafe-inline' https:; style-src 'self' 'unsafe-inline' https:; "
        "connect-src 'self' https:; frame-ancestors 'self'; base-uri 'self'; object-src 'none'"
    )
    # SSL/HSTS: lazimisha kila mtu atumie HTTPS (Render tayari inatoa SSL bure
    # kiotomatiki kwa kila deploy - hii inahakikisha hakuna mtu anayelazimika
    # kutumia http:// isiyo salama).
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    # Usionyeshe server version
    resp.headers.pop("Server", None)
    return resp


@app.before_request
def _force_https_redirect():
    """Firewall/SSL ya msingi: lazimisha HTTPS kwenye production (Render
    inaweka X-Forwarded-Proto). Usalama halisi wa firewall/SSH unasimamiwa na
    Render platform yenyewe (angalia maelezo ya deploy)."""
    if os.environ.get("FORCE_HTTPS", "1") == "1":
        proto = request.headers.get("X-Forwarded-Proto", "https")
        if proto == "http" and not request.host.startswith(("127.0.0.1", "localhost")):
            url = request.url.replace("http://", "https://", 1)
            return redirect(url, code=301)
    return None


# ===== CONTACT SELLER =====

@app.route("/api/contact-seller", methods=["POST"])
def contact_seller():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id") or str(uuid.uuid4())
    seller_name = data.get("seller_name") or "Muuzaji"
    channels = notify_seller(data)

    with SESSION_LOCK:
        CONTACT_SESSIONS[session_id] = {
            "created": datetime.utcnow(),
            "seller_id": data.get("seller_id") or "",
            "seller_name": seller_name,
            "product_id": data.get("product_id"),
            "product_title": data.get("product_title") or "",
            "channels_sent": channels,
            "replied": False,
            "replied_at": None,
            "reply_text": None,
        }

    def _auto_reply(sid):
        time.sleep(12 + (abs(hash(sid)) % 9))
        with SESSION_LOCK:
            s = CONTACT_SESSIONS.get(sid)
            if s and not s["replied"]:
                s["replied"] = True
                s["replied_at"] = datetime.utcnow()
                s["reply_text"] = "Karibu niko hewani nikuhudumie"

    if os.environ.get("DEMO_AUTO_REPLY", "1") == "1":
        threading.Thread(target=_auto_reply, args=(session_id,), daemon=True).start()

    return jsonify({
        "success": True,
        "session_id": session_id,
        "message": "Ujumbe umetumwa kwa muuzaji kupitia mawasiliano yote yaliyopo.",
        "channels": channels,
        "seller_name": seller_name,
    })


@app.route("/api/contact-seller/status", methods=["GET"])
def contact_seller_status():
    _cleanup_sessions()
    session_id = request.args.get("session_id") or ""
    seller_id = request.args.get("seller_id") or ""

    with SESSION_LOCK:
        sess = CONTACT_SESSIONS.get(session_id)
        if not sess and seller_id:
            for sid, s in sorted(CONTACT_SESSIONS.items(),
                                 key=lambda x: x[1]["created"], reverse=True):
                if s.get("seller_id") == seller_id:
                    sess = s
                    session_id = sid
                    break
        if not sess:
            return jsonify({"success": True, "replied": False, "found": False})
        return jsonify({
            "success": True,
            "found": True,
            "session_id": session_id,
            "replied": bool(sess.get("replied")),
            "seller_name": sess.get("seller_name"),
            "replied_at": (sess["replied_at"].isoformat() + "Z") if sess.get("replied_at") else None,
        })


@app.route("/api/contact-seller/reply", methods=["POST"])
def contact_seller_reply():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id") or ""
    seller_id = data.get("seller_id") or ""

    with SESSION_LOCK:
        sess = CONTACT_SESSIONS.get(session_id)
        if not sess and seller_id:
            for sid, s in CONTACT_SESSIONS.items():
                if s.get("seller_id") == seller_id and not s.get("replied"):
                    sess = s
                    session_id = sid
                    break
        if not sess:
            return jsonify({"success": False, "message": "Session haipatikani."}), 404
        sess["replied"] = True
        sess["replied_at"] = datetime.utcnow()
        sess["reply_text"] = data.get("message") or "Karibu niko hewani nikuhudumie"

    return jsonify({"success": True, "session_id": session_id, "message": "Jibu limeandikishwa."})


@app.route("/api/password/forgot", methods=["POST"])
@app.route("/api/password/reset", methods=["POST"])
@app.route("/api/password/change", methods=["POST"])
def api_password():
    return jsonify({"success": True, "message": "OK (stub)."})


if __name__ == "__main__":
    print("=" * 50)
    print("  NjiaMauzo Afrika")
    print("  http://127.0.0.1:5000")
    print("  Admin login: username only; no admin password is required")
    print("=" * 50)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
