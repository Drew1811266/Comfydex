import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_live_bridge.ps1"


def test_verify_script_covers_p6_end_to_end_checks():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "/comfydex/live/status" in source
    assert "/comfydex/live/reload_client" in source
    assert "/comfydex/live/reload_backend" in source
    assert "/comfydex/live/load_workflow" in source
    assert "Get-LiveBridgeDiagnostics" in source
    assert "diagnostics" in source
    assert "comfyui_unreachable" in source
    assert "bridge_not_loaded" in source
    assert "bridge_status_not_ok" in source
    assert "bridge_frontend_not_listed" in source
    assert "frontend_not_connected" in source
    assert "frontend_stale" in source
    assert "workflow_ack_timeout" in source
    assert "wait_for_ack = $true" in source
    assert "Wait-LiveWorkflowAck" in source
    assert "last_workflow_result" in source
    assert "request_id" in source
    assert "ConvertFrom-Json" in source
    assert "SkipPush" in source
    assert "WorkflowPath" in source
    assert "Force" in source


def test_verify_script_is_valid_powershell():
    command = (
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        f"'{SCRIPT}', [ref]$tokens, [ref]$errors) > $null; "
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { $_.Message }; exit 1 }"
    )

    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", command],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
