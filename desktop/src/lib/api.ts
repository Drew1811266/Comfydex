import { invoke } from "@tauri-apps/api/core";
import type { AssetRow, ConfigState, ProjectStatus, RunRow, WorkflowRow } from "./types";

type AssetSearchResult = {
  total: number;
  assets: AssetRow[];
};

const fallbackStatus: ProjectStatus = {
  workspace: "No workspace selected",
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

function hasTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

async function call<T>(command: string, fallback: T, args: Record<string, unknown> = {}): Promise<T> {
  if (!hasTauri()) {
    return fallback;
  }
  return invoke<T>(command, args);
}

export function getProjectStatus(): Promise<ProjectStatus> {
  return call("project_status", fallbackStatus);
}

export function getConfig(): Promise<ConfigState> {
  return call("get_config", fallbackConfig);
}

export function listWorkflows(): Promise<WorkflowRow[]> {
  return call("list_workflows", [
    { name: "sdxl-city.json", kind: "api", modified_time: 0, size: 3200, valid_json: true },
    { name: "portrait-lora.json", kind: "api", modified_time: 0, size: 4100, valid_json: true }
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

export function searchAssets(): Promise<AssetSearchResult> {
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
  });
}
