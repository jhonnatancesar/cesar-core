"""O provisionador de teste não pode remover recursos de outro ambiente."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def stack(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[1] / "scripts/stack_118h_dev.py"
    spec = importlib.util.spec_from_file_location("stack_118h", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "DATA", tmp_path / "build/118h")
    return module


def test_does_not_prepare_from_running_original(stack, monkeypatch):
    monkeypatch.setattr(stack, "docker", lambda *args: json.dumps([{"State": {"Running": True}}]))
    with pytest.raises(RuntimeError, match="original ativa"):
        stack.up()
    assert not stack.DATA.exists()


def test_does_not_delete_foreign_container(stack, monkeypatch):
    monkeypatch.setattr(stack.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout=json.dumps([{"Config": {"Labels": {"cesar.task": "other"}}}])
    ))
    with pytest.raises(RuntimeError, match="Container não pertence"):
        stack.down()


def test_does_not_delete_unmarked_directory(stack, monkeypatch):
    stack.DATA.mkdir(parents=True)
    monkeypatch.setattr(stack.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1))
    with pytest.raises(RuntimeError, match="Diretório não pertence"):
        stack.down()
    assert stack.DATA.exists()
