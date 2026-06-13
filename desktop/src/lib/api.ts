import { invoke } from "@tauri-apps/api/core";
import type {
  AppInfo,
  AssetComparison,
  AssetMetadataPatch,
  AssetReport,
  AssetRow,
  AssetSearchFilters,
  AssetSearchResult,
  BatchRecord,
  BatchSummary,
  CapabilityReport,
  CapabilityReportRequest,
  CleanupPlan,
  ConfigState,
  ConnectionResult,
  InstallAudit,
  InstallAuditEntry,
  InstallPlan,
  InstallPlanAction,
  LiveBridgeStatus,
  ProjectStatus,
  RunRepairHistory,
  RunRepairPlan,
  RunRepairResult,
  RunRow,
  UiGraphHistory,
  UiGraphPushResult,
  WorkflowRow
} from "./types";

type BridgeEnvelope<T> =
  | { ok: true; data: T }
  | { ok: false; error: { type: string; message: string } };

const fallbackStatus: ProjectStatus = {
  workspace: "C:/Users/Drew/Comfydex Demo Workspace",
  database_path: ".comfydex/comfydex.db",
  schema_version: 2,
  counts: {
    workflows: 3,
    runs: 8,
    outputs: 8,
    assets: 8,
    batches: 1,
    errors: 0
  },
  last_reindexed_at: "2026-06-08T00:00:00+00:00"
};

const fallbackConfig: ConfigState = {
  base_url: "http://127.0.0.1:8188",
  workflows_dir: "workflows",
  runs_dir: "runs",
  headers: {},
  request_timeout_seconds: 30,
  websocket_timeout_seconds: 600
};

const fallbackConnection: ConnectionResult = {
  ok: false,
  base_url: fallbackConfig.base_url,
  message: "Connection has not been checked",
  checked_at: "2026-06-08T00:00:00+00:00"
};

const fallbackLiveBridgeStatus: LiveBridgeStatus = {
  ok: false,
  ready: false,
  base_url: fallbackConfig.base_url,
  checked_at: "2026-06-08T00:00:00+00:00",
  server: { reachable: false, status_code: null },
  bridge: {
    loaded: false,
    name: null,
    version: null,
    generation: null,
    routes: []
  },
  frontend: {
    listed: false,
    connected: false,
    stale: true,
    version: null,
    client_id: null,
    last_seen_at: null,
    last_seen_age_ms: null
  },
  can_push: false,
  needs_restart: true,
  needs_refresh: false,
  diagnostics: [
    {
      code: "desktop_preview",
      message: "Live Bridge status is only available inside the desktop shell."
    }
  ]
};

const defaultCapabilityRequest: CapabilityReportRequest = {
  intent: "text to image",
  parameters: {
    checkpoint_name: "sdxl.safetensors",
    positive_prompt: "desktop capability probe"
  }
};

const fallbackCapabilityReport: CapabilityReport = {
  status: "missing_requirements",
  can_run_now: false,
  plan: {
    selected_template_id: "sdxl-text-to-image",
    required_nodes: [
      "CheckpointLoaderSimple",
      "CLIPTextEncode",
      "EmptyLatentImage",
      "KSampler",
      "VAEDecode",
      "SaveImage"
    ],
    parameters: defaultCapabilityRequest.parameters,
    semantic_coverage: { status: "desktop_preview" }
  },
  node_inventory: {
    node_count: 0,
    node_types: [],
    semantic_match: { status: "desktop_preview" }
  },
  model_inventory: {
    roots: [],
    missing_roots: ["models"],
    model_count: 0,
    models: [],
    by_type: {}
  },
  missing_nodes: [],
  missing_models: [
    {
      parameter: "checkpoint_name",
      filename: "sdxl.safetensors",
      model_type: "checkpoint",
      reason: "desktop_preview"
    }
  ],
  missing_information: []
};

function fallbackInstallPlanFrom(report: CapabilityReport): InstallPlan {
  const modelActions: InstallPlanAction[] = report.missing_models.map((model) => ({
    kind: "model",
    target_type: model.model_type,
    filename: model.filename,
    parameter: model.parameter,
    reason: model.reason,
    requires_confirmation: true,
    automatic: false
  }));
  const nodeActions: InstallPlanAction[] = report.missing_nodes.map((node) => ({
    kind: "custom_node",
    node_type: node.node_type,
    reason: node.reason,
    restart_required: true,
    requires_confirmation: true,
    automatic: false
  }));
  const actions = [...modelActions, ...nodeActions];
  return {
    status: actions.length ? "requires_confirmation" : "not_required",
    automatic: false,
    requires_confirmation: actions.length > 0,
    actions
  };
}

