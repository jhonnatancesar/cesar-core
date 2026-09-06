"""Regressão de segurança: `reject_ssrf_target` barra alvos internos/privados
antes de qualquer chamada upstream (achado de revisão automática, SSRF em
`src/cesar_core/fetch/contracts.py`).

Usa literais de IP como host (nunca um nome de domínio real) para que
`socket.getaddrinfo` nunca precise de rede/DNS de verdade -- os testes
continuam herméticos (FASE E.2).
"""

import pytest

from cesar_core.fetch.contracts import reject_ssrf_target


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/internal",
        "http://127.0.0.1:80/internal",
        "https://127.0.0.1/internal",
        "http://[::1]/internal",
        "http://10.0.0.5/internal",
        "http://172.16.0.5/internal",
        "http://192.168.1.5/internal",
        "http://169.254.169.254/latest/meta-data/",  # metadata de nuvem
        "http://0.0.0.0/internal",
        "http://224.0.0.1/internal",  # multicast
    ],
)
def test_rejects_internal_and_private_targets(url: str) -> None:
    with pytest.raises(ValueError, match="internal or private"):
        reject_ssrf_target(url)


def test_accepts_a_public_ip_literal_on_the_default_port() -> None:
    # 8.8.8.8 é público e conhecido; literal de IP não bate em DNS de verdade.
    reject_ssrf_target("https://8.8.8.8/product")


def test_rejects_non_standard_ports() -> None:
    with pytest.raises(ValueError, match="port must be 80 or 443"):
        reject_ssrf_target("http://8.8.8.8:6379/")


def test_rejects_userinfo_in_url() -> None:
    with pytest.raises(ValueError, match="userinfo"):
        reject_ssrf_target("http://user:pass@8.8.8.8/product")


def test_case_and_trailing_dot_do_not_bypass_the_guard() -> None:
    with pytest.raises(ValueError, match="internal or private"):
        reject_ssrf_target("http://127.0.0.1./internal")
