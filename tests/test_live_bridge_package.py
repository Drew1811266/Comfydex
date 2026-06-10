import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "custom_nodes" / "comfydex_live_bridge"
INSTALL_SCRIPT = ROOT / "scripts" / "install_live_bridge.ps1"


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

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALL_SCRIPT),
            "-ComfyCustomNodesDir",
            str(target_custom_nodes),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    installed_dir = target_custom_nodes / "comfydex_live_bridge"
    assert (installed_dir / "__init__.py").is_file()
    assert (installed_dir / "backend.py").is_file()
    assert (installed_dir / "runtime.py").is_file()
    assert (installed_dir / "web" / "comfydex_live_bridge.js").is_file()
