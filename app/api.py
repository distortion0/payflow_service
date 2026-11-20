"""Three thin routes over the events inbox and the read queries. No logic lives here."""

from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from app.db import ConnectionDep
from app.events import process_event
from app.queries import account_exists, get_balance, list_transactions
from app.schemas import (
    BalanceResponse,
    Envelope,
    TransactionItem,
    TransactionsResponse,
    WebhookAck,
)
from app.signature import SignedBody

router = APIRouter()


@router.post("/webhooks")
async def receive_webhook(raw_body: SignedBody, conn: ConnectionDep) -> WebhookAck:
    try:
        envelope = Envelope.model_validate_json(raw_body)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid event envelope") from exc
    outcome = await process_event(conn, envelope)
    return WebhookAck(outcome=outcome or "duplicate")


@router.get("/accounts/{account_id}/balance")
async def read_balance(account_id: str, conn: ConnectionDep) -> BalanceResponse:
    balance = await get_balance(conn, account_id)
    if balance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    return BalanceResponse.model_validate(balance, from_attributes=True)


@router.get("/accounts/{account_id}/transactions")
async def read_transactions(account_id: str, conn: ConnectionDep) -> TransactionsResponse:
    if not await account_exists(conn, account_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    rows = await list_transactions(conn, account_id)
    items = [TransactionItem.model_validate(row, from_attributes=True) for row in rows]
    return TransactionsResponse(items=items)
