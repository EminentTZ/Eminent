# Transportation Management System MVP

This is a developer-ready MVP backend for a transportation and logistics company.
It covers key modules needed to start system development:

- Authentication, users, and role-based access control (admin / accountant / operations / viewer)
- Clients
- Vehicles
- Drivers
- Routes, with predetermined milestones, time goals, fuel, and mileage budgets
- Trips and trip events, with planned-vs-actual timing, fuel, and mileage tracking
- Expenses
- Invoices
- Payments
- Maintenance records
- Full double-entry accounting (chart of accounts, journal, ledger, financial reports)
- Dashboard metrics

## Tech stack

- FastAPI
- SQLAlchemy
- SQLite (easy to replace with PostgreSQL)

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:
- API: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

## Quick start on this Windows machine

From the project folder, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

This copies the app to a local runtime folder and starts the API from there, which avoids SQLite issues in the OneDrive-backed workspace.

## Default login

Use the seeded admin account:

- username: `admin`
- password: `admin123`

See [User roles and authorization](#user-roles-and-authorization) below for what each
account type can do, and how to create accountant/operations/viewer accounts alongside it.

## Main workflows included

1. Create client, driver, vehicle, and route master data.
2. Create a trip.
3. Add trip events and expenses.
4. Complete the trip.
5. Generate invoice from the trip.
6. Record payment.
7. Review dashboard and profitability.

## Accounting module

The system now includes a full double-entry bookkeeping engine layered under the existing
operational workflows, rather than a separate bolt-on. Every trip expense, maintenance cost,
invoice, and payment automatically posts a balanced journal entry behind the scenes — the
operator never has to touch a debit/credit form for day-to-day work, but the books stay
audit-ready at all times.

**Chart of accounts.** Seeded with 152 accounts (`app/core/coa_seed.py`) mirroring the
company's live general ledger structure, grouped into asset, liability, equity, income, COGS,
and expense classes, with finer groupings (e.g. Bank, Cash on Hand, Accounts Receivable) used
to drive dashboard rollups. Using the same account codes here as in the company's main
accounting system means the two stay reconcilable — a trip expense coded to "Fuel" in this
system lands on the same GL account an accountant would use when reviewing the books
elsewhere.

**Automatic posting.** `app/services/accounting.py` is the single choke point
(`post_journal_entry`) that enforces debit = credit on every entry. Trip expenses and
maintenance costs auto-map to a GL account by keyword matching on their description (with a
manual override available per transaction), and resolve their payment side — cash, bank, or
accounts payable — from configurable defaults in **Settings → Ledger Settings**. Nothing is
ever deleted and reposted: corrections are made by reversing the original entry
(`reverse_journal_entry`) and, where relevant, posting a new one, so the audit trail is
never broken.

**Staged invoicing.** Trips can be invoiced in stages (advance / balance / final / full)
instead of one lump sum, with revenue recognized proportionally as each stage is issued. The
system tracks cumulative percentage billed per trip so it's not possible to over-invoice past
100%.

**Client-specific invoice numbering.** Each client can have its own invoice number format
(e.g. `ACME/{yy}/{mm}/{seq:04d}`) to match the numbering convention their own accounts-payable
team expects; clients without a custom format fall back to a simple house default
(`INV-{trip_number}`). Supported placeholders: `{seq}`, `{yy}`, `{yyyy}`, `{mm}`, `{stage}`,
`{trip}`, `{client}`.

**Invoice rejection.** If a client's AP team bounces an invoice back (wrong reference,
weight mismatch, etc.), it can be marked rejected with a reason and the client's ticket
number. This reverses the original posting automatically rather than deleting the invoice,
so the rejected invoice and its reversal both remain visible in the journal.

**Batch remittance.** Clients that pay several invoices in one bank transfer can be recorded
as a single remittance covering multiple invoices at once, sharing one reference number,
with each invoice's payment posted and reconciled individually underneath.

