export type ProjectCounts = {
  workflows: number;
  runs: number;
  outputs: number;
  assets: number;
  batches: number;
  errors: number;
};

export type ProjectStatus = {
  workspace: string;
  database_path: string;
  schema_version: number;
  counts: ProjectCounts;
  last_reindexed_at: string | null;
};

export type WorkflowRow = {
  name: string;
  kind: string;
  modified_time: number;
  size: number;
  valid_json: boolean;
};

export type RunRow = {
  run_id: string;
  workflow_name: string | null;
  status: string;
  updated_at: string | null;
  output_count: number;
};

export type AssetRow = {
  asset_id: string;
  filename: string;
  path?: string;
  workflow_name: string | null;
  status: string;
  rating: number | null;
  favorite: boolean;
  tags: string[];
  notes?: string | null;
  prompt_text?: string | null;
  model_references?: string[];
  size_bytes?: number | null;
  modified_time?: number;
};

export type ConfigState = {
  base_url: string;
  workflows_dir: string;
  runs_dir: string;
  headers: Record<string, string>;
  request_timeout_seconds: number;
  websocket_timeout_seconds: number;
};

export type AppInfo = {
  name: string;
  version: string;
};

export type ConnectionResult = {
  ok: boolean;
  base_url: string;
  message: string;
  checked_at: string | null;
};

export type LiveBridgeDiagnostic = {
  code: string;
  message: string;
  evidence?: Record<string, unknown>;
};

export type LiveBridgeStatus = {
  ok: boolean;
  ready: boolean;
  base_url: string;
  checked_at: string | null;
  server: {
    reachable: boolean;
    status_code?: number | null;
  };
  bridge: {
    loaded: boolean;
    name?: string | null;
    version?: string | null;
    generation?: number | null;
    routes: string[];
  };
  frontend: {
    listed: boolean;
    connected: boolean;
    stale: boolean;
    version?: string | null;
    client_id?: string | null;
    last_seen_at?: string | null;
    last_seen_age_ms?: number | null;
  };
  can_push: boolean;
  needs_restart: boolean;
  needs_refresh: boolean;
  diagnostics: LiveBridgeDiagnostic[];
};

export type AssetSearchFilters = {
  query?: string;
  favorite?: boolean;
  min_rating?: number;
  tags?: string[];
};

export type AssetSearchResult = {
  total: number;
  assets: AssetRow[];
};

export type AssetMetadataPatch = {
  favorite?: boolean;
  rating?: number | null;
  tags?: string[];
  notes?: string;
};

export type CleanupPlan = {
  dry_run: boolean;
  candidates: AssetRow[];
  deleted: string[];
  skipped: Array<AssetRow & { reason?: string }>;
};

export type AssetReport = {
  path: string;
  markdown: string;
};

export type AssetComparison = {
  left: AssetRow;
  right: AssetRow;
  differences: Record<string, { left: unknown; right: unknown; changed: boolean }>;
};

export type BatchSummary = {
  batch_id: string;
  label: string;
  workflow_name: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
  run_count: number;
  completed_count: number;
  failed_count: number;
};

export type BatchRunRow = {
  index: number;
  parameters: Record<string, unknown>;
  status: string;
  run_id: string | null;
  error?: string;
};

export type BatchRecord = BatchSummary & {
  runs: BatchRunRow[];
};

export type LoadState = "loading" | "empty" | "error" | "loaded";
