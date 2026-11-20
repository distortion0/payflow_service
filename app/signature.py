import hashlib
import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status


def verify_signature(raw_body: bytes, header: str | None, secret: str) -> bool:
    """True when header == hex(HMAC_SHA256(secret, raw_body)); constant-time comparison."""
    if header is None:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), header.encode())


async def signed_body(
    request: Request, x_payflow_signature: Annotated[str | None, Header()] = None
) -> bytes:
    """Read the raw body before any parsing and reject it unless the signature matches."""
    raw_body = await request.body()
    secret = request.app.state.settings.payflow_webhook_secret
    if not verify_signature(raw_body, x_payflow_signature, secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid signature")
    return raw_body


SignedBody = Annotated[bytes, Depends(signed_body)]
