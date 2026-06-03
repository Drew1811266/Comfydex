# Comfydex Second Batch Roadmap Design

Date: 2026-06-04

## Goal

The second batch is a single large feature release for Comfydex. It expands the project from a ComfyUI connection and run-control plugin into a broader ComfyUI development assistant inside Codex.

Version target: `0.2.0`

This release includes four major capability groups:

1. UI workflow import and conversion.
2. Natural-language-assisted workflow building.
3. ComfyUI custom node developer assistance.
4. Run diagnostics, output management, run comparison, and batch execution.

Although this is one large release, implementation must be split into milestones. Each milestone has its own tests, review gates, and completion criteria. When a milestone passes review, execution automatically moves to the next milestone without asking the user to continue. The process stops only for a real blocker, a failed review that cannot be resolved locally, or a scope change that needs user approval.

## Current Baseline

Comfydex `0.1.0` already provides:

- Codex plugin manifest.
- Python MCP server.
- ComfyUI HTTP client.
- WebSocket execution waiting.
- HTTP queue/history polling fallback.
- local workflow file management.
- local run record persistence.
- output fetching and registration.
- ComfyUI workflow Skill documentation.

Key current modules:

- `src/comfydex_mcp/config.py`
- `src/comfydex_mcp/paths.py`
- `src/comfydex_mcp/workflows.py`
- `src/comfydex_mcp/analyzer.py`
- `src/comfydex_mcp/runs.py`
- `src/comfydex_mcp/comfy_client.py`
- `src/comfydex_mcp/ws.py`
- `src/comfydex_mcp/server.py`
- `skills/comfyui-workflows/SKILL.md`

The important limitation is that `0.1.0` mainly works with submit-ready ComfyUI API prompt JSON. Many real users start with UI workflow JSON exported from ComfyUI, or they want Codex to help create and modify workflows from intent. The second batch addresses that gap.

## Release Principles

- Keep this as one release, but implement it as milestone-sized units.
- Preserve all `0.1.0` tools and behavior unless a change is explicitly backward compatible.
- Prefer explainable generation over opaque generation.
- Never submit generated workflow JSON until it has been classified and validated.
- Keep file writes inside configured workspace directories.
- Do not modify a user's ComfyUI installation unless the user explicitly configures that target.
- Treat remote ComfyUI headers as sensitive.
- All milestone completions require tests and two-stage review: spec compliance, then code quality.

## Milestone Execution Rules

Each milestone follows this lifecycle:

1. Implement the milestone with tests.
2. Run targeted tests for that milestone.
3. Run the full test suite.
4. Run Codex plugin validation.
5. Run a spec compliance review for the milestone.
6. Run a code quality review for the milestone.
7. Fix all Critical and Important review findings.
8. Re-run relevant tests and reviews.
9. Mark the milestone complete.
10. Automatically start the next milestone.

No user checkpoint is required between milestones if:

- the milestone scope matches this design,
- all tests pass,
- plugin validation passes,
- spec review approves,
- code quality review has no Critical or Important findings.

User input is required only if:

- a design-level ambiguity blocks implementation,
- a milestone requires changing the agreed scope,
- a destructive action is needed,
- an external dependency is unavailable and cannot be mocked or reasonably worked around.

## Milestone 1: UI Workflow Import And Conversion

### Objective

Allow Comfydex to import ComfyUI UI workflow JSON, analyze it, and convert supported parts into submit-ready API prompt JSON.

### New MCP Tools

- `comfy_import_ui_workflow`
- `comfy_classify_workflow`
- `comfy_convert_ui_to_api`
- `comfy_validate_api_workflow`
- `comfy_explain_conversion_gaps`

### New Modules

- `src/comfydex_mcp/ui_workflows.py`
- `src/comfydex_mcp/conversion.py`
- `src/comfydex_mcp/validation.py`

### Behavior

`comfy_import_ui_workflow`:

- accepts a workflow name and UI workflow JSON,
- saves the original UI workflow under the configured workflow directory,
- records that the workflow kind is `ui`,
- returns a summary and conversion readiness report.

`comfy_classify_workflow`:

- classifies a workflow as `api`, `ui`, or `unknown`,
- returns evidence for the classification,
- does not mutate files.

`comfy_convert_ui_to_api`:

- reads UI workflow JSON,
- maps UI nodes to API prompt nodes where possible,
- extracts node ids, node types, input links, widget values, and properties,
- writes a converted API workflow only when conversion reaches a valid submit-ready state,
- otherwise writes no API workflow unless explicitly requested with a draft flag.

`comfy_validate_api_workflow`:

- validates an API workflow against `/object_info`,
- checks missing node types,
- checks missing required inputs,
- checks link references,
- checks probable output nodes.

`comfy_explain_conversion_gaps`:

