"""
seed_qa_data.py — Load controlled QA test dataset for jaspernicole364@gmail.com
===============================================================================
Cows & anomaly rules:
  Tuya   (TU-354) → Rule 1: Z-Score drop  > 3 SD below personal baseline (HIGH)
  Chesa  (CH-175) → Rule 2: Yield < 75 %  of 7-day rolling mean (HIGH)
  Girlie (GL-425) → Rule 3: Sustained linear decline — slope < -0.2, R² > 0.6 (MEDIUM)

Anomalies fire on Days 17-18 (2026-04-17 / 2026-04-18).
Run from the project root:  python seed_qa_data.py
"""

import sqlite3
import bcrypt
from datetime import date, timedelta

DB_PATH           = "dairy_farm.db"
QA_EMAIL          = "jaspernicole364@gmail.com"
QA_PASSWORD       = "DairyQA2026!"   # test-only credential
LACTATION_START   = date(2026, 4, 1)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name     TEXT,
            date_of_birth TEXT,
            farm_name     TEXT,
            is_verified   INTEGER DEFAULT 0,
            created_at    TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS verification_codes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT NOT NULL,
            code       TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used       INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS password_reset_codes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT NOT NULL,
            code       TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used       INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS cows (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id              INTEGER,
            name                 TEXT NOT NULL,
            tag_number           TEXT NOT NULL,
            breed                TEXT DEFAULT 'Friesian',
            date_of_birth        TEXT,
            lactation_start_date TEXT,
            status               TEXT DEFAULT 'active',
            notes                TEXT
        );
        CREATE TABLE IF NOT EXISTS milk_records (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER,
            cow_id        INTEGER NOT NULL,
            record_date   TEXT NOT NULL,
            morning_yield REAL DEFAULT 0,
            evening_yield REAL DEFAULT 0,
            total_yield   REAL DEFAULT 0,
            notes         TEXT,
            FOREIGN KEY (cow_id) REFERENCES cows(id),
            UNIQUE(cow_id, record_date)
        );
        CREATE TABLE IF NOT EXISTS health_records (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER,
            cow_id         INTEGER NOT NULL,
            record_date    TEXT NOT NULL,
            condition      TEXT NOT NULL,
            treatment      TEXT,
            vet_notes      TEXT,
            follow_up_date TEXT,
            resolved       INTEGER DEFAULT 0,
            FOREIGN KEY (cow_id) REFERENCES cows(id)
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            cow_id     INTEGER NOT NULL,
            alert_date TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            message    TEXT NOT NULL,
            severity   TEXT DEFAULT 'warning',
            resolved   INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cow_id) REFERENCES cows(id)
        );
    """)
    conn.commit()


def get_or_create_user(conn) -> int:
    row = conn.execute("SELECT id FROM users WHERE email = ?", (QA_EMAIL,)).fetchone()
    if row:
        print(f"  [users] Found existing account  id={row['id']}")
        return row["id"]

    pw_hash = bcrypt.hashpw(QA_PASSWORD.encode(), bcrypt.gensalt()).decode()
    cur = conn.execute(
        "INSERT INTO users (email, password_hash, full_name, farm_name, is_verified) "
        "VALUES (?, ?, ?, ?, 1)",
        (QA_EMAIL, pw_hash, "QA Tester", "QA Test Farm"),
    )
    conn.commit()
    uid = cur.lastrowid
    print(f"  [users] Created account  id={uid}  email={QA_EMAIL}  password={QA_PASSWORD}")
    return uid


def get_or_create_cow(conn, user_id, name, tag, notes) -> int:
    row = conn.execute(
        "SELECT id FROM cows WHERE user_id = ? AND tag_number = ?",
        (user_id, tag),
    ).fetchone()
    if row:
        print(f"  [cows]  Found existing cow  '{name}' ({tag})  id={row['id']}")
        return row["id"]

    cur = conn.execute(
        "INSERT INTO cows (user_id, name, tag_number, breed, lactation_start_date, notes) "
        "VALUES (?, ?, ?, 'Friesian', ?, ?)",
        (user_id, name, tag, LACTATION_START.isoformat(), notes),
    )
    conn.commit()
    cid = cur.lastrowid
    print(f"  [cows]  Created cow  '{name}' ({tag})  id={cid}")
    return cid


def insert_records(conn, user_id, cow_id, rows):
    """rows = list of (morning, evening) tuples, index 0 = Day 1."""
    inserted = skipped = 0
    for i, (morning, evening) in enumerate(rows):
        rec_date = (LACTATION_START + timedelta(days=i)).isoformat()
        total    = round(morning + evening, 1)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO milk_records "
                "(user_id, cow_id, record_date, morning_yield, evening_yield, total_yield) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, cow_id, rec_date, morning, evening, total),
            )
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"    ERROR on {rec_date}: {e}")
    conn.commit()
    print(f"    Inserted {inserted} records, skipped {skipped} (already present)")


# ── Dataset ───────────────────────────────────────────────────────────────────
#
# Each tuple is (morning_yield, evening_yield).
# Total = morning + evening (computed at insert time).
#
# Design notes
# ------------
# TUYA   Days 1-16 stable ~29 L  → rolling_mean≈29.4, rolling_std≈0.56
#        Days 17-18 drop to 23.5 / 22.8 L
#        Z-day17 = (23.5-29.4)/0.56 ≈ -10.5  → HIGH Rule 1 ✓
#        23.5 > 75%×29.4=22.1  → Rule 2 does NOT fire ✓
#
# CHESA  Days 1-16 stable ~27 L  → rolling_mean≈27.4
#        Days 17-18 drop to 14.0 / 13.5 L
#        14.0 < 75%×27.4=20.6  → HIGH Rule 2 ✓
#
# GIRLIE Days 1-18 linear decline 30→18.2 L  (≈−0.7 L/day)
#        14-day window slope≈−0.70 < −0.2, R²≈0.997 > 0.6 → MEDIUM Rule 3 ✓
#        Yield stays above 75% of rolling mean → Rule 2 does NOT fire ✓

TUYA_RECORDS = [
    # Day  Date         Morning  Evening   Total
    (16.5, 12.0),   # 1  2026-04-01  28.5
    (17.3, 12.5),   # 2  2026-04-02  29.8
    (16.4, 11.8),   # 3  2026-04-03  28.2
    (17.5, 12.6),   # 4  2026-04-04  30.1
    (16.8, 12.2),   # 5  2026-04-05  29.0
    (16.6, 12.1),   # 6  2026-04-06  28.7
    (17.5, 12.7),   # 7  2026-04-07  30.2
    (17.1, 12.4),   # 8  2026-04-08  29.5
    (16.7, 12.1),   # 9  2026-04-09  28.8
    (17.4, 12.6),   # 10 2026-04-10  30.0
    (17.0, 12.3),   # 11 2026-04-11  29.3
    (16.6, 12.0),   # 12 2026-04-12  28.6
    (17.5, 12.6),   # 13 2026-04-13  30.1
    (16.9, 12.3),   # 14 2026-04-14  29.2
    (16.8, 12.1),   # 15 2026-04-15  28.9
    (17.2, 12.5),   # 16 2026-04-16  29.7
    (13.6, 9.9),    # 17 2026-04-17  23.5  ← Z-SCORE HIGH (Rule 1)
    (13.2, 9.6),    # 18 2026-04-18  22.8  ← Z-SCORE HIGH (Rule 1)
]

CHESA_RECORDS = [
    # Day  Date         Morning  Evening   Total
    (15.4, 11.1),   # 1  2026-04-01  26.5
    (16.1, 11.7),   # 2  2026-04-02  27.8
    (15.2, 11.0),   # 3  2026-04-03  26.2
    (16.3, 11.8),   # 4  2026-04-04  28.1
    (15.7, 11.3),   # 5  2026-04-05  27.0
    (15.5, 11.2),   # 6  2026-04-06  26.7
    (16.4, 11.8),   # 7  2026-04-07  28.2
    (16.0, 11.5),   # 8  2026-04-08  27.5
    (15.5, 11.3),   # 9  2026-04-09  26.8
    (16.2, 11.8),   # 10 2026-04-10  28.0
    (15.8, 11.5),   # 11 2026-04-11  27.3
    (15.4, 11.2),   # 12 2026-04-12  26.6
    (16.3, 11.8),   # 13 2026-04-13  28.1
    (15.8, 11.4),   # 14 2026-04-14  27.2
    (15.6, 11.3),   # 15 2026-04-15  26.9
    (16.1, 11.6),   # 16 2026-04-16  27.7
    ( 8.1,  5.9),   # 17 2026-04-17  14.0  ← ACUTE DROP HIGH (Rule 2)
    ( 7.8,  5.7),   # 18 2026-04-18  13.5  ← ACUTE DROP HIGH (Rule 2)
]

GIRLIE_RECORDS = [
    # Day  Date         Morning  Evening   Total
    (17.4, 12.6),   # 1  2026-04-01  30.0
    (17.1, 12.3),   # 2  2026-04-02  29.4
    (16.6, 12.0),   # 3  2026-04-03  28.6
    (16.3, 11.8),   # 4  2026-04-04  28.1
    (15.8, 11.5),   # 5  2026-04-05  27.3
    (15.5, 11.1),   # 6  2026-04-06  26.6
    (15.0, 10.9),   # 7  2026-04-07  25.9
    (14.5, 10.5),   # 8  2026-04-08  25.0
    (14.2, 10.3),   # 9  2026-04-09  24.5
    (13.8, 10.0),   # 10 2026-04-10  23.8
    (13.4,  9.7),   # 11 2026-04-11  23.1
    (13.0,  9.4),   # 12 2026-04-12  22.4
    (12.6,  9.1),   # 13 2026-04-13  21.7
    (12.2,  8.8),   # 14 2026-04-14  21.0  ← slope/R² threshold crossed
    (11.8,  8.5),   # 15 2026-04-15  20.3  ← TREND MEDIUM (Rule 3)
    (11.4,  8.2),   # 16 2026-04-16  19.6  ← TREND MEDIUM (Rule 3)
    (11.0,  7.9),   # 17 2026-04-17  18.9  ← TREND MEDIUM (Rule 3)
    (10.6,  7.6),   # 18 2026-04-18  18.2  ← TREND MEDIUM (Rule 3)
]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  DairyIQ — QA Data Seeder")
    print("  Target account:", QA_EMAIL)
    print("=" * 60)

    conn = get_conn()

    print("\n[1/5] Ensuring database tables exist …")
    ensure_tables(conn)

    print("\n[2/5] Resolving QA user account …")
    user_id = get_or_create_user(conn)

    print("\n[3/5] Registering cows …")
    tuya_id   = get_or_create_cow(conn, user_id, "Tuya",   "TU-354",
                                  "QA cow — Rule 1 Z-Score spike test")
    chesa_id  = get_or_create_cow(conn, user_id, "Chesa",  "CH-175",
                                  "QA cow — Rule 2 acute drop test")
    girlie_id = get_or_create_cow(conn, user_id, "Girlie", "GL-425",
                                  "QA cow — Rule 3 sustained trend test")

    print("\n[4/5] Loading milk production records …")
    print(f"  Tuya   (TU-354) — {len(TUYA_RECORDS)} days")
    insert_records(conn, user_id, tuya_id,   TUYA_RECORDS)

    print(f"  Chesa  (CH-175) — {len(CHESA_RECORDS)} days")
    insert_records(conn, user_id, chesa_id,  CHESA_RECORDS)

    print(f"  Girlie (GL-425) — {len(GIRLIE_RECORDS)} days")
    insert_records(conn, user_id, girlie_id, GIRLIE_RECORDS)

    conn.close()

    print("\n[5/5] Verification summary")
    print("  " + "-" * 68)
    print("  Cow          | Tag     | Expected anomaly (Days 17-18)")
    print("  " + "-" * 68)
    print("  Tuya         | TU-354  | Rule 1 HIGH   - Z-score > 3 SD drop")
    print("  Chesa        | CH-175  | Rule 2 HIGH   - yield < 75% rolling mean")
    print("  Girlie       | GL-425  | Rule 3 MEDIUM - sustained linear decline")
    print("  " + "-" * 68)
    print("\n  Login credentials for QA account:")
    print(f"    Email   : {QA_EMAIL}")
    print(f"    Password: {QA_PASSWORD}")
    print("\n  Seeding complete. [OK]")


if __name__ == "__main__":
    main()
