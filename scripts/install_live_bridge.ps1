param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyCustomNodesDir,

    [string]$SourceDir = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceDir)) {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
    $SourceDir = Join-Path $repoRoot "custom_nodes\comfydex_live_bridge"
}

$sourcePath = Resolve-Path -LiteralPath $SourceDir
$targetRoot = Resolve-Path -LiteralPath $ComfyCustomNodesDir
$targetPath = Join-Path $targetRoot "comfydex_live_bridge"

if (Test-Path -LiteralPath $targetPath) {
    Remove-Item -LiteralPath $targetPath -Recurse -Force
}

Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Recurse -Force

Write-Output "Installed Comfydex Live Bridge to $targetPath"
