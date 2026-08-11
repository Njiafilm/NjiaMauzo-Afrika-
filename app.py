import os, re, secrets, sqlite3, hashlib, hmac
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, jsonify, request, render_template, g, session

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "njiamauzo.db"))

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")

COUNTRY_RATES = {
    "Tanzania": ("TZS", 1.00),
    "Kenya": ("KES", 0.027),
    "Uganda": ("UGX", 2.80),
    "Rwanda": ("RWF", 0.58),
    "Burundi": ("BIF", 1.73),
}

# Ada ya msingi ya huduma - TZS 3,000
BASE_FEE_TZS = 3000

# Namba HALISI za malipo. Hazitolewi kwa mteja mpaka aombe kupitia
# /api/service/payment-number - hazionekani kamwe kwenye HTML/JS chanzo.
PAYMENT_NUMBERS = {
    "mpesa":   {"number": "0755 248 789", "label": "M-Pesa / Vodacom"},
    "halotel": {"number": "0625 031 460", "label": "Halotel"},
    "airtel":  {"number": "0691 925 100", "label": "Airtel Money"},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
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
verified_at TEXT
);
CREATE TABLE IF NOT EXISTS alerts(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
crop TEXT,
target_price REAL,
direction TEXT,
created_at TEXT NOT NULL
);
""")
    x.commit()

    # Demo market data, inserted once. (Hizi ni bei za soko za mfano - siyo
    # "demo payment mode"; zinahitajika ili mfumo uwe na data ya kuanzia.)
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
        x.executemany("""INSERT INTO prices
(crop, market, country, buy_price, sell_price, transport_per_kg, recorded_at)
VALUES (?,?,?,?,?,?,?)""", [(a, b, c, d, e, f, now()) for a, b, c, d, e, f in rows])

    if x.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 0:
        rows = [
            ("Ufuta", 20000, 3150, "Songea", "Tanzania", 1),
            ("Ufuta", 12000, 3300, "Mbeya", "Tanzania", 1),
            ("Mahindi", 50000, 900, "Mwanza", "Tanzania", 1),
            ("Maharage", 18000, 2350, "Mbeya", "Tanzania", 1),
            ("Karanga", 10000, 2700, "Dodoma", "Tanzania", 1),
            ("Ufuta", 25000, 3500, "Nairobi", "Kenya", 1),
        ]
        x.executemany("""INSERT INTO listings
(crop, quantity_kg, price, location, country, verified, created_at)
VALUES (?,?,?,?,?,?,?)""", [(a, b, c, d, e, f, now()) for a, b, c, d, e, f in rows])

    x.commit()
    x.close()


def hashpw(p):
    return hashlib.sha256(p.encode()).hexdigest()


def money(v):
    return round(float(v), 2)


def parse_query(q):
    ql = q.lower()
    crops = ["ufuta", "mahindi", "maize", "maharage", "beans", "mpunga", "rice", "korosho", "cashew", "karanga", "peanuts", "groundnuts"]
    crop = next((c for c in crops if c in ql), None)
    countries = ["tanzania", "kenya", "uganda", "rwanda", "burundi"]
    country = next((c.title() for c in countries if c in ql), None)
    nums = re.findall(r"\d[\d,]*", ql)
    quantity = None
    if nums:
        quantity = float(nums[0].replace(",", ""))
        if "tani" in ql or "ton" in ql:
            quantity = quantity * 1000
    price = None
    m = re.search(r"(?:chini ya|under|below|less than|max|maximum)\s*(?:tzs|kes|ugx|rwf|bif)?\s*([\d,]+)", ql)
    if m:
        price = float(m.group(1).replace(",", ""))
    return {
        "crop": crop.title() if crop else None,
        "country": country,
        "location": None,
        "quantity_kg": quantity,
        "max_price": price
    }


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
        countries=x.execute("SELECT COUNT(DISTINCT country) FROM prices").fetchone()[0]
    )


@app.get("/api/prices")
def prices():
    q = request.args.get("q", "").lower().strip()
    c = request.args.get("country", "").strip()
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
def intelligence():
    d = request.get_json() or {}
    crop = str(d.get("crop", "Ufuta"))
    qty = float(d.get("quantity_kg") or 0)
    buy = float(d.get("source_price") or 0)
    extra = float(d.get("extra_cost_per_kg") or 0)
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
            "margin_pct": margin
        })
    out.sort(key=lambda x: x["profit_total"], reverse=True)
    return jsonify(results=out, recommendation=out[0] if out else None)


@app.post("/api/ai/search")
def ai_search():
    d = request.get_json() or {}
    q = str(d.get("query", ""))
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
def ai_chat():
    m = str((request.get_json() or {}).get("message", "")).lower()
    if "bei" in m:
        reply = "Nenda Bei ili kulinganisha bei za masoko. Unaweza pia kutumia Profit AI."
    elif "ufuta" in m:
        reply = "Mfumo una listings za ufuta Tanzania na Kenya kwenye database."
    elif "malipo" in m:
        reply = "Huduma ya kutafutiwa bidhaa ni TZS 3,000 tu — karibu, mfumo utakutafutia kwa ada nafuu!"
    else:
        reply = "Nimepokea ombi lako. Jaribu kutaja zao, kiasi, eneo na bei unayotaka."
    return jsonify(reply=reply)


@app.get("/api/listings")
def listings():
    q = request.args.get("q", "").lower().strip()
    rows = db().execute("SELECT * FROM listings ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows if not q or q in f"{r['crop']} {r['location']} {r['country']}".lower()])


@app.get("/api/ads")
def free_ads():
    """Bidhaa za kuonyeshwa juu kama tangazo - bure kabisa, hazihusiani na malipo."""
    rows = db().execute("SELECT * FROM listings ORDER BY id DESC LIMIT 10").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/listings")
def create_listing():
    d = request.get_json() or {}
    try:
        crop = str(d["crop"]).strip()
        qty = float(d["quantity_kg"])
        price = float(d["price"])
        loc = str(d["location"]).strip()
        country = str(d.get("country", "Tanzania"))
    except Exception:
        return jsonify(error="Taarifa za bidhaa si sahihi."), 400
    if not crop or qty <= 0 or price <= 0 or not loc:
        return jsonify(error="Jaza taarifa zote."), 400
    db().execute("""INSERT INTO listings(crop, quantity_kg, price, location, country, verified, created_at)
