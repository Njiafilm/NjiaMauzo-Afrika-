"""
NjiaMauzo Afrika v5.3 — Dual Database Support
Supports SQLite (default) and PostgreSQL via environment variables.
"""
import os
import re
import time
import secrets
import hashlib
from datetime import datetime
from contextlib import contextmanager
from urllib.parse import urlparse

from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
)

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
# DATABASE_URL examples:
#   sqlite:///njiamauzo_v5.3.db          (default)
#   postgresql://user:pass@host:5432/dbname
#   postgres://user:pass@host:5432/dbname
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///" + os.path.join(os.path.dirname(__file__), "njiamauzo_v5.3.db")

_parsed = urlparse(DATABASE_URL)
DB_TYPE = "postgres" if _parsed.scheme in ("postgres", "postgresql") else "sqlite"

# Simple in-memory cache
_cache = {}

def cache_get(key, ttl=60):
    item = _cache.get(key)
    if item and time.time() < item["expires"]:
        return item["data"]
    return None

def cache_set(key, data, ttl=60):
    _cache[key] = {"data": data, "expires": time.time() + ttl}

def cache_clear(prefix=None):
    if prefix is None:
        _cache.clear()
    else:
        for k in list(_cache.keys()):
            if k.startswith(prefix):
                del _cache[k]


# ---------------------------------------------------------------------------
# Database drivers & helpers
# ---------------------------------------------------------------------------
if DB_TYPE == "postgres":
    import psycopg2
    import psycopg2.extras

    def _connect():
        # Support both postgres:// and postgresql://
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url)
        conn.autocommit = False
        return conn

    class DictCursor:
        """Make psycopg2 rows behave like sqlite3.Row (dict-like)."""
        def __init__(self, cursor):
            self._cursor = cursor
            self._description = None

        def execute(self, sql, params=None):
            # Convert ? placeholders to %s for psycopg2
            sql = sql.replace("?", "%s")
            self._cursor.execute(sql, params or ())
            self._description = self._cursor.description
            return self

        def executemany(self, sql, params_seq):
            sql = sql.replace("?", "%s")
            self._cursor.executemany(sql, params_seq)
            return self

        def fetchone(self):
            row = self._cursor.fetchone()
            if row is None:
                return None
            cols = [d[0] for d in self._cursor.description]
            return dict(zip(cols, row))

        def fetchall(self):
            rows = self._cursor.fetchall()
            if not rows:
                return []
            cols = [d[0] for d in self._cursor.description]
            return [dict(zip(cols, r)) for r in rows]

        @property
        def lastrowid(self):
            # Caller should use RETURNING id for inserts
            return getattr(self._cursor, "lastrowid", None)

        def close(self):
            self._cursor.close()

    def _cursor(conn):
        return DictCursor(conn.cursor())

    def _get_last_id(cur, table):
        """For PostgreSQL inserts without RETURNING we fall back to lastval."""
        cur.execute("SELECT lastval()")
        row = cur.fetchone()
        return row["lastval"] if row else None

else:
    # SQLite
    import sqlite3

    def _connect():
        path = DATABASE_URL.replace("sqlite:///", "")
        conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Performance PRAGMAs
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA cache_size=-64000;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA mmap_size=268435456;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _cursor(conn):
        return conn.cursor()

    def _get_last_id(cur, table):
        return cur.lastrowid


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def hp(password):
    salt = os.environ.get("PASSWORD_SALT", "njiamauzo-v5.3").encode()
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 160000).hex()