- returns a human-readable and machine-readable report of why conversion failed or is incomplete.

### Conversion Report

Every conversion attempt returns a report:

```json
{
  "source_workflow": "example.ui.json",
  "target_workflow": "example.api.json",
  "status": "converted|partial|failed",
  "nodes_total": 12,
  "nodes_converted": 10,
  "nodes_failed": 2,
  "gaps": [
    {
      "node_id": "7",
      "node_type": "CustomNode",
      "reason": "missing_object_info",
      "details": "Node type was not present in /object_info."
    }
  ]
}
```

### Acceptance Criteria

- UI workflow JSON can be imported without losing the original file.
- API workflow JSON can still be read, saved, analyzed, submitted, and run exactly as before.
- Conversion is conservative: unsupported nodes produce a gap report instead of a fake valid workflow.
- Converted workflows are validated before being marked submit-ready.
- Tests cover UI classification, successful conversion, partial conversion, unsupported node gaps, link conversion, widget value extraction, and validation errors.

## Milestone 2: Workflow Builder And Templates

### Objective

Let Codex generate workflow plans and API prompt JSON from user intent, using available ComfyUI node metadata where possible.

### New MCP Tools

- `comfy_list_workflow_templates`
- `comfy_suggest_workflow_template`
- `comfy_build_workflow_plan`
- `comfy_build_workflow`
- `comfy_patch_workflow`
- `comfy_validate_workflow_against_object_info`
- `comfy_explain_workflow_plan`

### New Modules

- `src/comfydex_mcp/templates.py`
- `src/comfydex_mcp/builder.py`
- `src/comfydex_mcp/patching.py`

### Template Scope

The first builder templates should include:

- basic text-to-image,
- basic image-to-image,
- upscale,
- SDXL text-to-image,
- LoRA text-to-image,
- ControlNet skeleton.

Templates are not hardcoded final workflows. They are graph recipes that can be adapted to the actual node metadata returned by `/object_info`.

### Workflow Build Plan

The builder must create a plan before writing workflow JSON:

```json
{
  "intent": "Create an SDXL text-to-image workflow with a LoRA.",
  "template": "sdxl-text-to-image-lora",
  "required_nodes": [
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "KSampler",
    "VAEDecode",
    "SaveImage"
  ],
  "parameters": {
    "width": 1024,
    "height": 1024,
    "steps": 30
  },
  "assumptions": [
    "User will provide the checkpoint name.",
    "LoRA strength defaults to 0.8."
  ],
  "missing_information": [
    "checkpoint_name",
    "positive_prompt"
  ]
}
```

### Behavior

`comfy_build_workflow_plan`:

- produces a structured plan,
- identifies required user inputs,
- identifies assumptions,
- does not write workflow JSON.

`comfy_build_workflow`:

- builds an API prompt JSON from a selected template and parameters,
- validates it against object metadata,
- saves it only if validation passes or if the user explicitly allows a draft.

`comfy_patch_workflow`:

- applies targeted parameter or node changes,
- preserves unrelated node ids and links,
- produces a patch report.

`comfy_explain_workflow_plan`:

- explains why the builder selected nodes and links,
- lists unresolved inputs before submission.

### Acceptance Criteria

- Builder can generate at least the listed template plans.
- At least basic text-to-image and image-to-image can produce valid API prompt JSON in tests.
- The builder refuses to claim submit-ready status when required information is missing.
- Workflow patches preserve unrelated graph structure.
- All generated workflows have validation reports.

## Milestone 3: Custom Node Developer Assistant

### Objective

Help developers create, inspect, validate, document, and test ComfyUI custom node packages.

### New MCP Tools

- `comfy_scaffold_custom_node_package`
- `comfy_inspect_custom_node_package`
- `comfy_validate_node_mappings`
- `comfy_validate_node_class`
- `comfy_generate_node_docs`
- `comfy_check_node_imports`

### New Modules

- `src/comfydex_mcp/custom_nodes.py`
- `src/comfydex_mcp/node_scaffold.py`
- `src/comfydex_mcp/node_docs.py`

### Filesystem Boundaries

Custom node development should default to a workspace-local directory:

```text
custom_nodes/
```

Comfydex must not write into the user's ComfyUI installation unless the user explicitly configures that directory.

### Scaffolded Package Shape

```text
custom_nodes/
  example_node/
    __init__.py
    nodes.py
    README.md
    pyproject.toml
    tests/
      test_nodes.py
```

### Behavior

`comfy_scaffold_custom_node_package`:

- creates a minimal custom node package,
- writes `NODE_CLASS_MAPPINGS`,
- writes `NODE_DISPLAY_NAME_MAPPINGS`,
- adds a sample node class,
- adds a basic test.

`comfy_inspect_custom_node_package`:

