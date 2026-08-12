"""
NjiaMauzo Afrika — Backend (Flask)
Live Activity Feed + AI Product Searcher
Covers all regions of Tanzania & East Africa
"""

from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from datetime import datetime, timezone
import random
import time
import os
import hashlib
import secrets
import threading
import logging

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("njiamauzo")

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
CORS(app, supports_credentials=True)

# ---------------------------------------------------------------------------
# Regions & Catalog
# ---------------------------------------------------------------------------
TANZANIA_REGIONS = [
    "Dar es Salaam", "Arusha", "Mwanza", "Mbeya", "Dodoma", "Morogoro",
    "Tanga", "Kilimanjaro", "Ruvuma", "Iringa", "Singida", "Tabora",
    "Kigoma", "Shinyanga", "Mtwara", "Lindi", "Pwani", "Geita",
    "Simiyu", "Katavi", "Njombe", "Rukwa", "Kagera", "Manyara",
    "Songwe", "Zanzibar", "Pemba",
]

EAST_AFRICA = [
    "Nairobi", "Mombasa", "Kisumu", "Nakuru",
    "Kampala", "Jinja", "Mbarara",
    "Kigali", "Musanze",
    "Bujumbura", "Gitega",
    "Juba", "Wau",
]

ALL_LOCATIONS = TANZANIA_REGIONS + EAST_AFRICA

PRODUCTS_CATALOG = [
    {"title": "Mahindi", "unit": "gunia", "category": "Nafaka", "price_range": (45000, 120000)},
    {"title": "Mchele", "unit": "gunia", "category": "Nafaka", "price_range": (80000, 180000)},
    {"title": "Ufuta", "unit": "tani", "category": "Mafuta", "price_range": (80000, 250000)},
    {"title": "Alizeti", "unit": "gunia", "category": "Mafuta", "price_range": (70000, 160000)},
    {"title": "Maharage", "unit": "gunia", "category": "Legume", "price_range": (60000, 150000)},
    {"title": "Korosho", "unit": "kg", "category": "Karanga", "price_range": (7000, 25000)},
    {"title": "Kahawa Arabica", "unit": "kg", "category": "Kahawa", "price_range": (8000, 18000)},
    {"title": "Chai", "unit": "kg", "category": "Chai", "price_range": (5000, 12000)},
    {"title": "Pamba", "unit": "tani", "category": "Pamba", "price_range": (1500000, 3500000)},
    {"title": "Viazi", "unit": "gunia", "category": "Mizizi", "price_range": (30000, 80000)},
    {"title": "Ndizi", "unit": "mkunguru", "category": "Matunda", "price_range": (15000, 45000)},
    {"title": "Embe", "unit": "sanduku", "category": "Matunda", "price_range": (20000, 60000)},
    {"title": "Nanasi", "unit": "sanduku", "category": "Matunda", "price_range": (18000, 50000)},
    {"title": "Karanga", "unit": "gunia", "category": "Karanga", "price_range": (50000, 110000)},
    {"title": "Uwele", "unit": "gunia", "category": "Nafaka", "price_range": (40000, 90000)},
    {"title": "Mtama", "unit": "gunia", "category": "Nafaka", "price_range": (35000, 85000)},
    {"title": "Mbaazi", "unit": "gunia", "category": "Legume", "price_range": (55000, 130000)},
    {"title": "Kunde", "unit": "gunia", "category": "Legume", "price_range": (50000, 120000)},
    {"title": "Ngano", "unit": "gunia", "category": "Nafaka", "price_range": (70000, 140000)},
    {"title": "Mihogo", "unit": "tani", "category": "Mizizi", "price_range": (200000, 500000)},
    {"title": "Viazi Vitamu", "unit": "gunia", "category": "Mizizi", "price_range": (25000, 70000)},
    {"title": "Nyanya", "unit": "sanduku", "category": "Mboga", "price_range": (20000, 70000)},
    {"title": "Vitunguu", "unit": "gunia", "category": "Mboga", "price_range": (40000, 100000)},
    {"title": "Pilipili", "unit": "kg", "category": "Mboga", "price_range": (3000, 12000)},
    {"title": "Maziwa", "unit": "lita", "category": "Maziwa", "price_range": (1200, 2500)},
    {"title": "Mayai", "unit": "tray", "category": "Kuku", "price_range": (6000, 12000)},
    {"title": "Kuku", "unit": "kilo", "category": "Kuku", "price_range": (7000, 15000)},
    {"title": "Samaki", "unit": "kg", "category": "Samaki", "price_range": (8000, 20000)},
    {"title": "Mbegu za Mahindi", "unit": "kg", "category": "Mbegu", "price_range": (5000, 30000)},
    {"title": "Mbegu za Maharage", "unit": "kg", "category": "Mbegu", "price_range": (4000, 25000)},
    {"title": "Mbolea NPK", "unit": "gunia", "category": "Mbolea", "price_range": (50000, 120000)},
    {"title": "Mbolea Urea", "unit": "gunia", "category": "Mbolea", "price_range": (55000, 130000)},
    {"title": "Dawa ya Mimea", "unit": "lita", "category": "Dawa", "price_range": (15000, 80000)},
    {"title": "Trekta", "unit": "pcs", "category": "Vifaa", "price_range": (8000000, 25000000)},
    {"title": "Pampu ya Maji", "unit": "pcs", "category": "Vifaa", "price_range": (150000, 800000)},
]

