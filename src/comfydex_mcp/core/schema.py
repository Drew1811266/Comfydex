from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 2

INITIAL_PROJECT_INDEX_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_records (
  name TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  kind TEXT NOT NULL,
  source TEXT NOT NULL,
  submit_ready INTEGER NOT NULL,
  validation_status TEXT NOT NULL,
  node_count INTEGER NOT NULL,
  node_types_json TEXT NOT NULL,
  model_references_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  indexed_at TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  valid_json INTEGER NOT NULL,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_workflow_records_kind
  ON workflow_records(kind);

CREATE INDEX IF NOT EXISTS idx_workflow_records_validation_status
  ON workflow_records(validation_status);

CREATE TABLE IF NOT EXISTS run_records (
  run_id TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  workflow_name TEXT,
  prompt_id TEXT,
  client_id TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  output_count INTEGER NOT NULL,
  event_count INTEGER NOT NULL,
  indexed_at TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  valid_json INTEGER NOT NULL,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_run_records_status
  ON run_records(status);

CREATE INDEX IF NOT EXISTS idx_run_records_updated_at
  ON run_records(updated_at);

CREATE TABLE IF NOT EXISTS output_records (
  output_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  path TEXT NOT NULL,
  filename TEXT NOT NULL,
  type TEXT NOT NULL,
  subfolder TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  modified_time REAL NOT NULL,
  downloaded_path TEXT,
  indexed_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES run_records(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_output_records_run_id
  ON output_records(run_id);

CREATE INDEX IF NOT EXISTS idx_output_records_modified_time
  ON output_records(modified_time);

CREATE TABLE IF NOT EXISTS batch_records (
  batch_id TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  label TEXT NOT NULL,
  workflow_name TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  run_count INTEGER NOT NULL,
  completed_count INTEGER NOT NULL,
  failed_count INTEGER NOT NULL,
  indexed_at TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  valid_json INTEGER NOT NULL,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_batch_records_status
  ON batch_records(status);

CREATE INDEX IF NOT EXISTS idx_batch_records_updated_at
  ON batch_records(updated_at);

CREATE TABLE IF NOT EXISTS index_errors (
  error_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  path TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_index_errors_source
  ON index_errors(source_type, source_id);
"""

ASSET_LIBRARY_CORE_SQL = """
CREATE TABLE IF NOT EXISTS asset_records (
  asset_id TEXT PRIMARY KEY,
  output_id TEXT NOT NULL UNIQUE,
  run_id TEXT NOT NULL,
  workflow_name TEXT,
  status TEXT NOT NULL,
  prompt_text TEXT NOT NULL,
  model_references_json TEXT NOT NULL,
  path TEXT NOT NULL,
  filename TEXT NOT NULL,
  type TEXT NOT NULL,
  subfolder TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  modified_time REAL NOT NULL,
  content_hash TEXT NOT NULL,
  sidecar_path TEXT,
  thumbnail_path TEXT,
  thumbnail_status TEXT NOT NULL,
  tags_json TEXT NOT NULL,
  rating INTEGER,
  favorite INTEGER NOT NULL,
  notes TEXT NOT NULL,
  indexed_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES run_records(run_id) ON DELETE CASCADE,
  FOREIGN KEY (output_id) REFERENCES output_records(output_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_asset_records_run_id
  ON asset_records(run_id);

CREATE INDEX IF NOT EXISTS idx_asset_records_workflow_name
  ON asset_records(workflow_name);

CREATE INDEX IF NOT EXISTS idx_asset_records_status
  ON asset_records(status);

CREATE INDEX IF NOT EXISTS idx_asset_records_modified_time
  ON asset_records(modified_time);

CREATE INDEX IF NOT EXISTS idx_asset_records_favorite
  ON asset_records(favorite);

CREATE INDEX IF NOT EXISTS idx_asset_records_rating
  ON asset_records(rating);
"""

MIGRATIONS: list[dict[str, Any]] = [
    {
        "version": 1,
        "name": "initial_project_index",
        "sql": INITIAL_PROJECT_INDEX_SQL,
    },
    {
        "version": 2,
        "name": "asset_library_core",
        "sql": ASSET_LIBRARY_CORE_SQL,
    }
]
