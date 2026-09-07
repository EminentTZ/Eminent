from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Trip, Route, Invoice, Payment, Client

VALID_INVOICE_STAGES = {"full", "advance", "balance", "final"}


def calculate_trip_delay_and_demurrage(trip: Trip, route: Route) -> tuple[float, float]:
    if not trip.actual_departure or not trip.actual_arrival or not route.expected_days:
        return trip.delay_charge or 0.0, trip.demurrage_cost or 0.0

    actual_days = (trip.actual_arrival - trip.actual_departure).total_seconds() / 86400
    extra_days = max(actual_days - (route.expected_days or 0.0), 0.0)
    delay_charge = 0.0
    demurrage_cost = 0.0

    if route.delay_threshold_days and extra_days > route.delay_threshold_days:
        delay_days = extra_days - route.delay_threshold_days
        delay_charge = round(delay_days * route.demurrage_rate_per_day, 2)

    if extra_days > 0:
        demurrage_cost = round(extra_days * route.demurrage_rate_per_day, 2)

    return delay_charge, demurrage_cost


def _next_invoice_number(db: Session, client: Client, trip: Trip, stage: str) -> str:
    """Format an invoice number the way this client's own AP team expects it.

    Cross-border broker customers each run their own numbering convention
    (e.g. Polytra: ``POL/TRANS/26/05/0002``, Poseidon: ``E2L/25/04/0011``).
    A client with ``invoice_number_format`` set gets its own sequence; every
    other client falls back to the house default, which stays stable and
    predictable (one invoice per stage per trip).
    """
    if not client.invoice_number_format:
        suffix = "" if stage == "full" else f"-{stage.upper()}"
        return f"INV-{trip.trip_number}{suffix}"

    client.invoice_sequence = (client.invoice_sequence or 0) + 1
    today = date.today()
    try:
        return client.invoice_number_format.format(
            seq=client.invoice_sequence,
            yy=today.strftime("%y"),
            yyyy=today.year,
            mm=today.strftime("%m"),
            stage=stage.upper(),
            trip=trip.trip_number,
            client=client.name,
        )
    except (KeyError, IndexError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Client '{client.name}' has an invalid invoice_number_format ({exc}). "
                   f"Supported placeholders: {{seq}}, {{yy}}, {{yyyy}}, {{mm}}, {{stage}}, {{trip}}, {{client}}.",
        )


def generate_invoice_for_trip(
    db: Session,
    trip: Trip,
    due_date=None,
    notes=None,
    stage: str = "full",
    stage_percentage: float = 100.0,
) -> Invoice:
    if trip.status not in {"completed", "closed"}:
        raise HTTPException(status_code=400, detail="Trip must be completed before invoice generation")
    if stage not in VALID_INVOICE_STAGES:
        raise HTTPException(status_code=400, detail=f"stage must be one of {sorted(VALID_INVOICE_STAGES)}")
    if not (0 < stage_percentage <= 100):
        raise HTTPException(status_code=400, detail="stage_percentage must be between 0 and 100")

    existing = db.query(Invoice).filter(Invoice.trip_id == trip.id, Invoice.stage == stage, Invoice.status != "rejected").first()
    if existing:
        raise HTTPException(status_code=400, detail=f"A '{stage}' invoice already exists for this trip ({existing.invoice_number})")

    already_billed_pct = sum(
        inv.stage_percentage for inv in trip.invoices if inv.status != "rejected"
    )
    if already_billed_pct + stage_percentage > 100.01:
        raise HTTPException(
            status_code=400,
            detail=f"This trip is already {already_billed_pct:.0f}% invoiced; a further {stage_percentage:.0f}% would exceed 100%.",
        )

    client = db.get(Client, trip.client_id)
    if not client:
        raise HTTPException(status_code=400, detail="Trip's client no longer exists")

    recoverable_expenses = sum(exp.amount for exp in trip.expenses if exp.is_recoverable)
    base_total = round(trip.agreed_revenue + (trip.delay_charge or 0.0) + recoverable_expenses, 2)
    amount = round(base_total * stage_percentage / 100, 2)

    # credit_days is captured on every client at onboarding but previously had
    # no effect anywhere -- default the due date to the client's own payment
    # terms when the caller doesn't explicitly override it.
    if due_date is None:
        due_date = date.today() + timedelta(days=client.credit_days or 0)

    invoice = Invoice(
        invoice_number=_next_invoice_number(db, client, trip, stage),
        trip_id=trip.id,
        client_id=trip.client_id,
        amount=amount,
        currency=trip.currency,
        status="issued",
        due_date=due_date,
        notes=notes,
        stage=stage,
        stage_percentage=stage_percentage,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def update_invoice_payment_status(invoice: Invoice) -> None:
    total_paid = sum(p.amount for p in invoice.payments)
    if total_paid <= 0:
        invoice.status = "issued"
    elif total_paid < invoice.amount:
        invoice.status = "partial"
    else:
        invoice.status = "paid"
