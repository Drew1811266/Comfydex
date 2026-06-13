from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import ensure_directory
from .templates import get_workflow_template
from .workflows import save_workflow

NODE_TITLES = {
    "checkpoint": "Checkpoint",
    "positive_prompt": "Positive Prompt",
    "negative_prompt": "Negative Prompt",
    "latent": "Latent Size",
    "sampler": "Sampler",
    "decode": "VAE Decode",
    "save": "Save Image",
    "load_image": "Source Image",
    "mask_image": "Mask Image",
    "encode": "VAE Encode",
    "encode_inpaint": "Encode Inpaint",
    "lora": "LoRA",
    "upscale_model": "Upscale Model",
    "upscale": "Upscale Image",
    "controlnet": "ControlNet",
    "pose_image": "Pose Image",
    "apply_controlnet": "Apply ControlNet",
}

LAYOUT_COLUMNS = {
    "load_image": 0,
    "mask_image": 0,
    "pose_image": 0,
    "checkpoint": 0,
    "lora": 1,
    "positive_prompt": 1,
    "negative_prompt": 1,
    "latent": 1,
    "encode": 2,
    "encode_inpaint": 2,
    "controlnet": 2,
    "apply_controlnet": 3,
    "sampler": 3,
    "decode": 4,
    "upscale_model": 4,
    "upscale": 5,
    "save": 6,
}

FALLBACK_OUTPUT_TYPES = {
    "CheckpointLoaderSimple": ["MODEL", "CLIP", "VAE"],
    "LoraLoader": ["MODEL", "CLIP"],
    "CLIPTextEncode": ["CONDITIONING"],
    "EmptyLatentImage": ["LATENT"],
    "KSampler": ["LATENT"],
    "VAEDecode": ["IMAGE"],
    "LoadImage": ["IMAGE", "MASK"],
    "LoadImageMask": ["MASK"],
    "VAEEncode": ["LATENT"],
    "VAEEncodeForInpaint": ["LATENT"],
    "UpscaleModelLoader": ["UPSCALE_MODEL"],
    "ImageUpscaleWithModel": ["IMAGE"],
    "ControlNetLoader": ["CONTROL_NET"],
    "ControlNetApply": ["CONDITIONING"],
    "SaveImage": [],
}

HISTORY_FILENAME = "ui_graph_history.jsonl"


def save_generated_ui_workflow(
    workspace: Path,
    workflows_dir: Path,
    filename: str,
    plan: dict[str, Any],
    *,
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    build = build_ui_workflow_from_plan(plan, object_info=object_info)
    if build["status"] != "valid":
        return build

    workflow = build["workflow"]
    path = save_workflow(
        workflows_dir,
        filename,
        workflow,
        require_api=False,
        source="generated_ui_graph",
        validation_status="valid",
    )
    summary = build["summary"]
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workflow_name": filename,
        "path": str(path),
        "status": "saved",
        "template_id": summary["template_id"],
        "recipe_id": summary["recipe_id"],
        "node_count": summary["node_count"],
        "link_count": summary["link_count"],
    }
    append_ui_graph_history(workspace, record)
    return {
        "status": "saved",
        "workflow_name": filename,
        "path": str(path),
        "workflow": workflow,
        "summary": summary,
        "history_record": record,
    }


