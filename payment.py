"""
NjiaMauzo Afrika - Payment module (production, no demo mode)
Namba za malipo hazipo kwenye HTML/JS ya mteja - zinatolewa na server
tu baada ya mtumiaji kuchagua njia, kupitia endpoint iliyolindwa na session.
"""

from flask import Blueprint, render_template, jsonify, request, session
import random
import string
from datetime import datetime

payment_bp = Blueprint("payment", __name__)

# --- Fedha za msingi ---
BASE_FEE_TZS = 3000  # Ada mpya badala ya 1000

# --- Namba HALISI za malipo (zihifadhiwe kwenye env vars kwenye production) ---
PAYMENT_NUMBERS = {
    "mpesa":   {"number": "0755 248 789", "label": "M-Pesa / Vodacom"},
    "halotel": {"number": "0625 031 460", "label": "Halotel"},
    "airtel":  {"number": "0691 925 100", "label": "Airtel Money"},
}

# Rates rahisi za currency dhidi ya TZS (weka rates halisi/API ya kubadilisha baadaye)
CURRENCY_RATES = {
    "TZ": {"symbol": "TZS", "rate": 1},
    "KE": {"symbol": "KES", "rate": 0.048},
    "UG": {"symbol": "UGX", "rate": 1.62},
    "RW": {"symbol": "RWF", "rate": 0.54},
}

# Hifadhi ya muda ya malipo yanayosubiri uthibitisho (tumia database halisi kwenye production)
PENDING_PAYMENTS = {}


def _generate_txn_id():
    return "TXN-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


@payment_bp.route("/payment")
def payment_page():
    """Onyesha ukurasa wa malipo pamoja na matangazo ya bidhaa bure juu."""
    ads = get_free_ads()
    return render_template("payment.html", ads=ads, base_fee=BASE_FEE_TZS)


@payment_bp.route("/api/payment-number")
def get_payment_number():
    """
    Inatoa namba ya malipo TU baada ya mtumiaji kuchagua njia (onclick).
    Namba haziko kwenye page source - zinaletwa hapa moja kwa moja.
    """
    method = request.args.get("method")
    info = PAYMENT_NUMBERS.get(method)
    if not info:
        return jsonify({"error": "Njia ya malipo si sahihi"}), 400

    # weka njia iliyochaguliwa kwenye session kwa uthibitisho wa baadaye
    session["selected_method"] = method
    session["expected_fee"] = BASE_FEE_TZS

    return jsonify({"number": info["number"], "label": info["label"]})


@payment_bp.route("/api/verify-payment", methods=["POST"])
def verify_payment():
    """
    Uthibitisho wa malipo - HAKUNA demo mode.
    Malipo yanawekwa 'PENDING' hadi admin/AI athibitishe kwa mkono
    kwa sababu M-Pesa/Halotel/Airtel hazitoi automatic webhook kwa
    watumiaji wadogo bila mkataba rasmi wa API na mtandao husika.
    """
    data = request.get_json(force=True)
    method = data.get("method")
    reference = (data.get("reference") or "").strip()
    country = data.get("country", "TZ")

    if method not in PAYMENT_NUMBERS:
        return jsonify({"status": "ERROR", "message": "Njia ya malipo si sahihi"}), 400
    if not reference:
        return jsonify({"status": "ERROR", "message": "Weka reference ya malipo"}), 400

    txn_id = _generate_txn_id()
    PENDING_PAYMENTS[txn_id] = {
        "method": method,
        "reference": reference,
        "country": country,
        "amount_tzs": BASE_FEE_TZS,
        "status": "PENDING",
        "created_at": datetime.utcnow().isoformat(),
        "user_id": session.get("user_id"),
    }

    # TODO: tuma notification kwa admin (email/telegram/WhatsApp) kuthibitisha
    # kisha admin ataita /api/admin/confirm/<txn_id> kubadilisha status kuwa VERIFIED

    return jsonify({
        "status": "PENDING",
        "txn_id": txn_id,
        "message": "Malipo yamepokelewa, yanasubiri uthibitisho."
    })


@payment_bp.route("/api/admin/confirm/<txn_id>", methods=["POST"])
def admin_confirm_payment(txn_id):
    """Endpoint ya admin/AI controller kuthibitisha malipo halisi (siyo demo)."""
    # HAKIKISHA endpoint hii ina ulinzi wa admin-auth kabla ya kwenda production
    txn = PENDING_PAYMENTS.get(txn_id)
    if not txn:
        return jsonify({"error": "Muamala haujapatikana"}), 404

    txn["status"] = "VERIFIED"
    txn["verified_at"] = datetime.utcnow().isoformat()
    return jsonify({"status": "VERIFIED", "txn_id": txn_id})


def get_free_ads():
    """
    Bidhaa/matangazo yanayoonekana juu ya ukurasa wa malipo BILA gharama.
    Badilisha hii itoe data kutoka database yako halisi ya listings.
    """
    # Mfano wa muundo - unganisha na jedwali lako la 'listings' kwenye DB
    return [
        {"title": "Mchele - Kilo 25", "image_url": "/static/ads/rice.jpg"},
        {"title": "Simu ya mkononi", "image_url": "/static/ads/phone.jpg"},
        {"title": "Nguo za watoto", "image_url": "/static/ads/clothes.jpg"},
    ]
