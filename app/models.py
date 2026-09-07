from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, ForeignKey, Boolean, Text
)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="operations")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    contact_person = Column(String(120), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(120), nullable=True)
    billing_email = Column(String(120), nullable=True)
    booking_email = Column(String(120), nullable=True)
    invoice_email = Column(String(120), nullable=True)
    loading_order_email = Column(String(120), nullable=True)
    statement_email = Column(String(120), nullable=True)
    address = Column(Text, nullable=True)
    tin = Column(String(50), nullable=True)
    currency = Column(String(10), default="TZS")
    credit_days = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    # Different brokers/customers name and number their paperwork differently
    # (e.g. one issues a "Transport Order" and expects invoices numbered
    # POL/TRANS/26/05/0002, another issues a "Loading Order" and expects
    # WC/RETURN/26/04/001). These let each client's documents match what
    # their own AP team expects, instead of forcing one house format on
    # everyone.
    document_label = Column(String(50), default="Loading Order")  # what this client calls their dispatch order
    invoice_number_format = Column(String(80), nullable=True)  # e.g. "POL/{stage}/{yy}/{mm}/{seq:04d}"; blank = house default
    invoice_sequence = Column(Integer, default=0)  # last sequence number used in this client's invoice format
    created_at = Column(DateTime, default=datetime.utcnow)

    trips = relationship("Trip", back_populates="client")


class Vendor(Base):
    """A supplier/workshop/service provider that expenses and maintenance bills are owed to.

    Previously expenses and maintenance costs posted straight to the
    Accounts Payable GL account with only a free-text description -- there
    was no way to answer "how much do we owe this workshop" or reconcile
    against a supplier's own statement. This gives payables an actual
    counterparty.
    """

    __tablename__ = "vendors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    contact_person = Column(String(120), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(120), nullable=True)
    tin = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, index=True)
    registration_no = Column(String(50), unique=True, nullable=False, index=True)
    vehicle_type = Column(String(30), nullable=False)  # tractor, trailer, dangler
    make = Column(String(80), nullable=True)
    model = Column(String(80), nullable=True)
    year = Column(Integer, nullable=True)
    capacity_tons = Column(Float, nullable=True)
    tyre_layout = Column(String(20), nullable=True)
    fuel_type = Column(String(30), nullable=True)
    status = Column(String(30), default="active")  # active, idle, assigned, maintenance
    insurance_expiry = Column(Date, nullable=True)
    road_license_expiry = Column(Date, nullable=True)
    c28_expiry = Column(Date, nullable=True)
    c28_card_path = Column(String(255), nullable=True)
    registration_card_path = Column(String(255), nullable=True)
    tyre_info_json = Column(Text, nullable=True)
    linked_vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    linked_vehicle = relationship("Vehicle", remote_side=[id])


