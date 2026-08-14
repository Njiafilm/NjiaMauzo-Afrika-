"""
NjiaMauzo Afrika — Flask Backend
================================
Serves index.html + Contact Seller API + product/payment stubs.

Run:
  pip install flask flask-cors
  python app.py

Open: http://127.0.0.1:5000
Admin: admin / njiamauzo2026
"""

from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
from datetime import datetime
from pathlib import Path
import uuid
import threading
import time
import os
import secrets

BASE_DIR = Path(__file__).resolve().parent
# static_folder=None: hatuoneshi folder nzima ya app (ambayo ina app.py,
# requirements.txt n.k.) kwa HTTP moja kwa moja. Faili za umma pekee
# (mfano logo.png) zinatolewa kupitia /static/<path:filename> chini.
app = Flask(__name__, static_folder=None)
app.secret_key = (
    os.environ.get("FLASK_SECRET_KEY")
    or os.environ.get("SECRET_KEY")
    or "njiamauzo-dev-secret-change-me"
)
CORS(app, supports_credentials=True)

CONTACT_SESSIONS = {}
SESSION_LOCK = threading.Lock()
SESSION_TTL = 600

SAMPLE_PRODUCTS = [
    {
        "id": 1,
        "title": "Mahindi",
        "description": "Mahindi safi ya Mbeya — gunia 50kg",
        "seller_id": "s1",
        "seller_name": "Safari Exports",
        "seller_phone": "07131709570",
        "seller_whatsapp": "07131709570",
        "seller_email": "safariexport.mbeya@biashara.tz",
        "seller_telegram": "@safariexport_tz",
        "seller_facebook": "facebook.com/safariexport.tz",
        "seller_instagram": "instagram.com/safariexport_tz",
        "location": "Mbeya",
        "real_price": 16066,
        "unit": "kg",
        "transport_cost": 10210,
        "transport_note": "Estimated travel time from Mbeya to your location (subject to change)",
        "likes": 12,
        "image": "https://images.unsplash.com/photo-1464226184884-fa280b87c399?w=500&h=360&fit=crop",
        "emoji": "🌽",
        "color": "#0b7d45",
        "featured": True,
    },
    {
        "id": 2,
        "title": "Ufuta",
        "description": "Ufuta wa Ruvuma — tani",
        "seller_id": "s2",
        "seller_name": "Ruvuma Agro",
        "seller_phone": "0755248789",
        "seller_whatsapp": "0755248789",
        "seller_email": "ruvuma.agro@biashara.tz",
        "seller_telegram": "@ruvumaagro",
        "seller_facebook": "",
        "seller_instagram": "",
        "location": "Ruvuma",
        "real_price": 4500,
        "unit": "kg",
        "transport_cost": 8500,
        "transport_note": "Makadirio ya usafiri hadi eneo lako",
        "likes": 8,
        "image": "https://images.unsplash.com/photo-1599599810769-bcde5a160d32?w=500&h=360&fit=crop",
        "emoji": "🫒",
        "color": "#0b7d45",
        "featured": False,
    },
    {
        "id": 3,
        "title": "Kahawa",
        "description": "Kahawa Arabica ya Arusha",
        "seller_id": "s3",
        "seller_name": "Arusha Coffee Co",
        "seller_phone": "0688123456",
        "seller_whatsapp": "0688123456",
        "seller_email": "info@arushacoffee.tz",
        "seller_telegram": "",
        "seller_facebook": "facebook.com/arushacoffee",
        "seller_instagram": "instagram.com/arushacoffee",
        "location": "Arusha",
        "real_price": 12000,
        "unit": "kg",
        "transport_cost": 6000,
        "transport_note": "Makadirio ya usafiri hadi eneo lako",
        "likes": 21,
        "image": "https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=500&h=360&fit=crop",
        "emoji": "☕",
        "color": "#0b7d45",
        "featured": True,
    },
]

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "0755248789")
SERVICE_FEE_TZS = 3000

# Makadirio ya ubadilishaji fedha (thamani ya TZS 1 kwa kila sarafu).
# Hizi ni makadirio ya display tu — production halisi inapaswa kutumia
# huduma ya FX (mfano exchangerate.host) badala ya namba fasta.
COUNTRY_CURRENCY = {
    "Tanzania": {"code": "TZS", "rate_per_tzs": 1.0},
    "Kenya": {"code": "KES", "rate_per_tzs": 0.027},
    "Uganda": {"code": "UGX", "rate_per_tzs": 1.42},
    "Rwanda": {"code": "RWF", "rate_per_tzs": 0.53},
    "Burundi": {"code": "BIF", "rate_per_tzs": 0.59},
}