const fallbackInstallAudit: InstallAudit = {
  path: ".comfydex/install_audit.jsonl",
  entries: []
};

const fallbackUiGraphHistory: UiGraphHistory = {
  path: ".comfydex/ui_graph_history.jsonl",
  entries: [
    {
      timestamp: "2026-06-08T00:20:00+00:00",
      workflow_name: "lake.ui.json",
      path: "workflows/lake.ui.json",
      status: "pushed",
      template_id: "basic-text-to-image",
      recipe_id: "text-to-image-basic",
      node_count: 7,
      link_count: 9,
      push_result: { ok: true, acknowledged: true }
    },
    {
      timestamp: "2026-06-08T00:15:00+00:00",
      workflow_name: "lake.ui.json",
      path: "workflows/lake.ui.json",
      status: "saved",
      template_id: "basic-text-to-image",
      recipe_id: "text-to-image-basic",
      node_count: 7,
      link_count: 9
    }
  ]
};

function fallbackRepairPlan(runId: string): RunRepairPlan {
  return {
    status: "retry_available",
    run_id: runId,
    workflow_name: "portrait-lora.json",
    failure_class: "execution_error",
    summary: "The run failed during execution; review the recorded event and retry after correction.",
    actions: [
      {
        kind: "inspect_history",
        requires_confirmation: false,
        automatic: false
      }
    ],
    retry: {
      supported: true,
      operation: "resubmit_workflow",
      arguments: { run_id: runId, workflow_name: "portrait-lora.json" },
      requires_confirmation: true
    }
  };
}

function fallbackRepairResult(runId: string, status = "planned"): RunRepairResult {
  const repairPlan = fallbackRepairPlan(runId);
  return {
    status,
    run_id: runId,
    diagnosis: {
      run_id: runId,
      status: "failed",
      failure_class: repairPlan.failure_class,
      repair_summary: repairPlan.summary,
      signals: ["execution_error"],
      retryable: true
    },
    repair_plan: repairPlan
  };
}

const fallbackRepairHistory: RunRepairHistory = {
  path: ".comfydex/repair_history.jsonl",
  entries: [
    {
      timestamp: "2026-06-08T01:15:00+00:00",
      run_id: "2026-06-08T01-00-00_portrait",
      workflow_name: "portrait-lora.json",
      status: "planned",
      failure_class: "execution_error",
      retry_supported: true,
      action_count: 1
    }
  ]
};

function hasTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

async function call<T>(command: string, fallback: T, args: Record<string, unknown> = {}): Promise<T> {
  if (!hasTauri()) {
    return fallback;
  }

  const result = await invoke<T | BridgeEnvelope<T>>(command, args);

  if (isBridgeEnvelope(result)) {
    if (result.ok) {
      return result.data;
    }
    throw new Error(`${result.error.type}: ${result.error.message}`);
  }

  return result;
}

function isBridgeEnvelope<T>(value: T | BridgeEnvelope<T>): value is BridgeEnvelope<T> {
  return (
    typeof value === "object" &&
    value !== null &&
    "ok" in value &&
    (("data" in value) || ("error" in value))
  );
}

export function getAppInfo(): Promise<AppInfo> {
  return call("app_info", { name: "Comfydex", version: "1.6.0" });
}

export function setWorkspace(path: string): Promise<ProjectStatus> {
  return call("set_workspace", fallbackStatus, { path });
}

export function getProjectStatus(): Promise<ProjectStatus> {
  return call("project_status", fallbackStatus);
}

export function reindexProject(): Promise<ProjectStatus> {
  return call("reindex_project", {
    ...fallbackStatus,
    last_reindexed_at: new Date().toISOString()
  });
}

export function getConfig(): Promise<ConfigState> {
  return call("get_config", fallbackConfig);
}

export function setConfig(configPatch: Partial<ConfigState>): Promise<ConfigState> {
  return call("set_config", { ...fallbackConfig, ...configPatch }, { payload: configPatch });
}

export function checkConnection(): Promise<ConnectionResult> {
  return call("check_connection", fallbackConnection);
}

