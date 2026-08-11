import os
import re
import secrets
import sqlite3
import hashlib
import hmac
import functools
from datetime import datetime, timezone, timedelta
from pathlib import Path

from flask import (
    Flask, jsonify, request, render_template, g, session,
    abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "njiamauzo.db"))

app = Flask(__name__, template_folder="templates", static_folder="static")

# ---------- SECURITY CONFIG ----------
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
if not app.secret_key:
    # Fail hard in production; allow temporary dev key only if explicitly allowed
    if os.environ.get("ALLOW_INSECURE_DEV") == "1":
        app.secret_key = "dev-only-change-me-insecure"
    else:
        raise RuntimeError(
            "FLASK_SECRET_KEY environment variable is required. "
            "Set a strong random value (e.g. python -c \"import secrets; print(secrets.token_hex(32))\")."
        )

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,  # 1 MB
)

# Trust proxy headers only when behind a reverse proxy you control
if os.environ.get("TRUST_PROXY") == "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Admin token for manual payment verification (set in env)
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
PAYMENT_WEBHOOK_SECRET = os.environ.get("PAYMENT_WEBHOOK_SECRET", "")

COUNTRY_RATES = {
    "Tanzania": ("TZS", 1.00),
    "Kenya": ("KES", 0.027),
    "Uganda": ("UGX", 2.80),
    "Rwanda": ("RWF", 0.58),
    "Burundi": ("BIF", 1.73),
}

BASE_FEE_TZS = 3000

