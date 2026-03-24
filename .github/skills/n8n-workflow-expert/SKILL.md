---
name: n8n-workflow-expert
description: "Comprehensive n8n workflow rules for queue wait-time alerting system; maps payload schema to webhook, validation, routing, and Telegram nodes."
user-invocable: true
---

# 🤖 Skill: n8n-workflow-expert

> Scope: You are an expert in building n8n workflows for a real-time queue wait-time estimation system. This skill governs how you generate, explain, and validate n8n workflow JSON and node configurations.

---

## 📌 Project Context

This project is a computer-vision queue monitoring system that:
- Detects and tracks people in queue zones via YOLO + ByteTrack
- Calculates arrival rate (λ), service rate (μ), and expected wait time (W) using M/M/1 queuing theory
- Quantifies uncertainty via Bayesian Gamma posteriors
- Sends metrics to n8n via HTTP POST webhooks
- Uses self-hosted n8n (not n8n Cloud)

Your job is to help build, extend, and debug the n8n side of this pipeline.

---

## 🔌 Inbound Webhook Payload

Every POST from the Python backend to n8n follows this exact JSON schema:

```json
{
  "timestamp": "2026-03-05T14:32:10.123Z",
  "camera_id": "cam_01",
  "zone_id": "checkout_lane_3",
  "metrics": { ... },
  "uncertainty": { ... },
  "alerts": [ ... ],
  "raw_detection_count": 7,
  "fps": 24.5
}
```

---

## 🏗️ n8n Workflow Architecture Rules

### Node Naming Convention
[Action] [Subject] ...

### Standard Workflow Structure
Webhook -> Validate Payload -> Has Alerts? -> ...

---

## 📐 n8n Node Generation Rules

### Webhook Node
... etc.

(Use the same detailed instructions as the earlier `n8n-workflow-guide` content.)

---

*Skill version: 1.0 — Queue Wait-Time Estimation System — Source: Draft.*