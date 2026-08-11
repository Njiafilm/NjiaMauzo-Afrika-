# ============================================================
# NJIA MAUZO AFRIKA
# Professional Flask Backend
# ============================================================

import os
import re
import json
import time
import uuid
import secrets
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
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
        "geolocation=()"
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
        "title":
            "Mahindi ya Ubora wa Juu – Tani 50",

        "real_price":
            850000,

        "description":
            "Mahindi yaliyovunwa hivi karibuni "
            "kutoka shamba la Morogoro.",

        "image":
            "https://images.unsplash.com/"
            "photo-1625246333195-78d9c38ad449"
            "?w=800",

        "seller_id":
            "101",

        "seller_name":
            "Juma Mkulima",

        "location":
            "Morogoro, Mvomero",

        "category":
            "mazao",

        "alama":
            "Mazao",

        "likes":
            12
    },

    {
        "title":
            "Mtaalamu wa Kilimo – Ushauri wa Shamba",

        "real_price":
            150000,

        "description":
            "Mtaalamu wa kilimo cha kisasa.",

        "image":
            "https://images.unsplash.com/"
            "photo-1592982537447-7440770cbfc9"
            "?w=800",

        "seller_id":
            "102",

        "seller_name":
            "Dkt. Amina Hassan",

        "location":
            "Arusha, Njiro",

        "category":
            "mtaalamu",

        "alama":
            "Mtaalamu",

        "likes":
            8
    },

    {
        "title":
            "Kahawa Arabica – Kilimanjaro Grade AA",

        "real_price":
            1200000,

        "description":
            "Kahawa bora ya Kilimanjaro, Grade AA.",

        "image":
            "https://images.unsplash.com/"
            "photo-1559056199-641a0ac8b55e"
            "?w=800",

        "seller_id":
            "103",

        "seller_name":
            "Kilimanjaro Coffee Co-op",

        "location":
            "Moshi, Kilimanjaro",

        "category":
            "mazao",

        "alama":
            "Mazao",

        "likes":
            21
    },

    {
        "title":
            "Huduma ya Usafirishaji wa Mazao",

        "real_price":
            350000,

        "description":
            "Lori za kusafirisha mazao "
            "kutoka shambani hadi soko.",

        "image":
            "https://images.unsplash.com/"
            "photo-1601584115197-04ecc0da31d7"
            "?w=800",

        "seller_id":
            "104",

        "seller_name":
            "Safari Mazao Ltd",

        "location":
            "Dar es Salaam",

        "category":
            "huduma",

        "alama":
            "Huduma",

        "likes":
            5
    },

    {
        "title":
            "Trekta ya Kukodi – John Deere",

        "real_price":
            250000,

        "description":
            "Trekta ya kisasa inayopatikana "
            "kwa kukodi.",

        "image":
            "https://images.unsplash.com/"
            "photo-1530267981375-f0de937f5f13"
            "?w=800",

        "seller_id":
            "105",

        "seller_name":
            "Vifaa vya Kilimo TZ",

        "location":
            "Dodoma",

        "category":
            "vifaa",

        "alama":
            "Vifaa",

        "likes":
            15
    },

    {
        "title":
            "Nyanya za Chafu – Tani 20",

        "real_price":
            480000,

        "description":
            "Nyanya safi zilizopandwa kwenye chafu.",

        "image":
            "https://images.unsplash.com/"
            "photo-1546094096-0df4bcaaa337"
            "?w=800",

        "seller_id":
            "106",

        "seller_name":
            "Green House Farm",

        "location":
            "Iringa",

        "category":
            "mazao",

        "alama":
            "Mazao",

        "likes":
            9
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
                title,
                real_price,
                description,
                image,
                seller_id,
                seller_name,
                location,
                category,
                alama,
                likes,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                product["title"],
                product["real_price"],
                product["description"],
                product["image"],
                product["seller_id"],
                product["seller_name"],
                product["location"],
                product["category"],
                product["alama"],
                product["likes"],
                datetime.now(
                    timezone.utc
                ).isoformat()
            )
        )

    db().commit()


