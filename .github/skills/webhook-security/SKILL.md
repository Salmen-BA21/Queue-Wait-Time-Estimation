---
name: webhook-security
description: "Header auth strategies, HMAC signature verification, replay protection, and reverse-proxy hardening for the queue system's self-hosted n8n."
user-invocable: true
---

# 🔐 Skill: webhook-security

> Header auth strategies, HMAC signature verification, replay protection, and reverse-proxy hardening for the queue system's self-hosted n8n.

---

## 🧱 Security Layers (in order of application)

```
Internet / Python Backend
        │
        ▼
  [1] Reverse Proxy (nginx)       ← IP allowlist, TLS termination, rate limiting
        │
        ▼
  [2] n8n Webhook Path            ← Non-guessable path + no public listing
        │
        ▼
  [3] Header Auth Check (IF node) ← X-Webhook-Secret header validation
        │
        ▼
  [4] HMAC Signature (optional)   ← Body integrity + timestamp replay protection
        │
        ▼
  Queue Processing Logic
```

Apply all 4 layers in production. In development, layer 3 alone is acceptable.

---

## Layer 1 – nginx Reverse Proxy

### Minimal Secure Config
```nginx
# /etc/nginx/sites-available/n8n

upstream n8n_app {
    server 127.0.0.1:5678;
}

server {
    listen 443 ssl;
    server_name n8n.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/n8n.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/n8n.yourdomain.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # ── Rate limit webhook endpoint ───────────────────────────────────────────
    limit_req_zone $binary_remote_addr zone=webhook:10m rate=30r/m;

    location /webhook/ {
        limit_req zone=webhook burst=10 nodelay;

        # ── IP allowlist (add your backend server IPs) ────────────────────
        allow 10.0.0.5;     # Python backend server
        allow 10.0.0.6;     # Backup / dev machine
        deny  all;

        proxy_pass http://n8n_app;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }

    # Block everything else except the n8n UI (if needed internally)
    location / {
        return 403;
    }
}
```

### Key rules
- Always terminate TLS at nginx; never expose n8n's port 5678 directly.
- Use `allow`/`deny` to restrict to known backend IPs.
- `limit_req` prevents burst flooding (30 req/min per IP is generous for queue data).

---

## Layer 2 – Non-Guessable Webhook Path

Never use obvious paths like `/webhook/queue` or `/webhook/data`.

```
✅  /webhook/q-a3f7b29c-metrics
✅  /webhook/cam-ingest-x9k2
❌  /webhook/queue
❌  /webhook/data
❌  /webhook/alert
```

Generate a path token once:
```python
import secrets
print(secrets.token_hex(8))   # e.g. "a3f7b29c44de8f01"
```

Set this in n8n's Webhook node `path` field and never change it without updating both sides.

---

## Layer 3 – Shared Secret Header (n8n IF Node)

### Python Side – Sending the Secret
```python
# backend/src/integrations/n8n_client.py
import os, requests

N8N_WEBHOOK_URL    = os.environ["N8N_WEBHOOK_URL"]
N8N_WEBHOOK_SECRET = os.environ["N8N_WEBHOOK_SECRET"]   # e.g. "s3cr3t-k3y-abc"

def post_metrics(payload: dict) -> requests.Response:
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Secret": N8N_WEBHOOK_SECRET,
    }
    return requests.post(N8N_WEBHOOK_URL, json=payload, headers=headers, timeout=5)
```

### n8n Side – Validating the Secret
Add an IF node immediately after the Webhook node:

```json
{
  "name": "Validate Webhook Secret",
  "type": "n8n-nodes-base.if",
  "typeVersion": 1,
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
  }
}
```

- `true` branch → continue to processing
- `false` branch → **Respond to Webhook** node returning `401`:

```json
{
  "name": "Reject Unauthorized",
  "type": "n8n-nodes-base.respondToWebhook",
  "typeVersion": 1,
  "parameters": {
    "respondWith": "json",
    "responseCode": 401,
    "responseBody": "{ \"error\": \"Unauthorized\" }"
  }
}
```

---

## Layer 4 – HMAC-SHA256 Signature (Replay Protection)

