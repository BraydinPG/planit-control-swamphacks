"""T027–T028: Auth0 token validation and role/permission dependencies.

Tokens are signed in the test with a throwaway RSA key and checked through a fake JWKS
client, so no Auth0 tenant or network is needed.
"""

from collections.abc import Iterator
from datetime import timedelta
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models
from app.security import (
    AuthenticatedUser,
    AuthSettings,
    CurrentUser,
    membership_for,
    require_permission,
    require_role,
    roles,
)
from tests.auth_fakes import DOMAIN, OTHER_KEY, FakeJwks, bearer, install, settings, token


def make_app(auth: AuthSettings, jwks: FakeJwks | None = None) -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    def me(user: AuthenticatedUser) -> dict[str, Any]:
        return {"sub": user.sub, "role": user.role, "permissions": sorted(user.permissions)}

    @app.post("/reports/review")
    def review(
        user: Annotated[CurrentUser, Depends(require_permission(roles.REVIEW_REPORTS))],
    ) -> dict[str, str]:
        return {"reviewer": user.sub}

    @app.get("/supervisor-only")
    def supervisor_only(
        user: Annotated[CurrentUser, Depends(require_role("supervisor"))],
    ) -> dict[str, str]:
        return {"role": user.role}

    install(app, auth, jwks)
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(make_app(settings()))


def test_missing_token_is_401_with_bearer_challenge(client: TestClient) -> None:
    response = client.get("/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "bad_token",
    [
        "not-a-jwt",
        token(key=OTHER_KEY),  # signed by someone else's key
        token(kid="unknown-key"),
        token(iss="https://evil.example/"),
        token(aud="https://some-other-api"),
        token(algorithm="HS256", key="shared-secret-that-is-at-least-32-bytes!"),
        token(sub=None),
    ],
    ids=["malformed", "wrong-key", "unknown-kid", "issuer", "audience", "hs256", "no-sub"],
)
def test_invalid_tokens_are_401(client: TestClient, bad_token: str) -> None:
    response = client.get("/me", headers=bearer(bad_token))
    assert response.status_code == 401


def test_expired_token_is_401(client: TestClient) -> None:
    response = client.get("/me", headers=bearer(token(expires_in=timedelta(minutes=-5))))
    assert response.status_code == 401
    assert response.json()["detail"] == "Token has expired"


def test_valid_token_returns_the_user_and_role(client: TestClient) -> None:
    granted = [roles.READ_ASSIGNED_SITES, roles.SUBMIT_REPORTS]
    response = client.get("/me", headers=bearer(token(["crew"], granted)))
    assert response.status_code == 200
    assert response.json() == {
        "sub": "auth0|demo-user",
        "role": "crew",
        "permissions": sorted(granted),
    }


def test_permissions_fall_back_to_the_role_when_the_claim_is_absent(client: TestClient) -> None:
    response = client.get("/me", headers=bearer(token(["supervisor"])))
    assert set(response.json()["permissions"]) == roles.ROLE_PERMISSIONS["supervisor"]


def test_token_without_a_planit_role_is_403(client: TestClient) -> None:
    response = client.get("/me", headers=bearer(token(["admin"])))
    assert response.status_code == 403


def test_crew_cannot_use_supervisor_actions(client: TestClient) -> None:
    crew = bearer(token(["crew"], sorted(roles.CREW_PERMISSIONS)))
    assert client.post("/reports/review", headers=crew).status_code == 403
    assert client.get("/supervisor-only", headers=crew).status_code == 403


def test_supervisor_can_use_supervisor_actions(client: TestClient) -> None:
    supervisor = bearer(token(["supervisor"], sorted(roles.SUPERVISOR_PERMISSIONS)))
    assert client.post("/reports/review", headers=supervisor).status_code == 200
    assert client.get("/supervisor-only", headers=supervisor).status_code == 200


