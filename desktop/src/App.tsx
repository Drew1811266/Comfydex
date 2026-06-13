import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  Database,
  FolderOpen,
  GitBranch,
  Image,
  ListChecks,
  RefreshCw,
  Settings
} from "lucide-react";
import {
  checkConnection,
  createInstallPlan,
  getConfig,
  getCapabilityReport,
  getLiveBridgeStatus,
  getProjectStatus,
  listGenerationPresets,
  listBatches,
  listRuns,
  listWorkflows,
  planRunRepair,
  pushUiWorkflow,
  readRepairHistory,
  readUiGraphHistory,
  readInstallAudit,
  reloadLiveBridgeBackend,
  reloadLiveBridgeClient,
  reindexProject,
  recordInstallAudit,
  retryRunRepair,
  searchAssets,
  summarizeAssets
} from "./lib/api";
import type {
  AssetRow,
  BatchSummary,
  CapabilityReport,
  ConfigState,
  ConnectionResult,
  GenerationPresets,
  InstallAudit,
  InstallPlan,
  LiveBridgeStatus,
  LoadState,
  ProjectStatus,
  RunRepairHistory,
  RunRepairResult,
  RunRow,
  UiGraphHistory,
  UiGraphPushResult,
  UserGuidance,
  WorkflowRow
} from "./lib/types";
import { AssetsView } from "./views/AssetsView";
import { BatchesView } from "./views/BatchesView";
import { DashboardView } from "./views/DashboardView";
import { GeneratedGraphsView } from "./views/GeneratedGraphsView";
import { RunsView } from "./views/RunsView";
import { SettingsView } from "./views/SettingsView";
import { WorkflowsView } from "./views/WorkflowsView";

type View = "dashboard" | "workflows" | "runs" | "assets" | "generated" | "batches" | "settings";
type InstallDecision = "accepted" | "rejected";

