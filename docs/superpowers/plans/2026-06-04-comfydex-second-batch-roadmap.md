# Comfydex Second Batch Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Comfydex `0.2.0` as one large release covering UI workflow import and conversion, assisted workflow building, ComfyUI custom node development support, and run/output/batch management.

**Architecture:** Keep the MCP server as a thin tool layer in `src/comfydex_mcp/server.py`, with each new capability implemented in focused pure-Python modules under `src/comfydex_mcp/`. Persist user artifacts only through configured workspace directories, and require validation reports before any generated or converted workflow is marked submit-ready.

**Tech Stack:** Python 3.11, FastMCP, httpx, websockets, pytest, pytest-asyncio, respx, JSON/AST/pathlib standard-library tooling.

---

## Source Design

Approved design document:

- `docs/superpowers/specs/2026-06-04-comfydex-second-batch-roadmap-design.md`

Version target:

- `0.2.0`

Execution rule:

- Complete milestones 1 through 5 in order.
- After a milestone passes its gate, immediately start the next milestone.
- Stop only for a true blocker, failed review gate, destructive action, or user-directed scope change.

## Review Gate Used After Every Milestone

Run this gate before marking a milestone complete:

1. Targeted tests listed in that milestone.
2. Full suite:

```powershell
python -m pytest -q
```

3. Local plugin validation:

```powershell
python scripts/validate_plugin.py
```

4. Manifest JSON checks:

```powershell
python -m json.tool .codex-plugin/plugin.json > $null
python -m json.tool .mcp.json > $null
```

5. Spec compliance review prompt:

```text
Review the just-completed Comfydex milestone against docs/superpowers/specs/2026-06-04-comfydex-second-batch-roadmap-design.md.
Classify findings as Critical, Important, or Minor.
Focus on missing acceptance criteria, safety boundary violations, persistence format drift, and backward compatibility regressions.
The milestone may proceed only when Critical and Important findings are resolved.
```

6. Code quality review prompt:

```text
Review the just-completed Comfydex milestone for maintainability, test quality, path safety, deterministic behavior, and clear tool errors.
Classify findings as Critical, Important, or Minor.
Treat path traversal, accidental deletion, leaking configured headers, generated workflow overclaiming, and unisolated custom-node imports as Critical.
The milestone may proceed only when Critical and Important findings are resolved.
```

Optional live smoke check when a ComfyUI server is intentionally running:

```powershell
python scripts/smoke_check.py
```

This live check is not required for automated gates because CI and local review can run without a ComfyUI instance.

## File Structure

Create or modify these files during the release:

- Modify `src/comfydex_mcp/workflows.py`: preserve 0.1 APIs; return workflow metadata fields; reuse classification helpers.
- Modify `src/comfydex_mcp/paths.py`: add safe helpers for workspace-local custom node packages, report directories, plan directories, and batch directories.
- Modify `src/comfydex_mcp/server.py`: register new MCP tools as thin wrappers around new modules.
- Create `src/comfydex_mcp/ui_workflows.py`: UI workflow classification, import summaries, readiness reports.
- Create `src/comfydex_mcp/conversion.py`: conservative UI-to-API conversion and conversion gap reports.
- Create `src/comfydex_mcp/validation.py`: API prompt validation against ComfyUI `/object_info` metadata.
- Create `src/comfydex_mcp/templates.py`: workflow template catalog and template selection metadata.
- Create `src/comfydex_mcp/builder.py`: structured workflow build plans and API workflow generation from templates.
- Create `src/comfydex_mcp/patching.py`: targeted workflow patch operations with patch reports.
- Create `src/comfydex_mcp/custom_nodes.py`: custom node package inspection, mapping validation, class validation, isolated import checks.
- Create `src/comfydex_mcp/node_scaffold.py`: workspace-local custom node package scaffolding.
- Create `src/comfydex_mcp/node_docs.py`: deterministic markdown documentation generation for custom nodes.
- Create `src/comfydex_mcp/diagnostics.py`: run diagnosis from run records, workflow snapshots, events, and history-like data.
- Create `src/comfydex_mcp/reports.py`: markdown run report generation.
- Create `src/comfydex_mcp/outputs.py`: output listing and confirmed cleanup within `runs_dir`.
- Create `src/comfydex_mcp/batches.py`: batch records, parameter variation expansion, and per-run status aggregation.
- Create `scripts/validate_plugin.py`: local plugin manifest and repository shape validator.
- Add tests named in each milestone under `tests/`.
- Update `skills/comfyui-workflows/SKILL.md`.
- Add `skills/comfyui-custom-nodes/SKILL.md`.
- Add examples under `examples/`.
- Add usage docs under `docs/usage/`.
- Update `README.md`, `pyproject.toml`, `.codex-plugin/plugin.json`, and `src/comfydex_mcp/__init__.py` for `0.2.0`.

## Milestone 0: Baseline And Local Plugin Validator

Milestone 0 creates the validator used by later gates and confirms the 0.1 baseline before feature work starts.

### Task 0.1: Create Local Plugin Validator

**Files:**

- Create: `scripts/validate_plugin.py`
- Test: `tests/test_plugin_validation.py`

- [ ] **Step 1: Write validator tests**

Create `tests/test_plugin_validation.py` with these cases:

```python
from pathlib import Path

from scripts.validate_plugin import validate_plugin


def test_validate_plugin_accepts_current_repository():
    root = Path(__file__).parents[1]
    assert validate_plugin(root) == []


def test_validate_plugin_reports_missing_manifest(tmp_path):
    errors = validate_plugin(tmp_path)
    assert any(".codex-plugin/plugin.json" in error for error in errors)
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
python -m pytest tests/test_plugin_validation.py -q
```

Expected: fail because `scripts.validate_plugin` does not exist.

- [ ] **Step 3: Implement validator**

Create `scripts/validate_plugin.py` with these public functions:

```python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _read_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing required file: {path.as_posix()}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path.as_posix()}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"JSON root must be an object: {path.as_posix()}")
        return {}
    return value


def validate_plugin(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    manifest = _read_json(root / ".codex-plugin" / "plugin.json", errors)
    mcp = _read_json(root / ".mcp.json", errors)

    for key in ("name", "version", "description", "skills", "mcpServers", "interface"):
        if manifest and key not in manifest:
            errors.append(f"plugin manifest missing key: {key}")

    skills_path = manifest.get("skills") if isinstance(manifest.get("skills"), str) else "./skills/"
    skills_dir = (root / skills_path).resolve()
    if not skills_dir.exists() or not skills_dir.is_dir():
        errors.append(f"skills directory not found: {skills_dir}")
    elif not list(skills_dir.glob("*/SKILL.md")):
        errors.append(f"skills directory has no skill definitions: {skills_dir}")

    if mcp and not mcp.get("mcpServers"):
        errors.append(".mcp.json must define mcpServers")

    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        errors.append("missing pyproject.toml")

    server = root / "src" / "comfydex_mcp" / "server.py"
    if not server.exists():
        errors.append("missing MCP server module: src/comfydex_mcp/server.py")

    return errors


def main() -> int:
    errors = validate_plugin(Path.cwd())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Comfydex plugin validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run validator tests**

Run:

```powershell
python -m pytest tests/test_plugin_validation.py -q
```

Expected: pass.

- [ ] **Step 5: Run full baseline**

Run:

```powershell
python -m pytest -q
python scripts/validate_plugin.py
```

Expected: all tests pass and validator prints `Comfydex plugin validation passed`.

- [ ] **Step 6: Commit**

```powershell
git add scripts/validate_plugin.py tests/test_plugin_validation.py
git commit -m "test: add plugin validation gate"
```

### Milestone 0 Gate

Run:

```powershell
python -m pytest -q
python scripts/validate_plugin.py
python -m json.tool .codex-plugin/plugin.json > $null
python -m json.tool .mcp.json > $null
```

Proceed to milestone 1 only after the gate passes.

## Milestone 1: UI Workflow Import And Conversion

### Task 1.1: Workflow Classification And Metadata

**Files:**

- Create: `src/comfydex_mcp/ui_workflows.py`
- Modify: `src/comfydex_mcp/workflows.py`
- Test: `tests/test_ui_workflows.py`
- Test: `tests/test_workflows.py`

- [ ] **Step 1: Write classification tests**

Create `tests/test_ui_workflows.py` with these cases:

```python
from comfydex_mcp.ui_workflows import classify_workflow_payload, summarize_import_readiness


def test_classify_workflow_payload_identifies_ui_with_evidence():
    result = classify_workflow_payload({"nodes": [{"id": 1, "type": "SaveImage"}], "links": []})
    assert result["kind"] == "ui"
    assert "nodes is a list" in result["evidence"]


def test_classify_workflow_payload_identifies_api_with_evidence():
    result = classify_workflow_payload({"1": {"class_type": "SaveImage", "inputs": {}}})
    assert result["kind"] == "api"
    assert "node values include class_type" in result["evidence"]


def test_summarize_import_readiness_reports_ui_counts():
    result = summarize_import_readiness(
        {"nodes": [{"id": 1, "type": "SaveImage"}, {"id": 2, "type": "CustomNode"}], "links": []},
        object_info={"SaveImage": {"input": {"required": {"images": ("IMAGE",)}}}},
    )
    assert result["kind"] == "ui"
    assert result["nodes_total"] == 2
    assert result["known_node_types"] == ["SaveImage"]
    assert result["unknown_node_types"] == ["CustomNode"]
```

Extend `tests/test_workflows.py` so `read_workflow()` returns metadata:

```python
def test_read_workflow_includes_metadata_fields(tmp_path):
    save_workflow(tmp_path, "wf.json", API_WORKFLOW)
    loaded = read_workflow(tmp_path, "wf.json")

    assert loaded["metadata"] == {
        "name": "wf.json",
        "kind": "api",
        "source": "manual",
        "submit_ready": True,
        "validation_status": "unknown",
    }


def test_workflow_metadata_persists_source_and_validation_status(tmp_path):
    save_workflow(
        tmp_path,
        "generated.json",
        API_WORKFLOW,
        source="generated",
        validation_status="valid",
    )

    loaded = read_workflow(tmp_path, "generated.json")

    assert loaded["metadata"]["source"] == "generated"
    assert loaded["metadata"]["validation_status"] == "valid"
    assert loaded["metadata"]["submit_ready"] is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_ui_workflows.py tests/test_workflows.py -q
```

Expected: fail because `ui_workflows.py` and metadata fields are not present.

- [ ] **Step 3: Implement classification module**

Create `src/comfydex_mcp/ui_workflows.py` with these functions:

```python
from __future__ import annotations

from collections import Counter
from typing import Any


def classify_workflow_payload(payload: Any) -> dict[str, Any]:
    evidence: list[str] = []
    if isinstance(payload, dict) and isinstance(payload.get("nodes"), list):
        evidence.append("nodes is a list")
        if isinstance(payload.get("links", []), list):
            evidence.append("links is a list")
        return {"kind": "ui", "evidence": evidence}
    if isinstance(payload, dict) and payload and all(
        isinstance(value, dict) and "class_type" in value for value in payload.values()
    ):
        evidence.append("node values include class_type")
        return {"kind": "api", "evidence": evidence}
    return {"kind": "unknown", "evidence": ["payload did not match ui or api workflow shape"]}


def summarize_import_readiness(payload: dict[str, Any], object_info: dict[str, Any] | None = None) -> dict[str, Any]:
    classification = classify_workflow_payload(payload)
    if classification["kind"] != "ui":
        return {
            "kind": classification["kind"],
            "nodes_total": 0,
            "known_node_types": [],
            "unknown_node_types": [],
            "node_types": {},
            "conversion_ready": classification["kind"] == "api",
        }

    node_types = Counter(
        str(node.get("type", "unknown"))
        for node in payload.get("nodes", [])
        if isinstance(node, dict)
    )
    known = sorted(node_type for node_type in node_types if object_info and node_type in object_info)
    unknown = sorted(node_type for node_type in node_types if object_info is not None and node_type not in object_info)
    return {
        "kind": "ui",
        "nodes_total": sum(node_types.values()),
        "known_node_types": known,
        "unknown_node_types": unknown,
        "node_types": dict(sorted(node_types.items())),
        "conversion_ready": object_info is None or not unknown,
    }
```

- [ ] **Step 4: Extend workflow metadata without breaking 0.1 behavior**

Modify `src/comfydex_mcp/workflows.py`:

```python
def workflow_metadata_filename(filename: str) -> str:
    stem = filename[:-5] if filename.endswith(".json") else filename
    return f"{stem}.metadata.json"


def workflow_metadata(
    filename: str,
    payload: dict[str, Any],
    *,
    source: str = "manual",
    validation_status: str = "unknown",
) -> dict[str, Any]:
    kind = classify_workflow(payload)
    return {
        "name": filename,
        "kind": kind,
        "source": source,
        "submit_ready": kind == "api" and validation_status in {"valid", "unknown"},
        "validation_status": validation_status,
    }


def save_workflow_metadata(
    workflows_dir: Path,
    filename: str,
    metadata: dict[str, Any],
) -> Path:
    metadata_dir = ensure_directory(workflows_dir / ".metadata")
    path = safe_json_path(metadata_dir, workflow_metadata_filename(filename))
    path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return path


