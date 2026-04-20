# All Eraser Diagram Codes

This file contains the code of all diagrams in this folder.

## Diagram Index

- database_auth_erd
- database_core_erd
- global_use_case
- sprint1_activity
- sprint1_sequence
- sprint1_use_case
- sprint2_component
- sprint2_data_flow
- sprint2_sequence
- sprint3_component
- sprint3_data_flow
- sprint3_sequence
- sprint4_frontend_arch
- sprint5_data_flow
- sprint5_sequence
- sprint6_component
- sprint6_data_flow

## database_auth_erd

Source file: database_auth_erd.eraserdiagram

    entity-relationship-diagram
    
    colorMode bold
    styleMode plain
    typeface clean
    notation crows-feet
    
    users [icon: user, color: blue] {
      id int pk
      email string not null unique
      display_name string not null
      password_hash string not null
      role string not null
      is_active boolean not null
      failed_login_attempts int not null
      locked_until timestamp
      last_login_at timestamp
      created_at timestamp not null
      updated_at timestamp not null
    }
    
    auth_refresh_sessions [icon: lock, color: green] {
      id string pk
      user_id int fk not null
      token_hash string not null unique
      expires_at timestamp not null
      created_at timestamp not null
      last_used_at timestamp
      revoked_at timestamp
      ip_address string
      user_agent text
    }
    
    auth_audit_log [icon: database, color: orange] {
      id int pk
      user_id int fk
      event_type string not null
      event_status string not null
      details_json json
      created_at timestamp not null
    }
    
    users.id < auth_refresh_sessions.user_id
    users.id < auth_audit_log.user_id

## database_core_erd

Source file: database_core_erd.eraserdiagram

    entity-relationship-diagram
    
    colorMode bold
    styleMode plain
    typeface clean
    notation crows-feet
    
    establishments [icon: database, color: blue] {
      id int pk
      name string not null unique
      created_at timestamp
    }
    
    caisses [icon: database, color: green] {
      id int pk
      name string not null
      establishment_id int fk not null
      zone_points_json json
      created_at timestamp
    }
    
    video_sessions [icon: database, color: orange] {
      id int pk
      video_source string not null
      establishment_id int fk
      caisse_id int fk
      start_time timestamp
      end_time timestamp
      created_at timestamp
    }
    
    feed_configs [icon: database, color: red] {
      feed_id string pk
      name string not null
      source string not null
      model_size string not null
      status string not null
      log_level string not null
      webhook_enabled boolean not null
      queue_length_warning int not null
      rtsp_username string
      rtsp_password string
      rtsp_transport string
      establishment_id int fk
      caisse_id int fk
      zone_points_json json
      last_error text
      created_at timestamp not null
      updated_at timestamp not null
    }
    
    alert_history [icon: database, color: orange] {
      id int pk
      timestamp timestamp
      camera_id string
      zone_id string
      alert_type string
      severity string
      message text
      value float
      threshold float
      people_in_zone int
      arrival_rate float
      service_rate float
      wait_time_seconds float
      queue_stable boolean
      raw_detection_count int
      fps float
      alerts_count int
      payload_json json not null
      created_at timestamp not null
    }
    
    establishments.id < caisses.establishment_id
    establishments.id < video_sessions.establishment_id
    caisses.id < video_sessions.caisse_id
    establishments.id < feed_configs.establishment_id
    caisses.id < feed_configs.caisse_id

## global_use_case

