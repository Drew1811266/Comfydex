# UI Graph Builder

Comfydex `1.6.0` adds a UI Graph Builder for supported built-in recipes. It converts a recipe-aware workflow generation plan into a generated UI workflow that can be opened in ComfyUI's visual editor and pushed through the Live Bridge.

The UI Graph Builder is for readable graph creation, review, and canvas handoff. It is no full visual editor, does not generate arbitrary unknown custom-node graphs, and does not download models or install custom nodes.

## Tool Flow

Use these MCP tools when the user wants a ComfyUI canvas workflow from natural language:

```text
comfy_build_ui_workflow
comfy_generate_ui_workflow
comfy_generate_push_ui_workflow
comfy_read_ui_graph_history
```

`comfy_build_ui_workflow` returns a generated UI workflow without saving. Use it when Codex should inspect the readable graph, selected template, selected recipe id, missing inputs, and layout before writing a file.

`comfy_generate_ui_workflow` saves the generated UI workflow under the configured workflows directory and appends `.comfydex/ui_graph_history.jsonl`.

`comfy_generate_push_ui_workflow` saves the generated UI workflow and performs a Live Bridge push into the ComfyUI desktop canvas. It records both the saved graph and the push result in generated graph history.

`comfy_read_ui_graph_history` reads newest generated graph history entries first. Desktop uses the same history for the Generated Graphs view.

## Generated UI Workflow Shape

A generated UI workflow is ComfyUI UI JSON, not API prompt JSON. It includes:

- `nodes` with stable node ids starting at `1`,
- `links` with stable link ids starting at `1`,
- readable node titles such as `Checkpoint`, `Positive Prompt`, `Sampler`, and `Save Image`,
- deterministic positions for a readable graph layout,
- widget values resolved from generation parameters,
- `extra.comfydex.source = "generated_ui_graph"`,
- `extra.comfydex.template_id`,
- `extra.comfydex.recipe_id`.

Stable node ids and deterministic links make the graph easier to inspect, compare, save, and push repeatedly. The workflow JSON does not include timestamps; timestamps belong only in generated graph history records.

## Missing Inputs

If a plan is missing required information such as `checkpoint_name`, the builder returns `status="blocked"` and does not create a workflow. Fill the missing fields before saving or pushing.

## Live Bridge Push

Live Bridge push requires the ComfyUI-side bridge to be installed and ready. Use `comfy_live_bridge_status` or the desktop Settings view when a push fails.

The push path accepts `force=True` only when the user intentionally wants to replace the current canvas state. If the frontend reports an unsaved canvas or other safety refusal, inspect the returned `push_result` before retrying.

## Desktop Generated Graphs View

The desktop app includes a Generated Graphs view. It reads generated UI workflow history, shows workflow name, status, template id, recipe id, node count, and timestamp, then lets the user push a selected generated graph through the Python desktop bridge operation `push_ui_workflow`.

Desktop is an action/history surface for generated UI workflow records. It does not provide node dragging, visual graph editing, automatic model downloads, or automatic custom node installation.