# Real payment numbers — NEVER exposed in HTML/JS source.
# Served only via authenticated API after user selects a method.
PAYMENT_NUMBERS = {
    "mpesa":   {"number": "0755 248 789", "label": "M-Pesa / Vodacom"},
    "halotel": {"number": "0625 031 460", "label": "Halotel / Tigo Pesa"},
    "airtel":  {"number": "0691 925 100", "label": "Airtel Money"},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    x = g.pop("db", None)
    if x:
        x.close()


def init_db():
    x = sqlite3.connect(DB_PATH)
    x.executescript("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    phone TEXT,
    role TEXT DEFAULT 'buyer',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS listings(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crop TEXT NOT NULL,
    quantity_kg REAL NOT NULL,
    price REAL NOT NULL,
    location TEXT NOT NULL,
    country TEXT NOT NULL,
    verified INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prices(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crop TEXT NOT NULL,
    market TEXT NOT NULL,
    country TEXT NOT NULL,
    buy_price REAL NOT NULL,
    sell_price REAL NOT NULL,
    transport_per_kg REAL NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS service_requests(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT UNIQUE NOT NULL,
    query TEXT NOT NULL,
    country TEXT NOT NULL,
    phone TEXT,
    method TEXT,
    fee_tzs REAL NOT NULL DEFAULT 3000,
    currency TEXT NOT NULL,
    amount REAL NOT NULL,
    payment_status TEXT NOT NULL DEFAULT 'PENDING',
    reference TEXT,
    created_at TEXT NOT NULL,
    verified_at TEXT,
    client_ip TEXT
);
CREATE TABLE IF NOT EXISTS alerts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    crop TEXT,
    target_price REAL,
    direction TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rate_limits(
    key TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0,
    window_start TEXT NOT NULL
);
""")
    x.commit()

    if x.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 0:
        rows = [
            ("Ufuta", "Songea", "Tanzania", 3000, 3600, 180),
            ("Ufuta", "Dar es Salaam", "Tanzania", 3200, 3900, 260),
            ("Ufuta", "Nairobi", "Kenya", 3500, 4300, 420),
            ("Ufuta", "Kampala", "Uganda", 3400, 4200, 460),
            ("Mahindi", "Mwanza", "Tanzania", 850, 1100, 120),
            ("Mahindi", "Nairobi", "Kenya", 1050, 1400, 250),
            ("Maharage", "Mbeya", "Tanzania", 2200, 2900, 180),
            ("Maharage", "Kigali", "Rwanda", 2700, 3500, 390),
            ("Karanga", "Dodoma", "Tanzania", 2500, 3300, 160),
            ("Karanga", "Nairobi", "Kenya", 3000, 3900, 380),
            ("Mpunga", "Mwanza", "Tanzania", 1600, 2300, 150),
            ("Korosho", "Mtwara", "Tanzania", 6500, 8200, 220),
        ]
        x.executemany(
            """INSERT INTO prices
               (crop, market, country, buy_price, sell_price, transport_per_kg, recorded_at)
               VALUES (?,?,?,?,?,?,?)""",
            [(a, b, c, d, e, f, now()) for a, b, c, d, e, f in rows],
        )

    if x.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 0:
        rows = [
            ("Ufuta", 20000, 3150, "Songea", "Tanzania", 1),
            ("Ufuta", 12000, 3300, "Mbeya", "Tanzania", 1),
            ("Mahindi", 50000, 900, "Mwanza", "Tanzania", 1),
            ("Maharage", 18000, 2350, "Mbeya", "Tanzania", 1),
            ("Karanga", 10000, 2700, "Dodoma", "Tanzania", 1),
            ("Ufuta", 25000, 3500, "Nairobi", "Kenya", 1),
        ]
        x.executemany(
            """INSERT INTO listings
               (crop, quantity_kg, price, location, country, verified, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            [(a, b, c, d, e, f, now()) for a, b, c, d, e, f in rows],
        )

    x.commit()
    x.close()


def client_ip():
    if os.environ.get("TRUST_PROXY") == "1":
        return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    return request.remote_addr or "unknown"


def rate_limit(key_prefix: str, max_calls: int = 20, window_seconds: int = 60):
    """Simple DB-backed rate limiter per key (IP or identifier)."""
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            key = f"{key_prefix}:{client_ip()}"
            now_iso = now()
            x = db()
            row = x.execute("SELECT count, window_start FROM rate_limits WHERE key=?", (key,)).fetchone()
            if row:
                try:
                    start = datetime.fromisoformat(row["window_start"])
                except Exception:
                    start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds + 1)
                if datetime.now(timezone.utc) - start > timedelta(seconds=window_seconds):
                    x.execute(
                        "UPDATE rate_limits SET count=1, window_start=? WHERE key=?",
                        (now_iso, key),
                    )
                    x.commit()
                else:
                    if row["count"] >= max_calls:
                        return jsonify(error="Umefikia kikomo cha maombi. Jaribu baadaye."), 429
                    x.execute(
                        "UPDATE rate_limits SET count=count+1 WHERE key=?",
                        (key,),
                    )
                    x.commit()
            else:
                x.execute(
                    "INSERT INTO rate_limits(key, count, window_start) VALUES(?,?,?)",
                    (key, 1, now_iso),
                )
                x.commit()
            return f(*args, **kwargs)
        return wrapped
    return decorator


def require_admin(f):
    """Protect admin-only endpoints with ADMIN_TOKEN header."""
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not ADMIN_TOKEN:
            return jsonify(error="Admin verification disabled. Set ADMIN_TOKEN."), 503
        supplied = request.headers.get("X-Admin-Token", "")
        if not hmac.compare_digest(ADMIN_TOKEN, supplied):
            return jsonify(error="Unauthorized"), 401
        return f(*args, **kwargs)
    return wrapped


def sanitize_text(value: str, max_len: int = 2000) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_len]


def parse_query(q: str):
    ql = q.lower()
    crops = [
        "ufuta", "mahindi", "maize", "maharage", "beans",
        "mpunga", "rice", "korosho", "cashew", "karanga",
        "peanuts", "groundnuts",
    ]
    crop = next((c for c in crops if c in ql), None)
    countries = ["tanzania", "kenya", "uganda", "rwanda", "burundi"]
    country = next((c.title() for c in countries if c in ql), None)
    nums = re.findall(r"\d[\d,]*", ql)
    quantity = None
    if nums:
        quantity = float(nums[0].replace(",", ""))
        if "tani" in ql or "ton" in ql:
            quantity *= 1000
    price = None
    m = re.search(
        r"(?:chini ya|under|below|less than|max|maximum)\s*(?:tzs|kes|ugx|rwf|bif)?\s*([\d,]+)",
        ql,
    )
    if m:
        price = float(m.group(1).replace(",", ""))
    return {
        "crop": crop.title() if crop else None,
        "country": country,
        "location": None,
        "quantity_kg": quantity,
        "max_price": price,
    }


def valid_phone(phone: str) -> bool:
    cleaned = re.sub(r"[\s\-]", "", phone)
    # Tanzania mobile: 06/07 + 8 digits, or +255...
    return bool(re.match(r"^(\+?255|0)[67]\d{8}$", cleaned))


# ---------- SECURITY HEADERS ----------
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # CSP: allow self + inline for existing page style/script (tighten later with nonces)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    if request.is_secure or os.environ.get("SESSION_COOKIE_SECURE") == "1":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ---------- ROUTES ----------

@app.route("/")
def home():
    return render_template("index.html")


@app.get("/api/stats")
def stats():
    x = db()
    return jsonify(
        users=x.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        listings=x.execute("SELECT COUNT(*) FROM listings").fetchone()[0],
        markets=x.execute("SELECT COUNT(DISTINCT market) FROM prices").fetchone()[0],
        countries=x.execute("SELECT COUNT(DISTINCT country) FROM prices").fetchone()[0],
    )


@app.get("/api/prices")
def prices():
    q = request.args.get("q", "").lower().strip()[:100]
    c = request.args.get("country", "").strip()[:50]
    rows = db().execute("SELECT * FROM prices ORDER BY recorded_at DESC").fetchall()
    out = []
    for r in rows:
        blob = f"{r['crop']} {r['market']} {r['country']}".lower()
        if q and q not in blob:
            continue
        if c and r["country"] != c:
            continue
        out.append(dict(r))
    return jsonify(out)


@app.post("/api/intelligence")
@rate_limit("intel", max_calls=30, window_seconds=60)
def intelligence():
    d = request.get_json(silent=True) or {}
    crop = sanitize_text(str(d.get("crop", "Ufuta")), 80)
    try:
        qty = float(d.get("quantity_kg") or 0)
        buy = float(d.get("source_price") or 0)
        extra = float(d.get("extra_cost_per_kg") or 0)
    except (TypeError, ValueError):
        return jsonify(error="Thamani si sahihi."), 400
    if qty < 0 or buy < 0 or extra < 0:
        return jsonify(error="Thamani si sahihi."), 400
    rows = db().execute("SELECT * FROM prices WHERE crop LIKE ?", (f"%{crop}%",)).fetchall()
    out = []
    for r in rows:
        landed = buy + extra + float(r["transport_per_kg"])
        profit = float(r["sell_price"]) - landed
        total = profit * qty
        margin = (profit / float(r["sell_price"]) * 100) if r["sell_price"] else 0
        out.append({
            "market": r["market"],
            "country": r["country"],
            "sell_price": r["sell_price"],
            "transport": r["transport_per_kg"],
            "landed_cost": landed,
            "profit_per_kg": profit,
            "profit_total": total,
            "margin_pct": margin,
        })
    out.sort(key=lambda x: x["profit_total"], reverse=True)
    return jsonify(results=out, recommendation=out[0] if out else None)


@app.post("/api/ai/search")
@rate_limit("ai_search", max_calls=20, window_seconds=60)
def ai_search():
    d = request.get_json(silent=True) or {}
    q = sanitize_text(str(d.get("query", "")), 500)
    i = parse_query(q)
    rows = db().execute("SELECT * FROM listings").fetchall()
    out = []
    for r in rows:
        score = 50
        if i["crop"] and r["crop"].lower() == i["crop"].lower():
            score += 30
        if i["country"] and r["country"].lower() == i["country"].lower():
            score += 15
        if i["quantity_kg"] and r["quantity_kg"] >= i["quantity_kg"]:
            score += 5
        if i["max_price"] and r["price"] <= i["max_price"]:
            score += 10
        if score >= 60:
            z = dict(r)
            z["match_score"] = min(score, 100)
            out.append(z)
    return jsonify(interpreted=i, results=sorted(out, key=lambda x: x["match_score"], reverse=True))


@app.post("/api/ai/chat")
@rate_limit("ai_chat", max_calls=30, window_seconds=60)
def ai_chat():
    m = sanitize_text(str((request.get_json(silent=True) or {}).get("message", "")), 500).lower()
    if "bei" in m:
        reply = "Nenda Bei ili kulinganisha bei za masoko. Unaweza pia kutumia Profit AI."
    elif "ufuta" in m:
        reply = "Mfumo una listings za ufuta Tanzania na Kenya kwenye database."
    elif "malipo" in m or "ada" in m:
        reply = "Huduma ya kutafutiwa bidhaa ni TZS 3,000. Lipa kupitia njia zilizochaguliwa baada ya kuomba huduma."
    else:
        reply = "Nimepokea ombi lako. Jaribu kutaja zao, kiasi, eneo na bei unayotaka."
    return jsonify(reply=reply)


@app.get("/api/listings")
def listings():
    q = request.args.get("q", "").lower().strip()[:100]
    rows = db().execute("SELECT * FROM listings ORDER BY id DESC").fetchall()
    return jsonify([
        dict(r) for r in rows
        if not q or q in f"{r['crop']} {r['location']} {r['country']}".lower()
    ])


@app.get("/api/ads")
def free_ads():
    rows = db().execute("SELECT * FROM listings ORDER BY id DESC LIMIT 10").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/listings")
@rate_limit("create_listing", max_calls=10, window_seconds=300)
def create_listing():
    d = request.get_json(silent=True) or {}
    try:
        crop = sanitize_text(str(d["crop"]), 80)
        qty = float(d["quantity_kg"])
        price = float(d["price"])
        loc = sanitize_text(str(d["location"]), 120)
        country = sanitize_text(str(d.get("country", "Tanzania")), 50)
    except (KeyError, TypeError, ValueError):
        return jsonify(error="Taarifa za bidhaa si sahihi."), 400
    if not crop or qty <= 0 or price <= 0 or not loc:
        return jsonify(error="Jaza taarifa zote."), 400
    db().execute(
        """INSERT INTO listings(crop, quantity_kg, price, location, country, verified, created_at)
           VALUES(?,?,?,?,?,1,?)""",
        (crop, qty, price, loc, country, now()),
    )
    db().commit()
    return jsonify(ok=True)


@app.post("/api/register")
@rate_limit("register", max_calls=5, window_seconds=300)
def register():
    d = request.get_json(silent=True) or {}
    name = sanitize_text(str(d.get("name", "")), 120)
    email = sanitize_text(str(d.get("email", "")).lower(), 200)
    password = str(d.get("password", ""))
    phone = sanitize_text(str(d.get("phone", "")), 30)
    role = sanitize_text(str(d.get("role", "buyer")), 20)
    if role not in ("buyer", "seller", "trader"):
        role = "buyer"
    if not name or not email or len(password) < 8:
        return jsonify(error="Jaza jina, email na password ya angalau herufi 8."), 400
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return jsonify(error="Email si sahihi."), 400
    try:
        cur = db().execute(
            "INSERT INTO users(name, email, password, phone, role, created_at) VALUES(?,?,?,?,?,?)",
            (name, email, generate_password_hash(password), phone, role, now()),
        )
        db().commit()
        session.clear()
        session["user_id"] = cur.lastrowid
        session.permanent = True
        return jsonify(ok=True)
    except sqlite3.IntegrityError:
        return jsonify(error="Email tayari imesajiliwa."), 409


@app.post("/api/login")
@rate_limit("login", max_calls=10, window_seconds=300)
def login():
    d = request.get_json(silent=True) or {}
    email = sanitize_text(str(d.get("email", "")).lower(), 200)
    password = str(d.get("password", ""))
    r = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not r or not check_password_hash(r["password"], password):
        return jsonify(error="Email au password si sahihi."), 401
    session.clear()
    session["user_id"] = r["id"]
    session.permanent = True
    return jsonify(name=r["name"], role=r["role"])


@app.get("/api/me")
def me():
    uid = session.get("user_id")
    if not uid:
        return jsonify(logged_in=False)
    r = db().execute(
        "SELECT name, email, role, phone FROM users WHERE id=?", (uid,)
    ).fetchone()
    return jsonify(logged_in=bool(r), **(dict(r) if r else {}))


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.post("/api/alerts")
def alerts():
    uid = session.get("user_id")
    if not uid:
        return jsonify(error="Ingia kwanza."), 401
    d = request.get_json(silent=True) or {}
    try:
        target = float(d.get("target_price") or 0)
    except (TypeError, ValueError):
        return jsonify(error="Bei si sahihi."), 400
    db().execute(
        "INSERT INTO alerts(user_id, crop, target_price, direction, created_at) VALUES(?,?,?,?,?)",
        (
            uid,
            sanitize_text(str(d.get("crop", "")), 80),
            target,
            sanitize_text(str(d.get("direction", "ABOVE")), 20),
            now(),
        ),
    )
    db().commit()
    return jsonify(ok=True)


# ---------- SERVICE (TZS 3,000) — NO DEMO ----------

@app.get("/api/service/fee")
def service_fee():
    country = sanitize_text(request.args.get("country", "Tanzania"), 50)
    currency, rate = COUNTRY_RATES.get(country, COUNTRY_RATES["Tanzania"])
    return jsonify(
        base_amount_tzs=BASE_FEE_TZS,
        amount=round(BASE_FEE_TZS * rate, 2),
        currency=currency,
        country=country,
    )


@app.post("/api/service/start")
@rate_limit("service_start", max_calls=10, window_seconds=300)
def service_start():
    d = request.get_json(silent=True) or {}
    q = sanitize_text(str(d.get("query", "")), 1000)
    if len(q) < 10:
        return jsonify(error="Andika ombi la kutafuta (angalau herufi 10)."), 400
    country = sanitize_text(str(d.get("country", "Tanzania")), 50)
    if country not in COUNTRY_RATES:
        country = "Tanzania"
    currency, rate = COUNTRY_RATES[country]
    phone = sanitize_text(str(d.get("phone", "")), 30)
    if phone and not valid_phone(phone):
        return jsonify(error="Namba ya simu si sahihi."), 400
    ref = secrets.token_urlsafe(16)
    cur = db().execute(
        """INSERT INTO service_requests
           (request_id, query, country, phone, fee_tzs, currency, amount, payment_status, created_at, client_ip)
           VALUES(?,?,?,?,?,?,?, 'PENDING',?,?)""",
        (
            ref,
            q,
            country,
            phone or None,
            BASE_FEE_TZS,
            currency,
            round(BASE_FEE_TZS * rate, 2),
            now(),
            client_ip(),
        ),
    )
    db().commit()
    return jsonify(
        request_id=cur.lastrowid,
        reference=ref,
        status="PENDING",
        amount=round(BASE_FEE_TZS * rate, 2),
        currency=currency,
        fee_tzs=BASE_FEE_TZS,
    )


@app.get("/api/service/payment-number")
@rate_limit("pay_number", max_calls=30, window_seconds=60)
def service_payment_number():
    """
    Returns payment number ONLY after user selects a method.
    Numbers are never in HTML/JS source.
    """
    method = sanitize_text(request.args.get("method", ""), 30).lower()
    info = PAYMENT_NUMBERS.get(method)
    if not info:
        return jsonify(error="Njia ya malipo si sahihi."), 400

    rid = request.args.get("request_id")
    if rid:
        try:
            rid_int = int(rid)
            db().execute(
                "UPDATE service_requests SET method=? WHERE id=? AND payment_status='PENDING'",
                (method, rid_int),
            )
            db().commit()
        except (ValueError, TypeError):
            pass

    return jsonify(number=info["number"], label=info["label"], method=method)


@app.post("/api/service/pay")
@rate_limit("service_pay", max_calls=15, window_seconds=300)
def service_pay():
    d = request.get_json(silent=True) or {}
    try:
        rid = int(d.get("request_id") or 0)
    except (TypeError, ValueError):
        return jsonify(error="Request ID si sahihi."), 400
    phone = sanitize_text(str(d.get("phone", "")), 30)
    reference = sanitize_text(str(d.get("reference", "")), 120)
    r = db().execute("SELECT * FROM service_requests WHERE id=?", (rid,)).fetchone()
    if not r:
        return jsonify(error="Request haipo."), 404
    if r["payment_status"] != "PENDING":
        return jsonify(error="Ombi hili limekwisha kushughulikiwa."), 400
    if not phone or not valid_phone(phone):
        return jsonify(error="Weka namba sahihi ya simu."), 400
    db().execute(
        "UPDATE service_requests SET reference=?, phone=? WHERE id=?",
        (reference or None, phone, rid),
    )
    db().commit()
    return jsonify(
        reference=r["request_id"],
        status="PENDING",
        amount=r["amount"],
        currency=r["currency"],
        message="Malipo yamepokelewa kama PENDING. Subiri uthibitisho kutoka kwa admin/system.",
    )


@app.get("/api/service/status/<int:rid>")
@rate_limit("service_status", max_calls=40, window_seconds=60)
def service_status(rid):
    r = db().execute("SELECT * FROM service_requests WHERE id=?", (rid,)).fetchone()
    if not r:
        return jsonify(error="Request haipo."), 404
    return jsonify(
        request_id=rid,
        status=r["payment_status"],
        reference=r["request_id"],
        amount=r["amount"],
        currency=r["currency"],
        fee_tzs=r["fee_tzs"],
    )


@app.post("/api/service/admin-verify")
@require_admin
def admin_verify():
    """
    ONLY way to mark payment VERIFIED manually.
    Requires header: X-Admin-Token: <ADMIN_TOKEN>
    """
    d = request.get_json(silent=True) or {}
    try:
        rid = int(d.get("request_id") or 0)
    except (TypeError, ValueError):
        return jsonify(error="Request ID si sahihi."), 400
    r = db().execute("SELECT * FROM service_requests WHERE id=?", (rid,)).fetchone()
    if not r:
        return jsonify(error="Request haipo."), 404
    if r["payment_status"] == "VERIFIED":
        return jsonify(status="VERIFIED", request_id=rid, reference=r["request_id"])
    db().execute(
        "UPDATE service_requests SET payment_status='VERIFIED', verified_at=? WHERE id=?",
        (now(), rid),
    )
    db().commit()
    return jsonify(status="VERIFIED", request_id=rid, reference=r["request_id"])


@app.post("/api/service/webhook")
def service_webhook():
    if not PAYMENT_WEBHOOK_SECRET:
        return jsonify(error="Webhook not configured"), 503
    supplied = request.headers.get("X-NjiaMauzo-Webhook-Secret", "")
    if not hmac.compare_digest(PAYMENT_WEBHOOK_SECRET, supplied):
        return jsonify(error="Invalid webhook"), 401
    d = request.get_json(silent=True) or {}
    try:
        rid = int(d.get("request_id") or 0)
    except (TypeError, ValueError):
        return jsonify(error="Invalid request_id"), 400
    if str(d.get("status", "")).upper() != "VERIFIED":
        return jsonify(status="IGNORED")
    r = db().execute("SELECT id FROM service_requests WHERE id=?", (rid,)).fetchone()
    if not r:
        return jsonify(error="Request haipo."), 404
    db().execute(
        "UPDATE service_requests SET payment_status='VERIFIED', reference=?, verified_at=? WHERE id=?",
        (sanitize_text(str(d.get("reference", "")), 120), now(), rid),
    )
    db().commit()
    return jsonify(status="VERIFIED", request_id=rid)


@app.post("/api/service/room")
@rate_limit("service_room", max_calls=20, window_seconds=60)
def service_room():
    d = request.get_json(silent=True) or {}
    try:
        rid = int(d.get("request_id") or 0)
    except (TypeError, ValueError):
        return jsonify(error="Request ID si sahihi."), 400
    r = db().execute("SELECT * FROM service_requests WHERE id=?", (rid,)).fetchone()
    if not r:
        return jsonify(error="Request haipo."), 404
    if r["payment_status"] != "VERIFIED":
        return jsonify(error="Malipo hayajathibitishwa."), 403
    interpreted = parse_query(r["query"])
    rows = db().execute("SELECT * FROM listings").fetchall()
    products = []
    for x in rows:
        score = 50
        if interpreted["crop"] and x["crop"].lower() == interpreted["crop"].lower():
            score += 30
        if interpreted["country"] and x["country"].lower() == interpreted["country"].lower():
            score += 15
        if interpreted["quantity_kg"] and x["quantity_kg"] >= interpreted["quantity_kg"]:
            score += 5
        if interpreted["max_price"] and x["price"] <= interpreted["max_price"]:
            score += 10
        if score >= 60:
            z = dict(x)
            z["match_score"] = min(score, 100)
            products.append(z)
    markets = []
    for p in db().execute("SELECT * FROM prices").fetchall():
        if interpreted["crop"] and p["crop"].lower() != interpreted["crop"].lower():
            continue
        markets.append({
            "market": p["market"],
            "country": p["country"],
            "crop": p["crop"],
            "sell_price": p["sell_price"],
            "transport_per_kg": p["transport_per_kg"],
        })
    return jsonify(
        status="VERIFIED",
        message="Malipo yamethibitishwa. User Room imefunguliwa na automatic search imekamilika.",
        query=r["query"],
        interpreted=interpreted,
        products=sorted(products, key=lambda x: x["match_score"], reverse=True),
        markets=markets[:20],
    )


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
