from collections.abc import Sequence

from sqlalchemy import Executable
from sqlalchemy.dialects.postgresql import insert

from app.models import refunds
from app.schemas import Envelope, RefundCreatedData


def refund_created(envelope: Envelope, data: RefundCreatedData) -> Sequence[Executable]:
    return [
        insert(refunds)
        .values(
            id=data.refund_id,
            authorization_id=data.authorization_id,
            account_id=data.account_id,
            amount=data.amount,
            currency=data.currency,
        )
        .on_conflict_do_nothing(index_elements=[refunds.c.id])
    ]
