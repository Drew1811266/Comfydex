param(
    [string]$BaseUrl = "http://127.0.0.1:8188",

    [string]$WorkflowPath = "",

    [string]$Name = "",

    [switch]$Force,

    [switch]$SkipPush
)

$ErrorActionPreference = "Stop"

$DiagnosticMessages = @{
    comfyui_unreachable = "ComfyUI did not respond to the live bridge status request."
    bridge_not_loaded = "The Comfydex Live Bridge status route is not loaded."
    bridge_status_not_ok = "The Comfydex Live Bridge status route did not report ok=true."
    bridge_frontend_not_listed = "ComfyUI did not list the Comfydex Live Bridge frontend extension."
    frontend_not_connected = "The Comfydex Live Bridge frontend client is not connected."
    frontend_stale = "The Comfydex Live Bridge frontend client is stale."
    unsaved_canvas = "The ComfyUI canvas has unsaved changes."
    stale_client = "The Comfydex Live Bridge frontend client needs refresh."
    workflow_ack_timeout = "Timed out waiting for the frontend workflow acknowledgement."
    workflow_must_be_json_object = "Workflow must be a JSON object."
    workflow_not_ui_json = "Workflow must be a ComfyUI UI workflow JSON object."
    workflow_path_required = "Pass -WorkflowPath or use -SkipPush for status-only verification."
}

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

function New-Diagnostic {
    param(
        [string]$Code,
        [hashtable]$Evidence = @{}
    )

    return @{
        code = $Code
        message = $DiagnosticMessages[$Code]
        evidence = $Evidence
    }
}

function Get-LiveBridgeDiagnostics {
    param([object]$Status)

    $diagnostics = @()
    if ($null -ne $Status.diagnostics) {
        foreach ($diagnostic in @($Status.diagnostics)) {
            if ($null -ne $diagnostic.code) {
                $code = [string]$diagnostic.code
                $message = if ($DiagnosticMessages.ContainsKey($code)) {
                    $DiagnosticMessages[$code]
                } else {
                    [string]$diagnostic.message
                }
                $diagnostics += @{
                    code = $code
                    message = $message
                    evidence = $diagnostic
                }
            }
        }
        return $diagnostics
    }

    if ($Status.ok -ne $true) {
        $diagnostics += New-Diagnostic -Code "bridge_status_not_ok" -Evidence @{
            status = $Status
        }
    }

    $frontend = $Status.frontend
    if ($null -eq $frontend) {
        $diagnostics += New-Diagnostic -Code "frontend_not_connected"
        return $diagnostics
    }
    if ($frontend.connected -ne $true) {
        $diagnostics += New-Diagnostic -Code "frontend_not_connected"
    }
    if ($frontend.stale -eq $true) {
        $diagnostics += New-Diagnostic -Code "frontend_stale"
    }
    if ($frontend.unsaved_canvas -eq $true) {
        $diagnostics += New-Diagnostic -Code "unsaved_canvas"
    }
    if ($frontend.stale_client -eq $true) {
        $diagnostics += New-Diagnostic -Code "stale_client"
    }

    return $diagnostics
}

