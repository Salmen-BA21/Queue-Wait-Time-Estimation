# 🤖 GitHub Copilot – n8n Workflow Expert

> **Scope:** You are an expert in building **n8n workflows** for a real-time queue wait-time estimation system.  
> This skill governs how you generate, explain, and validate n8n workflow JSON and node configurations.

---

## 📌 Project Context

This project is a **computer-vision queue monitoring system** that:
- Detects and tracks people in queue zones via YOLO + ByteTrack
- Calculates arrival rate (λ), service rate (μ), and expected wait time (W) using M/M/1 queuing theory
 - Calculates arrival rate (λ), service rate (μ), and expected wait time (W) using M/M/1 queuing theory
 - Uncertainty estimation is discussed in the project report but is NOT implemented in the codebase; the codebase is the single source of truth for implemented features
- Sends metrics to n8n via HTTP POST webhooks
- Uses **self-hosted n8n** (not n8n Cloud)

Your job is to help build, extend, and debug the **n8n side** of this pipeline.

---

## 🔌 Inbound Webhook Payload

Every POST from the Python backend to n8n follows this exact JSON schema (current runtime payload):

```json
{
  "timestamp": "2026-03-05T14:32:10.123Z",
  "camera_id": "cam_01",
  "zone_id": "checkout_lane_3",

  "metrics": {
    "people_in_zone": 7,
    "arrival_rate": 0.15,
    "service_rate": 0.16,
    "wait_time_seconds": 15.0,
    "queue_stable": true
  },

  "alerts": [
    {
      "type": "WAIT_TIME_WARNING",
      "severity": "warning",
      "message": "Wait time exceeded 60s threshold",
      "value": 72.3,
      "threshold": 60
    }
  ],

  "raw_detection_count": 7,
  "fps": 24.5
}
```

### Alert Types Reference

| `alert.type`              | `alert.severity` | Trigger condition                          |
|---------------------------|------------------|--------------------------------------------|
| `WAIT_TIME_WARNING`       | `warning`        | wait_time > 60s                            |
| `QUEUE_BACKLOG_WARNING`   | `warning`        | people_in_zone > 8                         |
| `ARRIVAL_SPIKE`           | `warning`        | arrival_rate > 0.5/sec                     |
| `SERVICE_DEGRADATION`     | `warning`        | service_rate dropped below threshold       |
| `HIGH_UNCERTAINTY`        | `warning`        | (only used if present in incoming payload; not produced by current codebase)                |
| `QUEUE_UNSTABLE`          | `warning`        | queue_stable == false                      |

---

## 🏗️ n8n Workflow Architecture Rules

### Node Naming Convention
Always name nodes descriptively using this pattern:
```
[Action] [Subject]
Examples:
  ✅ "Receive Queue Metrics"
  ✅ "Route by Severity"
  ✅ "Format Telegram Warning"
  ✅ "Send Telegram Alert"
  ❌ "Webhook"
  ❌ "IF1"
  ❌ "Telegram"
```

### Standard Workflow Structure
Every queue-alert workflow MUST follow this backbone:

```
Webhook (POST receiver)
    ↓
Validate Payload          ← Check required fields exist
    ↓
Has Alerts? (IF node)
    ├── NO  → Acknowledge Only (200 OK, no alert sent)
    └── YES
          ↓
        Route by Severity (Switch node)
                  └── warning → Format Warning Message → Send Telegram (Warning)
```

---

## 📐 n8n Node Generation Rules

### 1. Webhook Node
```json
{
  "parameters": {
    "httpMethod": "POST",
    "path": "queue-metrics",
    "responseMode": "lastNode",
    "options": {}
  },
  "name": "Receive Queue Metrics",
  "type": "n8n-nodes-base.webhook",
  "typeVersion": 1,
  "position": [240, 300]
}
```
- Always use `"responseMode": "lastNode"` so the final node controls the HTTP response.
- Path must match exactly what the Python backend posts to (`/webhook/queue-metrics`).

### 2. IF Node – Alert Check
Use this to gate whether any alerts exist in the payload:
```json
{
  "parameters": {
    "conditions": {
      "number": [
        {
          "value1": "={{ $json.body.alerts.length }}",
          "operation": "larger",
          "value2": 0
        }
      ]
    }
  },
  "name": "Has Alerts?",
  "type": "n8n-nodes-base.if",
  "typeVersion": 1
}
```

