import { Plug, RefreshCcw, RotateCw } from "lucide-react";
import type { ConnectionResult, LiveBridgeStatus, LoadState, ProjectStatus } from "../lib/types";

type DashboardProps = {
  busy: boolean;
  connection: ConnectionResult | null;
  error: string | null;
  liveBridgeStatus: LiveBridgeStatus | null;
  onCheckConnection: () => void;
  onRefresh: () => void;
  onReindex: () => void;
  state: LoadState;
  status: ProjectStatus | null;
};

export function DashboardView({
  busy,
  connection,
  error,
  liveBridgeStatus,
  onCheckConnection,
  onRefresh,
  onReindex,
  state,
  status
}: DashboardProps) {
  if (state === "loading") {
    return <StatePanel title="Loading project data" message="Reading workflows, runs, assets, and config." />;
  }

  if (state === "error") {
    return (
      <StatePanel
        actionLabel="Retry"
        message={error ?? "Unable to load project data."}
        onAction={onRefresh}
        tone="error"
        title="Unable to load project data"
      />
    );
  }

  const counts = status?.counts;
  const emptyWorkspace = state === "empty";
  const firstDiagnostic = liveBridgeStatus?.diagnostics[0];
  const liveBridgeLabel = liveBridgeStatus?.ready
    ? "Ready"
    : liveBridgeStatus?.needs_restart
      ? "Restart required"
      : liveBridgeStatus?.needs_refresh
        ? "Refresh required"
        : "Not ready";
  const liveBridgeTone = liveBridgeStatus?.ready ? "success" : liveBridgeStatus ? "warning" : "neutral";

  return (
    <section className="view">
      <div className="view-header split">
        <div>
          <h1>Project Dashboard</h1>
          <p>Schema, index counts, and ComfyUI readiness.</p>
        </div>
        <div className="action-row">
          <button disabled={busy || emptyWorkspace} onClick={onReindex} type="button">
            <RotateCw size={15} />
            <span>Reindex</span>
          </button>
          <button disabled={busy} onClick={onCheckConnection} type="button">
            <Plug size={15} />
            <span>Check connection</span>
          </button>
        </div>
      </div>

      {emptyWorkspace ? (
        <StatePanel
          message="Select a workspace before indexing workflows, runs, and generated assets."
          title="No workspace selected"
        />
      ) : null}

      <div className="status-grid">
        <StatusBand
          detail={connection?.message ?? "Connection has not been checked"}
          label={connection?.ok ? "Connected" : "Offline"}
          tone={connection?.ok ? "success" : "warning"}
          title="ComfyUI"
        >
          {connection?.base_url ?? "No base URL"}
        </StatusBand>
        <StatusBand
          detail={
            firstDiagnostic
              ? firstDiagnostic.code
              : liveBridgeStatus?.checked_at ?? "Live Bridge status has not been checked"
          }
          label={liveBridgeLabel}
          tone={liveBridgeTone}
          title="Live Bridge"
        >
          {liveBridgeStatus?.base_url ?? connection?.base_url ?? "No base URL"}
        </StatusBand>
      </div>

      <div className="metric-grid">
        <Metric label="Schema" value={status?.schema_version ?? "loading"} />
        <Metric label="Workflows" value={counts?.workflows ?? 0} />
        <Metric label="Runs" value={counts?.runs ?? 0} />
        <Metric label="Outputs" value={counts?.outputs ?? 0} />
        <Metric label="Assets" value={counts?.assets ?? 0} />
        <Metric label="Batches" value={counts?.batches ?? 0} />
        <Metric label="Errors" value={counts?.errors ?? 0} tone={counts?.errors ? "warn" : undefined} />
      </div>

      <div className="info-grid">
        <div className="detail-band">
          <span>Database</span>
          <strong>{status?.database_path ?? ".comfydex/comfydex.db"}</strong>
        </div>
        <div className="detail-band">
          <span>Last reindex</span>
          <strong>{status?.last_reindexed_at ?? "Not indexed"}</strong>
        </div>
        <div className="detail-band">
          <span>Connection result</span>
          <strong>{connection?.message ?? "Connection has not been checked"}</strong>
        </div>
      </div>
    </section>
  );
}

function StatusBand({
  children,
  detail,
  label,
  title,
  tone
}: {
  children: string;
  detail: string;
  label: string;
  title: string;
  tone: "neutral" | "success" | "warning";
}) {
  return (
    <div className={`status-band ${tone}`}>
      <div>
        <span>{title}</span>
        <strong>{label}</strong>
      </div>
      <div className="status-band-body">
        <span>{children}</span>
        <p>{detail}</p>
      </div>
    </div>
  );
}

function Metric({ label, tone, value }: { label: string; tone?: "warn"; value: string | number }) {
  return (
    <div className={tone ? `metric ${tone}` : "metric"}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatePanel({
  actionLabel,
  message,
  onAction,
  title,
  tone = "neutral"
}: {
  actionLabel?: string;
  message: string;
  onAction?: () => void;
  title: string;
  tone?: "neutral" | "error";
}) {
  return (
    <section className={`state-panel ${tone}`}>
      <RefreshCcw size={18} />
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      {actionLabel && onAction ? (
        <button onClick={onAction} type="button">
          {actionLabel}
        </button>
      ) : null}
    </section>
  );
}
