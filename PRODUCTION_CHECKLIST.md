# v3.2 production checklist

- [ ] Choose payment provider(s): M-Pesa, Airtel Money, Mixx by Yas, HaloPesa or an aggregator.
- [ ] Create merchant/API credentials.
- [ ] Configure HTTPS webhook endpoint.
- [ ] Verify webhook signatures server-side.
- [ ] Match provider amount/currency/reference against the pending payment.
- [ ] Make verification idempotent.
- [ ] Unlock User Room only after VERIFIED.
- [ ] Add FX provider for foreign-currency display.
- [ ] Add automated product/market matching provider or internal database.
- [ ] Add audit logs for payment and room-unlock events.