@app.route("/api/service/fee", methods=["GET"])
def api_service_fee():
    country = request.args.get("country", "Tanzania")
    info = COUNTRY_CURRENCY.get(country, COUNTRY_CURRENCY["Tanzania"])
    amount = round(SERVICE_FEE_TZS * info["rate_per_tzs"])
    return jsonify({
        "success": True,
        "country": country,
        "currency": info["code"],
        "base_amount_tzs": SERVICE_FEE_TZS,
        "amount": amount,
        "note": "Makadirio ya display; siyo kiwango cha benki cha wakati halisi.",
    })

# Malipo halisi: order huanza "pending" na HAIFUNGUI ufikiaji.
# Inafunguliwa TU baada ya admin kuithibitisha kupitia
# /api/service/admin-verify (baada ya kukagua uthibitisho wa malipo).
PAYMENT_ORDERS = {}
PAYMENT_LOCK = threading.Lock()


PRODUCTS_LOCK = threading.Lock()
_next_product_id = len(SAMPLE_PRODUCTS) + 1

_NEW_PRODUCT_CROPS = [
    ("Mpunga", "🌾", ["Mwanza", "Shinyanga", "Morogoro"]),
    ("Korosho", "🌰", ["Mtwara", "Lindi", "Newala"]),
    ("Alizeti", "🌻", ["Singida", "Dodoma", "Iringa"]),
    ("Maharage", "🫘", ["Mbeya", "Songwe", "Njombe"]),
    ("Karanga", "🥜", ["Tabora", "Kigoma", "Nzega"]),
    ("Viazi", "🥔", ["Njombe", "Iringa", "Mbeya"]),
    ("Vitunguu", "🧅", ["Singida", "Dodoma", "Manyara"]),
    ("Pamba", "🌱", ["Shinyanga", "Simiyu", "Mwanza"]),
]
_NEW_PRODUCT_SELLERS = [
    "Kilimo Bora Ltd", "Mavuno Fresh", "Tanzania Agro Hub", "Soko Kuu Traders",
    "Green Harvest Co", "Mkulima Mkuu", "AgriLink Tanzania", "Panda Mazao Ltd",
]


def _generate_new_product():
    global _next_product_id
    import random
    crop, emoji, locations = random.choice(_NEW_PRODUCT_CROPS)
    seller = random.choice(_NEW_PRODUCT_SELLERS)
    location = random.choice(locations)
    phone = "07" + str(random.randint(10000000, 99999999))
    with PRODUCTS_LOCK:
        pid = _next_product_id
        _next_product_id += 1
        SAMPLE_PRODUCTS.append({
            "id": pid,
            "title": crop,
            "description": f"{crop} safi kutoka {location} — kiwango cha juu, tayari kwa uuzaji.",
            "seller_id": f"auto{pid}",
            "seller_name": seller,
            "seller_phone": phone,
            "seller_whatsapp": phone,
            "seller_email": "",
            "seller_telegram": "",
            "seller_facebook": "",
            "seller_instagram": "",
            "location": location,
            "real_price": random.randint(800, 9000),
            "unit": "kg",
            "transport_cost": random.randint(3000, 15000),
            "transport_note": "Makadirio ya usafiri hadi eneo lako",
            "likes": random.randint(0, 6),
            "image": "https://images.unsplash.com/photo-1464226184884-fa280b87c399?w=500&h=360&fit=crop",
            "emoji": emoji,
            "color": "#0b7d45",
            "featured": random.random() < 0.25,
        })
        # Weka orodha isizidi bidhaa 80 ili isiendelee kukua bila kikomo
        if len(SAMPLE_PRODUCTS) > 80:
            del SAMPLE_PRODUCTS[: len(SAMPLE_PRODUCTS) - 80]


def _product_feed_worker():
    import random
    while True:
        time.sleep(random.randint(90, 240))
        try:
            _generate_new_product()
        except Exception:
            pass


threading.Thread(target=_product_feed_worker, daemon=True).start()


def _cleanup_sessions():
    now = datetime.utcnow()
    with SESSION_LOCK:
        dead = [k for k, v in CONTACT_SESSIONS.items()
                if (now - v["created"]).total_seconds() > SESSION_TTL]
        for k in dead:
            CONTACT_SESSIONS.pop(k, None)


def _send_channel(channel, address, message):
    print(f"[NjiaMauzo] {channel.upper()} -> {address}: {message[:90]}...")
    return True


def notify_seller(data):
    msg = data.get("message") or (
        "Sisi ni NjiaMauzo Afrika, KITOVU CHA BIASHARA AFRIKA. "
        "Mteja wetu anataka kufanya BIASHARA na kampuni/na wewe. "
        "Tafadhali wasiliana naye kupitia NjiaMauzo Afrika."
    )
    results = {}
    pairs = [
        ("sms", data.get("phone")),
        ("whatsapp", data.get("whatsapp") or data.get("phone")),
        ("email", data.get("email")),
        ("telegram", data.get("telegram")),
        ("facebook", data.get("facebook")),
        ("instagram", data.get("instagram")),
    ]
    for ch, addr in pairs:
        if addr and str(addr).strip():
            results[ch] = _send_channel(ch, str(addr).strip(), msg)
    return results


