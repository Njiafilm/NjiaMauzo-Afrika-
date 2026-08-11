# app.py - NJIA MAUZO AFRIKA Backend
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import requests
import os
import json
import uuid

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "njia-mauzo-afrika-2026-siri-kali")
CORS(app, supports_credentials=True)

# Hifadhi ya muda (kwa demo - badala ya DB halisi)
# Kwa uzalishaji tumia PostgreSQL/MongoDB
USERS_DB = {}  # {email: {password, name, phone}}
PRODUCTS_DB = []  # bidhaa
ORDERS_DB = []    # malipo/maagizo
COMMENTS_DB = {}  # {product_id: [comments]}

# API ya nje (njiamauzo-afrika.onrender.com)
EXTERNAL_API = "https://njiamauzo-afrika.onrender.com"

# ============ MAUZO ============
@app.route("/")
def index():
    return render_template("index.html")

# ============ AUTHENTICATION ============
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    name = data.get("name", "")
    phone = data.get("phone", "")

    if not all([email, password, name, phone]):
        return jsonify({"success": False, "message": "Jaza taarifa zote"}), 400

    if email in USERS_DB:
        return jsonify({"success": False, "message": "Barua pepe tayari ipo"}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "Nywila iwe na herufi 6+"}), 400

    USERS_DB[email] = {
        "password": generate_password_hash(password),
        "name": name,
        "phone": phone,
        "joined": datetime.now().isoformat(),
        "id": str(uuid.uuid4())
    }

    session["user"] = email
    return jsonify({
        "success": True,
        "message": "Umesajiliwa!",
        "user": {"email": email, "name": name, "phone": phone}
    })

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if email not in USERS_DB:
        return jsonify({"success": False, "message": "Mtumiaji hajapatikana"}), 401

    user = USERS_DB[email]
    if not check_password_hash(user["password"], password):
        return jsonify({"success": False, "message": "Nywila si sahihi"}), 401

    session["user"] = email
    return jsonify({
        "success": True,
        "message": "Umeingia!",
        "user": {"email": email, "name": user["name"], "phone": user["phone"]}
    })

@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    return jsonify({"success": True, "message": "Umetoka"})

@app.route("/api/me", methods=["GET"])
def me():
    email = session.get("user")
    if not email or email not in USERS_DB:
        return jsonify({"success": False}), 401
    u = USERS_DB[email]
    return jsonify({
        "success": True,
        "user": {"email": email, "name": u["name"], "phone": u["phone"]}
    })

# ============ BIDHAA ============
@app.route("/api/products", methods=["GET"])
def products():
    # Kwanza jaribu API ya nje
    try:
        r = requests.get(f"{EXTERNAL_API}/api/ai-products", timeout=5)
        if r.status_code == 200:
            return jsonify(r.json())
    except Exception:
        pass

    # Fallback: bidhaa za ndani
    default_products = [
        {
            "id": 1, "title": "Mahindi ya Ubora wa Juu – Tani 50",
            "realPrice": 850000, "description": "Mahindi yaliyovunwa hivi karibuni kutoka shamba la Morogoro.",
            "image": "https://images.unsplash.com/photo-1625246333195-78d9c38ad449?w=600",
            "seller_id": 101, "seller_name": "Juma Mkulima",
            "location": "Morogoro, Mvomero", "category": "mazao",
            "alama": "Mazao", "likes": 12
        },
        {
            "id": 2, "title": "Mtaalamu wa Kilimo – Ushauri wa Shamba",
            "realPrice": 150000, "description": "Mtaalamu aliyeidhinishwa wa kilimo cha kisasa.",
            "image": "https://images.unsplash.com/photo-1592982537447-7440770cbfc9?w=600",
            "seller_id": 102, "seller_name": "Dkt. Amina Hassan",
            "location": "Arusha, Njiro", "category": "mtaalamu",
            "alama": "Mtaalamu", "likes": 8
        },
        {
            "id": 3, "title": "Kahawa Arabica – Kilimanjaro Grade AA",
            "realPrice": 1200000, "description": "Kahawa bora ya Kilimanjaro, Grade AA.",
            "image": "https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=600",
            "seller_id": 103, "seller_name": "Kilimanjaro Coffee Co-op",
            "location": "Moshi, Kilimanjaro", "category": "mazao",
            "alama": "Mazao", "likes": 21
        },
        {
            "id": 4, "title": "Huduma ya Usafirishaji wa Mazao",
            "realPrice": 350000, "description": "Lori za kusafirisha mazao kutoka shambani hadi soko.",
            "image": "https://images.unsplash.com/photo-1601584115197-04ecc0da31d7?w=600",
            "seller_id": 104, "seller_name": "Safari Mazao Ltd",
            "location": "Dar es Salaam", "category": "huduma",
            "alama": "Huduma", "likes": 5
        },
        {
            "id": 5, "title": "Trekta ya Kukodi – John Deere",
            "realPrice": 250000, "description": "Trekta ya kisasa inayopatikana kwa kukodi.",
            "image": "https://images.unsplash.com/photo-1530267981375-f0de937f5f13?w=600",
            "seller_id": 105, "seller_name": "Vifaa vya Kilimo TZ",
            "location": "Dodoma", "category": "vifaa",
            "alama": "Vifaa", "likes": 15
        },
        {
            "id": 6, "title": "Nyanya za Chafu – Tani 20",
            "realPrice": 480000, "description": "Nyanya safi zilizopandwa kwenye chafu.",
            "image": "https://images.unsplash.com/photo-1546094096-0df4bcaaa337?w=600",
            "seller_id": 106, "seller_name": "Green House Farm",
            "location": "Iringa", "category": "mazao",
            "alama": "Mazao", "likes": 9
        }
    ]
    return jsonify({"success": True, "products": default_products})