SELLER_NAMES = [
    "Juma Mkulima", "Amina Biashara", "Peter Farms", "Grace Agro",
    "Hassan Traders", "Fatuma Supplies", "John Agriculture", "Maria Exports",
    "Said Cooperative", "Neema Fresh", "David Produce", "Rehema Market",
    "Baraka Farms", "Zainab Trading", "Michael Agro Hub", "Esther Seeds",
    "Kilimo Bora Ltd", "Green Valley Farms", "Umoja Cooperative", "Safari Exports",
]

ACTIVITY_TEMPLATES = [
    # Public feed: product + region only — NO prices, NO seller names
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

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
_lock = threading.Lock()
activity_store = []
activity_id_counter = 1
products_store = []
product_id_counter = 1

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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
        if len(activity_store) > 250:
            del activity_store[250:]
    return item


# ---------------------------------------------------------------------------
# AI Product Searcher
# ---------------------------------------------------------------------------
def ai_search_products(query="", region=None, limit=12):
    """Search products across Tanzania & East Africa regions."""
    results = []
    q = (query or "").lower().strip()

    matched = PRODUCTS_CATALOG
    if q:
        matched = [
            p for p in PRODUCTS_CATALOG
            if q in p["title"].lower() or q in p["category"].lower()
        ]
        if not matched:
            words = q.split()
            matched = [
                p for p in PRODUCTS_CATALOG
                if any(w in p["title"].lower() or w in p["category"].lower() for w in words)
            ]
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

        results.append({
            "id": next_product_id(),
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
            "image": "/static/logo.png",
            "picha": "/static/logo.png",
            "available": True,
        })

    return results


def generate_activity_message():
    template = random.choice(ACTIVITY_TEMPLATES)
    prod = random.choice(PRODUCTS_CATALOG)
    loc = random.choice(ALL_LOCATIONS)
    seller = random.choice(SELLER_NAMES)
    buyer = random.choice(SELLER_NAMES)
    qty = random.choice([5, 10, 20, 50, 100, 200])
    low, high = prod["price_range"]
    price = random.randint(low, high)

    msg = template.format(
        seller=seller,
        buyer=buyer,
        product=prod["title"],
        location=loc,
        qty=qty,
        unit=prod["unit"],
        price=price,
    )
    return push_activity(msg, activity_type="live", extra={
        "location": loc,
        "product": prod["title"],
    })


def seed_initial_data():
    global products_store
    logger.info("Seeding products & activity...")

    seeded = []
    for _ in range(42):
        batch = ai_search_products(limit=1)
        if batch:
            seeded.append(batch[0])
    products_store = seeded

    for _ in range(18):
        generate_activity_message()

    logger.info("Seeded %d products, %d activities", len(products_store), len(activity_store))


def background_activity_generator():
    """Generate live activity every 7-18 seconds."""
    while True:
        try:
            time.sleep(random.uniform(45, 120))  # every few minutes
            generate_activity_message()
        except Exception as e:
            logger.error("Activity generator error: %s", e)
            time.sleep(5)


# ---------------------------------------------------------------------------
# Routes — Pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    # Absolute path — works reliably on Render / gunicorn
    base = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(base, "index.html")

@app.route("/static/<path:filename>")
def static_files(filename):
    base = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(base, "static")
    if os.path.isdir(static_dir):
        return send_from_directory(static_dir, filename)
    return send_from_directory(base, filename)


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------
@app.route("/api/csrf-token")
def csrf_token():
    token = secrets.token_hex(16)
    session["csrf"] = token
    return jsonify({"csrf_token": token})


@app.route("/api/me")
def me():
    return jsonify({"success": False, "message": "Not logged in"})


@app.route("/api/products")
def get_products():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    products = []
    for p in products_store[:30]:
        # Public view: product name only — no seller, no exact location, no price
        public = {
            "id": p["id"],
            "title": p.get("jina") or p["title"].split("—")[0].strip(),
            "description": "Taarifa kamili (bei, eneo, muuzaji) zinapatikana baada ya kulipa ada.",
            "location": "",
            "seller_name": "",
            "seller_id": p.get("seller_id", ""),
            "likes": p.get("likes", 0),
            "image": p.get("image", "/static/logo.png"),
            "available": True,
            "category": p.get("category", ""),
        }
        if lat and lon:
            public["distance_km"] = None  # hidden until payment
        products.append(public)

    return jsonify({"success": True, "products": products})


@app.route("/api/ai-products")
def ai_products():
    """AI Searcher — searches all TZ + East Africa regions."""
    q = request.args.get("q", "").strip()
    region = request.args.get("region")
    results = ai_search_products(query=q, region=region, limit=16)

    if q:
        push_activity(
            f"🔍 AI Searcher imetafuta '{q}' katika mikoa ya Tanzania na Afrika Mashariki — {len(results)} matokeo",
            activity_type="ai_search",
        )

    # Public results: hide price, seller, exact location
    public_results = []
    for p in results:
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
            "image": p.get("image", "/static/logo.png"),
            "picha": p.get("image", "/static/logo.png"),
            "available": True,
            "category": p.get("category", ""),
        })

    return jsonify({"success": True, "products": public_results})


