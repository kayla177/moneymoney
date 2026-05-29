"""Optional HTTP Basic auth for the API.

Enforced only when APP_PASSWORD is set in the environment. This keeps local development
frictionless while ensuring a public deployment doesn't expose financial data unprotected.
The PWA's static shell stays public (it holds no secrets); all sensitive data is behind
/api, which this guards.
"""

from __future__ import annotations

import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_security = HTTPBasic(auto_error=False)


def require_auth(
    credentials: HTTPBasicCredentials | None = Depends(_security),
) -> None:
    password = os.environ.get("APP_PASSWORD")
    if not password:
        return  # auth disabled (e.g. local dev / tests)

    username = os.environ.get("APP_USERNAME", "me")
    ok = credentials is not None and secrets.compare_digest(
        credentials.username, username
    ) and secrets.compare_digest(credentials.password, password)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
