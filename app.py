# =========================================================
# NJIA MAUZO AFRIKA
# AI PRODUCT FINDER + 24/7 BOT CHAT + ADMIN WHATSAPP
# =========================================================

import os
import json
import urllib.request
import urllib.error


# =========================================================
# WHATSAPP CONFIGURATION
# Render → Environment Variables
# =========================================================

WHATSAPP_API_URL = os.environ.get(
    "WHATSAPP_API_URL",
    ""
).strip()

WHATSAPP_API_TOKEN = os.environ.get(
    "WHATSAPP_API_TOKEN",
    ""
).strip()

# Admin WhatsApp:
# M-Pesa: 0755 248 789
# International format: 255755248789

ADMIN_WHATSAPP_NUMBER = os.environ.get(
    "ADMIN_WHATSAPP_NUMBER",
    "255755248789"
).strip()


# =========================================================
# HELPER
# =========================================================

def _clean_text(value, max_length=1000):
    """
    Safely sanitize text.
    Inatumia sanitize_text iliyopo kwenye app.py kama ipo.
    """
    try:
        return sanitize_text(
            str(value or ""),
            max_length
        ).strip()
    except Exception:
        return str(value or "").strip()[:max_length]


# =========================================================
# WHATSAPP ADMIN NOTIFICATION
# =========================================================

def notify_admin_whatsapp(
    user_message: str,
    bot_reply: str
) -> bool:
    """
    Inatuma notification kwenda WhatsApp ya admin.

    Ikiwa WhatsApp API haijawekwa:
    - mfumo hau-crash
    - bot bado anajibu
    - error inawekwa kwenye log
    """

    # -----------------------------------------------------
    # CHECK CONFIGURATION
    # -----------------------------------------------------

    if not WHATSAPP_API_URL:
        app.logger.warning(
            "WHATSAPP_API_URL haijawekwa."
        )
        return False

    if not WHATSAPP_API_TOKEN:
        app.logger.warning(
            "WHATSAPP_API_TOKEN haijawekwa."
        )
        return False

    if not ADMIN_WHATSAPP_NUMBER:
        app.logger.warning(
            "ADMIN_WHATSAPP_NUMBER haijawekwa."
        )
        return False

    # -----------------------------------------------------
    # CLEAN DATA
    # -----------------------------------------------------

    safe_user_message = _clean_text(
        user_message,
        1000
    )

    safe_bot_reply = _clean_text(
        bot_reply,
        1000
    )

    # -----------------------------------------------------
    # WHATSAPP MESSAGE
    # -----------------------------------------------------

    whatsapp_message = (
        "🔔 NJIA MAUZO AFRIKA\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 UJUMBE MPYA WA MTUMIAJI\n\n"
        f"{safe_user_message}\n\n"
        "🤖 BOT AMEJIBU\n\n"
        f"{safe_bot_reply}\n\n"
        "💰 Ada ya AI Product Finder: TZS 3,000\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    # -----------------------------------------------------
    # GENERIC PAYLOAD
    # -----------------------------------------------------

    payload = {
        "to": ADMIN_WHATSAPP_NUMBER,
        "message": whatsapp_message
    }

    # -----------------------------------------------------
    # SEND REQUEST
    # -----------------------------------------------------

    try:

        request_data = json.dumps(
            payload,
            ensure_ascii=False
        ).encode("utf-8")

        req = urllib.request.Request(
            WHATSAPP_API_URL,
            data=request_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": (
                    f"Bearer {WHATSAPP_API_TOKEN}"
                )
            },
            method="POST"
        )

        with urllib.request.urlopen(
            req,
            timeout=8
        ) as response:

            status = response.status

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        if 200 <= status < 300:

            app.logger.info(
                "WhatsApp admin notification sent."
            )

            return True

        # -------------------------------------------------
        # FAILED STATUS
        # -------------------------------------------------

        app.logger.warning(
            "WhatsApp API returned HTTP %s",
            status
        )

        return False

    except urllib.error.HTTPError as e:

        app.logger.warning(
            "WhatsApp HTTP error: %s",
            e
        )

        return False

    except urllib.error.URLError as e:

        app.logger.warning(
            "WhatsApp URL error: %s",
            e
        )

        return False

    except TimeoutError:

        app.logger.warning(
            "WhatsApp request timed out."
        )

        return False

    except OSError as e:

        app.logger.warning(
            "WhatsApp network error: %s",
            e
        )

        return False

    except Exception as e:

        app.logger.exception(
            "Unexpected WhatsApp error: %s",
            e
        )

        return False


