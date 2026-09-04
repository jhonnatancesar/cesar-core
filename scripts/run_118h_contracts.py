"""Executa contracts existentes em processo DEV isolado, sem carregar dotenv.

Exige stack 118H já preparado em loopback. Não inicia containers nem lê o
banco original. Usar Python oficial, nunca apontar este harness para PROD.
"""

import argparse
import os
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configure(gg: Path) -> None:
    sys.path[:0] = [str(ROOT / "src"), str(gg / "backend")]
    # Não herdar flags, credenciais ou configuração de outro ambiente.
    for key in list(os.environ):
        if key.startswith(("CESAR_CORE_", "AISHOPPING_")):
            del os.environ[key]
    os.environ.update(
        CESAR_CORE_OMNIROUTE_BASE_URL="http://127.0.0.1:20128",
        CESAR_CORE_OMNIROUTE_TIMEOUT_SECONDS="90",
        CESAR_CORE_SECURITY_QUOTA_REDIS_URL="redis://127.0.0.1:16379/0",
        CESAR_CORE_SECURITY_QUOTA_NAMESPACE="cesar-core:test:118h",
        CESAR_CORE_CONTRACT_AUTO_SEARCH_PROVIDER="searxng-search",
        CESAR_CORE_AI_ENABLED="true",
        CESAR_CORE_AI_DEFAULT_MODEL="oc/mimo-v2.5-free",
        CESAR_CORE_AI_MODEL_ENFORCES_MAX_TOKENS="true",
        CESAR_CORE_SEARCH_ENABLED="true",
        CESAR_CORE_SEARCH_DEFAULT_PROVIDER="searxng-search",
        CESAR_CORE_SEARCH_PROVIDER_HEALTH_URL="http://127.0.0.1:18889/healthz",
        CESAR_CORE_SEARCH_TECHNICAL_DOCUMENTATION_PROVIDER="context7",
        CESAR_CORE_OMNIROUTE_AI_API_KEY_FILE=str(
            ROOT / ".secrets/omniroute_api_key"
        ),
        CESAR_CORE_OMNIROUTE_SEARCH_API_KEY_FILE=str(
            ROOT / "build/118h/search-key"
        ),
        CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE=str(
            ROOT / ".secrets/ggoferta-core-client-dev"
        ),
        AISHOPPING_ENVIRONMENT="development",
        AISHOPPING_RUN_SEARCH_CONTRACT="1",
        AISHOPPING_RUN_CESAR_CORE_CONTRACTS="1",
        AISHOPPING_CESAR_CORE_AI_ENABLED="true",
        AISHOPPING_CESAR_CORE_SEARCH_ENABLED="true",
        AISHOPPING_CESAR_CORE_SEARCH_FALLBACK_ENABLED="true",
        AISHOPPING_CESAR_CORE_API_KEY_FILE=str(gg / ".secrets/cesar-core-client-dev"),
        AISHOPPING_CESAR_CORE_MAX_TOKENS="512",
        AISHOPPING_FIRECRAWL_API_KEY_FILE=str(gg / ".secrets/firecrawl_api_key"),
    )
    from cesar_core.ai.config import AIConfig
    from cesar_core.config.settings import Settings
    from cesar_core.omniroute.config import OmniRouteConfig
    from cesar_core.search.config import SearchConfig
    from cesar_core.security.config import SecurityConfig

    for config in (AIConfig, Settings, OmniRouteConfig, SearchConfig, SecurityConfig):
        config.model_config["env_file"] = None
        config.model_config["hide_input_in_errors"] = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("core", "core-persistence", "gg", "resilience", "recovery", "serve"))
    parser.add_argument("--gg-repo", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--quota", type=int, default=60)
    parser.add_argument("--deny-search", action="store_true")
    parser.add_argument("--quota-namespace", default="cesar-core:test:118h")
    parser.add_argument("--quota-redis-port", type=int, choices=(16379, 16380), default=16379)
    args = parser.parse_args()
    gg = args.gg_repo.resolve()
    configure(gg)
    if not args.quota_namespace.startswith("cesar-core:test:"):
        raise ValueError("Harness requires isolated test namespace")
    os.environ["CESAR_CORE_SECURITY_QUOTA_NAMESPACE"] = args.quota_namespace
    os.environ["CESAR_CORE_SECURITY_QUOTA_REDIS_URL"] = f"redis://127.0.0.1:{args.quota_redis_port}/0"
    if args.phase == "core-persistence":
        import pytest

        os.environ["CESAR_CORE_RUN_PERSISTENCE_CONTRACT"] = "1"
        os.chdir(ROOT)
        return pytest.main(["tests/test_persistent_quota_contract.py", "--no-cov", "-q", "-rP",
                            "--tb=short", "-p", "no:cacheprovider",
                            "--basetemp=build/118h/persistence-tests"])
    if args.phase == "serve":
        serve(args)
        return 0
    if args.phase == "recovery":
        os.environ["AISHOPPING_RUN_118H_RECOVERY"] = "1"
        os.environ["CESAR_CORE_118H_SCRIPT"] = str(Path(__file__).resolve())
        import pytest

        os.chdir(gg)
        return pytest.main(["tests/test_118h_recovery_contract.py", "--no-cov", "-q",
                            "--tb=line", "-p", "no:cacheprovider",
                            f"--basetemp={ROOT / 'build/118h/recovery-tests'}"])
    if args.phase == "resilience":
        os.environ["AISHOPPING_RUN_118H_RESILIENCE"] = "1"
    import pytest

    common = ["--no-cov", "-q", "--tb=no", "-p", "no:cacheprovider"]
    if args.phase == "core":
        # Cada fixture histórica configura suas capabilities e seus arquivos.
        # Não herdar a configuração AI+Search usada pelo E2E do consumidor.
        keep = {
            "CESAR_CORE_OMNIROUTE_BASE_URL",
            "CESAR_CORE_OMNIROUTE_TIMEOUT_SECONDS",
            "CESAR_CORE_CONTRACT_AUTO_SEARCH_PROVIDER",
            "CESAR_CORE_SECURITY_QUOTA_REDIS_URL",
        }
        for key in list(os.environ):
            if key.startswith("CESAR_CORE_") and key not in keep:
                del os.environ[key]
        os.chdir(ROOT)
        return pytest.main(
            ["tests/test_omniroute_contract.py", "tests/test_security_contract.py"]
            + common + ["--basetemp=build/118h/core-tests"]
        )

    import httpx
    import uvicorn

    from cesar_core.api.app import create_app

    with socket.socket() as sock, socket.socket() as refused:
        sock.bind(("127.0.0.1", 0))
        refused.bind(("127.0.0.1", 0))
        base_url = f"http://127.0.0.1:{sock.getsockname()[1]}"
        os.environ["AISHOPPING_CESAR_CORE_BASE_URL"] = base_url
        os.environ["AISHOPPING_CORE_REFUSED_URL"] = (
            f"http://127.0.0.1:{refused.getsockname()[1]}"
        )
        server = uvicorn.Server(
            uvicorn.Config(create_app(), log_config=None, access_log=False)
        )
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.05)
            if not server.started:
                raise RuntimeError("Core isolado não iniciou")
            with httpx.Client(timeout=10, trust_env=False) as client:
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    try:
                        if client.get(base_url + "/ready").json().get("status") == "ok":
                            break
                    except (httpx.HTTPError, ValueError):
                        pass
                    time.sleep(0.5)
                else:
                    raise RuntimeError("Readiness DEV não recuperou; payload omitido")
            os.chdir(gg)
            selected = (
                ["tests/test_118h_resilience_contract.py"]
                if args.phase == "resilience"
                else ["tests/test_cesar_core_ai_contract.py", "tests/test_web_search_contract.py"]
            )
            return pytest.main(
                selected
                + common + [f"--basetemp={ROOT / 'build/118h/gg-tests'}"]
            )
        finally:
            server.should_exit = True
            thread.join(15)
            if thread.is_alive():
                raise RuntimeError("Core isolado não encerrou")


