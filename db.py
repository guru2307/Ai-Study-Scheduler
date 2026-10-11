"""
db.py - SQLite database layer for AI Study Scheduler.

All data access goes through this module so app.py stays clean.
"""
import sqlite3
import json
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "database.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

@contextmanager
def db_cursor(commit=False):
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    finally:
        conn.close()

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        topic TEXT NOT NULL,
        deadline TEXT NOT NULL,
        knowledge_level TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        difficulty_reason TEXT,
        estimated_hours REAL NOT NULL,
        hours_reason TEXT,
        priority_score INTEGER NOT NULL,
        priority_level TEXT NOT NULL,
        priority_reason TEXT,
        study_techniques TEXT,     -- JSON array
        study_tip TEXT,
        notes TEXT,
        completed_hours REAL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS preferences (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        hours_per_day REAL NOT NULL DEFAULT 4,
        session_length TEXT NOT NULL DEFAULT '1 hour',
        start_date TEXT,
        preferred_time TEXT NOT NULL DEFAULT 'Morning'
    );

    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
        date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        subject_name TEXT NOT NULL,
        topic TEXT NOT NULL,
        duration_minutes INTEGER NOT NULL,
        priority_level TEXT NOT NULL,
        technique TEXT,
        is_break INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
        subject_name TEXT,
        topic TEXT,
        filename TEXT NOT NULL,
        extracted_text TEXT,
        important_topics TEXT,      -- JSON
        key_definitions TEXT,       -- JSON
        important_facts TEXT,       -- JSON
        revision_areas TEXT,        -- JSON
        analysis_error TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS mock_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
        subject_name TEXT,
        topic TEXT,
        num_questions INTEGER NOT NULL,
        questions TEXT NOT NULL,   -- JSON array
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mock_test_id INTEGER REFERENCES mock_tests(id) ON DELETE CASCADE,
        subject_name TEXT,
        topic TEXT,
        total_questions INTEGER NOT NULL,
        correct_answers INTEGER NOT NULL,
        wrong_answers INTEGER NOT NULL,
        score REAL NOT NULL,
        percentage REAL NOT NULL,
        performance TEXT,
        answers TEXT,   -- JSON: user's answers + per-question correctness
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)

    cur.execute("SELECT COUNT(*) as c FROM preferences")
    if cur.fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO preferences (id, hours_per_day, session_length, start_date, preferred_time) "
            "VALUES (1, 4, '1 hour', date('now'), 'Morning')"
        )

    conn.commit()
    conn.close()

def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

def rows_to_list(rows):
    return [dict(r) for r in rows]

def json_loads_safe(value, default=None):
    if not value:
        return default if default is not None else []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []
