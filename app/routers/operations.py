from pathlib import Path
from uuid import uuid4

from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user
from app.models import User, Trip, TripMilestone, Client, Route, Vehicle, Driver, TripEvent, Expense, Invoice, Payment, MaintenanceRecord, EquipmentAssignment, Booking, Vendor
from app.permissions import require_roles, FINANCE, OPS, OPS_FINANCE
from app.schemas.trips import (
    BookingCreate, BookingOut, BookingStatusUpdate,
    TripCreate, TripOut, TripDetail, TripStatusUpdate, TripFuelMileageUpdate,
    TripEventCreate, TripEventOut, ExpenseCreate, ExpenseOut,
    TripMilestoneCreate, TripMilestoneOut, TripMilestoneRecordActual,
    InvoiceCreateFromTrip, InvoiceOut, InvoiceRejection, PaymentCreate, PaymentOut,
    BatchPaymentCreate, MaintenanceCreate, MaintenanceOut, PayableSettle,
)
from app.services.business import calculate_trip_delay_and_demurrage, generate_invoice_for_trip, update_invoice_payment_status
from app.services.notifications import send_booking_email, send_invoice_email
from app.services import accounting as accounting_service

router = APIRouter(prefix="/operations", tags=["Operations"])
POD_UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads" / "pod"


def _generate_trip_milestones(db: Session, trip: Trip, route: Route) -> None:
    """Snapshot the route's milestone template onto a newly-created trip.

    Copying rather than referencing the template means editing a route's
    milestones later never rewrites a checkpoint list a trip already has --
    the trip keeps exactly the plan it was dispatched with.
    """
    for route_milestone in sorted(route.milestones, key=lambda m: m.sequence):
        db.add(TripMilestone(
            trip_id=trip.id,
            route_milestone_id=route_milestone.id,
            sequence=route_milestone.sequence,
            name=route_milestone.name,
            milestone_type=route_milestone.milestone_type,
            target_hours_from_start=route_milestone.target_hours_from_start,
        ))


def _recompute_milestone_targets(trip: Trip) -> None:
    """Fill in each milestone's absolute target_at once actual_departure is
    known -- target_hours_from_start only means something relative to when
    the trip actually left, not when it was planned to."""
    if not trip.actual_departure:
        return
    for milestone in trip.milestones:
        if milestone.target_hours_from_start is not None:
            milestone.target_at = trip.actual_departure + timedelta(hours=milestone.target_hours_from_start)


def _apply_milestone_actual(milestone: TripMilestone, actual_at: datetime) -> None:
    milestone.actual_at = actual_at
    if milestone.target_at is None:
        milestone.status = "reached"
    else:
        milestone.status = "reached" if actual_at <= milestone.target_at else "late"


@router.get("/bookings", response_model=list[BookingOut])
def list_bookings(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Booking).order_by(Booking.created_at.desc()).all()


