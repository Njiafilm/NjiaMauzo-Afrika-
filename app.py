"""
NjiaMauzo Afrika — Backend (Flask)
Live Activity Feed + AI Product Searcher (Tanzania & East Africa)
"""

from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from datetime import datetime, timedelta
import random
import time
import os
import hashlib
import secrets
import threading

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = secrets.token_hex(32)
CORS(app, supports_credentials=True)

# ============================================================
# DATA: Mikoa ya Tanzania + Afrika Mashariki
# ============================================================

TANZANIA_REGIONS = [
    "Dar es Salaam", "Arusha", "Mwanza", "Mbeya", "Dodoma", "Morogoro",
    "Tanga", "Kilimanjaro", "Ruvuma", "Iringa", "Singida", "Tabora",
    "Kigoma", "Shinyanga", "Mtwara", "Lindi", "Pwani", "Geita",
    "Simiyu", "Katavi", "Njombe", "Rukwa", "Kagera", "Manyara",
    "Songwe", "Zanzibar", "Pemba"
]

EAST_AFRICA = [
    "Nairobi", "Mombasa", "Kisumu", "Nakuru",          # Kenya
    "Kampala", "Jinja", "Mbarara",                      # Uganda
    "Kigali", "Musanze",                                # Rwanda
    "Bujumbura", "Gitega",                              # Burundi
    "Juba", "Wau",                                      # South Sudan
]

ALL_LOCATIONS = TANZANIA_REGIONS + EAST_AFRICA

PRODUCTS_CATALOG = [
    {"title": "Mahindi", "unit": "gunia", "category": "Nafaka"},
    {"title": "Mchele", "unit": "gunia", "category": "Nafaka"},
    {"title": "Ufuta", "unit": "tani", "category": "Mafuta"},
    {"title": "Alizeti", "unit": "gunia", "category": "Mafuta"},
    {"title": "Maharage", "unit": "gunia", "category": "Legume"},
    {"title": "Korosho", "unit": "kg", "category": "Karanga"},
    {"title": "Kahawa Arabica", "unit": "kg", "category": "Kahawa"},
    {"title": "Chai", "unit": "kg", "category": "Chai"},
    {"title": "Pamba", "unit": "tani", "category": "Pamba"},
    {"title": "Viazi", "unit": "gunia", "category": "Mizizi"},
    {"title": "Ndizi", "unit": "mkunguru", "category": "Matunda"},
    {"title": "Embe", "unit": "sanduku", "category": "Matunda"},
    {"title": "Nanasi", "unit": "sanduku", "category": "Matunda"},
    {"title": "Karanga", "unit": "gunia", "category": "Karanga"},
    {"title": "Uwele", "unit": "gunia", "category": "Nafaka"},
    {"title": "Mtama", "unit": "gunia", "category": "Nafaka"},
    {"title": "Mbaazi", "unit": "gunia", "category": "Legume"},
    {"title": "Kunde", "unit": "gunia", "category": "Legume"},
    {"title": "Ngano", "unit": "gunia", "category": "Nafaka"},
    {"title": "Mihogo", "unit": "tani", "category": "Mizizi"},
    {"title": "Viazi Vitamu", "unit": "gunia", "category": "Mizizi"},
    {"title": "Nyanya", "unit": "sanduku", "category": "Mboga"},
    {"title": "Vitunguu", "unit": "gunia", "category": "Mboga"},
    {"title": "Pilipili", "unit": "kg", "category": "Mboga"},
    {"title": "Maziwa", "unit": "lita", "category": "Maziwa"},
    {"title": "Mayai", "unit": "tray", "category": "Kuku"},
    {"title": "Kuku", "unit": "kilo", "category": "Kuku"},
    {"title": "Samaki", "unit": "kg", "category": "Samaki"},
    {"title": "Mbegu za Mahindi", "unit": "kg", "category": "Mbegu"},
    {"title": "Mbegu za Maharage", "unit": "kg", "category": "Mbegu"},
    {"title": "Mbolea NPK", "unit": "gunia", "category": "Mbolea"},
    {"title": "Mbolea Urea", "unit": "gunia", "category": "Mbolea"},
    {"title": "Dawa ya Mimea", "unit": "lita", "category": "Dawa"},
    {"title": "Trekta", "unit": "pcs", "category": "Vifaa"},
    {"title": "Pampu ya Maji", "unit": "pcs", "category": "Vifaa"},
]

SELLER_NAMES = [
    "Juma Mkulima", "Amina Biashara", "Peter Farms", "Grace Agro",
    "Hassan Traders", "Fatuma Supplies", "John Agriculture", "Maria Exports",
    "Said Cooperative", "Neema Fresh", "David Produce", "Rehema Market",
    "Baraka Farms", "Zainab Trading", "Michael Agro Hub", "Esther Seeds",
]

