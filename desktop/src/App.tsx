import { useEffect, useState } from "react";
import { Activity, Database, FolderOpen, Image, ListChecks, Settings } from "lucide-react";
import { getConfig, getProjectStatus, listRuns, listWorkflows, searchAssets } from "./lib/api";
import type { AssetRow, ConfigState, ProjectStatus, RunRow, WorkflowRow } from "./lib/types";
import { AssetsView } from "./views/AssetsView";
import { DashboardView } from "./views/DashboardView";
import { RunsView } from "./views/RunsView";
import { SettingsView } from "./views/SettingsView";
import { WorkflowsView } from "./views/WorkflowsView";

type View = "dashboard" | "workflows" | "runs" | "assets" | "settings";

const navItems: Array<{ id: View; label: string; icon: typeof Activity }> = [
  { id: "dashboard", label: "Project", icon: Activity },
  { id: "workflows", label: "Workflows", icon: FolderOpen },
  { id: "runs", label: "Runs", icon: ListChecks },
  { id: "assets", label: "Assets", icon: Image },
  { id: "settings", label: "Settings", icon: Settings }
];

export function App() {
  const [view, setView] = useState<View>("dashboard");
  const [status, setStatus] = useState<ProjectStatus | null>(null);
  const [workflows, setWorkflows] = useState<WorkflowRow[]>([]);
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [assets, setAssets] = useState<AssetRow[]>([]);
  const [config, setConfig] = useState<ConfigState | null>(null);

  useEffect(() => {
    void Promise.all([
      getProjectStatus(),
      listWorkflows(),
      listRuns(),
      searchAssets(),
      getConfig()
    ]).then(([projectStatus, workflowRows, runRows, assetResult, configState]) => {
      setStatus(projectStatus);
      setWorkflows(workflowRows);
      setRuns(runRows);
      setAssets(assetResult.assets);
      setConfig(configState);
    });
  }, []);

  const currentView = (() => {
    if (view === "workflows") return <WorkflowsView workflows={workflows} />;
    if (view === "runs") return <RunsView runs={runs} />;
    if (view === "assets") return <AssetsView assets={assets} />;
    if (view === "settings") return <SettingsView config={config} />;
    return <DashboardView status={status} />;
  })();

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Database size={18} />
          <span>Comfydex</span>
        </div>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
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
          <div>
            <span className="eyebrow">Project</span>
            <strong>{status?.workspace ?? "Loading workspace"}</strong>
          </div>
          <div className="connection">
            <span className="status-dot" />
            <span>Connection</span>
          </div>
        </header>
        {currentView}
      </section>
    </main>
  );
}
