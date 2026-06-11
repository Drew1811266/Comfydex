param(
    [ValidateSet("status", "push-workflow", "reload-client", "reload-backend", "verify")]
    [string]$Command = "status",

    [string]$BaseUrl = "http://127.0.0.1:8188",

    [string]$WorkflowPath = "",

    [string]$Name = "",

    [string]$Version = "",

    [switch]$Force,

    [switch]$WaitForAck,

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

function Invoke-LiveBridgePost {
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
        $status = Invoke-RestMethod -Uri (Join-UrlPath -Root $BaseUrl -Path "/comfydex/live/status") -Method Get
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
            @{
                code = "workflow_ack_timeout"
                message = "Timed out waiting for the frontend workflow acknowledgement."
                request_id = $RequestId
            }
        )
    }
}

switch ($Command) {
    "status" {
        $result = Invoke-RestMethod -Uri (Join-UrlPath -Root $BaseUrl -Path "/comfydex/live/status") -Method Get
    }
    "push-workflow" {
        if ([string]::IsNullOrWhiteSpace($WorkflowPath)) {
            throw "-WorkflowPath is required for push-workflow."
        }

        $workflowFile = Resolve-Path -LiteralPath $WorkflowPath
        $workflow = Get-Content -LiteralPath $workflowFile -Raw | ConvertFrom-Json
        $workflowName = if ([string]::IsNullOrWhiteSpace($Name)) {
            [System.IO.Path]::GetFileNameWithoutExtension($workflowFile)
        } else {
            $Name
        }

        $result = Invoke-LiveBridgePost -Path "/comfydex/live/load_workflow" -Body @{
            workflow = $workflow
            name = $workflowName
            activate = $true
            force = $Force.IsPresent
            wait_for_ack = $WaitForAck.IsPresent
        }
        if ($WaitForAck.IsPresent -and $null -ne $result.request_id) {
            $ack = Wait-LiveWorkflowAck -RequestId ([string]$result.request_id)
            $result.ok = $ack.ok
            $result | Add-Member -NotePropertyName acknowledged -NotePropertyValue $ack.acknowledged -Force
            if ($null -ne $ack.last_workflow_result) {
                $result | Add-Member -NotePropertyName last_workflow_result -NotePropertyValue $ack.last_workflow_result -Force
            }
            if ($null -ne $ack.diagnostics) {
                $result | Add-Member -NotePropertyName diagnostics -NotePropertyValue $ack.diagnostics -Force
            }
        }
    }
    "reload-client" {
        $clientVersion = if ([string]::IsNullOrWhiteSpace($Version)) {
            [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds().ToString()
        } else {
            $Version
        }

        $result = Invoke-LiveBridgePost -Path "/comfydex/live/reload_client" -Body @{
            version = $clientVersion
        }
    }
    "reload-backend" {
        $result = Invoke-LiveBridgePost -Path "/comfydex/live/reload_backend" -Body @{}
    }
    "verify" {
        $verifyScript = Join-Path $PSScriptRoot "verify_live_bridge.ps1"
        $verifyArgs = @("-BaseUrl", $BaseUrl)
        if (-not [string]::IsNullOrWhiteSpace($WorkflowPath)) {
            $verifyArgs += @("-WorkflowPath", $WorkflowPath)
        }
        if (-not [string]::IsNullOrWhiteSpace($Name)) {
            $verifyArgs += @("-Name", $Name)
        }
        if ($Force.IsPresent) {
            $verifyArgs += "-Force"
        }
        if ($SkipPush.IsPresent) {
            $verifyArgs += "-SkipPush"
        }

        & $verifyScript @verifyArgs
        exit $LASTEXITCODE
    }
}

$result | ConvertTo-Json -Depth 100