Source file: global_use_case.eraserdiagram

    cloud-architecture-diagram
    
    direction right
    
    People [color: blue] {
      Admin [label: "Administrator", icon: user, color: blue]
      Manager [icon: user, color: blue]
    }
    
    MainActions [color: green] {
      ManageAccounts [label: "Manage accounts", icon: lock, color: blue]
      AddFeed [label: "Add video feed", icon: monitor, color: green]
      SetZone [label: "Set queue zone", icon: code, color: green]
      WatchQueue [label: "Monitor live queue", icon: monitor, color: orange]
      GetAlerts [label: "Receive alerts", icon: bell, color: red]
      CheckTrends [label: "Check trends", icon: database, color: orange]
    }
    
    SystemParts [color: orange] {
      Auth [label: "Auth service", icon: lock, color: blue]
      Runtime [label: "Runtime pipeline", icon: server, color: green]
      Analytics [icon: gear, color: orange]
      Dashboard [icon: react, color: red]
      Automation [label: "Alert automation", icon: mail, color: red]
    }
    
    Admin > ManageAccounts
    Manager > AddFeed, SetZone, WatchQueue, GetAlerts, CheckTrends
    
    ManageAccounts > Auth
    AddFeed > Runtime
    SetZone > Runtime
    WatchQueue > Dashboard
    GetAlerts > Automation
    CheckTrends > Analytics
    
    Runtime > Analytics: queue data
    Analytics > Dashboard: metrics
    Analytics > Automation: alert signal

## sprint1_activity

Source file: sprint1_activity.eraserdiagram

    flow-chart
    
    direction down
    
    Start [shape: oval, icon: monitor, color: blue]
    ChooseSource [label: "Choose source", shape: rectangle, icon: monitor, color: blue]
    SourceOk [label: "Source works?", shape: diamond, icon: gear, color: orange]
    DrawZone [label: "Draw queue zone", shape: rectangle, icon: code, color: green]
    RunAnalysis [label: "Run analysis", shape: rectangle, icon: gear, color: green]
    DetectTrack [label: "Detect and track people", shape: rectangle, icon: server, color: green]
    KeepInZone [label: "Keep only people in zone", shape: rectangle, icon: code, color: green]
    UpdateMetrics [label: "Update queue metrics", shape: rectangle, icon: database, color: orange]
    ShowResult [label: "Show live result", shape: rectangle, icon: monitor, color: red]
    MoreFrames [label: "More frames?", shape: diamond, icon: gear, color: orange]
    FixSource [label: "Fix source and retry", shape: rectangle, icon: key, color: red]
    Stop [shape: oval, icon: terminal, color: red]
    
    Start > ChooseSource
    ChooseSource > SourceOk
    SourceOk > DrawZone: yes
    SourceOk > FixSource: no
    FixSource > Stop
    
    DrawZone > RunAnalysis
    RunAnalysis > DetectTrack
    DetectTrack > KeepInZone
    KeepInZone > UpdateMetrics
    UpdateMetrics > ShowResult
    ShowResult > MoreFrames
    MoreFrames > DetectTrack: yes
    MoreFrames > Stop: no

## sprint1_sequence

Source file: sprint1_sequence.eraserdiagram

    sequence-diagram
    
    autoNumber on
    
    MainLoop [label: "Main loop", icon: gear, color: green]
    VideoSource [label: "Video source", icon: monitor, color: blue]
    Detector [label: "Person detector", icon: server, color: green]
    Tracker [label: "Object tracker", icon: gear, color: green]
    ZoneCheck [label: "Zone check", icon: code, color: orange]
    QueueLogic [label: "Queue analysis", icon: database, color: orange]
    
    loop [label: each frame] {
      MainLoop > VideoSource: read frame
      VideoSource > Detector: send frame
      Detector > Tracker: send detections
      Tracker > ZoneCheck: send tracked people
      ZoneCheck > QueueLogic: keep people in queue zone
      QueueLogic > MainLoop: return updated metrics
    }

## sprint1_use_case

