# ============================================================
# NJIA MAUZO AFRIKA — Secure Production Flask Backend
# ============================================================
# Features:
# - SQLite by default / PostgreSQL via DATABASE_URL
# - Registration / Login / Logout
# - PBKDF2 password hashing
# - Secure session cookies + CSRF protection
# - Optional Cloudflare Turnstile CAPTCHA
# - Admin first-login password change (default 0000)
# - Forgot password OTP via SMTP email / WhatsApp API / SMS webhook
# - Change password
# - Products, likes, comments, follows
# - Live activity feed
# - Browser geolocation + distance sorting
# - AI product finder + 24/7 bot
# - Assisted search fee TZS 3,000
# - Payment number API (numbers are NOT hardcoded in HTML)
# - Admin WhatsApp notification
# - Basic security headers + rate limiting
#
# Render:
# Build: pip install -r requirements.txt
# Start: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
# ============================================================

import os
import re
import json
import math
import time
import uuid
import random
import threading
import hmac
import secrets
import hashlib
import sqlite3
import smtplib
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from urllib.parse import urlparse

import requests
from flask import Flask, render_template, request, jsonify, session, g
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash


# ---------------- APP CONFIG ----------------
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "1") != "0",
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    MAX_CONTENT_LENGTH=1_000_000,
)

# Same-origin frontend is preferred. CORS is kept for compatible API clients.
CORS(app, supports_credentials=True)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
ASSISTED_SEARCH_FEE = 3000

PAYMENT_MPESA = os.environ.get("PAYMENT_MPESA", "0755248789")
PAYMENT_HALOTEL = os.environ.get("PAYMENT_HALOTEL", "0625031460")
PAYMENT_AIRTEL = os.environ.get("PAYMENT_AIRTEL", "0691925100")
ADMIN_WHATSAPP_NUMBER = os.environ.get("ADMIN_WHATSAPP_NUMBER", "255755248789")

TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")

# OTP providers are optional. Configure one or more in Render.
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)

WHATSAPP_API_URL = os.environ.get("WHATSAPP_API_URL", "")
WHATSAPP_API_TOKEN = os.environ.get("WHATSAPP_API_TOKEN", "")
SMS_API_URL = os.environ.get("SMS_API_URL", "")
SMS_API_TOKEN = os.environ.get("SMS_API_TOKEN", "")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
LIVE_SEARCH_MIN_SECONDS = int(os.environ.get("LIVE_SEARCH_MIN_SECONDS", "45"))
LIVE_SEARCH_MAX_SECONDS = int(os.environ.get("LIVE_SEARCH_MAX_SECONDS", "120"))
PAYMENT_WEBHOOK_SECRET = os.environ.get("PAYMENT_WEBHOOK_SECRET", "")
LIVE_SEARCH_ENABLED = os.environ.get("LIVE_SEARCH_ENABLED", "1") == "1"

PBKDF2_METHOD = "pbkdf2:sha256:600000"

