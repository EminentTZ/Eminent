from datetime import date, datetime
from typing import Optional, Literal, List
from pydantic import BaseModel, EmailStr, Field
from .common import ORMBase

# The four user groups this system recognizes -- see app/permissions.py for
# exactly what each one can do. Kept as a Literal (rather than a free-form
# str) so a typo in a role name fails loudly at the API boundary instead of
# silently creating a user with no matching permission bundle.
UserRole = Literal["admin", "accountant", "operations", "viewer"]


class UserCreate(BaseModel):
    username: str
    full_name: str
    email: Optional[EmailStr] = None
    password: str = Field(min_length=6)
    role: UserRole = "operations"


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None


class UserOut(ORMBase):
    id: int
    username: str
    full_name: str
    email: Optional[EmailStr] = None
    role: str
    is_active: bool


class ClientCreate(BaseModel):
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    billing_email: Optional[EmailStr] = None
    booking_email: Optional[EmailStr] = None
    invoice_email: Optional[EmailStr] = None
    loading_order_email: Optional[EmailStr] = None
    statement_email: Optional[EmailStr] = None
    address: Optional[str] = None
    tin: Optional[str] = None
    currency: str = "TZS"
    credit_days: int = 30
    document_label: str = "Loading Order"  # what this client's own paperwork calls a dispatch order
    invoice_number_format: Optional[str] = None  # e.g. "POL/{stage}/{yy}/{mm}/{seq:04d}"; blank uses the house default


class ClientOut(ORMBase):
    id: int
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    billing_email: Optional[EmailStr] = None
    booking_email: Optional[EmailStr] = None
    invoice_email: Optional[EmailStr] = None
    loading_order_email: Optional[EmailStr] = None
    statement_email: Optional[EmailStr] = None
    address: Optional[str] = None
    tin: Optional[str] = None
    currency: str
    credit_days: int
    is_active: bool
    document_label: str
    invoice_number_format: Optional[str] = None


class VendorCreate(BaseModel):
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    tin: Optional[str] = None
    address: Optional[str] = None


class VendorOut(ORMBase):
    id: int
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    tin: Optional[str] = None
    address: Optional[str] = None
    is_active: bool


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    tin: Optional[str] = None
    address: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    billing_email: Optional[EmailStr] = None
    booking_email: Optional[EmailStr] = None
    invoice_email: Optional[EmailStr] = None
    loading_order_email: Optional[EmailStr] = None
    statement_email: Optional[EmailStr] = None
    address: Optional[str] = None
    tin: Optional[str] = None
    currency: Optional[str] = None
    credit_days: Optional[int] = None
    document_label: Optional[str] = None
    invoice_number_format: Optional[str] = None


class VehicleCreate(BaseModel):
    registration_no: str
    vehicle_type: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    capacity_tons: Optional[float] = None
    tyre_layout: Optional[str] = None
    fuel_type: Optional[str] = None
    status: str = "active"
    insurance_expiry: Optional[date] = None
    road_license_expiry: Optional[date] = None
    c28_expiry: Optional[date] = None
    c28_card_path: Optional[str] = None
    registration_card_path: Optional[str] = None
    tyre_info_json: Optional[str] = None
    linked_vehicle_id: Optional[int] = None


class VehicleOut(ORMBase):
    id: int
    registration_no: str
    vehicle_type: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    capacity_tons: Optional[float] = None
    tyre_layout: Optional[str] = None
    fuel_type: Optional[str] = None
    status: str
    insurance_expiry: Optional[date] = None
    road_license_expiry: Optional[date] = None
    c28_expiry: Optional[date] = None
    c28_card_path: Optional[str] = None
    registration_card_path: Optional[str] = None
    tyre_info_json: Optional[str] = None
    linked_vehicle_id: Optional[int] = None


class VehicleTyreInfoUpdate(BaseModel):
    tyre_info_json: Optional[str] = None


class VehicleUpdate(BaseModel):
    registration_no: Optional[str] = None
    vehicle_type: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    capacity_tons: Optional[float] = None
    tyre_layout: Optional[str] = None
    fuel_type: Optional[str] = None
    # Deliberately excludes "assigned"/"maintenance"/"grounded" -- those are
    # system-managed transitions (trip dispatch, maintenance open/close, the
    # dedicated ground/reinstate endpoints) and shouldn't be hand-edited here.
    status: Optional[str] = None
    insurance_expiry: Optional[date] = None
    road_license_expiry: Optional[date] = None
    c28_expiry: Optional[date] = None
    linked_vehicle_id: Optional[int] = None