**Financial reports.** Trial balance, profit & loss, and balance sheet reports are generated
live from the journal (`GET /accounting/reports/...`) and are always in balance by
construction — there's no separate "closing the books" step that can drift out of sync with
operations.

**UI.** Three new sections were added to the app: **Chart of Accounts** (browse accounts and
drill into any account's ledger), **Journal** (view/post/reverse entries), and **Financial
Reports** (run the three reports on demand). Existing forms (trip expenses, maintenance,
invoices, payments) gained the small number of extra fields (payment source, GL account
override, invoice stage, etc.) needed to feed the ledger, without changing how those
workflows are used day to day.

## Customer needs incorporated into the design

A review of real order documents, loading orders, and invoice correspondence surfaced a
handful of recurring customer requirements that the original MVP didn't account for. These
are now built into the schema and workflows described above, in general form (no customer
names or account details are stored anywhere in this codebase):

- Several customers pay in stages tied to shipment milestones (e.g. an advance on booking,
  a balance on delivery) rather than a single invoice — handled by staged invoicing.
- Corporate/broker customers each enforce their own invoice numbering convention on
  suppliers, rather than accepting the supplier's own sequence — handled by per-client
  invoice number formats.
- Freight is frequently billed per ton of cargo carried, with the rate varying by trip
  direction (e.g. a lower rate on a backload/return leg) — the `Trip` model now records
  `cargo_weight_tons`, `rate_per_ton`, `rate_type`, and an `is_backload` flag so this can be
  captured and, going forward, used to derive billed amounts automatically.
- Some customers use a different name for the document that authorizes a shipment
  (e.g. "Loading Order" vs. "Booking Confirmation") — clients now have a configurable
  `document_label`.
- Invoices do sometimes get bounced back by a customer's AP team for correction — handled by
  the invoice rejection/reversal workflow above.
- Customers that run many shipments a month often settle several invoices in one payment —
  handled by batch remittance.

### Recommended future enhancements (not built in this pass)

A few patterns showed up in correspondence but were deliberately left out of this MVP pass,
either because they need more product decisions first or fell outside the current scope:

- **Vendor/customer compliance-document tracking** — some counterparties require proof of
  insurance, licenses, or other compliance documents to be on file and periodically renewed.
  A generic document-tracker (upload, expiry date, status) would suit this well as a follow-up
  module, alongside the general "document upload support" item already noted below.
- **Multi-rate rate tables** — rather than a single `rate_per_ton`/`rate_type` per trip,
  some lanes are quoted with several simultaneous rate types (e.g. one-way, round-trip, and
  return/backload rates) that a dispatcher chooses between per trip. A dedicated rate-table
  entity keyed by route + cargo type would generalize this cleanly.
- **Automatic rate-based invoicing** — once rate tables exist, trip revenue could be derived
  automatically from `cargo_weight_tons × rate_per_ton` rather than the operator entering
  `agreed_revenue` manually.

## Fleet, driver, trip, and client management fixes

A follow-up review of the master-data and dispatch workflows (clients, vehicles, drivers,
routes, trips, maintenance) surfaced one real bug and several structural gaps, all now fixed:

**Tractors could be double-booked.** Dispatching a new trip only checked that the tractor
wasn't `maintenance` or `grounded` — it never checked for `assigned` (the status a tractor
gets the moment it's put on a trip), so the same tractor could end up on two simultaneous
trips. `create_trip` now also blocks any tractor that already has another active trip.

**Trips had no cancellation path.** Status could move to `in_transit` or `completed`, but not
`cancelled` — an aborted trip left its tractor and driver stuck at "assigned"/"unavailable"
forever. `PATCH /operations/trips/{id}/status` now accepts `cancelled` (only before any
expenses or invoices exist against the trip) and releases the tractor and driver back to the
pool, the same way completion does. A trip that has already reached `completed` or
`cancelled` can no longer be silently rewound to an earlier status.

**Nothing could be edited after creation.** Clients, vehicles, drivers, and routes each had a
create endpoint and a list endpoint and nothing else — fixing a typo in a registration number
or a client's contact person meant editing the database directly. All four now have a `PUT`
edit endpoint (and matching edit forms in the UI — click **Edit** on any register row, make
changes, and **Update**; **Cancel Edit** returns the form to create mode). Vehicle and driver
`status` is deliberately left out of the generic edit — those transitions go through the
dedicated workflows below so an unrelated edit can never silently reset them.

**Dead fields, now wired up:**
- `Client.is_active` previously did nothing — a "deactivated" client could still be booked.
  Clients can now be deactivated/reactivated (`PATCH /master/clients/{id}/deactivate` |
  `/reactivate`), and booking/trip creation now reject a deactivated client.
- `Client.credit_days` was captured at onboarding but never used. Invoice due dates now
  default to `issue date + credit_days` when a due date isn't explicitly supplied.
- Vehicle status `"grounded"` was checked for in two places but nothing could ever set it.
  `PATCH /master/vehicles/{id}/ground` and `/reinstate` now make that state reachable, for
  taking a truck out of service manually (accident, compliance hold) outside the maintenance
  workflow.
- Opening a maintenance record correctly flipped a vehicle to `status = "maintenance"`, but
  there was no way to close the job and bring the vehicle back into service.
  `PATCH /operations/maintenance/{id}/complete` now does both.

**Compliance documents are now surfaced.** Insurance, road license, and C28 expiry (vehicles)
and license expiry (drivers) were captured but never checked anywhere — a vehicle with lapsed
insurance could be dispatched with no warning. The dashboard now shows a Compliance Alerts
panel (`GET /dashboard/compliance-alerts`) listing anything expired or expiring within 30
days, and the same status is shown as a badge next to each vehicle/driver in their registers.

## New features: email automation, proof of delivery, vendor/AP subledger, aging reports

A round of proactive feature proposals (not bug fixes) was reviewed and approved for
build. All six are implemented end-to-end (backend, UI, and tests):

**Automated invoice email delivery.** `POST /operations/trips/{id}/invoice` now emails the
new invoice to the client's `Invoice Email` (falling back to `Billing Email`) immediately
after posting it to the ledger. Delivery status, error, and timestamp are stored on the
invoice itself (`invoice_email_status/_error/_sent_at`) and shown as an **Email** column on
the Invoices page, the same pattern already used for booking emails.

**Client statement of accounts.** `GET /accounting/reports/client-statement/{client_id}`
lists every non-rejected invoice issued to a client with its amount, amount paid, and
running balance, and `POST /accounting/reports/client-statement/{client_id}/send` emails a
plain-text rendering of it to the client's `Statement of Accounts Email` (falling back to
`Billing Email`, then `Invoice Email`). Both are available from the new **Client Statement
of Accounts** panel on the Financial Reports page: pick a client, **View**, then **Send
Statement**.

