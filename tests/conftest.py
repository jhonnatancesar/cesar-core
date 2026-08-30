"""Suporte mínimo a testes ``async def`` sem depender de pytest-asyncio.

pytest-asyncio ainda não suporta pytest 9 (trava em ``pytest<9``), e o
projeto fixa ``pytest>=9.1,<10.0`` de propósito (mesma convenção do GG
Oferta). Este hook roda qualquer teste ``async def`` via
``asyncio.run()`` -- o client OmniRoute é assíncrono (``httpx.AsyncClient``).
"""

import asyncio
import inspect


def pytest_pyfunc_call(pyfuncitem):
    test_func = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_func):
        return None

    params = inspect.signature(test_func).parameters
    kwargs = {name: pyfuncitem.funcargs[name] for name in params}
    asyncio.run(test_func(**kwargs))
    return True
