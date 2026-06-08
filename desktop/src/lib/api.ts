import { invoke } from "@tauri-apps/api/core";
import type {
  AppInfo,
  AssetRow,
  AssetSearchFilters,
  AssetSearchResult,
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
  return call("app_info", { name: "Comfydex", version: "0.7.0" });
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
        workflow_name: "sdxl-city.json",
        status: "completed",
        rating: 5,
        favorite: true,
        tags: ["city", "keeper"]
      },
      {
        asset_id: "asset-2",
        filename: "portrait.png",
        workflow_name: "portrait-lora.json",
        status: "completed",
        rating: 4,
        favorite: false,
        tags: ["portrait"]
      }
    ]
  }, { payload: filters });
}
