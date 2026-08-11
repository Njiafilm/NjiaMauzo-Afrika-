import os
import secrets
import sqlite3
import time
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, g
from functools import wraps

app = Flask(__name__)

# =========================================================
# 1) CONFIGURATIONS & ENVIRONMENT VARIABLES
# =========================================================
# Render inatumia environment variables. Hakikisha umeweka SECRET_KEY kwenye Render Dashboard.
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))
DATABASE = os.environ.get("DATABASE_URL", "njia_mauzo.db")

# Admin Credentials (Unaweza kubadilisha hizi au kuziweka kwenye Render Environment)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin@njiamauzo.africa")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "0000")

# =========================================================
# 2) DATABASE SETUP (SQLite)
# =========================================================
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Inaunda majedwali ya database kama hayapo."""
    db = sqlite3.connect(DATABASE)
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product TEXT,
            price REAL,
            description TEXT
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL,
            status TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.commit()
    db.close()

# =========================================================
# 3) DECORATORS (Rate Limit & Admin Check)
# =========================================================
def rate_limit(limit, per):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Hapa unaweza kuongeza logic ya Redis/Memory kuzuia spam
            return f(*args, **kwargs)
        return wrapped
    return decorator

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# =========================================================
# 4) FRONTEND ROUTES (Hapa Ndio Iliyokuwa Shida Kuu)
# =========================================================
@app.get("/")
def index():
    # Hii inafungua faili lako la HTML lililo kwenye folda ya 'templates'
    return render_template("index.html")

# =========================================================
# 5) API ROUTES (Zinafanya kazi na Frontend yako)
# =========================================================
@app.get("/api/health")
def health_check():
    return jsonify({"success": True, "service": "NJIA MAUZO AFRIKA API", "status": "ok"})

@app.get("/api/ai-products")
def api_ai_products():
    # Data za mfano kwa ajili ya AI Products
    products = [
        {"id": 1, "name": "Mahindi", "price": 120000, "unit": "Tani", "market": "Dar es Salaam"},
        {"id": 2, "name": "Mpunga (Kilombero)", "price": 150000, "unit": "Tani", "market": "Kyela"},
        {"id": 3, "name": "Ufuta", "price": 8000, "unit": "Kg", "market": "Dodoma"}
    ]
    return jsonify({"success": True, "data": products})

@app.post("/api/bot-chat")
def api_bot_chat():
    user_message = request.json.get("message", "")
    # Majibu ya mfano ya Bot
    if "bei" in user_message.lower() or "soko" in user_message.lower():
        response = "Bei za Mahindi ziko juu kidogo sasa hivi (TZS 120,000/tani). Unataka kuagiza?"
    else:
        response = "Karibu Njia Mauzo Afrika! Ninaweza kukusaidia kupata mazao, wauzaji, na usafiri."
    return jsonify({"success": True, "reply": response})

@app.post("/api/notify-admin")
def api_notify_admin():
    return jsonify({"success": True, "message": "Admin amejaribiwa kutumiwa arifa."})

@app.get("/api/service/payment-number")
def api_payment_number():
    return jsonify({"success": True, "number": "0712345678", "provider": "M-Pesa / Tigo Pesa"})

@app.post("/api/service/payment-request")
def api_payment_request():
    data = request.json
    ref = f"REF{int(time.time())}"
    return jsonify({"success": True, "reference": ref, "status": "pending"})

@app.get("/api/service/payment-status/<reference>")
def api_payment_status(reference):
    return jsonify({"success": True, "reference": reference, "status": "completed"})

# =========================================================
# 6) ADMIN & AUTH ROUTES
# =========================================================
@app.route("/login", methods=["GET", "POST"])
@rate_limit(10, 60)
def login():
    error = None
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if secrets.compare_digest(u, ADMIN_USERNAME) and secrets.compare_digest(p, ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Jina au nenosiri si sahihi."
    
    # Kama una templates/login.html tumia: return render_template("login.html", error=error)
    return f"""
    <h2>Admin Login</h2>
    {f'<p style="color:red">{error}</p>' if error else ''}
    <form method="POST">
        <label>Email:</label><br>
        <input type="text" name="username" required><br>
        <label>Password:</label><br>
        <input type="password" name="password" required><br><br>
        <button type="submit">Ingia</button>
    </form>
    """

@app.get("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("login"))

@app.get("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    payments = db.execute("SELECT * FROM payments ORDER BY id DESC LIMIT 100").fetchall()
    listings = db.execute("SELECT * FROM listings ORDER BY id DESC LIMIT 200").fetchall()
    
    # Kama una templates/admin.html tumia: return render_template("admin.html", ...)
    return f"""
    <h2>Admin Dashboard - Njia Mauzo Afrika</h2>
    <p>Karibu, {ADMIN_USERNAME}</p>
    <a href="/logout">Toka (Logout)</a>
    <hr>
    <h3>Malipo ya Hivi Karibuni</h3>
    <ul>
        {''.join(f"<li>ID: {p['id']} - Kiasi: {p['amount']} - Hali: {p['status']}</li>" for p in payments) if payments else '<li>Hakuna malipo</li>'}
    </ul>
    <h3>Mazao Yaliyopo</h3>
    <ul>
        {''.join(f"<li>{l['product']} - Bei: {l['price']}</li>" for l in listings) if listings else '<li>Hakuna mazao</li>'}
    </ul>
    """

# =========================================================
# 7) FLASK STARTUP (MUHIMU KWA RENDER)
# =========================================================
if __name__ == "__main__":
    # Hakikisha DB imeundwa kabla ya kuanza
    if not os.path.exists(DATABASE):
        init_db()
        
    # Render inatoa PORT kupitia environment variables.
    # Bila hii, app itashindwa kuwaka (crash).
    port = int(os.environ.get("PORT", 5000))
    
    # host='0.0.0.0' inaruhusu Render kuipata app yako kutoka nje
    app.run(host="0.0.0.0", port=port, debug=False)