VALUES(?,?,?,?,?,1,?)""", (crop, qty, price, loc, country, now()))
    db().commit()
    return jsonify(ok=True)


@app.post("/api/register")
def register():
    d = request.get_json() or {}
    name = str(d.get("name", "")).strip()
    email = str(d.get("email", "")).strip().lower()
    password = str(d.get("password", ""))
    phone = str(d.get("phone", ""))
    role = str(d.get("role", "buyer"))
    if not name or not email or len(password) < 4:
        return jsonify(error="Jaza jina, email na password ya angalau herufi 4."), 400
    try:
        cur = db().execute(
            "INSERT INTO users(name, email, password, phone, role, created_at) VALUES(?,?,?,?,?,?)",
            (name, email, hashpw(password), phone, role, now())
        )
        db().commit()
        session["user_id"] = cur.lastrowid
        return jsonify(ok=True)
    except sqlite3.IntegrityError:
        return jsonify(error="Email tayari imesajiliwa."), 409


@app.post("/api/login")
def login():
    d = request.get_json() or {}
    r = db().execute(
        "SELECT * FROM users WHERE email=? AND password=?",
        (str(d.get("email", "")).lower(), hashpw(str(d.get("password", ""))))
    ).fetchone()
    if not r:
        return jsonify(error="Email au password si sahihi."), 401
    session["user_id"] = r["id"]
    return jsonify(name=r["name"], role=r["role"])


@app.get("/api/me")
def me():
    uid = session.get("user_id")
    if not uid:
        return jsonify(logged_in=False)
    r = db().execute("SELECT name, email, role, phone FROM users WHERE id=?", (uid,)).fetchone()
    return jsonify(logged_in=bool(r), **(dict(r) if r else {}))


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.post("/api/alerts")
def alerts():
    d = request.get_json() or {}
    db().execute(
        "INSERT INTO alerts(user_id, crop, target_price, direction, created_at) VALUES(?,?,?,?,?)",
        (session.get("user_id"), d.get("crop"), float(d.get("target_price") or 0), d.get("direction", "ABOVE"), now())
    )
    db().commit()
    return jsonify(ok=True)


# ---------- Service: TZS 3,000 + country conversion (HAKUNA DEMO) ----------

@app.get("/api/service/fee")
def service_fee():
    country = request.args.get("country", "Tanzania")
    currency, rate = COUNTRY_RATES.get(country, COUNTRY_RATES["Tanzania"])
    return jsonify(
        base_amount_tzs=BASE_FEE_TZS,
        amount=round(BASE_FEE_TZS * rate, 2),
        currency=currency,
        country=country,
        note="Thamani ni ya majaribio/display; production inapaswa kutumia FX/payment provider halisi."
    )


@app.post("/api/service/start")
def service_start():
    d = request.get_json() or {}
    q = str(d.get("query", "")).strip()
    if len(q) < 5:
        return jsonify(error="Andika ombi la kutafuta."), 400
    country = str(d.get("country", "Tanzania"))
    currency, rate = COUNTRY_RATES.get(country, COUNTRY_RATES["Tanzania"])
    ref = secrets.token_urlsafe(12)
    cur = db().execute("""INSERT INTO service_requests
