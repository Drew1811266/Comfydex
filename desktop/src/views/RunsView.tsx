import { useState } from "react";
import type { LoadState, RunRow } from "../lib/types";

export function RunsView({
  error,
  runs,
  state
}: {
  error: string | null;
  runs: RunRow[];
  state: LoadState;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedRun = runs.find((run) => run.run_id === selectedId) ?? runs[0];

  if (state === "loading") return <State title="Loading runs" message="Reading execution records." />;
  if (state === "error") return <State title="Unable to load runs" message={error ?? "Unable to load."} />;
  if (runs.length === 0) return <State title="No runs indexed" message="Completed queue jobs will appear here." />;

  return (
    <section className="view">
      <div className="view-header">
        <h1>Runs</h1>
        <p>Execution records and output counts.</p>
      </div>
      <div className="split-pane">
        <table>
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
              >
                <td>{run.run_id}</td>
                <td>{run.workflow_name ?? ""}</td>
                <td>
                  <span className={run.status === "completed" ? "badge ok" : "badge"}>{run.status}</span>
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
          <dl>
            <dt>Workflow</dt>
            <dd>{selectedRun?.workflow_name ?? "unknown"}</dd>
            <dt>Status</dt>
            <dd>{selectedRun?.status}</dd>
            <dt>Outputs</dt>
            <dd>{selectedRun?.output_count ?? 0}</dd>
          </dl>
        </aside>
      </div>
    </section>
  );
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
