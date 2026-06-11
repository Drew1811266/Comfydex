import { Plug, RefreshCcw, RotateCw } from "lucide-react";
import type { ConfigState, ConnectionResult, LiveBridgeStatus, LoadState } from "../lib/types";

export function SettingsView({
  busy,
  config,
  connection,
  error,
  liveBridgeStatus,
  onCheckConnection,
  onReloadLiveBridgeBackend,
  onReloadLiveBridgeClient,
  onVerifyLiveBridgeStatus,
  state
}: {
  busy: boolean;
  config: ConfigState | null;
  connection: ConnectionResult | null;
  error: string | null;
  liveBridgeStatus: LiveBridgeStatus | null;
  onCheckConnection: () => void;
  onReloadLiveBridgeBackend: () => void;
  onReloadLiveBridgeClient: () => void;
  onVerifyLiveBridgeStatus: () => void;
  state: LoadState;
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
    </section>
  );
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
