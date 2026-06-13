from pathlib import Path

from comfydex_mcp.generation import plan_workflow_generation
from comfydex_mcp.ui_graphs import (
    append_ui_graph_history,
    build_ui_workflow_from_plan,
    read_ui_graph_history,
    save_generated_ui_workflow,
    summarize_ui_graph,
)


TEXT_TO_IMAGE_OBJECT_INFO = {
    "CheckpointLoaderSimple": {
        "input": {"required": {"ckpt_name": ("STRING",)}},
        "output": ["MODEL", "CLIP", "VAE"],
    },
    "CLIPTextEncode": {
        "input": {"required": {"text": ("STRING",), "clip": ("CLIP",)}},
        "output": ["CONDITIONING"],
    },
    "EmptyLatentImage": {
        "input": {
            "required": {
                "width": ("INT",),
                "height": ("INT",),
                "batch_size": ("INT",),
            }
        },
        "output": ["LATENT"],
    },
    "KSampler": {
        "input": {
            "required": {
                "model": ("MODEL",),
                "seed": ("INT",),
                "steps": ("INT",),
                "cfg": ("FLOAT",),
                "sampler_name": ("STRING",),
                "scheduler": ("STRING",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent_image": ("LATENT",),
                "denoise": ("FLOAT",),
            }
        },
        "output": ["LATENT"],
    },
    "VAEDecode": {
        "input": {"required": {"samples": ("LATENT",), "vae": ("VAE",)}},
        "output": ["IMAGE"],
    },
    "SaveImage": {
        "input": {"required": {"images": ("IMAGE",), "filename_prefix": ("STRING",)}},
        "output": [],
    },
}


def test_build_ui_workflow_from_plan_creates_readable_text_to_image_graph():
    plan = plan_workflow_generation(
        "text to image",
        {"checkpoint_name": "sdxl.safetensors", "positive_prompt": "a quiet lake"},
    )

    result = build_ui_workflow_from_plan(plan, object_info=TEXT_TO_IMAGE_OBJECT_INFO)

    assert result["status"] == "valid"
    workflow = result["workflow"]
    assert workflow["last_node_id"] == 7
    assert workflow["last_link_id"] == 9
    assert workflow["extra"]["comfydex"]["template_id"] == "basic-text-to-image"
    assert [node["id"] for node in workflow["nodes"]] == [1, 2, 3, 4, 5, 6, 7]
    assert workflow["nodes"][0]["type"] == "CheckpointLoaderSimple"
    assert workflow["nodes"][0]["title"] == "Checkpoint"
    assert workflow["nodes"][0]["widgets_values"] == ["sdxl.safetensors"]
    assert workflow["nodes"][1]["widgets_values"] == ["a quiet lake"]
    assert workflow["nodes"][3]["pos"][0] > workflow["nodes"][0]["pos"][0]
    assert workflow["links"][0] == [1, 1, 0, 5, 0, "MODEL"]


def test_build_ui_workflow_reports_missing_information_without_graph():
    plan = plan_workflow_generation("text to image", {"positive_prompt": "a quiet lake"})

    result = build_ui_workflow_from_plan(plan, object_info=TEXT_TO_IMAGE_OBJECT_INFO)

    assert result["status"] == "blocked"
    assert result["workflow"] is None
    assert "checkpoint_name" in result["missing_information"]


def test_summarize_ui_graph_reports_layout_and_recipe_metadata():
    plan = plan_workflow_generation(
        "use a lora style for a portrait",
        {
            "checkpoint_name": "sdxl.safetensors",
            "lora_name": "style.safetensors",
            "positive_prompt": "portrait",
        },
    )
    result = build_ui_workflow_from_plan(plan)

    summary = summarize_ui_graph(result["workflow"])

    assert summary["node_count"] >= 7
    assert summary["link_count"] >= 9
    assert summary["template_id"] == "lora-text-to-image"
    assert summary["recipe_id"] == "text-to-image-lora"
    assert summary["has_layout"] is True


def test_build_ui_workflow_from_plan_creates_readable_inpaint_graph():
    plan = plan_workflow_generation(
        "inpaint masked area",
        {
            "checkpoint_name": "model.safetensors",
            "image": "input.png",
            "mask": "mask.png",
            "positive_prompt": "remove object",
        },
    )

    result = build_ui_workflow_from_plan(plan)

    assert result["status"] == "valid"
    assert result["summary"]["template_id"] == "inpaint-basic"
    assert result["summary"]["recipe_id"] == "inpainting-basic"
    node_types = {node["type"] for node in result["workflow"]["nodes"]}
    assert {
        "LoadImage",
        "LoadImageMask",
        "VAEEncodeForInpaint",
        "KSampler",
    }.issubset(node_types)


def test_save_generated_ui_workflow_writes_ui_json_metadata_and_history(
    tmp_path: Path,
):
    plan = plan_workflow_generation(
        "text to image",
        {"checkpoint_name": "sdxl.safetensors", "positive_prompt": "a quiet lake"},
    )

    result = save_generated_ui_workflow(
        tmp_path,
        tmp_path / "workflows",
        "lake.ui.json",
        plan,
        object_info=TEXT_TO_IMAGE_OBJECT_INFO,
    )

    assert result["status"] == "saved"
    assert result["workflow_name"] == "lake.ui.json"
    assert result["summary"]["template_id"] == "basic-text-to-image"
    assert (tmp_path / "workflows" / "lake.ui.json").exists()
    assert (
        tmp_path / "workflows" / ".metadata" / "lake.ui.metadata.json"
    ).exists()
    history = read_ui_graph_history(tmp_path)
    assert history["entries"][0]["workflow_name"] == "lake.ui.json"
    assert history["entries"][0]["template_id"] == "basic-text-to-image"
    assert history["entries"][0]["status"] == "saved"


def test_read_ui_graph_history_honors_limit(tmp_path: Path):
    append_ui_graph_history(tmp_path, {"workflow_name": "a.ui.json", "status": "saved"})
    append_ui_graph_history(tmp_path, {"workflow_name": "b.ui.json", "status": "pushed"})

    history = read_ui_graph_history(tmp_path, limit=1)

    assert history["entries"] == [{"workflow_name": "b.ui.json", "status": "pushed"}]
