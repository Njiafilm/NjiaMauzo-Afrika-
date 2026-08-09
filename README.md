# 🌾 NjiaMauzo Afrika Pro

**Agricultural marketplace for East Africa**  
Kitovu cha Biashara · The Hub of Business

Unganisha wakulima na wanunuzi — Tanzania, Kenya, Uganda, Rwanda, Burundi.

**Repo:** [github.com/Njiafilm/NjiaMauzo-Afrika-](https://github.com/Njiafilm/NjiaMauzo-Afrika-)

---

## ✨ Features

### Marketplace
- Listings za mazao (Mahindi, Ufuta, Maharage, Mpunga, Korosho, Kahawa, Chai…)
- Bei za soko (demo + admin can add)
- Profit Intelligence (landed cost, margin, best market)
- AI Search & Chat (Kiswahili / English)
- Product slider + AI Market Monitor (auto-refresh every 60s)

### Social
- Like · Comments · Follow
- Live activity feed
- Location detection + distance sorting

### Security & Auth
- Registration / Login with human verification (CAPTCHA)
- Admin default password: `0000` (change after first login)
- Forgot password + OTP (Email / SMS / WhatsApp)
- Password change for logged-in users
- PBKDF2 password hashing · session cookies

### Online Payments
- M-Pesa · Tigo Pesa · Airtel Money
- Card · Bank Transfer · Flutterwave
- OTP for large amounts · webhook-ready structure

### Admin + AI Controller
- Dashboard, users, listings, comments moderation
- AI query logs · settings · market prices
- Verify / hide content

### Info Email (`info@njiamauzo.africa`)
- Welcome · OTP · Password reset · Payment confirmation templates
- Demo mode (console) or real SMTP

---

## 🚀 Run locally

```bash
git clone https://github.com/Njiafilm/NjiaMauzo-Afrika-.git
cd NjiaMauzo-Afrika-

python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
# .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
# edit .env with your secrets

python app.py
```

Open: **http://127.0.0.1:5000**

### Admin login

| Field    | Value                      |
|----------|----------------------------|
| Email    | `admin@njiamauzo.africa`   |
| Password | `0000` (badilisha baadaye) |
| Panel    | http://127.0.0.1:5000/admin |

---

## 📁 Project structure

```
NjiaMauzo-Afrika-/
├── app.py
├── email_service.py
├── requirements.txt
├── .env.example
├── .gitignore
├── VERSION.txt
├── README.md
├── PAYMENT_SERVICE_SPEC.md
├── PRODUCTION_CHECKLIST.md
├── emails/
│   ├── welcome.html
│   ├── otp.html
│   ├── password_reset.html
│   └── payment.html
├── static/
│   ├── app.js
│   └── style.css
└── templates/
    ├── index.html
    └── admin.html
```

---

## 🔐 Production checklist

1. Set strong `SECRET_KEY` and `PASSWORD_SALT` in `.env`
2. Connect real market-price feeds (replace demo data)
3. Connect licensed payment gateway → `/api/payments/*` + webhook
4. Configure SMTP for `info@njiamauzo.africa`
5. Use PostgreSQL, HTTPS, CSRF, rate limiting, backups
6. Change admin password from `0000` immediately
7. Never put API keys or payment secrets in frontend JS

See also: [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md) · [PAYMENT_SERVICE_SPEC.md](PAYMENT_SERVICE_SPEC.md)

---

## Tech stack

- **Backend:** Python 3 · Flask · SQLite (dev)
- **Frontend:** HTML · CSS · Vanilla JS
- **Auth:** Sessions · CAPTCHA · OTP
- **Email:** SMTP-ready templates

---

Built with ❤️ for East African farmers & traders.  
**Contact:** info@njiamauzo.africa
