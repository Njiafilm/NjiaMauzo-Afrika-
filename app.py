"""
NjiaMauzo Afrika — Flask Backend (Complete)

Run:
pip install flask flask-cors
python app.py

Open:
http://127.0.0.1:5000

Admin:
username: admin
password: njiamauzo2026
"""

from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
from datetime import datetime
from pathlib import Path
import os
import secrets
import threading
import time
import random
import uuid


BASE_DIR = Path(__file__).resolve().parent

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

PAYMENT_ORDERS = {}
PAYMENT_LOCK = threading.Lock()

COMMENTS = {
    1: [],
    2: [],
    3: [],
}

ALERTS = []
ALERT_LOCK = threading.Lock()
ALERT_NEXT_ID = 1

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
SERVICE_FEE_TZS = int(os.environ.get("SERVICE_FEE_TZS", "1000"))

PAYMENT_NUMBERS = {
    "M-Pesa": "0755248789",
    "Halotel": "0625031460",
    "Airtel Money": "0691925100",
}

ACTIVITY_LOG = [
    {
        "id": 1,
        "message": "Wahudumu wanatafuta ufuta Ruvuma...",
        "created": datetime.utcnow().isoformat() + "Z",
    },
    {
        "id": 2,
        "message": "Mahindi Mbeya yameongezwa sokoni.",
        "created": datetime.utcnow().isoformat() + "Z",
    },
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

_ACTIVITY_PRODUCTS = [
    "ufuta",
    "mahindi",
    "kahawa",
    "mpunga",
    "korosho",
    "alizeti",
]

_ACTIVITY_LOCATIONS = [
    "Ruvuma",
    "Mbeya",
    "Arusha",
    "Dodoma",
    "Morogoro",
    "Iringa",
    "Tanga",
]


def now_iso():
    return datetime.utcnow().isoformat() + "Z"


def add_activity(message):
    global _activity_next_id

    with _activity_lock:
        item = {
            "id": _activity_next_id,
            "message": message,
            "created": now_iso(),
        }
        _activity_next_id += 1
        ACTIVITY_LOG.append(item)

        if len(ACTIVITY_LOG) > 100:
            del ACTIVITY_LOG[: len(ACTIVITY_LOG) - 100]

    return item


def _generate_activity_item():
    template = random.choice(_ACTIVITY_TEMPLATES)
    message = template.format(
        p=random.choice(_ACTIVITY_PRODUCTS),
        loc=random.choice(_ACTIVITY_LOCATIONS),
    )
    add_activity(message)


def _activity_worker():
    while True:
        time.sleep(random.randint(15, 35))
        try:
            _generate_activity_item()
        except Exception:
            pass


def _cleanup_sessions():
    now = datetime.utcnow()

    with SESSION_LOCK:
        dead = [
            k
            for k, v in CONTACT_SESSIONS.items()
            if (now - v["created"]).total_seconds() > SESSION_TTL
        ]

        for k in dead:
            CONTACT_SESSIONS.pop(k, None)


def _send_channel(channel, address, message):
    print(f"[NjiaMauzo] {channel.upper()} -> {address}: {message[:90]}...")
    return True


def notify_seller(data):
    message = data.get("message") or (
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

    for channel, address in pairs:
        if address and str(address).strip():
            results[channel] = _send_channel(channel, str(address).strip(), message)

    return results


def _is_unlocked():
    return session.get("unlocked") is True or session.get("is_admin") is True


def get_product(pid):
    try:
        pid = int(pid)
    except Exception:
        return None

    return next((p for p in SAMPLE_PRODUCTS if p["id"] == pid), None)


def _products_for_client():
    unlocked = _is_unlocked()
    out = []

    hidden_fields = {
        "real_price",
        "seller_phone",
        "seller_whatsapp",
        "seller_email",
        "seller_telegram",
        "seller_facebook",
        "seller_instagram",
        "transport_cost",
        "transport_note",
    }

    for p in SAMPLE_PRODUCTS:
        item = dict(p)

        if unlocked:
            item["full_access"] = True
        else:
            for field in hidden_fields:
                item.pop(field, None)

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


@app.route("/api/me", methods=["GET"])
def api_me():
    return jsonify(
        {
            "success": True,
            "logged_in": bool(session.get("user")),
            "user": session.get("user"),
            "is_admin": bool(session.get("is_admin")),
            "unlocked": _is_unlocked(),
        }
    )


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if email and "@" in email and password:
        session["user"] = {
            "email": email,
            "name": email.split("@")[0],
        }

        return jsonify(
            {
                "success": True,
                "message": "Umeingia.",
            }
        )

    return jsonify(
        {
            "success": False,
            "message": "Email au nywila si sahihi.",
        }
    )


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("user", None)
    session.pop("is_admin", None)
    session.pop("unlocked", None)
    session.pop("pending_order_id", None)

    return jsonify({"success": True})


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()

    if not email or not password:
        return jsonify(
            {
                "success": False,
                "message": "Jaza email na nywila.",
            }
        )

    session["user"] = {
        "email": email,
        "name": name or email.split("@")[0],
        "phone": phone,
    }

    return jsonify(
        {
            "success": True,
            "message": "Umesajiliwa.",
        }
    )


@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    data = request.get_json(silent=True) or {}

    username = data.get("username") or ""
    password = data.get("password") or ""

    if username == ADMIN_USER and password == ADMIN_PASS:
        session["is_admin"] = True
        session["unlocked"] = True
        session["user"] = {
            "email": "admin@njiamauzo.tz",
            "name": "Admin",
        }

        return jsonify(
            {
                "success": True,
                "message": "Admin umeingia.",
                "admin_mode": True,
            }
        )

    return jsonify(
        {
            "success": False,
            "message": "Admin credentials si sahihi.",
        }
    )


@app.route("/api/admin/logout", methods=["POST"])
def api_admin_logout():
    session.pop("is_admin", None)
    session.pop("unlocked", None)
    session.pop("user", None)

    return jsonify({"success": True})


@app.route("/api/admin/status", methods=["GET"])
def api_admin_status():
    return jsonify(
        {
            "success": True,
            "is_admin": bool(session.get("is_admin")),
            "unlocked": _is_unlocked(),
            "user": session.get("user"),
            "remaining_seconds": 3600 if _is_unlocked() else 0,
        }
    )


@app.route("/api/admin/change-password", methods=["POST"])
def api_admin_change_password():
    if not session.get("is_admin"):
        return jsonify(
            {
                "success": False,
                "message": "Si admin.",
            }
        ), 403

    return jsonify(
        {
            "success": True,
            "message": "Nywila imebadilishwa (demo).",
        }
    )


@app.route("/api/products", methods=["GET"])
def api_products():
    return jsonify(
        {
            "success": True,
            "products": _products_for_client(),
            "admin_mode": bool(session.get("is_admin")),
            "unlocked": _is_unlocked(),
        }
    )


@app.route("/api/ai-products", methods=["GET"])
def api_ai_products():
    q = (request.args.get("q") or "").lower()
    products = _products_for_client()

    if q:
        products = [
            p
            for p in products
            if q in (p.get("title") or "").lower()
            or q in (p.get("description") or "").lower()
            or q in (p.get("location") or "").lower()
        ]

    return jsonify(
        {
            "success": True,
            "products": products,
            "unlocked": _is_unlocked(),
        }
    )


@app.route("/api/products/<int:pid>/like", methods=["POST"])
def api_like(pid):
    product = get_product(pid)

    if not product:
        return jsonify(
            {
                "success": False,
                "message": "Bidhaa haipatikani.",
            }
        ), 404

    product["likes"] = product.get("likes", 0) + 1

    return jsonify(
        {
            "success": True,
            "likes": product["likes"],
            "liked": True,
        }
    )


@app.route("/api/comments/<int:pid>", methods=["GET", "POST"])
def api_comments(pid):
    if pid not in COMMENTS:
        COMMENTS[pid] = []

    if request.method == "GET":
        return jsonify(
            {
                "success": True,
                "comments": COMMENTS[pid],
            }
        )

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify(
            {
                "success": False,
                "message": "Andika maoni.",
            }
        ), 400

    user = (session.get("user") or {}).get("email") or "Guest"

    comment = {
        "id": secrets.token_hex(4),
        "message": message,
        "user": user,
        "created": now_iso(),
    }

    COMMENTS[pid].append(comment)

    return jsonify(
        {
            "success": True,
            "message": "Maoni yamepokewa.",
            "comment": comment,
        }
    )


@app.route("/api/market-stats", methods=["GET"])
def api_market_stats():
    unlocked = _is_unlocked()

    return jsonify(
        {
            "success": True,
            "unlocked": unlocked,
            "summary": {
                "total_products": len(SAMPLE_PRODUCTS),
                "total_categories": len(SAMPLE_PRODUCTS),
                "total_locations": len({p["location"] for p in SAMPLE_PRODUCTS}),
                "total_likes": sum(p.get("likes", 0) for p in SAMPLE_PRODUCTS),
            },
            "categories": [
                {
                    "label": p["title"],
                    "count": 1,
                    "share": round(100 / len(SAMPLE_PRODUCTS)),
                    "avg_price": p["real_price"] if unlocked else None,
                    "min_price": p["real_price"] if unlocked else None,
                    "max_price": p["real_price"] if unlocked else None,
                }
                for p in SAMPLE_PRODUCTS
            ],
            "recent": [{"title": p["title"]} for p in SAMPLE_PRODUCTS],
            "top_locations": sorted({p["location"] for p in SAMPLE_PRODUCTS}),
        }
    )


@app.route("/api/activity", methods=["GET"])
def api_activity():
    since_id = request.args.get("since_id", 0, type=int)

    with _activity_lock:
        items = [a for a in ACTIVITY_LOG if a["id"] > since_id]

    return jsonify(
        {
            "success": True,
            "activity": items,
        }
    )


@app.route("/api/research", methods=["POST"])
def api_research():
    unlocked = _is_unlocked()

    return jsonify(
        {
            "success": True,
            "unlocked": unlocked,
            "summary": {
                "total_listings": len(SAMPLE_PRODUCTS),
                "locations_covered": len({p["location"] for p in SAMPLE_PRODUCTS}),
                "avg_price": (
                    round(
                        sum(p["real_price"] for p in SAMPLE_PRODUCTS)
                        / len(SAMPLE_PRODUCTS)
                    )
                    if unlocked
                    else None
                ),
            },
            "comparison": [
                {
                    "location": p["location"],
                    "listings": 1,
                    "min_price": p["real_price"] if unlocked else None,
                    "max_price": p["real_price"] if unlocked else None,
                }
                for p in SAMPLE_PRODUCTS
            ],
            "sources": [
                {
                    "product": p["title"],
                    "location": p["location"],
                    "chanzo": p["seller_name"] if unlocked else "Imefungwa",
                    "updated": "leo",
                }
                for p in SAMPLE_PRODUCTS
            ],
        }
    )


@app.route("/api/automate/alerts", methods=["GET", "POST"])
@app.route("/api/automate/alerts/<int:aid>", methods=["DELETE"])
def api_alerts(aid=None):
    global ALERT_NEXT_ID

    if request.method == "GET":
        with ALERT_LOCK:
            alerts = list(ALERTS)

        return jsonify(
            {
                "success": True,
                "alerts": alerts,
            }
        )

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        product = (data.get("product") or "").strip()
        price = data.get("price")

        if not product:
            return jsonify(
                {
                    "success": False,
                    "message": "Andika bidhaa.",
                }
            ), 400

        with ALERT_LOCK:
            alert = {
                "id": ALERT_NEXT_ID,
                "product": product,
                "price": price,
                "created": now_iso(),
            }

            ALERT_NEXT_ID += 1
            ALERTS.append(alert)

        add_activity(f"Alert mpya: {product} bei {price or 'flexible'}.")

        return jsonify(
            {
                "success": True,
                "message": "Alert imewekwa.",
                "alert": alert,
            }
        )

    # DELETE
    with ALERT_LOCK:
        before = len(ALERTS)
        ALERTS[:] = [a for a in ALERTS if a["id"] != aid]
        deleted = len(ALERTS) < before

    if not deleted:
        return jsonify(
            {
                "success": False,
                "message": "Alert haipatikani.",
            }
        ), 404

    return jsonify(
        {
            "success": True,
            "message": "Alert imefutwa.",
        }
    )


@app.route("/api/bot-chat", methods=["POST"])
def api_bot_chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").lower()

    if "bei" in msg or "price" in msg:
        reply = f"Bei kamili unapata baada ya kulipa ada TZS {SERVICE_FEE_TZS:,}. Bofya LIPA ADA."
    elif "whatsapp" in msg or "mawasiliano" in msg:
        reply = "Wasiliana nasi WhatsApp: 0755 248 789 — tuko 24/7."
    elif "ufuta" in msg:
        reply = "Ufuta wa Ruvuma upo. Bofya Wasiliana kwenye bidhaa ya Ufuta."
    elif "mahindi" in msg:
        reply = "Mahindi ya Mbeya ipo. Bofya Wasiliana kwenye bidhaa ya Mahindi."
    elif "kahawa" in msg:
        reply = "Kahawa Arabica ya Arusha ipo. Bofya Wasiliana kwenye bidhaa ya Kahawa."
    else:
        reply = (
            "Habari! Mimi ni msaidizi wa NjiaMauzo Afrika. "
            "Naweza kukusaidia kutafuta mazao, bei, au kuunganisha na muuzaji."
        )

    return jsonify(
        {
            "success": True,
            "reply": reply,
        }
    )


@app.route("/api/service/payment-number", methods=["GET"])
def api_payment_numbers():
    return jsonify(
        {
            "success": True,
            "numbers": PAYMENT_NUMBERS,
        }
    )


@app.route("/api/payment/request", methods=["POST"])
def api_payment_request():
    data = request.get_json(silent=True) or {}

    if data.get("admin_bypass") and session.get("is_admin"):
        session["unlocked"] = True

        order_id = "ADM-" + secrets.token_hex(4).upper()

        with PAYMENT_LOCK:
            PAYMENT_ORDERS[order_id] = {
                "status": "verified",
                "method": "Admin Bypass",
                "amount": 0,
                "created": datetime.utcnow(),
                "verified_at": datetime.utcnow(),
                "phone": "",
                "user": "admin",
            }

        add_activity("Admin amefungua access kwa bypass.")

        return jsonify(
            {
                "success": True,
                "order_id": order_id,
                "message": "Admin access imefunguliwa.",
                "payment_number": "—",
            }
        )

    order_id = "ORD-" + secrets.token_hex(4).upper()
    method = data.get("njia") or data.get("method") or "M-Pesa"
    phone = data.get("phone") or ""

    with PAYMENT_LOCK:
        PAYMENT_ORDERS[order_id] = {
            "status": "pending",
            "method": method,
            "amount": SERVICE_FEE_TZS,
            "created": datetime.utcnow(),
            "phone": phone,
            "user": (session.get("user") or {}).get("email"),
        }

    session["pending_order_id"] = order_id

    return jsonify(
        {
            "success": True,
            "order_id": order_id,
            "payment_number": PAYMENT_NUMBERS.get(method, "0755248789"),
            "message": (
                f"Payment imeanzishwa. Tuma TZS {SERVICE_FEE_TZS:,}. "
                "Baada ya kulipa, admin atathibitisha — kisha utafunguliwa."
            ),
        }
    )


@app.route("/api/access/status", methods=["GET"])
def api_access_status():
    order_id = request.args.get("order_id") or session.get("pending_order_id")
    order = None

    if order_id:
        with PAYMENT_LOCK:
            order = PAYMENT_ORDERS.get(order_id)

    if order and order["status"] == "verified":
        session["unlocked"] = True

    return jsonify(
        {
            "success": True,
            "unlocked": _is_unlocked(),
            "order_status": order["status"] if order else None,
            "remaining_seconds": 3600 if _is_unlocked() else 0,
        }
    )


@app.route("/api/service/admin-verify", methods=["POST"])
def api_admin_verify_payment():
    if not session.get("is_admin"):
        return jsonify(
            {
                "success": False,
                "message": "Si admin.",
            }
        ), 403

    data = request.get_json(silent=True) or {}
    order_id = (data.get("order_id") or "").strip()

    with PAYMENT_LOCK:
        order = PAYMENT_ORDERS.get(order_id)

        if not order:
            return jsonify(
                {
                    "success": False,
                    "message": "Order haipatikani.",
                }
            ), 404

        order["status"] = "verified"
        order["verified_at"] = datetime.utcnow()

    add_activity(f"Order {order_id} imethibitishwa na admin.")

    return jsonify(
        {
            "success": True,
            "message": f"Order {order_id} imethibitishwa.",
            "order_id": order_id,
        }
    )


@app.route("/api/admin/orders", methods=["GET"])
def api_admin_orders():
    if not session.get("is_admin"):
        return jsonify(
            {
                "success": False,
                "message": "Si admin.",
            }
        ), 403

    with PAYMENT_LOCK:
        orders = []

        for oid, o in sorted(
            PAYMENT_ORDERS.items(),
            key=lambda x: x[1].get("created") or datetime.utcnow(),
            reverse=True,
        ):
            created = o.get("created")

            orders.append(
                {
                    "order_id": oid,
                    "status": o.get("status"),
                    "method": o.get("method"),
                    "amount": o.get("amount"),
                    "phone": o.get("phone"),
                    "user": o.get("user"),
                    "created": (
                        created.isoformat() + "Z"
                        if isinstance(created, datetime)
                        else created
                    ),
                }
            )

    return jsonify(
        {
            "success": True,
            "orders": orders,
        }
    )


@app.route("/api/contact-seller", methods=["POST"])
def contact_seller():
    data = request.get_json(silent=True) or {}

    pid = None

    if data.get("product_id") not in (None, ""):
        try:
            pid = int(data.get("product_id"))
        except Exception:
            pid = None

    product = get_product(pid) if pid else None

    if product:
        if not data.get("phone"):
            data["phone"] = product.get("seller_phone")

        if not data.get("whatsapp"):
            data["whatsapp"] = product.get("seller_whatsapp")

        if not data.get("email"):
            data["email"] = product.get("seller_email")

        if not data.get("telegram"):
            data["telegram"] = product.get("seller_telegram")

        if not data.get("facebook"):
            data["facebook"] = product.get("seller_facebook")

        if not data.get("instagram"):
            data["instagram"] = product.get("seller_instagram")

    session_id = data.get("session_id") or str(uuid.uuid4())
    seller_name = (
        data.get("seller_name")
        or (product.get("seller_name") if product else None)
        or "Muuzaji"
    )

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
        time.sleep(8 + (abs(hash(sid)) % 8))

        with SESSION_LOCK:
            s = CONTACT_SESSIONS.get(sid)

            if s and not s["replied"]:
                s["replied"] = True
                s["replied_at"] = datetime.utcnow()
                s["reply_text"] = "Karibu niko hewani nikuhudumie."

    if os.environ.get("DEMO_AUTO_REPLY", "1") == "1":
        threading.Thread(target=_auto_reply, args=(session_id,), daemon=True).start()

    return jsonify(
        {
            "success": True,
            "session_id": session_id,
            "message": "Ujumbe umetumwa kwa muuzaji kupitia mawasiliano yaliyopo.",
            "channels": channels,
            "seller_name": seller_name,
        }
    )


@app.route("/api/contact-seller/status", methods=["GET"])
def contact_seller_status():
    _cleanup_sessions()

    session_id = request.args.get("session_id") or ""
    seller_id = request.args.get("seller_id") or ""

    with SESSION_LOCK:
        sess = CONTACT_SESSIONS.get(session_id)

        if not sess and seller_id:
            for sid, s in sorted(
                CONTACT_SESSIONS.items(),
                key=lambda x: x[1]["created"],
                reverse=True,
            ):
                if s.get("seller_id") == seller_id:
                    sess = s
                    session_id = sid
                    break

        if not sess:
            return jsonify(
                {
                    "success": True,
                    "replied": False,
                    "found": False,
                }
            )

        return jsonify(
            {
                "success": True,
                "found": True,
                "session_id": session_id,
                "replied": bool(sess.get("replied")),
                "seller_name": sess.get("seller_name"),
                "reply_text": sess.get("reply_text"),
                "replied_at": (
                    sess["replied_at"].isoformat() + "Z"
                    if sess.get("replied_at")
                    else None
                ),
            }
        )


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
            return jsonify(
                {
                    "success": False,
                    "message": "Session haipatikani.",
                }
            ), 404

        sess["replied"] = True
        sess["replied_at"] = datetime.utcnow()
        sess["reply_text"] = data.get("message") or "Karibu niko hewani nikuhudumie."

    return jsonify(
        {
            "success": True,
            "session_id": session_id,
            "message": "Jibu limeandikishwa.",
        }
    )


@app.route("/api/ads/engage", methods=["POST"])
def api_ads_engage():
    return jsonify(
        {
            "success": True,
            "message": "Ad engagement imerekodiwa (demo).",
        }
    )


@app.route("/api/password/forgot", methods=["POST"])
@app.route("/api/password/reset", methods=["POST"])
@app.route("/api/password/change", methods=["POST"])
def api_password():
    return jsonify(
        {
            "success": True,
            "message": "OK (demo).",
        }
    )


threading.Thread(target=_activity_worker, daemon=True).start()

DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"

if __name__ == "__main__":
    print("=" * 50)
    print("  NjiaMauzo Afrika")
    print("  http://127.0.0.1:5000")
    print("  Admin: admin / njiamauzo2026")
    print("=" * 50)

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=DEBUG,
        use_reloader=False,
)