# ============ AI CHATBOT ============
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"success": False, "reply": "Tafadhali andika ujumbe."})

    # Jaribu API ya nje kwanza
    try:
        r = requests.post(
            f"{EXTERNAL_API}/api/bot-chat",
            json={"message": message},
            timeout=8
        )
        if r.status_code == 200:
            api_data = r.json()
            reply = api_data.get("reply") or api_data.get("response") or api_data.get("message")
            if reply:
                return jsonify({"success": True, "reply": reply})
    except Exception:
        pass

    # Fallback: bot ya ndani (misingi ya maneno)
    reply = generate_local_reply(message)
    return jsonify({"success": True, "reply": reply})

def generate_local_reply(msg):
    msg = msg.lower()
    if any(w in msg for w in ["malipo", "lipa", "pesa"]):
        return "Ada ya kutafuta ni TZS 2,000. Tunapokea M-Pesa (0691 925 100), Tigo Pesa (0625 031 460), na Airtel Money."
    if any(w in msg for w in ["bei", "gharama", "thamani"]):
        return "Bei halisi zinaonyeshwa baada ya kulipa ada ya TZS 2,000 ya kutafuta."
    if any(w in msg for w in ["mazao", "mahindi", "kahawa"]):
        return "Tuna mazao mbalimbali: mahindi, kahawa, nyanya na mengine. Tembelea sehemu ya Onyesho."
    if any(w in msg for w in ["wasiliana", "simu", "whatsapp"]):
        return "Piga 0691 925 100 au 0625 031 460. WhatsApp: 0755 248 789."
    if any(w in msg for w in ["habari", "hujambo", "mambo"]):
        return "Habari! Karibu Njia Mauzo Afrika. Ninawezaje kukusaidia leo?"
    if any(w in msg for w in ["asante", "shukran"]):
        return "Karibu sana! Tunashukuru kwa kututumia."
    return "Samahani, sikuelewi vyema. Jaribu kuuliza kuhusu: malipo, bei, mazao, au mawasiliano."

# ============ MALIPO ============
@app.route("/api/payment/request", methods=["POST"])
def payment_request():
    data = request.get_json()
    simu = data.get("simu", "").strip()
    njia = data.get("njia", "").strip()
    kiasi = data.get("kiasi", 2000)
    product_id = data.get("product_id")

    if not simu or not njia:
        return jsonify({"success": False, "message": "Jaza taarifa zote"}), 400

    # Jaribu API ya nje
    try:
        r = requests.post(
            f"{EXTERNAL_API}/api/service/payment-request",
            json={"simu": simu, "njia": njia, "kiasi": kiasi, "product_id": product_id},
            timeout=8
        )
        if r.status_code == 200:
            return jsonify(r.json())
    except Exception:
        pass

    # Fallback: simulate payment
    order = {
        "id": str(uuid.uuid4()),
        "simu": simu,
        "njia": njia,
        "kiasi": kiasi,
        "status": "inashughulikiwa",
        "product_id": product_id,
        "created": datetime.now().isoformat()
    }
    ORDERS_DB.append(order)

    return jsonify({
        "success": True,
        "message": f"Tuma TZS {kiasi:,} kwenda {get_payment_number(njia)} kupitia {njia}",
        "order_id": order["id"],
        "payment_number": get_payment_number(njia)
    })

def get_payment_number(njia):
    if "Tigo" in njia or "Halotel" in njia:
        return "0625 031 460"
    if "Airtel" in njia or "WhatsApp" in njia:
        return "0755 248 789"
    return "0691 925 100"

@app.route("/api/payment/status/<order_id>", methods=["GET"])
def payment_status(order_id):
    try:
        r = requests.get(f"{EXTERNAL_API}/api/service/payment-status/{order_id}", timeout=5)
        if r.status_code == 200:
            return jsonify(r.json())
    except Exception:
        pass

    for o in ORDERS_DB:
        if o["id"] == order_id:
            return jsonify({"success": True, "order": o})

    return jsonify({"success": False, "message": "Agizo halipatikani"}), 404

@app.route("/api/payment/numbers", methods=["GET"])
def payment_numbers():
    try:
        r = requests.get(f"{EXTERNAL_API}/api/service/payment-number", timeout=5)
        if r.status_code == 200:
            return jsonify(r.json())
    except Exception:
        pass

    return jsonify({
        "success": True,
        "numbers": {
            "mpesa": "0691 925 100",
            "tigo": "0625 031 460",
            "airtel": "0755 248 789"
        }
    })

# ============ MAONI ============
@app.route("/api/comments/<int:product_id>", methods=["GET"])
def get_comments(product_id):
    comments = COMMENTS_DB.get(product_id, [])
    return jsonify({"success": True, "comments": comments})

@app.route("/api/comments/<int:product_id>", methods=["POST"])
def add_comment(product_id):
    email = session.get("user")
    if not email or email not in USERS_DB:
        return jsonify({"success": False, "message": "Ingia kwanza"}), 401

    data = request.get_json()
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"success": False, "message": "Maoni hayawezi kuwa tupu"}), 400

    comment = {
        "id": str(uuid.uuid4()),
        "author": USERS_DB[email]["name"],
        "text": text,
        "time": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    COMMENTS_DB.setdefault(product_id, []).insert(0, comment)
    return jsonify({"success": True, "comment": comment})

# ============ HEALTH ============
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "success": True,
        "service": "NJIA MAUZO AFRIKA",
        "status": "imara",
        "endpoints": ["/api/login", "/api/register", "/api/products", "/api/chat", "/api/payment/request"]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