export function getLiveBridgeStatus(): Promise<LiveBridgeStatus> {
  return call("live_bridge_status", fallbackLiveBridgeStatus);
}

export function getCapabilityReport(
  payload: CapabilityReportRequest = defaultCapabilityRequest
): Promise<CapabilityReport> {
  return call("capability_report", fallbackCapabilityReport, { payload });
}

export function createInstallPlan(capabilityReport: CapabilityReport): Promise<InstallPlan> {
  return call("create_install_plan", fallbackInstallPlanFrom(capabilityReport), {
    payload: { capability_report: capabilityReport }
  });
}

export function recordInstallAudit(
  installPlan: InstallPlan,
  decision: "accepted" | "rejected"
): Promise<InstallAuditEntry> {
  return call("record_install_audit", {
    timestamp: new Date().toISOString(),
    decision,
    plan: installPlan
  }, { payload: { install_plan: installPlan, decision } });
}

export function readInstallAudit(): Promise<InstallAudit> {
  return call("read_install_audit", fallbackInstallAudit);
}

export function readUiGraphHistory(limit = 20): Promise<UiGraphHistory> {
  return call("read_ui_graph_history", fallbackUiGraphHistory, { payload: { limit } });
}

export function pushUiWorkflow(workflowName: string, force = false): Promise<UiGraphPushResult> {
  return call("push_ui_workflow", {
    status: "pushed",
    workflow_name: workflowName,
    push_result: { ok: true, desktop_preview: true },
    history_record: {
      timestamp: new Date().toISOString(),
      workflow_name: workflowName,
      status: "pushed"
    }
  }, { payload: { workflow_name: workflowName, force } });
}

export function reloadLiveBridgeClient(): Promise<Record<string, unknown>> {
  return call("live_bridge_reload_client", { ok: true, version: "desktop-preview" });
}

export function reloadLiveBridgeBackend(): Promise<Record<string, unknown>> {
  return call("live_bridge_reload_backend", { ok: true, generation: 0 });
}

export function listWorkflows(): Promise<WorkflowRow[]> {
  return call("list_workflows", [
    { name: "sdxl-city.json", kind: "api", modified_time: 1780924800, size: 3200, valid_json: true },
    { name: "portrait-lora.json", kind: "api", modified_time: 1780928400, size: 4100, valid_json: true }
  ]);
}

export function listRuns(): Promise<RunRow[]> {
  return call("list_runs", [
    {
      run_id: "2026-06-08T00-00-00_city",
      workflow_name: "sdxl-city.json",
      status: "completed",
      updated_at: "2026-06-08T00:00:00+00:00",
      output_count: 2
    },
    {
      run_id: "2026-06-08T01-00-00_portrait",
      workflow_name: "portrait-lora.json",
      status: "failed",
      updated_at: "2026-06-08T01:15:00+00:00",
      output_count: 0
    }
  ]);
}

export function planRunRepair(runId: string): Promise<RunRepairResult> {
  return call("plan_run_repair", fallbackRepairResult(runId), {
    payload: { run_id: runId }
  });
}

export function readRepairHistory(limit = 20): Promise<RunRepairHistory> {
  return call("read_repair_history", fallbackRepairHistory, { payload: { limit } });
}

export function retryRunRepair(runId: string, confirm = false): Promise<RunRepairResult> {
  const fallback = fallbackRepairResult(runId, confirm ? "retried" : "requires_confirmation");
  return call("retry_run_repair", fallback, {
    payload: { run_id: runId, confirm }
  });
}

export function searchAssets(filters: AssetSearchFilters = {}): Promise<AssetSearchResult> {
  return call("search_assets", {
    total: 2,
    assets: [
      {
        asset_id: "asset-1",
        filename: "city.png",
        path: "C:/Users/Drew/Comfydex Demo Workspace/runs/demo/outputs/city.png",
        workflow_name: "sdxl-city.json",
        status: "completed",
        rating: 5,
        favorite: true,
        tags: ["city", "keeper"],
        notes: "High contrast keeper",
        prompt_text: "cinematic city at night",
        model_references: ["sdxl.safetensors"],
        size_bytes: 2048,
        modified_time: 1780924800
      },
      {
        asset_id: "asset-2",
        filename: "portrait.png",
        path: "C:/Users/Drew/Comfydex Demo Workspace/runs/demo/outputs/portrait.png",
        workflow_name: "portrait-lora.json",
        status: "completed",
        rating: 4,
        favorite: false,
        tags: ["portrait"],
        notes: "Needs crop review",
        prompt_text: "studio portrait",
        model_references: ["portrait-lora.safetensors"],
        size_bytes: 3072,
        modified_time: 1780928400
      }
    ]
  }, { payload: filters });
}

