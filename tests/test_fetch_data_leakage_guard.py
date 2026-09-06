"""Regressão de segurança: FASE E.3 (vazamento de dados no Fetch/Enrichment).

Cobre três defesas independentes de `src/cesar_core/fetch/contracts.py`,
deliberadamente separadas de `reject_ssrf_target` (SSRF é sobre PRA ONDE a
URL aponta na rede; isto aqui é sobre O QUE a URL carrega como dado):

- `reject_sensitive_query_target`: recusa a URL inteira (nunca mascara) se a
  query carregar um parâmetro de alta confiança ou uma URL assinada de nuvem.
- `strip_url_fragment`: remove `#fragment` antes de qualquer uso interno.
- `FetchRequestPayload` com `extra="forbid"`: campo desconhecido no corpo é
  rejeitado antes de qualquer chamada ao manager/upstream.

Usa apenas hosts públicos/sintéticos e segredos claramente falsos
(``FAKE_AUDIT_TOKEN_123`` e afins) -- nunca um valor real.
"""

import pytest
from pydantic import ValidationError

from cesar_core.fetch.contracts import (
    FetchRequestPayload,
    reject_sensitive_query_target,
    strip_url_fragment,
)
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass

_REQUIREMENTS = Requirements(
    service_class=ServiceClass.STANDARD, cost_policy=CostPolicy.FREE_ONLY
)


# --- reject_sensitive_query_target -----------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://shop.example.test/product?access_token=FAKE_AUDIT_TOKEN_123",
        "https://shop.example.test/product?refresh_token=FAKE_AUDIT_TOKEN_123",
        "https://shop.example.test/product?oauth_token=FAKE_AUDIT_TOKEN_123",
        "https://shop.example.test/product?api_key=FAKE_AUDIT_TOKEN_123",
        "https://shop.example.test/product?apikey=FAKE_AUDIT_TOKEN_123",
        "https://shop.example.test/product?api-key=FAKE_AUDIT_TOKEN_123",
        "https://shop.example.test/product?Authorization=FAKE_AUDIT_TOKEN_123",
        "https://shop.example.test/product?password=FAKE_AUDIT_TOKEN_123",
        "https://shop.example.test/product?passwd=FAKE_AUDIT_TOKEN_123",
        "https://shop.example.test/product?session=FAKE_AUDIT_TOKEN_123",
        "https://shop.example.test/product?session_id=FAKE_AUDIT_TOKEN_123",
        "https://shop.example.test/product?jwt=FAKE_AUDIT_TOKEN_123",
    ],
)
def test_rejects_high_confidence_sensitive_query_keys(url: str) -> None:
    with pytest.raises(ValueError, match="sensitive credentials or tokens"):
        reject_sensitive_query_target(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://cdn.example.test/img.jpg?X-Amz-Signature=FAKE_SIG&X-Amz-Credential=FAKE_CRED",
        "https://storage.googleapis.com/bucket/obj?X-Goog-Signature=FAKE_SIG",
    ],
)
def test_rejects_known_cloud_signed_urls(url: str) -> None:
    with pytest.raises(ValueError, match="cloud-signed request"):
        reject_sensitive_query_target(url)


def test_rejects_azure_sas_by_sig_and_sv_combination() -> None:
    url = "https://acct.blob.core.windows.net/c/blob?sv=2024-01-01&sig=FAKE_SAS"
    with pytest.raises(ValueError, match="Azure SAS"):
        reject_sensitive_query_target(url)


def test_does_not_reject_lone_sig_or_sv_without_the_other() -> None:
    reject_sensitive_query_target("https://shop.example.test/product?sig=abc123")
    reject_sensitive_query_target("https://shop.example.test/product?sv=2024-01-01")


@pytest.mark.parametrize(
    "url",
    [
        "https://shop.example.test/product?id=123",
        "https://shop.example.test/product?sku=ABC-1",
        "https://shop.example.test/product?ref=homepage",
        "https://shop.example.test/product?page=2",
        "https://shop.example.test/product?category=notebooks",
        "https://shop.example.test/product?code=PROMO10",
        "https://shop.example.test/product?key=featured",
        "https://shop.example.test/product",
    ],
)
def test_does_not_reject_common_ecommerce_query_parameters(url: str) -> None:
    reject_sensitive_query_target(url)


# --- strip_url_fragment -----------------------------------------------------


def test_strips_fragment_from_url() -> None:
    result = strip_url_fragment("https://shop.example.test/product?id=1#reviews")
    assert result == "https://shop.example.test/product?id=1"


def test_leaves_url_without_fragment_unchanged() -> None:
    url = "https://shop.example.test/product?id=1"
    assert strip_url_fragment(url) == url


def test_strips_fragment_that_itself_carries_sensitive_looking_data() -> None:
    result = strip_url_fragment(
        "https://shop.example.test/callback#access_token=FAKE_AUDIT_TOKEN_123"
    )
    assert result == "https://shop.example.test/callback"


# --- FetchRequestPayload: integração dos dois guards + extra="forbid" ------


def test_payload_strips_fragment_end_to_end() -> None:
    payload = FetchRequestPayload(
        requirements=_REQUIREMENTS,
        url="https://shop.example.test/product?id=1#reviews",
    )
    assert payload.url == "https://shop.example.test/product?id=1"


def test_payload_rejects_sensitive_query_end_to_end() -> None:
    with pytest.raises(ValidationError, match="sensitive credentials or tokens"):
        FetchRequestPayload(
            requirements=_REQUIREMENTS,
            url="https://shop.example.test/product?session_id=FAKE_AUDIT_TOKEN_123",
        )


def test_payload_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError, match="extra"):
        FetchRequestPayload(
            requirements=_REQUIREMENTS,
            url="https://shop.example.test/product",
            provider="firecrawl",
        )
