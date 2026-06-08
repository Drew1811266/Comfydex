from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import ComfydexConfig
from .schema import SCHEMA_VERSION


@dataclass(frozen=True)
class ProjectContext:
    workspace: Path
    workflows_dir: Path
    runs_dir: Path
    state_dir: Path
    database_path: Path


def project_context_from_config(config: ComfydexConfig) -> ProjectContext:
    workspace = config.workspace.resolve()
    state_dir = (workspace / ".comfydex").resolve()
    database_path = (state_dir / "comfydex.db").resolve()
    database_path.relative_to(state_dir)
    return ProjectContext(
        workspace=workspace,
        workflows_dir=config.workflows_dir.resolve(),
        runs_dir=config.runs_dir.resolve(),
        state_dir=state_dir,
        database_path=database_path,
    )


def project_status(context: ProjectContext) -> dict[str, object]:
    from .database import migrate_project, open_database
    from .store import counts, metadata_value

    migrate_project(context)
    with open_database(context.database_path) as db:
        current_counts = counts(db)
        last_reindexed_at = metadata_value(db, "last_reindexed_at")

    return {
        "workspace": str(context.workspace),
        "workflows_dir": str(context.workflows_dir),
        "runs_dir": str(context.runs_dir),
        "state_dir": str(context.state_dir),
        "database_path": str(context.database_path),
        "schema_version": SCHEMA_VERSION,
        "database_exists": context.database_path.is_file(),
        "counts": current_counts,
        "last_reindexed_at": last_reindexed_at,
    }
