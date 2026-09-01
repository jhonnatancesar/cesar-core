"""Transporte de baixo nível do César Core para o OmniRoute (TASK-118B).

``client.py``/``config.py``/``auth.py``/``errors.py``/``models.py``:
``OmniRouteClient`` conhece os endpoints reais (``/api/health``,
``/v1/chat/completions``, ``/v1/search``), autenticação, timeout,
serialização/desserialização, correlation e normalização de erros --
mas nada de policy de aplicação, service_class, cost policy, GG Oferta,
Market Research, ou qual modelo/provider o negócio escolheu (isso nunca
é misturado aqui, ver ADR 0006/0011). AI e Search possuem cada um seu
próprio contrato e boundary de provider (``ai/provider.py``,
``search/provider.py``); os adapters concretos que montarão o payload de
negócio e usarão ``OmniRouteClient`` por baixo devem entrar em
``ai/providers/omniroute.py`` e ``search/providers/omniroute.py``
(TASK-118C/118D), cada um implementando o Protocol do seu próprio
domínio. O transporte em si (``chat_completions()``/``search()``) já
está implementado aqui.
"""
