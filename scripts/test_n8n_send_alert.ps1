param(
    [string]$N8nBaseUrl = $null,
    [string]$WebhookPath = "queue-metrics",
    [bool]$AlertTriggered = $true,
    [string]$AlertSeverity = "warning",
    [string]$AlertReason = "High queue length: 16 people (warning: 8)",
    [int]$PeopleInZone = 16,
    [double]$ArrivalRate = 0.15,
    [double]$ServiceRate = 0.16,
    [double]$EstimatedWaitSec = 137.4,
    [bool]$IncludeSecret = $true
)
if ($null -eq $N8nBaseUrl -or [string]::IsNullOrWhiteSpace($N8nBaseUrl)) {
    $N8nBaseUrl = $env:N8N_BASE_URL
}
if ($null -eq $N8nBaseUrl -or [string]::IsNullOrWhiteSpace($N8nBaseUrl)) {
    $N8nBaseUrl = "http://localhost:5678"
}
if ($N8nBaseUrl -notmatch '^https?://') {
    $N8nBaseUrl = "http://$N8nBaseUrl"
}
$url = "$N8nBaseUrl/webhook/$WebhookPath"
Write-Host "Posting test alert to: $url"

if (-not $AlertTriggered) {
    $PeopleInZone = 3
    $ArrivalRate = 0.05
    $ServiceRate = 0.10
    $EstimatedWaitSec = 5.0
    $AlertSeverity = "info"
    $AlertReason = "No active alert"
}

$alerts = @()
if ($AlertTriggered) {
    $alerts = @(@{
        type = if ($AlertSeverity -eq "critical") { "WAIT_TIME_CRITICAL" } else { "WAIT_TIME_WARNING" }
        severity = $AlertSeverity
        message = $AlertReason
        value = $EstimatedWaitSec
        threshold = if ($AlertSeverity -eq "critical") { 120 } else { 60 }
    })
}

$body = @{
    timestamp = (Get-Date).ToString("o")
    camera_id = "cam_01"
    zone_id = "checkout_lane_3"
    feed_id = "cashier_1"
    source = "C:/Users/ELITE/Downloads/retail_store.mp4"
    people_in_zone = $PeopleInZone
    arrival_rate = $ArrivalRate
    service_rate = $ServiceRate
    estimated_wait_sec = $EstimatedWaitSec
    arrival_rate_lower = 0.10
    arrival_rate_upper = 0.22
    service_rate_lower = 0.11
    service_rate_upper = 0.23
    wait_time_lower = 110.0
    wait_time_upper = 165.0
    uncertainty_level = "Low"
    queue_stable = -not $AlertTriggered
    alert_triggered = $AlertTriggered
    alert_reason = $AlertReason
    alert_severity = $AlertSeverity
    alerts = $alerts
    system_uptime_sec = 0
    confidence_scores = @()
    establishment_name = $null
    section_name = $null
    employee_name = $null
} | ConvertTo-Json -Depth 5
try {
    $headers = @{}
    if ($IncludeSecret -and $env:WEBHOOK_SECRET) {
        $headers['X-Webhook-Secret'] = $env:WEBHOOK_SECRET
    }
    $invokeParams = @{
        Uri = $url
        Method = 'Post'
        Body = $body
        ContentType = 'application/json'
        ErrorAction = 'Stop'
    }
    if ($headers.Count -gt 0) {
        $invokeParams['Headers'] = $headers
    }
    $resp = Invoke-RestMethod @invokeParams
    Write-Host "Response from n8n:`n" -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 5 | Out-Host
} catch {
    Write-Host "Error posting to n8n: $_" -ForegroundColor Red
    Write-Host "You can also try the curl script: scripts/test_n8n_send_alert.sh"
}
