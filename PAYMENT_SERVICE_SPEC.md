# Payment Service Spec — NjiaMauzo Afrika

## Supported methods (API)

| ID | Name | Typical use |
|----|------|-------------|
| MPESA | M-Pesa | TZ / KE mobile money |
| TIGOPESA | Tigo Pesa | Tanzania |
| AIRTELMONEY | Airtel Money | East Africa |
| CARD | Visa / Mastercard | Cards |
| BANK | Bank transfer | Manual + reference |
| FLUTTERWAVE | Flutterwave | Multi-method aggregator |

## Endpoints

### `GET /api/payments/methods`
List available payment methods.

### `POST /api/payments/initiate`
```json
{
  "amount": 1000,
  "method": "MPESA",
  "phone": "+2557...",
  "email": "user@example.com",
  "purpose": "SERVICE",
  "country": "Tanzania"
}
```
Returns `reference`, `status: PENDING`, optional OTP for large amounts.

### `POST /api/payments/confirm`
```json
{
  "reference": "NM-XXXX",
  "otp": "123456"
}
```
Demo marks payment VERIFIED. Production: trust gateway webhook only.

### `GET /api/payments/status/<reference>`
Poll payment status.

### `POST /api/service/webhook`
Gateway callback. Header: `X-Payment-Secret: <PAYMENT_WEBHOOK_SECRET>`

## Production rules
1. Browser must never set status to VERIFIED.
2. Only signed webhook (or trusted server-to-server call) confirms money.
3. Log every event in `payment_events`.
4. Amounts ≥ TZS 50,000 can require OTP (configurable).