def read_workflow_metadata(
    workflows_dir: Path,
    filename: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    path = workflows_dir / ".metadata" / workflow_metadata_filename(filename)
    if not path.exists():
        return workflow_metadata(filename, payload)
    saved = json.loads(path.read_text(encoding="utf-8"))
    default = workflow_metadata(filename, payload)
    return default | {
        key: saved[key]
        for key in ("source", "validation_status", "submit_ready")
        if key in saved
    }
```

Extend `save_workflow()` with keyword-only `source: str = "manual"` and `validation_status: str = "unknown"`, then call `save_workflow_metadata()` after writing the workflow JSON. Add `"metadata": read_workflow_metadata(workflows_dir, filename, payload)` to the dictionary returned by `read_workflow()`.

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_ui_workflows.py tests/test_workflows.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/comfydex_mcp/ui_workflows.py src/comfydex_mcp/workflows.py tests/test_ui_workflows.py tests/test_workflows.py
git commit -m "feat: classify ui workflows with metadata"
```

### Task 1.2: Import UI Workflows

**Files:**

- Modify: `src/comfydex_mcp/ui_workflows.py`
- Modify: `src/comfydex_mcp/server.py`
- Test: `tests/test_ui_workflows.py`
- Test: `tests/test_server_tools.py`

- [ ] **Step 1: Write import tests**

Append these tests to `tests/test_ui_workflows.py`:

```python
from pathlib import Path

from comfydex_mcp.ui_workflows import import_ui_workflow


UI_WORKFLOW = {
    "last_node_id": 2,
    "nodes": [{"id": 1, "type": "CheckpointLoaderSimple"}, {"id": 2, "type": "SaveImage"}],
    "links": [],
}


def test_import_ui_workflow_saves_original_json(tmp_path: Path):
    result = import_ui_workflow(tmp_path, "sample.ui.json", UI_WORKFLOW, object_info={})

    assert result["name"] == "sample.ui.json"
    assert result["metadata"]["kind"] == "ui"
    assert result["metadata"]["source"] == "imported"
    assert (tmp_path / "sample.ui.json").exists()


def test_import_ui_workflow_rejects_api_payload(tmp_path: Path):
    api = {"1": {"class_type": "SaveImage", "inputs": {}}}
    try:
        import_ui_workflow(tmp_path, "bad.ui.json", api)
    except ValueError as exc:
        assert "requires ComfyUI UI workflow JSON" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

Append this server tool test:

```python
@pytest.mark.asyncio
async def test_comfy_import_ui_workflow_tool(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    result = await server.comfy_import_ui_workflow(
        "sample.ui.json",
        {"nodes": [{"id": 1, "type": "SaveImage"}], "links": []},
        use_object_info=False,
    )

    assert result["metadata"]["kind"] == "ui"
    assert (tmp_path / "workflows" / "sample.ui.json").exists()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_ui_workflows.py::test_import_ui_workflow_saves_original_json tests/test_server_tools.py::test_comfy_import_ui_workflow_tool -q
```

Expected: fail because import function and MCP tool are not present.

- [ ] **Step 3: Implement import function**

Add to `src/comfydex_mcp/ui_workflows.py`:

```python
from pathlib import Path

from .workflows import read_workflow, save_workflow


def import_ui_workflow(
    workflows_dir: Path,
    filename: str,
    payload: dict[str, Any],
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    classification = classify_workflow_payload(payload)
    if classification["kind"] != "ui":
        raise ValueError("comfy_import_ui_workflow requires ComfyUI UI workflow JSON")

    target = save_workflow(
        workflows_dir,
        filename,
        payload,
        source="imported",
        validation_status="unknown",
    )
    loaded = read_workflow(workflows_dir, filename)
    readiness = summarize_import_readiness(payload, object_info)
    return {
        "name": filename,
        "path": str(target),
        "metadata": loaded["metadata"],
        "classification": classification,
        "readiness": readiness,
    }
```

- [ ] **Step 4: Wire MCP tools**

Modify `src/comfydex_mcp/server.py` imports:

```python
from .ui_workflows import classify_workflow_payload, import_ui_workflow
```

Add tools:

```python
@mcp.tool()
async def comfy_classify_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    return classify_workflow_payload(workflow)


@mcp.tool()
async def comfy_import_ui_workflow(
    name: str,
    workflow: dict[str, Any],
    use_object_info: bool = True,
) -> dict[str, Any]:
    ctx = tool_context()
    object_info = None
    if use_object_info:
        async with ComfyClient(
            ctx.config.base_url,
            ctx.config.headers,
            ctx.config.request_timeout_seconds,
        ) as client:
            object_info = await client.get_object_info()
    return import_ui_workflow(ctx.config.workflows_dir, name, workflow, object_info)
```

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_ui_workflows.py tests/test_server_tools.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/comfydex_mcp/ui_workflows.py src/comfydex_mcp/server.py tests/test_ui_workflows.py tests/test_server_tools.py
git commit -m "feat: import ui workflows"
```

### Task 1.3: API Workflow Validation

**Files:**

- Create: `src/comfydex_mcp/validation.py`
- Modify: `src/comfydex_mcp/server.py`
- Test: `tests/test_validation.py`
- Test: `tests/test_server_tools.py`

- [ ] **Step 1: Write validation tests**

Create `tests/test_validation.py`:

```python
from comfydex_mcp.validation import validate_api_workflow


OBJECT_INFO = {
    "SaveImage": {"input": {"required": {"images": ("IMAGE",)}}},
    "KSampler": {"input": {"required": {"model": ("MODEL",), "seed": ("INT",)}}},
}


def test_validate_api_workflow_passes_valid_links():
    workflow = {
        "1": {"class_type": "KSampler", "inputs": {"model": ["2", 0], "seed": 1}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }

    result = validate_api_workflow(workflow, OBJECT_INFO)

    assert result["status"] == "valid"
    assert result["errors"] == []


def test_validate_api_workflow_reports_missing_node_type():
    result = validate_api_workflow(
        {"1": {"class_type": "MissingNode", "inputs": {}}},
        OBJECT_INFO,
    )

    assert result["status"] == "invalid"
    assert result["errors"][0]["reason"] == "missing_object_info"


def test_validate_api_workflow_reports_missing_required_input():
    result = validate_api_workflow(
        {"1": {"class_type": "SaveImage", "inputs": {}}},
        OBJECT_INFO,
    )

    assert result["status"] == "invalid"
    assert result["errors"][0]["input"] == "images"


def test_validate_api_workflow_reports_broken_link_reference():
    result = validate_api_workflow(
        {"1": {"class_type": "SaveImage", "inputs": {"images": ["99", 0]}}},
        OBJECT_INFO,
    )

    assert result["status"] == "invalid"
    assert result["errors"][0]["reason"] == "broken_link"
```

Add server test:

```python
@pytest.mark.asyncio
async def test_comfy_validate_api_workflow_tool(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(tmp_path / "workflows", "wf.json", API_WORKFLOW)

    class ObjectInfoClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def get_object_info(self):
            return {"SaveImage": {"input": {"required": {}}}}

    monkeypatch.setattr(server, "ComfyClient", ObjectInfoClient)
    result = await server.comfy_validate_api_workflow("wf.json")
    assert result["status"] == "valid"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_validation.py -q
```

Expected: fail because validation module is not present.

- [ ] **Step 3: Implement validation module**

Create `src/comfydex_mcp/validation.py`:

```python
from __future__ import annotations

from typing import Any


def _required_inputs(node_info: dict[str, Any]) -> list[str]:
    input_info = node_info.get("input", {})
    required = input_info.get("required", {})
    if isinstance(required, dict):
        return list(required.keys())
    return []


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


def validate_api_workflow(workflow: dict[str, Any], object_info: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not isinstance(workflow, dict) or not workflow:
        return {"status": "invalid", "errors": [{"reason": "empty_or_non_object_workflow"}], "warnings": warnings}

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            errors.append({"node_id": str(node_id), "reason": "node_not_object"})
            continue
        node_type = node.get("class_type")
        if not isinstance(node_type, str):
            errors.append({"node_id": str(node_id), "reason": "missing_class_type"})
            continue
        node_info = object_info.get(node_type)
        if not isinstance(node_info, dict):
            errors.append({"node_id": str(node_id), "node_type": node_type, "reason": "missing_object_info"})
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            errors.append({"node_id": str(node_id), "node_type": node_type, "reason": "inputs_not_object"})
            continue
        for input_name in _required_inputs(node_info):
            if input_name not in inputs:
                errors.append({
                    "node_id": str(node_id),
                    "node_type": node_type,
                    "input": input_name,
                    "reason": "missing_required_input",
                })
        for input_name, value in inputs.items():
            if _is_link(value) and value[0] not in workflow:
                errors.append({
                    "node_id": str(node_id),
                    "node_type": node_type,
                    "input": input_name,
                    "reason": "broken_link",
                    "target_node_id": value[0],
                })

    output_nodes = [
        node_id
        for node_id, node in workflow.items()
        if isinstance(node, dict) and str(node.get("class_type", "")).lower() in {"saveimage", "previewimage", "saveaudio"}
    ]
    if not output_nodes:
        warnings.append({"reason": "no_probable_output_node"})

    return {
        "status": "invalid" if errors else "valid",
        "errors": errors,
        "warnings": warnings,
        "nodes_checked": len(workflow),
    }
```

- [ ] **Step 4: Wire MCP tool**

Modify `src/comfydex_mcp/server.py`:

```python
from .validation import validate_api_workflow
```

Add:

```python
@mcp.tool()
async def comfy_validate_api_workflow(name: str) -> dict[str, Any]:
    ctx = tool_context()
    loaded = read_workflow(ctx.config.workflows_dir, name)
    if loaded["kind"] != "api":
        raise ValueError("comfy_validate_api_workflow requires ComfyUI API prompt JSON")
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        object_info = await client.get_object_info()
    return validate_api_workflow(loaded["json"], object_info)
```

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_validation.py tests/test_server_tools.py::test_comfy_validate_api_workflow_tool -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/comfydex_mcp/validation.py src/comfydex_mcp/server.py tests/test_validation.py tests/test_server_tools.py
git commit -m "feat: validate api workflows"
```

### Task 1.4: Conservative UI-To-API Conversion

**Files:**

- Create: `src/comfydex_mcp/conversion.py`
- Modify: `src/comfydex_mcp/server.py`
- Test: `tests/test_conversion.py`
- Test: `tests/test_server_tools.py`

- [ ] **Step 1: Write conversion tests**

Create `tests/test_conversion.py`:

```python
from pathlib import Path

from comfydex_mcp.conversion import convert_ui_to_api, explain_conversion_gaps, save_conversion_report


OBJECT_INFO = {
    "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": ("STRING",)}}},
    "SaveImage": {"input": {"required": {"images": ("IMAGE",)}, "optional": {"filename_prefix": ("STRING",)}}},
}


def test_convert_ui_to_api_maps_widgets_and_links():
    ui = {
        "nodes": [
            {"id": 1, "type": "CheckpointLoaderSimple", "widgets_values": ["model.safetensors"]},
            {"id": 2, "type": "SaveImage", "widgets_values": ["ComfyUI"]},
        ],
        "links": [[7, 1, 0, 2, 0, "IMAGE"]],
    }

    result = convert_ui_to_api(ui, OBJECT_INFO, "sample.ui.json", "sample.api.json")

    assert result["report"]["status"] == "converted"
    assert result["workflow"]["1"]["inputs"]["ckpt_name"] == "model.safetensors"
    assert result["workflow"]["2"]["inputs"]["images"] == ["1", 0]


def test_convert_ui_to_api_reports_missing_object_info_without_fake_workflow():
    ui = {"nodes": [{"id": 1, "type": "CustomNode"}], "links": []}

    result = convert_ui_to_api(ui, OBJECT_INFO, "bad.ui.json", "bad.api.json")

    assert result["workflow"] is None
    assert result["report"]["status"] == "failed"
    assert result["report"]["gaps"][0]["reason"] == "missing_object_info"


def test_save_conversion_report_writes_reports_directory(tmp_path: Path):
    report = {"source_workflow": "a.ui.json", "target_workflow": "a.api.json", "status": "failed", "gaps": []}
    path = save_conversion_report(tmp_path, "a.ui.json", report)

    assert path == tmp_path / ".reports" / "a.ui.conversion.json"
    assert path.exists()