@router.post("/bookings", response_model=BookingOut)
def create_booking(payload: BookingCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    client = db.get(Client, payload.client_id)
    route = db.get(Route, payload.route_id)
    tractor = db.get(Vehicle, payload.tractor_id)
    if not client or not route or not tractor or tractor.vehicle_type != "tractor":
        raise HTTPException(status_code=400, detail="Invalid client, route, or tractor")
    if not client.is_active:
        raise HTTPException(status_code=400, detail="Selected client is deactivated and cannot be booked")
    if tractor.status in {"maintenance", "grounded"}:
        raise HTTPException(status_code=400, detail="Selected tractor is not available for booking")

    booking = Booking(
        booking_number=f"BK-{datetime.utcnow():%Y%m%d%H%M%S%f}",
        booking_email_to=client.booking_email or client.loading_order_email,
        booking_email_status="pending",
        **payload.model_dump(),
    )
    db.add(booking)
    db.flush()

    delivery = send_booking_email(
        recipient=booking.booking_email_to,
        booking_number=booking.booking_number,
        client_name=client.name,
        route_name=route.route_name,
        vehicle_registration=tractor.registration_no,
        cargo_type=booking.cargo_type,
        rate=booking.rate,
        currency=booking.currency,
        notes=booking.notes,
    )
    booking.booking_email_status = str(delivery["status"])
    booking.booking_email_error = delivery["error"] if isinstance(delivery["error"], str) or delivery["error"] is None else str(delivery["error"])
    booking.booking_email_sent_at = delivery["sent_at"] if isinstance(delivery["sent_at"], datetime) or delivery["sent_at"] is None else None

    db.commit()
    db.refresh(booking)
    return booking


@router.patch("/bookings/{booking_id}/status", response_model=BookingOut)
def update_booking_status(booking_id: int, payload: BookingStatusUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if payload.status not in {"pending", "accepted", "rejected", "converted"}:
        raise HTTPException(status_code=400, detail="Invalid booking status")
    if booking.status == "converted":
        raise HTTPException(status_code=400, detail="Converted bookings cannot be changed")
    booking.status = payload.status
    if payload.status == "accepted":
        booking.accepted_at = datetime.utcnow()
    elif payload.status == "rejected":
        booking.accepted_at = None
    db.commit()
    db.refresh(booking)
    return booking


@router.get("/trips", response_model=list[TripOut])
def list_trips(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Trip).order_by(Trip.created_at.desc()).all()


@router.post("/trips", response_model=TripOut)
def create_trip(payload: TripCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    if db.query(Trip).filter(Trip.trip_number == payload.trip_number).first():
        raise HTTPException(status_code=400, detail="Trip number already exists")

    booking = db.get(Booking, payload.booking_id) if payload.booking_id else None
    if payload.booking_id and not booking:
        raise HTTPException(status_code=400, detail="Selected booking was not found")
    if booking and booking.status != "accepted":
        raise HTTPException(status_code=400, detail="Only accepted bookings can be dispatched to trips")

    payload_data = payload.model_dump()
    if booking:
        payload_data["client_id"] = booking.client_id
        payload_data["route_id"] = booking.route_id
        payload_data["tractor_id"] = booking.tractor_id
        payload_data["cargo_type"] = booking.cargo_type
        payload_data["agreed_revenue"] = booking.rate
        payload_data["currency"] = booking.currency
        payload_data["container_size"] = None

    assignment = db.query(EquipmentAssignment).filter(
        EquipmentAssignment.tractor_id == payload_data["tractor_id"],
        EquipmentAssignment.status == "active",
    ).first()
    if assignment:
        payload_data["trailer_id"] = payload_data.get("trailer_id") or assignment.trailer_id
        payload_data["dangler_id"] = payload_data.get("dangler_id") or assignment.dangler_id
        payload_data["driver_id"] = payload_data.get("driver_id") or assignment.driver_id

    client = db.get(Client, payload.client_id)
    route = db.get(Route, payload.route_id)
    tractor = db.get(Vehicle, payload.tractor_id)
    driver = db.get(Driver, payload_data["driver_id"]) if payload_data.get("driver_id") else None

    if not client or not route or not tractor or not driver:
        raise HTTPException(status_code=400, detail="Invalid client, route, vehicle, or driver")
    if not client.is_active:
        raise HTTPException(status_code=400, detail="Selected client is deactivated and cannot be booked")
    if tractor.status in {"maintenance", "grounded", "assigned"}:
        raise HTTPException(status_code=400, detail="Selected vehicle is not available")
    # A tractor's status is normally kept in sync with its trips, but check the
    # trip table directly too -- this is the same guard already used for
    # equipment (re)assignment, and closes the gap where two trips could
    # otherwise be dispatched on the same tractor at once.
    active_trip_on_tractor = db.query(Trip).filter(
        Trip.tractor_id == tractor.id, Trip.status.in_({"planned", "approved", "in_transit"})
    ).first()
    if active_trip_on_tractor:
        raise HTTPException(
            status_code=400,
            detail=f"Selected vehicle is already on trip {active_trip_on_tractor.trip_number}",
        )
    if driver.status != "available":
        raise HTTPException(status_code=400, detail="Selected driver is not available")

    # Predetermined trip-planning figures come from the route by default --
    # a dispatcher can still override either one on the trip form itself.
    if payload_data.get("planned_fuel_liters") is None:
        payload_data["planned_fuel_liters"] = route.standard_fuel_liters
    if payload_data.get("planned_mileage_km") is None:
        payload_data["planned_mileage_km"] = route.standard_driver_mileage_km

    trip = Trip(**payload_data)
    db.add(trip)
    tractor.status = "assigned"
    driver.status = "assigned"
    if booking:
        booking.status = "converted"
        booking.converted_at = datetime.utcnow()
    db.flush()
    _generate_trip_milestones(db, trip, route)
    db.commit()
    db.refresh(trip)
    return trip


@router.get("/trips/{trip_id}", response_model=TripDetail)
def get_trip(trip_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    trip = db.query(Trip).options(joinedload(Trip.events), joinedload(Trip.expenses), joinedload(Trip.milestones)).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


VALID_TRIP_STATUSES = {"planned", "approved", "in_transit", "completed", "cancelled"}
# Once a trip has actually moved (or has money posted against it), it can no
# longer be silently rewound -- otherwise re-triggering "completed" could
# double-apply delay/demurrage calculations, and a trip with invoices/expenses
# has no business bouncing back to "planned".
TERMINAL_TRIP_STATUSES = {"completed", "cancelled"}


@router.patch("/trips/{trip_id}/status", response_model=TripOut)
def update_trip_status(trip_id: int, payload: TripStatusUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    trip = db.query(Trip).options(joinedload(Trip.expenses), joinedload(Trip.invoices)).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if payload.status not in VALID_TRIP_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(VALID_TRIP_STATUSES)}")
    if trip.status in TERMINAL_TRIP_STATUSES and payload.status != trip.status:
        raise HTTPException(status_code=400, detail=f"Trip is already '{trip.status}' and cannot be moved to '{payload.status}'")
    if payload.status == "cancelled" and (trip.expenses or trip.invoices):
        raise HTTPException(status_code=400, detail="Trip already has expenses or invoices recorded and cannot be cancelled; complete or reverse those first")

    trip.status = payload.status
    now = datetime.utcnow()
    if payload.status == "in_transit" and not trip.actual_departure:
        trip.actual_departure = now
        _recompute_milestone_targets(trip)
    if payload.status == "completed":
        trip.actual_arrival = now
        route = db.get(Route, trip.route_id)
        delay_charge, demurrage_cost = calculate_trip_delay_and_demurrage(trip, route)
        trip.delay_charge = delay_charge
        trip.demurrage_cost = demurrage_cost
        tractor = db.get(Vehicle, trip.tractor_id)
        driver = db.get(Driver, trip.driver_id)
        if tractor:
            tractor.status = "active"
        if driver:
            driver.status = "available"
    if payload.status == "cancelled":
        # A cancelled trip releases its equipment and driver back to the pool,
        # the same way completion does -- otherwise an aborted dispatch would
        # leave a perfectly good tractor and driver stuck as "assigned" forever.
        tractor = db.get(Vehicle, trip.tractor_id)
        driver = db.get(Driver, trip.driver_id)
        if tractor and tractor.status == "assigned":
            tractor.status = "active"
        if driver and driver.status == "assigned":
            driver.status = "available"
    db.commit()
    db.refresh(trip)
    return trip


@router.post("/trips/{trip_id}/events", response_model=TripEventOut)
def add_trip_event(trip_id: int, payload: TripEventCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    event = TripEvent(trip_id=trip_id, **payload.model_dump())
    if event.event_time is None:
        event.event_time = datetime.utcnow()
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.post("/trips/{trip_id}/milestones", response_model=TripMilestoneOut)
def add_trip_milestone(trip_id: int, payload: TripMilestoneCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    """Add a checkpoint to this specific trip that wasn't already in the
    route's milestone template (an unplanned stop, a one-off requirement)."""
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    milestone = TripMilestone(trip_id=trip_id, **payload.model_dump())
    if trip.actual_departure and milestone.target_hours_from_start is not None:
        milestone.target_at = trip.actual_departure + timedelta(hours=milestone.target_hours_from_start)
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.patch("/trips/{trip_id}/milestones/{milestone_id}/record", response_model=TripMilestoneOut)
def record_trip_milestone(trip_id: int, milestone_id: int, payload: TripMilestoneRecordActual, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    """Log that a checkpoint was actually reached -- this is what turns a
    predetermined time goal into a real planned-vs-actual comparison."""
    milestone = db.query(TripMilestone).filter(TripMilestone.id == milestone_id, TripMilestone.trip_id == trip_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Trip milestone not found")
    actual_at = payload.actual_at or datetime.utcnow()
    _apply_milestone_actual(milestone, actual_at)
    if payload.notes is not None:
        milestone.notes = payload.notes
    db.commit()
    db.refresh(milestone)
    return milestone


@router.patch("/trips/{trip_id}/milestones/{milestone_id}/skip", response_model=TripMilestoneOut)
def skip_trip_milestone(trip_id: int, milestone_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    """Mark a checkpoint as not applicable to how this trip actually ran
    (e.g. a route diversion bypassed a border post on the template)."""
    milestone = db.query(TripMilestone).filter(TripMilestone.id == milestone_id, TripMilestone.trip_id == trip_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Trip milestone not found")
    milestone.status = "skipped"
    db.commit()
    db.refresh(milestone)
    return milestone


@router.patch("/trips/{trip_id}/fuel-mileage", response_model=TripOut)
def update_trip_fuel_mileage(trip_id: int, payload: TripFuelMileageUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    """Record the actual fuel used and distance covered on a trip, for
    comparison against the planned figures snapshotted from its route."""
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(trip, field, value)
    db.commit()
    db.refresh(trip)
    return trip


@router.post("/trips/{trip_id}/expenses", response_model=ExpenseOut)
def add_trip_expense(trip_id: int, payload: ExpenseCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*OPS))):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if payload.vendor_id and not db.get(Vendor, payload.vendor_id):
        raise HTTPException(status_code=400, detail="Selected vendor was not found")
    expense = Expense(trip_id=trip_id, **payload.model_dump())
    db.add(expense)
    db.flush()
    accounting_service.post_trip_expense(
        db, expense, trip,
        payment_source=expense.payment_source,
        gl_account_code=expense.gl_account_code,
        created_by_id=user.id,
    )
    db.commit()
    db.refresh(expense)
    return expense


@router.patch("/expenses/{expense_id}/settle", response_model=ExpenseOut)
def settle_expense(expense_id: int, payload: PayableSettle, db: Session = Depends(get_db), user: User = Depends(require_roles(*FINANCE))):
    expense = db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense.payment_source != "payable":
        raise HTTPException(status_code=400, detail="Only payable-sourced expenses need settling -- this one was already paid via cash/bank when recorded")
    if expense.settled:
        raise HTTPException(status_code=400, detail="Expense is already settled")
    accounting_service.post_payable_settlement(
        db,
        source_type="trip_expense",
        source_id=expense.id,
        amount=expense.amount,
        description=f"{expense.expense_type} (expense #{expense.id})",
        payment_account_code=payload.payment_account_code,
        created_by_id=user.id,
    )
    expense.settled = True
    expense.settled_date = date.today()
    db.commit()
    db.refresh(expense)
    return expense


@router.patch("/maintenance/{record_id}/settle", response_model=MaintenanceOut)
def settle_maintenance(record_id: int, payload: PayableSettle, db: Session = Depends(get_db), user: User = Depends(require_roles(*FINANCE))):
    record = db.get(MaintenanceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    if record.payment_source != "payable":
        raise HTTPException(status_code=400, detail="Only payable-sourced maintenance costs need settling -- this one was already paid via cash/bank when recorded")
    if record.settled:
        raise HTTPException(status_code=400, detail="Maintenance cost is already settled")
    accounting_service.post_payable_settlement(
        db,
        source_type="maintenance",
        source_id=record.id,
        amount=record.cost or 0.0,
        description=f"{record.maintenance_type} (maintenance #{record.id})",
        payment_account_code=payload.payment_account_code,
        created_by_id=user.id,
    )
    record.settled = True
    record.settled_date = date.today()
    db.commit()
    db.refresh(record)
    return record


@router.post("/trips/{trip_id}/pod", response_model=TripOut)
async def upload_trip_pod(
    trip_id: int,
    notes: str | None = Form(None),
    document: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*OPS)),
):
    """Attach proof of delivery (a signed delivery note or photo) to a trip.

    Nothing previously required or even allowed recording evidence that
    cargo actually arrived before a trip could be invoiced -- this gives the
    accounts team something to point to when a client disputes an invoice.
    """
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if document and document.filename:
        POD_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        suffix = Path(document.filename).suffix or ".bin"
        filename = f"{trip.trip_number}-pod-{uuid4().hex}{suffix}"
        destination = POD_UPLOADS_DIR / filename
        contents = await document.read()
        destination.write_bytes(contents)
        trip.pod_document_path = f"/uploads/pod/{filename}"
    if notes is not None:
        trip.pod_notes = notes
    trip.pod_captured_at = datetime.utcnow()
    db.commit()
    db.refresh(trip)
    return trip


@router.post("/trips/{trip_id}/invoice", response_model=InvoiceOut)
def create_invoice_from_trip(trip_id: int, payload: InvoiceCreateFromTrip, db: Session = Depends(get_db), user: User = Depends(require_roles(*OPS_FINANCE))):
    trip = db.query(Trip).options(joinedload(Trip.expenses), joinedload(Trip.invoices)).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    invoice = generate_invoice_for_trip(
        db, trip, due_date=payload.due_date, notes=payload.notes,
        stage=payload.stage, stage_percentage=payload.stage_percentage,
    )
    accounting_service.post_invoice_issued(db, invoice, trip, created_by_id=user.id)

    client = db.get(Client, invoice.client_id)
    recipient = (client.invoice_email or client.billing_email) if client else None
    delivery = send_invoice_email(
        recipient=recipient,
        invoice_number=invoice.invoice_number,
        client_name=client.name if client else "",
        trip_number=trip.trip_number,
        amount=invoice.amount,
        currency=invoice.currency,
        stage=invoice.stage,
        due_date=invoice.due_date.isoformat() if invoice.due_date else None,
    )
    invoice.invoice_email_status = str(delivery["status"])
    invoice.invoice_email_error = delivery["error"] if isinstance(delivery["error"], str) or delivery["error"] is None else str(delivery["error"])
    invoice.invoice_email_sent_at = delivery["sent_at"] if isinstance(delivery["sent_at"], datetime) or delivery["sent_at"] is None else None

    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/invoices", response_model=list[InvoiceOut])
def list_invoices(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Invoice).order_by(Invoice.issue_date.desc()).all()


@router.patch("/invoices/{invoice_id}/reject", response_model=InvoiceOut)
def reject_invoice(invoice_id: int, payload: InvoiceRejection, db: Session = Depends(get_db), user: User = Depends(require_roles(*OPS_FINANCE))):
    """Record a client AP rejection (wrong route code, weight mismatch, etc.) and reverse its posting.

    Cross-border broker customers routinely bounce invoices back for
    correction with a ticket number; the revenue that was recognised when
    the invoice was issued should not stand until it is reissued, so the
    original journal entry is reversed here rather than left in the books.
    """
    invoice = db.query(Invoice).options(joinedload(Invoice.payments)).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.payments:
        raise HTTPException(status_code=400, detail="Cannot reject an invoice that already has payments recorded against it")
    if invoice.status == "rejected":
        raise HTTPException(status_code=400, detail="Invoice is already marked rejected")
    invoice.status = "rejected"
    invoice.rejection_reason = payload.rejection_reason
    invoice.rejection_ticket = payload.rejection_ticket
    accounting_service.reverse_source_entry(db, "trip_invoice", invoice.id, created_by_id=user.id, reason=f"Invoice {invoice.invoice_number} rejected: {payload.rejection_reason}")
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/payments", response_model=list[PaymentOut])
def list_payments(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Payment).order_by(Payment.payment_date.desc(), Payment.id.desc()).all()


@router.post("/payments/batch", response_model=list[PaymentOut])
def add_batch_payment(payload: BatchPaymentCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*FINANCE))):
    """Record one consolidated remittance advice that settles several invoices at once.

    Brokers like Poseidon pay a batch of invoices together and send a single
    remittance advice listing each one -- this posts a normal payment against
    every invoice in the batch while tagging them all with the same
    remittance_reference so they can be reconciled back to that one advice.
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="Provide at least one invoice/amount line")
    created: list[Payment] = []
    for item in payload.items:
        invoice = db.query(Invoice).options(joinedload(Invoice.payments)).filter(Invoice.id == item.invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail=f"Invoice {item.invoice_id} not found")
        payment = Payment(
            invoice_id=item.invoice_id,
            amount=item.amount,
            payment_date=payload.payment_date or datetime.utcnow().date(),
            method=payload.method,
            notes=payload.notes,
            deposit_account_code=payload.deposit_account_code,
            remittance_reference=payload.remittance_reference,
        )
        db.add(payment)
        db.flush()
        db.refresh(invoice)
        update_invoice_payment_status(invoice)
        accounting_service.post_payment_received(db, payment, invoice, deposit_account_code=payment.deposit_account_code, created_by_id=user.id)
        created.append(payment)
    db.commit()
    for payment in created:
        db.refresh(payment)
    return created


@router.post("/invoices/{invoice_id}/payments", response_model=PaymentOut)
def add_payment(invoice_id: int, payload: PaymentCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*FINANCE))):
    invoice = db.query(Invoice).options(joinedload(Invoice.payments)).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    payment = Payment(invoice_id=invoice_id, **payload.model_dump())
    if payment.payment_date is None:
        payment.payment_date = datetime.utcnow().date()
    db.add(payment)
    db.flush()
    db.refresh(invoice)
    update_invoice_payment_status(invoice)
    accounting_service.post_payment_received(
        db, payment, invoice,
        deposit_account_code=payment.deposit_account_code,
        created_by_id=user.id,
    )
    db.commit()
    db.refresh(payment)
    return payment


@router.get("/maintenance", response_model=list[MaintenanceOut])
def list_maintenance(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(MaintenanceRecord).order_by(MaintenanceRecord.created_at.desc()).all()


@router.post("/maintenance", response_model=MaintenanceOut)
def create_maintenance(payload: MaintenanceCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*OPS))):
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if payload.vendor_id and not db.get(Vendor, payload.vendor_id):
        raise HTTPException(status_code=400, detail="Selected vendor was not found")
    vehicle.status = "maintenance" if payload.status == "open" else vehicle.status
    record = MaintenanceRecord(**payload.model_dump())
    db.add(record)
    db.flush()
    accounting_service.post_maintenance_cost(
        db, record,
        payment_source=record.payment_source,
        gl_account_code=record.gl_account_code,
        created_by_id=user.id,
    )
    db.commit()
    db.refresh(record)
    return record


@router.patch("/maintenance/{record_id}/complete", response_model=MaintenanceOut)
def complete_maintenance(record_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    """Close a workshop job and hand the vehicle back to the active pool.

    Opening a maintenance record flips the vehicle to status="maintenance",
    but nothing previously closed the loop -- there was no way to bring the
    vehicle back into service short of editing the database directly. This
    finishes the job (records date_out, marks it closed) and reinstates the
    vehicle, unless it has another maintenance job still open.
    """
    record = db.get(MaintenanceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    if record.status == "closed":
        raise HTTPException(status_code=400, detail="Maintenance record is already closed")
    record.status = "closed"
    record.date_out = date.today()

    vehicle = db.get(Vehicle, record.vehicle_id)
    if vehicle and vehicle.status == "maintenance":
        other_open = db.query(MaintenanceRecord).filter(
            MaintenanceRecord.vehicle_id == vehicle.id,
            MaintenanceRecord.id != record.id,
            MaintenanceRecord.status == "open",
        ).first()
        if not other_open:
            vehicle.status = "active"
    db.commit()
    db.refresh(record)
    return record
