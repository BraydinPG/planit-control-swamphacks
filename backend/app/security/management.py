"""Give a user an Auth0 role through the Management API (supervisor onboarding).

A few calls, with a machine-to-machine app limited to `read:roles`, `create:role_members`
and `delete:role_members`: look up a role by name, add a user to it (a supervisor code is
redeemed), and take it away (the owner removes the supervisor). Auth0 stays the
authority for roles; the user's next sign-in carries the new role and its permissions.
"""

import time
from functools import lru_cache
from threading import Lock
from urllib.parse import quote

import httpx

from app.security.settings import AuthSettings, get_auth_settings


class ManagementUnavailable(Exception):
    """Auth0 refused or couldn't be reached; nothing was changed in the app."""


class Auth0Management:
    def __init__(
        self,
        domain: str,
        client_id: str,
        client_secret: str,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base = f"https://{domain}"
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = httpx.Client(timeout=timeout, transport=transport)
        self._token: tuple[str, float] | None = None
        self._roles: dict[str, str] = {}
        self._lock = Lock()

    @classmethod
    def from_settings(cls, settings: AuthSettings) -> "Auth0Management | None":
        if not settings.management_configured:
            return None
        return cls(
            settings.auth0_domain,
            settings.auth0_mgmt_client_id,
            settings.auth0_mgmt_client_secret.get_secret_value(),
        )

    def assign_role(self, user_id: str, role_name: str) -> None:
        """Add the user to the named role. Assigning a role they already have is a no-op."""
        role_id = self._role_id(role_name)
        self._call("POST", f"/api/v2/roles/{role_id}/users", json={"users": [user_id]})

    def remove_role(self, user_id: str, role_name: str) -> None:
        """Take the named role away from the user (needs `delete:role_members`)."""
        role_id = self._role_id(role_name)
        self._call(
            "DELETE", f"/api/v2/users/{quote(user_id, safe='')}/roles", json={"roles": [role_id]}
        )

    def _role_id(self, name: str) -> str:
        if name not in self._roles:
            roles = self._call("GET", "/api/v2/roles", params={"name_filter": name})
            # Capitalization doesn't matter (auth/SETUP.md): "Supervisor" is "supervisor".
            match = [r for r in roles or [] if str(r.get("name", "")).casefold() == name.casefold()]
            if not match:
                raise ManagementUnavailable(f"Auth0 has no role named {name!r}")
            self._roles[name] = match[0]["id"]
        return self._roles[name]

    def _access_token(self) -> str:
        with self._lock:
            if self._token and self._token[1] > time.monotonic():
                return self._token[0]
            try:
                response = self._http.post(
                    f"{self._base}/oauth/token",
                    json={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "audience": f"{self._base}/api/v2/",
                    },
                )
                response.raise_for_status()
                body = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise ManagementUnavailable(
                    f"Auth0 token request failed: {type(exc).__name__}"
                ) from exc
            token = body.get("access_token")
            if not token:
                raise ManagementUnavailable("Auth0 returned no access token")
            self._token = (token, time.monotonic() + max(60, body.get("expires_in", 3600) - 60))
            return token

    def _call(self, method: str, path: str, **kwargs):
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        try:
            response = self._http.request(method, f"{self._base}{path}", headers=headers, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ManagementUnavailable(
                f"Auth0 {method} {path.split('?')[0]} returned {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ManagementUnavailable(f"Auth0 request failed: {type(exc).__name__}") from exc
        return response.json() if response.content else None


@lru_cache
def _management() -> Auth0Management | None:
    return Auth0Management.from_settings(get_auth_settings())


def get_auth0_management() -> Auth0Management | None:
    """FastAPI dependency. None when the machine-to-machine app isn't configured."""
    return _management()
