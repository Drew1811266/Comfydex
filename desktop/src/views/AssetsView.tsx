import { FileText, Search, ShieldCheck, Star, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  compareAssets,
  exportAssetLibraryReport,
  planAssetCleanup,
  updateAssetMetadata
} from "../lib/api";
import type { AssetComparison, AssetReport, AssetRow, CleanupPlan, LoadState } from "../lib/types";

type AssetMode = "gallery" | "table";

export function AssetsView({
  assets,
  error,
  state
}: {
  assets: AssetRow[];
  error: string | null;
  state: LoadState;
}) {
  const [assetRows, setAssetRows] = useState<AssetRow[]>(assets);
  const [mode, setMode] = useState<AssetMode>("gallery");
  const [query, setQuery] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [minRating, setMinRating] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [comparison, setComparison] = useState<AssetComparison | null>(null);
  const [cleanupPlan, setCleanupPlan] = useState<CleanupPlan | null>(null);
  const [cleanupConfirmed, setCleanupConfirmed] = useState(false);
  const [report, setReport] = useState<AssetReport | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    setAssetRows(assets);
  }, [assets]);

  const filteredAssets = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const normalizedTag = tagFilter.trim().toLowerCase();
    return assetRows.filter((asset) => {
      const matchesQuery =
        normalized.length === 0 ||
        asset.filename.toLowerCase().includes(normalized) ||
        (asset.prompt_text ?? "").toLowerCase().includes(normalized) ||
        asset.tags.some((tag) => tag.toLowerCase().includes(normalized));
      const matchesTag =
        normalizedTag.length === 0 || asset.tags.some((tag) => tag.toLowerCase().includes(normalizedTag));
      const matchesFavorite = !favoritesOnly || asset.favorite;
      const matchesRating = (asset.rating ?? 0) >= minRating;
      return matchesQuery && matchesTag && matchesFavorite && matchesRating;
    });
  }, [assetRows, favoritesOnly, minRating, query, tagFilter]);
  const selected = filteredAssets.find((asset) => asset.asset_id === selectedId) ?? filteredAssets[0];

  if (state === "loading") return <State title="Loading assets" message="Reading generated output records." />;
  if (state === "error") return <State title="Unable to load assets" message={error ?? "Unable to load."} />;
  if (assets.length === 0) {
    return <State title="No assets indexed" message="Generated outputs will appear after a project reindex." />;
  }

  async function patchSelected(patch: Parameters<typeof updateAssetMetadata>[1]) {
    if (!selected) return;
    setBusy("metadata");
    setActionError(null);
    try {
      const updated = await updateAssetMetadata(selected.asset_id, patch);
      setAssetRows((rows) =>
        rows.map((asset) => (asset.asset_id === selected.asset_id ? { ...asset, ...updated } : asset))
      );
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function runCompare() {
    if (compareIds.length !== 2) return;
    setBusy("compare");
    setActionError(null);
    try {
      setComparison(await compareAssets(compareIds[0], compareIds[1]));
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function runCleanup(confirm: boolean) {
    const asset_ids = selected ? [selected.asset_id] : undefined;
    setBusy("cleanup");
    setActionError(null);
    try {
      setCleanupPlan(await planAssetCleanup({ asset_ids, confirm }));
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function runReport() {
    setBusy("report");
    setActionError(null);
    try {
      setReport(await exportAssetLibraryReport({ query, favorite: favoritesOnly || undefined, min_rating: minRating || undefined }));
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  function toggleCompare(assetId: string) {
    setComparison(null);
    setCompareIds((current) => {
      if (current.includes(assetId)) return current.filter((value) => value !== assetId);
      return [...current, assetId].slice(-2);
    });
  }

  return (
    <section className="view">
      <div className="view-header split">
        <div>
          <h1>Assets</h1>
          <p>Gallery, metadata, comparison, cleanup, and report controls.</p>
        </div>
        <div className="segmented">
          <button className={mode === "gallery" ? "active" : ""} onClick={() => setMode("gallery")} type="button">
            Gallery
          </button>
          <button className={mode === "table" ? "active" : ""} onClick={() => setMode("table")} type="button">
            Table
          </button>
        </div>
      </div>

      <div className="toolbar asset-toolbar">
        <label className="search-box">
          <Search size={15} />
          <input
            aria-label="Search assets"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search filename, prompt, or tag"
            value={query}
          />
        </label>
        <label className="search-box compact-field">
          Tag
          <input aria-label="Tag filter" onChange={(event) => setTagFilter(event.target.value)} value={tagFilter} />
        </label>
        <label className="toggle">
          <input
            checked={favoritesOnly}
            onChange={(event) => setFavoritesOnly(event.target.checked)}
            type="checkbox"
          />
          <span>Favorite</span>
        </label>
        <label className="compact-select">
          Rating
          <input
            max={5}
            min={0}
            onChange={(event) => setMinRating(Number(event.target.value))}
            type="number"
            value={minRating}
          />
        </label>
      </div>

      {actionError ? <div className="state-panel error">{actionError}</div> : null}

      <div className="asset-workbench">
        <div className="asset-main">
          {mode === "gallery" ? (
            <div className="asset-gallery">
              {filteredAssets.map((asset) => (
                <button
                  className={selected?.asset_id === asset.asset_id ? "asset-tile selected" : "asset-tile"}
                  key={asset.asset_id}
                  onClick={() => setSelectedId(asset.asset_id)}
                  type="button"
                >
                  <div className="asset-preview">{asset.filename.split(".").pop()?.toUpperCase() ?? "FILE"}</div>
                  <strong>{asset.filename}</strong>
                  <span>{asset.workflow_name ?? "unknown workflow"}</span>
                  <span>{asset.favorite ? "Favorite" : "Not favorite"} · Rating {asset.rating ?? "-"}</span>
                </button>
              ))}
            </div>
          ) : (
            <AssetTable assets={filteredAssets} onSelect={setSelectedId} selectedId={selected?.asset_id ?? null} />
          )}
        </div>

        <aside className="detail-panel asset-detail">
          <span className="eyebrow">Selected asset</span>
          <h2>{selected?.filename ?? "No matching assets"}</h2>
          {selected ? (
            <>
              <div className="metadata-actions">
                <button
                  disabled={busy === "metadata"}
                  onClick={() => void patchSelected({ favorite: !selected.favorite })}
                  type="button"
                >
                  <Star fill={selected.favorite ? "currentColor" : "none"} size={15} />
                  Favorite
                </button>
                <label>
                  Rating
                  <input
                    max={5}
                    min={0}
                    onBlur={(event) => void patchSelected({ rating: Number(event.target.value) || null })}
                    type="number"
                    defaultValue={selected.rating ?? 0}
                  />
                </label>
              </div>
              <label>
                Tags
                <input
                  defaultValue={selected.tags.join(", ")}
                  onBlur={(event) =>
                    void patchSelected({
                      tags: event.target.value
                        .split(",")
                        .map((tag) => tag.trim())
                        .filter(Boolean)
                    })
                  }
                />
              </label>
              <label>
                Notes
                <textarea
                  defaultValue={selected.notes ?? ""}
                  onBlur={(event) => void patchSelected({ notes: event.target.value })}
                />
              </label>
              <dl>
                <dt>Workflow</dt>
                <dd>{selected.workflow_name ?? "unknown"}</dd>
                <dt>Prompt</dt>
                <dd>{selected.prompt_text ?? "none"}</dd>
                <dt>Path</dt>
                <dd>{selected.path ?? "not recorded"}</dd>
              </dl>
            </>
          ) : (
            <p>No rows match the current filters.</p>
          )}
        </aside>
      </div>

      <div className="panel-grid">
        <section className="tool-panel">
          <h2>Compare</h2>
          <p>Select two assets, then compare indexed metadata.</p>
          <div className="compare-list">
            {filteredAssets.slice(0, 6).map((asset) => (
              <label className="toggle" key={asset.asset_id}>
                <input
                  checked={compareIds.includes(asset.asset_id)}
                  onChange={() => toggleCompare(asset.asset_id)}
                  type="checkbox"
                />
                <span>{asset.filename}</span>
              </label>
            ))}
          </div>
          <button disabled={compareIds.length !== 2 || busy === "compare"} onClick={() => void runCompare()} type="button">
            Compare
          </button>
          {comparison ? (
            <pre>{JSON.stringify(changedDifferences(comparison), null, 2)}</pre>
          ) : null}
        </section>

        <section className="tool-panel">
          <h2>Cleanup</h2>
          <p>Dry run first; confirmed cleanup uses the shared safe cleanup planner.</p>
          <button disabled={!selected || busy === "cleanup"} onClick={() => void runCleanup(false)} type="button">
            <ShieldCheck size={15} />
            Dry run
          </button>
          <label className="toggle">
            <input
              checked={cleanupConfirmed}
              onChange={(event) => setCleanupConfirmed(event.target.checked)}
              type="checkbox"
            />
            <span>Confirm cleanup</span>
          </label>
          <button
            disabled={!selected || !cleanupConfirmed || busy === "cleanup"}
            onClick={() => void runCleanup(true)}
            type="button"
          >
            <Trash2 size={15} />
            Confirm cleanup
          </button>
          {cleanupPlan ? (
            <dl>
              <dt>Candidates</dt>
              <dd>{cleanupPlan.candidates.length}</dd>
              <dt>Skipped</dt>
              <dd>{cleanupPlan.skipped.length}</dd>
              <dt>Deleted</dt>
              <dd>{cleanupPlan.deleted.length}</dd>
            </dl>
          ) : null}
        </section>

        <section className="tool-panel report-panel">
          <h2>Reports</h2>
          <p>Generate report for the current asset filters.</p>
          <button disabled={busy === "report"} onClick={() => void runReport()} type="button">
            <FileText size={15} />
            Generate report
          </button>
          {report ? (
            <>
              <span className="eyebrow">{report.path}</span>
              <pre>{report.markdown}</pre>
            </>
          ) : null}
        </section>
      </div>
    </section>
  );
}

function AssetTable({
  assets,
  onSelect,
  selectedId
}: {
  assets: AssetRow[];
  onSelect: (assetId: string) => void;
  selectedId: string | null;
}) {
  return (
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
          <tr
            className={selectedId === asset.asset_id ? "selected" : undefined}
            key={asset.asset_id}
            onClick={() => onSelect(asset.asset_id)}
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
  );
}

function changedDifferences(comparison: AssetComparison) {
  return Object.fromEntries(
    Object.entries(comparison.differences).filter(([, value]) => value.changed)
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