ACTIVITY_TEMPLATES = [
    "🆕 {seller} ameongeza {qty} {unit} za {product} kutoka {location}",
    "💰 Bei mpya: {product} {location} sasa TZS {price:,} / {unit}",
    "✅ {buyer} ametafuta {product} eneo la {location}",
    "📦 Agizo jipya: {qty} {unit} za {product} — {location}",
    "🔍 AI Searcher imepata {product} bora {location} (bei TZS {price:,})",
    "⭐ {product} kutoka {location} imependekezwa na wateja wengi",
    "🚚 {seller} yuko tayari kusafirisha {product} kutoka {location}",
    "📣 Mahitaji makubwa ya {product} yameonekana {location}",
    "🏆 {product} bora wiki hii: {location} — TZS {price:,}/{unit}",
    "📲 Mteja kutoka {location} anaomba ushauri wa kilimo cha {product}",
]

# In-memory stores
activity_store = []
activity_id_counter = 1
products_store = []
product_id_counter = 1

# ============================================================
# AI PRODUCT SEARCHER (simulates search across regions)
# ============================================================

def ai_search_products(query: str = "", region: str = None, limit: int = 12):
    """AI Searcher: tafuta bidhaa katika mikoa yote ya TZ + Afrika Mashariki"""
    results = []
    q = (query or "").lower().strip()

    # Filter catalog by query
    matched = PRODUCTS_CATALOG
    if q:
        matched = [
            p for p in PRODUCTS_CATALOG
            if q in p["title"].lower() or q in p["category"].lower()
        ]
        if not matched:
            # Fuzzy: return related categories
            matched = random.sample(PRODUCTS_CATALOG, min(8, len(PRODUCTS_CATALOG)))

    locations = [region] if region else ALL_LOCATIONS

    for i in range(min(limit, max(6, len(matched) * 2))):
        prod = random.choice(matched)
        loc = random.choice(locations)
        seller = random.choice(SELLER_NAMES)
        base_prices = {
            "Nafaka": (45000, 120000),
            "Mafuta": (80000, 250000),
            "Legume": (60000, 150000),
            "Karanga": (7000, 25000),
            "Kahawa": (8000, 18000),
            "Chai": (5000, 12000),
            "Pamba": (1500000, 3500000),
            "Mizizi": (30000, 80000),
            "Matunda": (15000, 60000),
            "Mboga": (20000, 70000),
            "Maziwa": (1200, 2500),
            "Kuku": (6000, 15000),
            "Samaki": (8000, 20000),
            "Mbegu": (5000, 30000),
            "Mbolea": (50000, 120000),
            "Dawa": (15000, 80000),
            "Vifaa": (200000, 15000000),
        }
        low, high = base_prices.get(prod["category"], (10000, 100000))
        price = random.randint(low, high)
        qty = random.choice([5, 10, 15, 20, 25, 50, 100, 200, 500])

        results.append({
            "id": random.randint(1000, 99999),
            "title": f"{prod['title']} — {loc}",
            "jina": prod["title"],
            "description": f"{prod['title']} bora kutoka {loc}. Bei nafuu, ubora wa juu.",
            "location": loc,
            "chanzo": loc,
            "seller_name": seller,
            "seller_id": hashlib.md5(seller.encode()).hexdigest()[:10],
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
    """Generate one realistic live activity message"""
    global activity_id_counter

    template = random.choice(ACTIVITY_TEMPLATES)
    prod = random.choice(PRODUCTS_CATALOG)
    loc = random.choice(ALL_LOCATIONS)
    seller = random.choice(SELLER_NAMES)
    buyer = random.choice(SELLER_NAMES)
    qty = random.choice([5, 10, 20, 50, 100, 200])
    price = random.randint(15000, 180000)

    msg = template.format(
        seller=seller,
        buyer=buyer,
        product=prod["title"],
        location=loc,
        qty=qty,
        unit=prod["unit"],
        price=price,
    )

    item = {
        "id": activity_id_counter,
        "message": msg,
        "created": datetime.utcnow().isoformat() + "Z",
        "location": loc,
        "product": prod["title"],
        "type": "search" if "AI Searcher" in msg or "ametafuta" in msg else "listing",
    }
    activity_id_counter += 1
    return item


def seed_initial_data():
    """Seed products and initial activity"""
    global products_store, product_id_counter, activity_store

    # Seed ~40 products across regions
    for _ in range(40):
        results = ai_search_products(limit=1)
        if results:
            p = results[0]
            p["id"] = product_id_counter
            product_id_counter += 1
            products_store.append(p)

    # Seed initial activity
    for _ in range(15):
        activity_store.append(generate_activity_message())

    activity_store.sort(key=lambda x: x["id"], reverse=True)


def background_activity_generator():
    """Continuously generate live activity every 8–20 seconds"""
    while True:
        delay = random.uniform(8, 20)
        time.sleep(delay)
        item = generate_activity_message()
        activity_store.insert(0, item)
        # Keep only last 200 activities
        if len(activity_store) > 200:
            activity_store[:] = activity_store[:200]


# ============================================================
# API ROUTES
# ============================================================

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


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
    products = list(products_store)

    # Optional distance simulation
    if lat and lon:
        for p in products:
            p["distance_km"] = round(random.uniform(2.5, 180), 1)

    return jsonify({"success": True, "products": products[:30]})


@app.route("/api/ai-products")
def ai_products():
    """AI Searcher endpoint — searches all TZ + East Africa regions"""
    q = request.args.get("q", "").strip()
    region = request.args.get("region")
    results = ai_search_products(query=q, region=region, limit=16)

    # Also push activity about this search
    if q:
        item = {
            "id": activity_id_counter,
            "message": f"🔍 AI Searcher imetafuta '{q}' katika mikoa ya Tanzania na Afrika Mashariki — {len(results)} matokeo",
            "created": datetime.utcnow().isoformat() + "Z",
            "type": "ai_search",
        }
        global activity_id_counter
        activity_id_counter += 1
        activity_store.insert(0, item)

    return jsonify({"success": True, "products": results})


@app.route("/api/activity")
def get_activity():
    """Live Activity Feed — returns new items since last id"""
    since_id = request.args.get("since_id", 0, type=int)
    items = [a for a in activity_store if a["id"] > since_id]
    # Newest first, limit
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

    cat_list = []
    total = max(1, len(products_store))
    for label, data in sorted(categories.items(), key=lambda x: -x[1]["count"]):
        prices = data["prices"] or [0]
        top_loc = max(set(data["locations"]), key=data["locations"].count) if data["locations"] else "—"
        cat_list.append({
            "label": label,
            "count": data["count"],
            "avg_price": int(sum(prices) / len(prices)),
            "min_price": min(prices),
            "max_price": max(prices),
            "top_location": top_loc,
            "share": round(data["count"] / total * 100, 1),
        })

    top_locations = [
        {"location": loc, "count": cnt}
        for loc, cnt in sorted(locations.items(), key=lambda x: -x[1])[:10]
    ]

    recent = [
        {"title": p["title"], "location": p.get("location", "")}
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
        }
    })