def test_explain_conversion_gaps_returns_text_and_gaps():
    report = {
        "status": "partial",
        "gaps": [{"node_id": "7", "node_type": "CustomNode", "reason": "missing_object_info"}],
    }

    result = explain_conversion_gaps(report)

    assert result["gap_count"] == 1
    assert "CustomNode" in result["summary"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_conversion.py -q
```

Expected: fail because conversion module is not present.

- [ ] **Step 3: Implement conversion module**

Create `src/comfydex_mcp/conversion.py` with these public functions:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import ensure_directory, safe_json_path
from .validation import validate_api_workflow


def _input_names(node_type: str, object_info: dict[str, Any]) -> list[str]:
    node_info = object_info.get(node_type, {})
    input_info = node_info.get("input", {})
    names: list[str] = []
    for group in ("required", "optional"):
        values = input_info.get(group, {})
        if isinstance(values, dict):
            names.extend(values.keys())
    return names


def _incoming_links(ui_workflow: dict[str, Any]) -> dict[tuple[str, int], list[Any]]:
    incoming: dict[tuple[str, int], list[Any]] = {}
    for link in ui_workflow.get("links", []):
        if isinstance(link, list) and len(link) >= 5:
            incoming[(str(link[3]), int(link[4]))] = link
    return incoming


def convert_ui_to_api(
    ui_workflow: dict[str, Any],
    object_info: dict[str, Any],
    source_workflow: str,
    target_workflow: str,
) -> dict[str, Any]:
    gaps: list[dict[str, Any]] = []
    workflow: dict[str, Any] = {}
    incoming = _incoming_links(ui_workflow)

    for node in ui_workflow.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id"))
        node_type = str(node.get("type", ""))
        if node_type not in object_info:
            gaps.append({"node_id": node_id, "node_type": node_type, "reason": "missing_object_info"})
            continue

        input_names = _input_names(node_type, object_info)
        widgets = list(node.get("widgets_values", [])) if isinstance(node.get("widgets_values", []), list) else []
        inputs: dict[str, Any] = {}
        widget_index = 0
        for slot, input_name in enumerate(input_names):
            link = incoming.get((node_id, slot))
            if link:
                inputs[input_name] = [str(link[1]), int(link[2])]
            elif widget_index < len(widgets):
                inputs[input_name] = widgets[widget_index]
                widget_index += 1
        workflow[node_id] = {"class_type": node_type, "inputs": inputs}

    validation = validate_api_workflow(workflow, object_info) if workflow else {"status": "invalid", "errors": []}
    status = "converted" if not gaps and validation["status"] == "valid" else "partial" if workflow else "failed"
    if validation["status"] == "invalid":
        for error in validation.get("errors", []):
            gaps.append({"node_id": error.get("node_id"), "node_type": error.get("node_type"), "reason": error.get("reason"), "details": error})
        status = "failed" if not workflow else "partial"

    report = {
        "source_workflow": source_workflow,
        "target_workflow": target_workflow,
        "status": status,
        "nodes_total": len([node for node in ui_workflow.get("nodes", []) if isinstance(node, dict)]),
        "nodes_converted": len(workflow),
        "nodes_failed": len(gaps),
        "gaps": gaps,
        "validation": validation,
    }
    return {"workflow": workflow if status == "converted" else None, "draft_workflow": workflow, "report": report}


def save_conversion_report(workflows_dir: Path, source_name: str, report: dict[str, Any]) -> Path:
    reports_dir = ensure_directory(workflows_dir / ".reports")
    stem = source_name[:-5] if source_name.endswith(".json") else source_name
    path = safe_json_path(reports_dir, f"{stem}.conversion.json")
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def explain_conversion_gaps(report: dict[str, Any]) -> dict[str, Any]:
    gaps = report.get("gaps", [])
    if not gaps:
        return {"gap_count": 0, "summary": "No conversion gaps were reported.", "gaps": []}
    parts = [
        f"Node {gap.get('node_id')} ({gap.get('node_type')}) failed because {gap.get('reason')}."
        for gap in gaps
    ]
    return {"gap_count": len(gaps), "summary": " ".join(parts), "gaps": gaps}
```

- [ ] **Step 4: Wire conversion MCP tools**

Modify `src/comfydex_mcp/server.py`:

```python
from .conversion import convert_ui_to_api, explain_conversion_gaps, save_conversion_report
```

Add:

```python
@mcp.tool()
async def comfy_convert_ui_to_api(
    source_name: str,
    target_name: str,
    allow_draft: bool = False,
) -> dict[str, Any]:
    ctx = tool_context()
    loaded = read_workflow(ctx.config.workflows_dir, source_name)
    if loaded["kind"] != "ui":
        raise ValueError("comfy_convert_ui_to_api requires ComfyUI UI workflow JSON")
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        object_info = await client.get_object_info()
    result = convert_ui_to_api(loaded["json"], object_info, source_name, target_name)
    report_path = save_conversion_report(ctx.config.workflows_dir, source_name, result["report"])
    if result["workflow"] is not None:
        save_workflow(
            ctx.config.workflows_dir,
            target_name,
            result["workflow"],
            require_api=True,
            source="converted",
            validation_status="valid",
        )
    elif allow_draft and result["draft_workflow"]:
        draft_name = target_name if target_name.endswith(".draft.json") else target_name.replace(".json", ".draft.json")
        save_workflow(
            ctx.config.workflows_dir,
            draft_name,
            result["draft_workflow"],
            require_api=False,
            source="converted",
            validation_status=result["report"]["status"],
        )
        result["draft_name"] = draft_name
    return result | {"report_path": str(report_path)}


@mcp.tool()
async def comfy_explain_conversion_gaps(source_name: str) -> dict[str, Any]:
    ctx = tool_context()
    stem = source_name[:-5] if source_name.endswith(".json") else source_name
    report = read_workflow(ctx.config.workflows_dir / ".reports", f"{stem}.conversion.json")["json"]
    return explain_conversion_gaps(report)
```

Add server tests for successful conversion and failed conversion:

```python
@pytest.mark.asyncio
async def test_comfy_convert_ui_to_api_writes_api_when_valid(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(
        tmp_path / "workflows",
        "sample.ui.json",
        {"nodes": [{"id": 1, "type": "SaveImage", "widgets_values": []}], "links": []},
    )

    class ObjectInfoClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        async def get_object_info(self):
            return {"SaveImage": {"input": {"required": {}}}}

    monkeypatch.setattr(server, "ComfyClient", ObjectInfoClient)
    result = await server.comfy_convert_ui_to_api("sample.ui.json", "sample.api.json")
    assert result["report"]["status"] == "converted"
    assert (tmp_path / "workflows" / "sample.api.json").exists()
```

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_conversion.py tests/test_validation.py tests/test_server_tools.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/comfydex_mcp/conversion.py src/comfydex_mcp/server.py tests/test_conversion.py tests/test_server_tools.py
git commit -m "feat: convert ui workflows conservatively"
```

### Milestone 1 Gate

Run:

```powershell
python -m pytest tests/test_ui_workflows.py tests/test_conversion.py tests/test_validation.py tests/test_workflows.py tests/test_server_tools.py -q
python -m pytest -q
python scripts/validate_plugin.py
```

Run the spec compliance review and code quality review using the prompts in the review gate section. Resolve Critical and Important findings, rerun the commands, then proceed to milestone 2.

## Milestone 2: Workflow Builder And Templates

### Task 2.1: Template Catalog

**Files:**

- Create: `src/comfydex_mcp/templates.py`
- Test: `tests/test_templates.py`

- [ ] **Step 1: Write template tests**

Create `tests/test_templates.py`:

```python
from comfydex_mcp.templates import list_workflow_templates, suggest_workflow_template


def test_list_workflow_templates_includes_required_templates():
    names = {template["name"] for template in list_workflow_templates()}
    assert {
        "basic-text-to-image",
        "basic-image-to-image",
        "upscale",
        "sdxl-text-to-image",
        "lora-text-to-image",
        "controlnet-skeleton",
    }.issubset(names)


def test_suggest_workflow_template_prefers_sdxl_lora():
    result = suggest_workflow_template("Create an SDXL text to image workflow with a LoRA")
    assert result["name"] == "lora-text-to-image"
    assert "lora" in result["matched_terms"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_templates.py -q
```

Expected: fail because `templates.py` is not present.

- [ ] **Step 3: Implement template catalog**

Create `src/comfydex_mcp/templates.py` with dataclass-backed templates:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NodeRecipe:
    key: str
    class_type: str
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LinkRecipe:
    source: str
    source_slot: int
    target: str
    input_name: str


@dataclass(frozen=True)
class WorkflowTemplate:
    name: str
    description: str
    tags: tuple[str, ...]
    required_parameters: tuple[str, ...]
    optional_parameters: dict[str, Any]
    nodes: tuple[NodeRecipe, ...]
    links: tuple[LinkRecipe, ...]


TEMPLATES: tuple[WorkflowTemplate, ...] = (
    WorkflowTemplate(
        name="basic-text-to-image",
        description="Checkpoint, text encoders, sampler, VAE decode, SaveImage.",
        tags=("text", "text-to-image", "txt2img"),
        required_parameters=("checkpoint_name", "positive_prompt"),
        optional_parameters={"negative_prompt": "", "width": 512, "height": 512, "steps": 20, "seed": 1},
        nodes=(
            NodeRecipe("checkpoint", "CheckpointLoaderSimple", {"ckpt_name": "$checkpoint_name"}),
            NodeRecipe("positive", "CLIPTextEncode", {"text": "$positive_prompt"}),
            NodeRecipe("negative", "CLIPTextEncode", {"text": "$negative_prompt"}),
            NodeRecipe("latent", "EmptyLatentImage", {"width": "$width", "height": "$height", "batch_size": 1}),
            NodeRecipe("sampler", "KSampler", {"seed": "$seed", "steps": "$steps"}),
            NodeRecipe("decode", "VAEDecode", {}),
            NodeRecipe("save", "SaveImage", {"filename_prefix": "Comfydex"}),
        ),
        links=(
            LinkRecipe("checkpoint", 0, "sampler", "model"),
            LinkRecipe("positive", 0, "sampler", "positive"),
            LinkRecipe("negative", 0, "sampler", "negative"),
            LinkRecipe("latent", 0, "sampler", "latent_image"),
            LinkRecipe("sampler", 0, "decode", "samples"),
            LinkRecipe("checkpoint", 2, "decode", "vae"),
            LinkRecipe("decode", 0, "save", "images"),
        ),
    ),
)
```

Add the remaining five templates with concrete names, tags, required parameters, and node/link recipes using ComfyUI common node types:

- `basic-image-to-image`: `LoadImage`, `VAEEncode`, `KSampler`, `VAEDecode`, `SaveImage`.
- `upscale`: `LoadImage`, `UpscaleModelLoader`, `ImageUpscaleWithModel`, `SaveImage`.
- `sdxl-text-to-image`: `CheckpointLoaderSimple`, two `CLIPTextEncodeSDXL` nodes, `EmptyLatentImage`, `KSampler`, `VAEDecode`, `SaveImage`.
- `lora-text-to-image`: `CheckpointLoaderSimple`, `LoraLoader`, two `CLIPTextEncode` nodes, `EmptyLatentImage`, `KSampler`, `VAEDecode`, `SaveImage`.
- `controlnet-skeleton`: `LoadImage`, `ControlNetLoader`, `ControlNetApply`, `CheckpointLoaderSimple`, `CLIPTextEncode`, `KSampler`, `VAEDecode`, `SaveImage`.

Expose:

```python
def list_workflow_templates() -> list[dict[str, Any]]:
    return [
        {
            "name": template.name,
            "description": template.description,
            "tags": list(template.tags),
            "required_parameters": list(template.required_parameters),
            "optional_parameters": template.optional_parameters,
        }
        for template in TEMPLATES
    ]


def get_workflow_template(name: str) -> WorkflowTemplate:
    for template in TEMPLATES:
        if template.name == name:
            return template
    raise ValueError(f"unknown workflow template: {name}")


def suggest_workflow_template(intent: str) -> dict[str, Any]:
    lowered = intent.lower()
    scored = []
    for template in TEMPLATES:
        matched = [tag for tag in template.tags if tag in lowered]
        score = len(matched)
        if "lora" in lowered and "lora" in template.tags:
            score += 3
        if "sdxl" in lowered and "sdxl" in template.tags:
            score += 2
        scored.append((score, template, matched))
    score, template, matched = max(scored, key=lambda item: item[0])
    return {"name": template.name, "score": score, "matched_terms": matched, "template": list_workflow_templates()[TEMPLATES.index(template)]}
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_templates.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comfydex_mcp/templates.py tests/test_templates.py
git commit -m "feat: add workflow template catalog"
```

### Task 2.2: Build Plans

**Files:**

- Create: `src/comfydex_mcp/builder.py`
- Test: `tests/test_builder.py`

- [ ] **Step 1: Write build plan tests**

Create `tests/test_builder.py`:

```python
from comfydex_mcp.builder import build_workflow_plan


def test_build_workflow_plan_reports_missing_information():
    result = build_workflow_plan(
        "Create a text to image workflow",
        parameters={"width": 768},
        object_info={"CheckpointLoaderSimple": {}, "KSampler": {}, "SaveImage": {}},
    )

    assert result["template"] == "basic-text-to-image"
    assert "checkpoint_name" in result["missing_information"]
    assert "positive_prompt" in result["missing_information"]
    assert result["parameters"]["width"] == 768


def test_build_workflow_plan_reports_unavailable_nodes():
    result = build_workflow_plan(
        "Create an upscale workflow",
        parameters={"image": "input.png"},
        object_info={"LoadImage": {}},
    )

    assert result["template"] == "upscale"
    assert "UpscaleModelLoader" in result["unavailable_node_types"]


def test_save_build_plan_writes_only_when_called(tmp_path):
    from comfydex_mcp.builder import save_build_plan

    plan = {"intent": "Create text to image", "template": "basic-text-to-image"}

    path = save_build_plan(tmp_path, "text2img.plan.json", plan)

    assert path == tmp_path / ".plans" / "text2img.plan.json"
    assert path.exists()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_builder.py::test_build_workflow_plan_reports_missing_information -q
```

Expected: fail because `builder.py` is not present.

- [ ] **Step 3: Implement build plan generation**

Create `src/comfydex_mcp/builder.py`:

```python
from __future__ import annotations

from typing import Any

import json
from pathlib import Path

from .paths import ensure_directory, safe_json_path
from .templates import get_workflow_template, suggest_workflow_template


def build_workflow_plan(
    intent: str,
    parameters: dict[str, Any] | None = None,
    object_info: dict[str, Any] | None = None,
    template_name: str | None = None,
) -> dict[str, Any]:
    selected = get_workflow_template(template_name) if template_name else get_workflow_template(suggest_workflow_template(intent)["name"])
    supplied = parameters or {}
    merged = dict(selected.optional_parameters)
    merged.update(supplied)
    missing = [name for name in selected.required_parameters if name not in supplied or supplied[name] in (None, "")]
    required_nodes = sorted({node.class_type for node in selected.nodes})
    unavailable = sorted(node_type for node_type in required_nodes if object_info is not None and node_type not in object_info)
    assumptions = [
        f"{name} defaults to {value!r}."
        for name, value in selected.optional_parameters.items()
        if name not in supplied
    ]
    return {
        "intent": intent,
        "template": selected.name,
        "required_nodes": required_nodes,
        "parameters": merged,
        "assumptions": assumptions,
        "missing_information": missing,
        "unavailable_node_types": unavailable,
        "submit_ready": not missing and not unavailable,
    }


def save_build_plan(workflows_dir: Path, filename: str, plan: dict[str, Any]) -> Path:
    plans_dir = ensure_directory(workflows_dir / ".plans")
    path = safe_json_path(plans_dir, filename)
    path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return path
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_builder.py::test_build_workflow_plan_reports_missing_information tests/test_builder.py::test_build_workflow_plan_reports_unavailable_nodes -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comfydex_mcp/builder.py tests/test_builder.py
git commit -m "feat: build workflow plans"
```

### Task 2.3: Build API Workflows From Templates

**Files:**

- Modify: `src/comfydex_mcp/builder.py`
- Test: `tests/test_builder.py`

- [ ] **Step 1: Add workflow generation tests**

Append:

```python
from comfydex_mcp.builder import build_workflow


OBJECT_INFO_BASIC = {
    "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": ("STRING",)}}},
    "CLIPTextEncode": {"input": {"required": {"text": ("STRING",), "clip": ("CLIP",)}}},
    "EmptyLatentImage": {"input": {"required": {"width": ("INT",), "height": ("INT",), "batch_size": ("INT",)}}},
    "KSampler": {"input": {"required": {"model": ("MODEL",), "positive": ("CONDITIONING",), "negative": ("CONDITIONING",), "latent_image": ("LATENT",), "seed": ("INT",), "steps": ("INT",)}}},
    "VAEDecode": {"input": {"required": {"samples": ("LATENT",), "vae": ("VAE",)}}},
    "SaveImage": {"input": {"required": {"images": ("IMAGE",)}}},
}


def test_build_workflow_creates_valid_text_to_image_workflow():
    result = build_workflow(
        intent="Create text to image",
        parameters={"checkpoint_name": "model.safetensors", "positive_prompt": "a city"},
        object_info=OBJECT_INFO_BASIC,
        template_name="basic-text-to-image",
    )

    assert result["validation"]["status"] == "valid"
    assert result["metadata"]["submit_ready"] is True
    assert any(node["class_type"] == "SaveImage" for node in result["workflow"].values())


def test_build_workflow_refuses_submit_ready_when_information_missing():
    result = build_workflow(
        intent="Create text to image",
        parameters={"checkpoint_name": "model.safetensors"},
        object_info=OBJECT_INFO_BASIC,
        template_name="basic-text-to-image",
    )

    assert result["workflow"] is None
    assert result["plan"]["submit_ready"] is False
    assert "positive_prompt" in result["plan"]["missing_information"]


OBJECT_INFO_IMAGE_TO_IMAGE = OBJECT_INFO_BASIC | {
    "LoadImage": {"input": {"required": {"image": ("STRING",)}}},
    "VAEEncode": {"input": {"required": {"pixels": ("IMAGE",), "vae": ("VAE",)}}},
}


def test_build_workflow_creates_valid_image_to_image_workflow():
    result = build_workflow(
        intent="Create image to image",
        parameters={
            "checkpoint_name": "model.safetensors",
            "positive_prompt": "a restored portrait",
            "image": "input.png",
        },
        object_info=OBJECT_INFO_IMAGE_TO_IMAGE,
        template_name="basic-image-to-image",
    )

    assert result["validation"]["status"] == "valid"
    assert result["metadata"]["submit_ready"] is True
    assert any(node["class_type"] == "LoadImage" for node in result["workflow"].values())
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_builder.py::test_build_workflow_creates_valid_text_to_image_workflow tests/test_builder.py::test_build_workflow_refuses_submit_ready_when_information_missing -q
```

Expected: fail because `build_workflow()` is not present.

- [ ] **Step 3: Implement workflow generation**

Add to `src/comfydex_mcp/builder.py`:

```python
from .validation import validate_api_workflow


def _resolve_value(value: Any, parameters: dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        return parameters[value[1:]]
    return value


def build_workflow(
    intent: str,
    parameters: dict[str, Any],
    object_info: dict[str, Any],
    template_name: str | None = None,
    allow_draft: bool = False,
) -> dict[str, Any]:
    plan = build_workflow_plan(intent, parameters, object_info, template_name)
    if not plan["submit_ready"] and not allow_draft:
        return {"workflow": None, "plan": plan, "validation": {"status": "invalid", "errors": []}, "metadata": {"submit_ready": False}}

    template = get_workflow_template(plan["template"])
    key_to_id = {node.key: str(index) for index, node in enumerate(template.nodes, start=1)}
    workflow: dict[str, Any] = {}
    for node in template.nodes:
        workflow[key_to_id[node.key]] = {
            "class_type": node.class_type,
            "inputs": {name: _resolve_value(value, plan["parameters"]) for name, value in node.inputs.items()},
        }
    for link in template.links:
        target_id = key_to_id[link.target]
        workflow[target_id]["inputs"][link.input_name] = [key_to_id[link.source], link.source_slot]

    validation = validate_api_workflow(workflow, object_info)
    submit_ready = plan["submit_ready"] and validation["status"] == "valid"
    return {
        "workflow": workflow if submit_ready or allow_draft else None,
        "plan": plan,
        "validation": validation,
        "metadata": {
            "kind": "api",
            "source": "generated",
            "submit_ready": submit_ready,
            "validation_status": validation["status"],
        },
    }
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_builder.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comfydex_mcp/builder.py tests/test_builder.py
git commit -m "feat: build api workflows from templates"
```

### Task 2.4: Workflow Patching

**Files:**

- Create: `src/comfydex_mcp/patching.py`
- Test: `tests/test_patching.py`

- [ ] **Step 1: Write patching tests**

Create `tests/test_patching.py`:

```python
from comfydex_mcp.patching import patch_workflow


def test_patch_workflow_sets_input_and_preserves_unrelated_nodes():
    workflow = {
        "1": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 20}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }

    result = patch_workflow(workflow, [{"op": "set_input", "node_id": "1", "input": "seed", "value": 42}])

    assert result["workflow"]["1"]["inputs"]["seed"] == 42
    assert result["workflow"]["2"] == workflow["2"]
    assert result["report"]["changes"][0]["old_value"] == 1


def test_patch_workflow_reports_missing_node_without_mutating_original():
    workflow = {"1": {"class_type": "SaveImage", "inputs": {}}}

    result = patch_workflow(workflow, [{"op": "set_input", "node_id": "99", "input": "seed", "value": 42}])

    assert result["workflow"] == workflow
    assert result["report"]["status"] == "failed"
    assert result["report"]["errors"][0]["reason"] == "missing_node"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_patching.py -q
```

Expected: fail because `patching.py` is not present.

- [ ] **Step 3: Implement patching module**

Create `src/comfydex_mcp/patching.py`:

```python
from __future__ import annotations

import copy
from typing import Any


def patch_workflow(workflow: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    patched = copy.deepcopy(workflow)
    changes: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for operation in operations:
        op = operation.get("op")
        node_id = str(operation.get("node_id"))
        if node_id not in patched:
            errors.append({"op": op, "node_id": node_id, "reason": "missing_node"})
            continue
        if op == "set_input":
            input_name = str(operation.get("input"))
            inputs = patched[node_id].setdefault("inputs", {})
            old_value = copy.deepcopy(inputs.get(input_name))
            inputs[input_name] = copy.deepcopy(operation.get("value"))
            changes.append({"op": op, "node_id": node_id, "input": input_name, "old_value": old_value, "new_value": operation.get("value")})
        elif op == "set_class_type":
            old_value = patched[node_id].get("class_type")
            patched[node_id]["class_type"] = str(operation.get("value"))
            changes.append({"op": op, "node_id": node_id, "old_value": old_value, "new_value": patched[node_id]["class_type"]})
        else:
            errors.append({"op": op, "node_id": node_id, "reason": "unsupported_operation"})

    return {
        "workflow": patched if not errors else workflow,
        "report": {
            "status": "failed" if errors else "patched",
            "changes": changes,
            "errors": errors,
        },
    }
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_patching.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comfydex_mcp/patching.py tests/test_patching.py
git commit -m "feat: patch workflows with reports"
```

### Task 2.5: Builder MCP Tools

**Files:**

- Modify: `src/comfydex_mcp/server.py`
- Test: `tests/test_server_tools.py`

- [ ] **Step 1: Write server tests for builder tools**

Append:

```python
@pytest.mark.asyncio
async def test_comfy_list_workflow_templates_tool():
    result = await server.comfy_list_workflow_templates()
    assert any(template["name"] == "basic-text-to-image" for template in result)


@pytest.mark.asyncio
async def test_comfy_build_workflow_plan_tool(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))

    class ObjectInfoClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        async def get_object_info(self):
            return {"CheckpointLoaderSimple": {}, "KSampler": {}, "SaveImage": {}}

    monkeypatch.setattr(server, "ComfyClient", ObjectInfoClient)
    result = await server.comfy_build_workflow_plan("Create text to image", {"width": 512})
    assert result["template"] == "basic-text-to-image"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_server_tools.py::test_comfy_list_workflow_templates_tool tests/test_server_tools.py::test_comfy_build_workflow_plan_tool -q
```

Expected: fail because MCP tools are not present.

- [ ] **Step 3: Wire server tools**

Modify imports:

```python
from .builder import build_workflow, build_workflow_plan, save_build_plan
from .patching import patch_workflow
from .templates import list_workflow_templates, suggest_workflow_template
```

Add tools:

```python
@mcp.tool()
async def comfy_list_workflow_templates() -> list[dict[str, Any]]:
    return list_workflow_templates()


@mcp.tool()
async def comfy_suggest_workflow_template(intent: str) -> dict[str, Any]:
    return suggest_workflow_template(intent)


@mcp.tool()
async def comfy_build_workflow_plan(
    intent: str,
    parameters: dict[str, Any] | None = None,
    template_name: str | None = None,
    save_plan_name: str | None = None,
) -> dict[str, Any]:
    ctx = tool_context()
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        object_info = await client.get_object_info()
    plan = build_workflow_plan(intent, parameters or {}, object_info, template_name)
    if save_plan_name:
        path = save_build_plan(ctx.config.workflows_dir, save_plan_name, plan)
        plan = plan | {"plan_path": str(path)}
    return plan


@mcp.tool()
async def comfy_build_workflow(
    name: str,
    intent: str,
    parameters: dict[str, Any],
    template_name: str | None = None,
    allow_draft: bool = False,
) -> dict[str, Any]:
    ctx = tool_context()
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        object_info = await client.get_object_info()
    result = build_workflow(intent, parameters, object_info, template_name, allow_draft)
    if result["workflow"] is not None:
        save_workflow(
            ctx.config.workflows_dir,
            name,
            result["workflow"],
            require_api=result["metadata"]["submit_ready"],
            source="generated",
            validation_status=result["metadata"]["validation_status"],
        )
    return result


@mcp.tool()
async def comfy_patch_workflow(name: str, operations: list[dict[str, Any]], target_name: str | None = None) -> dict[str, Any]:
    ctx = tool_context()
    loaded = read_workflow(ctx.config.workflows_dir, name)
    result = patch_workflow(loaded["json"], operations)
    if result["report"]["status"] == "patched":
        save_workflow(ctx.config.workflows_dir, target_name or name, result["workflow"], require_api=False)
    return result


@mcp.tool()
async def comfy_validate_workflow_against_object_info(name: str) -> dict[str, Any]:
    return await comfy_validate_api_workflow(name)


@mcp.tool()
async def comfy_explain_workflow_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": f"Template {plan.get('template')} uses {len(plan.get('required_nodes', []))} node types.",
        "missing_information": plan.get("missing_information", []),
        "assumptions": plan.get("assumptions", []),
        "unavailable_node_types": plan.get("unavailable_node_types", []),
    }
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_templates.py tests/test_builder.py tests/test_patching.py tests/test_server_tools.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comfydex_mcp/server.py tests/test_server_tools.py
git commit -m "feat: expose workflow builder tools"
```

### Milestone 2 Gate

Run:

```powershell
python -m pytest tests/test_templates.py tests/test_builder.py tests/test_patching.py tests/test_server_tools.py -q
python -m pytest -q
python scripts/validate_plugin.py
```

Run the spec compliance review and code quality review using the prompts in the review gate section. Resolve Critical and Important findings, rerun the commands, then proceed to milestone 3.

## Milestone 3: Custom Node Developer Assistant

### Task 3.1: Safe Custom Node Paths And Scaffolding

**Files:**

- Modify: `src/comfydex_mcp/paths.py`
- Create: `src/comfydex_mcp/node_scaffold.py`
- Test: `tests/test_custom_node_scaffold.py`

- [ ] **Step 1: Write scaffold tests**

Create `tests/test_custom_node_scaffold.py`:

```python
from pathlib import Path

from comfydex_mcp.node_scaffold import scaffold_custom_node_package


def test_scaffold_custom_node_package_creates_workspace_local_package(tmp_path: Path):
    result = scaffold_custom_node_package(tmp_path, "simple_math")
    package_dir = tmp_path / "custom_nodes" / "simple_math"

    assert result["package_dir"] == str(package_dir)
    assert (package_dir / "__init__.py").exists()
    assert (package_dir / "nodes.py").exists()
    assert (package_dir / "README.md").exists()
    assert (package_dir / "pyproject.toml").exists()
    assert (package_dir / "tests" / "test_nodes.py").exists()


def test_scaffold_custom_node_package_rejects_path_traversal(tmp_path: Path):
    try:
        scaffold_custom_node_package(tmp_path, "../bad")
    except ValueError as exc:
        assert "package name" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_custom_node_scaffold.py -q
```

Expected: fail because scaffold module is not present.

- [ ] **Step 3: Add safe package path helper**

Modify `src/comfydex_mcp/paths.py`:

```python
import re


def safe_package_dir(base_dir: Path, package_name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", package_name or ""):
        raise ValueError("package name must contain only letters, numbers, underscores, and hyphens")
    base = base_dir.resolve()
    target = (base / package_name).resolve()
    if not _is_relative_to(target, base):
        raise ValueError("package path must stay inside base directory")
    return target
```

- [ ] **Step 4: Implement scaffolding**

Create `src/comfydex_mcp/node_scaffold.py`:

```python
from __future__ import annotations

from pathlib import Path

from .paths import ensure_directory, safe_package_dir


def scaffold_custom_node_package(workspace: Path, package_name: str) -> dict[str, object]:
    custom_nodes_dir = ensure_directory(workspace / "custom_nodes")
    package_dir = safe_package_dir(custom_nodes_dir, package_name)
    ensure_directory(package_dir)
    ensure_directory(package_dir / "tests")

    class_name = "".join(part.capitalize() for part in package_name.replace("-", "_").split("_")) + "Node"
    mapping_key = class_name

    (package_dir / "__init__.py").write_text(
        "from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS\n"
        "__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']\n",
        encoding="utf-8",
    )
    (package_dir / "nodes.py").write_text(
        f"class {class_name}:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {'a': ('INT', {'default': 1}), 'b': ('INT', {'default': 1})}}\n\n"
        "    def run(self, a, b):\n"
        "        return (a + b,)\n\n\n"
        f"NODE_CLASS_MAPPINGS = {{{mapping_key!r}: {class_name}}}\n"
        f"NODE_DISPLAY_NAME_MAPPINGS = {{{mapping_key!r}: '{class_name}'}}\n",
        encoding="utf-8",
    )
    (package_dir / "README.md").write_text(f"# {package_name}\n\nGenerated ComfyUI custom node package.\n", encoding="utf-8")
    (package_dir / "pyproject.toml").write_text("[project]\nname = \"comfydex-custom-node\"\nversion = \"0.1.0\"\n", encoding="utf-8")
    (package_dir / "tests" / "test_nodes.py").write_text(
        "from nodes import NODE_CLASS_MAPPINGS\n\n\n"
        "def test_sample_node_runs():\n"
        f"    node = NODE_CLASS_MAPPINGS[{mapping_key!r}]()\n"
        "    assert node.run(2, 3) == (5,)\n",
        encoding="utf-8",
    )

    return {"package_dir": str(package_dir), "mapping_key": mapping_key, "class_name": class_name}
```

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_custom_node_scaffold.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/comfydex_mcp/paths.py src/comfydex_mcp/node_scaffold.py tests/test_custom_node_scaffold.py
git commit -m "feat: scaffold custom node packages"
```

### Task 3.2: Inspect Packages And Validate Mappings

**Files:**

- Create: `src/comfydex_mcp/custom_nodes.py`
- Test: `tests/test_custom_nodes.py`

- [ ] **Step 1: Write inspection and mapping tests**

Create `tests/test_custom_nodes.py`:

```python
from pathlib import Path

from comfydex_mcp.custom_nodes import inspect_custom_node_package, validate_node_mappings


def _write_package(path: Path) -> None:
    path.mkdir()
    (path / "__init__.py").write_text("from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS\n", encoding="utf-8")
    (path / "nodes.py").write_text(
        "class GoodNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {'value': ('INT',)}}\n"
        "    def run(self, value):\n"
        "        return (value,)\n\n"
        "NODE_CLASS_MAPPINGS = {'GoodNode': GoodNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'GoodNode': 'Good Node'}\n",
        encoding="utf-8",
    )


def test_inspect_custom_node_package_reports_classes_and_mappings(tmp_path: Path):
    package = tmp_path / "pkg"
    _write_package(package)

    result = inspect_custom_node_package(package)

    assert "GoodNode" in result["node_classes"]
    assert result["class_mappings"] == {"GoodNode": "GoodNode"}


def test_validate_node_mappings_reports_missing_class(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text("NODE_CLASS_MAPPINGS = {'Missing': MissingClass}\n", encoding="utf-8")

    result = validate_node_mappings(package)

    assert result["status"] == "invalid"
    assert result["errors"][0]["reason"] == "missing_class"


def test_validate_node_mappings_reports_duplicate_mapping_keys(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class A: pass\n"
        "class B: pass\n"
        "NODE_CLASS_MAPPINGS = {'Node': A, 'Node': B}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'Node': 'Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_mappings(package)

    assert result["status"] == "invalid"
    assert result["errors"][0]["reason"] == "duplicate_mapping_key"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_custom_nodes.py::test_inspect_custom_node_package_reports_classes_and_mappings -q
```

Expected: fail because custom node inspection is not present.

- [ ] **Step 3: Implement AST inspection**

Create `src/comfydex_mcp/custom_nodes.py`:

```python
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any


def _nodes_py(package_dir: Path) -> Path:
    path = package_dir / "nodes.py"
    if not path.exists():
        raise ValueError(f"missing nodes.py: {path}")
    return path


def _parse_nodes(package_dir: Path) -> ast.Module:
    return ast.parse(_nodes_py(package_dir).read_text(encoding="utf-8"))


def _dict_name_mappings(tree: ast.Module, variable_name: str) -> dict[str, str]:
    mappings: dict[str, str] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            targets = [target.id for target in statement.targets if isinstance(target, ast.Name)]
            if variable_name in targets and isinstance(statement.value, ast.Dict):
                for key, value in zip(statement.value.keys, statement.value.values):
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        if isinstance(value, ast.Name):
                            mappings[key.value] = value.id
                        elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                            mappings[key.value] = value.value
    return mappings


def _duplicate_dict_keys(tree: ast.Module, variable_name: str) -> list[str]:
    duplicates: list[str] = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            targets = [target.id for target in statement.targets if isinstance(target, ast.Name)]
            if variable_name in targets and isinstance(statement.value, ast.Dict):
                seen: set[str] = set()
                for key in statement.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        if key.value in seen:
                            duplicates.append(key.value)
                        seen.add(key.value)
    return duplicates


def inspect_custom_node_package(package_dir: Path) -> dict[str, Any]:
    tree = _parse_nodes(package_dir)
    classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    return {
        "package_dir": str(package_dir),
        "node_classes": classes,
        "class_mappings": _dict_name_mappings(tree, "NODE_CLASS_MAPPINGS"),
        "display_name_mappings": _dict_name_mappings(tree, "NODE_DISPLAY_NAME_MAPPINGS"),
    }


def validate_node_mappings(package_dir: Path) -> dict[str, Any]:
    inspected = inspect_custom_node_package(package_dir)
    errors: list[dict[str, Any]] = []
    classes = set(inspected["node_classes"])
    tree = _parse_nodes(package_dir)
    for duplicate in _duplicate_dict_keys(tree, "NODE_CLASS_MAPPINGS"):
        errors.append({"mapping_key": duplicate, "reason": "duplicate_mapping_key"})
    for key, class_name in inspected["class_mappings"].items():
        if class_name not in classes:
            errors.append({"mapping_key": key, "class_name": class_name, "reason": "missing_class"})
        if key not in inspected["display_name_mappings"]:
            errors.append({"mapping_key": key, "reason": "missing_display_name"})
    return {"status": "invalid" if errors else "valid", "errors": errors, "inspection": inspected}
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_custom_nodes.py -q
```

Expected: pass for inspection and mapping cases.

- [ ] **Step 5: Commit**

```powershell
git add src/comfydex_mcp/custom_nodes.py tests/test_custom_nodes.py
git commit -m "feat: inspect custom node mappings"
```

### Task 3.3: Validate Node Classes And Isolated Imports

**Files:**

- Modify: `src/comfydex_mcp/custom_nodes.py`
- Test: `tests/test_custom_nodes.py`

- [ ] **Step 1: Add class validation and import tests**

Append:

```python
from comfydex_mcp.custom_nodes import check_node_imports, validate_node_class


def test_validate_node_class_reports_missing_input_types(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    def run(self):\n"
        "        return (1,)\n"
        "NODE_CLASS_MAPPINGS = {'BadNode': BadNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'BadNode': 'Bad Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_class(package, "BadNode")

    assert result["status"] == "invalid"
    assert any(error["reason"] == "missing_input_types" for error in result["errors"])


def test_check_node_imports_returns_import_error(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("from .nodes import NODE_CLASS_MAPPINGS\n", encoding="utf-8")
    (package / "nodes.py").write_text("import does_not_exist_here\n", encoding="utf-8")

    result = check_node_imports(package)

    assert result["status"] == "failed"
    assert "does_not_exist_here" in result["stderr"]


def test_validate_node_class_reports_missing_callable_function(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'missing_run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {}}\n"
        "NODE_CLASS_MAPPINGS = {'BadNode': BadNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'BadNode': 'Bad Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_class(package, "BadNode")

    assert result["status"] == "invalid"
    assert any(error["reason"] == "missing_callable_function" for error in result["errors"])
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_custom_nodes.py::test_validate_node_class_reports_missing_input_types tests/test_custom_nodes.py::test_check_node_imports_returns_import_error -q
```

Expected: fail because the functions are not present.

- [ ] **Step 3: Implement class validation**

Add:

```python
def _class_node(tree: ast.Module, class_name: str) -> ast.ClassDef | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def validate_node_class(package_dir: Path, class_name: str) -> dict[str, Any]:
    tree = _parse_nodes(package_dir)
    class_node = _class_node(tree, class_name)
    if class_node is None:
        return {"status": "invalid", "errors": [{"class_name": class_name, "reason": "missing_class"}]}

    errors: list[dict[str, Any]] = []
    assigned_names = {
        target.id
        for statement in class_node.body
        if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name)
    }
    method_names = {statement.name for statement in class_node.body if isinstance(statement, ast.FunctionDef)}

    if "INPUT_TYPES" not in method_names:
        errors.append({"class_name": class_name, "reason": "missing_input_types"})
    if "RETURN_TYPES" not in assigned_names:
        errors.append({"class_name": class_name, "reason": "missing_return_types"})
    if "FUNCTION" not in assigned_names:
        errors.append({"class_name": class_name, "reason": "missing_function"})
    if "CATEGORY" not in assigned_names:
        errors.append({"class_name": class_name, "reason": "missing_category"})

    function_name = None
    for statement in class_node.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id == "FUNCTION" and isinstance(statement.value, ast.Constant):
                    function_name = str(statement.value.value)
    if function_name and function_name not in method_names:
        errors.append({"class_name": class_name, "function": function_name, "reason": "missing_callable_function"})

    return {"status": "invalid" if errors else "valid", "errors": errors, "class_name": class_name}
```

- [ ] **Step 4: Implement isolated import checks**

Add:

```python
def check_node_imports(package_dir: Path, timeout_seconds: int = 5) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    script = (
        "import importlib.util, pathlib, sys\n"
        f"package_dir = pathlib.Path({str(package_dir)!r})\n"
        "sys.path.insert(0, str(package_dir.parent))\n"
        "module_name = package_dir.name\n"
        "module = __import__(module_name)\n"
        "print(getattr(module, 'NODE_CLASS_MAPPINGS', {}))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=str(package_dir.parent),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
```

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_custom_nodes.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/comfydex_mcp/custom_nodes.py tests/test_custom_nodes.py
git commit -m "feat: validate custom node classes"
```

### Task 3.4: Generate Custom Node Documentation

**Files:**

- Create: `src/comfydex_mcp/node_docs.py`
- Test: `tests/test_node_docs.py`

- [ ] **Step 1: Write documentation tests**

Create `tests/test_node_docs.py`:

```python
from pathlib import Path

from comfydex_mcp.node_docs import generate_node_docs


def test_generate_node_docs_is_deterministic(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class GoodNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {'value': ('INT',)}}\n"
        "    def run(self, value):\n"
        "        return (value,)\n"
        "NODE_CLASS_MAPPINGS = {'GoodNode': GoodNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'GoodNode': 'Good Node'}\n",
        encoding="utf-8",
    )

    result = generate_node_docs(package)

    assert result["path"] == str(package / "NODE_DOCS.md")
    assert "# Custom Node Documentation" in result["markdown"]
    assert "GoodNode" in result["markdown"]
    assert (package / "NODE_DOCS.md").read_text(encoding="utf-8") == result["markdown"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_node_docs.py -q
```

Expected: fail because `node_docs.py` is not present.

- [ ] **Step 3: Implement deterministic docs**

Create `src/comfydex_mcp/node_docs.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from .custom_nodes import inspect_custom_node_package, validate_node_class


def generate_node_docs(package_dir: Path) -> dict[str, Any]:
    inspection = inspect_custom_node_package(package_dir)
    lines = ["# Custom Node Documentation", ""]
    for mapping_key, class_name in sorted(inspection["class_mappings"].items()):
        validation = validate_node_class(package_dir, class_name)
        display = inspection["display_name_mappings"].get(mapping_key, class_name)
        lines.extend(
            [
                f"## {display}",
                "",
                f"- Mapping key: `{mapping_key}`",
                f"- Class: `{class_name}`",
                f"- Validation status: `{validation['status']}`",
                "",
            ]
        )
    markdown = "\n".join(lines).rstrip() + "\n"
    path = package_dir / "NODE_DOCS.md"
    path.write_text(markdown, encoding="utf-8")
    return {"path": str(path), "markdown": markdown, "inspection": inspection}
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_node_docs.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comfydex_mcp/node_docs.py tests/test_node_docs.py
git commit -m "feat: generate custom node docs"
```

### Task 3.5: Custom Node MCP Tools

**Files:**

- Modify: `src/comfydex_mcp/server.py`
- Test: `tests/test_server_tools.py`

- [ ] **Step 1: Write custom node server tests**

Append:

```python
@pytest.mark.asyncio
async def test_comfy_scaffold_custom_node_package_tool(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    result = await server.comfy_scaffold_custom_node_package("simple_math")
    assert result["class_name"] == "SimpleMathNode"
    assert (tmp_path / "custom_nodes" / "simple_math" / "nodes.py").exists()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_server_tools.py::test_comfy_scaffold_custom_node_package_tool -q
```

Expected: fail because MCP tools are not present.

- [ ] **Step 3: Wire custom node tools**

Modify imports:

```python
from .custom_nodes import (
    check_node_imports,
    inspect_custom_node_package,
    validate_node_class,
    validate_node_mappings,
)
from .node_docs import generate_node_docs
from .node_scaffold import scaffold_custom_node_package
```

Add helper:

```python
def _custom_node_package_path(workspace: Path, package_name: str) -> Path:
    from .paths import safe_package_dir

    return safe_package_dir(workspace / "custom_nodes", package_name)
```

Add tools:

```python
@mcp.tool()
async def comfy_scaffold_custom_node_package(package_name: str) -> dict[str, Any]:
    ctx = tool_context()
    return scaffold_custom_node_package(ctx.workspace, package_name)


@mcp.tool()
async def comfy_inspect_custom_node_package(package_name: str) -> dict[str, Any]:
    ctx = tool_context()
    return inspect_custom_node_package(_custom_node_package_path(ctx.workspace, package_name))


@mcp.tool()
async def comfy_validate_node_mappings(package_name: str) -> dict[str, Any]:
    ctx = tool_context()
    return validate_node_mappings(_custom_node_package_path(ctx.workspace, package_name))


@mcp.tool()
async def comfy_validate_node_class(package_name: str, class_name: str) -> dict[str, Any]:
    ctx = tool_context()
    return validate_node_class(_custom_node_package_path(ctx.workspace, package_name), class_name)


@mcp.tool()
async def comfy_generate_node_docs(package_name: str) -> dict[str, Any]:
    ctx = tool_context()
    return generate_node_docs(_custom_node_package_path(ctx.workspace, package_name))


@mcp.tool()
async def comfy_check_node_imports(package_name: str) -> dict[str, Any]:
    ctx = tool_context()
    return check_node_imports(_custom_node_package_path(ctx.workspace, package_name))
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_custom_node_scaffold.py tests/test_custom_nodes.py tests/test_node_docs.py tests/test_server_tools.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comfydex_mcp/server.py tests/test_server_tools.py
git commit -m "feat: expose custom node tools"
```

### Milestone 3 Gate

Run:

```powershell
python -m pytest tests/test_custom_node_scaffold.py tests/test_custom_nodes.py tests/test_node_docs.py tests/test_server_tools.py -q
python -m pytest -q
python scripts/validate_plugin.py
```

Run the spec compliance review and code quality review using the prompts in the review gate section. Resolve Critical and Important findings, rerun the commands, then proceed to milestone 4.

## Milestone 4: Run Diagnostics, Output Management, Comparison, And Batch Runs

### Task 4.1: Run Diagnostics

**Files:**

- Create: `src/comfydex_mcp/diagnostics.py`
- Test: `tests/test_diagnostics.py`

- [ ] **Step 1: Write diagnosis tests**

Create `tests/test_diagnostics.py`:

```python
from comfydex_mcp.diagnostics import diagnose_run


def test_diagnose_run_explains_failed_submission():
    run = {
        "run_id": "r1",
        "status": "failed",
        "events": [{"type": "submission_error", "error": "missing node type"}],
        "outputs": [],
    }
    workflow = {"1": {"class_type": "MissingNode", "inputs": {}}}

    result = diagnose_run(run, workflow, object_info={})

    assert result["status"] == "failed"
    assert "submission_error" in result["signals"]
    assert result["missing_node_types"] == ["MissingNode"]
    assert "missing node type" in result["summary"]


def test_diagnose_run_reports_missing_outputs_for_completed_run():
    run = {"run_id": "r2", "status": "completed", "events": [], "outputs": []}
    result = diagnose_run(run, {"1": {"class_type": "SaveImage", "inputs": {}}}, object_info={"SaveImage": {}})

    assert "missing_outputs" in result["signals"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_diagnostics.py -q
```

Expected: fail because diagnostics module is not present.

- [ ] **Step 3: Implement diagnosis**

Create `src/comfydex_mcp/diagnostics.py`:

```python
from __future__ import annotations

import json
from typing import Any


def diagnose_run(
    run_record: dict[str, Any],
    workflow: dict[str, Any] | None = None,
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    signals: list[str] = []
    missing_node_types: list[str] = []
    events = run_record.get("events", [])

    for event in events:
        if isinstance(event, dict) and event.get("type"):
            signals.append(str(event["type"]))

    if workflow and object_info is not None:
        for node in workflow.values():
            if isinstance(node, dict):
                node_type = node.get("class_type")
                if isinstance(node_type, str) and node_type not in object_info:
                    missing_node_types.append(node_type)

    if run_record.get("status") == "completed" and not run_record.get("outputs"):
        signals.append("missing_outputs")

    event_text = json.dumps(events, ensure_ascii=False)
    summary_parts = [f"Run {run_record.get('run_id')} status is {run_record.get('status', 'unknown')}."]
    if "submission_error" in signals:
        summary_parts.append("Submission failed before queue execution.")
    if missing_node_types:
        summary_parts.append(f"Missing node types: {', '.join(sorted(set(missing_node_types)))}.")
    if "missing_outputs" in signals:
        summary_parts.append("The run completed but no outputs are registered.")
    if event_text and event_text != "[]":
        summary_parts.append(event_text[:300])

    return {
        "run_id": run_record.get("run_id"),
        "status": run_record.get("status", "unknown"),
        "signals": sorted(set(signals)),
        "missing_node_types": sorted(set(missing_node_types)),
        "summary": " ".join(summary_parts),
    }
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_diagnostics.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comfydex_mcp/diagnostics.py tests/test_diagnostics.py
git commit -m "feat: diagnose runs"
```

### Task 4.2: Markdown Run Reports

**Files:**

- Create: `src/comfydex_mcp/reports.py`
- Test: `tests/test_reports.py`

- [ ] **Step 1: Write report tests**

Create `tests/test_reports.py`:

```python
from pathlib import Path

from comfydex_mcp.reports import export_run_report


def test_export_run_report_writes_markdown(tmp_path: Path):
    run_dir = tmp_path / "runs" / "r1"
    run_dir.mkdir(parents=True)
    run = {"run_id": "r1", "workflow_name": "wf.json", "prompt_id": "p1", "status": "completed", "events": [], "outputs": [{"filename": "a.png"}]}
    diagnosis = {"summary": "Run completed.", "signals": []}

    result = export_run_report(run_dir, run, {"node_count": 1}, diagnosis)

    assert result["path"] == str(run_dir / "report.md")
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "# Comfydex Run Report" in markdown
    assert "wf.json" in markdown
    assert "a.png" in markdown
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_reports.py -q
```

Expected: fail because reports module is not present.

- [ ] **Step 3: Implement report export**

Create `src/comfydex_mcp/reports.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any


def export_run_report(
    run_dir: Path,
    run_record: dict[str, Any],
    workflow_summary: dict[str, Any],
    diagnosis: dict[str, Any],
) -> dict[str, Any]:
    outputs = run_record.get("outputs", [])
    lines = [
        "# Comfydex Run Report",
        "",
        f"- Run ID: `{run_record.get('run_id')}`",
        f"- Workflow: `{run_record.get('workflow_name')}`",
        f"- Prompt ID: `{run_record.get('prompt_id')}`",
        f"- Status: `{run_record.get('status')}`",
        "",
        "## Diagnosis",
        "",
        diagnosis.get("summary", ""),
        "",
        "## Workflow Summary",
        "",
        f"- Node count: `{workflow_summary.get('node_count', 0)}`",
        "",
        "## Outputs",
        "",
    ]
    if outputs:
        for output in outputs:
            lines.append(f"- `{output.get('filename') or output.get('downloaded_path')}`")
    else:
        lines.append("- No outputs registered.")
    markdown = "\n".join(lines).rstrip() + "\n"
    path = run_dir / "report.md"
    path.write_text(markdown, encoding="utf-8")
    return {"path": str(path), "markdown": markdown}
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_reports.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comfydex_mcp/reports.py tests/test_reports.py
git commit -m "feat: export run reports"
```

### Task 4.3: Run Comparison

**Files:**

- Modify: `src/comfydex_mcp/diagnostics.py`
- Test: `tests/test_diagnostics.py`

- [ ] **Step 1: Write comparison tests**

Append:

```python
from comfydex_mcp.diagnostics import compare_runs


def test_compare_runs_reports_changed_node_inputs():
    left_run = {"run_id": "a", "status": "completed", "outputs": [{"filename": "a.png"}]}
    right_run = {"run_id": "b", "status": "failed", "outputs": []}
    left_workflow = {"1": {"class_type": "KSampler", "inputs": {"seed": 1}}}
    right_workflow = {"1": {"class_type": "KSampler", "inputs": {"seed": 2}}}

    result = compare_runs(left_run, right_run, left_workflow, right_workflow)

    assert result["status_changed"] == {"left": "completed", "right": "failed"}
    assert result["input_changes"][0]["input"] == "seed"
    assert result["output_count_changed"] == {"left": 1, "right": 0}
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_diagnostics.py::test_compare_runs_reports_changed_node_inputs -q
```

Expected: fail because `compare_runs()` is not present.

- [ ] **Step 3: Implement semantic comparison**

Add:

```python
def compare_runs(
    left_run: dict[str, Any],
    right_run: dict[str, Any],
    left_workflow: dict[str, Any],
    right_workflow: dict[str, Any],
) -> dict[str, Any]:
    input_changes: list[dict[str, Any]] = []
    all_node_ids = sorted(set(left_workflow) | set(right_workflow))
    for node_id in all_node_ids:
        left_node = left_workflow.get(node_id, {})
        right_node = right_workflow.get(node_id, {})
        left_inputs = left_node.get("inputs", {}) if isinstance(left_node, dict) else {}
        right_inputs = right_node.get("inputs", {}) if isinstance(right_node, dict) else {}
        for input_name in sorted(set(left_inputs) | set(right_inputs)):
            if left_inputs.get(input_name) != right_inputs.get(input_name):
                input_changes.append({
                    "node_id": node_id,
                    "input": input_name,
                    "left": left_inputs.get(input_name),
                    "right": right_inputs.get(input_name),
                })
    return {
        "left_run_id": left_run.get("run_id"),
        "right_run_id": right_run.get("run_id"),
        "status_changed": None if left_run.get("status") == right_run.get("status") else {"left": left_run.get("status"), "right": right_run.get("status")},
        "output_count_changed": None if len(left_run.get("outputs", [])) == len(right_run.get("outputs", [])) else {"left": len(left_run.get("outputs", [])), "right": len(right_run.get("outputs", []))},
        "input_changes": input_changes,
    }
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_diagnostics.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comfydex_mcp/diagnostics.py tests/test_diagnostics.py
git commit -m "feat: compare run workflows"
```

### Task 4.4: Output Listing And Confirmed Cleanup

**Files:**

- Create: `src/comfydex_mcp/outputs.py`
- Test: `tests/test_outputs.py`

- [ ] **Step 1: Write output management tests**

Create `tests/test_outputs.py`:

```python
from pathlib import Path
import os
import time

from comfydex_mcp.outputs import cleanup_outputs, list_outputs


def test_list_outputs_stays_inside_runs_dir(tmp_path: Path):
    output = tmp_path / "runs" / "r1" / "outputs" / "output" / "a.png"
    output.parent.mkdir(parents=True)
    output.write_text("x", encoding="utf-8")

    result = list_outputs(tmp_path / "runs")

    assert result[0]["run_id"] == "r1"
    assert result[0]["filename"] == "a.png"
    assert Path(result[0]["path"]).is_relative_to(tmp_path / "runs")


def test_cleanup_outputs_dry_run_by_default(tmp_path: Path):
    output = tmp_path / "runs" / "r1" / "outputs" / "output" / "a.png"
    output.parent.mkdir(parents=True)
    output.write_text("x", encoding="utf-8")

    result = cleanup_outputs(tmp_path / "runs", confirm=False)

    assert result["deleted"] == []
    assert result["candidates"]
    assert output.exists()


def test_cleanup_outputs_requires_confirm_for_deletion(tmp_path: Path):
    output = tmp_path / "runs" / "r1" / "outputs" / "output" / "a.png"
    output.parent.mkdir(parents=True)
    output.write_text("x", encoding="utf-8")

    result = cleanup_outputs(tmp_path / "runs", confirm=True)

    assert result["deleted"] == [str(output)]
    assert not output.exists()


def test_cleanup_outputs_filters_by_age_threshold(tmp_path: Path):
    old_output = tmp_path / "runs" / "r1" / "outputs" / "output" / "old.png"
    new_output = tmp_path / "runs" / "r1" / "outputs" / "output" / "new.png"
    old_output.parent.mkdir(parents=True)
    old_output.write_text("old", encoding="utf-8")
    new_output.write_text("new", encoding="utf-8")
    old_time = time.time() - 7200
    os.utime(old_output, (old_time, old_time))

    result = cleanup_outputs(tmp_path / "runs", older_than_seconds=3600, confirm=False)

    assert [Path(row["path"]).name for row in result["candidates"]] == ["old.png"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_outputs.py -q
```

Expected: fail because outputs module is not present.

- [ ] **Step 3: Implement output listing and cleanup**

Create `src/comfydex_mcp/outputs.py`:

```python
from __future__ import annotations

import time
from pathlib import Path
from typing import Any


def _inside(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def list_outputs(runs_dir: Path) -> list[dict[str, Any]]:
    base = runs_dir.resolve()
    rows: list[dict[str, Any]] = []
    for path in sorted(base.glob("*/outputs/**/*")):
        if not path.is_file() or not _inside(path, base):
            continue
        run_id = path.relative_to(base).parts[0]
        rows.append({
            "run_id": run_id,
            "path": str(path),
            "filename": path.name,
            "size": path.stat().st_size,
            "modified_time": path.stat().st_mtime,
            "type": path.parent.name,
        })
    return rows


def cleanup_outputs(
    runs_dir: Path,
    confirm: bool = False,
    failed_run_ids: list[str] | None = None,
    older_than_seconds: int | None = None,
) -> dict[str, Any]:
    outputs = list_outputs(runs_dir)
    if failed_run_ids is not None:
        candidates = [row for row in outputs if row["run_id"] in set(failed_run_ids)]
    else:
        candidates = outputs
    if older_than_seconds is not None:
        cutoff = time.time() - older_than_seconds
        candidates = [row for row in candidates if row["modified_time"] < cutoff]
    deleted: list[str] = []
    if confirm:
        base = runs_dir.resolve()
        for row in candidates:
            path = Path(row["path"]).resolve()
            if not _inside(path, base):
                raise ValueError("cleanup candidate escaped runs_dir")
            path.unlink()
            deleted.append(str(path))
    return {"dry_run": not confirm, "candidates": candidates, "deleted": deleted}
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_outputs.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comfydex_mcp/outputs.py tests/test_outputs.py
git commit -m "feat: manage run outputs safely"
```

### Task 4.5: Batch Records And Batch Submission

**Files:**

- Create: `src/comfydex_mcp/batches.py`
- Modify: `src/comfydex_mcp/server.py`
- Test: `tests/test_batches.py`
- Test: `tests/test_server_tools.py`

- [ ] **Step 1: Write batch tests**

Create `tests/test_batches.py`:

```python
from pathlib import Path

from comfydex_mcp.batches import create_batch_record, read_batch_record, update_batch_run, variation_to_operations


def test_create_batch_record_writes_batch_json(tmp_path: Path):
    result = create_batch_record(
        tmp_path / "runs",
        "seed-sweep",
        "wf.json",
        [{"seed": 1}, {"seed": 2}],
    )

    assert result["status"] == "queued"
    assert len(result["runs"]) == 2
    assert (tmp_path / "runs" / ".batches" / result["batch_id"] / "batch.json").exists()


def test_update_batch_run_preserves_partial_failure(tmp_path: Path):
    batch = create_batch_record(tmp_path / "runs", "seed-sweep", "wf.json", [{"seed": 1}, {"seed": 2}])
    update_batch_run(tmp_path / "runs", batch["batch_id"], 0, run_id="r1", status="completed")
    updated = update_batch_run(tmp_path / "runs", batch["batch_id"], 1, run_id="r2", status="failed")

    assert updated["status"] == "partial"
    assert read_batch_record(tmp_path / "runs", batch["batch_id"])["runs"][1]["status"] == "failed"


def test_variation_to_operations_accepts_node_inputs_schema():
    result = variation_to_operations({"node_id": "1", "inputs": {"seed": 42, "steps": 30}})

    assert result == [
        {"op": "set_input", "node_id": "1", "input": "seed", "value": 42},
        {"op": "set_input", "node_id": "1", "input": "steps", "value": 30},
    ]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_batches.py -q
```

Expected: fail because `batches.py` is not present.

- [ ] **Step 3: Implement batch records**

Create `src/comfydex_mcp/batches.py`:

```python
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import ensure_directory


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-").lower() or "batch"


def _batch_dir(runs_dir: Path, batch_id: str) -> Path:
    base = (runs_dir / ".batches").resolve()
    target = (base / batch_id).resolve()
    target.relative_to(base)
    return target


def _batch_path(runs_dir: Path, batch_id: str) -> Path:
    return _batch_dir(runs_dir, batch_id) / "batch.json"


def create_batch_record(
    runs_dir: Path,
    label: str,
    workflow_name: str,
    variations: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    created = now or datetime.now(timezone.utc)
    prefix = created.strftime("%Y-%m-%dT%H-%M-%S")
    batch_id = f"{prefix}_{_slug(label)}"
    directory = ensure_directory(_batch_dir(runs_dir, batch_id))
    record = {
        "batch_id": batch_id,
        "workflow_name": workflow_name,
        "status": "queued",
        "created_at": created.isoformat(),
        "runs": [
            {"index": index, "parameters": parameters, "status": "queued", "run_id": None}
            for index, parameters in enumerate(variations)
        ],
    }
    (directory / "batch.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def read_batch_record(runs_dir: Path, batch_id: str) -> dict[str, Any]:
    return json.loads(_batch_path(runs_dir, batch_id).read_text(encoding="utf-8"))


def update_batch_run(runs_dir: Path, batch_id: str, index: int, run_id: str, status: str) -> dict[str, Any]:
    record = read_batch_record(runs_dir, batch_id)
    record["runs"][index]["run_id"] = run_id
    record["runs"][index]["status"] = status
    statuses = {row["status"] for row in record["runs"]}
    if statuses <= {"completed"}:
        record["status"] = "completed"
    elif "failed" in statuses and "completed" in statuses:
        record["status"] = "partial"
    elif "failed" in statuses and statuses <= {"failed"}:
        record["status"] = "failed"
    elif "running" in statuses:
        record["status"] = "running"
    _batch_path(runs_dir, batch_id).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def variation_to_operations(variation: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(variation.get("changes"), list):
        return [
            {
                "op": str(change.get("op", "set_input")),
                "node_id": str(change["node_id"]),
                "input": str(change["input"]),
                "value": change.get("value"),
            }
            for change in variation["changes"]
        ]
    node_id = variation.get("node_id")
    inputs = variation.get("inputs", {})
    if node_id is not None and isinstance(inputs, dict):
        return [
            {"op": "set_input", "node_id": str(node_id), "input": str(input_name), "value": value}
            for input_name, value in inputs.items()
        ]
    return []
```

- [ ] **Step 4: Wire batch server tools**

Add imports:

```python
from .batches import create_batch_record, read_batch_record, update_batch_run, variation_to_operations
from .patching import patch_workflow
```

Add:

```python
@mcp.tool()
async def comfy_batch_submit(
    workflow_name: str,
    variations: list[dict[str, Any]],
    batch_label: str = "batch",
) -> dict[str, Any]:
    ctx = tool_context()
    batch = create_batch_record(ctx.config.runs_dir, batch_label, workflow_name, variations)
    for index, parameters in enumerate(variations):
        try:
            loaded = read_workflow(ctx.config.workflows_dir, workflow_name)
            patched = patch_workflow(loaded["json"], variation_to_operations(parameters))
            child_name = f"{Path(workflow_name).stem}.{batch['batch_id']}.{index}.json"
            if patched["report"]["status"] == "patched":
                save_workflow(ctx.config.workflows_dir, child_name, patched["workflow"], require_api=True)
            run = await comfy_submit_workflow(child_name if patched["report"]["status"] == "patched" else workflow_name, run_label=f"{batch['batch_id']}-{index}")
            batch = update_batch_run(ctx.config.runs_dir, batch["batch_id"], index, run["run_id"], run["status"])
        except Exception:
            batch = update_batch_run(ctx.config.runs_dir, batch["batch_id"], index, "", "failed")
    return batch


@mcp.tool()
async def comfy_read_batch(batch_id: str) -> dict[str, Any]:
    return read_batch_record(tool_context().config.runs_dir, batch_id)
```

Add a server test using a monkeypatched `comfy_submit_workflow` wrapper if direct network behavior makes the test brittle:

```python
@pytest.mark.asyncio
async def test_comfy_read_batch_tool(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    batch = create_batch_record(tmp_path / "runs", "seed-sweep", "wf.json", [{"seed": 1}])
    result = await server.comfy_read_batch(batch["batch_id"])
    assert result["batch_id"] == batch["batch_id"]
```

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_batches.py tests/test_server_tools.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/comfydex_mcp/batches.py src/comfydex_mcp/server.py tests/test_batches.py tests/test_server_tools.py
git commit -m "feat: manage batch runs"
```

### Task 4.6: Diagnostics And Output MCP Tools

**Files:**

- Modify: `src/comfydex_mcp/server.py`
- Test: `tests/test_server_tools.py`

- [ ] **Step 1: Write server tests**

Append:

```python
@pytest.mark.asyncio
async def test_comfy_diagnose_run_tool(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    run = create_run(tmp_path / "runs", "wf.json", API_WORKFLOW, "http://127.0.0.1:8188", None, "client")
    result = await server.comfy_diagnose_run(run["run_id"], use_object_info=False)
    assert result["run_id"] == run["run_id"]


@pytest.mark.asyncio
async def test_comfy_list_outputs_tool(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    output = tmp_path / "runs" / "r1" / "outputs" / "output" / "a.png"
    output.parent.mkdir(parents=True)
    output.write_text("x", encoding="utf-8")
    result = await server.comfy_list_outputs()
    assert result[0]["filename"] == "a.png"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_server_tools.py::test_comfy_diagnose_run_tool tests/test_server_tools.py::test_comfy_list_outputs_tool -q
```

Expected: fail because server tools are not present.

- [ ] **Step 3: Wire diagnostics, reports, comparison, and output tools**

Add imports:

```python
from .diagnostics import compare_runs, diagnose_run
from .outputs import cleanup_outputs, list_outputs as list_run_outputs
from .reports import export_run_report
```

Add:

```python
@mcp.tool()
async def comfy_diagnose_run(run_id: str, use_object_info: bool = True) -> dict[str, Any]:
    ctx = tool_context()
    record = read_run(ctx.config.runs_dir, run_id)
    workflow_path = ctx.config.runs_dir / run_id / "workflow.json"
    workflow = json.loads(workflow_path.read_text(encoding="utf-8")) if workflow_path.exists() else None
    object_info = None
    if use_object_info:
        async with ComfyClient(
            ctx.config.base_url,
            ctx.config.headers,
            ctx.config.request_timeout_seconds,
        ) as client:
            object_info = await client.get_object_info()
    return diagnose_run(record, workflow, object_info)


@mcp.tool()
async def comfy_export_run_report(run_id: str) -> dict[str, Any]:
    ctx = tool_context()
    record = read_run(ctx.config.runs_dir, run_id)
    workflow_path = ctx.config.runs_dir / run_id / "workflow.json"
    workflow = json.loads(workflow_path.read_text(encoding="utf-8")) if workflow_path.exists() else {}
    diagnosis = diagnose_run(record, workflow, object_info=None)
    summary = analyze_workflow(workflow, object_info=None) if workflow else {"node_count": 0}
    return export_run_report(ctx.config.runs_dir / run_id, record, summary, diagnosis)


@mcp.tool()
async def comfy_compare_runs(left_run_id: str, right_run_id: str) -> dict[str, Any]:
    ctx = tool_context()
    left = read_run(ctx.config.runs_dir, left_run_id)
    right = read_run(ctx.config.runs_dir, right_run_id)
    left_workflow = json.loads((ctx.config.runs_dir / left_run_id / "workflow.json").read_text(encoding="utf-8"))
    right_workflow = json.loads((ctx.config.runs_dir / right_run_id / "workflow.json").read_text(encoding="utf-8"))
    return compare_runs(left, right, left_workflow, right_workflow)


@mcp.tool()
async def comfy_list_outputs() -> list[dict[str, Any]]:
    return list_run_outputs(tool_context().config.runs_dir)


@mcp.tool()
async def comfy_cleanup_outputs(
    confirm: bool = False,
    failed_run_ids: list[str] | None = None,
    older_than_seconds: int | None = None,
) -> dict[str, Any]:
    return cleanup_outputs(
        tool_context().config.runs_dir,
        confirm=confirm,
        failed_run_ids=failed_run_ids,
        older_than_seconds=older_than_seconds,
    )
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_diagnostics.py tests/test_reports.py tests/test_outputs.py tests/test_batches.py tests/test_server_tools.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comfydex_mcp/server.py tests/test_server_tools.py
git commit -m "feat: expose run management tools"
```

### Milestone 4 Gate

Run:

```powershell
python -m pytest tests/test_diagnostics.py tests/test_reports.py tests/test_outputs.py tests/test_batches.py tests/test_server_tools.py -q
python -m pytest -q
python scripts/validate_plugin.py
```

Run the spec compliance review and code quality review using the prompts in the review gate section. Resolve Critical and Important findings, rerun the commands, then proceed to milestone 5.

## Milestone 5: Skills, Examples, Documentation, And Release Integration

### Task 5.1: Codex Skills

**Files:**

- Modify: `skills/comfyui-workflows/SKILL.md`
- Create: `skills/comfyui-custom-nodes/SKILL.md`
- Test: `tests/test_docs_examples.py`

- [ ] **Step 1: Write skill presence tests**

Create `tests/test_docs_examples.py`:

```python
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_workflow_skill_mentions_new_tool_order():
    text = (ROOT / "skills" / "comfyui-workflows" / "SKILL.md").read_text(encoding="utf-8")
    assert "comfy_import_ui_workflow" in text
    assert "comfy_build_workflow_plan" in text
    assert "comfy_validate_api_workflow" in text


def test_custom_node_skill_exists_and_mentions_workspace_boundary():
    text = (ROOT / "skills" / "comfyui-custom-nodes" / "SKILL.md").read_text(encoding="utf-8")
    assert "custom_nodes/" in text
    assert "comfy_scaffold_custom_node_package" in text
    assert "comfy_check_node_imports" in text
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_docs_examples.py::test_custom_node_skill_exists_and_mentions_workspace_boundary -q
```

Expected: fail because the new skill is not present.

- [ ] **Step 3: Update workflow skill**

Add these sections to `skills/comfyui-workflows/SKILL.md`:

```markdown
## UI Workflow Import

When the user provides ComfyUI UI workflow JSON, call tools in this order:

1. `comfy_classify_workflow`
2. `comfy_import_ui_workflow`
3. `comfy_convert_ui_to_api`
4. `comfy_validate_api_workflow`
5. `comfy_submit_workflow` only after validation reports `valid`

Keep the original `.ui.json` file. Treat conversion gaps as actionable work, not as successful conversion.

## Workflow Builder

For workflow creation from intent, call:

1. `comfy_list_workflow_templates`
2. `comfy_build_workflow_plan`
3. `comfy_explain_workflow_plan`
4. `comfy_build_workflow`
5. `comfy_validate_workflow_against_object_info`

Do not submit generated workflows while required inputs or unavailable node types are listed in the plan.
```

- [ ] **Step 4: Add custom node skill**

Create `skills/comfyui-custom-nodes/SKILL.md`:

```markdown
---
name: comfyui-custom-nodes
description: Use when developing, inspecting, validating, documenting, or smoke-checking ComfyUI custom node packages with Comfydex.
---

# ComfyUI Custom Nodes With Comfydex

Use this skill when the user wants help building a ComfyUI custom node package.

## Safety Boundary

Default writes go under workspace-local `custom_nodes/`.
Do not write into a user's ComfyUI installation unless the user explicitly configures that target.

## Scaffold Flow

1. `comfy_scaffold_custom_node_package`
2. `comfy_inspect_custom_node_package`
3. `comfy_validate_node_mappings`
4. `comfy_validate_node_class`
5. `comfy_check_node_imports`
6. `comfy_generate_node_docs`

## Existing Package Flow

1. `comfy_inspect_custom_node_package`
2. `comfy_validate_node_mappings`
3. `comfy_validate_node_class`
4. `comfy_check_node_imports`
5. `comfy_generate_node_docs`

Report import errors without crashing the MCP server. Keep generated documentation deterministic.
```

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_docs_examples.py -q
```

Expected: pass for skill tests.

- [ ] **Step 6: Commit**

```powershell
git add skills/comfyui-workflows/SKILL.md skills/comfyui-custom-nodes/SKILL.md tests/test_docs_examples.py
git commit -m "docs: update skills for 0.2 workflows"
```

### Task 5.2: Examples

**Files:**

- Create: `examples/workflows/basic_text_to_image.api.json`
- Create: `examples/workflows/sample_ui_workflow.ui.json`
- Create: `examples/custom_nodes/simple_math_node/__init__.py`
- Create: `examples/custom_nodes/simple_math_node/nodes.py`
- Create: `examples/custom_nodes/simple_math_node/README.md`
- Create: `examples/custom_nodes/simple_math_node/pyproject.toml`
- Create: `examples/custom_nodes/simple_math_node/tests/test_nodes.py`
- Create: `examples/reports/sample_run_report.md`
- Modify: `tests/test_docs_examples.py`

- [ ] **Step 1: Add example tests**

Append:

```python
import json

from comfydex_mcp.workflows import classify_workflow


def test_example_workflows_are_classified():
    api = json.loads((ROOT / "examples" / "workflows" / "basic_text_to_image.api.json").read_text(encoding="utf-8"))
    ui = json.loads((ROOT / "examples" / "workflows" / "sample_ui_workflow.ui.json").read_text(encoding="utf-8"))

    assert classify_workflow(api) == "api"
    assert classify_workflow(ui) == "ui"


def test_example_custom_node_contains_mappings():
    text = (ROOT / "examples" / "custom_nodes" / "simple_math_node" / "nodes.py").read_text(encoding="utf-8")
    assert "NODE_CLASS_MAPPINGS" in text
    assert "NODE_DISPLAY_NAME_MAPPINGS" in text


def test_example_report_is_markdown():
    text = (ROOT / "examples" / "reports" / "sample_run_report.md").read_text(encoding="utf-8")
    assert text.startswith("# Comfydex Run Report")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_docs_examples.py::test_example_workflows_are_classified -q
```

Expected: fail because examples are not present.

- [ ] **Step 3: Add workflow examples**

Create `examples/workflows/basic_text_to_image.api.json`:

```json
{
  "1": {
    "class_type": "CheckpointLoaderSimple",
    "inputs": {
      "ckpt_name": "example.safetensors"
    }
  },
  "2": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "a clean product photo",
      "clip": [
        "1",
        1
      ]
    }
  },
  "3": {
    "class_type": "SaveImage",
    "inputs": {
      "images": [
        "2",
        0
      ]
    }
  }
}
```

Create `examples/workflows/sample_ui_workflow.ui.json`:

```json
{
  "last_node_id": 2,
  "nodes": [
    {
      "id": 1,
      "type": "CheckpointLoaderSimple",
      "widgets_values": [
        "example.safetensors"
      ]
    },
    {
      "id": 2,
      "type": "SaveImage",
      "widgets_values": [
        "Comfydex"
      ]
    }
  ],
  "links": [
    [
      1,
      1,
      0,
      2,
      0,
      "IMAGE"
    ]
  ]
}
```

- [ ] **Step 4: Add custom node example and report**

Use the same package shape produced by `scaffold_custom_node_package()` for `examples/custom_nodes/simple_math_node/`.

Create `examples/reports/sample_run_report.md`:

```markdown
# Comfydex Run Report

- Run ID: `sample-run`
- Workflow: `basic_text_to_image.api.json`
- Prompt ID: `sample-prompt`
- Status: `completed`

## Diagnosis

Run completed.

## Workflow Summary

- Node count: `3`

## Outputs

- `sample.png`
```

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_docs_examples.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add examples tests/test_docs_examples.py
git commit -m "docs: add 0.2 examples"
```

### Task 5.3: Usage Documentation And README

**Files:**

- Create: `docs/usage/workflow-import.md`
- Create: `docs/usage/workflow-builder.md`
- Create: `docs/usage/custom-node-development.md`
- Create: `docs/usage/run-diagnostics.md`
- Modify: `README.md`
- Modify: `tests/test_docs_examples.py`

- [ ] **Step 1: Add documentation tests**

Append:

```python
def test_usage_docs_cover_new_capabilities():
    required = {
        "workflow-import.md": "comfy_convert_ui_to_api",
        "workflow-builder.md": "comfy_build_workflow_plan",
        "custom-node-development.md": "comfy_validate_node_class",
        "run-diagnostics.md": "comfy_diagnose_run",
    }
    for filename, marker in required.items():
        text = (ROOT / "docs" / "usage" / filename).read_text(encoding="utf-8")
        assert marker in text


def test_readme_mentions_0_2_capabilities():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "0.2.0" in text
    assert "UI workflow" in text
    assert "custom node" in text
    assert "batch" in text
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_docs_examples.py::test_usage_docs_cover_new_capabilities -q
```

Expected: fail because usage docs are not present.

- [ ] **Step 3: Add usage docs**

Each usage doc must include:

- Tool order.
- Required inputs.
- Safety boundary.
- Example command-like MCP call names.
- Failure handling guidance.

Use these required headings:

```markdown
# Workflow Import

## Tool Order

## Validation

## Conversion Gaps

## Safe Submission
```

```markdown
# Workflow Builder

## Tool Order

## Build Plans

## Required Inputs

## Validation
```

```markdown
# Custom Node Development

## Workspace Boundary

## Scaffold Flow

## Inspection And Validation

## Import Checks
```

```markdown
# Run Diagnostics

## Diagnosis

## Reports

## Output Cleanup

## Batch Runs
```

- [ ] **Step 4: Update README**

Update `README.md` to include:

- Version `0.2.0`.
- A capability table for all 0.2 tool groups.
- UI workflow import and conversion examples.
- Workflow builder examples.
- Custom node assistant examples.
- Run diagnostics, reports, outputs, and batch examples.
- Safety boundaries:
  - workspace-only workflow files,
  - workspace-local `custom_nodes/`,
  - output cleanup dry-run by default,
  - no submission before validation.
- Release notes for 0.2.0.

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_docs_examples.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add README.md docs/usage tests/test_docs_examples.py
git commit -m "docs: document 0.2 capabilities"
```

### Task 5.4: Version Bump And Release Validation

**Files:**

- Modify: `pyproject.toml`
- Modify: `.codex-plugin/plugin.json`
- Modify: `src/comfydex_mcp/__init__.py`
- Test: `tests/test_version.py`

- [ ] **Step 1: Write version tests**

Create `tests/test_version.py`:

```python
import json
import tomllib
from pathlib import Path

import comfydex_mcp


ROOT = Path(__file__).parents[1]


def test_versions_match_0_2_0():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == "0.2.0"
    assert manifest["version"] == "0.2.0"
    assert comfydex_mcp.__version__ == "0.2.0"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_version.py -q
```

Expected: fail because versions are still `0.1.0` or package version constant is absent.

- [ ] **Step 3: Bump package and plugin versions**

Set:

- `pyproject.toml` `[project].version = "0.2.0"`
- `.codex-plugin/plugin.json` `"version": "0.2.0"`
- `src/comfydex_mcp/__init__.py`:

```python
__version__ = "0.2.0"
```

- [ ] **Step 4: Run full release validation**

Run:

```powershell
python -m pytest -q
python scripts/validate_plugin.py
python -m json.tool .codex-plugin/plugin.json > $null
python -m json.tool .mcp.json > $null
```

Expected: all commands pass.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml .codex-plugin/plugin.json src/comfydex_mcp/__init__.py tests/test_version.py
git commit -m "chore: release 0.2.0"
```

### Milestone 5 Gate

Run:

```powershell
python -m pytest tests/test_docs_examples.py tests/test_version.py -q
python -m pytest -q
python scripts/validate_plugin.py
python -m json.tool .codex-plugin/plugin.json > $null
python -m json.tool .mcp.json > $null
```

Run the spec compliance review and code quality review using the prompts in the review gate section. Resolve Critical and Important findings, rerun the commands, then proceed to the final release gate.

## Final Release Gate For 0.2.0

- [ ] Run all tests:

```powershell
python -m pytest -q
```

- [ ] Run plugin validation:

```powershell
python scripts/validate_plugin.py
```

- [ ] Validate JSON manifests:

```powershell
python -m json.tool .codex-plugin/plugin.json > $null
python -m json.tool .mcp.json > $null
```

- [ ] Confirm release files mention `0.2.0`:

```powershell
rg -n "0\\.2\\.0" README.md pyproject.toml .codex-plugin/plugin.json src/comfydex_mcp/__init__.py
```

- [ ] Confirm all new MCP tool names are documented:

```powershell
rg -n "comfy_import_ui_workflow|comfy_build_workflow_plan|comfy_scaffold_custom_node_package|comfy_diagnose_run|comfy_batch_submit" README.md skills docs/usage
```

- [ ] Review final git state:

```powershell
git status -sb
git log --oneline -5
```

- [ ] Create tag after the user approves release publication:

```powershell
git tag v0.2.0
```

- [ ] Publish GitHub release notes after the tag exists:

```text
Title: Comfydex 0.2.0

Highlights:
- UI workflow import, classification, conservative conversion, validation, and gap reports.
- Workflow templates, build plans, generated API workflows, and targeted patching.
- Workspace-local custom node scaffolding, inspection, validation, import checks, and docs.
- Run diagnosis, markdown reports, output listing and cleanup, run comparison, and batch records.
```

## Regression Requirements

Keep these 0.1 behaviors passing throughout the release:

- `comfy_submit_workflow` rejects non-API workflow JSON.
- Failed prompt submission creates a failed run record.
- WebSocket fallback polling reaches terminal history status.
- WebSocket URL base paths are preserved.
- Output downloads include the ComfyUI output type directory.
- Headers are redacted from config output.
- Workflow and output paths cannot escape configured directories.

Relevant regression commands:

```powershell
python -m pytest tests/test_server_tools.py tests/test_ws.py tests/test_paths.py tests/test_config.py tests/test_comfy_client.py -q
```

## Automatic Milestone Progression

Use this status rule during execution:

- Mark a milestone complete when its targeted tests, full suite, plugin validation, spec compliance review, and code quality review pass.
- Immediately begin the next milestone after completion.
- Do not ask the user to confirm between milestones when the implementation still matches the approved design.
- Stop and report only when a blocker cannot be solved locally, a review gate fails after fixes, a destructive action is required, or the user changes scope.
