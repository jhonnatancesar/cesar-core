"""Suporte mínimo a testes ``async def`` sem depender de pytest-asyncio.

O projeto usa um hook local pequeno em vez de adicionar um plugin assíncrono
à suíte. Ele executa qualquer teste ``async def`` via ``asyncio.run()``; isso
é suficiente porque o client OmniRoute usa ``httpx.AsyncClient`` e os testes
não precisam de fixtures de event loop compartilhadas.
"""

import asyncio
import inspect
from threading import Lock
from time import monotonic
from uuid import uuid4

import pytest

from cesar_core.admin.storage import reset_store_for_tests


@pytest.fixture(autouse=True)
def _isolated_settings_env_file(tmp_path, monkeypatch):
    """Neutraliza o `.env` operacional de DEV (`C:\\cesar-core\\.env`) para
    toda a suíte -- FASE E.2.

    Toda classe de configuração do Core (``AIConfig``, ``SearchConfig``,
    ``FetchConfig``, ``OmniRouteConfig``, ``SecurityConfig``, ``AdminConfig``)
    declara ``env_file=".env"`` em ``model_config``, um caminho relativo
    resolvido pelo cwd do PROCESSO no momento em que a classe é instanciada
    -- nunca relativo ao pacote. Rodar os testes a partir da raiz do
    repositório (onde o `.env` real de DEV mora) faz qualquer instanciação
    "nua" (``Settings()`` sem ``_env_file=None``) herdar esse arquivo por
    acidente.

    A contaminação nunca é um valor plausível e ignorado silenciosamente:
    `pydantic-settings` (`DotEnvSettingsSource`) carrega TODAS as chaves do
    arquivo `.env`, mesmo as de um `env_prefix` diferente do da classe sendo
    instanciada -- ao contrário de uma variável de ambiente real do
    processo, que já chega filtrada por prefixo. Como toda `BaseSettings`
    aqui usa `extra="forbid"` (default), o resultado é `ValidationError`
    (`extra_forbidden`) para a chave de outra capability, não um valor
    errado silencioso -- mas ainda assim um teste cujo resultado depende de
    qual `.env` (se algum) existe no cwd de quem rodou o pytest, o que é
    exatamente o que esta fixture elimina.

    ``monkeypatch.chdir`` para um diretório vazio por teste é suficiente e
    não exige tocar as ~6 classes uma a uma nem seus ``model_config``: sem
    `.env` para encontrar, cada uma cai de volta a variáveis de ambiente
    reais (explicitamente setadas por outro fixture/teste via
    ``monkeypatch.setenv``, que não sofrem este problema) e aos defaults do
    próprio modelo -- nunca a um arquivo. Runtime de produção/DEV real
    (`python -m uvicorn ...`, containers) nunca passa por este `conftest.py`
    e continua lendo o `.env` normalmente.
    """
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True)
def isolated_quota_store(request, monkeypatch, tmp_path):
    """Units usam fake explícito; contracts nunca substituem o Redis real."""
    monkeypatch.setenv(
        "CESAR_CORE_SECURITY_QUOTA_NAMESPACE", f"cesar-core:test:{uuid4().hex}"
    )
    monkeypatch.setenv(
        "CESAR_CORE_ADMIN_DATABASE_PATH", str(tmp_path / "control-plane.sqlite3")
    )
    reset_store_for_tests()
    if request.node.get_closest_marker("contract"):
        yield
        reset_store_for_tests()
        return

    class MemoryTestStore:
        def __init__(self):
            self.values = {}
            self.lock = Lock()

        def probe(self):
            pass

        def consume(self, key, limit, window_ms):
            with self.lock:
                now = monotonic()
                count, expiry = self.values.get(key, (0, now + window_ms / 1000))
                if expiry <= now:
                    count, expiry = 0, now + window_ms / 1000
                allowed = int(count < limit)
                self.values[key] = (count + allowed, expiry)
                return allowed, max(0, round((expiry - now) * 1000))

        def reset(self):
            self.values.clear()

    store = MemoryTestStore()
    monkeypatch.setattr("cesar_core.security.quota.build_store", lambda config: store)
    yield
    reset_store_for_tests()


def pytest_pyfunc_call(pyfuncitem):
    test_func = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_func):
        return None

    params = inspect.signature(test_func).parameters
    kwargs = {name: pyfuncitem.funcargs[name] for name in params}
    asyncio.run(test_func(**kwargs))
    return True
