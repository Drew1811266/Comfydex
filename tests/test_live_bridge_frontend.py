from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "custom_nodes" / "comfydex_live_bridge" / "web"
LOADER = WEB_DIR / "comfydex_live_bridge.js"
CLIENT = WEB_DIR / "client.js"


def read(path):
    return path.read_text(encoding="utf-8")


def test_loader_uses_dynamic_import_for_cache_busted_client():
    source = read(LOADER)

    assert "app.registerExtension" in source
    assert "comfydex.live_bridge.loader" in source
    assert "api.addEventListener(\"comfydex_live_reload_client\"" in source
    assert "import(" in source
    assert "client.js?v=${version}" in source


def test_loader_disposes_previous_client_before_reloading():
    source = read(LOADER)

    assert "activeClient?.dispose?.()" in source
    assert "activeClient = await module.setup" in source


def test_client_exports_setup_and_dispose_contract():
    source = read(CLIENT)

    assert "export async function setup" in source
    assert "dispose()" in source
    assert "api.addEventListener(\"comfydex_live_load_workflow\"" in source
    assert "removeEventListener" in source


def test_client_posts_heartbeat_and_workflow_results():
    source = read(CLIENT)

    assert "/comfydex/live/frontend_status" in source
    assert "/comfydex/live/workflow_result" in source
    assert "request_id" in source
    assert "unsaved_canvas" in source
    assert "setInterval" in source
    assert "clearInterval" in source
    assert "dispose" in source


def test_client_dirty_check_runs_inside_ack_failure_path():
    source = read(CLIENT)
    function_source = source[
        source.index("async function loadWorkflowIntoCanvas") : source.index(
            "export async function setup"
        )
    ]

    assert function_source.index("try {") < function_source.index(
        "isCurrentWorkflowDirty(app)"
    )
    assert "catch (error)" in function_source
    assert 'error: "load_failed"' in function_source
    assert "await postWorkflowResult" in function_source
