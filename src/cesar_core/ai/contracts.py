"""Contrato neutro de AI Gateway do César Core.

Sem provider/model específico: nenhuma chamada real é feita nesta fase.
A implementação concreta (Gemini/Groq/OpenRouter/etc.) pertence ao
OmniRoute e a TASKs futuras, nunca a este módulo.
"""

from pydantic import BaseModel, Field

from cesar_core.applications.identity import ApplicationId
from cesar_core.policy.requirements import Requirements


class AIRequest(BaseModel):
    """Forma neutra de uma requisição de AI feita ao César Core."""

    application_id: ApplicationId
    correlation_id: str = Field(min_length=1)
    requirements: Requirements
    prompt: str = Field(min_length=1)


class AIResponse(BaseModel):
    """Forma neutra de uma resposta de AI devolvida pelo César Core."""

    correlation_id: str = Field(min_length=1)
    content: str
