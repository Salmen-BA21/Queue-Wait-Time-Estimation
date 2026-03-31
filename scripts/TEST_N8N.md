# Testing the n8n -> Telegram workflow

Quick test guide for webhook delivery and Telegram routing.

## Prerequisites

- n8n running at `http://localhost:5678`
- Workflow `n8n_workflow_with_telegram.json` imported and active
- Optional: `WEBHOOK_SECRET` exported for header-auth branch
- Optional: `N8N_API_KEY` exported for automated execution polling

## PowerShell (Windows)

```powershell
# 1) Happy-path warning alert
$env:N8N_BASE_URL="http://localhost:5678"
.\scripts\test_n8n_send_alert.ps1

# 2) Automated send + execution polling
$env:N8N_API_KEY="your_n8n_api_key"
.\scripts\test_n8n_automated.ps1

# 3) No-alert branch
.\scripts\test_n8n_send_alert.ps1 -AlertTriggered:$false

# 4) Unauthorized branch (missing X-Webhook-Secret)
.\scripts\test_n8n_send_alert.ps1 -IncludeSecret:$false

# 5) Multi-feed scenario with configurable alert pacing
.\scripts\test_n8n_multi_feed_scenario.ps1 -AlertCooldownSeconds 120
```

## Shell (macOS / Linux)

```bash
N8N_BASE_URL=http://localhost:5678 ./scripts/test_n8n_send_alert.sh
```

## What the Scripts Validate

- POST payload delivery to `/webhook/queue-metrics`
- Header secret forwarding (`X-Webhook-Secret`) when configured
- Alert/no-alert routing behavior
- Optional execution polling using n8n API

The automated runner (`test_n8n_automated.ps1`) polls:

- `/api/v1/executions?limit=10`

using header `X-N8N-API-KEY`.

## Cooldown Note

Current `n8n_workflow_with_telegram.json` includes a per-alert cooldown in the "Check Alert Cooldown" code node and defaults to 120 seconds.

Use `-ForceTelegram:$true` in test scripts when you need to bypass cooldown behavior for validation.

## Useful Cases

- No alert: `test_n8n_send_alert.ps1 -AlertTriggered:$false`
- Unauthorized request: `test_n8n_send_alert.ps1 -IncludeSecret:$false`
- Warning: `test_n8n_send_alert.ps1 -AlertTriggered:$true -AlertSeverity warning`
- Critical: `test_n8n_send_alert.ps1 -AlertTriggered:$true -AlertSeverity critical`
- Automated end-to-end: `test_n8n_automated.ps1`

## Troubleshooting

- Ensure n8n URL is correct and reachable.
- Ensure workflow is active and credentials are configured.
- Check n8n Executions view for node-level failures.
- If polling fails, verify `N8N_API_KEY` and API access in your n8n instance.
