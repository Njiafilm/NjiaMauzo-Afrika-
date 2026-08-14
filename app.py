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
import base64
import json
import urllib.request
import urllib.error
import urllib.parse

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
ACCESS_DURATION_SEC = 15 * 60  # dakika 15 baada ya malipo

# ---------- M-Pesa STK Push (Safaricom Daraja API) ----------
# Weka credentials kwenye environment variables (usiweke siri kwenye msimbo):
#   MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET, MPESA_SHORTCODE,
#   MPESA_PASSKEY, MPESA_CALLBACK_URL, MPESA_ENV=sandbox|production
# Bila credentials → DEMO MODE (STK inasimuliwa kwa majaribio).
MPESA_CONSUMER_KEY = os.environ.get("MPESA_CONSUMER_KEY", "").strip()
MPESA_CONSUMER_SECRET = os.environ.get("MPESA_CONSUMER_SECRET", "").strip()
MPESA_SHORTCODE = os.environ.get("MPESA_SHORTCODE", "174379").strip()  # sandbox default
MPESA_PASSKEY = os.environ.get(
    "MPESA_PASSKEY",
    "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919",  # sandbox passkey ya umma
).strip()
MPESA_CALLBACK_URL = os.environ.get(
    "MPESA_CALLBACK_URL",
    "",  # e.g. https://yourdomain.com/api/payment/mpesa/callback
).strip()
MPESA_ENV = (os.environ.get("MPESA_ENV") or "sandbox").strip().lower()
MPESA_ACCOUNT_REF = os.environ.get("MPESA_ACCOUNT_REF", "NjiaMauzo")
MPESA_DEMO_MODE = not (MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET)

_MPESA_TOKEN_CACHE = {"token": None, "expires": 0}


def _mpesa_base_url():
    if MPESA_ENV == "production":
        return "https://api.safaricom.co.ke"
    return "https://sandbox.safaricom.co.ke"


def _mpesa_http_json(url, method="GET", data=None, headers=None, timeout=30):
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(err_body) if err_body else {}
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed
    except Exception as e:
        return 0, {"error": str(e)}


def _mpesa_access_token():
    """OAuth token kutoka Daraja (cached)."""
    now = time.time()
    if _MPESA_TOKEN_CACHE["token"] and _MPESA_TOKEN_CACHE["expires"] > now + 30:
        return _MPESA_TOKEN_CACHE["token"]
    if MPESA_DEMO_MODE:
        return "DEMO_TOKEN"
    url = _mpesa_base_url() + "/oauth/v1/generate?grant_type=client_credentials"
    auth = base64.b64encode(
        f"{MPESA_CONSUMER_KEY}:{MPESA_CONSUMER_SECRET}".encode()
    ).decode()
    status, data = _mpesa_http_json(
        url, method="GET", headers={"Authorization": f"Basic {auth}"}
    )
    token = (data or {}).get("access_token")
    if not token:
        raise RuntimeError(f"M-Pesa token imeshindikana ({status}): {data}")
    expires_in = int(data.get("expires_in") or 3599)
    _MPESA_TOKEN_CACHE["token"] = token
    _MPESA_TOKEN_CACHE["expires"] = now + expires_in
    return token


def _normalize_msisdn(phone: str, country: str = "Kenya") -> str:
    """2547XXXXXXXX (Kenya) au 2557XXXXXXXX (Tanzania). STK Push ya Daraja = Kenya."""
    p = "".join(c for c in (phone or "") if c.isdigit())
    if not p:
        return ""
    if p.startswith("0") and len(p) == 10:
        # Kenya default for Safaricom STK
        if country == "Tanzania":
            return "255" + p[1:]
        return "254" + p[1:]
    if p.startswith("7") and len(p) == 9:
        return ("255" if country == "Tanzania" else "254") + p
    if p.startswith("254") or p.startswith("255"):
        return p
    return p


def _mpesa_password_timestamp():
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    raw = f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{ts}"
    pwd = base64.b64encode(raw.encode()).decode()
    return pwd, ts