def serve(args):
    """Processo Core real; instrumentação passiva de socket apenas no harness."""
    import json
    import logging

    import httpx
    import uvicorn

    from cesar_core.api.app import create_app
    from cesar_core.applications.identity import ApplicationId
    from cesar_core.applications.registry import REGISTRY
    from cesar_core.telemetry.metrics import METRICS

    class FullRecordFormatter(logging.Formatter):
        def format(self, record):
            return json.dumps(record.__dict__, default=str)

    handler = logging.StreamHandler()
    handler.setFormatter(FullRecordFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)

    if not 1024 <= args.port <= 65535:
        raise ValueError("Porta DEV inválida")
    os.environ["CESAR_CORE_SECURITY_AI_REQUESTS_PER_MINUTE"] = str(args.quota)
    os.environ["CESAR_CORE_SECURITY_SEARCH_REQUESTS_PER_MINUTE"] = str(args.quota)
    if args.deny_search:
        entry = REGISTRY[ApplicationId.GG_OFERTA]
        REGISTRY[ApplicationId.GG_OFERTA] = entry.model_copy(
            update={"allowed_capabilities": frozenset({"ai"})}
        )
    original = httpx.AsyncHTTPTransport.handle_async_request

    async def observe(transport, request):
        if request.url.port == 20128:
            METRICS.increment("cesar_core_118h_wire_total", path=request.url.path)
        return await original(transport, request)

    httpx.AsyncHTTPTransport.handle_async_request = observe
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    raise SystemExit(main())