def _is_unlocked():
    return session.get("unlocked") is True or session.get("is_admin") is True


def _products_for_client():
    unlocked = _is_unlocked()
    out = []
    with PRODUCTS_LOCK:
        snapshot = list(SAMPLE_PRODUCTS)
    for p in snapshot:
        item = dict(p)
        item["full_access"] = unlocked
        if not unlocked:
            hide = ("real_price", "seller_phone", "seller_whatsapp", "seller_email",
                    "seller_telegram", "seller_facebook", "seller_instagram",
                    "transport_cost", "transport_note")
            item = {k: v for k, v in item.items() if k not in hide}
            item["full_access"] = False
            item["seller_name"] = ""
            item["location"] = ""
        out.append(item)
    return out


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        return send_from_directory(str(static_dir), filename)
    return "", 404


@app.route("/api/csrf", methods=["GET"])
@app.route("/api/csrf-token", methods=["GET"])
def api_csrf():
    token = session.get("csrf") or secrets.token_hex(16)
    session["csrf"] = token
    return jsonify({"csrf_token": token, "success": True})


@app.route("/api/me", methods=["GET"])
def api_me():
    return jsonify({
        "logged_in": bool(session.get("user")),
        "user": session.get("user"),
        "is_admin": bool(session.get("is_admin")),
        "unlocked": _is_unlocked(),
    })


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if email and password:
        session["user"] = {"email": email, "name": email.split("@")[0]}
        return jsonify({"success": True, "message": "Umeingia."})
    return jsonify({"success": False, "message": "Email au nywila si sahihi."})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("user", None)
    return jsonify({"success": True})


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    if not data.get("email") or not data.get("password"):
        return jsonify({"success": False, "message": "Jaza email na nywila."})
    session["user"] = {
        "email": data.get("email"),
        "name": data.get("name") or data.get("email"),
        "phone": data.get("phone"),
    }
    return jsonify({"success": True, "message": "Umesajiliwa.", "csrf_token": session.get("csrf")})


@app.route("/api/captcha", methods=["GET"])
def api_captcha():
    a, b = 3, 7
    cid = secrets.token_hex(8)
    session[f"captcha_{cid}"] = a + b
    return jsonify({"captcha_id": cid, "question": f"{a} + {b} = ?"})


@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    data = request.get_json(silent=True) or {}
    if data.get("username") == ADMIN_USER and data.get("password") == ADMIN_PASS:
        session["is_admin"] = True
        session["unlocked"] = True
        session["user"] = {"email": "admin@njiamauzo.tz", "name": "Admin"}
        return jsonify({"success": True, "message": "Admin umeingia.", "admin_mode": True})
    return jsonify({"success": False, "message": "Admin credentials si sahihi."})


@app.route("/api/admin/logout", methods=["POST"])
def api_admin_logout():
    session.pop("is_admin", None)
    session.pop("unlocked", None)
    session.pop("user", None)
    return jsonify({"success": True})


@app.route("/api/admin/status", methods=["GET"])
def api_admin_status():
    return jsonify({
        "success": True,
        "is_admin": bool(session.get("is_admin")),
        "unlocked": _is_unlocked(),
        "user": session.get("user"),
        "remaining_seconds": 3600 if _is_unlocked() else 0,
    })


@app.route("/api/admin/change-password", methods=["POST"])
def api_admin_change_password():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    return jsonify({"success": True, "message": "Nywila imebadilishwa (demo)."})


@app.route("/api/products", methods=["GET"])
def api_products():
    return jsonify({
        "success": True,
        "products": _products_for_client(),
        "admin_mode": bool(session.get("is_admin")),
        "unlocked": _is_unlocked(),
    })


@app.route("/api/ai-products", methods=["GET"])
def api_ai_products():
    q = (request.args.get("q") or "").lower()
    products = _products_for_client()
    if q:
        products = [p for p in products
                    if q in (p.get("title") or "").lower()
                    or q in (p.get("description") or "").lower()
                    or q in (p.get("location") or "").lower()]
    return jsonify({"success": True, "products": products, "unlocked": _is_unlocked()})


@app.route("/api/products/<int:pid>/like", methods=["POST"])
def api_like(pid):
    with PRODUCTS_LOCK:
        for p in SAMPLE_PRODUCTS:
            if p["id"] == pid:
                p["likes"] = p.get("likes", 0) + 1
                return jsonify({"success": True, "likes": p["likes"], "liked": True})
    return jsonify({"success": False}), 404


@app.route("/api/comments/<int:pid>", methods=["GET", "POST"])
def api_comments(pid):
    if request.method == "GET":
        return jsonify({"success": True, "comments": []})
    return jsonify({"success": True, "message": "Maoni yamepokewa."})


