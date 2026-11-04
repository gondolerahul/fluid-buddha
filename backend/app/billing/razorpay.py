"""
A small Razorpay client (WS12): only the calls billing needs, over the REST
API with HTTP basic auth (key id + key secret).

* Plans and subscriptions: an account on a paid plan has one Razorpay
  subscription; the visitor-facing checkout is Razorpay Checkout opened with
  the subscription id.
* Add-ons: overage for a finished period is added to the subscription and
  charged with its next invoice.
* Signatures: Checkout's ``razorpay_signature`` (HMAC-SHA256 of
  ``payment_id|subscription_id`` with the key secret) and webhook
  ``X-Razorpay-Signature`` (HMAC-SHA256 of the raw body with the webhook
  secret), both compared in constant time.

Test-mode keys (``rzp_test_…``) talk to the same API without moving money.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any, Optional

import httpx

API = "https://api.razorpay.com/v1"
_TIMEOUT = 20.0


class RazorpayError(RuntimeError):
    """Razorpay refused a request; ``description`` is safe to show the tenant."""

    def __init__(self, status: int, description: str) -> None:
        super().__init__(f"Razorpay {status}: {description}")
        self.status = status
        self.description = description


class Razorpay:
    def __init__(self, key_id: str, key_secret: str, *,
                 transport: Optional[httpx.AsyncBaseTransport] = None,
                 base_url: str = API) -> None:
        self.key_id = key_id
        self._secret = key_secret
        self._transport = transport
        self._base = base_url.rstrip("/")

    async def _call(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        async with httpx.AsyncClient(
            base_url=self._base, auth=(self.key_id, self._secret), timeout=_TIMEOUT,
            transport=self._transport, trust_env=False,
        ) as client:
            resp = await client.request(method, path, json=body)
        if resp.status_code >= 400:
            try:
                desc = resp.json().get("error", {}).get("description") or resp.text
            except ValueError:
                desc = resp.text
            raise RazorpayError(resp.status_code, str(desc)[:300])
        return resp.json()

    # ---- plans & subscriptions ----
    async def create_plan(self, *, name: str, amount: int, currency: str,
                          description: str = "") -> dict:
        return await self._call("POST", "/plans", {
            "period": "monthly", "interval": 1,
            "item": {"name": name, "amount": amount, "currency": currency,
                     "description": description},
        })

    async def fetch_plan(self, plan_id: str) -> dict:
        return await self._call("GET", f"/plans/{plan_id}")

    async def create_subscription(self, *, plan_id: str, notes: dict[str, str],
                                  total_count: int = 120) -> dict:
        # total_count: how many monthly charges before it ends (10 years).
        return await self._call("POST", "/subscriptions", {
            "plan_id": plan_id, "total_count": total_count, "quantity": 1,
            "customer_notify": 1, "notes": notes,
        })

    async def fetch_subscription(self, subscription_id: str) -> dict:
        return await self._call("GET", f"/subscriptions/{subscription_id}")

    async def change_plan(self, subscription_id: str, plan_id: str, *, now: bool) -> dict:
        return await self._call("PATCH", f"/subscriptions/{subscription_id}", {
            "plan_id": plan_id, "schedule_change_at": "now" if now else "cycle_end",
        })

    async def cancel_subscription(self, subscription_id: str, *, at_cycle_end: bool = True) -> dict:
        return await self._call("POST", f"/subscriptions/{subscription_id}/cancel",
                                {"cancel_at_cycle_end": 1 if at_cycle_end else 0})

    async def create_addon(self, subscription_id: str, *, name: str, amount: int,
                           currency: str, description: str = "") -> dict:
        return await self._call("POST", f"/subscriptions/{subscription_id}/addons", {
            "item": {"name": name, "amount": amount, "currency": currency,
                     "description": description},
            "quantity": 1,
        })

    # ---- signatures ----
    def checkout_signature_ok(self, *, payment_id: str, subscription_id: str,
                              signature: str) -> bool:
        expected = _hmac(self._secret, f"{payment_id}|{subscription_id}".encode())
        return hmac.compare_digest(expected, signature or "")


def webhook_signature_ok(body: bytes, signature: Optional[str], secret: str) -> bool:
    if not secret or not signature:
        return False
    return hmac.compare_digest(_hmac(secret, body), signature)


def _hmac(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def client_from_settings(settings, *, transport: Any = None) -> Optional[Razorpay]:
    """None when Razorpay isn't configured (billing then shows plans only)."""
    if not (settings.razorpay_key_id and settings.razorpay_key_secret):
        return None
    return Razorpay(settings.razorpay_key_id, settings.razorpay_key_secret, transport=transport)
