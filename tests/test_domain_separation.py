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


def test_omniroute_package_defines_no_protocol_yet() -> None:
    omniroute_dir = SRC / "omniroute"
    python_files = list(omniroute_dir.glob("*.py"))
    assert len(python_files) == 1  # apenas __init__.py: nenhum Protocol ainda
    for path in python_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        class_defs = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        assert class_defs == []