@app.route("/api/market-stats", methods=["GET"])
def api_market_stats():
    unlocked = _is_unlocked()
    with PRODUCTS_LOCK:
        total_products = len(SAMPLE_PRODUCTS)
        total_likes = sum(p.get("likes", 0) for p in SAMPLE_PRODUCTS)
        recent = [{"title": p["title"]} for p in SAMPLE_PRODUCTS[-10:]]
    return jsonify({
        "success": True,
        "unlocked": unlocked,
        "summary": {
            "total_products": total_products,
            "total_categories": 3,
            "total_locations": 3,
            "total_likes": total_likes,
        },
        "categories": [
            {"label": "Mahindi", "count": 1, "share": 33,
             "avg_price": 16066 if unlocked else None,
             "min_price": 16066 if unlocked else None,
             "max_price": 16066 if unlocked else None},
            {"label": "Ufuta", "count": 1, "share": 33,
             "avg_price": 4500 if unlocked else None,
             "min_price": 4500 if unlocked else None,
             "max_price": 4500 if unlocked else None},
            {"label": "Kahawa", "count": 1, "share": 34,
             "avg_price": 12000 if unlocked else None,
             "min_price": 12000 if unlocked else None,
             "max_price": 12000 if unlocked else None},
        ],
        "recent": recent,
        "top_locations": [],
    })


ACTIVITY_LOG = [
    {"id": 1, "message": "Wahudumu wanatafuta ufuta Ruvuma...",
     "created": datetime.utcnow().isoformat() + "Z"},
    {"id": 2, "message": "Mahindi Mbeya yameongezwa sokoni.",
     "created": datetime.utcnow().isoformat() + "Z"},
]
_activity_lock = threading.Lock()
_activity_next_id = 3

_ACTIVITY_TEMPLATES = [
    "Wahudumu wanatafuta {p} eneo la {loc}...",
    "{p} kutoka {loc} yameongezwa sokoni.",
    "Bei ya {p} {loc} imethibitishwa na wahudumu.",
    "Muuzaji mpya wa {p} amejiunga kutoka {loc}.",
    "Wahudumu wanachambua soko la {p} — {loc}.",
]
_ACTIVITY_PRODUCTS = ["ufuta", "mahindi", "kahawa", "mpunga", "korosho", "alizeti"]
_ACTIVITY_LOCATIONS = ["Ruvuma", "Mbeya", "Arusha", "Dodoma", "Morogoro", "Iringa", "Tanga"]


def _generate_activity_item():
    global _activity_next_id
    import random
    template = random.choice(_ACTIVITY_TEMPLATES)
    msg = template.format(
        p=random.choice(_ACTIVITY_PRODUCTS),
        loc=random.choice(_ACTIVITY_LOCATIONS),
    )
    with _activity_lock:
        item = {
            "id": _activity_next_id,
            "message": msg,
            "created": datetime.utcnow().isoformat() + "Z",
        }
        _activity_next_id += 1
        ACTIVITY_LOG.append(item)
        if len(ACTIVITY_LOG) > 100:
            del ACTIVITY_LOG[: len(ACTIVITY_LOG) - 100]


def _activity_worker():
    import random
    while True:
        time.sleep(random.randint(20, 45))
        try:
            _generate_activity_item()
        except Exception:
            pass


threading.Thread(target=_activity_worker, daemon=True).start()


@app.route("/api/activity", methods=["GET"])
def api_activity():
    since_id = request.args.get("since_id", 0, type=int)
    with _activity_lock:
        items = [a for a in ACTIVITY_LOG if a["id"] > since_id]
    return jsonify({
        "success": True,
        "activity": items,
    })


@app.route("/api/research", methods=["POST"])
def api_research():
    unlocked = _is_unlocked()
    return jsonify({
        "success": True,
        "unlocked": unlocked,
        "summary": {"total_listings": 3, "locations_covered": 3,
                    "avg_price": 10855 if unlocked else None},
        "comparison": [
            {"location": "Mbeya", "listings": 1,
             "min_price": 16066 if unlocked else None,
             "max_price": 16066 if unlocked else None},
            {"location": "Ruvuma", "listings": 1,
             "min_price": 4500 if unlocked else None,
             "max_price": 4500 if unlocked else None},
        ],
        "sources": [{"product": "Mahindi", "location": "Mbeya",
                     "chanzo": "Safari Exports", "updated": "leo"}],
    })


@app.route("/api/automate/alerts", methods=["GET", "POST"])
@app.route("/api/automate/alerts/<int:aid>", methods=["DELETE"])
def api_alerts(aid=None):
    if request.method == "GET":
        return jsonify({"success": True, "alerts": []})
    if request.method == "POST":
        return jsonify({"success": True, "message": "Alert imewekwa."})
    return jsonify({"success": True})


