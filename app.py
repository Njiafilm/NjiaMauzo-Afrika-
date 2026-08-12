# ============================================================
# NJIA MAUZO AFRIKA
# Professional Flask Backend
# ============================================================

import os
import re
import json
import time
import uuid
import math
import random
import smtplib
import secrets
import logging
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    g
)

from flask_cors import CORS
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    secrets.token_hex(32)
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get(
        "SESSION_COOKIE_SECURE",
        "true"
    ).lower() == "true"
)

app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


# ============================================================
# CORS
# ============================================================

CORS(
    app,
    supports_credentials=True,
    origins=os.environ.get(
        "CORS_ORIGINS",
        "*"
    ).split(",")
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s "
        "%(message)s"
    )
)

logger = logging.getLogger(
    "njiamauzo"
)


# ============================================================
# PAYMENT CONFIGURATION
# ============================================================

SERVICE_FEE = 3000

PAYMENT_MPESA = os.environ.get(
    "PAYMENT_MPESA",
    "0755248789"
)

PAYMENT_HALOTEL = os.environ.get(
    "PAYMENT_HALOTEL",
    "0625031460"
)

PAYMENT_AIRTEL = os.environ.get(
    "PAYMENT_AIRTEL",
    "0691925100"
)


# ============================================================
# WHATSAPP CONFIGURATION
# ============================================================

WHATSAPP_API_URL = os.environ.get(
    "WHATSAPP_API_URL",
    ""
)

WHATSAPP_API_TOKEN = os.environ.get(
    "WHATSAPP_API_TOKEN",
    ""
)

ADMIN_WHATSAPP_NUMBER = os.environ.get(
    "ADMIN_WHATSAPP_NUMBER",
    "255755248789"
)


# ============================================================
# SMS CONFIGURATION (generic HTTP gateway, e.g. Beem/Twilio-like)
# ============================================================

SMS_API_URL = os.environ.get("SMS_API_URL", "")
SMS_API_KEY = os.environ.get("SMS_API_KEY", "")
SMS_SENDER_ID = os.environ.get("SMS_SENDER_ID", "NjiaMauzo")


# ============================================================
# EMAIL / SMTP CONFIGURATION
# ============================================================

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "info@njiamauzo.africa")


# ============================================================
# EXTERNAL API
# ============================================================

EXTERNAL_API = os.environ.get(
    "EXTERNAL_API",
    "https://njiamauzo-afrika.onrender.com"
).rstrip("/")


# ============================================================
# DATABASE
# ============================================================

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    ""
)

DB_TYPE = (
    "postgresql"
    if DATABASE_URL
    else "sqlite"
)

if DB_TYPE == "postgresql":

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        psycopg = None

else:

    import sqlite3


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():

    if hasattr(g, "db"):
        return g.db

    if DB_TYPE == "postgresql":

        if psycopg is None:
            raise RuntimeError(
                "psycopg haijawekwa."
            )

        g.db = psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row
        )

    else:

        g.db = sqlite3.connect(
            os.environ.get(
                "SQLITE_PATH",
                "njiamauzo.db"
            ),
            timeout=20
        )

        g.db.row_factory = sqlite3.Row

        g.db.execute(
            "PRAGMA foreign_keys=ON"
        )

        g.db.execute(
            "PRAGMA journal_mode=WAL"
        )

    return g.db


def db():
    return get_db()


@app.teardown_appcontext
def close_db(error=None):

    connection = g.pop(
        "db",
        None
    )

    if connection:
        connection.close()


def sql(query):

    if DB_TYPE == "postgresql":
        return query.replace(
            "?",
            "%s"
        )

    return query


def execute(
    query,
    params=(),
    commit=False
):

    connection = db()

    cursor = connection.cursor()

    cursor.execute(
        sql(query),
        params
    )

    if commit:
        connection.commit()

    return cursor


def fetchone(
    query,
    params=()
):

    return execute(
        query,
        params
    ).fetchone()


def fetchall(
    query,
    params=()
):

    return execute(
        query,
        params
    ).fetchall()


# ============================================================
# SECURITY HELPERS
# ============================================================

