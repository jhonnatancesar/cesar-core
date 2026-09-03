"""Leitura segura e comparação de credenciais de aplicações."""

from pathlib import Path
from secrets import compare_digest


def read_secret(path: Path) -> str:
    """Lê um segredo de arquivo sem incluí-lo em mensagens de erro."""
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError("Application credential file is empty")
    return value


def credential_matches(candidate: str, expected: str) -> bool:
    """Compara credenciais em tempo constante."""
    return compare_digest(candidate.encode(), expected.encode())