@app.route("/api/payment/request", methods=["POST"])
def payment_request():
    data = request.get_json(force=True, silent=True) or {}
    method = data.get("njia", "")
    phone = data.get("simu", "")
    numbers = {
        "M-Pesa": "0755248789",
        "Halotel": "0625031460",
        "Airtel Money": "0691925100",
    }
    payment_number = numbers.get(method, "0755248789")
    order_id = "ORD-" + secrets.token_hex(4).upper()

    # Log activity
    item = {
        "id": activity_id_counter,
        "message": f"💳 Ada imelipwa ({method}) — Order {order_id}. Mteja anaunganishwa na mshauri.",
        "created": datetime.utcnow().isoformat() + "Z",
        "type": "payment",
    }
    global activity_id_counter
    activity_id_counter += 1
    activity_store.insert(0, item)

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
    return jsonify({
        "captcha_id": captcha_id,
        "question": f"{a} + {b} = ?",
    })


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
    elif any(w in msg for w in ["mahindi", "mchele", "ufuta", "kahawa", "maharage"]):
        reply = f"Nimeelewa unatafuta mazao. Nitatumia AI Searcher kutafuta katika mikoa yote ya Tanzania na Afrika Mashariki. Bofya 'Tafuta' au PATA MSAADA HAPA."
    elif any(w in msg for w in ["ushauri", "mshauri", "kilimo", "mbegu"]):
        reply = "Kwa ushauri wa kitaalamu, bofya 'Omba Ushauri wa Kitaalamu', lipa ada ya TZS 3,000 kisha utaunganishwa na mshauri kupitia WhatsApp."
    else:
        reply = "Karibu NjiaMauzo Afrika! 🌍 Naweza kukusaidia kutafuta bidhaa, mazao, na kuunganisha na washauri wa kilimo. Unauliza nini?"

    return jsonify({"reply": reply})


# ============================================================
# STARTUP
# ============================================================

seed_initial_data()

# Start background live activity generator
t = threading.Thread(target=background_activity_generator, daemon=True)
t.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 NjiaMauzo Afrika running on http://0.0.0.0:{port}")
    print("📡 Live Activity Feed is ACTIVE — AI Searcher covering Tanzania + East Africa")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
