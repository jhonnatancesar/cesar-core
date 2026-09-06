-- Amplia os CHECKs de capability para incluir 'fetch' (Central Web
-- Fetch/Enrichment Gateway). SQLite não suporta ALTER de CHECK
-- constraints existentes: recria cada tabela afetada, copia os dados e
-- troca o nome -- nenhuma linha existente é perdida ou alterada.

CREATE TABLE application_capabilities_new (
  application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  capability TEXT NOT NULL CHECK (capability IN ('ai','search','fetch')),
  PRIMARY KEY (application_id, capability)
);
INSERT INTO application_capabilities_new SELECT * FROM application_capabilities;
DROP TABLE application_capabilities;
ALTER TABLE application_capabilities_new RENAME TO application_capabilities;

CREATE TABLE quota_policies_new (
  application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  capability TEXT NOT NULL CHECK (capability IN ('ai','search','fetch')),
  limit_per_minute INTEGER NOT NULL CHECK (limit_per_minute > 0),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (application_id, capability)
);
INSERT INTO quota_policies_new SELECT * FROM quota_policies;
DROP TABLE quota_policies;
ALTER TABLE quota_policies_new RENAME TO quota_policies;

CREATE TABLE usage_rollups_new (
  bucket_hour TEXT NOT NULL,
  application_id TEXT NOT NULL,
  capability TEXT NOT NULL CHECK (capability IN ('ai','search','fetch')),
  status_class TEXT NOT NULL CHECK (status_class IN ('success','error')),
  provider TEXT NOT NULL DEFAULT '',
  cached INTEGER NOT NULL DEFAULT 0 CHECK (cached IN (0,1)),
  requests INTEGER NOT NULL DEFAULT 0,
  tokens INTEGER NOT NULL DEFAULT 0,
  queries INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (bucket_hour, application_id, capability, status_class, provider, cached)
);
INSERT INTO usage_rollups_new SELECT * FROM usage_rollups;
DROP TABLE usage_rollups;
ALTER TABLE usage_rollups_new RENAME TO usage_rollups;
