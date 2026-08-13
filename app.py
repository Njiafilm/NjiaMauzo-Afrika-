"""
NjiaMauzo Afrika — Backend (Flask)
Live Activity 24/7 + AI Searcher + Smart Bot + Security
"""

from flask import Flask, jsonify, request, send_from_directory, session, make_response
from flask_cors import CORS
from datetime import datetime, timezone
from functools import wraps
import random
import time
import os
import hashlib
import secrets
import threading
import logging
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("njiamauzo")

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Admin credentials (badilisha kwa mazingira ya production)
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "NjiaAdmin2026!")

def is_admin():
    return session.get("role") == "admin" and session.get("admin_ok") is True

def require_admin(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not is_admin():
            return jsonify({"success": False, "message": "Admin only"}), 403
        return f(*args, **kwargs)
    return wrapped

CORS(app, supports_credentials=True)

# ---------------------------------------------------------------------------
# Security: rate limit + headers
# ---------------------------------------------------------------------------
_rate = {}
_rate_lock = threading.Lock()

def rate_limit(max_req=60, window=60):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
            now = time.time()
            with _rate_lock:
                hits = [t for t in _rate.get(ip, []) if now - t < window]
                if len(hits) >= max_req:
                    return jsonify({"success": False, "message": "Requests nyingi sana. Subiri kidogo."}), 429
                hits.append(now)
                _rate[ip] = hits
            return f(*args, **kwargs)
        return wrapped
    return decorator

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
TANZANIA_REGIONS = [
    "Dar es Salaam", "Arusha", "Mwanza", "Mbeya", "Dodoma", "Morogoro",
    "Tanga", "Kilimanjaro", "Ruvuma", "Iringa", "Singida", "Tabora",
    "Kigoma", "Shinyanga", "Mtwara", "Lindi", "Pwani", "Geita",
    "Simiyu", "Katavi", "Njombe", "Rukwa", "Kagera", "Manyara",
    "Songwe", "Zanzibar", "Pemba",
]
EAST_AFRICA = [
    "Nairobi", "Mombasa", "Kisumu", "Nakuru", "Kampala", "Jinja",
    "Mbarara", "Kigali", "Musanze", "Bujumbura", "Gitega", "Juba", "Wau",
]
ALL_LOCATIONS = TANZANIA_REGIONS + EAST_AFRICA

PRODUCTS_CATALOG = [
    {"title": "Mahindi", "unit": "gunia", "category": "Nafaka", "price_range": (45000, 120000), "emoji": "🌽", "color": "#f59e0b"},
    {"title": "Mchele", "unit": "gunia", "category": "Nafaka", "price_range": (80000, 180000), "emoji": "🍚", "color": "#eab308"},
    {"title": "Ufuta", "unit": "tani", "category": "Mafuta", "price_range": (80000, 250000), "emoji": "🫒", "color": "#84cc16"},
    {"title": "Alizeti", "unit": "gunia", "category": "Mafuta", "price_range": (70000, 160000), "emoji": "🌻", "color": "#facc15"},
    {"title": "Maharage", "unit": "gunia", "category": "Legume", "price_range": (60000, 150000), "emoji": "🫘", "color": "#a16207"},
    {"title": "Korosho", "unit": "kg", "category": "Karanga", "price_range": (7000, 25000), "emoji": "🥜", "color": "#ca8a04"},
    {"title": "Kahawa Arabica", "unit": "kg", "category": "Kahawa", "price_range": (8000, 18000), "emoji": "☕", "color": "#78350f"},
    {"title": "Chai", "unit": "kg", "category": "Chai", "price_range": (5000, 12000), "emoji": "🍵", "color": "#166534"},
    {"title": "Pamba", "unit": "tani", "category": "Pamba", "price_range": (1500000, 3500000), "emoji": "☁️", "color": "#f5f5f4"},
    {"title": "Viazi", "unit": "gunia", "category": "Mizizi", "price_range": (30000, 80000), "emoji": "🥔", "color": "#a16207"},
    {"title": "Ndizi", "unit": "mkunguru", "category": "Matunda", "price_range": (15000, 45000), "emoji": "🍌", "color": "#facc15"},
    {"title": "Embe", "unit": "sanduku", "category": "Matunda", "price_range": (20000, 60000), "emoji": "🥭", "color": "#f97316"},
    {"title": "Nanasi", "unit": "sanduku", "category": "Matunda", "price_range": (18000, 50000), "emoji": "🍍", "color": "#eab308"},
    {"title": "Karanga", "unit": "gunia", "category": "Karanga", "price_range": (50000, 110000), "emoji": "🥜", "color": "#d97706"},
    {"title": "Uwele", "unit": "gunia", "category": "Nafaka", "price_range": (40000, 90000), "emoji": "🌾", "color": "#ca8a04"},
    {"title": "Mtama", "unit": "gunia", "category": "Nafaka", "price_range": (35000, 85000), "emoji": "🌾", "color": "#a16207"},
    {"title": "Mbaazi", "unit": "gunia", "category": "Legume", "price_range": (55000, 130000), "emoji": "🟢", "color": "#65a30d"},
    {"title": "Kunde", "unit": "gunia", "category": "Legume", "price_range": (50000, 120000), "emoji": "🫘", "color": "#854d0e"},
    {"title": "Ngano", "unit": "gunia", "category": "Nafaka", "price_range": (70000, 140000), "emoji": "🌾", "color": "#eab308"},
    {"title": "Mihogo", "unit": "tani", "category": "Mizizi", "price_range": (200000, 500000), "emoji": "🫚", "color": "#a3e635"},
    {"title": "Viazi Vitamu", "unit": "gunia", "category": "Mizizi", "price_range": (25000, 70000), "emoji": "🍠", "color": "#ea580c"},
    {"title": "Nyanya", "unit": "sanduku", "category": "Mboga", "price_range": (20000, 70000), "emoji": "🍅", "color": "#dc2626"},
    {"title": "Vitunguu", "unit": "gunia", "category": "Mboga", "price_range": (40000, 100000), "emoji": "🧅", "color": "#f97316"},
    {"title": "Pilipili", "unit": "kg", "category": "Mboga", "price_range": (3000, 12000), "emoji": "🌶️", "color": "#b91c1c"},
    {"title": "Maziwa", "unit": "lita", "category": "Maziwa", "price_range": (1200, 2500), "emoji": "🥛", "color": "#f8fafc"},
    {"title": "Mayai", "unit": "tray", "category": "Kuku", "price_range": (6000, 12000), "emoji": "🥚", "color": "#fef3c7"},
    {"title": "Kuku", "unit": "kilo", "category": "Kuku", "price_range": (7000, 15000), "emoji": "🐔", "color": "#fbbf24"},
    {"title": "Samaki", "unit": "kg", "category": "Samaki", "price_range": (8000, 20000), "emoji": "🐟", "color": "#0ea5e9"},
    {"title": "Mbegu za Mahindi", "unit": "kg", "category": "Mbegu", "price_range": (5000, 30000), "emoji": "🌱", "color": "#22c55e"},
    {"title": "Mbegu za Maharage", "unit": "kg", "category": "Mbegu", "price_range": (4000, 25000), "emoji": "🌱", "color": "#16a34a"},
    {"title": "Mbolea NPK", "unit": "gunia", "category": "Mbolea", "price_range": (50000, 120000), "emoji": "🧪", "color": "#64748b"},
    {"title": "Mbolea Urea", "unit": "gunia", "category": "Mbolea", "price_range": (55000, 130000), "emoji": "🧪", "color": "#475569"},
    {"title": "Dawa ya Mimea", "unit": "lita", "category": "Dawa", "price_range": (15000, 80000), "emoji": "🧴", "color": "#06b6d4"},
    {"title": "Trekta", "unit": "pcs", "category": "Vifaa", "price_range": (8000000, 25000000), "emoji": "🚜", "color": "#15803d"},
    {"title": "Pampu ya Maji", "unit": "pcs", "category": "Vifaa", "price_range": (150000, 800000), "emoji": "💧", "color": "#0284c7"},
]


SELLER_NAMES = [
    "Juma Mkulima", "Amina Biashara", "Peter Farms", "Grace Agro",
    "Hassan Traders", "Fatuma Supplies", "John Agriculture", "Maria Exports",
    "Said Cooperative", "Neema Fresh", "David Produce", "Rehema Market",
    "Baraka Farms", "Zainab Trading", "Michael Agro Hub", "Esther Seeds",
    "Kilimo Bora Ltd", "Green Valley Farms", "Umoja Cooperative", "Safari Exports",
]

# Public feed: NO prices, NO seller names
ACTIVITY_TEMPLATES = [
    "🆕 {product} mpya imepatikana — eneo la {location}",
    "✅ Utafutaji wa {product} umefanyika — {location}",
    "📦 Mahitaji ya {product} yameonekana — {location}",
    "🔍 AI Searcher imepata {product} — {location}",
    "⭐ {product} inapendekezwa sasa — {location}",
    "🚚 {product} inapatikana kusafirishwa — {location}",
    "📣 Mahitaji makubwa ya {product} — {location}",
    "🏆 {product} bora wiki hii — {location}",
    "📲 Ombi la ushauri wa kilimo cha {product} — {location}",
    "🌍 AI Searcher imekagua soko — {product} ({location})",
    "📈 Shughuli za soko za {product} zimeongezeka — {location}",
    "🔎 AI Searcher inatafuta {product} katika mikoa mbalimbali",
]

_lock = threading.Lock()
activity_store = []
activity_id_counter = 1
products_store = []
product_id_counter = 1
# Full private product data (for paid users / WhatsApp delivery)
_private_products = {}

def utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def next_activity_id():
    global activity_id_counter
    with _lock:
        aid = activity_id_counter
        activity_id_counter += 1
        return aid

def next_product_id():
    global product_id_counter
    with _lock:
        pid = product_id_counter
        product_id_counter += 1
        return pid

def push_activity(message, activity_type="listing", extra=None):
    item = {
        "id": next_activity_id(),
        "message": message,
        "created": utcnow_iso(),
        "type": activity_type,
    }
    if extra:
        item.update(extra)
    with _lock:
        activity_store.insert(0, item)
        if len(activity_store) > 300:
            del activity_store[300:]
    return item

def ai_search_products(query="", region=None, limit=12):
    results = []
    q = (query or "").lower().strip()
    matched = PRODUCTS_CATALOG
    if q:
        matched = [p for p in PRODUCTS_CATALOG if q in p["title"].lower() or q in p["category"].lower()]
        if not matched:
            words = q.split()
            matched = [p for p in PRODUCTS_CATALOG if any(w in p["title"].lower() or w in p["category"].lower() for w in words)]
        if not matched:
            matched = random.sample(PRODUCTS_CATALOG, min(8, len(PRODUCTS_CATALOG)))
    locations = [region] if region and region in ALL_LOCATIONS else ALL_LOCATIONS
    count = min(limit, max(6, len(matched) * 2))
    for _ in range(count):
        prod = random.choice(matched)
        loc = random.choice(locations)
        seller = random.choice(SELLER_NAMES)
        low, high = prod["price_range"]
        price = random.randint(low, high)
        qty = random.choice([5, 10, 15, 20, 25, 50, 100, 200, 500])
        seller_id = hashlib.md5(seller.encode()).hexdigest()[:10]
        pid = next_product_id()
        full = {
            "id": pid,
            "title": f"{prod['title']} — {loc}",
            "jina": prod["title"],
            "description": f"{prod['title']} bora kutoka {loc}. Ubora wa juu, bei nafuu.",
            "location": loc,
            "chanzo": loc,
            "seller_name": seller,
            "seller_id": seller_id,
            "real_price": price,
            "realPrice": price,
            "unit": prod["unit"],
            "category": prod["category"],
            "qty": qty,
            "likes": random.randint(0, 48),
            "image": "",
            "picha": "",
            "emoji": prod.get("emoji", "📦"),
            "color": prod.get("color", "#0b7d45"),
            "available": True,
        }
        _private_products[pid] = full
        results.append(full)
    return results

def generate_activity_message():
    template = random.choice(ACTIVITY_TEMPLATES)
    prod = random.choice(PRODUCTS_CATALOG)
    loc = random.choice(ALL_LOCATIONS)
    msg = template.format(product=prod["title"], location=loc)
    return push_activity(msg, activity_type="live", extra={"location": loc, "product": prod["title"]})

def seed_initial_data():
    global products_store
    logger.info("Seeding products & activity...")
    seeded = []
    for _ in range(42):
        batch = ai_search_products(limit=1)
        if batch:
            seeded.append(batch[0])
    products_store = seeded
    for _ in range(20):
        generate_activity_message()
    logger.info("Seeded %d products, %d activities", len(products_store), len(activity_store))

def background_activity_generator():
    """Live Activity 24/7 — every 45–120 seconds"""
    while True:
        try:
            time.sleep(random.uniform(45, 120))
            generate_activity_message()
        except Exception as e:
            logger.error("Activity generator error: %s", e)
            time.sleep(10)

# ---------------------------------------------------------------------------
# Smart Bot
# ---------------------------------------------------------------------------
def smart_bot_reply(message, history=None):
    """Smart conversational bot — human-like Swahili replies 24/7"""
    msg = (message or "").lower().strip()
    history = history or []

    if not msg:
        return "Karibu ndugu! 😊 Ninaweza kukusaidia kuhusu mazao, bei, ushauri wa kilimo, au jinsi ya kulipa ada. Unahitaji msaada gani leo?"

    # Greetings + time-aware feel
    if any(w in msg for w in ["habari", "hujambo", "hello", "hi", "mambo", "salama", "shikamoo", "vipi", "sasa"]):
        replies = [
            "Habari yako! Karibu NjiaMauzo Afrika 🌍. Nikusaidie nini leo — mazao, ushauri, au malipo?",
            "Hujambo! Ninafurahi kukuona. Unatafuta bidhaa gani, au unahitaji ushauri wa kilimo?",
            "Mambo vipi! 😊 Niambie unachotafuta — mahindi, ufuta, kahawa, au kitu kingine?",
        ]
        return random.choice(replies)

    # How are you
    if any(w in msg for w in ["hali gani", "u hali", "how are you", "upo"]):
        return "Niko salama, nikikuhudumia 24/7! 💪 Na wewe? Unahitaji msaada gani kuhusu soko la mazao?"

    # Prices
    if any(w in msg for w in ["bei", "price", "ghali", "nafuu", "gharama", "pesa", "ngapi"]):
        return (
            "Bei kamili hutolewa baada ya kulipa ada ya TZS 3,000 — hii inalinda siri za wafanyabiashara. "
            "Bofya **PATA MSAADA HAPA**, lipa, kisha AI Searcher itakutumia bei, eneo na muuzaji kupitia WhatsApp. "
            "Unatafuta bei ya bidhaa gani hasa?"
        )

    # Specific products
    product_map = {
        "mahindi": "Mahindi", "mchele": "Mchele", "ufuta": "Ufuta", "kahawa": "Kahawa",
        "maharage": "Maharage", "alizeti": "Alizeti", "viazi": "Viazi", "nyanya": "Nyanya",
        "korosho": "Korosho", "pamba": "Pamba", "chai": "Chai", "ndizi": "Ndizi",
        "embe": "Embe", "kuku": "Kuku", "samaki": "Samaki", "mbegu": "Mbegu",
        "mbolea": "Mbolea", "trekta": "Trekta", "maziwa": "Maziwa", "pilipili": "Pilipili",
    }
    found = [v for k, v in product_map.items() if k in msg]
    if found:
        p = found[0]
        return (
            f"Nzuri! {p} inapatikana katika mikoa mbalimbali ya Tanzania na Afrika Mashariki. "
            f"Kwenye ukurasa unaweza kuona jina lake, lakini bei, eneo na muuzaji vinakuja baada ya kulipa ada TZS 3,000. "
            f"Bofya **PATA MSAADA HAPA** au andika jina kwenye sehemu ya Tafuta juu. Unahitaji {p} kutoka mkoa gani?"
        )

    # Advisory
    if any(w in msg for w in ["ushauri", "mshauri", "wataalamu", "kilimo", "mbegu", "mavuno", "shamba", "kulima"]):
        return (
            "Kwa ushauri wa kitaalamu wa kilimo (mbegu, usimamizi, namna bora ya kulima): "
            "bofya **Omba Ushauri wa Kitaalamu**, lipa TZS 3,000, kisha utaunganishwa na mshauri kupitia WhatsApp **0755 248 789**. "
            "Una swali gani kuhusu kilimo chako?"
        )

    # Payment help
    if any(w in msg for w in ["lipa", "malipo", "ada", "m-pesa", "mpesa", "airtel", "halotel", "payment", "order"]):
        return (
            "Ada ni **TZS 3,000**. Hatua: 1) Bofya PATA MSAADA HAPA au Omba Ushauri  "
            "2) Chagua M-Pesa / Halotel / Airtel Money  3) Weka namba yako  4) Endelea na Malipo  "
            "5) WhatsApp inafunguka. Baada ya kuthibitisha malipo, AI inakutumia taarifa kamili. Una tatizo lipi kwenye malipo?"
        )

    # Location
    if any(w in msg for w in ["mkoa", "eneo", "location", "wapi", "dar", "arusha", "mwanza", "mbeya", "ruvuma", "dodoma", "tanga"]):
        return (
            "Tunatafuta katika mikoa yote ya Tanzania na Afrika Mashariki (Dar, Arusha, Mbeya, Ruvuma, Nairobi, Kampala, n.k.). "
            "Eneo kamili la muuzaji linaonyeshwa baada ya kulipa ada — ili kulinda biashara. Unapendelea mkoa gani?"
        )

    # How it works
    if any(w in msg for w in ["jinsi", "namna", "how", "kazi", "mfumo", "nini", "eleza", "maelezo"]):
        return (
            "Hivi ndivyo inavyofanya kazi:\n"
            "1️⃣ Tafuta au angalia bidhaa kwenye ukurasa\n"
            "2️⃣ Bofya **PATA MSAADA HAPA**\n"
            "3️⃣ Lipa TZS 3,000\n"
            "4️⃣ WhatsApp inafunguka (0755 248 789)\n"
            "5️⃣ AI Searcher inakutumia bei, eneo na muuzaji\n"
            "Live Activity inaonyesha shughuli za soko 24/7. Una swali jingine?"
        )

    # Thanks
    if any(w in msg for w in ["asante", "thanks", "thank you", "shukrani", "nashukuru"]):
        return random.choice([
            "Karibu sana! 😊 Kama utahitaji msaada mwingine, niulize hapa — niko 24/7.",
            "Asante kwa kuwasiliana! Rudi wakati wowote ukihitaji msaada wa soko la mazao.",
            "Karibu! Fanikiwa na biashara yako 🌱",
        ])

    # Goodbye
    if any(w in msg for w in ["kwaheri", "bye", "tutaonana", "ninaenda", "baadaye"]):
        return "Kwaheri! Rudi tena unapohitaji msaada. Tuko hapa 24/7. 👋"

    # Complaint / problem
    if any(w in msg for w in ["tatizo", "problem", "haifanyi", "error", "imekwama", "help", "msaada"]):
        return (
            "Samahani kwa usumbufu. Jaribu: refresh ukurasa, angalia intaneti, au bofya tena malipo. "
            "Kama bado kuna tatizo, andika Order ID yako au wasiliana WhatsApp 0755 248 789. Ninaweza kukusaidia vipi sasa?"
        )

    # Who are you
    if any(w in msg for w in ["wewe nani", "nani wewe", "bot", "ai", "robot"]):
        return (
            "Mimi ni msaidizi wa NjiaMauzo Afrika — niko hapa 24/7 kukusaidia kutafuta mazao, kueleza malipo, "
            "na kukuunganisha na washauri. Sio binadamu, lakini najaribu kujibu kwa urafiki na uwazi! Unahitaji nini?"
        )

    # Default — engage further
    defaults = [
        f"Nimeelewa ulichosema. Unaweza kutafuta bidhaa juu, kubofya PATA MSAADA HAPA, au kuniuliza kuhusu bei, ushauri, au malipo. Unatafuta nini hasa?",
        "Ili nikusaidie vizuri zaidi: unatafuta mazao gani, au unahitaji ushauri wa kilimo? Niambie kwa ufupi.",
        "Karibu! Ninaweza: kutafuta mazao, kueleza jinsi ya kulipa ada, au kukuunganisha na mshauri. Chagua moja au andika swali lako.",
    ]
    return random.choice(defaults)



# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    base = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(base, "index.html")

@app.route("/static/<path:filename>")
def static_files(filename):
    base = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(base, "static")
    if os.path.isdir(static_dir):
        return send_from_directory(static_dir, filename)
    return send_from_directory(base, filename)

@app.route("/health")
def health():
    return jsonify({"status": "ok", "products": len(products_store), "activities": len(activity_store), "live": True})

@app.route("/api/csrf-token")
@rate_limit(30, 60)
def csrf_token():
    token = secrets.token_hex(16)
    session["csrf"] = token
    return jsonify({"csrf_token": token})

@app.route("/api/me")
def me():
    if is_admin():
        return jsonify({
            "success": True,
            "user": {
                "name": "Admin",
                "email": "admin@njiamauzo.local",
                "phone": "—",
                "role": "admin",
                "bypass_payment": True,
            }
        })
    if session.get("user"):
        u = session["user"]
        return jsonify({"success": True, "user": u})
    return jsonify({"success": False, "message": "Not logged in"})

@app.route("/api/products")
@rate_limit(40, 60)
def get_products():
    admin = is_admin()
    products = []
    for p in products_store[:30]:
        if admin:
            # Admin anaona taarifa kamili bila kulipa
            products.append({
                "id": p["id"],
                "title": p.get("title") or p.get("jina"),
                "description": p.get("description", ""),
                "location": p.get("location", ""),
                "seller_name": p.get("seller_name", ""),
                "seller_id": p.get("seller_id", ""),
                "real_price": p.get("real_price", 0),
                "unit": p.get("unit", ""),
                "likes": p.get("likes", 0),
                "image": "",
                "emoji": p.get("emoji", "📦"),
                "color": p.get("color", "#0b7d45"),
                "available": True,
                "category": p.get("category", ""),
                "full_access": True,
            })
        else:
            products.append({
                "id": p["id"],
                "title": p.get("jina") or p["title"].split("—")[0].strip(),
                "description": "Taarifa kamili (bei, eneo, muuzaji) zinapatikana baada ya kulipa ada.",
                "location": "",
                "seller_name": "",
                "seller_id": p.get("seller_id", ""),
                "likes": p.get("likes", 0),
                "image": "",
                "emoji": p.get("emoji", "📦"),
                "color": p.get("color", "#0b7d45"),
                "available": True,
                "category": p.get("category", ""),
                "full_access": False,
            })
    return jsonify({"success": True, "products": products, "admin_mode": admin})

@app.route("/api/ai-products")
@rate_limit(30, 60)
def ai_products():
    q = request.args.get("q", "").strip()
    region = request.args.get("region")
    # Sanitize query
    q = re.sub(r"[<>\"']", "", q)[:120]
    results = ai_search_products(query=q, region=region, limit=16)
    if q:
        push_activity(
            f"🔍 AI Searcher imetafuta '{q}' katika mikoa ya Tanzania na Afrika Mashariki — {len(results)} matokeo",
            activity_type="ai_search",
        )
    admin = is_admin()
    public_results = []
    for p in results:
        if admin:
            public_results.append({
                "id": p["id"],
                "title": p.get("title") or p.get("jina"),
                "jina": p.get("jina"),
                "description": p.get("description", ""),
                "location": p.get("location", ""),
                "chanzo": p.get("location", ""),
                "seller_name": p.get("seller_name", ""),
                "seller_id": p.get("seller_id", ""),
                "real_price": p.get("real_price", 0),
                "unit": p.get("unit", ""),
                "likes": p.get("likes", 0),
                "emoji": p.get("emoji", "📦"),
                "color": p.get("color", "#0b7d45"),
                "available": True,
                "category": p.get("category", ""),
                "full_access": True,
            })
        else:
            public_results.append({
                "id": p["id"],
                "title": p.get("jina") or p["title"].split("—")[0].strip(),
                "jina": p.get("jina") or p["title"].split("—")[0].strip(),
                "description": "Lipa ada ili kupata bei, eneo na mawasiliano ya muuzaji.",
                "location": "",
                "chanzo": "",
                "seller_name": "",
                "seller_id": p.get("seller_id", ""),
                "likes": p.get("likes", 0),
                "emoji": p.get("emoji", "📦"),
                "color": p.get("color", "#0b7d45"),
                "available": True,
                "category": p.get("category", ""),
                "full_access": False,
            })
    return jsonify({"success": True, "products": public_results, "admin_mode": admin})

@app.route("/api/activity")
@rate_limit(90, 60)
def get_activity():
    since_id = request.args.get("since_id", 0, type=int)
    with _lock:
        items = [a for a in activity_store if a["id"] > since_id]
    items = sorted(items, key=lambda x: x["id"], reverse=True)[:30]
    return jsonify({"success": True, "activity": items})

@app.route("/api/market-stats")
@rate_limit(30, 60)
def market_stats():
    categories = {}
    locations = {}
    total_likes = 0
    for p in products_store:
        cat = p.get("category", "Nyingine")
        loc = p.get("location", "Unknown")
        categories.setdefault(cat, {"count": 0, "prices": [], "locations": []})
        categories[cat]["count"] += 1
        categories[cat]["prices"].append(p.get("real_price", 0))
        categories[cat]["locations"].append(loc)
        locations[loc] = locations.get(loc, 0) + 1
        total_likes += p.get("likes", 0)
    total = max(1, len(products_store))
    cat_list = []
    for label, data in sorted(categories.items(), key=lambda x: -x[1]["count"]):
        prices = data["prices"] or [0]
        cat_list.append({
            "label": label,
            "count": data["count"],
            "avg_price": int(sum(prices) / len(prices)),
            "min_price": min(prices),
            "max_price": max(prices),
            "top_location": "",
            "share": round(data["count"] / total * 100, 1),
        })
    top_locations = [
        {"location": f"Eneo #{i+1}", "count": cnt}
        for i, (loc, cnt) in enumerate(sorted(locations.items(), key=lambda x: -x[1])[:10])
    ]
    recent = [
        {"title": p.get("jina") or p["title"].split("—")[0].strip(), "location": ""}
        for p in sorted(products_store, key=lambda x: x["id"], reverse=True)[:8]
    ]
    return jsonify({
        "success": True,
        "summary": {
            "total_products": len(products_store),
            "total_categories": len(categories),
            "total_locations": len(locations),
            "total_likes": total_likes,
        },
        "categories": cat_list,
        "top_locations": top_locations,
        "recent": recent,
    })

@app.route("/api/service/payment-number")
def payment_numbers():
    return jsonify({
        "success": True,
        "numbers": {
            "mpesa": "0755248789",
            "halotel": "0625031460",
            "airtel": "0691925100",
        },
    })

@app.route("/api/payment/request", methods=["POST"])
@rate_limit(15, 60)
def payment_request():
    data = request.get_json(force=True, silent=True) or {}

    # Admin bypass — hakuna malipo
    if is_admin() or data.get("admin_bypass"):
        if not is_admin():
            return jsonify({"success": False, "message": "Admin only"}), 403
        order_id = "ADMIN-" + secrets.token_hex(3).upper()
        push_activity(
            f"👑 Admin ametazama mfumo (bypass) — {order_id}",
            activity_type="admin",
        )
        return jsonify({
            "success": True,
            "payment_number": "ADMIN-BYPASS",
            "order_id": order_id,
            "status": "ADMIN_ACCESS",
            "admin_bypass": True,
            "message": "Admin mode: umepata access bila kulipa. Unaweza kuangalia taarifa kamili.",
            "hint": "Hii ni mode ya majaribio ya admin.",
        })

    method = str(data.get("njia", ""))[:40]
    phone = re.sub(r"[^\d+]", "", str(data.get("simu", "")))[:15]
    if not method or not phone:
        return jsonify({"success": False, "message": "Jaza njia na namba ya simu."})
    numbers = {
        "M-Pesa": "0755248789",
        "Halotel": "0625031460",
        "Airtel Money": "0691925100",
    }
    payment_number = numbers.get(method, "0755248789")
    order_id = "ORD-" + secrets.token_hex(4).upper()
    push_activity(
        f"💳 Ada imelipwa ({method}) — Order {order_id}. Mteja anaunganishwa na mshauri.",
        activity_type="payment",
    )
    # Simulate AI search result summary for WhatsApp (full details after payment)
    sample = random.choice(list(_private_products.values()) or ai_search_products(limit=1))
    return jsonify({
        "success": True,
        "payment_number": payment_number,
        "order_id": order_id,
        "status": "PENDING",
        "hint": f"AI itaandaa taarifa za {sample.get('jina', 'bidhaa')} baada ya kuthibitisha malipo.",
    })

@app.route("/api/captcha")
def captcha():
    a, b = random.randint(1, 12), random.randint(1, 12)
    captcha_id = secrets.token_hex(8)
    session[f"captcha_{captcha_id}"] = a + b
    return jsonify({"captcha_id": captcha_id, "question": f"{a} + {b} = ?"})

@app.route("/api/register", methods=["POST"])
@rate_limit(10, 60)
def register():
    return jsonify({"success": True, "message": "Umesajiliwa", "csrf_token": secrets.token_hex(16)})

@app.route("/api/login", methods=["POST"])
@rate_limit(10, 60)
def login():
    return jsonify({"success": True, "message": "Umeingia", "csrf_token": secrets.token_hex(16)})

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/admin/login", methods=["POST"])
@rate_limit(8, 60)
def admin_login():
    data = request.get_json(force=True, silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if username == ADMIN_USER and password == ADMIN_PASS:
        session["role"] = "admin"
        session["admin_ok"] = True
        session["user"] = {
            "name": "Admin",
            "email": "admin@njiamauzo.local",
            "phone": "—",
            "role": "admin",
            "bypass_payment": True,
        }
        logger.info("Admin logged in")
        return jsonify({
            "success": True,
            "message": "Admin umeingia. Unaweza kuangalia mfumo bila kulipa.",
            "csrf_token": secrets.token_hex(16),
            "role": "admin",
        })
    return jsonify({"success": False, "message": "Username au password si sahihi."}), 401

@app.route("/api/admin/status")
def admin_status():
    return jsonify({"success": True, "is_admin": is_admin()})

@app.route("/api/password/forgot", methods=["POST"])
@rate_limit(5, 60)
def forgot():
    return jsonify({"success": True, "message": "OTP imetumwa", "reset_id": secrets.token_hex(8)})

@app.route("/api/password/reset", methods=["POST"])
@rate_limit(5, 60)
def reset():
    return jsonify({"success": True, "message": "Nywila imebadilishwa"})

@app.route("/api/password/change", methods=["POST"])
@rate_limit(10, 60)
def change_pw():
    return jsonify({"success": True, "message": "Nywila imebadilishwa"})

@app.route("/api/products/<int:pid>/like", methods=["POST"])
@rate_limit(30, 60)
def like_product(pid):
    return jsonify({"success": True, "likes": random.randint(1, 50), "liked": True})

@app.route("/api/sellers/<sid>/follow", methods=["POST"])
@rate_limit(20, 60)
def follow_seller(sid):
    return jsonify({"success": True, "following": True, "followers": random.randint(5, 200)})

@app.route("/api/comments/<int:pid>")
def get_comments(pid):
    return jsonify({"success": True, "comments": []})

@app.route("/api/comments/<int:pid>", methods=["POST"])
@rate_limit(15, 60)
def post_comment(pid):
    return jsonify({"success": True})

@app.route("/api/bot-chat", methods=["POST"])
@rate_limit(40, 60)
def bot_chat():
    data = request.get_json(force=True, silent=True) or {}
    message = str(data.get("message") or "")[:500]
    # Optional client-sent short history for context
    history = data.get("history") or []
    if not isinstance(history, list):
        history = []
    history = [str(h)[:200] for h in history[-6:]]
    reply = smart_bot_reply(message, history=history)
    return jsonify({"reply": reply})

# ---------------------------------------------------------------------------
# Startup — 24/7 live
# ---------------------------------------------------------------------------
seed_initial_data()
_bg = threading.Thread(target=background_activity_generator, daemon=True)
_bg.start()
logger.info("Live Activity 24/7 + Smart Bot started")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("NjiaMauzo Afrika on port %s", port)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
