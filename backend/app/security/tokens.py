"""Auth0 access-token validation.

Tokens must be RS256, signed by a key from the tenant's JWKS, issued by
`https://{AUTH0_DOMAIN}/`, addressed to AUTH0_AUDIENCE, and not expired. Signing keys
are fetched once and cached; a token with an unknown key id triggers one refetch.
"""

from typing import Any

import jwt

from app.security.settings import AuthSettings

ALGORITHMS = ["RS256"]
REQUIRED_CLAIMS = ["exp", "iat", "iss", "aud", "sub"]
LEEWAY_SECONDS = 30


class InvalidToken(Exception):
    """The token is missing, malformed, expired, or not from this tenant and API."""


class AuthUnavailable(Exception):
    """Auth0 signing keys could not be fetched, so no token can be checked."""


class TokenValidator:
    def __init__(self, settings: AuthSettings, jwks_client: jwt.PyJWKClient | None = None):
        if not settings.configured:
            raise AuthUnavailable("AUTH0_DOMAIN and AUTH0_AUDIENCE must be set")
        self.issuer = settings.issuer
        self.audience = settings.auth0_audience
        self.jwks = jwks_client or jwt.PyJWKClient(
            settings.jwks_url, cache_keys=True, lifespan=3600, timeout=5
        )

    def decode(self, token: str) -> dict[str, Any]:
        """Verified claims, or raises `InvalidToken` / `AuthUnavailable`."""
        try:
            key = self.jwks.get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientConnectionError as exc:
            raise AuthUnavailable("Could not fetch Auth0 signing keys") from exc
        except jwt.PyJWTError as exc:
            raise InvalidToken("Token signing key is not recognized") from exc
        try:
            return jwt.decode(
                token,
                key,
                algorithms=ALGORITHMS,
                audience=self.audience,
                issuer=self.issuer,
                leeway=LEEWAY_SECONDS,
                options={"require": REQUIRED_CLAIMS},
            )
        except jwt.ExpiredSignatureError as exc:
            raise InvalidToken("Token has expired") from exc
        except jwt.PyJWTError as exc:
            raise InvalidToken("Token is not valid for this API") from exc
