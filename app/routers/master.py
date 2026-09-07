from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User, Client, Vehicle, Driver, Route, RouteMilestone, EquipmentAssignment, Trip, Vendor
from app.permissions import require_roles, ADMIN_ONLY, OPS, OPS_FINANCE
from app.schemas.auth import ResetPasswordRequest
from app.schemas.master import (
    UserCreate, UserOut, UserUpdate,
    ClientCreate, ClientOut, ClientUpdate,
    VendorCreate, VendorOut, VendorUpdate,
    VehicleCreate, VehicleOut, VehicleTyreInfoUpdate, VehicleUpdate,
    DriverCreate, DriverOut, DriverUpdate,
    EquipmentAssignmentCreate, EquipmentAssignmentOut,
    RouteCreate, RouteOut, RouteUpdate, RouteDetail,
    RouteMilestoneCreate, RouteMilestoneOut, RouteMilestoneUpdate,
)
from app.security import get_password_hash

router = APIRouter(prefix="/master", tags=["Master Data"])
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads" / "vehicles"
DRIVER_UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads" / "drivers"


ACTIVE_TRIP_STATUSES = {"planned", "approved", "in_transit"}


def entity_has_active_trip(db: Session, entity_type: str, entity_id: int) -> bool:
    filters = {
        "tractor": Trip.tractor_id == entity_id,
        "trailer": Trip.trailer_id == entity_id,
        "dangler": Trip.dangler_id == entity_id,
        "driver": Trip.driver_id == entity_id,
    }
    return db.query(Trip).filter(filters[entity_type], Trip.status.in_(ACTIVE_TRIP_STATUSES)).first() is not None


def vehicle_has_active_trip(db: Session, vehicle_id: int) -> bool:
    return db.query(Trip).filter(
        or_(Trip.tractor_id == vehicle_id, Trip.trailer_id == vehicle_id, Trip.dangler_id == vehicle_id),
        Trip.status.in_(ACTIVE_TRIP_STATUSES),
    ).first() is not None


def assignment_has_active_trip(db: Session, assignment: EquipmentAssignment) -> bool:
    filters = [Trip.tractor_id == assignment.tractor_id]
    if assignment.trailer_id:
        filters.append(Trip.trailer_id == assignment.trailer_id)
    if assignment.dangler_id:
        filters.append(Trip.dangler_id == assignment.dangler_id)
    if assignment.driver_id:
        filters.append(Trip.driver_id == assignment.driver_id)
    return db.query(Trip).filter(or_(*filters), Trip.status.in_(ACTIVE_TRIP_STATUSES)).first() is not None


@router.post("/users", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*ADMIN_ONLY))):
    exists = db.query(User).filter(User.username == payload.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_roles(*ADMIN_ONLY))):
    # Who has an account and what role they hold is itself sensitive --
    # unlike almost everything else in this API, this list is admin-only
    # even to read.
    return db.query(User).order_by(User.created_at.desc()).all()


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*ADMIN_ONLY))):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = payload.model_dump(exclude_unset=True)
    if user.id == current_user.id and "role" in data and data["role"] != "admin" and current_user.role == "admin":
        raise HTTPException(status_code=400, detail="You cannot change your own admin role -- ask another admin to do this")
    for field, value in data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*ADMIN_ONLY))):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/reactivate", response_model=UserOut)
