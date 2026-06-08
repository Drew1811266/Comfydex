import type { AssetRow } from "../lib/types";

export function AssetsView({ assets }: { assets: AssetRow[] }) {
  return (
    <section className="view">
      <div className="view-header">
        <h1>Assets</h1>
        <p>Searchable generated output records.</p>
      </div>
      <table>
        <thead>
          <tr>
            <th>Filename</th>
            <th>Workflow</th>
            <th>Status</th>
            <th>Rating</th>
            <th>Tags</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => (
            <tr key={asset.asset_id}>
              <td>{asset.filename}</td>
              <td>{asset.workflow_name ?? ""}</td>
              <td>{asset.status}</td>
              <td>{asset.rating ?? ""}</td>
              <td>{asset.tags.join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
