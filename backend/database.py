"""SQLite helpers. Each uploaded file is a "patient" row in one table."""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "dataset_doctor.db"
JSON_FIELDS = ("diagnosis", "applied", "after", "applied_fix_ids", "applied_fixes")
ALLOWED = JSON_FIELDS + ("cleaned_path", "code")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_path TEXT NOT NULL,
                cleaned_path TEXT,
                diagnosis TEXT,
                applied TEXT,
                after TEXT,
                code TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(patients)")}
        if "applied_fix_ids" not in columns:
            conn.execute("ALTER TABLE patients ADD COLUMN applied_fix_ids TEXT")
        if "applied_fixes" not in columns:
            conn.execute("ALTER TABLE patients ADD COLUMN applied_fixes TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patient_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            )""")


def create_patient(filename, original_path):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO patients (filename, original_path) VALUES (?, ?)",
            (filename, original_path))
        return cur.lastrowid


def get_patient(patient_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    if row is None:
        return None
    patient = dict(row)
    for field in JSON_FIELDS:
        if patient[field]:
            patient[field] = json.loads(patient[field])
    return patient


def update_patient(patient_id, **fields):
    for name, value in fields.items():
        if name not in ALLOWED:
            raise ValueError(f"Unknown field: {name}")
        if name in JSON_FIELDS:
            fields[name] = json.dumps(value)
    sets = ", ".join(f"{name} = ?" for name in fields)
    with connect() as conn:
        conn.execute(f"UPDATE patients SET {sets} WHERE id = ?", (*fields.values(), patient_id))


def add_history(patient_id, event_type, details):
    with connect() as conn:
        conn.execute(
            "INSERT INTO patient_history (patient_id, event_type, details) VALUES (?, ?, ?)",
            (patient_id, event_type, json.dumps(details)))


def get_history(limit=50):
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, filename, created_at, diagnosis, applied, after "
            "FROM patients ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,)).fetchall()
        if not rows:
            return []
        patient_ids = [row["id"] for row in rows]
        placeholders = ",".join("?" for _ in patient_ids)
        events = conn.execute(
            f"SELECT id, patient_id, event_type, details, created_at FROM patient_history "
            f"WHERE patient_id IN ({placeholders}) ORDER BY created_at, id",
            patient_ids).fetchall()

    events_by_patient = {patient_id: [] for patient_id in patient_ids}
    for event in events:
        item = dict(event)
        item["details"] = json.loads(item["details"])
        events_by_patient[item["patient_id"]].append(item)

    history = []
    for row in rows:
        item = dict(row)
        for field in ("diagnosis", "applied", "after"):
            if item[field]:
                item[field] = json.loads(item[field])
        item["events"] = events_by_patient[item["id"]]
        history.append(item)
    return history
