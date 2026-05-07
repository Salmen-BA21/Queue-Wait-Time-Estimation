"""Database module for queue metrics metadata tracking.

Provides SQLite database initialization and helper functions for managing:
- Establishments (companies/stores)
- Caisses (checkout counters/registers)
- Video sessions (tracking which metadata was used for each video)
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any, cast


DB_PATH = Path(__file__).parent.parent / "data" / "queue_metrics.db"


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    """Return True when the requested table exists."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _get_table_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    """Return the column names defined for a SQLite table."""
    # Validate table name to avoid SQL injection when interpolating into PRAGMA.
    if not table_name.isidentifier():
        raise ValueError(f"Invalid table name: {table_name!r}")
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    return {row[1] for row in cursor.fetchall()}


def _create_current_schema(cursor: sqlite3.Cursor) -> None:
    """Create the current metadata schema if it does not exist."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS establishments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS caisses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            establishment_id INTEGER NOT NULL,
            zone_points_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (establishment_id) REFERENCES establishments (id),
            UNIQUE(name, establishment_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_source TEXT NOT NULL,
            establishment_id INTEGER,
            caisse_id INTEGER,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (establishment_id) REFERENCES establishments (id),
            FOREIGN KEY (caisse_id) REFERENCES caisses (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feed_configs (
            feed_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source TEXT NOT NULL,
            manager_user_id INTEGER,
            model_size TEXT NOT NULL DEFAULT 'n',
            status TEXT NOT NULL DEFAULT 'created',
            log_level TEXT NOT NULL DEFAULT 'INFO',
            webhook_enabled INTEGER NOT NULL DEFAULT 1,
            queue_length_warning INTEGER NOT NULL DEFAULT 8,
            rtsp_username TEXT,
            rtsp_password TEXT,
            rtsp_transport TEXT,
            establishment_id INTEGER,
            caisse_id INTEGER,
            zone_points_json TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (establishment_id) REFERENCES establishments (id) ON DELETE SET NULL,
            FOREIGN KEY (caisse_id) REFERENCES caisses (id) ON DELETE SET NULL,
            FOREIGN KEY (manager_user_id) REFERENCES users (id) ON DELETE SET NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            camera_id TEXT,
            zone_id TEXT,
            alert_type TEXT,
            severity TEXT,
            message TEXT,
            value REAL,
            threshold REAL,
            people_in_zone INTEGER,
            arrival_rate REAL,
            service_rate REAL,
            wait_time_seconds REAL,
            queue_stable INTEGER,
            raw_detection_count INTEGER,
            fps REAL,
            alerts_count INTEGER,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'manager')),
            is_active INTEGER NOT NULL DEFAULT 1,
            failed_login_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT,
            last_login_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_refresh_sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_used_at TEXT,
            revoked_at TEXT,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_type TEXT NOT NULL,
            event_status TEXT NOT NULL,
            details_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
    """)

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_auth_refresh_sessions_user_id ON auth_refresh_sessions(user_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_role_is_active ON users(role, is_active)"
    )
    if "manager_user_id" in _get_table_columns(cursor, "feed_configs"):
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_feed_configs_manager_user_id ON feed_configs(manager_user_id)"
        )


def _migrate_feed_configs_schema(cursor: sqlite3.Cursor) -> None:
    """Add newly required feed config columns for existing databases."""
    if not _table_exists(cursor, "feed_configs"):
        return

    columns = _get_table_columns(cursor, "feed_configs")
    if "log_level" not in columns:
        cursor.execute(
            "ALTER TABLE feed_configs ADD COLUMN log_level TEXT NOT NULL DEFAULT 'INFO'"
        )
    if "webhook_enabled" not in columns:
        cursor.execute(
            "ALTER TABLE feed_configs ADD COLUMN webhook_enabled INTEGER NOT NULL DEFAULT 1"
        )
    if "queue_length_warning" not in columns:
        cursor.execute(
            "ALTER TABLE feed_configs ADD COLUMN queue_length_warning INTEGER NOT NULL DEFAULT 8"
        )
    if "manager_user_id" not in columns:
        cursor.execute(
            "ALTER TABLE feed_configs ADD COLUMN manager_user_id INTEGER"
        )

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_feed_configs_manager_user_id ON feed_configs(manager_user_id)"
    )


def _migrate_legacy_sections_to_caisses(cursor: sqlite3.Cursor) -> None:
    """Copy legacy section rows into the caisse table when needed."""
    if not _table_exists(cursor, "sections"):
        return

    cursor.execute("""
        INSERT OR IGNORE INTO caisses (id, name, establishment_id, zone_points_json, created_at)
        SELECT id, name, establishment_id, zone_points_json, created_at
        FROM sections
    """)


def _migrate_legacy_video_sessions(cursor: sqlite3.Cursor) -> None:
    """Upgrade legacy video_sessions rows to the current caisse-based schema."""
    if not _table_exists(cursor, "video_sessions"):
        return

    columns = _get_table_columns(cursor, "video_sessions")
    if "caisse_id" in columns and "employee_id" not in columns:
        return

    cursor.execute("ALTER TABLE video_sessions RENAME TO video_sessions_legacy")
    _create_current_schema(cursor)

    legacy_columns = _get_table_columns(cursor, "video_sessions_legacy")
    caisse_expr = "caisse_id" if "caisse_id" in legacy_columns else "section_id"
    end_time_expr = "end_time" if "end_time" in legacy_columns else "NULL"
    created_at_expr = "created_at" if "created_at" in legacy_columns else "CURRENT_TIMESTAMP"

    cursor.execute(f"""
        INSERT INTO video_sessions (
            id,
            video_source,
            establishment_id,
            caisse_id,
            start_time,
            end_time,
            created_at
        )
        SELECT
            id,
            video_source,
            establishment_id,
            {caisse_expr},
            start_time,
            {end_time_expr},
            {created_at_expr}
        FROM video_sessions_legacy
    """)
    cursor.execute("DROP TABLE video_sessions_legacy")


def init_db() -> None:
    """Initialize database schema if it doesn't exist. Idempotent - safe to call multiple times."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_keys = OFF")
    _create_current_schema(cursor)
    _migrate_feed_configs_schema(cursor)
    _migrate_legacy_sections_to_caisses(cursor)
    _migrate_legacy_video_sessions(cursor)
    cursor.execute("PRAGMA foreign_keys = ON")

    conn.commit()
    conn.close()


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory for dict-like rows."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ============================================================================
# ESTABLISHMENT OPERATIONS
# ============================================================================

def create_establishment(name: str) -> int:
    """
    Create a new establishment.

    Args:
        name: Establishment name (unique)

    Returns:
        Establishment ID

    Raises:
        sqlite3.IntegrityError: If establishment name already exists
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO establishments (name) VALUES (?)", (name,))
        conn.commit()
        est_id = cursor.lastrowid
        return cast(int, est_id)
    finally:
        conn.close()


def get_establishments() -> List[Dict[str, Any]]:
    """Get all establishments."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, created_at FROM establishments ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_establishment_by_id(est_id: int) -> Optional[Dict[str, Any]]:
    """Get establishment by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, created_at FROM establishments WHERE id = ?", (est_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ============================================================================
# CAISSE OPERATIONS
# ============================================================================

def create_caisse(name: str, establishment_id: int, zone_points: Optional[List] = None) -> int:
    """
    Create a new caisse within an establishment.

    Args:
        name: Caisse name or number (unique within establishment)
        establishment_id: Parent establishment ID
        zone_points: Optional list of [x, y] coordinates defining zone polygon

    Returns:
        Caisse ID

    Raises:
        sqlite3.IntegrityError: If caisse name already exists in this establishment
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        zone_json = json.dumps(zone_points) if zone_points else None
        cursor.execute(
            "INSERT INTO caisses (name, establishment_id, zone_points_json) VALUES (?, ?, ?)",
            (name, establishment_id, zone_json)
        )
        conn.commit()
        caisse_id = cursor.lastrowid
        return cast(int, caisse_id)
    finally:
        conn.close()


def get_caisses_by_establishment(establishment_id: int) -> List[Dict[str, Any]]:
    """Get all caisses for an establishment."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, name, establishment_id, zone_points_json, created_at FROM caisses WHERE establishment_id = ? ORDER BY name",
            (establishment_id,)
        )
        caisses = []
        for row in cursor.fetchall():
            caisse = dict(row)
            if caisse['zone_points_json']:
                caisse['zone_points'] = json.loads(caisse['zone_points_json'])
            else:
                caisse['zone_points'] = None
            caisses.append(caisse)
        return caisses
    finally:
        conn.close()


def get_caisse_by_id(caisse_id: int) -> Optional[Dict[str, Any]]:
    """Get caisse by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, name, establishment_id, zone_points_json, created_at FROM caisses WHERE id = ?",
            (caisse_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        caisse = dict(row)
        if caisse['zone_points_json']:
            caisse['zone_points'] = json.loads(caisse['zone_points_json'])
        else:
            caisse['zone_points'] = None
        return caisse
    finally:
        conn.close()


def update_caisse_zone_points(caisse_id: int, zone_points: List) -> None:
    """Update zone points for a caisse."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        zone_json = json.dumps(zone_points)
        cursor.execute("UPDATE caisses SET zone_points_json = ? WHERE id = ?", (zone_json, caisse_id))
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# VIDEO SESSION OPERATIONS
# ============================================================================

def create_video_session(
    video_source: str,
    establishment_id: Optional[int] = None,
    caisse_id: Optional[int] = None,
) -> int:
    """
    Create a video session record linking video to metadata.

    Args:
        video_source: File path or RTSP URL
        establishment_id: Associated establishment
        caisse_id: Associated caisse

    Returns:
        Video session ID
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO video_sessions (video_source, establishment_id, caisse_id, start_time) VALUES (?, ?, ?, ?)",
            (video_source, establishment_id, caisse_id, datetime.now())
        )
        conn.commit()
        session_id = cursor.lastrowid
        return cast(int, session_id)
    finally:
        conn.close()


def get_metadata_for_video(video_source: str) -> Optional[Dict[str, Any]]:
    """
    Get the most recent metadata for a video source.

    Returns:
        Dict with keys: establishment_name, caisse_name (or None if not available)
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT
                e.name as establishment_name,
                c.name as caisse_name
            FROM video_sessions vs
            LEFT JOIN establishments e ON vs.establishment_id = e.id
            LEFT JOIN caisses c ON vs.caisse_id = c.id
            WHERE vs.video_source = ?
            ORDER BY vs.created_at DESC
            LIMIT 1
        """, (video_source,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def end_video_session(session_id: int) -> None:
    """Mark video session as ended."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE video_sessions SET end_time = ? WHERE id = ?",
            (datetime.now(), session_id)
        )
        conn.commit()
    finally:
        conn.close()


def end_open_video_sessions() -> int:
    """Close any sessions left open by a previous backend process."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE video_sessions SET end_time = ? WHERE end_time IS NULL",
            (datetime.now(),)
        )
        conn.commit()
        return cast(int, cursor.rowcount)
    finally:
        conn.close()


# ============================================================================
# FEED CONFIG OPERATIONS
# ============================================================================

def upsert_feed_config(
    *,
    feed_id: str,
    name: str,
    source: str,
    model_size: str,
    status: str,
    log_level: str = "INFO",
    webhook_enabled: bool = True,
    created_at: datetime,
    updated_at: datetime,
    manager_user_id: Optional[int] = None,
    queue_length_warning: int = 8,
    rtsp_username: Optional[str] = None,
    rtsp_password: Optional[str] = None,
    rtsp_transport: Optional[str] = None,
    establishment_id: Optional[int] = None,
    caisse_id: Optional[int] = None,
    zone_points: Optional[List[List[float]]] = None,
    last_error: Optional[str] = None,
) -> None:
    """Create or update a persisted feed configuration."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        zone_json = json.dumps(zone_points) if zone_points else None
        cursor.execute(
            """
            INSERT INTO feed_configs (
                feed_id,
                name,
                source,
                manager_user_id,
                model_size,
                status,
                log_level,
                webhook_enabled,
                queue_length_warning,
                rtsp_username,
                rtsp_password,
                rtsp_transport,
                establishment_id,
                caisse_id,
                zone_points_json,
                last_error,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(feed_id) DO UPDATE SET
                name = excluded.name,
                source = excluded.source,
                manager_user_id = excluded.manager_user_id,
                model_size = excluded.model_size,
                status = excluded.status,
                log_level = excluded.log_level,
                webhook_enabled = excluded.webhook_enabled,
                queue_length_warning = excluded.queue_length_warning,
                rtsp_username = excluded.rtsp_username,
                rtsp_password = excluded.rtsp_password,
                rtsp_transport = excluded.rtsp_transport,
                establishment_id = excluded.establishment_id,
                caisse_id = excluded.caisse_id,
                zone_points_json = excluded.zone_points_json,
                last_error = excluded.last_error,
                updated_at = excluded.updated_at
            """,
            (
                feed_id,
                name,
                source,
                manager_user_id,
                model_size,
                status,
                log_level,
                int(webhook_enabled),
                queue_length_warning,
                rtsp_username,
                rtsp_password,
                rtsp_transport,
                establishment_id,
                caisse_id,
                zone_json,
                last_error,
                created_at.isoformat(),
                updated_at.isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_feed_configs() -> List[Dict[str, Any]]:
    """Return all persisted feed configurations in creation order."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT
                feed_id,
                name,
                source,
                manager_user_id,
                model_size,
                status,
                log_level,
                webhook_enabled,
                queue_length_warning,
                rtsp_username,
                rtsp_password,
                rtsp_transport,
                establishment_id,
                caisse_id,
                zone_points_json,
                last_error,
                created_at,
                updated_at
            FROM feed_configs
            ORDER BY created_at, feed_id
            """
        )
        feed_configs = []
        for row in cursor.fetchall():
            feed = dict(row)
            if feed["zone_points_json"]:
                feed["zone_points"] = json.loads(feed["zone_points_json"])
            else:
                feed["zone_points"] = None
            feed_configs.append(feed)
        return feed_configs
    finally:
        conn.close()


def delete_feed_config(feed_id: str) -> None:
    """Delete a persisted feed configuration."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM feed_configs WHERE feed_id = ?", (feed_id,))
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# ALERT HISTORY OPERATIONS
# ============================================================================

def archive_alert_payload(payload: Dict[str, Any]) -> int:
    """Persist an incoming queue alert payload as one row per alert."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        metrics = payload.get("metrics") or {}
        alerts = payload.get("alerts") or []
        serialized_payload = json.dumps(payload, default=str)
        rows_inserted = 0

        if not alerts:
            cursor.execute(
                """
                INSERT INTO alert_history (
                    timestamp,
                    camera_id,
                    zone_id,
                    alert_type,
                    severity,
                    message,
                    value,
                    threshold,
                    people_in_zone,
                    arrival_rate,
                    service_rate,
                    wait_time_seconds,
                    queue_stable,
                    raw_detection_count,
                    fps,
                    alerts_count,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("timestamp"),
                    payload.get("camera_id"),
                    payload.get("zone_id"),
                    payload.get("alert_type"),
                    payload.get("alert_severity") or payload.get("severity"),
                    payload.get("alert_reason") or payload.get("message"),
                    payload.get("alert_value") or payload.get("value"),
                    payload.get("alert_threshold") or payload.get("threshold"),
                    metrics.get("people_in_zone"),
                    metrics.get("arrival_rate"),
                    metrics.get("service_rate"),
                    metrics.get("wait_time_seconds"),
                    int(bool(metrics.get("queue_stable", True))),
                    payload.get("raw_detection_count"),
                    payload.get("fps"),
                    0,
                    serialized_payload,
                ),
            )
            conn.commit()
            return 1

        for alert in alerts:
            cursor.execute(
                """
                INSERT INTO alert_history (
                    timestamp,
                    camera_id,
                    zone_id,
                    alert_type,
                    severity,
                    message,
                    value,
                    threshold,
                    people_in_zone,
                    arrival_rate,
                    service_rate,
                    wait_time_seconds,
                    queue_stable,
                    raw_detection_count,
                    fps,
                    alerts_count,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("timestamp"),
                    payload.get("camera_id"),
                    payload.get("zone_id"),
                    alert.get("type"),
                    alert.get("severity"),
                    alert.get("message"),
                    alert.get("value"),
                    alert.get("threshold"),
                    metrics.get("people_in_zone"),
                    metrics.get("arrival_rate"),
                    metrics.get("service_rate"),
                    metrics.get("wait_time_seconds"),
                    int(bool(metrics.get("queue_stable", True))),
                    payload.get("raw_detection_count"),
                    payload.get("fps"),
                    len(alerts),
                    serialized_payload,
                ),
            )
            rows_inserted += 1

        conn.commit()
        return rows_inserted
    finally:
        conn.close()


def _build_alert_history_filters(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    camera_id: str | None = None,
    zone_id: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    scope_to_active_feeds: bool = False,
    owner_user_id: int | None = None,
) -> tuple[str, list[Any]]:
    """Build a safe WHERE clause for alert_history queries."""
    clauses: list[str] = []
    params: list[Any] = []

    if from_date:
        clauses.append("date(timestamp) >= date(?)")
        params.append(from_date)
    if to_date:
        clauses.append("date(timestamp) <= date(?)")
        params.append(to_date)
    if camera_id:
        clauses.append("camera_id = ?")
        params.append(camera_id)
    if zone_id:
        clauses.append("zone_id = ?")
        params.append(zone_id)
    if severity:
        clauses.append("severity = ?")
        params.append(severity)
    if alert_type:
        clauses.append("alert_type = ?")
        params.append(alert_type)

    if scope_to_active_feeds:
        if owner_user_id is None:
            clauses.append("camera_id IN (SELECT feed_id FROM feed_configs)")
        else:
            clauses.append(
                """
                camera_id IN (
                    SELECT feed_id
                    FROM feed_configs
                    WHERE manager_user_id = ? OR manager_user_id IS NULL
                )
                """
            )
            params.append(owner_user_id)

    if not clauses:
        return "", params

    return "WHERE " + " AND ".join(clauses), params


def query_alert_history(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    camera_id: str | None = None,
    zone_id: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
) -> List[Dict[str, Any]]:
    """Return archived alert rows matching the provided filters."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        where_clause, params = _build_alert_history_filters(
            from_date=from_date,
            to_date=to_date,
            camera_id=camera_id,
            zone_id=zone_id,
            severity=severity,
            alert_type=alert_type,
        )
        cursor.execute(
            f"""
            SELECT
                id,
                timestamp,
                camera_id,
                zone_id,
                alert_type,
                severity,
                message,
                value,
                threshold,
                people_in_zone,
                arrival_rate,
                service_rate,
                wait_time_seconds,
                queue_stable,
                raw_detection_count,
                fps,
                alerts_count,
                payload_json,
                created_at
            FROM alert_history
            {where_clause}
            ORDER BY timestamp DESC, id DESC
            """,
            params,
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_overview_statistics(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    owner_user_id: int | None = None,
) -> Dict[str, Any]:
    """Return dashboard-level aggregate statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        where_clause, params = _build_alert_history_filters(
            from_date=from_date,
            to_date=to_date,
            scope_to_active_feeds=True,
            owner_user_id=owner_user_id,
        )
        cursor.execute(
            f"""
            SELECT
                COALESCE(ROUND(AVG(wait_time_seconds), 2), 0) AS avg_wait_time,
                COALESCE(MAX(people_in_zone), 0) AS peak_queue_length,
                COALESCE(ROUND(100.0 * AVG(CASE WHEN queue_stable = 1 THEN 1.0 ELSE 0.0 END), 2), 0) AS stability_score,
                COUNT(*) AS total_alerts,
                COALESCE(ROUND(AVG(people_in_zone), 2), 0) AS avg_people_in_zone,
                COALESCE(ROUND(AVG(service_rate), 3), 0) AS avg_service_rate,
                COALESCE(ROUND(AVG(arrival_rate), 3), 0) AS avg_arrival_rate
            FROM alert_history
            {where_clause}
            """,
            params,
        )
        row = cursor.fetchone() or {}
        return dict(row)
    finally:
        conn.close()


def get_zone_statistics(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    owner_user_id: int | None = None,
) -> List[Dict[str, Any]]:
    """Return aggregate metrics grouped by camera and zone."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        where_clause, params = _build_alert_history_filters(
            from_date=from_date,
            to_date=to_date,
            scope_to_active_feeds=True,
            owner_user_id=owner_user_id,
        )
        cursor.execute(
            f"""
            SELECT
                camera_id,
                zone_id,
                COUNT(*) AS total_alerts,
                COALESCE(ROUND(AVG(wait_time_seconds), 2), 0) AS avg_wait_time,
                COALESCE(MAX(wait_time_seconds), 0) AS max_wait_time,
                COALESCE(MIN(wait_time_seconds), 0) AS min_wait_time,
                COALESCE(ROUND(AVG(people_in_zone), 2), 0) AS avg_people_in_zone,
                COALESCE(MAX(people_in_zone), 0) AS peak_queue_length,
                COALESCE(ROUND(AVG(service_rate), 3), 0) AS avg_service_rate,
                COALESCE(ROUND(100.0 * AVG(CASE WHEN queue_stable = 1 THEN 1.0 ELSE 0.0 END), 2), 0) AS stability_score
            FROM alert_history
            {where_clause}
            GROUP BY camera_id, zone_id
            ORDER BY avg_wait_time DESC, total_alerts DESC, camera_id, zone_id
            """,
            params,
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_time_based_statistics(
    *,
    period: str = "daily",
    from_date: str | None = None,
    to_date: str | None = None,
    owner_user_id: int | None = None,
) -> List[Dict[str, Any]]:
    """Return aggregated time-series metrics for a chosen period."""
    period_key = period.lower().strip()
    if period_key == "hourly":
        period_expr = "strftime('%H', timestamp)"
        order_expr = "period"
    elif period_key == "weekly":
        period_expr = "strftime('%Y-W%W', timestamp)"
        order_expr = "period"
    else:
        period_expr = "date(timestamp)"
        order_expr = "period"
        period_key = "daily"

    conn = get_connection()
    cursor = conn.cursor()
    try:
        where_clause, params = _build_alert_history_filters(
            from_date=from_date,
            to_date=to_date,
            scope_to_active_feeds=True,
            owner_user_id=owner_user_id,
        )
        cursor.execute(
            f"""
            SELECT
                {period_expr} AS period,
                COUNT(*) AS alert_count,
                COALESCE(ROUND(AVG(wait_time_seconds), 2), 0) AS avg_wait_time,
                COALESCE(MAX(people_in_zone), 0) AS peak_queue_length,
                COALESCE(ROUND(100.0 * AVG(CASE WHEN queue_stable = 1 THEN 1.0 ELSE 0.0 END), 2), 0) AS stability_score,
                COALESCE(ROUND(AVG(service_rate), 3), 0) AS avg_service_rate,
                COALESCE(ROUND(AVG(arrival_rate), 3), 0) AS avg_arrival_rate
            FROM alert_history
            {where_clause}
            GROUP BY period
            ORDER BY {order_expr}
            """,
            params,
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_alert_distribution_statistics(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    owner_user_id: int | None = None,
) -> List[Dict[str, Any]]:
    """Return alert type and severity frequency counts."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        where_clause, params = _build_alert_history_filters(
            from_date=from_date,
            to_date=to_date,
            scope_to_active_feeds=True,
            owner_user_id=owner_user_id,
        )
        alert_only_clause = "WHERE alert_type IS NOT NULL AND severity IS NOT NULL"
        if where_clause:
            alert_only_clause = f"{where_clause} AND alert_type IS NOT NULL AND severity IS NOT NULL"
        cursor.execute(
            f"""
            SELECT
                alert_type,
                severity,
                COUNT(*) AS count
            FROM alert_history
            {alert_only_clause}
            GROUP BY alert_type, severity
            ORDER BY count DESC, alert_type, severity
            """,
            params,
        )
        rows = [dict(row) for row in cursor.fetchall()]

        total_where_clause, total_params = _build_alert_history_filters(
            from_date=from_date,
            to_date=to_date,
            scope_to_active_feeds=True,
            owner_user_id=owner_user_id,
        )
        if total_where_clause:
            total_where_clause = f"{total_where_clause} AND alert_type IS NOT NULL AND severity IS NOT NULL"
        else:
            total_where_clause = "WHERE alert_type IS NOT NULL AND severity IS NOT NULL"

        cursor.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM alert_history
            {total_where_clause}
            """,
            total_params,
        )
        total_row = cursor.fetchone() or {"total": 0}
        total = int(total_row["total"] if isinstance(total_row, sqlite3.Row) else total_row.get("total", 0))

        if total <= 0:
            return []

        for row in rows:
            row["percentage"] = round((int(row.get("count", 0)) / total) * 100.0, 2)
        return rows
    finally:
        conn.close()


# ============================================================================
# AUTH / USER OPERATIONS
# ============================================================================

def create_user(*, email: str, display_name: str, password_hash: str, role: str) -> int:
    """Create a new user account and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        now_iso = datetime.now().isoformat()
        cursor.execute(
            """
            INSERT INTO users (email, display_name, password_hash, role, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email.strip().lower(), display_name.strip(), password_hash, role, now_iso),
        )
        conn.commit()
        user_id = cursor.lastrowid
        return cast(int, user_id)
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Fetch one user by email."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT
                id,
                email,
                display_name,
                password_hash,
                role,
                is_active,
                failed_login_attempts,
                locked_until,
                last_login_at,
                created_at,
                updated_at
            FROM users
            WHERE email = ?
            """,
            (email.strip().lower(),),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch one user by identifier."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT
                id,
                email,
                display_name,
                password_hash,
                role,
                is_active,
                failed_login_attempts,
                locked_until,
                last_login_at,
                created_at,
                updated_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_users_by_role(role: str) -> List[Dict[str, Any]]:
    """List users belonging to a role."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT
                id,
                email,
                display_name,
                role,
                is_active,
                failed_login_attempts,
                locked_until,
                last_login_at,
                created_at,
                updated_at
            FROM users
            WHERE role = ?
            ORDER BY created_at DESC
            """,
            (role,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def set_user_active(user_id: int, is_active: bool) -> bool:
    """Activate or deactivate one user account."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET
                is_active = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (int(is_active), datetime.now().isoformat(), user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_user_password_hash(user_id: int, password_hash: str) -> bool:
    """Update password hash and clear lockout counters for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET
                password_hash = ?,
                failed_login_attempts = 0,
                locked_until = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (password_hash, datetime.now().isoformat(), user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def record_successful_login(user_id: int) -> None:
    """Reset login-failure counters and record last-login timestamp."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        now_iso = datetime.now().isoformat()
        cursor.execute(
            """
            UPDATE users
            SET
                failed_login_attempts = 0,
                locked_until = NULL,
                last_login_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (now_iso, now_iso, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def record_failed_login_attempt(user_id: int, *, locked_until: Optional[str] = None) -> int:
    """Increment failed-login count and optionally set lockout timestamp."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET
                failed_login_attempts = failed_login_attempts + 1,
                locked_until = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (locked_until, datetime.now().isoformat(), user_id),
        )
        conn.commit()
        cursor.execute("SELECT failed_login_attempts FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return int(row["failed_login_attempts"]) if row else 0
    finally:
        conn.close()


def create_refresh_session(
    *,
    session_id: str,
    user_id: int,
    token_hash: str,
    expires_at: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> None:
    """Persist a refresh-token session entry."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO auth_refresh_sessions (
                id,
                user_id,
                token_hash,
                expires_at,
                ip_address,
                user_agent
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, user_id, token_hash, expires_at, ip_address, user_agent),
        )
        conn.commit()
    finally:
        conn.close()


def get_refresh_session_by_token_hash(token_hash: str) -> Optional[Dict[str, Any]]:
    """Load refresh-token session by hashed token value."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT
                id,
                user_id,
                token_hash,
                expires_at,
                created_at,
                last_used_at,
                revoked_at,
                ip_address,
                user_agent
            FROM auth_refresh_sessions
            WHERE token_hash = ?
            """,
            (token_hash,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def revoke_refresh_session(session_id: str) -> None:
    """Mark one refresh session as revoked."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE auth_refresh_sessions
            SET revoked_at = ?, last_used_at = ?
            WHERE id = ?
            """,
            (datetime.now().isoformat(), datetime.now().isoformat(), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def revoke_refresh_session_by_token_hash(token_hash: str) -> None:
    """Revoke one refresh session selected by token hash."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        now_iso = datetime.now().isoformat()
        cursor.execute(
            """
            UPDATE auth_refresh_sessions
            SET revoked_at = ?, last_used_at = ?
            WHERE token_hash = ?
            """,
            (now_iso, now_iso, token_hash),
        )
        conn.commit()
    finally:
        conn.close()


def touch_refresh_session(session_id: str) -> None:
    """Update the last-used timestamp for one refresh session."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE auth_refresh_sessions SET last_used_at = ? WHERE id = ?",
            (datetime.now().isoformat(), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def create_auth_audit_event(
    *,
    user_id: Optional[int],
    event_type: str,
    event_status: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist an authentication and authorization audit event."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        details_json = json.dumps(details, default=str) if details is not None else None
        cursor.execute(
            """
            INSERT INTO auth_audit_log (user_id, event_type, event_status, details_json)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, event_type, event_status, details_json),
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# HELPER FUNCTIONS FOR GUI
# ============================================================================

def get_full_hierarchy() -> Dict[int, Dict[str, Any]]:
    """
    Get complete hierarchy: establishments with caisses.

    Returns:
        Dict[establishment_id] -> {name, caisses: Dict[caisse_id] -> {name, zone_points}}
    """
    conn = get_connection()
    cursor = conn.cursor()

    hierarchy = {}

    # Get all establishments
    cursor.execute("SELECT id, name FROM establishments ORDER BY name")
    for est_row in cursor.fetchall():
        est_id = est_row['id']
        hierarchy[est_id] = {
            'name': est_row['name'],
            'caisses': {}
        }

        # Get caisses for this establishment
        cursor.execute(
            "SELECT id, name, zone_points_json FROM caisses WHERE establishment_id = ? ORDER BY name",
            (est_id,)
        )
        for caisse_row in cursor.fetchall():
            caisse_id = caisse_row['id']
            zone_points = json.loads(caisse_row['zone_points_json']) if caisse_row['zone_points_json'] else None
            hierarchy[est_id]['caisses'][caisse_id] = {
                'name': caisse_row['name'],
                'zone_points': zone_points,
            }

    conn.close()
    return hierarchy


if __name__ == "__main__":
    # Test database initialization
    init_db()
    print(f"Database initialized at: {DB_PATH}")
