import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "custom_nodes" / "comfydex_live_bridge"
INSTALL_SCRIPT = ROOT / "scripts" / "install_live_bridge.ps1"


def _run_install_script(*args: str) -> dict:
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALL_SCRIPT),
            *args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def test_live_bridge_package_files_are_workspace_owned():
    assert (PACKAGE_DIR / "__init__.py").is_file()
    assert (PACKAGE_DIR / "backend.py").is_file()
    assert (PACKAGE_DIR / "runtime.py").is_file()
    assert (PACKAGE_DIR / "web" / "comfydex_live_bridge.js").is_file()


def test_live_bridge_package_exports_comfyui_metadata():
    init_source = (PACKAGE_DIR / "__init__.py").read_text(encoding="utf-8")

    assert 'WEB_DIRECTORY = "./web"' in init_source
    assert "NODE_CLASS_MAPPINGS" in init_source
    assert "NODE_DISPLAY_NAME_MAPPINGS" in init_source


def test_install_live_bridge_script_copies_package(tmp_path):
    target_custom_nodes = tmp_path / "custom_nodes"
    target_custom_nodes.mkdir()

    payload = _run_install_script(
        "-ComfyCustomNodesDir",
        str(target_custom_nodes),
    )

    assert payload["ok"] is True
    assert payload["version"] == "1.2.0"
    assert payload["restart_required"] is True
    assert payload["dry_run"] is False
    assert payload["backup"] is None
    installed_dir = target_custom_nodes / "comfydex_live_bridge"
    assert Path(payload["target"]) == installed_dir
    assert (installed_dir / "__init__.py").is_file()
    assert (installed_dir / "backend.py").is_file()
    assert (installed_dir / "runtime.py").is_file()
    assert (installed_dir / "web" / "comfydex_live_bridge.js").is_file()

    manifest_path = target_custom_nodes / "comfydex_live_bridge.install.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["version"] == "1.2.0"
    assert Path(manifest["source"]) == PACKAGE_DIR
    assert Path(manifest["target"]) == installed_dir
    assert manifest["backup"] is None


def test_install_live_bridge_script_supports_comfy_base_dir(tmp_path):
    comfy_base = tmp_path / "ComfyUI"
    target_custom_nodes = comfy_base / "custom_nodes"
    target_custom_nodes.mkdir(parents=True)

    payload = _run_install_script("-ComfyBaseDir", str(comfy_base))

    assert Path(payload["target"]).parent == target_custom_nodes
    assert (target_custom_nodes / "comfydex_live_bridge").is_dir()


def test_install_live_bridge_script_backs_up_existing_install(tmp_path):
    target_custom_nodes = tmp_path / "custom_nodes"
    target_custom_nodes.mkdir()

    first = _run_install_script("-ComfyCustomNodesDir", str(target_custom_nodes))
    assert first["backup"] is None

    marker = target_custom_nodes / "comfydex_live_bridge" / "old.txt"
    marker.write_text("old", encoding="utf-8")

    second = _run_install_script("-ComfyCustomNodesDir", str(target_custom_nodes))

    backup = Path(second["backup"])
    assert second["ok"] is True
    assert backup.is_dir()
    assert backup.name.startswith("comfydex_live_bridge.backup.")
    assert (backup / "old.txt").read_text(encoding="utf-8") == "old"
    assert (target_custom_nodes / "comfydex_live_bridge.install.json").is_file()


def test_install_live_bridge_script_no_backup_removes_existing_install(tmp_path):
    target_custom_nodes = tmp_path / "custom_nodes"
    existing = target_custom_nodes / "comfydex_live_bridge"
    existing.mkdir(parents=True)
    (existing / "old.txt").write_text("old", encoding="utf-8")

    payload = _run_install_script(
        "-ComfyCustomNodesDir",
        str(target_custom_nodes),
        "-NoBackup",
    )

    assert payload["backup"] is None
    assert not any(target_custom_nodes.glob("comfydex_live_bridge.backup.*"))
    assert not (target_custom_nodes / "comfydex_live_bridge" / "old.txt").exists()


def test_install_live_bridge_script_requires_custom_nodes_target(tmp_path):
    bad_target = tmp_path / "nodes"
    bad_target.mkdir()

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALL_SCRIPT),
            "-ComfyCustomNodesDir",
            str(bad_target),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "target_must_be_custom_nodes"