(request_id, query, country, fee_tzs, currency, amount, payment_status, created_at)
VALUES(?,?,?,?,?,?, 'PENDING',?)""",
        (ref, q, country, BASE_FEE_TZS, currency, round(BASE_FEE_TZS * rate, 2), now()))
    db().commit()
    return jsonify(request_id=cur.lastrowid, reference=ref, status="PENDING")


@app.get("/api/service/payment-number")
def service_payment_number():
    """
    Inatoa namba ya malipo TU baada ya mtumiaji kuchagua njia kwenye button.
    Namba HAZIPO kwenye HTML/JS chanzo - zinatolewa hapa moja kwa moja.
    """
    method = request.args.get("method")
    info = PAYMENT_NUMBERS.get(method)
    if not info:
        return jsonify(error="Njia ya malipo si sahihi"), 400

    rid = request.args.get("request_id")
    if rid:
        db().execute(
            "UPDATE service_requests SET method=? WHERE id=?",
            (method, int(rid))
        )
        db().commit()

    return jsonify(number=info["number"], label=info["label"])


@app.post("/api/service/pay")
def service_pay():
    d = request.get_json() or {}
    rid = int(d.get("request_id") or 0)
    phone = str(d.get("phone", "")).strip()
    reference = str(d.get("reference", "")).strip()
    r = db().execute("SELECT * FROM service_requests WHERE id=?", (rid,)).fetchone()
    if not r:
        return jsonify(error="Request haipo."), 404
    if not phone:
        return jsonify(error="Weka namba ya simu."), 400
    if reference:
        db().execute(
            "UPDATE service_requests SET reference=?, phone=? WHERE id=?",
            (reference, phone, rid)
        )
        db().commit()
    return jsonify(
        reference=r["request_id"],
        status="PENDING",
        amount=r["amount"],
        currency=r["currency"]
    )


@app.get("/api/service/status/<int:rid>")
def service_status(rid):
    r = db().execute("SELECT * FROM service_requests WHERE id=?", (rid,)).fetchone()
    if not r:
        return jsonify(error="Request haipo."), 404
    return jsonify(
        request_id=rid,
        status=r["payment_status"],
        reference=r["request_id"],
        amount=r["amount"],
        currency=r["currency"]
    )


@app.post("/api/service/admin-verify")
def admin_verify():
    """
    Njia PEKEE ya kuthibitisha malipo - kwa mkono, na admin/AI controller.
    TODO: ongeza ulinzi wa admin-auth (session ya admin au token) kabla
    ya kwenda live - kwa sasa mtu yeyote anayejua request_id anaweza kuita hii.
    """
    d = request.get_json() or {}
    rid = int(d.get("request_id") or 0)
    r = db().execute("SELECT * FROM service_requests WHERE id=?", (rid,)).fetchone()
    if not r:
        return jsonify(error="Request haipo."), 404
    db().execute(
        "UPDATE service_requests SET payment_status='VERIFIED', verified_at=? WHERE id=?",
        (now(), rid)
    )
    db().commit()
    return jsonify(status="VERIFIED", request_id=rid, reference=r["request_id"])


@app.post("/api/service/webhook")
def service_webhook():
    secret = os.environ.get("PAYMENT_WEBHOOK_SECRET", "")
    supplied = request.headers.get("X-NjiaMauzo-Webhook-Secret", "")
    if not secret or not hmac.compare_digest(secret, supplied):
        return jsonify(error="Invalid webhook"), 401
    d = request.get_json() or {}
    rid = int(d.get("request_id") or 0)
    if str(d.get("status", "")).upper() != "VERIFIED":
        return jsonify(status="IGNORED")
    r = db().execute("SELECT id FROM service_requests WHERE id=?", (rid,)).fetchone()
    if not r:
        return jsonify(error="Request haipo."), 404
    db().execute(
        "UPDATE service_requests SET payment_status='VERIFIED', reference=?, verified_at=? WHERE id=?",
        (str(d.get("reference", "")), now(), rid)
    )
    db().commit()
    return jsonify(status="VERIFIED", request_id=rid)


@app.post("/api/service/room")
def service_room():
    d = request.get_json() or {}
    rid = int(d.get("request_id") or 0)
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
            "transport_per_kg": p["transport_per_kg"]
        })
    return jsonify(
        status="VERIFIED",
        message="Malipo yamethibitishwa. User Room imefunguliwa na automatic search imekamilika.",
        interpreted=interpreted,
        products=products,
        markets=markets[:20]
    )


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
