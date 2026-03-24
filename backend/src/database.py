"""Database module for queue metrics metadata tracking.

Provides SQLite database initialization and helper functions for managing:
- Establishments (companies/stores)
- Caisses (checkout counters/registers)
- Video sessions (tracking which metadata was used for each video)
"""

import sqlite3
import json
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
            FOREIGN KEY (caisse_id) REFERENCES caisses (id) ON DELETE SET NULL
        )
    """)


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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(feed_id) DO UPDATE SET
                name = excluded.name,
                source = excluded.source,
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
