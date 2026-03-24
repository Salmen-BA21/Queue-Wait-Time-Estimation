param(
    [string]$N8nBaseUrl = $env:N8N_BASE_URL,
    [string]$WebhookPath = "queue-metrics"
)
if (-not $N8nBaseUrl) {
    $N8nBaseUrl = Read-Host -Prompt "Enter your n8n base URL (e.g. http://localhost:5678)"
}
$url = "$N8nBaseUrl/webhook/$WebhookPath"
Write-Host "Posting test alert to: $url"
$body = @{
    alert_triggered = $true
    alert_reason = "Automated test alert: queue exceeded"
    alert_type = "threshold"
    alert_severity = "critical"
    people_in_zone = 9
    threshold_value = 8
    source = "test-script"
    timestamp = (Get-Date).ToString("o")
} | ConvertTo-Json -Depth 5
try {
    $resp = Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType 'application/json' -ErrorAction Stop
    Write-Host "Response from n8n:`n" -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 5 | Out-Host
} catch {
    Write-Host "Error posting to n8n: $_" -ForegroundColor Red
    Write-Host "You can also try the curl script: scripts/test_n8n_send_alert.sh"
}