# =========================================================
# AI PRODUCT FINDER
# GET /api/ai-products?q=ufuta
# =========================================================

@app.get("/api/ai-products")
@rate_limit(
    "ai_products",
    max_calls=30,
    window_seconds=60
)
def ai_products():

    """
    AI Product Finder.

    Examples:

        /api/ai-products?q=ufuta
        /api/ai-products?q=mahindi
        /api/ai-products?q=Ruvuma

    Inatafuta bidhaa kwenye listings database.
    """

    # -----------------------------------------------------
    # GET SEARCH QUERY
    # -----------------------------------------------------

    q = _clean_text(
        request.args.get("q", ""),
        100
    ).lower()

    try:

        rows = db().execute(
            """
            SELECT *
            FROM listings
            ORDER BY id DESC
            """
        ).fetchall()

    except Exception as e:

        app.logger.exception(
            "AI Product Finder database error: %s",
            e
        )

        return jsonify({
            "success": False,
            "error": (
                "Imeshindikana kupata bidhaa "
                "kwa sasa."
            ),
            "products": []
        }), 500

    # -----------------------------------------------------
    # SEARCH RESULTS
    # -----------------------------------------------------

    products = []

    for r in rows:

        try:

            crop = str(
                r["crop"]
                if r["crop"] is not None
                else ""
            )

            location = str(
                r["location"]
                if r["location"] is not None
                else ""
            )

            country = str(
                r["country"]
                if r["country"] is not None
                else ""
            )

            price = r["price"]

        except Exception:

            continue

        # -------------------------------------------------
        # SEARCH TEXT
        # -------------------------------------------------

        search_blob = (
            f"{crop} "
            f"{location} "
            f"{country}"
        ).lower()

        # -------------------------------------------------
        # FILTER
        # -------------------------------------------------

        if q and q not in search_blob:
            continue

        # -------------------------------------------------
        # FORMAT PRICE
        # -------------------------------------------------

        try:

            formatted_price = (
                f"TZS {float(price):,.0f}/kg"
            )

        except (
            TypeError,
            ValueError
        ):

            formatted_price = "Bei haijawekwa"

        # -------------------------------------------------
        # SOURCE
        # -------------------------------------------------

        source = location

        if country:

            source = (
                f"{location}, {country}"
                if location
                else country
            )

        # -------------------------------------------------
        # PRODUCT
        # -------------------------------------------------

        products.append({
            "jina": crop or "Bidhaa",
            "picha": "/static/favicon.png",
            "chanzo": source,
            "bei": formatted_price
        })

        # -------------------------------------------------
        # LIMIT
        # -------------------------------------------------

        if len(products) >= 20:
            break

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return jsonify({
        "success": True,
        "products": products,
        "count": len(products)
    })


# =========================================================
# 24/7 BOT CHAT
# POST /api/bot-chat
# =========================================================