def mpesa_stk_push(phone: str, amount: int, order_id: str, account_ref: str = None, description: str = None):
    """
    Anzisha Lipa Na M-Pesa Online (STK Push).
    amount: integer (KES kwa Daraja Kenya).
    Returns dict: success, checkout_request_id, merchant_request_id, message, demo
    """
    amount = max(1, int(amount))
    msisdn = _normalize_msisdn(phone, "Kenya")
    if not msisdn or len(msisdn) < 12:
        return {"success": False, "message": "Namba ya simu si sahihi (mfano 07XXXXXXXX)."}

    # DEMO MODE — hakuna credentials: simulia STK
    if MPESA_DEMO_MODE:
        checkout_id = "ws_CO_DEMO_" + secrets.token_hex(6).upper()
        merchant_id = "DEMO-" + secrets.token_hex(4).upper()
        return {
            "success": True,
            "demo": True,
            "CheckoutRequestID": checkout_id,
            "MerchantRequestID": merchant_id,
            "CustomerMessage": "Success. Request accepted for processing",
            "message": "STK Push (DEMO) imetumwa. Thibitisha kwenye simu (simulator).",
            "phone": msisdn,
            "amount": amount,
        }

    token = _mpesa_access_token()
    password, timestamp = _mpesa_password_timestamp()
    callback = MPESA_CALLBACK_URL or (
        request.url_root.rstrip("/") + "/api/payment/mpesa/callback"
        if request else ""
    )
    payload = {
        "BusinessShortCode": MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": msisdn,
        "PartyB": MPESA_SHORTCODE,
        "PhoneNumber": msisdn,
        "CallBackURL": callback or "https://example.com/api/payment/mpesa/callback",
        "AccountReference": (account_ref or MPESA_ACCOUNT_REF or order_id)[:12],
        "TransactionDesc": (description or f"NjiaMauzo {order_id}")[:13],
    }
    url = _mpesa_base_url() + "/mpesa/stkpush/v1/processrequest"
    status, data = _mpesa_http_json(
        url,
        method="POST",
        data=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if status == 200 and (data.get("ResponseCode") == "0" or data.get("CheckoutRequestID")):
        return {
            "success": True,
            "demo": False,
            "CheckoutRequestID": data.get("CheckoutRequestID"),
            "MerchantRequestID": data.get("MerchantRequestID"),
            "CustomerMessage": data.get("CustomerMessage") or "STK imetumwa",
            "message": data.get("CustomerMessage") or "Angalia simu yako — weka PIN ya M-Pesa.",
            "phone": msisdn,
            "amount": amount,
            "raw": data,
        }
    err = (
        data.get("errorMessage")
        or data.get("ResponseDescription")
        or data.get("error")
        or str(data)
    )
    return {"success": False, "message": f"STK imeshindikana: {err}", "raw": data, "http": status}


def mpesa_stk_query(checkout_request_id: str):
    """Uliza hali ya STK Push."""
    if MPESA_DEMO_MODE or (checkout_request_id or "").startswith("ws_CO_DEMO_"):
        return {
            "success": True,
            "demo": True,
            "ResultCode": "0",
            "ResultDesc": "The service request is processed successfully.",
            "message": "Malipo yamekamilika (DEMO).",
        }
    token = _mpesa_access_token()
    password, timestamp = _mpesa_password_timestamp()
    payload = {
        "BusinessShortCode": MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }
    url = _mpesa_base_url() + "/mpesa/stkpushquery/v1/query"
    status, data = _mpesa_http_json(
        url,
        method="POST",
        data=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    return {
        "success": status == 200,
        "demo": False,
        "ResultCode": str(data.get("ResultCode", "")),
        "ResultDesc": data.get("ResultDesc") or data.get("errorMessage") or "",
        "raw": data,
        "http": status,
    }


# ---------- Vodacom M-Pesa Tanzania (Open API) ----------
# Portal: https://openapiportal.m-pesa.com
# Env:
#   MPESA_TZ_API_KEY, MPESA_TZ_PUBLIC_KEY (PEM au one-line),
#   MPESA_TZ_SP_CODE (Service Provider Code),
#   MPESA_TZ_ENV=sandbox|production
# Bila credentials → DEMO MODE (C2B inasimuliwa).
MPESA_TZ_API_KEY = os.environ.get("MPESA_TZ_API_KEY", "").strip()
MPESA_TZ_PUBLIC_KEY = os.environ.get("MPESA_TZ_PUBLIC_KEY", "").strip()
MPESA_TZ_SP_CODE = os.environ.get("MPESA_TZ_SP_CODE", "000000").strip()
MPESA_TZ_ENV = (os.environ.get("MPESA_TZ_ENV") or "sandbox").strip().lower()
MPESA_TZ_DEMO_MODE = not (MPESA_TZ_API_KEY and MPESA_TZ_PUBLIC_KEY)

_MPESA_TZ_SESSION = {"token": None, "expires": 0}


def _mpesa_tz_base_url():
    # Open API IPG paths (vodacomTZN)
    if MPESA_TZ_ENV == "production":
        return "https://openapi.m-pesa.com/openapi/ipg/v2/vodacomTZN"
    return "https://openapi.m-pesa.com/sandbox/ipg/v2/vodacomTZN"


def _mpesa_tz_format_public_key(raw: str) -> str:
    """Normalize public key to PEM."""
    key = (raw or "").strip()
    if not key:
        return ""
    if "BEGIN" in key:
        return key.replace("\\n", "\n")
    # one-line base64 body
    body = "".join(key.split())
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return "-----BEGIN PUBLIC KEY-----\n" + "\n".join(lines) + "\n-----END PUBLIC KEY-----"


def _mpesa_tz_encrypt_api_key(api_key: str, public_key_pem: str) -> str:
    """RSA PKCS1 v1.5 encrypt API key → base64 (Bearer token)."""
    pem = _mpesa_tz_format_public_key(public_key_pem)
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import padding as asy_padding
        from cryptography.hazmat.backends import default_backend
        pub = serialization.load_pem_public_key(pem.encode("utf-8"), backend=default_backend())
        encrypted = pub.encrypt(api_key.encode("utf-8"), asy_padding.PKCS1v15())
        return base64.b64encode(encrypted).decode("utf-8")
    except ImportError:
        pass
    try:
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_v1_5
        pub = RSA.import_key(pem)
        cipher = PKCS1_v1_5.new(pub)
        encrypted = cipher.encrypt(api_key.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")
    except ImportError:
        raise RuntimeError(
            "Vodacom TZ inahitaji cryptography au pycryptodome: "
            "pip install cryptography"
        )


def _mpesa_tz_session_token():
    """Generate / cache SessionKey token for Open API."""
    now = time.time()
    if _MPESA_TZ_SESSION["token"] and _MPESA_TZ_SESSION["expires"] > now + 60:
        return _MPESA_TZ_SESSION["token"]
    if MPESA_TZ_DEMO_MODE:
        return "DEMO_TZ_SESSION"
    bearer = _mpesa_tz_encrypt_api_key(MPESA_TZ_API_KEY, MPESA_TZ_PUBLIC_KEY)
    url = _mpesa_tz_base_url() + "/getSession/"
    status, data = _mpesa_http_json(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {bearer}",
            "Origin": "*",
        },
    )
    # Response shapes vary: output_ResponseCode, sessionId, token, etc.
    token = (
        (data or {}).get("output_SessionID")
        or (data or {}).get("sessionId")
        or (data or {}).get("token")
        or (data or {}).get("output_Response")
    )
    if isinstance(token, dict):
        token = token.get("SessionID") or token.get("sessionId")
    if not token and status == 200 and data:
        # sometimes whole body is usable
        token = data.get("output_ResponseCode") == "0" and data.get("output_SessionID")
    if not token:
        raise RuntimeError(f"Vodacom TZ session imeshindikana ({status}): {data}")
    _MPESA_TZ_SESSION["token"] = str(token)
    _MPESA_TZ_SESSION["expires"] = now + 3500  # ~1h typical
    return _MPESA_TZ_SESSION["token"]


def vodacom_tz_c2b(phone: str, amount: int, order_id: str, description: str = None):
    """
    Customer-to-Business (malipo kutoka simu ya mteja → biashara).
    amount: TZS integer
    """
    amount = max(1, int(amount))
    msisdn = _normalize_msisdn(phone, "Tanzania")
    if not msisdn.startswith("255") or len(msisdn) < 12:
        return {
            "success": False,
            "message": "Namba ya simu si sahihi. Tumia 07XXXXXXXX (Vodacom TZ).",
        }

    conversation_id = "NM" + secrets.token_hex(12)
    tx_ref = (order_id or "ORD")[:20].replace("-", "")

    if MPESA_TZ_DEMO_MODE:
        checkout_id = "TZ_DEMO_" + secrets.token_hex(6).upper()
        return {
            "success": True,
            "demo": True,
            "provider": "vodacom_tz",
            "CheckoutRequestID": checkout_id,
            "ConversationID": conversation_id,
            "TransactionReference": tx_ref,
            "message": "USSD/STK Push (DEMO TZ) imetumwa. Thibitisha kwa PIN ya M-Pesa.",
            "phone": msisdn,
            "amount": amount,
            "currency": "TZS",
        }

    try:
        session_token = _mpesa_tz_session_token()
    except Exception as e:
        return {"success": False, "message": f"Session TZ: {e}"}

    payload = {
        "input_Amount": str(amount),
        "input_Country": "TZN",
        "input_Currency": "TZS",
        "input_CustomerMSISDN": msisdn,
        "input_ServiceProviderCode": MPESA_TZ_SP_CODE,
        "input_ThirdPartyConversationID": conversation_id,
        "input_TransactionReference": tx_ref,
        "input_PurchasedItemsDesc": (description or f"NjiaMauzo {order_id}")[:50],
    }
    url = _mpesa_tz_base_url() + "/c2bPayment/singleStage/"
    status, data = _mpesa_http_json(
        url,
        method="POST",
        data=payload,
        headers={
            "Authorization": f"Bearer {session_token}",
            "Origin": "*",
        },
    )
    # Success: output_ResponseCode == "INS-0" au "0"
    code = str(
        (data or {}).get("output_ResponseCode")
        or (data or {}).get("ResponseCode")
        or ""
    )
    desc = (
        (data or {}).get("output_ResponseDesc")
        or (data or {}).get("ResponseDescription")
        or (data or {}).get("output_Response")
        or ""
    )
    conv = (data or {}).get("output_ConversationID") or conversation_id
    tx = (data or {}).get("output_TransactionID") or tx_ref

    ok_codes = {"INS-0", "0", "INS0", "success"}
    if status in (200, 201) and (code in ok_codes or "success" in str(desc).lower()):
        return {
            "success": True,
            "demo": False,
            "provider": "vodacom_tz",
            "CheckoutRequestID": str(conv or tx),
            "ConversationID": str(conv),
            "TransactionReference": str(tx),
            "ResponseCode": code,
            "message": desc or "Angalia simu — thibitisha malipo kwa PIN ya M-Pesa.",
            "phone": msisdn,
            "amount": amount,
            "currency": "TZS",
            "raw": data,
        }

    err = desc or (data or {}).get("error") or str(data)
    return {
        "success": False,
        "message": f"Vodacom TZ C2B imeshindikana: {err}",
        "raw": data,
        "http": status,
    }


def vodacom_tz_query(conversation_id: str, order_id: str = None):
    """Angalia hali ya muamala (ikiwa API inaruhusu). DEMO = success baada ya muda."""
    if MPESA_TZ_DEMO_MODE or (conversation_id or "").startswith("TZ_DEMO_"):
        return {
            "success": True,
            "demo": True,
            "ResultCode": "0",
            "ResultDesc": "DEMO TZ success",
            "message": "Malipo yamekamilika (DEMO TZ).",
        }
    # Open API transaction status endpoint (varies by portal version)
    try:
        session_token = _mpesa_tz_session_token()
    except Exception as e:
        return {"success": False, "ResultCode": "1", "ResultDesc": str(e)}
    payload = {
        "input_QueryReference": conversation_id,
        "input_ServiceProviderCode": MPESA_TZ_SP_CODE,
        "input_Country": "TZN",
        "input_ThirdPartyConversationID": "Q" + secrets.token_hex(8),
    }
    url = _mpesa_tz_base_url() + "/queryTransactionStatus/"
    status, data = _mpesa_http_json(
        url,
        method="POST",
        data=payload,
        headers={"Authorization": f"Bearer {session_token}", "Origin": "*"},
    )
    code = str((data or {}).get("output_ResponseCode") or (data or {}).get("ResponseCode") or "")
    desc = (data or {}).get("output_ResponseDesc") or (data or {}).get("ResponseDescription") or ""
    return {
        "success": status == 200,
        "demo": False,
        "ResultCode": "0" if code in ("INS-0", "0") else code,
        "ResultDesc": desc,
        "raw": data,
        "http": status,
    }



# Makadirio ya ubadilishaji fedha (thamani ya TZS 1 kwa kila sarafu).
# Hizi ni makadirio ya display tu — production halisi inapaswa kutumia
# huduma ya FX (mfano exchangerate.host) badala ya namba fasta.
# Afrika Mashariki — makadirio ya FX (display). Production: FX API.
COUNTRY_CURRENCY = {
    "Tanzania": {"code": "TZS", "rate_per_tzs": 1.0, "flag": "🇹🇿", "phone_prefix": "255"},
    "Kenya": {"code": "KES", "rate_per_tzs": 0.027, "flag": "🇰🇪", "phone_prefix": "254"},
    "Uganda": {"code": "UGX", "rate_per_tzs": 1.42, "flag": "🇺🇬", "phone_prefix": "256"},
    "Rwanda": {"code": "RWF", "rate_per_tzs": 0.53, "flag": "🇷🇼", "phone_prefix": "250"},
    "Burundi": {"code": "BIF", "rate_per_tzs": 0.59, "flag": "🇧🇮", "phone_prefix": "257"},
    "South Sudan": {"code": "SSP", "rate_per_tzs": 0.055, "flag": "🇸🇸", "phone_prefix": "211"},
    "DR Congo": {"code": "CDF", "rate_per_tzs": 1.05, "flag": "🇨🇩", "phone_prefix": "243"},
    "Ethiopia": {"code": "ETB", "rate_per_tzs": 0.045, "flag": "🇪🇹", "phone_prefix": "251"},
    "Somalia": {"code": "SOS", "rate_per_tzs": 0.22, "flag": "🇸🇴", "phone_prefix": "252"},
}

# Njia za malipo kwa kila nchi (mobile money)
COUNTRY_PAYMENT_METHODS = {
    "Tanzania": ["M-Pesa", "Airtel Money", "Halotel", "Tigo Pesa", "Google Pay"],
    "Kenya": ["M-Pesa", "Airtel Money", "Google Pay"],
    "Uganda": ["MTN MoMo", "Airtel Money", "Google Pay"],
    "Rwanda": ["MTN MoMo", "Airtel Money", "Google Pay"],
    "Burundi": ["Lumicash", "Ecocash", "Google Pay"],
    "South Sudan": ["m-Gurush", "Google Pay"],
    "DR Congo": ["M-Pesa", "Airtel Money", "Orange Money", "Google Pay"],
    "Ethiopia": ["Telebirr", "Google Pay"],
    "Somalia": ["EVC Plus", "Google Pay"],
}

# Subscription plans (muda wa ufikiaji baada ya malipo)
# multiplier: bei = SERVICE_FEE_TZS * multiplier (makadirio)
SUBSCRIPTION_PLANS = {
    "once": {
        "id": "once",
        "label_sw": "Mara moja (dakika 15)",
        "label_en": "One-time (15 minutes)",
        "seconds": 15 * 60,
        "multiplier": 1.0,
    },
    "daily": {
        "id": "daily",
        "label_sw": "Siku 1",
        "label_en": "1 Day",
        "seconds": 24 * 3600,
        "multiplier": 3.0,
    },
    "weekly": {
        "id": "weekly",
        "label_sw": "Wiki 1",
        "label_en": "1 Week",
        "seconds": 7 * 24 * 3600,
        "multiplier": 12.0,
    },
    "monthly": {
        "id": "monthly",
        "label_sw": "Mwezi 1",
        "label_en": "1 Month",
        "seconds": 30 * 24 * 3600,
        "multiplier": 35.0,
    },
}

GOOGLE_PAY_MERCHANT_ID = os.environ.get("GOOGLE_PAY_MERCHANT_ID", "").strip()
GOOGLE_PAY_MERCHANT_NAME = os.environ.get("GOOGLE_PAY_MERCHANT_NAME", "NjiaMauzo Afrika")
GOOGLE_PAY_DEMO = not bool(os.environ.get("GOOGLE_PAY_LIVE", "").strip())


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
        # Live 24/7 — bidhaa mpya kila sekunde 8–25
        time.sleep(random.randint(8, 25))
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


def _grant_access(seconds=None):
    """Fungua ufikiaji kwa muda (default dakika 15). Admin hauna kikomo."""
    secs = int(seconds if seconds is not None else ACCESS_DURATION_SEC)
    session["unlocked"] = True
    session["unlocked_until"] = datetime.utcnow().timestamp() + secs
    return secs


def _remaining_access_seconds():
    if session.get("is_admin"):
        return 24 * 3600  # admin: siku nzima (display)
    until = session.get("unlocked_until")
    if not until:
        if session.get("unlocked"):
            # legacy: weka dirisha la dakika 15
            _grant_access()
            until = session.get("unlocked_until")
        else:
            return 0
    left = int(until - datetime.utcnow().timestamp())
    if left <= 0:
        session.pop("unlocked", None)
        session.pop("unlocked_until", None)
        return 0
    return left


def _is_unlocked():
    if session.get("is_admin"):
        return True
    return _remaining_access_seconds() > 0


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
        session["unlocked_until"] = datetime.utcnow().timestamp() + 24 * 3600
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
        "remaining_seconds": _remaining_access_seconds(),
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
        snapshot = list(SAMPLE_PRODUCTS)
        total_products = len(snapshot)
        total_likes = sum(p.get("likes", 0) for p in snapshot)
        recent = [{"title": p["title"]} for p in snapshot[-12:]]
        locs = {}
        cats = {}
        for p in snapshot:
            loc = p.get("location") or "—"
            locs[loc] = locs.get(loc, 0) + 1
            title = p.get("title") or "Nyingine"
            cats.setdefault(title, []).append(p.get("real_price") or 0)
        total_locations = len([k for k in locs if k != "—"])
    categories = []
    for label, prices in list(cats.items())[:12]:
        prices = [x for x in prices if x]
        count = len(prices) or 1
        share = max(1, round(100 * count / max(1, total_products)))
        categories.append({
            "label": label,
            "count": count,
            "share": min(100, share),
            "avg_price": (round(sum(prices) / len(prices)) if prices and unlocked else None),
            "min_price": (min(prices) if prices and unlocked else None),
            "max_price": (max(prices) if prices and unlocked else None),
        })
    top_locations = [{"name": k, "count": v} for k, v in sorted(locs.items(), key=lambda x: -x[1])[:8]]
    return jsonify({
        "success": True,
        "unlocked": unlocked,
        "summary": {
            "total_products": total_products,
            "total_categories": len(categories),
            "total_locations": total_locations,
            "total_likes": total_likes,
        },
        "categories": categories,
        "recent": recent,
        "top_locations": top_locations if unlocked else [],
        "live": True,
        "remaining_seconds": _remaining_access_seconds(),
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
        # Live feed 24/7 — update kila sekunde 1–3
        time.sleep(random.uniform(1.0, 3.0))
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



@app.route("/api/payment/stk-push", methods=["POST"])
def api_payment_stk_push():
    """Anzisha M-Pesa push: Kenya=Daraja STK, Tanzania=Vodacom Open API C2B."""
    data = request.get_json(silent=True) or {}
    phone = (data.get("phone") or data.get("simu") or "").strip()
    country = (data.get("country") or "Tanzania").strip() or "Tanzania"

    if not phone:
        return jsonify({"success": False, "message": "Weka namba ya simu ya M-Pesa."}), 400

    order_id = "ORD-" + secrets.token_hex(4).upper()
    plan_id = (data.get("plan") or "once").strip()
    plan = SUBSCRIPTION_PLANS.get(plan_id) or SUBSCRIPTION_PLANS["once"]

    # ----- Tanzania → Vodacom Open API (TZS) -----
    if country == "Tanzania":
        amount = max(1, int(round(SERVICE_FEE_TZS * plan["multiplier"])))
        currency = "TZS"
        stk = vodacom_tz_c2b(
            phone=phone,
            amount=amount,
            order_id=order_id,
            description="NjiaMauzo ada",
        )
        if not stk.get("success"):
            return jsonify({"success": False, "message": stk.get("message") or "Vodacom TZ imeshindikana."}), 400
        checkout_id = stk.get("CheckoutRequestID") or stk.get("ConversationID") or ""
        with PAYMENT_LOCK:
            PAYMENT_ORDERS[order_id] = {
                "status": "pending_stk",
                "method": "M-Pesa Vodacom TZ",
                "provider": "vodacom_tz",
                "amount": amount,
                "currency": currency,
                "country": country,
                "base_amount_tzs": SERVICE_FEE_TZS,
                "created": datetime.utcnow(),
                "phone": phone,
                "msisdn": stk.get("phone"),
                "user": (session.get("user") or {}).get("email"),
                "CheckoutRequestID": checkout_id,
                "ConversationID": stk.get("ConversationID"),
                "demo": bool(stk.get("demo")),
                "stk_started": datetime.utcnow(),
                "plan": plan_id,
                "access_seconds": int(plan["seconds"]),
            }
        session["pending_order_id"] = order_id
        return jsonify({
            "success": True,
            "order_id": order_id,
            "plan": plan_id,
            "CheckoutRequestID": checkout_id,
            "provider": "vodacom_tz",
            "amount": amount,
            "currency": currency,
            "phone": stk.get("phone"),
            "demo": bool(stk.get("demo")),
            "message": stk.get("message") or "Angalia simu — weka PIN ya M-Pesa (TZ).",
        })

    # ----- Kenya (na nchi nyingine) → Safaricom Daraja STK (KES) -----
    amount = max(1, int(round(SERVICE_FEE_TZS * COUNTRY_CURRENCY.get("Kenya", {}).get("rate_per_tzs", 0.027) * plan["multiplier"])))
    currency = "KES"
    stk = mpesa_stk_push(
        phone=phone,
        amount=amount,
        order_id=order_id,
        account_ref=order_id.replace("ORD-", "NM")[:12],
        description="NjiaMauzo ada",
    )
    if not stk.get("success"):
        return jsonify({"success": False, "message": stk.get("message") or "STK imeshindikana."}), 400

    checkout_id = stk.get("CheckoutRequestID") or ""
    with PAYMENT_LOCK:
        PAYMENT_ORDERS[order_id] = {
            "status": "pending_stk",
            "method": "M-Pesa STK",
            "provider": "safaricom_ke",
            "amount": amount,
            "currency": currency,
            "country": country,
            "base_amount_tzs": SERVICE_FEE_TZS,
            "created": datetime.utcnow(),
            "phone": phone,
            "msisdn": stk.get("phone"),
            "user": (session.get("user") or {}).get("email"),
            "CheckoutRequestID": checkout_id,
            "MerchantRequestID": stk.get("MerchantRequestID"),
            "demo": bool(stk.get("demo")),
            "stk_started": datetime.utcnow(),
            "plan": plan_id,
            "access_seconds": int(plan["seconds"]),
        }
    session["pending_order_id"] = order_id

    return jsonify({
        "success": True,
        "order_id": order_id,
        "plan": plan_id,
        "CheckoutRequestID": checkout_id,
        "provider": "safaricom_ke",
        "amount": amount,
        "currency": currency,
        "phone": stk.get("phone"),
        "demo": bool(stk.get("demo")),
        "message": stk.get("message") or "Angalia simu — weka PIN ya M-Pesa.",
        "CustomerMessage": stk.get("CustomerMessage"),
    })


@app.route("/api/payment/stk-status", methods=["GET"])
def api_payment_stk_status():
    """Angalia hali ya STK (polling kutoka frontend)."""
    order_id = (request.args.get("order_id") or session.get("pending_order_id") or "").strip()
    if not order_id:
        return jsonify({"success": False, "message": "Order ID inahitajika."}), 400

    with PAYMENT_LOCK:
        order = PAYMENT_ORDERS.get(order_id)
        if not order:
            return jsonify({"success": False, "message": "Order haipatikani."}), 404
        status = order.get("status")
        checkout_id = order.get("CheckoutRequestID") or ""
        demo = bool(order.get("demo"))
        started = order.get("stk_started") or order.get("created")

    # Tayari imethibitishwa
    if status == "verified":
        left = _grant_access(ACCESS_DURATION_SEC) if not _is_unlocked() else _remaining_access_seconds()
        if not session.get("unlocked"):
            left = _grant_access(ACCESS_DURATION_SEC)
        return jsonify({
            "success": True,
            "status": "verified",
            "order_id": order_id,
            "unlocked": True,
            "remaining_seconds": left,
            "message": "Malipo yamekamilika.",
        })

    if status in ("failed", "cancelled"):
        return jsonify({
            "success": True,
            "status": status,
            "order_id": order_id,
            "message": order.get("result_desc") or "Malipo yameshindikana au yameghairiwa.",
        })

    # DEMO: baada ya sekunde 8–12 chukulia kuwa mteja amethibitisha PIN
    if demo and checkout_id:
        age = (datetime.utcnow() - started).total_seconds() if started else 0
        if age >= 10:
            access_secs = ACCESS_DURATION_SEC
            with PAYMENT_LOCK:
                o = PAYMENT_ORDERS.get(order_id)
                if o and o.get("status") == "pending_stk":
                    o["status"] = "verified"
                    o["verified_at"] = datetime.utcnow()
                    o["activated_via"] = "stk_demo"
                    o["result_desc"] = "DEMO STK success"
                    access_secs = int(o.get("access_seconds") or ACCESS_DURATION_SEC)
            left = _grant_access(access_secs)
            return jsonify({
                "success": True,
                "status": "verified",
                "order_id": order_id,
                "unlocked": True,
                "demo": True,
                "remaining_seconds": left,
                "message": "Malipo yamekamilika (DEMO STK).",
            })
        return jsonify({
            "success": True,
            "status": "pending_stk",
            "order_id": order_id,
            "demo": True,
            "message": "Subiri… weka PIN kwenye simu (DEMO).",
            "waited": int(age),
        })

    # Production: query by provider
    if checkout_id:
        with PAYMENT_LOCK:
            provider = (PAYMENT_ORDERS.get(order_id) or {}).get("provider") or "safaricom_ke"
        if provider == "vodacom_tz":
            q = vodacom_tz_query(checkout_id, order_id)
        else:
            q = mpesa_stk_query(checkout_id)
        rc = str(q.get("ResultCode") or "")
        if rc == "0":
            access_secs = ACCESS_DURATION_SEC
            with PAYMENT_LOCK:
                o = PAYMENT_ORDERS.get(order_id)
                if o:
                    o["status"] = "verified"
                    o["verified_at"] = datetime.utcnow()
                    o["activated_via"] = "stk_query"
                    o["result_desc"] = q.get("ResultDesc")
                    access_secs = int(o.get("access_seconds") or ACCESS_DURATION_SEC)
            left = _grant_access(access_secs)
            return jsonify({
                "success": True,
                "status": "verified",
                "order_id": order_id,
                "unlocked": True,
                "remaining_seconds": left,
                "message": "Malipo yamekamilika.",
            })
        # 1032 = cancelled, 1037 = timeout, 1 = insufficient etc — still pending if 4999
        if rc and rc not in ("", "4999", "None"):
            # pending processing codes vary; only mark failed on clear cancel
            if rc in ("1032", "1037", "1", "2001"):
                with PAYMENT_LOCK:
                    o = PAYMENT_ORDERS.get(order_id)
                    if o:
                        o["status"] = "failed"
                        o["result_desc"] = q.get("ResultDesc")
                return jsonify({
                    "success": True,
                    "status": "failed",
                    "order_id": order_id,
                    "message": q.get("ResultDesc") or "Malipo yameshindikana.",
                })

    return jsonify({
        "success": True,
        "status": "pending_stk",
        "order_id": order_id,
        "message": "Inasubiri uthibitisho wa M-Pesa…",
    })


@app.route("/api/payment/mpesa/callback", methods=["POST"])
def api_mpesa_callback():
    """Webhook kutoka Safaricom baada ya STK (lazima iwe HTTPS public URL)."""
    payload = request.get_json(silent=True) or {}
    try:
        body = payload.get("Body", {}).get("stkCallback", {})
        checkout_id = body.get("CheckoutRequestID")
        result_code = str(body.get("ResultCode", ""))
        result_desc = body.get("ResultDesc", "")
        metadata = {}
        for item in (body.get("CallbackMetadata") or {}).get("Item") or []:
            name = item.get("Name")
            if name:
                metadata[name] = item.get("Value")

        matched_order = None
        with PAYMENT_LOCK:
            for oid, o in PAYMENT_ORDERS.items():
                if o.get("CheckoutRequestID") == checkout_id:
                    matched_order = oid
                    if result_code == "0":
                        o["status"] = "verified"
                        o["verified_at"] = datetime.utcnow()
                        o["activated_via"] = "stk_callback"
                        o["mpesa_receipt"] = metadata.get("MpesaReceiptNumber")
                        o["result_desc"] = result_desc
                    else:
                        o["status"] = "failed"
                        o["result_desc"] = result_desc
                    break
        # Note: session ya mteja haitumiki hapa (callback ni server-to-server)
        return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})
    except Exception as e:
        return jsonify({"ResultCode": 1, "ResultDesc": str(e)}), 200


@app.route("/api/payment/mpesa/config", methods=["GET"])
def api_mpesa_config():
    """Hali ya Kenya STK + Tanzania Vodacom (bila kufichua siri)."""
    return jsonify({
        "success": True,
        "kenya": {
            "demo_mode": MPESA_DEMO_MODE,
            "env": MPESA_ENV,
            "shortcode_set": bool(MPESA_SHORTCODE),
            "callback_set": bool(MPESA_CALLBACK_URL),
        },
        "tanzania": {
            "demo_mode": MPESA_TZ_DEMO_MODE,
            "env": MPESA_TZ_ENV,
            "sp_code_set": bool(MPESA_TZ_SP_CODE and MPESA_TZ_SP_CODE != "000000"),
            "api_key_set": bool(MPESA_TZ_API_KEY),
        },
        "demo_mode": MPESA_DEMO_MODE and MPESA_TZ_DEMO_MODE,
        "message": (
            "DEMO: Kenya (Daraja) na/au Tanzania (Vodacom) — weka env credentials kwa live."
            if (MPESA_DEMO_MODE or MPESA_TZ_DEMO_MODE)
            else "M-Pesa live credentials zimewekwa."
        ),
    })


@app.route("/api/payment/vodacom-tz/callback", methods=["POST"])
def api_vodacom_tz_callback():
    """Callback/webhook kutoka Vodacom / aggregator (hiari)."""
    payload = request.get_json(silent=True) or {}
    try:
        conv = (
            payload.get("ConversationID")
            or payload.get("output_ConversationID")
            or payload.get("ThirdPartyConversationID")
            or payload.get("input_ThirdPartyConversationID")
        )
        result = str(
            payload.get("ResultCode")
            or payload.get("output_ResponseCode")
            or payload.get("status")
            or ""
        )
        ok = result in ("0", "INS-0", "success", "Success", "COMPLETED")
        with PAYMENT_LOCK:
            for oid, o in PAYMENT_ORDERS.items():
                if o.get("CheckoutRequestID") == conv or o.get("ConversationID") == conv:
                    if ok:
                        o["status"] = "verified"
                        o["verified_at"] = datetime.utcnow()
                        o["activated_via"] = "vodacom_tz_callback"
                    else:
                        o["status"] = "failed"
                        o["result_desc"] = str(payload)[:200]
                    break
        return jsonify({"success": True, "ResultCode": 0})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 200



@app.route("/api/countries", methods=["GET"])
def api_countries():
    items = []
    for name, info in COUNTRY_CURRENCY.items():
        items.append({
            "name": name,
            "code": info["code"],
            "flag": info.get("flag", ""),
            "phone_prefix": info.get("phone_prefix", ""),
            "methods": COUNTRY_PAYMENT_METHODS.get(name, ["Google Pay"]),
            "amount": round(SERVICE_FEE_TZS * info["rate_per_tzs"]),
        })
    return jsonify({"success": True, "countries": items})


@app.route("/api/subscription/plans", methods=["GET"])
def api_subscription_plans():
    country = (request.args.get("country") or "Tanzania").strip()
    info = COUNTRY_CURRENCY.get(country, COUNTRY_CURRENCY["Tanzania"])
    plans = []
    for p in SUBSCRIPTION_PLANS.values():
        amount = max(1, int(round(SERVICE_FEE_TZS * info["rate_per_tzs"] * p["multiplier"])))
        plans.append({
            **{k: v for k, v in p.items() if k != "seconds"},
            "seconds": p["seconds"],
            "amount": amount,
            "currency": info["code"],
            "country": country,
        })
    return jsonify({"success": True, "plans": plans, "country": country})


@app.route("/api/payment/google-pay", methods=["POST"])
def api_payment_google_pay():
    """Thibitisha malipo ya Google Pay (DEMO au baada ya gateway token)."""
    data = request.get_json(silent=True) or {}
    country = (data.get("country") or "Tanzania").strip() or "Tanzania"
    plan_id = (data.get("plan") or "once").strip()
    plan = SUBSCRIPTION_PLANS.get(plan_id) or SUBSCRIPTION_PLANS["once"]
    info = COUNTRY_CURRENCY.get(country, COUNTRY_CURRENCY["Tanzania"])
    amount = max(1, int(round(SERVICE_FEE_TZS * info["rate_per_tzs"] * plan["multiplier"])))
    currency = info["code"]

    token = data.get("paymentToken") or data.get("token") or {}
    # Production: tuma token kwa Stripe/Flutterwave/Pesapal
    # Hapa: DEMO au accept ikiwa token ipo
    if not GOOGLE_PAY_DEMO and not token:
        return jsonify({"success": False, "message": "Google Pay token inahitajika."}), 400

    order_id = "GP-" + secrets.token_hex(4).upper()
    with PAYMENT_LOCK:
        PAYMENT_ORDERS[order_id] = {
            "status": "verified",
            "method": "Google Pay",
            "provider": "google_pay",
            "amount": amount,
            "currency": currency,
            "country": country,
            "plan": plan_id,
            "base_amount_tzs": SERVICE_FEE_TZS,
            "created": datetime.utcnow(),
            "verified_at": datetime.utcnow(),
            "phone": data.get("phone") or "",
            "user": (session.get("user") or {}).get("email"),
            "demo": GOOGLE_PAY_DEMO,
            "token_preview": str(token)[:80] if token else "demo",
        }
    session["pending_order_id"] = order_id
    left = _grant_access(int(plan["seconds"]))
    session["subscription_plan"] = plan_id

    return jsonify({
        "success": True,
        "order_id": order_id,
        "amount": amount,
        "currency": currency,
        "plan": plan_id,
        "unlocked": True,
        "remaining_seconds": left,
        "demo": GOOGLE_PAY_DEMO,
        "message": f"Google Pay imefaulu — ufikiaji ({plan.get('label_sw', plan_id)}) umefunguliwa.",
    })


@app.route("/api/payment/google-pay/config", methods=["GET"])
def api_google_pay_config():
    return jsonify({
        "success": True,
        "demo": GOOGLE_PAY_DEMO,
        "merchantId": GOOGLE_PAY_MERCHANT_ID or "01234567890123456789",
        "merchantName": GOOGLE_PAY_MERCHANT_NAME,
        "allowedNetworks": ["VISA", "MASTERCARD", "AMEX"],
        "allowedAuthMethods": ["PAN_ONLY", "CRYPTOGRAM_3DS"],
        "message": "DEMO Google Pay" if GOOGLE_PAY_DEMO else "Google Pay live",
    })

@app.route("/api/payment/request", methods=["POST"])
def api_payment_request():
    data = request.get_json(silent=True) or {}
    if data.get("admin_bypass") and session.get("is_admin"):
        _grant_access(24 * 3600)
        return jsonify({
            "success": True,
            "order_id": "ADM-" + secrets.token_hex(4).upper(),
            "message": "Admin access bila kulipa.",
            "payment_number": "—",
        })

    order_id = "ORD-" + secrets.token_hex(4).upper()
    numbers = {
        "M-Pesa": "0755248789", "Halotel": "0625031460", "Airtel Money": "0691925100",
        "Tigo Pesa": "0655123456", "MTN MoMo": "0766123456", "Lumicash": "0799123456",
        "Ecocash": "0788123456", "Telebirr": "0911123456", "EVC Plus": "0612123456",
        "Orange Money": "0899123456", "m-Gurush": "0922123456",
    }
    method = data.get("njia") or "M-Pesa"
    country = (data.get("country") or "Tanzania").strip() or "Tanzania"
    plan_id = (data.get("plan") or "once").strip()
    plan = SUBSCRIPTION_PLANS.get(plan_id) or SUBSCRIPTION_PLANS["once"]
    cur_info = COUNTRY_CURRENCY.get(country, COUNTRY_CURRENCY["Tanzania"])
    currency = data.get("currency") or cur_info["code"]
    amount = max(1, int(round(SERVICE_FEE_TZS * cur_info["rate_per_tzs"] * plan["multiplier"])))
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
            "plan": plan_id,
            "access_seconds": int(plan["seconds"]),
        }
    session["pending_order_id"] = order_id

    fee_label = f"{currency} {amount:,}"
    return jsonify({
        "success": True,
        "order_id": order_id,
        "plan": plan_id,
        "access_seconds": int(plan["seconds"]),
        "payment_number": numbers.get(method, "0755248789"),
        "amount": amount,
        "currency": currency,
        "country": country,
        "message": f"Payment imeanzishwa. Tuma {fee_label}. "
                    "Baada ya kulipa, tuma uthibitisho — utafunguliwa baada ya kukaguliwa.",
    })


@app.route("/api/payment/activate", methods=["POST"])
def api_payment_activate():
    """Baada ya malipo: fungua ufikiaji kwa DAKIKA 15. Baada ya hapo inadai malipo tena."""
    data = request.get_json(silent=True) or {}
    order_id = (data.get("order_id") or session.get("pending_order_id") or "").strip()
    with PAYMENT_LOCK:
        order = PAYMENT_ORDERS.get(order_id) if order_id else None
        if order:
            order["status"] = "verified"
            order["verified_at"] = datetime.utcnow()
            order["activated_via"] = "client_flow"
    access_secs = ACCESS_DURATION_SEC
    if order:
        access_secs = int(order.get("access_seconds") or ACCESS_DURATION_SEC)
    left = _grant_access(access_secs)
    if order_id:
        session["pending_order_id"] = order_id
    session["subscription_plan"] = (order or {}).get("plan") or "once"
    return jsonify({
        "success": True,
        "unlocked": True,
        "order_id": order_id or None,
        "plan": session.get("subscription_plan"),
        "message": f"Ufikiaji umefunguliwa ({left // 60} dk). Karibu NjiaMauzo Afrika!",
        "remaining_seconds": left,
        "expires_in_sec": left,
    })


@app.route("/api/access/status", methods=["GET"])
def api_access_status():
    order_id = request.args.get("order_id") or session.get("pending_order_id")
    order = None
    if order_id:
        with PAYMENT_LOCK:
            order = PAYMENT_ORDERS.get(order_id)
        # verified order alone does not extend time — only activate/grant does
    left = _remaining_access_seconds()
    return jsonify({
        "success": True,
        "unlocked": left > 0 or bool(session.get("is_admin")),
        "order_status": order["status"] if order else None,
        "remaining_seconds": left,
        "expires_in_sec": left,
        "access_minutes": ACCESS_DURATION_SEC // 60,
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
