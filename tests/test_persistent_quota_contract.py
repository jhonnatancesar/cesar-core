"""Redis/AOF, processos Core e dependências reais; exclusivo da stack DEV 118H."""

import json
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from cesar_core.applications.identity import ApplicationId
from cesar_core.security.config import SecurityConfig
from cesar_core.security.errors import QuotaExceededError, QuotaStoreUnavailableError
from cesar_core.security.quota import QuotaLimiter, probe_quota_storage

pytestmark = [pytest.mark.contract, pytest.mark.skipif(
    os.environ.get("CESAR_CORE_RUN_PERSISTENCE_CONTRACT") != "1",
    reason="Exige stack 118H descartável e opt-in explícito",
)]
ROOT = Path(__file__).resolve().parents[1]
GG = Path("C:/AIShoppingAgent/AIShoppingAgent")
DOCKER = Path(os.environ["LOCALAPPDATA"]) / "Programs/DockerDesktop/resources/bin/docker.exe"


def docker(action, name):
    assert name in {"redis-118h-validation", "omniroute-118h-validation", "searxng-118h-validation"}
    inspected = subprocess.run([str(DOCKER), "inspect", name], capture_output=True, text=True, check=True)
    assert json.loads(inspected.stdout)[0]["Config"]["Labels"]["cesar.task"] == "118h"
    result = subprocess.run([str(DOCKER), action, name], capture_output=True, timeout=40)
    assert result.returncode == 0, "Operação isolada Docker falhou; saída omitida"


@pytest.fixture
def redis_client():
    config = SecurityConfig()
    assert config.quota_redis_url == "redis://127.0.0.1:16379/0"
    assert config.quota_namespace.startswith("cesar-core:test:")
    client = Redis.from_url(config.quota_redis_url, decode_responses=True)
    probe_quota_storage()
    yield client
    client.close()


def quota_key(capability="search"):
    return f"{SecurityConfig().quota_namespace}:gg_oferta:{capability}"


def admit(limit=13, window=60):
    try:
        QuotaLimiter(window_seconds=window).check(ApplicationId.GG_OFERTA, "search", limit)
        return 1
    except QuotaExceededError:
        return 0


