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


def test_fetch_provider_does_not_import_ai_or_search() -> None:
    modules = _imported_modules(SRC / "fetch" / "provider.py")
    assert not any(
        module.startswith(("cesar_core.ai", "cesar_core.search")) for module in modules
    )


def test_omniroute_client_does_not_import_ai_or_search_domain() -> None:
    """omniroute/ é transporte de baixo nível (TASK-118B) -- nunca conhece
    contratos de domínio de AI/Search/Fetch (ADR 0006/0011)."""
    modules = _imported_modules(SRC / "omniroute" / "client.py")
    assert not any(
        module.startswith(("cesar_core.ai", "cesar_core.search", "cesar_core.fetch"))
        for module in modules
    )


def test_omniroute_client_transport_methods_take_neutral_payloads() -> None:
    """chat_completions()/search() são transporte de baixo nível de verdade
    (118B é dona desse transporte, ver ADR 0012) -- mas recebem um dict
    neutro no formato nativo do OmniRoute, nunca um AIRequestPayload/
    SearchRequestPayload de negócio (isso seria o adapter de 118C/118D
    vazando pra dentro do transporte)."""
    import inspect

    from cesar_core.omniroute.client import OmniRouteClient

    for method_name in ("chat_completions", "search", "fetch"):
        signature = inspect.signature(getattr(OmniRouteClient, method_name))
        payload_annotation = str(signature.parameters["payload"].annotation)
        assert "dict" in payload_annotation
        assert "AIRequestPayload" not in payload_annotation
        assert "SearchRequestPayload" not in payload_annotation
