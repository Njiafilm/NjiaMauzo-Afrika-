# =========================================================
# AI PRODUCT FINDER + 24/7 BOT CHAT + ADMIN WHATSAPP NOTIFY
# NjiaMauzo Afrika
# =========================================================

import os
import json
import urllib.request
import urllib.error


# =========================================================
# WHATSAPP CONFIGURATION
# Weka hizi kwenye Render → Environment Variables
# =========================================================

WHATSAPP_API_URL = os.environ.get(
    "WHATSAPP_API_URL",
    ""
)

WHATSAPP_API_TOKEN = os.environ.get(
    "WHATSAPP_API_TOKEN",
    ""
)

# Admin WhatsApp:
# 0755 248 789 → 255755248789
ADMIN_WHATSAPP_NUMBER = os.environ.get(
    "ADMIN_WHATSAPP_NUMBER",
    "255755248789"
)


# =========================================================
# AI PRODUCT FINDER
# GET /api/ai-products?q=ufuta
# =========================================================

@app.get("/api/ai-products")
@rate_limit("ai_products", max_calls=30, window_seconds=60)
def ai_products():

    """
    AI Product Finder.

    Inatafuta bidhaa kutoka kwenye listings zilizopo
    kwenye database ya NjiaMauzo Afrika.

    Mfano:
        /api/ai-products?q=ufuta
        /api/ai-products?q=mahindi
        /api/ai-products?q=Ruvuma
    """

    q = sanitize_text(
        request.args.get("q", ""),
        100
    ).strip().lower()

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

        return jsonify(
            error="Imeshindikana kupata bidhaa kwa sasa."
        ), 500


    products = []

    for r in rows:

        # -------------------------------------------------
        # Safely read database values
        # -------------------------------------------------

        crop = str(
            r["crop"] if r["crop"] is not None else ""
        )

        location = str(
            r["location"] if r["location"] is not None else ""
        )

        country = str(
            r["country"] if r["country"] is not None else ""
        )

        price = r["price"]


        # -------------------------------------------------
        # Search blob
        # -------------------------------------------------

        blob = (
            f"{crop} "
            f"{location} "
            f"{country}"
        ).lower()


        # -------------------------------------------------
        # Filter
        # -------------------------------------------------

        if q and q not in blob:
            continue


        # -------------------------------------------------
        # Format price
        # -------------------------------------------------

        try:
            formatted_price = (
                f"TZS {float(price):,.0f}/kg"
            )
        except (TypeError, ValueError):
            formatted_price = "Bei haijawekwa"


        # -------------------------------------------------
        # Product result
        # -------------------------------------------------

        products.append({

            "jina": crop,

            "picha": "favicon.png",

            "chanzo": (
                f"{location}, {country}"
                if country
                else location
            ),

            "bei": formatted_price,

        })


    # -----------------------------------------------------
    # Return maximum 20 products
    # -----------------------------------------------------

    return jsonify(
        products=products[:20],
        count=len(products[:20])
    )


# =========================================================
# 24/7 BOT CHAT
# POST /api/bot-chat
# =========================================================

@app.post("/api/bot-chat")
@rate_limit("bot_chat", max_calls=40, window_seconds=60)
def bot_chat():

    """
    Bot ya NjiaMauzo Afrika inayopatikana 24/7.

    Kwa sasa inatumia rule-based responses.
    Inaweza kuunganishwa na AI API baadaye.
    """

    d = request.get_json(
        silent=True
    ) or {}


    message = sanitize_text(
        str(d.get("message", "")),
        500
    ).strip()


    if not message:

        return jsonify(
            error="Andika ujumbe."
        ), 400


    ml = message.lower()


    # =====================================================
    # BOT RESPONSES
    # =====================================================

    if any(
        word in ml
        for word in [
            "bei",
            "price",
            "gharama",
            "market"
        ]
    ):

        reply = (
            "Nenda sehemu ya Bei kulinganisha bei "
            "za masoko, au tumia Profit AI kukokotoa faida."
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
            "Tunayo listings za zao hilo kwenye mfumo. "
            "Bonyeza 'Tazama Bidhaa (AI)' kuona bidhaa "
            "zilizopo sasa."
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
            "Huduma ya kutafutiwa bidhaa ni TZS 3,000. "
            "Bonyeza 'KARIBU GUSA HAPA TUKUHUDUMIE' "
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
            "kukusaidia kupata bidhaa na taarifa za masoko."
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
            "Unatafuta zao gani, kiasi gani, eneo gani, "
            "au bei gani?"
        )


    else:

        reply = (
            "Nimepokea ujumbe wako. "
            "Niambie zao unalotafuta, kiasi unachohitaji, "
            "eneo, au bei unayotaka. "
            "Mfano: 'Natafuta tani 20 za ufuta Ruvuma "
            "chini ya TZS 3,200/kg.'"
        )


    # =====================================================
    # NOTIFY ADMIN WHATSAPP
    # Best-effort:
    # Ikiwa WhatsApp haijaunganishwa, bot bado itajibu.
    # =====================================================

    notify_admin_whatsapp(
        user_message=message,
        bot_reply=reply
    )


    # =====================================================
    # RESPONSE
    # =====================================================

    return jsonify(
        reply=reply
    )


