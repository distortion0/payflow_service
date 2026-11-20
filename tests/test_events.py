from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import accounts, authorizations, events, fundings
from app.queries import get_balance, list_transactions
from app.schemas import AuthorizationStatus, Outcome
from tests.conftest import Deliver
from tests.factories import auth_captured, auth_created, event, funded


async def count(conn: AsyncConnection, table: Any) -> int:
    return await conn.scalar(select(func.count()).select_from(table))


async def event_row(conn: AsyncConnection, event_id: str) -> Any:
    stmt = select(events.c.outcome, events.c.error).where(events.c.id == event_id)
    return (await conn.execute(stmt)).one()


async def test_duplicate_id_is_applied_once(deliver: Deliver, conn: AsyncConnection) -> None:
    funding = funded("1000.00", id="evt_dup")

    assert await deliver(funding) is Outcome.PROCESSED
    assert await deliver(funding) is None
    assert await deliver({**funding, "data": {**funding["data"], "amount": "5000.00"}}) is None

    assert await count(conn, fundings) == 1
    assert (await get_balance(conn, "acc_1")).available == Decimal("1000.00")


async def test_unknown_type_is_ignored(deliver: Deliver, conn: AsyncConnection) -> None:
    unknown = event("card.issued", {"account_id": "acc_1", "card_id": "card_1"})

    assert await deliver(unknown) is Outcome.IGNORED

    row = await event_row(conn, unknown["id"])
    assert (row.outcome, row.error) == (Outcome.IGNORED, None)
    assert await count(conn, accounts) == 0


@pytest.mark.parametrize(
    "broken",
    [
        funded("-5.00"),
        funded("10.005"),
        funded("10.00", currency="usd"),
        auth_created("auth_1", "oops"),
        {**auth_created("auth_1", "10.00"), "data": {"account_id": "acc_1"}},
    ],
)
async def test_invalid_data_is_failed_and_changes_nothing(
    deliver: Deliver, conn: AsyncConnection, broken: dict[str, Any]
) -> None:
    await deliver(funded("1000.00"))

    assert await deliver(broken) is Outcome.FAILED
    assert await deliver(broken) is None

    row = await event_row(conn, broken["id"])
    assert row.outcome == Outcome.FAILED
    assert row.error
    assert (await get_balance(conn, "acc_1")).available == Decimal("1000.00")
    assert await count(conn, authorizations) == 0


async def test_captured_before_created_builds_partial_row_which_created_completes(
    deliver: Deliver, conn: AsyncConnection
) -> None:
    await deliver(funded("1000.00"))

    assert await deliver(auth_captured("auth_7", "70.00")) is Outcome.PROCESSED

    row = (await conn.execute(select(authorizations))).one()
    assert (row.authorized_amount, row.merchant, row.created_at) == (None, None, None)
    assert (row.captured_amount, row.reversed) == (Decimal("70.00"), False)
    [tx] = await list_transactions(conn, "acc_1")
    assert tx.status == AuthorizationStatus.CAPTURED
    balance = await get_balance(conn, "acc_1")
    assert (balance.available, balance.pending) == (Decimal("930.00"), Decimal("0.00"))

    created = auth_created("auth_7", "60.00", merchant="Uber", created_at="2026-10-19T10:30:00Z")
    assert await deliver(created) is Outcome.PROCESSED

    row = (await conn.execute(select(authorizations))).one()
    assert (row.authorized_amount, row.merchant) == (Decimal("60.00"), "Uber")
    assert row.created_at == datetime(2026, 10, 19, 10, 30, tzinfo=UTC)
    assert row.captured_amount == Decimal("70.00")
    [tx] = await list_transactions(conn, "acc_1")
    assert (tx.status, tx.authorized_amount, tx.captured_amount) == (
        AuthorizationStatus.CAPTURED,
        Decimal("60.00"),
        Decimal("70.00"),
    )
    balance = await get_balance(conn, "acc_1")
    assert (balance.available, balance.pending) == (Decimal("930.00"), Decimal("0.00"))


async def test_zero_amount_is_accepted_and_changes_nothing(
    deliver: Deliver, conn: AsyncConnection
) -> None:
    await deliver(funded("1000.00"))

    assert await deliver(funded("0.00")) is Outcome.PROCESSED
    assert await deliver(auth_created("auth_1", "0.00")) is Outcome.PROCESSED

    balance = await get_balance(conn, "acc_1")
    assert (balance.available, balance.pending) == (Decimal("1000.00"), Decimal("0.00"))
