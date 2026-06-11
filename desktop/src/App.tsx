import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  Database,
  FolderOpen,
  Image,
  ListChecks,
  RefreshCw,
  Settings
} from "lucide-react";
import {
  checkConnection,
  getConfig,
  getLiveBridgeStatus,
  getProjectStatus,
  listBatches,
  listRuns,
  listWorkflows,
  reloadLiveBridgeBackend,
  reloadLiveBridgeClient,
  reindexProject,
  searchAssets
} from "./lib/api";
import type {
  AssetRow,
  BatchSummary,
  ConfigState,
  ConnectionResult,
  LiveBridgeStatus,
  LoadState,
  ProjectStatus,
  RunRow,
  WorkflowRow
} from "./lib/types";
import { AssetsView } from "./views/AssetsView";
import { BatchesView } from "./views/BatchesView";
import { DashboardView } from "./views/DashboardView";
import { RunsView } from "./views/RunsView";
import { SettingsView } from "./views/SettingsView";
import { WorkflowsView } from "./views/WorkflowsView";

type View = "dashboard" | "workflows" | "runs" | "assets" | "batches" | "settings";

const navItems: Array<{ id: View; label: string; icon: typeof Activity }> = [
  { id: "dashboard", label: "Project", icon: Activity },
  { id: "workflows", label: "Workflows", icon: FolderOpen },
  { id: "runs", label: "Runs", icon: ListChecks },
  { id: "assets", label: "Assets", icon: Image },
  { id: "batches", label: "Batches", icon: ListChecks },
  { id: "settings", label: "Settings", icon: Settings }
];

async function getLiveBridgeStatusOrNull(): Promise<LiveBridgeStatus | null> {
  try {
    return await getLiveBridgeStatus();
  } catch {
    return null;
  }
}

export function App() {
  const [view, setView] = useState<View>("dashboard");
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [actionBusy, setActionBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<ProjectStatus | null>(null);
  const [connection, setConnection] = useState<ConnectionResult | null>(null);
  const [workflows, setWorkflows] = useState<WorkflowRow[]>([]);
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [assets, setAssets] = useState<AssetRow[]>([]);
  const [batches, setBatches] = useState<BatchSummary[]>([]);
  const [config, setConfigState] = useState<ConfigState | null>(null);
  const [liveBridgeStatus, setLiveBridgeStatus] = useState<LiveBridgeStatus | null>(null);

  const refresh = useCallback(async () => {
    setLoadState("loading");
    setError(null);
    try {
      const [projectStatus, workflowRows, runRows, assetResult, batchRows, configState, connectionState, bridgeState] =
        await Promise.all([
          getProjectStatus(),
          listWorkflows(),
          listRuns(),
          searchAssets(),
          listBatches(),
          getConfig(),
          checkConnection(),
          getLiveBridgeStatusOrNull()
        ]);

      setStatus(projectStatus);
      setWorkflows(workflowRows);
      setRuns(runRows);
      setAssets(assetResult.assets);
      setBatches(batchRows);
      setConfigState(configState);
      setConnection(connectionState);
      setLiveBridgeStatus(bridgeState);
      setLoadState(projectStatus.workspace === "No workspace selected" ? "empty" : "loaded");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleReindex() {
    setActionBusy(true);
    setError(null);
    try {
      const nextStatus = await reindexProject();
      setStatus(nextStatus);
      setLoadState(nextStatus.workspace === "No workspace selected" ? "empty" : "loaded");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      setLoadState("error");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleCheckConnection() {
    setActionBusy(true);
    setError(null);
    try {
      const [connectionState, bridgeState] = await Promise.all([
        checkConnection(),
        getLiveBridgeStatusOrNull()
      ]);
      setConnection(connectionState);
      setLiveBridgeStatus(bridgeState);
    } catch (caught) {
      setConnection({
        ok: false,
        base_url: config?.base_url ?? "unknown",
        message: caught instanceof Error ? caught.message : String(caught),
        checked_at: new Date().toISOString()
      });
    } finally {
      setActionBusy(false);
    }
  }

  async function handleVerifyLiveBridgeStatus() {
    setActionBusy(true);
    setError(null);
    try {
      setLiveBridgeStatus(await getLiveBridgeStatus());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setActionBusy(false);
    }
  }

  async function handleReloadLiveBridgeClient() {
    setActionBusy(true);
    setError(null);
    try {
      await reloadLiveBridgeClient();
      setLiveBridgeStatus(await getLiveBridgeStatus());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setActionBusy(false);
    }
  }

  async function handleReloadLiveBridgeBackend() {
    setActionBusy(true);
    setError(null);
    try {
      await reloadLiveBridgeBackend();
      setLiveBridgeStatus(await getLiveBridgeStatus());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setActionBusy(false);
    }
  }

  const currentView = (() => {
    if (view === "workflows") return <WorkflowsView error={error} state={loadState} workflows={workflows} />;
    if (view === "runs") return <RunsView error={error} runs={runs} state={loadState} />;
    if (view === "assets") return <AssetsView assets={assets} error={error} state={loadState} />;
    if (view === "batches") return <BatchesView batches={batches} error={error} state={loadState} />;
    if (view === "settings") {
      return (
        <SettingsView
          busy={actionBusy}
          config={config}
          connection={connection}
          error={error}
          liveBridgeStatus={liveBridgeStatus}
          onCheckConnection={handleCheckConnection}
          onReloadLiveBridgeBackend={handleReloadLiveBridgeBackend}
          onReloadLiveBridgeClient={handleReloadLiveBridgeClient}
          onVerifyLiveBridgeStatus={handleVerifyLiveBridgeStatus}
          state={loadState}
        />
      );
    }
    return (
      <DashboardView
        busy={actionBusy}
        connection={connection}
        error={error}
        liveBridgeStatus={liveBridgeStatus}
        onCheckConnection={handleCheckConnection}
        onRefresh={refresh}
        onReindex={handleReindex}
        state={loadState}
        status={status}
      />
    );
  })();

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Database size={18} />
          <span>Comfydex</span>
        </div>
        <nav aria-label="Primary">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                aria-current={view === item.id ? "page" : undefined}
                className={view === item.id ? "nav-item active" : "nav-item"}
                key={item.id}
                onClick={() => setView(item.id)}
                type="button"
              >
                <Icon size={16} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <div className="topbar-project">
            <span className="eyebrow">Project</span>
            <strong>{status?.workspace ?? "Loading workspace"}</strong>
          </div>
          <div className={connection?.ok ? "connection online" : "connection offline"}>
            <span className="status-dot" />
            <span>Connection</span>
          </div>
          <button className="icon-button" onClick={() => void refresh()} title="Refresh project data" type="button">
            <RefreshCw size={16} />
          </button>
        </header>
        {currentView}
      </section>
    </main>
  );
}