# =========================================================
# ADMIN NOTIFICATION ENDPOINT
# POST /api/notify-admin
# =========================================================

@app.post("/api/notify-admin")
@rate_limit(
    "notify_admin",
    max_calls=40,
    window_seconds=60
)
def notify_admin_endpoint():

    """
    Endpoint ya kutuma notification kwa admin.

    Frontend inaweza kuitumia kama inahitaji
    kutuma user_message na bot_reply moja kwa moja.
    """

    d = request.get_json(
        silent=True
    ) or {}


    user_message = sanitize_text(
        str(d.get("user_message", "")),
        1000
    ).strip()


    bot_reply = sanitize_text(
        str(d.get("bot_reply", "")),
        1000
    ).strip()


    if not user_message:

        return jsonify(
            ok=False,
            error="user_message inahitajika."
        ), 400


    ok = notify_admin_whatsapp(
        user_message=user_message,
        bot_reply=bot_reply
    )


    return jsonify(
        ok=ok
    )


# =========================================================
# WHATSAPP ADMIN NOTIFICATION
# =========================================================

def notify_admin_whatsapp(
    user_message: str,
    bot_reply: str
) -> bool:

    """
    Inatuma ujumbe wa bot kwenda WhatsApp ya admin.

    Admin:
        0755 248 789
        International:
        255755248789

    MUHIMU:
    WhatsApp API halisi inahitajika.

    Render Environment Variables:

        WHATSAPP_API_URL
        WHATSAPP_API_TOKEN
        ADMIN_WHATSAPP_NUMBER

    Ikiwa credentials hazijawekwa,
    function inarudisha False bila kuvunja bot.
    """


    # =====================================================
    # CHECK CONFIG
    # =====================================================

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


    # =====================================================
    # SANITIZE MESSAGE
    # =====================================================

    safe_user_message = sanitize_text(
        str(user_message),
        1000
    )

    safe_bot_reply = sanitize_text(
        str(bot_reply),
        1000
    )


    # =====================================================
    # WHATSAPP MESSAGE
    # =====================================================

    whatsapp_message = (
        "🔔 NJIA MAUZO AFRIKA\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "👤 Ujumbe mpya wa mtumiaji:\n"
        f"{safe_user_message}\n\n"
        "🤖 Bot imejibu:\n"
        f"{safe_bot_reply}\n\n"
        "💰 Ada ya AI Product Finder: TZS 3,000\n"
        "━━━━━━━━━━━━━━━━━━"
    )


    # =====================================================
    # PAYLOAD
    #
    # Hii ni generic JSON payload.
    # Endpoint ya WhatsApp provider lazima ikubali
    # format hii.
    # =====================================================

    payload = {

        "to": ADMIN_WHATSAPP_NUMBER,

        "message": whatsapp_message

    }


    # =====================================================
    # REQUEST
    # =====================================================

    try:

        request_data = json.dumps(
            payload,
            ensure_ascii=False
        ).encode("utf-8")


        req = urllib.request.Request(

            WHATSAPP_API_URL,

            data=request_data,

            headers={

                "Content-Type":
                    "application/json",

                "Authorization":
                    f"Bearer {WHATSAPP_API_TOKEN}"

            },

            method="POST"

        )


        with urllib.request.urlopen(
            req,
            timeout=5
        ) as response:

            status = response.status


        # =================================================
        # SUCCESS
        # =================================================

        if 200 <= status < 300:

            app.logger.info(
                "WhatsApp admin notification sent successfully."
            )

            return True


        # =================================================
        # FAILED HTTP STATUS
        # =================================================

        app.logger.warning(
            "WhatsApp notification failed with HTTP status %s",
            status
        )

        return False


    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError
    ) as e:

        app.logger.warning(
            "WhatsApp notify failed: %s",
            e
        )

        return False


    except Exception as e:

        app.logger.exception(
            "Unexpected WhatsApp notification error: %s",
            e
        )

        return False


# =========================================================
# END:
# AI PRODUCT FINDER + 24/7 BOT + WHATSAPP ADMIN
# =========================================================