def init_db():
    with get_db() as conn:
        cur = _cursor(conn)

        if DB_TYPE == "postgres":
            # PostgreSQL schema
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
              id SERIAL PRIMARY KEY,
              name TEXT NOT NULL,
              email TEXT UNIQUE NOT NULL,
              phone TEXT,
              password_hash TEXT NOT NULL,
              role TEXT DEFAULT 'buyer',
              verified INTEGER DEFAULT 0,
              created_at TEXT NOT NULL
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS prices (
              id SERIAL PRIMARY KEY,
              crop TEXT,
              market TEXT,
              country TEXT,
              buy_price DOUBLE PRECISION,
              sell_price DOUBLE PRECISION,
              transport_per_kg DOUBLE PRECISION,
              source TEXT,
              recorded_at TEXT
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS listings (
              id SERIAL PRIMARY KEY,
              crop TEXT,
              quantity_kg DOUBLE PRECISION,
              price DOUBLE PRECISION,
              location TEXT,
              country TEXT,
              seller_id INTEGER,
              verified INTEGER DEFAULT 0,
              status TEXT DEFAULT 'ACTIVE',
              created_at TEXT
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
              id SERIAL PRIMARY KEY,
              buyer_id INTEGER,
              listing_id INTEGER,
              quantity_kg DOUBLE PRECISION,
              unit_price DOUBLE PRECISION,
              total DOUBLE PRECISION,
              status TEXT DEFAULT 'PENDING',
              created_at TEXT
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS payments (
              id SERIAL PRIMARY KEY,
              user_id INTEGER,
              amount DOUBLE PRECISION,
              method TEXT,
              status TEXT DEFAULT 'PENDING',
              reference TEXT UNIQUE,
              purpose TEXT,
              created_at TEXT
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
              id SERIAL PRIMARY KEY,
              user_id INTEGER,
              crop TEXT,
              target_price DOUBLE PRECISION,
              market TEXT,
              created_at TEXT
            );
            """)
        else:
            # SQLite schema
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              email TEXT UNIQUE NOT NULL,
              phone TEXT,
              password_hash TEXT NOT NULL,
              role TEXT DEFAULT 'buyer',
              verified INTEGER DEFAULT 0,
              created_at TEXT NOT NULL
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS prices(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              crop TEXT, market TEXT, country TEXT,
              buy_price REAL, sell_price REAL, transport_per_kg REAL,
              source TEXT, recorded_at TEXT
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS listings(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              crop TEXT, quantity_kg REAL, price REAL,
              location TEXT, country TEXT, seller_id INTEGER,
              verified INTEGER DEFAULT 0, status TEXT DEFAULT 'ACTIVE',
              created_at TEXT
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS orders(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              buyer_id INTEGER, listing_id INTEGER,
              quantity_kg REAL, unit_price REAL, total REAL,
              status TEXT DEFAULT 'PENDING', created_at TEXT
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS payments(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER, amount REAL, method TEXT,
              status TEXT DEFAULT 'PENDING', reference TEXT UNIQUE,
              purpose TEXT, created_at TEXT
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER, crop TEXT, target_price REAL,
              market TEXT, created_at TEXT
            );
            """)

        # Indexes (same for both)
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_prices_crop ON prices(crop)",
            "CREATE INDEX IF NOT EXISTS idx_prices_country ON prices(country)",
            "CREATE INDEX IF NOT EXISTS idx_prices_crop_country ON prices(crop, country)",
            "CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status)",
            "CREATE INDEX IF NOT EXISTS idx_listings_crop ON listings(crop)",
            "CREATE INDEX IF NOT EXISTS idx_listings_seller ON listings(seller_id)",
            "CREATE INDEX IF NOT EXISTS idx_listings_status_crop ON listings(status, crop)",
            "CREATE INDEX IF NOT EXISTS idx_orders_buyer ON orders(buyer_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_listing ON orders(listing_id)",
            "CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_payments_ref ON payments(reference)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts(user_id)",
        ]
        for sql in indexes:
            try:
                cur.execute(sql)
            except Exception:
                pass  # index may already exist with different name

        # Seed prices
        cur.execute("SELECT COUNT(*) AS cnt FROM prices")
        row = cur.fetchone()
        count = row["cnt"] if isinstance(row, dict) else row[0]
        if count == 0:
            now = datetime.utcnow().isoformat()
            rows = [
                ("Ufuta", "Songea", "Tanzania", 3100, 3300, 150),
                ("Ufuta", "Dar es Salaam", "Tanzania", 3600, 3900, 350),
                ("Ufuta", "Nairobi", "Kenya", 3700, 4100, 520),
                ("Ufuta", "Kampala", "Uganda", 3500, 4000, 480),
                ("Mahindi", "Mwanza", "Tanzania", 800, 850, 120),
                ("Mahindi", "Dar es Salaam", "Tanzania", 900, 1050, 250),
                ("Mahindi", "Nairobi", "Kenya", 980, 1100, 430),
                ("Maharage", "Arusha", "Tanzania", 2300, 2500, 180),
                ("Maharage", "Dar es Salaam", "Tanzania", 2600, 2900, 260),
                ("Mpunga", "Morogoro", "Tanzania", 1650, 1800, 120),
                ("Mpunga", "Dar es Salaam", "Tanzania", 1900, 2150, 230),
                ("Korosho", "Mtwara", "Tanzania", 4500, 5000, 170),
                ("Korosho", "Dar es Salaam", "Tanzania", 5200, 5700, 300),
            ]
            for r in rows:
                cur.execute(
                    "INSERT INTO prices (crop, market, country, buy_price, sell_price, transport_per_kg, source, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                    r + ("NjiaMauzo Demo Dataset", now)
                )

        # Demo users
        if os.environ.get("SEED_DEMO_USERS", "0") == "1":
            demo = [
                ("Admin", "admin@njiamauzo.demo", "admin123", "admin"),
                ("Juma", "juma@njiamauzo.demo", "seller123", "seller"),
                ("Amina", "amina@njiamauzo.demo", "buyer123", "buyer"),
            ]
            for name, email, password, role in demo:
                cur.execute("SELECT 1 AS x FROM users WHERE email=?", (email,))
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO users (name, email, phone, password_hash, role, verified, created_at) VALUES (?,?,?,?,?,?,?)",
                        (name, email, "", hp(password), role, 1, datetime.utcnow().isoformat())
                    )


