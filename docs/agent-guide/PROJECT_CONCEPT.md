# 📚 Queue Wait-Time Estimation System – Project Concept

**Purpose:** This document explains the **complete idea** behind this project – what problem it solves, how it works, and why each component exists.

---

## 🎯 The Problem We're Solving

### Real-World Scenario
At supermarket checkouts, banks, or service centers:
- **Customers don't know how long they'll wait** before joining a queue
- **Staff can't prioritize** resource allocation (open more lanes? call for backup?)
- **Managers lack real-time data** on queue dynamics and bottlenecks

### Current Solutions Are Limited
- ❌ Manual counting is slow and inaccurate
- ❌ Simple queue counters don't predict wait times
- ❌ No uncertainty quantification = false confidence in estimates

### Our Solution
**Real-time computer vision system** that:
1. 📹 Watches video from a single camera at the queue
2. 🤖 Automatically detects people using YOLO26 AI
3. 📍 Tracks individuals as they move through the queue zone
4. 📊 Calculates arrival rate (λ), service rate (μ), and wait time (W)
5. 📈 **Provides confidence intervals** for each metric (Bayesian uncertainty)
6. 🔔 Generates alerts when thresholds are crossed
7. 📤 Sends data to n8n for further processing/alerting

---

## 🔄 How It Works End-to-End

### Step 1: Video Input
```
Camera Feed (webcam, RTSP, MP4 file)
         ↓
    Video Stream
```

### Step 2: People Detection
```
Video Frame
     ↓
[YOLO26 Neural Network] ← Detects all people in frame
     ↓
Bounding Boxes + Confidence Scores
```
- Models: nano (fast), small, medium, large, xlarge (accurate)
- Input: Each video frame
- Output: Bounding boxes for each detected person + confidence %

### Step 3: Person Tracking
```
Detections (Frame 1)
     ↓
[ByteTrack Algorithm] ← Assigns consistent IDs to people across frames
     ↓
Detections (Frame 2) with IDs
     ↓
Detections (Frame N) with IDs
```
- Tracks the same person even if they move or briefly disappear
- Prevents counting the same person twice

### Step 4: Zone Filtering
```
All Detected People
     ↓
[Is person inside queue zone polygon?]
     ↓
People In Zone (filtered list)
```
- User draws a polygon around the queue area (via GUI)
- Only people inside this zone are counted
- Each video feed can have a different zone

### Step 5: Queue Metrics Calculation
```
People In Zone (+ their entry/exit times)
     ↓
Calculate:
  • λ (lambda) = Arrival Rate = people entering/sec
  • μ (mu) = Service Rate = people exiting/sec
  • W = Wait Time = λ / (μ - λ)    [M/M/1 Queuing Theory]
     ↓
Queue Metrics
```

**Example:**
- 3 people enter per minute (λ = 0.05/sec)
- 4 people exit per minute (μ = 0.067/sec)
- Expected wait = 0.05 / (0.067 - 0.05) = **3 seconds**

### Step 6: Uncertainty Quantification (Bayesian)
```
Confidence Scores + Historical Data
     ↓
[Bayesian Gamma Distribution Analysis]
     ↓
Confidence Intervals:
  • λ ± [lower, upper]
  • μ ± [lower, upper]
  • W ± [lower, upper]
  • Uncertainty Level: Low / Medium / High
```

**Why?** Raw estimates can be noisy. We provide **95% credible intervals** so decision-makers know the confidence level.

Example:
- Point estimate: wait = 3.2 seconds
- With uncertainty: wait = 3.2 seconds **[2.1s, 4.8s]** (Medium uncertainty)

### Step 7: Alert Threshold Detection
```
Current Metrics
     ↓
[Compare against thresholds]
     ↓
Alert Types (if crossed):
  • Wait time > 60s (warning) or > 120s (critical)
  • Queue backlog > 8 people (warning) or > 15 (critical)
  • Arrival spike > 0.5/sec
  • Service degradation (rate drops below threshold)
  • High uncertainty detected
  • Queue unstable (large fluctuations)
```

### Step 8: Data Persistence & External Integration
```
Metrics → CSV File (local backup)
       → JSON → n8n Webhook → Google Sheets / Telegram / Dashboard
```

---

## 📐 The Mathematics Behind Queue Estimation

### M/M/1 Queuing Theory
We use the **M/M/1 model** (Markovian arrivals, Markovian service, 1 server):

