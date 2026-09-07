from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import Base, engine, SessionLocal
from app.models import User
from app.routers import auth, master, operations, dashboard, accounting
from app.security import get_password_hash
from app.services.accounting import seed_chart_of_accounts

app = FastAPI(title="Transportation Management System MVP", version="1.0.0")
static_dir = Path(__file__).parent / "static"
uploads_dir = Path(__file__).parent / "uploads"

Base.metadata.create_all(bind=engine)


def ensure_schema_compatibility() -> None:
    with engine.begin() as connection:
        client_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(clients)"))
        }
        if "billing_email" not in client_columns:
            connection.execute(text("ALTER TABLE clients ADD COLUMN billing_email VARCHAR(120)"))
        if "booking_email" not in client_columns:
            connection.execute(text("ALTER TABLE clients ADD COLUMN booking_email VARCHAR(120)"))
        if "invoice_email" not in client_columns:
            connection.execute(text("ALTER TABLE clients ADD COLUMN invoice_email VARCHAR(120)"))
        if "loading_order_email" not in client_columns:
            connection.execute(text("ALTER TABLE clients ADD COLUMN loading_order_email VARCHAR(120)"))
        if "statement_email" not in client_columns:
            connection.execute(text("ALTER TABLE clients ADD COLUMN statement_email VARCHAR(120)"))
        if "document_label" not in client_columns:
            connection.execute(text("ALTER TABLE clients ADD COLUMN document_label VARCHAR(50) DEFAULT 'Loading Order'"))
        if "invoice_number_format" not in client_columns:
            connection.execute(text("ALTER TABLE clients ADD COLUMN invoice_number_format VARCHAR(80)"))
        if "invoice_sequence" not in client_columns:
            connection.execute(text("ALTER TABLE clients ADD COLUMN invoice_sequence INTEGER DEFAULT 0"))

        vehicle_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(vehicles)"))
        }
        if "c28_expiry" not in vehicle_columns:
            connection.execute(text("ALTER TABLE vehicles ADD COLUMN c28_expiry DATE"))
        if "c28_card_path" not in vehicle_columns:
            connection.execute(text("ALTER TABLE vehicles ADD COLUMN c28_card_path VARCHAR(255)"))
        if "registration_card_path" not in vehicle_columns:
            connection.execute(text("ALTER TABLE vehicles ADD COLUMN registration_card_path VARCHAR(255)"))
        if "tyre_layout" not in vehicle_columns:
            connection.execute(text("ALTER TABLE vehicles ADD COLUMN tyre_layout VARCHAR(20)"))
        if "tyre_info_json" not in vehicle_columns:
            connection.execute(text("ALTER TABLE vehicles ADD COLUMN tyre_info_json TEXT"))

        driver_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(drivers)"))
        }
        if "first_name" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN first_name VARCHAR(80)"))
        if "middle_name" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN middle_name VARCHAR(80)"))
        if "last_name" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN last_name VARCHAR(80)"))
        if "national_id_no" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN national_id_no VARCHAR(100)"))
        if "date_of_birth" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN date_of_birth DATE"))
        if "sex" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN sex VARCHAR(20)"))
        if "passport_no" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN passport_no VARCHAR(100)"))
        if "gcla_certificate_no" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN gcla_certificate_no VARCHAR(100)"))
        if "date_of_employment" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN date_of_employment DATE"))
        if "home_address" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN home_address TEXT"))
        if "emergency_contact_name" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN emergency_contact_name VARCHAR(150)"))
        if "emergency_contact_relationship" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN emergency_contact_relationship VARCHAR(80)"))
        if "emergency_contact_phone" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN emergency_contact_phone VARCHAR(50)"))
        if "referee1_first_name" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN referee1_first_name VARCHAR(80)"))
        if "referee1_middle_name" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN referee1_middle_name VARCHAR(80)"))
        if "referee1_last_name" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN referee1_last_name VARCHAR(80)"))
        if "referee1_phone" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN referee1_phone VARCHAR(50)"))
        if "referee2_first_name" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN referee2_first_name VARCHAR(80)"))
        if "referee2_middle_name" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN referee2_middle_name VARCHAR(80)"))
        if "referee2_last_name" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN referee2_last_name VARCHAR(80)"))
        if "referee2_phone" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN referee2_phone VARCHAR(50)"))
        if "passport_copy_path" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN passport_copy_path VARCHAR(255)"))
        if "photo_path" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN photo_path VARCHAR(255)"))
        if "license_copy_path" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN license_copy_path VARCHAR(255)"))
        if "gcla_certificate_copy_path" not in driver_columns:
            connection.execute(text("ALTER TABLE drivers ADD COLUMN gcla_certificate_copy_path VARCHAR(255)"))

        trip_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(trips)"))
        }
        if "booking_id" not in trip_columns:
            connection.execute(text("ALTER TABLE trips ADD COLUMN booking_id INTEGER"))
        if "customer_reference" not in trip_columns:
            connection.execute(text("ALTER TABLE trips ADD COLUMN customer_reference VARCHAR(100)"))
        if "cargo_weight_tons" not in trip_columns:
            connection.execute(text("ALTER TABLE trips ADD COLUMN cargo_weight_tons FLOAT"))
        if "rate_per_ton" not in trip_columns:
            connection.execute(text("ALTER TABLE trips ADD COLUMN rate_per_ton FLOAT"))
        if "rate_type" not in trip_columns:
            connection.execute(text("ALTER TABLE trips ADD COLUMN rate_type VARCHAR(20)"))
        if "is_backload" not in trip_columns:
            connection.execute(text("ALTER TABLE trips ADD COLUMN is_backload BOOLEAN DEFAULT 0"))

        booking_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(bookings)"))
        } if connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='bookings'")).fetchone() else set()
        if booking_columns:
            if "booking_email_to" not in booking_columns:
                connection.execute(text("ALTER TABLE bookings ADD COLUMN booking_email_to VARCHAR(120)"))
            if "booking_email_status" not in booking_columns:
                connection.execute(text("ALTER TABLE bookings ADD COLUMN booking_email_status VARCHAR(30)"))
            if "booking_email_error" not in booking_columns:
                connection.execute(text("ALTER TABLE bookings ADD COLUMN booking_email_error TEXT"))
            if "booking_email_sent_at" not in booking_columns:
                connection.execute(text("ALTER TABLE bookings ADD COLUMN booking_email_sent_at DATETIME"))

        expense_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(expenses)"))
        }
        if "payment_source" not in expense_columns:
            connection.execute(text("ALTER TABLE expenses ADD COLUMN payment_source VARCHAR(20) DEFAULT 'payable'"))
        if "gl_account_code" not in expense_columns:
            connection.execute(text("ALTER TABLE expenses ADD COLUMN gl_account_code VARCHAR(20)"))

        maintenance_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(maintenance_records)"))
        }
        if "payment_source" not in maintenance_columns:
            connection.execute(text("ALTER TABLE maintenance_records ADD COLUMN payment_source VARCHAR(20) DEFAULT 'payable'"))
        if "gl_account_code" not in maintenance_columns:
            connection.execute(text("ALTER TABLE maintenance_records ADD COLUMN gl_account_code VARCHAR(20)"))

        payment_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(payments)"))
        }
        if "deposit_account_code" not in payment_columns:
            connection.execute(text("ALTER TABLE payments ADD COLUMN deposit_account_code VARCHAR(20)"))
        if "remittance_reference" not in payment_columns:
            connection.execute(text("ALTER TABLE payments ADD COLUMN remittance_reference VARCHAR(80)"))

        invoice_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(invoices)"))
        }
        if "stage" not in invoice_columns:
            connection.execute(text("ALTER TABLE invoices ADD COLUMN stage VARCHAR(20) DEFAULT 'full'"))
        if "stage_percentage" not in invoice_columns:
            connection.execute(text("ALTER TABLE invoices ADD COLUMN stage_percentage FLOAT DEFAULT 100.0"))
        if "rejection_reason" not in invoice_columns:
            connection.execute(text("ALTER TABLE invoices ADD COLUMN rejection_reason TEXT"))
        if "rejection_ticket" not in invoice_columns:
            connection.execute(text("ALTER TABLE invoices ADD COLUMN rejection_ticket VARCHAR(60)"))
        if "invoice_email_status" not in invoice_columns:
            connection.execute(text("ALTER TABLE invoices ADD COLUMN invoice_email_status VARCHAR(30)"))
        if "invoice_email_error" not in invoice_columns:
            connection.execute(text("ALTER TABLE invoices ADD COLUMN invoice_email_error TEXT"))
        if "invoice_email_sent_at" not in invoice_columns:
            connection.execute(text("ALTER TABLE invoices ADD COLUMN invoice_email_sent_at DATETIME"))

        if "pod_document_path" not in trip_columns:
            connection.execute(text("ALTER TABLE trips ADD COLUMN pod_document_path VARCHAR(255)"))
        if "pod_notes" not in trip_columns:
            connection.execute(text("ALTER TABLE trips ADD COLUMN pod_notes TEXT"))
        if "pod_captured_at" not in trip_columns:
            connection.execute(text("ALTER TABLE trips ADD COLUMN pod_captured_at DATETIME"))

        if "vendor_id" not in expense_columns:
            connection.execute(text("ALTER TABLE expenses ADD COLUMN vendor_id INTEGER"))
        if "settled" not in expense_columns:
            connection.execute(text("ALTER TABLE expenses ADD COLUMN settled BOOLEAN DEFAULT 0"))
        if "settled_date" not in expense_columns:
            connection.execute(text("ALTER TABLE expenses ADD COLUMN settled_date DATE"))

        if "vendor_id" not in maintenance_columns:
            connection.execute(text("ALTER TABLE maintenance_records ADD COLUMN vendor_id INTEGER"))
        if "settled" not in maintenance_columns:
            connection.execute(text("ALTER TABLE maintenance_records ADD COLUMN settled BOOLEAN DEFAULT 0"))
        if "settled_date" not in maintenance_columns:
            connection.execute(text("ALTER TABLE maintenance_records ADD COLUMN settled_date DATE"))


