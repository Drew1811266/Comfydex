import { useEffect, useMemo, useState } from "react";
import { readBatch } from "../lib/api";
import type { BatchRecord, BatchSummary, LoadState } from "../lib/types";

export function BatchesView({
  batches,
  error,
  state
}: {
  batches: BatchSummary[];
  error: string | null;
  state: LoadState;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<BatchRecord | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const selected = useMemo(
    () => batches.find((batch) => batch.batch_id === selectedId) ?? batches[0],
    [batches, selectedId]
  );

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    let active = true;
    setDetailError(null);
    void readBatch(selected.batch_id)
      .then((record) => {
        if (active) setDetail(record);
      })
      .catch((caught) => {
        if (active) setDetailError(caught instanceof Error ? caught.message : String(caught));
      });
    return () => {
      active = false;
    };
  }, [selected]);

  if (state === "loading") return <State title="Loading batches" message="Reading batch records." />;
  if (state === "error") return <State title="Unable to load batches" message={error ?? "Unable to load."} />;
  if (batches.length === 0) {
    return <State title="No batches indexed" message="Batch records created by MCP tools will appear here." />;
  }

  return (
    <section className="view">
      <div className="view-header">
        <h1>Batches</h1>
        <p>Batch task records, child runs, and variation parameters.</p>
      </div>
      <div className="split-pane batch-workbench">
        <table>
          <thead>
            <tr>
              <th>Batch</th>
              <th>Workflow</th>
              <th>Status</th>
              <th>Runs</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {batches.map((batch) => (
              <tr
                className={selected?.batch_id === batch.batch_id ? "selected" : undefined}
                key={batch.batch_id}
                onClick={() => setSelectedId(batch.batch_id)}
              >
                <td>{batch.label || batch.batch_id}</td>
                <td>{batch.workflow_name}</td>
                <td>
                  <span className={batch.status === "completed" ? "badge ok" : "badge warn"}>{batch.status}</span>
                </td>
                <td>
                  {batch.completed_count} completed / {batch.failed_count} failed
                </td>
                <td>{batch.updated_at ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <aside className="detail-panel">
          <span className="eyebrow">Batch detail</span>
          <h2>{selected?.batch_id}</h2>
          {detailError ? <p>{detailError}</p> : null}
          <dl>
            <dt>Status</dt>
            <dd>{detail?.status ?? selected?.status}</dd>
            <dt>Workflow</dt>
            <dd>{detail?.workflow_name ?? selected?.workflow_name}</dd>
            <dt>Created</dt>
            <dd>{detail?.created_at ?? selected?.created_at ?? ""}</dd>
            <dt>Updated</dt>
            <dd>{detail?.updated_at ?? selected?.updated_at ?? ""}</dd>
          </dl>
        </aside>
      </div>

      <div className="panel-grid batch-panels">
        <section className="tool-panel">
          <h2>Child runs</h2>
          <table>
            <thead>
              <tr>
                <th>Index</th>
                <th>Status</th>
                <th>Run</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {(detail?.runs ?? []).map((run) => (
                <tr key={run.index}>
                  <td>{run.index}</td>
                  <td>{run.status}</td>
                  <td>{run.run_id ?? ""}</td>
                  <td>{run.error ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="tool-panel report-panel">
          <h2>Variation parameters</h2>
          <pre>{JSON.stringify((detail?.runs ?? []).map((run) => run.parameters), null, 2)}</pre>
        </section>
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
