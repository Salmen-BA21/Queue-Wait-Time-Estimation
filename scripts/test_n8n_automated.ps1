param(
    [string]$N8nBaseUrl = $null,
    [string]$WebhookPath = "queue-metrics",
    [string]$N8nApiKey = $null,
    [bool]$AlertTriggered = $true,
    [string]$AlertSeverity = "warning",
    [string]$AlertReason = "High queue length: 16 people (warning: 8)",
    [int]$PeopleInZone = 16,
    [int]$TimeoutSeconds = 60,
    [int]$PollIntervalSeconds = 3,
    [bool]$IncludeSecret = $true
)

if (-not $N8nBaseUrl) {
    $N8nBaseUrl = $env:N8N_BASE_URL
}
if (-not $N8nBaseUrl) {
    $N8nBaseUrl = "http://localhost:5678"
}
if ($N8nBaseUrl -notmatch '^https?://') {
    $N8nBaseUrl = "http://$N8nBaseUrl"
}
if (-not $N8nApiKey) {
    $N8nApiKey = $env:N8N_API_KEY
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$sendScript = Join-Path $PSScriptRoot "test_n8n_send_alert.ps1"
$sendStartedAt = Get-Date

Write-Host "Running automated n8n test against: $N8nBaseUrl"
Write-Host "Webhook path: $WebhookPath"
Write-Host "Polling timeout: $TimeoutSeconds seconds"

try {
    & $sendScript `
        -N8nBaseUrl $N8nBaseUrl `
        -WebhookPath $WebhookPath `
        -AlertTriggered:$AlertTriggered `
        -AlertSeverity $AlertSeverity `
        -AlertReason $AlertReason `
        -PeopleInZone $PeopleInZone `
        -IncludeSecret:$IncludeSecret
} catch {
    throw "Webhook post failed: $($_.Exception.Message)"
}

if (-not $N8nApiKey) {
    Write-Host "N8N_API_KEY is not set, so execution polling is skipped." -ForegroundColor Yellow
    Write-Host "Set N8N_API_KEY to enable execution verification."
    exit 0
}

$headers = @{ "X-N8N-API-KEY" = $N8nApiKey }
$executionUrl = "$N8nBaseUrl/api/v1/executions?limit=10"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$matchedExecution = $null

while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-RestMethod -Uri $executionUrl -Method Get -Headers $headers -ErrorAction Stop
        $executions = @()
        if ($response.data) {
            $executions = @($response.data)
        } elseif ($response.results) {
            $executions = @($response.results)
        } elseif ($response -is [System.Collections.IEnumerable] -and $response -isnot [string]) {
            $executions = @($response)
        }

        $matchedExecution = $executions | Where-Object {
            $createdAt = $null
            if ($_.createdAt) {
                try {
                    $createdAt = [datetime]$_.createdAt
                } catch {
                    $createdAt = $null
                }
            }
            if ($null -eq $createdAt) {
                return $true
            }
            return $createdAt -ge $sendStartedAt.AddSeconds(-5)
        } | Select-Object -First 1

        if ($matchedExecution) {
            break
        }
    } catch {
        Write-Host "Polling n8n executions failed: $_" -ForegroundColor Yellow
    }

    Start-Sleep -Seconds $PollIntervalSeconds
}

if (-not $matchedExecution) {
    throw "No matching execution was found within $TimeoutSeconds seconds."
}

Write-Host "Matched execution:" -ForegroundColor Green
$matchedExecution | ConvertTo-Json -Depth 8 | Out-Host

$status = $matchedExecution.status
if ($status -and $status -notin @('success', 'running', 'waiting')) {
    throw "Execution ended with unexpected status: $status"
}

Write-Host "Automated n8n test completed successfully." -ForegroundColor Green
