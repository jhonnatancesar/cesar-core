FROM node:24.19.0-alpine@sha256:d32cdf619f63fe0471182d08996dd516c6275bb5fd31ae06e55a570bd9e1ad43 AS frontend
WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14.6-slim-bookworm@sha256:4c92ffcde4dd6f1ff72a24518f49fd4990b27134987dfa31a733badde66df9f8 AS builder
WORKDIR /build
COPY requirements/build.lock /build/build.lock
RUN python -m pip install --no-cache-dir --require-hashes -r build.lock
COPY pyproject.toml LICENSE ./
COPY src ./src
COPY --from=frontend /workspace/src/cesar_core/admin/static ./src/cesar_core/admin/static
RUN python -m pip wheel --no-cache-dir --no-deps --no-build-isolation --wheel-dir /wheels .

FROM python:3.14.6-slim-bookworm@sha256:4c92ffcde4dd6f1ff72a24518f49fd4990b27134987dfa31a733badde66df9f8 AS runtime
ARG VERSION=1.1.0
ARG REVISION=unknown
LABEL org.opencontainers.image.title="Cesar Core" \
      org.opencontainers.image.source="https://github.com/jhonnatancesar/cesar-core" \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$REVISION \
      org.opencontainers.image.licenses="LicenseRef-Proprietary"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY requirements/runtime.lock /opt/runtime.lock
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --require-hashes -r /opt/runtime.lock \
    && groupadd --gid 10001 core \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin core \
    && install -d -o 10001 -g 10001 /var/lib/cesar-core
ENV CESAR_CORE_ADMIN_DATABASE_PATH=/var/lib/cesar-core/control-plane.sqlite3
COPY --from=builder /wheels /wheels
RUN /opt/venv/bin/pip install --no-cache-dir --no-deps /wheels/*.whl && rm -r /wheels
COPY LICENSE /usr/share/licenses/cesar-core/LICENSE
USER 10001:10001
EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import json,urllib.request; r=json.load(urllib.request.urlopen('http://127.0.0.1:8100/ready',timeout=8)); raise SystemExit(0 if r['status']=='ok' else 1)"]
STOPSIGNAL SIGTERM
ENTRYPOINT ["python", "-m", "uvicorn", "cesar_core.api.app:app"]
CMD ["--host", "0.0.0.0", "--port", "8100", "--no-access-log", "--timeout-graceful-shutdown", "30"]
