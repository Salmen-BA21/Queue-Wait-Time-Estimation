# Testing the n8n → Telegram workflow

Quick steps to test the `queue-metrics` webhook and Telegram delivery.

PowerShell (Windows):

```powershell
# option A: set env var once
$env:N8N_BASE_URL="http://localhost:5678"
.\scripts\test_n8n_send_alert.ps1

# option B: run and enter URL when prompted
.\scripts\test_n8n_send_alert.ps1
```

Shell (macOS / Linux):

```bash
# option A: one-liner
N8N_BASE_URL=http://localhost:5678 ./scripts/test_n8n_send_alert.sh

# option B: run and enter URL when prompted
./scripts/test_n8n_send_alert.sh
```

What the scripts do:
- POST a flat JSON payload that matches the backend webhook contract, including `alert_triggered=true`, `alert_reason`, and `alert_severity=warning`, to `/webhook/queue-metrics`.
- If `WEBHOOK_SECRET` is set, the scripts send it as `X-Webhook-Secret`.
- The n8n workflow should evaluate `If Alert` as true and call the Telegram node.
- Check the n8n Executions UI for node outputs and check your Telegram chat for the message.

Troubleshooting:
- Ensure n8n is running and accessible at the URL you provide.
- Ensure the workflow is active in n8n and the Telegram credential is configured.
- If no message appears, open the Workflow Execution details in n8n to inspect errors from the Telegram node.
