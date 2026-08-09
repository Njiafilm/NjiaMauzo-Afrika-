# NjiaMauzo Afrika v3 Professional

## Run locally
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python app.py

Open: http://127.0.0.1:5000

## v3 features
- Responsive web application
- Tanzania + East Africa demo market dataset
- Price comparison
- AI-style natural-language product search
- AI chatbot interface
- Price & Profit Intelligence
- Transport cost, landed cost, profit/kg, total profit and margin
- Market recommendation
- Marketplace listings
- Seller/buyer registration and login
- Password hashing
- Price alerts
- Payment intent architecture
- Basic platform statistics
- Search history for logged-in users

## Production integrations still required
The included market feed is demo data. For real deployment:
1. Connect verified market-price APIs/data feeds and implement scheduled ingestion.
2. Connect a real server-side AI provider using an environment secret.
3. Connect a licensed payment gateway for mobile money/banks/cards.
4. Add HTTPS, CSRF protection, rate limiting, secure cookies, email/OTP verification,
   PostgreSQL, backups, audit logs and admin RBAC.
5. Build Flutter/React Native mobile client and publish through official store accounts.

Never place API keys, payment secrets or bank credentials in HTML/JavaScript.


## v3.1 — Paid Assisted Search / User Room
- Kila mgeni anayeingia anaulizwa kama anataka NjiaMauzo imsaidie kutafuta bidhaa na masoko.
- Akikubali, anaandika ombi lake (bidhaa/zao, kiasi, eneo, bei n.k.).
- Ada ya huduma ni **TZS 1,000**.
- Mfumo huonyesha equivalent ya TZS 1,000 katika currency ya nchi iliyochaguliwa (TZS/KES/UGX/RWF/BIF). Viwango vilivyowekwa kwenye code ni reference/configurable; production itumie FX feed ya kuaminika.
- Payment huanza ikiwa `PENDING`; **browser haiwezi kujiwekea VERIFIED**.
- `POST /api/service/webhook` ndiyo sehemu ya gateway yenye secret kuthibitisha malipo upande wa server.
- Baada ya `VERIFIED`, mfumo hufungua **User Room** na kufanya automatic matching ya listings + market prices kulingana na ombi la user.
- User Room haipatikani kabla ya payment verification.
- Kwa production, weka `PAYMENT_WEBHOOK_SECRET` na uunganishe gateway halisi ya mobile money/card/bank inayoruhusiwa kisheria.