Source file: sprint1_use_case.eraserdiagram

    cloud-architecture-diagram
    
    direction right
    
    Manager [icon: user, color: blue]
    
    Sprint1Actions [color: blue] {
      ChooseSource [label: "Choose video source", icon: monitor, color: blue]
      DrawZone [label: "Draw queue zone", icon: code, color: green]
      StartAnalysis [label: "Start queue analysis", icon: gear, color: green]
      ViewLive [label: "View live video", icon: monitor, color: red]
      ReviewQueue [label: "Review queue status", icon: database, color: orange]
    }
    
    RuntimeFlow [color: green] {
      CaptureVideo [label: "Capture video", icon: monitor, color: blue]
      DetectPeople [label: "Detect people", icon: server, color: green]
      TrackPeople [label: "Track people", icon: gear, color: green]
      CheckZone [label: "Check zone membership", icon: code, color: orange]
      UpdateQueue [label: "Update queue state", icon: database, color: orange]
    }
    
    Manager > ChooseSource, DrawZone, StartAnalysis, ViewLive, ReviewQueue
    
    ChooseSource > CaptureVideo
    DrawZone > CheckZone
    StartAnalysis > DetectPeople
    ViewLive > UpdateQueue
    ReviewQueue > UpdateQueue
    
    CaptureVideo > DetectPeople: frames
    DetectPeople > TrackPeople
    TrackPeople > CheckZone
    CheckZone > UpdateQueue

## sprint2_component

Source file: sprint2_component.eraserdiagram

    cloud-architecture-diagram
    
    direction right
    
    QueueEvents [label: "Queue events", icon: database, color: blue]
    QueueAnalyzer [label: "Queue analyzer", icon: gear, color: green]
    RateCalculator [label: "Rate calculator", icon: code, color: green]
    StabilityCheck [label: "Stability check", icon: lock, color: green]
    WaitTime [label: "Wait time calculator", icon: terminal, color: orange]
    Metrics [label: "Metrics payload", icon: database, color: orange]
    Dashboard [icon: react, color: red]
    Webhook [icon: mail, color: red]
    CsvLog [label: "CSV log", icon: database, color: orange]
    
    QueueEvents > QueueAnalyzer
    QueueAnalyzer > RateCalculator
    RateCalculator > StabilityCheck
    StabilityCheck > WaitTime
    RateCalculator > Metrics
    WaitTime > Metrics
    
    Metrics > Dashboard
    Metrics > Webhook
    Metrics > CsvLog

## sprint2_data_flow

Source file: sprint2_data_flow.eraserdiagram

    flow-chart
    
    direction down
    
    Start [label: "New frame events", shape: oval, icon: database, color: blue]
    BuildEvents [label: "Build arrival and departure events", shape: rectangle, icon: gear, color: green]
    CalcRates [label: "Calculate arrival and service rates", shape: rectangle, icon: code, color: green]
    Stable [label: "Queue stable?", shape: diamond, icon: lock, color: orange]
    WaitStable [label: "Use stable wait formula", shape: rectangle, icon: terminal, color: green]
    WaitFallback [label: "Use fallback wait formula", shape: rectangle, icon: terminal, color: orange]
    BuildMetrics [label: "Create metrics payload", shape: rectangle, icon: database, color: orange]
    SendDashboard [label: "Send to dashboard", shape: rectangle, icon: react, color: red]
    SendWebhook [label: "Send to webhook", shape: rectangle, icon: mail, color: red]
    SaveCsv [label: "Save to CSV", shape: rectangle, icon: database, color: orange]
    End [shape: oval, icon: terminal, color: red]
    
    Start > BuildEvents
    BuildEvents > CalcRates
    CalcRates > Stable
    Stable > WaitStable: yes
    Stable > WaitFallback: no
    WaitStable > BuildMetrics
    WaitFallback > BuildMetrics
    BuildMetrics > SendDashboard
    BuildMetrics > SendWebhook
    BuildMetrics > SaveCsv
    SendDashboard > End
    SendWebhook > End
    SaveCsv > End

## sprint2_sequence

