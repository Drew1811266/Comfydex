import { useMemo, useState } from "react";
import type { LoadState, WorkflowRow } from "../lib/types";

export function WorkflowsView({
  error,
  state,
  workflows
}: {
  error: string | null;
  state: LoadState;
  workflows: WorkflowRow[];
}) {
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const selected = useMemo(
    () => workflows.find((workflow) => workflow.name === selectedName) ?? workflows[0],
    [selectedName, workflows]
  );

  if (state === "loading") return <State title="Loading workflows" message="Scanning local workflow records." />;
  if (state === "error") return <State title="Unable to load workflows" message={error ?? "Unable to load."} />;
  if (workflows.length === 0) {
    return <State title="No workflows indexed" message="Run Reindex after selecting a workspace." />;
  }

  return (
    <section className="view">
      <div className="view-header">
        <h1>Workflows</h1>
        <p>Local workflow files and validation state.</p>
      </div>
      <div className="split-pane">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Kind</th>
              <th>Valid</th>
              <th>Size</th>
            </tr>
          </thead>
          <tbody>
            {workflows.map((workflow) => (
              <tr
                className={selected?.name === workflow.name ? "selected" : undefined}
                key={workflow.name}
                onClick={() => setSelectedName(workflow.name)}
              >
                <td>{workflow.name}</td>
                <td>{workflow.kind}</td>
                <td>
                  <span className={workflow.valid_json ? "badge ok" : "badge warn"}>
                    {workflow.valid_json ? "valid" : "invalid"}
                  </span>
                </td>
                <td>{workflow.size}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <aside className="detail-panel">
          <span className="eyebrow">Selected workflow</span>
          <h2>{selected?.name}</h2>
          <dl>
            <dt>Kind</dt>
            <dd>{selected?.kind}</dd>
            <dt>Validation</dt>
            <dd>{selected?.valid_json ? "valid JSON" : "invalid JSON"}</dd>
            <dt>Modified</dt>
            <dd>{selected ? new Date(selected.modified_time * 1000).toLocaleString() : ""}</dd>
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
