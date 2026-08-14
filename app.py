"""
NjiaMauzo Afrika — Flask Backend
================================
Serves index.html + Contact Seller API + product/payment stubs.Run:
  pip install flask flask-cors
  python app.py

Open: http://127.0.0.1:5000
Admin: admin / njiamauzo2026
"""flask import Flask, request, jsonify, send_from_directory, session
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
    },
]

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "njiamauzo2026")
SERVICE_FEE_TZS = 3000

# Malipo halisi: order huanza "pending" na HAIFUNGUI ufikiaji.
# Inafunguliwa TU baada ya admin kuithibitisha kupitia
# /api/service/admin-verify (baada ya kukagua uthibitisho wa malipo).
PAYMENT_ORDERS = {}
PAYMENT_LOCK = threading.Lock()


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
    for p in SAMPLE_PRODUCTS:
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
    return jsonify({
        "success": True,
        "unlocked": unlocked,
        "summary": {
            "total_products": len(SAMPLE_PRODUCTS),
            "total_categories": 3,
            "total_locations": 3,
            "total_likes": sum(p.get("likes", 0) for p in SAMPLE_PRODUCTS),
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
        "recent": [{"title": p["title"]} for p in SAMPLE_PRODUCTS],
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

    # Order huanza "pending" — HAIFUNGUI chochote mpaka admin athibitishe
    # malipo halisi (angalia /api/service/admin-verify).
    with PAYMENT_LOCK:
        PAYMENT_ORDERS[order_id] = {
            "status": "pending",
            "method": method,
            "amount": SERVICE_FEE_TZS,
            "created": datetime.utcnow(),
            "phone": data.get("phone") or "",
            "user": (session.get("user") or {}).get("email"),
        }
    session["pending_order_id"] = order_id

    return jsonify({
        "success": True,
        "order_id": order_id,
        "payment_number": numbers.get(method, "0755248789"),
        "message": f"Payment imeanzishwa. Tuma TZS {SERVICE_FEE_TZS:,}. "
                    "Baada ya kulipa, tuma uthibitisho — utafunguliwa baada ya kukaguliwa.",
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
            "product_id": t(os.environ.get("PORT", 5000)), debug=True)
