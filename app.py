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
app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")
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
        reply = "Bei kamili unapata baada ya kulipa ada TZS 1,000. Bofya PATA MSAADA HAPA."
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
    session["unlocked"] = True  # demo unlock
    numbers = {"M-Pesa": "0755248789", "Halotel": "0625031460", "Airtel Money": "0691925100"}
    method = data.get("njia") or "M-Pesa"
    return jsonify({
        "success": True,
        "order_id": order_id,
        "payment_number": numbers.get(method, "0755248789"),
        "message": "Payment imeanzishwa. Tuma TZS 1,000.",
    })


@app.route("/api/access/status", methods=["GET"])
def api_access_status():
    return jsonify({
        "success": True,
        "unlocked": _is_unlocked(),
        "remaining_seconds": 3600 if _is_unlocked() else 0,
    })


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


@app.route("/api/ads/engage", methods=["POST"])
def api_ads_engage():
    return jsonify({"success": True})


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
