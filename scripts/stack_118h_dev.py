"""Stack descartável 118H; não inicia nem modifica containers originais."""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "build/118h"
DOCKER = Path(os.environ["LOCALAPPDATA"]) / "Programs/DockerDesktop/resources/bin/docker.exe"
OMNI = "sha256:085c57adf499a8aaa9f35ccde95c0df9c11bd9ecd18d6c9edbf3b68b8079ba9d"
SEARX = "searxng/searxng@sha256:3602e6ddbeba037f5d800d1ed9d296a8b93c9f5b3cf9d05fa179d0e766dd59a1"
NETWORK = "cesar-118h-validation"
REDIS = "docker.io/library/redis:8.6.5-alpine"


def docker(*args, env=None):
    result = subprocess.run([str(DOCKER), *args], env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Operação Docker falhou; saída omitida")
    return result.stdout


def up():
    original = json.loads(docker("inspect", "omniroute"))[0]
    if original["State"]["Running"] or DATA.exists():
        raise RuntimeError("Instância original ativa ou diretório temporário já existe")
    docker("image", "inspect", OMNI)
    docker("image", "inspect", SEARX)
    docker("image", "inspect", REDIS)
    DATA.mkdir(parents=True)
    (DATA / "owned-by-118h").touch()
    database = DATA / "omniroute-data"
    database.mkdir()
    source = Path("C:/omniroute/data/storage.sqlite")
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src:
        with sqlite3.connect(database / "storage.sqlite") as dst:
            src.backup(dst)
            dst.execute(
                """insert into provider_connections
                (id,provider,auth_type,name,priority,is_active,provider_specific_data,created_at,updated_at)
                values (?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
                ("118h-searx", "searxng-search", "none", "118H isolated", 1, 1,
                 json.dumps({"baseUrl": "http://searxng-118h-validation:8080/search"})),
            )
    shutil.copyfile(ROOT / ".secrets/omniroute_api_key", DATA / "search-key")
    (DATA / "settings.yml").write_text(
        'use_default_settings: true\nserver:\n  secret_key: "dev-isolated-not-production"\n'
        '  limiter: false\nsearch:\n  formats: [html, json]\n  default_lang: "pt-BR"\n'
        'outgoing:\n  request_timeout: 7.0\n', encoding="utf-8",
    )
    docker("network", "create", "--label", "cesar.task=118h", NETWORK)
    (DATA / "redis").mkdir()
    docker("run", "-d", "--name", "redis-118h-validation", "--label", "cesar.task=118h",
           "--network", NETWORK, "-p", "127.0.0.1:16379:6379", "--mount",
           f"type=bind,source={DATA / 'redis'},target=/data", REDIS,
           "redis-server", "--appendonly", "yes", "--appendfsync", "always",
           "--maxmemory-policy", "noeviction", "--no-appendfsync-on-rewrite", "no")
    docker("run", "-d", "--name", "searxng-118h-validation", "--label", "cesar.task=118h",
           "--network", NETWORK, "-p", "127.0.0.1:18889:8080", "--mount",
           f"type=bind,source={DATA / 'settings.yml'},target=/etc/searxng/settings.yml,readonly", SEARX)
    values = dict(item.split("=", 1) for item in original["Config"]["Env"])
    values.update(REQUIRE_API_KEY="true", REDIS_URL="", QUOTA_STORE_DRIVER="sqlite",
                  OMNIROUTE_ALLOW_PRIVATE_PROVIDER_URLS="true")
    args = ["run", "-d", "--name", "omniroute-118h-validation", "--label", "cesar.task=118h",
            "--network", NETWORK, "-p", "127.0.0.1:20128:20128", "--mount",
            f"type=bind,source={database},target=/app/data"]
    for key in values:
        args.extend(["-e", key])
    docker(*args, OMNI, env={**os.environ, **values})
    print("Stack 118H isolado iniciado; originais intocados")


def down():
    # Nome, label e marcador impedem apagar diretórios/containers alheios.
    for name in ("omniroute-118h-validation", "searxng-118h-validation", "redis-118h-validation"):
        result = subprocess.run([str(DOCKER), "inspect", name], capture_output=True, text=True)
        if result.returncode == 0:
            info = json.loads(result.stdout)[0]
            if info["Config"]["Labels"].get("cesar.task") != "118h":
                raise RuntimeError("Container não pertence a este harness")
            docker("rm", "-f", name)
    result = subprocess.run([str(DOCKER), "network", "inspect", NETWORK], capture_output=True, text=True)
    if result.returncode == 0:
        if json.loads(result.stdout)[0]["Labels"].get("cesar.task") != "118h":
            raise RuntimeError("Rede não pertence a este harness")
        docker("network", "rm", NETWORK)
    if DATA.exists():
        if DATA.resolve() != ROOT / "build/118h" or not (DATA / "owned-by-118h").is_file():
            raise RuntimeError("Diretório não pertence a este harness")
        shutil.rmtree(DATA)
    print("Recursos temporários 118H removidos")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("up", "down"))
    arguments = parser.parse_args()
    if arguments.action == "up":
        up()
    else:
        down()
