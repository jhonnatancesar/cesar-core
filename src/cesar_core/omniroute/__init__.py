"""Reserva de espaço para o OmniRoute -- transporte de baixo nível.

Esta TASK (118A) não define nenhum Protocol aqui. `omniroute/` é
reservado para, em TASK futura (118B+), abrigar o cliente HTTP de baixo
nível do OmniRoute (transporte/client/config/models/erros) -- nunca uma
abstração compartilhada entre AI e Search. AI e Search possuem cada um
seu próprio contrato e boundary de provider (``ai/provider.py``,
``search/provider.py``); um adapter concreto que fala com o OmniRoute
entra depois em ``ai/providers/omniroute.py`` e
``search/providers/omniroute.py``, cada um implementando o Protocol do
seu próprio domínio. Nenhuma chamada real é feita por este pacote ainda.
"""