**Compliance alerts digest email.** The existing Compliance Alerts panel on the dashboard
only helped if someone opened it. `POST /dashboard/compliance-alerts/send-digest` emails the
same alert list to every active admin user with an email on file; the dashboard panel now has
an **Email Digest to Admins** button that triggers it on demand. Wiring this to a daily
schedule needs a job runner (cron/celery) at deploy time — this endpoint is the send itself,
ready to be called by one.

**Proof of Delivery (POD) capture.** Trips gained `pod_document_path`, `pod_notes`, and
`pod_captured_at`. `POST /operations/trips/{id}/pod` (multipart: optional file + notes)
stamps the capture time even if only notes are provided. The Trip Workspace has a
**Proof of Delivery** card next to Add Expense, and generating an invoice for a trip with no
POD captured now shows a confirming warning ("no proof of delivery has been captured...")
instead of silently proceeding — it's a soft warning, not a hard block, since some trips are
invoiced before POD paperwork arrives back from the client.

**Vendor entity, Accounts Payable settlement, and AP aging.** Previously `payment_source =
"payable"` on an expense or maintenance bill only meant "which GL bucket to post to" — there
was no concept of a specific supplier, and no way to later mark the bill as paid. This is now
a real subledger:
- A new `Vendor` master-data entity (name, contact, phone, email, TIN, address,
  active/inactive) with full CRUD at `/master/vendors`, and a **Vendors** page in the UI.
