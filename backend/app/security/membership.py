"""Organization and team scope for the signed-in user.

Auth0 says which role a person has. The `memberships` table says which organization and
team they belong to, keyed by the Auth0 user id (`sub`). Routes use this for scope rules
such as "own organization only" and "assigned site only".
"""

from sqlalchemy.orm import Session

from app.db.models import Membership
from app.security.dependencies import CurrentUser


def membership_for(session: Session, user: CurrentUser) -> Membership | None:
    """The caller's membership row, or None when they are not linked to an organization.

    Treat None as "no access to organization data", never as "access to everything".
    """
    return session.query(Membership).filter(Membership.user_id == user.sub).one_or_none()
