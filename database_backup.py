import sqlite3
import pandas as pd

DB_PATH = "dairy_farm.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def initialize_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cows (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            name                 TEXT NOT NULL,
            tag_number           TEXT UNIQUE NOT NULL,
            breed                TEXT DEFAULT 'Friesian',
            date_of_birth        TEXT,
            lactation_start_date TEXT,
            status               TEXT DEFAULT 'active',
            notes                TEXT
        );

        CREATE TABLE IF NOT EXISTS milk_records (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            cow_id         INTEGER NOT NULL,
            record_date    TEXT NOT NULL,
            morning_yield  REAL DEFAULT 0,
            evening_yield  REAL DEFAULT 0,
            total_yield    REAL DEFAULT 0,
            notes          TEXT,
            FOREIGN KEY (cow_id) REFERENCES cows(id),
            UNIQUE(cow_id, record_date)
        );

        CREATE TABLE IF NOT EXISTS health_records (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cow_id          INTEGER NOT NULL,
            record_date     TEXT NOT NULL,
            condition       TEXT NOT NULL,
            treatment       TEXT,
            vet_notes       TEXT,
            follow_up_date  TEXT,
            resolved        INTEGER DEFAULT 0,
            FOREIGN KEY (cow_id) REFERENCES cows(id)
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            cow_id      INTEGER NOT NULL,
            alert_date  TEXT NOT NULL,
            alert_type  TEXT NOT NULL,
            message     TEXT NOT NULL,
            severity    TEXT DEFAULT 'warning',
            resolved    INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cow_id) REFERENCES cows(id)
        );
    """)
    conn.commit()
    conn.close()


# ── Cow operations ──────────────────────────────────────────────────────────

def add_cow(name, tag_number, breed, dob, lactation_start, notes=""):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO cows (name, tag_number, breed, date_of_birth, lactation_start_date, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, tag_number, breed, dob, lactation_start, notes),
        )
        conn.commit()
        return True, "Cow added successfully"
    except sqlite3.IntegrityError:
        return False, f"Tag number '{tag_number}' already exists"
    finally:
        conn.close()


def get_all_cows():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM cows WHERE status = 'active' ORDER BY name", conn)
    conn.close()
    return df


def get_cow_by_id(cow_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM cows WHERE id = ?", (cow_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_cow_status(cow_id, status):
    conn = get_connection()
    conn.execute("UPDATE cows SET status = ? WHERE id = ?", (status, cow_id))
    conn.commit()
    conn.close()


# ── Milk record operations ───────────────────────────────────────────────────

def add_milk_record(cow_id, record_date, morning, evening, notes=""):
    total = round(morning + evening, 2)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO milk_records "
            "(cow_id, record_date, morning_yield, evening_yield, total_yield, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (cow_id, record_date, morning, evening, total, notes),
        )
        conn.commit()
        return True, "Record saved"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def get_milk_records(cow_id=None, days=90):
    conn = get_connection()
    base_query = """
        SELECT m.*, c.name AS cow_name, c.tag_number, c.breed,
               c.lactation_start_date,
               CAST(julianday(m.record_date) - julianday(c.lactation_start_date) + 1 AS INTEGER) AS dim
        FROM milk_records m
        JOIN cows c ON m.cow_id = c.id
    """
    if cow_id:
        df = pd.read_sql(
            base_query + " WHERE m.cow_id = ? AND m.record_date >= date('now', ?) ORDER BY m.record_date",
            conn, params=(cow_id, f"-{days} days"),
        )
    else:
        df = pd.read_sql(
            base_query + " WHERE m.record_date >= date('now', ?) ORDER BY m.record_date, c.name",
            conn, params=(f"-{days} days",),
        )
    conn.close()
    return df


def get_all_milk_records_for_cow(cow_id):
    conn = get_connection()
    df = pd.read_sql(
        """SELECT m.*, c.name AS cow_name, c.lactation_start_date,
                  CAST(julianday(m.record_date) - julianday(c.lactation_start_date) + 1 AS INTEGER) AS dim
           FROM milk_records m
           JOIN cows c ON m.cow_id = c.id
           WHERE m.cow_id = ?
           ORDER BY m.record_date""",
        conn, params=(cow_id,),
    )
    conn.close()
    return df


# ── Health record operations ─────────────────────────────────────────────────

def add_health_record(cow_id, record_date, condition, treatment, vet_notes, follow_up):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO health_records (cow_id, record_date, condition, treatment, vet_notes, follow_up_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (cow_id, record_date, condition, treatment, vet_notes, follow_up),
        )
        conn.commit()
        return True, "Health record saved"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def get_health_records(cow_id=None):
    conn = get_connection()
    base = """
        SELECT h.*, c.name AS cow_name, c.tag_number
        FROM health_records h
        JOIN cows c ON h.cow_id = c.id
    """
    if cow_id:
        df = pd.read_sql(base + " WHERE h.cow_id = ? ORDER BY h.record_date DESC", conn, params=(cow_id,))
    else:
        df = pd.read_sql(base + " ORDER BY h.record_date DESC", conn)
    conn.close()
    return df


def resolve_health_record(record_id):
    conn = get_connection()
    conn.execute("UPDATE health_records SET resolved = 1 WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


# ── Alert operations ─────────────────────────────────────────────────────────

def save_alert(cow_id, alert_date, alert_type, message, severity):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM alerts WHERE cow_id = ? AND alert_type = ? AND alert_date = ? AND resolved = 0",
        (cow_id, alert_type, alert_date),
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO alerts (cow_id, alert_date, alert_type, message, severity) VALUES (?, ?, ?, ?, ?)",
            (cow_id, alert_date, alert_type, message, severity),
        )
        conn.commit()
    conn.close()


def get_active_alerts():
    conn = get_connection()
    df = pd.read_sql(
        """SELECT a.*, c.name AS cow_name, c.tag_number
           FROM alerts a
           JOIN cows c ON a.cow_id = c.id
           WHERE a.resolved = 0
           ORDER BY CASE a.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                    a.alert_date DESC""",
        conn,
    )
    conn.close()
    return df


def resolve_alert(alert_id):
    conn = get_connection()
    conn.execute("UPDATE alerts SET resolved = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()


def clear_old_resolved_alerts(days=30):
    conn = get_connection()
    conn.execute(
        "DELETE FROM alerts WHERE resolved = 1 AND alert_date < date('now', ?)",
        (f"-{days} days",),
    )
    conn.commit()
    conn.close()


# ── Summary helpers ──────────────────────────────────────────────────────────

def get_herd_summary():
    conn = get_connection()
    total_cows = conn.execute("SELECT COUNT(*) FROM cows WHERE status = 'active'").fetchone()[0]
    today_prod = conn.execute(
        "SELECT COALESCE(SUM(total_yield), 0) FROM milk_records WHERE record_date = date('now')"
    ).fetchone()[0]
    active_alerts = conn.execute("SELECT COUNT(*) FROM alerts WHERE resolved = 0").fetchone()[0]
    yesterday_prod = conn.execute(
        "SELECT COALESCE(SUM(total_yield), 0) FROM milk_records WHERE record_date = date('now', '-1 day')"
    ).fetchone()[0]
    conn.close()
    return total_cows, today_prod, yesterday_prod, active_alerts


def cow_exists():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM cows").fetchone()[0]
    conn.close()
    return count > 0
