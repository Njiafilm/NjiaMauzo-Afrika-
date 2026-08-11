# =========================================================
# NJIA MAUZO AFRIKA
# AI PRODUCT FINDER + 24/7 BOT CHAT + ADMIN WHATSAPP
# app.py — professional, Render/Gunicorn ready
#
# FIX KUU YA NameError:
# app = Flask(__name__) iko MWANZO kabla ya route yoyote.
# =========================================================

import os
import re
import json
import time
import logging
import secrets
import sqlite3
import threading
from functools import wraps

import urllib.request
import urllib.error

from flask import (
    Flask, request, jsonify, session,
    redirect, url_for, render_template_string,
)
from werkzeug.middleware.proxy_fix import ProxyFix

# =========================================================
# 1) FLASK APP — MWANZO KABLA YA ROUTES ZOTE (FIX)
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

try:
    app.json.ensure_ascii = False
except Exception:
    app.config["JSON_AS_ASCII"] = False

# IP halisi behind Render proxy (kwa rate limiting)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("njia_mauzo")

# =========================================================
# 2) CONFIGURATION
# =========================================================

SERVICE_FEE_TZS = 3000

PAYMENT_NUMBERS = [
    {"network": "M-Pesa",       "number": "0755 248 789", "jina": "Njia Mauzo Afrika"},
    {"network": "Halotel",      "number": "0625 031 460", "jina": "Njia Mauzo Afrika"},
    {"network": "Airtel Money", "number": "0691 925 100", "jina": "Njia Mauzo Afrika"},
]

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
if not ADMIN_PASSWORD:
    ADMIN_PASSWORD = secrets.token_urlsafe(12)
    logger.warning("ADMIN_PASSWORD haijawekwa kwenye env — tumia hii kwa sasa: %s", ADMIN_PASSWORD)

WHATSAPP_API_URL = os.environ.get("WHATSAPP_API_URL", "").strip()
WHATSAPP_API_TOKEN = os.environ.get("WHATSAPP_API_TOKEN", "").strip()
ADMIN_WHATSAPP_NUMBER = os.environ.get("ADMIN_WHATSAPP_NUMBER", "255755248789").strip()

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH = os.environ.get("SQLITE_PATH", "njia_mauzo.db").strip()

# =========================================================
# 3) HELPERS
# =========================================================

def _clean_text(value, max_length=1000):
    text = str(value or "").strip()
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text[:max_length]

# =========================================================
# 4) DATABASE LAYER — SQLite / PostgreSQL
# =========================================================

def _is_postgres():
    return DATABASE_URL.startswith(("postgres://", "postgresql://"))

class DB:
    """Wrapper inayofanisha API ya SQLite na PostgreSQL."""

    def __init__(self):
        self.pg = None
        self._psycopg2 = None
        if _is_postgres():
            import psycopg2
            import psycopg2.extras
            self._psycopg2 = psycopg2
            self.pg = psycopg2.connect(DATABASE_URL, sslmode="require", connect_timeout=10)
        else:
            self.sqlite = sqlite3.connect(SQLITE_PATH, timeout=30)
            self.sqlite.row_factory = sqlite3.Row
            self.sqlite.execute("PRAGMA journal_mode=WAL;")

    def execute(self, sql, params=()):
        if self.pg is not None:
            sql = sql.replace("?", "%s")
            cur = self.pg.cursor(cursor_factory=self._psycopg2.extras.RealDictCursor)
            cur.execute(sql, params)
            return cur
        return self.sqlite.execute(sql, params)

    def commit(self):
        if self.pg is not None:
            self.pg.commit()
        else:
            self.sqlite.commit()

    def close(self):
        try:
            if self.pg is not None:
                self.pg.close()
            else:
                self.sqlite.close()
        except Exception:
            pass

