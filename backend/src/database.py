"""
Database module for queue metrics metadata tracking.

Provides SQLite database initialization and helper functions for managing:
- Establishments (companies/stores)
- Sections (checkout zones/areas)
- Employees (cashiers/staff)
- Video Sessions (tracking which metadata was used for each video)
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any, cast


DB_PATH = Path(__file__).parent.parent / "data" / "queue_metrics.db"


def init_db() -> None:
    """Initialize database schema if it doesn't exist. Idempotent - safe to call multiple times."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")

    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS establishments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sections (
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
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            section_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (section_id) REFERENCES sections (id),
            UNIQUE(name, section_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_source TEXT NOT NULL,
            establishment_id INTEGER,
            section_id INTEGER,
            employee_id INTEGER,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (establishment_id) REFERENCES establishments (id),
            FOREIGN KEY (section_id) REFERENCES sections (id),
            FOREIGN KEY (employee_id) REFERENCES employees (id)
        )
    """)

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
# SECTION OPERATIONS
# ============================================================================

def create_section(name: str, establishment_id: int, zone_points: Optional[List] = None) -> int:
    """
    Create a new section within an establishment.

    Args:
        name: Section name (unique within establishment)
        establishment_id: Parent establishment ID
        zone_points: Optional list of [x, y] coordinates defining zone polygon

    Returns:
        Section ID

    Raises:
        sqlite3.IntegrityError: If section name already exists in this establishment
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        zone_json = json.dumps(zone_points) if zone_points else None
        cursor.execute(
            "INSERT INTO sections (name, establishment_id, zone_points_json) VALUES (?, ?, ?)",
            (name, establishment_id, zone_json)
        )
        conn.commit()
        section_id = cursor.lastrowid
        return cast(int, section_id)
    finally:
        conn.close()


def get_sections_by_establishment(establishment_id: int) -> List[Dict[str, Any]]:
    """Get all sections for an establishment."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, name, establishment_id, zone_points_json, created_at FROM sections WHERE establishment_id = ? ORDER BY name",
            (establishment_id,)
        )
        sections = []
        for row in cursor.fetchall():
            section = dict(row)
            if section['zone_points_json']:
                section['zone_points'] = json.loads(section['zone_points_json'])
            else:
                section['zone_points'] = None
            sections.append(section)
        return sections
    finally:
        conn.close()


def get_section_by_id(section_id: int) -> Optional[Dict[str, Any]]:
    """Get section by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, name, establishment_id, zone_points_json, created_at FROM sections WHERE id = ?",
            (section_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        section = dict(row)
        if section['zone_points_json']:
            section['zone_points'] = json.loads(section['zone_points_json'])
        else:
            section['zone_points'] = None
        return section
    finally:
        conn.close()


def update_section_zone_points(section_id: int, zone_points: List) -> None:
    """Update zone points for a section."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        zone_json = json.dumps(zone_points)
        cursor.execute("UPDATE sections SET zone_points_json = ? WHERE id = ?", (zone_json, section_id))
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# EMPLOYEE OPERATIONS
# ============================================================================

def create_employee(name: str, section_id: int) -> int:
    """
    Create a new employee in a section.

    Args:
        name: Employee name (unique within section)
        section_id: Parent section ID

    Returns:
        Employee ID

    Raises:
        sqlite3.IntegrityError: If employee name already exists in this section
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO employees (name, section_id) VALUES (?, ?)",
            (name, section_id)
        )
        conn.commit()
        emp_id = cursor.lastrowid
        return cast(int, emp_id)
    finally:
        conn.close()


def get_employees_by_section(section_id: int) -> List[Dict[str, Any]]:
    """Get all employees for a section."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, name, section_id, created_at FROM employees WHERE section_id = ? ORDER BY name",
            (section_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_employee_by_id(employee_id: int) -> Optional[Dict[str, Any]]:
    """Get employee by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, name, section_id, created_at FROM employees WHERE id = ?",
            (employee_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ============================================================================
# VIDEO SESSION OPERATIONS
# ============================================================================

def create_video_session(
    video_source: str,
    establishment_id: Optional[int] = None,
    section_id: Optional[int] = None,
    employee_id: Optional[int] = None
) -> int:
    """
    Create a video session record linking video to metadata.

    Args:
        video_source: File path or RTSP URL
        establishment_id: Associated establishment
        section_id: Associated section
        employee_id: Associated employee

    Returns:
        Video session ID
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO video_sessions (video_source, establishment_id, section_id, employee_id, start_time) VALUES (?, ?, ?, ?, ?)",
            (video_source, establishment_id, section_id, employee_id, datetime.now())
        )
        conn.commit()
        session_id = cursor.lastrowid
        return cast(int, session_id)
    finally:
        conn.close()


def get_metadata_for_video(video_source: str) -> Optional[Dict[str, Any]]:
    """
    Get the most recent metadata for a video source (establishment, section, employee names).

    Returns:
        Dict with keys: establishment_name, section_name, employee_name (or None if not available)
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT
                e.name as establishment_name,
                s.name as section_name,
                emp.name as employee_name
            FROM video_sessions vs
            LEFT JOIN establishments e ON vs.establishment_id = e.id
            LEFT JOIN sections s ON vs.section_id = s.id
            LEFT JOIN employees emp ON vs.employee_id = emp.id
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


# ============================================================================
# HELPER FUNCTIONS FOR GUI
# ============================================================================

def get_full_hierarchy() -> Dict[int, Dict[str, Any]]:
    """
    Get complete hierarchy: establishments with sections with employees.

    Returns:
        Dict[establishment_id] -> {name, sections: Dict[section_id] -> {name, zone_points, employees}}
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
            'sections': {}
        }

        # Get sections for this establishment
        cursor.execute(
            "SELECT id, name, zone_points_json FROM sections WHERE establishment_id = ? ORDER BY name",
            (est_id,)
        )
        for sec_row in cursor.fetchall():
            sec_id = sec_row['id']
            zone_points = json.loads(sec_row['zone_points_json']) if sec_row['zone_points_json'] else None
            hierarchy[est_id]['sections'][sec_id] = {
                'name': sec_row['name'],
                'zone_points': zone_points,
                'employees': {}
            }

            # Get employees for this section
            cursor.execute(
                "SELECT id, name FROM employees WHERE section_id = ? ORDER BY name",
                (sec_id,)
            )
            for emp_row in cursor.fetchall():
                emp_id = emp_row['id']
                hierarchy[est_id]['sections'][sec_id]['employees'][emp_id] = emp_row['name']

    conn.close()
    return hierarchy


if __name__ == "__main__":
    # Test database initialization
    init_db()
    print(f"Database initialized at: {DB_PATH}")
