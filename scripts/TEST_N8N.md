# Testing the n8n → Telegram workflow

Quick steps to test the `queue-metrics` webhook and Telegram delivery.

PowerShell (Windows):

```powershell
# Happy path warning alert
$env:N8N_BASE_URL="http://localhost:5678"
.\scripts\test_n8n_send_alert.ps1

# Fully automated send + execution poll
$env:N8N_API_KEY="your_n8n_api_key"
.\scripts\test_n8n_automated.ps1

# No-alert branch
.\scripts\test_n8n_send_alert.ps1 -AlertTriggered:$false

# Unauthorized branch
.\scripts\test_n8n_send_alert.ps1 -IncludeSecret:$false

# Multi-feed run with a 2 minute cooldown between alert posts
.\scripts\test_n8n_multi_feed_scenario.ps1 -AlertCooldownSeconds 120
```

Shell (macOS / Linux):

```bash
# option A: one-liner
N8N_BASE_URL=http://localhost:5678 ./scripts/test_n8n_send_alert.sh

# option B: run and enter URL when prompted
./scripts/test_n8n_send_alert.sh
```

What the scripts do:
- POST webhook payloads that cover the alert, no-alert, and multi-alert shapes used by the queue system.
- If `WEBHOOK_SECRET` is set and secret sending is enabled, the scripts send it as `X-Webhook-Secret`.
- The n8n workflow now suppresses repeated alerts for the same lane and alert type for 2 minutes so Telegram does not get spammed.
- The new automated runner posts the payload and then polls `/rest/executions` with `N8N_API_KEY` until a matching execution appears.
- Check the n8n Executions UI for node outputs and check your Telegram chat for the message.

Useful test cases:
- No-alert branch: `test_n8n_send_alert.ps1 -AlertTriggered:$false`
- Unauthorized request: `test_n8n_send_alert.ps1 -IncludeSecret:$false`
- Warning alert: `test_n8n_send_alert.ps1 -AlertTriggered:$true -AlertSeverity warning`
- Critical alert: `test_n8n_send_alert.ps1 -AlertTriggered:$true -AlertSeverity critical`
- Multi-feed pacing: `test_n8n_multi_feed_scenario.ps1 -AlertCooldownSeconds 120`
- Automated end-to-end test: `test_n8n_automated.ps1` with `N8N_API_KEY`

Troubleshooting:
- Ensure n8n is running and accessible at the URL you provide.
- Ensure the workflow is active in n8n and the Telegram credential is configured.
- If no message appears, open the Workflow Execution details in n8n to inspect errors from the Telegram node.