def reactivate_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*ADMIN_ONLY))):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/reset-password", response_model=UserOut)
def reset_user_password(user_id: int, payload: ResetPasswordRequest, db: Session = Depends(get_db), _: User = Depends(require_roles(*ADMIN_ONLY))):
    """Admin override -- set someone else's password without knowing the old
    one (they forgot it, or an account needs to be handed to someone new)."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    db.refresh(user)
    return user


@router.get("/clients", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Client).order_by(Client.name).all()


@router.post("/clients", response_model=ClientOut)
def create_client(payload: ClientCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    client = Client(**payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.put("/clients/{client_id}", response_model=ClientOut)
def update_client(client_id: int, payload: ClientUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return client


@router.patch("/clients/{client_id}/deactivate", response_model=ClientOut)
def deactivate_client(client_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    client.is_active = False
    db.commit()
    db.refresh(client)
    return client


@router.patch("/clients/{client_id}/reactivate", response_model=ClientOut)
def reactivate_client(client_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    client.is_active = True
    db.commit()
    db.refresh(client)
    return client


@router.get("/vendors", response_model=list[VendorOut])
def list_vendors(active_only: bool = False, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    query = db.query(Vendor)
    if active_only:
        query = query.filter(Vendor.is_active.is_(True))
    return query.order_by(Vendor.name).all()


@router.post("/vendors", response_model=VendorOut)
def create_vendor(payload: VendorCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS_FINANCE))):
    vendor = Vendor(**payload.model_dump())
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.put("/vendors/{vendor_id}", response_model=VendorOut)
def update_vendor(vendor_id: int, payload: VendorUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS_FINANCE))):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vendor, field, value)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.patch("/vendors/{vendor_id}/deactivate", response_model=VendorOut)
def deactivate_vendor(vendor_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS_FINANCE))):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    vendor.is_active = False
    db.commit()
    db.refresh(vendor)
    return vendor


@router.patch("/vendors/{vendor_id}/reactivate", response_model=VendorOut)
def reactivate_vendor(vendor_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS_FINANCE))):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    vendor.is_active = True
    db.commit()
    db.refresh(vendor)
    return vendor


@router.get("/vehicles", response_model=list[VehicleOut])
def list_vehicles(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Vehicle).order_by(Vehicle.registration_no).all()


@router.post("/vehicles", response_model=VehicleOut)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    exists = db.query(Vehicle).filter(Vehicle.registration_no == payload.registration_no).first()
    if exists:
        raise HTTPException(status_code=400, detail="Vehicle already exists")
    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.post("/vehicles/upload", response_model=VehicleOut)
async def create_vehicle_with_upload(
    registration_no: str = Form(...),
    vehicle_type: str = Form(...),
    make: str | None = Form(None),
    model: str | None = Form(None),
    year: int | None = Form(None),
    capacity_tons: float | None = Form(None),
    tyre_layout: str | None = Form(None),
    tyre_info_json: str | None = Form(None),
    fuel_type: str | None = Form(None),
    status: str = Form("active"),
    insurance_expiry: date | None = Form(None),
    road_license_expiry: date | None = Form(None),
    c28_expiry: date | None = Form(None),
    linked_vehicle_id: int | None = Form(None),
    c28_card: UploadFile | None = File(None),
    registration_card: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*OPS)),
):
    exists = db.query(Vehicle).filter(Vehicle.registration_no == registration_no).first()
    if exists:
        raise HTTPException(status_code=400, detail="Vehicle already exists")

    c28_card_path = None
    if c28_card and c28_card.filename:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        suffix = Path(c28_card.filename).suffix or ".bin"
        filename = f"{registration_no}-c28-{uuid4().hex}{suffix}"
        destination = UPLOADS_DIR / filename
        contents = await c28_card.read()
        destination.write_bytes(contents)
        c28_card_path = f"/uploads/vehicles/{filename}"

    registration_card_path = None
    if registration_card and registration_card.filename:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        suffix = Path(registration_card.filename).suffix or ".bin"
        filename = f"{registration_no}-registration-{uuid4().hex}{suffix}"
        destination = UPLOADS_DIR / filename
        contents = await registration_card.read()
        destination.write_bytes(contents)
        registration_card_path = f"/uploads/vehicles/{filename}"

    vehicle = Vehicle(
        registration_no=registration_no,
        vehicle_type=vehicle_type,
        make=make,
        model=model,
        year=year,
        capacity_tons=capacity_tons,
        tyre_layout=tyre_layout,
        tyre_info_json=tyre_info_json,
        fuel_type=fuel_type,
        status=status,
        insurance_expiry=insurance_expiry,
        road_license_expiry=road_license_expiry,
        c28_expiry=c28_expiry,
        c28_card_path=c28_card_path,
        registration_card_path=registration_card_path,
        linked_vehicle_id=linked_vehicle_id,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


MANUAL_VEHICLE_STATUSES = {"active", "idle"}


@router.put("/vehicles/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: int, payload: VehicleUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    data = payload.model_dump(exclude_unset=True)
    if "registration_no" in data and data["registration_no"] != vehicle.registration_no:
        exists = db.query(Vehicle).filter(Vehicle.registration_no == data["registration_no"]).first()
        if exists:
            raise HTTPException(status_code=400, detail="Another vehicle already uses that registration number")
    if "status" in data and data["status"] != vehicle.status and data["status"] not in MANUAL_VEHICLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="status can only be manually set to 'active' or 'idle' here; use the maintenance, "
                   "ground/reinstate, or trip workflows for other states",
        )
    for field, value in data.items():
        setattr(vehicle, field, value)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.patch("/vehicles/{vehicle_id}/ground", response_model=VehicleOut)
def ground_vehicle(vehicle_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    """Manually take a vehicle out of service (accident, compliance hold, etc.).

    Booking and trip creation both already refuse a "grounded" vehicle, but
    until now nothing could ever put a vehicle into that state -- there was
    no way to ground one short of editing the database directly.
    """
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.status == "grounded":
        raise HTTPException(status_code=400, detail="Vehicle is already grounded")
    if vehicle_has_active_trip(db, vehicle_id):
        raise HTTPException(status_code=400, detail="Vehicle is in an active trip and cannot be grounded")
    vehicle.status = "grounded"
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.patch("/vehicles/{vehicle_id}/reinstate", response_model=VehicleOut)
def reinstate_vehicle(vehicle_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.status != "grounded":
        raise HTTPException(status_code=400, detail="Vehicle is not currently grounded")
    vehicle.status = "active"
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.patch("/vehicles/{vehicle_id}/tyre-info", response_model=VehicleOut)
def update_vehicle_tyre_info(
    vehicle_id: int,
    payload: VehicleTyreInfoUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*OPS)),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    vehicle.tyre_info_json = payload.tyre_info_json
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.get("/drivers", response_model=list[DriverOut])
def list_drivers(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Driver).order_by(Driver.full_name).all()


@router.post("/drivers", response_model=DriverOut)
def create_driver(payload: DriverCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    exists = db.query(Driver).filter(Driver.license_no == payload.license_no).first()
    if exists:
        raise HTTPException(status_code=400, detail="Driver already exists")
    full_name = " ".join(part for part in [payload.first_name, payload.middle_name, payload.last_name] if part and part.strip())
    driver = Driver(**payload.model_dump(), full_name=full_name)
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return driver


MANUAL_DRIVER_STATUSES = {"available", "off_duty"}


@router.put("/drivers/{driver_id}", response_model=DriverOut)
def update_driver(driver_id: int, payload: DriverUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    data = payload.model_dump(exclude_unset=True)
    if "license_no" in data and data["license_no"] != driver.license_no:
        exists = db.query(Driver).filter(Driver.license_no == data["license_no"]).first()
        if exists:
            raise HTTPException(status_code=400, detail="Another driver already uses that license number")
    if "status" in data and data["status"] != driver.status and data["status"] not in MANUAL_DRIVER_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="status can only be manually set to 'available' or 'off_duty' here; "
                   "'assigned' is managed through Equipment Assignment",
        )
    for field, value in data.items():
        setattr(driver, field, value)
    if any(k in data for k in ("first_name", "middle_name", "last_name")):
        driver.full_name = " ".join(part for part in [driver.first_name, driver.middle_name, driver.last_name] if part and part.strip())
    db.commit()
    db.refresh(driver)
    return driver


@router.get("/assignments", response_model=list[EquipmentAssignmentOut])
def list_assignments(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(EquipmentAssignment).order_by(EquipmentAssignment.created_at.desc()).all()


@router.post("/assignments", response_model=EquipmentAssignmentOut)
def upsert_assignment(payload: EquipmentAssignmentCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    tractor = db.get(Vehicle, payload.tractor_id)
    if not tractor or tractor.vehicle_type != "tractor":
        raise HTTPException(status_code=400, detail="Selected tractor is invalid")

    trailer = db.get(Vehicle, payload.trailer_id) if payload.trailer_id else None
    if payload.trailer_id and (not trailer or trailer.vehicle_type != "trailer"):
        raise HTTPException(status_code=400, detail="Selected trailer is invalid")

    dangler = db.get(Vehicle, payload.dangler_id) if payload.dangler_id else None
    if payload.dangler_id and (not dangler or dangler.vehicle_type != "dangler"):
        raise HTTPException(status_code=400, detail="Selected dangler is invalid")

    if payload.dangler_id and not payload.trailer_id:
        raise HTTPException(status_code=400, detail="Assign a trailer before attaching a dangler")

    driver = db.get(Driver, payload.driver_id) if payload.driver_id else None
    if payload.driver_id and not driver:
        raise HTTPException(status_code=400, detail="Selected driver is invalid")

    current = db.query(EquipmentAssignment).filter(EquipmentAssignment.tractor_id == payload.tractor_id).first()
    current_id = current.id if current else None

    if entity_has_active_trip(db, "tractor", payload.tractor_id):
        raise HTTPException(status_code=400, detail="Selected tractor is in an active trip and cannot be reassigned")
    if payload.trailer_id and entity_has_active_trip(db, "trailer", payload.trailer_id):
        raise HTTPException(status_code=400, detail="Selected trailer is in an active trip and cannot be reassigned")
    if payload.dangler_id and entity_has_active_trip(db, "dangler", payload.dangler_id):
        raise HTTPException(status_code=400, detail="Selected dangler is in an active trip and cannot be reassigned")
    if payload.driver_id and entity_has_active_trip(db, "driver", payload.driver_id):
        raise HTTPException(status_code=400, detail="Selected driver is in an active trip and cannot be reassigned")

    if payload.status == "active":
        def conflicting_active_assignment(field_name: str, field_value: int | None):
            if not field_value:
                return None
            query = db.query(EquipmentAssignment).filter(
                EquipmentAssignment.status == "active",
                getattr(EquipmentAssignment, field_name) == field_value,
            )
            if current_id is not None:
                query = query.filter(EquipmentAssignment.id != current_id)
            return query.first()

        if payload.trailer_id:
            trailer_conflict = conflicting_active_assignment("trailer_id", payload.trailer_id)
            if trailer_conflict:
                if payload.allow_reassignment and not assignment_has_active_trip(db, trailer_conflict):
                    trailer_conflict.trailer_id = None
                else:
                    conflict_tractor = db.get(Vehicle, trailer_conflict.tractor_id)
                    raise HTTPException(
                        status_code=400,
                        detail=f"Trailer is already assigned to tractor {conflict_tractor.registration_no if conflict_tractor else trailer_conflict.tractor_id}",
                    )

        if payload.dangler_id:
            dangler_conflict = conflicting_active_assignment("dangler_id", payload.dangler_id)
            if dangler_conflict:
                if payload.allow_reassignment and not assignment_has_active_trip(db, dangler_conflict):
                    dangler_conflict.dangler_id = None
                else:
                    conflict_tractor = db.get(Vehicle, dangler_conflict.tractor_id)
                    raise HTTPException(
                        status_code=400,
                        detail=f"Dangler is already assigned to tractor {conflict_tractor.registration_no if conflict_tractor else dangler_conflict.tractor_id}",
                    )

        if payload.driver_id:
            driver_conflict = conflicting_active_assignment("driver_id", payload.driver_id)
            if driver_conflict:
                if payload.allow_reassignment and not assignment_has_active_trip(db, driver_conflict):
                    driver_conflict.driver_id = None
                    conflict_driver = db.get(Driver, payload.driver_id)
                    if conflict_driver and conflict_driver.assigned_vehicle_id == driver_conflict.tractor_id:
                        conflict_driver.assigned_vehicle_id = None
                else:
                    conflict_tractor = db.get(Vehicle, driver_conflict.tractor_id)
                    raise HTTPException(
                        status_code=400,
                        detail=f"Driver is already assigned to tractor {conflict_tractor.registration_no if conflict_tractor else driver_conflict.tractor_id}",
                    )

    previous_driver_id = current.driver_id if current else None
    if current:
        current.trailer_id = payload.trailer_id
        current.dangler_id = payload.dangler_id
        current.driver_id = payload.driver_id
        current.status = payload.status
        assignment = current
    else:
        assignment = EquipmentAssignment(**payload.model_dump())
        db.add(assignment)

    if previous_driver_id and previous_driver_id != payload.driver_id:
        previous_driver = db.get(Driver, previous_driver_id)
        if previous_driver and previous_driver.assigned_vehicle_id == payload.tractor_id:
            previous_driver.assigned_vehicle_id = None

    if payload.status == "active" and payload.driver_id:
        db.query(Driver).filter(Driver.id != payload.driver_id, Driver.assigned_vehicle_id == payload.tractor_id).update({Driver.assigned_vehicle_id: None})
        driver.assigned_vehicle_id = payload.tractor_id
    elif previous_driver_id:
        previous_driver = db.get(Driver, previous_driver_id)
        if previous_driver and previous_driver.assigned_vehicle_id == payload.tractor_id:
            previous_driver.assigned_vehicle_id = None

    db.commit()
    db.refresh(assignment)
    return assignment


async def save_driver_upload(file: UploadFile | None, license_no: str, suffix_label: str) -> str | None:
    if not file or not file.filename:
        return None
    DRIVER_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename).suffix or ".bin"
    filename = f"{license_no}-{suffix_label}-{uuid4().hex}{suffix}"
    destination = DRIVER_UPLOADS_DIR / filename
    contents = await file.read()
    destination.write_bytes(contents)
    return f"/uploads/drivers/{filename}"


@router.post("/drivers/upload", response_model=DriverOut)
async def create_driver_with_upload(
    first_name: str = Form(...),
    middle_name: str | None = Form(None),
    last_name: str = Form(...),
    phone: str | None = Form(None),
    national_id_no: str | None = Form(None),
    date_of_birth: date | None = Form(None),
    sex: str | None = Form(None),
    passport_no: str | None = Form(None),
    gcla_certificate_no: str | None = Form(None),
    date_of_employment: date | None = Form(None),
    home_address: str | None = Form(None),
    emergency_contact_name: str | None = Form(None),
    emergency_contact_relationship: str | None = Form(None),
    emergency_contact_phone: str | None = Form(None),
    referee1_first_name: str | None = Form(None),
    referee1_middle_name: str | None = Form(None),
    referee1_last_name: str | None = Form(None),
    referee1_phone: str | None = Form(None),
    referee2_first_name: str | None = Form(None),
    referee2_middle_name: str | None = Form(None),
    referee2_last_name: str | None = Form(None),
    referee2_phone: str | None = Form(None),
    license_no: str = Form(...),
    license_class: str | None = Form(None),
    license_expiry: date = Form(...),
    status: str = Form("available"),
    assigned_vehicle_id: int | None = Form(None),
    passport_copy: UploadFile | None = File(None),
    photo: UploadFile | None = File(None),
    license_copy: UploadFile | None = File(None),
    gcla_certificate_copy: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*OPS)),
):
    exists = db.query(Driver).filter(Driver.license_no == license_no).first()
    if exists:
        raise HTTPException(status_code=400, detail="Driver already exists")

    full_name = " ".join(part for part in [first_name, middle_name, last_name] if part and part.strip())
    driver = Driver(
        full_name=full_name,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        phone=phone,
        national_id_no=national_id_no,
        date_of_birth=date_of_birth,
        sex=sex,
        passport_no=passport_no,
        gcla_certificate_no=gcla_certificate_no,
        date_of_employment=date_of_employment,
        home_address=home_address,
        emergency_contact_name=emergency_contact_name,
        emergency_contact_relationship=emergency_contact_relationship,
        emergency_contact_phone=emergency_contact_phone,
        referee1_first_name=referee1_first_name,
        referee1_middle_name=referee1_middle_name,
        referee1_last_name=referee1_last_name,
        referee1_phone=referee1_phone,
        referee2_first_name=referee2_first_name,
        referee2_middle_name=referee2_middle_name,
        referee2_last_name=referee2_last_name,
        referee2_phone=referee2_phone,
        passport_copy_path=await save_driver_upload(passport_copy, license_no, "passport"),
        photo_path=await save_driver_upload(photo, license_no, "photo"),
        license_copy_path=await save_driver_upload(license_copy, license_no, "license"),
        gcla_certificate_copy_path=await save_driver_upload(gcla_certificate_copy, license_no, "gcla"),
        license_no=license_no,
        license_class=license_class,
        license_expiry=license_expiry,
        status=status,
        assigned_vehicle_id=assigned_vehicle_id,
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return driver


@router.get("/routes", response_model=list[RouteOut])
def list_routes(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Route).order_by(Route.route_name).all()


@router.post("/routes", response_model=RouteOut)
def create_route(payload: RouteCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    exists = db.query(Route).filter(Route.route_name == payload.route_name).first()
    if exists:
        raise HTTPException(status_code=400, detail="Route already exists")
    route = Route(**payload.model_dump())
    db.add(route)
    db.commit()
    db.refresh(route)
    return route


@router.put("/routes/{route_id}", response_model=RouteOut)
def update_route(route_id: int, payload: RouteUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    data = payload.model_dump(exclude_unset=True)
    if "route_name" in data and data["route_name"] != route.route_name:
        exists = db.query(Route).filter(Route.route_name == data["route_name"]).first()
        if exists:
            raise HTTPException(status_code=400, detail="Another route already uses that name")
    for field, value in data.items():
        setattr(route, field, value)
    db.commit()
    db.refresh(route)
    return route


@router.get("/routes/{route_id}", response_model=RouteDetail)
def get_route(route_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


@router.post("/routes/{route_id}/milestones", response_model=RouteMilestoneOut)
def create_route_milestone(route_id: int, payload: RouteMilestoneCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    """Add a predetermined checkpoint (a border, a fuel stop, the destination
    itself) to a route's template, with a time goal expressed as hours after
    departure. Every trip dispatched on this route from now on will get its
    own copy of this checkpoint -- see create_trip in operations.py.
    """
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    milestone = RouteMilestone(route_id=route_id, **payload.model_dump())
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.put("/routes/{route_id}/milestones/{milestone_id}", response_model=RouteMilestoneOut)
def update_route_milestone(route_id: int, milestone_id: int, payload: RouteMilestoneUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    milestone = db.query(RouteMilestone).filter(RouteMilestone.id == milestone_id, RouteMilestone.route_id == route_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Route milestone not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(milestone, field, value)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.delete("/routes/{route_id}/milestones/{milestone_id}")
def delete_route_milestone(route_id: int, milestone_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*OPS))):
    milestone = db.query(RouteMilestone).filter(RouteMilestone.id == milestone_id, RouteMilestone.route_id == route_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Route milestone not found")
    db.delete(milestone)
    db.commit()
    return {"status": "deleted"}
