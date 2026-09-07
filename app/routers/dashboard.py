from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User, Vehicle, Driver, Trip, Invoice, Expense, MaintenanceRecord
from app.permissions import require_roles, OPS_FINANCE
from app.services import accounting as accounting_service
from app.services.notifications import send_compliance_digest_email

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

COMPLIANCE_WARNING_DAYS = 30


def _compliance_alerts(db: Session):
    """Flag vehicles/drivers whose compliance documents are expired or expiring soon.

    insurance_expiry, road_license_expiry, c28_expiry, and driver
    license_expiry are all captured at data entry but nothing previously
    surfaced them -- a truck with lapsed insurance could be dispatched with
    no warning. This mirrors the same "expired" vs "expiring within N days"
    split for both vehicles and drivers.
    """
    today = date.today()
    warning_cutoff = today + timedelta(days=COMPLIANCE_WARNING_DAYS)
    alerts = []

    vehicle_checks = [
        ("insurance_expiry", "Insurance"),
        ("road_license_expiry", "Road License"),
        ("c28_expiry", "C28"),
    ]
    vehicles = db.query(Vehicle).all()
    for vehicle in vehicles:
        for field, label in vehicle_checks:
            expiry = getattr(vehicle, field)
            if not expiry:
                continue
            if expiry < today:
                alerts.append({"entity_type": "vehicle", "entity_id": vehicle.id, "entity_label": vehicle.registration_no, "document": label, "expiry_date": expiry.isoformat(), "status": "expired"})
            elif expiry <= warning_cutoff:
                alerts.append({"entity_type": "vehicle", "entity_id": vehicle.id, "entity_label": vehicle.registration_no, "document": label, "expiry_date": expiry.isoformat(), "status": "expiring_soon"})

    drivers = db.query(Driver).all()
    for driver in drivers:
        expiry = driver.license_expiry
        if not expiry:
            continue
        if expiry < today:
            alerts.append({"entity_type": "driver", "entity_id": driver.id, "entity_label": driver.full_name, "document": "Driver License", "expiry_date": expiry.isoformat(), "status": "expired"})
        elif expiry <= warning_cutoff:
            alerts.append({"entity_type": "driver", "entity_id": driver.id, "entity_label": driver.full_name, "document": "Driver License", "expiry_date": expiry.isoformat(), "status": "expiring_soon"})

    alerts.sort(key=lambda a: a["expiry_date"])
    return alerts


@router.get("/compliance-alerts")
def compliance_alerts(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return _compliance_alerts(db)


def _render_digest_text(alerts: list[dict]) -> str:
    if not alerts:
        return "No expired or soon-to-expire compliance documents."
    lines = [f"{a['entity_type'].title()} {a['entity_label']}: {a['document']} {a['status'].replace('_', ' ')} ({a['expiry_date']})" for a in alerts]
    return "\n".join(lines)


@router.post("/compliance-alerts/send-digest")
def send_compliance_digest(db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS_FINANCE))):
    """Email the current compliance alert list to every admin user with an email on file.

    The dashboard panel only helps if someone actually opens it -- this is
    the manually-triggered version of a daily digest. Wiring it to an actual
    schedule needs a job runner (cron/celery) at deploy time; this endpoint
    is the send itself, ready to be called by one.
    """
    alerts = _compliance_alerts(db)
    admin_emails = [u.email for u in db.query(User).filter(User.role == "admin", User.is_active.is_(True)).all() if u.email]
    digest_text = _render_digest_text(alerts)
    deliveries = []
    if not admin_emails:
        deliveries.append(send_compliance_digest_email(recipient=None, digest_text=digest_text))
    else:
        for email in admin_emails:
            deliveries.append({"recipient": email, **send_compliance_digest_email(recipient=email, digest_text=digest_text)})
    return {"alerts_count": len(alerts), "deliveries": deliveries}


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    active_trips = db.query(func.count(Trip.id)).filter(Trip.status.in_(["planned", "approved", "in_transit"])).scalar() or 0
    completed_trips = db.query(func.count(Trip.id)).filter(Trip.status == "completed").scalar() or 0
    idle_vehicles = db.query(func.count(Vehicle.id)).filter(Vehicle.status == "idle").scalar() or 0
    maintenance_vehicles = db.query(func.count(Vehicle.id)).filter(Vehicle.status == "maintenance").scalar() or 0
    outstanding_invoices = db.query(func.count(Invoice.id)).filter(Invoice.status.in_(["issued", "partial"])).scalar() or 0
    revenue = db.query(func.coalesce(func.sum(Invoice.amount), 0.0)).scalar() or 0.0
    trip_expenses = db.query(func.coalesce(func.sum(Expense.amount), 0.0)).scalar() or 0.0
    compliance_alert_list = _compliance_alerts(db)

    # General-ledger figures, sourced from the same double-entry books used
    # by the Accounting module, so the dashboard and the ledger never drift.
    cash_and_bank_balance = accounting_service.account_group_balance(db, "Bank") + accounting_service.account_group_balance(db, "Cash on Hand")
    accounts_receivable_balance = accounting_service.account_group_balance(db, "Accounts Receivable (A/R)")
    accounts_payable_balance = accounting_service.account_group_balance(db, "Accounts Payable (A/P)")
    net_profit = accounting_service.profit_and_loss(db)["net_profit"]

    return {
        "active_trips": active_trips,
        "completed_trips": completed_trips,
        "idle_vehicles": idle_vehicles,
        "maintenance_vehicles": maintenance_vehicles,
        "outstanding_invoices": outstanding_invoices,
        "total_invoiced_revenue": round(revenue, 2),
        "total_recorded_expenses": round(trip_expenses, 2),
        "estimated_gross_margin": round(revenue - trip_expenses, 2),
        "cash_and_bank_balance": round(cash_and_bank_balance, 2),
        "accounts_receivable_balance": round(accounts_receivable_balance, 2),
        "accounts_payable_balance": round(accounts_payable_balance, 2),
        "ledger_net_profit": net_profit,
        "compliance_alerts_count": len(compliance_alert_list),
        "compliance_alerts_expired_count": sum(1 for a in compliance_alert_list if a["status"] == "expired"),
    }
