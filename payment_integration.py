"""
NjiaMauzo Afrika v3.2 payment integration contract.

This module deliberately does not fake successful payments.
Connect one real provider adapter and call verify_webhook_event() from
the provider's signed server-side webhook.
"""

from dataclasses import dataclass
from decimal import Decimal


BASE_FEE_TZS = Decimal("1000.00")


@dataclass
class PaymentResult:
    status: str
    provider_reference: str
    amount: Decimal
    currency: str


def foreign_display_amount(rate_from_tzs: Decimal) -> Decimal:
    """Convert the canonical TZS 1,000 service fee for display only."""
    return (BASE_FEE_TZS * rate_from_tzs).quantize(Decimal("0.01"))


def verify_webhook_event(payload: dict, signature_ok: bool) -> PaymentResult:
    """
    Production adapter contract.

    `signature_ok` must be produced by real provider signature verification.
    This function refuses to verify a payment when the trusted signature is
    missing or invalid.
    """
    if not signature_ok:
        raise ValueError("Untrusted payment webhook")

    status = str(payload.get("status", "")).upper()
    reference = str(payload.get("provider_reference", "")).strip()
    amount = Decimal(str(payload.get("amount", "0")))
    currency = str(payload.get("currency", "")).upper()

    if status != "VERIFIED":
        return PaymentResult(status="PENDING", provider_reference=reference,
                             amount=amount, currency=currency)

    if not reference:
        raise ValueError("Missing provider transaction reference")

    return PaymentResult(status="VERIFIED", provider_reference=reference,
                         amount=amount, currency=currency)