class Driver(Base):
    __tablename__ = "drivers"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False, index=True)
    first_name = Column(String(80), nullable=True)
    middle_name = Column(String(80), nullable=True)
    last_name = Column(String(80), nullable=True)
    phone = Column(String(50), nullable=True)
    national_id_no = Column(String(100), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    sex = Column(String(20), nullable=True)
    passport_no = Column(String(100), nullable=True)
    gcla_certificate_no = Column(String(100), nullable=True)
    date_of_employment = Column(Date, nullable=True)
    home_address = Column(Text, nullable=True)
    emergency_contact_name = Column(String(150), nullable=True)
    emergency_contact_relationship = Column(String(80), nullable=True)
    emergency_contact_phone = Column(String(50), nullable=True)
    referee1_first_name = Column(String(80), nullable=True)
    referee1_middle_name = Column(String(80), nullable=True)
    referee1_last_name = Column(String(80), nullable=True)
    referee1_phone = Column(String(50), nullable=True)
    referee2_first_name = Column(String(80), nullable=True)
    referee2_middle_name = Column(String(80), nullable=True)
    referee2_last_name = Column(String(80), nullable=True)
    referee2_phone = Column(String(50), nullable=True)
    passport_copy_path = Column(String(255), nullable=True)
    photo_path = Column(String(255), nullable=True)
    license_copy_path = Column(String(255), nullable=True)
    gcla_certificate_copy_path = Column(String(255), nullable=True)
    license_no = Column(String(100), unique=True, nullable=False)
    license_class = Column(String(20), nullable=True)
    license_expiry = Column(Date, nullable=False)
    status = Column(String(30), default="available")  # available, assigned, off_duty
    assigned_vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    assigned_vehicle = relationship("Vehicle")


class EquipmentAssignment(Base):
    __tablename__ = "equipment_assignments"
    id = Column(Integer, primary_key=True, index=True)
    tractor_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, unique=True)
    trailer_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    dangler_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    status = Column(String(30), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    tractor = relationship("Vehicle", foreign_keys=[tractor_id])
    trailer = relationship("Vehicle", foreign_keys=[trailer_id])
    dangler = relationship("Vehicle", foreign_keys=[dangler_id])
    driver = relationship("Driver", foreign_keys=[driver_id])


class Route(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True, index=True)
    route_name = Column(String(150), nullable=False, unique=True)
    origin = Column(String(120), nullable=False)
    destination = Column(String(120), nullable=False)
    distance_km = Column(Float, nullable=True)
    expected_days = Column(Float, nullable=True)
    border_charges = Column(Float, default=0.0)
    driver_allowance = Column(Float, default=0.0)
    delay_threshold_days = Column(Float, default=0.0)
    demurrage_rate_per_day = Column(Float, default=0.0)
    # Predetermined trip planning figures for this route -- set once here so
    # every trip dispatched on the route starts from the same fuel/mileage
    # budget instead of dispatchers guessing per trip. Both are snapshotted
    # onto the Trip at creation time (and can still be overridden per trip).
    standard_fuel_liters = Column(Float, nullable=True)
    standard_driver_mileage_km = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    milestones = relationship(
        "RouteMilestone", back_populates="route",
        order_by="RouteMilestone.sequence", cascade="all, delete-orphan",
    )


class RouteMilestone(Base):
    """A predetermined checkpoint template for a route (a border, a fuel stop,
    the destination itself) with a time goal expressed as hours after the
    trip's actual departure. Every trip dispatched on this route gets its own
    snapshot copy of these (see TripMilestone) so editing the template later
    never rewrites history for a trip already in progress.
    """
    __tablename__ = "route_milestones"
    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    sequence = Column(Integer, nullable=False, default=0)
    name = Column(String(150), nullable=False)
    milestone_type = Column(String(30), nullable=False, default="checkpoint")  # departure, border, checkpoint, fuel_stop, destination, other
    target_hours_from_start = Column(Float, nullable=True)  # time goal: hours after actual departure this checkpoint should be reached
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    route = relationship("Route", back_populates="milestones")


class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    booking_number = Column(String(50), unique=True, nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    tractor_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    cargo_type = Column(String(50), nullable=False)
    rate = Column(Float, nullable=False)
    currency = Column(String(10), default="TZS")
    status = Column(String(30), default="pending")
    booking_email_to = Column(String(120), nullable=True)
    booking_email_status = Column(String(30), default="pending")
    booking_email_error = Column(Text, nullable=True)
    booking_email_sent_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    converted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client")
    route = relationship("Route")
    tractor = relationship("Vehicle", foreign_keys=[tractor_id])


class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True, index=True)
    trip_number = Column(String(50), unique=True, nullable=False, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    tractor_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    trailer_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    dangler_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    cargo_description = Column(Text, nullable=True)
    cargo_type = Column(String(50), nullable=False)
    container_size = Column(String(20), nullable=True)
    agreed_revenue = Column(Float, nullable=False)
    currency = Column(String(10), default="TZS")
    # Bulk/mineral hauls (common on cross-border broker business) are quoted
    # per metric ton rather than a flat trip rate, and a broker's own
    # booking/allocation code (their reference, not ours) is how they
    # reconcile our invoice against their file -- capturing both keeps
    # agreed_revenue as the one number operations and accounting rely on
    # while still recording how it was arrived at.
    customer_reference = Column(String(100), nullable=True)  # client's own order/allocation/booking code
    cargo_weight_tons = Column(Float, nullable=True)
    rate_per_ton = Column(Float, nullable=True)
    rate_type = Column(String(20), nullable=True)  # flat, roundtrip, going, return
    is_backload = Column(Boolean, default=False)  # true if this trip carries return cargo (avoids a backload penalty)
    planned_departure = Column(DateTime, nullable=True)
    planned_arrival = Column(DateTime, nullable=True)
    actual_departure = Column(DateTime, nullable=True)
    actual_arrival = Column(DateTime, nullable=True)
    # Predetermined figures snapshotted from the route at trip creation
    # (editable per trip after that), plus the actual figures recorded once
    # known -- together these give operations a planned-vs-actual view on
    # fuel and distance for every trip, not just an after-the-fact expense.
    planned_fuel_liters = Column(Float, nullable=True)
    planned_mileage_km = Column(Float, nullable=True)
    actual_fuel_liters = Column(Float, nullable=True)
    actual_mileage_km = Column(Float, nullable=True)
    status = Column(String(30), default="planned")
    delay_charge = Column(Float, default=0.0)
    demurrage_cost = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    # Proof of delivery: nothing previously required (or even allowed
    # recording) any evidence that cargo actually arrived before a trip could
    # be invoiced. Cross-border broker customers dispute invoices over
    # exactly this (wrong weight, wrong reference) -- a signed delivery note
    # or photo attached here gives the accounts team something to point to.
    pod_document_path = Column(String(255), nullable=True)
    pod_notes = Column(Text, nullable=True)
    pod_captured_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="trips")
    booking = relationship("Booking")
    route = relationship("Route")
    tractor = relationship("Vehicle", foreign_keys=[tractor_id])
    trailer = relationship("Vehicle", foreign_keys=[trailer_id])
    dangler = relationship("Vehicle", foreign_keys=[dangler_id])
    driver = relationship("Driver")
    events = relationship("TripEvent", back_populates="trip", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="trip", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="trip", cascade="all, delete-orphan")
    milestones = relationship(
        "TripMilestone", back_populates="trip",
        order_by="TripMilestone.sequence", cascade="all, delete-orphan",
    )

    @property
    def duration_hours(self):
        """End-to-end trip time: actual departure to actual arrival, in hours.

        None until both timestamps are known -- while a trip is still in
        transit there is no finished duration yet, only elapsed time, which
        the caller can compute the same way against "now" if it wants a
        live-ticking figure.
        """
        if self.actual_departure and self.actual_arrival:
            return round((self.actual_arrival - self.actual_departure).total_seconds() / 3600, 2)
        return None


class TripMilestone(Base):
    """A checkpoint on one specific trip -- either copied from the route's
    RouteMilestone templates when the trip was created, or added ad hoc for
    something the route template didn't anticipate. target_at is filled in
    once the trip's actual_departure is known (target_hours_from_start is
    meaningless until there is a start to count from); actual_at is filled in
    by operations when the checkpoint is actually reached, which is what
    turns the predetermined time goal into a real planned-vs-actual record.
    """
    __tablename__ = "trip_milestones"
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    route_milestone_id = Column(Integer, ForeignKey("route_milestones.id"), nullable=True)
    sequence = Column(Integer, nullable=False, default=0)
    name = Column(String(150), nullable=False)
    milestone_type = Column(String(30), nullable=False, default="checkpoint")
    target_hours_from_start = Column(Float, nullable=True)
    target_at = Column(DateTime, nullable=True)
    actual_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending, reached, late, skipped
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    trip = relationship("Trip", back_populates="milestones")


class TripEvent(Base):
    __tablename__ = "trip_events"
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    location = Column(String(150), nullable=True)
    event_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    delay_cause = Column(String(80), nullable=True)
    notes = Column(Text, nullable=True)

    trip = relationship("Trip", back_populates="events")


class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    expense_type = Column(String(80), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="TZS")
    description = Column(Text, nullable=True)
    is_recoverable = Column(Boolean, default=False)
    payment_source = Column(String(20), default="payable")  # cash, bank, payable
    gl_account_code = Column(String(20), nullable=True)  # override the auto-mapped expense account
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    # Only meaningful when payment_source == "payable" -- cash/bank expenses
    # are settled the moment they're recorded, so they're never "outstanding".
    settled = Column(Boolean, default=False)
    settled_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    trip = relationship("Trip", back_populates="expenses")
    vendor = relationship("Vendor")


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="TZS")
    status = Column(String(30), default="draft")  # draft, issued, partial, paid, rejected
    issue_date = Column(Date, default=date.today)
    due_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    # Cross-border broker business is commonly invoiced in stages (a common
    # pattern: 70% on dispatch, 30% on POD) rather than one invoice per trip.
    stage = Column(String(20), default="full")  # full, advance, balance, final
    stage_percentage = Column(Float, default=100.0)  # % of the trip's total this invoice represents
    rejection_reason = Column(Text, nullable=True)
    rejection_ticket = Column(String(60), nullable=True)
    invoice_email_status = Column(String(30), nullable=True)  # mirrors Booking's email delivery tracking
    invoice_email_error = Column(Text, nullable=True)
    invoice_email_sent_at = Column(DateTime, nullable=True)

    trip = relationship("Trip", back_populates="invoices")
    client = relationship("Client")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_date = Column(Date, default=date.today)
    method = Column(String(30), nullable=False)
    reference = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    deposit_account_code = Column(String(20), nullable=True)  # override the auto-mapped cash/bank account
    remittance_reference = Column(String(80), nullable=True)  # groups payments settled together in one consolidated remittance advice

    invoice = relationship("Invoice", back_populates="payments")


