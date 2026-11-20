"""
SQLAlchemy Core without the ORM: the service never manages objects, every write
is one atomic statement and every read is one SELECT.
"""

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Column,
    MetaData,
    Numeric,
    Table,
    Text,
    case,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.schemas import AuthorizationStatus

metadata = MetaData()

AMOUNT = Numeric(18, 2)
TIMESTAMPTZ = TIMESTAMP(timezone=True)


# Inbox of received webhook events; the primary key makes processing idempotent.
events = Table(
    "events",
    metadata,
    Column("id", Text, primary_key=True),
    Column("type", Text, nullable=False),
    Column("occurred_at", TIMESTAMPTZ, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("outcome", Text, nullable=False),
    Column("error", Text),
    Column("received_at", TIMESTAMPTZ, nullable=False, server_default=func.now()),
    CheckConstraint("outcome IN ('processed', 'ignored', 'failed')", name="events_outcome_check"),
)


accounts = Table(
    "accounts",
    metadata,
    Column("id", Text, primary_key=True),
    Column("currency", Text, nullable=False),
)


fundings = Table(
    "fundings",
    metadata,
    Column("event_id", Text, primary_key=True),
    Column("account_id", Text, nullable=False, index=True),
    Column("amount", AMOUNT, nullable=False),
    Column("currency", Text, nullable=False),
    CheckConstraint("amount >= 0", name="fundings_amount_non_negative"),
)

# One row per authorization; each event type fills only its own columns:
#   authorization.created  -> merchant, authorized_amount, created_at
#   authorization.captured -> captured_amount
#   authorization.reversed -> reversed
authorizations = Table(
    "authorizations",
    metadata,
    Column("id", Text, primary_key=True),
    Column("account_id", Text, nullable=False, index=True),
    Column("currency", Text, nullable=False),
    Column("merchant", Text),
    Column("authorized_amount", AMOUNT),
    Column("captured_amount", AMOUNT),
    Column("reversed", Boolean, nullable=False, server_default=text("false")),
    Column("created_at", TIMESTAMPTZ),
    CheckConstraint("authorized_amount >= 0", name="authorizations_authorized_amount_non_negative"),
    CheckConstraint("captured_amount >= 0", name="authorizations_captured_amount_non_negative"),
)

# The only place that knows how the facts above turn into a status.
authorization_status = case(
    (authorizations.c.captured_amount.is_not(None), AuthorizationStatus.CAPTURED.value),
    (authorizations.c.reversed, AuthorizationStatus.REVERSED.value),
    else_=AuthorizationStatus.PENDING.value,
)

refunds = Table(
    "refunds",
    metadata,
    Column("id", Text, primary_key=True),
    Column("authorization_id", Text, nullable=False, index=True),
    Column("account_id", Text, nullable=False, index=True),
    Column("amount", AMOUNT, nullable=False),
    Column("currency", Text, nullable=False),
    CheckConstraint("amount >= 0", name="refunds_amount_non_negative"),
)
