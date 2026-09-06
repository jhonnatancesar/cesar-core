"""FASE E.2 -- regressão: testes nunca herdam o `.env` operacional de DEV.

Root cause: toda classe de configuração (`AIConfig`, `SearchConfig`,
`FetchConfig`, `OmniRouteConfig`, `SecurityConfig`, `AdminConfig`) declara
``env_file=".env"``, resolvido pelo cwd do processo -- nunca pelo pacote.
`pydantic-settings` carrega TODAS as chaves de um `.env` encontrado, mesmo
as de outro `env_prefix` (ao contrário de uma env var real do processo, já
filtrada por prefixo antes de chegar ao modelo); como toda classe usa
`extra="forbid"` (default), isso vira `ValidationError` sempre que a suíte
roda com cwd = raiz do repositório (onde mora o `.env` real de DEV) e algum
teste instancia uma classe sem `_env_file=None`. A fixture autouse
``_isolated_settings_env_file`` (`conftest.py`) neutraliza isso via
``monkeypatch.chdir`` para um diretório vazio por teste -- sem tocar as
~6 classes uma a uma.

Nenhum valor real de `.env`/secret é usado aqui -- só sintéticos.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from cesar_core.security.config import SecurityConfig

REPO_ROOT = Path(__file__).resolve().parent.parent

_POISONED_ENV_CONTENT = (
    "CESAR_CORE_AI_ENABLED=true\nCESAR_CORE_SECURITY_AI_REQUESTS_PER_MINUTE=999999\n"
)


def test_bare_instantiation_ignores_a_poisoned_env_file_outside_the_cwd(
    tmp_path_factory, monkeypatch
):
    """(A)/(B) Controle sintético, sem nenhum valor real: um `.env` com uma
    chave de OUTRA capability (`CESAR_CORE_AI_ENABLED`) quebra
    `SecurityConfig()` nua quando o cwd aponta pra ele (prova que o "veneno"
    é real e a classe é vulnerável sem isolamento) -- mas some assim que o
    cwd muda para um diretório limpo, mesmo o arquivo poluído continuando a
    existir em disco. `ai_requests_per_minute` (campo que o teste não
    forneceu) permanece o default (60), nunca 999999."""
    poisoned_dir = tmp_path_factory.mktemp("poisoned")
    (poisoned_dir / ".env").write_text(_POISONED_ENV_CONTENT, encoding="utf-8")

    monkeypatch.chdir(poisoned_dir)
    with pytest.raises(ValidationError, match="cesar_core_ai_enabled"):
        SecurityConfig()

    clean_dir = tmp_path_factory.mktemp("clean")
    monkeypatch.chdir(clean_dir)
    config = SecurityConfig()
    assert config.ai_requests_per_minute == 60
    assert config.gg_oferta_api_key_file is None


def test_explicit_override_wins_over_any_env_file_value(tmp_path, monkeypatch):
    """Config que o teste FORNECE explicitamente sempre vence -- nunca um
    valor sintético "vazado" de um `.env` no cwd."""
    (tmp_path / ".env").write_text(
        "CESAR_CORE_SECURITY_AI_REQUESTS_PER_MINUTE=999999\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    config = SecurityConfig(ai_requests_per_minute=7)

    assert config.ai_requests_per_minute == 7


def test_autouse_fixture_already_isolates_every_test_by_default():
    """Nenhum teste normal (sem chdir manual) precisa se preocupar com
    isolamento: a fixture autouse (`conftest.py`) já garante que o cwd
    durante QUALQUER teste nunca é a raiz do repositório -- onde mora o
    `.env` real de DEV, se existir -- e `SecurityConfig()` nua sempre
    devolve os defaults da classe."""
    assert Path.cwd() != REPO_ROOT
    config = SecurityConfig()
    assert config.ai_requests_per_minute == 60


def test_isolation_result_is_identical_regardless_of_pytest_launch_cwd(tmp_path):
    """(C)/(D) Rodar esta suíte a partir da raiz do repositório (onde mora o
    `.env` real de DEV, se existir) ou de um diretório completamente alheio
    produz o MESMO resultado -- a fixture autouse neutraliza o `.env` de
    qualquer cwd de lançamento.

    Sobe dois subprocessos reais de pytest (não dá para provar isso dentro
    do mesmo processo, que só tem um cwd por execução), usando caminho
    absoluto do arquivo de teste para que o cwd do subprocesso não afete a
    descoberta do arquivo -- só o comportamento de `env_file` é testado.
    `--basetemp` próprio evita o bloqueio de ACL conhecido e preexistente
    do diretório temporário compartilhado do Windows (não é o bug desta
    fase; ver runbook), que bloquearia os dois subprocessos igualmente.
    """
    target_file = REPO_ROOT / "tests" / "test_settings_env_isolation.py"
    node_id = (
        f"{target_file}::test_autouse_fixture_already_isolates_every_test_by_default"
    )

    def run(cwd: Path, basetemp: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "--no-cov",
                "-q",
                "-c",
                str(REPO_ROOT / "pyproject.toml"),
                f"--basetemp={basetemp}",
                node_id,
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )

    from_repo_root = run(REPO_ROOT, tmp_path / "bt-root")
    from_unrelated_dir = run(tmp_path, tmp_path / "bt-other")

    assert from_repo_root.returncode == 0, from_repo_root.stdout[-2000:]
    assert from_unrelated_dir.returncode == 0, from_unrelated_dir.stdout[-2000:]
    # (E) nenhum segredo real é lido/impresso por este teste em nenhum ramo.