def sanitize_text(
    value,
    maximum=500
):

    value = str(
        value or ""
    )

    value = value.replace(
        "\x00",
        ""
    )

    value = re.sub(
        r"[\r\n\t]+",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()[:maximum]


def valid_email(email):

    return bool(
        re.match(
            r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            email or ""
        )
    )


def client_ip():

    return request.remote_addr or "unknown"


# ============================================================
# RATE LIMITER
# ============================================================

RATE_LIMIT_STORE = {}


def rate_limit(
    name,
    max_calls=30,
    window_seconds=60
):

    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            now = time.time()

            key = (
                f"{name}:"
                f"{client_ip()}"
            )

            timestamps = RATE_LIMIT_STORE.get(
                key,
                []
            )

            timestamps = [
                value
                for value in timestamps
                if now - value < window_seconds
            ]

            if len(timestamps) >= max_calls:

                return jsonify({
                    "success": False,
                    "message": (
                        "Umefanya maombi mengi. "
                        "Jaribu tena baadaye."
                    )
                }), 429

            timestamps.append(
                now
            )

            RATE_LIMIT_STORE[key] = timestamps

            return function(
                *args,
                **kwargs
            )

        return wrapper

    return decorator


# ============================================================
# CSRF
# ============================================================

def csrf_token():

    if "csrf_token" not in session:

        session["csrf_token"] = (
            secrets.token_urlsafe(32)
        )

    return session["csrf_token"]


def check_csrf():

    if request.method in {
        "POST",
        "PUT",
        "PATCH",
        "DELETE"
    }:

        # login/register are protected by CAPTCHA instead of CSRF
        # (no session exists yet for a first-time visitor)
        if request.path in {
            "/api/login",
            "/api/register"
        }:
            return True

        provided = (
            request.headers.get(
                "X-CSRF-Token"
            )
            or
            (
                request.get_json(
                    silent=True
                )
                or {}
            ).get(
                "csrf_token"
            )
        )

        expected = session.get(
            "csrf_token"
        )

        if not provided or not expected:

            return False

        return secrets.compare_digest(
            str(provided),
            str(expected)
        )

    return True


@app.before_request
def before_request():

    if not check_csrf():

        return jsonify({
            "success": False,
            "message": "CSRF token si sahihi."
        }), 403


# ============================================================
# SECURITY HEADERS
# ============================================================

@app.after_request
def security_headers(response):

    response.headers[
        "X-Content-Type-Options"
    ] = "nosniff"

    response.headers[
        "X-Frame-Options"
    ] = "DENY"

    response.headers[
        "Referrer-Policy"
    ] = "strict-origin-when-cross-origin"

    response.headers[
        "Permissions-Policy"
    ] = (
        "camera=(), "
        "microphone=(), "
        "geolocation=(self)"
    )

    if request.is_secure:

        response.headers[
            "Strict-Transport-Security"
        ] = (
            "max-age=31536000; "
            "includeSubDomains"
        )

    return response


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    connection = db()

    if DB_TYPE == "sqlite":

        statements = [

            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                failed_logins INTEGER DEFAULT 0,
                locked_until TEXT,
                must_change_password INTEGER DEFAULT 0,
                lat REAL,
                lon REAL,
                joined TEXT NOT NULL
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                real_price REAL NOT NULL,
                description TEXT,
                image TEXT,
                seller_id TEXT,
                seller_name TEXT,
                location TEXT,
                lat REAL,
                lon REAL,
                category TEXT,
                alama TEXT,
                likes INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                user_email TEXT,
                simu TEXT NOT NULL,
                njia TEXT NOT NULL,
                kiasi REAL NOT NULL,
                product_id TEXT,
                status TEXT NOT NULL,
                created TEXT NOT NULL
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS comments (
                id TEXT PRIMARY KEY,
                product_id INTEGER NOT NULL,
                author TEXT NOT NULL,
                text TEXT NOT NULL,
                time TEXT NOT NULL
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                user_email TEXT NOT NULL,
                created TEXT NOT NULL,
                UNIQUE(product_id, user_email)
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS follows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                follower_email TEXT NOT NULL,
                seller_id TEXT NOT NULL,
                created TEXT NOT NULL,
                UNIQUE(follower_email, seller_id)
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS activity_feed (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                actor_name TEXT,
                product_id INTEGER,
                product_title TEXT,
                message TEXT NOT NULL,
                created TEXT NOT NULL
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS password_resets (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                otp_hash TEXT NOT NULL,
                channel TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                expires TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                created TEXT NOT NULL
            )
            """
        ]

    else:

        statements = [

            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                failed_logins INTEGER DEFAULT 0,
                locked_until TEXT,
                must_change_password INTEGER DEFAULT 0,
                lat DOUBLE PRECISION,
                lon DOUBLE PRECISION,
                joined TEXT NOT NULL
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS products (
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                real_price DOUBLE PRECISION NOT NULL,
                description TEXT,
                image TEXT,
                seller_id TEXT,
                seller_name TEXT,
                location TEXT,
                lat DOUBLE PRECISION,
                lon DOUBLE PRECISION,
                category TEXT,
                alama TEXT,
                likes INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                user_email TEXT,
                simu TEXT NOT NULL,
                njia TEXT NOT NULL,
                kiasi DOUBLE PRECISION NOT NULL,
                product_id TEXT,
                status TEXT NOT NULL,
                created TEXT NOT NULL
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS comments (
                id TEXT PRIMARY KEY,
                product_id BIGINT NOT NULL,
                author TEXT NOT NULL,
                text TEXT NOT NULL,
                time TEXT NOT NULL
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS likes (
                id BIGSERIAL PRIMARY KEY,
                product_id BIGINT NOT NULL,
                user_email TEXT NOT NULL,
                created TEXT NOT NULL,
                UNIQUE(product_id, user_email)
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS follows (
                id BIGSERIAL PRIMARY KEY,
                follower_email TEXT NOT NULL,
                seller_id TEXT NOT NULL,
                created TEXT NOT NULL,
                UNIQUE(follower_email, seller_id)
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS activity_feed (
                id BIGSERIAL PRIMARY KEY,
                type TEXT NOT NULL,
                actor_name TEXT,
                product_id BIGINT,
                product_title TEXT,
                message TEXT NOT NULL,
                created TEXT NOT NULL
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS password_resets (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                otp_hash TEXT NOT NULL,
                channel TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                expires TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                created TEXT NOT NULL
            )
            """
        ]

    for statement in statements:

        connection.cursor().execute(
            statement
        )

    connection.commit()


# ============================================================
# DEFAULT PRODUCTS
# ============================================================

DEFAULT_PRODUCTS = [

    {
        "title": "Mahindi ya Ubora wa Juu – Tani 50",
        "real_price": 850000,
        "description": "Mahindi yaliyovunwa hivi karibuni kutoka shamba la Morogoro.",
        "image": "https://images.unsplash.com/photo-1625246333195-78d9c38ad449?w=800",
        "seller_id": "101",
        "seller_name": "Juma Mkulima",
        "location": "Morogoro, Mvomero",
        "lat": -8.9333, "lon": 37.6667,
        "category": "mazao",
        "alama": "Mazao",
        "likes": 12
    },
    {
        "title": "Mtaalamu wa Kilimo – Ushauri wa Shamba",
        "real_price": 150000,
        "description": "Mtaalamu wa kilimo cha kisasa.",
        "image": "https://images.unsplash.com/photo-1592982537447-7440770cbfc9?w=800",
        "seller_id": "102",
        "seller_name": "Dkt. Amina Hassan",
        "location": "Arusha, Njiro",
        "lat": -3.3869, "lon": 36.6822,
        "category": "mtaalamu",
        "alama": "Mtaalamu",
        "likes": 8
    },
    {
        "title": "Kahawa Arabica – Kilimanjaro Grade AA",
        "real_price": 1200000,
        "description": "Kahawa bora ya Kilimanjaro, Grade AA.",
        "image": "https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=800",
        "seller_id": "103",
        "seller_name": "Kilimanjaro Coffee Co-op",
        "location": "Moshi, Kilimanjaro",
        "lat": -3.3349, "lon": 37.3407,
        "category": "mazao",
        "alama": "Mazao",
        "likes": 21
    },
    {
        "title": "Huduma ya Usafirishaji wa Mazao",
        "real_price": 350000,
        "description": "Lori za kusafirisha mazao kutoka shambani hadi soko.",
        "image": "https://images.unsplash.com/photo-1601584115197-04ecc0da31d7?w=800",
        "seller_id": "104",
        "seller_name": "Safari Mazao Ltd",
        "location": "Dar es Salaam",
        "lat": -6.7924, "lon": 39.2083,
        "category": "huduma",
        "alama": "Huduma",
        "likes": 5
    },
    {
        "title": "Trekta ya Kukodi – John Deere",
        "real_price": 250000,
        "description": "Trekta ya kisasa inayopatikana kwa kukodi.",
        "image": "https://images.unsplash.com/photo-1530267981375-f0de937f5f13?w=800",
        "seller_id": "105",
        "seller_name": "Vifaa vya Kilimo TZ",
        "location": "Dodoma",
        "lat": -6.1630, "lon": 35.7516,
        "category": "vifaa",
        "alama": "Vifaa",
        "likes": 15
    },
    {
        "title": "Nyanya za Chafu – Tani 20",
        "real_price": 480000,
        "description": "Nyanya safi zilizopandwa kwenye chafu.",
        "image": "https://images.unsplash.com/photo-1546094096-0df4bcaaa337?w=800",
        "seller_id": "106",
        "seller_name": "Green House Farm",
        "location": "Iringa",
        "lat": -7.7690, "lon": 35.6960,
        "category": "mazao",
        "alama": "Mazao",
        "likes": 9
    }
]


def seed_products():

    existing = fetchone(
        "SELECT id FROM products LIMIT 1"
    )

    if existing:
        return

    for product in DEFAULT_PRODUCTS:

        execute(
            """
            INSERT INTO products
            (
                title, real_price, description, image,
                seller_id, seller_name, location, lat, lon,
                category, alama, likes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product["title"],
                product["real_price"],
                product["description"],
                product["image"],
                product["seller_id"],
                product["seller_name"],
                product["location"],
                product["lat"],
                product["lon"],
                product["category"],
                product["alama"],
                product["likes"],
                datetime.now(timezone.utc).isoformat()
            )
        )

    db().commit()


# ============================================================
# ADMIN SEED  (default password 0000 -> must change on first login)
# ============================================================

def seed_admin():

    email = os.environ.get(
        "ADMIN_EMAIL",
        "admin@njiamauzo.africa"
    ).strip().lower()

    password = os.environ.get(
        "ADMIN_PASSWORD",
        "0000"
    )

    existing = fetchone(
        "SELECT id FROM users WHERE email = ?",
        (email,)
    )

    if existing:
        return

    execute(
        """
        INSERT INTO users
        (email, password, name, phone, role, must_change_password, joined)
        VALUES (?, ?, ?, ?, 'admin', 1, ?)
        """,
        (
            email,
            generate_password_hash(password),
            "NjiaMauzo Admin",
            "",
            datetime.now(timezone.utc).isoformat()
        ),
        commit=True
    )

    logger.info(
        "Admin default akaunti imeundwa: %s / nywila ya awali: 0000 "
        "(itabidi ibadilishwe baada ya login ya kwanza)",
        email
    )


# ============================================================
# AUTH DECORATORS
# ============================================================

def current_user_row():

    email = session.get("user")

    if not email:
        return None

    return fetchone(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    )


def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        email = session.get("user")

        if not email:
            return jsonify({
                "success": False,
                "message": "Ingia kwanza."
            }), 401

        return function(*args, **kwargs)

    return wrapper


def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        email = session.get("user")

        if not email:
            return jsonify({
                "success": False,
                "message": "Ingia kwanza."
            }), 401

        user = fetchone(
            "SELECT role FROM users WHERE email = ?",
            (email,)
        )

        if not user or user["role"] != "admin":

            return jsonify({
                "success": False,
                "message": "Huna ruhusa ya admin."
            }), 403

        return function(*args, **kwargs)

    return wrapper


# ============================================================
# ACTIVITY FEED HELPER
# ============================================================

def log_activity(activity_type, actor_name, message, product_id=None, product_title=None):

    try:
        execute(
            """
            INSERT INTO activity_feed
            (type, actor_name, product_id, product_title, message, created)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                activity_type,
                actor_name,
                product_id,
                product_title,
                message,
                datetime.now(timezone.utc).isoformat()
            ),
            commit=True
        )
    except Exception:
        logger.exception("Imeshindikana kuandika activity feed")


# ============================================================
# CAPTCHA  (simple math challenge, no external service required)
# ============================================================

def make_captcha():

    a = random.randint(1, 9)
    b = random.randint(1, 9)

    session["captcha_answer"] = str(a + b)
    session["captcha_id"] = secrets.token_urlsafe(8)

    return {
        "captcha_id": session["captcha_id"],
        "question": f"{a} + {b} = ?"
    }


def check_captcha(captcha_id, answer):

    expected_id = session.get("captcha_id")
    expected_answer = session.get("captcha_answer")

    if not expected_id or not expected_answer:
        return False

    if str(captcha_id) != str(expected_id):
        return False

    ok = str(answer).strip() == str(expected_answer)

    # one-time use
    session.pop("captcha_answer", None)
    session.pop("captcha_id", None)

    return ok


@app.route("/api/captcha", methods=["GET"])
def captcha():

    return jsonify({
        "success": True,
        **make_captcha()
    })


# ============================================================
# DISTANCE HELPER (haversine, km)
# ============================================================

def haversine_km(lat1, lon1, lat2, lon2):

    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    except (TypeError, ValueError):
        return None

    r = 6371.0

    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return round(r * c, 1)


# ============================================================
# OTP / MESSAGING HELPERS
# ============================================================

def send_email_otp(to_email, otp):

    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):

        logger.warning(
            "SMTP haijawekwa - OTP kwa %s: %s (dev mode)",
            to_email, otp
        )

        return False

    try:

        message = MIMEText(
            f"Nambari yako ya uthibitisho (OTP) ni: {otp}\n"
            "Haitumiki baada ya dakika 10.\n\nNjiaMauzo Afrika"
        )

        message["Subject"] = "Nambari ya Uthibitisho - NjiaMauzo Afrika"
        message["From"] = SMTP_FROM
        message["To"] = to_email

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:

            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to_email], message.as_string())

        return True

    except Exception as error:

        logger.warning("Email OTP error: %s", error)
        return False