def init_db():
    conn = DB()
    try:
        if _is_postgres():
            conn.execute("""
                CREATE TABLE IF NOT EXISTS listings (
                    id SERIAL PRIMARY KEY,
                    crop TEXT, location TEXT, country TEXT,
                    price NUMERIC, created_at TIMESTAMPTZ DEFAULT NOW()
                )""")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    phone TEXT NOT NULL, network TEXT,
                    amount INTEGER NOT NULL DEFAULT 3000,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    reference TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    verified_at TIMESTAMPTZ
                )""")
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS listings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crop TEXT, location TEXT, country TEXT,
                    price REAL, created_at TEXT DEFAULT (datetime('now'))
                )""")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT NOT NULL, network TEXT,
                    amount INTEGER NOT NULL DEFAULT 3000,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    reference TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    verified_at TEXT
                )""")
        conn.commit()

        count = conn.execute("SELECT COUNT(*) AS c FROM listings").fetchone()["c"]
        if not count:
            seed = [
                ("Ufuta", "Ruvuma", "Tanzania", 3200),
                ("Ufuta", "Mtwara", "Tanzania", 3100),
                ("Mahindi", "Dodoma", "Tanzania", 1200),
                ("Maharage", "Mbeya", "Tanzania", 2500),
                ("Korosho", "Mtwara", "Tanzania", 4500),
                ("Mpunga", "Morogoro", "Tanzania", 1800),
                ("Soya", "Rukwa", "Tanzania", 2000),
                ("Karanga", "Singida", "Tanzania", 2800),
            ]
            for crop, loc, country, price in seed:
                conn.execute(
                    "INSERT INTO listings (crop, location, country, price) VALUES (?, ?, ?, ?)",
                    (crop, loc, country, price),
                )
            conn.commit()
            logger.info("Listings seed zimepandikizwa.")
    finally:
        conn.close()

def search_products(q="", limit=20):
    products = []
    conn = DB()
    try:
        rows = conn.execute(
            "SELECT crop, location, country, price FROM listings ORDER BY id DESC"
        ).fetchall()
    finally:
        conn.close()

    for r in rows:
        crop = str(r["crop"] or "")
        location = str(r["location"] or "")
        country = str(r["country"] or "")
        blob = f"{crop} {location} {country}".lower()

        if q and q not in blob:
            continue

        try:
            bei = f"TZS {float(r['price']):,.0f}/kg"
        except (TypeError, ValueError):
            bei = "Bei haijawekwa"

        chanzo = f"{location}, {country}" if location and country else (location or country)

        products.append({
            "jina": crop or "Bidhaa",
            "picha": "/static/favicon.png",
            "chanzo": chanzo,
            "bei": bei,
        })
        if len(products) >= limit:
            break
    return products

def create_payment(phone, network, reference):
    conn = DB()
    try:
        if _is_postgres():
            cur = conn.execute(
                "INSERT INTO payments (phone, network, amount, status, reference) "
                "VALUES (?, ?, ?, 'PENDING', ?) RETURNING id",
                (phone, network, SERVICE_FEE_TZS, reference),
            )
            pid = cur.fetchone()["id"]
        else:
            cur = conn.execute(
                "INSERT INTO payments (phone, network, amount, status, reference) "
                "VALUES (?, ?, ?, 'PENDING', ?)",
                (phone, network, SERVICE_FEE_TZS, reference),
            )
            pid = cur.lastrowid
        conn.commit()
        return pid
    finally:
        conn.close()

def verify_payment(pid):
    conn = DB()
    try:
        if _is_postgres():
            conn.execute("UPDATE payments SET status='VERIFIED', verified_at=NOW() WHERE id=?", (pid,))
        else:
            conn.execute("UPDATE payments SET status='VERIFIED', verified_at=datetime('now') WHERE id=?", (pid,))
        conn.commit()
    finally:
        conn.close()

# =========================================================
# 5) RATE LIMITING (in-memory, per IP)
# =========================================================

_RATE_STORE = {}
_RATE_LOCK = threading.Lock()

def rate_limit(max_calls=30, window=60):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (fn.__name__, request.remote_addr or "unknown")
            now = time.time()
            with _RATE_LOCK:
                bucket = _RATE_STORE.setdefault(key, [])
                while bucket and bucket[0] <= now - window:
                    bucket.pop(0)
                if len(bucket) >= max_calls:
                    return jsonify({
                        "success": False,
                        "error": "Rate limit imefikwa. Jaribu baada ya dakika moja.",
                    }), 429
                bucket.append(now)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# =========================================================
# 6) SECURITY HEADERS + CORS
# =========================================================

@app.after_request
def secure_response(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:"
    )
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    if request.path.startswith("/api/"):
        response.headers["Access-Control-Allow-Origin"] = os.environ.get("CORS_ORIGINS", "*")
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        return "", 204

# =========================================================
# 7) WHATSAPP ADMIN NOTIFICATION
# =========================================================

def notify_admin_whatsapp(user_message: str, bot_reply: str) -> bool:
    if not WHATSAPP_API_URL or not WHATSAPP_API_TOKEN or not ADMIN_WHATSAPP_NUMBER:
        logger.warning("WhatsApp config haikamilika — notification imerukwa.")
        return False

    message = (
        "🔔 NJIA MAUZO AFRIKA\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 UJUMBE MPYA WA MTUMIAJI\n\n"
        f"{_clean_text(user_message, 1000)}\n\n"
        "🤖 BOT AMEJIBU\n\n"
        f"{_clean_text(bot_reply, 1000)}\n\n"
        "💰 Ada ya AI Product Finder: TZS 3,000\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    payload = {"to": ADMIN_WHATSAPP_NUMBER, "message": message}

    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            WHATSAPP_API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            status = resp.status
        if 200 <= status < 300:
            logger.info("WhatsApp admin notification sent.")
            return True
        logger.warning("WhatsApp API HTTP %s", status)
        return False
    except Exception as e:
        logger.warning("WhatsApp error: %s", e)
        return False

# =========================================================
# 8) ADMIN AUTH
# =========================================================

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Login inahitajika."}), 401
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

LOGIN_TEMPLATE = """
<!doctype html><html lang="sw"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin Login</title>
<style>body{font-family:system-ui;background:#0b1220;color:#e5e7eb;display:flex;
justify-content:center;align-items:center;min-height:100vh;margin:0}
.card{background:#111827;padding:24px;border-radius:12px;width:300px}
input{width:100%;margin:6px 0;padding:8px;border-radius:6px;border:1px solid #374151;
background:#0b1220;color:#e5e7eb;box-sizing:border-box}
button{width:100%;background:#0ea5e9;border:0;color:#fff;padding:8px;border-radius:6px}
.err{color:#fca5a5;font-size:13px}</style></head>
<body><form class="card" method="post">
<h2>🔐 Admin Login</h2>
{% if error %}<p class="err">{{ error }}</p>{% endif %}
<input name="username" placeholder="Jina la admin" required>
<input name="password" type="password" placeholder="Nenosiri" required>
<button type="submit">Ingia</button>
</form></body></html>
"""

ADMIN_TEMPLATE = """
<!doctype html><html lang="sw"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin — Njia Mauzo Afrika</title>
<style>body{font-family:system-ui;background:#0b1220;color:#e5e7eb;margin:0;padding:16px}
h1,h2{color:#7dd3fc}table{width:100%;border-collapse:collapse;font-size:14px;margin-bottom:16px}
th,td{border:1px solid #1f2937;padding:8px;text-align:left}th{background:#111827}
.badge{padding:2px 8px;border-radius:10px;font-size:12px}
.PENDING{background:#7c2d12;color:#fed7aa}.VERIFIED{background:#14532d;color:#bbf7d0}
button{background:#0ea5e9;border:0;color:#fff;padding:6px 12px;border-radius:6px;cursor:pointer}
.card{background:#111827;padding:16px;border-radius:10px;margin-bottom:24px}
input{padding:6px;border-radius:6px;border:1px solid #374151;background:#0b1220;color:#e5e7eb}
a{color:#7dd3fc}</style></head>
<body>
<h1>🛠️ Admin — {{ username }}</h1>
<p><a href="{{ url_for('logout') }}">Toka (Logout)</a></p>

<div class="card"><h2>💳 Malipo (PENDING → VERIFIED)</h2>
<table><tr><th>ID</th><th>Simu</th><th>Mtandao</th><th>Kiasi</th><th>Hali</th><th>Tarehe</th><th>Kitendo</th></tr>
{% for p in payments %}
<tr><td>{{ p['id'] }}</td><td>{{ p['phone'] }}</td><td>{{ p['network'] or '-' }}</td>
<td>TZS {{ p['amount'] }}</td>
<td><span class="badge {{ p['status'] }}">{{ p['status'] }}</span></td>
<td>{{ p['created_at'] or '-' }}</td>
<td>{% if p['status'] == 'PENDING' %}
<form method="post" action="{{ url_for('admin_verify_payment', pid=p['id']) }}">
<button type="submit">✅ Verify</button></form>
{% else %}✅{% endif %}</td></tr>
{% else %}<tr><td colspan="7">Hakuna malipo bado.</td></tr>{% endfor %}
</table></div>

<div class="card"><h2>📦 Listings (Bidhaa)</h2>
<form method="post" action="{{ url_for('admin_add_listing') }}" style="margin-bottom:12px">
<input name="crop" placeholder="Zao (mf. Ufuta)" required>
<input name="location" placeholder="Eneo (mf. Ruvuma)">
<input name="country" placeholder="Nchi" value="Tanzania">
<input name="price" placeholder="Bei TZS/kg" type="number" step="any" required>
<button type="submit">+ Ongeza</button></form>
<table><tr><th>ID</th><th>Zao</th><th>Eneo</th><th>Nchi</th><th>Bei</th></tr>
{% for l in listings %}
<tr><td>{{ l['id'] }}</td><td>{{ l['crop'] }}</td><td>{{ l['location'] }}</td>
<td>{{ l['country'] }}</td><td>{{ l['price'] }}</td></tr>
{% endfor %}</table></div>
</body></html>
"""

# =========================================================
# 9) ROUTES — ZOTE BAADA YA app = Flask(__name__)
# =========================================================

@app.get("/")
def index():
    return jsonify({
        "success": True,
        "service": "NJIA MAUZO AFRIKA API",
        "endpoints": [
            "/api/ai-products", "/api/bot-chat", "/api/notify-admin",
            "/api/service/payment-number", "/api/service/payment-request",
            "/api/service/payment-status", "/api/health", "/login",
        ],
    })

@app.get("/api/health")
def health():
    return jsonify({"success": True, "status": "OK", "service": "Njia Mauzo Afrika"})

# ---------------- AI PRODUCT FINDER ----------------
@app.get("/api/ai-products")
@rate_limit(60, 60)
def ai_products():
    q = _clean_text(request.args.get("q", ""), 100).lower()
    try:
        products = search_products(q, 20)
    except Exception as e:
        logger.exception("AI Product Finder error: %s", e)
        return jsonify({
            "success": False,
            "error": "Imeshindikana kupata bidhaa kwa sasa.",
            "products": [],
        }), 500
    return jsonify({"success": True, "products": products, "count": len(products)})

# ---------------- 24/7 BOT CHAT ----------------
@app.post("/api/bot-chat")
@rate_limit(30, 60)
def bot_chat():
    data = request.get_json(silent=True) or {}
    message = _clean_text(data.get("message", ""), 500)

    if not message:
        return jsonify({"success": False, "error": "Andika ujumbe."}), 400

    ml = message.lower()
    products = []

    crop_words = ["ufuta", "mahindi", "maharage", "maharagwe", "mpunga",
                  "korosho", "karanga", "soya", "mtama", "dengu"]

    if any(w in ml for w in ["bei", "price", "gharama", "market", "soko", "masoko"]):
        reply = ("Nenda sehemu ya Bei kulinganisha bei za masoko, "
                 "au tumia Profit AI kukokotoa faida.")

    elif (matched_crop := next((c for c in crop_words if c in ml), None)):
        reply = ("Tunayo listings za zao hilo kwenye mfumo. Bonyeza "
                 "'Tazama Bidhaa (AI)' kuona bidhaa zilizopo sasa.")
        try:
            products = search_products(matched_crop, 5)
        except Exception:
            products = []

    elif any(w in ml for w in ["malipo", "ada", "lipa", "payment"]):
        reply = ("Huduma ya kutafutiwa bidhaa ni TZS 3,000. Tumia "
                 "M-Pesa 0755 248 789, Halotel 0625 031 460, au "
                 "Airtel Money 0691 925 100, kisha subiri uthibitisho (VERIFIED).")

    elif any(w in ml for w in ["asante", "ahsante", "sawa", "poa"]):
        reply = "Karibu sana! Nipo hapa muda wote kukusaidia kupata bidhaa na taarifa za masoko."

    elif any(w in ml for w in ["habari", "hello", "hi", "mambo"]):
        reply = ("Karibu NjiaMauzo Afrika! 👋 Unatafuta zao gani, "
                 "kiasi gani, eneo gani, au bei gani?")

    else:
        reply = ("Nimepokea ujumbe wako. Niambie zao unalotafuta, kiasi, "
                 "eneo, au bei unayotaka.\n\nMfano: Natafuta tani 20 za "
                 "ufuta Ruvuma chini ya TZS 3,200/kg.")

    try:
        notify_admin_whatsapp(user_message=message, bot_reply=reply)
    except Exception as e:
        logger.warning("Admin WhatsApp notification skipped: %s", e)

    return jsonify({"success": True, "reply": reply, "products": products})

# ---------------- ADMIN NOTIFICATION ----------------
@app.post("/api/notify-admin")
@rate_limit(30, 60)
def notify_admin_endpoint():
    data = request.get_json(silent=True) or {}
    user_message = _clean_text(data.get("user_message", ""), 1000)
    bot_reply = _clean_text(data.get("bot_reply", ""), 1000)

    if not user_message:
        return jsonify({"success": False, "ok": False,
                        "error": "user_message inahitajika."}), 400

    ok = notify_admin_whatsapp(user_message=user_message, bot_reply=bot_reply)
    return jsonify({"success": True, "ok": ok})

# ---------------- PAYMENT SERVICES ----------------
@app.get("/api/service/payment-number")
@rate_limit(60, 60)
def payment_number():
    return jsonify({
        "success": True,
        "fee": "TZS 3,000",
        "amount": SERVICE_FEE_TZS,
        "currency": "TZS",
        "numbers": PAYMENT_NUMBERS,
        "instructions": ("Tuma TZS 3,000 kwenye nambari yoyote hapo juu, "
                         "kisha wasilisha nambari yako ya simu kupitia "
                         "/api/service/payment-request ili kupata hali ya "
                         "malipo (PENDING → VERIFIED)."),
    })

@app.post("/api/service/payment-request")
@rate_limit(10, 60)
def payment_request():
    data = request.get_json(silent=True) or {}
    phone = re.sub(r"\D", "", str(data.get("phone", "")))
    if not (9 <= len(phone) <= 15):
        return jsonify({"success": False, "error": "Nambari ya simu si sahihi."}), 400

    network = _clean_text(data.get("network", ""), 50)
    reference = _clean_text(data.get("reference", ""), 100)

    try:
        pid = create_payment(phone, network, reference)
    except Exception as e:
        logger.exception("Payment create error: %s", e)
        return jsonify({"success": False, "error": "Imeshindikana kuandikisha malipo."}), 500

    return jsonify({
        "success": True,
        "payment_id": pid,
        "status": "PENDING",
        "amount": SERVICE_FEE_TZS,
        "numbers": PAYMENT_NUMBERS,
        "message": "Malipo yameandikishwa (PENDING). Admin atathibitisha (VERIFIED) baada ya kupokea TZS 3,000.",
    }), 201

@app.get("/api/service/payment-status")
@rate_limit(30, 60)
def payment_status():
    phone = re.sub(r"\D", "", request.args.get("phone", ""))
    if len(phone) < 9:
        return jsonify({"success": False, "error": "Nambari ya simu si sahihi."}), 400

    conn = DB()
    try:
        row = conn.execute(
            "SELECT id, amount, status FROM payments WHERE phone=? ORDER BY id DESC LIMIT 1",
            (phone,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"success": True, "status": "HAKUNA",
                        "message": "Hakuna malipo kwa nambari hii."})
    return jsonify({"success": True, "payment_id": row["id"],
                    "amount": row["amount"], "status": row["status"]})

# ---------------- LOGIN / ADMIN ----------------
@app.route("/login", methods=["GET", "POST"])
@rate_limit(10, 60)
def login():
    error = None
    if request.method == "POST":
        u = _clean_text(request.form.get("username", ""), 100)
        p = request.form.get("password", "") or ""
        if secrets.compare_digest(u, ADMIN_USERNAME) and secrets.compare_digest(p, ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Jina au nenosiri si sahihi."
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.get("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("login"))

@app.get("/admin")
@admin_required
def admin_dashboard():
    conn = DB()
    try:
        payments = conn.execute("SELECT * FROM payments ORDER BY id DESC LIMIT 100").fetchall()
        listings = conn.execute("SELECT * FROM listings ORDER BY id DESC LIMIT 200").fetchall()
    finally:
        conn.close()
    return render_template_string(ADMIN_TEMPLATE, payments=payments,
                                  listings=listings, username=ADMIN_USERNAME)

@app.post("/admin/payments/<int:pid>/verify")
@admin_required
def admin_verify_payment(pid):
    verify_payment(pid)
    logger.info("Payment %s → VERIFIED", pid)
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/listings/add")
@admin_required
def admin_add_listing():
    crop = _clean_text(request.form.get("crop", ""), 100)
    location = _clean_text(request.form.get("location", ""), 100)
    country = _clean_text(request.form.get("country", ""), 100)
    try:
        price = float(request.form.get("price", 0))
    except (TypeError, ValueError):
        price = 0.0

    conn = DB()
    try:
        conn.execute(
            "INSERT INTO listings (crop, location, country, price) VALUES (?, ?, ?, ?)",
            (crop, location, country, price),
        )
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("admin_dashboard"))

# ---------------- ERROR HANDLERS ----------------
@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Endpoint haipatikani."}), 404

@app.errorhandler(500)
def server_error(e):
    logger.exception("Internal server error")
    return jsonify({"success": False, "error": "Hitilafu ya seva."}), 500

# =========================================================
# 10) STARTUP
# =========================================================

try:
    init_db()
    logger.info("Database iko tayari.")
except Exception as e:
    logger.exception("init_db imeshindikana: %s", e)

logger.info("NJIA MAUZO AFRIKA API imeanza. Endpoints: /api/ai-products, /api/bot-chat, /admin")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