function Stop-WithJson {
    param(
        [string]$ErrorCode,
        [string]$Message,
        [array]$Diagnostics = @(),
        [hashtable]$Evidence = @{}
    )

    if ($Diagnostics.Count -eq 0) {
        $Diagnostics = @(New-Diagnostic -Code $ErrorCode -Evidence $Evidence)
    }

    Convert-ToJsonOutput @{
        ok = $false
        error = $ErrorCode
        message = $Message
        diagnostics = $Diagnostics
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

function Wait-LiveWorkflowAck {
    param(
        [string]$RequestId,
        [int]$TimeoutSeconds = 5
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $status = Invoke-LiveGet -Path "/comfydex/live/status"
        $lastResult = $status.last_workflow_result
        if ($null -ne $lastResult -and $lastResult.request_id -eq $RequestId) {
            return @{
                ok = ($lastResult.ok -eq $true)
                acknowledged = $true
                last_workflow_result = $lastResult
            }
        }
        Start-Sleep -Milliseconds 250
    }

    return @{
        ok = $false
        acknowledged = $false
        diagnostics = @(
            New-Diagnostic -Code "workflow_ack_timeout" -Evidence @{
                request_id = $RequestId
            }
        )
    }
}

function Get-ErrorStatusCode {
    param([object]$ErrorRecord)

    if ($ErrorRecord.Exception.Response) {
        return [int]$ErrorRecord.Exception.Response.StatusCode
    }
    return -1
}

try {
    $status = Invoke-LiveGet -Path "/comfydex/live/status"
} catch {
    $statusCode = Get-ErrorStatusCode -ErrorRecord $_
    $errorCode = if ($statusCode -eq 404) { "bridge_not_loaded" } else { "comfyui_unreachable" }
    Stop-WithJson `
        -ErrorCode $errorCode `
        -Message $DiagnosticMessages[$errorCode] `
        -Evidence @{
            status = $statusCode
            exception = $_.Exception.Message
        }
}

$diagnostics = @(Get-LiveBridgeDiagnostics -Status $status)
if ($status.ok -ne $true) {
    Stop-WithJson `
        -ErrorCode "bridge_status_not_ok" `
        -Message $DiagnosticMessages["bridge_status_not_ok"] `
        -Diagnostics $diagnostics `
        -Evidence @{ status = $status }
}

$bridgeExtensions = @()
try {
    $extensions = Invoke-LiveGet -Path "/extensions"
    $bridgeExtensions = @($extensions | Where-Object { $_ -like "*comfydex_live_bridge*" })
} catch {
    $extensions = @()
}

if ($bridgeExtensions.Count -eq 0) {
    $diagnostics += New-Diagnostic -Code "bridge_frontend_not_listed" -Evidence @{
        status = $status
    }
}

$blockingCodes = @($diagnostics | ForEach-Object { $_.code })
foreach ($code in @("bridge_frontend_not_listed", "frontend_not_connected", "frontend_stale", "unsaved_canvas", "stale_client")) {
    if ($blockingCodes -contains $code) {
        Stop-WithJson `
            -ErrorCode $code `
            -Message $DiagnosticMessages[$code] `
            -Diagnostics $diagnostics `
            -Evidence @{ status = $status }
    }
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
            -Message $DiagnosticMessages["workflow_path_required"] `
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
        wait_for_ack = $true
    }
    if ($null -ne $pushWorkflow.request_id) {
        $ack = Wait-LiveWorkflowAck -RequestId ([string]$pushWorkflow.request_id)
        $pushWorkflow.ok = $ack.ok
        $pushWorkflow | Add-Member -NotePropertyName acknowledged -NotePropertyValue $ack.acknowledged -Force
        if ($null -ne $ack.last_workflow_result) {
            $pushWorkflow | Add-Member -NotePropertyName last_workflow_result -NotePropertyValue $ack.last_workflow_result -Force
        }
        if ($null -ne $ack.diagnostics) {
            $pushWorkflow | Add-Member -NotePropertyName diagnostics -NotePropertyValue $ack.diagnostics -Force
        }
    }

    if ($pushWorkflow.ok -ne $true -or $pushWorkflow.acknowledged -ne $true) {
        $pushDiagnostics = if ($null -ne $pushWorkflow.diagnostics) {
            @($pushWorkflow.diagnostics)
        } else {
            @(New-Diagnostic -Code "workflow_ack_timeout" -Evidence @{ push_workflow = $pushWorkflow })
        }
        Stop-WithJson `
            -ErrorCode "workflow_ack_timeout" `
            -Message $DiagnosticMessages["workflow_ack_timeout"] `
            -Diagnostics $pushDiagnostics `
            -Evidence @{ push_workflow = $pushWorkflow }
    }
}

Convert-ToJsonOutput @{
    ok = $true
    status = $status
    extensions = $bridgeExtensions
    diagnostics = $diagnostics
    reload_client = $reloadClient
    reload_backend = $reloadBackend
    push_workflow = $pushWorkflow
}
