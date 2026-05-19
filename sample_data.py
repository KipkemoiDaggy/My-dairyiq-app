"""
Sample Data Generator
======================
Generates 6 months of realistic dairy farm data using Wood's lactation model
for 10 cows (common Kenyan breeds). Three cows have injected illness episodes
to demonstrate the anomaly detection system.

All sample data is saved with user_id = 0 (guest mode).
"""

import numpy as np
import sqlite3
import random
from datetime import date, timedelta
import database as db

random.seed(42)
np.random.seed(42)

# ── Cow profiles ─────────────────────────────────────────────────────────────
COW_PROFILES = [
    {"name": "Bessie",  "tag": "KE-001", "breed": "Friesian",  "peak": 28, "b": 0.150, "c": 0.0030},
    {"name": "Daisy",   "tag": "KE-002", "breed": "Holstein",  "peak": 33, "b": 0.180, "c": 0.0035},
    {"name": "Rosie",   "tag": "KE-003", "breed": "Jersey",    "peak": 22, "b": 0.120, "c": 0.0025},
    {"name": "Flora",   "tag": "KE-004", "breed": "Ayrshire",  "peak": 26, "b": 0.140, "c": 0.0028},
    {"name": "Lily",    "tag": "KE-005", "breed": "Friesian",  "peak": 30, "b": 0.160, "c": 0.0032},
    {"name": "Mara",    "tag": "KE-006", "breed": "Holstein",  "peak": 35, "b": 0.200, "c": 0.0040},
    {"name": "Nala",    "tag": "KE-007", "breed": "Jersey",    "peak": 20, "b": 0.110, "c": 0.0022},
    {"name": "Pearl",   "tag": "KE-008", "breed": "Guernsey",  "peak": 24, "b": 0.130, "c": 0.0026},
    {"name": "Queen",   "tag": "KE-009", "breed": "Friesian",  "peak": 29, "b": 0.170, "c": 0.0033},
    {"name": "Ruby",    "tag": "KE-010", "breed": "Ayrshire",  "peak": 27, "b": 0.155, "c": 0.0031},
]

# Cows with injected illness episodes: {tag: (start_day, end_day, disease)}
ILLNESS_EVENTS = {
    "KE-003": (115, 132, "Mastitis", "Antibiotic course - Penicillin 3 days. Left front quarter affected. Milk slightly discoloured. Isolate for 3 days."),
    "KE-007": (88,  98,  "Bloat",    "Trocarization performed. Antacid administered. Likely caused by lush pasture after rain. Monitor feed transition."),
    "KE-001": (158, 175, "Lameness", "Hoof trimming performed. Anti-inflammatory prescribed. Check bedding and flooring surface."),
}

GUEST_USER_ID = 0  # Reserved user_id for guest/sample data


def wood(t, a, b, c):
    t = max(float(t), 0.5)
    return a * (t ** b) * np.exp(-c * t)


def compute_a(peak_yield, b, c):
    """Back-calculate 'a' so that wood(t_peak) == peak_yield."""
    t_peak = b / c
    y_at_1 = wood(t_peak, 1.0, b, c)
    return peak_yield / y_at_1


def generate_all():
    today = date.today()
    start_date = today - timedelta(days=180)

    conn = sqlite3.connect(db.DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

    for profile in COW_PROFILES:
        dim_offset = random.randint(15, 70)
        lactation_start = start_date - timedelta(days=dim_offset)
        dob = lactation_start - timedelta(days=random.randint(365 * 3, 365 * 7))

        try:
            cursor.execute(
                "INSERT INTO cows (user_id, name, tag_number, breed, date_of_birth, lactation_start_date) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (GUEST_USER_ID, profile["name"], profile["tag"], profile["breed"],
                 dob.isoformat(), lactation_start.isoformat()),
            )
        except sqlite3.IntegrityError:
            continue  # already exists

        cow_id = cursor.lastrowid
        a = compute_a(profile["peak"], profile["b"], profile["c"])
        tag = profile["tag"]
        illness = ILLNESS_EVENTS.get(tag)

        for day_offset in range(181):
            record_date = start_date + timedelta(days=day_offset)
            if record_date > today:
                break

            dim = dim_offset + day_offset
            base = wood(dim, a, profile["b"], profile["c"])
            noise = np.random.normal(0, base * 0.07)
            total = max(0.0, base + noise)

            if illness:
                s, e = illness[0], illness[1]
                if s <= day_offset <= e:
                    prog = day_offset - s
                    duration = e - s
                    half = max(duration // 2, 1)
                    if prog <= half:
                        factor = 1 - (prog / half) * 0.50
                    else:
                        factor = 0.50 + ((prog - half) / half) * 0.50
                    total = max(0.0, total * factor)

            morning = round(total * random.uniform(0.56, 0.64), 2)
            evening = round(max(0.0, total - morning), 2)
            total_r = round(morning + evening, 2)

            cursor.execute(
                "INSERT OR IGNORE INTO milk_records "
                "(user_id, cow_id, record_date, morning_yield, evening_yield, total_yield) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (GUEST_USER_ID, cow_id, record_date.isoformat(), morning, evening, total_r),
            )

        if illness:
            s_day = illness[0]
            disease_date = (start_date + timedelta(days=s_day + 2)).isoformat()
            followup = (start_date + timedelta(days=s_day + 14)).isoformat()
            cursor.execute(
                "INSERT OR IGNORE INTO health_records "
                "(user_id, cow_id, record_date, condition, treatment, vet_notes, follow_up_date, resolved) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (GUEST_USER_ID, cow_id, disease_date, illness[2], "See vet notes",
                 illness[3], followup, 1),
            )

    conn.commit()
    conn.close()
    print("Sample data generated successfully.")


if __name__ == "__main__":
    db.initialize_db()
    generate_all()