def append_ui_graph_history(workspace: Path, record: dict[str, Any]) -> dict[str, Any]:
    path = _history_path(workspace)
    ensure_directory(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def read_ui_graph_history(workspace: Path, limit: int = 20) -> dict[str, Any]:
    path = _history_path(workspace)
    if limit <= 0:
        return {"path": str(path), "entries": []}
    if not path.exists():
        return {"path": str(path), "entries": []}

    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            entries.append(value)
    return {"path": str(path), "entries": list(reversed(entries))[:limit]}


def build_ui_workflow_from_plan(
    plan: dict[str, Any],
    *,
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    missing_information = list(plan.get("missing_information") or [])
    if missing_information:
        return {
            "status": "blocked",
            "workflow": None,
            "missing_information": missing_information,
            "issues": ["missing_information"],
        }

    template_id = str(plan["selected_template_id"])
    template = get_workflow_template(template_id)
    parameters = dict(plan.get("parameters") or {})
    object_info = object_info or {}
    template_nodes = _template_nodes(template)
    template_links = _template_links(template)
    incoming_inputs = _incoming_inputs_by_key(template_links)
    key_to_id = {
        str(template_node["key"]): index
        for index, template_node in enumerate(template_nodes, start=1)
    }
    input_names_by_key = {
        str(template_node["key"]): _input_names(template_node, object_info, incoming_inputs)
        for template_node in template_nodes
    }

    nodes = [
        _ui_node(
            index,
            template_node,
            parameters,
            input_names_by_key[str(template_node["key"])],
            set(incoming_inputs.get(str(template_node["key"]), [])),
            object_info,
        )
        for index, template_node in enumerate(template_nodes, start=1)
    ]
    links = _ui_links(template_nodes, template_links, key_to_id, input_names_by_key, nodes, object_info)
    workflow = {
        "last_node_id": len(nodes),
        "last_link_id": len(links),
        "nodes": nodes,
        "links": links,
        "groups": _groups_for_nodes(nodes),
        "config": {},
        "extra": {
            "comfydex": {
                "source": "generated_ui_graph",
                "template_id": template_id,
                "recipe_id": plan.get("selected_recipe_id"),
            }
        },
        "version": 0.4,
    }
    return {
        "status": "valid",
        "workflow": workflow,
        "summary": summarize_ui_graph(workflow),
        "missing_information": [],
        "issues": [],
    }


def summarize_ui_graph(workflow: dict[str, Any]) -> dict[str, Any]:
    nodes = workflow.get("nodes", [])
    links = workflow.get("links", [])
    metadata = workflow.get("extra", {}).get("comfydex", {})
    has_layout = all(
        isinstance(node, dict)
        and isinstance(node.get("pos"), list)
        and len(node.get("pos", [])) == 2
        for node in nodes
        if isinstance(node, dict)
    )
    return {
        "node_count": len(nodes) if isinstance(nodes, list) else 0,
        "link_count": len(links) if isinstance(links, list) else 0,
        "template_id": metadata.get("template_id"),
        "recipe_id": metadata.get("recipe_id"),
        "has_layout": has_layout,
    }


def _template_nodes(template: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = template.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("template nodes must be a list")
    return [node for node in nodes if isinstance(node, dict)]


def _template_links(template: dict[str, Any]) -> list[dict[str, Any]]:
    links = template.get("links", [])
    if not isinstance(links, list):
        raise ValueError("template links must be a list")
    return [link for link in links if isinstance(link, dict)]


def _incoming_inputs_by_key(links: list[dict[str, Any]]) -> dict[str, list[str]]:
    incoming: dict[str, list[str]] = {}
    for link in links:
        target_key = link.get("to")
        input_name = link.get("input")
        if not isinstance(target_key, str) or not isinstance(input_name, str):
            continue
        incoming.setdefault(target_key, [])
        if input_name not in incoming[target_key]:
            incoming[target_key].append(input_name)
    return incoming


def _input_names(
    template_node: dict[str, Any],
    object_info: dict[str, Any],
    incoming_inputs: dict[str, list[str]],
) -> list[str]:
    node_type = str(template_node["class_type"])
    key = str(template_node["key"])
    names = _object_info_input_names(object_info.get(node_type))
    descriptors = template_node.get("inputs", {})
    if isinstance(descriptors, dict):
        for input_name in descriptors:
            if isinstance(input_name, str) and input_name not in names:
                names.append(input_name)
    for input_name in incoming_inputs.get(key, []):
        if input_name not in names:
            names.append(input_name)
    return names


def _object_info_input_names(node_info: Any) -> list[str]:
    if not isinstance(node_info, dict):
        return []
    inputs = node_info.get("input")
    if not isinstance(inputs, dict):
        return []
    names: list[str] = []
    for group in ("required", "optional"):
        grouped_inputs = inputs.get(group)
        if isinstance(grouped_inputs, dict):
            names.extend(str(name) for name in grouped_inputs)
    return names


def _ui_node(
    node_id: int,
    template_node: dict[str, Any],
    parameters: dict[str, Any],
    input_names: list[str],
    linked_inputs: set[str],
    object_info: dict[str, Any],
) -> dict[str, Any]:
    key = str(template_node["key"])
    node_type = str(template_node["class_type"])
    widgets_values = _widget_values(template_node, parameters, input_names, linked_inputs)
    return {
        "id": node_id,
        "type": node_type,
        "title": NODE_TITLES.get(key, _title_from_key(key)),
        "pos": _position_for_key(key, node_id),
        "size": [315, max(88, 54 + 24 * max(1, len(widgets_values)))],
        "flags": {},
        "order": node_id,
        "mode": 0,
        "inputs": [
            {"name": input_name, "type": _input_type(node_type, input_name, object_info), "link": None}
            for input_name in input_names
        ],
        "outputs": [
            {"name": output_type, "type": output_type, "links": [], "slot_index": slot}
            for slot, output_type in enumerate(_output_types(node_type, object_info))
        ],
        "properties": {"Node name for S&R": node_type},
        "widgets_values": widgets_values,
    }


def _widget_values(
    template_node: dict[str, Any],
    parameters: dict[str, Any],
    input_names: list[str],
    linked_inputs: set[str],
) -> list[Any]:
    descriptors = template_node.get("inputs", {})
    if not isinstance(descriptors, dict):
        return []
    values: list[Any] = []
    for input_name in input_names:
        if input_name in linked_inputs or input_name not in descriptors:
            continue
        values.append(_resolve_descriptor(descriptors[input_name], parameters))
    return values


def _resolve_descriptor(descriptor: Any, parameters: dict[str, Any]) -> Any:
    if isinstance(descriptor, dict) and set(descriptor) == {"parameter"}:
        parameter_name = descriptor["parameter"]
        if isinstance(parameter_name, str):
            return deepcopy(parameters.get(parameter_name))
    if isinstance(descriptor, dict) and set(descriptor) == {"value"}:
        return deepcopy(descriptor["value"])
    return deepcopy(descriptor)


def _ui_links(
    template_nodes: list[dict[str, Any]],
    template_links: list[dict[str, Any]],
    key_to_id: dict[str, int],
    input_names_by_key: dict[str, list[str]],
    nodes: list[dict[str, Any]],
    object_info: dict[str, Any],
) -> list[list[Any]]:
    nodes_by_id = {node["id"]: node for node in nodes}
    node_type_by_key = {
        str(template_node["key"]): str(template_node["class_type"])
        for template_node in template_nodes
    }
    links: list[list[Any]] = []
    for link_id, template_link in enumerate(template_links, start=1):
        source_key = str(template_link["from"])
        target_key = str(template_link["to"])
        input_name = str(template_link["input"])
        source_slot = int(template_link["output_slot"])
        source_id = key_to_id[source_key]
        target_id = key_to_id[target_key]
        target_slot = input_names_by_key[target_key].index(input_name)
        output_type = _output_type(node_type_by_key[source_key], source_slot, object_info)
        link = [link_id, source_id, source_slot, target_id, target_slot, output_type]
        links.append(link)
        _attach_link(nodes_by_id[source_id], nodes_by_id[target_id], link_id, source_slot, target_slot, output_type)
    return links


def _attach_link(
    source_node: dict[str, Any],
    target_node: dict[str, Any],
    link_id: int,
    source_slot: int,
    target_slot: int,
    output_type: str,
) -> None:
    outputs = source_node.setdefault("outputs", [])
    while len(outputs) <= source_slot:
        slot = len(outputs)
        outputs.append({"name": output_type, "type": output_type, "links": [], "slot_index": slot})
    outputs[source_slot].setdefault("links", []).append(link_id)
    inputs = target_node.setdefault("inputs", [])
    while len(inputs) <= target_slot:
        inputs.append({"name": f"input_{len(inputs)}", "type": output_type, "link": None})
    inputs[target_slot]["link"] = link_id


def _input_type(node_type: str, input_name: str, object_info: dict[str, Any]) -> str:
    node_info = object_info.get(node_type)
    if isinstance(node_info, dict):
        inputs = node_info.get("input")
        if isinstance(inputs, dict):
            for group in ("required", "optional"):
                grouped = inputs.get(group)
                if isinstance(grouped, dict) and input_name in grouped:
                    return _spec_type(grouped[input_name])
    return "UNKNOWN"


def _output_types(node_type: str, object_info: dict[str, Any]) -> list[str]:
    node_info = object_info.get(node_type)
    if isinstance(node_info, dict):
        outputs = node_info.get("output")
        if isinstance(outputs, list):
            return [str(output) for output in outputs]
    return list(FALLBACK_OUTPUT_TYPES.get(node_type, []))


def _output_type(node_type: str, slot: int, object_info: dict[str, Any]) -> str:
    outputs = _output_types(node_type, object_info)
    if 0 <= slot < len(outputs):
        return outputs[slot]
    return "UNKNOWN"


def _spec_type(spec: Any) -> str:
    if isinstance(spec, str):
        return spec
    if isinstance(spec, (list, tuple)) and spec:
        return str(spec[0])
    return "UNKNOWN"


def _position_for_key(key: str, node_id: int) -> list[int]:
    column = LAYOUT_COLUMNS.get(key, min(6, node_id - 1))
    row = _row_for_key(key)
    return [80 + column * 290, 80 + row * 150]


def _row_for_key(key: str) -> int:
    rows = {
        "checkpoint": 0,
        "load_image": 0,
        "mask_image": 1,
        "pose_image": 0,
        "lora": 0,
        "positive_prompt": 0,
        "negative_prompt": 1,
        "latent": 2,
        "controlnet": 1,
        "apply_controlnet": 0,
        "encode": 1,
        "encode_inpaint": 1,
        "sampler": 1,
        "decode": 1,
        "upscale_model": 0,
        "upscale": 1,
        "save": 1,
    }
    return rows.get(key, 0)


def _groups_for_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not nodes:
        return []
    return [
        {
            "title": "Comfydex Generated Graph",
            "bounding": _bounding_box(nodes),
            "color": "#2F7D6D",
            "font_size": 24,
        }
    ]


def _bounding_box(nodes: list[dict[str, Any]]) -> list[int]:
    xs = [int(node["pos"][0]) for node in nodes if isinstance(node.get("pos"), list)]
    ys = [int(node["pos"][1]) for node in nodes if isinstance(node.get("pos"), list)]
    if not xs or not ys:
        return [40, 40, 420, 260]
    return [min(xs) - 40, min(ys) - 50, max(xs) - min(xs) + 420, max(ys) - min(ys) + 230]


def _title_from_key(key: str) -> str:
    return " ".join(part.capitalize() for part in key.split("_"))


def _history_path(workspace: Path) -> Path:
    return workspace / ".comfydex" / HISTORY_FILENAME