### 3. Switch Node – Route by Severity
```json
{
  "parameters": {
    "dataType": "string",
    "value1": "={{ $json.body.alerts[0].severity }}",
    "rules": {
      "rules": [
        { "value2": "warning" }
      ]
    },
    "fallbackOutput": "none"
  },
  "name": "Route by Severity",
  "type": "n8n-nodes-base.switch",
  "typeVersion": 1
}
```
> ⚠️ If multiple alerts exist in one payload, always loop with a **Split In Batches** or **Item Lists** node before the Switch so each alert is routed individually.

### 4. Set Node – Format Telegram Message

**For WARNING alerts:**
```json
{
  "parameters": {
    "values": {
      "string": [
        {
          "name": "message",
          "value": "={{ '⚠️ *WARNING* — ' + $json.body.zone_id + '\\n\\n' + '📍 *Alert:* ' + $json.body.alerts[0].type + '\\n' + '📊 *Value:* ' + $json.body.alerts[0].value + ' (threshold: ' + $json.body.alerts[0].threshold + ')' + '\\n' + '👥 *In Queue:* ' + $json.body.metrics.people_in_zone + ' people' + '\\n' + '⏱ *Wait Time:* ' + $json.body.metrics.wait_time_seconds + 's' + '\\n' + '🕐 ' + $json.body.timestamp }}"
        }
      ]
    }
  },
  "name": "Format Warning Message",
  "type": "n8n-nodes-base.set",
  "typeVersion": 1
}
```

### 5. Telegram Node
```json
{
  "parameters": {
    "chatId": "={{ $vars.TELEGRAM_CHAT_ID }}",
    "text": "={{ $json.message }}",
    "additionalFields": {
      "parse_mode": "Markdown"
    }
  },
  "name": "Send Telegram Alert",
  "type": "n8n-nodes-base.telegram",
  "typeVersion": 1,
  "credentials": {
    "telegramApi": {
      "id": "telegram_bot_creds",
      "name": "Queue Monitor Bot"
    }
  }
}
```

---

## 🔐 Credentials & Environment Variables

### Use n8n Variables (not hardcoded values)
Always reference secrets via `$vars.*` or n8n credential objects. Never hardcode tokens.

| Variable               | Where to set              | Used in             |
|------------------------|---------------------------|---------------------|
| `TELEGRAM_CHAT_ID`     | n8n → Settings → Variables | Telegram node       |
| `TELEGRAM_BOT_TOKEN`   | n8n → Credentials          | Telegram credential |
| `WEBHOOK_SECRET`       | n8n → Variables            | Header auth check   |

### Webhook Security (self-hosted)
Always add a **Header Auth** check right after the Webhook node to validate the `X-Webhook-Secret` header:

```json
{
  "parameters": {
    "conditions": {
      "string": [
        {
          "value1": "={{ $json.headers['x-webhook-secret'] }}",
          "operation": "equal",
          "value2": "={{ $vars.WEBHOOK_SECRET }}"
        }
      ]
    }
  },
  "name": "Validate Webhook Secret",
  "type": "n8n-nodes-base.if",
  "typeVersion": 1
}
```
- `true` branch → continue to processing
- `false` branch → **Respond to Webhook** node with `401 Unauthorized`

---

## 📨 Telegram Message Format Standards

### Alert Message Template
```
⚠️ *WARNING* — checkout_lane_3

📍 *Alert:* WAIT_TIME_WARNING
📊 *Value:* 137s  (threshold: 60s)
👥 *In Queue:* 12 people
⏱ *Wait Time:* 137.4s  [CI: 110s – 165s]
📈 *Uncertainty:* (not produced by current codebase)
🕐 2026-03-05T14:32:10Z
```

### Severity → Emoji Mapping
| Severity   | Emoji | Prefix text       |
|------------|-------|-------------------|
| `warning`  | ⚠️    | `WARNING`         |
| `info`     | ℹ️    | `INFO`            |

### Rules
- Always use Telegram **Markdown** parse mode (not HTML)
- Escape special characters: `.`, `(`, `)`, `-`, `!` with `\` in MarkdownV2
- Keep messages under **4096 characters** (Telegram limit)
- Include `camera_id` and `zone_id` in every alert so staff knows which lane

---

## 🔄 Multi-Alert Handling

When `alerts` array has more than one item, split before routing:

```
Receive Queue Metrics
    ↓
Has Alerts?
    ↓ YES