@app.route("/api/activity")
def get_activity():
    """Live Activity Feed."""
    since_id = request.args.get("since_id", 0, type=int)
    with _lock:
        items = [a for a in activity_store if a["id"] > since_id]
    items = sorted(items, key=lambda x: x["id"], reverse=True)[:30]
    return jsonify({"success": True, "activity": items})


@app.route("/api/market-stats")
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
            "top_location": "",  # hidden — available after payment
            "share": round(data["count"] / total * 100, 1),
        })

    # Locations hidden publicly — full details after payment
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
def payment_request():
    data = request.get_json(force=True, silent=True) or {}
    method = data.get("njia", "")
    phone = data.get("simu", "")

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

    return jsonify({
        "success": True,
        "payment_number": payment_number,
        "order_id": order_id,
        "status": "PENDING",
    })


@app.route("/api/captcha")
def captcha():
    a, b = random.randint(1, 12), random.randint(1, 12)
    captcha_id = secrets.token_hex(8)
    session[f"captcha_{captcha_id}"] = a + b
    return jsonify({"captcha_id": captcha_id, "question": f"{a} + {b} = ?"})


@app.route("/api/register", methods=["POST"])
def register():
    return jsonify({"success": True, "message": "Umesajiliwa", "csrf_token": secrets.token_hex(16)})


@app.route("/api/login", methods=["POST"])
def login():
    return jsonify({"success": True, "message": "Umeingia", "csrf_token": secrets.token_hex(16)})


@app.route("/api/logout", methods=["POST"])
def logout():
    return jsonify({"success": True})


@app.route("/api/password/forgot", methods=["POST"])
def forgot():
    return jsonify({"success": True, "message": "OTP imetumwa", "reset_id": secrets.token_hex(8)})


@app.route("/api/password/reset", methods=["POST"])
def reset():
    return jsonify({"success": True, "message": "Nywila imebadilishwa"})


@app.route("/api/password/change", methods=["POST"])
def change_pw():
    return jsonify({"success": True, "message": "Nywila imebadilishwa"})


@app.route("/api/products/<int:pid>/like", methods=["POST"])
def like_product(pid):
    return jsonify({"success": True, "likes": random.randint(1, 50), "liked": True})


@app.route("/api/sellers/<sid>/follow", methods=["POST"])
def follow_seller(sid):
    return jsonify({"success": True, "following": True, "followers": random.randint(5, 200)})


@app.route("/api/comments/<int:pid>")
def get_comments(pid):
    return jsonify({"success": True, "comments": []})


@app.route("/api/comments/<int:pid>", methods=["POST"])
def post_comment(pid):
    return jsonify({"success": True})


@app.route("/api/bot-chat", methods=["POST"])
def bot_chat():
    data = request.get_json(force=True, silent=True) or {}
    msg = (data.get("message") or "").lower()

    if any(w in msg for w in ["bei", "price", "ghali", "nafuu"]):
        reply = "Bei za mazao zinabadilika kulingana na eneo. Tumia utafutaji au bofya PATA MSAADA HAPA ili tukumsaidie."
    elif any(w in msg for w in ["mahindi", "mchele", "ufuta", "kahawa", "maharage", "alizeti"]):
        reply = "Nimeelewa unatafuta mazao. Nitatumia AI Searcher kutafuta katika mikoa yote ya Tanzania na Afrika Mashariki. Bofya 'Tafuta' au PATA MSAADA HAPA."
    elif any(w in msg for w in ["ushauri", "mshauri", "kilimo", "mbegu"]):
        reply = "Kwa ushauri wa kitaalamu, bofya 'Omba Ushauri wa Kitaalamu', lipa ada ya TZS 3,000 kisha utaunganishwa na mshauri kupitia WhatsApp."
    elif any(w in msg for w in ["habari", "hujambo", "hello", "hi", "mambo"]):
        reply = "Karibu NjiaMauzo Afrika! 🌍 Naweza kukusaidia kutafuta bidhaa, mazao, na kuunganisha na washauri wa kilimo. Unauliza nini?"
    else:
        reply = "Karibu NjiaMauzo Afrika! 🌍 Naweza kukusaidia kutafuta bidhaa, mazao, na kuunganisha na washauri wa kilimo. Unauliza nini?"

    return jsonify({"reply": reply})


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "products": len(products_store),
        "activities": len(activity_store),
    })


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
seed_initial_data()

_bg = threading.Thread(target=background_activity_generator, daemon=True)
_bg.start()
logger.info("Live Activity generator started")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("NjiaMauzo Afrika starting on port %s", port)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
