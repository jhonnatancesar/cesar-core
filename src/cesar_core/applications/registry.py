"""Registry persistente de aplicações consumidoras."""

from collections.abc import Iterator, MutableMapping

from cesar_core.admin.storage import get_store
from cesar_core.applications.identity import ApplicationId, ApplicationState
from cesar_core.applications.models import Application


def get_application(application_id: ApplicationId) -> Application:
    row = get_store().get_application(application_id.value)
    if row is None:
        raise KeyError(application_id)
    return Application(
        id=ApplicationId(row["id"]),
        state=ApplicationState(row["state"]),
        display_name=row["display_name"],
        client_id=row["client_id"],
        allowed_capabilities=frozenset(row["capabilities"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        protected=row["protected"],
    )


def list_applications() -> list[Application]:
    return [
        get_application(ApplicationId(row["id"]))
        for row in get_store().list_applications()
    ]


def is_active(application_id: ApplicationId) -> bool:
    return get_application(application_id).state is ApplicationState.ACTIVE


def allows_capability(application_id: ApplicationId, capability: str) -> bool:
    application = get_application(application_id)
    return (
        application.state is ApplicationState.ACTIVE
        and capability in application.allowed_capabilities
    )


class _RegistryCompatibilityView(MutableMapping[ApplicationId, Application]):
    """Vista de mapping para consumidores históricos; SQLite segue autoritativo."""

    def __getitem__(self, key: ApplicationId) -> Application:
        return get_application(key)

    def __setitem__(self, key: ApplicationId, value: Application) -> None:
        row = get_store().get_application(key.value)
        if row is None:
            raise KeyError(key)
        get_store().update_application(
            key.value,
            display_name=value.display_name,
            state=value.state.value,
            capabilities=set(value.allowed_capabilities),
            quotas={
                cap: row["quotas"].get(cap, 60) for cap in value.allowed_capabilities
            },
        )

    def __delitem__(self, key: ApplicationId) -> None:
        raise TypeError("Applications cannot be deleted")

    def __iter__(self) -> Iterator[ApplicationId]:
        return (ApplicationId(row["id"]) for row in get_store().list_applications())

    def __len__(self) -> int:
        return len(get_store().list_applications())


REGISTRY: MutableMapping[ApplicationId, Application] = _RegistryCompatibilityView()