Split Alerts (Item Lists node — splits alerts array into individual items)
    ↓
Merge alert item + parent payload (Set node)
    ↓
Route by Severity (Switch)
    ↓
Format + Send
```

### Split Alerts Node
```json
{
  "parameters": {
    "fieldToSplitOut": "body.alerts",
    "include": "allOtherFields"
  },
  "name": "Split Alerts",
  "type": "n8n-nodes-base.splitOut",
  "typeVersion": 1
}
```

---

## 🧪 Testing Workflows

### Test Payload (paste into n8n's "Test Webhook" feature)
```json
{
  "timestamp": "2026-03-05T14:32:10.123Z",
  "camera_id": "cam_01",
  "zone_id": "checkout_lane_3",
  "metrics": {
    "people_in_zone": 16,
    "arrival_rate": 0.15,
    "service_rate": 0.16,
    "wait_time_seconds": 137.4,
    "queue_stable": false
  },
  /* uncertainty omitted - not produced by runtime */
  "alerts": [
    {
      "type": "WAIT_TIME_WARNING",
      "severity": "warning",
      "message": "Wait time exceeded 60s threshold",
      "value": 137.4,
      "threshold": 60
    },
    {
      "type": "QUEUE_BACKLOG_WARNING",
      "severity": "warning",
      "message": "Queue backlog exceeded 8 people threshold",
      "value": 16,
      "threshold": 8
    }
  ],
  "raw_detection_count": 16,
  "fps": 23.8
}
```

### Stable / No-Alert Payload (tests the "no alert" branch)
```json
{
  "timestamp": "2026-03-05T14:45:00.000Z",
  "camera_id": "cam_01",
  "zone_id": "checkout_lane_3",
  "metrics": {
    "people_in_zone": 3,
    "arrival_rate": 0.05,
    "service_rate": 0.10,
    "wait_time_seconds": 5.0,
    "queue_stable": true
  },
  /* uncertainty omitted - not produced by runtime */
  "alerts": [],
  "raw_detection_count": 3,
  "fps": 24.9
}
```

---

## 🐛 Common Errors & Fixes

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `Cannot read property 'alerts' of undefined` | Payload accessed as `$json.alerts` instead of `$json.body.alerts` | Webhook nodes wrap body in `.body`; always use `$json.body.*` |
| Telegram `Bad Request: can't parse entities` | Unescaped Markdown special chars | Escape `.` `(` `)` `-` or switch to plain text mode |
| Switch node only hits fallback | `alerts[0].severity` is undefined when `alerts` is empty | Always guard with the **Has Alerts?** IF node first |
| Workflow executes but no Telegram message | `chatId` is a string not a number | Telegram accepts both; check the bot was added to the chat |
| `401` on webhook from Python backend | Missing or wrong `X-Webhook-Secret` header | Set `X-Webhook-Secret` header in Python's `requests.post()` call |
| n8n self-hosted webhook not reachable | Firewall or wrong `WEBHOOK_TUNNEL_URL` env var | Set `N8N_HOST`, `N8N_PORT`, `WEBHOOK_URL` in n8n's `.env` |

---

## 📁 File Structure Convention

When generating workflow export files, use this naming pattern:

```
n8n/
├── workflows/
│   ├── queue_telegram_alerts.json        ← Main alert workflow
│   ├── queue_no_alert_ack.json           ← Stable-state acknowledgment
│   └── queue_multi_alert_splitter.json   ← Multi-alert routing
├── credentials/
│   └── README.md                         ← Instructions (never commit actual creds)
└── test-payloads/
    ├── warning_alert.json
    ├── multi_alert.json
    └── no_alert.json
```

---

## ✅ Workflow Generation Checklist

When generating any n8n workflow JSON, verify:

- [ ] Webhook node uses `responseMode: lastNode`
- [ ] Payload accessed via `$json.body.*` (not `$json.*`)
- [ ] Webhook secret validated before processing
- [ ] `Has Alerts?` IF node guards all alert routing
- [ ] Alert array split before per-alert routing (if multi-alert)
- [ ] Telegram messages use Markdown parse mode
- [ ] All secrets use `$vars.*` or credential references
- [ ] Node names follow `[Action] [Subject]` convention
- [ ] Test payload included as a comment or companion file
- [ ] Final node sends a `200 OK` response back to Python

---

*Skill version: 1.0 — Queue Wait-Time Estimation System — Self-hosted n8n — March 2026*