class DriverCreate(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    phone: Optional[str] = None
    national_id_no: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    passport_no: Optional[str] = None
    gcla_certificate_no: Optional[str] = None
    date_of_employment: Optional[date] = None
    home_address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    referee1_first_name: Optional[str] = None
    referee1_middle_name: Optional[str] = None
    referee1_last_name: Optional[str] = None
    referee1_phone: Optional[str] = None
    referee2_first_name: Optional[str] = None
    referee2_middle_name: Optional[str] = None
    referee2_last_name: Optional[str] = None
    referee2_phone: Optional[str] = None
    passport_copy_path: Optional[str] = None
    photo_path: Optional[str] = None
    license_copy_path: Optional[str] = None
    gcla_certificate_copy_path: Optional[str] = None
    license_no: str
    license_class: Optional[str] = None
    license_expiry: date
    status: str = "available"
    assigned_vehicle_id: Optional[int] = None


class DriverOut(ORMBase):
    id: int
    full_name: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    national_id_no: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    passport_no: Optional[str] = None
    gcla_certificate_no: Optional[str] = None
    date_of_employment: Optional[date] = None
    home_address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    referee1_first_name: Optional[str] = None
    referee1_middle_name: Optional[str] = None
    referee1_last_name: Optional[str] = None
    referee1_phone: Optional[str] = None
    referee2_first_name: Optional[str] = None
    referee2_middle_name: Optional[str] = None
    referee2_last_name: Optional[str] = None
    referee2_phone: Optional[str] = None
    passport_copy_path: Optional[str] = None
    photo_path: Optional[str] = None
    license_copy_path: Optional[str] = None
    gcla_certificate_copy_path: Optional[str] = None
    license_no: str
    license_class: Optional[str] = None
    license_expiry: date
    status: str
    assigned_vehicle_id: Optional[int] = None


class DriverUpdate(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    national_id_no: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    passport_no: Optional[str] = None
    gcla_certificate_no: Optional[str] = None
    date_of_employment: Optional[date] = None
    home_address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    referee1_first_name: Optional[str] = None
    referee1_middle_name: Optional[str] = None
    referee1_last_name: Optional[str] = None
    referee1_phone: Optional[str] = None
    referee2_first_name: Optional[str] = None
    referee2_middle_name: Optional[str] = None
    referee2_last_name: Optional[str] = None
    referee2_phone: Optional[str] = None
    license_no: Optional[str] = None
    license_class: Optional[str] = None
    license_expiry: Optional[date] = None
    # Deliberately excludes "assigned" -- that's driven by the Equipment
    # Assignment workflow, not a manual edit.
    status: Optional[str] = None


class EquipmentAssignmentCreate(BaseModel):
    tractor_id: int
    trailer_id: Optional[int] = None
    dangler_id: Optional[int] = None
    driver_id: Optional[int] = None
    status: str = "active"
    allow_reassignment: bool = False


class EquipmentAssignmentOut(ORMBase):
    id: int
    tractor_id: int
    trailer_id: Optional[int] = None
    dangler_id: Optional[int] = None
    driver_id: Optional[int] = None
    status: str


class RouteCreate(BaseModel):
    route_name: str
    origin: str
    destination: str
    distance_km: Optional[float] = None
    expected_days: Optional[float] = None
    border_charges: float = 0.0
    driver_allowance: float = 0.0
    delay_threshold_days: float = 0.0
    demurrage_rate_per_day: float = 0.0
    standard_fuel_liters: Optional[float] = None
    standard_driver_mileage_km: Optional[float] = None


class RouteUpdate(BaseModel):
    route_name: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    distance_km: Optional[float] = None
    expected_days: Optional[float] = None
    border_charges: Optional[float] = None
    driver_allowance: Optional[float] = None
    delay_threshold_days: Optional[float] = None
    demurrage_rate_per_day: Optional[float] = None
    standard_fuel_liters: Optional[float] = None
    standard_driver_mileage_km: Optional[float] = None


class RouteOut(ORMBase):
    id: int
    route_name: str
    origin: str
    destination: str
    distance_km: Optional[float] = None
    expected_days: Optional[float] = None
    border_charges: float
    driver_allowance: float
    delay_threshold_days: float
    demurrage_rate_per_day: float
    standard_fuel_liters: Optional[float] = None
    standard_driver_mileage_km: Optional[float] = None


class RouteMilestoneCreate(BaseModel):
    sequence: int = 0
    name: str
    milestone_type: str = "checkpoint"  # departure, border, checkpoint, fuel_stop, destination, other
    target_hours_from_start: Optional[float] = None
    notes: Optional[str] = None


class RouteMilestoneUpdate(BaseModel):
    sequence: Optional[int] = None
    name: Optional[str] = None
    milestone_type: Optional[str] = None
    target_hours_from_start: Optional[float] = None
    notes: Optional[str] = None


class RouteMilestoneOut(ORMBase):
    id: int
    route_id: int
    sequence: int
    name: str
    milestone_type: str
    target_hours_from_start: Optional[float] = None
    notes: Optional[str] = None


class RouteDetail(RouteOut):
    milestones: List[RouteMilestoneOut] = []
