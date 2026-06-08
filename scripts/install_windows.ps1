[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [switch]$SkipDesktopInstall,
    [switch]$SkipVerification
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Title,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Title"
    & $Command
}

$resolvedRoot = (Resolve-Path $RepoRoot).Path
Set-Location $resolvedRoot

Invoke-Step "Check Python" {
    python --version
}

Invoke-Step "Install Comfydex Python package" {
    python -m pip install -e ".[dev]"
}

if (-not $SkipDesktopInstall) {
    Invoke-Step "Install desktop dependencies" {
        npm --prefix desktop install
    }
}

if (-not $SkipVerification) {
    Invoke-Step "Validate Codex plugin manifest" {
        python scripts\validate_plugin.py
    }

    Invoke-Step "Validate release package" {
        python scripts\validate_release_package.py
    }

    Invoke-Step "Run Python test suite" {
        python -m pytest tests -q
    }

    if (-not $SkipDesktopInstall) {
        Invoke-Step "Typecheck desktop app" {
            npm --prefix desktop run typecheck
        }

        Invoke-Step "Build desktop app" {
            npm --prefix desktop run build
        }

        Invoke-Step "Check Tauri shell" {
            cargo check --manifest-path desktop\src-tauri\Cargo.toml
        }
    }
}

Write-Host ""
Write-Host "Comfydex local install complete."
Write-Host "Refresh or reinstall the local Codex plugin so Codex can discover updated MCP tools and Skills."
Write-Host "After ComfyUI is running, ask Codex to call comfy_check_connection."