def send_sms_otp(to_phone, otp):

    if not (SMS_API_URL and SMS_API_KEY):

        logger.warning(
            "SMS gateway haijawekwa - OTP kwa %s: %s (dev mode)",
            to_phone, otp
        )

        return False

    try:

        payload = json.dumps({
            "sender": SMS_SENDER_ID,
            "to": to_phone,
            "message": f"Nambari yako ya uthibitisho NjiaMauzo Afrika: {otp}"
        }).encode("utf-8")

        req = urllib.request.Request(
            SMS_API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {SMS_API_KEY}"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=8) as response:
            return 200 <= response.status < 300

    except Exception as error:

        logger.warning("SMS OTP error: %s", error)
        return False


def send_whatsapp_otp(to_phone, otp):

    if not (WHATSAPP_API_URL and WHATSAPP_API_TOKEN):

        logger.warning(
            "WhatsApp API haijawekwa - OTP kwa %s: %s (dev mode)",
            to_phone, otp
        )

        return False

    try:

        payload = json.dumps({
            "to": to_phone,
            "message": f"🔐 Nambari yako ya uthibitisho NjiaMauzo Afrika: {otp}"
        }).encode("utf-8")

        req = urllib.request.Request(
            WHATSAPP_API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {WHATSAPP_API_TOKEN}"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=8) as response:
            return 200 <= response.status < 300

    except Exception as error:

        logger.warning("WhatsApp OTP error: %s", error)
        return False


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():

    return render_template("index.html")


# ============================================================
# CSRF TOKEN
# ============================================================

@app.route("/api/csrf-token", methods=["GET"])
def csrf():

    return jsonify({
        "success": True,
        "csrf_token": csrf_token()
    })


# ============================================================
# REGISTER  (requires CAPTCHA)
# ============================================================

@app.route("/api/register", methods=["POST"])
@rate_limit("register", 5, 600)
def register():

    data = request.get_json(silent=True) or {}

    email = sanitize_text(data.get("email"), 150).lower()
    password = str(data.get("password") or "")
    name = sanitize_text(data.get("name"), 100)
    phone = sanitize_text(data.get("phone"), 30)
    captcha_id = data.get("captcha_id")
    captcha_answer = data.get("captcha_answer")

    if not check_captcha(captcha_id, captcha_answer):

        return jsonify({
            "success": False,
            "message": "Jibu la uthibitisho (CAPTCHA) si sahihi.",
            **make_captcha()
        }), 400

    if not all([email, password, name, phone]):

        return jsonify({
            "success": False,
            "message": "Jaza taarifa zote."
        }), 400

    if not valid_email(email):

        return jsonify({
            "success": False,
            "message": "Barua pepe si sahihi."
        }), 400

    if len(password) < 8:

        return jsonify({
            "success": False,
            "message": "Nywila iwe na angalau herufi 8."
        }), 400

    existing = fetchone(
        "SELECT id FROM users WHERE email = ?",
        (email,)
    )

    if existing:

        return jsonify({
            "success": False,
            "message": "Barua pepe tayari ipo."
        }), 409

    execute(
        """
        INSERT INTO users (email, password, name, phone, joined)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            email,
            generate_password_hash(password),
            name,
            phone,
            datetime.now(timezone.utc).isoformat()
        ),
        commit=True
    )

    log_activity("register", name, f"{name} amejiunga na NjiaMauzo Afrika 🎉")

    session.clear()
    session["user"] = email
    session["csrf_token"] = secrets.token_urlsafe(32)

    return jsonify({
        "success": True,
        "message": "Umesajiliwa!",
        "user": {"email": email, "name": name, "phone": phone},
        "csrf_token": session["csrf_token"]
    })


# ============================================================
# LOGIN
# ============================================================

@app.route("/api/login", methods=["POST"])
@rate_limit("login", 10, 300)
def login():

    data = request.get_json(silent=True) or {}

    email = sanitize_text(data.get("email"), 150).lower()
    password = str(data.get("password") or "")

    user = fetchone(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    )

    if not user:

        return jsonify({
            "success": False,
            "message": "Mtumiaji hajapatikana."
        }), 401

    if not user["is_active"]:

        return jsonify({
            "success": False,
            "message": "Akaunti imezimwa."
        }), 403

    if not check_password_hash(user["password"], password):

        failures = int(user["failed_logins"] or 0) + 1

        execute(
            "UPDATE users SET failed_logins = ? WHERE email = ?",
            (failures, email),
            commit=True
        )

        return jsonify({
            "success": False,
            "message": "Nywila si sahihi."
        }), 401

    execute(
        "UPDATE users SET failed_logins = 0 WHERE email = ?",
        (email,),
        commit=True
    )

    session.clear()
    session["user"] = email
    session["csrf_token"] = secrets.token_urlsafe(32)

    return jsonify({
        "success": True,
        "message": "Umeingia!",
        "user": {
            "email": email,
            "name": user["name"],
            "phone": user["phone"],
            "role": user["role"]
        },
        "must_change_password": bool(user["must_change_password"]),
        "csrf_token": session["csrf_token"]
    })


# ============================================================
# LOGOUT
# ============================================================

@app.route("/api/logout", methods=["POST"])
@login_required
def logout():

    session.clear()

    return jsonify({"success": True, "message": "Umetoka."})


# ============================================================
# CURRENT USER
# ============================================================

@app.route("/api/me", methods=["GET"])
def me():

    email = session.get("user")

    if not email:
        return jsonify({"success": False}), 401

    user = fetchone(
        """
        SELECT email, name, phone, role, must_change_password
        FROM users WHERE email = ?
        """,
        (email,)
    )

    if not user:
        session.clear()
        return jsonify({"success": False}), 401

    return jsonify({"success": True, "user": dict(user)})


# ============================================================
# PASSWORD CHANGE (logged-in users, also used to clear
# must_change_password after admin's first login)
# ============================================================

@app.route("/api/password/change", methods=["POST"])
@login_required
@rate_limit("password_change", 10, 300)
def change_password():

    data = request.get_json(silent=True) or {}

    current_password = str(data.get("current_password") or "")
    new_password = str(data.get("new_password") or "")

    email = session.get("user")
    user = fetchone("SELECT * FROM users WHERE email = ?", (email,))

    if not user:
        return jsonify({"success": False, "message": "Mtumiaji hajapatikana."}), 404

    if not check_password_hash(user["password"], current_password):

        return jsonify({
            "success": False,
            "message": "Nywila ya sasa si sahihi."
        }), 401

    if len(new_password) < 8:

        return jsonify({
            "success": False,
            "message": "Nywila mpya iwe na angalau herufi 8."
        }), 400

    execute(
        """
        UPDATE users
        SET password = ?, must_change_password = 0
        WHERE email = ?
        """,
        (generate_password_hash(new_password), email),
        commit=True
    )

    return jsonify({"success": True, "message": "Nywila imebadilishwa."})


# ============================================================
# FORGOT PASSWORD -> REQUEST OTP  (email / sms / whatsapp)
# ============================================================

@app.route("/api/password/forgot", methods=["POST"])
@rate_limit("password_forgot", 5, 600)
def forgot_password():

    data = request.get_json(silent=True) or {}

    email = sanitize_text(data.get("email"), 150).lower()
    channel = sanitize_text(data.get("channel"), 20).lower() or "email"

    if channel not in {"email", "sms", "whatsapp"}:
        channel = "email"

    user = fetchone("SELECT * FROM users WHERE email = ?", (email,))

    generic_response = {
        "success": True,
        "message": (
            "Kama akaunti ipo, nambari ya uthibitisho (OTP) "
            "imetumwa kupitia " + channel + "."
        )
    }

    if not user:
        # do not reveal whether the account exists
        return jsonify(generic_response)

    otp = f"{random.randint(0, 999999):06d}"

    reset_id = str(uuid.uuid4())

    execute(
        """
        INSERT INTO password_resets
        (id, email, otp_hash, channel, expires, created)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            reset_id,
            email,
            generate_password_hash(otp),
            channel,
            (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            datetime.now(timezone.utc).isoformat()
        ),
        commit=True
    )

    if channel == "email":
        send_email_otp(email, otp)
    elif channel == "sms":
        send_sms_otp(user["phone"], otp)
    else:
        send_whatsapp_otp(user["phone"], otp)

    generic_response["reset_id"] = reset_id

    return jsonify(generic_response)


# ============================================================
# FORGOT PASSWORD -> VERIFY OTP AND SET NEW PASSWORD
# ============================================================

@app.route("/api/password/reset", methods=["POST"])
@rate_limit("password_reset", 10, 600)
def reset_password():

    data = request.get_json(silent=True) or {}

    reset_id = sanitize_text(data.get("reset_id"), 60)
    otp = sanitize_text(data.get("otp"), 10)
    new_password = str(data.get("new_password") or "")

    record = fetchone(
        "SELECT * FROM password_resets WHERE id = ?",
        (reset_id,)
    )

    if not record or record["used"]:

        return jsonify({
            "success": False,
            "message": "Ombi la kubadilisha nywila si sahihi."
        }), 400

    expires = datetime.fromisoformat(record["expires"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires:

        return jsonify({
            "success": False,
            "message": "Muda wa OTP umeisha. Omba OTP mpya."
        }), 400

    if record["attempts"] >= 5:

        return jsonify({
            "success": False,
            "message": "Umejaribu mara nyingi sana. Omba OTP mpya."
        }), 429

    if not check_password_hash(record["otp_hash"], otp):

        execute(
            "UPDATE password_resets SET attempts = attempts + 1 WHERE id = ?",
            (reset_id,),
            commit=True
        )

        return jsonify({
            "success": False,
            "message": "OTP si sahihi."
        }), 400

    if len(new_password) < 8:

        return jsonify({
            "success": False,
            "message": "Nywila mpya iwe na angalau herufi 8."
        }), 400

    execute(
        """
        UPDATE users
        SET password = ?, must_change_password = 0, failed_logins = 0
        WHERE email = ?
        """,
        (generate_password_hash(new_password), record["email"]),
        commit=True
    )

    execute(
        "UPDATE password_resets SET used = 1 WHERE id = ?",
        (reset_id,),
        commit=True
    )

    return jsonify({"success": True, "message": "Nywila imebadilishwa. Sasa ingia."})


# ============================================================
# PRODUCTS  (with optional distance sorting)
# ============================================================

@app.route("/api/products", methods=["GET"])
@rate_limit("products", 60, 60)
def products():

    rows = fetchall(
        "SELECT * FROM products ORDER BY id DESC LIMIT 100"
    )

    items = [dict(row) for row in rows]

    user_lat = request.args.get("lat")
    user_lon = request.args.get("lon")

    if user_lat and user_lon:

        for item in items:

            item["distance_km"] = haversine_km(
                user_lat, user_lon, item.get("lat"), item.get("lon")
            )

        items.sort(
            key=lambda p: (
                p["distance_km"] is None,
                p["distance_km"] if p["distance_km"] is not None else 0
            )
        )

    return jsonify({"success": True, "products": items})


# ============================================================
# AI PRODUCT FINDER
# ============================================================

@app.route("/api/ai-products", methods=["GET"])
@rate_limit("ai_products", 30, 60)
def ai_products():

    query = sanitize_text(request.args.get("q", ""), 100).lower()

    rows = fetchall(
        "SELECT * FROM products ORDER BY id DESC LIMIT 100"
    )

    output = []

    for row in rows:

        searchable = (
            f"{row['title']} {row['description']} "
            f"{row['location']} {row['category']}"
        ).lower()

        if query and query not in searchable:
            continue

        output.append({
            "id": row["id"],
            "jina": row["title"],
            "title": row["title"],
            "picha": row["image"],
            "image": row["image"],
            "chanzo": row["location"],
            "location": row["location"],
            "bei": f"TZS {row['real_price']:,.0f}",
            "realPrice": row["real_price"],
            "description": row["description"],
            "seller_name": row["seller_name"],
            "category": row["category"]
        })

    return jsonify({"success": True, "products": output[:20]})


# ============================================================
# LIKES
# ============================================================

@app.route("/api/products/<int:product_id>/like", methods=["POST"])
@login_required
@rate_limit("like", 60, 60)
def like_product(product_id):

    email = session.get("user")

    product = fetchone("SELECT * FROM products WHERE id = ?", (product_id,))

    if not product:
        return jsonify({"success": False, "message": "Bidhaa haijapatikana."}), 404

    existing = fetchone(
        "SELECT id FROM likes WHERE product_id = ? AND user_email = ?",
        (product_id, email)
    )

    if existing:

        execute(
            "DELETE FROM likes WHERE product_id = ? AND user_email = ?",
            (product_id, email),
            commit=True
        )

        execute(
            "UPDATE products SET likes = MAX(likes - 1, 0) WHERE id = ?",
            (product_id,),
            commit=True
        )

        liked = False

    else:

        execute(
            "INSERT INTO likes (product_id, user_email, created) VALUES (?, ?, ?)",
            (product_id, email, datetime.now(timezone.utc).isoformat()),
            commit=True
        )

        execute(
            "UPDATE products SET likes = likes + 1 WHERE id = ?",
            (product_id,),
            commit=True
        )

        liked = True

        user = fetchone("SELECT name FROM users WHERE email = ?", (email,))

        log_activity(
            "like",
            user["name"] if user else email,
            f"{(user['name'] if user else email)} amependa \"{product['title']}\" ❤️",
            product_id=product_id,
            product_title=product["title"]
        )

    updated = fetchone("SELECT likes FROM products WHERE id = ?", (product_id,))

    return jsonify({
        "success": True,
        "liked": liked,
        "likes": updated["likes"]
    })


# ============================================================
# FOLLOW (follow a seller)
# ============================================================

@app.route("/api/sellers/<seller_id>/follow", methods=["POST"])
@login_required
@rate_limit("follow", 60, 60)
def follow_seller(seller_id):

    email = session.get("user")

    existing = fetchone(
        "SELECT id FROM follows WHERE follower_email = ? AND seller_id = ?",
        (email, seller_id)
    )

    if existing:

        execute(
            "DELETE FROM follows WHERE follower_email = ? AND seller_id = ?",
            (email, seller_id),
            commit=True
        )

        following = False

    else:

        execute(
            "INSERT INTO follows (follower_email, seller_id, created) VALUES (?, ?, ?)",
            (email, seller_id, datetime.now(timezone.utc).isoformat()),
            commit=True
        )

        following = True

        user = fetchone("SELECT name FROM users WHERE email = ?", (email,))
        seller_product = fetchone(
            "SELECT seller_name FROM products WHERE seller_id = ? LIMIT 1",
            (seller_id,)
        )

        seller_name = seller_product["seller_name"] if seller_product else seller_id

        log_activity(
            "follow",
            user["name"] if user else email,
            f"{(user['name'] if user else email)} anamfuata {seller_name} 👥"
        )

    count = fetchone(
        "SELECT COUNT(*) AS c FROM follows WHERE seller_id = ?",
        (seller_id,)
    )

    return jsonify({
        "success": True,
        "following": following,
        "followers": count["c"]
    })


# ============================================================
# LIVE ACTIVITY FEED
# ============================================================

@app.route("/api/activity", methods=["GET"])
@rate_limit("activity", 60, 60)
def activity_feed():

    since_id = request.args.get("since_id", type=int)

    if since_id:

        rows = fetchall(
            """
            SELECT * FROM activity_feed
            WHERE id > ?
            ORDER BY id DESC LIMIT 30
            """,
            (since_id,)
        )

    else:

        rows = fetchall(
            "SELECT * FROM activity_feed ORDER BY id DESC LIMIT 15"
        )

    return jsonify({
        "success": True,
        "activity": [dict(row) for row in rows]
    })


# ============================================================
# BOT CHAT
# ============================================================

@app.route("/api/chat", methods=["POST"])
@rate_limit("chat", 40, 60)
def chat():

    data = request.get_json(silent=True) or {}

    message = sanitize_text(data.get("message"), 500)

    if not message:

        return jsonify({
            "success": False,
            "reply": "Tafadhali andika ujumbe."
        }), 400

    reply = generate_local_reply(message)

    notify_admin_whatsapp(message, reply)

    return jsonify({"success": True, "reply": reply})


@app.route("/api/bot-chat", methods=["POST"])
@rate_limit("bot_chat", 40, 60)
def bot_chat():

    return chat()


def generate_local_reply(message):

    msg = message.lower()

    if any(word in msg for word in ["malipo", "lipa", "pesa", "ada"]):

        return (
            "Ada ya huduma ya kutafutiwa bidhaa ni TZS 3,000. "
            "Tunapokea M-Pesa, Halotel na Airtel Money."
        )

    if any(word in msg for word in ["bei", "gharama", "thamani"]):

        return (
            "NjiaMauzo Afrika inakusaidia kulinganisha bei na "
            "kutafuta bidhaa kulingana na zao, eneo na kiasi."
        )

    if any(word in msg for word in ["mazao", "mahindi", "ufuta", "kahawa", "maharage", "karanga", "mpunga"]):

        return (
            "Tunaweza kukusaidia kutafuta zao, kiasi, eneo na bei. "
            "Mfano: Natafuta tani 20 za ufuta Ruvuma chini ya TZS 3,200/kg."
        )

    if any(word in msg for word in ["whatsapp", "simu", "wasiliana"]):

        return (
            "Karibu NjiaMauzo Afrika. Unaweza kutumia huduma ya "
            "kutafutiwa bidhaa hapa kwenye mfumo."
        )

    if any(word in msg for word in ["habari", "hujambo", "mambo", "hello"]):

        return "Habari! 👋 Karibu NjiaMauzo Afrika. Unatafuta bidhaa au zao gani?"

    if any(word in msg for word in ["asante", "shukrani"]):

        return "Karibu sana! Nipo hapa kukusaidia."

    return (
        "Nimepokea ujumbe wako. Niambie zao unalotafuta, "
        "kiasi, eneo au bei unayotaka."
    )


# ============================================================
# PAYMENT NUMBERS
# ============================================================

@app.route("/api/service/payment-number", methods=["GET"])
def service_payment_number():

    return jsonify({
        "success": True,
        "fee": SERVICE_FEE,
        "currency": "TZS",
        "numbers": {
            "mpesa": PAYMENT_MPESA,
            "halotel": PAYMENT_HALOTEL,
            "airtel": PAYMENT_AIRTEL
        }
    })


@app.route("/api/payment/numbers", methods=["GET"])
def payment_numbers():

    return service_payment_number()


def get_payment_number(method):

    method = (method or "").lower()

    if "mpesa" in method or "vodacom" in method:
        return PAYMENT_MPESA

    if "halotel" in method or "tigo" in method:
        return PAYMENT_HALOTEL

    if "airtel" in method:
        return PAYMENT_AIRTEL

    return None


# ============================================================
# PAYMENT REQUEST
# ============================================================

@app.route("/api/payment/request", methods=["POST"])
@login_required
@rate_limit("payment_request", 10, 300)
def payment_request():

    data = request.get_json(silent=True) or {}

    simu = sanitize_text(data.get("simu"), 30)
    njia = sanitize_text(data.get("njia"), 50)
    product_id = data.get("product_id")

    try:
        kiasi = int(data.get("kiasi", SERVICE_FEE))
    except (TypeError, ValueError):

        return jsonify({"success": False, "message": "Kiasi si sahihi."}), 400

    if kiasi != SERVICE_FEE:

        return jsonify({
            "success": False,
            "message": "Ada ya huduma ni TZS 3,000."
        }), 400

    payment_number = get_payment_number(njia)

    if not payment_number:

        return jsonify({
            "success": False,
            "message": "Chagua M-Pesa, Halotel au Airtel Money."
        }), 400

    if not simu:

        return jsonify({"success": False, "message": "Weka namba ya simu."}), 400

    order_id = str(uuid.uuid4())

    execute(
        """
        INSERT INTO orders
        (id, user_email, simu, njia, kiasi, product_id, status, created)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            session.get("user"),
            simu,
            njia,
            SERVICE_FEE,
            str(product_id) if product_id else None,
            "PENDING",
            datetime.now(timezone.utc).isoformat()
        ),
        commit=True
    )

    notify_admin_whatsapp(
        f"Payment mpya: {order_id}",
        f"{njia} / {simu} / TZS {SERVICE_FEE:,}"
    )

    return jsonify({
        "success": True,
        "message": (
            f"Tuma TZS {SERVICE_FEE:,} kwenda {payment_number} kupitia {njia}."
        ),
        "order_id": order_id,
        "payment_number": payment_number,
        "amount": SERVICE_FEE,
        "status": "PENDING"
    })


# ============================================================
# PAYMENT STATUS
# ============================================================

@app.route("/api/payment/status/<order_id>", methods=["GET"])
@login_required
def payment_status(order_id):

    order = fetchone(
        "SELECT * FROM orders WHERE id = ? AND user_email = ?",
        (order_id, session.get("user"))
    )

    if not order:

        return jsonify({"success": False, "message": "Agizo halipatikani."}), 404

    return jsonify({"success": True, "order": dict(order)})


# ============================================================
# ADMIN PAYMENT VERIFICATION
# ============================================================

@app.route("/api/admin/payment/<order_id>/verify", methods=["POST"])
@admin_required
def verify_payment(order_id):

    order = fetchone("SELECT id FROM orders WHERE id = ?", (order_id,))

    if not order:

        return jsonify({"success": False, "message": "Agizo halipatikani."}), 404

    execute(
        "UPDATE orders SET status = 'VERIFIED' WHERE id = ?",
        (order_id,),
        commit=True
    )

    return jsonify({"success": True, "status": "VERIFIED"})


# ============================================================
# COMMENTS
# ============================================================

@app.route("/api/comments/<int:product_id>", methods=["GET"])
def get_comments(product_id):

    rows = fetchall(
        "SELECT * FROM comments WHERE product_id = ? ORDER BY time DESC",
        (product_id,)
    )

    return jsonify({
        "success": True,
        "comments": [dict(row) for row in rows]
    })


@app.route("/api/comments/<int:product_id>", methods=["POST"])
@login_required
@rate_limit("comments", 20, 60)
def add_comment(product_id):

    data = request.get_json(silent=True) or {}

    text = sanitize_text(data.get("text"), 500)

    if not text:

        return jsonify({"success": False, "message": "Maoni hayawezi kuwa tupu."}), 400

    user = fetchone(
        "SELECT name FROM users WHERE email = ?",
        (session.get("user"),)
    )

    if not user:
        return jsonify({"success": False}), 401

    product = fetchone("SELECT title FROM products WHERE id = ?", (product_id,))

    comment = {
        "id": str(uuid.uuid4()),
        "product_id": product_id,
        "author": user["name"],
        "text": text,
        "time": datetime.now().strftime("%d/%m/%Y %H:%M")
    }

    execute(
        """
        INSERT INTO comments (id, product_id, author, text, time)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            comment["id"], product_id, comment["author"],
            comment["text"], comment["time"]
        ),
        commit=True
    )

    if product:

        log_activity(
            "comment",
            user["name"],
            f"{user['name']} ametoa maoni kwenye \"{product['title']}\" 💬",
            product_id=product_id,
            product_title=product["title"]
        )

    return jsonify({"success": True, "comment": comment})


# ============================================================
# WHATSAPP ADMIN
# ============================================================

def notify_admin_whatsapp(user_message, bot_reply):

    if not (WHATSAPP_API_URL and WHATSAPP_API_TOKEN):
        return False

    payload = {
        "to": ADMIN_WHATSAPP_NUMBER,
        "message": (
            "🔔 NJIA MAUZO AFRIKA\n\n"
            "👤 Ujumbe:\n"
            f"{sanitize_text(user_message, 1000)}\n\n"
            "🤖 Mfumo:\n"
            f"{sanitize_text(bot_reply, 1000)}\n\n"
            "💰 Ada: TZS 3,000"
        )
    }

    try:

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            WHATSAPP_API_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {WHATSAPP_API_TOKEN}"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            return 200 <= response.status < 300

    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as error:

        logger.warning("WhatsApp error: %s", error)
        return False


@app.route("/api/notify-admin", methods=["POST"])
@rate_limit("notify_admin", 20, 60)
def notify_admin():

    data = request.get_json(silent=True) or {}

    user_message = sanitize_text(data.get("user_message"), 1000)
    bot_reply = sanitize_text(data.get("bot_reply"), 1000)

    if not user_message:

        return jsonify({"success": False, "message": "Ujumbe haupo."}), 400

    ok = notify_admin_whatsapp(user_message, bot_reply)

    return jsonify({"success": ok})


# ============================================================
# HEALTH
# ============================================================

@app.route("/health", methods=["GET"])
@app.route("/api/health", methods=["GET"])
def health():

    try:

        fetchone("SELECT 1")

        return jsonify({
            "success": True,
            "service": "NJIA MAUZO AFRIKA",
            "status": "imara",
            "database": DB_TYPE,
            "fee": SERVICE_FEE
        })

    except Exception:

        logger.exception("Health check error")

        return jsonify({"success": False, "status": "error"}), 503


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(413)
def too_large(error):

    return jsonify({"success": False, "message": "Request ni kubwa sana."}), 413


@app.errorhandler(404)
def not_found(error):

    if request.path.startswith("/api/"):

        return jsonify({"success": False, "message": "Endpoint haijapatikana."}), 404

    return "Ukurasa haujapatikana.", 404


@app.errorhandler(500)
def server_error(error):

    logger.exception("Internal server error")

    return jsonify({"success": False, "message": "Server imepata hitilafu."}), 500


# ============================================================
# STARTUP
# ============================================================

with app.app_context():

    init_db()
    seed_products()
    seed_admin()


# ============================================================
# PRODUCTION START
# ============================================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", "5000"))

    app.run(host="0.0.0.0", port=port, debug=False)