def test_real_atomic_quota_concurrent_threads_and_processes(redis_client):
    with ThreadPoolExecutor(max_workers=12) as pool:
        assert sum(pool.map(lambda _: admit(), range(48))) == 13
    assert redis_client.get(quota_key()) == "13"
    # Outra capability, mesmo namespace, concorrência entre interpretadores reais.
    program = """
from cesar_core.security.config import SecurityConfig
SecurityConfig.model_config['env_file'] = None
from cesar_core.security.quota import QuotaLimiter
from cesar_core.security.errors import QuotaExceededError
from cesar_core.applications.identity import ApplicationId
n = 0
for _ in range(10):
    try:
        QuotaLimiter().check(ApplicationId.GG_OFERTA, 'ai', 13)
        n += 1
    except QuotaExceededError:
        pass
print(n)
"""
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    processes = [subprocess.Popen([sys.executable, "-c", program], env=environment,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
    results = []
    for process in processes:
        out, _ = process.communicate(timeout=30)
        assert process.returncode == 0, "Worker falhou; saída omitida"
        results.append(int(out))
    assert sum(results) == 13
    assert redis_client.get(quota_key("ai")) == "13"
    print("Concorrência real: 48 requests em 12 threads/13 admissões; 40 requests em 4 processos/13 admissões")


def test_real_fixed_window_expiry_and_corruption_fail_closed(redis_client):
    assert admit(limit=1, window=1) == 1
    ttl = redis_client.pttl(quota_key())
    assert admit(limit=1, window=1) == 0
    assert redis_client.pttl(quota_key()) <= ttl
    assert redis_client.get(quota_key()) == "1"
    deadline = time.monotonic() + 3
    while redis_client.exists(quota_key()) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert admit(limit=1, window=1) == 1
    for value in ("broken", "0", "1.5"):
        redis_client.set(quota_key(), value, px=1000)
        with pytest.raises(QuotaStoreUnavailableError):
            admit(limit=2)
    redis_client.set(quota_key(), "1")  # contador sem TTL não pode ser resetado.
    with pytest.raises(QuotaStoreUnavailableError):
        admit(limit=2)


def test_real_redis_aof_restart_preserves_quota(redis_client):
    assert admit(limit=1, window=300) == 1
    ttl = redis_client.pttl(quota_key())
    docker("kill", "redis-118h-validation")  # SIGKILL: não depender de snapshot no shutdown.
    docker("start", "redis-118h-validation")
    # Docker start confirma o processo, não o término do carregamento AOF.
    # Espera apenas de leitura no harness; consumo EVAL nunca é repetido.
    deadline = time.monotonic() + 10
    while True:
        try:
            probe_quota_storage()
            break
        except QuotaStoreUnavailableError as exc:
            if exc.code != "quota_store_unavailable" or time.monotonic() >= deadline:
                raise
            time.sleep(0.1)
    assert redis_client.get(quota_key()) == "1"
    assert 0 < redis_client.pttl(quota_key()) <= ttl
    assert admit(limit=1, window=300) == 0
    print("Redis reiniciado: AOF preservou consumo=1 e TTL; nova tentativa negada")


class Core:
    def __init__(self, directory, limit, redis_port=16379, ready_status="ok"):
        self.directory, self.limit = directory, limit
        self.redis_port, self.ready_status = redis_port, ready_status
        self.process = None
        self.logs = []
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.headers = {
            "Authorization": "Bearer " + (ROOT / ".secrets/ggoferta-core-client-dev").read_text().strip(),
            "X-Service": "quota_validation", "X-Purpose": "web_research",
            "X-Correlation-ID": "118h-persistent-quota",
        }

    def start(self):
        path = self.directory / f"core-{len(self.logs)}.log"
        self.logs.append(path)
        self.log = path.open("wb")
        self.process = subprocess.Popen([
            sys._base_executable, str(ROOT / "scripts/run_118h_contracts.py"), "serve", "--gg-repo", str(GG),
            "--port", str(self.port), "--quota", str(self.limit),
            "--quota-namespace", SecurityConfig().quota_namespace,
            "--quota-redis-port", str(self.redis_port),
        ], stdout=self.log, stderr=subprocess.STDOUT, cwd=ROOT)
        self.ready(self.ready_status)
        return self.process.pid

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=15)
            self.log.close()
            self.process = None

    def get(self, path):
        return httpx.get(self.url + path, timeout=10, trust_env=False)

    def ready(self, expected):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                if self.get("/ready").json()["status"] == expected:
                    return
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(0.2)
        pytest.fail("Readiness não convergiu; logs omitidos")

    def search(self, query="Python programming language official documentation"):
        return httpx.post(self.url + "/v1/search", headers=self.headers,
                          json={"query": query, "max_results": 3,
                                "requirements": {"service_class": "standard", "cost_policy": "free_only"}},
                          timeout=100, trust_env=False)

    def wire(self):
        return [line for line in self.get("/metrics").text.splitlines()
                if line.startswith("cesar_core_118h_wire_total")]


@pytest.fixture
def core_factory(tmp_path, redis_client, caplog):
    cores = []

    def factory(limit=60, **kwargs):
        directory = tmp_path / str(len(cores))
        directory.mkdir()
        core = Core(directory, limit, **kwargs)
        cores.append(core)
        core.start()
        return core

    yield factory
    output = caplog.text + repr([record.__dict__ for record in caplog.records])
    for core in cores:
        core.stop()
        for log in core.logs:
            output += log.read_text(errors="replace")
            log.unlink()
    for name in ("ggoferta-core-client-dev", "omniroute_api_key"):
        secret = (ROOT / ".secrets" / name).read_text().strip()
        assert secret not in output, "Credencial detectada; valor omitido"


def test_real_core_restart_preserves_quota_pre_upstream(core_factory, redis_client):
    core = core_factory(limit=2)
    assert core.get("/ready").json() == {"status": "ok", "core": "available"}
    first = core.search()
    assert first.status_code == 200
    assert 1 <= len(first.json()["results"]) <= 3
    assert redis_client.get(quota_key()) == "1"
    ttl = redis_client.pttl(quota_key())
    old_pid = core.process.pid
    core.stop()
    assert core.start() != old_pid
    assert redis_client.get(quota_key()) == "1"
    assert 0 < redis_client.pttl(quota_key()) <= ttl
    assert core.search().status_code == 200
    wire = core.wire()
    rejected = core.search()
    assert rejected.status_code == 429
    detail = rejected.json()["error"]
    assert detail["code"] == "quota_exceeded" and detail["request_id"]
    assert detail["correlation_id"] == "118h-persistent-quota"
    assert core.wire() == wire
    assert redis_client.get(quota_key()) == "2"
    assert 'path="/v1/search",status="429"} 1' in core.get("/metrics").text
    core.ready("ok")  # saldo esgotado não é indisponibilidade da dependência.
    assert core.get("/health").json()["status"] == "ok"
    print("Core PID alterado: 200(consumo 1) -> restart -> 200(consumo 2) -> 429; zero novo socket upstream")


def test_real_quota_outage_fails_closed_then_recovers(core_factory):
    core = core_factory()
    docker("stop", "redis-118h-validation")
    try:
        core.ready("degraded")
        assert core.get("/ready").json()["reason"] == "quota_store_unavailable"
        before = core.wire()
        response = core.search()
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "quota_store_unavailable"
        assert core.wire() == before
        assert core.get("/health").json()["status"] == "ok"
    finally:
        docker("start", "redis-118h-validation")
    core.ready("ok")
    assert core.search().status_code == 200
    print("Redis fora: 503 quota_store_unavailable sem upstream; retorno: ready=ok e Search=200, mesmo Core")


@pytest.mark.parametrize("name,query", [
    ("omniroute-118h-validation", "Redis official persistence documentation"),
    ("searxng-118h-validation", "PostgreSQL official documentation transactions"),
])
def test_real_dependency_recovers_without_core_restart(core_factory, name, query):
    core = core_factory()
    old_pid = core.process.pid
    # Primeiro reinicia Core para provar recovery também após restart, sem estado local pendurado.
    core.stop()
    assert core.start() != old_pid
    current_pid = core.process.pid
    docker("stop", name)
    try:
        core.ready("degraded")
        response = core.search(query)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "search_upstream_unavailable"
        assert core.get("/health").json()["status"] == "ok"
    finally:
        docker("start", name)
    core.ready("ok")
    result = core.search(query)
    assert result.status_code == 200
    assert result.json()["provider"] == "searxng-search"
    assert 1 <= len(result.json()["results"]) <= 3
    assert core.process.pid == current_pid
    print(f"{name}: degraded/503 -> retorno -> ok/200, mesmo processo Core")


@pytest.mark.parametrize("appendonly,fsync", [("no", "always"), ("yes", "everysec")])
def test_real_ping_does_not_certify_durability(core_factory, appendonly, fsync):
    # Configuração de inicialização de OUTRO Redis descartável. Nunca CONFIG SET.
    name = "redis-118h-inadequate"
    result = subprocess.run([
        str(DOCKER), "run", "-d", "--name", name, "--label", "cesar.task=118h",
        "-p", "127.0.0.1:16380:6379", "redis:8.6.5-alpine", "redis-server",
        "--appendonly", appendonly, "--appendfsync", fsync,
    ], capture_output=True, timeout=30)
    assert result.returncode == 0, "Redis descartável não iniciou; saída omitida"
    container_id = result.stdout.decode().strip()
    try:
        with Redis(host="127.0.0.1", port=16380, decode_responses=True) as client:
            deadline = time.monotonic() + 10
            while True:
                try:
                    assert client.ping()
                    break
                except RedisConnectionError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.1)
            before = client.config_get("appendonly", "appendfsync")
            core = core_factory(redis_port=16380, ready_status="degraded")
            assert core.get("/ready").json() == {
                "status": "degraded", "core": "available", "reason": "quota_store_misconfigured",
            }
            wire = core.wire()
            for endpoint, body in [
                ("/v1/search", {"query": "Python documentation", "max_results": 3}),
                ("/v1/ai/generate", {"prompt": "Reply OK", "max_tokens": 8}),
            ]:
                body["requirements"] = {"service_class": "standard", "cost_policy": "free_only"}
                response = httpx.post(core.url + endpoint, headers=core.headers, json=body, trust_env=False)
                assert response.status_code == 503
                detail = response.json()["error"]
                assert detail["code"] == "quota_store_misconfigured" and detail["request_id"]
                assert detail["correlation_id"] == "118h-persistent-quota"
            assert core.wire() == wire
            assert client.get(quota_key()) is None
            assert client.get(quota_key("ai")) is None
            assert client.config_get("appendonly", "appendfsync") == before
            assert core.get("/health").json()["status"] == "ok"
            core.stop()
            print(f"PING=True, AOF={appendonly}, fsync={fsync}: ready=degraded/misconfigured; AI/Search=503; upstream=0; config intacta")
    finally:
        result = subprocess.run([str(DOCKER), "rm", "-f", container_id], capture_output=True, timeout=30)
        assert result.returncode == 0, "Cleanup Redis descartável falhou"
