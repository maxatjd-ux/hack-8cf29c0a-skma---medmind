import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", BASE_DIR / "instance" / "medflow.sqlite3"))


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with connect_db() as db:
        db.executescript((BASE_DIR / "schema.sql").read_text(encoding="utf-8"))


def seed_demo_data():
    demo = [
        ("Амина Садуакасова", "+77012451809", 1),
        ("Марат Тлеубаев", "+77773314220", 1),
        ("Елена Новикова", "+77058801243", 1),
        ("Данияр Касымов", "+77026043311", 1),
        ("Ольга Белова", "+77472107655", 0),
    ]
    with connect_db() as db:
        count = db.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        if count == 0:
            db.executemany(
                "INSERT INTO patients(full_name, phone, consent_whatsapp) VALUES (?, ?, ?)", demo
            )
            db.commit()