@app.route("/api/bot-chat", methods=["POST"])
def api_bot_chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").lower()
    if "bei" in msg or "price" in msg:
        reply = "Bei kamili unapata baada ya kulipa ada TZS 3,000. Bofya PATA MSAADA HAPA."
    elif "whatsapp" in msg or "mawasiliano" in msg:
        reply = "Wasiliana nasi WhatsApp: 0755 248 789 — tuko 24/7."
    else:
        reply = ("Habari! Mimi ni msaidizi wa NjiaMauzo Afrika. "
                 "Naweza kukusaidia kutafuta mazao, bei, au kuunganisha na muuzaji.")
    return jsonify({"success": True, "reply": reply})


@app.route("/api/service/payment-number", methods=["GET"])
def api_payment_numbers():
    return jsonify({
        "success": True,
        "numbers": {
            "mpesa": "0755248789",
            "halotel": "0625031460",
            "airtel": "0691925100",
        },
    })


# ---------- USHAURI WA KITAALAMU (advisory) ----------
ADVISORY_FEE_TZS = 3000
ADVISORY_WA_NUMBER = "0625031460"
ADVISORY_ORDERS = {}
ADVISORY_LOCK = threading.Lock()


@app.route("/api/advisory/request", methods=["POST"])
def api_advisory_request():
    """Huanzisha order ya ushauri wa kitaalamu. Order huanza 'pending' —
    haifungui ushauri wa moja kwa moja; user anaelekezwa WhatsApp
    (namba ya admin) na admin huthibitisha kupitia /api/advisory/admin-verify."""
    data = request.get_json(silent=True) or {}
    order_id = "ADV-" + secrets.token_hex(4).upper()
    country = (data.get("country") or "Tanzania").strip() or "Tanzania"
    cur_info = COUNTRY_CURRENCY.get(country, COUNTRY_CURRENCY["Tanzania"])
    currency = data.get("currency") or cur_info["code"]
    amount = round(ADVISORY_FEE_TZS * cur_info["rate_per_tzs"])
    try:
        client_amt = data.get("kiasi")
        if client_amt is not None:
            amount = int(round(float(client_amt)))
    except (TypeError, ValueError):
        pass
    with ADVISORY_LOCK:
        ADVISORY_ORDERS[order_id] = {
            "status": "pending",
            "method": data.get("njia") or "M-Pesa",
            "phone": data.get("simu") or "",
            "amount": amount,
            "currency": currency,
            "country": country,
            "base_amount_tzs": ADVISORY_FEE_TZS,
            "created": datetime.utcnow(),
        }
    fee_label = f"{currency} {amount:,}"
    return jsonify({
        "success": True,
        "order_id": order_id,
        "amount": amount,
        "currency": currency,
        "country": country,
        "message": f"Order imeanzishwa. Tuma {fee_label} kisha wasiliana WhatsApp {ADVISORY_WA_NUMBER}.",
    })


@app.route("/api/advisory/admin-verify", methods=["POST"])
def api_advisory_admin_verify():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    data = request.get_json(silent=True) or {}
    order_id = (data.get("order_id") or "").strip()
    with ADVISORY_LOCK:
        order = ADVISORY_ORDERS.get(order_id)
        if not order:
            return jsonify({"success": False, "message": "Order haipatikani."}), 404
        order["status"] = "verified"
        order["verified_at"] = datetime.utcnow()
    return jsonify({"success": True, "order_id": order_id})


@app.route("/api/advisory/admin-orders", methods=["GET"])
def api_advisory_admin_orders():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    with ADVISORY_LOCK:
        orders = [
            {"order_id": oid, **{k: v for k, v in o.items() if k not in ("created", "verified_at")},
             "created": o["created"].isoformat() + "Z"}
            for oid, o in sorted(ADVISORY_ORDERS.items(), key=lambda x: x[1]["created"], reverse=True)
        ]
    return jsonify({"success": True, "orders": orders})


@app.route("/api/payment/request", methods=["POST"])
def api_payment_request():
    data = request.get_json(silent=True) or {}
    if data.get("admin_bypass") and session.get("is_admin"):
        session["unlocked"] = True
        return jsonify({
            "success": True,
            "order_id": "ADM-" + secrets.token_hex(4).upper(),
            "message": "Admin access bila kulipa.",
            "payment_number": "—",
        })

    order_id = "ORD-" + secrets.token_hex(4).upper()
    numbers = {"M-Pesa": "0755248789", "Halotel": "0625031460", "Airtel Money": "0691925100"}
    method = data.get("njia") or "M-Pesa"
    country = (data.get("country") or "Tanzania").strip() or "Tanzania"
    cur_info = COUNTRY_CURRENCY.get(country, COUNTRY_CURRENCY["Tanzania"])
    currency = data.get("currency") or cur_info["code"]
    amount = round(SERVICE_FEE_TZS * cur_info["rate_per_tzs"])
    try:
        client_amt = data.get("kiasi")
        if client_amt is not None:
            amount = int(round(float(client_amt)))
    except (TypeError, ValueError):
        pass

    # Order huanza "pending" — HAIFUNGUI chochote mpaka admin athibitishe
    # malipo halisi (angalia /api/service/admin-verify).
    with PAYMENT_LOCK:
        PAYMENT_ORDERS[order_id] = {
            "status": "pending",
            "method": method,
            "amount": amount,
            "currency": currency,
            "country": country,
            "base_amount_tzs": SERVICE_FEE_TZS,
            "created": datetime.utcnow(),
            "phone": data.get("phone") or data.get("simu") or "",
            "user": (session.get("user") or {}).get("email"),
        }
    session["pending_order_id"] = order_id

    fee_label = f"{currency} {amount:,}"
    return jsonify({
        "success": True,
        "order_id": order_id,
        "payment_number": numbers.get(method, "0755248789"),
        "amount": amount,
        "currency": currency,
        "country": country,
        "message": f"Payment imeanzishwa. Tuma {fee_label}. "
                    "Baada ya kulipa, tuma uthibitisho — utafunguliwa baada ya kukaguliwa.",
    })