def seed_admin() -> None:
    db: Session = SessionLocal()
    try:
        exists = db.query(User).filter(User.username == "admin").first()
        if not exists:
            user = User(
                username="admin",
                full_name="System Administrator",
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                role="admin",
                is_active=True,
            )
            db.add(user)
            db.commit()
    finally:
        db.close()


seed_admin()
# This ad-hoc migration shim speaks SQLite's PRAGMA/sqlite_master dialect
# specifically -- it exists to add columns to an existing SQLite dev database
# as the schema evolved across this project's development. On any other
# database engine (Postgres in production) there's nothing to migrate on a
# fresh deploy since create_all() above already created the full current
# schema, and running SQLite-only statements against Postgres would just
# crash startup -- so this only runs when the configured DB actually is
# SQLite. A real deployment that later changes its schema should move to
# proper Alembic migrations rather than extending this shim.
if engine.dialect.name == "sqlite":
    ensure_schema_compatibility()


def seed_accounting() -> None:
    db: Session = SessionLocal()
    try:
        seed_chart_of_accounts(db)
    finally:
        db.close()


seed_accounting()
uploads_dir.mkdir(parents=True, exist_ok=True)

app.include_router(auth.router)
app.include_router(master.router)
app.include_router(operations.router)
app.include_router(dashboard.router)
app.include_router(accounting.router)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


@app.get("/")
def root():
    return FileResponse(static_dir / "index.html")


@app.get("/api/health")
def health():
    return {
        "message": "Transportation Management System MVP API is running",
        "docs": "/docs",
    }
