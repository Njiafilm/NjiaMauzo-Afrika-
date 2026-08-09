# Production Checklist — NjiaMauzo Afrika

## Security
- [ ] Change `SECRET_KEY` and `PASSWORD_SALT`
- [ ] Change admin password from `0000`
- [ ] Enable HTTPS only
- [ ] Set secure session cookies (`SESSION_COOKIE_SECURE=True`)
- [ ] Add CSRF protection
- [ ] Add rate limiting on login / OTP / payments
- [ ] Never expose secrets in frontend

## Database
- [ ] Migrate from SQLite to PostgreSQL
- [ ] Automated backups
- [ ] Audit logs for admin actions

## Payments
- [ ] Connect licensed gateway (M-Pesa Daraja, Flutterwave, etc.)
- [ ] Set `PAYMENT_WEBHOOK_SECRET`
- [ ] Verify all payments server-side only (webhook)
- [ ] Test STK push + failure paths

## Email / OTP
- [ ] Configure SMTP for `info@njiamauzo.africa`
- [ ] Connect SMS (Africa's Talking / Twilio)
- [ ] Connect WhatsApp Business API if needed
- [ ] Remove `demo_code` from API responses in production

## Data & AI
- [ ] Live market price feeds + scheduled ingestion
- [ ] Real AI provider for chat/search (optional)
- [ ] Content moderation workflow

## Deploy
- [ ] Domain + SSL
- [ ] Process manager (gunicorn + systemd / Docker)
- [ ] Monitoring & error tracking
- [ ] Mobile app (Flutter / React Native) — optional phase 2