- reads package files,
- reports discovered node classes,
- reports mapping declarations,
- reports import errors when detectable.

`comfy_validate_node_mappings`:

- checks that mappings reference existing classes,
- checks display names,
- checks duplicate keys.

`comfy_validate_node_class`:

- checks class attributes and methods commonly expected by ComfyUI nodes,
- checks input/output declaration shapes,
- checks category and function names.

`comfy_generate_node_docs`:

- generates markdown documentation for node inputs, outputs, category, and examples.

`comfy_check_node_imports`:

- attempts safe import checks in a controlled subprocess,
- returns import errors without crashing the MCP server.

### Acceptance Criteria

- A minimal custom node package can be scaffolded in workspace-local `custom_nodes/`.
- Existing custom node packages can be inspected.
- Mapping validation catches missing classes and duplicate mapping keys.
- Node class validation catches missing input declarations and missing callable function names.
- Import checking is isolated and does not modify the environment.
- Documentation generation is deterministic and test-covered.

## Milestone 4: Run Diagnostics, Output Management, Comparison, And Batch Runs

### Objective

Turn run records into useful debugging and experiment-management artifacts.

### New MCP Tools

- `comfy_diagnose_run`
- `comfy_export_run_report`
- `comfy_compare_runs`
- `comfy_list_outputs`
- `comfy_cleanup_outputs`
- `comfy_batch_submit`
- `comfy_read_batch`

### New Modules

- `src/comfydex_mcp/diagnostics.py`
- `src/comfydex_mcp/reports.py`
- `src/comfydex_mcp/outputs.py`
- `src/comfydex_mcp/batches.py`

### Run Diagnosis

`comfy_diagnose_run` should inspect:

- run status,
- WebSocket events,
- fallback polling results,
- ComfyUI history status,
- exception messages,
- missing outputs,
- workflow analysis,
- missing node types,
- missing model references where detectable.

It returns both a structured report and a short narrative summary.

### Run Report

`comfy_export_run_report` writes a markdown report under the run directory:

```text
runs/<run_id>/report.md
```

The report includes:

- run metadata,
- workflow name,
- prompt id,
- final status,
- important events,
- output files,
- diagnosis,
- workflow summary.

### Run Comparison

`comfy_compare_runs` compares two run directories:

- workflow JSON differences,
- changed node inputs,
- changed model references,
- changed output counts,
- status differences,
- timing differences when available.

The first version should avoid a complex visual graph diff. It should produce a structured semantic diff by node id and input name.

### Output Management

`comfy_list_outputs`:

- lists outputs across runs,
- includes file size, type, run id, and modified time.

`comfy_cleanup_outputs`:

- supports dry-run by default,
- can delete outputs older than a threshold or belonging to failed runs,
- must never delete outside configured `runs_dir`,
- requires an explicit `confirm=True` or equivalent parameter for deletion.

### Batch Runs

`comfy_batch_submit`:

- submits one workflow multiple times with parameter variations,
- stores a batch record,
- limits concurrency,
- records per-run status.

`comfy_read_batch`:

- reads the batch record,
- lists child run ids and statuses.

Batch record example:

```json
{
  "batch_id": "2026-06-04T10-00-00_sdxl-sweep",
  "workflow_name": "sdxl.json",
  "status": "running|completed|failed|partial",
  "runs": [
    {
      "run_id": "2026-06-04T10-00-00_sdxl-sweep-1",
      "parameters": {
        "seed": 1
      },
      "status": "completed"
    }
  ]
}
```

### Acceptance Criteria

- Failed runs produce useful diagnosis reports.
- Completed runs can export markdown reports.
- Two runs can be compared by node id and input value.
- Output listing never leaves `runs_dir`.
- Cleanup defaults to dry-run and requires explicit confirmation for deletion.
- Batch submission records each child run and handles partial failures.

## Milestone 5: Skills, Examples, Documentation, And Release Integration

### Objective

Update Codex-facing guidance and repository documentation so the new capabilities are discoverable and safe to use.

### Skill Updates

Update:

- `skills/comfyui-workflows/SKILL.md`

Add:

- `skills/comfyui-custom-nodes/SKILL.md`

### Examples

Add examples under:

```text
examples/
```

Recommended examples:

- `examples/workflows/basic_text_to_image.api.json`
- `examples/workflows/sample_ui_workflow.ui.json`
- `examples/custom_nodes/simple_math_node/`
- `examples/reports/sample_run_report.md`

### Documentation Updates

Update `README.md` with:

- version `0.2.0`,
- UI workflow import and conversion,
- workflow builder usage,
- custom node assistant usage,
- run diagnostics and batch run usage,
- safety boundaries,
- milestone-based release notes.

Add:

- `docs/usage/workflow-import.md`
- `docs/usage/workflow-builder.md`
- `docs/usage/custom-node-development.md`
- `docs/usage/run-diagnostics.md`