Source file: sprint2_sequence.eraserdiagram

    sequence-diagram
    
    autoNumber on
    
    Analyzer [label: "Queue analyzer", icon: database, color: blue]
    Rates [label: "Rate calculator", icon: code, color: blue]
    Stability [label: "Stability check", icon: lock, color: green]
    WaitTime [label: "Wait time logic", icon: terminal, color: green]
    Metrics [label: "Metrics payload", icon: database, color: orange]
    Dashboard [label: "Dashboard", icon: react, color: red]
    Webhook [label: "Webhook sender", icon: mail, color: red]
    
    Analyzer > Rates: compute arrival and service rates
    Rates > Stability: evaluate queue condition
    
    alt [label: queue is stable] {
      Stability > WaitTime: use stable wait formula
    }
    else [label: queue is not stable] {
      Stability > WaitTime: use fallback wait formula
    }
    
    WaitTime > Metrics: set wait time and stability flag
    Rates > Metrics: set arrival and service rates
    Metrics > Dashboard: publish metrics
    Metrics > Webhook: publish payload

## sprint3_component

Source file: sprint3_component.eraserdiagram

    cloud-architecture-diagram
    
    direction right
    
    Sources [color: blue] {
      LocalVideo [label: "Local file or webcam", icon: monitor, color: blue]
      RtspCamera [label: "RTSP camera", icon: server, color: blue]
      OnvifCamera [label: "ONVIF camera", icon: server, color: blue]
    }
    
    Backend [color: green] {
      Api [label: "Backend API", icon: python, color: blue]
      FeedManager [label: "Feed manager", icon: database, color: green]
      Worker [label: "Worker runtime", icon: terminal, color: green]
      WebSocketHub [label: "WebSocket hub", icon: globe, color: orange]
      MjpegStream [label: "MJPEG stream", icon: monitor, color: orange]
      WebRtcOffer [label: "WebRTC offer endpoint", icon: cloud, color: orange]
    }
    
    MediaServer [label: "Media server", icon: cloud, color: orange]
    Dashboard [label: "Dashboard", icon: react, color: red]
    
    LocalVideo > Worker
    RtspCamera > Api
    OnvifCamera > Api
    
    Dashboard > Api: setup and control
    Api > FeedManager
    FeedManager > Worker
    Worker > WebSocketHub
    WebSocketHub > Dashboard: live events
    
    Dashboard > WebRtcOffer: start WebRTC
    WebRtcOffer <> MediaServer: SDP exchange
    Worker > MjpegStream
    MjpegStream > Dashboard: fallback video

## sprint3_data_flow

Source file: sprint3_data_flow.eraserdiagram

    flow-chart
    
    direction down
    
    StartSetup [label: "User starts feed setup", shape: oval, icon: user, color: blue]
    CallApi [label: "Send setup request", shape: rectangle, icon: python, color: blue]
    SaveFeed [label: "Save feed settings", shape: rectangle, icon: database, color: green]
    StartWorker [label: "Start worker", shape: rectangle, icon: terminal, color: green]
    EmitEvents [label: "Emit live events", shape: rectangle, icon: globe, color: orange]
    RefreshDashboard [label: "Refresh dashboard", shape: oval, icon: react, color: red]
    
    CheckTransport [label: "Check transport readiness", shape: rectangle, icon: cloud, color: blue]
    WebRtcReady [label: "WebRTC ready?", shape: diamond, icon: gear, color: orange]
    OfferAnswer [label: "Exchange offer and answer", shape: rectangle, icon: cloud, color: green]
    UseWebRtc [label: "Show WebRTC video", shape: rectangle, icon: monitor, color: red]
    UseMjpeg [label: "Use MJPEG fallback", shape: rectangle, icon: monitor, color: orange]
    
    StartSetup > CallApi
    CallApi > SaveFeed
    SaveFeed > StartWorker
    StartWorker > EmitEvents
    EmitEvents > RefreshDashboard
    
    StartSetup > CheckTransport
    CheckTransport > WebRtcReady
    WebRtcReady > OfferAnswer: yes
    OfferAnswer > UseWebRtc
    UseWebRtc > RefreshDashboard
    WebRtcReady > UseMjpeg: no
    UseMjpeg > RefreshDashboard

## sprint3_sequence