const navItems: Array<{ id: View; label: string; icon: typeof Activity }> = [
  { id: "dashboard", label: "Project", icon: Activity },
  { id: "workflows", label: "Workflows", icon: FolderOpen },
  { id: "runs", label: "Runs", icon: ListChecks },
  { id: "assets", label: "Assets", icon: Image },
  { id: "generated", label: "Generated", icon: GitBranch },
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

type InstallReviewResult = {
  capabilityReport: CapabilityReport | null;
  installPlan: InstallPlan | null;
  installAudit: InstallAudit | null;
  error: string | null;
};

async function fetchInstallReview(): Promise<InstallReviewResult> {
  try {
    const capabilityReport = await getCapabilityReport();
    const [installPlan, installAudit] = await Promise.all([
      createInstallPlan(capabilityReport),
      readInstallAudit()
    ]);
    return { capabilityReport, installPlan, installAudit, error: null };
  } catch (caught) {
    return {
      capabilityReport: null,
      installPlan: null,
      installAudit: null,
      error: caught instanceof Error ? caught.message : String(caught)
    };
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
  const [runRepair, setRunRepair] = useState<RunRepairResult | null>(null);
  const [runRepairHistory, setRunRepairHistory] = useState<RunRepairHistory | null>(null);
  const [runRepairBusy, setRunRepairBusy] = useState(false);
  const [runRepairError, setRunRepairError] = useState<string | null>(null);
  const [assets, setAssets] = useState<AssetRow[]>([]);
  const [assetSummary, setAssetSummary] = useState<UserGuidance | null>(null);
  const [uiGraphHistory, setUiGraphHistory] = useState<UiGraphHistory | null>(null);
  const [generationPresets, setGenerationPresets] = useState<GenerationPresets | null>(null);
  const [lastGraphPush, setLastGraphPush] = useState<UiGraphPushResult | null>(null);
  const [batches, setBatches] = useState<BatchSummary[]>([]);
  const [config, setConfigState] = useState<ConfigState | null>(null);
  const [liveBridgeStatus, setLiveBridgeStatus] = useState<LiveBridgeStatus | null>(null);
  const [capabilityReport, setCapabilityReport] = useState<CapabilityReport | null>(null);
  const [installPlan, setInstallPlan] = useState<InstallPlan | null>(null);
  const [installAudit, setInstallAudit] = useState<InstallAudit | null>(null);
  const [installReviewError, setInstallReviewError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoadState("loading");
    setError(null);
    try {
      const [
        projectStatus,
        workflowRows,
        runRows,
        assetResult,
        assetSummaryResult,
        generatedHistory,
        presets,
        repairHistory,
        batchRows,
        configState,
        connectionState,
        bridgeState,
        installReview
      ] =
        await Promise.all([
          getProjectStatus(),
          listWorkflows(),
          listRuns(),
          searchAssets(),
          summarizeAssets(),
          readUiGraphHistory(),
          listGenerationPresets(),
          readRepairHistory(),
          listBatches(),
          getConfig(),
          checkConnection(),
          getLiveBridgeStatusOrNull(),
          fetchInstallReview()
        ]);

      setStatus(projectStatus);
      setWorkflows(workflowRows);
      setRuns(runRows);
      setAssets(assetResult.assets);
      setAssetSummary(assetSummaryResult.summary ?? assetResult.summary ?? null);
      setUiGraphHistory(generatedHistory);
      setGenerationPresets(presets);
      setRunRepairHistory(repairHistory);
      setBatches(batchRows);
      setConfigState(configState);
      setConnection(connectionState);
      setLiveBridgeStatus(bridgeState);
      setCapabilityReport(installReview.capabilityReport);
      setInstallPlan(installReview.installPlan);
      setInstallAudit(installReview.installAudit);
      setInstallReviewError(installReview.error);
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

  async function handleRefreshInstallPlan() {
    setActionBusy(true);
    setInstallReviewError(null);
    try {
      const installReview = await fetchInstallReview();
      setCapabilityReport(installReview.capabilityReport);
      setInstallPlan(installReview.installPlan);
      setInstallAudit(installReview.installAudit);
      setInstallReviewError(installReview.error);
    } finally {
      setActionBusy(false);
    }
  }

  async function handleRecordInstallDecision(decision: InstallDecision) {
    if (!installPlan) return;
    setActionBusy(true);
    setInstallReviewError(null);
    try {
      await recordInstallAudit(installPlan, decision);
      setInstallAudit(await readInstallAudit());
    } catch (caught) {
      setInstallReviewError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setActionBusy(false);
    }
  }

  async function handlePushGeneratedGraph(workflowName: string) {
    setActionBusy(true);
    setError(null);
    try {
      const pushResult = await pushUiWorkflow(workflowName, true);
      setLastGraphPush(pushResult);
      const [history, bridgeState] = await Promise.all([
        readUiGraphHistory(),
        getLiveBridgeStatusOrNull()
      ]);
      setUiGraphHistory(history);
      setLiveBridgeStatus(bridgeState);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setActionBusy(false);
    }
  }

  async function handlePlanRunRepair(runId: string) {
    setRunRepairBusy(true);
    setRunRepairError(null);
    try {
      const repair = await planRunRepair(runId);
      const history = await readRepairHistory();
      setRunRepair(repair);
      setRunRepairHistory(history);
    } catch (caught) {
      setRunRepairError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setRunRepairBusy(false);
    }
  }

  async function handleRetryRunRepair(runId: string, confirm = false) {
    setRunRepairBusy(true);
    setRunRepairError(null);
    try {
      const repair = await retryRunRepair(runId, confirm);
      const [history, runRows] = await Promise.all([readRepairHistory(), listRuns()]);
      setRunRepair(repair);
      setRunRepairHistory(history);
      setRuns(runRows);
    } catch (caught) {
      setRunRepairError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setRunRepairBusy(false);
    }
  }

  const currentView = (() => {
    if (view === "workflows") return <WorkflowsView error={error} state={loadState} workflows={workflows} />;
    if (view === "runs") {
      return (
        <RunsView
          busy={runRepairBusy}
          error={error}
          onPlanRepair={handlePlanRunRepair}
          onRefresh={() => void refresh()}
          onRetryRepair={handleRetryRunRepair}
          repair={runRepair}
          repairError={runRepairError}
          repairHistory={runRepairHistory}
          runs={runs}
          state={loadState}
        />
      );
    }
    if (view === "assets") {
      return <AssetsView assetSummary={assetSummary} assets={assets} error={error} state={loadState} />;
    }
    if (view === "generated") {
      return (
        <GeneratedGraphsView
          busy={actionBusy}
          error={error}
          history={uiGraphHistory}
          lastPush={lastGraphPush}
          onPush={handlePushGeneratedGraph}
          onRefresh={() => void refresh()}
          presets={generationPresets}
          state={loadState}
        />
      );
    }
    if (view === "batches") return <BatchesView batches={batches} error={error} state={loadState} />;
    if (view === "settings") {
      return (
        <SettingsView
          busy={actionBusy}
          capabilityReport={capabilityReport}
          config={config}
          connection={connection}
          error={error}
          installAudit={installAudit}
          installPlan={installPlan}
          installReviewError={installReviewError}
          liveBridgeStatus={liveBridgeStatus}
          onCheckConnection={handleCheckConnection}
          onRecordInstallDecision={handleRecordInstallDecision}
          onReloadLiveBridgeBackend={handleReloadLiveBridgeBackend}
          onReloadLiveBridgeClient={handleReloadLiveBridgeClient}
          onRefreshInstallPlan={handleRefreshInstallPlan}
          onVerifyLiveBridgeStatus={handleVerifyLiveBridgeStatus}
          state={loadState}
        />
      );
    }
    return (
      <DashboardView
        busy={actionBusy}
        assetSummary={assetSummary}
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
                aria-label={item.label}
                className={view === item.id ? "nav-item active" : "nav-item"}
                key={item.id}
                onClick={() => setView(item.id)}
                title={item.label}
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
