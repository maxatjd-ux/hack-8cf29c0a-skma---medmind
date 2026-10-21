import os
from datetime import datetime, timezone

import requests

from db import connect_db


def send_template(phone, appointment_time, patient_name):
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    template = os.getenv("WHATSAPP_TEMPLATE", "appointment_reminder")
    language = os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "ru")
    if not token or not phone_number_id:
        raise RuntimeError("Не заданы WHATSAPP_ACCESS_TOKEN и WHATSAPP_PHONE_NUMBER_ID")

    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone.replace("+", ""),
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": language},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": patient_name},
                    {"type": "text", "text": appointment_time},
                ],
            }],
        },
    }
    response = requests.post(url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    response.raise_for_status()
    return response.json()["messages"][0]["id"]


def process_queue(limit=20):
    now = datetime.now(timezone.utc).isoformat()
    with connect_db() as db:
        messages = db.execute(
            "SELECT q.id, q.phone, p.full_name, a.starts_at FROM message_queue q "
            "JOIN patients p ON p.id = q.patient_id JOIN appointments a ON a.id = q.appointment_id "
            "WHERE q.status = 'queued' AND q.scheduled_for <= ? ORDER BY q.id LIMIT ?",
            (now, limit),
        ).fetchall()

    for message in messages:
        try:
            provider_id = send_template(message["phone"], message["starts_at"], message["full_name"])
            with connect_db() as db:
                db.execute(
                    "UPDATE message_queue SET status='sent', sent_at=?, provider_message_id=? WHERE id=?",
                    (datetime.now(timezone.utc).isoformat(), provider_id, message["id"]),
                )
                db.commit()
        except Exception as exc:
            with connect_db() as db:
                db.execute(
                    "UPDATE message_queue SET status='failed', error_text=? WHERE id=?",
                    (str(exc)[:500], message["id"]),
                )
                db.commit()

    return len(messages)

