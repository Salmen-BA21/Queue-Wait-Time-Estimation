# Copilot Skills (Queue Wait-Time Estimation)

This folder contains workflow and domain skills used by GitHub Copilot agents.

## Key directories

- `ci-cd-validation`: CI, lint, env checks, and workflow validation scripts.
- `frontend-live-dashboard`: React/WebSocket dashboard contract and UI behavior.
- `inference-calibration`: YOLO/ByteTrack tuning, count smoothing, alert rules.
- `n8n-workflow-expert`: n8n workflow node mapping for queue alerts.
- `observability-logging`: logging, metrics, and SLO instrumentation.
- `queue-metrics-testdata`: payload fixtures and test helpers.
- `queue-system-dev`: baseline queue-system architecture and invariants.
- `queue-uncertainty-theory`: statistical model and uncertainty math.
- `webhook-security`: security hardening for self-hosted webhook ingestion.

## Using skills

1. Use `agent/runSubagent` with the right agent (e.g., `python-queue-vision-backend-dev`).
2. The agent automatically references these skills based on task context.
3. For local development, read `index.md` for quick skill links.