- Trip expenses and maintenance records can optionally carry a `vendor_id`, validated against
  the vendor table (`Add Expense` and the Maintenance form now have a **Vendor** selector).
- `PATCH /operations/expenses/{id}/settle` and `/operations/maintenance/{id}/settle` post a
  real settlement journal entry (Debit Accounts Payable / Credit cash-or-bank) and flip
  `settled = true` — this is the *only* way an on-account bill is marked paid. Settling an
  already-settled or non-payable-sourced bill is rejected (400). **Settle** buttons appear
  next to outstanding on-account expenses (Trip Workspace) and maintenance jobs.
- `GET /accounting/reports/ap-aging` groups every unsettled payable bill by vendor and age
  (0-30 / 31-60 / 61-90 / 90+ days), shown on the Financial Reports page.

**Accounts receivable aging.** `GET /accounting/reports/ar-aging` groups every outstanding
invoice balance by client and days overdue (Not Yet Due / 1-30 / 31-60 / 61-90 / 90+ days,
using the invoice's `due_date`), shown alongside AP aging on the Financial Reports page.

These are intentionally scoped as the "ready to build now" items from a longer list of
proposals; a full audit log, a driver-facing mobile app, and full multi-currency support
remain bigger-ticket items for a separate discussion.

## User roles and authorization

Every account belongs to exactly one of four user groups, and `get_current_user()` re-reads
that role from the database on every request (not from the JWT payload) — a role change by
an admin takes effect on the user's very next API call, no re-login required. As a design
principle, **reads stay open to every authenticated role** (visibility is not the risk in
this system); only mutating endpoints (the ones that create, change, or post something) are
role-gated. The four groups:

- **admin** — full access to everything, including user management. Only an admin can create
  or edit other users, change roles, deactivate/reactivate accounts, or reset someone's
  password. `GET /master/users` (the list of who has an account and what role they hold) is
  admin-only even to read.
- **accountant** — owns the books: chart of accounts, journal entries and reversals, ledger
  settings, all financial reports, recording payments, and settling payable bills (expense
  and maintenance settlement). Can also generate or reject invoices. Read-only on fleet,
  driver, client, and trip master data.
- **operations** — runs dispatch: clients, fleet, drivers, routes and route milestones,
  vendors, equipment assignments, bookings, trips (create, status changes, events, expenses,
  proof of delivery, milestone recording, fuel/mileage), and maintenance (create/complete).
  Can also generate or reject invoices, since that's the natural end of the dispatch
  workflow. Cannot record payments, settle payable bills, or touch the ledger, chart of
  accounts, or journal.
- **viewer** — read-only across the entire system. No create, update, settle, or post action
  is available anywhere, but every report, register, and ledger is visible.

A 403 response from any mutating endpoint includes which roles are allowed, e.g.
`"This action requires one of the following roles: accountant, admin."` The frontend hides
nav items, forms, and action buttons a role can't use (including blocking direct URL-hash
navigation to a restricted page like `#users`), but that's a UX convenience only — the actual
security boundary is enforced server-side by `app/permissions.py`'s `require_roles(...)`
dependency on every mutating router function.

**Managing users** (admin only, from the **Users** page or directly against the API):

- `POST /master/users` — create a user (`username`, `password`, `full_name`, `email`,
  `role`).
- `PUT /master/users/{id}` — edit `full_name`, `email`, or `role`. An admin cannot demote
  their own account away from `admin` this way (400) — ask another admin to do it, so nobody
  can accidentally lock every admin out.