### Acceptance Criteria

- All new tools are documented.
- Skills describe tool order and safety boundaries.
- README explains `0.2.0` capabilities.
- Examples are valid enough for tests or fixture-based validation.
- Plugin validation passes.
- Full test suite passes.

## Cross-Cutting Data Model Changes

### Workflow Metadata

Workflow save/read results should include metadata:

```json
{
  "name": "example.api.json",
  "kind": "api|ui|unknown",
  "source": "imported|generated|converted|manual",
  "submit_ready": true,
  "validation_status": "valid|invalid|partial|unknown"
}
```

### Conversion Reports

Conversion reports should be saved when useful:

```text
workflows/.reports/<workflow-name>.conversion.json
```

### Build Plans

Build plans should be saved only when requested:

```text
workflows/.plans/<workflow-name>.plan.json
```

### Run Reports

Run reports are saved under the run directory:

```text
runs/<run_id>/report.md
```

### Batch Records

Batch records are saved under:

```text
runs/.batches/<batch_id>/batch.json
```

## Error Handling

All new tools must return actionable errors:

- UI conversion errors identify the node id and reason.
- Builder errors identify missing user inputs or unavailable node types.
- Custom node validation errors identify file path, class name, and mapping key.
- Run diagnosis errors preserve original run data and never overwrite events.
- Cleanup tools report exactly what would be deleted before deleting.
- Batch tools report partial failures without discarding successful child run records.

## Testing Strategy

### Unit Tests

Add focused tests for:

- UI workflow classification and conversion.
- conversion gap reports.
- API workflow validation against object metadata.
- workflow template selection.
- workflow build plan generation.
- workflow patching.
- custom node scaffolding.
- custom node mapping validation.
- node class validation.
- safe import checks.
- run diagnosis.
- markdown report generation.
- run comparison.
- output listing and cleanup dry-run.
- batch record creation and partial failure handling.

### Integration-Style Tests

Use mocked ComfyUI HTTP/WebSocket behavior for:

- `/object_info` variations,
- submit success and failure,
- history success and failure,
- output references,
- batch run partial failures.

### Regression Tests

Preserve all `0.1.0` tests. Add regression tests for:

- path traversal boundaries,
- header redaction,
- failed submission persistence,
- WebSocket path prefixes,
- HTTP fallback polling,
- output type directory collision prevention.

## Review Gates

Each milestone must pass:

- targeted tests,
- full test suite,
- plugin validation,
- spec compliance review,
- code quality review.

The implementation agent must not proceed to the next milestone if:

- any targeted test fails,
- full suite fails,
- plugin validation fails,
- spec review reports missing requirements,
- code quality review reports Critical or Important issues.

If a review reports only Minor issues, the implementation may proceed unless the issue affects user-facing behavior or safety boundaries.

## Release Criteria For 0.2.0

The second batch is complete when:

- Milestones 1 through 5 are implemented.
- All review gates pass.
- README is updated to `0.2.0`.
- Plugin manifest version is updated to `0.2.0`.
- Full test suite passes.
- Plugin validation passes.
- GitHub tag `v0.2.0` is created.
- GitHub release notes summarize the four capability groups.

## Risks And Mitigations

### UI Workflow Conversion Is Not Always Lossless

Mitigation:

- keep original UI workflow,
- produce conversion reports,
- avoid claiming submit-ready status unless validation passes.

### Natural-Language Workflow Generation Can Overpromise

Mitigation:

- require build plans,
- require validation,
- report assumptions and missing inputs,
- keep templates narrow in the first release.

### Custom Node Validation Can Become Too Broad

Mitigation:

- focus on package shape, mappings, imports, and common node class declarations,
- avoid trying to execute arbitrary node logic unless explicitly isolated.

### Output Cleanup Can Be Destructive

Mitigation:

- dry-run by default,
- require explicit confirmation,
- restrict deletion to `runs_dir`.

### Batch Runs Can Overload ComfyUI

Mitigation:

- default low concurrency,
- allow user-configured limit,
- record partial failures,
- do not retry indefinitely.

## Out Of Scope For This Release

- Full visual graph editor.
- Full ComfyUI UI workflow round-trip editing.
- Guaranteed conversion for every custom node.
- OAuth or browser login flows for remote ComfyUI.
- Direct installation into the user's ComfyUI custom nodes directory without explicit configuration.
- Rich media preview UI inside Codex.

## Implementation Handoff

After this design is approved, write a detailed implementation plan at:

```text
docs/superpowers/plans/2026-06-04-comfydex-second-batch-roadmap.md
```

The implementation plan must preserve the milestone gates described here. It should instruct the executor to continue automatically from one approved milestone to the next, stopping only for blockers, failed review gates, or explicit user changes.
