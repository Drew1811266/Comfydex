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

export type ModelInventoryItem = {
  filename: string;
  path: string;
  model_type: string;
  size_bytes: number;
};

export type ModelInventory = {
  roots: string[];
  missing_roots: string[];
  model_count: number;
  models: ModelInventoryItem[];
  by_type: Record<string, ModelInventoryItem[]>;
};

export type CapabilityMissingModel = {
  parameter: string;
  filename: string;
  model_type: string;
  reason: string;
};

export type CapabilityMissingNode = {
  node_type: string;
  reason: string;
};

export type CapabilityReportRequest = {
  intent: string;
  parameters?: Record<string, unknown>;
  template_id?: string;
  model_roots?: string[];
};

export type CapabilityReport = {
  status: string;
  can_run_now: boolean;
  plan: {
    selected_template_id?: string;
    title?: string;
    required_nodes?: string[];
    parameters?: Record<string, unknown>;
    semantic_coverage?: Record<string, unknown>;
    [key: string]: unknown;
  };
  node_inventory: {
    node_count: number;
    node_types: string[];
    semantic_match?: Record<string, unknown>;
  };
  model_inventory: ModelInventory;
  missing_nodes: CapabilityMissingNode[];
  missing_models: CapabilityMissingModel[];
  missing_information: string[];
};

export type InstallPlanAction = {
  kind: string;
  target_type?: string;
  filename?: string;
  parameter?: string;
  node_type?: string;
  reason?: string;
  restart_required?: boolean;
  requires_confirmation: boolean;
  automatic: boolean;
};

export type InstallPlan = {
  status: string;
  automatic: boolean;
  requires_confirmation: boolean;
  actions: InstallPlanAction[];
};

export type InstallAuditEntry = {
  timestamp: string;
  decision: string;
  plan: InstallPlan;
};

export type InstallAudit = {
  path: string;
  entries: InstallAuditEntry[];
};

export type UiGraphHistoryEntry = {
  timestamp: string;
  workflow_name: string;
  path?: string;
  status: string;
  template_id?: string | null;
  recipe_id?: string | null;
  node_count?: number | null;
  link_count?: number | null;
  push_result?: Record<string, unknown>;
};

export type UiGraphHistory = {
  path: string;
  entries: UiGraphHistoryEntry[];
};

export type UiGraphPushResult = {
  status: string;
  workflow_name: string;
  push_result: Record<string, unknown>;
  history_record?: UiGraphHistoryEntry;
};

export type LoadState = "loading" | "empty" | "error" | "loaded";
