from datetime import datetime

from pydantic import BaseModel

from cesar_core.applications.identity import ApplicationId, ApplicationState


class Application(BaseModel):
    """Um consumidor do César Core, com seu estado de habilitação no registry."""

    id: ApplicationId
    state: ApplicationState
    display_name: str
    client_id: str
    allowed_capabilities: frozenset[str] = frozenset()
    created_at: datetime | None = None
    updated_at: datetime | None = None
    protected: bool = False