Source file: sprint3_sequence.eraserdiagram

    sequence-diagram
    
    autoNumber on
    
    Dashboard [label: "Dashboard", icon: react, color: blue]
    Api [label: "Backend API", icon: python, color: blue]
    Manager [label: "Feed manager", icon: database, color: green]
    Worker [label: "Worker runtime", icon: terminal, color: green]
    Socket [label: "WebSocket hub", icon: globe, color: orange]
    MediaServer [label: "Media server", icon: cloud, color: red]
    
    Dashboard > Api: request feed action
    Api > Manager: apply feed change
    Manager > Worker: start or stop worker
    Worker > Socket: emit status and metrics
    Socket > Dashboard: push live update
    
    opt [label: if WebRTC is available] {
      Dashboard > Api: request WebRTC session
      Api > MediaServer: exchange session info
      MediaServer > Dashboard: return video session
    }

## sprint4_frontend_arch

Source file: sprint4_frontend_arch.eraserdiagram

    cloud-architecture-diagram
    
    direction right
    
    Pages [color: blue] {
      DashboardPage [label: "Dashboard page", icon: react, color: blue]
      ZoneEditorPage [label: "Zone editor page", icon: react, color: green]
      AnalyticsPage [label: "Analytics page", icon: react, color: orange]
      SettingsPage [label: "Settings page", icon: react, color: red]
    }
    
    SharedLayer [color: green] {
      UiComponents [label: "Reusable UI components", icon: monitor, color: green]
      DataHooks [label: "Data hooks", icon: gear, color: orange]
      ApiClient [label: "API client", icon: typescript, color: blue]
      QueryCache [label: "Query cache", icon: database, color: orange]
    }
    
    BackendApi [label: "Backend API", icon: python, color: red]
    LiveSocket [label: "WebSocket stream", icon: globe, color: orange]
    
    DashboardPage > UiComponents
    ZoneEditorPage > UiComponents
    AnalyticsPage > UiComponents
    SettingsPage > UiComponents
    
    DashboardPage > DataHooks
    ZoneEditorPage > DataHooks
    AnalyticsPage > DataHooks
    SettingsPage > DataHooks
    
    DataHooks <> QueryCache
    DataHooks > ApiClient
    ApiClient > BackendApi
    LiveSocket > DataHooks: live updates

## sprint5_data_flow

Source file: sprint5_data_flow.eraserdiagram

    flow-chart
    
    direction down
    
    UserAction [label: "User action on dashboard", shape: oval, icon: user, color: blue]
    ApiRequest [label: "Send API request", shape: rectangle, icon: python, color: blue]
    UpdateRuntime [label: "Update feed state", shape: rectangle, icon: database, color: green]
    PushStatus [label: "Push status event", shape: rectangle, icon: globe, color: orange]
    UpdateState [label: "Update dashboard state", shape: rectangle, icon: gear, color: orange]
    RefreshUi [label: "Refresh cards and feed grid", shape: oval, icon: react, color: red]
    
    MetricsEvent [label: "Metrics event arrives", shape: rectangle, icon: database, color: orange]
    AlertEvent [label: "Alert event arrives", shape: rectangle, icon: bell, color: red]
    UpdateKpi [label: "Update KPI values", shape: rectangle, icon: monitor, color: orange]
    UpdatePanels [label: "Update activity and attention", shape: rectangle, icon: bell, color: red]
    
    UserAction > ApiRequest
    ApiRequest > UpdateRuntime
    UpdateRuntime > PushStatus
    PushStatus > UpdateState
    UpdateState > RefreshUi
    
    MetricsEvent > UpdateKpi
    UpdateKpi > RefreshUi
    
    AlertEvent > UpdatePanels
    UpdatePanels > RefreshUi

## sprint5_sequence

