"""
auth.py — Authentication module for DairyMind
Handles user registration, login, email verification, and session management.
"""

import os
import sqlite3
import bcrypt
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env (silently skipped if file absent)
load_dotenv()

def email_is_valid(email):
    """Format + DNS MX record check"""
    import re
    import socket
    
    # Format check
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "invalid_format"
    
    # MX record check — checks if domain can receive emails
    domain = email.split('@')[1]
    try:
        import dns.resolver
        records = dns.resolver.resolve(domain, 'MX')
        if records:
            return True, "ok"
        return False, "domain_not_found"
    except Exception:
        return False, "domain_not_found"

# ── Email config (loaded from .env) ──────────────────────────────────────────
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_EMAIL    = os.getenv("EMAIL_ADDRESS", "")
SMTP_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
DB_PATH = "dairy_farm.db"


# ── Database setup ────────────────────────────────────────────────────────────
def init_auth_tables():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            date_of_birth TEXT,
            farm_name TEXT,
            is_verified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS password_reset_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()


# ── Helpers ───────────────────────────────────────────────────────────────────
def generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))


def send_email(to_email, subject, body):
    """Send an HTML email via Gmail SMTP (port 587, STARTTLS)."""
    # ── Debug: confirm recipient before sending ────────────────────────────
    print(f"[DairyIQ] Sending email to: {to_email}")
    print(f"[DairyIQ] Subject       : {subject}")
    print(f"[DairyIQ] From          : {SMTP_EMAIL}")

    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("[DairyIQ] ERROR: EMAIL_ADDRESS or EMAIL_PASSWORD not set in .env")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"]    = SMTP_EMAIL
        msg["To"]      = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()                        # upgrade to TLS
            server.ehlo()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())

        print(f"[DairyIQ] Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"[DairyIQ] Email error: {e}")
        return False


# ── Registration ──────────────────────────────────────────────────────────────
def email_exists(email):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email.lower(),)).fetchone()
    conn.close()
    return row is not None


def register_user(email, password, full_name, date_of_birth, farm_name):
    # Validate email
    valid, reason = email_is_valid(email)
    if not valid:
        return False, reason
    email = email.lower().strip()

    if email_exists(email):
        return False, "already_exists"

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    code = generate_code()
    expires_at = (datetime.now() + timedelta(minutes=15)).isoformat()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, date_of_birth, farm_name) VALUES (?, ?, ?, ?, ?)",
            (email, password_hash, full_name, date_of_birth, farm_name)
        )
        conn.execute(
            "INSERT INTO verification_codes (email, code, expires_at) VALUES (?, ?, ?)",
            (email, code, expires_at)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return False, str(e)
    conn.close()

    body = f"""
    <html><body>
    <h2>🐄 Welcome to DairyMind!</h2>
    <p>Your verification code is:</p>
    <h1 style="color:#1a5276; letter-spacing:8px;">{code}</h1>
    <p>This code expires in <b>15 minutes</b>.</p>
    <p>If you did not create this account, ignore this email.</p>
    </body></html>
    """
    sent = send_email(email, "DairyMind — Verify Your Email", body)
    if not sent:
        return False, "email_failed"

    return True, "ok"


def verify_email_code(email, code):
    email = email.lower().strip()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        """SELECT id, expires_at FROM verification_codes
           WHERE email=? AND code=? AND used=0
           ORDER BY id DESC LIMIT 1""",
        (email, code)
    ).fetchone()

    if not row:
        conn.close()
        return False, "invalid_code"

    if datetime.now() > datetime.fromisoformat(row[1]):
        conn.close()
        return False, "expired"

    conn.execute("UPDATE verification_codes SET used=1 WHERE id=?", (row[0],))
    conn.execute("UPDATE users SET is_verified=1 WHERE email=?", (email,))
    conn.commit()
    conn.close()
    return True, "ok"


# ── Login ─────────────────────────────────────────────────────────────────────
def login_user(email, password):
    email = email.lower().strip()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE email=?",
        (email,)
    ).fetchone()
    conn.close()

    if not row:
        return False, "not_found", None

    user_id, password_hash = row

    if not bcrypt.checkpw(password.encode(), password_hash.encode()):
        return False, "wrong_password", None

    return True, "ok", user_id


# ── Forgot password ───────────────────────────────────────────────────────────
def send_reset_code(email):
    email = email.lower().strip()
    if not email_exists(email):
        return False, "not_found"

    code = generate_code()
    expires_at = (datetime.now() + timedelta(minutes=15)).isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO password_reset_codes (email, code, expires_at) VALUES (?, ?, ?)",
        (email, code, expires_at)
    )
    conn.commit()
    conn.close()

    body = f"""
    <html><body>
    <h2>🐄 DairyMind Password Reset</h2>
    <p>Your password reset code is:</p>
    <h1 style="color:#e74c3c; letter-spacing:8px;">{code}</h1>
    <p>This code expires in <b>15 minutes</b>.</p>
    <p>If you did not request this, ignore this email.</p>
    </body></html>
    """
    sent = send_email(email, "DairyMind — Password Reset Code", body)
    return (True, "ok") if sent else (False, "email_failed")


def reset_password(email, code, new_password):
    email = email.lower().strip()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        """SELECT id, expires_at FROM password_reset_codes
           WHERE email=? AND code=? AND used=0
           ORDER BY id DESC LIMIT 1""",
        (email, code)
    ).fetchone()

    if not row:
        conn.close()
        return False, "invalid_code"

    if datetime.now() > datetime.fromisoformat(row[1]):
        conn.close()
        return False, "expired"

    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn.execute("UPDATE password_reset_codes SET used=1 WHERE id=?", (row[0],))
    conn.execute("UPDATE users SET password_hash=? WHERE email=?", (new_hash, email))
    conn.commit()
    conn.close()
    return True, "ok"


def get_user_id(email):
    email = email.lower().strip()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    return row[0] if row else None