# ============================================================
# ADMIN SEED
# ============================================================

def seed_admin():

    email = os.environ.get(
        "ADMIN_EMAIL",
        ""
    ).strip().lower()

    password = os.environ.get(
        "ADMIN_PASSWORD",
        ""
    )

    if not email or not password:
        return

    existing = fetchone(
        "SELECT id FROM users WHERE email = ?",
        (email,)
    )

    if existing:
        return

    execute(
        """
        INSERT INTO users
        (
            email,
            password,
            name,
            phone,
            role,
            joined
        )
        VALUES (?, ?, ?, ?, 'admin', ?)
        """,
        (
            email,
            generate_password_hash(
                password
            ),
            "NjiaMauzo Admin",
            "",
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        commit=True
    )


# ============================================================
# AUTH DECORATORS
# ============================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        email = session.get(
            "user"
        )

        if not email:
            return jsonify({
                "success": False,
                "message":
                    "Ingia kwanza."
            }), 401

        return function(
            *args,
            **kwargs
        )

    return wrapper


def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        email = session.get(
            "user"
        )

        if not email:
            return jsonify({
                "success": False,
                "message":
                    "Ingia kwanza."
            }), 401

        user = fetchone(
            """
            SELECT role
            FROM users
            WHERE email = ?
            """,
            (email,)
        )

        if not user or user["role"] != "admin":

            return jsonify({
                "success": False,
                "message":
                    "Huna ruhusa ya admin."
            }), 403

        return function(
            *args,
            **kwargs
        )

    return wrapper


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# ============================================================
# CSRF TOKEN
# ============================================================

