import type { ProjectStatus } from "../lib/types";

export function DashboardView({ status }: { status: ProjectStatus | null }) {
  const counts = status?.counts;
  return (
    <section className="view">
      <div className="view-header">
        <h1>Project Dashboard</h1>
        <p>Schema, index counts, and connection readiness.</p>
      </div>
      <div className="metric-grid">
        <Metric label="Schema" value={status?.schema_version ?? "loading"} />
        <Metric label="Workflows" value={counts?.workflows ?? 0} />
        <Metric label="Runs" value={counts?.runs ?? 0} />
        <Metric label="Assets" value={counts?.assets ?? 0} />
        <Metric label="Errors" value={counts?.errors ?? 0} />
      </div>
      <div className="detail-band">
        <span>Database</span>
        <strong>{status?.database_path ?? ".comfydex/comfydex.db"}</strong>
      </div>
      <div className="detail-band">
        <span>Last reindex</span>
        <strong>{status?.last_reindexed_at ?? "Not indexed"}</strong>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
