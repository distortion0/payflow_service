from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
)


def _two_places(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


# Digits are capped to fit NUMERIC(18, 2).
Money = Annotated[
    Decimal,
    Field(ge=0, max_digits=18, decimal_places=2),
    AfterValidator(_two_places),
    PlainSerializer(lambda value: f"{value:.2f}", return_type=str, when_used="json"),
]

Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class Outcome(StrEnum):
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"


class AuthorizationStatus(StrEnum):
    PENDING = "pending"
    CAPTURED = "captured"
    REVERSED = "reversed"


class Envelope(BaseModel):
    # Unknown top-level fields are kept so that events.payload holds everything PayFlow sent.
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    created_at: AwareDatetime
    data: dict[str, Any]


class FundedData(BaseModel):
    account_id: str
    amount: Money
    currency: Currency


class AuthorizationCreatedData(BaseModel):
    account_id: str
    authorization_id: str
    amount: Money
    currency: Currency
    merchant: str | None = None


class AuthorizationCapturedData(BaseModel):
    account_id: str
    authorization_id: str
    amount: Money
    currency: Currency


class AuthorizationReversedData(BaseModel):
    account_id: str
    authorization_id: str
    amount: Money
    currency: Currency


class RefundCreatedData(BaseModel):
    account_id: str
    refund_id: str
    authorization_id: str
    amount: Money
    currency: Currency
