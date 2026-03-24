# Skill Discovery Index

This index lists available Copilot skills in this repository with paths and short descriptions.

| Skill name | Path | Description |
|---|---|---|
| ci-cd-validation | `.github/skills/ci-cd-validation/SKILL.md` | Pre-commit checks, n8n JSON validation, lint rules, env var checks, and deployment pipeline validation. |
| frontend-live-dashboard | `.github/skills/frontend-live-dashboard/SKILL.md` | Live metrics dashboard UX, WebSocket + REST contract, reconnection, and chart throttling rules. |
| inference-calibration | `.github/skills/inference-calibration/SKILL.md` | YOLO/ByteTrack tuning, counters smoothing, and alert decision mapping. |
| n8n-workflow-expert | `.github/skills/n8n-workflow-expert/SKILL.md` | n8n workflow standard for queue alert processing (webhook → validate → route → Telegram). |
| observability-logging | `.github/skills/observability-logging/SKILL.md` | JSON logging conventions, Prometheus metrics, Grafana panels, webhook retry + dead-letter queue. |
| queue-metrics-testdata | `.github/skills/queue-metrics-testdata/SKILL.md` | Payload fixtures, generators, replay sequences, and pytest helpers. |
| queue-system-dev | `.github/skills/queue-system-dev/SKILL.md` | Core queue system architecture, module mapping, and invariants. |
| queue-uncertainty-theory | `.github/skills/queue-uncertainty-theory/SKILL.md` | Bayesian CI math, queue stability, model switch, drift detection. |
| webhook-security | `.github/skills/webhook-security/SKILL.md` | Header auth/hmac/replay protection for n8n webhook ingestion. |

## Canonical workflow skill

- `queue-system-dev/n8n-workflow-guide.md` is the recommended canonical workflow guide for this project.
- `n8n-workflow-expert/SKILL.md` is an alternate path for skill-based invocation (same content).