- `PATCH /master/users/{id}/deactivate` / `.../reactivate` — an admin cannot deactivate their
  own account (400), for the same reason.
- `PATCH /master/users/{id}/reset-password` — admin-set a new password without knowing the
  old one (handing off/forgotten-password case).
- `POST /auth/change-password` — self-service, any signed-in user, requires the current
  password. Available from the **My Account** card in the sidebar.
- `GET /auth/me` — returns the signed-in user's own profile and role; this is what the
  frontend uses to decide what to show.

## Route module: predetermined milestones, fuel, mileage, and end-to-end timing

Routes now carry a planning template that every trip dispatched on them inherits, plus a way
to record what actually happened against that plan:

- **Standard fuel and mileage.** A route can have a `standard_fuel_liters` and
  `standard_driver_mileage_km` budget (Route Entry form, or `RouteCreate`/`RouteUpdate`).
  When a trip is created on that route, these are snapshotted onto the trip as
  `planned_fuel_liters` / `planned_mileage_km` — a dispatcher can still override either one
  directly on the Trip Entry form if this specific trip needs to differ from the route norm.
- **Route milestones with time goals.** From the Routes page, click **Milestones** on any
  route to add predetermined checkpoints (`POST /master/routes/{id}/milestones`) — a border
  crossing, a fuel stop, the destination itself — each with a `milestone_type` and a
  `target_hours_from_start` (a time goal expressed as hours after the trip actually departs,
  since that's the only meaningful zero point; the planned departure on a Trip Entry form is
  just a plan). Edit or delete them with `PUT`/`DELETE
  /master/routes/{id}/milestones/{milestone_id}`.
- **Snapshotted onto every trip.** When a trip is dispatched on a route, `POST
  /operations/trips` copies that route's milestone template onto the trip
  (`TripMilestone` rows, each still linked back to its `route_milestone_id`). Editing the
  route's template later never rewrites a trip already in progress — each trip keeps exactly
  the checkpoint list it was dispatched with. A trip can also get a one-off checkpoint the
  template didn't anticipate via `POST /operations/trips/{id}/milestones`.
- **Target times fill in once the trip actually departs.** `target_hours_from_start` is
  relative to departure, so it means nothing until there is a departure to count from. The
  moment a trip's status moves to `in_transit` (which is also when `actual_departure` gets
  set), every milestone's `target_at` is computed as `actual_departure + target_hours`.
- **Recording what actually happened.** From the Trip Workspace's **Milestones** table,
  **Record Arrival** (`PATCH /operations/trips/{id}/milestones/{milestone_id}/record`) logs
  the actual arrival time (defaults to now) and marks the checkpoint `reached` or `late`
  depending on whether it beat its `target_at`. **Skip** marks one `not applicable` for how
  the trip actually ran (e.g. a diversion bypassed a border post on the template).
- **End-to-end trip timing.** A trip's `actual_departure` and `actual_arrival` are already
  set automatically on the `in_transit` and `completed` status transitions; `duration_hours`
  (visible on the Trip Workspace's timing line, and in the `TripOut`/`TripDetail` API
  response) is the door-to-door time between them, computed once both are known. While a
  trip is still moving, the same timing line shows elapsed hours so far instead.
- **Actual fuel and mileage.** `PATCH /operations/trips/{id}/fuel-mileage` records
  `actual_fuel_liters` / `actual_mileage_km` against the trip (the Trip Workspace's **Actual
  Fuel & Mileage** card) for a direct planned-vs-actual comparison alongside the timing line.