export function updateAssetMetadata(assetId: string, patch: AssetMetadataPatch): Promise<AssetRow> {
  return call("update_asset_metadata", {
    asset_id: assetId,
    filename: "updated.png",
    workflow_name: null,
    status: "completed",
    rating: patch.rating ?? null,
    favorite: patch.favorite ?? false,
    tags: patch.tags ?? [],
    notes: patch.notes ?? ""
  }, { payload: { asset_id: assetId, ...patch } });
}

export function planAssetCleanup(payload: {
  asset_ids?: string[];
  filters?: AssetSearchFilters;
  confirm?: boolean;
}): Promise<CleanupPlan> {
  return call("plan_asset_cleanup", {
    dry_run: payload.confirm !== true,
    candidates: [],
    deleted: [],
    skipped: []
  }, { payload });
}

export function exportAssetLibraryReport(filters: AssetSearchFilters = {}): Promise<AssetReport> {
  return call("export_asset_library_report", {
    path: ".comfydex/reports/asset-library-report.md",
    markdown: "# Comfydex Asset Library Report\n\n## Summary\n\n- Total assets: 2\n"
  }, { payload: filters });
}

export function compareAssets(leftAssetId: string, rightAssetId: string): Promise<AssetComparison> {
  const left = {
    asset_id: leftAssetId,
    filename: "city.png",
    workflow_name: "sdxl-city.json",
    status: "completed",
    rating: 5,
    favorite: true,
    tags: ["city"]
  };
  const right = {
    asset_id: rightAssetId,
    filename: "portrait.png",
    workflow_name: "portrait-lora.json",
    status: "completed",
    rating: 4,
    favorite: false,
    tags: ["portrait"]
  };
  return call("compare_assets", {
    left,
    right,
    differences: {
      workflow_name: { left: left.workflow_name, right: right.workflow_name, changed: true },
      rating: { left: left.rating, right: right.rating, changed: true },
      favorite: { left: left.favorite, right: right.favorite, changed: true }
    }
  }, { payload: { left_asset_id: leftAssetId, right_asset_id: rightAssetId } });
}

const fallbackBatches: BatchRecord[] = [
  {
    batch_id: "2026-06-08T00-00-00-city-sweep",
    label: "city sweep",
    workflow_name: "sdxl-city.json",
    status: "completed",
    created_at: "2026-06-08T00:00:00+00:00",
    updated_at: "2026-06-08T00:20:00+00:00",
    run_count: 2,
    completed_count: 2,
    failed_count: 0,
    runs: [
      {
        index: 0,
        parameters: { node_id: "4", inputs: { text: "cinematic city morning" } },
        status: "completed",
        run_id: "run-city-0"
      },
      {
        index: 1,
        parameters: { node_id: "4", inputs: { text: "cinematic city night" } },
        status: "completed",
        run_id: "run-city-1"
      }
    ]
  },
  {
    batch_id: "2026-06-08T01-00-00-portrait-test",
    label: "portrait test",
    workflow_name: "portrait-lora.json",
    status: "failed",
    created_at: "2026-06-08T01:00:00+00:00",
    updated_at: "2026-06-08T01:12:00+00:00",
    run_count: 2,
    completed_count: 1,
    failed_count: 1,
    runs: [
      {
        index: 0,
        parameters: { node_id: "6", inputs: { strength: 0.7 } },
        status: "completed",
        run_id: "run-portrait-0"
      },
      {
        index: 1,
        parameters: { node_id: "6", inputs: { strength: 1.1 } },
        status: "failed",
        run_id: null,
        error: "missing model"
      }
    ]
  }
];

export function listBatches(): Promise<BatchSummary[]> {
  return call("list_batches", fallbackBatches.map(({ runs: _runs, ...summary }) => summary));
}

export function readBatch(batchId: string): Promise<BatchRecord> {
  return call("read_batch", fallbackBatches.find((batch) => batch.batch_id === batchId) ?? fallbackBatches[0], {
    batchId
  });
}
