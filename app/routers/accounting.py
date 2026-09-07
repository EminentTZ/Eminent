from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user
from app.models import User, Account, JournalEntry, JournalLine, Client
from app.permissions import require_roles, FINANCE
from app.schemas.accounting import (
    AccountCreate, AccountOut,
    JournalEntryCreate, JournalEntryOut,
    LedgerSettingsOut, LedgerSettingsUpdate,
)
from app.services import accounting as accounting_service
from app.services.notifications import send_statement_email

router = APIRouter(prefix="/accounting", tags=["Accounting"])


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(
    statement_class: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(Account)
    if statement_class:
        query = query.filter(Account.statement_class == statement_class)
    if active_only:
        query = query.filter(Account.is_active.is_(True))
    return query.order_by(Account.code).all()


@router.post("/accounts", response_model=AccountOut)
def create_account(payload: AccountCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*FINANCE))):
    if db.query(Account).filter(Account.code == payload.code).first():
        raise HTTPException(status_code=400, detail="An account with this code already exists")
    if payload.statement_class not in {"asset", "liability", "equity", "income", "cogs", "expense"}:
        raise HTTPException(status_code=400, detail="statement_class must be one of asset, liability, equity, income, cogs, expense")
    if payload.normal_balance not in {"debit", "credit"}:
        raise HTTPException(status_code=400, detail="normal_balance must be debit or credit")
    parent = None
    if payload.parent_code:
        parent = db.query(Account).filter(Account.code == payload.parent_code).first()
        if not parent:
            raise HTTPException(status_code=400, detail="parent_code does not match any existing account")
    account = Account(
        code=payload.code,
        name=payload.name,
        statement_class=payload.statement_class,
        account_group=payload.account_group,
        normal_balance=payload.normal_balance,
        is_system=False,
        parent_id=parent.id if parent else None,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.patch("/accounts/{account_id}/deactivate", response_model=AccountOut)
def deactivate_account(account_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*FINANCE))):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.is_system:
        raise HTTPException(status_code=400, detail="System accounts from the official chart of accounts cannot be deactivated")
    account.is_active = False
    db.commit()
    db.refresh(account)
    return account


@router.get("/journal", response_model=list[JournalEntryOut])
def list_journal_entries(
    source_type: Optional[str] = None,
    source_id: Optional[int] = None,
    trip_id: Optional[int] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(JournalEntry).options(joinedload(JournalEntry.lines))
    if source_type:
        query = query.filter(JournalEntry.source_type == source_type)
    if source_id is not None:
        query = query.filter(JournalEntry.source_id == source_id)
    if start:
        query = query.filter(JournalEntry.entry_date >= start)
    if end:
        query = query.filter(JournalEntry.entry_date <= end)
    if trip_id is not None:
        query = query.join(JournalLine, JournalEntry.lines).filter(JournalLine.trip_id == trip_id)
    return query.order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc()).limit(limit).all()


@router.get("/journal/{entry_id}", response_model=JournalEntryOut)
def get_journal_entry(entry_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    entry = db.query(JournalEntry).options(joinedload(JournalEntry.lines)).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry


@router.post("/journal", response_model=JournalEntryOut)
def create_manual_journal_entry(payload: JournalEntryCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*FINANCE))):
    entry = accounting_service.post_journal_entry(
        db,
        entry_date=payload.entry_date or date.today(),
        memo=payload.memo,
        source_type="manual",
        created_by_id=user.id,
        lines=[line.model_dump() for line in payload.lines],
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/journal/{entry_id}/reverse", response_model=JournalEntryOut)
def reverse_journal_entry(entry_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*FINANCE))):
    original = db.query(JournalEntry).options(joinedload(JournalEntry.lines)).filter(JournalEntry.id == entry_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    reversal = accounting_service.reverse_journal_entry(db, original, created_by_id=user.id)
    db.commit()
    db.refresh(reversal)
    return reversal


@router.get("/ledger/{account_code}")
def get_account_ledger(
    account_code: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    account = accounting_service.get_account_by_code(db, account_code)
    return accounting_service.account_ledger(db, account, start=start, end=end)


@router.get("/reports/trial-balance")
def get_trial_balance(as_of: Optional[date] = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return accounting_service.trial_balance(db, as_of=as_of)


@router.get("/reports/profit-and-loss")
def get_profit_and_loss(start: Optional[date] = None, end: Optional[date] = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return accounting_service.profit_and_loss(db, start=start, end=end)


@router.get("/reports/balance-sheet")
def get_balance_sheet(as_of: Optional[date] = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return accounting_service.balance_sheet(db, as_of=as_of)


@router.get("/reports/ar-aging")
def get_ar_aging(as_of: Optional[date] = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return accounting_service.ar_aging(db, as_of=as_of)


@router.get("/reports/ap-aging")
def get_ap_aging(as_of: Optional[date] = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return accounting_service.ap_aging(db, as_of=as_of)


@router.get("/reports/client-statement/{client_id}")
def get_client_statement(client_id: int, as_of: Optional[date] = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return accounting_service.client_statement(db, client, as_of=as_of)


@router.post("/reports/client-statement/{client_id}/send")
def send_client_statement(client_id: int, as_of: Optional[date] = None, db: Session = Depends(get_db), _: User = Depends(require_roles(*FINANCE))):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    statement = accounting_service.client_statement(db, client, as_of=as_of)
    recipient = client.statement_email or client.billing_email or client.invoice_email
    delivery = send_statement_email(
        recipient=recipient,
        client_name=client.name,
        statement_text=accounting_service.render_statement_text(statement),
    )
    return {"statement": statement, "delivery": delivery}


@router.get("/settings", response_model=LedgerSettingsOut)
def get_ledger_settings(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return accounting_service.get_settings(db)


@router.put("/settings", response_model=LedgerSettingsOut)
def update_ledger_settings(payload: LedgerSettingsUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*FINANCE))):
    settings = accounting_service.get_settings(db)
    updates = payload.model_dump(exclude_unset=True)
    for code_value in updates.values():
        if code_value and not db.query(Account).filter(Account.code == code_value).first():
            raise HTTPException(status_code=400, detail=f"No account exists with code '{code_value}'")
    for field, value in updates.items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings
