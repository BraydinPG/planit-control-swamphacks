"""Reusable FastAPI security dependencies (T027, T028).

Typical route use:

    from typing import Annotated

    from app.security import AuthenticatedUser, CurrentUser, require_permission, roles

    @router.get("/api/alerts")
    def list_alerts(user: AuthenticatedUser): ...

    @router.post("/api/reports/{report_id}/review")
    def review(
        user: Annotated[CurrentUser, Depends(require_permission(roles.REVIEW_REPORTS))],
    ): ...

Responses: 401 for a missing, invalid, or expired token; 403 when the token is valid
but its role or permissions do not allow the action; 503 when Auth0 is not configured
or its signing keys cannot be fetched. The backend is the authority; frontend guards
only improve the experience.

Demo guests (DEMO_GUEST_ENABLED, default false): a request with no Authorization header
may send `X-Demo-Role: crew` or `X-Demo-Role: supervisor` to read the demo organization
as its guest crew member or supervisor (`GUEST_USER_IDS`, linked by `app.demo.freshen`).
Guests may only read (GET/HEAD); every write is refused with 403, as are the team roster
and supervisor keys. Their scope comes from those memberships, like any other user.

Development bypass (DEV_AUTH_BYPASS, default false): when true, a request with no
Authorization header may send `X-Dev-Role: crew` or `X-Dev-Role: supervisor`. It is
honored only from a loopback client with no proxy forwarding headers, so it cannot be
reached through a deployed reverse proxy. Never enable it in a deployed environment.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.security import roles
from app.security.roles import ROLE_PERMISSIONS, ROLES, Role
from app.security.settings import AuthSettings, get_auth_settings
from app.security.tokens import AuthUnavailable, InvalidToken, TokenValidator

logger = logging.getLogger(__name__)

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
FORWARDING_HEADERS = ("x-forwarded-for", "x-real-ip", "forwarded")
DEV_ROLE_HEADER = "x-dev-role"
DEV_USER_HEADER = "x-dev-user"
DEMO_ROLE_HEADER = "x-demo-role"
# The demo organization's guest accounts; never real Auth0 users.
GUEST_USER_IDS: dict[str, str] = {"crew": "demo-guest|crew", "supervisor": "demo-guest|supervisor"}
GUEST_PERMISSIONS: dict[str, frozenset[str]] = {
    "crew": frozenset({roles.READ_ASSIGNED_SITES, roles.READ_ORG_BRIEFINGS}),
    "supervisor": frozenset(
        {roles.READ_ASSIGNED_SITES, roles.READ_ALL_SITES, roles.READ_ORG_BRIEFINGS}
    ),
}
GUEST_READ_METHODS = frozenset({"GET", "HEAD"})
GUEST_BLOCKED_PATHS = ("/api/team", "/api/supervisor-invites")

_bearer = HTTPBearer(auto_error=False, description="Auth0 access token")


@dataclass(frozen=True)
class CurrentUser:
    """The caller, from a verified Auth0 access token.

    `email` and `name` come from the "Add PlanIT roles" Action's profile claims. They are
    used only for the supervisor's team roster, never for access decisions.
    """

    sub: str
    role: Role
    permissions: frozenset[str]
    dev_bypass: bool = False
    guest: bool = False
    email: str | None = None
    name: str | None = None

    def can(self, permission: str) -> bool:
        return permission in self.permissions


@lru_cache
def _validator(domain: str, audience: str, roles_claim: str) -> TokenValidator:
    return TokenValidator(
        AuthSettings(auth0_domain=domain, auth0_audience=audience, auth0_roles_claim=roles_claim)
    )


Settings = Annotated[AuthSettings, Depends(get_auth_settings)]


def get_token_validator(settings: Settings) -> TokenValidator | None:
    """The tenant's validator, or None when Auth0 is not configured. Tests override this."""
    if not settings.configured:
        return None
    return _validator(settings.auth0_domain, settings.auth0_audience, settings.auth0_roles_claim)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Settings,
    validator: Annotated[TokenValidator | None, Depends(get_token_validator)],
) -> CurrentUser:
    """The authenticated caller. Raises 401, 403, or 503 as described above."""
    if credentials is None:
        guest = _guest_user(request, settings)
        if guest is not None:
            return guest
        dev_user = _dev_user(request, settings)
        if dev_user is not None:
            return dev_user
        raise _unauthorized("Sign in required")
    if validator is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth0 is not configured")
    try:
        claims = validator.decode(credentials.credentials)
    except InvalidToken as exc:
        raise _unauthorized(str(exc)) from exc
    except AuthUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return user_from_claims(claims, settings.auth0_roles_claim)


AuthenticatedUser = Annotated[CurrentUser, Depends(get_current_user)]


def user_from_claims(claims: dict[str, Any], roles_claim: str) -> CurrentUser:
    """Map verified claims to a user. A token without a FORESITE role is refused (403).

    Role names match regardless of case or surrounding spaces ("Supervisor" counts). A new
    account gets the `crew` role claim from the Auth0 Action before any role is assigned in
    the dashboard; its permissions list is then empty, so the crew permissions apply. Crew
    permissions show nothing until the account joins a team with a join code. A supervisor
    always needs its permissions assigned in Auth0.
    """
    assigned = claims.get(roles_claim)
    items = assigned if isinstance(assigned, list) else []
    names = {name.strip().lower() for name in items if isinstance(name, str)}
    if "supervisor" in names:
        role: Role = "supervisor"
    elif "crew" in names:
        role = "crew"
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account has no FORESITE role")
    granted = claims.get("permissions")
    if isinstance(granted, list) and (granted or role != "crew"):
        permissions = frozenset(p for p in granted if isinstance(p, str))
    else:
        # No permissions claim, or a new account's default crew role with none assigned yet.
        # Only crew, the least-privileged role, falls back: supervisors are always explicit.
        permissions = ROLE_PERMISSIONS[role]
    namespace = roles_claim.rsplit("/", 1)[0] + "/"
    return CurrentUser(
        sub=str(claims["sub"]),
        role=role,
        permissions=permissions,
        email=_text(claims.get(namespace + "email")),
        name=_text(claims.get(namespace + "name")),
    )


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip()[:200] or None


def require_permission(*permissions: str) -> Callable[..., CurrentUser]:
    """Dependency that allows the caller only if they hold every listed permission."""

    def dependency(user: AuthenticatedUser) -> CurrentUser:
        missing = [p for p in permissions if not user.can(p)]
        if missing:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"Missing permission: {', '.join(missing)}"
            )
        return user

    return dependency


def require_role(*allowed: Role) -> Callable[..., CurrentUser]:
    """Dependency that allows only the listed roles. Prefer `require_permission`."""

    def dependency(user: AuthenticatedUser) -> CurrentUser:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This action needs another role")
        return user

    return dependency


def _guest_user(request: Request, settings: AuthSettings) -> CurrentUser | None:
    if not settings.demo_guest_enabled:
        return None
    role = request.headers.get(DEMO_ROLE_HEADER, "").strip().lower()
    if role not in GUEST_USER_IDS:
        return None
    if request.method not in GUEST_READ_METHODS:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "The demo is read-only. Sign in to make changes."
        )
    if request.url.path.startswith(GUEST_BLOCKED_PATHS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign in to manage a team.")
    return CurrentUser(
        sub=GUEST_USER_IDS[role], role=role, permissions=GUEST_PERMISSIONS[role], guest=True
    )


def _dev_user(request: Request, settings: AuthSettings) -> CurrentUser | None:
    if not settings.dev_auth_bypass:
        return None
    role = request.headers.get(DEV_ROLE_HEADER, "").strip().lower()
    if role not in ROLES:
        return None
    host = request.client.host if request.client else ""
    if host not in LOOPBACK_HOSTS or any(h in request.headers for h in FORWARDING_HEADERS):
        logger.warning("Refused development auth bypass from a non-local request")
        return None
    name = request.headers.get(DEV_USER_HEADER, "").strip() or role
    logger.warning("DEV_AUTH_BYPASS is on: treating a local request as %s", role)
    return CurrentUser(
        sub=f"dev|{name}", role=role, permissions=ROLE_PERMISSIONS[role], dev_bypass=True
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )
