import os
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import connect_db, init_db, seed_demo_data

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, template_folder="templates")
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "change-this-before-production"),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",
)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Требуется авторизация"}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def ensure_database():
    init_db()
    if os.getenv("SEED_DEMO_DATA", "1") == "1":
        seed_demo_data()


@app.get("/login")
def login():
    if session.get("admin"):
        return redirect(url_for("index"))
    return render_template("login.html", error=None)


@app.post("/login")
def login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    expected_user = os.getenv("ADMIN_USERNAME", "admin")
    password_hash = os.getenv("ADMIN_PASSWORD_HASH")
    valid_password = (
        check_password_hash(password_hash, password)
        if password_hash
        else password == os.getenv("ADMIN_PASSWORD", "admin123")
    )
    if username == expected_user and valid_password:
        session.clear()
        session["admin"] = username
        return redirect(url_for("index"))
    return render_template("login.html", error="Неверный логин или пароль"), 401


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required
def index():
    return send_from_directory(BASE_DIR / "dist", "index.html")


@app.get("/tokens.css")
def public_tokens():
    return send_from_directory(BASE_DIR / "dist", "tokens.css")


@app.get("/assets/<path:filename>")
@login_required
def assets(filename):
    return send_from_directory(BASE_DIR / "dist", filename)


@app.get("/<path:filename>")
@login_required
def static_files(filename):
    if filename in {"tokens.css", "app.js"}:
        return send_from_directory(BASE_DIR / "dist", filename)
    return jsonify({"error": "Не найдено"}), 404


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


@app.get("/api/patients")
@login_required
def patients():
    query = request.args.get("q", "").strip()
    with connect_db() as db:
        if query:
            rows = db.execute(
                "SELECT id, full_name, phone, consent_whatsapp, created_at FROM patients "
                "WHERE full_name LIKE ? OR phone LIKE ? ORDER BY full_name",
                (f"%{query}%", f"%{query}%"),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id, full_name, phone, consent_whatsapp, created_at FROM patients ORDER BY full_name"
            ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.post("/api/patients")
@login_required
def create_patient():
    data = request.get_json(silent=True) or {}
    name = str(data.get("full_name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    if len(name) < 2 or len(phone) < 7:
        return jsonify({"error": "Укажите имя и корректный телефон"}), 400
    try:
        with connect_db() as db:
            cursor = db.execute(
                "INSERT INTO patients(full_name, phone, consent_whatsapp) VALUES (?, ?, ?)",
                (name, phone, int(bool(data.get("consent_whatsapp")))),
            )
            db.commit()
            patient_id = cursor.lastrowid
    except Exception as exc:
        if "UNIQUE" in str(exc):
            return jsonify({"error": "Пациент с таким телефоном уже существует"}), 409
        raise
    return jsonify({"id": patient_id, "full_name": name, "phone": phone}), 201


@app.get("/api/appointments")
@login_required
def appointments():
    date = request.args.get("date")
    sql = (
        "SELECT a.id, a.patient_id, p.full_name AS patient_name, p.phone, a.procedure_name, "
        "a.doctor_name, a.starts_at, a.status, a.created_at FROM appointments a "
        "JOIN patients p ON p.id = a.patient_id"
    )
    params = ()
    if date:
        sql += " WHERE substr(a.starts_at, 1, 10) = ?"
        params = (date,)
    sql += " ORDER BY a.starts_at"
    with connect_db() as db:
        rows = db.execute(sql, params).fetchall()
    return jsonify([dict(row) for row in rows])


@app.post("/api/appointments")
@login_required
def create_appointment():
    data = request.get_json(silent=True) or {}
    required = ("patient_id", "procedure_name", "doctor_name", "starts_at")
    if any(not data.get(field) for field in required):
        return jsonify({"error": "Заполните пациента, процедуру, врача, дату и время"}), 400
    try:
        starts_at = datetime.fromisoformat(str(data["starts_at"]))
    except ValueError:
        return jsonify({"error": "Неверный формат даты"}), 400

    with connect_db() as db:
        patient = db.execute(
            "SELECT id, full_name, phone, consent_whatsapp FROM patients WHERE id = ?",
            (int(data["patient_id"]),),
        ).fetchone()
        if not patient:
            return jsonify({"error": "Пациент не найден"}), 404
        cursor = db.execute(
            "INSERT INTO appointments(patient_id, procedure_name, doctor_name, starts_at, status) "
            "VALUES (?, ?, ?, ?, 'scheduled')",
            (patient["id"], str(data["procedure_name"]).strip(), str(data["doctor_name"]).strip(), starts_at.isoformat(timespec="minutes")),
        )
        appointment_id = cursor.lastrowid
        queued = False
        if bool(data.get("send_whatsapp", True)) and patient["consent_whatsapp"]:
            db.execute(
                "INSERT INTO message_queue(appointment_id, patient_id, phone, template_name, scheduled_for, status) "
                "VALUES (?, ?, ?, ?, ?, 'queued')",
                (appointment_id, patient["id"], patient["phone"], os.getenv("WHATSAPP_TEMPLATE", "appointment_reminder"), datetime.now(timezone.utc).isoformat()),
            )
            queued = True
        db.commit()
    return jsonify({"id": appointment_id, "status": "scheduled", "whatsapp_queued": queued}), 201


@app.patch("/api/appointments/<int:appointment_id>/status")
@login_required
def update_appointment_status(appointment_id):
    status = (request.get_json(silent=True) or {}).get("status")
    allowed = {"scheduled", "confirmed", "completed", "cancelled", "reschedule_requested", "no_show"}
    if status not in allowed:
        return jsonify({"error": "Недопустимый статус"}), 400
    with connect_db() as db:
        cursor = db.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, appointment_id))
        db.commit()
    if cursor.rowcount == 0:
        return jsonify({"error": "Запись не найдена"}), 404
    return jsonify({"id": appointment_id, "status": status})


@app.get("/api/messages")
@login_required
def messages():
    with connect_db() as db:
        rows = db.execute(
            "SELECT q.id, p.full_name AS patient_name, q.phone, q.template_name, q.status, "
            "q.scheduled_for, q.sent_at, q.provider_message_id, q.error_text "
            "FROM message_queue q JOIN patients p ON p.id = q.patient_id ORDER BY q.id DESC LIMIT 100"
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.post("/webhooks/whatsapp")
def whatsapp_webhook():
    """Minimal webhook receiver. Add signature verification before production use."""
    payload = request.get_json(silent=True) or {}
    return jsonify({"received": True, "events": len(payload.get("entry", []))})


if __name__ == "__main__":
    init_db()
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG", "0") == "1")

