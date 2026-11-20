from collections.abc import Sequence
from typing import Any

from sqlalchemy import Executable
from sqlalchemy.dialects.postgresql import insert

from app.models import authorizations
from app.schemas import (
    AuthorizationCapturedData,
    AuthorizationCreatedData,
    AuthorizationReversedData,
    Envelope,
)


def _upsert(values: dict[str, Any], *owned: str) -> Executable:
    """Insert the authorization row, or update only the columns this event owns."""
    stmt = insert(authorizations).values(values)
    return stmt.on_conflict_do_update(
        index_elements=[authorizations.c.id],
        set_={column: stmt.excluded[column] for column in owned},
    )


def authorization_created(
    envelope: Envelope, data: AuthorizationCreatedData
) -> Sequence[Executable]:
    values = {
        "id": data.authorization_id,
        "account_id": data.account_id,
        "currency": data.currency,
        "merchant": data.merchant,
        "authorized_amount": data.amount,
        "created_at": envelope.created_at,
    }
    return [
        _upsert(values, "account_id", "currency", "merchant", "authorized_amount", "created_at")
    ]


def authorization_captured(
    envelope: Envelope, data: AuthorizationCapturedData
) -> Sequence[Executable]:
    values = {
        "id": data.authorization_id,
        "account_id": data.account_id,
        "currency": data.currency,
        "captured_amount": data.amount,
    }
    return [_upsert(values, "captured_amount")]


def authorization_reversed(
    envelope: Envelope, data: AuthorizationReversedData
) -> Sequence[Executable]:
    values = {
        "id": data.authorization_id,
        "account_id": data.account_id,
        "currency": data.currency,
        "reversed": True,
    }
    return [_upsert(values, "reversed")]
