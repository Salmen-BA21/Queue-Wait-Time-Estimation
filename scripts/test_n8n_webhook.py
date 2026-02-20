#!/usr/bin/env python3
"""
Simple tester for the n8n webhook endpoint used by this project.
Sends one or more JSON payloads that match the project's `QueuePayload` shape.

Usage examples:
  python scripts/test_n8n_webhook.py                       # send 1 payload to default URL
  python scripts/test_n8n_webhook.py --count 5 --interval 1  # send 5 payloads, 1s apart
  python scripts/test_n8n_webhook.py --url http://localhost:5678/webhook-test/queue-metrics

The script retries on HTTP/network errors and prints status + response body for each send.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime

import requests

DEFAULT_URL = "http://localhost:5678/webhook/queue-metrics"


def classify_uncertainty(wait, lower, upper) -> str:
    cv = (upper - lower) / max(wait, 1.0)
    if cv < 0.2:
        return "Low"
    if cv < 0.5:
        return "Medium"
    return "High"


def make_payload(i: int, source: str, rnd: bool = False) -> dict:
    now = time.time()
    if rnd:
        people = random.randint(0, 12)
    else:
        people = max(0, (i % 8))

    arrival_rate = round(max(0.0, people / 30.0 + (random.uniform(-0.02, 0.02) if rnd else 0.0)), 3)
    service_rate = round(max(0.01, arrival_rate * (0.5 + (random.random() * 0.6 if rnd else 0.1))), 3)
    estimated_wait = round(people / max(service_rate, 0.01), 1) if people > 0 else 0.0

    # +/- 20% credible intervals (simple synthetic)
    arrival_lower = round(max(0.0, arrival_rate * 0.8), 3)
    arrival_upper = round(arrival_rate * 1.2, 3)
    service_lower = round(max(0.0, service_rate * 0.8), 3)
    service_upper = round(service_rate * 1.2, 3)
    wait_lower = round(max(0.0, estimated_wait * 0.8), 1)
    wait_upper = round(estimated_wait * 1.2, 1)

    unc = classify_uncertainty(estimated_wait if estimated_wait > 0 else 1.0, wait_lower, wait_upper)

    payload = {
        "timestamp": now,
        "frame_id": i,
        "source": source,
        "people_in_zone": people,
        "arrival_rate": arrival_rate,
        "service_rate": service_rate,
        "estimated_wait_sec": estimated_wait,
        "arrival_rate_lower": arrival_lower,
        "arrival_rate_upper": arrival_upper,
        "service_rate_lower": service_lower,
        "service_rate_upper": service_upper,
        "wait_time_lower": wait_lower,
        "wait_time_upper": wait_upper,
        "uncertainty_level": unc,
        "queue_stable": people <= 5,
        "alert_triggered": False,
        "alert_message": None,
    }
    return payload


def send_payload(url: str, payload: dict, timeout: float = 5.0, max_retries: int = 3) -> requests.Response:
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            return resp
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            backoff = 2 ** attempt
            print(f"  - attempt {attempt} failed: {exc} (backoff {backoff}s)")
            time.sleep(backoff)
    
    # If we get here, all retries failed
    if last_exc:
        raise last_exc
    else:
        raise RuntimeError(f"Failed to send webhook after {max_retries} attempts")


def main() -> None:
    p = argparse.ArgumentParser(description="Send test payload(s) to n8n webhook URL")
    p.add_argument("--url", default=DEFAULT_URL, help="Webhook URL")
    p.add_argument("--count", type=int, default=1, help="Number of payloads to send")
    p.add_argument("--interval", type=float, default=0.5, help="Seconds between payloads")
    p.add_argument("--source", default="test-cam", help="source field value")
    p.add_argument("--random", action="store_true", help="randomize payload values")
    p.add_argument("--retries", type=int, default=3, help="HTTP send retries per payload")
    p.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout (seconds)")
    args = p.parse_args()

    print(f"Sending {args.count} payload(s) to {args.url} (interval={args.interval}s)")

    for i in range(1, args.count + 1):
        payload = make_payload(i, args.source, rnd=args.random)
        pretty = json.dumps(payload, sort_keys=True)
        print(f"[{i}/{args.count}] -> payload: people={payload['people_in_zone']} wait={payload['estimated_wait_sec']}s unc={payload['uncertainty_level']}")
        try:
            resp = send_payload(args.url, payload, timeout=args.timeout, max_retries=args.retries)
            print(f"   HTTP {resp.status_code} — {resp.text[:200]}")
        except Exception as exc:
            print(f"   ERROR sending payload: {exc}")
        if i < args.count:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