### How It Works
```
Python backend:
  1. Serialize payload to JSON string
  2. Get current UTC timestamp (Unix seconds)
  3. signature = HMAC-SHA256(secret, timestamp + "." + body)
  4. Send headers: X-Signature, X-Timestamp

n8n / Python validator:
  1. Check |now - X-Timestamp| ≤ 300 seconds (5 min replay window)
  2. Recompute HMAC with same formula
  3. Compare signatures (constant-time)
```

### Python – Signing Outbound Requests
```python
import hashlib, hmac, time, json, os, requests

SECRET = os.environ["N8N_WEBHOOK_SECRET"].encode()

def _sign(body_bytes: bytes) -> tuple[str, str]:
    ts = str(int(time.time()))
    sig_input = (ts + ".").encode() + body_bytes
    sig = hmac.new(SECRET, sig_input, hashlib.sha256).hexdigest()
    return ts, sig

def post_metrics_signed(payload: dict) -> requests.Response:
    body = json.dumps(payload, separators=(",", ":")).encode()
    ts, sig = _sign(body)
    return requests.post(
        os.environ["N8N_WEBHOOK_URL"],
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Timestamp": ts,
            "X-Signature": f"sha256={sig}",
        },
        timeout=5,
    )
```

### n8n – HMAC Validation via Code Node
```javascript
// "Validate HMAC Signature" — Code node (JavaScript)
const crypto = require('crypto');

const secret    = $vars.WEBHOOK_SECRET;
const body      = JSON.stringify($json.body);
const ts        = $json.headers['x-timestamp'];
const received  = ($json.headers['x-signature'] || '').replace('sha256=', '');

// ── Replay protection ────────────────────────────────────────────────────────
const now = Math.floor(Date.now() / 1000);
if (Math.abs(now - parseInt(ts, 10)) > 300) {
  throw new Error('Request timestamp too old — possible replay attack');
}

// ── Signature check ──────────────────────────────────────────────────────────
const expected = crypto
  .createHmac('sha256', secret)
  .update(`${ts}.${body}`)
  .digest('hex');

if (!crypto.timingSafeEqual(Buffer.from(received, 'hex'), Buffer.from(expected, 'hex'))) {
  throw new Error('Invalid HMAC signature');
}

return $input.all();   // pass through if valid
```

---

## 401 vs 403 Response Patterns

| Situation | Status | Reason |
|-----------|--------|--------|
| Missing `X-Webhook-Secret` header | `401` | Authentication required |
| Wrong secret value | `401` | Authentication failed |
| Valid secret, IP not in allowlist | `403` | Forbidden (nginx blocks before n8n) |
| Valid secret, timestamp expired | `403` | Replay protection triggered |
| Valid secret, bad HMAC | `403` | Body tampered |

---

## Environment Variables Reference

| Variable | Where set | Example |
|----------|-----------|---------|
| `N8N_WEBHOOK_SECRET` | n8n Settings → Variables AND Python `.env` | `s3cr3t-k3y-abc` |
| `N8N_WEBHOOK_URL` | Python `.env` | `https://n8n.yourdomain.com/webhook/q-a3f7b29c-metrics` |
| `N8N_HOST` | n8n Docker `.env` | `n8n.yourdomain.com` |
| `N8N_PORT` | n8n Docker `.env` | `5678` |
| `N8N_PROTOCOL` | n8n Docker `.env` | `https` |
| `WEBHOOK_URL` | n8n Docker `.env` | `https://n8n.yourdomain.com/` |

### Docker `.env` for self-hosted n8n
```env
N8N_HOST=n8n.yourdomain.com
N8N_PORT=5678
N8N_PROTOCOL=https
WEBHOOK_URL=https://n8n.yourdomain.com/
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=strongpassword123
```

---

## Security Checklist

- [ ] TLS enabled (Let's Encrypt via certbot or similar)
- [ ] Webhook path contains a random token (not guessable)
- [ ] `X-Webhook-Secret` header validated in first n8n IF node
- [ ] Unauthorized requests return 401 immediately (no further processing)
- [ ] nginx IP allowlist restricts to known backend IPs
- [ ] Rate limiting configured at nginx (`limit_req`)
- [ ] Secrets in n8n Variables or env vars — never hardcoded in nodes
- [ ] HMAC signature used in production (Layer 4)
- [ ] Replay window ≤ 5 minutes enforced
- [ ] n8n admin UI not exposed publicly (firewall rule or separate vhost)

---

*Skill version: 1.0 — Queue Wait-Time Estimation System — Self-hosted n8n — March 2026*