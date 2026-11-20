from collections.abc import Sequence

from sqlalchemy import Executable
from sqlalchemy.dialects.postgresql import insert

from app.models import accounts, fundings
from app.schemas import Envelope, FundedData


def account_funded(envelope: Envelope, data: FundedData) -> Sequence[Executable]:
    return [
        insert(accounts)
        .values(id=data.account_id, currency=data.currency)
        .on_conflict_do_nothing(index_elements=[accounts.c.id]),
        insert(fundings).values(
            event_id=envelope.id,
            account_id=data.account_id,
            amount=data.amount,
            currency=data.currency,
        ),
    ]
