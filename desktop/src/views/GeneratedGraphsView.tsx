import { RefreshCw, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import type { LoadState, UiGraphHistory, UiGraphHistoryEntry } from "../lib/types";

type GeneratedGraphsViewProps = {
  busy: boolean;
  error: string | null;
  history: UiGraphHistory | null;
  onPush: (workflowName: string) => void;
  onRefresh: () => void;
  state: LoadState;
};

export function GeneratedGraphsView({
  busy,
  error,
  history,
  onPush,
  onRefresh,
  state
}: GeneratedGraphsViewProps) {
  const entries = history?.entries ?? [];
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const selected = useMemo(
    () => entries.find((entry) => entryKey(entry) === selectedKey) ?? entries[0],
    [entries, selectedKey]
  );

  if (state === "loading") return <State title="Loading generated graphs" message="Reading graph history." />;
  if (state === "error") return <State title="Unable to load generated graphs" message={error ?? "Unable to load."} />;
  if (entries.length === 0) {
    return <State title="No generated graphs" message="Generated UI workflow records will appear here." />;
  }

  return (
    <section className="view">
      <div className="view-header split">
        <div>
          <h1>Generated Graphs</h1>
          <p>Generated UI workflow history and Live Bridge push state.</p>
        </div>
        <div className="action-row">
          <button disabled={busy} onClick={onRefresh} type="button">
            <RefreshCw size={15} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      <div className="split-pane generated-workbench">
        <table className="generated-table">
          <thead>
            <tr>
              <th>Workflow</th>
              <th>Status</th>
              <th>Template</th>
              <th>Recipe</th>
              <th>Nodes</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const key = entryKey(entry);
              return (
                <tr
                  className={selected && entryKey(selected) === key ? "selected" : undefined}
                  key={key}
                  onClick={() => setSelectedKey(key)}
                >
                  <td>{entry.workflow_name}</td>
                  <td>
                    <span className={statusClass(entry.status)}>{entry.status}</span>
                  </td>
                  <td>{entry.template_id ?? ""}</td>
                  <td>{entry.recipe_id ?? ""}</td>
                  <td>{formatCount(entry.node_count)}</td>
                  <td>{formatTimestamp(entry.timestamp)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <aside className="detail-panel generated-detail">
          <span className="eyebrow">Selected graph</span>
          <h2>{selected?.workflow_name}</h2>
          <div className="generated-actions">
            <button
              disabled={busy || !selected}
              onClick={() => selected && onPush(selected.workflow_name)}
              type="button"
            >
              <Upload size={15} />
              <span>Push</span>
            </button>
          </div>
          <dl>
            <dt>Status</dt>
            <dd>{selected?.status ?? ""}</dd>
            <dt>Template</dt>
            <dd>{selected?.template_id ?? ""}</dd>
            <dt>Recipe</dt>
            <dd>{selected?.recipe_id ?? ""}</dd>
            <dt>Nodes</dt>
            <dd>{formatCount(selected?.node_count)}</dd>
            <dt>Links</dt>
            <dd>{formatCount(selected?.link_count)}</dd>
            <dt>Timestamp</dt>
            <dd>{selected ? formatTimestamp(selected.timestamp) : ""}</dd>
            <dt>Path</dt>
            <dd>{selected?.path ?? history?.path ?? ""}</dd>
          </dl>
          {selected?.push_result ? (
            <pre>{JSON.stringify(selected.push_result, null, 2)}</pre>
          ) : null}
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

function entryKey(entry: UiGraphHistoryEntry): string {
  return `${entry.timestamp}:${entry.workflow_name}:${entry.status}`;
}

function statusClass(status: string): string {
  return status === "saved" || status === "pushed" ? "badge ok" : "badge warn";
}

function formatCount(value: number | null | undefined): string {
  return value == null ? "" : String(value);
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