def parse_query(t):
    t = (t or "").lower()
    crops = {
        "mahindi": "Mahindi", "maize": "Mahindi",
        "ufuta": "Ufuta", "sesame": "Ufuta",
        "maharage": "Maharage", "beans": "Maharage",
        "mpunga": "Mpunga", "rice": "Mpunga",
        "korosho": "Korosho", "cashew": "Korosho",
    }
    crop = next((v for k, v in crops.items() if k in t), None)
    places = ["Songea", "Ruvuma", "Mwanza", "Arusha", "Morogoro", "Mtwara",
              "Dar es Salaam", "Nairobi", "Kampala", "Kigali"]
    loc = next((x for x in places if x.lower() in t), None)
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*(tani|ton|tons|kg)?', t)
    qty = None
    if m:
        qty = float(m.group(1).replace(",", ""))
        if m.group(2) in ("tani", "ton", "tons"):
            qty *= 1000
    p = re.search(r'(?:chini ya|under|below|max|<=)\s*(?:tzs)?\s*([\d,]+)', t)
    return crop, loc, qty, float(p.group(1).replace(",", "")) if p else None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.get("/api/me")
def me():
    return jsonify(
        logged_in=bool(session.get("user_id")),
        name=session.get("name"),
        role=session.get("role"),
    )