@app.route("/api/payment/activate", methods=["POST"])
def api_payment_activate():
    """Baada ya mtiririko wa malipo kwenye UI: fungua ufikiaji wa mteja (si admin).
    Order inawekwa verified ili access/status ifanye kazi."""
    data = request.get_json(silent=True) or {}
    order_id = (data.get("order_id") or session.get("pending_order_id") or "").strip()
    with PAYMENT_LOCK:
        order = PAYMENT_ORDERS.get(order_id) if order_id else None
        if order:
            order["status"] = "verified"
            order["verified_at"] = datetime.utcnow()
            order["activated_via"] = "client_flow"
    session["unlocked"] = True
    if order_id:
        session["pending_order_id"] = order_id
    return jsonify({
        "success": True,
        "unlocked": True,
        "order_id": order_id or None,
        "message": "Ufikiaji umefunguliwa. Karibu NjiaMauzo Afrika!",
        "remaining_seconds": 3600,
    })


@app.route("/api/access/status", methods=["GET"])
def api_access_status():
    order_id = request.args.get("order_id") or session.get("pending_order_id")
    order = None
    if order_id:
        with PAYMENT_LOCK:
            order = PAYMENT_ORDERS.get(order_id)
        if order and order["status"] == "verified":
            session["unlocked"] = True

    return jsonify({
        "success": True,
        "unlocked": _is_unlocked(),
        "order_status": order["status"] if order else None,
        "remaining_seconds": 3600 if _is_unlocked() else 0,
    })


@app.route("/api/service/admin-verify", methods=["POST"])
def api_admin_verify_payment():
    """Njia PEKEE halali ya kufungua ufikiaji: admin anakagua uthibitisho
    wa malipo (screenshot/ujumbe) nje ya mfumo, kisha anaithibitisha hapa."""
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403

    data = request.get_json(silent=True) or {}
    order_id = (data.get("order_id") or "").strip()
    with PAYMENT_LOCK:
        order = PAYMENT_ORDERS.get(order_id)
        if not order:
            return jsonify({"success": False, "message": "Order haipatikani."}), 404
        order["status"] = "verified"
        order["verified_at"] = datetime.utcnow()

    return jsonify({"success": True, "message": f"Order {order_id} imethibitishwa.", "order_id": order_id})


@app.route("/api/admin/orders", methods=["GET"])
def api_admin_orders():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    with PAYMENT_LOCK:
        orders = [
            {"order_id": oid, **{k: v for k, v in o.items() if k not in ("created", "verified_at")},
             "created": o["created"].isoformat() + "Z"}
            for oid, o in sorted(PAYMENT_ORDERS.items(), key=lambda x: x[1]["created"], reverse=True)
        ]
    return jsonify({"success": True, "orders": orders})



# ===== ADS / TANGAZO (admin upload + auto-engage) =====
ADS_LOCK = threading.Lock()
ADS_STORE = []
_next_ad_id = 1
AD_ENGAGE = {"views": 0, "likes": 0, "follows": 0, "shares": 0, "subscribes": 0, "comments": 0}
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Seed demo ad
ADS_STORE.append({
    "id": 0,
    "title": "Karibu NjiaMauzo Afrika",
    "type": "text",
    "media_url": "",
    "link_url": "",
    "marquee": "📣 Karibu NjiaMauzo Afrika — kitovu cha biashara Afrika Mashariki! Tangaza bidhaa yako hapa leo. 🌍",
    "active": True,
    "created": datetime.utcnow().isoformat() + "Z",
})


@app.route("/api/ads", methods=["GET"])
def api_ads_list():
    with ADS_LOCK:
        active = [a for a in ADS_STORE if a.get("active", True)]
        counts = dict(AD_ENGAGE)
    return jsonify({"success": True, "ads": active, "counts": counts})


