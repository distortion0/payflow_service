"""Idempotent receiver for PayFlow events.

process_event records the event and applies it in one transaction. The INSERT into
events is the idempotency guard: a conflict on the id means the event was already
delivered and nothing else runs. Handlers are pure functions that turn an event
into INSERT ... ON CONFLICT statements touching only the columns the event owns;
they never see the database, so the result is the same for any delivery order,
duplicates and parallel deliveries.
"""

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import Executable
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from app.events.account import account_funded
from app.events.authorization import (
    authorization_captured,
    authorization_created,
    authorization_reversed,
)
from app.events.refund import refund_created
from app.models import events
from app.schemas import (
    AuthorizationCapturedData,
    AuthorizationCreatedData,
    AuthorizationReversedData,
    Envelope,
    FundedData,
    Outcome,
    RefundCreatedData,
)

Handler = Callable[[Envelope, Any], Sequence[Executable]]

# Event type -> (schema of its data block, handler)
# Types not listed here are recorded as ignored: PayFlow adds event types without notice
HANDLERS: dict[str, tuple[type[BaseModel], Handler]] = {
    "account.funded": (FundedData, account_funded),
    "authorization.created": (AuthorizationCreatedData, authorization_created),
    "authorization.captured": (AuthorizationCapturedData, authorization_captured),
    "authorization.reversed": (AuthorizationReversedData, authorization_reversed),
    "refund.created": (RefundCreatedData, refund_created),
}


async def process_event(conn: AsyncConnection, envelope: Envelope) -> Outcome | None:
    """Record the event and apply it. Returns None for a duplicate delivery.

    Opens its own transaction, so the connection must not have one in progress.
    """
    outcome, error, statements = plan(envelope)
    claim = (
        insert(events)
        .values(
            id=envelope.id,
            type=envelope.type,
            occurred_at=envelope.created_at,
            payload=envelope.model_dump(mode="json"),
            outcome=outcome.value,
            error=error,
        )
        .on_conflict_do_nothing(index_elements=[events.c.id])
        .returning(events.c.id)
    )
    async with conn.begin():
        if await conn.scalar(claim) is None:
            return None
        for statement in statements:
            await conn.execute(statement)
    return outcome


def plan(envelope: Envelope) -> tuple[Outcome, str | None, Sequence[Executable]]:
    """Decide the outcome and build the statements without touching the database."""
    if envelope.type not in HANDLERS:
        return Outcome.IGNORED, None, []
    schema, handler = HANDLERS[envelope.type]
    try:
        data = schema.model_validate(envelope.data)
    except ValidationError as exc:
        return Outcome.FAILED, _error_text(exc), []
    return Outcome.PROCESSED, None, handler(envelope, data)


def _error_text(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in err['loc']) or 'data'}: {err['msg']}"
        for err in exc.errors()
    )