@app.route(
    "/api/csrf-token",
    methods=["GET"]
)
def csrf():

    return jsonify({
        "success": True,
        "csrf_token":
            csrf_token()
    })


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/api/register",
    methods=["POST"]
)
@rate_limit(
    "register",
    5,
    600
)
def register():

    data = request.get_json(
        silent=True
    ) or {}

    email = sanitize_text(
        data.get("email"),
        150
    ).lower()

    password = str(
        data.get("password") or ""
    )

    name = sanitize_text(
        data.get("name"),
        100
    )

    phone = sanitize_text(
        data.get("phone"),
        30
    )

    if not all([
        email,
        password,
        name,
        phone
    ]):

        return jsonify({
            "success": False,
            "message":
                "Jaza taarifa zote."
        }), 400

    if not valid_email(email):

        return jsonify({
            "success": False,
            "message":
                "Barua pepe si sahihi."
        }), 400

    if len(password) < 8:

        return jsonify({
            "success": False,
            "message":
                "Nywila iwe na angalau herufi 8."
        }), 400

    existing = fetchone(
        """
        SELECT id
        FROM users
        WHERE email = ?
        """,
        (email,)
    )

    if existing:

        return jsonify({
            "success": False,
            "message":
                "Barua pepe tayari ipo."
        }), 409

    execute(
        """
        INSERT INTO users
        (
            email,
            password,
            name,
            phone,
            joined
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            email,
            generate_password_hash(
                password
            ),
            name,
            phone,
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        commit=True
    )

    session.clear()

    session["user"] = email

    session["csrf_token"] = (
        secrets.token_urlsafe(32)
    )

    return jsonify({
        "success": True,
        "message":
            "Umesajiliwa!",
        "user": {
            "email": email,
            "name": name,
            "phone": phone
        },
        "csrf_token":
            session["csrf_token"]
    })


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/api/login",
    methods=["POST"]
)
@rate_limit(
    "login",
    10,
    300
)
def login():

    data = request.get_json(
        silent=True
    ) or {}

    email = sanitize_text(
        data.get("email"),
        150
    ).lower()

    password = str(
        data.get("password") or ""
    )

    user = fetchone(
        """
        SELECT *
        FROM users
        WHERE email = ?
        """,
        (email,)
    )

    if not user:

        return jsonify({
            "success": False,
            "message":
                "Mtumiaji hajapatikana."
        }), 401

    if not user["is_active"]:

        return jsonify({
            "success": False,
            "message":
                "Akaunti imezimwa."
        }), 403

    if not check_password_hash(
        user["password"],
        password
    ):

        failures = (
            int(
                user["failed_logins"] or 0
            ) + 1
        )

        execute(
            """
            UPDATE users
            SET failed_logins = ?
            WHERE email = ?
            """,
            (
                failures,
                email
            ),
            commit=True
        )

        return jsonify({
            "success": False,
            "message":
                "Nywila si sahihi."
        }), 401

    execute(
        """
        UPDATE users
        SET failed_logins = 0
        WHERE email = ?
        """,
        (email,),
        commit=True
    )

    session.clear()

    session["user"] = email

    session["csrf_token"] = (
        secrets.token_urlsafe(32)
    )

    return jsonify({
        "success": True,
        "message":
            "Umeingia!",
        "user": {
            "email": email,
            "name": user["name"],
            "phone": user["phone"]
        },
        "csrf_token":
            session["csrf_token"]
    })


# ============================================================
# LOGOUT
# ============================================================

@app.route(
    "/api/logout",
    methods=["POST"]
)
@login_required
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message":
            "Umetoka."
    })


# ============================================================
# CURRENT USER
# ============================================================

@app.route(
    "/api/me",
    methods=["GET"]
)
def me():

    email = session.get(
        "user"
    )

    if not email:

        return jsonify({
            "success": False
        }), 401

    user = fetchone(
        """
        SELECT email, name, phone, role
        FROM users
        WHERE email = ?
        """,
        (email,)
    )

    if not user:

        session.clear()

        return jsonify({
            "success": False
        }), 401

    return jsonify({
        "success": True,
        "user": dict(user)
    })


# ============================================================
# PRODUCTS
# ============================================================

@app.route(
    "/api/products",
    methods=["GET"]
)
@rate_limit(
    "products",
    60,
    60
)
def products():

    rows = fetchall(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        LIMIT 100
        """
    )

    return jsonify({
        "success": True,
        "products": [
            dict(row)
            for row in rows
        ]
    })


# ============================================================
# AI PRODUCT FINDER
# ============================================================

