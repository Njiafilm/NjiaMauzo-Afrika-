#!/usr/bin/env python3
"""
NjiaMauzo Afrika Pro - Agricultural Marketplace for East Africa
Professional version with social features, location, live feed, and AI Admin Controller.
"""

import os
import re
import sqlite3
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from functools import wraps

try:
    from email_service import send_otp_email, send_welcome_email, send_payment_email, send_password_reset_email, get_info_email_config
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False
from flask import (
    Flask, render_template, request, jsonify, session,
    send_from_directory, redirect, url_for, flash
)

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "njiamauzo_pro.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "njiamauzo-pro-secret-change-in-production-2026")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

SERVICE_FEE_TZS = 1000.0
CURRENCY_RATES = {
    "Tanzania": {"code": "TZS", "name": "Tanzanian Shilling", "per_tzs": 1.0},
    "Kenya": {"code": "KES", "name": "Kenyan Shilling", "per_tzs": 0.049},
    "Uganda": {"code": "UGX", "name": "Ugandan Shilling", "per_tzs": 1.33},
    "Rwanda": {"code": "RWF", "name": "Rwandan Franc", "per_tzs": 0.55},
    "Burundi": {"code": "BIF", "name": "Burundian Franc", "per_tzs": 0.43},
}

CROPS = {
    "mahindi": "Mahindi", "maize": "Mahindi",
    "ufuta": "Ufuta", "sesame": "Ufuta",
    "maharage": "Maharage", "beans": "Maharage",
    "mpunga": "Mpunga", "rice": "Mpunga",
    "korosho": "Korosho", "cashew": "Korosho",
    "kahawa": "Kahawa", "coffee": "Kahawa",
    "chai": "Chai", "tea": "Chai",
}

LOCATIONS = [
    "Songea", "Ruvuma", "Mwanza", "Arusha", "Morogoro", "Mtwara",
    "Dar es Salaam", "Dodoma", "Mbeya", "Kilimanjaro",
    "Nairobi", "Mombasa", "Kisumu",
    "Kampala", "Jinja", "Mbarara",
    "Kigali", "Butare", "Bujumbura"
]

# ──────────────────────────────────────────────
# DATABASE HELPERS
# ──────────────────────────────────────────────
def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_password(password: str) -> str:
    salt = os.environ.get("PASSWORD_SALT", "njiamauzo-pro-salt-v2").encode()
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000).hex()

