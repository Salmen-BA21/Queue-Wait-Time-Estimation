#!/usr/bin/env bash
# Usage: N8N_BASE_URL=http://localhost:5678 ./scripts/test_n8n_send_alert.sh
N8N_BASE_URL=${N8N_BASE_URL:-}
WEBHOOK_PATH=${WEBHOOK_PATH:-queue-metrics}
if [ -z "$N8N_BASE_URL" ]; then
  read -p "Enter your n8n base URL (e.g. http://localhost:5678): " N8N_BASE_URL
fi
URL="$N8N_BASE_URL/webhook/$WEBHOOK_PATH"
echo "Posting test alert to: $URL"
cat <<EOF > /tmp/n8n_test_payload.json
{
  "alert_triggered": true,
  "alert_reason": "Automated test alert: queue exceeded",
  "alert_type": "threshold",
  "alert_severity": "critical",
  "people_in_zone": 9,
  "threshold_value": 8,
  "source": "test-script",
  "timestamp": "$(date -Iseconds)"
}
EOF
curl -s -X POST "$URL" -H "Content-Type: application/json" --data-binary @/tmp/n8n_test_payload.json | jq || true
rm -f /tmp/n8n_test_payload.json
