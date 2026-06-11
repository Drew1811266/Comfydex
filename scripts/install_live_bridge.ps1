param(
    [string]$ComfyBaseDir = "",
    [string]$ComfyCustomNodesDir = "",
    [string]$SourceDir = "",
    [switch]$DryRun,
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"
$BridgeVersion = "1.2.0"
$BridgeDirectoryName = "comfydex_live_bridge"

function Convert-ToJsonOutput {
    param([object]$Value)

    $Value | ConvertTo-Json -Depth 100
}

function Stop-WithJson {
    param(
        [string]$ErrorCode,
        [string]$Message,
        [hashtable]$Evidence = @{}
    )

    Convert-ToJsonOutput @{
        ok = $false
        error = $ErrorCode
        message = $Message
        evidence = $Evidence
    }
    exit 1
}

function Resolve-RequiredPath {
    param(
        [string]$PathValue,
        [string]$ErrorCode,
        [string]$Message
    )

    try {
        return (Resolve-Path -LiteralPath $PathValue).Path
    } catch {
        Stop-WithJson -ErrorCode $ErrorCode -Message $Message -Evidence @{
            path = $PathValue
            exception = $_.Exception.Message
        }
    }
}

function New-BackupPath {
    param([string]$TargetPath)

    $targetRoot = Split-Path -Parent $TargetPath
    $timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
    $baseName = "$BridgeDirectoryName.backup.$timestamp"
    $candidate = Join-Path $targetRoot $baseName
    $index = 1
    while (Test-Path -LiteralPath $candidate) {
        $candidate = Join-Path $targetRoot "$baseName.$index"
        $index += 1
    }
    return $candidate
}

function Test-ExcludedInstallPath {
    param(
        [string]$RelativePath,
        [System.IO.FileSystemInfo]$Item
    )

    $parts = $RelativePath -split '[\\/]'
    if ($parts -contains "__pycache__" -or $parts -contains ".pytest_cache") {
        return $true
    }
    if (-not $Item.PSIsContainer) {
        $extension = [System.IO.Path]::GetExtension($Item.Name).ToLowerInvariant()
        if ($extension -in @(".pyc", ".pyo")) {
            return $true
        }
    }
    return $false
}

function Copy-FilteredDirectory {
    param(
        [string]$SourcePath,
        [string]$DestinationPath
    )

    New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
    Get-ChildItem -LiteralPath $SourcePath -Force -Recurse | ForEach-Object {
        $relativePath = [System.IO.Path]::GetRelativePath($SourcePath, $_.FullName)
        if (-not (Test-ExcludedInstallPath -RelativePath $relativePath -Item $_)) {
            $destination = Join-Path $DestinationPath $relativePath
            if ($_.PSIsContainer) {
                New-Item -ItemType Directory -Path $destination -Force | Out-Null
            } else {
                $parent = Split-Path -Parent $destination
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
                Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
            }
        }
    }
}

if ([string]::IsNullOrWhiteSpace($SourceDir)) {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
    $SourceDir = Join-Path $repoRoot "custom_nodes\comfydex_live_bridge"
}

if (-not [string]::IsNullOrWhiteSpace($ComfyBaseDir)) {
    $targetRootInput = Join-Path $ComfyBaseDir "custom_nodes"
} elseif (-not [string]::IsNullOrWhiteSpace($ComfyCustomNodesDir)) {
    $targetRootInput = $ComfyCustomNodesDir
} else {
    Stop-WithJson `
        -ErrorCode "target_required" `
        -Message "Pass -ComfyBaseDir or -ComfyCustomNodesDir."
}

$sourcePath = Resolve-RequiredPath `
    -PathValue $SourceDir `
    -ErrorCode "source_not_found" `
    -Message "Comfydex Live Bridge source directory was not found."
$targetRoot = Resolve-RequiredPath `
    -PathValue $targetRootInput `
    -ErrorCode "target_not_found" `
    -Message "ComfyUI custom_nodes target directory was not found."

if ((Split-Path -Leaf $targetRoot) -ne "custom_nodes") {
    Stop-WithJson `
        -ErrorCode "target_must_be_custom_nodes" `
        -Message "The final live bridge install target root must be named custom_nodes." `
        -Evidence @{ target_root = $targetRoot }
}

$targetPath = Join-Path $targetRoot $BridgeDirectoryName
$manifestPath = Join-Path $targetRoot "$BridgeDirectoryName.install.json"
$backupPath = $null

if ((Test-Path -LiteralPath $targetPath) -and (-not $NoBackup.IsPresent)) {
    $backupPath = New-BackupPath -TargetPath $targetPath
}

$installedAt = [DateTime]::UtcNow.ToString("o")

if (-not $DryRun.IsPresent) {
    if (Test-Path -LiteralPath $targetPath) {
        if ($NoBackup.IsPresent) {
            Remove-Item -LiteralPath $targetPath -Recurse -Force
        } else {
            Move-Item -LiteralPath $targetPath -Destination $backupPath
        }
    }

    Copy-FilteredDirectory -SourcePath $sourcePath -DestinationPath $targetPath

    $manifest = @{
        version = $BridgeVersion
        installed_at = $installedAt
        source = $sourcePath
        target = $targetPath
        backup = $backupPath
    }
    $manifest | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
}

Convert-ToJsonOutput @{
    ok = $true
    version = $BridgeVersion
    target = $targetPath
    backup = $backupPath
    restart_required = $true
    dry_run = $DryRun.IsPresent
    manifest = $manifestPath
}
