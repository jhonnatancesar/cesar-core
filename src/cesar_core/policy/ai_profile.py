"""Perfil de chamada declarado pelo cliente para uma execução de AI."""

from enum import StrEnum


class AIProfile(StrEnum):
    """Perfil que a aplicação chamadora declara para uma chamada de AI.

    Diferente de ``ApplicationContext`` (sempre resolvido pelo Core a
    partir da credencial autenticada, nunca do corpo -- ver ADR 0002),
    este campo precisa vir do cliente: o Core autentica a aplicação
    inteira (ex.: GG Oferta), não o usuário final por trás de uma
    chamada específica, então só a aplicação sabe se aquela chamada é
    de um usuário final ou de um fluxo ADMIN/DEV. Não é sinal de
    qualidade/custo (por isso não faz parte de ``Requirements``): a
    policy usa este campo para restringir quais rotas/providers de AI
    cada perfil pode alcançar (ex.: USER nunca alcança Groq/OpenRouter).
    """

    USER = "user"
    ADMIN_DEV = "admin_dev"