# ---------------- HARDENING ----------------
@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    response.headers["Content-Security-Policy"] = ("default-src 'self' https: data:; "
        "img-src 'self' https: data:; style-src 'self' 'unsafe-inline' https:; "
        "script-src 'self' 'unsafe-inline' https:; connect-src 'self' https:; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@app.errorhandler(413)
def too_large(_):
    return json_error("Ombi ni kubwa sana.", 413)

# ---------------- DB ----------------
def is_postgres():
    return DATABASE_URL.startswith(("postgres://", "postgresql://"))

def db():
    if "db" not in g:
        if is_postgres():
            # PostgreSQL support via psycopg2-binary.
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            g.db = conn
            g.db_cursor_factory = RealDictCursor
        else:
            path = os.environ.get("SQLITE_PATH", "/tmp/njiamauzo.sqlite3")
            # On Render, /tmp is ephemeral. Set SQLITE_PATH to a persistent disk
            # path or use PostgreSQL for production persistence.
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            g.db = conn
            g.db_cursor_factory = None
    return g.db

def q(sql, params=(), one=False, many=False):
    conn = db()
    if is_postgres():
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        if sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            conn.commit()
        if one:
            row = cur.fetchone()
        elif many:
            row = cur.fetchall()
        else:
            row = None
        cur.close()
        return row
    else:
        cur = conn.execute(sql, params)
        if sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            conn.commit()
        if one:
            return cur.fetchone()
        if many:
            return cur.fetchall()
        return None

@app.teardown_appcontext
def close_db(exception=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    conn = db()
    if is_postgres():
        statements = [
            """CREATE TABLE IF NOT EXISTS users(
                id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
                name TEXT NOT NULL, phone TEXT, is_admin INTEGER DEFAULT 0,
                must_change_password INTEGER DEFAULT 0, created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS products(
                id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT,
                price REAL NOT NULL, image TEXT, seller_name TEXT NOT NULL,
                location TEXT, category TEXT, latitude REAL, longitude REAL,
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS likes(
                user_id TEXT NOT NULL, product_id TEXT NOT NULL,
                created_at TEXT NOT NULL, PRIMARY KEY(user_id, product_id)
            )""",
            """CREATE TABLE IF NOT EXISTS comments(
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, product_id TEXT NOT NULL,
                text TEXT NOT NULL, created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS follows(
                follower_id TEXT NOT NULL, following_id TEXT NOT NULL,
                created_at TEXT NOT NULL, PRIMARY KEY(follower_id, following_id)
            )""",
            """CREATE TABLE IF NOT EXISTS activities(
                id TEXT PRIMARY KEY, actor_id TEXT, action TEXT NOT NULL,
                product_id TEXT, message TEXT NOT NULL, created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS orders(
                id TEXT PRIMARY KEY, user_id TEXT, phone TEXT NOT NULL,
                method TEXT NOT NULL, amount REAL NOT NULL, product_id TEXT,
                status TEXT NOT NULL, created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS otp_codes(
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, purpose TEXT NOT NULL,
                code_hash TEXT NOT NULL, expires_at TEXT NOT NULL,
                attempts INTEGER DEFAULT 0, used INTEGER DEFAULT 0, created_at TEXT NOT NULL
            )""",
        ]
    else:
        statements = [
            """CREATE TABLE IF NOT EXISTS users(
                id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
                name TEXT NOT NULL, phone TEXT, is_admin INTEGER DEFAULT 0,
                must_change_password INTEGER DEFAULT 0, created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS products(
                id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT,
                price REAL NOT NULL, image TEXT, seller_name TEXT NOT NULL,
                location TEXT, category TEXT, latitude REAL, longitude REAL,
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS likes(
                user_id TEXT NOT NULL, product_id TEXT NOT NULL,
                created_at TEXT NOT NULL, PRIMARY KEY(user_id, product_id)
            )""",
            """CREATE TABLE IF NOT EXISTS comments(
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, product_id TEXT NOT NULL,
                text TEXT NOT NULL, created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS follows(
                follower_id TEXT NOT NULL, following_id TEXT NOT NULL,
                created_at TEXT NOT NULL, PRIMARY KEY(follower_id, following_id)
            )""",
            """CREATE TABLE IF NOT EXISTS activities(
                id TEXT PRIMARY KEY, actor_id TEXT, action TEXT NOT NULL,
                product_id TEXT, message TEXT NOT NULL, created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS orders(
                id TEXT PRIMARY KEY, user_id TEXT, phone TEXT NOT NULL,
                method TEXT NOT NULL, amount REAL NOT NULL, product_id TEXT,
                status TEXT NOT NULL, created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS otp_codes(
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, purpose TEXT NOT NULL,
                code_hash TEXT NOT NULL, expires_at TEXT NOT NULL,
                attempts INTEGER DEFAULT 0, used INTEGER DEFAULT 0, created_at TEXT NOT NULL
            )""",
        ]
    for statement in statements:
        conn.execute(statement)
    conn.execute("""CREATE TABLE IF NOT EXISTS assisted_search_jobs(
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, order_id TEXT NOT NULL,
        query TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'QUEUED',
        last_run_at TEXT, next_run_at TEXT, created_at TEXT NOT NULL,
        UNIQUE(order_id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS assisted_search_results(
        id TEXT PRIMARY KEY, job_id TEXT NOT NULL, product_id TEXT,
        title TEXT NOT NULL, price REAL, location TEXT, seller_name TEXT,
        description TEXT, source TEXT, score REAL DEFAULT 0, created_at TEXT NOT NULL,
        UNIQUE(job_id, product_id)
    )""")
    conn.commit()

    # Seed admin. Password is deliberately the temporary default requested.
    admin = q("SELECT id FROM users WHERE email=?", (os.environ.get("ADMIN_EMAIL", "admin@njiamauzo.africa"),), one=True)
    if not admin:
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@njiamauzo.africa").lower()
        now = datetime.utcnow().isoformat()
        q("""INSERT INTO users(id,email,password,name,phone,is_admin,must_change_password,created_at)
             VALUES(?,?,?,?,?,?,?,?)""",
          (str(uuid.uuid4()), admin_email, generate_password_hash("0000", method=PBKDF2_METHOD),
           "NjiaMauzo Admin", "", 1, 1, now))

    count = q("SELECT COUNT(*) AS n FROM products", one=True)
    n = count["n"] if count else 0
    if int(n) == 0:
        products = [
            ("Mahindi ya Ubora — Tani 50", "Mahindi yaliyovunwa hivi karibuni.", 850000,
             "https://images.unsplash.com/photo-1625246333195-78d9c38ad449?w=800",
             "Juma Mkulima", "Morogoro, Mvomero", "mazao", -6.8, 37.66),
            ("Kahawa Arabica — Grade AA", "Kahawa bora ya Kilimanjaro.", 1200000,
             "https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=800",
             "Kilimanjaro Coffee Co-op", "Moshi, Kilimanjaro", "mazao", -3.34, 37.34),
            ("Huduma ya Usafirishaji wa Mazao", "Usafirishaji kutoka shambani hadi sokoni.", 350000,
             "https://images.unsplash.com/photo-1601584115197-04ecc0da31d7?w=800",
             "Safari Mazao Ltd", "Dar es Salaam", "huduma", -6.79, 39.21),
            ("Trekta ya Kukodi", "Trekta kwa kazi za shamba.", 250000,
             "https://images.unsplash.com/photo-1530267981375-f0de937f5f13?w=800",
             "Vifaa vya Kilimo TZ", "Dodoma", "vifaa", -6.16, 35.75),
            ("Nyanya za Chafu — Tani 20", "Nyanya safi za chafu.", 480000,
             "https://images.unsplash.com/photo-1546094096-0df4bcaaa337?w=800",
             "Green House Farm", "Iringa", "mazao", -7.77, 35.69),
        ]
        for p in products:
            q("""INSERT INTO products(id,title,description,price,image,seller_name,location,category,latitude,longitude,created_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
              (str(uuid.uuid4()), *p, datetime.utcnow().isoformat()))


# ---------------- HELPERS ----------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def clean(value, limit=500):
    value = str(value or "").strip()
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
    return value[:limit]

def json_error(message, code=400):
    return jsonify(success=False, message=message), code

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return q("SELECT * FROM users WHERE id=?", (uid,), one=True)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return json_error("Ingia kwanza.", 401)
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        u = current_user()
        if not u or not int(u["is_admin"]):
            return json_error("Huna ruhusa ya admin.", 403)
        return fn(*args, **kwargs)
    return wrapper

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]

def verify_csrf():
    token = request.headers.get("X-CSRF-Token") or (request.get_json(silent=True) or {}).get("csrf")
    expected = session.get("csrf", "")
    return bool(token and expected and hmac.compare_digest(str(token), str(expected)))

def protected(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not verify_csrf():
            return json_error("CSRF token si sahihi.", 403)
        return fn(*args, **kwargs)
    return wrapper

_RATE = {}
def rate_limit(key, max_calls=30, window=60):
    now = time.time()
    bucket = _RATE.setdefault(key, [])
    _RATE[key] = [t for t in bucket if now - t < window]
    if len(_RATE[key]) >= max_calls:
        return False
    _RATE[key].append(now)
    return True

def rate_limited(name, max_calls=30, window=60):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = f"{name}:{request.remote_addr or 'unknown'}"
            if not rate_limit(key, max_calls, window):
                return json_error("Umefikia kikomo cha maombi. Jaribu tena baadaye.", 429)
            return fn(*args, **kwargs)
        return wrapper
    return deco

def verify_turnstile(token):
    if not TURNSTILE_SECRET_KEY:
        return True  # Optional during development; configure it in production.
    if not token:
        return False
    try:
        r = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": TURNSTILE_SECRET_KEY, "response": token,
                  "remoteip": request.remote_addr},
            timeout=5,
        )
        return bool(r.ok and r.json().get("success"))
    except requests.RequestException:
        return False

def product_json(p, user_id=None, lat=None, lon=None):
    likes = q("SELECT COUNT(*) AS n FROM likes WHERE product_id=?", (p["id"],), one=True)
    liked = False
    if user_id:
        liked = bool(q("SELECT 1 FROM likes WHERE product_id=? AND user_id=?",
                       (p["id"], user_id), one=True))
    distance = None
    if lat is not None and lon is not None and p["latitude"] is not None and p["longitude"] is not None:
        distance = haversine(float(lat), float(lon), float(p["latitude"]), float(p["longitude"]))
    return {
        "id": p["id"], "title": p["title"], "description": p["description"],
        "price": float(p["price"]), "image": p["image"], "seller_name": p["seller_name"],
        "location": p["location"], "category": p["category"], "latitude": p["latitude"],
        "longitude": p["longitude"], "likes": int(likes["n"]), "liked": liked,
        "distance_km": round(distance, 2) if distance is not None else None,
        "created_at": p["created_at"],
    }

def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(a))

def add_activity(actor_id, action, message, product_id=None):
    q("""INSERT INTO activities(id,actor_id,action,product_id,message,created_at)
         VALUES(?,?,?,?,?,?)""",
      (str(uuid.uuid4()), actor_id, action, product_id, message, datetime.utcnow().isoformat()))

def payment_number(method):
    m = clean(method, 30).lower()
    if "mpesa" in m or "m-pesa" in m:
        return PAYMENT_MPESA
    if "halotel" in m or "tigo" in m:
        return PAYMENT_HALOTEL
    if "airtel" in m:
        return PAYMENT_AIRTEL
    return ""

def send_email_otp(to_email, code):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD and SMTP_FROM):
        return False
    msg = EmailMessage()
    msg["Subject"] = "NjiaMauzo Afrika — OTP ya kubadilisha password"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(f"OTP yako ni {code}. Itaisha ndani ya dakika 10. Usimpe mtu mwingine.")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        app.logger.warning("Email OTP failed: %s", e)
        return False

def send_whatsapp_text(to, text):
    if not (WHATSAPP_API_URL and WHATSAPP_API_TOKEN):
        return False
    payload = {"to": to, "message": text}
    try:
        req = urllib.request.Request(
            WHATSAPP_API_URL, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {WHATSAPP_API_TOKEN}"},
            method="POST")
        with urllib.request.urlopen(req, timeout=8) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        app.logger.warning("WhatsApp send failed: %s", e)
        return False

def send_sms(to, text):
    if not (SMS_API_URL and SMS_API_TOKEN):
        return False
    try:
        r = requests.post(SMS_API_URL,
                           json={"to": to, "message": text},
                           headers={"Authorization": f"Bearer {SMS_API_TOKEN}"},
                           timeout=8)
        return 200 <= r.status_code < 300
    except Exception as e:
        app.logger.warning("SMS send failed: %s", e)
        return False

def issue_otp(user_id, purpose="password_reset"):
    code = f"{secrets.randbelow(1_000_000):06d}"
    digest = hashlib.sha256(code.encode()).hexdigest()
    now = datetime.utcnow()
    q("UPDATE otp_codes SET used=1 WHERE user_id=? AND purpose=? AND used=0",
      (user_id, purpose))
    otp_id = str(uuid.uuid4())
    q("""INSERT INTO otp_codes(id,user_id,purpose,code_hash,expires_at,attempts,used,created_at)
         VALUES(?,?,?,?,?,?,?,?)""",
      (otp_id, user_id, purpose, digest, (now+timedelta(minutes=10)).isoformat(),
       0, 0, now.isoformat()))
    return code

def notify_admin_whatsapp(user_message, bot_reply):
    return send_whatsapp_text(
        ADMIN_WHATSAPP_NUMBER,
        f"🔔 NjiaMauzo Afrika Bot\n\nMtumiaji: {clean(user_message,1000)}\n\nBot: {clean(bot_reply,1000)}"
    )


# ---------------- SECURITY HEADERS ----------------
@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(self)"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' https: data:; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://challenges.cloudflare.com; "
        "frame-src https://challenges.cloudflare.com; connect-src 'self' https:;"
    )
    return resp


# ---------------- PAGES ----------------
@app.route("/")
def index():
    return render_template("index.html", turnstile_site_key=TURNSTILE_SITE_KEY)


# ---------------- AUTH ----------------
@app.get("/api/csrf")
def get_csrf():
    return jsonify(success=True, csrf=csrf_token())

@app.post("/api/register")
@rate_limited("register", 8, 300)
def register():
    if not verify_csrf():
        return json_error("CSRF token si sahihi.", 403)
    d = request.get_json(silent=True) or {}
    email = clean(d.get("email"), 150).lower()
    password = str(d.get("password") or "")
    name = clean(d.get("name"), 100)
    phone = clean(d.get("phone"), 30)
    if not EMAIL_RE.match(email):
        return json_error("Barua pepe si sahihi.")
    if len(name) < 2 or len(password) < 8:
        return json_error("Jina na password yenye angalau herufi 8 vinahitajika.")
    if not verify_turnstile(d.get("captcha_token")):
        return json_error("CAPTCHA haijathibitishwa.", 400)
    if q("SELECT id FROM users WHERE email=?", (email,), one=True):
        return json_error("Barua pepe tayari imesajiliwa.", 409)
    uid = str(uuid.uuid4())
    q("""INSERT INTO users(id,email,password,name,phone,is_admin,must_change_password,created_at)
         VALUES(?,?,?,?,?,?,?,?)""",
      (uid, email, generate_password_hash(password, method=PBKDF2_METHOD),
       name, phone, 0, 0, datetime.utcnow().isoformat()))
    session.clear()
    session.permanent = True
    session["user_id"] = uid
    csrf_token()
    return jsonify(success=True, message="Umesajiliwa.", user={"id":uid,"email":email,"name":name,"phone":phone})

@app.post("/api/login")
@rate_limited("login", 10, 300)
def login():
    if not verify_csrf():
        return json_error("CSRF token si sahihi.", 403)
    d = request.get_json(silent=True) or {}
    email = clean(d.get("email"), 150).lower()
    password = str(d.get("password") or "")
    if not verify_turnstile(d.get("captcha_token")):
        return json_error("CAPTCHA haijathibitishwa.", 400)
    u = q("SELECT * FROM users WHERE email=?", (email,), one=True)
    if not u or not check_password_hash(u["password"], password):
        return json_error("Email au password si sahihi.", 401)
    session.clear()
    session.permanent = True
    session["user_id"] = u["id"]
    csrf_token()
    return jsonify(success=True, message="Umeingia.",
                   must_change_password=bool(u["must_change_password"]),
                   user={"id":u["id"],"email":u["email"],"name":u["name"],"phone":u["phone"],"is_admin":bool(u["is_admin"])})

@app.post("/api/logout")
@protected
def logout():
    session.clear()
    return jsonify(success=True, message="Umetoka.")

@app.get("/api/me")
def me():
    u = current_user()
    if not u:
        return json_error("Hujaingia.", 401)
    return jsonify(success=True, csrf=csrf_token(),
                   must_change_password=bool(u["must_change_password"]),
                   user={"id":u["id"],"email":u["email"],"name":u["name"],"phone":u["phone"],"is_admin":bool(u["is_admin"])})

@app.post("/api/change-password")
@login_required
@protected
def change_password():
    d = request.get_json(silent=True) or {}
    old = str(d.get("old_password") or "")
    new = str(d.get("new_password") or "")
    u = current_user()
    if not check_password_hash(u["password"], old):
        return json_error("Password ya sasa si sahihi.", 401)
    if len(new) < 8:
        return json_error("Password mpya iwe na angalau herufi 8.")
    q("UPDATE users SET password=?, must_change_password=0 WHERE id=?",
      (generate_password_hash(new, method=PBKDF2_METHOD), u["id"]))
    return jsonify(success=True, message="Password imebadilishwa.")


# ---------------- PASSWORD RESET / OTP ----------------
@app.post("/api/forgot-password")
@rate_limited("forgot", 5, 300)
def forgot_password():
    if not verify_csrf():
        return json_error("CSRF token si sahihi.", 403)
    d = request.get_json(silent=True) or {}
    email = clean(d.get("email"), 150).lower()
    method = clean(d.get("method"), 20).lower()
    u = q("SELECT * FROM users WHERE email=?", (email,), one=True)
    # Generic response prevents account enumeration.
    generic = "Ikiwa akaunti ipo, OTP itatumwa kupitia njia uliyochagua."
    if not u:
        return jsonify(success=True, message=generic)
    code = issue_otp(u["id"])
    sent = False
    if method == "email":
        sent = send_email_otp(u["email"], code)
    elif method == "whatsapp":
        sent = send_whatsapp_text(u["phone"], f"NjiaMauzo Afrika OTP: {code}. Itaisha ndani ya dakika 10.")
    elif method == "sms":
        sent = send_sms(u["phone"], f"NjiaMauzo Afrika OTP: {code}. Itaisha ndani ya dakika 10.")
    return jsonify(success=True, message=generic, delivery_configured=sent)

@app.post("/api/verify-otp")
@rate_limited("verify_otp", 10, 300)
def verify_otp():
    if not verify_csrf():
        return json_error("CSRF token si sahihi.", 403)
    d = request.get_json(silent=True) or {}
    email = clean(d.get("email"), 150).lower()
    code = clean(d.get("otp"), 10)
    u = q("SELECT * FROM users WHERE email=?", (email,), one=True)
    if not u:
        return json_error("OTP si sahihi.", 400)
    otp = q("""SELECT * FROM otp_codes WHERE user_id=? AND purpose='password_reset'
               AND used=0 ORDER BY created_at DESC""", (u["id"],), one=True)
    if not otp or datetime.fromisoformat(otp["expires_at"]) < datetime.utcnow():
        return json_error("OTP imeisha muda.", 400)
    if int(otp["attempts"]) >= 5:
        return json_error("Majaribio ya OTP yamekwisha.", 429)
    digest = hashlib.sha256(code.encode()).hexdigest()
    if not hmac.compare_digest(digest, otp["code_hash"]):
        q("UPDATE otp_codes SET attempts=attempts+1 WHERE id=?", (otp["id"],))
        return json_error("OTP si sahihi.", 400)
    q("UPDATE otp_codes SET used=1 WHERE id=?", (otp["id"],))
    reset_token = secrets.token_urlsafe(32)
    session["password_reset_user"] = u["id"]
    session["password_reset_token"] = reset_token
    session["password_reset_expires"] = (datetime.utcnow()+timedelta(minutes=10)).isoformat()
    return jsonify(success=True, reset_token=reset_token)

@app.post("/api/reset-password")
@protected
def reset_password():
    d = request.get_json(silent=True) or {}
    token = clean(d.get("reset_token"), 100)
    new = str(d.get("new_password") or "")
    if token != session.get("password_reset_token"):
        return json_error("Reset token si sahihi.", 403)
    if datetime.fromisoformat(session.get("password_reset_expires")) < datetime.utcnow():
        return json_error("Reset token imeisha.", 400)
    if len(new) < 8:
        return json_error("Password mpya iwe na angalau herufi 8.")
    uid = session.get("password_reset_user")
    q("UPDATE users SET password=?, must_change_password=0 WHERE id=?",
      (generate_password_hash(new, method=PBKDF2_METHOD), uid))
    session.pop("password_reset_user", None)
    session.pop("password_reset_token", None)
    session.pop("password_reset_expires", None)
    return jsonify(success=True, message="Password mpya imewekwa.")


# ---------------- PRODUCTS + LOCATION ----------------
@app.get("/api/products")
@rate_limited("products", 60, 60)
def products():
    user = current_user()
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    qtext = clean(request.args.get("q"), 100).lower()
    rows = q("""SELECT * FROM products
                WHERE lower(title) LIKE ? OR lower(description) LIKE ?
                ORDER BY created_at DESC""",
             (f"%{qtext}%", f"%{qtext}%"), many=True) if qtext else q(
             "SELECT * FROM products ORDER BY created_at DESC", many=True)
    out = [product_json(r, user["id"] if user else None, lat, lon) for r in rows]
    if lat is not None and lon is not None:
        out.sort(key=lambda x: x["distance_km"] if x["distance_km"] is not None else 10**9)
    return jsonify(success=True, products=out)

@app.post("/api/products/<product_id>/like")
@login_required
@protected
def like_product(product_id):
    u = current_user()
    p = q("SELECT * FROM products WHERE id=?", (product_id,), one=True)
    if not p:
        return json_error("Bidhaa haipo.", 404)
    existing = q("SELECT 1 FROM likes WHERE user_id=? AND product_id=?", (u["id"], product_id), one=True)
    if existing:
        q("DELETE FROM likes WHERE user_id=? AND product_id=?", (u["id"], product_id))
        liked = False
        action = "unliked"
        message = f"{u['name']} ameondoa Like kwenye {p['title']}"
    else:
        q("INSERT INTO likes(user_id,product_id,created_at) VALUES(?,?,?)",
          (u["id"], product_id, datetime.utcnow().isoformat()))
        liked = True
        action = "liked"
        message = f"{u['name']} amependa {p['title']}"
    add_activity(u["id"], action, message, product_id)
    n = q("SELECT COUNT(*) AS n FROM likes WHERE product_id=?", (product_id,), one=True)
    return jsonify(success=True, liked=liked, likes=int(n["n"]))

@app.get("/api/comments/<product_id>")
def comments(product_id):
    rows = q("""SELECT c.*, u.name FROM comments c JOIN users u ON u.id=c.user_id
                WHERE c.product_id=? ORDER BY c.created_at DESC""", (product_id,), many=True)
    return jsonify(success=True, comments=[{"id":r["id"],"author":r["name"],"text":r["text"],"created_at":r["created_at"]} for r in rows])

@app.post("/api/comments/<product_id>")
@login_required
@protected
def add_comment(product_id):
    u = current_user()
    p = q("SELECT * FROM products WHERE id=?", (product_id,), one=True)
    if not p:
        return json_error("Bidhaa haipo.", 404)
    d = request.get_json(silent=True) or {}
    text = clean(d.get("text"), 500)
    if len(text) < 1:
        return json_error("Maoni hayawezi kuwa tupu.")
    cid = str(uuid.uuid4())
    q("INSERT INTO comments(id,user_id,product_id,text,created_at) VALUES(?,?,?,?,?)",
      (cid,u["id"],product_id,text,datetime.utcnow().isoformat()))
    add_activity(u["id"], "commented", f"{u['name']} ameacha maoni kwenye {p['title']}", product_id)
    return jsonify(success=True, comment={"id":cid,"author":u["name"],"text":text})

@app.post("/api/follow/<user_id>")
@login_required
@protected
def follow_user(user_id):
    u = current_user()
    if user_id == u["id"]:
        return json_error("Huwezi kujifollow.")
    target = q("SELECT id,name FROM users WHERE id=?", (user_id,), one=True)
    if not target:
        return json_error("Mtumiaji haipo.", 404)
    existing = q("SELECT 1 FROM follows WHERE follower_id=? AND following_id=?", (u["id"],user_id), one=True)
    if existing:
        q("DELETE FROM follows WHERE follower_id=? AND following_id=?", (u["id"],user_id))
        following = False
    else:
        q("INSERT INTO follows(follower_id,following_id,created_at) VALUES(?,?,?)",
          (u["id"],user_id,datetime.utcnow().isoformat()))
        following = True
    add_activity(u["id"], "follow", f"{u['name']} {'' if following else 'ameacha'} kumfollow {target['name']}")
    return jsonify(success=True, following=following)


# ---------------- LIVE ACTIVITY ----------------
@app.get("/api/activity")
def activity():
    rows = q("""SELECT a.*, COALESCE(u.name,'Mgeni') AS actor FROM activities a
                LEFT JOIN users u ON u.id=a.actor_id
                ORDER BY a.created_at DESC LIMIT 50""", many=True)
    return jsonify(success=True, activities=[
        {"id":r["id"],"actor":r["actor"],"action":r["action"],
         "product_id":r["product_id"],"message":r["message"],"created_at":r["created_at"]}
        for r in rows
    ])


# ---------------- AI PRODUCT FINDER ----------------
@app.get("/api/ai-products")
@rate_limited("ai_products", 30, 60)
def ai_products():
    qtext = clean(request.args.get("q"), 100).lower()
    rows = q("""SELECT * FROM products
                WHERE lower(title) LIKE ? OR lower(description) LIKE ? OR lower(location) LIKE ?
                ORDER BY created_at DESC LIMIT 20""",
             (f"%{qtext}%",f"%{qtext}%",f"%{qtext}%"), many=True) if qtext else q(
             "SELECT * FROM products ORDER BY created_at DESC LIMIT 20", many=True)
    return jsonify(success=True, products=[product_json(r) for r in rows])

@app.post("/api/bot-chat")
@rate_limited("bot_chat", 40, 60)
def bot_chat():
    d = request.get_json(silent=True) or {}
    message = clean(d.get("message"), 500)
    if not message:
        return json_error("Andika ujumbe.")
    ml = message.lower()
    if "bei" in ml:
        reply = "Nenda sehemu ya Bei kulinganisha masoko, au tumia AI Product Finder. Huduma ya kutafutiwa bidhaa maalum ni TZS 3,000."
    elif any(c in ml for c in ["ufuta","mahindi","maharage","mpunga","korosho","karanga","kahawa","nyanya"]):
        reply = "Tuna listings za mazao na huduma mbalimbali. Taja zao, kiasi, eneo na bei unayotaka."
    elif any(x in ml for x in ["malipo","ada","lipa","pesa"]):
        reply = "Ada ya Assisted Search ni TZS 3,000. Chagua njia ya malipo kwenye sehemu ya Huduma ya Kutafutiwa Bidhaa."
    elif any(x in ml for x in ["asante","sawa","poa"]):
        reply = "Karibu sana! Nipo hapa muda wote."
    else:
        reply = "Nimepokea ujumbe wako. Nitajie zao, kiasi, eneo na bei unayolenga."
    notify_admin_whatsapp(message, reply)
    return jsonify(success=True, reply=reply)


# ---------------- LIVE PAID AI SEARCH ----------------
def _search_products_for_job(job_id, user_id, query_text):
    words = [w for w in re.findall(r"[a-zA-ZÀ-ÿ0-9]+", query_text.lower()) if len(w) >= 3][:12]
    rows = q("SELECT * FROM products ORDER BY created_at DESC LIMIT 250", many=True)
    scored = []
    for p in rows or []:
        hay = " ".join([str(p["title"] or ""), str(p["description"] or ""),
                        str(p["location"] or ""), str(p["category"] or ""),
                        str(p["seller_name"] or "")]).lower()
        score = sum(1 for w in words if w in hay)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: (x[0], x[1]["created_at"]), reverse=True)
    now = datetime.utcnow().isoformat()
    for score, p in scored[:50]:
        try:
            q("""INSERT INTO assisted_search_results
                 (id,job_id,product_id,title,price,location,seller_name,description,source,score,created_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
              (str(uuid.uuid4()),job_id,p["id"],p["title"],float(p["price"]),p["location"],
               p["seller_name"],p["description"],"NjiaMauzo Live Search",float(score),now))
        except Exception:
            q("""UPDATE assisted_search_results SET title=?,price=?,location=?,seller_name=?,
                 description=?,source=?,score=?,created_at=? WHERE job_id=? AND product_id=?""",
              (p["title"],float(p["price"]),p["location"],p["seller_name"],p["description"],
               "NjiaMauzo Live Search",float(score),now,job_id,p["id"]))
    return len(scored)

def _run_live_search_once(job):
    try:
        count = _search_products_for_job(job["id"],job["user_id"],job["query"])
        now=datetime.utcnow()
        delay=random.randint(LIVE_SEARCH_MIN_SECONDS,LIVE_SEARCH_MAX_SECONDS)
        q("""UPDATE assisted_search_jobs SET status='SEARCHING',last_run_at=?,next_run_at=? WHERE id=?""",
          (now.isoformat(),(now+timedelta(seconds=delay)).isoformat(),job["id"]))
        add_activity(job["user_id"],"live_ai_search",
                     f"AI Searcher amefanya utafutaji wa moja kwa moja: {count} matches; refresh ndani ya {delay}s")
    except Exception:
        q("UPDATE assisted_search_jobs SET status='RETRYING',next_run_at=? WHERE id=?",
          ((datetime.utcnow()+timedelta(seconds=60)).isoformat(),job["id"]))

def live_search_worker():
    while LIVE_SEARCH_ENABLED:
        try:
            with app.app_context():
                jobs=q("""SELECT * FROM assisted_search_jobs
                          WHERE status IN ('QUEUED','SEARCHING','RETRYING')
                          AND (next_run_at IS NULL OR next_run_at<=?)
                          ORDER BY created_at ASC LIMIT 20""",
                       (datetime.utcnow().isoformat(),),many=True)
                for job in jobs or []: _run_live_search_once(job)
        except Exception:
            pass
        time.sleep(5)

def start_live_search_worker():
    if LIVE_SEARCH_ENABLED and os.environ.get("DISABLE_LIVE_SEARCH_WORKER")!="1":
        threading.Thread(target=live_search_worker,name="njiamauzo-live-search",daemon=True).start()

@app.post("/api/assisted-search/start")
@login_required
@protected
@rate_limited("assisted_start",10,60)
def assisted_search_start():
    u=current_user(); d=request.get_json(silent=True) or {}
    order_id=clean(d.get("order_id"),100)
    o=q("SELECT * FROM orders WHERE id=? AND user_id=? AND status='VERIFIED'",(order_id,u["id"]),one=True)
    if not o: return json_error("Malipo yaliyothibitishwa hayajapatikana.",403)
    existing=q("SELECT * FROM assisted_search_jobs WHERE order_id=?",(order_id,),one=True)
    if existing: return jsonify(success=True,job_id=existing["id"],status=existing["status"])
    query_text=clean(d.get("query") or "",1000)
    if len(query_text)<5: return json_error("Eleza bidhaa unayotafuta, eneo, bei au kiasi.")
    jid=str(uuid.uuid4()); now=datetime.utcnow().isoformat()
    q("""INSERT INTO assisted_search_jobs(id,user_id,order_id,query,status,created_at)
         VALUES(?,?,?,?,?,?)""",(jid,u["id"],order_id,query_text,"QUEUED",now))
    add_activity(u["id"],"live_ai_search",f"AI Searcher imeanza kutafuta: {query_text[:120]}")
    return jsonify(success=True,job_id=jid,status="QUEUED")

@app.get("/api/assisted-search/<job_id>")
@login_required
def assisted_search_results(job_id):
    u=current_user()
    job=q("SELECT * FROM assisted_search_jobs WHERE id=? AND user_id=?",(job_id,u["id"]),one=True)
    if not job: return json_error("Utafutaji haujapatikana.",404)
    rows=q("""SELECT * FROM assisted_search_results WHERE job_id=?
              ORDER BY score DESC,created_at DESC LIMIT 50""",(job_id,),many=True)
    return jsonify(success=True,job={"id":job["id"],"status":job["status"],"query":job["query"],
        "last_run_at":job["last_run_at"],"next_run_at":job["next_run_at"]},
        results=[{"id":r["id"],"product_id":r["product_id"],"title":r["title"],
        "price":float(r["price"]) if r["price"] is not None else None,"location":r["location"],
        "seller_name":r["seller_name"],"description":r["description"],"source":r["source"],
        "score":float(r["score"])} for r in rows])

# ---------------- PAYMENTS ----------------
@app.get("/api/service/payment-number")
def service_payment_number():
    # Numbers are delivered by backend, not embedded in HTML.
    return jsonify(success=True, fee=ASSISTED_SEARCH_FEE,
                   numbers={"mpesa":PAYMENT_MPESA, "halotel":PAYMENT_HALOTEL, "airtel":PAYMENT_AIRTEL})

@app.get("/api/payment/numbers")
def payment_numbers():
    return service_payment_number()

@app.post("/api/payment/request")
@login_required
@protected
def payment_request():
    u = current_user()
    d = request.get_json(silent=True) or {}
    phone = clean(d.get("simu"), 30)
    method = clean(d.get("njia"), 30)
    amount = int(d.get("kiasi") or ASSISTED_SEARCH_FEE)
    product_id = clean(d.get("product_id"), 100)
    if amount != ASSISTED_SEARCH_FEE:
        return json_error(f"Ada sahihi ni TZS {ASSISTED_SEARCH_FEE:,}.")
    number = payment_number(method)
    if not phone or not number:
        return json_error("Weka simu na njia sahihi ya malipo.")
    oid = str(uuid.uuid4())
    q("""INSERT INTO orders(id,user_id,phone,method,amount,product_id,status,created_at)
         VALUES(?,?,?,?,?,?,?,?)""",
      (oid,u["id"],phone,method,amount,product_id,"PENDING",datetime.utcnow().isoformat()))
    add_activity(u["id"], "payment_pending", f"{u['name']} ameanzisha malipo ya TZS {amount:,}")
    notify_admin_whatsapp(f"Payment request {oid} kutoka {u['name']} {phone} {method}",
                          f"Amount TZS {amount:,}, status PENDING")
    return jsonify(success=True, order_id=oid, status="PENDING",
                   message=f"Tuma TZS {amount:,} kupitia {method} kwenda {number}.")

@app.post("/api/payment/webhook")
@rate_limited("payment_webhook",60,60)
def payment_webhook():
    if not PAYMENT_WEBHOOK_SECRET: return json_error("PAYMENT_WEBHOOK_SECRET haijawekwa.",503)
    supplied=request.headers.get("X-NjiaMauzo-Webhook-Secret","")
    if not hmac.compare_digest(str(supplied),str(PAYMENT_WEBHOOK_SECRET)): return json_error("Invalid webhook.",401)
    d=request.get_json(silent=True) or {}
    order_id=clean(d.get("order_id") or d.get("payment_id"),100)
    status=clean(d.get("status"),30).upper(); reference=clean(d.get("provider_reference"),150)
    if status!="VERIFIED" or not order_id or not reference: return json_error("order_id, VERIFIED na provider_reference zinahitajika.")
    o=q("SELECT * FROM orders WHERE id=?",(order_id,),one=True)
    if not o: return json_error("Payment not found.",404)
    q("UPDATE orders SET status='VERIFIED' WHERE id=?",(order_id,))
    add_activity(o["user_id"],"payment_verified",f"Malipo ya TZS {int(o['amount']):,} yamethibitishwa.")
    return jsonify(success=True,status="VERIFIED",order_id=order_id)

@app.get("/api/payment/status/<order_id>")
@login_required
def payment_status(order_id):
    u = current_user()
    o = q("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id,u["id"]), one=True)
    if not o:
        return json_error("Agizo halipatikani.", 404)
    return jsonify(success=True, order={"id":o["id"],"amount":o["amount"],"method":o["method"],
                                        "status":o["status"],"created_at":o["created_at"]})


# ---------------- ADMIN ----------------
@app.get("/api/admin/stats")
@admin_required
def admin_stats():
    return jsonify(success=True,
        users=int(q("SELECT COUNT(*) AS n FROM users",one=True)["n"]),
        products=int(q("SELECT COUNT(*) AS n FROM products",one=True)["n"]),
        orders=int(q("SELECT COUNT(*) AS n FROM orders",one=True)["n"]),
        pending_payments=int(q("SELECT COUNT(*) AS n FROM orders WHERE status='PENDING'",one=True)["n"]))

@app.post("/api/notify-admin")
@protected
def notify_admin_endpoint():
    d = request.get_json(silent=True) or {}
    ok = notify_admin_whatsapp(clean(d.get("user_message"),1000), clean(d.get("bot_reply"),1000))
    return jsonify(success=True, sent=ok)


# ---------------- HEALTH ----------------
@app.get("/api/health")
def health():
    try:
        q("SELECT 1", one=True)
        return jsonify(success=True, service="NJIA MAUZO AFRIKA", status="ok")
    except Exception:
        return jsonify(success=False, status="database_error"), 503


# ---------------- STARTUP ----------------
with app.app_context():
    init_db()

start_live_search_worker()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