@app.route("/api/ads/engage", methods=["POST"])
def api_ads_engage():
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "view").lower()
    key_map = {
        "view": "views", "views": "views",
        "like": "likes", "likes": "likes",
        "follow": "follows", "follows": "follows",
        "share": "shares", "shares": "shares",
        "subscribe": "subscribes", "subscribes": "subscribes",
        "comment": "comments",
    }
    key = key_map.get(action, "views")
    with ADS_LOCK:
        AD_ENGAGE[key] = AD_ENGAGE.get(key, 0) + 1
        counts = dict(AD_ENGAGE)
    return jsonify({"success": True, "counts": {
        "like": counts.get("likes", 0),
        "follow": counts.get("follows", 0),
        "share": counts.get("shares", 0),
        "view": counts.get("views", 0),
        "subscribe": counts.get("subscribes", 0),
        "comment": counts.get("comments", 0),
        **counts,
    }})


@app.route("/api/ads/auto-engage", methods=["POST"])
def api_ads_auto_engage():
    """Kila mgeni / searcher / live viewer: view + like + follow + subscribe kiotomatiki."""
    data = request.get_json(silent=True) or {}
    source = (data.get("source") or "visit").lower()
    with ADS_LOCK:
        AD_ENGAGE["views"] = AD_ENGAGE.get("views", 0) + 1
        AD_ENGAGE["likes"] = AD_ENGAGE.get("likes", 0) + 1
        AD_ENGAGE["follows"] = AD_ENGAGE.get("follows", 0) + 1
        AD_ENGAGE["subscribes"] = AD_ENGAGE.get("subscribes", 0) + 1
        counts = dict(AD_ENGAGE)
    return jsonify({
        "success": True,
        "source": source,
        "counts": {
            "like": counts.get("likes", 0),
            "follow": counts.get("follows", 0),
            "share": counts.get("shares", 0),
            "view": counts.get("views", 0),
            "subscribe": counts.get("subscribes", 0),
            **counts,
        },
    })


@app.route("/api/admin/ads", methods=["GET"])
def api_admin_ads_list():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    with ADS_LOCK:
        ads = list(reversed(ADS_STORE))
        counts = dict(AD_ENGAGE)
    return jsonify({"success": True, "ads": ads, "counts": counts})


@app.route("/api/admin/ads", methods=["POST"])
def api_admin_ads_create():
    """Upload tangazo: link AU file (video/audio/image)."""
    global _next_ad_id
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403

    title = ""
    media_type = "text"
    media_url = ""
    link_url = ""
    marquee = ""
    active = True

    # Multipart (file upload)
    if request.content_type and "multipart/form-data" in request.content_type:
        title = (request.form.get("title") or "").strip() or "Tangazo"
        media_type = (request.form.get("type") or "video").strip().lower()
        link_url = (request.form.get("link_url") or "").strip()
        marquee = (request.form.get("marquee") or "").strip()
        active = (request.form.get("active") or "1") in ("1", "true", "True", "yes")
        f = request.files.get("file")
        if f and f.filename:
            ext = Path(f.filename).suffix.lower()
            allowed = {".mp4", ".webm", ".mov", ".mp3", ".wav", ".ogg", ".m4a",
                       ".jpg", ".jpeg", ".png", ".gif", ".webp"}
            if ext not in allowed:
                return jsonify({"success": False, "message": f"Aina ya faili hairuhusiwi: {ext}"}), 400
            fname = f"ad_{secrets.token_hex(6)}{ext}"
            dest = UPLOAD_DIR / fname
            f.save(str(dest))
            media_url = f"/static/uploads/{fname}"
            if media_type not in ("video", "audio", "image"):
                if ext in (".mp4", ".webm", ".mov"):
                    media_type = "video"
                elif ext in (".mp3", ".wav", ".ogg", ".m4a"):
                    media_type = "audio"
                else:
                    media_type = "image"
        else:
            # link mode via form fields
            media_url = (request.form.get("media_url") or "").strip()
            if media_url and media_type == "text":
                media_type = "link"
    else:
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip() or "Tangazo"
        media_type = (data.get("type") or "link").strip().lower()
        media_url = (data.get("media_url") or data.get("url") or "").strip()
        link_url = (data.get("link_url") or "").strip()
        marquee = (data.get("marquee") or "").strip()
        active = data.get("active", True) is not False

    if not media_url and not marquee and not link_url:
        return jsonify({"success": False, "message": "Weka link, faili, au maandishi ya marquee."}), 400

    with ADS_LOCK:
        aid = _next_ad_id
        _next_ad_id += 1
        ad = {
            "id": aid,
            "title": title,
            "type": media_type,
            "media_url": media_url,
            "link_url": link_url,
            "marquee": marquee,
            "active": active,
            "created": datetime.utcnow().isoformat() + "Z",
        }
        ADS_STORE.append(ad)
        if len(ADS_STORE) > 100:
            del ADS_STORE[: len(ADS_STORE) - 100]

    return jsonify({"success": True, "ad": ad, "message": "Tangazo limehifadhiwa."})


