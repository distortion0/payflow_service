import json
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import events
from tests.factories import auth_captured, event, funded
from tests.helpers import assert_happy_path_responses, post_event, post_raw, sign


async def stored_events(conn: AsyncConnection) -> int:
    return await conn.scalar(select(func.count()).select_from(events))


async def test_missing_signature_is_rejected_and_nothing_is_stored(
    client: AsyncClient, conn: AsyncConnection
) -> None:
    response = await post_raw(client, json.dumps(funded("1000.00")).encode(), None)

    assert response.status_code == 401
    assert await stored_events(conn) == 0


async def test_wrong_signature_is_rejected_and_nothing_is_stored(
    client: AsyncClient, conn: AsyncConnection
) -> None:
    body = json.dumps(funded("1000.00")).encode()

    response = await post_raw(client, body, sign(body, "whsec_live_456"))

    assert response.status_code == 401
    assert await stored_events(conn) == 0


async def test_signature_is_computed_over_the_raw_bytes(client: AsyncClient) -> None:
    payload = funded("1000.00")
    pretty = json.dumps(payload, indent=4).encode()
    compact = json.dumps(payload, separators=(",", ":")).encode()

    assert (await post_raw(client, pretty, sign(compact))).status_code == 401
    assert (await post_raw(client, pretty, sign(pretty))).status_code == 200


@pytest.mark.parametrize("body", [b"not json", b"{}", b'{"id": "evt_1"}', b"[]", b""])
async def test_unreadable_envelope_is_400(client: AsyncClient, body: bytes) -> None:
    response = await post_raw(client, body, sign(body))

    assert response.status_code == 400


async def test_unknown_type_and_invalid_data_are_acknowledged(client: AsyncClient) -> None:
    ignored = await post_event(client, event("card.issued", {"card_id": "card_1"}))
    failed = await post_event(client, funded("-1.00"))

    assert (ignored.status_code, ignored.json()) == (200, {"outcome": "ignored"})
    assert (failed.status_code, failed.json()) == (200, {"outcome": "failed"})


async def test_duplicate_delivery_is_acknowledged(client: AsyncClient) -> None:
    payload = funded("1000.00")

    assert (await post_event(client, payload)).json() == {"outcome": "processed"}
    assert (await post_event(client, payload)).json() == {"outcome": "duplicate"}


async def test_happy_path_over_http_gives_the_responses_from_the_assignment(
    client: AsyncClient, happy_path: list[dict[str, Any]]
) -> None:
    for payload in happy_path:
        response = await post_event(client, payload)
        assert (response.status_code, response.json()) == (200, {"outcome": "processed"})

    await assert_happy_path_responses(client)


async def test_unknown_account_is_404_on_both_reads(client: AsyncClient) -> None:
    assert (await client.get("/accounts/acc_404/balance")).status_code == 404
    assert (await client.get("/accounts/acc_404/transactions")).status_code == 404


async def test_capture_without_created_gives_nulls_and_available_can_go_negative(
    client: AsyncClient,
) -> None:
    await post_event(client, funded("100.00"))
    await post_event(client, auth_captured("auth_1", "180.00"))

    balance = await client.get("/accounts/acc_1/balance")
    assert balance.json() == {
        "account_id": "acc_1",
        "currency": "USD",
        "available": "-80.00",
        "pending": "0.00",
    }
    transactions = await client.get("/accounts/acc_1/transactions")
    assert transactions.json() == {
        "items": [
            {
                "authorization_id": "auth_1",
                "merchant": None,
                "currency": "USD",
                "status": "captured",
                "authorized_amount": None,
                "captured_amount": "180.00",
                "refunded_amount": "0.00",
                "created_at": None,
            }
        ]
    }
