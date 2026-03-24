# Legacy Phase 5 Setup Guide: n8n Integration (Sprint 5 Equivalent)

## Quick Start

### Prerequisites
- n8n running locally on `http://localhost:5678`
- Python dependencies installed

## Step-by-Step Setup

### 1. n8n Webhook Configuration (5 minutes)

**In n8n Dashboard:**

```
1. Click "New" → Select "Workflow"
2. Name it: "Queue-Metrics-Pipeline"
3. Add "Webhook" node:
   - HTTP Method: POST
   - Path: queue-metrics
   - Leave other defaults
4. Click "Test" to see webhook URL
   → Copy this URL (looks like: http://localhost:5678/webhook/...)
5. Activate workflow: Toggle "ON" in top-right
```

### 2. Python Webhook Sender Setup (5 minutes)

**In Python code:**

```python
from src.webhook_client import WebhookClient
from src.config import N8N_WEBHOOK_URL

# Initialize webhook client
client = WebhookClient(
    webhook_url=N8N_WEBHOOK_URL,  # http://localhost:5678/webhook/queue-metrics
    timeout=5.0,
    retry_count=3,
)

# Send metrics every 5 seconds (in main loop)
client.send_metrics(
    metrics=queue_metrics,
    frame_id=current_frame,
    source="video_source.mp4",
    alert_triggered=False,
)
```

### 3. Update Configuration

**In `src/config.py`:**

```python
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/queue-metrics"
WEBHOOK_ENABLED = True
WEBHOOK_SEND_INTERVAL_SEC = 5.0
```

### 4. Test Webhook Payload

```bash
cd Stage_PFE
python -c "
from src.webhook_client import WebhookClient
from src.config import N8N_WEBHOOK_URL
import json

client = WebhookClient(N8N_WEBHOOK_URL)
print('Webhook URL:', N8N_WEBHOOK_URL)
print('Client initialized successfully!')
"
```

## Payload Structure

Every webhook send includes:

```json
{
  "timestamp": 1708294800.123,
  "frame_id": 1500,
  "source": "video_file.mp4",
  "people_in_zone": 4,
  "arrival_rate": 0.133,
  "service_rate": 0.050,
  "estimated_wait_sec": 5.2,
  "arrival_rate_lower": 0.089,
  "arrival_rate_upper": 0.177,
  "service_rate_lower": 0.020,
  "service_rate_upper": 0.080,
  "wait_time_lower": 4.1,
  "wait_time_upper": 6.3,
  "uncertainty_level": "Low",
  "queue_stable": true,
  "alert_triggered": false,
  "alert_reason": "",
  "alert_severity": "info",
  "system_uptime_sec": 3600.5,
  "confidence_scores": [0.95, 0.93, 0.96, 0.94]
}
```

## n8n Processing Workflow

### Basic Flow
```
Webhook Input → Parse JSON → Store/Process → Alert (if needed)
```

### Processing Nodes

**1. Webhook Node (Trigger)**
- Receives POST data
- Converts to JSON

**2. Log/Debug Node (Optional)**
- View incoming data
- Useful for testing

**3. Alerts and Storage**
- Send notifications on conditions (Telegram recommended for quick setup)
- Persist metrics locally as CSV using the built-in backup (see `src/csv_logger.py`) if you need historical records

## Integration with Main Pipeline

### In `src/main.py` - Main Loop

```python
from src.webhook_client import WebhookClient
from src.config import N8N_WEBHOOK_URL, WEBHOOK_ENABLED, WEBHOOK_SEND_INTERVAL_SEC

# Initialize webhook client
webhook_client = WebhookClient(N8N_WEBHOOK_URL)

# In main analysis loop
last_webhook_send = time.time()

while True:
    # ... detection, tracking, analysis ...
    
    metrics = analyzer.metrics
    
    # Send to n8n every WEBHOOK_SEND_INTERVAL_SEC
    if WEBHOOK_ENABLED and (time.time() - last_webhook_send) > WEBHOOK_SEND_INTERVAL_SEC:
        webhook_client.send_metrics(
            metrics=metrics,
            frame_id=frame_count,
            source=str(args.source),
            confidence_scores=confidence_scores_in_zone,
        )
        last_webhook_send = time.time()
```

## Troubleshooting

### Webhook Not Connecting
### Processing Nodes

**1. Webhook Node (Trigger)**
- Receives POST data
- Converts to JSON

**2. Log/Debug Node (Optional)**
- View incoming data
- Useful for testing

**3. Alerts (Telegram / other)**
- Send notifications on conditions (configure Telegram/Twilio in n8n)

**Storage**
- The backend already writes CSV backups for metrics; use those for historical records or connect another persistence node if desired.
- Validate JSON with `python src/webhook.py`
- Check all required fields present
- Review logs in n8n

### n8n Not Receiving
- Ensure workflow is ACTIVATED (toggle ON)
- Check webhook URL in config matches n8n
- Add Log node to see incoming data

## Files Created

- `src/webhook.py` – Payload structure
- `src/webhook_client.py` – Webhook sender
- `n8n_workflow_template.json` – Sample n8n workflow

## Next Steps

1. Set up n8n webhook (5 min)
2. Test webhook connectivity (5 min)
3. Configure alert channels (Telegram/Twilio)
4. Add Telegram notifications
5. Test end-to-end flow

---

**Total Setup Time: ~15-20 minutes**
