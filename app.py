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

# Admin security — Weka ADMIN_USER na ADMIN_PASS kwenye Render Environment!
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
_ADMIN_PASS_ENV_SET = "ADMIN_PASS" in os.environ
ADMIN_PASS = os.environ.get("ADMIN_PASS", "0000")
# Ikiwa hakuna ADMIN_PASS kwenye env, tunatumia default "0000" na kulazimisha
# admin abadilishe password mara ya kwanza anapoingia.
_admin_pass_lock = threading.Lock()
_admin_must_change_password = not _ADMIN_PASS_ENV_SET
ADMIN_SESSION_HOURS = float(os.environ.get("ADMIN_SESSION_HOURS", "4"))
ADMIN_MAX_FAILS = int(os.environ.get("ADMIN_MAX_FAILS", "5"))
ADMIN_LOCK_MINUTES = int(os.environ.get("ADMIN_LOCK_MINUTES", "15"))

# Failed login tracking (IP-based lockout)
_admin_fails = {}  # ip -> {"count": int, "locked_until": float}
_admin_fail_lock = threading.Lock()

def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()

def _admin_is_locked(ip):
    with _admin_fail_lock:
        rec = _admin_fails.get(ip)
        if not rec:
            return False
        if rec.get("locked_until", 0) > time.time():
            return True
        if rec.get("locked_until", 0) and rec["locked_until"] <= time.time():
            _admin_fails.pop(ip, None)
        return False

def _admin_register_fail(ip):
    with _admin_fail_lock:
        rec = _admin_fails.get(ip, {"count": 0, "locked_until": 0})
        rec["count"] = rec.get("count", 0) + 1
        if rec["count"] >= ADMIN_MAX_FAILS:
            rec["locked_until"] = time.time() + ADMIN_LOCK_MINUTES * 60
            rec["count"] = 0
            logger.warning("Admin login LOCKED for IP %s for %s min", ip, ADMIN_LOCK_MINUTES)
        _admin_fails[ip] = rec
        return rec

def _admin_clear_fails(ip):
    with _admin_fail_lock:
        _admin_fails.pop(ip, None)

def is_admin():
    if session.get("role") != "admin" or session.get("admin_ok") is not True:
        return False
    # Session expiry
    exp = session.get("admin_expires")
    if exp and time.time() > float(exp):
        session.clear()
        return False
    return True

