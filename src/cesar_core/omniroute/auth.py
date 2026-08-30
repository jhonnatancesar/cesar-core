"""Autenticação de baixo nível contra o OmniRoute.

Só monta o header; nunca decide política de acesso (isso é do
César Core/OmniRoute, fora do escopo do transporte).
"""


def bearer_header(api_key: str) -> dict[str, str]:
    """Monta o header ``Authorization`` no formato que o OmniRoute espera."""
    return {"Authorization": f"Bearer {api_key}"}
