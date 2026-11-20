import random
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from app.queries import get_balance, list_transactions
from app.schemas import AuthorizationStatus, Outcome
from tests.conftest import Deliver
from tests.factories import auth_captured, auth_created, auth_reversed, funded, refund

PENDING, CAPTURED, REVERSED = AuthorizationStatus


def summary(items: Sequence[Row[Any]]) -> list[tuple[Any, ...]]:
    return [
        (t.authorization_id, t.status, t.authorized_amount, t.captured_amount, t.refunded_amount)
        for t in items
    ]


async def assert_balance(conn: AsyncConnection, account_id: str, available: str, pending: str):
    balance = await get_balance(conn, account_id)
    assert (balance.available, balance.pending) == (Decimal(available), Decimal(pending))


async def assert_happy_path_figures(conn: AsyncConnection) -> None:
    balance = await get_balance(conn, "acc_1")
    assert (balance.account_id, balance.currency) == ("acc_1", "USD")
    assert (balance.available, balance.pending) == (Decimal("585.00"), Decimal("15.00"))

    items = await list_transactions(conn, "acc_1")
    assert summary(items) == [
        ("auth_100", CAPTURED, Decimal("125.50"), Decimal("125.50"), Decimal("25.50")),
        ("auth_101", REVERSED, Decimal("40.00"), Decimal("0.00"), Decimal("0.00")),
        ("auth_102", CAPTURED, Decimal("300.00"), Decimal("300.00"), Decimal("0.00")),
        ("auth_103", PENDING, Decimal("15.00"), Decimal("0.00"), Decimal("0.00")),
    ]
    assert (items[0].merchant, items[0].currency) == ("AWS", "USD")
    assert items[0].created_at == datetime(2026, 10, 19, 10, 1, tzinfo=UTC)


async def test_happy_path_gives_the_figures_from_the_assignment(
    deliver: Deliver, conn: AsyncConnection, happy_path: list[dict[str, Any]]
) -> None:
    for event in happy_path:
        assert await deliver(event) is Outcome.PROCESSED

    await assert_happy_path_figures(conn)


@pytest.mark.parametrize("seed", range(5))
async def test_happy_path_in_any_order_gives_the_same_figures(
    deliver: Deliver, conn: AsyncConnection, happy_path: list[dict[str, Any]], seed: int
) -> None:
    random.Random(seed).shuffle(happy_path)

    for event in happy_path:
        await deliver(event)

    await assert_happy_path_figures(conn)


async def test_capture_above_or_below_authorized_releases_the_whole_block(
    deliver: Deliver, conn: AsyncConnection
) -> None:
    await deliver(funded("1000.00"))
    await deliver(auth_created("auth_1", "100.00"))
    await deliver(auth_created("auth_2", "100.00"))
    await assert_balance(conn, "acc_1", available="800.00", pending="200.00")

    await deliver(auth_captured("auth_1", "130.00"))
    await deliver(auth_captured("auth_2", "80.00"))

    await assert_balance(conn, "acc_1", available="790.00", pending="0.00")
    assert summary(await list_transactions(conn, "acc_1")) == [
        ("auth_1", CAPTURED, Decimal("100.00"), Decimal("130.00"), Decimal("0.00")),
        ("auth_2", CAPTURED, Decimal("100.00"), Decimal("80.00"), Decimal("0.00")),
    ]


async def test_multiple_refunds_are_summed_and_a_refund_id_counts_once(
    deliver: Deliver, conn: AsyncConnection
) -> None:
    await deliver(funded("1000.00"))
    await deliver(auth_created("auth_1", "100.00"))
    await deliver(auth_captured("auth_1", "100.00"))

    await deliver(refund("re_1", "auth_1", "30.00"))
    await deliver(refund("re_2", "auth_1", "20.00"))
    assert await deliver(refund("re_2", "auth_1", "20.00")) is Outcome.PROCESSED

    await assert_balance(conn, "acc_1", available="950.00", pending="0.00")
    [tx] = await list_transactions(conn, "acc_1")
    assert tx.refunded_amount == Decimal("50.00")


async def test_refund_before_capture_counts_immediately(
    deliver: Deliver, conn: AsyncConnection
) -> None:
    await deliver(funded("1000.00"))
    await deliver(auth_created("auth_1", "100.00"))

    await deliver(refund("re_1", "auth_1", "25.00"))
    await assert_balance(conn, "acc_1", available="925.00", pending="100.00")

    await deliver(auth_captured("auth_1", "90.00"))
    await assert_balance(conn, "acc_1", available="935.00", pending="0.00")
    [tx] = await list_transactions(conn, "acc_1")
    assert (tx.status, tx.refunded_amount) == (CAPTURED, Decimal("25.00"))


async def test_events_before_funding_are_kept_and_counted_once_the_account_exists(
    deliver: Deliver, conn: AsyncConnection
) -> None:
    await deliver(auth_created("auth_1", "50.00", account_id="acc_9"))
    await deliver(auth_captured("auth_1", "60.00", account_id="acc_9"))
    await deliver(refund("re_1", "auth_1", "10.00", account_id="acc_9"))

    assert await get_balance(conn, "acc_9") is None
    assert summary(await list_transactions(conn, "acc_9")) == [
        ("auth_1", CAPTURED, Decimal("50.00"), Decimal("60.00"), Decimal("10.00")),
    ]

    await deliver(funded("100.00", account_id="acc_9"))

    await assert_balance(conn, "acc_9", available="50.00", pending="0.00")


async def test_reversal_releases_the_whole_hold(deliver: Deliver, conn: AsyncConnection) -> None:
    await deliver(funded("1000.00"))
    await deliver(auth_created("auth_1", "100.00"))
    await assert_balance(conn, "acc_1", available="900.00", pending="100.00")

    await deliver(auth_reversed("auth_1", "100.00"))

    await assert_balance(conn, "acc_1", available="1000.00", pending="0.00")
    assert summary(await list_transactions(conn, "acc_1")) == [
        ("auth_1", REVERSED, Decimal("100.00"), Decimal("0.00"), Decimal("0.00")),
    ]


@pytest.mark.parametrize("captured_first", [True, False])
async def test_captured_wins_when_both_captured_and_reversed_arrive(
    deliver: Deliver, conn: AsyncConnection, captured_first: bool
) -> None:
    await deliver(funded("1000.00"))
    await deliver(auth_created("auth_1", "100.00"))
    contradiction = [auth_captured("auth_1", "90.00"), auth_reversed("auth_1", "100.00")]

    for payload in contradiction if captured_first else reversed(contradiction):
        await deliver(payload)

    await assert_balance(conn, "acc_1", available="910.00", pending="0.00")
    [tx] = await list_transactions(conn, "acc_1")
    assert (tx.status, tx.captured_amount) == (CAPTURED, Decimal("90.00"))
