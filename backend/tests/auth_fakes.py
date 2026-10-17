"""Auth0-shaped access tokens for tests, signed with a throwaway RSA key.

`install(app)` points an app's security dependencies at a fake tenant, so tokens from
`token()` validate through the real code path with no Auth0 tenant or network.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI

from app.security import (
    AuthSettings,
    TokenValidator,
    get_auth_settings,
    get_token_validator,
    roles,
)

DOMAIN = "planit-test.us.auth0.com"
AUDIENCE = "https://api.planit-control.test"
ISSUER = f"https://{DOMAIN}/"
ROLES_CLAIM = roles.DEFAULT_ROLES_CLAIM
KID = "test-key"
TENANT_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeJwks:
    """Stands in for PyJWKClient: knows one key id, or simulates an outage."""

    def __init__(self, down: bool = False) -> None:
        self.down = down

    def get_signing_key_from_jwt(self, token: str):
        if self.down:
            raise jwt.PyJWKClientConnectionError("JWKS unreachable")
        if jwt.get_unverified_header(token).get("kid") != KID:
            raise jwt.PyJWKClientError("Unable to find a signing key that matches")
        return type("SigningKey", (), {"key": TENANT_KEY.public_key()})()


def token(
    role_names: list[str] | None = None,
    permissions: list[str] | None = None,
    *,
    key: Any = TENANT_KEY,
    algorithm: str = "RS256",
    kid: str = KID,
    expires_in: timedelta = timedelta(hours=1),
    **overrides: Any,
) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": [AUDIENCE, f"{ISSUER}userinfo"],
        "sub": "auth0|demo-user",
        "iat": now,
        "exp": now + expires_in,
        ROLES_CLAIM: role_names if role_names is not None else ["crew"],
    }
    if permissions is not None:
        claims["permissions"] = permissions
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": kid})


def bearer(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


def crew(sub: str = "auth0|crew-a") -> dict[str, str]:
    return bearer(token(["crew"], sorted(roles.CREW_PERMISSIONS), sub=sub))


def supervisor(sub: str = "auth0|supervisor-1") -> dict[str, str]:
    return bearer(token(["supervisor"], sorted(roles.SUPERVISOR_PERMISSIONS), sub=sub))


def settings(**overrides: Any) -> AuthSettings:
    values = {"auth0_domain": DOMAIN, "auth0_audience": AUDIENCE, **overrides}
    return AuthSettings(_env_file=None, **values)


def install(app: FastAPI, auth: AuthSettings | None = None, jwks: FakeJwks | None = None) -> None:
    auth = auth or settings()
    app.dependency_overrides[get_auth_settings] = lambda: auth
    if auth.configured:
        validator = TokenValidator(auth, jwks_client=jwks or FakeJwks())
        app.dependency_overrides[get_token_validator] = lambda: validator
