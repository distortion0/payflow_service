"""Shared helpers for tests that talk to the service over HTTP."""

import hashlib
import hmac
import json
from typing import Any

from httpx import AsyncClient, Response

SECRET = "whsec_test_123"

# Responses the assignment expects after happy_path.json, whatever the delivery looked like.
EXPECTED_BALANCE = {
    "account_id": "acc_1",
    "currency": "USD",
    "available": "585.00",
    "pending": "15.00",
}
EXPECTED_TRANSACTIONS = {
    "items": [
        {
            "authorization_id": "auth_100",
            "merchant": "AWS",
            "currency": "USD",
            "status": "captured",
            "authorized_amount": "125.50",
            "captured_amount": "125.50",
            "refunded_amount": "25.50",
            "created_at": "2026-10-19T10:01:00Z",
        },
        {
            "authorization_id": "auth_101",
            "merchant": "Uber",
            "currency": "USD",
            "status": "reversed",
            "authorized_amount": "40.00",
            "captured_amount": "0.00",
            "refunded_amount": "0.00",
            "created_at": "2026-10-19T10:02:00Z",
        },
        {
            "authorization_id": "auth_102",
            "merchant": "Hilton",
            "currency": "USD",
            "status": "captured",
            "authorized_amount": "300.00",
            "captured_amount": "300.00",
            "refunded_amount": "0.00",
            "created_at": "2026-10-19T10:10:00Z",
        },
        {
            "authorization_id": "auth_103",
            "merchant": "Slack",
            "currency": "USD",
            "status": "pending",
            "authorized_amount": "15.00",
            "captured_amount": "0.00",
            "refunded_amount": "0.00",
            "created_at": "2026-10-19T12:30:00Z",
        },
    ]
}


def sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def post_raw(client: AsyncClient, body: bytes, signature: str | None) -> Response:
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["X-PayFlow-Signature"] = signature
    return await client.post("/webhooks", content=body, headers=headers)


async def post_event(client: AsyncClient, event: dict[str, Any]) -> Response:
    body = json.dumps(event, separators=(",", ":")).encode()
    return await post_raw(client, body, sign(body))


async def assert_happy_path_responses(client: AsyncClient) -> None:
    balance = await client.get("/accounts/acc_1/balance")
    assert (balance.status_code, balance.json()) == (200, EXPECTED_BALANCE)

    transactions = await client.get("/accounts/acc_1/transactions")
    assert (transactions.status_code, transactions.json()) == (200, EXPECTED_TRANSACTIONS)
