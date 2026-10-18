"""The Auth0 Management client that gives and takes the supervisor role (no network)."""

import json

import httpx
import pytest

from app.security.management import Auth0Management, ManagementUnavailable
from app.security.settings import AuthSettings


def fake_auth0(calls, *, roles=None, assign_status=201, token_status=200):
    roles = roles if roles is not None else [{"id": "rol_sup", "name": "supervisor"}]

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.headers.get("Authorization")))
        if request.url.path == "/oauth/token":
            body = json.loads(request.content)
            assert body["grant_type"] == "client_credentials"
            assert body["audience"] == "https://tenant.example/api/v2/"
            return httpx.Response(token_status, json={"access_token": "mgmt", "expires_in": 86400})
        if request.url.path == "/api/v2/roles":
            assert request.url.params["name_filter"] == "supervisor"
            return httpx.Response(200, json=roles)
        if (
            request.method == "DELETE"
            and request.url.raw_path == b"/api/v2/users/auth0%7Cnew/roles"
        ):
            assert json.loads(request.content) == {"roles": ["rol_sup"]}
            return httpx.Response(assign_status if assign_status != 201 else 204)
        if request.url.path == "/api/v2/roles/rol_sup/users":
            assert json.loads(request.content) == {"users": ["auth0|new"]}
            return httpx.Response(assign_status)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def client(transport):
    return Auth0Management("tenant.example", "id", "secret", transport=transport)


def test_assigns_the_role_and_reuses_the_token():
    calls = []
    management = client(fake_auth0(calls))
    management.assign_role("auth0|new", "supervisor")
    management.assign_role("auth0|new", "supervisor")
    paths = [path for _, path, _ in calls]
    assert paths.count("/oauth/token") == 1 and paths.count("/api/v2/roles") == 1
    assert paths.count("/api/v2/roles/rol_sup/users") == 2
    assert all(auth == "Bearer mgmt" for _, path, auth in calls if path.startswith("/api/v2"))


@pytest.mark.parametrize("kwargs", [{"roles": []}, {"assign_status": 403}, {"token_status": 401}])
def test_any_auth0_refusal_raises(kwargs):
    with pytest.raises(ManagementUnavailable):
        client(fake_auth0([], **kwargs)).assign_role("auth0|new", "supervisor")


def test_not_configured_without_the_secret():
    settings = AuthSettings(
        _env_file=None, auth0_domain="tenant.example", auth0_mgmt_client_id="id"
    )
    assert Auth0Management.from_settings(settings) is None
    full = AuthSettings(
        _env_file=None,
        auth0_domain="https://tenant.example/",
        auth0_mgmt_client_id="id",
        auth0_mgmt_client_secret="hunter2-value",
    )
    assert Auth0Management.from_settings(full) is not None
    assert "hunter2-value" not in repr(full)


def test_role_names_ignore_capitalization():
    calls = []
    transport = fake_auth0(calls, roles=[{"id": "rol_sup", "name": "Supervisor"}])
    client(transport).assign_role("auth0|new", "supervisor")
    assert ("POST", "/api/v2/roles/rol_sup/users", "Bearer mgmt") in calls


def test_removes_the_role_from_the_user():
    calls = []
    client(fake_auth0(calls)).remove_role("auth0|new", "supervisor")
    assert ("DELETE", "/api/v2/users/auth0|new/roles", "Bearer mgmt") in calls
    with pytest.raises(ManagementUnavailable):
        client(fake_auth0([], assign_status=403)).remove_role("auth0|new", "supervisor")