```
Assumptions:
  • Arrivals follow Poisson distribution (random but predictable)
  • Service times are exponential (random)
  • Single queue, single service point
  
Formula:
  W = λ / (μ - λ)
  
Where:
  λ = average arrival rate (people/sec)
  μ = average service rate (people/sec)
  W = expected wait time (seconds)
  
Conditions:
  λ < μ (system must be stable)
```

### Bayesian Uncertainty
```
For λ (arrival rate):
  Prior: Gamma(α=1, β=1)  [uninformative]
  Likelihood: Count of arrivals in window
  Posterior: Gamma(α=count+1, β=window_seconds)
  
  Confidence Interval = [gamma_ppf(0.025), gamma_ppf(0.975)]
  
For W (wait time):
  Variance = σ² = historical variance of measurements
  Confidence = mean ± t_critical * SE
  Degrees of Freedom = n - 1 (for small samples)
```

---

## 🏗️ System Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    VIDEO INPUT LAYER                        │
│  (Webcam, RTSP Stream, MP4 File, Multi-source support)      │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│              PERCEPTION LAYER                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  YOLO26 Person Detector (nano/small/medium/large/xl) │   │
│  └──────────────┬───────────────────────────────────────┘   │
│                 │ (Bounding boxes + confidence)              │
│  ┌──────────────▼───────────────────────────────────────┐   │
│  │  ByteTrack Object Tracker (assigns consistent IDs)  │   │
│  └──────────────┬───────────────────────────────────────┘   │
│                 │ (People with tracked IDs)                  │
│  ┌──────────────▼───────────────────────────────────────┐   │
│  │  Zone Manager (polygon zone filtering)               │   │
│  └──────────────┬───────────────────────────────────────┘   │
│                 │ (People inside queue zone)                 │
└──────────────────┼──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│             ANALYSIS LAYER                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Queue Analyzer                                      │   │
│  │  • Arrival/exit event detection                      │   │
│  │  • λ, μ, W calculation (M/M/1 theory)               │   │
│  │  • EMA smoothing (exponential moving average)        │   │
│  └──────────────┬───────────────────────────────────────┘   │
│                 │ (Raw metrics)                               │
│  ┌──────────────▼───────────────────────────────────────┐   │
│  │  Uncertainty Quantifier (Bayesian Gamma)             │   │
│  │  • Credible intervals for λ, μ, W                    │   │
│  │  • Confidence classification (Low/Med/High)          │   │
│  │  • Detection-confidence weighting                    │   │
│  └──────────────┬───────────────────────────────────────┘   │
│                 │ (Metrics with uncertainty)                 │
│  ┌──────────────▼───────────────────────────────────────┐   │
│  │  Threshold Detector (alert generation)               │   │
│  │  • Wait time thresholds                              │   │
│  │  • Queue backlog detection                           │   │
│  │  • Arrival spike / service degradation               │   │
│  │  • Stability monitoring                              │   │
│  └──────────────┬───────────────────────────────────────┘   │
│                 │ (Alerts + classified metrics)              │
└──────────────────┼──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│           OUTPUT & INTEGRATION LAYER                        │
│  ┌──────────────┬──────────────┬──────────────┐             │
│  ▼              ▼              ▼              ▼             │
│ Display      CSV Logger    n8n Webhook   GUI Dashboard    │
│ (OpenCV)    (Backup)     (External alerts) (Live metrics) │
│  Video       CSV Files      JSON / HTTP    Tkinter        │
│  Output      Data           → Telegram/Sheets             │
│              Persistence                                   │
└───────────────────────────────────────────────────────────┘
```

---

## 💾 Data Flow Example

### Real-World Timeline

**Second 0-1:** Person A enters queue zone
- YOLO detects person A (conf=0.92)
- ByteTrack assigns ID=15
- Zone check: YES, inside
- Event: `ARRIVAL` recorded

**Second 5:** Person A still in queue, Person B enters
- λ = 1 person/5s = 0.2 people/sec
- People in zone = 2

**Second 10:** Person A exits
- Zone check: NO, outside
- Event: `EXIT` recorded
- Service time for Person A = 10 seconds

**Second 11:** System update
- λ = 2 arrivals / 11sec = 0.18 people/sec
- μ = 1 exit / 11sec = 0.09 people/sec
- **W = 0.18 / (0.09 - 0.18)** = **UNSTABLE** (μ < λ)

**Second 15:** Person C enters
- λ = 2 arrivals / 15sec = 0.13/sec
- μ = 1 exit / 15sec = 0.067/sec
- **W = 0.13 / (0.067 - 0.13)** = **NEGATIVE** (still unstable)

**After 100 seconds:** System stabilizes
- λ = 15 arrivals / 100sec = 0.15/sec
- μ = 16 exits / 100sec = 0.16/sec
- **W = 0.15 / (0.16 - 0.15) = 15 seconds** ✓

**Uncertainty calculation:**
- λ posterior = Gamma(α=15+1, β=100) → CI: [0.10, 0.22]/sec
- μ posterior = Gamma(α=16+1, β=100) → CI: [0.11, 0.23]/sec
- W uncertainty level = **MEDIUM**

---

## 🔌 Why Each Component Exists

| Component | Problem It Solves | How |
|-----------|------------------|-----|
| **YOLO26** | Need to detect people automatically | Deep learning on GPU for fast, accurate detection |
| **ByteTrack** | Need to identify same person across frames | Lightweight tracking with ID assignment |
| **Zone Manager** | Only care about queue, not entire frame | Polygon zone filtering |
| **Queue Analyzer** | Calculate metrics from tracking data | Entry/exit event detection + M/M/1 theory |
| **Uncertainty** | Raw estimates aren't trustworthy | Bayesian Gamma posteriors + confidence intervals |
| **Threshold Detector** | Need alerts for abnormal situations | Compare metrics against configurable thresholds |
| **Webhook Client** | Need external alerting (Telegram, Sheets) | HTTP POST to n8n REST API |
| **CSV Logger** | n8n might be down, data shouldn't be lost | Local CSV backup persistence |
| **GUI** | Multi-video + zone setup should be easy | Tkinter GUI with zone selector + video manager |

---

## 📊 What Gets Measured & Why

### Core Metrics
```
People In Zone      → Real-time queue length
Arrival Rate (λ)    → How fast people enter (demand signal)
Service Rate (μ)    → How fast people are served (capacity signal)
Wait Time (W)       → Expected time next customer waits
Uncertainty Level   → How confident are we in those estimates?
Queue Stable        → Are metrics fluctuating wildly?
```

### Why Uncertainty?
Decision-makers need to know:
- **"Wait time is 10 seconds"** ← sounds confident but might be wrong
- **"Wait time is 10 ± 5 seconds at 95% confidence"** ← realistic and actionable

---

## 🎯 Use Cases

### For Customers
- **"Should I join this queue?"** → Check estimated wait time before joining
- **"Is it getting better or worse?"** → See trends in wait time

### For Staff
- **"Do we need another cashier?"** → If queue_length > threshold AND wait_time > critical
- **"When will the rush end?"** → Monitor arrival rate spike alerts

### For Managers
- **"How's our service efficiency?"** → Track service rate trends
- **"What's our worst bottleneck?"** → Compare multiple queue zones
- **"Is the system reliable?"** → Review uncertainty levels across time

---

## 🚀 Why This Approach?

### Advantages
✅ **Non-intrusive** – Uses existing ceiling cameras  
✅ **Real-time** – Instant metrics, not delayed reports  
✅ **Uncertainty-aware** – Provides confidence, not false precision  
✅ **Scalable** – Can monitor multiple queues with same system  
✅ **Integrated** – Connects to external alerting (Telegram, Sheets)  
✅ **Reliable** – Local CSV backup prevents data loss  

### Limitations (Honest Assessment)
⚠️ **Occlusion** – People blocking each other aren't always detected  
⚠️ **Lighting** – Poor lighting reduces detection accuracy  
⚠️ **Crowding** – Very dense crowds → tracking ID swaps  
⚠️ **Theory assumptions** – M/M/1 assumes Poisson arrivals (real world varies)  
⚠️ **YOLO confidence** – Not always calibrated (trust intervals matter!)  

---

## 📚 Further Reading

For deeper technical details:
- **Sprint 4 Summary:** [../sprints/SPRINT4_SUMMARY.md](../sprints/SPRINT4_SUMMARY.md) – Uncertainty implementation
- **Sprint 5 Setup:** [../sprints/SPRINT5_SETUP.md](../sprints/SPRINT5_SETUP.md) – n8n integration details
- **Daily Logs:** [../daily-logs/](../daily-logs/) – Development decisions logged per sprint activity
- **Code:** Start with [../../src/main.py](../../src/main.py) to see the full pipeline

---

**Summary:** This is a **smart queue monitoring system** that uses computer vision + statistics to give real-time, confidence-aware wait time estimates.

*Last Updated: February 23, 2026*