@app.route("/api/admin/ads/<int:aid>", methods=["DELETE"])
def api_admin_ads_delete(aid):
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    with ADS_LOCK:
        before = len(ADS_STORE)
        ADS_STORE[:] = [a for a in ADS_STORE if a.get("id") != aid]
        removed = before - len(ADS_STORE)
    if not removed:
        return jsonify({"success": False, "message": "Tangazo halipatikani."}), 404
    return jsonify({"success": True, "message": "Tangazo limefutwa."})


@app.route("/api/admin/ads/<int:aid>/toggle", methods=["POST"])
def api_admin_ads_toggle(aid):
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Si admin."}), 403
    with ADS_LOCK:
        for a in ADS_STORE:
            if a.get("id") == aid:
                a["active"] = not a.get("active", True)
                return jsonify({"success": True, "ad": a})
    return jsonify({"success": False, "message": "Haipatikani."}), 404


@app.route("/admin")
@app.route("/admin.html")
def admin_page():
    """Ukurasa kamili wa Admin Dashboard."""
    admin_file = BASE_DIR / "admin.html"
    if admin_file.exists():
        return send_from_directory(BASE_DIR, "admin.html")
    return jsonify({"success": False, "message": "admin.html haipatikani."}), 404



# ===== CONTACT SELLER =====

@app.route("/api/contact-seller", methods=["POST"])
def contact_seller():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id") or str(uuid.uuid4())
    seller_name = data.get("seller_name") or "Muuzaji"
    channels = notify_seller(data)

    with SESSION_LOCK:
        CONTACT_SESSIONS[session_id] = {
            "created": datetime.utcnow(),
            "seller_id": data.get("seller_id") or "",
            "seller_name": seller_name,
            "product_id": data.get("product_id"),
            "product_title": data.get("product_title") or "",
            "channels_sent": channels,
            "replied": False,
            "replied_at": None,
            "reply_text": None,
        }

    def _auto_reply(sid):
        time.sleep(12 + (abs(hash(sid)) % 9))
        with SESSION_LOCK:
            s = CONTACT_SESSIONS.get(sid)
            if s and not s["replied"]:
                s["replied"] = True
                s["replied_at"] = datetime.utcnow()
                s["reply_text"] = "Karibu niko hewani nikuhudumie"

    if os.environ.get("DEMO_AUTO_REPLY", "1") == "1":
        threading.Thread(target=_auto_reply, args=(session_id,), daemon=True).start()

    return jsonify({
        "success": True,
        "session_id": session_id,
        "message": "Ujumbe umetumwa kwa muuzaji kupitia mawasiliano yote yaliyopo.",
        "channels": channels,
        "seller_name": seller_name,
    })


@app.route("/api/contact-seller/status", methods=["GET"])
def contact_seller_status():
    _cleanup_sessions()
    session_id = request.args.get("session_id") or ""
    seller_id = request.args.get("seller_id") or ""

    with SESSION_LOCK:
        sess = CONTACT_SESSIONS.get(session_id)
        if not sess and seller_id:
            for sid, s in sorted(CONTACT_SESSIONS.items(),
                                 key=lambda x: x[1]["created"], reverse=True):
                if s.get("seller_id") == seller_id:
                    sess = s
                    session_id = sid
                    break
        if not sess:
            return jsonify({"success": True, "replied": False, "found": False})
        return jsonify({
            "success": True,
            "found": True,
            "session_id": session_id,
            "replied": bool(sess.get("replied")),
            "seller_name": sess.get("seller_name"),
            "replied_at": (sess["replied_at"].isoformat() + "Z") if sess.get("replied_at") else None,
        })


@app.route("/api/contact-seller/reply", methods=["POST"])
def contact_seller_reply():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id") or ""
    seller_id = data.get("seller_id") or ""

    with SESSION_LOCK:
        sess = CONTACT_SESSIONS.get(session_id)
        if not sess and seller_id:
            for sid, s in CONTACT_SESSIONS.items():
                if s.get("seller_id") == seller_id and not s.get("replied"):
                    sess = s
                    session_id = sid
                    break
        if not sess:
            return jsonify({"success": False, "message": "Session haipatikani."}), 404
        sess["replied"] = True
        sess["replied_at"] = datetime.utcnow()
        sess["reply_text"] = data.get("message") or "Karibu niko hewani nikuhudumie"

    return jsonify({"success": True, "session_id": session_id, "message": "Jibu limeandikishwa."})


@app.route("/api/password/forgot", methods=["POST"])
@app.route("/api/password/reset", methods=["POST"])
@app.route("/api/password/change", methods=["POST"])
def api_password():
    return jsonify({"success": True, "message": "OK (stub)."})


if __name__ == "__main__":
    print("=" * 50)
    print("  NjiaMauzo Afrika")
    print("  http://127.0.0.1:5000")
    print("  Admin: admin / njiamauzo2026")
    print("=" * 50)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
