#!/usr/bin/env bash
# Usage: N8N_BASE_URL=http://localhost:5678 ./scripts/poll_n8n_executions.sh
N8N_BASE_URL=${N8N_BASE_URL:-}
N8N_API_KEY=${N8N_API_KEY:-}
if [ -z "$N8N_BASE_URL" ]; then
  read -p "Enter your n8n base URL (e.g. http://localhost:5678): " N8N_BASE_URL
fi
URL="$N8N_BASE_URL/api/v1/executions?limit=1"
echo "Querying n8n executions: $URL"
AUTH_HEADER=()
if [ -n "$N8N_API_KEY" ]; then
  AUTH_HEADER=( -H "X-N8N-API-KEY: $N8N_API_KEY" )
fi
# Try to fetch and print the first execution
RESP=$(curl -s "${AUTH_HEADER[@]}" -X GET "$URL")
if [ -z "$RESP" ]; then
  echo "No response from n8n." >&2
  exit 1
fi
# Try to pretty print
if command -v jq >/dev/null 2>&1; then
  echo "$RESP" | jq '.'
else
  echo "$RESP"
fi
