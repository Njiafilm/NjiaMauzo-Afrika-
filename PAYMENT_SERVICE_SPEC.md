# NjiaMauzo Afrika v3.2 — Paid Assisted Search

## Business flow

1. Anyone can browse products and markets without paying.
2. The system asks whether the visitor wants assisted product/market discovery.
3. If accepted, the user submits a search request.
4. The service fee is TZS 1,000 as the base price.
5. The UI may display the equivalent amount in the selected country currency.
6. A payment is created with status `PENDING`.
7. Only a trusted server-side payment callback/webhook can change it to `VERIFIED`.
8. After `VERIFIED`, the user's private `User Room` is unlocked.
9. The matching engine uses the user's request to find relevant products/markets.
10. The room remains locked for unverified/failed/expired payments.

## Security rules

- Never trust a browser-submitted `paid=true` flag.
- Never unlock the User Room based only on a payment screenshot.
- Verify the transaction with the payment provider or a signed webhook.
- Store provider transaction ID/reference and prevent duplicate verification.
- Keep payment secrets in environment variables.
- Use HTTPS in production.

## Currency

TZS 1,000 is the canonical service price. Foreign-currency display should be calculated from a configurable FX source. The system should not permanently hard-code foreign equivalents because exchange rates change.

## Required production environment

PAYMENT_PROVIDER=
PAYMENT_API_KEY=
PAYMENT_API_SECRET=
PAYMENT_WEBHOOK_SECRET=
PAYMENT_CALLBACK_URL=
FX_API_URL=
FX_API_KEY=