@app.post("/api/register")
def register():
    d = request.json or {}
    if not d.get("name") or not d.get("email") or not d.get("password"):
        return jsonify(error="Jina, email na password vinahitajika"), 400
    if len(d["password"]) < 6:
        return jsonify(error="Password iwe na angalau herufi/namba 6"), 400
    role = d.get("role", "buyer")
    if role not in ("buyer", "seller"):
        role = "buyer"

    with get_db() as conn:
        cur = _cursor(conn)
        try:
            if DB_TYPE == "postgres":
                cur.execute(
                    "INSERT INTO users (name, email, phone, password_hash, role, created_at) VALUES (?,?,?,?,?,?) RETURNING id",
                    (d["name"], d["email"].strip().lower(), d.get("phone", ""),
                     hp(d["password"]), role, datetime.utcnow().isoformat())
                )
                row = cur.fetchone()
                uid = row["id"]
            else:
                cur.execute(
                    "INSERT INTO users (name, email, phone, password_hash, role, created_at) VALUES (?,?,?,?,?,?)",
                    (d["name"], d["email"].strip().lower(), d.get("phone", ""),
                     hp(d["password"]), role, datetime.utcnow().isoformat())
                )
                uid = cur.lastrowid
        except Exception as e:
            msg = str(e).lower()
            if "unique" in msg or "duplicate" in msg:
                return jsonify(error="Email tayari imesajiliwa"), 409
            raise

    session.update(user_id=uid, name=d["name"], role=role)
    return jsonify(ok=True, name=d["name"], role=role)


@app.post("/api/login")
def login():
    d = request.json or {}
    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(
            "SELECT id, name, role, password_hash FROM users WHERE email=?",
            (d.get("email", "").strip().lower(),)
        )
        u = cur.fetchone()
    if not u or u["password_hash"] != hp(d.get("password", "")):
        return jsonify(error="Email au password si sahihi"), 401
    session.update(user_id=u["id"], name=u["name"], role=u["role"])
    return jsonify(ok=True, name=u["name"], role=u["role"])


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/prices")
def prices():
    q = request.args.get("q", "").lower()
    country = request.args.get("country", "")
    cache_key = f"prices:{q}:{country}"
    cached = cache_get(cache_key, ttl=45)
    if cached is not None:
        return jsonify(cached)

    with get_db() as conn:
        cur = _cursor(conn)
        if country and q:
            cur.execute("""
                SELECT crop, market, country, buy_price, sell_price, transport_per_kg, source, recorded_at
                FROM prices
                WHERE country = ? AND (crop LIKE ? OR market LIKE ? OR country LIKE ?)
                ORDER BY crop, market
            """, (country, f"%{q}%", f"%{q}%", f"%{q}%"))
        elif country:
            cur.execute("""
                SELECT crop, market, country, buy_price, sell_price, transport_per_kg, source, recorded_at
                FROM prices WHERE country = ? ORDER BY crop, market
            """, (country,))
        elif q:
            cur.execute("""
                SELECT crop, market, country, buy_price, sell_price, transport_per_kg, source, recorded_at
                FROM prices
                WHERE crop LIKE ? OR market LIKE ? OR country LIKE ?
                ORDER BY crop, market
            """, (f"%{q}%", f"%{q}%", f"%{q}%"))
        else:
            cur.execute("""
                SELECT crop, market, country, buy_price, sell_price, transport_per_kg, source, recorded_at
                FROM prices ORDER BY crop, market
            """)
        rows = cur.fetchall()

    result = [dict(x) for x in rows]
    cache_set(cache_key, result, ttl=45)
    return jsonify(result)


@app.post("/api/intelligence")
def intelligence():
    d = request.json or {}
    crop = d.get("crop")
    qty = float(d.get("quantity_kg") or 0)
    buy = float(d.get("source_price") or 0)
    extra = float(d.get("extra_cost_per_kg") or 0)
    if not crop or qty <= 0 or buy <= 0:
        return jsonify(error="Weka zao, kiasi na bei ya kununua"), 400

    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(
            "SELECT market, country, sell_price, transport_per_kg FROM prices WHERE crop=?",
            (crop,)
        )
        rows = cur.fetchall()

    results = []
    for x in rows:
        transport = x["transport_per_kg"] or 0
        landed = buy + transport + extra
        profit_per_kg = x["sell_price"] - landed
        profit_total = profit_per_kg * qty
        margin = (profit_per_kg / x["sell_price"] * 100) if x["sell_price"] else 0
        results.append({
            "market": x["market"],
            "country": x["country"],
            "sell_price": x["sell_price"],
            "transport": transport,
            "landed_cost": round(landed, 2),
            "profit_per_kg": round(profit_per_kg, 2),
            "profit_total": round(profit_total, 2),
            "margin_pct": round(margin, 2),
        })
    results.sort(key=lambda r: -r["profit_total"])
    recommendation = results[0] if results else None
    return jsonify(results=results, recommendation=recommendation)


