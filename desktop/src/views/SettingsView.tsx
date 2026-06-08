import type { ConfigState } from "../lib/types";

export function SettingsView({ config }: { config: ConfigState | null }) {
  return (
    <section className="view">
      <div className="view-header">
        <h1>Settings</h1>
        <p>Workspace paths and ComfyUI connection configuration.</p>
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
      </div>
    </section>
  );
}
