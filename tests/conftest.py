"""Suporte mínimo a testes ``async def`` sem depender de pytest-asyncio.

O projeto usa um hook local pequeno em vez de adicionar um plugin assíncrono
à suíte. Ele executa qualquer teste ``async def`` via ``asyncio.run()``; isso
é suficiente porque o client OmniRoute usa ``httpx.AsyncClient`` e os testes
não precisam de fixtures de event loop compartilhadas.
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
