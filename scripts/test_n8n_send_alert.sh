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
  "timestamp": "$(date -Iseconds)",
  "camera_id": "cam_01",
  "zone_id": "checkout_lane_3",
  "feed_id": "cashier_1",
  "source": "C:/Users/ELITE/Downloads/retail_store.mp4",
  "people_in_zone": 16,
  "arrival_rate": 0.15,
  "service_rate": 0.16,
  "estimated_wait_sec": 137.4,
  "queue_stable": false,
  "alert_triggered": true,
  "alert_reason": "High queue length: 16 people (warning: 8)",
  "alert_severity": "warning",
  "system_uptime_sec": 0,
  "confidence_scores": [],
  "establishment_name": null,
  "section_name": null,
  "employee_name": null
}
EOF
HEADER_ARGS=()
if [ -n "$WEBHOOK_SECRET" ]; then
  HEADER_ARGS+=( -H "X-Webhook-Secret: $WEBHOOK_SECRET" )
fi
curl -s -X POST "$URL" -H "Content-Type: application/json" "${HEADER_ARGS[@]}" --data-binary @/tmp/n8n_test_payload.json | jq || true
rm -f /tmp/n8n_test_payload.json