def require_admin(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not is_admin():
            return jsonify({"success": False, "message": "Admin only"}), 403
        return f(*args, **kwargs)
    return wrapped

def _check_admin_password(password: str) -> bool:
    """Constant-time-ish compare"""
    with _admin_pass_lock:
        current = ADMIN_PASS
    expected = current.encode("utf-8")
    given = (password or "").encode("utf-8")
    if len(expected) != len(given):
        # still run compare on dummy to reduce timing leak slightly
        secrets.compare_digest(expected, expected)
        return False
    return secrets.compare_digest(expected, given)

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

# Picha halisi za bidhaa (Unsplash) — badala ya logo
PRODUCT_IMAGE_MAP = {
    "Mahindi": "https://images.unsplash.com/photo-1551754655-cd27e38d2076?w=500&h=360&fit=crop",
    "Mchele": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500&h=360&fit=crop",
    "Ufuta": "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=500&h=360&fit=crop",
    "Alizeti": "https://images.unsplash.com/photo-1597848212624-e593b9f0b0b6?w=500&h=360&fit=crop",
    "Maharage": "https://images.unsplash.com/photo-1515543904379-3d757afe72e4?w=500&h=360&fit=crop",
    "Korosho": "https://images.unsplash.com/photo-1508747703725-719777637510?w=500&h=360&fit=crop",
    "Kahawa Arabica": "https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=500&h=360&fit=crop",
    "Chai": "https://images.unsplash.com/photo-1564890369478-c89ca6d9cde9?w=500&h=360&fit=crop",
    "Pamba": "https://images.unsplash.com/photo-1615485290382-441e4d049cb5?w=500&h=360&fit=crop",
    "Viazi": "https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=500&h=360&fit=crop",
    "Ndizi": "https://images.unsplash.com/photo-1571771894821-ce9b6c11b25e?w=500&h=360&fit=crop",
    "Embe": "https://images.unsplash.com/photo-1553279768-865429fa0078?w=500&h=360&fit=crop",
    "Nanasi": "https://images.unsplash.com/photo-1550258987-190a2d41a8ba?w=500&h=360&fit=crop",
    "Karanga": "https://images.unsplash.com/photo-1567892730792-2045c3e5a3c8?w=500&h=360&fit=crop",
    "Uwele": "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=500&h=360&fit=crop",
    "Mtama": "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=500&h=360&fit=crop",
    "Mbaazi": "https://images.unsplash.com/photo-1596797038530-2c107229654b?w=500&h=360&fit=crop",
    "Kunde": "https://images.unsplash.com/photo-1596797038530-2c107229654b?w=500&h=360&fit=crop",
    "Ngano": "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=500&h=360&fit=crop",
    "Mihogo": "https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=500&h=360&fit=crop",
    "Viazi Vitamu": "https://images.unsplash.com/photo-1596097635121-14b63b7a0c19?w=500&h=360&fit=crop",
    "Nyanya": "https://images.unsplash.com/photo-1546470427-e26264be0b27?w=500&h=360&fit=crop",
    "Vitunguu": "https://images.unsplash.com/photo-1518977956812-cd3dbadaaf31?w=500&h=360&fit=crop",
    "Pilipili": "https://images.unsplash.com/photo-1588252303782-a876e8e22b6e?w=500&h=360&fit=crop",
    "Maziwa": "https://images.unsplash.com/photo-1563636619-e9143da7973b?w=500&h=360&fit=crop",
    "Mayai": "https://images.unsplash.com/photo-1582722872445-44dc5f7e3c8f?w=500&h=360&fit=crop",
    "Kuku": "https://images.unsplash.com/photo-1548550023-2bdb3ff85d85?w=500&h=360&fit=crop",
    "Samaki": "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=500&h=360&fit=crop",
    "Mbegu za Mahindi": "https://images.unsplash.com/photo-1464226184884-fa280b87c399?w=500&h=360&fit=crop",
    "Mbegu za Maharage": "https://images.unsplash.com/photo-1464226184884-fa280b87c399?w=500&h=360&fit=crop",
    "Mbolea NPK": "https://images.unsplash.com/photo-1416879595882-3373a0480b5b?w=500&h=360&fit=crop",
    "Mbolea Urea": "https://images.unsplash.com/photo-1416879595882-3373a0480b5b?w=500&h=360&fit=crop",
    "Dawa ya Mimea": "https://images.unsplash.com/photo-1416879595882-3373a0480b5b?w=500&h=360&fit=crop",
    "Trekta": "https://images.unsplash.com/photo-1625246333195-78d9c38ad449?w=500&h=360&fit=crop",
    "Pampu ya Maji": "https://images.unsplash.com/photo-1581094794329-adee35d56517?w=500&h=360&fit=crop",
}
DEFAULT_PRODUCT_IMAGE = "https://images.unsplash.com/photo-1464226184884-fa280b87c399?w=500&h=360&fit=crop"


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
            "image": PRODUCT_IMAGE_MAP.get(prod["title"], DEFAULT_PRODUCT_IMAGE),
            "picha": PRODUCT_IMAGE_MAP.get(prod["title"], DEFAULT_PRODUCT_IMAGE),
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
    """Smart conversational bot — no repetitive greetings, guides to payment"""
    msg = (message or "").strip()
    msg_l = msg.lower()
    history = history or []

    def cta_pay(topic="huduma"):
        return (
            f"\n\n💡 Ili kupata taarifa kamili za {topic} (bei, eneo, muuzaji), "
            "bofya **PATA MSAADA HAPA** au **Omba Ushauri**, lipa ada **TZS 3,000**, "
            "kisha AI itakutumia taarifa kupitia WhatsApp.\n"
            "Karibu tena wakati wowote — tunaweza kuendelea kuongea hapa ukihitaji! 😊"
        )

    if not msg_l:
        return "Karibu! Niambie unachotafuta — mfano mahindi, ufuta, au ushauri wa kilimo."

    # --- Detect product FIRST (before greetings) ---
    product_map = {
        "mahindi": "Mahindi", "mchele": "Mchele", "ufuta": "Ufuta", "kahawa": "Kahawa",
        "maharage": "Maharage", "alizeti": "Alizeti", "viazi": "Viazi", "nyanya": "Nyanya",
        "korosho": "Korosho", "pamba": "Pamba", "chai": "Chai", "ndizi": "Ndizi",
        "embe": "Embe", "kuku": "Kuku", "samaki": "Samaki", "mbegu": "Mbegu",
        "mbolea": "Mbolea", "trekta": "Trekta", "maziwa": "Maziwa", "pilipili": "Pilipili",
        "nanasi": "Nanasi", "karanga": "Karanga", "vitunguu": "Vitunguu", "mihogo": "Mihogo",
    }
    found = []
    for k, v in product_map.items():
        if k in msg_l:
            found.append(v)
    # unique preserve order
    seen = set()
    found = [x for x in found if not (x in seen or seen.add(x))]

    if found:
        p = found[0]
        return (
            f"Nzuri sana! **{p}** inapatikana katika mikoa mbalimbali ya Tanzania na Afrika Mashariki. "
            f"Unaweza kuona jina lake kwenye orodha ya bidhaa. "
            f"Unahitaji {p} kutoka mkoa gani, au kiasi gani?"
            + cta_pay(p)
        )

    # Searching intent
    if any(w in msg_l for w in ["natafuta", "nataka", "ninatafuta", "tafuta", "napata", "ipo", "linapatikana"]):
        return (
            "Sawa, niko tayari kukusaidia kutafuta. Andika jina la bidhaa — mfano: *mahindi*, *ufuta*, *kahawa*. "
            "Unaweza pia kutumia sehemu ya **Tafuta** juu ya ukurasa."
            + cta_pay("bidhaa unayotafuta")
        )

    # Prices
    if any(w in msg_l for w in ["bei", "price", "ghali", "nafuu", "gharama", "pesa", "ngapi"]):
        return (
            "Bei kamili hutolewa baada ya kulipa ada ya **TZS 3,000** — hii inalinda siri za wafanyabiashara. "
            "Bofya **PATA MSAADA HAPA**, lipa, kisha utapata bei, eneo na muuzaji kwa WhatsApp."
            + "\n\nTunaweza kuendelea kuongea hapa kama una maswali mengine! 😊"
        )

    # Payment
    if any(w in msg_l for w in ["lipa", "malipo", "ada", "m-pesa", "mpesa", "airtel", "halotel", "payment", "order"]):
        return (
            "Ada ni **TZS 3,000**.\n"
            "1️⃣ Bofya **PATA MSAADA HAPA** au **Omba Ushauri**\n"
            "2️⃣ Chagua M-Pesa / Halotel / Airtel Money\n"
            "3️⃣ Weka namba yako → Endelea na Malipo\n"
            "4️⃣ WhatsApp inafunguka (0755 248 789)\n"
            "Baada ya kuthibitisha, AI inakutumia taarifa kamili.\n"
            "Una swali jingine kuhusu malipo? Naweza kuendelea kukuongoza."
        )

    # Advisory
    if any(w in msg_l for w in ["ushauri", "mshauri", "wataalamu", "kilimo", "mavuno", "shamba", "kulima"]):
        return (
            "Kwa ushauri wa kitaalamu wa kilimo: bofya **Omba Ushauri wa Kitaalamu**, "
            "lipa TZS 3,000, kisha utaunganishwa na mshauri kupitia WhatsApp **0755 248 789**."
            + "\n\nUnaweza kuniuliza zaidi hapa kabla ya kulipa — niko 24/7! 🌱"
        )

    # Location
    if any(w in msg_l for w in ["mkoa", "eneo", "location", "wapi", "dar", "arusha", "mwanza", "mbeya", "ruvuma", "dodoma"]):
        return (
            "Tunatafuta katika mikoa yote ya Tanzania na Afrika Mashariki. "
            "Eneo kamili la muuzaji linaonyeshwa baada ya kulipa ada."
            + cta_pay("eneo na muuzaji")
        )

    # How it works
    if any(w in msg_l for w in ["jinsi", "namna", "how", "kazi", "mfumo", "eleza", "maelezo"]):
        return (
            "Hivi ndivyo inavyofanya kazi:\n"
            "1️⃣ Tafuta / angalia bidhaa\n"
            "2️⃣ Bofya **PATA MSAADA HAPA**\n"
            "3️⃣ Lipa TZS 3,000\n"
            "4️⃣ WhatsApp inafunguka\n"
            "5️⃣ AI inakutumia bei, eneo na muuzaji\n"
            "Unaweza kuendelea kuuliza maswali hapa kabla ya kulipa. Karibu! 😊"
        )

    # Thanks
    if any(w in msg_l for w in ["asante", "thanks", "thank you", "shukrani", "nashukuru"]):
        return "Karibu sana! 😊 Rudi wakati wowote — niko hapa 24/7. Ukikoa tayari, bofya **PATA MSAADA HAPA** kupata taarifa kamili."

    # Bye
    if any(w in msg_l for w in ["kwaheri", "bye", "tutaonana", "baadaye"]):
        return "Kwaheri! Rudi tena unapohitaji msaada. Tuko hapa 24/7. 👋"

    # Problem
    if any(w in msg_l for w in ["tatizo", "problem", "haifanyi", "error", "imekwama", "help", "msaada"]):
        return (
            "Samahani. Jaribu refresh ukurasa au angalia intaneti. "
            "Kama bado, wasiliana WhatsApp **0755 248 789**. Ninaweza kukusaidia vipi sasa?"
        )

    # Who are you
    if any(w in msg_l for w in ["wewe nani", "nani wewe", "bot", "robot"]):
        return (
            "Mimi ni msaidizi wa NjiaMauzo Afrika — niko 24/7. "
            "Naweza kukusaidia kutafuta mazao, kueleza malipo, na kukuunganisha na washauri. Unahitaji nini?"
        )

    # Greetings ONLY if message is short greeting (not mixed with product words)
    greet_words = ["habari", "hujambo", "hello", "hi", "mambo", "salama", "shikamoo", "vipi", "sasa"]
    is_pure_greet = any(w in msg_l for w in greet_words) and len(msg_l.split()) <= 4 and not found
    if is_pure_greet:
        # Avoid repeating same greeting if history has recent bot greeting
        recent = " ".join(history[-3:]).lower() if history else ""
        if "niambie unachotafuta" in recent or "karibu njiamauzo" in recent:
            return "Ndiyo, niko hapa! 😊 Andika bidhaa unayotafuta (mfano *mahindi*) au uliza kuhusu bei / ushauri / malipo."
        return random.choice([
            "Habari yako! Karibu NjiaMauzo Afrika 🌍. Unatafuta bidhaa gani leo?",
            "Hujambo! Ninafurahi kukuona. Niambie unachotafuta — mahindi, ufuta, kahawa...?",
            "Mambo vipi! 😊 Naweza kukusaidia kutafuta mazao au kueleza jinsi ya kupata bei. Unahitaji nini?",
        ])

    # How are you
    if any(w in msg_l for w in ["hali gani", "u hali", "how are you", "upo salama"]):
        return "Niko salama, nikikuhudumia 24/7! 💪 Na wewe? Unahitaji msaada gani kuhusu soko la mazao?"

    # Default — engage + soft CTA
    return (
        "Nimeelewa. Ili nikusaidie vizuri: andika jina la bidhaa (mfano *mahindi*, *ufuta*) "
        "au uliza kuhusu bei, ushauri wa kilimo, au malipo.\n"
        "Tunaweza kuendelea kuongea hapa. Ukikoa tayari kupata taarifa kamili, bofya **PATA MSAADA HAPA** (ada TZS 3,000). 😊"
    )



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
                "image": p.get("image") or PRODUCT_IMAGE_MAP.get(p.get("jina") or "", DEFAULT_PRODUCT_IMAGE),
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
                "image": p.get("image") or PRODUCT_IMAGE_MAP.get(p.get("jina") or "", DEFAULT_PRODUCT_IMAGE),
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
                "image": p.get("image") or PRODUCT_IMAGE_MAP.get(p.get("jina") or "", DEFAULT_PRODUCT_IMAGE),
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
                "image": p.get("image") or PRODUCT_IMAGE_MAP.get(p.get("jina") or "", DEFAULT_PRODUCT_IMAGE),
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

def require_csrf(f):
    """CSRF check kwa endpoints mpya (frontend tayari inatuma X-CSRF-Token)."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        sent = request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf", "")
        if not expected or not sent or not secrets.compare_digest(str(sent), str(expected)):
            return jsonify({"success": False, "message": "CSRF token si sahihi. Onyesha upya ukurasa."}), 403
        return f(*args, **kwargs)
    return wrapped

# ---------------------------------------------------------------------------
# RESEARCH — AI kutafuta taarifa za bidhaa, masoko, bei na wauzaji
# ---------------------------------------------------------------------------
def _audit_log(action, detail=""):
    logger.info("AUDIT action=%s ip=%s detail=%s", action, _client_ip(), detail)

@app.route("/api/research", methods=["POST"])
@rate_limit(20, 60)
def research():
    data = request.get_json(force=True, silent=True) or {}
    query = str(data.get("query", "")).strip()[:200]
    region = str(data.get("region", "")).strip() or None
    if not query:
        return jsonify({"success": False, "message": "Andika unachotafuta, mfano: ufuta Ruvuma"}), 400

    _audit_log("research", query[:80])
    matches = ai_search_products(query=query, region=region, limit=10)

    by_location = {}
    for m in matches:
        loc = m["location"]
        by_location.setdefault(loc, []).append(m["real_price"])

    comparison = [
        {
            "location": loc,
            "avg_price": int(sum(prices) / len(prices)),
            "min_price": min(prices),
            "max_price": max(prices),
            "listings": len(prices),
        }
        for loc, prices in sorted(by_location.items(), key=lambda x: sum(x[1]) / len(x[1]))
    ]

    all_prices = [m["real_price"] for m in matches] or [0]
    summary = {
        "query": query,
        "total_listings": len(matches),
        "avg_price": int(sum(all_prices) / len(all_prices)),
        "min_price": min(all_prices),
        "max_price": max(all_prices),
        "locations_covered": len(by_location),
        "generated_at": utcnow_iso(),
    }

    sources = [
        {
            "product": m["jina"],
            "location": m["location"],
            "chanzo": "NjiaMauzo AI Searcher",
            "updated": utcnow_iso(),
        }
        for m in matches[:6]
    ]

    return jsonify({
        "success": True,
        "summary": summary,
        "comparison": comparison,
        "sources": sources,
    })

# ---------------------------------------------------------------------------
# AUTOMATE — price alerts zinazojiendesha automatically (dakika 45-120)
# ---------------------------------------------------------------------------
_price_alerts = {}   # alert_id -> alert dict
_alert_id_counter = 1
_alert_lock = threading.Lock()

def _next_alert_id():
    global _alert_id_counter
    with _alert_lock:
        aid = _alert_id_counter
        _alert_id_counter += 1
        return aid

@app.route("/api/automate/alerts", methods=["GET"])
def list_alerts():
    owner = session.get("alert_owner")
    mine = [a for a in _price_alerts.values() if a["owner"] == owner] if owner else []
    return jsonify({"success": True, "alerts": mine})

@app.route("/api/automate/alerts", methods=["POST"])
@rate_limit(10, 60)
@require_csrf
def create_alert():
    if not session.get("alert_owner"):
        session["alert_owner"] = secrets.token_hex(8)
    data = request.get_json(force=True, silent=True) or {}
    keyword = str(data.get("keyword", "")).strip()[:80]
    try:
        threshold = int(data.get("threshold_price", 0))
    except (TypeError, ValueError):
        threshold = 0
    if not keyword or threshold <= 0:
        return jsonify({"success": False, "message": "Weka bidhaa na kiwango cha bei (TZS)."}), 400

    alert = {
        "id": _next_alert_id(),
        "owner": session["alert_owner"],
        "keyword": keyword,
        "threshold_price": threshold,
        "created": utcnow_iso(),
        "last_checked": None,
        "triggered": [],
    }
    with _alert_lock:
        _price_alerts[alert["id"]] = alert
    _audit_log("create_alert", f"{keyword} <= {threshold}")
    push_activity(f"⚙️ Alert mpya imewekwa: {keyword} chini ya TZS {threshold:,}", activity_type="automate")
    return jsonify({"success": True, "alert": alert})

@app.route("/api/automate/alerts/<int:alert_id>", methods=["DELETE"])
@require_csrf
def delete_alert(alert_id):
    owner = session.get("alert_owner")
    with _alert_lock:
        a = _price_alerts.get(alert_id)
        if not a or a["owner"] != owner:
            return jsonify({"success": False, "message": "Alert haipatikani."}), 404
        del _price_alerts[alert_id]
    return jsonify({"success": True})

def _check_price_alerts():
    """Inaangalia alerts zote dhidi ya bei za sasa - inaitwa na background thread."""
    with _alert_lock:
        alerts = list(_price_alerts.values())
    for alert in alerts:
        matches = [
            p for p in PRODUCTS_CATALOG
            if alert["keyword"].lower() in p["title"].lower() or alert["keyword"].lower() in p["category"].lower()
        ]
        if not matches:
            continue
        prod = random.choice(matches)
        low, high = prod["price_range"]
        current_price = random.randint(low, high)
        alert["last_checked"] = utcnow_iso()
        if current_price <= alert["threshold_price"]:
            hit = {"price": current_price, "time": utcnow_iso(), "product": prod["title"]}
            alert["triggered"].insert(0, hit)
            alert["triggered"] = alert["triggered"][:10]
            push_activity(
                f"🔔 ALERT: {prod['title']} imefika TZS {current_price:,} (chini ya kiwango chako TZS {alert['threshold_price']:,})",
                activity_type="alert",
                extra={"product": prod["title"], "price": current_price},
            )

def background_automation_loop():
    """Automate — kazi za kurudia zinajiendesha kila dakika 45-120 sekunde"""
    while True:
        try:
            time.sleep(random.uniform(45, 120))
            if _price_alerts:
                _check_price_alerts()
        except Exception as e:
            logger.error("Automation loop error: %s", e)
            time.sleep(10)


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
@rate_limit(5, 60)
def admin_login():
    ip = _client_ip()

    if _admin_is_locked(ip):
        logger.warning("Admin login blocked (locked) IP=%s", ip)
        return jsonify({
            "success": False,
            "message": f"Jaribio nyingi. Subiri dakika {ADMIN_LOCK_MINUTES} kisha ujaribu tena."
        }), 429

    data = request.get_json(force=True, silent=True) or {}
    username = str(data.get("username", "")).strip()[:64]
    password = str(data.get("password", ""))[:128]

    # Reject empty
    if not username or not password:
        return jsonify({"success": False, "message": "Jaza username na password."}), 400

    user_ok = secrets.compare_digest(username, ADMIN_USER)
    pass_ok = _check_admin_password(password)

    if user_ok and pass_ok:
        _admin_clear_fails(ip)
        session.clear()
        session["role"] = "admin"
        session["admin_ok"] = True
        session["admin_expires"] = time.time() + ADMIN_SESSION_HOURS * 3600
        session["admin_ip"] = ip
        session["user"] = {
            "name": "Admin",
            "email": "admin@njiamauzo.local",
            "phone": "—",
            "role": "admin",
            "bypass_payment": True,
        }
        logger.info("Admin login SUCCESS ip=%s", ip)
        return jsonify({
            "success": True,
            "message": f"Admin umeingia. Session inaisha baada ya saa {int(ADMIN_SESSION_HOURS)}.",
            "csrf_token": secrets.token_hex(16),
            "role": "admin",
            "expires_hours": ADMIN_SESSION_HOURS,
            "must_change_password": _admin_must_change_password,
        })

    rec = _admin_register_fail(ip)
    logger.warning("Admin login FAIL ip=%s user=%s", ip, username[:20])
    remaining = max(0, ADMIN_MAX_FAILS - rec.get("count", 0))
    if rec.get("locked_until", 0) > time.time():
        msg = f"Jaribio nyingi. Akaunti imefungwa kwa dakika {ADMIN_LOCK_MINUTES}."
    else:
        msg = f"Username au password si sahihi. Jaribio zilizobaki: {remaining}."
    return jsonify({"success": False, "message": msg}), 401

@app.route("/api/admin/status")
def admin_status():
    return jsonify({
        "success": True,
        "is_admin": is_admin(),
        "expires_in_sec": max(0, int(float(session.get("admin_expires", 0)) - time.time())) if is_admin() else 0,
        "must_change_password": _admin_must_change_password if is_admin() else False,
    })

@app.route("/api/admin/change-password", methods=["POST"])
@require_admin
@rate_limit(5, 60)
def admin_change_password():
    global ADMIN_PASS, _admin_must_change_password
    data = request.get_json(force=True, silent=True) or {}
    old_password = str(data.get("old_password", ""))[:128]
    new_password = str(data.get("new_password", ""))[:128]

    if not _check_admin_password(old_password):
        return jsonify({"success": False, "message": "Password ya sasa si sahihi."}), 401
    if len(new_password) < 4:
        return jsonify({"success": False, "message": "Password mpya lazima iwe na urefu wa herufi 4 au zaidi."}), 400
    if new_password == old_password:
        return jsonify({"success": False, "message": "Password mpya isiwe sawa na ya zamani."}), 400

    with _admin_pass_lock:
        ADMIN_PASS = new_password
    _admin_must_change_password = False
    logger.info("Admin password changed ip=%s", _client_ip())
    return jsonify({"success": True, "message": "Password ya Admin imebadilishwa. Itumie mara ijayo utakapoingia."})

@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return jsonify({"success": True, "message": "Admin ametoka."})

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

_bg_automation = threading.Thread(target=background_automation_loop, daemon=True)
_bg_automation.start()
logger.info("Live Activity 24/7 + Smart Bot started")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("NjiaMauzo Afrika on port %s", port)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
