import type { RunRow } from "../lib/types";

export function RunsView({ runs }: { runs: RunRow[] }) {
  return (
    <section className="view">
      <div className="view-header">
        <h1>Runs</h1>
        <p>Execution records and output counts.</p>
      </div>
      <table>
        <thead>
          <tr>
            <th>Run</th>
            <th>Workflow</th>
            <th>Status</th>
            <th>Outputs</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.run_id}>
              <td>{run.run_id}</td>
              <td>{run.workflow_name ?? ""}</td>
              <td>{run.status}</td>
              <td>{run.output_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