class Account(Base):
    """A chart-of-accounts entry.

    Codes mirror the live NextAccounting Chart of Accounts used by this
    company's bookkeeping instance, so transaction data recorded here can be
    reconciled directly against the general ledger of record.
    """

    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    statement_class = Column(String(20), nullable=False)  # asset, liability, equity, income, cogs, expense
    account_group = Column(String(100), nullable=True)
    normal_balance = Column(String(10), nullable=False)  # debit, credit
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=True)  # seeded from the official COA; protected from deletion
    parent_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    parent = relationship("Account", remote_side=[id])


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True, index=True)
    entry_number = Column(String(30), unique=True, nullable=False, index=True)
    entry_date = Column(Date, nullable=False, default=date.today)
    memo = Column(Text, nullable=True)
    source_type = Column(String(30), nullable=False, default="manual")
    # trip_invoice, payment, trip_expense, maintenance, payroll, manual, opening_balance
    source_id = Column(Integer, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    reversed_entry_id = Column(Integer, ForeignKey("journal_entries.id"), nullable=True)

    lines = relationship("JournalLine", back_populates="entry", cascade="all, delete-orphan")
    created_by = relationship("User")
    reversed_entry = relationship("JournalEntry", remote_side=[id])


class JournalLine(Base):
    __tablename__ = "journal_lines"
    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    debit = Column(Float, nullable=False, default=0.0)
    credit = Column(Float, nullable=False, default=0.0)
    description = Column(Text, nullable=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)

    entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("Account")
    trip = relationship("Trip")
    vehicle = relationship("Vehicle")

    @property
    def account_code(self) -> str:
        return self.account.code if self.account else ""

    @property
    def account_name(self) -> str:
        return self.account.name if self.account else ""


class LedgerSettings(Base):
    """Singleton row (id=1) mapping business events to default GL accounts.

    Kept editable so a bookkeeper can repoint postings without a code change,
    while still shipping with sensible defaults drawn from the company COA.
    """

    __tablename__ = "ledger_settings"
    id = Column(Integer, primary_key=True, default=1)
    default_cash_account_code = Column(String(20), default="1021")  # Petty Cash
    default_bank_account_code = Column(String(20), default="1000")  # Bank
    receivable_account_code = Column(String(20), default="1100")  # Account Receivable (A/R)
    payable_account_code = Column(String(20), default="2000")  # Accounts Payable (A/P)
    revenue_account_code = Column(String(20), default="4003")  # Transportation Sales
    delay_income_account_code = Column(String(20), default="4002")  # Delay Charge Fee
    recovered_expense_income_code = Column(String(20), default="4005")  # Un-categorized Income
    default_trip_cogs_account_code = Column(String(20), default="5200")  # Trip Driver Expenses
    default_maintenance_account_code = Column(String(20), default="6350")  # Motor Repair and Maintenance
    default_expense_account_code = Column(String(20), default="6903")  # Un-categorized Expenses
    retained_earnings_account_code = Column(String(20), default="3100")


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    maintenance_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    service_provider = Column(String(120), nullable=True)
    cost = Column(Float, default=0.0)
    payment_source = Column(String(20), default="payable")  # cash, bank, payable
    gl_account_code = Column(String(20), nullable=True)  # override the auto-mapped maintenance account
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    settled = Column(Boolean, default=False)
    settled_date = Column(Date, nullable=True)
    date_in = Column(Date, nullable=False)
    date_out = Column(Date, nullable=True)
    next_service_due = Column(Date, nullable=True)
    status = Column(String(30), default="open")
    created_at = Column(DateTime, default=datetime.utcnow)

    vehicle = relationship("Vehicle")
    vendor = relationship("Vendor")
