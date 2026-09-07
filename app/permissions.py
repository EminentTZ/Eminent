"""Role-based access control.

Four user groups, matching how a small transport company is actually
organized. Every authenticated user can still *read* virtually everything
(list/get endpoints stay on plain `get_current_user`) -- visibility isn't
usually the risk in a system like this, the risk is who can *change* things.
So `require_roles(...)` is only applied to endpoints that create, update,
settle, post, or delete something. See README.md for the full narrative.

    admin       Full access, including user management and every module
                below. The only role that can create/edit/deactivate other
                users or change someone's role.
    accountant  Owns the books: chart of accounts, journal entries and
                reversals, ledger settings, all financial reports, recording
                customer payments, and settling payable bills (expenses /
                maintenance). Can generate and reject invoices. Can view
                (but not edit) fleet/driver/client/trip master data.
    operations  Runs dispatch: clients, fleet, drivers, routes, vendors,
                assignments, bookings, trips (create/status/events/expenses/
                POD), and maintenance jobs (create/complete). Can generate
                and reject invoices, since that's the natural last step of
                closing out a trip. Cannot record payments, settle payable
                bills, or touch the ledger/chart of accounts/journal.
    viewer      Read-only across the whole system. No create/update/settle/
                post action is available. Useful for an owner, auditor, or
                manager who wants visibility without operational risk.
"""

from fastapi import Depends, HTTPException, status

from app.deps import get_current_user
from app.models import User

ROLE_ADMIN = "admin"
ROLE_ACCOUNTANT = "accountant"
ROLE_OPERATIONS = "operations"
ROLE_VIEWER = "viewer"
ALL_ROLES = (ROLE_ADMIN, ROLE_ACCOUNTANT, ROLE_OPERATIONS, ROLE_VIEWER)

# Convenience role bundles used across the routers.
ADMIN_ONLY = (ROLE_ADMIN,)
FINANCE = (ROLE_ADMIN, ROLE_ACCOUNTANT)
OPS = (ROLE_ADMIN, ROLE_OPERATIONS)
OPS_FINANCE = (ROLE_ADMIN, ROLE_OPERATIONS, ROLE_ACCOUNTANT)


def require_roles(*roles: str):
    """FastAPI dependency factory -- drop-in replacement for
    `Depends(get_current_user)` on any endpoint that should be restricted to
    specific roles. Still returns the User object, so it works anywhere the
    plain dependency did (including endpoints that use the user for
    `created_by_id` tracking)."""
    allowed = set(roles)

    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of the following roles: {', '.join(sorted(allowed))}.",
            )
        return current_user

    return _check
