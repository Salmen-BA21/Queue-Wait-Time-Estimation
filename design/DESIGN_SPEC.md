# 🎨 QueueVision Web Application – Complete Design Specification

**Design File:** `pencil-new.pen` (Pencil MCP format)  
**Total Pages:** 7  
**Canvas Size:** 1440 × 900 px per page  
**Created:** February 27, 2026  
**Style Guide:** Terminal Minimal  

---

## 📋 Table of Contents

1. [Design System](#-design-system)
2. [Page 1 – Landing Page](#page-1--landing-page)
3. [Page 2 – Dashboard](#page-2--dashboard)
4. [Page 3 – Setup Wizard](#page-3--setup-wizard)
5. [Page 4 – Zone Editor](#page-4--zone-editor)
6. [Page 5 – Historical Analytics](#page-5--historical-analytics)
7. [Page 6 – Settings / Config](#page-6--settings--config)
8. [Page 7 – Heatmap Overlay](#page-7--heatmap-overlay)
9. [Implementation Notes](#-implementation-notes)

---

## 🎨 Design System

### Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-primary` | `#0A0F1C` | Page background, root canvas |
| `--bg-card` | `#1E293B` | Cards, panels, sidebar surfaces |
| `--bg-card-alt` | `#0F172A` | Alternate card backgrounds, metric strips |
| `--border-default` | `#334155` | Card borders, dividers, input borders |
| `--accent-cyan` | `#22D3EE` | Primary accent – buttons, links, active states, highlights |
| `--accent-amber` | `#F59E0B` | Warning states, zone editor badge, caution alerts |
| `--accent-red` | `#EF4444` | Critical alerts, heatmap badge, error states |
| `--accent-purple` | `#A78BFA` | Uncertainty metrics, analytics badge |
| `--accent-green` | `#10B981` | Success states, "online" indicators, positive trends |
| `--text-primary` | `#F1F5F9` | Headings, primary text |
| `--text-secondary` | `#94A3B8` | Body text, labels, descriptions |
| `--text-muted` | `#64748B` | Placeholder text, disabled states |
| `--bg-input` | `#0F172A` | Input field backgrounds |
| `--bg-hover` | `#334155` | Hover states on interactive elements |

### Typography

| Role | Font Family | Weight | Size |
|------|-------------|--------|------|
| Display / Hero | Inter | 700 (Bold) | 48px |
| Section Title | Inter | 600 (SemiBold) | 28–32px |
| Card Title | Inter | 600 (SemiBold) | 18–20px |
| Body Text | Inter | 400 (Regular) | 14–16px |
| Labels / Captions | Inter | 500 (Medium) | 12–13px |
| Data Values / Monospace | JetBrains Mono | 600 | 14–24px |
| KPI Numbers | JetBrains Mono | 700 | 28–36px |
| Code / Terminal Text | JetBrains Mono | 400 | 13px |

### Spacing & Layout

- **Page padding:** 20px all sides
- **Card padding:** 16–20px internal
- **Card border-radius:** 12px
- **Card border:** 1px solid `#334155`
- **Grid gap:** 16px (standard), 12px (compact)
- **Section gap:** 24px between major sections
- **Button border-radius:** 8px
- **Input border-radius:** 8px
- **Badge border-radius:** 4–6px

### Component Patterns

- **Status Badge:** Small rounded rectangle with colored background (10% opacity) + colored text
- **KPI Card:** Card with label (muted), large monospace value, trend indicator (▲/▼ + percentage)
- **Icon + Text:** Lucide icon (16–20px) followed by label, 8px gap
- **Toggle/Switch:** 44×24px with cyan active state, gray inactive
- **Dropdown:** Input-styled with chevron-down icon on right

---

## Page 1 – Landing Page

**Node ID:** `tvmWe`  
**Canvas Position:** x: 0, y: 0  
**Purpose:** Public-facing marketing page to introduce QueueVision  

### Layout Structure

```
┌─────────────────────────────────────────────────────┐
│ HEADER: Logo + Nav links + "Get Started" button     │
├─────────────────────────────────────────────────────┤
│ HERO SECTION                                        │
│   Left: Headline + subtitle + 2 CTA buttons         │
│   Right: AI-generated dashboard preview image        │
├─────────────────────────────────────────────────────┤
│ HOW IT WORKS – 4-step pipeline                       │
│   [Capture] → [Detect] → [Analyze] → [Alert]       │
├─────────────────────────────────────────────────────┤
│ FEATURES – 3×2 grid of feature cards                │
│   Real-Time Detection | Queue Analytics | Smart...  │
│   Multi-Camera       | Uncertainty     | n8n...     │
├─────────────────────────────────────────────────────┤
│ TECH STACK – 5 technology cards in a row            │
│   YOLO26 | ByteTrack | OpenCV | Supervision | n8n  │
├─────────────────────────────────────────────────────┤
│ FOOTER – 3 columns + bottom copyright              │
│   Product links | Resources | Connect              │
└─────────────────────────────────────────────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| **Header** | Logo text "QueueVision" in cyan, nav links (Features, How It Works, Tech Stack), cyan "Get Started" button |
| **Hero Headline** | "Intelligent Queue Monitoring" – 48px Inter Bold, white |
| **Hero Subtitle** | "Real-time wait-time estimation..." – 18px Inter, `#94A3B8` |
| **CTA Buttons** | Primary: "Start Monitoring" (cyan bg), Secondary: "View Demo" (border only) |
| **Dashboard Preview** | AI-generated image showing a dark-themed analytics dashboard |
| **Pipeline Steps** | 4 cards with numbered circles (1–4), icon, title, description, connected by arrow lines |
| **Feature Cards** | Icon (cyan) + title + 2-line description, `#1E293B` background |
| **Tech Cards** | Centered icon + name + subtitle, `#1E293B` background |
| **Footer** | 3 columns of links, bottom bar with "© 2026 QueueVision" |

---

## Page 2 – Dashboard

**Node ID:** `OPPgB`  
**Canvas Position:** x: 1540, y: 0  
**Purpose:** Main admin dashboard – real-time monitoring of all camera feeds and alerts  

### Layout Structure

```
┌─────────────────────────────────────────────────────┐
│ TOP BAR: "QueueVision" + LIVE badge + controls      │
├──────────────────────────────────┬──────────────────┤
│                                  │ ALERT SIDEBAR    │
│   2×2 CAMERA GRID                │  Threshold card  │
│   ┌────────┬────────┐           │  Alert 1 (red)   │
│   │ Cam 1  │ Cam 2  │           │  Alert 2 (amber) │
│   │ (live) │ (live) │           │  Alert 3 (green) │
│   ├────────┼────────┤           │  Webhook status  │
│   │ Cam 3  │ Cam 4  │           │                  │
│   │ (live) │(offline)│           │                  │
├──────────────────────────────────┴──────────────────┤
│ METRICS STRIP                                       │
│  [Wait Time Chart] [Queue Size Chart] KPI KPI KPI   │
└─────────────────────────────────────────────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| **Top Bar** | Logo, green "LIVE" badge, date/time display, "Add Camera" button (cyan), settings gear icon |
| **Camera Grid** | 2×2 grid. Each cell: dark frame with camera name overlay, status dot (green=live, red=offline), person count badge |
| **Camera 4 Offline** | Shows "NO SIGNAL" text with red status dot |
| **Alert Sidebar** | Width ~280px. Contains threshold status card, 3 alert cards, webhook status |
| **Threshold Card** | "Threshold Status" header, "ACTIVE" green badge, max wait/queue limit display |
| **Alert Cards** | Colored left border (red/amber/green), timestamp, title, description |
| **Webhook Status** | "n8n Connected" with green dot, last ping timestamp |
| **Metrics Strip** | Bottom 180px. Two chart placeholders (line chart + bar chart) and 3 KPI cards |
| **KPI Cards** | Avg Wait (4.2 min), Queue Size (12), Served/hr (34) – monospace values with trend arrows |

---

## Page 3 – Setup Wizard

**Node ID:** `8QJyT`  
**Canvas Position:** x: 3080, y: 0  
**Purpose:** First-time onboarding – step-by-step camera source configuration  

### Layout Structure

```
┌─────────────────────────────────────────────────────┐
│ TOP BAR: Logo + SETUP badge (amber) + progress      │
├────────────┬────────────────────────────────────────┤
│ LEFT       │ MAIN CONTENT                           │
│ SIDEBAR    │                                        │
│            │ "Add Camera Sources" title              │
│ 1 Sources  │ Subtitle text                          │
│ 2 Zones  ●│                                        │
│ 3 Thresh.  │ Camera Item 1 (file, status dots)      │
│ 4 Review   │ Camera Item 2 (RTSP, status dots)     │
│            │                                        │
│            │ [Browse File...] [rtsp:// input]       │
│            │                                        │
│            │ ──────── Action Bar ────────           │
│            │ [Back]              [Next: Draw Zones]  │
└────────────┴────────────────────────────────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| **Top Bar** | Logo, amber "SETUP" badge, "Step 1 of 4" text, progress dots |
| **Left Sidebar** | 4 numbered steps: "Sources" (active, cyan highlight), "Zones", "Thresholds", "Review". Active step has cyan left border + background |
| **Step Items** | Circle with number + step name, inactive = `#64748B`, active = `#22D3EE` |
| **Camera List** | 2 pre-added cameras showing name, source type badge (FILE/RTSP), 3 status dots (source ✓, zones pending, thresholds pending) |
| **Browse Button** | "Browse Local File..." button with folder icon, `#1E293B` background |
| **RTSP Input** | Text input field with `rtsp://` placeholder, full width |
| **Action Bar** | Bottom bar with "Back" (ghost button) on left, "Next: Draw Zones →" (cyan button) on right |

### Wizard Steps (Full Flow)

1. **Sources** – Add camera feeds (current page)
2. **Zones** – Draw detection zones on each camera view (opens Zone Editor)
3. **Thresholds** – Set alert thresholds per zone
4. **Review** – Confirm configuration and start monitoring

---

## Page 4 – Zone Editor

**Node ID:** `y64OV`  
**Canvas Position:** x: 4620, y: 0  
**Purpose:** Draw and configure detection zones on camera feeds  

### Layout Structure

```
┌─────────────────────────────────────────────────────┐
│ TOP BAR: Logo + ZONE EDITOR (amber) + camera name   │
├──────────────────────────────────┬──────────────────┤
│                                  │ PROPERTIES PANEL │
│   CANVAS AREA                    │                  │
│   ┌──────────────────────────┐  │ Zone Name input  │
│   │                          │  │                  │
│   │   Video frame with       │  │ Polygon Vertices │
│   │   zone polygon overlay   │  │ P1: (120, 80)    │
│   │                          │  │ P2: (580, 80)    │
│   │                          │  │ P3: (620, 400)   │
│   │                          │  │ P4: (100, 400)   │
│   └──────────────────────────┘  │                  │
│                                  │ Trigger: Entry   │
│   TOOLBAR: [Polygon][Rect][Move] │                  │
│                                  │ [Save Zone]      │
│   Instructions card              │ [Undo] [Cancel]  │
└──────────────────────────────────┴──────────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| **Top Bar** | Logo, amber "ZONE EDITOR" badge, camera name "Main Entrance – Camera 1" |
| **Canvas** | Large area (~930×500px) with dark video frame, overlaid cyan polygon zone with dotted border + corner handles |
| **Zone Polygon** | Cyan (#22D3EE) border 2px dashed, 10% fill, 4 corner handles (small cyan circles) |
| **Drawing Toolbar** | 3 tool buttons: Polygon Draw (active, cyan bg), Rectangle Select, Move/Pan. Below the canvas |
| **Instructions Card** | "Click to place vertices..." helper text, `#0F172A` background |
| **Properties Panel** | Right side ~300px width. Zone name input, vertex coordinate list (P1–P4), Trigger Anchor dropdown (Entry/Exit/Center) |
| **Vertex List** | 4 rows showing P1–P4 with x,y coordinates in monospace, each with cyan dot indicator |
| **Trigger Dropdown** | Shows "Entry Edge" with chevron, selects which polygon edge triggers enter/exit events |
| **Action Buttons** | "Save Zone" (cyan, full width), "Undo" + "Cancel" (ghost buttons side by side) |

---

## Page 5 – Historical Analytics

**Node ID:** `RraID`  
**Canvas Position:** x: 6160, y: 0  
**Purpose:** Historical data analysis with charts, KPIs, and trend visualization  

### Layout Structure

```
┌─────────────────────────────────────────────────────┐
│ TOP BAR: Logo + ANALYTICS (purple) + date range     │
│          + Export CSV button                         │
├─────────────────────────────────────────────────────┤
│ KPI ROW – 4 cards                                   │
│  Avg Wait 4.2m ↓12% | Peak 18 ↑8% | Served 2847   │
│  ↑23% | Uncertainty ±0.8 LOW                        │
├───────────────────────────┬─────────────────────────┤
│ WAIT TIME TREND CHART     │ QUEUE SIZE BAR CHART    │
│ Line chart with CI band   │ 4 horizontal bars       │
│ (purple uncertainty area)  │ by camera               │
├───────────────────────────┼─────────────────────────┤
│ PEAK HOURS HEATMAP        │ RECENT ALERTS LOG       │
│ 3×7 grid (Mon–Sun,       │ 4 alert entries with    │
│ Morning/Afternoon/Evening)│ timestamps and badges   │
└───────────────────────────┴─────────────────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| **Top Bar** | Logo, purple "ANALYTICS" badge, date range picker "Feb 20 – Feb 27, 2026", "Export CSV" button |
| **KPI Cards (4)** | Avg Wait: 4.2 min (↓12% green), Peak Queue: 18 (↑8% red), Total Served: 2,847 (↑23% green), Avg Uncertainty: ±0.8 (LOW green badge) |
| **Trend Chart** | Title "Wait Time Trend", line chart placeholder with purple CI (confidence interval) band area, x-axis = time, y-axis = minutes |
| **Bar Chart** | Title "Queue Size by Camera", 4 horizontal bars (Main Entrance, Side Door, Checkout, VIP) with cyan fill and values |
| **Peak Hours Heatmap** | Title "Peak Hours", 3×7 grid. Rows: Morning/Afternoon/Evening. Cols: Mon–Sun. Cells colored in varying cyan opacity (0.2–0.9) representing density |
| **Alerts Log** | Title "Recent Alerts", 4 entries: CRITICAL (red badge), WARNING (amber), INFO (cyan), RESOLVED (green). Each has timestamp + message |

### KPI Card Structure

```
┌──────────────────┐
│ Label (muted)    │
│ VALUE (mono, lg) │
│ ▲ +23% vs prev  │
└──────────────────┘
```

---

## Page 6 – Settings / Config

**Node ID:** `XJlxs`  
**Canvas Position:** x: 7700, y: 0  
**Purpose:** Application configuration – models, thresholds, webhooks, data export  

### Layout Structure

```
┌─────────────────────────────────────────────────────┐
│ TOP BAR: Logo + SETTINGS (muted)                     │
├────────────┬────────────────────────────────────────┤
│ LEFT NAV   │ MAIN CONTENT                           │
│            │                                        │
│ ● General  │ "General Settings" + [Save Changes]    │
│   Model    │                                        │
│   Alerts   │ ─── Application ───                    │
│   Webhooks │ App Name: [QueueVision        ]       │
│   Data     │ Refresh Rate: [30 FPS         ]       │
│   Zones    │ Dark Mode: [======●]                   │
│            │                                        │
│            │ ─── Model & Detection ───              │
│            │ YOLO Model: [yolo26n ▼        ]       │
│            │ Confidence: [0.45             ]       │
│            │ ByteTrack maxAge: [30         ]       │
│            │ Uncertainty: [======●]                  │
│            │                                        │
│            │ ─── Webhooks ───                       │
│            │ n8n URL: [https://n8n.example...]     │
│            │ Enable Webhook: [======●]              │
│            │ CSV Logging: [======●]                 │
│            │ Export Dir: [./data             ]      │
└────────────┴────────────────────────────────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| **Left Navigation** | 6 nav items: General (active, cyan dot + bg highlight), Model & Detection, Alerts & Thresholds, Webhooks, Data & Export, Zones |
| **Nav Item (active)** | Cyan dot + label, `#1E293B` background, left cyan border |
| **Nav Item (inactive)** | Gray dot + label, transparent background |
| **Section Headers** | Uppercase tracking text in `#64748B`, 13px, with bottom divider line |
| **Text Inputs** | Full-width, `#0F172A` background, `#334155` border, 14px, 8px radius |
| **Dropdown** | Same as input but with "▼" chevron indicator on right side |
| **Toggle Switch** | 44×24px. Active: cyan track + white circle. Inactive: `#334155` track |
| **Save Button** | Top right corner, cyan background, "Save Changes" text |

### Settings Sections (All)

1. **Application** – App name, refresh rate (FPS), dark mode toggle
2. **Model & Detection** – YOLO model selector (nano/small/medium/large/xlarge), confidence threshold, ByteTrack max age, track threshold, enable uncertainty toggle
3. **Alerts & Thresholds** – (on separate nav page) max wait time, max queue size, spike detection sensitivity
4. **Webhooks** – n8n webhook URL, enable webhook toggle, CSV logging toggle, export directory path
5. **Data & Export** – (on separate nav page) data retention period, auto-export settings
6. **Zones** – (on separate nav page) zone list with edit/delete actions

---

## Page 7 – Heatmap Overlay

**Node ID:** `SU8Ec`  
**Canvas Position:** x: 9240, y: 0  
**Purpose:** Real-time or historical density/dwell heatmap visualization  

### Layout Structure

```
┌─────────────────────────────────────────────────────┐
│ TOP BAR: Logo + HEATMAP (red) + camera selector     │
│          + toggle: Density | Paths | Dwell          │
├──────────────────────────────────┬──────────────────┤
│                                  │ SIDE PANEL       │
│   MAIN CANVAS                    │                  │
│   ┌──────────────────────────┐  │ Zone Density     │
│   │                          │  │  Main Queue: 87% │
│   │   AI-generated thermal   │  │  Side: 52%       │
│   │   heatmap image          │  │  Exit: 18%       │
│   │                          │  │                  │
│   │                          │  │ Live Statistics  │
│   └──────────────────────────┘  │  24 people       │
│                                  │  3.2min dwell    │
│   GRADIENT LEGEND BAR            │  34% hotspot     │
│   Low ████████████████████ High │                  │
│                                  │ Peak Congestion  │
│                                  │  AM Rush (green) │
│                                  │  Lunch (amber)   │
│                                  │  Evening (red)   │
└──────────────────────────────────┴──────────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| **Top Bar** | Logo, red "HEATMAP" badge, camera selector dropdown ("Main Entrance ▼"), 3-button toggle group (Density active, Paths, Dwell) |
| **Toggle Group** | 3 buttons side by side. Active = cyan bg, inactive = `#1E293B`. Rounded corners on ends |
| **Canvas** | Large area (~940×500px) with AI-generated thermal heatmap image overlaying a camera view |
| **Gradient Legend** | Horizontal bar under canvas. Left: "Low" (blue/green), Right: "High" (red/yellow). Continuous gradient fill |
| **Zone Density Card** | 3 zones with name + percentage bar. Main Queue: 87% (near full cyan bar), Side Entrance: 52%, Exit Area: 18% |
| **Percentage Bars** | Background `#334155`, filled portion in cyan, value text on right |
| **Live Statistics Card** | 3 rows: 24 people (person icon), 3.2 min avg dwell (clock icon), 34% hotspot area (flame icon) |
| **Peak Congestion Card** | 3 time slots: AM Rush 08–10 (green dot), Lunch Peak 12–14 (amber dot), Evening Rush 17–19 (red dot) |

---

## 🛠 Implementation Notes

### Recommended Tech Stack for Frontend

| Layer | Technology | Reason |
|-------|-----------|--------|
| **Framework** | Next.js 14+ (App Router) or React + Vite | Component-based, fast dev |
| **Styling** | Tailwind CSS | Matches design tokens directly |
| **Charts** | Recharts or Chart.js | Line, bar, heatmap charts |
| **Icons** | Lucide React | Used throughout the design |
| **State** | Zustand or React Context | Camera feeds, alert state |
| **Real-time** | WebSocket or SSE | Live camera + metrics updates |
| **Video** | HTML5 `<video>` + Canvas API | Camera feeds + zone overlay drawing |

### Tailwind Color Mapping

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        'qv-bg': '#0A0F1C',
        'qv-card': '#1E293B',
        'qv-card-alt': '#0F172A',
        'qv-border': '#334155',
        'qv-cyan': '#22D3EE',
        'qv-amber': '#F59E0B',
        'qv-red': '#EF4444',
        'qv-purple': '#A78BFA',
        'qv-green': '#10B981',
        'qv-text': '#F1F5F9',
        'qv-text-secondary': '#94A3B8',
        'qv-text-muted': '#64748B',
      },
      fontFamily: {
        display: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
}
```

### Page Routing Map

| Route | Page | Auth Required |
|-------|------|---------------|
| `/` | Landing Page | No |
| `/dashboard` | Dashboard | Yes (Admin) |
| `/setup` | Setup Wizard | Yes (Admin) |
| `/setup/zones` | Zone Editor | Yes (Admin) |
| `/analytics` | Historical Analytics | Yes (Admin) |
| `/settings` | Settings / Config | Yes (Admin) |
| `/heatmap` | Heatmap Overlay | Yes (Admin) |

### Component Hierarchy

```
<App>
├── <LandingPage />          ← Public
├── <AdminLayout>             ← Authenticated wrapper
│   ├── <TopBar />            ← Shared across admin pages
│   ├── <Dashboard>
│   │   ├── <CameraGrid />
│   │   ├── <AlertSidebar />
│   │   └── <MetricsStrip />
│   ├── <SetupWizard>
│   │   ├── <StepSidebar />
│   │   ├── <SourceStep />
│   │   ├── <ZoneStep />      ← Opens ZoneEditor overlay
│   │   ├── <ThresholdStep />
│   │   └── <ReviewStep />
│   ├── <ZoneEditor>
│   │   ├── <DrawingCanvas />
│   │   ├── <Toolbar />
│   │   └── <PropertiesPanel />
│   ├── <Analytics>
│   │   ├── <KPIRow />
│   │   ├── <TrendChart />
│   │   ├── <BarChart />
│   │   ├── <HeatmapGrid />
│   │   └── <AlertLog />
│   ├── <Settings>
│   │   ├── <SettingsNav />
│   │   └── <SettingsForm />
│   └── <HeatmapOverlay>
│       ├── <HeatmapCanvas />
│       ├── <GradientLegend />
│       └── <StatsPanel />
```

### API Endpoints (Suggested)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/cameras` | List all configured cameras |
| POST | `/api/cameras` | Add a new camera source |
| GET | `/api/cameras/:id/stream` | Get video stream (WebSocket) |
| GET | `/api/metrics/live` | Real-time queue metrics (SSE) |
| GET | `/api/metrics/history` | Historical metrics with date range |
| GET | `/api/alerts` | Recent alerts list |
| GET | `/api/zones/:cameraId` | Get zones for a camera |
| POST | `/api/zones/:cameraId` | Save zone polygon |
| GET | `/api/heatmap/:cameraId` | Get heatmap data |
| GET/PUT | `/api/settings` | Read/update application settings |
| POST | `/api/export/csv` | Export metrics as CSV |

### Data Models (Key)

```typescript
interface Camera {
  id: string;
  name: string;
  source: 'file' | 'rtsp' | 'webcam';
  url: string;
  status: 'online' | 'offline';
  zones: Zone[];
}

interface Zone {
  id: string;
  name: string;
  polygon: [number, number][];  // Array of [x, y] vertices
  triggerAnchor: 'entry' | 'exit' | 'center';
}

interface QueueMetrics {
  cameraId: string;
  timestamp: string;
  queueLength: number;
  avgWaitTime: number;         // minutes
  arrivalRate: number;         // λ (persons/min)
  serviceRate: number;         // μ (persons/min)
  uncertainty: number;         // ± value
  confidenceInterval: [number, number];
}

interface Alert {
  id: string;
  type: 'critical' | 'warning' | 'info' | 'resolved';
  title: string;
  message: string;
  timestamp: string;
  cameraId: string;
}

interface AppSettings {
  appName: string;
  refreshRateFps: number;
  darkMode: boolean;
  yoloModel: 'yolo26n' | 'yolo26s' | 'yolo26m' | 'yolo26l' | 'yolo26x';
  confidenceThreshold: number;
  bytetrackMaxAge: number;
  enableUncertainty: boolean;
  webhookUrl: string;
  enableWebhook: boolean;
  csvLogging: boolean;
  exportDirectory: string;
}
```

---

## 📂 Design File Reference

| Item | Value |
|------|-------|
| **File** | `pencil-new.pen` (workspace root) |
| **Tool** | Pencil MCP (`.pen` format, encrypted) |
| **Access** | Use Pencil MCP tools only (`batch_get`, `get_screenshot`, etc.) |
| **Pages** | 7 frames, each 1440×900px, spaced 1540px apart on x-axis |

### Node ID Quick Reference

| Page | Root Node ID | X Position |
|------|-------------|------------|
| Landing Page | `tvmWe` | 0 |
| Dashboard | `OPPgB` | 1540 |
| Setup Wizard | `8QJyT` | 3080 |
| Zone Editor | `y64OV` | 4620 |
| Historical Analytics | `RraID` | 6160 |
| Settings / Config | `XJlxs` | 7700 |
| Heatmap Overlay | `SU8Ec` | 9240 |

---

*This specification was generated from the Pencil design file and should be used as the single source of truth for frontend implementation.*
