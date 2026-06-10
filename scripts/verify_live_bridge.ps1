param(
    [string]$BaseUrl = "http://127.0.0.1:8000",

    [string]$WorkflowPath = "",

    [string]$Name = "",

    [switch]$Force,

    [switch]$SkipPush
)

$ErrorActionPreference = "Stop"

function Join-UrlPath {
    param(
        [string]$Root,
        [string]$Path
    )

    return $Root.TrimEnd("/") + $Path
}

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

function Invoke-LiveGet {
    param([string]$Path)

    return Invoke-RestMethod -Uri (Join-UrlPath -Root $BaseUrl -Path $Path) -Method Get
}

function Invoke-LivePost {
    param(
        [string]$Path,
        [hashtable]$Body
    )

    $json = $Body | ConvertTo-Json -Depth 100
    return Invoke-RestMethod `
        -Uri (Join-UrlPath -Root $BaseUrl -Path $Path) `
        -Method Post `
        -ContentType "application/json" `
        -Body $json
}

try {
    $status = Invoke-LiveGet -Path "/comfydex/live/status"
} catch {
    $statusCode = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { -1 }
    Stop-WithJson `
        -ErrorCode "bridge_not_loaded" `
        -Message "Comfydex Live Bridge is not loaded by the running ComfyUI process." `
        -Evidence @{
            status = $statusCode
            exception = $_.Exception.Message
        }
}

if (-not $status.ok) {
    Stop-WithJson `
        -ErrorCode "bridge_status_not_ok" `
        -Message "Comfydex Live Bridge status endpoint responded but did not report ok=true." `
        -Evidence @{ status = $status }
}

$extensions = Invoke-LiveGet -Path "/extensions"
$bridgeExtensions = @($extensions | Where-Object { $_ -like "*comfydex_live_bridge*" })

if ($bridgeExtensions.Count -eq 0) {
    Stop-WithJson `
        -ErrorCode "bridge_frontend_not_listed" `
        -Message "ComfyUI did not list the Comfydex Live Bridge frontend extension." `
        -Evidence @{ status = $status }
}

$version = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds().ToString()
$reloadClient = Invoke-LivePost -Path "/comfydex/live/reload_client" -Body @{
    version = $version
}
$reloadBackend = Invoke-LivePost -Path "/comfydex/live/reload_backend" -Body @{}

$pushWorkflow = $null
if (-not $SkipPush.IsPresent) {
    if ([string]::IsNullOrWhiteSpace($WorkflowPath)) {
        Stop-WithJson `
            -ErrorCode "workflow_path_required" `
            -Message "Pass -WorkflowPath or use -SkipPush for status-only verification." `
            -Evidence @{ status = $status }
    }

    $workflowFile = Resolve-Path -LiteralPath $WorkflowPath
    $workflow = Get-Content -LiteralPath $workflowFile -Raw | ConvertFrom-Json
    $workflowName = if ([string]::IsNullOrWhiteSpace($Name)) {
        [System.IO.Path]::GetFileNameWithoutExtension($workflowFile)
    } else {
        $Name
    }

    $pushWorkflow = Invoke-LivePost -Path "/comfydex/live/load_workflow" -Body @{
        workflow = $workflow
        name = $workflowName
        activate = $true
        force = $Force.IsPresent
    }
}

Convert-ToJsonOutput @{
    ok = $true
    status = $status
    extensions = $bridgeExtensions
    reload_client = $reloadClient
    reload_backend = $reloadBackend
    push_workflow = $pushWorkflow
}
