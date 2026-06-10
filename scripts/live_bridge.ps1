param(
    [ValidateSet("status", "push-workflow", "reload-client", "reload-backend")]
    [string]$Command = "status",

    [string]$BaseUrl = "http://127.0.0.1:8000",

    [string]$WorkflowPath = "",

    [string]$Name = "",

    [string]$Version = "",

    [switch]$Force
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
}

$result | ConvertTo-Json -Depth 100
