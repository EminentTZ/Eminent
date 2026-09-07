"""Double-entry bookkeeping engine for the transport system.

The chart of accounts seeded here (see ``app/core/coa_seed.py``) is a direct
mirror of the company's live NextAccounting general ledger, so operational
events recorded in this system (trips, invoices, payments, running costs,
workshop bills) post journal entries against the *same* account codes the
company's bookkeeper already reconciles against. Nothing here replaces the
books of record kept in NextAccounting -- it gives the operations system its
own consistent, auditable ledger using identical account numbers, so figures
can be compared side by side or migrated later without a remapping exercise.

Every posting goes through :func:`post_journal_entry`, which enforces that
debits equal credits before anything is written. Routers should never create
``JournalEntry``/``JournalLine`` rows directly.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from sqlalchemy.orm import joinedload

from app.core.coa_seed import COA_SEED
from app.models import Account, JournalEntry, JournalLine, LedgerSettings, Trip, Invoice, Payment, Expense, MaintenanceRecord, Client

AMOUNT_EPSILON = 0.01  # allow sub-cent floating point noise, nothing more


# ---------------------------------------------------------------------------
# Chart of accounts & settings bootstrap
# ---------------------------------------------------------------------------

def seed_chart_of_accounts(db: Session) -> None:
    """Idempotently load the official chart of accounts and default settings."""
    existing_codes = {code for (code,) in db.query(Account.code).all()}
    for code, name, statement_class, group, normal_balance in COA_SEED:
        if code in existing_codes:
            continue
        db.add(Account(
            code=code,
            name=name,
            statement_class=statement_class,
            account_group=group,
            normal_balance=normal_balance,
            is_active=True,
            is_system=True,
        ))
    if db.query(LedgerSettings).get(1) is None:
        db.add(LedgerSettings(id=1))
    db.commit()


def get_settings(db: Session) -> LedgerSettings:
    settings = db.query(LedgerSettings).get(1)
    if settings is None:
        settings = LedgerSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def get_account_by_code(db: Session, code: str) -> Account:
    account = db.query(Account).filter(Account.code == code).first()
    if not account:
        raise HTTPException(status_code=400, detail=f"Unknown ledger account code '{code}'. Check Accounting > Settings.")
    return account


# ---------------------------------------------------------------------------
# Journal posting engine
# ---------------------------------------------------------------------------

def _next_entry_number(entry: JournalEntry) -> str:
    return f"JE-{entry.id:06d}"


def post_journal_entry(
    db: Session,
    *,
    entry_date: date,
    memo: str,
    source_type: str,
    lines: list[dict],
    source_id: Optional[int] = None,
    created_by_id: Optional[int] = None,
) -> JournalEntry:
    """Create a balanced journal entry.

    ``lines`` is a list of dicts with keys: ``account_code`` (str),
    ``debit`` (float, default 0), ``credit`` (float, default 0),
    ``description`` (str, optional), ``trip_id`` / ``vehicle_id`` (optional
    cost-tracking dimensions). Zero-amount lines are dropped automatically so
    callers can pass optional components (e.g. a delay charge that may be 0)
    without extra branching.
    """
    clean_lines = [l for l in lines if round(float(l.get("debit", 0) or 0), 2) or round(float(l.get("credit", 0) or 0), 2)]
    if len(clean_lines) < 2:
        raise HTTPException(status_code=400, detail="A journal entry needs at least two non-zero lines.")

    total_debit = round(sum(float(l.get("debit", 0) or 0) for l in clean_lines), 2)
    total_credit = round(sum(float(l.get("credit", 0) or 0) for l in clean_lines), 2)
    if abs(total_debit - total_credit) > AMOUNT_EPSILON:
        raise HTTPException(
            status_code=400,
            detail=f"Journal entry does not balance: debits {total_debit:,.2f} vs credits {total_credit:,.2f}.",
        )

    entry = JournalEntry(
        entry_number="PENDING",
        entry_date=entry_date or date.today(),
        memo=memo,
        source_type=source_type,
        source_id=source_id,
        created_by_id=created_by_id,
    )
    db.add(entry)
    db.flush()  # assign entry.id
    entry.entry_number = _next_entry_number(entry)

    for line in clean_lines:
        account = get_account_by_code(db, line["account_code"])
        db.add(JournalLine(
            journal_entry_id=entry.id,
            account_id=account.id,
            debit=round(float(line.get("debit", 0) or 0), 2),
            credit=round(float(line.get("credit", 0) or 0), 2),
            description=line.get("description"),
            trip_id=line.get("trip_id"),
            vehicle_id=line.get("vehicle_id"),
        ))
    db.flush()
    return entry


def reverse_journal_entry(db: Session, original: JournalEntry, *, memo: Optional[str] = None, created_by_id: Optional[int] = None) -> JournalEntry:
    """Post the mirror image of an existing entry (a correction, never a delete)."""
    if original.reversed_entry_id:
        raise HTTPException(status_code=400, detail="This entry is already a reversal.")
    already_reversed = db.query(JournalEntry).filter(JournalEntry.reversed_entry_id == original.id).first()
    if already_reversed:
        raise HTTPException(status_code=400, detail=f"Entry {original.entry_number} was already reversed by {already_reversed.entry_number}.")

    lines = [
        {
            "account_code": line.account.code,
            "debit": line.credit,
            "credit": line.debit,
            "description": line.description,
            "trip_id": line.trip_id,
            "vehicle_id": line.vehicle_id,
        }
        for line in original.lines
    ]
    reversal = post_journal_entry(
        db,
        entry_date=date.today(),
        memo=memo or f"Reversal of {original.entry_number}: {original.memo or ''}".strip(),
        source_type=original.source_type,
        source_id=original.source_id,
        created_by_id=created_by_id,
        lines=lines,
    )
    reversal.reversed_entry_id = original.id
    db.flush()
    return reversal


def reverse_source_entry(db: Session, source_type: str, source_id: int, *, created_by_id: Optional[int] = None, reason: Optional[str] = None) -> Optional[JournalEntry]:
    """Reverse whatever journal entry a given operational record posted, if any.

    Used when an operational event is voided after the fact (e.g. a client
    rejects an invoice) so the ledger no longer reflects it, without ever
    deleting the original entry.
    """
    entry = db.query(JournalEntry).filter(JournalEntry.source_type == source_type, JournalEntry.source_id == source_id).first()
    if not entry:
        return None
    already_reversed = db.query(JournalEntry).filter(JournalEntry.reversed_entry_id == entry.id).first()
    if already_reversed:
        return already_reversed
    return reverse_journal_entry(db, entry, memo=reason, created_by_id=created_by_id)


# ---------------------------------------------------------------------------
# Expense / maintenance category -> GL account mapping
# ---------------------------------------------------------------------------

# Ordered (keyword, account code) pairs checked against the lower-cased
# expense_type / maintenance_type text. First match wins. These are cost
# accounts already in the seeded COA (5xxx trip cost-of-service accounts).
EXPENSE_ACCOUNT_KEYWORDS: list[tuple[str, str]] = [
    ("fuel", "5202"),                # Trip Fuel
    ("toll", "5101"),                 # Toll Gate
    ("border", "5100"),               # Boarder Charges
    ("boarder", "5100"),
    ("bypass", "5111"),               # Bypass
    ("peage", "5110"),                # Peages
    ("council", "5109"),              # Council
    ("load", "5001"),                 # Loading / Offloading Fee
    ("offload", "5001"),
    ("container", "5003"),            # Container fee
    ("yellow card", "5002"),          # Yellow Card
    ("demurrage", "5007"),            # Demurrage & Drop Off Charges
  # spelled both ways in the live COA:
    ("drop off", "5007"),
    ("delay", "5004"),                # Delay Charges
    ("dispatch", "5204"),             # Dispatch Allowance
    ("allowance", "5204"),
    ("transaction charge", "5205"),   # Trip Transaction Charges
    ("weight bridge", "6209"),
    ("weighbridge", "6209"),
    ("park", "6213"),                 # Parking Fee
    ("fine", "6206"),                 # Fines & Penalties
    ("penalt", "6206"),
    ("inspection", "6201"),           # Inspection fee
    ("covid", "5005"),
    ("exit", "5006"),
]
DEFAULT_TRIP_EXPENSE_KEYWORD_FALLBACK = None  # falls back to settings.default_trip_cogs_account_code


MAINTENANCE_ACCOUNT_KEYWORDS: list[tuple[str, str]] = [
    ("spare", "6351"),      # Motor Spare Part
    ("part", "6351"),
    ("oil", "6352"),        # Oil & Grease
    ("grease", "6352"),
    ("labour", "6353"),     # Motor Service Charge (Labour)
    ("labor", "6353"),
    ("service", "6353"),
    ("tyre", "6351"),
    ("tire", "6351"),
]


def resolve_category_account_code(description: str, keyword_map: list[tuple[str, str]], fallback_code: str) -> str:
    text = (description or "").strip().lower()
    for keyword, code in keyword_map:
        if keyword in text:
            return code
    return fallback_code


def resolve_payment_account_code(settings: LedgerSettings, payment_source: str, explicit_code: Optional[str] = None) -> str:
    if explicit_code:
        return explicit_code
    mapping = {
        "cash": settings.default_cash_account_code,
        "bank": settings.default_bank_account_code,
        "payable": settings.payable_account_code,
    }
    return mapping.get(payment_source, settings.payable_account_code)


PAYMENT_METHOD_ACCOUNT_HINTS = {
    "cash": "cash",
    "petty_cash": "cash",
    "bank_transfer": "bank",
    "cheque": "bank",
    "check": "bank",
    "mobile_money": "bank",
    "card": "bank",
}


# ---------------------------------------------------------------------------
# Auto-posting for operational events
# ---------------------------------------------------------------------------

def post_trip_expense(db: Session, expense: Expense, trip: Trip, *, payment_source: str = "payable", gl_account_code: Optional[str] = None, created_by_id: Optional[int] = None) -> JournalEntry:
    settings = get_settings(db)
    expense_account_code = gl_account_code or resolve_category_account_code(
        expense.expense_type, EXPENSE_ACCOUNT_KEYWORDS, settings.default_trip_cogs_account_code
    )
    payment_account_code = resolve_payment_account_code(settings, payment_source)
    memo = f"Trip {trip.trip_number} expense: {expense.expense_type}"
    return post_journal_entry(
        db,
        entry_date=expense.created_at.date() if expense.created_at else date.today(),
        memo=memo,
        source_type="trip_expense",
        source_id=expense.id,
        created_by_id=created_by_id,
        lines=[
            {"account_code": expense_account_code, "debit": expense.amount, "description": memo, "trip_id": trip.id, "vehicle_id": trip.tractor_id},
            {"account_code": payment_account_code, "credit": expense.amount, "description": f"Paid via {payment_source} for {memo}", "trip_id": trip.id},
        ],
    )


def post_maintenance_cost(db: Session, record: MaintenanceRecord, *, payment_source: str = "payable", gl_account_code: Optional[str] = None, created_by_id: Optional[int] = None) -> Optional[JournalEntry]:
    if not record.cost:
        return None
    settings = get_settings(db)
    maintenance_account_code = gl_account_code or resolve_category_account_code(
        record.maintenance_type, MAINTENANCE_ACCOUNT_KEYWORDS, settings.default_maintenance_account_code
    )
    payment_account_code = resolve_payment_account_code(settings, payment_source)
    memo = f"Maintenance on vehicle #{record.vehicle_id}: {record.maintenance_type}"
    return post_journal_entry(
        db,
        entry_date=record.date_in or date.today(),
        memo=memo,
        source_type="maintenance",
        source_id=record.id,
        created_by_id=created_by_id,
        lines=[
            {"account_code": maintenance_account_code, "debit": record.cost, "description": memo, "vehicle_id": record.vehicle_id},
            {"account_code": payment_account_code, "credit": record.cost, "description": f"Paid via {payment_source} for {memo}"},
        ],
    )


def post_invoice_issued(db: Session, invoice: Invoice, trip: Trip, *, created_by_id: Optional[int] = None) -> JournalEntry:
    settings = get_settings(db)
    # A staged invoice (e.g. a 70% advance) bills only a fraction of the
    # trip's total -- recognise revenue in that same proportion so partial
    # invoices don't overstate income before the balance is even billed.
    factor = (invoice.stage_percentage or 100.0) / 100.0
    recoverable_total = round(sum(exp.amount for exp in trip.expenses if exp.is_recoverable) * factor, 2)
    revenue_component = round(trip.agreed_revenue * factor, 2)
    delay_component = round((trip.delay_charge or 0.0) * factor, 2)
    stage_note = "" if invoice.stage == "full" else f" ({invoice.stage} {invoice.stage_percentage:.0f}%)"
    memo = f"Invoice {invoice.invoice_number}{stage_note} for trip {trip.trip_number}"

    credit_lines = [
        {"account_code": settings.revenue_account_code, "credit": revenue_component, "description": "Agreed freight revenue", "trip_id": trip.id},
    ]
    if delay_component:
        credit_lines.append({"account_code": settings.delay_income_account_code, "credit": delay_component, "description": "Delay / demurrage charge to client", "trip_id": trip.id})
    if recoverable_total:
        credit_lines.append({"account_code": settings.recovered_expense_income_code, "credit": recoverable_total, "description": "Recoverable trip expenses recharged to client", "trip_id": trip.id})

    # Guard against rounding drift between the invoice total and its components.
    credited_total = round(sum(l["credit"] for l in credit_lines), 2)
    drift = round(invoice.amount - credited_total, 2)
    if abs(drift) >= 0.01:
        credit_lines.append({"account_code": settings.recovered_expense_income_code, "credit": drift, "description": "Rounding adjustment", "trip_id": trip.id})

    lines = [
        {"account_code": settings.receivable_account_code, "debit": invoice.amount, "description": memo, "trip_id": trip.id},
        *credit_lines,
    ]
    return post_journal_entry(
        db,
        entry_date=invoice.issue_date or date.today(),
        memo=memo,
        source_type="trip_invoice",
        source_id=invoice.id,
        created_by_id=created_by_id,
        lines=lines,
    )


def post_payable_settlement(
    db: Session,
    *,
    source_type: str,
    source_id: int,
    amount: float,
    description: str,
    payment_account_code: Optional[str] = None,
    entry_date: Optional[date] = None,
    created_by_id: Optional[int] = None,
) -> JournalEntry:
    """Clear a previously-posted payable once it's actually paid.

    Expenses and maintenance costs recorded with payment_source="payable"
    post straight to Accounts Payable the moment they're recorded -- there
    was previously no way to record that the bill was later actually paid.
    This is that settlement leg: debit Accounts Payable, credit whichever
    cash/bank account the payment came from.
    """
    settings = get_settings(db)
    payable_code = settings.payable_account_code
    cash_code = payment_account_code or settings.default_bank_account_code
    memo = f"Settlement: {description}"
    return post_journal_entry(
        db,
        entry_date=entry_date or date.today(),
        memo=memo,
        source_type=f"{source_type}_settlement",
        source_id=source_id,
        created_by_id=created_by_id,
        lines=[
            {"account_code": payable_code, "debit": amount, "description": memo},
            {"account_code": cash_code, "credit": amount, "description": memo},
        ],
    )


def post_payment_received(db: Session, payment: Payment, invoice: Invoice, *, deposit_account_code: Optional[str] = None, created_by_id: Optional[int] = None) -> JournalEntry:
    settings = get_settings(db)
    hint = PAYMENT_METHOD_ACCOUNT_HINTS.get((payment.method or "").strip().lower(), "bank")
    deposit_code = deposit_account_code or resolve_payment_account_code(settings, hint)
    memo = f"Payment received for invoice {invoice.invoice_number}"
    return post_journal_entry(
        db,
        entry_date=payment.payment_date or date.today(),
        memo=memo,
        source_type="payment",
        source_id=payment.id,
        created_by_id=created_by_id,
        lines=[
            {"account_code": deposit_code, "debit": payment.amount, "description": memo, "trip_id": invoice.trip_id},
            {"account_code": settings.receivable_account_code, "credit": payment.amount, "description": memo, "trip_id": invoice.trip_id},
        ],
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _line_query(db: Session, start: Optional[date] = None, end: Optional[date] = None):
    query = db.query(JournalLine).join(JournalEntry)
    if start:
        query = query.filter(JournalEntry.entry_date >= start)
    if end:
        query = query.filter(JournalEntry.entry_date <= end)
    return query


def trial_balance(db: Session, as_of: Optional[date] = None) -> dict:
    totals = db.query(
        JournalLine.account_id,
        func.coalesce(func.sum(JournalLine.debit), 0.0),
        func.coalesce(func.sum(JournalLine.credit), 0.0),
    ).join(JournalEntry)
    if as_of:
        totals = totals.filter(JournalEntry.entry_date <= as_of)
    totals = totals.group_by(JournalLine.account_id).all()
    totals_by_account = {account_id: (debit, credit) for account_id, debit, credit in totals}

    rows = []
    total_debit_col = 0.0
    total_credit_col = 0.0
    for account in db.query(Account).order_by(Account.code).all():
        debit, credit = totals_by_account.get(account.id, (0.0, 0.0))
        net = round(debit - credit, 2)
        if abs(net) < AMOUNT_EPSILON:
            continue
        debit_col = net if net > 0 else 0.0
        credit_col = -net if net < 0 else 0.0
        total_debit_col += debit_col
        total_credit_col += credit_col
        rows.append({
            "code": account.code,
            "name": account.name,
            "statement_class": account.statement_class,
            "debit": round(debit_col, 2),
            "credit": round(credit_col, 2),
        })
    return {
        "as_of": as_of.isoformat() if as_of else None,
        "rows": rows,
        "total_debit": round(total_debit_col, 2),
        "total_credit": round(total_credit_col, 2),
        "balanced": abs(total_debit_col - total_credit_col) < AMOUNT_EPSILON,
    }


def _net_balance(debit: float, credit: float, normal_balance: str) -> float:
    return debit - credit if normal_balance == "debit" else credit - debit


def profit_and_loss(db: Session, start: Optional[date] = None, end: Optional[date] = None) -> dict:
    totals = _line_query(db, start, end).with_entities(
        JournalLine.account_id,
        func.coalesce(func.sum(JournalLine.debit), 0.0),
        func.coalesce(func.sum(JournalLine.credit), 0.0),
    ).group_by(JournalLine.account_id).all()
    totals_by_account = {account_id: (debit, credit) for account_id, debit, credit in totals}

    sections: dict[str, list[dict]] = {"income": [], "cogs": [], "expense": []}
    section_totals = {"income": 0.0, "cogs": 0.0, "expense": 0.0}
    for account in db.query(Account).filter(Account.statement_class.in_(["income", "cogs", "expense"])).order_by(Account.code).all():
        debit, credit = totals_by_account.get(account.id, (0.0, 0.0))
        amount = round(_net_balance(debit, credit, account.normal_balance), 2)
        if abs(amount) < AMOUNT_EPSILON:
            continue
        sections[account.statement_class].append({"code": account.code, "name": account.name, "amount": amount})
        section_totals[account.statement_class] += amount

    total_income = round(section_totals["income"], 2)
    total_cogs = round(section_totals["cogs"], 2)
    total_expense = round(section_totals["expense"], 2)
    gross_profit = round(total_income - total_cogs, 2)
    net_profit = round(gross_profit - total_expense, 2)

    return {
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "income": sections["income"],
        "cogs": sections["cogs"],
        "expense": sections["expense"],
        "total_income": total_income,
        "total_cogs": total_cogs,
        "gross_profit": gross_profit,
        "total_expense": total_expense,
        "net_profit": net_profit,
    }


def balance_sheet(db: Session, as_of: Optional[date] = None) -> dict:
    totals = db.query(
        JournalLine.account_id,
        func.coalesce(func.sum(JournalLine.debit), 0.0),
        func.coalesce(func.sum(JournalLine.credit), 0.0),
    ).join(JournalEntry)
    if as_of:
        totals = totals.filter(JournalEntry.entry_date <= as_of)
    totals = totals.group_by(JournalLine.account_id).all()
    totals_by_account = {account_id: (debit, credit) for account_id, debit, credit in totals}

    sections: dict[str, list[dict]] = {"asset": [], "liability": [], "equity": []}
    section_totals = {"asset": 0.0, "liability": 0.0, "equity": 0.0}
    for account in db.query(Account).filter(Account.statement_class.in_(["asset", "liability", "equity"])).order_by(Account.code).all():
        debit, credit = totals_by_account.get(account.id, (0.0, 0.0))
        amount = round(_net_balance(debit, credit, account.normal_balance), 2)
        if abs(amount) < AMOUNT_EPSILON:
            continue
        sections[account.statement_class].append({"code": account.code, "name": account.name, "amount": amount})
        section_totals[account.statement_class] += amount

    # Retained earnings only reflects prior closing entries. Until a formal
    # period-close posts current profit into it, show current profit as its
    # own equity line so the statement still balances and stays honest about
    # what has (and hasn't) been closed out.
    pl = profit_and_loss(db, start=None, end=as_of)
    current_earnings = pl["net_profit"]
    if abs(current_earnings) >= AMOUNT_EPSILON:
        sections["equity"].append({"code": "-", "name": "Net Profit (current, not yet closed to Retained Earnings)", "amount": current_earnings})
        section_totals["equity"] += current_earnings

    total_assets = round(section_totals["asset"], 2)
    total_liabilities = round(section_totals["liability"], 2)
    total_equity = round(section_totals["equity"], 2)

    return {
        "as_of": as_of.isoformat() if as_of else None,
        "asset": sections["asset"],
        "liability": sections["liability"],
        "equity": sections["equity"],
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "balanced": abs(total_assets - (total_liabilities + total_equity)) < 0.02,
    }


def net_account_balance(db: Session, code: str, as_of: Optional[date] = None) -> float:
    """Convenience helper for dashboards: net balance of a single account."""
    account = db.query(Account).filter(Account.code == code).first()
    if not account:
        return 0.0
    query = db.query(
        func.coalesce(func.sum(JournalLine.debit), 0.0),
        func.coalesce(func.sum(JournalLine.credit), 0.0),
    ).join(JournalEntry).filter(JournalLine.account_id == account.id)
    if as_of:
        query = query.filter(JournalEntry.entry_date <= as_of)
    debit, credit = query.first()
    return round(_net_balance(debit or 0.0, credit or 0.0, account.normal_balance), 2)


def group_balance(db: Session, statement_class: str, as_of: Optional[date] = None) -> float:
    """Convenience helper for dashboards: net balance across a whole class (e.g. all 'asset' accounts of type Bank/Cash)."""
    accounts = db.query(Account).filter(Account.statement_class == statement_class).all()
    return round(sum(net_account_balance(db, a.code, as_of=as_of) for a in accounts), 2)


def account_group_balance(db: Session, account_group: str, as_of: Optional[date] = None) -> float:
    """Net balance across every account sharing an ``account_group`` label (e.g. 'Bank', 'Cash on Hand')."""
    accounts = db.query(Account).filter(Account.account_group == account_group).all()
    return round(sum(net_account_balance(db, a.code, as_of=as_of) for a in accounts), 2)


def account_ledger(db: Session, account: Account, start: Optional[date] = None, end: Optional[date] = None) -> dict:
    opening_balance = 0.0
    if start:
        opening_debit, opening_credit = db.query(
            func.coalesce(func.sum(JournalLine.debit), 0.0),
            func.coalesce(func.sum(JournalLine.credit), 0.0),
        ).join(JournalEntry).filter(JournalLine.account_id == account.id, JournalEntry.entry_date < start).first()
        opening_balance = _net_balance(opening_debit or 0.0, opening_credit or 0.0, account.normal_balance)

    query = db.query(JournalLine, JournalEntry).join(JournalEntry).filter(JournalLine.account_id == account.id)
    if start:
        query = query.filter(JournalEntry.entry_date >= start)
    if end:
        query = query.filter(JournalEntry.entry_date <= end)
    query = query.order_by(JournalEntry.entry_date, JournalEntry.id)

    running = round(opening_balance, 2)
    rows = []
    for line, entry in query.all():
        delta = line.debit - line.credit if account.normal_balance == "debit" else line.credit - line.debit
        running = round(running + delta, 2)
        rows.append({
            "entry_number": entry.entry_number,
            "entry_date": entry.entry_date.isoformat(),
            "memo": entry.memo,
            "source_type": entry.source_type,
            "description": line.description,
            "debit": line.debit,
            "credit": line.credit,
            "running_balance": running,
        })

    return {
        "account": {"code": account.code, "name": account.name, "statement_class": account.statement_class, "normal_balance": account.normal_balance},
        "opening_balance": round(opening_balance, 2),
        "closing_balance": running,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Aging reports & client statements
# ---------------------------------------------------------------------------
# These read the operational Invoice/Expense/Payment/MaintenanceRecord rows
# directly rather than the journal -- "who owes us, and how overdue" and
# "who do we owe" are subledger questions, not general-ledger ones, and the
# journal doesn't retain a per-invoice/per-bill running balance.

AR_AGING_LABELS = ["Not Yet Due", "1-30 Days", "31-60 Days", "61-90 Days", "90+ Days"]
AP_AGING_LABELS = ["0-30 Days", "31-60 Days", "61-90 Days", "90+ Days"]


def _ar_bucket(days_overdue: int) -> str:
    if days_overdue < 0:
        return "Not Yet Due"
    if days_overdue <= 30:
        return "1-30 Days"
    if days_overdue <= 60:
        return "31-60 Days"
    if days_overdue <= 90:
        return "61-90 Days"
    return "90+ Days"


def _ap_bucket(age_days: int) -> str:
    if age_days <= 30:
        return "0-30 Days"
    if age_days <= 60:
        return "31-60 Days"
    if age_days <= 90:
        return "61-90 Days"
    return "90+ Days"


def ar_aging(db: Session, as_of: Optional[date] = None) -> dict:
    """Outstanding customer invoices grouped by client and days overdue.

    An invoice with no due_date is treated as "not yet due" rather than
    guessed at -- it shouldn't silently drop into an aging bucket.
    """
    as_of = as_of or date.today()
    invoices = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments), joinedload(Invoice.client))
        .filter(Invoice.status.in_(["issued", "partial"]))
        .all()
    )
    by_client: dict[int, dict] = {}
    bucket_totals = {label: 0.0 for label in AR_AGING_LABELS}
    for inv in invoices:
        paid = sum(p.amount for p in inv.payments)
        balance = round(inv.amount - paid, 2)
        if balance <= AMOUNT_EPSILON:
            continue
        days_overdue = (as_of - inv.due_date).days if inv.due_date else -1
        bucket = _ar_bucket(days_overdue)
        client_name = inv.client.name if inv.client else str(inv.client_id)
        entry = by_client.setdefault(inv.client_id, {
            "client_id": inv.client_id, "client_name": client_name,
            "buckets": {label: 0.0 for label in AR_AGING_LABELS}, "total": 0.0,
        })
        entry["buckets"][bucket] += balance
        entry["total"] += balance
        bucket_totals[bucket] += balance

    rows = sorted(by_client.values(), key=lambda r: -r["total"])
    for row in rows:
        row["buckets"] = {k: round(v, 2) for k, v in row["buckets"].items()}
        row["total"] = round(row["total"], 2)
    return {
        "as_of": as_of.isoformat(),
        "bucket_labels": AR_AGING_LABELS,
        "rows": rows,
        "bucket_totals": {k: round(v, 2) for k, v in bucket_totals.items()},
        "grand_total": round(sum(bucket_totals.values()), 2),
    }


def ap_aging(db: Session, as_of: Optional[date] = None) -> dict:
    """Outstanding (unsettled, payment_source="payable") bills grouped by vendor and age.

    Combines trip expenses and maintenance costs -- both post to Accounts
    Payable the same way -- into one payables view. Items with no vendor
    attached are grouped as "Unassigned" rather than dropped.
    """
    as_of = as_of or date.today()
    items = []
    for exp in db.query(Expense).options(joinedload(Expense.vendor)).filter(Expense.payment_source == "payable", Expense.settled.is_(False)).all():
        items.append({
            "source_type": "trip_expense", "source_id": exp.id,
            "vendor_id": exp.vendor_id, "vendor_name": exp.vendor.name if exp.vendor else "Unassigned",
            "description": exp.expense_type, "amount": exp.amount,
            "date": exp.created_at.date() if exp.created_at else as_of,
        })
    for m in db.query(MaintenanceRecord).options(joinedload(MaintenanceRecord.vendor)).filter(MaintenanceRecord.payment_source == "payable", MaintenanceRecord.settled.is_(False)).all():
        items.append({
            "source_type": "maintenance", "source_id": m.id,
            "vendor_id": m.vendor_id, "vendor_name": m.vendor.name if m.vendor else "Unassigned",
            "description": m.maintenance_type, "amount": m.cost or 0.0,
            "date": m.date_in or as_of,
        })

    by_vendor: dict[str, dict] = {}
    bucket_totals = {label: 0.0 for label in AP_AGING_LABELS}
    for item in items:
        if not item["amount"]:
            continue
        age_days = max((as_of - item["date"]).days, 0)
        bucket = _ap_bucket(age_days)
        key = str(item["vendor_id"]) if item["vendor_id"] else f"unassigned:{item['vendor_name']}"
        entry = by_vendor.setdefault(key, {
            "vendor_id": item["vendor_id"], "vendor_name": item["vendor_name"], "items": [],
            "buckets": {label: 0.0 for label in AP_AGING_LABELS}, "total": 0.0,
        })
        entry["items"].append({
            "source_type": item["source_type"], "source_id": item["source_id"],
            "description": item["description"], "amount": round(item["amount"], 2),
            "date": item["date"].isoformat(), "age_days": age_days,
        })
        entry["buckets"][bucket] += item["amount"]
        entry["total"] += item["amount"]
        bucket_totals[bucket] += item["amount"]

    rows = sorted(by_vendor.values(), key=lambda r: -r["total"])
    for row in rows:
        row["buckets"] = {k: round(v, 2) for k, v in row["buckets"].items()}
        row["total"] = round(row["total"], 2)
    return {
        "as_of": as_of.isoformat(),
        "bucket_labels": AP_AGING_LABELS,
        "rows": rows,
        "bucket_totals": {k: round(v, 2) for k, v in bucket_totals.items()},
        "grand_total": round(sum(bucket_totals.values()), 2),
    }


def client_statement(db: Session, client: Client, as_of: Optional[date] = None) -> dict:
    """Every non-rejected invoice issued to a client up to as_of, with amount/paid/balance."""
    as_of = as_of or date.today()
    invoices = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments))
        .filter(Invoice.client_id == client.id, Invoice.status != "rejected", Invoice.issue_date <= as_of)
        .order_by(Invoice.issue_date)
        .all()
    )
    rows = []
    total_outstanding = 0.0
    for inv in invoices:
        paid = round(sum(p.amount for p in inv.payments if p.payment_date <= as_of), 2)
        balance = round(inv.amount - paid, 2)
        rows.append({
            "invoice_number": inv.invoice_number,
            "issue_date": inv.issue_date.isoformat() if inv.issue_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "amount": inv.amount,
            "paid": paid,
            "balance": balance,
            "status": inv.status,
        })
        total_outstanding += balance
    return {
        "client_id": client.id,
        "client_name": client.name,
        "as_of": as_of.isoformat(),
        "invoices": rows,
        "total_outstanding": round(total_outstanding, 2),
    }


def render_statement_text(statement: dict) -> str:
    """Plain-text rendering of client_statement(), used for the emailed statement body."""
    lines = [f"Statement of Accounts as of {statement['as_of']}", ""]
    if not statement["invoices"]:
        lines.append("No invoices on file.")
    else:
        lines.append(f"{'Invoice':<20}{'Issue Date':<14}{'Due Date':<14}{'Amount':>14}{'Paid':>14}{'Balance':>14}")
        for row in statement["invoices"]:
            lines.append(
                f"{row['invoice_number']:<20}{row['issue_date'] or '-':<14}{row['due_date'] or '-':<14}"
                f"{row['amount']:>14,.2f}{row['paid']:>14,.2f}{row['balance']:>14,.2f}"
            )
    lines += ["", f"Total Outstanding: {statement['total_outstanding']:,.2f}"]
    return "\n".join(lines)
