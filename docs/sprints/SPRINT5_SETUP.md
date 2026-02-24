# Sprint 5 Setup Guide: n8n Integration

## Quick Start

### Prerequisites
- n8n running locally on `http://localhost:5678`
- Python dependencies installed

## Sprint Goal

Complete external metric delivery for queue analytics with reliable webhook transport, structured payloads, and threshold-aware alert triggers.

## Step-by-Step Setup

### 1. n8n Webhook Configuration
1. Create workflow: `Queue-Metrics-Pipeline`
2. Add `Webhook` node (`POST`, path `queue-metrics`)
3. Copy test URL
4. Activate workflow

### 2. Python Webhook Sender Setup
Use `src/webhook_client.py` with retry logic and periodic sends in `src/main.py`.

### 3. Update Configuration
Set in `src/config.py`:
- `N8N_WEBHOOK_URL`
- `WEBHOOK_ENABLED = True`
- `WEBHOOK_SEND_INTERVAL_SEC = 5.0`

### 4. Verify Payload Delivery
Validate that n8n receives fields for:
- queue state (`people_in_zone`, stability)
- rates (`arrival_rate`, `service_rate`)
- waiting time and uncertainty bounds
- alert metadata (`alert_triggered`, reason, severity)

## Integration Scope (Sprint 5)
- webhook transport reliability
- JSON payload consistency
- CSV backup logging
- threshold detection hook-up

## Remaining Items (carried to Sprint 6)
- Telegram bot integration
- persistence checks and anti-spam rules
- interactive inline actions in notifications

---

*Migrated to sprint terminology from legacy phase setup documentation.*