@app.route(
    "/api/ai-products",
    methods=["GET"]
)
@rate_limit(
    "ai_products",
    30,
    60
)
def ai_products():

    query = sanitize_text(
        request.args.get(
            "q",
            ""
        ),
        100
    ).lower()

    rows = fetchall(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        LIMIT 100
        """
    )

    output = []

    for row in rows:

        searchable = (
            f"{row['title']} "
            f"{row['description']} "
            f"{row['location']} "
            f"{row['category']}"
        ).lower()

        if query and query not in searchable:
            continue

        output.append({
            "id":
                row["id"],

            "jina":
                row["title"],

            "title":
                row["title"],

            "picha":
                row["image"],

            "image":
                row["image"],

            "chanzo":
                row["location"],

            "location":
                row["location"],

            "bei":
                f"TZS "
                f"{row['real_price']:,.0f}",

            "realPrice":
                row["real_price"],

            "description":
                row["description"],

            "seller_name":
                row["seller_name"],

            "category":
                row["category"]
        })

    return jsonify({
        "success": True,
        "products":
            output[:20]
    })


# ============================================================
# BOT CHAT
# ============================================================

@app.route(
    "/api/chat",
    methods=["POST"]
)
@rate_limit(
    "chat",
    40,
    60
)
def chat():

    data = request.get_json(
        silent=True
    ) or {}

    message = sanitize_text(
        data.get("message"),
        500
    )

    if not message:

        return jsonify({
            "success": False,
            "reply":
                "Tafadhali andika ujumbe."
        }), 400

    reply = generate_local_reply(
        message
    )

    notify_admin_whatsapp(
        message,
        reply
    )

    return jsonify({
        "success": True,
        "reply": reply
    })


@app.route(
    "/api/bot-chat",
    methods=["POST"]
)
@rate_limit(
    "bot_chat",
    40,
    60
)
def bot_chat():

    return chat()


def generate_local_reply(message):

    msg = message.lower()

    if any(
        word in msg
        for word in [
            "malipo",
            "lipa",
            "pesa",
            "ada"
        ]
    ):

        return (
            "Ada ya huduma ya kutafutiwa "
            "bidhaa ni TZS 3,000. "
            "Tunapokea M-Pesa, Halotel "
            "na Airtel Money."
        )

    if any(
        word in msg
        for word in [
            "bei",
            "gharama",
            "thamani"
        ]
    ):

        return (
            "NjiaMauzo Afrika inakusaidia "
            "kulinganisha bei na kutafuta "
            "bidhaa kulingana na zao, "
            "eneo na kiasi."
        )

    if any(
        word in msg
        for word in [
            "mazao",
            "mahindi",
            "ufuta",
            "kahawa",
            "maharage",
            "karanga",
            "mpunga"
        ]
    ):

        return (
            "Tunaweza kukusaidia kutafuta "
            "zao, kiasi, eneo na bei. "
            "Mfano: Natafuta tani 20 za "
            "ufuta Ruvuma chini ya "
            "TZS 3,200/kg."
        )

    if any(
        word in msg
        for word in [
            "whatsapp",
            "simu",
            "wasiliana"
        ]
    ):

        return (
            "Karibu NjiaMauzo Afrika. "
            "Unaweza kutumia huduma ya "
            "kutafutiwa bidhaa hapa kwenye mfumo."
        )

    if any(
        word in msg
        for word in [
            "habari",
            "hujambo",
            "mambo",
            "hello"
        ]
    ):

        return (
            "Habari! 👋 Karibu NjiaMauzo Afrika. "
            "Unatafuta bidhaa au zao gani?"
        )

    if any(
        word in msg
        for word in [
            "asante",
            "shukrani"
        ]
    ):

        return (
            "Karibu sana! Nipo hapa kukusaidia."
        )

    return (
        "Nimepokea ujumbe wako. "
        "Niambie zao unalotafuta, "
        "kiasi, eneo au bei unayotaka."
    )


# ============================================================
# PAYMENT NUMBERS
# ============================================================

@app.route(
    "/api/service/payment-number",
    methods=["GET"]
)
def service_payment_number():

    return jsonify({
        "success": True,
        "fee": SERVICE_FEE,
        "currency": "TZS",
        "numbers": {
            "mpesa":
                PAYMENT_MPESA,
            "halotel":
                PAYMENT_HALOTEL,
            "airtel":
                PAYMENT_AIRTEL
        }
    })


@app.route(
    "/api/payment/numbers",
    methods=["GET"]
)
def payment_numbers():

    return service_payment_number()


def get_payment_number(method):

    method = (
        method or ""
    ).lower()

    if (
        "mpesa" in method
        or "vodacom" in method
    ):
        return PAYMENT_MPESA

    if (
        "halotel" in method
        or "tigo" in method
    ):
        return PAYMENT_HALOTEL

    if "airtel" in method:

        return PAYMENT_AIRTEL

    return None


# ============================================================
# PAYMENT REQUEST
# ============================================================

@app.route(
    "/api/payment/request",
    methods=["POST"]
)
@login_required
@rate_limit(
    "payment_request",
    10,
    300
)
def payment_request():

    data = request.get_json(
        silent=True
    ) or {}

    simu = sanitize_text(
        data.get("simu"),
        30
    )

    njia = sanitize_text(
        data.get("njia"),
        50
    )

    product_id = data.get(
        "product_id"
    )

    try:

        kiasi = int(
            data.get(
                "kiasi",
                SERVICE_FEE
            )
        )

    except (
        TypeError,
        ValueError
    ):

        return jsonify({
            "success": False,
            "message":
                "Kiasi si sahihi."
        }), 400

    if kiasi != SERVICE_FEE:

        return jsonify({
            "success": False,
            "message":
                "Ada ya huduma ni TZS 3,000."
        }), 400

    payment_number = (
        get_payment_number(
            njia
        )
    )

    if not payment_number:

        return jsonify({
            "success": False,
            "message":
                "Chagua M-Pesa, "
                "Halotel au Airtel Money."
        }), 400

    if not simu:

        return jsonify({
            "success": False,
            "message":
                "Weka namba ya simu."
        }), 400

    order_id = str(
        uuid.uuid4()
    )

    execute(
        """
        INSERT INTO orders
        (
            id,
            user_email,
            simu,
            njia,
            kiasi,
            product_id,
            status,
            created
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            session.get("user"),
            simu,
            njia,
            SERVICE_FEE,
            str(product_id)
            if product_id
            else None,
            "PENDING",
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        commit=True
    )

    notify_admin_whatsapp(
        (
            f"Payment mpya: "
            f"{order_id}"
        ),
        (
            f"{njia} / "
            f"{simu} / "
            f"TZS {SERVICE_FEE:,}"
        )
    )

    return jsonify({
        "success": True,
        "message": (
            f"Tuma TZS "
            f"{SERVICE_FEE:,} kwenda "
            f"{payment_number} kupitia "
            f"{njia}."
        ),
        "order_id":
            order_id,
        "payment_number":
            payment_number,
        "amount":
            SERVICE_FEE,
        "status":
            "PENDING"
    })


# ============================================================
# PAYMENT STATUS
# ============================================================

@app.route(
    "/api/payment/status/<order_id>",
    methods=["GET"]
)
@login_required
def payment_status(
    order_id
):

    order = fetchone(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        AND user_email = ?
        """,
        (
            order_id,
            session.get("user")
        )
    )

    if not order:

        return jsonify({
            "success": False,
            "message":
                "Agizo halipatikani."
        }), 404

    return jsonify({
        "success": True,
        "order":
            dict(order)
    })


# ============================================================
# ADMIN PAYMENT VERIFICATION
# ============================================================

@app.route(
    "/api/admin/payment/<order_id>/verify",
    methods=["POST"]
)
@admin_required
def verify_payment(
    order_id
):

    order = fetchone(
        """
        SELECT id
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    )

    if not order:

        return jsonify({
            "success": False,
            "message":
                "Agizo halipatikani."
        }), 404

    execute(
        """
        UPDATE orders
        SET status = 'VERIFIED'
        WHERE id = ?
        """,
        (order_id,),
        commit=True
    )

    return jsonify({
        "success": True,
        "status":
            "VERIFIED"
    })


# ============================================================
# COMMENTS
# ============================================================

@app.route(
    "/api/comments/<int:product_id>",
    methods=["GET"]
)
def get_comments(
    product_id
):

    rows = fetchall(
        """
        SELECT *
        FROM comments
        WHERE product_id = ?
        ORDER BY time DESC
        """,
        (product_id,)
    )

    return jsonify({
        "success": True,
        "comments": [
            dict(row)
            for row in rows
        ]
    })


@app.route(
    "/api/comments/<int:product_id>",
    methods=["POST"]
)
@login_required
@rate_limit(
    "comments",
    20,
    60
)
def add_comment(
    product_id
):

    data = request.get_json(
        silent=True
    ) or {}

    text = sanitize_text(
        data.get("text"),
        500
    )

    if not text:

        return jsonify({
            "success": False,
            "message":
                "Maoni hayawezi kuwa tupu."
        }), 400

    user = fetchone(
        """
        SELECT name
        FROM users
        WHERE email = ?
        """,
        (
            session.get("user"),
        )
    )

    if not user:

        return jsonify({
            "success": False
        }), 401

    comment = {

        "id":
            str(uuid.uuid4()),

        "product_id":
            product_id,

        "author":
            user["name"],

        "text":
            text,

        "time":
            datetime.now().strftime(
                "%d/%m/%Y %H:%M"
            )
    }

    execute(
        """
        INSERT INTO comments
        (
            id,
            product_id,
            author,
            text,
            time
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            comment["id"],
            product_id,
            comment["author"],
            comment["text"],
            comment["time"]
        ),
        commit=True
    )

    return jsonify({
        "success": True,
        "comment":
            comment
    })


# ============================================================
# WHATSAPP ADMIN
# ============================================================

def notify_admin_whatsapp(
    user_message,
    bot_reply
):

    if not (
        WHATSAPP_API_URL
        and WHATSAPP_API_TOKEN
    ):

        return False

    payload = {

        "to":
            ADMIN_WHATSAPP_NUMBER,

        "message":
            (
                "🔔 NJIA MAUZO AFRIKA\n\n"
                "👤 Ujumbe:\n"
                f"{sanitize_text(user_message, 1000)}\n\n"
                "🤖 Mfumo:\n"
                f"{sanitize_text(bot_reply, 1000)}\n\n"
                "💰 Ada: TZS 3,000"
            )
    }

    try:

        body = json.dumps(
            payload,
            ensure_ascii=False
        ).encode(
            "utf-8"
        )

        req = urllib.request.Request(

            WHATSAPP_API_URL,

            data=body,

            headers={
                "Content-Type":
                    "application/json",

                "Authorization":
                    (
                        "Bearer "
                        f"{WHATSAPP_API_TOKEN}"
                    )
            },

            method="POST"
        )

        with urllib.request.urlopen(
            req,
            timeout=5
        ) as response:

            return (
                200
                <= response.status
                < 300
            )

    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError
    ) as error:

        logger.warning(
            "WhatsApp error: %s",
            error
        )

        return False


@app.route(
    "/api/notify-admin",
    methods=["POST"]
)
@rate_limit(
    "notify_admin",
    20,
    60
)
def notify_admin():

    data = request.get_json(
        silent=True
    ) or {}

    user_message = sanitize_text(
        data.get(
            "user_message"
        ),
        1000
    )

    bot_reply = sanitize_text(
        data.get(
            "bot_reply"
        ),
        1000
    )

    if not user_message:

        return jsonify({
            "success": False,
            "message":
                "Ujumbe haupo."
        }), 400

    ok = notify_admin_whatsapp(
        user_message,
        bot_reply
    )

    return jsonify({
        "success":
            ok
    })


# ============================================================
# HEALTH
# ============================================================

@app.route(
    "/health",
    methods=["GET"]
)
@app.route(
    "/api/health",
    methods=["GET"]
)
def health():

    try:

        fetchone(
            "SELECT 1"
        )

        return jsonify({

            "success":
                True,

            "service":
                "NJIA MAUZO AFRIKA",

            "status":
                "imara",

            "database":
                DB_TYPE,

            "fee":
                SERVICE_FEE

        })

    except Exception as error:

        logger.exception(
            "Health check error"
        )

        return jsonify({
            "success": False,
            "status": "error"
        }), 503


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(413)
def too_large(error):

    return jsonify({
        "success": False,
        "message":
            "Request ni kubwa sana."
    }), 413


@app.errorhandler(404)
def not_found(error):

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({
            "success": False,
            "message":
                "Endpoint haijapatikana."
        }), 404

    return (
        "Ukurasa haujapatikana.",
        404
    )


@app.errorhandler(500)
def server_error(error):

    logger.exception(
        "Internal server error"
    )

    return jsonify({
        "success": False,
        "message":
            "Server imepata hitilafu."
    }), 500


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

    port = int(
        os.environ.get(
            "PORT",
            "5000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
