import { useState } from "react";
import { RefreshCw, RotateCcw, ShieldCheck, Wrench } from "lucide-react";
import type {
  LoadState,
  RunRepairHistory,
  RunRepairResult,
  RunRow,
  UserGuidance
} from "../lib/types";

export function RunsView({
  busy,
  error,
  onPlanRepair,
  onRefresh,
  onRetryRepair,
  repair,
  repairError,
  repairHistory,
  runs,
  state
}: {
  busy: boolean;
  error: string | null;
  onPlanRepair: (runId: string) => void | Promise<void>;
  onRefresh: () => void;
  onRetryRepair: (runId: string, confirm?: boolean) => void | Promise<void>;
  repair: RunRepairResult | null;
  repairError: string | null;
  repairHistory: RunRepairHistory | null;
  runs: RunRow[];
  state: LoadState;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedRun = runs.find((run) => run.run_id === selectedId) ?? runs[0];
  const activeRepair =
    repair && selectedRun?.run_id === repair.run_id ? repair : null;

  if (state === "loading") return <State title="Loading runs" message="Reading execution records." />;
  if (state === "error") return <State title="Unable to load runs" message={error ?? "Unable to load."} />;
  if (runs.length === 0) return <State title="No runs indexed" message="Completed queue jobs will appear here." />;

  return (
    <section className="view">
      <div className="view-header">
        <h1>Runs</h1>
        <p>Execution records and output counts.</p>
      </div>
      <div className="split-pane runs-workbench">
        <table className="runs-table">
          <thead>
            <tr>
              <th>Run</th>
              <th>Workflow</th>
              <th>Status</th>
              <th>Outputs</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr
                className={selectedRun?.run_id === run.run_id ? "selected" : undefined}
                key={run.run_id}
                onClick={() => setSelectedId(run.run_id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedId(run.run_id);
                  }
                }}
                tabIndex={0}
              >
                <td>{run.run_id}</td>
                <td>{run.workflow_name ?? ""}</td>
                <td>
                  <span className={statusBadgeClass(run.status)}>{run.status}</span>
                </td>
                <td>{run.output_count}</td>
                <td>{run.updated_at ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <aside className="detail-panel">
          <span className="eyebrow">Selected run</span>
          <h2>{selectedRun?.run_id}</h2>
          <div className="detail-actions">
            <button
              disabled={busy || !selectedRun}
              onClick={() => selectedRun && void onPlanRepair(selectedRun.run_id)}
              type="button"
            >
              <Wrench size={14} />
              <span>Plan repair</span>
            </button>
            <button disabled={busy} onClick={onRefresh} title="Refresh runs" type="button">
              <RefreshCw size={14} />
            </button>
          </div>
          <dl>
            <dt>Workflow</dt>
            <dd>{selectedRun?.workflow_name ?? "unknown"}</dd>
            <dt>Status</dt>
            <dd>{selectedRun?.status}</dd>
            <dt>Outputs</dt>
            <dd>{selectedRun?.output_count ?? 0}</dd>
          </dl>
          <RepairPanel
            busy={busy}
            repair={activeRepair}
            repairError={repairError}
            run={selectedRun}
            onRetry={onRetryRepair}
          />
          <RepairHistory history={repairHistory} runId={selectedRun?.run_id} />
        </aside>
      </div>
    </section>
  );
}

function RepairPanel({
  busy,
  onRetry,
  repair,
  repairError,
  run
}: {
  busy: boolean;
  onRetry: (runId: string, confirm?: boolean) => void | Promise<void>;
  repair: RunRepairResult | null;
  repairError: string | null;
  run: RunRow | undefined;
}) {
  const retry = repair?.repair_plan.retry;
  const canRetry = Boolean(retry?.supported);
  const needsConfirmation = Boolean(retry?.requires_confirmation);
  const confirmationReady = repair?.status === "requires_confirmation";
  const retryLabel = needsConfirmation
    ? confirmationReady
      ? "Confirm retry"
      : "Prepare retry"
    : "Retry";

  return (
    <section className="repair-panel" aria-label="Run repair">
      <div className="repair-header">
        <span className="eyebrow">Repair</span>
        <span className={repair ? "badge warn" : "badge"}>{repair?.repair_plan.failure_class ?? run?.status}</span>
      </div>
      {repairError ? <p className="inline-error">{repairError}</p> : null}
      {repair ? (
        <>
          {repair.user_guidance ? (
            <GuidanceSummary guidance={repair.user_guidance} />
          ) : (
            <p className="repair-summary">{repair.repair_plan.summary}</p>
          )}
          <ul className="repair-action-list">
            {repair.repair_plan.actions.map((action, index) => (
              <li key={`${action.kind}-${action.target ?? index}`}>
                <ShieldCheck size={14} />
                <span>{action.kind}</span>
                <strong>{action.target ?? action.target_type ?? ""}</strong>
              </li>
            ))}
          </ul>
          {canRetry ? (
            <button
              className="repair-retry-button"
              disabled={busy || !run}
              onClick={() => run && void onRetry(run.run_id, confirmationReady)}
              type="button"
            >
              <RotateCcw size={14} />
              <span>{retryLabel}</span>
            </button>
          ) : null}
          {repair.retry_result ? (
            <p className="repair-summary">Retry result: {String(repair.retry_result.status ?? repair.status)}</p>
          ) : null}
        </>
      ) : (
        <p className="repair-summary">No repair plan loaded.</p>
      )}
    </section>
  );
}

function GuidanceSummary({ guidance }: { guidance: UserGuidance }) {
  return (
    <section className="inline-guidance" aria-label="Repair summary">
      <span className={guidance.severity === "ok" ? "badge ok" : "badge warn"}>{guidance.severity}</span>
      <div>
        <strong>{guidance.title}</strong>
        <p>{guidance.summary}</p>
      </div>
    </section>
  );
}

function RepairHistory({
  history,
  runId
}: {
  history: RunRepairHistory | null;
  runId: string | undefined;
}) {
  const entries = (history?.entries ?? [])
    .filter((entry) => !runId || entry.run_id === runId)
    .slice(0, 3);
  if (entries.length === 0) return null;

  return (
    <section className="repair-history" aria-label="Repair history">
      <span className="eyebrow">History</span>
      <ul>
        {entries.map((entry) => (
          <li key={`${entry.timestamp}-${entry.status}`}>
            <span>{entry.status}</span>
            <strong>{entry.failure_class ?? "unknown"}</strong>
          </li>
        ))}
      </ul>
    </section>
  );
}

function statusBadgeClass(status: string): string {
  if (status === "completed") return "badge ok";
  if (status === "failed") return "badge warn";
  return "badge";
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
