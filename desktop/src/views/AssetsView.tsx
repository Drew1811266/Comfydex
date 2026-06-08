import { Search, Star } from "lucide-react";
import { useMemo, useState } from "react";
import type { AssetRow, LoadState } from "../lib/types";

export function AssetsView({
  assets,
  error,
  state
}: {
  assets: AssetRow[];
  error: string | null;
  state: LoadState;
}) {
  const [query, setQuery] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const filteredAssets = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return assets.filter((asset) => {
      const matchesQuery =
        normalized.length === 0 ||
        asset.filename.toLowerCase().includes(normalized) ||
        asset.tags.some((tag) => tag.toLowerCase().includes(normalized));
      const matchesFavorite = !favoritesOnly || asset.favorite;
      return matchesQuery && matchesFavorite;
    });
  }, [assets, favoritesOnly, query]);
  const selected = filteredAssets.find((asset) => asset.asset_id === selectedId) ?? filteredAssets[0];

  if (state === "loading") return <State title="Loading assets" message="Reading generated output records." />;
  if (state === "error") return <State title="Unable to load assets" message={error ?? "Unable to load."} />;
  if (assets.length === 0) {
    return <State title="No assets indexed" message="Generated outputs will appear after a project reindex." />;
  }

  return (
    <section className="view">
      <div className="view-header split">
        <div>
          <h1>Assets</h1>
          <p>Searchable generated output records.</p>
        </div>
        <div className="toolbar">
          <label className="search-box">
            <Search size={15} />
            <input
              aria-label="Search assets"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search filename or tag"
              value={query}
            />
          </label>
          <label className="toggle">
            <input
              checked={favoritesOnly}
              onChange={(event) => setFavoritesOnly(event.target.checked)}
              type="checkbox"
            />
            <span>Favorites</span>
          </label>
        </div>
      </div>
      <div className="split-pane">
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
            {filteredAssets.map((asset) => (
              <tr
                className={selected?.asset_id === asset.asset_id ? "selected" : undefined}
                key={asset.asset_id}
                onClick={() => setSelectedId(asset.asset_id)}
              >
                <td>{asset.filename}</td>
                <td>{asset.workflow_name ?? ""}</td>
                <td>
                  <span className={asset.status === "completed" ? "badge ok" : "badge"}>{asset.status}</span>
                </td>
                <td>{asset.rating ?? ""}</td>
                <td>{asset.tags.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <aside className="detail-panel">
          <span className="eyebrow">Selected asset</span>
          <h2>{selected?.filename ?? "No matching assets"}</h2>
          {selected ? (
            <dl>
              <dt>Workflow</dt>
              <dd>{selected.workflow_name ?? "unknown"}</dd>
              <dt>Favorite</dt>
              <dd>
                {selected.favorite ? <Star className="inline-icon" fill="currentColor" size={14} /> : null}
                {selected.favorite ? "favorite" : "not favorite"}
              </dd>
              <dt>Tags</dt>
              <dd>{selected.tags.join(", ") || "none"}</dd>
            </dl>
          ) : (
            <p>No rows match the current filters.</p>
          )}
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
