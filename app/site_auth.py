"""Acesso simples ao site em produção (senha única, validada no backend)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Optional

from fastapi import Header, HTTPException

from app.config import settings


def site_auth_enabled() -> bool:
    if settings.UPI_DEV_MODE:
        return False
    return bool((settings.SITE_ACCESS_PASSWORD or "").strip())


def issue_site_token() -> str:
    secret = (settings.SITE_AUTH_SECRET or "upi-site-auth").encode("utf-8")
    password = settings.SITE_ACCESS_PASSWORD.strip().encode("utf-8")
    return hmac.new(secret, password, hashlib.sha256).hexdigest()


def verify_password(password: str) -> bool:
    expected = (settings.SITE_ACCESS_PASSWORD or "").strip()
    if not expected:
        return False
    return secrets.compare_digest(password.strip(), expected)


def verify_site_token(token: Optional[str]) -> bool:
    if not token:
        return False
    return secrets.compare_digest(token.strip(), issue_site_token())


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def require_site_access(
    authorization: Optional[str] = Header(None),
    x_site_token: Optional[str] = Header(None),
) -> None:
    if not site_auth_enabled():
        return

    token = extract_bearer_token(authorization) or (
        x_site_token.strip() if x_site_token else None
    )
    if not verify_site_token(token):
        raise HTTPException(status_code=401, detail="Acesso não autorizado")
