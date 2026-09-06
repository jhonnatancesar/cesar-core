"""SQLite versionado: registry, credenciais, sessões, audit e rollups."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from threading import Lock

from cesar_core.admin.config import AdminConfig

_LOCK = Lock()


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


class ControlPlaneStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or AdminConfig().database_path

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with _LOCK, self.connect() as db:
            mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if mode.lower() != "wal":
                raise RuntimeError("Control Plane database requires WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {
                row[0] for row in db.execute("SELECT version FROM schema_migrations")
            }
            migrations = files("cesar_core.admin.migrations")
            for resource in sorted(migrations.iterdir(), key=lambda item: item.name):
                if not resource.name.endswith(".sql"):
                    continue
                version = int(resource.name.split("_", 1)[0])
                if version in applied:
                    continue
                applied_at = utcnow().replace("'", "''")
                script = resource.read_text(encoding="utf-8")
                db.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + script
                    + f"\nINSERT INTO schema_migrations VALUES ({version},'{applied_at}');\n"
                    + "COMMIT;"
                )

    def bootstrap(
        self, ai_limit: int, search_limit: int, fetch_limit: int = 60
    ) -> None:
        now = utcnow()
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO applications VALUES (?,?,?,?,?,?,?)",
                (
                    "gg_oferta",
                    "GG Oferta",
                    "ggoferta-core-client",
                    "active",
                    0,
                    now,
                    now,
                ),
            )
            db.execute(
                "INSERT OR IGNORE INTO applications VALUES (?,?,?,?,?,?,?)",
                (
                    "claudiao",
                    "Claudião",
                    "claudiao-core-client",
                    "reserved",
                    1,
                    now,
                    now,
                ),
            )
            for capability, limit in (
                ("ai", ai_limit),
                ("search", search_limit),
                ("fetch", fetch_limit),
            ):
                db.execute(
                    "INSERT OR IGNORE INTO application_capabilities VALUES (?,?)",
                    ("gg_oferta", capability),
                )
                db.execute(
                    "INSERT OR IGNORE INTO quota_policies VALUES (?,?,?,?)",
                    ("gg_oferta", capability, limit, now),
                )

    def list_applications(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT a.*, GROUP_CONCAT(c.capability) capabilities
                   FROM applications a LEFT JOIN application_capabilities c
                   ON c.application_id=a.id GROUP BY a.id ORDER BY a.created_at"""
            ).fetchall()
            return [self._application(row, db) for row in rows]

    def get_application(self, application_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute(
                """SELECT a.*, GROUP_CONCAT(c.capability) capabilities
                   FROM applications a LEFT JOIN application_capabilities c
                   ON c.application_id=a.id WHERE a.id=? GROUP BY a.id""",
                (application_id,),
            ).fetchone()
            return self._application(row, db) if row else None

    @staticmethod
    def _application(row: sqlite3.Row, db: sqlite3.Connection) -> dict:
        quotas = {
            item["capability"]: item["limit_per_minute"]
            for item in db.execute(
                "SELECT capability,limit_per_minute FROM quota_policies WHERE application_id=?",
                (row["id"],),
            )
        }
        return {
            "id": row["id"],
            "display_name": row["display_name"],
            "client_id": row["client_id"],
            "state": row["state"],
            "protected": bool(row["protected"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "capabilities": sorted((row["capabilities"] or "").split(","))
            if row["capabilities"]
            else [],
            "quotas": quotas,
        }

    def create_application(
        self, application_id: str, display_name: str, client_id: str
    ) -> dict:
        now = utcnow()
        with self.connect() as db:
            db.execute(
                "INSERT INTO applications VALUES (?,?,?,?,?,?,?)",
                (application_id, display_name, client_id, "disabled", 0, now, now),
            )
        result = self.get_application(application_id)
        assert result
        return result

    def update_application(
        self,
        application_id: str,
        *,
        display_name: str,
        state: str,
        capabilities: set[str],
        quotas: dict[str, int],
    ) -> dict:
        current = self.get_application(application_id)
        if current is None:
            raise KeyError(application_id)
        if current["protected"]:
            raise PermissionError("Protected application cannot be changed")
        now = utcnow()
        with self.connect() as db:
            db.execute(
                "UPDATE applications SET display_name=?,state=?,updated_at=? WHERE id=?",
                (display_name, state, now, application_id),
            )
            db.execute(
                "DELETE FROM application_capabilities WHERE application_id=?",
                (application_id,),
            )
            for capability in sorted(capabilities):
                db.execute(
                    "INSERT INTO application_capabilities VALUES (?,?)",
                    (application_id, capability),
                )
                db.execute(
                    """INSERT INTO quota_policies VALUES (?,?,?,?)
                       ON CONFLICT(application_id,capability) DO UPDATE SET
                       limit_per_minute=excluded.limit_per_minute,updated_at=excluded.updated_at""",
                    (application_id, capability, quotas[capability], now),
                )
        result = self.get_application(application_id)
        assert result
        return result

    def get_quota(self, application_id: str, capability: str) -> int | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT limit_per_minute FROM quota_policies WHERE application_id=? AND capability=?",
                (application_id, capability),
            ).fetchone()
            return int(row[0]) if row else None

    def list_credentials(self, application_id: str | None = None) -> list[dict]:
        sql = "SELECT id,application_id,name,fingerprint,created_at,revoked_at,last_used_at FROM api_credentials"
        params: tuple = ()
        if application_id:
            sql += " WHERE application_id=?"
            params = (application_id,)
        sql += " ORDER BY created_at DESC"
        with self.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def insert_credential(
        self,
        credential_id: str,
        application_id: str,
        name: str,
        fingerprint: str,
        secret_hmac: bytes,
    ) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO api_credentials VALUES (?,?,?,?,?,?,?,?)",
                (
                    credential_id,
                    application_id,
                    name,
                    fingerprint,
                    secret_hmac,
                    utcnow(),
                    None,
                    None,
                ),
            )

    def credential_digest(self, credential_id: str) -> tuple[str, bytes] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT application_id,secret_hmac FROM api_credentials WHERE id=? AND revoked_at IS NULL",
                (credential_id,),
            ).fetchone()
            return (row[0], row[1]) if row else None

    def revoke_credential(self, credential_id: str) -> bool:
        with self.connect() as db:
            result = db.execute(
                "UPDATE api_credentials SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
                (utcnow(), credential_id),
            )
            return result.rowcount == 1

    def active_credential_count(self, application_id: str) -> int:
        with self.connect() as db:
            return int(
                db.execute(
                    "SELECT COUNT(*) FROM api_credentials WHERE application_id=? AND revoked_at IS NULL",
                    (application_id,),
                ).fetchone()[0]
            )

    def create_session(
        self, session_id: str, token_hash: bytes, csrf_hash: bytes, lifetime: int
    ) -> None:
        now = datetime.now(UTC)
        with self.connect() as db:
            db.execute(
                "INSERT INTO admin_sessions VALUES (?,?,?,?,?,?,?)",
                (
                    session_id,
                    token_hash,
                    csrf_hash,
                    now.isoformat(),
                    now.isoformat(),
                    (now + timedelta(seconds=lifetime)).isoformat(),
                    None,
                ),
            )

    def validate_session(
        self, token_hash: bytes, csrf_hash: bytes | None, idle_seconds: int
    ) -> dict | None:
        now = datetime.now(UTC)
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM admin_sessions WHERE token_hash=? AND revoked_at IS NULL",
                (token_hash,),
            ).fetchone()
            if not row:
                return None
            if datetime.fromisoformat(row["expires_at"]) <= now:
                return None
            if (
                datetime.fromisoformat(row["last_seen_at"])
                + timedelta(seconds=idle_seconds)
                <= now
            ):
                return None
            if csrf_hash is not None and row["csrf_hash"] != csrf_hash:
                return None
            db.execute(
                "UPDATE admin_sessions SET last_seen_at=? WHERE id=?",
                (now.isoformat(), row["id"]),
            )
            return dict(row)

    def revoke_session(self, token_hash: bytes) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE admin_sessions SET revoked_at=? WHERE token_hash=?",
                (utcnow(), token_hash),
            )

    def audit(
        self,
        action: str,
        outcome: str,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        correlation_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO admin_audit_events (occurred_at,action,target_type,target_id,outcome,correlation_id,metadata_json) VALUES (?,?,?,?,?,?,?)",
                (
                    utcnow(),
                    action,
                    target_type,
                    target_id,
                    outcome,
                    correlation_id,
                    json.dumps(metadata or {}, separators=(",", ":")),
                ),
            )

    def list_audit(self, limit: int = 50) -> list[dict]:
        with self.connect() as db:
            return [
                {**dict(row), "metadata": json.loads(row["metadata_json"])}
                for row in db.execute(
                    "SELECT * FROM admin_audit_events ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            ]

    def record_usage(
        self,
        application_id: str,
        capability: str,
        status_class: str,
        *,
        provider: str = "",
        cached: bool = False,
        tokens: int = 0,
        queries: int = 0,
    ) -> None:
        bucket = (
            datetime.now(UTC).replace(minute=0, second=0, microsecond=0).isoformat()
        )
        with self.connect() as db:
            db.execute(
                """INSERT INTO usage_rollups VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(bucket_hour,application_id,capability,status_class,provider,cached)
                   DO UPDATE SET requests=requests+1,tokens=tokens+excluded.tokens,queries=queries+excluded.queries""",
                (
                    bucket,
                    application_id,
                    capability,
                    status_class,
                    provider,
                    int(cached),
                    1,
                    tokens,
                    queries,
                ),
            )

    def usage(self, days: int = 7) -> list[dict]:
        since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM usage_rollups WHERE bucket_hour>=? ORDER BY bucket_hour",
                    (since,),
                )
            ]

    def prune_usage(self, retention_days: int) -> int:
        """Remove rollups older than the configured aggregate-retention window."""
        cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat()
        with self.connect() as db:
            result = db.execute(
                "DELETE FROM usage_rollups WHERE bucket_hour<?", (cutoff,)
            )
            return result.rowcount


_STORE: ControlPlaneStore | None = None


def get_store() -> ControlPlaneStore:
    global _STORE
    if _STORE is None:
        _STORE = ControlPlaneStore()
        _STORE.migrate()
        from cesar_core.security.config import SecurityConfig

        config = SecurityConfig()
        _STORE.bootstrap(
            config.ai_requests_per_minute,
            config.search_requests_per_minute,
            config.fetch_requests_per_minute,
        )
        _STORE.prune_usage(AdminConfig().usage_retention_days)
    return _STORE


def reset_store_for_tests() -> None:
    global _STORE
    _STORE = None
