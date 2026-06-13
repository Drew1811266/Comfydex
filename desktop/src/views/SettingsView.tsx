import { CheckCircle2, Plug, RefreshCcw, RotateCw, ShieldCheck, XCircle } from "lucide-react";
import type {
  CapabilityReport,
  ConfigState,
  ConnectionResult,
  InstallAudit,
  InstallPlan,
  InstallPlanAction,
  LiveBridgeStatus,
  LoadState,
  TwentyReadinessReport
} from "../lib/types";

export function SettingsView({
  busy,
  capabilityReport,
  config,
  connection,
  error,
  installAudit,
  installPlan,
  installReviewError,
  liveBridgeStatus,
  onCheckConnection,
  onRecordInstallDecision,
  onReloadLiveBridgeBackend,
  onReloadLiveBridgeClient,
  onRefreshInstallPlan,
  onVerifyLiveBridgeStatus,
  state,
  twentyReadiness
}: {
  busy: boolean;
  capabilityReport: CapabilityReport | null;
  config: ConfigState | null;
  connection: ConnectionResult | null;
  error: string | null;
  installAudit: InstallAudit | null;
  installPlan: InstallPlan | null;
  installReviewError: string | null;
  liveBridgeStatus: LiveBridgeStatus | null;
  onCheckConnection: () => void;
  onRecordInstallDecision: (decision: "accepted" | "rejected") => void;
  onReloadLiveBridgeBackend: () => void;
  onReloadLiveBridgeClient: () => void;
  onRefreshInstallPlan: () => void;
  onVerifyLiveBridgeStatus: () => void;
  state: LoadState;
  twentyReadiness: TwentyReadinessReport | null;
}) {
  if (state === "loading") return <State title="Loading settings" message="Reading project configuration." />;
  if (state === "error") return <State title="Unable to load settings" message={error ?? "Unable to load."} />;

  const actionsDisabled = busy || state === "empty";
  const bridgeState = formatBridgeState(liveBridgeStatus);

  return (
    <section className="view">
      <div className="view-header split">
        <div>
          <h1>Settings</h1>
          <p>Workspace paths and ComfyUI connection configuration.</p>
        </div>
        <button disabled={busy} onClick={onCheckConnection} type="button">
          <Plug size={15} />
          <span>Check connection</span>
        </button>
      </div>
      <div className="settings-grid">
        <label>
          Base URL
          <input readOnly value={config?.base_url ?? ""} />
        </label>
        <label>
          Workflows
          <input readOnly value={config?.workflows_dir ?? ""} />
        </label>
        <label>
          Runs
          <input readOnly value={config?.runs_dir ?? ""} />
        </label>
        <label>
          Request timeout
          <input readOnly value={config?.request_timeout_seconds ?? ""} />
        </label>
        <label>
          WebSocket timeout
          <input readOnly value={config?.websocket_timeout_seconds ?? ""} />
        </label>
      </div>
      <div className={connection?.ok ? "detail-band success" : "detail-band warning"}>
        <span>Connection</span>
        <strong>{connection?.message ?? "Connection has not been checked"}</strong>
      </div>
      <div className="detail-band">
        <span>Headers</span>
        <strong>{Object.keys(config?.headers ?? {}).length} redacted headers</strong>
      </div>
      <section className="tool-panel settings-advanced">
        <div className="view-header split compact">
          <div>
            <h2>Live Bridge</h2>
            <p>{bridgeState.detail}</p>
          </div>
          <span className={liveBridgeStatus?.ready ? "badge ok" : "badge warn"}>{bridgeState.label}</span>
        </div>
        <div className="action-row">
          <button disabled={actionsDisabled} onClick={onVerifyLiveBridgeStatus} type="button">
            <Plug size={15} />
            <span>Verify status</span>
          </button>
          <button disabled={actionsDisabled} onClick={onReloadLiveBridgeClient} type="button">
            <RefreshCcw size={15} />
            <span>Reload client</span>
          </button>
          <button disabled={actionsDisabled} onClick={onReloadLiveBridgeBackend} type="button">
            <RotateCw size={15} />
            <span>Reload backend</span>
          </button>
        </div>
        <div className="settings-grid bridge-settings-grid">
          <label>
            Base URL
            <input readOnly value={liveBridgeStatus?.base_url ?? config?.base_url ?? ""} />
          </label>
          <label>
            Bridge version
            <input readOnly value={liveBridgeStatus?.bridge.version ?? ""} />
          </label>
          <label>
            Frontend client
            <input readOnly value={liveBridgeStatus?.frontend.client_id ?? ""} />
          </label>
          <label>
            Last checked
            <input readOnly value={liveBridgeStatus?.checked_at ?? ""} />
          </label>
        </div>
        {liveBridgeStatus?.diagnostics.length ? (
          <ul className="diagnostic-list">
            {liveBridgeStatus.diagnostics.slice(0, 4).map((diagnostic) => (
              <li key={`${diagnostic.code}-${diagnostic.message}`}>
                <strong>{diagnostic.code}</strong>
                <span>{diagnostic.message}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
      <InstallPlanPanel
        audit={installAudit}
        busy={actionsDisabled}
        capabilityReport={capabilityReport}
        error={installReviewError}
        installPlan={installPlan}
        onRecordInstallDecision={onRecordInstallDecision}
        onRefreshInstallPlan={onRefreshInstallPlan}
      />
      <ReadinessPanel report={twentyReadiness} />
    </section>
  );
}

function ReadinessPanel({ report }: { report: TwentyReadinessReport | null }) {
  const scenarios = report?.scenarios ?? [];
  const criteria = report?.acceptance_criteria ?? [];
  const statusClass = report?.status === "ready_for_2_0" ? "badge ok" : "badge warn";

  return (
    <section className="tool-panel readiness-panel">
      <div className="view-header split compact">
        <div>
          <p className="eyebrow">2.0 readiness</p>
          <h2>Conversational workflow gate</h2>
        </div>
        <span className={statusClass}>{formatStatus(report?.status ?? "unchecked")}</span>
      </div>
      <div className="readiness-summary-grid">
        <SummaryCell label="Scenarios" value={String(report?.summary.scenario_count ?? 0)} />
        <SummaryCell label="Ready" value={String(report?.summary.ready_count ?? 0)} />
        <SummaryCell label="Needs work" value={String(report?.summary.needs_work_count ?? 0)} />
        <SummaryCell label="Version" value={report?.readiness_version ?? "unchecked"} />
      </div>
      <div className="readiness-grid">
        {scenarios.map((scenario) => (
          <div className="readiness-item" key={scenario.scenario_id}>
            <div>
              <strong>{scenario.name}</strong>
              <span>{scenario.ready_recipe_ids.length ? scenario.ready_recipe_ids.join(", ") : scenario.gaps.join(", ")}</span>
            </div>
            <span className={scenario.status === "ready" ? "badge ok" : "badge warn"}>
              {formatStatus(scenario.status)}
            </span>
          </div>
        ))}
      </div>
      {criteria.length ? (
        <div className="readiness-criteria">
          {criteria.map((criterion) => (
            <div className="readiness-criterion" key={criterion.criterion_id}>
              <strong>{criterion.label}</strong>
              <span className={criterion.status === "ready" ? "badge ok" : "badge warn"}>
                {formatStatus(criterion.status)}
              </span>
            </div>
          ))}
        </div>
      ) : null}
      {report?.next_steps.length ? (
        <ul className="readiness-next">
          {report.next_steps.slice(0, 4).map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function InstallPlanPanel({
  audit,
  busy,
  capabilityReport,
  error,
  installPlan,
  onRecordInstallDecision,
  onRefreshInstallPlan
}: {
  audit: InstallAudit | null;
  busy: boolean;
  capabilityReport: CapabilityReport | null;
  error: string | null;
  installPlan: InstallPlan | null;
  onRecordInstallDecision: (decision: "accepted" | "rejected") => void;
  onRefreshInstallPlan: () => void;
}) {
  const missingModels = capabilityReport?.missing_models ?? [];
  const missingNodes = capabilityReport?.missing_nodes ?? [];
  const actions = installPlan?.actions ?? [];
  const isReady = capabilityReport?.can_run_now === true;
  const badgeClass = isReady || installPlan?.status === "not_required" ? "badge ok" : "badge warn";
  const actionDisabled = busy || !installPlan || actions.length === 0;

  return (
    <section className="tool-panel install-plan-panel">
      <div className="view-header split compact">
        <div>
          <h2>Install Plan</h2>
          <p>{error ?? installSummary(capabilityReport, installPlan)}</p>
        </div>
        <button disabled={busy} onClick={onRefreshInstallPlan} type="button">
          <RefreshCcw size={15} />
          <span>Refresh plan</span>
        </button>
      </div>
      <div className="install-summary-grid">
        <SummaryCell label="Capability" value={capabilityReport?.status ?? "unchecked"} />
        <SummaryCell label="Models" value={`${missingModels.length} missing`} />
        <SummaryCell label="Nodes" value={`${missingNodes.length} missing`} />
        <div>
          <span>Plan</span>
          <strong>
            <span className={badgeClass}>{installPlan?.status ?? "unchecked"}</span>
          </strong>
        </div>
      </div>
      <div className="install-list-grid">
        <RequirementList
          empty="No missing model references."
          items={missingModels.map((model) => model.filename)}
          title="Missing models"
        />
        <RequirementList
          empty="No missing node types."
          items={missingNodes.map((node) => node.node_type)}
          title="Missing nodes"
        />
      </div>
      <ActionTable actions={actions} />
      <div className="action-row install-actions">
        <button disabled={actionDisabled} onClick={() => onRecordInstallDecision("accepted")} type="button">
          <CheckCircle2 size={15} />
          <span>Record accepted</span>
        </button>
        <button disabled={actionDisabled} onClick={() => onRecordInstallDecision("rejected")} type="button">
          <XCircle size={15} />
          <span>Record rejected</span>
        </button>
      </div>
      <AuditList audit={audit} />
    </section>
  );
}

function SummaryCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function RequirementList({ empty, items, title }: { empty: string; items: string[]; title: string }) {
  return (
    <div className="install-requirements">
      <h3>{title}</h3>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p>{empty}</p>
      )}
    </div>
  );
}

function ActionTable({ actions }: { actions: InstallPlanAction[] }) {
  if (actions.length === 0) {
    return (
      <div className="install-empty">
        <ShieldCheck size={16} />
        <span>No pending install actions.</span>
      </div>
    );
  }

  return (
    <div className="install-table-wrap">
      <table className="install-table">
        <thead>
          <tr>
            <th>Kind</th>
            <th>Target</th>
            <th>Reason</th>
            <th>Mode</th>
          </tr>
        </thead>
        <tbody>
          {actions.map((action, index) => (
            <tr key={`${action.kind}-${action.filename ?? action.node_type ?? index}`}>
              <td>{action.kind}</td>
              <td>{action.filename ?? action.node_type ?? action.target_type ?? ""}</td>
              <td>{action.reason ?? ""}</td>
              <td>{action.automatic ? "automatic" : "manual review"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuditList({ audit }: { audit: InstallAudit | null }) {
  const entries = audit?.entries ?? [];
  return (
    <div className="install-audit">
      <h3>Recent decisions</h3>
      {entries.length ? (
        <ul>
          {entries.slice(-5).reverse().map((entry) => (
            <li key={`${entry.timestamp}-${entry.decision}`}>
              <span>{entry.decision}</span>
              <strong>{entry.timestamp}</strong>
            </li>
          ))}
        </ul>
      ) : (
        <p>No audit entries recorded.</p>
      )}
    </div>
  );
}

function installSummary(report: CapabilityReport | null, plan: InstallPlan | null): string {
  if (!report) return "Capability report has not been loaded.";
  if (report.can_run_now) return "The current text-to-image probe is ready with local nodes and models.";
  if (plan?.actions.length) return `${plan.actions.length} manual review actions are pending.`;
  return "Capability review found missing information but no install actions.";
}

function formatBridgeState(status: LiveBridgeStatus | null): { label: string; detail: string } {
  if (!status) {
    return {
      label: "Unchecked",
      detail: "Live Bridge status has not been checked."
    };
  }
  if (status.ready) {
    return {
      label: "Ready",
      detail: "Bridge route, frontend client, and ComfyUI connection are ready."
    };
  }
  if (status.needs_restart) {
    return {
      label: "Restart required",
      detail: "ComfyUI needs to load the installed Live Bridge custom node."
    };
  }
  if (status.needs_refresh) {
    return {
      label: "Refresh required",
      detail: "The ComfyUI frontend client needs to reconnect."
    };
  }
  return {
    label: "Not ready",
    detail: status.diagnostics[0]?.message ?? "Live Bridge is not ready."
  };
}

function formatStatus(value: string): string {
  return value.replace(/[_-]/g, " ");
}

function State({ message, title }: { message: string; title: string }) {
  return (
    <section className="view">
      <div className="state-panel">
        <div>
          <h2>{title}</h2>
          <p>{message}</p>
        </div>
      </div>
    </section>
  );
}
