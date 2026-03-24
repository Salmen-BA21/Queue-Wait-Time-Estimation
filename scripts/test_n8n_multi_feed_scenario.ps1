param(
    [string]$N8nBaseUrl = $null,
    [string]$WebhookPath = "queue-metrics",
    [int]$Rounds = 30,
    [int]$DelaySeconds = 1
)

if (-not $N8nBaseUrl) {
    if ($env:N8N_BASE_URL) {
        $N8nBaseUrl = $env:N8N_BASE_URL
    } else {
        $N8nBaseUrl = "http://localhost:5678"
    }
}

$url = "$N8nBaseUrl/webhook/$WebhookPath"
$feeds = @("cashier_1", "cashier_2", "cashier_3")

Write-Host "Starting multi-feed test:
  URL: $url
  Rounds: $Rounds
  Delay(s): $DelaySeconds
  Feeds: $($feeds -join ', ')"

for ($i=1; $i -le $Rounds; $i++) {
    foreach ($feed in $feeds) {
        $people = Get-Random -Minimum 1 -Maximum 24
        $arrival = [math]::Round((Get-Random -Minimum 0.02 -Maximum 0.7), 3)
        $service = [math]::Round((Get-Random -Minimum 0.03 -Maximum 0.8), 3)
        $wait = [math]::Round((Get-Random -Minimum 2 -Maximum 180), 1)
        $stable = $people -le 8

        $alerts = @()
        if ($wait -gt 120) {
            $alerts += @{ type = "WAIT_TIME_CRITICAL"; severity = "critical"; message = "Wait time >120"; value = $wait; threshold = 120 }
        } elseif ($wait -gt 60) {
            $alerts += @{ type = "WAIT_TIME_WARNING"; severity = "warning"; message = "Wait time >60"; value = $wait; threshold = 60 }
        }
        if ($people -gt 15) {
            $alerts += @{ type = "QUEUE_BACKLOG_CRITICAL"; severity = "critical"; message = "Queue >15"; value = $people; threshold = 15 }
        } elseif ($people -gt 8) {
            $alerts += @{ type = "QUEUE_BACKLOG_WARNING"; severity = "warning"; message = "Queue >8"; value = $people; threshold = 8 }
        }

        $payload = @{ 
            timestamp = (Get-Date).ToString("o")
            camera_id = "cam_$feed"
            zone_id = "checkout_$feed"
            source = "rtsp://stream/$feed"
            feed_id = $feed
            metrics = @{ people_in_zone = $people; arrival_rate = $arrival; service_rate = $service; wait_time_seconds = $wait; queue_stable = $stable }
            uncertainty = @{ lambda_ci = @([math]::Round($arrival - 0.03,3), [math]::Round($arrival + 0.03,3)); mu_ci = @([math]::Round($service - 0.03,3), [math]::Round($service + 0.03,3)); wait_time_ci = @([math]::Round($wait - 10,1), [math]::Round($wait + 10,1)); level = "MEDIUM" }
            alerts = $alerts
            raw_detection_count = $people
            fps = 24.5
            alert_triggered = ($alerts.Count -gt 0)
            alert_reason = if ($alerts.Count -gt 0) { $alerts[0].message } else { "none" }
            alert_severity = if ($alerts.Count -gt 0) { $alerts[0].severity } else { "info" }
        }

        $jsonBody = $payload | ConvertTo-Json -Depth 10

        try {
            $resp = Invoke-RestMethod -Uri $url -Method Post -Body $jsonBody -ContentType 'application/json' -ErrorAction Stop
            Write-Host "[$i,$feed] OK: $(if ($resp -is [string]) { $resp } else { $resp | ConvertTo-Json -Depth 5 })"
        } catch {
            Write-Host "[$i,$feed] ERROR: $_" -ForegroundColor Red
        }
    }
    Start-Sleep -Seconds $DelaySeconds
}

Write-Host "Test completed."