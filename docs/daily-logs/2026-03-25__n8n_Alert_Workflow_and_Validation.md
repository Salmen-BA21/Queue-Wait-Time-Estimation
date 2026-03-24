# Daily Progress Log – 2026-03-25  
**Sprint:** Alerting / n8n Integration  
**Task completed:** Warning-only queue alert validation, n8n workflow alignment, and test script cleanup  

## Summary (1–2 sentences)
Aligned the queue alert pipeline with the simplified warning-only contract and verified end-to-end webhook delivery to n8n/Telegram. Also documented the alert timing behavior, confirmed the current dedupe window, and fixed the PowerShell test script parser issue so the helper is ready to commit.

## What I did today (step-by-step)
1. Reviewed the current n8n workflow export and the backend webhook payload shape to confirm the real contract being sent from the queue pipeline.
2. Reworked the n8n test payloads so they match the flat backend webhook schema instead of the older nested/critical-alert examples.
3. Updated the PowerShell and shell test helpers to post a warning-only payload with optional `X-Webhook-Secret` support.
4. Validated the updated `n8n_workflow_with_telegram.json` export and confirmed it still parses as valid JSON after the formatter and acknowledgement fixes.
5. Ran the sample video through the backend with webhook enabled and verified that the queue alert triggered correctly at the warning threshold.
6. Lowered the warning threshold to `2` for a test run and confirmed that warnings were emitted immediately when the queue exceeded the threshold.
7. Investigated alert timing and confirmed that the system triggers on the first frame above threshold, then suppresses repeated webhook delivery for 5 minutes.
8. Fixed the PowerShell script parser issue by moving environment defaulting out of the `param(...)` block and using a safe null/empty check.
9. Added this documentation entry in `docs/daily-logs/` to capture the final workflow and validation state.

## Important code / configuration

### Backend alert timing
`backend/src/threshold_detector.py`
```python
if people_in_zone > self.config.queue_length_warning:
    alerts.append(QueueAlert(
        alert_type=AlertType.QUEUE_BACKLOG,
        severity=AlertSeverity.WARNING,
        message=f"High queue length: {people_in_zone} people (warning: {self.config.queue_length_warning})",
        threshold_name="queue_length_warning",
        current_value=float(people_in_zone),
        threshold_value=float(self.config.queue_length_warning),
        frame_id=frame_id,
        timestamp=timestamp,
    ))
```

### Webhook dedupe window
`backend/src/config.py`
```python
WEBHOOK_SEND_INTERVAL_SEC: float = 5.0
ALERT_DEDUPE_WINDOW_SEC: int = 300  # 5 minutes
```

### PowerShell test helper
`scripts/test_n8n_send_alert.ps1`
```powershell
param(
    [string]$N8nBaseUrl = $null,
    [string]$WebhookPath = "queue-metrics"
)

if ($null -eq $N8nBaseUrl -or [string]::IsNullOrWhiteSpace($N8nBaseUrl)) {
    $N8nBaseUrl = $env:N8N_BASE_URL
}
if ($null -eq $N8nBaseUrl -or [string]::IsNullOrWhiteSpace($N8nBaseUrl)) {
    $N8nBaseUrl = "http://localhost:5678"
}
```

### n8n workflow formatter
`n8n_workflow_with_telegram.json`
```javascript
const d = $json.body ?? $json;
const escapeMarkdown = (value) => String(value ?? 'n/a').replace(/([_*\[\]()`])/g, '\\$1');
```

## Results / Observations
- The alert fires immediately when `people_in_zone > queue_length_warning`; it does not wait for a 5-second sustain period.
- The system then suppresses repeat webhook deliveries for the same warning for 5 minutes.
- With `--queue-length-warning 2`, the sample video triggered warning alerts as soon as the first logged frame exceeded the threshold.
- The Telegram alert arrived on the phone successfully after the workflow alignment and formatter fixes.
- The PowerShell helper is now parser-safe and ready for commit.

## Problems encountered & solutions
- **Problem:** The test helper still posted an older critical-alert payload that did not match the flattened backend contract.
  - **→ Solution:** Replaced it with a flat warning-only payload using the same keys as the backend webhook.
- **Problem:** The n8n acknowledgement node lost feed/zone context after the Telegram node.
  - **→ Solution:** Passed `feed_id` and `zone_id` forward from the formatter node and referenced them there.
- **Problem:** Telegram formatting showed underscores collapsed in the displayed queue name.
  - **→ Solution:** Escaped Markdown-sensitive characters in the n8n formatter.
- **Problem:** PowerShell diagnostics reported a parser error in `scripts/test_n8n_send_alert.ps1`.
  - **→ Solution:** Removed the environment-variable default from the `param(...)` block and applied explicit null/empty checks after parsing.

## Decisions made / Notes for later
- Kept the system in warning-only mode with queue length as the sole alert source.
- Preserved the 5-minute dedupe window to avoid repeated phone alerts on every frame.
- Kept the n8n workflow export focused on the single warning flow rather than reintroducing multi-alert routing.
- Documented the command-line test helper behavior so future runs are reproducible.

## Files modified
- `n8n_workflow_with_telegram.json` – aligned to the flat backend payload, warning-only routing, and Markdown-safe Telegram formatting.
- `scripts/test_n8n_send_alert.ps1` – updated payload and fixed the parser issue.
- `scripts/test_n8n_send_alert.sh` – updated payload to match backend contract.
- `scripts/TEST_N8N.md` – updated testing instructions.
- `backend/src/config.py` – confirmed timing constants used by the alert path.
- `backend/src/main.py` – confirmed immediate alert delivery and dedupe behavior.

## Next planned tasks
1. If desired, change the alert policy from immediate trigger to sustained trigger over a fixed duration like 5 seconds.
2. Optionally reduce or expose the 5-minute dedupe window as a tunable setting.
3. Continue testing with the sample video at realistic thresholds to choose a production warning value.

## Time spent
~2.5 hours

**Mood / feeling:** Productive