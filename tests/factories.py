"""Builders for raw PayFlow events. Event ids are unique unless given explicitly."""

import itertools
from typing import Any

_ids = itertools.count(1)


def event(
    type_: str,
    data: dict[str, Any],
    *,
    id: str | None = None,
    created_at: str = "2026-10-19T10:00:00Z",
) -> dict[str, Any]:
    return {
        "id": id or f"evt_test_{next(_ids):04d}",
        "type": type_,
        "created_at": created_at,
        "data": data,
    }


def funded(
    amount: str, *, account_id: str = "acc_1", currency: str = "USD", **kwargs: Any
) -> dict[str, Any]:
    data = {"account_id": account_id, "amount": amount, "currency": currency}
    return event("account.funded", data, **kwargs)


def auth_created(
    authorization_id: str,
    amount: str,
    *,
    account_id: str = "acc_1",
    currency: str = "USD",
    merchant: str = "AWS",
    **kwargs: Any,
) -> dict[str, Any]:
    data = {
        "account_id": account_id,
        "authorization_id": authorization_id,
        "amount": amount,
        "currency": currency,
        "merchant": merchant,
    }
    return event("authorization.created", data, **kwargs)


def auth_captured(
    authorization_id: str,
    amount: str,
    *,
    account_id: str = "acc_1",
    currency: str = "USD",
    **kwargs: Any,
) -> dict[str, Any]:
    data = {
        "account_id": account_id,
        "authorization_id": authorization_id,
        "amount": amount,
        "currency": currency,
    }
    return event("authorization.captured", data, **kwargs)


def auth_reversed(
    authorization_id: str,
    amount: str,
    *,
    account_id: str = "acc_1",
    currency: str = "USD",
    **kwargs: Any,
) -> dict[str, Any]:
    data = {
        "account_id": account_id,
        "authorization_id": authorization_id,
        "amount": amount,
        "currency": currency,
    }
    return event("authorization.reversed", data, **kwargs)


def refund(
    refund_id: str,
    authorization_id: str,
    amount: str,
    *,
    account_id: str = "acc_1",
    currency: str = "USD",
    **kwargs: Any,
) -> dict[str, Any]:
    data = {
        "account_id": account_id,
        "refund_id": refund_id,
        "authorization_id": authorization_id,
        "amount": amount,
        "currency": currency,
    }
    return event("refund.created", data, **kwargs)
