import type { WorkflowRow } from "../lib/types";

export function WorkflowsView({ workflows }: { workflows: WorkflowRow[] }) {
  return (
    <section className="view">
      <div className="view-header">
        <h1>Workflows</h1>
        <p>Local workflow files and validation state.</p>
      </div>
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
            <tr key={workflow.name}>
              <td>{workflow.name}</td>
              <td>{workflow.kind}</td>
              <td>{workflow.valid_json ? "yes" : "no"}</td>
              <td>{workflow.size}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
