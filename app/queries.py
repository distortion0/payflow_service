"""Read side: status and balance are derived from the stored facts, never stored."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Row, ScalarSelect, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import accounts, authorization_status, authorizations, fundings, refunds
from app.schemas import AuthorizationStatus


def _total(column: ColumnElement[Any], *conditions: ColumnElement[bool]) -> ScalarSelect[Any]:
    return select(func.coalesce(func.sum(column), 0)).where(*conditions).scalar_subquery()


async def get_balance(conn: AsyncConnection, account_id: str) -> Row[Any] | None:
    """One SELECT giving (account_id, currency, available, pending); None if never funded."""
    funded = _total(fundings.c.amount, fundings.c.account_id == account_id)
    pending = _total(
        authorizations.c.authorized_amount,
        authorizations.c.account_id == account_id,
        authorization_status == AuthorizationStatus.PENDING.value,
    )
    captured = _total(
        authorizations.c.captured_amount,
        authorizations.c.account_id == account_id,
        authorization_status == AuthorizationStatus.CAPTURED.value,
    )
    refunded = _total(refunds.c.amount, refunds.c.account_id == account_id)
    stmt = select(
        accounts.c.id.label("account_id"),
        accounts.c.currency,
        (funded - pending - captured + refunded).label("available"),
        pending.label("pending"),
    ).where(accounts.c.id == account_id)
    return (await conn.execute(stmt)).one_or_none()


async def list_transactions(conn: AsyncConnection, account_id: str) -> Sequence[Row[Any]]:
    """Authorizations of the account with their derived status and refund total."""
    refund_totals = (
        select(
            refunds.c.authorization_id,
            func.sum(refunds.c.amount).label("refunded_amount"),
        )
        .group_by(refunds.c.authorization_id)
        .subquery()
    )
    stmt = (
        select(
            authorizations.c.id.label("authorization_id"),
            authorizations.c.merchant,
            authorizations.c.currency,
            authorization_status.label("status"),
            authorizations.c.authorized_amount,
            func.coalesce(authorizations.c.captured_amount, 0).label("captured_amount"),
            func.coalesce(refund_totals.c.refunded_amount, 0).label("refunded_amount"),
            authorizations.c.created_at,
        )
        .select_from(
            authorizations.outerjoin(
                refund_totals, refund_totals.c.authorization_id == authorizations.c.id
            )
        )
        .where(authorizations.c.account_id == account_id)
        .order_by(authorizations.c.created_at.asc().nulls_last(), authorizations.c.id)
    )
    return (await conn.execute(stmt)).all()
