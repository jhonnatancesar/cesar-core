CREATE TABLE applications (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  client_id TEXT NOT NULL UNIQUE,
  state TEXT NOT NULL CHECK (state IN ('active','disabled','reserved')),
  protected INTEGER NOT NULL DEFAULT 0 CHECK (protected IN (0,1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE application_capabilities (
  application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  capability TEXT NOT NULL CHECK (capability IN ('ai','search')),
  PRIMARY KEY (application_id, capability)
);
CREATE TABLE quota_policies (
  application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  capability TEXT NOT NULL CHECK (capability IN ('ai','search')),
  limit_per_minute INTEGER NOT NULL CHECK (limit_per_minute > 0),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (application_id, capability)
);
CREATE TABLE api_credentials (
  id TEXT PRIMARY KEY,
  application_id TEXT NOT NULL REFERENCES applications(id),
  name TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  secret_hmac BLOB NOT NULL,
  created_at TEXT NOT NULL,
  revoked_at TEXT,
  last_used_at TEXT,
  CHECK (length(secret_hmac) = 32)
);
CREATE INDEX api_credentials_application_idx ON api_credentials(application_id);
CREATE TABLE admin_sessions (
  id TEXT PRIMARY KEY,
  token_hash BLOB NOT NULL UNIQUE,
  csrf_hash BLOB NOT NULL,
  created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  CHECK (length(token_hash) = 32 AND length(csrf_hash) = 32)
);
CREATE TABLE admin_audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at TEXT NOT NULL,
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  outcome TEXT NOT NULL,
  correlation_id TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE usage_rollups (
  bucket_hour TEXT NOT NULL,
  application_id TEXT NOT NULL,
  capability TEXT NOT NULL CHECK (capability IN ('ai','search')),
  status_class TEXT NOT NULL CHECK (status_class IN ('success','error')),
  provider TEXT NOT NULL DEFAULT '',
  cached INTEGER NOT NULL DEFAULT 0 CHECK (cached IN (0,1)),
  requests INTEGER NOT NULL DEFAULT 0,
  tokens INTEGER NOT NULL DEFAULT 0,
  queries INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (bucket_hour, application_id, capability, status_class, provider, cached)
);