def now_iso():
    return datetime.utcnow().isoformat()

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'buyer',          -- buyer | seller | admin
        bio TEXT DEFAULT '',
        location TEXT DEFAULT '',
        latitude REAL,
        longitude REAL,
        avatar_url TEXT DEFAULT '',
        is_verified INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        followers_count INTEGER DEFAULT 0,
        following_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        last_seen TEXT
    );

    CREATE TABLE IF NOT EXISTS prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        crop TEXT NOT NULL,
        market TEXT NOT NULL,
        country TEXT NOT NULL,
        buy_price REAL,
        sell_price REAL,
        transport_per_kg REAL DEFAULT 0,
        source TEXT DEFAULT 'Demo',
        recorded_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        crop TEXT NOT NULL,
        quantity_kg REAL NOT NULL,
        price REAL NOT NULL,
        location TEXT NOT NULL,
        country TEXT DEFAULT 'Tanzania',
        description TEXT DEFAULT '',
        seller_id INTEGER,
        latitude REAL,
        longitude REAL,
        verified INTEGER DEFAULT 0,
        status TEXT DEFAULT 'ACTIVE',      -- ACTIVE | SOLD | HIDDEN
        likes_count INTEGER DEFAULT 0,
        comments_count INTEGER DEFAULT 0,
        views_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY (seller_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        listing_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(user_id, listing_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        parent_id INTEGER,                 -- for replies
        content TEXT NOT NULL,
        is_hidden INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (parent_id) REFERENCES comments(id)
    );

    CREATE TABLE IF NOT EXISTS follows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        follower_id INTEGER NOT NULL,
        following_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(follower_id, following_id),
        FOREIGN KEY (follower_id) REFERENCES users(id),
        FOREIGN KEY (following_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        crop TEXT NOT NULL,
        target_price REAL NOT NULL,
        direction TEXT DEFAULT 'ABOVE',
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL NOT NULL,
        method TEXT,
        status TEXT DEFAULT 'PENDING',
        reference TEXT UNIQUE,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        query TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS service_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        guest_token TEXT,
        query TEXT NOT NULL,
        status TEXT DEFAULT 'AWAITING_PAYMENT',
        payment_id INTEGER,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS service_rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER UNIQUE,
        user_id INTEGER,
        guest_token TEXT,
        query TEXT,
        status TEXT DEFAULT 'OPEN',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS payment_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_id INTEGER,
        event_type TEXT,
        payload TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS activity_feed (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action_type TEXT NOT NULL,        -- LIKE | COMMENT | FOLLOW | LISTING | PRICE_UPDATE | SYSTEM
        target_type TEXT,                 -- listing | user | price
        target_id INTEGER,
        message TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS admin_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS ai_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        query TEXT,
        response TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS otps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        email TEXT,
        phone TEXT,
        code TEXT NOT NULL,
        purpose TEXT NOT NULL,          -- LOGIN | RESET | VERIFY | PAYMENT
        channel TEXT DEFAULT 'EMAIL',    -- EMAIL | SMS | WHATSAPP
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS captcha_challenges (
        id TEXT PRIMARY KEY,
        answer TEXT NOT NULL,
        expires_at TEXT NOT NULL
    );
    """)

    # Ensure extra columns exist (migration-safe)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "must_change_password" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0")
    if "password_changed_at" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN password_changed_at TEXT")

    # Seed admin user with default password 0000
    admin = conn.execute("SELECT id FROM users WHERE email = ?", ("admin@njiamauzo.africa",)).fetchone()
    if not admin:
        conn.execute("""
            INSERT INTO users (name, email, phone, password_hash, role, is_verified, must_change_password, created_at)
            VALUES (?, ?, ?, ?, 'admin', 1, 1, ?)
        """, ("NjiaMauzo Admin", "admin@njiamauzo.africa", "+255700000000",
              hash_password("0000"), now_iso()))
    else:
        # Ensure admin exists; do not reset password if already set
        pass

    # Seed demo prices
    if conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 0:
        now = now_iso()
        rows = [
            ("Ufuta", "Songea", "Tanzania", 3100, 3300, 150, "Demo Market Feed"),
            ("Ufuta", "Dar es Salaam", "Tanzania", 3600, 3900, 350, "Demo Market Feed"),
            ("Ufuta", "Nairobi", "Kenya", 3700, 4100, 520, "Demo Market Feed"),
            ("Ufuta", "Kampala", "Uganda", 3400, 3800, 600, "Demo Market Feed"),
            ("Ufuta", "Kigali", "Rwanda", 3500, 4000, 650, "Demo Market Feed"),
            ("Mahindi", "Mwanza", "Tanzania", 800, 850, 120, "Demo Market Feed"),
            ("Mahindi", "Dar es Salaam", "Tanzania", 900, 1050, 250, "Demo Market Feed"),
            ("Mahindi", "Nairobi", "Kenya", 920, 1100, 480, "Demo Market Feed"),
            ("Maharage", "Arusha", "Tanzania", 2300, 2500, 180, "Demo Market Feed"),
            ("Maharage", "Dar es Salaam", "Tanzania", 2600, 2900, 260, "Demo Market Feed"),
            ("Maharage", "Kampala", "Uganda", 2100, 2500, 550, "Demo Market Feed"),
            ("Mpunga", "Morogoro", "Tanzania", 1650, 1800, 120, "Demo Market Feed"),
            ("Mpunga", "Dar es Salaam", "Tanzania", 1900, 2150, 230, "Demo Market Feed"),
            ("Mpunga", "Kigali", "Rwanda", 1900, 2300, 600, "Demo Market Feed"),
            ("Korosho", "Mtwara", "Tanzania", 4500, 5000, 170, "Demo Market Feed"),
            ("Korosho", "Dar es Salaam", "Tanzania", 5200, 5700, 300, "Demo Market Feed"),
            ("Kahawa", "Kilimanjaro", "Tanzania", 8500, 9200, 280, "Demo Market Feed"),
            ("Chai", "Mbeya", "Tanzania", 3200, 3600, 200, "Demo Market Feed"),
        ]
        conn.executemany("""
            INSERT INTO prices (crop, market, country, buy_price, sell_price, transport_per_kg, source, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [r + (now,) for r in rows])

    # Seed demo listings
    if conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 0:
        now = now_iso()
        demo = [
            ("Ufuta", 20000, 3150, "Songea", "Tanzania", "Ufuta bora kutoka Songea, grade A", 1),
            ("Mahindi", 30000, 820, "Mwanza", "Tanzania", "Mahindi ya mavuno mapya", 1),
            ("Maharage", 12000, 2350, "Arusha", "Tanzania", "Maharage nyekundu safi", 1),
            ("Mpunga", 18000, 1700, "Morogoro", "Tanzania", "Mpunga wa Morogoro", 1),
            ("Korosho", 5000, 4800, "Mtwara", "Tanzania", "Korosho mbichi za Mtwara", 1),
        ]
        for r in demo:
            conn.execute("""
                INSERT INTO listings (crop, quantity_kg, price, location, country, description, seller_id, verified, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (*r, now))

    # Default AI settings
    defaults = {
        "ai_enabled": "1",
        "ai_welcome": "Karibu NjiaMauzo AI! Ninaweza kukusaidia kutafuta mazao, bei, na masoko.",
        "moderation_enabled": "1",
        "live_feed_enabled": "1",
    }
    for k, v in defaults.items():
        conn.execute("""
            INSERT OR IGNORE INTO admin_settings (key, value, updated_at) VALUES (?, ?, ?)
        """, (k, v, now_iso()))

    conn.commit()
    conn.close()

# ──────────────────────────────────────────────
# AUTH HELPERS
# ──────────────────────────────────────────────
def logged_in():
    return bool(session.get("user_id"))

def current_user():
    if not logged_in():
        return None
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    conn.close()
    return user

def is_admin():
    user = current_user()
    return user and user["role"] == "admin"

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not logged_in():
            return jsonify(error="Login required"), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_admin():
            return jsonify(error="Admin access required"), 403
        return f(*args, **kwargs)
    return decorated

def add_activity(user_id, action_type, target_type=None, target_id=None, message=""):
    try:
        conn = db()
        conn.execute("""
            INSERT INTO activity_feed (user_id, action_type, target_type, target_id, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, action_type, target_type, target_id, message, now_iso()))
        conn.commit()
        conn.close()
    except Exception:
        pass

# ──────────────────────────────────────────────
# QUERY PARSER
# ──────────────────────────────────────────────
def parse_query(text):
    t = (text or "").lower()
    crop = next((v for k, v in CROPS.items() if k in t), None)
    loc = next((x for x in LOCATIONS if x.lower() in t), None)
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*(tani|ton|tons|kg)?', t)
    qty = None
    if m:
        qty = float(m.group(1).replace(",", ""))
        if m.group(2) in ("tani", "ton", "tons"):
            qty *= 1000
    p = re.search(r'(?:chini ya|under|below|max|<=)\s*(?:tzs)?\s*([\d,]+)', t)
    maxp = float(p.group(1).replace(",", "")) if p else None
    return crop, loc, qty, maxp

# ──────────────────────────────────────────────
# STATIC FILES
# ──────────────────────────────────────────────
@app.route("/static/<path:filename>")
def static_files(filename):
    _mt = {"css":"text/css","js":"application/javascript","png":"image/png",
           "jpg":"image/jpeg","jpeg":"image/jpeg","svg":"image/svg+xml",
           "ico":"image/x-icon","json":"application/json","woff":"font/woff",
           "woff2":"font/woff2"}
    ext = filename.rsplit(".",1)[-1].lower() if "." in filename else ""
    mimetype = _mt.get(ext)
    if mimetype:
        return send_from_directory(os.path.join(BASE, "static"), filename, mimetype=mimetype)
    return send_from_directory(os.path.join(BASE, "static"), filename)

# ──────────────────────────────────────────────
# MAIN PAGES
# ──────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/admin")
def admin_page():
    if not is_admin():
        return redirect(url_for("home"))
    return render_template("admin.html")

# ──────────────────────────────────────────────
# AUTH API
# ──────────────────────────────────────────────
@app.post("/api/register")
def register():
    d = request.json or {}
    required = ("name", "email", "password")
    if not all(d.get(k) for k in required):
        return jsonify(error="Jaza jina, email na password"), 400

    # Human verification
    if not verify_captcha(d.get("captcha_id"), d.get("captcha_answer")):
        return jsonify(error="Human verification imeshindikana. Jaribu tena."), 400

    email = d["email"].lower().strip()
    role = d.get("role", "buyer")
    if role not in ("buyer", "seller"):
        role = "buyer"

    conn = db()
    try:
        uid = conn.execute("""
            INSERT INTO users (name, email, phone, password_hash, role, location, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (d["name"].strip(), email, d.get("phone", ""),
              hash_password(d["password"]), role, d.get("location", ""), now_iso())).lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify(error="Email tayari imesajiliwa"), 409
    conn.close()

    session.update(user_id=uid, name=d["name"], role=role)
    add_activity(uid, "SYSTEM", message=f"Mtumiaji mpya: {d['name']}")
    if HAS_EMAIL:
        try:
            send_welcome_email(email, d["name"].strip())
        except Exception:
            pass
    return jsonify(ok=True, name=d["name"], role=role)

@app.post("/api/login")
def login():
    d = request.json or {}
    email = (d.get("email") or "").lower().strip()
    password = d.get("password") or ""

    # Optional captcha on login (recommended after failed attempts; always for now)
    captcha_id = d.get("captcha_id")
    if captcha_id and not verify_captcha(captcha_id, d.get("captcha_answer")):
        return jsonify(error="Human verification imeshindikana. Jaribu tena."), 400

    conn = db()
    user = conn.execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)).fetchone()
    conn.close()

    if not user or user["password_hash"] != hash_password(password):
        return jsonify(error="Email au password si sahihi"), 401

    session.update(user_id=user["id"], name=user["name"], role=user["role"])
    conn = db()
    conn.execute("UPDATE users SET last_seen = ? WHERE id = ?", (now_iso(), user["id"]))
    conn.commit()
    # Check must_change_password
    must_change = False
    try:
        must_change = bool(user["must_change_password"])
    except (IndexError, KeyError):
        must_change = False
    conn.close()

    return jsonify(
        ok=True,
        name=user["name"],
        role=user["role"],
        is_admin=user["role"] == "admin",
        must_change_password=must_change
    )

@app.get("/api/me")
def me():
    user = current_user()
    if not user:
        return jsonify(logged_in=False)
    must_change = False
    try:
        must_change = bool(user["must_change_password"])
    except (IndexError, KeyError, TypeError):
        must_change = False
    return jsonify(
        logged_in=True,
        id=user["id"],
        name=user["name"],
        email=user["email"],
        role=user["role"],
        location=user["location"],
        latitude=user["latitude"],
        longitude=user["longitude"],
        bio=user["bio"],
        is_verified=bool(user["is_verified"]),
        is_admin=user["role"] == "admin",
        must_change_password=must_change,
        followers_count=user["followers_count"],
        following_count=user["following_count"]
    )

@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)

@app.post("/api/location")
@login_required
def update_location():
    d = request.json or {}
    lat = d.get("latitude")
    lon = d.get("longitude")
    location_name = d.get("location", "")

    conn = db()
    conn.execute("""
        UPDATE users SET latitude = ?, longitude = ?, location = ?, last_seen = ?
        WHERE id = ?
    """, (lat, lon, location_name, now_iso(), session["user_id"]))
    conn.commit()
    conn.close()
    return jsonify(ok=True, location=location_name)

# ──────────────────────────────────────────────
# PRICES & STATS
# ──────────────────────────────────────────────
@app.get("/api/prices")
def prices():
    q = request.args.get("q", "").lower()
    country = request.args.get("country", "")
    crop = request.args.get("crop", "")

    conn = db()
    rows = conn.execute("SELECT * FROM prices ORDER BY recorded_at DESC, crop, market").fetchall()
    conn.close()

    out = []
    for x in rows:
        hay = f'{x["crop"]} {x["market"]} {x["country"]}'.lower()
        if q and q not in hay:
            continue
        if country and x["country"] != country:
            continue
        if crop and x["crop"] != crop:
            continue
        out.append(dict(x))
    return jsonify(out)

@app.get("/api/stats")
def stats():
    conn = db()
    data = {
        "users": conn.execute("SELECT COUNT(*) FROM users WHERE is_active=1").fetchone()[0],
        "listings": conn.execute("SELECT COUNT(*) FROM listings WHERE status='ACTIVE'").fetchone()[0],
        "markets": conn.execute("SELECT COUNT(DISTINCT market) FROM prices").fetchone()[0],
        "countries": conn.execute("SELECT COUNT(DISTINCT country) FROM prices").fetchone()[0],
        "likes": conn.execute("SELECT COUNT(*) FROM likes").fetchone()[0],
        "comments": conn.execute("SELECT COUNT(*) FROM comments WHERE is_hidden=0").fetchone()[0],
    }
    conn.close()
    return jsonify(data)

@app.post("/api/intelligence")
def intelligence():
    d = request.json or {}
    crop = d.get("crop")
    qty = float(d.get("quantity_kg") or 0)
    buy = float(d.get("source_price") or 0)
    extra = float(d.get("extra_cost_per_kg") or 0)

    if not crop or qty <= 0 or buy <= 0:
        return jsonify(error="Weka zao, kiasi na bei ya kununua"), 400

    conn = db()
    rows = conn.execute("SELECT * FROM prices WHERE crop = ?", (crop,)).fetchall()
    conn.close()

    out = []
    for x in rows:
        landed = buy + x["transport_per_kg"] + extra
        profit = x["sell_price"] - landed
        out.append({
            "market": x["market"],
            "country": x["country"],
            "sell_price": x["sell_price"],
            "transport": x["transport_per_kg"],
            "landed_cost": round(landed, 2),
            "profit_per_kg": round(profit, 2),
            "profit_total": round(profit * qty, 2),
            "margin_pct": round(profit / landed * 100, 1) if landed else 0,
            "recorded_at": x["recorded_at"],
            "source": x["source"]
        })
    out.sort(key=lambda x: x["profit_total"], reverse=True)
    return jsonify(results=out, recommendation=out[0] if out else None)

# ──────────────────────────────────────────────
# AI SEARCH & CHAT
# ──────────────────────────────────────────────
@app.post("/api/ai/search")
def ai_search():
    text = (request.json or {}).get("query", "")
    crop, loc, qty, maxp = parse_query(text)

    conn = db()
    rows = conn.execute("SELECT * FROM listings WHERE status='ACTIVE'").fetchall()
    if logged_in():
        conn.execute("INSERT INTO searches (user_id, query, created_at) VALUES (?, ?, ?)",
                     (session["user_id"], text, now_iso()))
        conn.commit()
    conn.close()

    out = []
    for x in rows:
        if crop and x["crop"] != crop:
            continue
        if loc and loc.lower() not in x["location"].lower():
            continue
        if qty and x["quantity_kg"] < qty:
            continue
        if maxp and x["price"] > maxp:
            continue
        score = (100 if crop else 0) + (40 if loc else 0) + (20 if x["verified"] else 0)
        out.append({**dict(x), "match_score": score})
    out.sort(key=lambda x: (-x["match_score"], x["price"]))

    return jsonify(
        interpreted={"crop": crop, "location": loc, "quantity_kg": qty, "max_price": maxp},
        results=out
    )

@app.post("/api/ai/chat")
def ai_chat():
    msg = (request.json or {}).get("message", "")
    crop, loc, qty, maxp = parse_query(msg)

    if crop:
        text = f"Nimeelewa unatafuta **{crop}**"
        if loc:
            text += f" katika **{loc}**"
        if qty:
            text += f", kiasi cha takribani **{qty:,.0f} kg**"
        if maxp:
            text += f", kwa bei isiyozidi **TZS {maxp:,.0f}/kg**"
        text += ".\n\nTumia **AI Search** au **Profit Intelligence** kupata matching na soko lenye makadirio bora."
    else:
        text = (
            "Karibu NjiaMauzo AI! 🌾\n\n"
            "Jaribu kuuliza kama:\n"
            "• \"Natafuta tani 20 za ufuta Songea chini ya TZS 3,200/kg\"\n"
            "• \"Nina tani 30 za mahindi Mwanza, niuze wapi?\"\n"
            "• \"Bei ya maharage Arusha leo ni ngapi?\""
        )

    # Log AI interaction
    if logged_in():
        conn = db()
        conn.execute("INSERT INTO ai_logs (user_id, query, response, created_at) VALUES (?, ?, ?, ?)",
                     (session.get("user_id"), msg, text, now_iso()))
        conn.commit()
        conn.close()

    return jsonify(reply=text)

# ──────────────────────────────────────────────
# LISTINGS
# ──────────────────────────────────────────────
@app.get("/api/listings")
def get_listings():
    q = request.args.get("q", "").lower()
    crop = request.args.get("crop", "")
    location = request.args.get("location", "")
    user_lat = request.args.get("lat", type=float)
    user_lon = request.args.get("lon", type=float)

    conn = db()
    rows = conn.execute("""
        SELECT l.*, u.name as seller_name, u.is_verified as seller_verified
        FROM listings l
        LEFT JOIN users u ON l.seller_id = u.id
        WHERE l.status = 'ACTIVE'
        ORDER BY l.verified DESC, l.likes_count DESC, l.created_at DESC
    """).fetchall()
    conn.close()

    out = []
    for x in rows:
        item = dict(x)
        hay = f'{item["crop"]} {item["location"]} {item["country"]} {item.get("description","")}'.lower()
        if q and q not in hay:
            continue
        if crop and item["crop"] != crop:
            continue
        if location and location.lower() not in item["location"].lower():
            continue

        # Simple distance calculation if coords available
        if user_lat and user_lon and item.get("latitude") and item.get("longitude"):
            # Haversine approx (km)
            from math import radians, cos, sin, asin, sqrt
            R = 6371
            dlat = radians(item["latitude"] - user_lat)
            dlon = radians(item["longitude"] - user_lon)
            a = sin(dlat/2)**2 + cos(radians(user_lat)) * cos(radians(item["latitude"])) * sin(dlon/2)**2
            item["distance_km"] = round(2 * R * asin(sqrt(a)), 1)
        else:
            item["distance_km"] = None

        out.append(item)

    # Sort by distance if available
    if user_lat and user_lon:
        out.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] or 9999))

    return jsonify(out)

@app.post("/api/listings")
@login_required
def add_listing():
    d = request.json or {}
    try:
        qty = float(d["quantity_kg"])
        price = float(d["price"])
    except (KeyError, ValueError, TypeError):
        return jsonify(error="Kiasi na bei si sahihi"), 400

    crop = d.get("crop", "").strip()
    location = d.get("location", "").strip()
    if not crop or not location:
        return jsonify(error="Zao na eneo vinahitajika"), 400

    conn = db()
    lid = conn.execute("""
        INSERT INTO listings
        (crop, quantity_kg, price, location, country, description, seller_id,
         latitude, longitude, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        crop, qty, price, location,
        d.get("country", "Tanzania"),
        d.get("description", ""),
        session["user_id"],
        d.get("latitude"),
        d.get("longitude"),
        now_iso()
    )).lastrowid
    conn.commit()
    conn.close()

    add_activity(session["user_id"], "LISTING", "listing", lid,
                 f"Ameweka listing mpya: {crop} - {qty}kg @ TZS {price}")
    return jsonify(ok=True, id=lid)

@app.get("/api/listings/<int:lid>")
def get_listing(lid):
    conn = db()
    row = conn.execute("""
        SELECT l.*, u.name as seller_name, u.is_verified as seller_verified,
               u.followers_count, u.location as seller_location
        FROM listings l
        LEFT JOIN users u ON l.seller_id = u.id
        WHERE l.id = ?
    """, (lid,)).fetchone()
    if not row:
        conn.close()
        return jsonify(error="Listing haipo"), 404

    # Increment views
    conn.execute("UPDATE listings SET views_count = views_count + 1 WHERE id = ?", (lid,))
    conn.commit()

    # Check if current user liked
    liked = False
    if logged_in():
        liked = bool(conn.execute(
            "SELECT 1 FROM likes WHERE user_id=? AND listing_id=?",
            (session["user_id"], lid)
        ).fetchone())

    conn.close()
    data = dict(row)
    data["liked"] = liked
    return jsonify(data)

# ──────────────────────────────────────────────
# LIKES
# ──────────────────────────────────────────────
@app.post("/api/listings/<int:lid>/like")
@login_required
def toggle_like(lid):
    conn = db()
    existing = conn.execute(
        "SELECT id FROM likes WHERE user_id=? AND listing_id=?",
        (session["user_id"], lid)
    ).fetchone()

    if existing:
        conn.execute("DELETE FROM likes WHERE id=?", (existing["id"],))
        conn.execute("UPDATE listings SET likes_count = MAX(0, likes_count - 1) WHERE id=?", (lid,))
        liked = False
    else:
        conn.execute(
            "INSERT INTO likes (user_id, listing_id, created_at) VALUES (?, ?, ?)",
            (session["user_id"], lid, now_iso())
        )
        conn.execute("UPDATE listings SET likes_count = likes_count + 1 WHERE id=?", (lid,))
        liked = True
        add_activity(session["user_id"], "LIKE", "listing", lid, "Amependa listing")

    conn.commit()
    count = conn.execute("SELECT likes_count FROM listings WHERE id=?", (lid,)).fetchone()["likes_count"]
    conn.close()
    return jsonify(ok=True, liked=liked, likes_count=count)

# ──────────────────────────────────────────────
# COMMENTS
# ──────────────────────────────────────────────
@app.get("/api/listings/<int:lid>/comments")
def get_comments(lid):
    conn = db()
    rows = conn.execute("""
        SELECT c.*, u.name as user_name, u.is_verified as user_verified
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.listing_id = ? AND c.is_hidden = 0
        ORDER BY c.created_at ASC
    """, (lid,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.post("/api/listings/<int:lid>/comments")
@login_required
def add_comment(lid):
    d = request.json or {}
    content = (d.get("content") or "").strip()
    if not content or len(content) < 2:
        return jsonify(error="Andika maoni angalau herufi 2"), 400
    if len(content) > 1000:
        return jsonify(error="Maoni marefu mno (max 1000)"), 400

    parent_id = d.get("parent_id")

    conn = db()
    # Check listing exists
    if not conn.execute("SELECT id FROM listings WHERE id=?", (lid,)).fetchone():
        conn.close()
        return jsonify(error="Listing haipo"), 404

    cid = conn.execute("""
        INSERT INTO comments (listing_id, user_id, parent_id, content, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (lid, session["user_id"], parent_id, content, now_iso())).lastrowid

    conn.execute("UPDATE listings SET comments_count = comments_count + 1 WHERE id=?", (lid,))
    conn.commit()
    conn.close()

    add_activity(session["user_id"], "COMMENT", "listing", lid, f"Ameandika maoni: {content[:60]}...")
    return jsonify(ok=True, id=cid)

@app.delete("/api/comments/<int:cid>")
@login_required
def delete_comment(cid):
    conn = db()
    comment = conn.execute("SELECT * FROM comments WHERE id=?", (cid,)).fetchone()
    if not comment:
        conn.close()
        return jsonify(error="Comment haipo"), 404

    # Owner or admin can delete
    if comment["user_id"] != session["user_id"] and not is_admin():
        conn.close()
        return jsonify(error="Huna ruhusa"), 403

    conn.execute("UPDATE comments SET is_hidden=1 WHERE id=?", (cid,))
    conn.execute("UPDATE listings SET comments_count = MAX(0, comments_count-1) WHERE id=?",
                 (comment["listing_id"],))
    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ──────────────────────────────────────────────
# FOLLOW
# ──────────────────────────────────────────────
@app.post("/api/users/<int:uid>/follow")
@login_required
def toggle_follow(uid):
    if uid == session["user_id"]:
        return jsonify(error="Huwezi kujifuata mwenyewe"), 400

    conn = db()
    target = conn.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone()
    if not target:
        conn.close()
        return jsonify(error="Mtumiaji haipo"), 404

    existing = conn.execute(
        "SELECT id FROM follows WHERE follower_id=? AND following_id=?",
        (session["user_id"], uid)
    ).fetchone()

    if existing:
        conn.execute("DELETE FROM follows WHERE id=?", (existing["id"],))
        conn.execute("UPDATE users SET following_count = MAX(0, following_count-1) WHERE id=?",
                     (session["user_id"],))
        conn.execute("UPDATE users SET followers_count = MAX(0, followers_count-1) WHERE id=?", (uid,))
        following = False
    else:
        conn.execute(
            "INSERT INTO follows (follower_id, following_id, created_at) VALUES (?, ?, ?)",
            (session["user_id"], uid, now_iso())
        )
        conn.execute("UPDATE users SET following_count = following_count + 1 WHERE id=?",
                     (session["user_id"],))
        conn.execute("UPDATE users SET followers_count = followers_count + 1 WHERE id=?", (uid,))
        following = True
        add_activity(session["user_id"], "FOLLOW", "user", uid, "Amefuata mtumiaji")

    conn.commit()
    count = conn.execute("SELECT followers_count FROM users WHERE id=?", (uid,)).fetchone()["followers_count"]
    conn.close()
    return jsonify(ok=True, following=following, followers_count=count)

@app.get("/api/users/<int:uid>")
def get_user(uid):
    conn = db()
    user = conn.execute("""
        SELECT id, name, bio, location, role, is_verified, followers_count, following_count, created_at
        FROM users WHERE id=? AND is_active=1
    """, (uid,)).fetchone()
    if not user:
        conn.close()
        return jsonify(error="Mtumiaji haipo"), 404

    is_following = False
    if logged_in():
        is_following = bool(conn.execute(
            "SELECT 1 FROM follows WHERE follower_id=? AND following_id=?",
            (session["user_id"], uid)
        ).fetchone())

    listings = conn.execute("""
        SELECT id, crop, quantity_kg, price, location, likes_count, comments_count, created_at
        FROM listings WHERE seller_id=? AND status='ACTIVE' ORDER BY created_at DESC LIMIT 20
    """, (uid,)).fetchall()
    conn.close()

    data = dict(user)
    data["is_following"] = is_following
    data["listings"] = [dict(l) for l in listings]
    return jsonify(data)

# ──────────────────────────────────────────────
# LIVE ACTIVITY FEED
# ──────────────────────────────────────────────
@app.get("/api/live")
def live_feed():
    limit = min(int(request.args.get("limit", 30)), 50)
    conn = db()
    rows = conn.execute("""
        SELECT a.*, u.name as user_name
        FROM activity_feed a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# ──────────────────────────────────────────────
# ALERTS
# ──────────────────────────────────────────────
@app.post("/api/alerts")
@login_required
def create_alert():
    d = request.json or {}
    crop = d.get("crop")
    target = float(d.get("target_price") or 0)
    if not crop or target <= 0:
        return jsonify(error="Weka zao na bei ya target"), 400

    conn = db()
    conn.execute("""
        INSERT INTO alerts (user_id, crop, target_price, direction, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (session["user_id"], crop, target, d.get("direction", "ABOVE"), now_iso()))
    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ──────────────────────────────────────────────
# SERVICE (Assisted Search) - kept from original
# ──────────────────────────────────────────────
def guest_token():
    if not session.get("guest_token"):
        session["guest_token"] = secrets.token_urlsafe(24)
    return session["guest_token"]

def service_access(request_id):
    conn = db()
    r = conn.execute("SELECT * FROM service_requests WHERE id=?", (request_id,)).fetchone()
    if not r:
        conn.close()
        return None, "NOT_FOUND"
    same_user = r["user_id"] and r["user_id"] == session.get("user_id")
    same_guest = r["guest_token"] and r["guest_token"] == session.get("guest_token")
    if not (same_user or same_guest):
        conn.close()
        return None, "FORBIDDEN"
    ok = False
    if r["payment_id"]:
        p = conn.execute("SELECT status FROM payments WHERE id=?", (r["payment_id"],)).fetchone()
        ok = p and p["status"] == "VERIFIED"
    conn.close()
    return r, ("OK" if ok else "PAYMENT_REQUIRED")

@app.get("/api/service/fee")
def service_fee():
    country = request.args.get("country", "Tanzania")
    cur = CURRENCY_RATES.get(country, CURRENCY_RATES["Tanzania"])
    return jsonify(
        base_amount_tzs=SERVICE_FEE_TZS,
        country=country,
        currency=cur["code"],
        amount=round(SERVICE_FEE_TZS * cur["per_tzs"], 2),
        currency_name=cur["name"]
    )

@app.post("/api/service/start")
def service_start():
    d = request.json or {}
    query = (d.get("query") or "").strip()
    if not query:
        return jsonify(error="Andika bidhaa/zao unalotafuta"), 400
    uid = session.get("user_id")
    gt = guest_token()
    conn = db()
    rid = conn.execute("""
        INSERT INTO service_requests (user_id, guest_token, query, status, created_at)
        VALUES (?, ?, ?, 'AWAITING_PAYMENT', ?)
    """, (uid, gt, query, now_iso())).lastrowid
    conn.commit()
    conn.close()
    return jsonify(ok=True, request_id=rid, status="AWAITING_PAYMENT", fee_tzs=SERVICE_FEE_TZS)

# ──────────────────────────────────────────────
# ADMIN API
# ──────────────────────────────────────────────
@app.get("/api/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = db()
    data = {
        "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "active_users": conn.execute("SELECT COUNT(*) FROM users WHERE is_active=1").fetchone()[0],
        "listings": conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0],
        "active_listings": conn.execute("SELECT COUNT(*) FROM listings WHERE status='ACTIVE'").fetchone()[0],
        "comments": conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0],
        "likes": conn.execute("SELECT COUNT(*) FROM likes").fetchone()[0],
        "payments": conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0],
        "verified_payments": conn.execute("SELECT COUNT(*) FROM payments WHERE status='VERIFIED'").fetchone()[0],
        "ai_queries": conn.execute("SELECT COUNT(*) FROM ai_logs").fetchone()[0],
        "recent_activity": [dict(r) for r in conn.execute("""
            SELECT a.*, u.name as user_name FROM activity_feed a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.created_at DESC LIMIT 15
        """).fetchall()],
        "recent_users": [dict(r) for r in conn.execute("""
            SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC LIMIT 10
        """).fetchall()],
    }
    conn.close()
    return jsonify(data)

@app.get("/api/admin/users")
@admin_required
def admin_users():
    conn = db()
    rows = conn.execute("""
        SELECT id, name, email, phone, role, location, is_verified, is_active,
               followers_count, created_at, last_seen
        FROM users ORDER BY created_at DESC
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.post("/api/admin/users/<int:uid>/toggle")
@admin_required
def admin_toggle_user(uid):
    conn = db()
    user = conn.execute("SELECT is_active, role FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        conn.close()
        return jsonify(error="User not found"), 404
    if user["role"] == "admin":
        conn.close()
        return jsonify(error="Cannot deactivate admin"), 400
    new_status = 0 if user["is_active"] else 1
    conn.execute("UPDATE users SET is_active=? WHERE id=?", (new_status, uid))
    conn.commit()
    conn.close()
    return jsonify(ok=True, is_active=bool(new_status))

@app.post("/api/admin/users/<int:uid>/verify")
@admin_required
def admin_verify_user(uid):
    conn = db()
    conn.execute("UPDATE users SET is_verified=1 WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify(ok=True)

@app.get("/api/admin/listings")
@admin_required
def admin_listings():
    conn = db()
    rows = conn.execute("""
        SELECT l.*, u.name as seller_name
        FROM listings l LEFT JOIN users u ON l.seller_id = u.id
        ORDER BY l.created_at DESC
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.post("/api/admin/listings/<int:lid>/verify")
@admin_required
def admin_verify_listing(lid):
    conn = db()
    conn.execute("UPDATE listings SET verified=1 WHERE id=?", (lid,))
    conn.commit()
    conn.close()
    return jsonify(ok=True)

@app.post("/api/admin/listings/<int:lid>/hide")
@admin_required
def admin_hide_listing(lid):
    conn = db()
    conn.execute("UPDATE listings SET status='HIDDEN' WHERE id=?", (lid,))
    conn.commit()
    conn.close()
    return jsonify(ok=True)

@app.get("/api/admin/comments")
@admin_required
def admin_comments():
    conn = db()
    rows = conn.execute("""
        SELECT c.*, u.name as user_name, l.crop as listing_crop
        FROM comments c
        JOIN users u ON c.user_id = u.id
        JOIN listings l ON c.listing_id = l.id
        ORDER BY c.created_at DESC LIMIT 100
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.post("/api/admin/comments/<int:cid>/hide")
@admin_required
def admin_hide_comment(cid):
    conn = db()
    conn.execute("UPDATE comments SET is_hidden=1 WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return jsonify(ok=True)

@app.get("/api/admin/ai-logs")
@admin_required
def admin_ai_logs():
    conn = db()
    rows = conn.execute("""
        SELECT a.*, u.name as user_name
        FROM ai_logs a LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.created_at DESC LIMIT 50
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.get("/api/admin/settings")
@admin_required
def admin_get_settings():
    conn = db()
    rows = conn.execute("SELECT key, value FROM admin_settings").fetchall()
    conn.close()
    return jsonify({r["key"]: r["value"] for r in rows})

@app.post("/api/admin/settings")
@admin_required
def admin_update_settings():
    d = request.json or {}
    conn = db()
    for k, v in d.items():
        conn.execute("""
            INSERT INTO admin_settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """, (k, str(v), now_iso()))
    conn.commit()
    conn.close()
    return jsonify(ok=True)

@app.post("/api/admin/prices")
@admin_required
def admin_add_price():
    d = request.json or {}
    required = ("crop", "market", "country", "buy_price", "sell_price")
    if not all(d.get(k) is not None for k in required):
        return jsonify(error="Missing fields"), 400
    conn = db()
    conn.execute("""
        INSERT INTO prices (crop, market, country, buy_price, sell_price, transport_per_kg, source, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        d["crop"], d["market"], d["country"],
        float(d["buy_price"]), float(d["sell_price"]),
        float(d.get("transport_per_kg", 0)),
        d.get("source", "Admin"), now_iso()
    ))
    conn.commit()
    conn.close()
    add_activity(session["user_id"], "PRICE_UPDATE", message=f"Bei mpya: {d['crop']} @ {d['market']}")
    return jsonify(ok=True)


# ──────────────────────────────────────────────
# CAPTCHA (Human Verification)
# ──────────────────────────────────────────────
import random

@app.get("/api/captcha")
def get_captcha():
    """Generate simple math CAPTCHA."""
    a = random.randint(2, 15)
    b = random.randint(1, 12)
    op = random.choice(["+", "-"])
    if op == "+":
        answer = str(a + b)
        question = f"{a} + {b} = ?"
    else:
        if a < b:
            a, b = b, a
        answer = str(a - b)
        question = f"{a} - {b} = ?"

    cid = secrets.token_urlsafe(12)
    expires = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    conn = db()
    conn.execute("INSERT INTO captcha_challenges (id, answer, expires_at) VALUES (?, ?, ?)",
                 (cid, answer, expires))
    # Cleanup old
    conn.execute("DELETE FROM captcha_challenges WHERE expires_at < ?", (now_iso(),))
    conn.commit()
    conn.close()
    return jsonify(captcha_id=cid, question=question)


def verify_captcha(captcha_id, user_answer):
    if not captcha_id or user_answer is None:
        return False
    conn = db()
    row = conn.execute("SELECT answer, expires_at FROM captcha_challenges WHERE id=?",
                       (captcha_id,)).fetchone()
    if not row:
        conn.close()
        return False
    if row["expires_at"] < now_iso():
        conn.execute("DELETE FROM captcha_challenges WHERE id=?", (captcha_id,))
        conn.commit()
        conn.close()
        return False
    ok = str(user_answer).strip() == str(row["answer"]).strip()
    # One-time use
    conn.execute("DELETE FROM captcha_challenges WHERE id=?", (captcha_id,))
    conn.commit()
    conn.close()
    return ok


# ──────────────────────────────────────────────
# OTP SYSTEM (Email / SMS / WhatsApp)
# ──────────────────────────────────────────────
def generate_otp_code():
    return f"{random.randint(100000, 999999)}"


def send_otp_demo(channel, destination, code, purpose):
    """
    Send OTP via EMAIL (info@njiamauzo.africa), SMS or WhatsApp.
    Demo logs to console; production uses SMTP / gateway env vars.
    """
    msg = f"[NjiaMauzo OTP] Code: {code} | Purpose: {purpose} | To: {destination} via {channel}"
    print(f"\n📨 OTP SENT → {msg}\n")
    if channel == "EMAIL" and HAS_EMAIL:
        try:
            if purpose == "RESET":
                send_password_reset_email(destination, "", code)
            else:
                send_otp_email(destination, code, purpose)
        except Exception as e:
            print(f"[email] {e}")
    return {"ok": True, "demo": True, "message": msg, "code_for_demo": code}


@app.post("/api/otp/send")
def otp_send():
    d = request.json or {}
    email = (d.get("email") or "").lower().strip()
    phone = (d.get("phone") or "").strip()
    channel = (d.get("channel") or "EMAIL").upper()  # EMAIL | SMS | WHATSAPP
    purpose = (d.get("purpose") or "RESET").upper()  # RESET | VERIFY | LOGIN | PAYMENT

    if channel not in ("EMAIL", "SMS", "WHATSAPP"):
        return jsonify(error="Channel must be EMAIL, SMS or WHATSAPP"), 400
    if channel == "EMAIL" and not email:
        return jsonify(error="Email inahitajika"), 400
    if channel in ("SMS", "WHATSAPP") and not phone:
        return jsonify(error="Namba ya simu inahitajika"), 400

    # Find user if exists
    conn = db()
    user = None
    if email:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    elif phone:
        user = conn.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()

    if purpose == "RESET" and not user:
        conn.close()
        return jsonify(error="Akaunti haipo kwa email/simu hiyo"), 404

    code = generate_otp_code()
    expires = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    dest = email if channel == "EMAIL" else phone

    conn.execute("""
        INSERT INTO otps (user_id, email, phone, code, purpose, channel, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user["id"] if user else None,
        email or (user["email"] if user else None),
        phone or (user["phone"] if user else None),
        code, purpose, channel, expires, now_iso()
    ))
    conn.commit()
    conn.close()

    result = send_otp_demo(channel, dest, code, purpose)
    # In production do NOT return the code. For demo we return it so testing is easy.
    return jsonify(
        ok=True,
        channel=channel,
        destination=dest,
        expires_in_minutes=10,
        message=f"OTP imetumwa kupitia {channel}",
        demo_code=result.get("code_for_demo")  # remove in production
    )


@app.post("/api/otp/verify")
def otp_verify():
    d = request.json or {}
    code = str(d.get("code") or "").strip()
    email = (d.get("email") or "").lower().strip()
    phone = (d.get("phone") or "").strip()
    purpose = (d.get("purpose") or "RESET").upper()

    if not code:
        return jsonify(error="Weka OTP code"), 400

    conn = db()
    q = "SELECT * FROM otps WHERE code=? AND purpose=? AND used=0 ORDER BY id DESC LIMIT 1"
    params = [code, purpose]
    row = conn.execute(q, params).fetchone()

    if not row:
        conn.close()
        return jsonify(error="OTP si sahihi"), 400
    if row["expires_at"] < now_iso():
        conn.close()
        return jsonify(error="OTP imeisha muda (expired)"), 400

    # Optional match email/phone
    if email and row["email"] and row["email"] != email:
        conn.close()
        return jsonify(error="OTP haihusu email hii"), 400
    if phone and row["phone"] and row["phone"] != phone:
        conn.close()
        return jsonify(error="OTP haihusu namba hii"), 400

    conn.execute("UPDATE otps SET used=1 WHERE id=?", (row["id"],))
    conn.commit()

    # Issue a short-lived reset token for password reset
    reset_token = None
    if purpose == "RESET":
        reset_token = secrets.token_urlsafe(24)
        session["reset_token"] = reset_token
        session["reset_user_id"] = row["user_id"]
        session["reset_expires"] = (datetime.utcnow() + timedelta(minutes=15)).isoformat()

    conn.close()
    return jsonify(ok=True, purpose=purpose, reset_token=reset_token)


@app.post("/api/password/reset")
def password_reset():
    """Reset password after OTP verification."""
    d = request.json or {}
    new_password = d.get("new_password") or ""
    reset_token = d.get("reset_token") or session.get("reset_token")

    if len(new_password) < 4:
        return jsonify(error="Nenosiri jipya angalau herufi 4"), 400
    if not reset_token or reset_token != session.get("reset_token"):
        return jsonify(error="Reset token si sahihi. Omba OTP upya."), 400
    if session.get("reset_expires", "") < now_iso():
        return jsonify(error="Reset token imeisha muda"), 400

    uid = session.get("reset_user_id")
    if not uid:
        return jsonify(error="User not found for reset"), 400

    conn = db()
    conn.execute("""
        UPDATE users SET password_hash=?, must_change_password=0, password_changed_at=?
        WHERE id=?
    """, (hash_password(new_password), now_iso(), uid))
    conn.commit()
    conn.close()

    session.pop("reset_token", None)
    session.pop("reset_user_id", None)
    session.pop("reset_expires", None)
    return jsonify(ok=True, message="Nenosiri limebadilishwa. Ingia sasa.")


@app.post("/api/password/change")
@login_required
def password_change():
    """Logged-in user changes password (e.g. admin from 0000)."""
    d = request.json or {}
    current = d.get("current_password") or ""
    new_password = d.get("new_password") or ""

    if len(new_password) < 4:
        return jsonify(error="Nenosiri jipya angalau herufi 4"), 400

    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    if not user or user["password_hash"] != hash_password(current):
        conn.close()
        return jsonify(error="Nenosiri la sasa si sahihi"), 401

    conn.execute("""
        UPDATE users SET password_hash=?, must_change_password=0, password_changed_at=?
        WHERE id=?
    """, (hash_password(new_password), now_iso(), session["user_id"]))
    conn.commit()
    conn.close()
    return jsonify(ok=True, message="Nenosiri limebadilishwa")


# ──────────────────────────────────────────────
# ENHANCED ONLINE PAYMENTS
# ──────────────────────────────────────────────
@app.get("/api/payments/methods")
def payment_methods():
    return jsonify(methods=[
        {"id": "MPESA", "name": "M-Pesa", "icon": "📱", "countries": ["Tanzania", "Kenya"]},
        {"id": "TIGOPESA", "name": "Tigo Pesa", "icon": "📱", "countries": ["Tanzania"]},
        {"id": "AIRTELMONEY", "name": "Airtel Money", "icon": "📱", "countries": ["Tanzania", "Kenya", "Uganda", "Rwanda"]},
        {"id": "CARD", "name": "Card (Visa/Mastercard)", "icon": "💳", "countries": ["All"]},
        {"id": "BANK", "name": "Bank Transfer", "icon": "🏦", "countries": ["All"]},
        {"id": "FLUTTERWAVE", "name": "Flutterwave", "icon": "🌍", "countries": ["All"]},
    ])


@app.post("/api/payments/initiate")
def payment_initiate():
    """Start an online payment (demo + structure for real gateways)."""
    d = request.json or {}
    amount = float(d.get("amount") or 0)
    method = (d.get("method") or "MPESA").upper()
    phone = (d.get("phone") or "").strip()
    email = (d.get("email") or "").strip()
    purpose = d.get("purpose") or "SERVICE"  # SERVICE | ORDER | LISTING_BOOST
    listing_id = d.get("listing_id")
    country = d.get("country") or "Tanzania"

    if amount <= 0:
        return jsonify(error="Kiasi si sahihi"), 400
    if method in ("MPESA", "TIGOPESA", "AIRTELMONEY") and not phone:
        return jsonify(error="Namba ya simu inahitajika kwa mobile money"), 400

    ref = "NM-" + secrets.token_hex(5).upper()
    uid = session.get("user_id")

    # Optional OTP confirmation for high amounts
    require_otp = amount >= 50000
    otp_sent = False
    demo_otp = None
    if require_otp:
        code = generate_otp_code()
        expires = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
        conn = db()
        conn.execute("""
            INSERT INTO otps (user_id, email, phone, code, purpose, channel, expires_at, created_at)
            VALUES (?, ?, ?, ?, 'PAYMENT', ?, ?, ?)
        """, (uid, email, phone, code, "SMS" if phone else "EMAIL", expires, now_iso()))
        conn.commit()
        conn.close()
        r = send_otp_demo("SMS" if phone else "EMAIL", phone or email, code, "PAYMENT")
        otp_sent = True
        demo_otp = r.get("code_for_demo")

    conn = db()
    pid = conn.execute("""
        INSERT INTO payments (user_id, amount, method, status, reference, created_at)
        VALUES (?, ?, ?, 'PENDING', ?, ?)
    """, (uid, amount, method, ref, now_iso())).lastrowid

    conn.execute("""
        INSERT INTO payment_events (payment_id, event_type, payload, created_at)
        VALUES (?, 'INITIATED', ?, ?)
    """, (pid, json.dumps({
        "method": method, "phone": phone, "email": email,
        "purpose": purpose, "listing_id": listing_id, "country": country,
        "require_otp": require_otp
    }), now_iso()))
    conn.commit()
    conn.close()

    # Demo: simulate STK push instruction
    instructions = {
        "MPESA": f"STK Push imetumwa kwa {phone}. Weka PIN yako ya M-Pesa.",
        "TIGOPESA": f"Ombi la malipo limetumwa kwa {phone} (Tigo Pesa).",
        "AIRTELMONEY": f"Ombi la malipo limetumwa kwa {phone} (Airtel Money).",
        "CARD": "Fungua ukurasa wa card payment (Stripe/Flutterwave) — demo mode.",
        "BANK": f"Weka kiasi kwenye akaunti yetu. Reference: {ref}",
        "FLUTTERWAVE": "Redirect to Flutterwave checkout — demo mode.",
    }

    return jsonify(
        ok=True,
        payment_id=pid,
        reference=ref,
        status="PENDING",
        method=method,
        amount=amount,
        require_otp=require_otp,
        otp_sent=otp_sent,
        demo_otp=demo_otp,
        instructions=instructions.get(method, "Subiri uthibitisho."),
        message="Malipo yameanzishwa. Katika production gateway itathibitisha kiotomatiki."
    )


@app.post("/api/payments/confirm")
def payment_confirm():
    """Confirm payment (demo: mark VERIFIED). Production: webhook from gateway."""
    d = request.json or {}
    ref = d.get("reference")
    otp = str(d.get("otp") or "").strip()

    if not ref:
        return jsonify(error="Reference inahitajika"), 400

    conn = db()
    p = conn.execute("SELECT * FROM payments WHERE reference=?", (ref,)).fetchone()
    if not p:
        conn.close()
        return jsonify(error="Payment haipo"), 404
    if p["status"] == "VERIFIED":
        conn.close()
        return jsonify(ok=True, status="VERIFIED", message="Tayari imethibitishwa")

    # If OTP was required, verify it
    events = conn.execute(
        "SELECT payload FROM payment_events WHERE payment_id=? AND event_type='INITIATED'",
        (p["id"],)
    ).fetchone()
    if events:
        payload = json.loads(events["payload"] or "{}")
        if payload.get("require_otp"):
            otp_row = conn.execute("""
                SELECT * FROM otps WHERE purpose='PAYMENT' AND used=0 AND code=?
                ORDER BY id DESC LIMIT 1
            """, (otp,)).fetchone()
            if not otp_row or otp_row["expires_at"] < now_iso():
                conn.close()
                return jsonify(error="OTP ya malipo si sahihi au imeisha"), 400
            conn.execute("UPDATE otps SET used=1 WHERE id=?", (otp_row["id"],))

    conn.execute("UPDATE payments SET status='VERIFIED' WHERE id=?", (p["id"],))
    conn.execute("""
        INSERT INTO payment_events (payment_id, event_type, payload, created_at)
        VALUES (?, 'VERIFIED', ?, ?)
    """, (p["id"], json.dumps(d), now_iso()))
    conn.commit()
    conn.close()
    return jsonify(ok=True, status="VERIFIED", reference=ref, message="Malipo yamethibitishwa!")


@app.get("/api/payments/status/<ref>")
def payment_status(ref):
    conn = db()
    p = conn.execute("SELECT id, amount, method, status, reference, created_at FROM payments WHERE reference=?",
                     (ref,)).fetchone()
    conn.close()
    if not p:
        return jsonify(error="Not found"), 404
    return jsonify(dict(p))


# ──────────────────────────────────────────────
# STARTUP
# ──────────────────────────────────────────────

@app.get("/api/info-email")
def info_email_config():
    if HAS_EMAIL:
        return jsonify(get_info_email_config())
    return jsonify(info_email="info@njiamauzo.africa", smtp_configured=False, templates=[])

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print(f"\n🌾 NjiaMauzo Afrika Pro running on http://0.0.0.0:{port}")
    print(f"   Admin login → email: admin@njiamauzo.africa  |  password: 0000 (badilisha baadaye)\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
