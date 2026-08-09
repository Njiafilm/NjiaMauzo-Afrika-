import os, re, sqlite3, secrets, hashlib, json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, send_from_directory
BASE = os.path.dirname(__file__)
DB = os.path.join(BASE, "njiamauzo_v3.db")
app = Flask(__name__)@app.route("/static/style.css")
def static_css():
    return send_from_directory('static','style.css',mimetype='text/css')

@app.route("/static/app.js")
def static_js():
    return send_from_directory('static','app.js',mimetype='application/javascript')
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def hash_password(password):
    salt = os.environ.get("PASSWORD_SALT", "njiamauzo-demo-salt").encode()
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180000).hex()

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT,
      password_hash TEXT NOT NULL, role TEXT DEFAULT 'buyer',
      verified INTEGER DEFAULT 0, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS prices(
      id INTEGER PRIMARY KEY AUTOINCREMENT, crop TEXT, market TEXT, country TEXT,
      buy_price REAL, sell_price REAL, transport_per_kg REAL DEFAULT 0,
      source TEXT, recorded_at TEXT
    );
    CREATE TABLE IF NOT EXISTS listings(
      id INTEGER PRIMARY KEY AUTOINCREMENT, crop TEXT, quantity_kg REAL,
      price REAL, location TEXT, country TEXT, seller_id INTEGER,
      verified INTEGER DEFAULT 0, status TEXT DEFAULT 'ACTIVE', created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS alerts(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, crop TEXT,
      target_price REAL, direction TEXT DEFAULT 'ABOVE', created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS payments(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL,
      method TEXT, status TEXT, reference TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS searches(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, query TEXT,
      created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS service_requests(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, guest_token TEXT,
      query TEXT NOT NULL, status TEXT DEFAULT 'AWAITING_PAYMENT',
      payment_id INTEGER, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS service_rooms(
      id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER UNIQUE,
      user_id INTEGER, guest_token TEXT, query TEXT, status TEXT DEFAULT 'OPEN',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS payment_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT, payment_id INTEGER, event_type TEXT,
      payload TEXT, created_at TEXT NOT NULL
    );
    """)
    if c.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 0:
        now = datetime.utcnow().isoformat()
        rows = [
          ("Ufuta","Songea","Tanzania",3100,3300,150,"Demo Market Feed"),
          ("Ufuta","Dar es Salaam","Tanzania",3600,3900,350,"Demo Market Feed"),
          ("Ufuta","Nairobi","Kenya",3700,4100,520,"Demo Market Feed"),
          ("Ufuta","Kampala","Uganda",3400,3800,600,"Demo Market Feed"),
          ("Ufuta","Kigali","Rwanda",3500,4000,650,"Demo Market Feed"),
          ("Mahindi","Mwanza","Tanzania",800,850,120,"Demo Market Feed"),
          ("Mahindi","Dar es Salaam","Tanzania",900,1050,250,"Demo Market Feed"),
          ("Mahindi","Nairobi","Kenya",920,1100,480,"Demo Market Feed"),
          ("Maharage","Arusha","Tanzania",2300,2500,180,"Demo Market Feed"),
          ("Maharage","Dar es Salaam","Tanzania",2600,2900,260,"Demo Market Feed"),
          ("Maharage","Kampala","Uganda",2100,2500,550,"Demo Market Feed"),
          ("Mpunga","Morogoro","Tanzania",1650,1800,120,"Demo Market Feed"),
          ("Mpunga","Dar es Salaam","Tanzania",1900,2150,230,"Demo Market Feed"),
          ("Mpunga","Kigali","Rwanda",1900,2300,600,"Demo Market Feed"),
          ("Korosho","Mtwara","Tanzania",4500,5000,170,"Demo Market Feed"),
          ("Korosho","Dar es Salaam","Tanzania",5200,5700,300,"Demo Market Feed"),
        ]
        c.executemany("""INSERT INTO prices
          (crop,market,country,buy_price,sell_price,transport_per_kg,source,recorded_at)
          VALUES(?,?,?,?,?,?,?,?)""", [r + (now,) for r in rows])
    if c.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 0:
        now = datetime.utcnow().isoformat()
        demo = [
          ("Ufuta",20000,3150,"Songea","Tanzania",1),
          ("Mahindi",30000,820,"Mwanza","Tanzania",1),
          ("Maharage",12000,2350,"Arusha","Tanzania",1),
          ("Mpunga",18000,1700,"Morogoro","Tanzania",1),
        ]
        c.executemany("""INSERT INTO listings
          (crop,quantity_kg,price,location,country,verified,created_at)
          VALUES(?,?,?,?,?,?,?)""", [r[:6] + (now,) for r in demo])
    c.commit()
    c.close()

CROPS = {
    "mahindi":"Mahindi","maize":"Mahindi","ufuta":"Ufuta","sesame":"Ufuta",
    "maharage":"Maharage","beans":"Maharage","mpunga":"Mpunga","rice":"Mpunga",
    "korosho":"Korosho","cashew":"Korosho"
}
LOCATIONS = ["Songea","Ruvuma","Mwanza","Arusha","Morogoro","Mtwara",
             "Dar es Salaam","Nairobi","Kampala","Kigali","Bujumbura"]

def parse_query(text):
    t = (text or "").lower()
    crop = next((v for k,v in CROPS.items() if k in t), None)
    loc = next((x for x in LOCATIONS if x.lower() in t), None)
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*(tani|ton|tons|kg)?', t)
    qty = None
    if m:
        qty = float(m.group(1).replace(",",""))
        if m.group(2) in ("tani","ton","tons"):
            qty *= 1000
    p = re.search(r'(?:chini ya|under|below|max|<=)\s*(?:tzs)?\s*([\d,]+)', t)
    maxp = float(p.group(1).replace(",","")) if p else None
    return crop, loc, qty, maxp

def logged():
    return bool(session.get("user_id"))

@app.route("/")
def home():
    return render_template("index.html")

@app.get("/api/prices")
def prices():
    q = request.args.get("q","").lower()
    country = request.args.get("country","")
    crop = request.args.get("crop","")
    c = db()
    rows = c.execute("SELECT * FROM prices ORDER BY recorded_at DESC, crop, market").fetchall()
    c.close()
    out = []
    for x in rows:
        hay = f'{x["crop"]} {x["market"]} {x["country"]}'.lower()
        if q and q not in hay: continue
        if country and x["country"] != country: continue
        if crop and x["crop"] != crop: continue
        out.append(dict(x))
    return jsonify(out)

@app.get("/api/stats")
def stats():
    c = db()
    data = {
      "users": c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
      "listings": c.execute("SELECT COUNT(*) FROM listings WHERE status='ACTIVE'").fetchone()[0],
      "markets": c.execute("SELECT COUNT(DISTINCT market) FROM prices").fetchone()[0],
      "countries": c.execute("SELECT COUNT(DISTINCT country) FROM prices").fetchone()[0],
    }
    c.close()
    return jsonify(data)

@app.post("/api/intelligence")
def intelligence():
    d = request.json or {}
    crop = d.get("crop")
    qty = float(d.get("quantity_kg") or 0)
    buy = float(d.get("source_price") or 0)
    extra = float(d.get("extra_cost_per_kg") or 0)
    if not crop or qty <= 0 or buy <= 0:
        return jsonify(error="Weka zao, kiasi na bei ya kununua"), 400
    c = db()
    rows = c.execute("SELECT * FROM prices WHERE crop=?", (crop,)).fetchall()
    c.close()
    out = []
    for x in rows:
        landed = buy + x["transport_per_kg"] + extra
        profit = x["sell_price"] - landed
        out.append({
          "market":x["market"],"country":x["country"],"sell_price":x["sell_price"],
          "transport":x["transport_per_kg"],"landed_cost":landed,
          "profit_per_kg":profit,"profit_total":profit*qty,
          "margin_pct":profit/landed*100 if landed else 0,
          "recorded_at":x["recorded_at"],"source":x["source"]
        })
    out.sort(key=lambda x:x["profit_total"], reverse=True)
    return jsonify(results=out, recommendation=out[0] if out else None)

@app.post("/api/ai/search")
def ai_search():
    text = request.json.get("query","")
    crop, loc, qty, maxp = parse_query(text)
    c = db()
    rows = c.execute("SELECT * FROM listings WHERE status='ACTIVE'").fetchall()
    if logged():
        c.execute("INSERT INTO searches(user_id,query,created_at) VALUES(?,?,?)",
                  (session["user_id"], text, datetime.utcnow().isoformat()))
        c.commit()
    c.close()
    out=[]
    for x in rows:
        if crop and x["crop"] != crop: continue
        if loc and loc.lower() not in x["location"].lower(): continue
        if qty and x["quantity_kg"] < qty: continue
        if maxp and x["price"] > maxp: continue
        score=(100 if crop else 0)+(40 if loc else 0)+(20 if x["verified"] else 0)
        out.append({**dict(x), "match_score":score})
    out.sort(key=lambda x:(-x["match_score"], x["price"]))
    return jsonify(interpreted={"crop":crop,"location":loc,"quantity_kg":qty,"max_price":maxp},
                    results=out)

@app.post("/api/ai/chat")
def ai_chat():
    msg = request.json.get("message","")
    crop, loc, qty, maxp = parse_query(msg)
    if crop:
        text = f"Nimeelewa unatafuta {crop}"
        if loc: text += f" katika {loc}"
        if qty: text += f", kiasi cha takribani {qty:,.0f} kg"
        if maxp: text += f", kwa bei isiyozidi TZS {maxp:,.0f}/kg"
        text += ". Tumia AI Search au Profit Intelligence kupata matching na soko lenye makadirio bora."
    else:
        text = "Jaribu: “Natafuta tani 20 za ufuta Songea chini ya TZS 3,200/kg.” au “Nina tani 30 za mahindi Mwanza, niuze wapi?”"
    return jsonify(reply=text)

@app.post("/api/register")
def register():
    d=request.json or {}
    required=("name","email","password")
    if not all(d.get(k) for k in required):
        return jsonify(error="Jaza jina, email na password"),400
    c=db()
    try:
        uid=c.execute("""INSERT INTO users(name,email,phone,password_hash,role,created_at)
          VALUES(?,?,?,?,?,?)""",(d["name"],d["email"].lower(),d.get("phone",""),
          hash_password(d["password"]),d.get("role","buyer"),datetime.utcnow().isoformat())).lastrowid
        c.commit()
    except sqlite3.IntegrityError:
        c.close(); return jsonify(error="Email tayari imesajiliwa"),409
    c.close()
    session.update(user_id=uid,name=d["name"],role=d.get("role","buyer"))
    return jsonify(ok=True,name=d["name"])

@app.post("/api/login")
def login():
    d=request.json or {}
    c=db()
    u=c.execute("SELECT * FROM users WHERE email=?", (d.get("email","").lower(),)).fetchone()
    c.close()
    if not u or u["password_hash"] != hash_password(d.get("password","")):
        return jsonify(error="Login si sahihi"),401
    session.update(user_id=u["id"],name=u["name"],role=u["role"])
    return jsonify(ok=True,name=u["name"],role=u["role"])

@app.get("/api/me")
def me():
    return jsonify(logged_in=logged(),name=session.get("name"),role=session.get("role"))

@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)

@app.post("/api/listings")
def add_listing():
    if not logged(): return jsonify(error="Login required"),401
    d=request.json or {}
    try:
        qty=float(d["quantity_kg"]); price=float(d["price"])
    except:
        return jsonify(error="Kiasi na bei si sahihi"),400
    c=db()
    c.execute("""INSERT INTO listings(crop,quantity_kg,price,location,country,seller_id,created_at)
      VALUES(?,?,?,?,?,?,?)""",(d["crop"],qty,price,d["location"],d.get("country","Tanzania"),
      session["user_id"],datetime.utcnow().isoformat()))
    c.commit(); c.close()
    return jsonify(ok=True)

@app.get("/api/listings")
def get_listings():
    q=request.args.get("q","").lower()
    c=db(); rows=c.execute("SELECT * FROM listings WHERE status='ACTIVE' ORDER BY verified DESC,price ASC").fetchall(); c.close()
    return jsonify([dict(x) for x in rows if not q or q in f'{x["crop"]} {x["location"]} {x["country"]}'.lower()])

@app.post("/api/alerts")
def alerts():
    if not logged(): return jsonify(error="Login required"),401
    d=request.json or {}
    c=db()
    c.execute("""INSERT INTO alerts(user_id,crop,target_price,direction,created_at)
      VALUES(?,?,?,?,?)""",(session["user_id"],d["crop"],float(d["target_price"]),
      d.get("direction","ABOVE"),datetime.utcnow().isoformat()))
    c.commit(); c.close()
    return jsonify(ok=True)

# --- Assisted Market/Product Search ---------------------------------------
SERVICE_FEE_TZS = 1000.0
# Reference rates are deliberately configurable. For production, refresh these
# from a trusted FX provider and store the effective date.
CURRENCY_RATES = {
    "Tanzania": {"code":"TZS","name":"Tanzanian Shilling","per_tzs":1.0},
    "Kenya": {"code":"KES","name":"Kenyan Shilling","per_tzs":0.049},
    "Uganda": {"code":"UGX","name":"Ugandan Shilling","per_tzs":1.33},
    "Rwanda": {"code":"RWF","name":"Rwandan Franc","per_tzs":0.55},
    "Burundi": {"code":"BIF","name":"Burundian Franc","per_tzs":0.43},
}

def guest_token():
    if not session.get("guest_token"):
        session["guest_token"] = secrets.token_urlsafe(24)
    return session["guest_token"]

def service_identity():
    return session.get("user_id"), guest_token()

def payment_verified(payment_id):
    c=db()
    p=c.execute("SELECT status FROM payments WHERE id=?", (payment_id,)).fetchone()
    c.close()
    return bool(p and p["status"] == "VERIFIED")

def service_access(request_id):
    c=db()
    r=c.execute("SELECT * FROM service_requests WHERE id=?", (request_id,)).fetchone()
    if not r:
        c.close(); return None, "NOT_FOUND"
    same_user = r["user_id"] and r["user_id"] == session.get("user_id")
    same_guest = r["guest_token"] and r["guest_token"] == session.get("guest_token")
    if not (same_user or same_guest):
        c.close(); return None, "FORBIDDEN"
    ok = bool(r["payment_id"] and c.execute(
        "SELECT status FROM payments WHERE id=?", (r["payment_id"],)
    ).fetchone()["status"] == "VERIFIED")
    c.close()
    return r, ("OK" if ok else "PAYMENT_REQUIRED")

@app.get("/api/service/fee")
def service_fee():
    country=request.args.get("country","Tanzania")
    cur=CURRENCY_RATES.get(country,CURRENCY_RATES["Tanzania"])
    return jsonify(base_amount_tzs=SERVICE_FEE_TZS, country=country,
                   currency=cur["code"], amount=round(SERVICE_FEE_TZS*cur["per_tzs"],2),
                   currency_name=cur["name"],
                   note="Kiwango cha fedha ni reference/configurable; gateway ya malipo ndiyo chanzo cha kiasi cha mwisho.")

@app.post("/api/service/start")
def service_start():
    d=request.json or {}
    query=(d.get("query") or "").strip()
    if not query:
        return jsonify(error="Andika bidhaa/zao, kiasi, eneo au soko unalotafuta."),400
    uid,gt=service_identity()
    c=db()
    rid=c.execute("""INSERT INTO service_requests(user_id,guest_token,query,status,created_at)
                     VALUES(?,?,?,?,?)""",
                  (uid,gt,query,"AWAITING_PAYMENT",datetime.utcnow().isoformat())).lastrowid
    c.commit(); c.close()
    return jsonify(ok=True,request_id=rid,status="AWAITING_PAYMENT",
                   fee_tzs=SERVICE_FEE_TZS, message="Lipa TZS 1,000 (au sawa na fedha ya nchi yako) ili kufungua User Room.")

@app.post("/api/service/pay")
def service_pay():
    d=request.json or {}
    rid=int(d.get("request_id") or 0)
    country=d.get("country") or "Tanzania"
    method=d.get("method") or "MOBILE_MONEY"
    phone=(d.get("phone") or "").strip()
    r,status=service_access(rid)
    if not r: return jsonify(error="Request haijapatikana"),404
    if status=="FORBIDDEN": return jsonify(error="Huna ruhusa ya request hii"),403
    if status=="OK": return jsonify(ok=True,status="VERIFIED",room_url=f"/#service-room-{rid}")
    cur=CURRENCY_RATES.get(country,CURRENCY_RATES["Tanzania"])
    amount=round(SERVICE_FEE_TZS*cur["per_tzs"],2)
    ref="NM-SVC-"+secrets.token_hex(6).upper()
    c=db()
    pid=c.execute("""INSERT INTO payments(user_id,amount,method,status,reference,created_at)
                     VALUES(?,?,?,?,?,?)""",
                  (session.get("user_id"),amount,method,"PENDING",ref,datetime.utcnow().isoformat())).lastrowid
    c.execute("UPDATE service_requests SET payment_id=? WHERE id=?", (pid,rid))
    c.execute("""INSERT INTO payment_events(payment_id,event_type,payload,created_at)
                 VALUES(?,?,?,?)""",(pid,"PAYMENT_INITIATED",
                 json.dumps({"request_id":rid,"country":country,"phone":phone,"amount":amount,"currency":cur["code"]}),
                 datetime.utcnow().isoformat()))
    c.commit(); c.close()
    return jsonify(ok=True,status="PENDING",payment_id=pid,reference=ref,
                   amount=amount,currency=cur["code"],
                   message="Malipo yameanzishwa. Subiri gateway ithibitishe malipo.")

@app.get("/api/service/status/<int:rid>")
def service_status(rid):
    r,status=service_access(rid)
    if not r:
        return jsonify(error="Request haijapatikana"),404
    if status=="FORBIDDEN": return jsonify(error="Huna ruhusa"),403
    return jsonify(request_id=rid,status="VERIFIED" if status=="OK" else "PENDING",
                   room_url=f"/#service-room-{rid}" if status=="OK" else None)

@app.post("/api/service/room")
def service_room():
    d=request.json or {}
    rid=int(d.get("request_id") or 0)
    r,status=service_access(rid)
    if not r: return jsonify(error="Request haijapatikana"),404
    if status=="FORBIDDEN": return jsonify(error="Huna ruhusa"),403
    if status!="OK": return jsonify(error="Malipo bado hayajathibitishwa"),402
    c=db()
    room=c.execute("SELECT * FROM service_rooms WHERE request_id=?", (rid,)).fetchone()
    if not room:
        c.execute("""INSERT INTO service_rooms(request_id,user_id,guest_token,query,status,created_at)
                     VALUES(?,?,?,?,?,?)""",
                  (rid,r["user_id"],r["guest_token"],r["query"],"OPEN",datetime.utcnow().isoformat()))
        c.commit()
    c.close()
    # Automatic first search is performed only after payment verification.
    return service_search_internal(r["query"], rid)

def service_search_internal(query, rid):
    crop,loc,qty,maxp=parse_query(query)
    c=db()
    listings=c.execute("SELECT * FROM listings WHERE status='ACTIVE'").fetchall()
    prices=c.execute("SELECT * FROM prices").fetchall()
    c.close()
    products=[]
    for x in listings:
        if crop and x["crop"]!=crop: continue
        if loc and loc.lower() not in f'{x["location"]} {x["country"]}'.lower(): continue
        if qty and x["quantity_kg"]<qty: continue
        if maxp and x["price"]>maxp: continue
        score=(100 if crop else 0)+(40 if loc else 0)+(20 if x["verified"] else 0)
        products.append({**dict(x),"match_score":score,"type":"PRODUCT"})
    markets=[]
    for x in prices:
        if crop and x["crop"]!=crop: continue
        if loc and loc.lower() not in f'{x["market"]} {x["country"]}'.lower(): continue
        if maxp and x["sell_price"]>maxp: continue
        markets.append({**dict(x),"type":"MARKET"})
    products.sort(key=lambda x:(-x["match_score"],x["price"]))
    markets.sort(key=lambda x:(x["sell_price"],x["market"]))
    return jsonify(ok=True,request_id=rid,interpreted={"crop":crop,"location":loc,"quantity_kg":qty,"max_price":maxp},
                   products=products[:50],markets=markets[:50],
                   message="User Room imefunguliwa. Mfumo umeanza kutafuta bidhaa na masoko kulingana na ombi lako.")

@app.post("/api/service/webhook")
def service_webhook():
    # Connect your licensed gateway to this endpoint. Never trust the browser
    # to mark a payment verified.
    secret=os.environ.get("PAYMENT_WEBHOOK_SECRET","")
    provided=request.headers.get("X-Payment-Secret","")
    if not secret or not secrets.compare_digest(secret,provided):
        return jsonify(error="Unauthorized"),401
    d=request.json or {}
    ref=d.get("reference")
    gateway_status=str(d.get("status","")).upper()
    if not ref: return jsonify(error="reference required"),400
    c=db()
    p=c.execute("SELECT * FROM payments WHERE reference=?", (ref,)).fetchone()
    if not p:
        c.close(); return jsonify(error="Payment not found"),404
    status="VERIFIED" if gateway_status in ("SUCCESS","PAID","VERIFIED") else "FAILED" if gateway_status in ("FAILED","CANCELLED") else "PENDING"
    c.execute("UPDATE payments SET status=? WHERE id=?", (status,p["id"]))
    c.execute("""INSERT INTO payment_events(payment_id,event_type,payload,created_at)
                 VALUES(?,?,?,?)""",(p["id"],"GATEWAY_CALLBACK",json.dumps(d),datetime.utcnow().isoformat()))
    if status=="VERIFIED":
        c.execute("""UPDATE service_requests SET status='PAID' WHERE payment_id=?""",(p["id"],))
    c.commit(); c.close()
    return jsonify(ok=True,status=status)

@app.post("/api/payment")
def payment():
    if not logged(): return jsonify(error="Login required"),401
    amount=float((request.json or {}).get("amount") or 0)
    if amount<=0:return jsonify(error="Amount invalid"),400
    ref="NM-"+secrets.token_hex(6).upper()
    c=db()
    c.execute("""INSERT INTO payments(user_id,amount,method,status,reference,created_at)
      VALUES(?,?,?,?,?,?)""",(session["user_id"],amount,(request.json or {}).get("method","MOBILE_MONEY"),
      "PENDING",ref,datetime.utcnow().isoformat()))
    c.commit(); c.close()
    return jsonify(ok=True,status="PENDING",reference=ref,
                    message="Payment intent created. Connect a real licensed gateway for live money.")

init_db()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=True)
