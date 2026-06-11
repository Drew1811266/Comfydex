from comfydex_mcp.node_semantics import (
    get_node_semantics,
    list_node_semantics,
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
