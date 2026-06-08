import { Plug } from "lucide-react";
import type { ConfigState, ConnectionResult, LoadState } from "../lib/types";

export function SettingsView({
  config,
  connection,
  error,
  onCheckConnection,
  state
}: {
  config: ConfigState | null;
  connection: ConnectionResult | null;
  error: string | null;
  onCheckConnection: () => void;
  state: LoadState;
}) {
  if (state === "loading") return <State title="Loading settings" message="Reading project configuration." />;
  if (state === "error") return <State title="Unable to load settings" message={error ?? "Unable to load."} />;

  return (
    <section className="view">
      <div className="view-header split">
        <div>
          <h1>Settings</h1>
          <p>Workspace paths and ComfyUI connection configuration.</p>
        </div>
        <button onClick={onCheckConnection} type="button">
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
