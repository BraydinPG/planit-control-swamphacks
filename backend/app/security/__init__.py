"""Auth0 security dependencies for FastAPI routes. Setup: auth/SETUP.md."""

from app.security import roles
from app.security.dependencies import (
    AuthenticatedUser,
    CurrentUser,
    get_current_user,
    get_token_validator,
    require_permission,
    require_role,
)
from app.security.membership import membership_for
from app.security.settings import AuthSettings, get_auth_settings
from app.security.tokens import AuthUnavailable, InvalidToken, TokenValidator

__all__ = [
    "AuthSettings",
    "AuthenticatedUser",
    "AuthUnavailable",
    "CurrentUser",
    "InvalidToken",
    "TokenValidator",
    "get_auth_settings",
    "get_current_user",
    "get_token_validator",
    "membership_for",
    "require_permission",
    "require_role",
    "roles",
]
