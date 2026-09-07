import os
import smtplib
from datetime import datetime
from email.message import EmailMessage


def _mail_settings() -> dict[str, str | int | bool | None]:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM_EMAIL") or username
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}
    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "sender": sender,
        "use_tls": use_tls,
    }


def _send_email(*, recipient: str | None, subject: str, body: str, missing_recipient_message: str) -> dict[str, str | datetime | None]:
    """Shared SMTP send used by every outbound notification in this module.

    Every caller (booking, invoice, statement, compliance digest) needs the
    same three checks -- no recipient, no SMTP configured, and the send
    itself failing -- so this is the one place that logic lives.
    """
    if not recipient:
        return {"status": "missing_recipient", "error": missing_recipient_message, "sent_at": None}

    settings = _mail_settings()
    if not settings["host"] or not settings["sender"]:
        return {"status": "not_configured", "error": "SMTP settings are not configured.", "sent_at": None}

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = str(settings["sender"])
    message["To"] = recipient
    message.set_content(body)

    try:
        with smtplib.SMTP(str(settings["host"]), int(settings["port"]), timeout=20) as smtp:
            if settings["use_tls"]:
                smtp.starttls()
            if settings["username"] and settings["password"]:
                smtp.login(str(settings["username"]), str(settings["password"]))
            smtp.send_message(message)
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "sent_at": None}

    return {"status": "sent", "error": None, "sent_at": datetime.utcnow()}


def send_booking_email(*, recipient: str | None, booking_number: str, client_name: str, route_name: str, vehicle_registration: str, cargo_type: str, rate: float, currency: str, notes: str | None) -> dict[str, str | datetime | None]:
    body = "\n".join(
        [
            f"Dear {client_name},",
            "",
            "A truck booking has been created with the following details:",
            f"Booking Number: {booking_number}",
            f"Route: {route_name}",
            f"Vehicle: {vehicle_registration}",
            f"Cargo Type: {cargo_type}",
            f"Rate: {currency} {rate:,.2f}",
            f"Notes: {notes or '-'}",
            "",
            "Please confirm acceptance with the transport team.",
        ]
    )
    return _send_email(
        recipient=recipient,
        subject=f"Truck Booking {booking_number}",
        body=body,
        missing_recipient_message="Client booking email is not set.",
    )


def send_invoice_email(*, recipient: str | None, invoice_number: str, client_name: str, trip_number: str, amount: float, currency: str, stage: str, due_date: str | None) -> dict[str, str | datetime | None]:
    stage_label = "" if stage == "full" else f" ({stage} invoice)"
    body = "\n".join(
        [
            f"Dear {client_name},",
            "",
            f"Please find invoice {invoice_number}{stage_label} for trip {trip_number}.",
            f"Amount Due: {currency} {amount:,.2f}",
            f"Due Date: {due_date or '-'}",
            "",
            "Kindly arrange payment by the due date. Contact the accounts team with any queries.",
        ]
    )
    return _send_email(
        recipient=recipient,
        subject=f"Invoice {invoice_number}",
        body=body,
        missing_recipient_message="Client invoice email is not set.",
    )


def send_statement_email(*, recipient: str | None, client_name: str, statement_text: str) -> dict[str, str | datetime | None]:
    body = "\n".join([f"Dear {client_name},", "", "Please find your statement of accounts below.", "", statement_text])
    return _send_email(
        recipient=recipient,
        subject=f"Statement of Accounts - {client_name}",
        body=body,
        missing_recipient_message="Client statement email is not set.",
    )


def send_compliance_digest_email(*, recipient: str | None, digest_text: str) -> dict[str, str | datetime | None]:
    return _send_email(
        recipient=recipient,
        subject="Fleet Compliance Alerts",
        body=digest_text,
        missing_recipient_message="No admin recipient email is configured.",
    )
