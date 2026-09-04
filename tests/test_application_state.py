import pytest
from pydantic import ValidationError

from cesar_core.applications.identity import ApplicationId, ApplicationState
from cesar_core.applications.models import Application


def test_application_state_supports_safe_disabled_bootstrap() -> None:
    assert {member.value for member in ApplicationState} == {
        "active",
        "disabled",
        "reserved",
    }


def test_application_model_requires_known_state() -> None:
    app = Application(
        id=ApplicationId.GG_OFERTA,
        state=ApplicationState.ACTIVE,
        display_name="GG Oferta",
        client_id="ggoferta-core-client",
    )
    assert app.state is ApplicationState.ACTIVE


def test_application_model_rejects_unknown_state() -> None:
    with pytest.raises(ValidationError):
        Application(
            id=ApplicationId.GG_OFERTA,
            state="unknown",
            display_name="x",
            client_id="client",
        )
