from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel
from .common import ORMBase


class TripCreate(BaseModel):
    trip_number: str
    booking_id: Optional[int] = None
    client_id: int
    route_id: int
    tractor_id: int
    trailer_id: Optional[int] = None
    dangler_id: Optional[int] = None
    driver_id: Optional[int] = None
    cargo_description: Optional[str] = None
    cargo_type: str
    container_size: Optional[str] = None
    agreed_revenue: float
    currency: str = "TZS"
    customer_reference: Optional[str] = None  # client's own order / allocation / booking code
    cargo_weight_tons: Optional[float] = None
    rate_per_ton: Optional[float] = None
    rate_type: Optional[str] = None  # flat, roundtrip, going, return
    is_backload: bool = False
    planned_departure: Optional[datetime] = None
    planned_arrival: Optional[datetime] = None
    # Optional per-trip overrides -- when omitted, create_trip snapshots
    # these from the route's standard_fuel_liters / standard_driver_mileage_km.
    planned_fuel_liters: Optional[float] = None
    planned_mileage_km: Optional[float] = None
    notes: Optional[str] = None


class TripStatusUpdate(BaseModel):
    status: str


class TripFuelMileageUpdate(BaseModel):
    """Actual fuel and mileage recorded against a trip, for comparison
    against the planned figures snapshotted from the route at dispatch."""
    actual_fuel_liters: Optional[float] = None
    actual_mileage_km: Optional[float] = None


class TripEventCreate(BaseModel):
    event_type: str
    location: Optional[str] = None
    event_time: Optional[datetime] = None
    delay_cause: Optional[str] = None
    notes: Optional[str] = None


class TripMilestoneCreate(BaseModel):
    """Add an ad-hoc checkpoint to a trip that wasn't already copied in from
    the route's milestone template (e.g. an unplanned stop)."""
    sequence: int = 0
    name: str
    milestone_type: str = "checkpoint"
    target_hours_from_start: Optional[float] = None
    notes: Optional[str] = None


class TripMilestoneRecordActual(BaseModel):
    """Record that a checkpoint was actually reached. actual_at defaults to
    now if omitted -- the common case is "just arrived, log it"."""
    actual_at: Optional[datetime] = None
    notes: Optional[str] = None


class TripMilestoneOut(ORMBase):
    id: int
    trip_id: int
    route_milestone_id: Optional[int] = None
    sequence: int
    name: str
    milestone_type: str
    target_hours_from_start: Optional[float] = None
    target_at: Optional[datetime] = None
    actual_at: Optional[datetime] = None
    status: str
    notes: Optional[str] = None


class ExpenseCreate(BaseModel):
    expense_type: str
    amount: float
    currency: str = "TZS"
    description: Optional[str] = None
    is_recoverable: bool = False
    payment_source: str = "payable"  # cash, bank, payable
    gl_account_code: Optional[str] = None
    vendor_id: Optional[int] = None


class TripEventOut(ORMBase):
    id: int
    trip_id: int
    event_type: str
    location: Optional[str] = None
    event_time: datetime
    delay_cause: Optional[str] = None
    notes: Optional[str] = None


class ExpenseOut(ORMBase):
    id: int
    trip_id: int
    expense_type: str
    amount: float
    currency: str
    description: Optional[str] = None
    is_recoverable: bool
    payment_source: str
    gl_account_code: Optional[str] = None
    vendor_id: Optional[int] = None
    settled: bool
    settled_date: Optional[date] = None


class TripOut(ORMBase):
    id: int
    trip_number: str
    booking_id: Optional[int] = None
    client_id: int
    route_id: int
    tractor_id: int
    trailer_id: Optional[int] = None
    dangler_id: Optional[int] = None
    driver_id: int
    cargo_description: Optional[str] = None
    cargo_type: str
    container_size: Optional[str] = None
    agreed_revenue: float
    currency: str
    customer_reference: Optional[str] = None
    cargo_weight_tons: Optional[float] = None
    rate_per_ton: Optional[float] = None
    rate_type: Optional[str] = None
    is_backload: bool
    planned_departure: Optional[datetime] = None
    planned_arrival: Optional[datetime] = None
    actual_departure: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    planned_fuel_liters: Optional[float] = None
    planned_mileage_km: Optional[float] = None
    actual_fuel_liters: Optional[float] = None
    actual_mileage_km: Optional[float] = None
    duration_hours: Optional[float] = None
    status: str
    delay_charge: float
    demurrage_cost: float
    notes: Optional[str] = None
    pod_document_path: Optional[str] = None
    pod_notes: Optional[str] = None
    pod_captured_at: Optional[datetime] = None


