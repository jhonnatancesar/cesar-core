"""Contrato neutro de AI Gateway do César Core.

Sem provider/model específico: nenhuma chamada real é feita nesta fase.
A implementação concreta (Gemini/Groq/OpenRouter/etc.) chega via
``ai/providers/`` em TASKs futuras, nunca a este módulo.

Duas camadas (ver ADR 0010): ``AIRequestPayload`` é o DTO HTTP público
-- nunca carrega identidade do chamador, só o payload funcional e os
requirements. ``AIRequest`` é a requisição interna de domínio: o César
Core a constrói combinando o ``ApplicationContext`` confiável (resolvido
por ``api/deps.py``, e futuramente por autenticação real na TASK-118E)
com um ``AIRequestPayload`` já validado. Nenhuma rota usa isso ainda
nesta TASK -- é só o contrato, pronto para quando a rota existir.
"""

from pydantic import BaseModel, Field

from cesar_core.applications.context import ApplicationContext
from cesar_core.policy.requirements import Requirements


class AIRequestPayload(BaseModel):
    """DTO HTTP público de uma requisição de AI.

    Não recebe ``application_id`` nem qualquer outro dado de identidade
    no corpo: quem está chamando é sempre resolvido pelo Core, nunca
    declarado pelo cliente dentro do payload.
    """

    requirements: Requirements
    prompt: str = Field(min_length=1)


class AIRequest(AIRequestPayload):
    """Requisição interna de domínio: contexto confiável + payload.

    Só o César Core cria esta instância, depois de resolver
    ``ApplicationContext`` -- nunca é deserializada diretamente do corpo
    de uma requisição HTTP.
    """

    context: ApplicationContext


class AIResponse(BaseModel):
    """Forma neutra de uma resposta de AI devolvida pelo César Core."""

    correlation_id: str = Field(min_length=1)
    content: str
