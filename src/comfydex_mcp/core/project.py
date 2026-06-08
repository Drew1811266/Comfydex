from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import ComfydexConfig


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
