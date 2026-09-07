from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel
from .common import ORMBase


class AccountCreate(BaseModel):
    code: str
    name: str
    statement_class: str  # asset, liability, equity, income, cogs, expense
    account_group: Optional[str] = None
    normal_balance: str  # debit, credit
    parent_code: Optional[str] = None


class AccountOut(ORMBase):
    id: int
    code: str
    name: str
    statement_class: str
    account_group: Optional[str] = None
    normal_balance: str
    is_active: bool
    is_system: bool


class JournalLineIn(BaseModel):
    account_code: str
    debit: float = 0.0
    credit: float = 0.0
    description: Optional[str] = None
    trip_id: Optional[int] = None
    vehicle_id: Optional[int] = None


class JournalLineOut(ORMBase):
    id: int
    account_id: int
    account_code: str
    account_name: str
    debit: float
    credit: float
    description: Optional[str] = None
    trip_id: Optional[int] = None
    vehicle_id: Optional[int] = None


class JournalEntryCreate(BaseModel):
    entry_date: Optional[date] = None
    memo: str
    lines: List[JournalLineIn]


class JournalEntryOut(ORMBase):
    id: int
    entry_number: str
    entry_date: date
    memo: Optional[str] = None
    source_type: str
    source_id: Optional[int] = None
    created_at: datetime
    reversed_entry_id: Optional[int] = None
    lines: List[JournalLineOut] = []


class LedgerSettingsOut(ORMBase):
    default_cash_account_code: str
    default_bank_account_code: str
    receivable_account_code: str
    payable_account_code: str
    revenue_account_code: str
    delay_income_account_code: str
    recovered_expense_income_code: str
    default_trip_cogs_account_code: str
    default_maintenance_account_code: str
    default_expense_account_code: str
    retained_earnings_account_code: str


class LedgerSettingsUpdate(BaseModel):
    default_cash_account_code: Optional[str] = None
    default_bank_account_code: Optional[str] = None
    receivable_account_code: Optional[str] = None
    payable_account_code: Optional[str] = None
    revenue_account_code: Optional[str] = None
    delay_income_account_code: Optional[str] = None
    recovered_expense_income_code: Optional[str] = None
    default_trip_cogs_account_code: Optional[str] = None
    default_maintenance_account_code: Optional[str] = None
    default_expense_account_code: Optional[str] = None
    retained_earnings_account_code: Optional[str] = None