Source file: sprint5_sequence.eraserdiagram

    sequence-diagram
    
    autoNumber on
    
    Dashboard [label: "Dashboard UI", icon: react, color: blue]
    Api [label: "Backend API", icon: python, color: blue]
    Manager [label: "Feed manager", icon: database, color: green]
    Socket [label: "WebSocket hub", icon: globe, color: orange]
    State [label: "Dashboard state", icon: gear, color: orange]
    Kpi [label: "KPI cards", icon: monitor, color: green]
    Activity [label: "Activity panel", icon: bell, color: orange]
    Attention [label: "Attention panel", icon: bell, color: red]
    
    Dashboard > Api: send feed action
    Api > Manager: update feed state
    Manager > Socket: emit feed status
    Socket > State: update dashboard state
    State > Kpi: refresh feed overview
    
    par [label: live metrics] {
      Socket > State: metrics update
    }
    and [label: live alerts] {
      Socket > State: alert event
    }
    
    State > Kpi: refresh wait and queue values
    State > Activity: add recent event
    State > Attention: refresh attention count

## sprint6_component

Source file: sprint6_component.eraserdiagram

    cloud-architecture-diagram
    
    direction right
    
    Backend [color: blue] {
      QueueRuntime [label: "Queue runtime", icon: python, color: blue]
      AlertRules [label: "Alert rules", icon: bell, color: orange]
      WebhookSender [label: "Webhook sender", icon: mail, color: red]
    }
    
    N8nFlow [color: orange] {
      ReceiveWebhook [label: "Receive webhook", icon: cloud, color: blue]
      CheckSecret [label: "Check webhook secret", icon: lock, color: green]
      CheckAlerts [label: "Check alerts", icon: bell, color: orange]
      RouteSeverity [label: "Route by severity", icon: gear, color: orange]
      FormatMessage [label: "Format message", icon: code, color: green]
    }
    
    Telegram [label: "Telegram", icon: bell, color: red]
    ArchiveApi [label: "Alert archive API", icon: database, color: orange]
    
    QueueRuntime > AlertRules
    AlertRules > WebhookSender
    WebhookSender > ReceiveWebhook
    
    ReceiveWebhook > CheckSecret
    CheckSecret > CheckAlerts: valid
    CheckAlerts > RouteSeverity: alerts found
    RouteSeverity > FormatMessage
    FormatMessage > Telegram
    FormatMessage --> ArchiveApi: save alert

## sprint6_data_flow

Source file: sprint6_data_flow.eraserdiagram

    flow-chart
    
    direction down
    
    Incoming [label: "Incoming webhook payload", shape: oval, icon: mail, color: blue]
    ValidSecret [label: "Secret is valid?", shape: diamond, icon: lock, color: orange]
    Reject [label: "Return unauthorized", shape: rectangle, icon: key, color: red]
    Validate [label: "Validate payload", shape: rectangle, icon: code, color: green]
    HasAlerts [label: "Any alerts?", shape: diamond, icon: bell, color: orange]
    AckNoAlerts [label: "Acknowledge no alerts", shape: rectangle, icon: terminal, color: blue]
    Cooldown [label: "Cooldown passed?", shape: diamond, icon: gear, color: orange]
    AckSuppressed [label: "Acknowledge suppressed alert", shape: rectangle, icon: terminal, color: orange]
    PickType [label: "Pick warning or critical", shape: rectangle, icon: bell, color: orange]
    SendTelegram [label: "Send Telegram message", shape: rectangle, icon: bell, color: red]
    Archive [label: "Archive alert", shape: rectangle, icon: database, color: orange]
    Done [shape: oval, icon: terminal, color: red]
    
    Incoming > ValidSecret
    ValidSecret > Reject: no
    Reject > Done
    
    ValidSecret > Validate: yes
    Validate > HasAlerts
    HasAlerts > AckNoAlerts: no
    AckNoAlerts > Done
    
    HasAlerts > Cooldown: yes
    Cooldown > AckSuppressed: no
    AckSuppressed > Done
    
    Cooldown > PickType: yes
    PickType > SendTelegram
    SendTelegram > Archive
    Archive > Done