class TripDetail(TripOut):
    events: List[TripEventOut] = []
    expenses: List[ExpenseOut] = []
    milestones: List[TripMilestoneOut] = []


class BookingCreate(BaseModel):
    client_id: int
    route_id: int
    tractor_id: int
    cargo_type: str
    rate: float
    currency: str = "TZS"
    notes: Optional[str] = None


class BookingStatusUpdate(BaseModel):
    status: str


class BookingOut(ORMBase):
    id: int
    booking_number: str
    client_id: int
    route_id: int
    tractor_id: int
    cargo_type: str
    rate: float
    currency: str
    status: str
    booking_email_to: Optional[str] = None
    booking_email_status: Optional[str] = None
    booking_email_error: Optional[str] = None
    booking_email_sent_at: Optional[datetime] = None
    notes: Optional[str] = None
    accepted_at: Optional[datetime] = None
    converted_at: Optional[datetime] = None


class InvoiceCreateFromTrip(BaseModel):
    due_date: Optional[date] = None
    notes: Optional[str] = None
    stage: str = "full"  # full, advance, balance, final -- matches how the client's own AP team expects the trip billed
    stage_percentage: float = 100.0  # e.g. 70 for a 70% advance invoice


class InvoiceRejection(BaseModel):
    rejection_reason: str
    rejection_ticket: Optional[str] = None


class InvoiceOut(ORMBase):
    id: int
    invoice_number: str
    trip_id: int
    client_id: int
    amount: float
    currency: str
    status: str
    issue_date: date
    due_date: Optional[date] = None
    notes: Optional[str] = None
    stage: str
    stage_percentage: float
    rejection_reason: Optional[str] = None
    rejection_ticket: Optional[str] = None
    invoice_email_status: Optional[str] = None
    invoice_email_error: Optional[str] = None
    invoice_email_sent_at: Optional[datetime] = None


class PaymentCreate(BaseModel):
    amount: float
    payment_date: Optional[date] = None
    method: str
    reference: Optional[str] = None
    notes: Optional[str] = None
    deposit_account_code: Optional[str] = None
    remittance_reference: Optional[str] = None


class BatchPaymentItem(BaseModel):
    invoice_id: int
    amount: float


class BatchPaymentCreate(BaseModel):
    items: List[BatchPaymentItem]
    payment_date: Optional[date] = None
    method: str
    remittance_reference: str  # groups these settlements as one consolidated remittance advice
    deposit_account_code: Optional[str] = None
    notes: Optional[str] = None


class PaymentOut(ORMBase):
    id: int
    invoice_id: int
    amount: float
    payment_date: date
    method: str
    reference: Optional[str] = None
    notes: Optional[str] = None
    deposit_account_code: Optional[str] = None
    remittance_reference: Optional[str] = None


class MaintenanceCreate(BaseModel):
    vehicle_id: int
    maintenance_type: str
    description: Optional[str] = None
    service_provider: Optional[str] = None
    cost: float = 0.0
    payment_source: str = "payable"  # cash, bank, payable
    gl_account_code: Optional[str] = None
    vendor_id: Optional[int] = None
    date_in: date
    date_out: Optional[date] = None
    next_service_due: Optional[date] = None
    status: str = "open"


class MaintenanceOut(ORMBase):
    id: int
    vehicle_id: int
    maintenance_type: str
    description: Optional[str] = None
    service_provider: Optional[str] = None
    cost: float
    payment_source: str
    gl_account_code: Optional[str] = None
    vendor_id: Optional[int] = None
    settled: bool
    settled_date: Optional[date] = None
    date_in: date
    date_out: Optional[date] = None
    next_service_due: Optional[date] = None
    status: str


class PayableSettle(BaseModel):
    payment_account_code: Optional[str] = None
