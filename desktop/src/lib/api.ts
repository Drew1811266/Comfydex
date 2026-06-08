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
  CleanupPlan,
  ConfigState,
  ConnectionResult,
  ProjectStatus,
  RunRow,
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
  return call("app_info", { name: "Comfydex", version: "1.0.0" });
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
    }
  ]);
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