@app.get("/api/listings")
def listings():
    q = request.args.get("q", "").lower()
    with get_db() as conn:
        cur = _cursor(conn)
        if q:
            cur.execute("""
                SELECT id, crop, quantity_kg, price, location, country, seller_id, verified, status, created_at
                FROM listings
                WHERE status='ACTIVE' AND (crop LIKE ? OR location LIKE ? OR country LIKE ?)
                ORDER BY created_at DESC
            """, (f"%{q}%", f"%{q}%", f"%{q}%"))
        else:
            cur.execute("""
                SELECT id, crop, quantity_kg, price, location, country, seller_id, verified, status, created_at
                FROM listings WHERE status='ACTIVE' ORDER BY created_at DESC
            """)
        rows = cur.fetchall()
    return jsonify([dict(x) for x in rows])


@app.post("/api/listings")
def create_listing():
    if not session.get("user_id"):
        return jsonify(error="Login required"), 401
    d = request.json or {}
    crop = d.get("crop")
    try:
        qty = float(d.get("quantity_kg") or 0)
        price = float(d.get("price") or 0)
    except (TypeError, ValueError):
        return jsonify(error="Kiasi au bei si sahihi"), 400
    if not crop or qty <= 0 or price <= 0:
        return jsonify(error="Weka zao, kiasi na bei"), 400

    with get_db() as conn:
        cur = _cursor(conn)
        if DB_TYPE == "postgres":
            cur.execute("""
                INSERT INTO listings (crop, quantity_kg, price, location, country, seller_id, created_at)
                VALUES (?,?,?,?,?,?,?) RETURNING id
            """, (crop, qty, price, d.get("location", ""), d.get("country", "Tanzania"),
                  session["user_id"], datetime.utcnow().isoformat()))
            lid = cur.fetchone()["id"]
        else:
            cur.execute("""
                INSERT INTO listings (crop, quantity_kg, price, location, country, seller_id, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (crop, qty, price, d.get("location", ""), d.get("country", "Tanzania"),
                  session["user_id"], datetime.utcnow().isoformat()))
            lid = cur.lastrowid

    return jsonify(ok=True, id=lid)


@app.post("/api/orders")
def create_order():
    if not session.get("user_id"):
        return jsonify(error="Login required"), 401
    d = request.json or {}
    try:
        listing_id = int(d.get("listing_id"))
        qty = float(d.get("quantity_kg") or 0)
    except (TypeError, ValueError):
        return jsonify(error="Data si sahihi"), 400
    if qty <= 0:
        return jsonify(error="Kiasi lazima kiwe chanya"), 400

    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(
            "SELECT id, price, quantity_kg, status FROM listings WHERE id=?",
            (listing_id,)
        )
        listing = cur.fetchone()
        if not listing or listing["status"] != "ACTIVE":
            return jsonify(error="Bidhaa haipatikani"), 404
        if qty > listing["quantity_kg"]:
            return jsonify(error="Kiasi kinazidi kilichopo"), 400
        total = qty * listing["price"]

        if DB_TYPE == "postgres":
            cur.execute("""
                INSERT INTO orders (buyer_id, listing_id, quantity_kg, unit_price, total, created_at)
                VALUES (?,?,?,?,?,?) RETURNING id
            """, (session["user_id"], listing_id, qty, listing["price"], total,
                  datetime.utcnow().isoformat()))
            oid = cur.fetchone()["id"]
        else:
            cur.execute("""
                INSERT INTO orders (buyer_id, listing_id, quantity_kg, unit_price, total, created_at)
                VALUES (?,?,?,?,?,?)
            """, (session["user_id"], listing_id, qty, listing["price"], total,
                  datetime.utcnow().isoformat()))
            oid = cur.lastrowid

    return jsonify(ok=True, order_id=oid, total=total)


@app.post("/api/ai/search")
def ai_search():
    crop, loc, qty, maxp = parse_query((request.json or {}).get("query", ""))
    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute("""
            SELECT id, crop, quantity_kg, price, location, country, seller_id, verified, status
            FROM listings WHERE status='ACTIVE'
        """)
        rows = cur.fetchall()

    out = []
    for x in rows:
        if crop and x["crop"] != crop:
            continue
        if loc and loc.lower() not in (x["location"] or "").lower():
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
        results=out,
    )


@app.post("/api/ai/chat")
def ai_chat():
    text = (request.json or {}).get("message", "")
    crop, loc, qty, maxp = parse_query(text)
    if crop:
        answer = f"Nimeelewa unatafuta {crop}" + (f" katika {loc}" if loc else "") + \
                 ". Naweza kusaidia kulinganisha bei, usafiri na faida."
    else:
        answer = "Uliza mfano: 'Nina tani 20 za ufuta Songea, niuze wapi?'"
    return jsonify(reply=answer)


@app.post("/api/alerts")
def alerts():
    if not session.get("user_id"):
        return jsonify(error="Login required"), 401
    d = request.json or {}
    with get_db() as conn:
        cur = _cursor(conn)
        if DB_TYPE == "postgres":
            cur.execute("""
                INSERT INTO alerts (user_id, crop, target_price, market, created_at)
                VALUES (?,?,?,?,?) RETURNING id
            """, (session["user_id"], d["crop"], float(d["target_price"]),
                  d.get("market"), datetime.utcnow().isoformat()))
            aid = cur.fetchone()["id"]
        else:
            cur.execute("""
                INSERT INTO alerts (user_id, crop, target_price, market, created_at)
                VALUES (?,?,?,?,?)
            """, (session["user_id"], d["crop"], float(d["target_price"]),
                  d.get("market"), datetime.utcnow().isoformat()))
            aid = cur.lastrowid
    return jsonify(ok=True, id=aid)


@app.post("/api/payment-intent")
def payment_intent():
    if not session.get("user_id"):
        return jsonify(error="Login required"), 401
    d = request.json or {}
    try:
        amount = float(d.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0
    if amount <= 0:
        return jsonify(error="Amount si sahihi"), 400
    ref = "NM-" + secrets.token_hex(6).upper()

    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute("""
            INSERT INTO payments (user_id, amount, method, status, reference, purpose, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (session["user_id"], amount, d.get("method", "MOBILE_MONEY"),
              "PENDING", ref, d.get("purpose", "subscription"),
              datetime.utcnow().isoformat()))

    return jsonify(
        ok=True,
        status="PENDING",
        reference=ref,
        message="Payment intent imetengenezwa; gateway halisi inahitaji credentials/webhook.",
    )


@app.get("/api/stats")
def stats():
    cached = cache_get("stats", ttl=30)
    if cached is not None:
        return jsonify(cached)

    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute("SELECT COUNT(*) AS c FROM users")
        users = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM listings WHERE status='ACTIVE'")
        listings = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM orders")
        orders = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM prices")
        prices = cur.fetchone()["c"]
        r = {"users": users, "listings": listings, "orders": orders, "prices": prices}

    cache_set("stats", r, ttl=30)
    return jsonify(r)


@app.get("/api/health")
def health():
    """Simple health check that also reports which DB is in use."""
    return jsonify(
        status="ok",
        version="5.3",
        database=DB_TYPE,
        database_url_scheme=_parsed.scheme or "sqlite",
    )


# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------
init_db()

if __name__ == "__main__":
    print(f"NjiaMauzo Afrika v5.3 | Database: {DB_TYPE.upper()}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
