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
    
    users [icon: user] {
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
    
    auth_refresh_sessions [icon: lock] {
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
    
    auth_audit_log [icon: database] {
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
    
    establishments [icon: database] {
      id int pk
      name string not null unique
      created_at timestamp
    }
    
    caisses [icon: database] {
      id int pk
      name string not null
      establishment_id int fk not null
      zone_points_json json
      created_at timestamp
    }
    
    video_sessions [icon: database] {
      id int pk
      video_source string not null
      establishment_id int fk
      caisse_id int fk
      start_time timestamp
      end_time timestamp
      created_at timestamp
    }
    
    feed_configs [icon: database] {
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
    
    alert_history [icon: database] {
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
    
    People {
      Admin [label: "Administrator", icon: user]
      Manager [icon: user]
    }
    
    MainActions {
      ManageAccounts [label: "Manage accounts", icon: lock]
      AddFeed [label: "Add video feed", icon: monitor]
      SetZone [label: "Set queue zone", icon: code]
      WatchQueue [label: "Monitor live queue", icon: monitor]
      GetAlerts [label: "Receive alerts", icon: bell]
      CheckTrends [label: "Check trends", icon: database]
    }
    
    SystemParts {
      Auth [label: "Auth service", icon: lock]
      Runtime [label: "Runtime pipeline", icon: server]
      Analytics [icon: gear]
      Dashboard [icon: react]
      Automation [label: "Alert automation", icon: mail]
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
    
    Start [shape: oval, icon: monitor]
    ChooseSource [label: "Choose source", shape: rectangle, icon: monitor]
    SourceOk [label: "Source works?", shape: diamond, icon: gear]
    DrawZone [label: "Draw queue zone", shape: rectangle, icon: code]
    RunAnalysis [label: "Run analysis", shape: rectangle, icon: gear]
    DetectTrack [label: "Detect and track people", shape: rectangle, icon: server]
    KeepInZone [label: "Keep only people in zone", shape: rectangle, icon: code]
    UpdateMetrics [label: "Update queue metrics", shape: rectangle, icon: database]
    ShowResult [label: "Show live result", shape: rectangle, icon: monitor]
    MoreFrames [label: "More frames?", shape: diamond, icon: gear]
    FixSource [label: "Fix source and retry", shape: rectangle, icon: key]
    Stop [shape: oval, icon: terminal]
    
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
    
    MainLoop [label: "Main loop", icon: gear]
    VideoSource [label: "Video source", icon: monitor]
    Detector [label: "Person detector", icon: server]
    Tracker [label: "Object tracker", icon: gear]
    ZoneCheck [label: "Zone check", icon: code]
    QueueLogic [label: "Queue analysis", icon: database]
    
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
    
    Manager [icon: user]
    
    Sprint1Actions {
      ChooseSource [label: "Choose video source", icon: monitor]
      DrawZone [label: "Draw queue zone", icon: code]
      StartAnalysis [label: "Start queue analysis", icon: gear]
      ViewLive [label: "View live video", icon: monitor]
      ReviewQueue [label: "Review queue status", icon: database]
    }
    
    RuntimeFlow {
      CaptureVideo [label: "Capture video", icon: monitor]
      DetectPeople [label: "Detect people", icon: server]
      TrackPeople [label: "Track people", icon: gear]
      CheckZone [label: "Check zone membership", icon: code]
      UpdateQueue [label: "Update queue state", icon: database]
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
    
    QueueEvents [label: "Queue events", icon: database]
    QueueAnalyzer [label: "Queue analyzer", icon: gear]
    RateCalculator [label: "Rate calculator", icon: code]
    StabilityCheck [label: "Stability check", icon: lock]
    WaitTime [label: "Wait time calculator", icon: terminal]
    Metrics [label: "Metrics payload", icon: database]
    Dashboard [icon: react]
    Webhook [icon: mail]
    CsvLog [label: "CSV log", icon: database]
    
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
    
    Start [label: "New frame events", shape: oval, icon: database]
    BuildEvents [label: "Build arrival and departure events", shape: rectangle, icon: gear]
    CalcRates [label: "Calculate arrival and service rates", shape: rectangle, icon: code]
    Stable [label: "Queue stable?", shape: diamond, icon: lock]
    WaitStable [label: "Use stable wait formula", shape: rectangle, icon: terminal]
    WaitFallback [label: "Use fallback wait formula", shape: rectangle, icon: terminal]
    BuildMetrics [label: "Create metrics payload", shape: rectangle, icon: database]
    SendDashboard [label: "Send to dashboard", shape: rectangle, icon: react]
    SendWebhook [label: "Send to webhook", shape: rectangle, icon: mail]
    SaveCsv [label: "Save to CSV", shape: rectangle, icon: database]
    End [shape: oval, icon: terminal]
    
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
    
    Analyzer [label: "Queue analyzer", icon: database]
    Rates [label: "Rate calculator", icon: code]
    Stability [label: "Stability check", icon: lock]
    WaitTime [label: "Wait time logic", icon: terminal]
    Metrics [label: "Metrics payload", icon: database]
    Dashboard [label: "Dashboard", icon: react]
    Webhook [label: "Webhook sender", icon: mail]
    
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
    
    Sources {
      LocalVideo [label: "Local file or webcam", icon: monitor]
      RtspCamera [label: "RTSP camera", icon: server]
      OnvifCamera [label: "ONVIF camera", icon: server]
    }
    
    Backend {
      Api [label: "Backend API", icon: python]
      FeedManager [label: "Feed manager", icon: database]
      Worker [label: "Worker runtime", icon: terminal]
      WebSocketHub [label: "WebSocket hub", icon: globe]
      MjpegStream [label: "MJPEG stream", icon: monitor]
      WebRtcOffer [label: "WebRTC offer endpoint", icon: cloud]
    }
    
    MediaServer [label: "Media server", icon: cloud]
    Dashboard [label: "Dashboard", icon: react]
    
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
    
    StartSetup [label: "User starts feed setup", shape: oval, icon: user]
    CallApi [label: "Send setup request", shape: rectangle, icon: python]
    SaveFeed [label: "Save feed settings", shape: rectangle, icon: database]
    StartWorker [label: "Start worker", shape: rectangle, icon: terminal]
    EmitEvents [label: "Emit live events", shape: rectangle, icon: globe]
    RefreshDashboard [label: "Refresh dashboard", shape: oval, icon: react]
    
    CheckTransport [label: "Check transport readiness", shape: rectangle, icon: cloud]
    WebRtcReady [label: "WebRTC ready?", shape: diamond, icon: gear]
    OfferAnswer [label: "Exchange offer and answer", shape: rectangle, icon: cloud]
    UseWebRtc [label: "Show WebRTC video", shape: rectangle, icon: monitor]
    UseMjpeg [label: "Use MJPEG fallback", shape: rectangle, icon: monitor]
    
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
    
    Dashboard [label: "Dashboard", icon: react]
    Api [label: "Backend API", icon: python]
    Manager [label: "Feed manager", icon: database]
    Worker [label: "Worker runtime", icon: terminal]
    Socket [label: "WebSocket hub", icon: globe]
    MediaServer [label: "Media server", icon: cloud]
    
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
    
    Pages {
      DashboardPage [label: "Dashboard page", icon: react]
      ZoneEditorPage [label: "Zone editor page", icon: react]
      AnalyticsPage [label: "Analytics page", icon: react]
      SettingsPage [label: "Settings page", icon: react]
    }
    
    SharedLayer {
      UiComponents [label: "Reusable UI components", icon: monitor]
      DataHooks [label: "Data hooks", icon: gear]
      ApiClient [label: "API client", icon: typescript]
      QueryCache [label: "Query cache", icon: database]
    }
    
    BackendApi [label: "Backend API", icon: python]
    LiveSocket [label: "WebSocket stream", icon: globe]
    
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
    
    UserAction [label: "User action on dashboard", shape: oval, icon: user]
    ApiRequest [label: "Send API request", shape: rectangle, icon: python]
    UpdateRuntime [label: "Update feed state", shape: rectangle, icon: database]
    PushStatus [label: "Push status event", shape: rectangle, icon: globe]
    UpdateState [label: "Update dashboard state", shape: rectangle, icon: gear]
    RefreshUi [label: "Refresh cards and feed grid", shape: oval, icon: react]
    
    MetricsEvent [label: "Metrics event arrives", shape: rectangle, icon: database]
    AlertEvent [label: "Alert event arrives", shape: rectangle, icon: bell]
    UpdateKpi [label: "Update KPI values", shape: rectangle, icon: monitor]
    UpdatePanels [label: "Update activity and attention", shape: rectangle, icon: bell]
    
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
    
    Dashboard [label: "Dashboard UI", icon: react]
    Api [label: "Backend API", icon: python]
    Manager [label: "Feed manager", icon: database]
    Socket [label: "WebSocket hub", icon: globe]
    State [label: "Dashboard state", icon: gear]
    Kpi [label: "KPI cards", icon: monitor]
    Activity [label: "Activity panel", icon: bell]
    Attention [label: "Attention panel", icon: bell]
    
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
    
    Backend {
      QueueRuntime [label: "Queue runtime", icon: python]
      AlertRules [label: "Alert rules", icon: bell]
      WebhookSender [label: "Webhook sender", icon: mail]
    }
    
    N8nFlow {
      ReceiveWebhook [label: "Receive webhook", icon: cloud]
      CheckSecret [label: "Check webhook secret", icon: lock]
      CheckAlerts [label: "Check alerts", icon: bell]
      RouteSeverity [label: "Route by severity", icon: gear]
      FormatMessage [label: "Format message", icon: code]
    }
    
    Telegram [label: "Telegram", icon: bell]
    ArchiveApi [label: "Alert archive API", icon: database]
    
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
    
    Incoming [label: "Incoming webhook payload", shape: oval, icon: mail]
    ValidSecret [label: "Secret is valid?", shape: diamond, icon: lock]
    Reject [label: "Return unauthorized", shape: rectangle, icon: key]
    Validate [label: "Validate payload", shape: rectangle, icon: code]
    HasAlerts [label: "Any alerts?", shape: diamond, icon: bell]
    AckNoAlerts [label: "Acknowledge no alerts", shape: rectangle, icon: terminal]
    Cooldown [label: "Cooldown passed?", shape: diamond, icon: gear]
    AckSuppressed [label: "Acknowledge suppressed alert", shape: rectangle, icon: terminal]
    PickType [label: "Pick warning or critical", shape: rectangle, icon: bell]
    SendTelegram [label: "Send Telegram message", shape: rectangle, icon: bell]
    Archive [label: "Archive alert", shape: rectangle, icon: database]
    Done [shape: oval, icon: terminal]
    
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

