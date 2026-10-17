from app.schemas.common import Schema


class Organization(Schema):
    id: str
    name: str


class TeamRef(Schema):
    """Compact team reference embedded in site summaries."""

    id: str
    name: str
    organization_id: str


class Team(Schema):
    """A team belongs to one organization and is assigned to at most one site."""

    id: str
    organization_id: str
    name: str
    site_id: str | None = None
