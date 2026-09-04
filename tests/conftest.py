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


@pytest.fixture(autouse=True)
def isolated_quota_store(request, monkeypatch):
    """Units usam fake explícito; contracts nunca substituem o Redis real."""
    monkeypatch.setenv("CESAR_CORE_SECURITY_QUOTA_NAMESPACE", f"cesar-core:test:{uuid4().hex}")
    if request.node.get_closest_marker("contract"):
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


def pytest_pyfunc_call(pyfuncitem):
    test_func = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_func):
        return None

    params = inspect.signature(test_func).parameters
    kwargs = {name: pyfuncitem.funcargs[name] for name in params}
    asyncio.run(test_func(**kwargs))
    return True
