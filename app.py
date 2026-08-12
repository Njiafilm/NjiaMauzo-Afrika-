import os
import time
import random
import threading
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ==========================================
# USANIDI WA AWALI (INITIALIZATION)
# ==========================================
app = Flask(__name__)
# Saini ya siri imelindwa: .0a1b2c3d4e5f6g7h8i9j0
app.config['SECRET_KEY'] = 'njiamauzo-secret-key-0a1b2c3d4e5f6g7h8i9j0' 

socketio = SocketIO(app, cors_allowed_origins="*")

# Ulinzi wa Server: Kuzuia mashambulizi ya kutuma maombi mengi (DDoS/Bot spam)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# ==========================================
# ULINZI WA SERVER (SECURITY HEADERS)
# ==========================================
@app.after_request
def apply_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # CSP inazuia tovuti nyingine kuiba scripts zako
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.socket.io https://cdnjs.cloudflare.com https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.tailwindcss.com;"
    return response

# ==========================================
# BOT CHAT YENYE AKILI (AI MOCK LOGIC)
# ==========================================
@app.route('/api/chat', methods=['POST'])
@limiter.limit("10 per minute") # Ulinzi dhidi ya spam
def chat():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"reply": "Tafadhali tuma ujumbe sahihi."}), 400
        
    user_message = data['message'].lower()
    
    # Kanuni za Msingi za AI (Unaweza kubadili hapa na kuingiza OpenAI API)
    if "bei" in user_message or "gharama" in user_message or "ada" in user_message:
        reply = "Ili kupata bei halisi, anuani na namba ya muuzaji, ada yetu ni TZS 3,000 tu. Je, ungependa kujua namna ya kulipa?"
    elif "kilimo" in user_message or "ushauri" in user_message or "mbegu" in user_message:
        reply = "Tunatoa ushauri wa kitaalamu wa kilimo. Eleza eneo lako na zao unalotaka kuuza au kulima ili tukupe mtaalamu sahihi."
    elif "salama" in user_message or "nakili" in user_message or "copy" in user_message:
        reply = "Tovuti yetu inalindwa kwa kiwango cha juu (0a1b2c3d4e5f6g7h8i9j0). Haki za kunakili na kupiga picha zimezuiwa ili kulinda siri za wateja wetu."
    elif "habari" in user_message or "hujambo" in user_message or "hello" in user_message:
        reply = "Hujambo! Karibu NjiaMauzo Afrika 🌍. Naweza kukusaidia kupata wauzaji, mazao, au ushauri wa kilimo. Nianzeje?"
    else:
        reply = "Nimeshindwa kuelewa swali lako kikamilifu, lakini nipo hapa kukusaidia kuhusu masoko ya Afrika na kilimo. Jaribu kuuliza kuhusu 'bei', 'kilimo', au 'mazao'."
        
    return jsonify({"reply": reply})

# ==========================================
# LIVE FEED 24/7 (BACKGROUND THREAD)
# ==========================================
def live_feed_background():
    events = [
        "🔴 Mtumiaji kutoka Dar es Salaam anatafuta Chai.",
        "🟢 Mnunuzi kutoka Arusha amelipia ada ya TZS 3,000 kupata wauzaji wa Nyanya.",
        "🟡 Msambazaji wa Mahindi amejiunga kutoka Nairobi, Kenya.",
        "🔵 Mkulima anauliza ushauri wa kilimo cha Parachichi.",
        "🟣 Mtaalamu wa Mbegu amejibu swali kutoka Dodoma."
    ]
    while True:
        time.sleep(5) # Kila baada ya sekunde 5
        random_event = random.choice(events)
        current_time = time.strftime("%H:%M:%S")
        socketio.emit('live_update', {'msg': random_event, 'time': current_time})

# Anza Thread ya Live Feed kwenye background
thread = threading.Thread(target=live_feed_background, daemon=True)
thread.start()

# ==========================================
# ROUTES ZA TOVUTI
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

# ==========================================
# KUANZISHA SERVER
# ==========================================
if __name__ == '__main__':
    # Kwa Render au Production, tumia port inayotolewa na mfumo
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
