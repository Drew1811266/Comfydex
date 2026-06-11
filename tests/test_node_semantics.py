from comfydex_mcp.node_semantics import (
    get_node_semantics,
    list_node_semantics,
    match_semantics_to_object_info,
    validate_semantic_registry,
)


def test_native_registry_contains_core_text_to_image_nodes():
    entries = {entry["node_type"]: entry for entry in list_node_semantics()}

    for node_type in (
        "CheckpointLoaderSimple",
        "CLIPTextEncode",
        "EmptyLatentImage",
        "KSampler",
        "VAEDecode",
        "SaveImage",
    ):
        assert node_type in entries
        assert entries[node_type]["safe_for_user"] is True
        assert entries[node_type]["category"]
        assert entries[node_type]["purpose"]
        assert entries[node_type]["inputs"]
        assert entries[node_type]["outputs"]


def test_get_node_semantics_returns_none_for_unknown_nodes():
    assert get_node_semantics("UnknownNodeForTest") is None


def test_registry_validation_accepts_builtin_entries():
    report = validate_semantic_registry()

    assert report["status"] == "valid"
    assert report["errors"] == []
    assert report["entry_count"] >= 18


def test_match_semantics_to_object_info_reports_supported_missing_and_unknown():
    object_info = {
        "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": ("COMBO",)}}},
        "KSampler": {"input": {"required": {"model": ("MODEL",)}}},
        "UnknownCustomNode": {"input": {"required": {}}},
    }

    report = match_semantics_to_object_info(object_info)

    assert report["supported_node_types"] == ["CheckpointLoaderSimple", "KSampler"]
    assert "CLIPTextEncode" in report["missing_supported_node_types"]
    assert report["unknown_node_types"] == ["UnknownCustomNode"]
    assert report["status"] == "partial"


def test_match_semantics_to_object_info_rejects_non_mapping_payload():
    report = match_semantics_to_object_info(["not", "a", "mapping"])

    assert report["status"] == "invalid_object_info"
    assert report["supported_node_types"] == []
    assert report["unknown_node_types"] == []


def test_registry_contains_conservative_functional_pack_entries():
    entries = {entry["node_type"]: entry for entry in list_node_semantics()}

    for node_type in (
        "LoraLoader",
        "ControlNetLoader",
        "ControlNetApply",
        "UpscaleModelLoader",
        "ImageUpscaleWithModel",
        "VAELoader",
        "VAEEncodeForInpaint",
        "SetLatentNoiseMask",
    ):
        assert node_type in entries
        assert entries[node_type]["requires_external_models"] is True or node_type in {
            "ControlNetApply",
            "VAEEncodeForInpaint",
            "SetLatentNoiseMask",
        }


def test_custom_pack_entries_identify_package_when_not_native():
    entries = {entry["node_type"]: entry for entry in list_node_semantics()}

    assert entries["IPAdapterUnifiedLoader"]["custom_node_package"] == (
        "ComfyUI_IPAdapter_plus"
    )
    assert entries["IPAdapterAdvanced"]["custom_node_package"] == (
        "ComfyUI_IPAdapter_plus"
    )
    assert entries["IPAdapterUnifiedLoader"]["first_class"] is False
