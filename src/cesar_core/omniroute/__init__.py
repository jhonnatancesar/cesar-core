"""Transporte de baixo nível do César Core para o OmniRoute (TASK-118B).

``client.py``/``config.py``/``auth.py``/``errors.py``/``models.py``:
transporte HTTP genérico (config, autenticação, timeout, serialização/
desserialização, correlation, normalização de erros). Nenhuma regra de
negócio, nenhuma seleção de provider, nenhum conhecimento de AI/Search
-- isso nunca é misturado aqui (ver ADR 0006/0011). AI e Search possuem
cada um seu próprio contrato e boundary de provider
(``ai/provider.py``, ``search/provider.py``); um adapter concreto que
usa este client entra depois em ``ai/providers/omniroute.py`` e
``search/providers/omniroute.py`` (TASK-118C/118D), cada um
implementando o Protocol do seu próprio domínio.
"""
