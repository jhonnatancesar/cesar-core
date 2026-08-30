import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "cesar_core"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
    return modules


def test_ai_provider_does_not_import_search() -> None:
    modules = _imported_modules(SRC / "ai" / "provider.py")
    assert not any(module.startswith("cesar_core.search") for module in modules)


def test_search_provider_does_not_import_ai() -> None:
    modules = _imported_modules(SRC / "search" / "provider.py")
    assert not any(module.startswith("cesar_core.ai") for module in modules)


def test_omniroute_client_does_not_import_ai_or_search_domain() -> None:
    """omniroute/ é transporte de baixo nível (TASK-118B) -- nunca conhece
    contratos de domínio de AI/Search (ADR 0006/0011)."""
    modules = _imported_modules(SRC / "omniroute" / "client.py")
    assert not any(module.startswith(("cesar_core.ai", "cesar_core.search")) for module in modules)


def test_omniroute_client_has_no_ai_or_search_business_methods() -> None:
    """OmniRouteClient expõe só transporte genérico -- nunca métodos de
    domínio como complete()/search() (isso é dos adapters em 118C/118D)."""
    from cesar_core.omniroute.client import OmniRouteClient

    assert not hasattr(OmniRouteClient, "complete")
    assert not hasattr(OmniRouteClient, "search")