def test_permission_claim_is_the_authority_when_present(client: TestClient) -> None:
    # A supervisor whose Auth0 role lacks review:reports cannot review.
    limited = bearer(token(["supervisor"], [roles.READ_ALL_SITES]))
    assert client.post("/reports/review", headers=limited).status_code == 403


def test_role_policy_matches_the_spec() -> None:
    crew, supervisor = roles.ROLE_PERMISSIONS["crew"], roles.ROLE_PERMISSIONS["supervisor"]
    supervisor_only = {
        roles.READ_ALL_SITES,
        roles.REVIEW_REPORTS,
        roles.CONFIRM_HAZARDS,
        roles.SEND_INSTRUCTIONS,
        roles.GENERATE_BRIEFINGS,
    }
    assert crew.isdisjoint(supervisor_only)
    assert crew < supervisor
    assert supervisor - crew == supervisor_only
    assert set(roles.PERMISSION_DESCRIPTIONS) == supervisor


def test_unconfigured_auth0_is_503_not_open() -> None:
    client = TestClient(make_app(AuthSettings(_env_file=None)))
    assert client.get("/me", headers=bearer(token())).status_code == 503
    assert client.get("/me").status_code == 401


def test_unreachable_jwks_is_503() -> None:
    client = TestClient(make_app(settings(), FakeJwks(down=True)))
    assert client.get("/me", headers=bearer(token())).status_code == 503


def test_dev_bypass_is_off_by_default() -> None:
    assert AuthSettings(_env_file=None).dev_auth_bypass is False
    local = TestClient(make_app(settings()), client=("127.0.0.1", 50000))
    assert local.get("/me", headers={"X-Dev-Role": "supervisor"}).status_code == 401


def test_dev_bypass_works_only_for_local_unforwarded_requests() -> None:
    app = make_app(settings(dev_auth_bypass=True))
    local = TestClient(app, client=("127.0.0.1", 50000))
    response = local.get("/me", headers={"X-Dev-Role": "crew"})
    assert response.status_code == 200
    assert response.json()["sub"] == "dev|crew"
    assert local.post("/reports/review", headers={"X-Dev-Role": "crew"}).status_code == 403
    assert local.post("/reports/review", headers={"X-Dev-Role": "supervisor"}).status_code == 200

    proxied = {"X-Dev-Role": "supervisor", "X-Forwarded-For": "203.0.113.9"}
    assert local.get("/me", headers=proxied).status_code == 401
    assert local.get("/me", headers={"X-Dev-Role": "admin"}).status_code == 401
    remote = TestClient(app, client=("203.0.113.9", 50000))
    assert remote.get("/me", headers={"X-Dev-Role": "supervisor"}).status_code == 401


def test_dev_bypass_never_overrides_a_bad_token() -> None:
    local = TestClient(make_app(settings(dev_auth_bypass=True)), client=("127.0.0.1", 50000))
    headers = {"X-Dev-Role": "supervisor", **bearer("not-a-jwt")}
    assert local.get("/me", headers=headers).status_code == 401


def test_settings_accept_a_domain_with_scheme_and_blank_values() -> None:
    parsed = AuthSettings(_env_file=None, auth0_domain=f"https://{DOMAIN}/", auth0_audience=" ")
    assert parsed.auth0_domain == DOMAIN
    assert parsed.auth0_audience is None
    assert parsed.configured is False


@pytest.fixture
def session() -> Iterator[Any]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add(models.Organization(id="org-1", name="Demo Org"))
        session.add(
            models.Membership(
                id="m-1", user_id="auth0|sup", organization_id="org-1", role="supervisor"
            )
        )
        session.commit()
        yield session


def test_membership_for_finds_the_callers_organization(session) -> None:
    supervisor = CurrentUser("auth0|sup", "supervisor", roles.SUPERVISOR_PERMISSIONS)
    stranger = CurrentUser("auth0|nobody", "crew", roles.CREW_PERMISSIONS)
    assert membership_for(session, supervisor).organization_id == "org-1"
    assert membership_for(session, stranger) is None