@app.post("/api/bot-chat")
@rate_limit(
    "bot_chat",
    max_calls=40,
    window_seconds=60
)
def bot_chat():

    """
    24/7 NjiaMauzo Afrika Bot.

    Kwa sasa ni rule-based.
    Inaweza kuunganishwa na AI API baadaye.
    """

    # -----------------------------------------------------
    # GET JSON
    # -----------------------------------------------------

    data = request.get_json(
        silent=True
    ) or {}

    message = _clean_text(
        data.get("message", ""),
        500
    )

    # -----------------------------------------------------
    # VALIDATE
    # -----------------------------------------------------

    if not message:

        return jsonify({
            "success": False,
            "error": "Andika ujumbe."
        }), 400

    ml = message.lower()

    # -----------------------------------------------------
    # BOT RESPONSES
    # -----------------------------------------------------

    if any(
        word in ml
        for word in [
            "bei",
            "price",
            "gharama",
            "market",
            "soko",
            "masoko"
        ]
    ):

        reply = (
            "Nenda sehemu ya Bei kulinganisha "
            "bei za masoko, au tumia Profit AI "
            "kukokotoa faida."
        )

    elif any(
        crop in ml
        for crop in [
            "ufuta",
            "mahindi",
            "maharage",
            "maharagwe",
            "mpunga",
            "korosho",
            "karanga",
            "soya",
            "mtama",
            "dengu"
        ]
    ):

        reply = (
            "Tunayo listings za zao hilo kwenye "
            "mfumo. Bonyeza 'Tazama Bidhaa (AI)' "
            "kuona bidhaa zilizopo sasa."
        )

    elif any(
        word in ml
        for word in [
            "malipo",
            "ada",
            "lipa",
            "payment",
            "gharama ya kutafuta"
        ]
    ):

        reply = (
            "Huduma ya kutafutiwa bidhaa ni "
            "TZS 3,000. Bonyeza "
            "'KARIBU GUSA HAPA TUKUHUDUMIE' "
            "kuendelea na malipo."
        )

    elif any(
        word in ml
        for word in [
            "asante",
            "ahsante",
            "sawa",
            "poa"
        ]
    ):

        reply = (
            "Karibu sana! Nipo hapa muda wote "
            "kukusaidia kupata bidhaa na "
            "taarifa za masoko."
        )

    elif any(
        word in ml
        for word in [
            "habari",
            "hello",
            "hi",
            "mambo"
        ]
    ):

        reply = (
            "Karibu NjiaMauzo Afrika! 👋 "
            "Unatafuta zao gani, kiasi gani, "
            "eneo gani, au bei gani?"
        )

    else:

        reply = (
            "Nimepokea ujumbe wako. "
            "Niambie zao unalotafuta, "
            "kiasi unachohitaji, eneo, "
            "au bei unayotaka.\n\n"
            "Mfano: Natafuta tani 20 za ufuta "
            "Ruvuma chini ya TZS 3,200/kg."
        )

    # -----------------------------------------------------
    # ADMIN NOTIFICATION
    # -----------------------------------------------------

    try:

        notify_admin_whatsapp(
            user_message=message,
            bot_reply=reply
        )

    except Exception as e:

        # WhatsApp is optional.
        # Bot lazima aendelee kufanya kazi.

        app.logger.warning(
            "Admin notification skipped: %s",
            e
        )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return jsonify({
        "success": True,
        "reply": reply
    })


# =========================================================
# ADMIN NOTIFICATION ENDPOINT
# POST /api/notify-admin
# =========================================================

@app.post("/api/notify-admin")
@rate_limit(
    "notify_admin",
    max_calls=20,
    window_seconds=60
)
def notify_admin_endpoint():

    """
    Endpoint ya admin notification.

    Frontend inaweza kuitumia kutuma:
        user_message
        bot_reply
    """

    data = request.get_json(
        silent=True
    ) or {}

    user_message = _clean_text(
        data.get("user_message", ""),
        1000
    )

    bot_reply = _clean_text(
        data.get("bot_reply", ""),
        1000
    )

    if not user_message:

        return jsonify({
            "success": False,
            "ok": False,
            "error": "user_message inahitajika."
        }), 400

    ok = notify_admin_whatsapp(
        user_message=user_message,
        bot_reply=bot_reply
    )

    return jsonify({
        "success": True,
        "ok": ok
    })


# =========================================================
# END
# AI PRODUCT FINDER
# 24/7 BOT CHAT
# ADMIN WHATSAPP NOTIFICATION
# =========================================================
