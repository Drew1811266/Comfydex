import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "live_bridge.ps1"


def test_live_bridge_script_exposes_expected_commands():
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'ValidateSet("status", "push-workflow", "reload-client", "reload-backend", "verify")' in source
    assert "[switch]$WaitForAck" in source
    assert "[switch]$SkipPush" in source
    assert "/comfydex/live/status" in source
    assert "/comfydex/live/load_workflow" in source
    assert "/comfydex/live/reload_client" in source
    assert "/comfydex/live/reload_backend" in source
    assert "verify_live_bridge.ps1" in source
    assert 'verifyArgs += "-SkipPush"' in source
    assert "wait_for_ack = $WaitForAck.IsPresent" in source
    assert "Wait-LiveWorkflowAck" in source
    assert "last_workflow_result" in source
    assert "request_id" in source
    assert "Invoke-RestMethod" in source
    assert "ConvertFrom-Json" in source


def test_live_bridge_script_is_valid_powershell():
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