All of the mutating endpoints above follow the same `operations`/`admin` authorization as the
rest of dispatch (see [User roles and authorization](#user-roles-and-authorization)); every
read (route detail with its milestones, trip detail with its milestones) stays open to every
signed-in role.

## Deploying to the web

The app already *is* a web app (FastAPI serves the browser GUI at `/`) — this section is
about putting it on the public internet with a real URL (and your own domain) instead of
just running on your own machine. It's already prepared for this: `Dockerfile`,
`.dockerignore`, and `render.yaml` are included, `DATABASE_URL` accepts a Postgres connection
string (the app runs on Postgres exactly the same as SQLite — this was tested end-to-end
against a real Postgres database as part of adding this), and the SQLite-only startup
migration shim automatically skips itself when the database isn't SQLite.

Recommended stack (no cost to start, no credit card required for either service):

- **Database: [Neon](https://neon.com)** — free Postgres with no time limit and no
  inactivity deletion (unlike some free database tiers that quietly expire after 30 days).
- **App hosting: [Render](https://render.com)** — free web service hosting that builds
  straight from the included `Dockerfile`, and free custom domains (up to 2) on every plan
  including the free one.

Steps:

1. **Push this code to a GitHub repository.** Render deploys from a git repo. From the
   unzipped `transport_system_mvp` folder:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```
   (Create the empty repository on GitHub first if you haven't — no need to check "add a
   README", since this folder already has one.)

2. **Create a free Neon database.** Sign up at neon.com, create a project, and copy the
   connection string it gives you (starts with `postgresql://`). That's your `DATABASE_URL`.

3. **Deploy on Render.** Sign up at render.com, choose **New > Blueprint**, and point it at
   your GitHub repo — Render reads `render.yaml` automatically and sets up the web service
   from the Dockerfile. When prompted for environment variables, set:
   - `DATABASE_URL` — the Neon connection string from step 2
   - `SECRET_KEY` — any long random string (e.g. run `python -c "import secrets;
     print(secrets.token_hex(32))"` locally and paste the result)
   - the `SMTP_*` variables, only if you want real emails sent (invoices, statements,
     compliance digests) — leave them blank to run without email and the app still works
     fine, it just logs deliveries as `not_configured`.

   Render builds the image and gives you a `https://<something>.onrender.com` URL when it's
   live. Log in with the same seeded `admin` / `admin123` account as local dev — change that
   password immediately (My Account in the sidebar) since this URL is public.

4. **Point your domain at it.** In the Render service's **Settings > Custom Domains**, add
   your domain and Render will show you the exact DNS record to create (a `CNAME` if you're
   using a subdomain like `app.yourdomain.com`, or Render's own instructions for an apex/root
   domain like `yourdomain.com`) — add that record with whoever you registered the domain
   through. Render issues the HTTPS certificate automatically once the DNS record is in
   place; this usually takes a few minutes to a couple of hours to propagate.

**Two things worth knowing about the free tier before relying on it:**

- Render's free web service spins down after periods of inactivity, so the first request
  after a quiet spell takes ~30-60 seconds to wake back up (afterwards it's normal speed).
  Render's paid tier ($7/mo) removes the spin-down if that matters for real use.
- File uploads (driver license copies, vehicle documents, proof-of-delivery photos) are
  written to local disk, which is **not persistent** on Render's free tier — anything
  uploaded is lost on the next deploy/restart. A Render persistent disk ($0.25/GB/month) or
  moving upload storage to S3-compatible storage fixes this; fine to skip while just trying
  the system out.

## Notes for production

Before relying on this for real operations, a developer should also:

- add migrations with Alembic (this MVP uses an ad-hoc `ensure_schema_compatibility()`
  startup routine as a SQLite-only stand-in; fine for local dev, not a substitute for real
  migrations once the schema needs to evolve against a live production database)
- add persistent storage for uploaded documents (S3-compatible storage or a mounted disk —
  see "Deploying to the web" above)
- integrate GPS tracking (would let milestone arrivals and mileage be captured automatically
  instead of manually recorded)
- add audit logging middleware
- add a driver-facing mobile app

## Booking email delivery

When a booking is created, the system now attempts to send a booking email to the client's `Booking Email`.
If that field is empty, it falls back to `Loading Order Email`.

Configure SMTP with:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS`

If SMTP is not configured, the booking is still saved and the booking register shows the email status.
