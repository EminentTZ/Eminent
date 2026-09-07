const pages = [
  ["dashboard", "Dashboard"],
  ["clients", "Clients"],
  ["trucks", "Fleet"],
  ["assignments", "Assignments"],
  ["drivers", "Drivers"],
  ["routes", "Routes"],
  ["vendors", "Vendors"],
  ["bookings", "Bookings"],
  ["trips", "Trips"],
  ["invoices", "Invoices & Payments"],
  ["maintenance", "Maintenance"],
  ["accounts", "Chart of Accounts"],
  ["journal", "Journal"],
  ["reports", "Financial Reports"],
  ["users", "Users"],
];

const state = {
  token: localStorage.getItem("tms_token") || "",
  currentPage: "dashboard",
  selectedBookingId: null,
  selectedTripId: null,
  selectedInvoiceId: null,
  selectedVehicleTyreId: null,
  selectedJournalEntryId: null,
  selectedLedgerAccountCode: null,
  selectedRouteId: null,
  selectedRouteMilestones: [],
  selectedRouteLabelText: null,
  data: { summary: null, users: [], clients: [], vehicles: [], assignments: [], drivers: [], routes: [], vendors: [], bookings: [], trips: [], invoices: [], payments: [], maintenance: [], accounts: [], complianceAlerts: [] },
  arAging: null,
  apAging: null,
  statement: null,
  me: null,
  journal: [],
  ledger: null,
  reports: { trialBalance: null, profitAndLoss: null, balanceSheet: null },
};

const PAYMENT_SOURCE_LABELS = { cash: "Cash on Hand", bank: "Bank", payable: "On Account (Accounts Payable)" };

// --- Roles & permissions --------------------------------------------------
// Mirrors app/permissions.py on the backend. The API is the real gatekeeper
// (it re-checks role on every write regardless of what this UI shows); this
// is purely so the UI doesn't dangle controls a role can't actually use.
const ROLE_BUNDLES = {
  ADMIN: ["admin"],
  FINANCE: ["admin", "accountant"],
  OPS: ["admin", "operations"],
  OPS_FINANCE: ["admin", "operations", "accountant"],
};
const PAGE_ROLE_REQUIREMENTS = { users: ROLE_BUNDLES.ADMIN };

function hasAnyRole(bundle) {
  return Boolean(state.me && bundle.includes(state.me.role));
}

function canAccessPage(key) {
  const required = PAGE_ROLE_REQUIREMENTS[key];
  return !required || hasAnyRole(required);
}

function setElementVisible(el, visible) {
  if (el) el.classList.toggle("hidden", !visible);
}

// Hides a create/edit form -- and the panel it lives in, if that panel
// exists solely to hold it -- from anyone outside `bundle`.
function gatePanelOf(formId, bundle) {
  const form = document.getElementById(formId);
  if (!form) return;
  const panel = form.closest(".panel") || form.closest(".card-form");
  setElementVisible(panel || form, hasAnyRole(bundle));
}

// Hides a form (plus its immediately preceding heading, if any) without
// touching the rest of the panel it shares with other content.
function gateForm(formId, bundle) {
  const form = document.getElementById(formId);
  if (!form) return;
  const visible = hasAnyRole(bundle);
  setElementVisible(form, visible);
  const header = form.previousElementSibling;
  if (header && header.classList.contains("panel-header")) setElementVisible(header, visible);
}

function applyRoleVisibility() {
  gatePanelOf("clientForm", ROLE_BUNDLES.OPS);
  gatePanelOf("vehicleForm", ROLE_BUNDLES.OPS);
  gatePanelOf("driverForm", ROLE_BUNDLES.OPS);
  gatePanelOf("routeForm", ROLE_BUNDLES.OPS);
  gatePanelOf("tripMilestoneForm", ROLE_BUNDLES.OPS);
  gatePanelOf("fuelMileageForm", ROLE_BUNDLES.OPS);
  // routeMilestoneForm shares its panel with the read-only milestones table
  // (which stays open to every role), so only the form itself is hidden --
  // not the whole panel the way gatePanelOf would.
  setElementVisible(document.getElementById("routeMilestoneForm"), hasAnyRole(ROLE_BUNDLES.OPS));
  gatePanelOf("assignmentForm", ROLE_BUNDLES.OPS);
  gatePanelOf("bookingForm", ROLE_BUNDLES.OPS);
  gatePanelOf("vendorForm", ROLE_BUNDLES.OPS_FINANCE);
  gatePanelOf("maintenanceForm", ROLE_BUNDLES.OPS);
  gatePanelOf("tripForm", ROLE_BUNDLES.OPS);
  gatePanelOf("tripEventForm", ROLE_BUNDLES.OPS);
  gatePanelOf("tripExpenseForm", ROLE_BUNDLES.OPS);
  gatePanelOf("podForm", ROLE_BUNDLES.OPS);
  gatePanelOf("invoiceFromTripForm", ROLE_BUNDLES.OPS_FINANCE);
  gateForm("paymentForm", ROLE_BUNDLES.FINANCE);
  gateForm("batchPaymentForm", ROLE_BUNDLES.FINANCE);
  gatePanelOf("accountForm", ROLE_BUNDLES.FINANCE);
  gatePanelOf("ledgerSettingsForm", ROLE_BUNDLES.FINANCE);
  gatePanelOf("journalEntryForm", ROLE_BUNDLES.FINANCE);

  setElementVisible(document.getElementById("reverseJournalBtn"), hasAnyRole(ROLE_BUNDLES.FINANCE));
  setElementVisible(document.querySelector("#tripStatusSelect")?.closest(".toolbar"), hasAnyRole(ROLE_BUNDLES.OPS));
  setElementVisible(document.getElementById("sendStatementBtn"), hasAnyRole(ROLE_BUNDLES.FINANCE));
  setElementVisible(document.getElementById("sendComplianceDigestBtn"), hasAnyRole(ROLE_BUNDLES.OPS_FINANCE));

  const opsOnlyRowActions = "[data-edit-client],[data-client-deactivate],[data-client-reactivate],[data-edit-vehicle],[data-vehicle-ground],[data-vehicle-reinstate],[data-edit-driver],[data-edit-route],[data-route-milestone-delete],[data-milestone-record],[data-milestone-skip],[data-maintenance-complete],[data-booking-accept],[data-booking-reject],[data-booking-use]";
  document.querySelectorAll(opsOnlyRowActions).forEach((el) => setElementVisible(el, hasAnyRole(ROLE_BUNDLES.OPS)));
  document.querySelectorAll("[data-edit-vendor],[data-vendor-deactivate],[data-vendor-reactivate]").forEach((el) => setElementVisible(el, hasAnyRole(ROLE_BUNDLES.OPS_FINANCE)));
  document.querySelectorAll("[data-expense-settle],[data-maintenance-settle]").forEach((el) => setElementVisible(el, hasAnyRole(ROLE_BUNDLES.FINANCE)));
  document.querySelectorAll("[data-invoice-reject]").forEach((el) => setElementVisible(el, hasAnyRole(ROLE_BUNDLES.OPS_FINANCE)));
}

const tyreInfoFields = ["date_of_installation", "mileage_at_installation_km", "brand", "serial_number"];

const tyreLayoutConfigs = {
  trailer: {
    "111": {
      code: "111",
      label: "three axle super single tyre",
      title: "Trailer Position Chart",
      subtitle: "3 axle super single tyre",
      unitLabel: "trailer",
      rows: [
        { axle: "Axle 1", left: [{ key: "L1", short: "L1", label: "Axle 1 - Left (L1)" }], right: [{ key: "R1", short: "R1", label: "Axle 1 - Right (R1)" }] },
        { axle: "Axle 2", left: [{ key: "L2", short: "L2", label: "Axle 2 - Left (L2)" }], right: [{ key: "R2", short: "R2", label: "Axle 2 - Right (R2)" }] },
        { axle: "Axle 3", left: [{ key: "L3", short: "L3", label: "Axle 3 - Left (L3)" }], right: [{ key: "R3", short: "R3", label: "Axle 3 - Right (R3)" }] },
      ],
    },
    "222": {
      code: "222",
      label: "three axle double tyre",
      title: "Trailer Position Chart",
      subtitle: "3 axle double tyre",
      unitLabel: "trailer",
      rows: [
        { axle: "Axle 1", left: [{ key: "L1I", short: "L1I", label: "Axle 1 - Left Inner (L1I)" }, { key: "L1O", short: "L1O", label: "Axle 1 - Left Outer (L1O)" }], right: [{ key: "R1I", short: "R1I", label: "Axle 1 - Right Inner (R1I)" }, { key: "R1O", short: "R1O", label: "Axle 1 - Right Outer (R1O)" }] },
        { axle: "Axle 2", left: [{ key: "L2I", short: "L2I", label: "Axle 2 - Left Inner (L2I)" }, { key: "L2O", short: "L2O", label: "Axle 2 - Left Outer (L2O)" }], right: [{ key: "R2I", short: "R2I", label: "Axle 2 - Right Inner (R2I)" }, { key: "R2O", short: "R2O", label: "Axle 2 - Right Outer (R2O)" }] },
        { axle: "Axle 3", left: [{ key: "L3I", short: "L3I", label: "Axle 3 - Left Inner (L3I)" }, { key: "L3O", short: "L3O", label: "Axle 3 - Left Outer (L3O)" }], right: [{ key: "R3I", short: "R3I", label: "Axle 3 - Right Inner (R3I)" }, { key: "R3O", short: "R3O", label: "Axle 3 - Right Outer (R3O)" }] },
      ],
    },
  },
  dangler: {
    "1": {
      code: "1",
      label: "One axle super single",
      title: "Dangler Position Chart",
      subtitle: "Single axle super single tyre",
      unitLabel: "dangler",
      rows: [
        { axle: "Axle 1", left: [{ key: "L", short: "L", label: "Left (L)" }], right: [{ key: "R", short: "R", label: "Right (R)" }] },
      ],
    },
    "2": {
      code: "2",
      label: "One Axle double tyre",
      title: "Dangler Position Chart",
      subtitle: "Single axle double tyre",
      unitLabel: "dangler",
      rows: [
        { axle: "Axle 1", left: [{ key: "LI", short: "LI", label: "Left Inner (LI)" }, { key: "LO", short: "LO", label: "Left Outer (LO)" }], right: [{ key: "RI", short: "RI", label: "Right Inner (RI)" }, { key: "RO", short: "RO", label: "Right Outer (RO)" }] },
      ],
    },
    "11": {
      code: "11",
      label: "Two axle super single tyre",
      title: "Dangler Position Chart",
      subtitle: "Two axle super single tyre",
      unitLabel: "dangler",
      rows: [
        { axle: "Front Axle", left: [{ key: "LF", short: "LF", label: "Left Front (LF)" }], right: [{ key: "RF", short: "RF", label: "Right Front (RF)" }] },
        { axle: "Rear Axle", left: [{ key: "LR", short: "LR", label: "Left Rear (LR)" }], right: [{ key: "RR", short: "RR", label: "Right Rear (RR)" }] },
      ],
    },
    "22": {
      code: "22",
      label: "two axle double tyre",
      title: "Dangler Position Chart",
      subtitle: "Two axle double tyre",
      unitLabel: "dangler",
      rows: [
        { axle: "Front Axle", left: [{ key: "LFI", short: "LFI", label: "Left Front Inner (LFI)" }, { key: "LFO", short: "LFO", label: "Left Front Outer (LFO)" }], right: [{ key: "RFI", short: "RFI", label: "Right Front Inner (RFI)" }, { key: "RFO", short: "RFO", label: "Right Front Outer (RFO)" }] },
        { axle: "Rear Axle", left: [{ key: "LRI", short: "LRI", label: "Left Rear Inner (LRI)" }, { key: "LRO", short: "LRO", label: "Left Rear Outer (LRO)" }], right: [{ key: "RRI", short: "RRI", label: "Right Rear Inner (RRI)" }, { key: "RRO", short: "RRO", label: "Right Rear Outer (RRO)" }] },
      ],
    },
  },
};

const pageLabels = Object.fromEntries(pages);
const pageIcons = {
  dashboard: "📊", clients: "🤝", trucks: "🚚", assignments: "🔗", drivers: "🪪", routes: "🗺️",
  vendors: "🏢", bookings: "📋", trips: "🛣️", invoices: "🧾", maintenance: "🔧", accounts: "📒",
  journal: "📖", reports: "📈", users: "👤",
};
const numberFields = new Set(["credit_days", "year", "capacity_tons", "distance_km", "expected_days", "border_charges", "driver_allowance", "delay_threshold_days", "demurrage_rate_per_day", "agreed_revenue", "amount", "cost", "rate", "cargo_weight_tons", "rate_per_ton", "stage_percentage", "vendor_id", "standard_fuel_liters", "standard_driver_mileage_km", "planned_fuel_liters", "planned_mileage_km", "actual_fuel_liters", "actual_mileage_km", "sequence", "target_hours_from_start"]);
const booleanFields = new Set(["is_recoverable", "allow_reassignment", "is_backload"]);
const flash = document.getElementById("flash");
const sessionStatus = document.getElementById("sessionStatus");
const pageTitle = document.getElementById("pageTitle");
const viewRoot = document.getElementById("viewRoot");
const loginPanel = document.querySelector(".login-panel");

function buildNav() {
  document.getElementById("navList").innerHTML = pages.filter(([key]) => canAccessPage(key)).map(([key, label]) => `<a class="nav-link${key === state.currentPage ? " active" : ""}" data-page="${key}" href="#${key}"><span class="nav-icon">${pageIcons[key] || "•"}</span><span class="nav-label">${label}</span></a>`).join("");
}

function dashboardView() {
  return `
    <section class="view-stack">
      <div class="stats-grid" id="dashboardStats"></div>
      <div class="split-grid">
        <section class="panel">
          <div class="panel-header"><div><h3>Operations Snapshot</h3><p class="subtle">A quick read on fleet and revenue movement.</p></div></div>
          <div class="mini-grid">
            <div class="info-card"><span class="info-label">Open Trips</span><strong id="dashboardOpenTrips">0</strong></div>
            <div class="info-card"><span class="info-label">Ready Drivers</span><strong id="dashboardReadyDrivers">0</strong></div>
            <div class="info-card"><span class="info-label">Active Trucks</span><strong id="dashboardActiveVehicles">0</strong></div>
            <div class="info-card"><span class="info-label">Maintenance Queue</span><strong id="dashboardMaintenanceCount">0</strong></div>
          </div>
        </section>
        <section class="panel">
          <div class="panel-header"><div><h3>Recent Trips</h3><p class="subtle">Latest dispatches and completions.</p></div></div>
          <div class="table-wrap"><table><thead><tr><th>Trip</th><th>Client</th><th>Status</th><th>Revenue</th></tr></thead><tbody id="dashboardTripsBody"></tbody></table></div>
        </section>
      </div>
      <section class="panel">
        <div class="panel-header"><div><h3>Compliance Alerts</h3><p class="subtle">Vehicles and drivers with a document that's expired or expiring within 30 days -- insurance, road license, C28, or driver license.</p></div><button type="button" id="sendComplianceDigestBtn" class="ghost-button">Email Digest to Admins</button></div>
        <div class="table-wrap"><table><thead><tr><th>Type</th><th>Name</th><th>Document</th><th>Expiry</th><th>Status</th></tr></thead><tbody id="complianceAlertsBody"></tbody></table></div>
      </section>
    </section>`;
}

function entityPage(title, note, formId, formFields, tableId, headers) {
  return `
    <section class="split-grid">
      <section class="panel">
        <div class="panel-header"><div><h3>${title} Entry</h3><p class="subtle">${note}</p></div></div>
        <form id="${formId}" class="form-grid">
          <input type="hidden" name="_edit_id" data-edit-id-field>
          ${formFields}
          <div class="form-actions span-2"><button type="submit">Save</button><button type="button" class="ghost-button hidden" data-cancel-edit>Cancel Edit</button></div>
        </form>
      </section>
      <section class="panel">
        <div class="panel-header"><div><h3>${title} Register</h3><p class="subtle">Current records in the system.</p></div></div>
        <div class="table-wrap"><table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody id="${tableId}"></tbody></table></div>
      </section>
    </section>`;
}

function routesView() {
  return `
    <section class="stack-grid">
      <section class="split-grid">
        <section class="panel">
          <div class="panel-header"><div><h3>Route Entry</h3><p class="subtle">Configure route economics, distances, delay rules, and the predetermined fuel/mileage budget every trip on this route should start from.</p></div></div>
          <form id="routeForm" class="form-grid">
            <input type="hidden" name="_edit_id" data-edit-id-field>
            <label><span>Route Name</span><input name="route_name" required></label>
            <label><span>Origin</span><input name="origin" required></label>
            <label><span>Destination</span><input name="destination" required></label>
            <label><span>Distance KM</span><input name="distance_km" type="number" step="0.1"></label>
            <label><span>Expected Days</span><input name="expected_days" type="number" step="0.1"></label>
            <label><span>Border Charges</span><input name="border_charges" type="number" step="0.01" value="0"></label>
            <label><span>Driver Allowance</span><input name="driver_allowance" type="number" step="0.01" value="0"></label>
            <label><span>Delay Threshold Days</span><input name="delay_threshold_days" type="number" step="0.1" value="0"></label>
            <label><span>Demurrage Rate / Day</span><input name="demurrage_rate_per_day" type="number" step="0.01" value="0"></label>
            <label><span>Standard Fuel (liters)</span><input name="standard_fuel_liters" type="number" step="0.1" placeholder="Predetermined fuel budget"></label>
            <label><span>Standard Driver Mileage (km)</span><input name="standard_driver_mileage_km" type="number" step="0.1" placeholder="Predetermined mileage"></label>
            <div class="form-actions span-2"><button type="submit">Save</button><button type="button" class="ghost-button hidden" data-cancel-edit>Cancel Edit</button></div>
          </form>
        </section>
        <section class="panel">
          <div class="panel-header"><div><h3>Route Register</h3><p class="subtle">Click "Milestones" to set predetermined checkpoints and time goals -- every trip dispatched on that route from then on gets its own copy of them.</p></div></div>
          <div class="table-wrap"><table><thead><tr><th>Route</th><th>Origin</th><th>Destination</th><th>Expected Days</th><th>Fuel (L)</th><th>Mileage (km)</th><th>Actions</th></tr></thead><tbody id="routesBody"></tbody></table></div>
        </section>
      </section>
      <section class="panel">
        <div class="panel-header"><div><h3>Route Milestones</h3><p id="selectedRouteLabel" class="subtle">Select a route above to manage its predetermined checkpoints and time goals.</p></div></div>
        <form id="routeMilestoneForm" class="form-grid compact-grid">
          <label><span>Sequence</span><input name="sequence" type="number" value="0"></label>
          <label class="span-2"><span>Name</span><input name="name" required placeholder="e.g. Namanga Border"></label>
          <label><span>Type</span><select name="milestone_type"><option value="departure">departure</option><option value="border">border</option><option value="checkpoint" selected>checkpoint</option><option value="fuel_stop">fuel_stop</option><option value="destination">destination</option><option value="other">other</option></select></label>
          <label><span>Time Goal (hrs from departure)</span><input name="target_hours_from_start" type="number" step="0.1" placeholder="e.g. 6"></label>
          <div class="form-actions span-2"><button type="submit">Add Milestone</button></div>
        </form>
        <div class="table-wrap"><table><thead><tr><th>#</th><th>Name</th><th>Type</th><th>Time Goal (hrs)</th><th>Actions</th></tr></thead><tbody id="routeMilestonesBody"><tr><td colspan="5">Select a route above.</td></tr></tbody></table></div>
      </section>
    </section>`;
}

function trucksView() {
  return `
    <section class="split-grid">
      <section class="panel">
        <div class="panel-header"><div><h3>Vehicle Entry</h3><p class="subtle">All visible vehicle details are mandatory. Tyre position details remain optional.</p></div></div>
        <form id="vehicleForm" class="form-grid">
          <input type="hidden" name="_edit_id" data-edit-id-field>
          <label><span>Registration No</span><input name="registration_no" required></label>
          <label><span>Vehicle Type</span><select name="vehicle_type" id="vehicleTypeSelect" required><option value="tractor">tractor</option><option value="trailer">trailer</option><option value="dangler">dangler</option></select></label>
          <label><span>Make</span><input name="make" required></label>
          <label><span>Model</span><input name="model" required></label>
          <label><span>Year</span><input name="year" type="number" required></label>
          <label id="capacityField"><span>Capacity Tons</span><input name="capacity_tons" type="number" step="0.1"></label>
          <label id="tyreLayoutField"><span>Tyre Layout</span><select name="tyre_layout" id="tyreLayoutSelect"></select></label>
          <label id="c28ExpiryField"><span>C28 Expiry</span><input name="c28_expiry" type="date"></label>
          <label id="c28CardField"><span>C28 Document</span><input name="c28_card" type="file" accept='.pdf,.jpg,.jpeg,.png,.webp'></label>
          <label id="registrationCardField"><span>Registration Card</span><input name="registration_card" type="file" accept='.pdf,.jpg,.jpeg,.png,.webp'></label>
          <label><span>Status</span><select name="status" required><option value="active">active</option><option value="idle">idle</option><option value="maintenance">maintenance</option></select></label>
          <label><span>Insurance Expiry</span><input name="insurance_expiry" type="date" required></label>
          <label><span>Road License Expiry</span><input name="road_license_expiry" type="date" required></label>
          <input type="hidden" name="tyre_info_json" id="tyreInfoJson">
          <section id="tyreCaptureField" class="tyre-capture-field span-2 hidden">
            <div class="tyre-capture-header"><div><h3>Tyre Position & Information</h3><p class="subtle">Capture tyre installation date, mileage, brand, and serial number when available.</p></div></div>
            <div id="tyreCaptureBoard" class="tyre-capture-board"></div>
            <div id="tyreCaptureCards" class="tyre-capture-grid"></div>
          </section>
          <div class="form-actions span-2"><button type="submit">Save Vehicle</button><button type="button" class="ghost-button hidden" data-cancel-edit>Cancel Edit</button></div>
        </form>
      </section>
      <section class="panel">
        <div class="panel-header"><div><h3>Vehicle Register</h3><p class="subtle">Current fleet records and tyre information status.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Registration</th><th>Type</th><th>Status</th><th>Capacity</th><th>Tyre Layout</th><th>Tyre Status</th><th>Compliance</th><th>Documents</th><th>Actions</th></tr></thead><tbody id="vehiclesBody"></tbody></table></div>
      </section>
    </section>`;
}

function assignmentsView() {
  return `
    <section class="split-grid">
      <section class="panel">
        <div class="panel-header"><div><h3>Equipment Assignment</h3><p class="subtle">Assign a trailer and dangler chain to a tractor, and link the working driver to that tractor.</p></div></div>
        <form id="assignmentForm" class="form-grid">
          <label class="checkbox-row span-2"><input id="assignmentAllowReassignment" name="allow_reassignment" type="checkbox"><span>Show reassignable equipment and drivers that are not in an active trip</span></label>
          <label><span>Tractor</span><select id="assignmentTractor" name="tractor_id" required></select></label>
          <label><span>Driver</span><select id="assignmentDriver" name="driver_id"></select></label>
          <label><span>Trailer</span><select id="assignmentTrailer" name="trailer_id"></select></label>
          <label><span>Dangler</span><select id="assignmentDangler" name="dangler_id"></select></label>
          <div id="assignmentConflictNotice" class="inline-warning hidden span-2"></div>
          <div class="form-actions span-2"><button id="assignmentSaveBtn" type="submit">Save Assignment</button></div>
        </form>
      </section>
      <section class="panel">
        <div class="panel-header"><div><h3>Assignment Register</h3><p class="subtle">These active links are used to auto-fill trips when a tractor is selected.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Tractor</th><th>Driver</th><th>Trailer</th><th>Dangler</th><th>Status</th></tr></thead><tbody id="assignmentsBody"></tbody></table></div>
      </section>
    </section>`;
}

function bookingsView() {
  return `
    <section class="split-grid">
      <section class="panel">
        <div class="panel-header"><div><h3>Booking Entry</h3><p class="subtle">Transport officers can reserve a truck, route, client, cargo type, and rate before client acceptance.</p></div></div>
        <form id="bookingForm" class="form-grid">
          <label><span>Vehicle</span><select id="bookingVehicle" name="tractor_id" required></select></label>
          <label><span>Route</span><select id="bookingRoute" name="route_id" required></select></label>
          <label><span>Client</span><select id="bookingClient" name="client_id" required></select></label>
          <label><span>Cargo Type</span><select name="cargo_type" required><option value="20feet container">20feet container</option><option value="40 feet container">40 feet container</option><option value="loose cargo">loose cargo</option></select></label>
          <label><span>Rate</span><input name="rate" type="number" step="0.01" required></label>
          <label><span>Currency</span><input name="currency" value="TZS"></label>
          <label class="span-2"><span>Notes</span><input name="notes"></label>
          <div class="form-actions span-2"><button type="submit">Save Booking</button></div>
        </form>
      </section>
      <section class="panel">
        <div class="panel-header"><div><h3>Booking Register</h3><p class="subtle">Accepted bookings can be sent straight into the Trips module for dispatch planning.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Booking</th><th>Client</th><th>Route</th><th>Vehicle</th><th>Cargo</th><th>Rate</th><th>Status</th><th>Email Status</th><th>Action</th></tr></thead><tbody id="bookingsBody"></tbody></table></div>
      </section>
    </section>`;
}

function tripsView() {
  return `
    <section class="stack-grid">
      <section class="panel">
        <div class="panel-header"><div><h3>Trip Entry</h3><p class="subtle">Dispatch new jobs using client, route, and tractor assignments. Selecting a tractor auto-loads its linked driver, trailer, and dangler if assigned.</p></div></div>
        <form id="tripForm" class="form-grid trip-grid">
          <label><span>Accepted Booking</span><select id="tripBooking" name="booking_id"></select></label>
          <label><span>Trip Number</span><input name="trip_number" required></label>
          <label><span>Client</span><select id="tripClient" name="client_id" required></select></label>
          <label><span>Route</span><select id="tripRoute" name="route_id" required></select></label>
          <label><span>Tractor</span><select id="tripVehicle" name="tractor_id" required></select></label>
          <label><span>Trailer</span><select id="tripTrailer" name="trailer_id"></select></label>
          <label><span>Dangler</span><select id="tripDangler" name="dangler_id"></select></label>
          <label><span>Driver</span><select id="tripDriver" name="driver_id" required></select></label>
          <p id="tripAssignmentNotice" class="subtle span-3">Select a tractor to load its assignment.</p>
          <label><span>Cargo Type</span><select id="tripCargoType" name="cargo_type" required><option value="20feet container">20feet container</option><option value="40 feet container">40 feet container</option><option value="loose cargo">loose cargo</option><option value="bulk mineral">bulk mineral</option></select></label>
          <label><span id="tripRevenueLabel">Agreed Revenue</span><input id="tripRevenueInput" name="agreed_revenue" type="number" step="0.01" required></label>
          <label><span>Currency</span><input name="currency" value="TZS"></label>
          <label><span>Client Order / Booking Reference</span><input name="customer_reference" placeholder="e.g. client's own Transport Order or Loading Order number"></label>
          <label><span>Cargo Weight (tons)</span><input name="cargo_weight_tons" type="number" step="0.01"></label>
          <label><span>Rate Per Ton (informational)</span><input name="rate_per_ton" type="number" step="0.01"></label>
          <label><span>Rate Type</span><select name="rate_type"><option value="">Not applicable</option><option value="flat">Flat per trip</option><option value="roundtrip">Roundtrip per ton</option><option value="going">Going leg per ton</option><option value="return">Return leg per ton</option></select></label>
          <label class="checkbox-row"><input name="is_backload" type="checkbox"><span>Carrying backload (return cargo)</span></label>
          <label><span>Planned Departure</span><input name="planned_departure" type="datetime-local"></label>
          <label><span>Planned Arrival</span><input name="planned_arrival" type="datetime-local"></label>
          <label><span>Planned Fuel (liters)</span><input name="planned_fuel_liters" type="number" step="0.1" placeholder="Defaults to the route's standard fuel budget"></label>
          <label><span>Planned Mileage (km)</span><input name="planned_mileage_km" type="number" step="0.1" placeholder="Defaults to the route's standard mileage"></label>
          <label class="span-3"><span>Cargo Description</span><input name="cargo_description"></label>
          <label class="span-3"><span>Notes</span><input name="notes"></label>
          <div class="form-actions span-3"><button type="submit">Create Trip</button></div>
        </form>
      </section>
      <section class="split-grid">
        <section class="panel">
          <div class="panel-header"><div><h3>Trip Register</h3><p class="subtle">Select a trip to manage status, events, expenses, and invoicing.</p></div></div>
          <div class="table-wrap"><table><thead><tr><th>Trip</th><th>Status</th><th>Revenue</th><th>Action</th></tr></thead><tbody id="tripsBody"></tbody></table></div>
        </section>
        <section class="panel">
          <div class="panel-header"><div><h3>Trip Workspace</h3><p id="selectedTripLabel" class="subtle">Select a trip from the register.</p></div></div>
          <p id="tripTimingSummary" class="subtle"></p>
          <div class="toolbar"><label><span>Status</span><select id="tripStatusSelect"><option value="planned">planned</option><option value="approved">approved</option><option value="in_transit">in_transit</option><option value="completed">completed</option><option value="cancelled">cancelled</option></select></label><button id="updateTripStatusBtn" type="button">Update Status</button></div>
          <div class="mini-grid">
            <form id="tripEventForm" class="card-form"><h3>Add Event</h3><label><span>Event Type</span><input name="event_type" required></label><label><span>Location</span><input name="location"></label><label><span>Event Time</span><input name="event_time" type="datetime-local"></label><label><span>Delay Cause</span><input name="delay_cause"></label><label><span>Notes</span><input name="notes"></label><button type="submit">Save Event</button></form>
            <form id="tripExpenseForm" class="card-form"><h3>Add Expense</h3><label><span>Expense Type</span><input name="expense_type" required></label><label><span>Amount</span><input name="amount" type="number" step="0.01" required></label><label><span>Currency</span><input name="currency" value="TZS"></label><label><span>Description</span><input name="description"></label><label class="checkbox-row"><input name="is_recoverable" type="checkbox"><span>Recoverable</span></label><label><span>Payment Source</span><select name="payment_source"><option value="payable">On Account (Accounts Payable)</option><option value="cash">Cash on Hand</option><option value="bank">Bank</option></select></label><label><span>Vendor (if on account)</span><select id="tripExpenseVendorId" name="vendor_id"></select></label><label><span>GL Account (optional override)</span><select id="tripExpenseGlAccount" name="gl_account_code"><option value="">Auto-detect from expense type</option></select></label><button type="submit">Save Expense</button></form>
            <form id="tripMilestoneForm" class="card-form"><h3>Add Milestone</h3><p class="subtle">Checkpoints copied from the route appear below automatically -- use this only for something extra this trip needs.</p><label><span>Sequence</span><input name="sequence" type="number" value="0"></label><label><span>Name</span><input name="name" required placeholder="e.g. Unplanned stop"></label><label><span>Type</span><select name="milestone_type"><option value="departure">departure</option><option value="border">border</option><option value="checkpoint" selected>checkpoint</option><option value="fuel_stop">fuel_stop</option><option value="destination">destination</option><option value="other">other</option></select></label><label><span>Time Goal (hrs from departure)</span><input name="target_hours_from_start" type="number" step="0.1"></label><button type="submit">Save Milestone</button></form>
            <form id="fuelMileageForm" class="card-form"><h3>Actual Fuel &amp; Mileage</h3><p class="subtle">Record what was actually used, against the planned figures shown below.</p><label><span>Actual Fuel (liters)</span><input name="actual_fuel_liters" type="number" step="0.1"></label><label><span>Actual Mileage (km)</span><input name="actual_mileage_km" type="number" step="0.1"></label><button type="submit">Save</button></form>
            <form id="podForm" class="card-form"><h3>Proof of Delivery</h3><p class="subtle">Capture confirmation that cargo was delivered before invoicing.</p><label><span>Notes</span><input name="notes" placeholder="e.g. received by, condition on arrival"></label><label><span>Document</span><input name="document" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp"></label><button type="submit">Save POD</button><p id="tripPodStatus" class="subtle"></p></form>
            <form id="invoiceFromTripForm" class="card-form"><h3>Generate Invoice</h3><label><span>Stage</span><select id="invoiceStageSelect" name="stage"><option value="full">Full (100%)</option><option value="advance">Advance</option><option value="balance">Balance</option><option value="final">Final</option></select></label><label><span>Stage %</span><input id="invoiceStagePercentage" name="stage_percentage" type="number" step="1" min="1" max="100" value="100"></label><label><span>Due Date</span><input name="due_date" type="date"></label><label><span>Notes</span><input name="notes"></label><button type="submit">Create Invoice</button></form>
          </div>
          <div class="split-grid"><div><h3>Events</h3><ul id="tripEventsList" class="detail-list"></ul></div><div><h3>Expenses</h3><ul id="tripExpensesList" class="detail-list"></ul></div></div>
          <div class="panel-header"><div><h3>Milestones</h3><p class="subtle">Predetermined checkpoints and time goals for this trip, target vs actual.</p></div></div>
          <div class="table-wrap"><table><thead><tr><th>#</th><th>Name</th><th>Type</th><th>Target</th><th>Actual</th><th>Status</th><th>Actions</th></tr></thead><tbody id="tripMilestonesBody"><tr><td colspan="7">Select a trip from the register.</td></tr></tbody></table></div>
        </section>
      </section>
    </section>`;
}

function invoicesView() {
  return `
    <section class="split-grid">
      <section class="panel">
        <div class="panel-header"><div><h3>Invoices</h3><p class="subtle">Issued invoice records linked to trips. Staged invoices (advance/balance/final) may appear more than once per trip.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Invoice</th><th>Trip</th><th>Stage</th><th>Status</th><th>Amount</th><th>Email</th><th>Action</th></tr></thead><tbody id="invoicesBody"></tbody></table></div>
      </section>
      <section class="panel">
        <div class="panel-header"><div><h3>Record Payment</h3><p id="selectedInvoiceLabel" class="subtle">Select an invoice from the table.</p></div></div>
        <form id="paymentForm" class="form-grid">
          <label><span>Invoice</span><select id="paymentInvoiceId" name="invoice_id" required></select></label>
          <label><span>Amount</span><input name="amount" type="number" step="0.01" required></label>
          <label><span>Payment Date</span><input name="payment_date" type="date"></label>
          <label><span>Method</span><input name="method" value="bank_transfer" required></label>
          <label><span>Reference</span><input name="reference"></label>
          <label><span>Deposit To (optional override)</span><select id="paymentDepositAccount" name="deposit_account_code"><option value="">Auto-detect from method</option></select></label>
          <label class="span-2"><span>Notes</span><input name="notes"></label>
          <div class="form-actions span-2"><button type="submit">Record Payment</button></div>
        </form>
        <div class="panel-header"><div><h3>Batch Remittance</h3><p class="subtle">Settle several invoices at once from one consolidated remittance advice (e.g. a broker paying a batch of trips together).</p></div></div>
        <form id="batchPaymentForm" class="form-grid">
          <label class="span-2"><span>Remittance Reference</span><input name="remittance_reference" required placeholder="e.g. the broker's remittance advice number"></label>
          <div class="span-2" id="batchPaymentLinesContainer"></div>
          <div class="form-actions span-2"><button type="button" id="addBatchPaymentLineBtn" class="ghost-button">+ Add Invoice</button></div>
          <label><span>Payment Date</span><input name="payment_date" type="date"></label>
          <label><span>Method</span><input name="method" value="bank_transfer" required></label>
          <div class="form-actions span-2"><button type="submit">Record Batch Payment</button></div>
        </form>
        <div class="panel-header"><div><h3>Payments</h3><p class="subtle">Latest recorded settlements.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Invoice ID</th><th>Amount</th><th>Date</th><th>Method</th><th>Remittance</th></tr></thead><tbody id="paymentsBody"></tbody></table></div>
      </section>
    </section>`;
}

function accountsView() {
  return `
    <section class="view-stack">
      <section class="panel">
        <div class="panel-header"><div><h3>About this Chart of Accounts</h3><p class="subtle">Seeded directly from the company's live general ledger, so every code here matches the books of record. Postings from trips, invoices, payments, running costs, and workshop bills all land against these same accounts.</p></div></div>
      </section>
      <section class="split-grid">
        <section class="panel">
          <div class="panel-header"><div><h3>Add Custom Account</h3><p class="subtle">Only add an account if nothing in the official chart fits.</p></div></div>
          <form id="accountForm" class="form-grid">
            <label><span>Code</span><input name="code" required></label>
            <label><span>Name</span><input name="name" required></label>
            <label><span>Statement Class</span><select name="statement_class" required><option value="asset">Asset</option><option value="liability">Liability</option><option value="equity">Equity</option><option value="income">Income</option><option value="cogs">Cost of Goods Sold</option><option value="expense">Expense</option></select></label>
            <label><span>Normal Balance</span><select name="normal_balance" required><option value="debit">Debit</option><option value="credit">Credit</option></select></label>
            <label class="span-2"><span>Account Group</span><input name="account_group"></label>
            <div class="form-actions span-2"><button type="submit">Add Account</button></div>
          </form>
        </section>
        <section class="panel">
          <div class="panel-header"><div><h3>Ledger Settings</h3><p class="subtle">Default accounts used for auto-posting. Change only if the bookkeeper wants postings redirected.</p></div></div>
          <form id="ledgerSettingsForm" class="form-grid" id="ledgerSettingsForm">
            <label><span>Default Cash Account</span><select id="settingsCash" name="default_cash_account_code"></select></label>
            <label><span>Default Bank Account</span><select id="settingsBank" name="default_bank_account_code"></select></label>
            <label><span>Accounts Receivable</span><select id="settingsReceivable" name="receivable_account_code"></select></label>
            <label><span>Accounts Payable</span><select id="settingsPayable" name="payable_account_code"></select></label>
            <label><span>Revenue Account</span><select id="settingsRevenue" name="revenue_account_code"></select></label>
            <label><span>Delay Income Account</span><select id="settingsDelay" name="delay_income_account_code"></select></label>
            <label><span>Recovered Expense Income</span><select id="settingsRecovered" name="recovered_expense_income_code"></select></label>
            <label><span>Default Trip Cost Account</span><select id="settingsTripCogs" name="default_trip_cogs_account_code"></select></label>
            <label><span>Default Maintenance Account</span><select id="settingsMaintenance" name="default_maintenance_account_code"></select></label>
            <label><span>Default Expense Account</span><select id="settingsExpense" name="default_expense_account_code"></select></label>
            <div class="form-actions span-2"><button type="submit">Save Settings</button></div>
          </form>
        </section>
      </section>
      <section class="panel">
        <div class="panel-header">
          <div><h3>Chart of Accounts</h3><p class="subtle">Click a row to view its ledger (transaction history and running balance).</p></div>
          <select id="accountsClassFilter"><option value="">All classes</option><option value="asset">Asset</option><option value="liability">Liability</option><option value="equity">Equity</option><option value="income">Income</option><option value="cogs">Cost of Goods Sold</option><option value="expense">Expense</option></select>
        </div>
        <div class="table-wrap"><table><thead><tr><th>Code</th><th>Name</th><th>Class</th><th>Group</th><th>Normal Balance</th></tr></thead><tbody id="accountsBody"></tbody></table></div>
      </section>
      <section class="panel">
        <div class="panel-header"><div><h3>Account Ledger</h3><p id="ledgerLabel" class="subtle">Select an account above to view its transaction history.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Date</th><th>Entry</th><th>Memo / Line</th><th>Debit</th><th>Credit</th><th>Balance</th></tr></thead><tbody id="ledgerBody"><tr><td colspan="6">No account selected.</td></tr></tbody></table></div>
      </section>
    </section>`;
}

function journalView() {
  return `
    <section class="view-stack">
      <section class="panel">
        <div class="panel-header"><div><h3>New Journal Entry</h3><p class="subtle">Every operational event (trip expenses, invoices, payments, workshop bills) posts automatically. Use this only for manual corrections, opening balances, or adjustments -- debits must equal credits.</p></div></div>
        <form id="journalEntryForm" class="form-grid">
          <label><span>Entry Date</span><input name="entry_date" type="date"></label>
          <label class="span-1"><span>Memo</span><input name="memo" required></label>
          <div class="span-2" id="journalLinesContainer"></div>
          <div class="form-actions span-2">
            <button type="button" id="addJournalLineBtn" class="ghost-button">+ Add Line</button>
            <span id="journalBalanceHint" class="subtle"></span>
          </div>
          <div class="form-actions span-2"><button type="submit">Post Journal Entry</button></div>
        </form>
      </section>
      <section class="split-grid">
        <section class="panel">
          <div class="panel-header"><div><h3>Journal Register</h3><p class="subtle">Most recent entries first. Select one to inspect its lines.</p></div></div>
          <div class="table-wrap"><table><thead><tr><th>Entry</th><th>Date</th><th>Source</th><th>Memo</th><th>Amount</th><th>Action</th></tr></thead><tbody id="journalBody"></tbody></table></div>
        </section>
        <section class="panel">
          <div class="panel-header"><div><h3>Entry Detail</h3><p id="selectedJournalLabel" class="subtle">Select an entry from the register.</p></div></div>
          <div class="table-wrap"><table><thead><tr><th>Account</th><th>Description</th><th>Debit</th><th>Credit</th></tr></thead><tbody id="journalLinesBody"><tr><td colspan="4">No entry selected.</td></tr></tbody></table></div>
          <div class="form-actions"><button type="button" id="reverseJournalBtn" class="ghost-button" disabled>Reverse This Entry</button></div>
        </section>
      </section>
    </section>`;
}

function reportsView() {
  return `
    <section class="view-stack">
      <section class="panel">
        <div class="panel-header"><div><h3>Trial Balance</h3><p class="subtle">Every account's net movement. Debit and credit columns must total to the same figure.</p></div></div>
        <div class="toolbar"><label><span>As Of</span><input id="tbAsOf" type="date"></label><button type="button" id="runTrialBalanceBtn">Run</button><span id="tbStatus" class="subtle"></span></div>
        <div class="table-wrap"><table><thead><tr><th>Code</th><th>Account</th><th>Debit</th><th>Credit</th></tr></thead><tbody id="trialBalanceBody"><tr><td colspan="4">Run the report to see figures.</td></tr></tbody></table></div>
      </section>
      <section class="panel">
        <div class="panel-header"><div><h3>Profit &amp; Loss</h3><p class="subtle">Income, cost of goods sold, and operating expenses for a date range.</p></div></div>
        <div class="toolbar"><label><span>Start</span><input id="plStart" type="date"></label><label><span>End</span><input id="plEnd" type="date"></label><button type="button" id="runProfitLossBtn">Run</button></div>
        <div class="mini-grid" id="plSummary"></div>
        <div class="table-wrap"><table><thead><tr><th>Code</th><th>Account</th><th>Amount</th></tr></thead><tbody id="profitLossBody"><tr><td colspan="3">Run the report to see figures.</td></tr></tbody></table></div>
      </section>
      <section class="panel">
        <div class="panel-header"><div><h3>Balance Sheet</h3><p class="subtle">Assets, liabilities, and equity as of a chosen date.</p></div></div>
        <div class="toolbar"><label><span>As Of</span><input id="bsAsOf" type="date"></label><button type="button" id="runBalanceSheetBtn">Run</button><span id="bsStatus" class="subtle"></span></div>
        <div class="mini-grid" id="bsSummary"></div>
        <div class="table-wrap"><table><thead><tr><th>Code</th><th>Account</th><th>Amount</th></tr></thead><tbody id="balanceSheetBody"><tr><td colspan="3">Run the report to see figures.</td></tr></tbody></table></div>
      </section>
      <section class="panel">
        <div class="panel-header"><div><h3>Accounts Receivable Aging</h3><p class="subtle">Outstanding invoice balances by client, bucketed by days overdue.</p></div></div>
        <div class="toolbar"><button type="button" id="runArAgingBtn">Run</button><span id="arAgingAsOf" class="subtle"></span></div>
        <div class="table-wrap"><table><thead><tr><th>Client</th><th>Not Yet Due</th><th>1-30 Days</th><th>31-60 Days</th><th>61-90 Days</th><th>90+ Days</th><th>Total</th></tr></thead><tbody id="arAgingBody"><tr><td colspan="7">Run the report to see figures.</td></tr></tbody></table></div>
      </section>
      <section class="panel">
        <div class="panel-header"><div><h3>Accounts Payable Aging</h3><p class="subtle">Outstanding, unsettled bills by vendor, bucketed by age.</p></div></div>
        <div class="toolbar"><button type="button" id="runApAgingBtn">Run</button><span id="apAgingAsOf" class="subtle"></span></div>
        <div class="table-wrap"><table><thead><tr><th>Vendor</th><th>0-30 Days</th><th>31-60 Days</th><th>61-90 Days</th><th>90+ Days</th><th>Total</th></tr></thead><tbody id="apAgingBody"><tr><td colspan="6">Run the report to see figures.</td></tr></tbody></table></div>
      </section>
      <section class="panel">
        <div class="panel-header"><div><h3>Client Statement of Accounts</h3><p class="subtle">Every outstanding invoice for one client, ready to review or email.</p></div></div>
        <div class="toolbar"><label><span>Client</span><select id="statementClientId"></select></label><button type="button" id="viewStatementBtn">View</button><button type="button" id="sendStatementBtn" class="ghost-button">Send Statement</button><span id="statementSendStatus" class="subtle"></span></div>
        <div class="table-wrap"><table><thead><tr><th>Invoice</th><th>Issue Date</th><th>Due Date</th><th>Amount</th><th>Paid</th><th>Balance</th><th>Status</th></tr></thead><tbody id="statementBody"><tr><td colspan="7">Select a client and click View.</td></tr></tbody></table></div>
        <p id="statementTotal" class="subtle"></p>
      </section>
    </section>`;
}

const pageViews = {
  dashboard: dashboardView,
  clients: () => entityPage("Client", "Capture commercial information and credit settings. Different brokers name and number their paperwork differently -- set that up here so documents match what their AP team expects.", "clientForm", `<label><span>Name</span><input name="name" required></label><label><span>Contact Person</span><input name="contact_person"></label><label><span>Phone</span><input name="phone"></label><label><span>Email</span><input name="email" type="email"></label><label><span>Booking Email</span><input name="booking_email" type="email"></label><label><span>Invoice Email</span><input name="invoice_email" type="email"></label><label><span>Loading Order Email</span><input name="loading_order_email" type="email"></label><label><span>Statement of Accounts Email</span><input name="statement_email" type="email"></label><label class="span-2"><span>Address</span><input name="address"></label><label><span>TIN</span><input name="tin"></label><label><span>Currency</span><input name="currency" value="TZS"></label><label><span>Credit Days</span><input name="credit_days" type="number" value="30"></label><label><span>What This Client Calls Their Dispatch Order</span><input name="document_label" value="Loading Order" placeholder="e.g. Loading Order, Transport Order, Pre-Alert"></label><label><span>Invoice Number Format (optional)</span><input name="invoice_number_format" placeholder="e.g. POL/{stage}/{yy}/{mm}/{seq:04d}"></label>`, "clientsBody", ["Name", "Contact", "Document Label", "Invoice Format", "Booking Email", "Invoice Email", "Currency", "Credit Days", "Status", "Actions"]),
  trucks: trucksView,
  assignments: assignmentsView,
  drivers: () => entityPage("Driver", "Capture driver identity, employment, license, emergency, referee, and document details.", "driverForm", `<label><span>First Name</span><input name="first_name" required></label><label><span>Middle Name</span><input name="middle_name"></label><label><span>Last Name</span><input name="last_name" required></label><label><span>Phone</span><input name="phone"></label><label><span>National ID Number</span><input name="national_id_no"></label><label><span>Passport Number</span><input name="passport_no"></label><label><span>Date of Birth</span><input name="date_of_birth" type="date"></label><label><span>Sex</span><select name="sex"><option value="">Select sex</option><option value="male">male</option><option value="female">female</option></select></label><label><span>Date of Employment</span><input name="date_of_employment" type="date"></label><label class="span-2"><span>Home Address</span><input name="home_address"></label><div class="form-section-title span-2">Emergency Contact Information</div><label><span>Emergency Contact Name</span><input name="emergency_contact_name"></label><label><span>Relationship</span><input name="emergency_contact_relationship"></label><label><span>Emergency Contact Phone</span><input name="emergency_contact_phone"></label><div class="form-section-title span-2">Referee 1</div><label><span>Referee 1 First Name</span><input name="referee1_first_name"></label><label><span>Referee 1 Middle Name</span><input name="referee1_middle_name"></label><label><span>Referee 1 Surname</span><input name="referee1_last_name"></label><label><span>Referee 1 Telephone Number</span><input name="referee1_phone"></label><div class="form-section-title span-2">Referee 2</div><label><span>Referee 2 First Name</span><input name="referee2_first_name"></label><label><span>Referee 2 Middle Name</span><input name="referee2_middle_name"></label><label><span>Referee 2 Surname</span><input name="referee2_last_name"></label><label><span>Referee 2 Telephone Number</span><input name="referee2_phone"></label><div class="form-section-title span-2">License Information</div><label><span>License No</span><input name="license_no" required></label><label><span>License Class</span><input name="license_class" value="CE"></label><label><span>License Expiry</span><input name="license_expiry" type="date" required></label><label><span>GCLA Certificate</span><input name="gcla_certificate_no"></label><label><span>Status</span><select name="status"><option value="available">available</option><option value="assigned">assigned</option><option value="off_duty">off_duty</option></select></label><div class="form-section-title span-2">Document Uploads</div><label><span>Passport Copy</span><input name="passport_copy" type="file" accept='.pdf,.jpg,.jpeg,.png,.webp'></label><label><span>Photo</span><input name="photo" type="file" accept='.jpg,.jpeg,.png,.webp'></label><label><span>License Copy</span><input name="license_copy" type="file" accept='.pdf,.jpg,.jpeg,.png,.webp'></label><label><span>GCLA Certificate Copy</span><input name="gcla_certificate_copy" type="file" accept='.pdf,.jpg,.jpeg,.png,.webp'></label>`, "driversBody", ["Name", "National ID", "GCLA", "License", "License Expiry", "Docs", "Status", "Actions"]),
  routes: routesView,
  vendors: () => entityPage("Vendor", "Suppliers and workshops billed on account -- link them to trip expenses and maintenance jobs to track what's owed and settle it later.", "vendorForm", `<label><span>Name</span><input name="name" required></label><label><span>Contact Person</span><input name="contact_person"></label><label><span>Phone</span><input name="phone"></label><label><span>Email</span><input name="email" type="email"></label><label><span>TIN</span><input name="tin"></label><label class="span-2"><span>Address</span><input name="address"></label>`, "vendorsBody", ["Name", "Contact", "Phone", "Email", "TIN", "Status", "Actions"]),
  bookings: bookingsView,
  trips: tripsView,
  invoices: invoicesView,
  maintenance: () => entityPage("Maintenance", "Track workshop jobs and service planning.", "maintenanceForm", `<label><span>Vehicle</span><select id="maintenanceVehicleId" name="vehicle_id" required></select></label><label><span>Maintenance Type</span><input name="maintenance_type" required></label><label><span>Service Provider</span><input name="service_provider"></label><label><span>Cost</span><input name="cost" type="number" step="0.01" value="0"></label><label><span>Payment Source</span><select name="payment_source"><option value="payable">On Account (Accounts Payable)</option><option value="cash">Cash on Hand</option><option value="bank">Bank</option></select></label><label><span>Vendor (if on account)</span><select id="maintenanceVendorId" name="vendor_id"></select></label><label><span>GL Account (optional override)</span><select id="maintenanceGlAccount" name="gl_account_code"><option value="">Auto-detect from maintenance type</option></select></label><label><span>Date In</span><input name="date_in" type="date" required></label><label><span>Date Out</span><input name="date_out" type="date"></label><label><span>Next Service Due</span><input name="next_service_due" type="date"></label><label><span>Status</span><select name="status"><option value="open">open</option><option value="closed">closed</option></select></label><label class="span-2"><span>Description</span><input name="description"></label>`, "maintenanceBody", ["Vehicle", "Type", "Vendor", "Status", "Cost", "Settled", "Actions"]),
  users: () => entityPage("User", "Create internal users and manage which of the four user groups (admin, accountant, operations, viewer) they belong to. This page is only visible to admins.", "userForm", `<label><span>Username</span><input name="username" required></label><label><span>Full Name</span><input name="full_name" required></label><label><span>Email</span><input name="email" type="email"></label><label id="userPasswordField"><span>Password</span><input name="password" type="password" required minlength="6"></label><label><span>Role</span><select name="role"><option value="operations">operations</option><option value="accountant">accountant</option><option value="admin">admin</option><option value="viewer">viewer</option></select></label>`, "usersBody", ["Username", "Full Name", "Email", "Role", "Status", "Actions"]),
  accounts: accountsView,
  journal: journalView,
  reports: reportsView,
};

function renderView() {
  pageTitle.textContent = pageLabels[state.currentPage];
  loginPanel.classList.toggle("hidden", Boolean(state.token));
  location.hash = state.currentPage;
  viewRoot.innerHTML = pageViews[state.currentPage]();
  buildNav();
  bindDynamicForms();
  renderData();
  if (state.token && state.currentPage === "journal") {
    ensureJournalFormReady();
    loadJournal().then(renderJournalDetail).catch((error) => setFlash(error.message, "error"));
  }
  if (state.token && state.currentPage === "accounts") {
    loadLedgerSettings().catch((error) => setFlash(error.message, "error"));
    loadAccountLedger(state.selectedLedgerAccountCode);
  }
}

function setFlash(message, type = "") { flash.textContent = message; flash.className = type ? `flash ${type}` : "flash"; }
function setSessionStatus() {
  sessionStatus.textContent = state.token ? `Signed in as ${state.me ? state.me.username : "..."}` : "Not signed in";
  const roleLine = document.getElementById("sessionRole");
  if (roleLine) {
    setElementVisible(roleLine, Boolean(state.token && state.me));
    if (state.me) roleLine.textContent = `Role: ${state.me.role}`;
  }
  setElementVisible(document.getElementById("changePasswordCard"), Boolean(state.token));
}
function money(v, c = "TZS") { return `${c} ${Number(v || 0).toLocaleString()}`; }
function when(v) { return v ? String(v).replace("T", " ").slice(0, 16) : "-"; }

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!options.skipJson) headers["Content-Type"] = "application/json";
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { const data = await response.json(); message = data.detail || JSON.stringify(data); } catch { message = await response.text(); }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function formPayload(form) {
  const payload = {};
  new FormData(form).forEach((value, key) => {
    if (key.startsWith("_")) return; // internal UI bookkeeping fields (e.g. the edit-mode record id), never sent to the API
    if (value === "" && !booleanFields.has(key)) return;
    payload[key] = booleanFields.has(key) ? form.querySelector(`[name="${key}"]`).checked : (numberFields.has(key) ? Number(value) : value);
  });
  form.querySelectorAll('input[type="checkbox"]').forEach((box) => { if (!(box.name in payload)) payload[box.name] = box.checked; });
  return payload;
}

// --- Generic create/edit form support -------------------------------------
// Several registers (clients, vehicles, drivers, routes) only ever supported
// creating a new record -- there was no way to fix a typo or update a detail
// without editing the database directly. This lets any of those forms be
// reused in "edit" mode: a hidden record id field switches bindForm (and the
// vehicle/driver custom submit handlers) from POST-create to PUT-update.
function setFormEditState(form, isEditing) {
  if (!form) return;
  const submitBtn = form.querySelector('button[type="submit"]');
  const cancelBtn = form.querySelector("[data-cancel-edit]");
  if (submitBtn) {
    if (!submitBtn.dataset.defaultLabel) submitBtn.dataset.defaultLabel = submitBtn.textContent;
    submitBtn.textContent = isEditing ? "Update" : submitBtn.dataset.defaultLabel;
  }
  if (cancelBtn) cancelBtn.classList.toggle("hidden", !isEditing);
}

function startEntityEdit(formId, record, fieldNames) {
  const form = document.getElementById(formId);
  if (!form) return;
  const editIdField = form.querySelector("[data-edit-id-field]");
  if (editIdField) editIdField.value = record.id;
  fieldNames.forEach((name) => {
    const el = form.elements.namedItem(name);
    if (!el) return;
    const value = record[name];
    if (el.type === "checkbox") el.checked = Boolean(value);
    else el.value = value === null || value === undefined ? "" : value;
    el.dispatchEvent(new Event("change"));
  });
  setFormEditState(form, true);
  form.scrollIntoView({ behavior: "smooth", block: "start" });
}

function cancelEntityEdit(form) {
  if (!form) return;
  const editIdField = form.querySelector("[data-edit-id-field]");
  if (editIdField) editIdField.value = "";
  form.reset();
  setFormEditState(form, false);
  // Users don't set a new password through the generic edit flow (that's a
  // separate admin-only Reset Password action) -- restore the password
  // field once editing ends so a fresh "create user" has it back.
  if (form.id === "userForm") {
    const pwField = document.getElementById("userPasswordField");
    if (pwField) {
      pwField.classList.remove("hidden");
      const input = pwField.querySelector("input");
      if (input) input.required = true;
    }
  }
}

function complianceStatus(expiryDateStr) {
  if (!expiryDateStr) return { label: "Not set", cls: "not-required" };
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const expiry = new Date(expiryDateStr);
  const days = Math.floor((expiry - today) / 86400000);
  if (days < 0) return { label: `Expired ${expiryDateStr}`, cls: "expired" };
  if (days <= 30) return { label: `Due ${expiryDateStr}`, cls: "pending" };
  return { label: expiryDateStr, cls: "complete" };
}

function complianceBadge(label, expiryDateStr) {
  const s = complianceStatus(expiryDateStr);
  return `<span class="status-pill ${s.cls}" title="${label}: ${s.label}">${label}</span>`;
}

function vehicleComplianceCell(v) {
  const badges = [
    v.insurance_expiry ? complianceBadge("Insurance", v.insurance_expiry) : "",
    v.road_license_expiry ? complianceBadge("Road License", v.road_license_expiry) : "",
    v.c28_expiry ? complianceBadge("C28", v.c28_expiry) : "",
  ].filter(Boolean).join(" ");
  return badges || "-";
}

function fillSelect(id, items, label, blank = false) {
  const node = document.getElementById(id);
  if (!node) return;
  node.innerHTML = `${blank ? `<option value="">None</option>` : ""}${items.map((item) => `<option value="${item.id}">${label(item)}</option>`).join("")}`;
}

function confirmAction(message) {
  return window.confirm(message);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getTyreLayoutConfig(vehicleType, tyreLayout) {
  return tyreLayoutConfigs[vehicleType]?.[tyreLayout] || null;
}

function getTyrePositions(config) {
  return config.rows.flatMap((row) => [...row.left, ...row.right]);
}

function parseTyreInfo(raw) {
  if (!raw) return null;
  if (typeof raw === "object") return raw;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function getTyrePositionMap(raw) {
  const info = parseTyreInfo(raw);
  return new Map((info?.positions || []).map((position) => [position.position_code, position]));
}

function getTyreCaptureNodes(scope) {
  if (scope === "workspace") {
    return {
      field: document.getElementById("tyreWorkspaceField"),
      board: document.getElementById("tyreWorkspaceBoard"),
      cards: document.getElementById("tyreWorkspaceCards"),
      hiddenInput: null,
      empty: document.getElementById("vehicleTyreWorkspaceEmpty"),
    };
  }
  return {
    field: document.getElementById("tyreCaptureField"),
    board: document.getElementById("tyreCaptureBoard"),
    cards: document.getElementById("tyreCaptureCards"),
    hiddenInput: document.getElementById("tyreInfoJson"),
    empty: null,
  };
}

function getVehicleTyreStatus(vehicle) {
  const config = getTyreLayoutConfig(vehicle.vehicle_type, vehicle.tyre_layout);
  if (!config) return { applicable: false, status: "not-required", label: "Not required", complete: true, completed: 0, total: 0 };
  const positions = getTyrePositions(config);
  const tyreMap = getTyrePositionMap(vehicle.tyre_info_json);
  let completed = 0;
  positions.forEach((position) => {
    const entry = tyreMap.get(position.key) || {};
    const filledCount = tyreInfoFields.filter((field) => String(entry[field] || "").trim()).length;
    if (filledCount === tyreInfoFields.length) completed += 1;
  });
  const total = positions.length;
  const complete = completed === total;
  return {
    applicable: true,
    status: complete ? "complete" : "pending",
    label: complete ? `Complete (${completed}/${total})` : `Pending (${completed}/${total})`,
    complete,
    completed,
    total,
  };
}

function buildTyreBoard(config) {
  return `
    <section class="tyre-board-panel">
      <header class="tyre-board-header">
        <p class="kicker">${config.title}</p>
        <h3>${config.subtitle}</h3>
        <p class="subtle">Front of ${config.unitLabel}</p>
      </header>
      <div class="tyre-arrow">&uarr;</div>
      <div class="tyre-rows">
        ${config.rows.map((row) => `
          <div class="tyre-row">
            <div class="tyre-wheel-group left">
              ${row.left.map((position) => `<span class="tyre-wheel-chip">${position.short}</span>`).join("")}
            </div>
            <div class="tyre-axle">
              <span class="tyre-axle-label">${row.axle}</span>
              <span class="tyre-axle-line"></span>
            </div>
            <div class="tyre-wheel-group right">
              ${row.right.map((position) => `<span class="tyre-wheel-chip">${position.short}</span>`).join("")}
            </div>
          </div>
        `).join("")}
      </div>
      <footer class="tyre-board-legend">
        <span><strong>I</strong> = Inner</span>
        <span><strong>O</strong> = Outer</span>
        <span><strong>L</strong> = Left</span>
        <span><strong>R</strong> = Right</span>
        </footer>
      </section>`;
}

function buildTyreCards(config, scope, raw = null) {
  const positions = getTyrePositions(config);
  const tyreMap = getTyrePositionMap(raw);
  return positions.map((position) => `
    <article class="tyre-card">
      <div class="tyre-card-head">
        <strong>${position.short}</strong>
        <span>${position.label}</span>
      </div>
      <div class="tyre-card-grid">
        <label><span>Date of Installation</span><input type="date" data-tyre-scope="${scope}" data-tyre-position="${position.key}" data-tyre-field="date_of_installation" value="${escapeHtml(tyreMap.get(position.key)?.date_of_installation || "")}"></label>
        <label><span>Mileage at Installation (KM)</span><input type="number" step="0.1" min="0" data-tyre-scope="${scope}" data-tyre-position="${position.key}" data-tyre-field="mileage_at_installation_km" value="${escapeHtml(tyreMap.get(position.key)?.mileage_at_installation_km || "")}"></label>
        <label><span>Brand</span><input data-tyre-scope="${scope}" data-tyre-position="${position.key}" data-tyre-field="brand" value="${escapeHtml(tyreMap.get(position.key)?.brand || "")}"></label>
        <label><span>Serial Number</span><input data-tyre-scope="${scope}" data-tyre-position="${position.key}" data-tyre-field="serial_number" value="${escapeHtml(tyreMap.get(position.key)?.serial_number || "")}"></label>
      </div>
    </article>`).join("");
}

function renderTyreCapture(scope, vehicleType, tyreLayout, raw = null) {
  const { field, board, cards, hiddenInput, empty } = getTyreCaptureNodes(scope);
  const config = getTyreLayoutConfig(vehicleType, tyreLayout);

  if (!field || !board || !cards) return;

  if (!config) {
    field.classList.add("hidden");
    board.innerHTML = "";
    cards.innerHTML = "";
    if (hiddenInput) hiddenInput.value = "";
    if (empty) empty.classList.remove("hidden");
    return;
  }

  field.classList.remove("hidden");
  board.innerHTML = buildTyreBoard(config);
  cards.innerHTML = buildTyreCards(config, scope, raw);
  if (hiddenInput) hiddenInput.value = raw && typeof raw === "string" ? raw : "";
  if (empty) empty.classList.add("hidden");
}

function serializeTyreInfo(scope, vehicleType, tyreLayout) {
  const { hiddenInput } = getTyreCaptureNodes(scope);
  const config = getTyreLayoutConfig(vehicleType, tyreLayout);
  if (!config) {
    if (hiddenInput) hiddenInput.value = "";
    return { json: "", hasAny: false, isComplete: true, completed: 0, total: 0 };
  }

  let completed = 0;
  const positions = getTyrePositions(config).map((position) => {
    const entry = { position_code: position.key, position_label: position.label };
    let filledCount = 0;
    tyreInfoFields.forEach((field) => {
      const input = document.querySelector(`[data-tyre-scope="${scope}"][data-tyre-position="${position.key}"][data-tyre-field="${field}"]`);
      const value = input?.value?.trim() || "";
      entry[field] = value;
      if (value) filledCount += 1;
    });
    if (filledCount === tyreInfoFields.length) completed += 1;
    entry._filledCount = filledCount;
    return entry;
  });

  const hasAny = positions.some((position) => position._filledCount > 0);
  const total = positions.length;
  const isComplete = total > 0 && completed === total;
  const payload = JSON.stringify({
    vehicle_type: vehicleType,
    tyre_layout: tyreLayout,
    layout_label: config.label,
    positions: positions.map(({ _filledCount, ...position }) => position),
  });
  if (hiddenInput) hiddenInput.value = hasAny ? payload : "";
  return { json: hasAny ? payload : "", hasAny, isComplete, completed, total };
}

function rows(id, html, colspan) {
  const node = document.getElementById(id);
  if (node) node.innerHTML = html || `<tr><td colspan="${colspan}">No records found.</td></tr>`;
}

function renderVehicleTyreNotice() {
  const notice = document.getElementById("vehicleTyreNotice");
  const list = document.getElementById("vehicleTyrePendingList");
  if (!notice || !list) return;
  const pendingVehicles = state.data.vehicles.filter((vehicle) => getTyreLayoutConfig(vehicle.vehicle_type, vehicle.tyre_layout) && !getVehicleTyreStatus(vehicle).complete);
  if (!pendingVehicles.length) {
    notice.classList.add("hidden");
    notice.textContent = "";
    list.innerHTML = "";
    return;
  }
  notice.classList.remove("hidden");
  notice.textContent = pendingVehicles.length === 1
    ? `1 vehicle still needs tyre position information.`
    : `${pendingVehicles.length} vehicles still need tyre position information.`;
  list.innerHTML = pendingVehicles.map((vehicle) => {
    const status = getVehicleTyreStatus(vehicle);
    return `<button type="button" class="pending-chip" data-vehicle-tyre="${vehicle.id}">${vehicle.registration_no} | ${vehicle.tyre_layout} | ${status.label}</button>`;
  }).join("");
}

function renderVehicleTyreWorkspace() {
  const label = document.getElementById("selectedVehicleTyreLabel");
  const empty = document.getElementById("vehicleTyreWorkspaceEmpty");
  const selectedVehicle = state.data.vehicles.find((vehicle) => vehicle.id === state.selectedVehicleTyreId);
  if (!label || !empty) return;
  if (!selectedVehicle || !getTyreLayoutConfig(selectedVehicle.vehicle_type, selectedVehicle.tyre_layout)) {
    label.textContent = "Select a trailer or dangler to complete tyre position details.";
    renderTyreCapture("workspace", "", "", null);
    empty.classList.remove("hidden");
    return;
  }
  const status = getVehicleTyreStatus(selectedVehicle);
  label.textContent = `${selectedVehicle.registration_no} | ${selectedVehicle.vehicle_type} | ${selectedVehicle.tyre_layout} | ${status.label}`;
  renderTyreCapture("workspace", selectedVehicle.vehicle_type, selectedVehicle.tyre_layout, selectedVehicle.tyre_info_json);
}

function setInvoice(id) {
  state.selectedInvoiceId = id || null;
  const invoice = state.data.invoices.find((item) => item.id === id);
  const label = document.getElementById("selectedInvoiceLabel");
  const select = document.getElementById("paymentInvoiceId");
  if (select && id) select.value = id;
  if (label) label.textContent = invoice ? `Selected invoice ${invoice.invoice_number} (${invoice.status})` : "Select an invoice from the table.";
}

function setBooking(id) {
  state.selectedBookingId = id || null;
  const select = document.getElementById("tripBooking");
  if (select) select.value = id ? String(id) : "";
}

function isActiveTrip(trip) {
  return trip.status !== "completed";
}

function getActiveTripUsage() {
  const usage = {
    tractors: new Set(),
    trailers: new Set(),
    danglers: new Set(),
    drivers: new Set(),
  };
  state.data.trips.filter(isActiveTrip).forEach((trip) => {
    if (trip.tractor_id) usage.tractors.add(trip.tractor_id);
    if (trip.trailer_id) usage.trailers.add(trip.trailer_id);
    if (trip.dangler_id) usage.danglers.add(trip.dangler_id);
    if (trip.driver_id) usage.drivers.add(trip.driver_id);
  });
  return usage;
}

function assignmentTouchesActiveTrip(assignment, activeUsage = getActiveTripUsage()) {
  return activeUsage.tractors.has(assignment.tractor_id)
    || (assignment.trailer_id ? activeUsage.trailers.has(assignment.trailer_id) : false)
    || (assignment.dangler_id ? activeUsage.danglers.has(assignment.dangler_id) : false)
    || (assignment.driver_id ? activeUsage.drivers.has(assignment.driver_id) : false);
}

function getActiveAssignmentMap(fieldName) {
  const map = new Map();
  state.data.assignments.filter((item) => item.status === "active" && item[fieldName]).forEach((item) => {
    map.set(item[fieldName], item);
  });
  return map;
}

function syncAssignmentSelectors() {
  const form = document.getElementById("assignmentForm");
  if (!form) return;

  const allowReassignment = Boolean(document.getElementById("assignmentAllowReassignment")?.checked);
  const tractorSelect = document.getElementById("assignmentTractor");
  const driverSelect = document.getElementById("assignmentDriver");
  const trailerSelect = document.getElementById("assignmentTrailer");
  const danglerSelect = document.getElementById("assignmentDangler");
  if (!tractorSelect || !driverSelect || !trailerSelect || !danglerSelect) return;

  const currentTractorId = Number(tractorSelect.value || 0);
  const currentAssignment = state.data.assignments.find((item) => item.tractor_id === currentTractorId) || null;
  const activeTrips = getActiveTripUsage();
  const tractorAssignments = new Map(state.data.assignments.filter((item) => item.status === "active").map((item) => [item.tractor_id, item]));
  const trailerAssignments = getActiveAssignmentMap("trailer_id");
  const danglerAssignments = getActiveAssignmentMap("dangler_id");
  const driverAssignments = getActiveAssignmentMap("driver_id");

  const freeTractors = state.data.vehicles.filter((item) => item.vehicle_type === "tractor" && !activeTrips.tractors.has(item.id) && !tractorAssignments.has(item.id));
  const reassignableTractors = state.data.vehicles.filter((item) => item.vehicle_type === "tractor" && !activeTrips.tractors.has(item.id) && tractorAssignments.has(item.id));
  const tractorOptions = [...freeTractors, ...(allowReassignment ? reassignableTractors : [])];
  if (currentTractorId) {
    const currentTractor = state.data.vehicles.find((item) => item.id === currentTractorId);
    if (currentTractor && !tractorOptions.some((item) => item.id === currentTractorId)) tractorOptions.unshift(currentTractor);
  }
  fillSelect("assignmentTractor", tractorOptions, (item) => {
    const tag = tractorAssignments.has(item.id) ? "reassignable" : "free";
    return `${item.registration_no} (${tag})`;
  });
  if (currentTractorId) tractorSelect.value = String(currentTractorId);

  const selectedAssignment = state.data.assignments.find((item) => item.tractor_id === Number(tractorSelect.value || 0)) || null;
  if (selectedAssignment) {
    if (selectedAssignment.driver_id) driverSelect.value = String(selectedAssignment.driver_id);
    if (selectedAssignment.trailer_id) trailerSelect.value = String(selectedAssignment.trailer_id);
    if (selectedAssignment.dangler_id) danglerSelect.value = String(selectedAssignment.dangler_id);
  }

  const filterVehicles = (vehicleType, activeSet, assignmentMap, selectedId = 0) => state.data.vehicles.filter((item) => {
    if (item.vehicle_type !== vehicleType) return false;
    if (activeSet.has(item.id)) return false;
    const assignedElsewhere = assignmentMap.get(item.id);
    if (!assignedElsewhere) return true;
    if (selectedAssignment && assignedElsewhere.id === selectedAssignment.id) return true;
    return allowReassignment;
  });

  const filterDrivers = (selectedId = 0) => state.data.drivers.filter((item) => {
    if (activeTrips.drivers.has(item.id)) return false;
    const assignedElsewhere = driverAssignments.get(item.id);
    if (!assignedElsewhere) return true;
    if (selectedAssignment && assignedElsewhere.id === selectedAssignment.id) return true;
    return allowReassignment;
  });

  const currentDriverId = Number(driverSelect.value || selectedAssignment?.driver_id || 0);
  const currentTrailerId = Number(trailerSelect.value || selectedAssignment?.trailer_id || 0);
  const currentDanglerId = Number(danglerSelect.value || selectedAssignment?.dangler_id || 0);

  fillSelect("assignmentDriver", filterDrivers(currentDriverId), (item) => {
    const assigned = driverAssignments.get(item.id);
    return `${item.full_name} (${assigned && (!selectedAssignment || assigned.id !== selectedAssignment.id) ? "reassignable" : "free"})`;
  }, true);
  fillSelect("assignmentTrailer", filterVehicles("trailer", activeTrips.trailers, trailerAssignments, currentTrailerId), (item) => {
    const assigned = trailerAssignments.get(item.id);
    return `${item.registration_no} (${assigned && (!selectedAssignment || assigned.id !== selectedAssignment.id) ? "reassignable" : "free"})`;
  }, true);
  fillSelect("assignmentDangler", filterVehicles("dangler", activeTrips.danglers, danglerAssignments, currentDanglerId), (item) => {
    const assigned = danglerAssignments.get(item.id);
    return `${item.registration_no} (${assigned && (!selectedAssignment || assigned.id !== selectedAssignment.id) ? "reassignable" : "free"})`;
  }, true);

  if (currentDriverId) driverSelect.value = String(currentDriverId);
  if (currentTrailerId) trailerSelect.value = String(currentTrailerId);
  if (currentDanglerId) danglerSelect.value = String(currentDanglerId);
}

function populateSelectors() {
  const acceptedBookings = state.data.bookings.filter((i) => i.status === "accepted" || i.id === state.selectedBookingId);
  fillSelect("bookingClient", state.data.clients, (i) => i.name);
  fillSelect("bookingRoute", state.data.routes, (i) => i.route_name);
  fillSelect("bookingVehicle", state.data.vehicles.filter((i) => i.vehicle_type === "tractor"), (i) => `${i.registration_no} (${i.status})`);
  fillSelect("tripBooking", acceptedBookings, (i) => {
    const client = state.data.clients.find((item) => item.id === i.client_id)?.name || i.client_id;
    return `${i.booking_number} | ${client} | ${i.cargo_type}`;
  }, true);
  fillSelect("tripClient", state.data.clients, (i) => i.name);
  fillSelect("tripRoute", state.data.routes, (i) => i.route_name);
  fillSelect("tripVehicle", state.data.vehicles.filter((i) => i.vehicle_type === "tractor"), (i) => `${i.registration_no} (${i.status})`);
  fillSelect("tripTrailer", state.data.vehicles.filter((i) => i.vehicle_type === "trailer"), (i) => i.registration_no, true);
  fillSelect("tripDangler", state.data.vehicles.filter((i) => i.vehicle_type === "dangler"), (i) => i.registration_no, true);
  fillSelect("tripDriver", state.data.drivers, (i) => `${i.full_name} (${i.status})`);
  if (state.selectedBookingId) setBooking(state.selectedBookingId);
  syncAssignmentSelectors();
  fillSelect("paymentInvoiceId", state.data.invoices, (i) => `${i.invoice_number} - ${i.status}`, true);
  fillSelect("maintenanceVehicleId", state.data.vehicles, (i) => i.registration_no);
  const activeVendors = state.data.vendors.filter((v) => v.is_active);
  fillSelect("tripExpenseVendorId", activeVendors, (i) => i.name, true);
  fillSelect("maintenanceVendorId", activeVendors, (i) => i.name, true);
  fillSelect("statementClientId", state.data.clients, (i) => i.name);
  syncTripBooking();
  syncTripAssignment();
}

function syncTripBooking() {
  const bookingSelect = document.getElementById("tripBooking");
  const clientSelect = document.getElementById("tripClient");
  const routeSelect = document.getElementById("tripRoute");
  const tractorSelect = document.getElementById("tripVehicle");
  const cargoTypeSelect = document.getElementById("tripCargoType");
  const revenueInput = document.getElementById("tripRevenueInput");
  const currencyInput = document.querySelector('#tripForm input[name="currency"]');
  if (!bookingSelect || !clientSelect || !routeSelect || !tractorSelect || !cargoTypeSelect || !revenueInput || !currencyInput) return;
  const bookingId = Number(bookingSelect.value || 0);
  if (!bookingId) return;
  const booking = state.data.bookings.find((item) => item.id === bookingId);
  if (!booking) return;
  clientSelect.value = String(booking.client_id);
  routeSelect.value = String(booking.route_id);
  tractorSelect.value = String(booking.tractor_id);
  cargoTypeSelect.value = booking.cargo_type;
  revenueInput.value = String(booking.rate);
  currencyInput.value = booking.currency || "TZS";
}

function syncTripAssignment() {
  const tractorSelect = document.getElementById("tripVehicle");
  const trailerSelect = document.getElementById("tripTrailer");
  const danglerSelect = document.getElementById("tripDangler");
  const driverSelect = document.getElementById("tripDriver");
  const notice = document.getElementById("tripAssignmentNotice");
  if (!tractorSelect || !trailerSelect || !danglerSelect || !driverSelect) return;
  const tractorId = Number(tractorSelect.value || 0);
  if (!tractorId) {
    trailerSelect.value = "";
    danglerSelect.value = "";
    driverSelect.value = "";
    trailerSelect.disabled = false;
    danglerSelect.disabled = false;
    driverSelect.disabled = false;
    if (notice) notice.textContent = "Select a tractor to load its assignment.";
    return;
  }
  const assignment = state.data.assignments.find((item) => item.tractor_id === tractorId && item.status === "active");
  if (!assignment) {
    trailerSelect.value = "";
    danglerSelect.value = "";
    driverSelect.value = "";
    trailerSelect.disabled = false;
    danglerSelect.disabled = false;
    driverSelect.disabled = false;
    if (notice) notice.textContent = "No active assignment found for this tractor. You can choose driver, trailer, and dangler manually.";
    return;
  }

  trailerSelect.value = assignment.trailer_id ? String(assignment.trailer_id) : "";
  danglerSelect.value = assignment.dangler_id ? String(assignment.dangler_id) : "";
  driverSelect.value = assignment.driver_id ? String(assignment.driver_id) : "";
  trailerSelect.disabled = true;
  danglerSelect.disabled = true;
  driverSelect.disabled = true;

  const missing = [
    assignment.driver_id ? "" : "driver",
    assignment.trailer_id ? "" : "trailer",
  ].filter(Boolean);
  if (notice) {
    notice.textContent = missing.length
      ? `Active assignment loaded for this tractor. Locked fields cannot be changed here. Complete the missing ${missing.join(" and ")} in Assignments before creating the trip.`
      : "Active assignment loaded for this tractor. Driver, trailer, and dangler are locked here. Update the Assignments page to make changes.";
  }
}

function getAssignmentConflictMessage() {
  const tractorId = Number(document.getElementById("assignmentTractor")?.value || 0);
  const trailerId = Number(document.getElementById("assignmentTrailer")?.value || 0);
  const danglerId = Number(document.getElementById("assignmentDangler")?.value || 0);
  const driverId = Number(document.getElementById("assignmentDriver")?.value || 0);
  const allowReassignment = Boolean(document.getElementById("assignmentAllowReassignment")?.checked);
  if (!tractorId) return "";
  const currentAssignment = state.data.assignments.find((item) => item.tractor_id === tractorId);
  const currentId = currentAssignment?.id;
  const activeUsage = getActiveTripUsage();

  if (activeUsage.tractors.has(tractorId)) return "Selected tractor is in an active trip and cannot be changed.";

  const findConflict = (field, value) => {
    if (!value) return null;
    return state.data.assignments.find((item) => item.status === "active" && item[field] === value && item.id !== currentId);
  };

  const trailerConflict = findConflict("trailer_id", trailerId);
  if (trailerConflict) {
    if (!(allowReassignment && !assignmentTouchesActiveTrip(trailerConflict, activeUsage))) {
      const tractor = state.data.vehicles.find((item) => item.id === trailerConflict.tractor_id);
      return `Trailer is already assigned to tractor ${tractor?.registration_no || trailerConflict.tractor_id}.`;
    }
  }

  const danglerConflict = findConflict("dangler_id", danglerId);
  if (danglerConflict) {
    if (!(allowReassignment && !assignmentTouchesActiveTrip(danglerConflict, activeUsage))) {
      const tractor = state.data.vehicles.find((item) => item.id === danglerConflict.tractor_id);
      return `Dangler is already assigned to tractor ${tractor?.registration_no || danglerConflict.tractor_id}.`;
    }
  }

  const driverConflict = findConflict("driver_id", driverId);
  if (driverConflict) {
    if (!(allowReassignment && !assignmentTouchesActiveTrip(driverConflict, activeUsage))) {
      const tractor = state.data.vehicles.find((item) => item.id === driverConflict.tractor_id);
      return `Driver is already assigned to tractor ${tractor?.registration_no || driverConflict.tractor_id}.`;
    }
  }

  if (trailerId && activeUsage.trailers.has(trailerId)) return "Selected trailer is in an active trip and cannot be reassigned.";
  if (danglerId && activeUsage.danglers.has(danglerId)) return "Selected dangler is in an active trip and cannot be reassigned.";
  if (driverId && activeUsage.drivers.has(driverId)) return "Selected driver is in an active trip and cannot be reassigned.";

  if (danglerId && !trailerId) return "Assign a trailer before attaching a dangler.";
  return "";
}

function renderAssignmentConflictState() {
  const notice = document.getElementById("assignmentConflictNotice");
  const saveButton = document.getElementById("assignmentSaveBtn");
  if (!notice || !saveButton) return "";
  const message = getAssignmentConflictMessage();
  notice.textContent = message;
  notice.classList.toggle("hidden", !message);
  saveButton.disabled = Boolean(message);
  return message;
}

function milestoneStatusBadge(status) {
  const cls = status === "reached" ? "complete" : status === "late" ? "expired" : status === "skipped" ? "not-required" : "pending";
  return `<span class="status-pill ${cls}">${status}</span>`;
}

async function loadTripDetail() {
  const label = document.getElementById("selectedTripLabel");
  const events = document.getElementById("tripEventsList");
  const expenses = document.getElementById("tripExpensesList");
  const timingSummary = document.getElementById("tripTimingSummary");
  const milestonesBody = document.getElementById("tripMilestonesBody");
  if (!label || !events || !expenses) return;
  if (!state.selectedTripId) {
    label.textContent = "Select a trip from the register.";
    events.innerHTML = "<li>No events yet.</li>";
    expenses.innerHTML = "<li>No expenses yet.</li>";
    if (timingSummary) timingSummary.textContent = "";
    if (milestonesBody) milestonesBody.innerHTML = `<tr><td colspan="7">Select a trip from the register.</td></tr>`;
    return;
  }
  const trip = await api(`/operations/trips/${state.selectedTripId}`);
  label.textContent = `Trip ${trip.trip_number}${trip.customer_reference ? ` (client ref: ${trip.customer_reference})` : ""} | ${trip.status} | Delay ${trip.delay_charge}`;
  const status = document.getElementById("tripStatusSelect");
  if (status) status.value = trip.status;
  events.innerHTML = trip.events.map((i) => `<li>${i.event_type} at ${i.location || "-"} on ${when(i.event_time)}</li>`).join("") || "<li>No events yet.</li>";
  expenses.innerHTML = trip.expenses.map((i) => {
    const vendorName = i.vendor_id ? (state.data.vendors.find((v) => v.id === i.vendor_id)?.name || i.vendor_id) : "";
    const settleBtn = i.payment_source === "payable" && !i.settled ? ` <button type="button" class="ghost-button" data-expense-settle="${i.id}">Settle</button>` : (i.payment_source === "payable" ? " (Settled)" : "");
    return `<li>${i.expense_type}: ${money(i.amount, i.currency)}${vendorName ? ` -- ${vendorName}` : ""}${settleBtn}</li>`;
  }).join("") || "<li>No expenses yet.</li>";
  const podStatus = document.getElementById("tripPodStatus");
  if (podStatus) {
    podStatus.textContent = trip.pod_captured_at
      ? `POD captured ${when(trip.pod_captured_at)}${trip.pod_notes ? ` -- ${trip.pod_notes}` : ""}${trip.pod_document_path ? " (document attached)" : ""}`
      : "No proof of delivery captured yet.";
  }
  const podForm = document.getElementById("podForm");
  if (podForm) podForm.querySelector('[name="notes"]').value = trip.pod_notes || "";

  // Timing: end-to-end trip time (actual departure -> actual arrival, or
  // elapsed so far while still moving) plus planned-vs-actual fuel/mileage.
  if (timingSummary) {
    const parts = [];
    if (trip.actual_departure) {
      parts.push(`Departed ${when(trip.actual_departure)}`);
      if (trip.actual_arrival) {
        parts.push(`arrived ${when(trip.actual_arrival)}`);
        parts.push(`duration ${trip.duration_hours ?? "-"} hrs`);
      } else {
        const elapsedHours = Math.round(((Date.now() - new Date(trip.actual_departure)) / 3600000) * 10) / 10;
        parts.push(`in transit for ${elapsedHours} hrs so far`);
      }
    } else {
      parts.push("Not yet departed");
    }
    const fuelPart = `Fuel: planned ${trip.planned_fuel_liters ?? "-"} L / actual ${trip.actual_fuel_liters ?? "-"} L`;
    const mileagePart = `Mileage: planned ${trip.planned_mileage_km ?? "-"} km / actual ${trip.actual_mileage_km ?? "-"} km`;
    timingSummary.textContent = `${parts.join(", ")}. ${fuelPart}. ${mileagePart}.`;
  }
  const fuelMileageForm = document.getElementById("fuelMileageForm");
  if (fuelMileageForm) {
    const fuelInput = fuelMileageForm.querySelector('[name="actual_fuel_liters"]');
    const mileageInput = fuelMileageForm.querySelector('[name="actual_mileage_km"]');
    if (fuelInput) fuelInput.value = trip.actual_fuel_liters ?? "";
    if (mileageInput) mileageInput.value = trip.actual_mileage_km ?? "";
  }

  if (milestonesBody) {
    const milestones = [...trip.milestones].sort((a, b) => a.sequence - b.sequence);
    milestonesBody.innerHTML = milestones.map((m) => {
      const actions = m.status === "pending"
        ? `<button type="button" class="ghost-button" data-milestone-record="${m.id}">Record Arrival</button> <button type="button" class="ghost-button" data-milestone-skip="${m.id}">Skip</button>`
        : "";
      return `<tr><td>${m.sequence}</td><td>${escapeHtml(m.name)}</td><td>${m.milestone_type}</td><td>${when(m.target_at)}</td><td>${when(m.actual_at)}</td><td>${milestoneStatusBadge(m.status)}</td><td><div class="row-actions">${actions}</div></td></tr>`;
    }).join("") || `<tr><td colspan="7">No milestones on this trip yet.</td></tr>`;
  }
}

async function loadRouteMilestones() {
  if (!state.selectedRouteId) { state.selectedRouteMilestones = []; renderRouteMilestonesTable(); return; }
  try {
    const route = await api(`/master/routes/${state.selectedRouteId}`);
    state.selectedRouteMilestones = route.milestones || [];
    state.selectedRouteLabelText = route.route_name;
  } catch (error) {
    setFlash(error.message, "error");
  }
  renderRouteMilestonesTable();
}

function renderRouteMilestonesTable() {
  const label = document.getElementById("selectedRouteLabel");
  const body = document.getElementById("routeMilestonesBody");
  if (!label || !body) return;
  if (!state.selectedRouteId) {
    label.textContent = "Select a route above to manage its predetermined checkpoints and time goals.";
    body.innerHTML = `<tr><td colspan="5">Select a route above.</td></tr>`;
    return;
  }
  label.textContent = `Milestones for ${state.selectedRouteLabelText || "route " + state.selectedRouteId}`;
  const milestones = state.selectedRouteMilestones || [];
  body.innerHTML = milestones.map((m) => `<tr><td>${m.sequence}</td><td>${escapeHtml(m.name)}</td><td>${m.milestone_type}</td><td>${m.target_hours_from_start ?? "-"}</td><td><button type="button" class="ghost-button" data-route-milestone-delete="${m.id}">Delete</button></td></tr>`).join("") || `<tr><td colspan="5">No milestones yet -- add the checkpoints this route should hit and when.</td></tr>`;
}

function renderData() {
  const s = state.data.summary || {};
  const stats = document.getElementById("dashboardStats");
  if (stats) {
    stats.innerHTML = [
      ["Active Trips", s.active_trips ?? 0], ["Completed Trips", s.completed_trips ?? 0], ["Idle Vehicles", s.idle_vehicles ?? 0],
      ["Maintenance Vehicles", s.maintenance_vehicles ?? 0], ["Outstanding Invoices", s.outstanding_invoices ?? 0],
      ["Revenue", money(s.total_invoiced_revenue ?? 0)], ["Expenses", money(s.total_recorded_expenses ?? 0)], ["Gross Margin", money(s.estimated_gross_margin ?? 0)],
      ["Cash & Bank (Ledger)", money(s.cash_and_bank_balance ?? 0)], ["Receivables (Ledger)", money(s.accounts_receivable_balance ?? 0)],
      ["Payables (Ledger)", money(s.accounts_payable_balance ?? 0)], ["Net Profit (Ledger)", money(s.ledger_net_profit ?? 0)],
    ].map(([l, v]) => `<article class="stat-card"><span class="stat-label">${l}</span><strong>${v}</strong></article>`).join("");
  }
  const openTrips = document.getElementById("dashboardOpenTrips"); if (openTrips) openTrips.textContent = s.active_trips ?? 0;
  const readyDrivers = document.getElementById("dashboardReadyDrivers"); if (readyDrivers) readyDrivers.textContent = state.data.drivers.filter((i) => i.status === "available").length;
  const activeVehicles = document.getElementById("dashboardActiveVehicles"); if (activeVehicles) activeVehicles.textContent = state.data.vehicles.filter((i) => ["active", "idle"].includes(i.status)).length;
  const maintCount = document.getElementById("dashboardMaintenanceCount"); if (maintCount) maintCount.textContent = state.data.maintenance.length;
  rows("dashboardTripsBody", state.data.trips.slice(0, 6).map((t) => `<tr><td>${t.trip_number}</td><td>${state.data.clients.find((c) => c.id === t.client_id)?.name || t.client_id}</td><td>${t.status}</td><td>${money(t.agreed_revenue, t.currency)}</td></tr>`).join(""), 4);
  rows("clientsBody", state.data.clients.map((i) => `<tr><td>${i.name}</td><td>${i.contact_person || i.phone || "-"}</td><td>${i.document_label || "-"}</td><td>${i.invoice_number_format || "House default"}</td><td>${i.booking_email || "-"}</td><td>${i.invoice_email || i.billing_email || "-"}</td><td>${i.currency}</td><td>${i.credit_days}</td><td><span class="status-pill ${i.is_active ? "complete" : "not-required"}">${i.is_active ? "active" : "inactive"}</span></td><td><div class="row-actions"><button type="button" class="ghost-button" data-edit-client="${i.id}">Edit</button>${i.is_active ? `<button type="button" class="ghost-button" data-client-deactivate="${i.id}">Deactivate</button>` : `<button type="button" data-client-reactivate="${i.id}">Reactivate</button>`}</div></td></tr>`).join(""), 10);
  rows("vehiclesBody", state.data.vehicles.map((i) => {
    const tyreStatus = getVehicleTyreStatus(i);
    const docs = [
      i.c28_card_path ? `<a href="${i.c28_card_path}" target="_blank" rel="noreferrer">C28 Doc</a>` : "",
      i.registration_card_path ? `<a href="${i.registration_card_path}" target="_blank" rel="noreferrer">Registration Card</a>` : "",
    ].filter(Boolean).join(" | ") || "-";
    const actions = [`<button type="button" class="ghost-button" data-edit-vehicle="${i.id}">Edit</button>`];
    if (i.status === "grounded") actions.push(`<button type="button" data-vehicle-reinstate="${i.id}">Reinstate</button>`);
    else if (i.status !== "assigned" && i.status !== "maintenance") actions.push(`<button type="button" class="ghost-button" data-vehicle-ground="${i.id}">Ground</button>`);
    return `<tr><td>${i.registration_no}</td><td>${i.vehicle_type}</td><td>${i.status}</td><td>${i.capacity_tons ?? "-"}</td><td>${i.tyre_layout || "-"}</td><td><span class="status-pill ${tyreStatus.status}">${tyreStatus.label}</span></td><td>${vehicleComplianceCell(i)}</td><td>${docs}</td><td><div class="row-actions">${actions.join("")}</div></td></tr>`;
  }).join(""), 9);
  rows("assignmentsBody", state.data.assignments.map((i) => `<tr><td>${state.data.vehicles.find((v) => v.id === i.tractor_id)?.registration_no || i.tractor_id}</td><td>${state.data.drivers.find((d) => d.id === i.driver_id)?.full_name || "-"}</td><td>${state.data.vehicles.find((v) => v.id === i.trailer_id)?.registration_no || "-"}</td><td>${state.data.vehicles.find((v) => v.id === i.dangler_id)?.registration_no || "-"}</td><td>${i.status}</td></tr>`).join(""), 5);
  rows("driversBody", state.data.drivers.map((i) => {
    const driverName = [i.first_name, i.middle_name, i.last_name].filter(Boolean).join(" ") || i.full_name || "-";
    const docLinks = [
      i.passport_copy_path ? `<a href="${i.passport_copy_path}" target="_blank" rel="noreferrer">Passport</a>` : "",
      i.photo_path ? `<a href="${i.photo_path}" target="_blank" rel="noreferrer">Photo</a>` : "",
      i.license_copy_path ? `<a href="${i.license_copy_path}" target="_blank" rel="noreferrer">License</a>` : "",
      i.gcla_certificate_copy_path ? `<a href="${i.gcla_certificate_copy_path}" target="_blank" rel="noreferrer">GCLA</a>` : "",
    ].filter(Boolean).join(" | ");
    return `<tr><td>${driverName}</td><td>${i.national_id_no || "-"}</td><td>${i.gcla_certificate_no || "-"}</td><td>${i.license_no}</td><td>${complianceBadge("License", i.license_expiry)}</td><td>${docLinks || "-"}</td><td>${i.status}</td><td><div class="row-actions"><button type="button" class="ghost-button" data-edit-driver="${i.id}">Edit</button></div></td></tr>`;
  }).join(""), 8);
  rows("routesBody", state.data.routes.map((i) => `<tr><td>${i.route_name}</td><td>${i.origin}</td><td>${i.destination}</td><td>${i.expected_days ?? "-"}</td><td>${i.standard_fuel_liters ?? "-"}</td><td>${i.standard_driver_mileage_km ?? "-"}</td><td><div class="row-actions"><button type="button" class="ghost-button" data-edit-route="${i.id}">Edit</button><button type="button" class="ghost-button" data-route-milestones="${i.id}">Milestones</button></div></td></tr>`).join(""), 7);
  renderRouteMilestonesTable();
  rows("vendorsBody", state.data.vendors.map((i) => `<tr><td>${i.name}</td><td>${i.contact_person || "-"}</td><td>${i.phone || "-"}</td><td>${i.email || "-"}</td><td>${i.tin || "-"}</td><td><span class="status-pill ${i.is_active ? "complete" : "not-required"}">${i.is_active ? "active" : "inactive"}</span></td><td><div class="row-actions"><button type="button" class="ghost-button" data-edit-vendor="${i.id}">Edit</button>${i.is_active ? `<button type="button" class="ghost-button" data-vendor-deactivate="${i.id}">Deactivate</button>` : `<button type="button" data-vendor-reactivate="${i.id}">Reactivate</button>`}</div></td></tr>`).join(""), 7);
  rows("complianceAlertsBody", (state.data.complianceAlerts || []).map((a) => `<tr><td>${a.entity_type}</td><td>${a.entity_label}</td><td>${a.document}</td><td>${a.expiry_date}</td><td><span class="status-pill ${a.status === "expired" ? "expired" : "pending"}">${a.status === "expired" ? "Expired" : "Expiring Soon"}</span></td></tr>`).join(""), 5);
  rows("bookingsBody", state.data.bookings.map((i) => {
    const client = state.data.clients.find((item) => item.id === i.client_id)?.name || i.client_id;
    const route = state.data.routes.find((item) => item.id === i.route_id)?.route_name || i.route_id;
    const tractor = state.data.vehicles.find((item) => item.id === i.tractor_id)?.registration_no || i.tractor_id;
    const emailStatus = i.booking_email_status === "sent"
      ? `Sent to ${i.booking_email_to || "-"}`
      : i.booking_email_status === "failed"
          ? `Failed${i.booking_email_error ? `: ${i.booking_email_error}` : ""}`
          : i.booking_email_status === "not_configured"
              ? "SMTP not configured"
              : i.booking_email_status === "missing_recipient"
                  ? "Client booking email missing"
                  : (i.booking_email_status || "-");
    const actions = i.status === "pending"
      ? `<div class="row-actions"><button type="button" data-booking-accept="${i.id}">Accept</button><button type="button" data-booking-reject="${i.id}">Reject</button></div>`
      : i.status === "accepted"
          ? `<div class="row-actions"><button type="button" data-booking-use="${i.id}">Use In Trip</button></div>`
          : "-";
    return `<tr><td>${i.booking_number}</td><td>${client}</td><td>${route}</td><td>${tractor}</td><td>${i.cargo_type}</td><td>${money(i.rate, i.currency)}</td><td>${i.status}</td><td>${emailStatus}</td><td>${actions}</td></tr>`;
  }).join(""), 9);
  rows("tripsBody", state.data.trips.map((i) => `<tr><td>${i.trip_number}</td><td>${i.status}</td><td>${money(i.agreed_revenue, i.currency)}</td><td><div class="row-actions"><button type="button" data-trip="${i.id}">Open</button></div></td></tr>`).join(""), 4);
  rows("invoicesBody", state.data.invoices.map((i) => {
    const trip = state.data.trips.find((t) => t.id === i.trip_id);
    const actions = [`<button type="button" data-invoice="${i.id}">Use</button>`];
    if (i.status !== "rejected" && i.status !== "paid") actions.push(`<button type="button" class="ghost-button" data-invoice-reject="${i.id}">Reject</button>`);
    const statusLabel = i.status === "rejected" ? `rejected${i.rejection_ticket ? ` (${i.rejection_ticket})` : ""}` : i.status;
    const emailLabel = i.invoice_email_status === "sent" ? "Sent" : i.invoice_email_status === "failed" ? `Failed${i.invoice_email_error ? `: ${i.invoice_email_error}` : ""}` : i.invoice_email_status === "not_configured" ? "SMTP not configured" : i.invoice_email_status === "missing_recipient" ? "Client invoice email missing" : (i.invoice_email_status || "-");
    return `<tr><td>${i.invoice_number}</td><td>${trip ? trip.trip_number : i.trip_id}</td><td>${i.stage}${i.stage_percentage !== 100 ? ` (${i.stage_percentage}%)` : ""}</td><td>${statusLabel}</td><td>${money(i.amount, i.currency)}</td><td>${emailLabel}</td><td><div class="row-actions">${actions.join("")}</div></td></tr>`;
  }).join(""), 7);
  rows("paymentsBody", state.data.payments.map((i) => `<tr><td>${i.invoice_id}</td><td>${money(i.amount)}</td><td>${i.payment_date}</td><td>${i.method}</td><td>${i.remittance_reference || "-"}</td></tr>`).join(""), 5);
  rows("maintenanceBody", state.data.maintenance.map((i) => {
    const vendorName = i.vendor_id ? (state.data.vendors.find((v) => v.id === i.vendor_id)?.name || i.vendor_id) : "-";
    const actions = [];
    if (i.status === "open") actions.push(`<button type="button" data-maintenance-complete="${i.id}">Mark Complete</button>`);
    if (i.payment_source === "payable" && !i.settled) actions.push(`<button type="button" class="ghost-button" data-maintenance-settle="${i.id}">Settle</button>`);
    return `<tr><td>${state.data.vehicles.find((v) => v.id === i.vehicle_id)?.registration_no || i.vehicle_id}</td><td>${i.maintenance_type}</td><td>${vendorName}</td><td>${i.status}</td><td>${money(i.cost)}</td><td>${i.payment_source === "payable" ? (i.settled ? `Settled${i.settled_date ? ` (${i.settled_date})` : ""}` : "Outstanding") : "-"}</td><td>${actions.length ? `<div class="row-actions">${actions.join("")}</div>` : "-"}</td></tr>`;
  }).join(""), 7);
  rows("usersBody", state.data.users.map((i) => {
    const isSelf = Boolean(state.me && state.me.id === i.id);
    const actions = [`<button type="button" class="ghost-button" data-edit-user="${i.id}">Edit</button>`];
    if (!isSelf) actions.push(i.is_active ? `<button type="button" class="ghost-button" data-user-deactivate="${i.id}">Deactivate</button>` : `<button type="button" data-user-reactivate="${i.id}">Reactivate</button>`);
    actions.push(`<button type="button" class="ghost-button" data-user-reset-password="${i.id}">Reset Password</button>`);
    return `<tr><td>${i.username}${isSelf ? " (you)" : ""}</td><td>${i.full_name}</td><td>${i.email || "-"}</td><td>${i.role}</td><td><span class="status-pill ${i.is_active ? "complete" : "not-required"}">${i.is_active ? "active" : "inactive"}</span></td><td><div class="row-actions">${actions.join("")}</div></td></tr>`;
  }).join(""), 6);
  renderAccountsTable();
  populateAccountSelects();
  populateSelectors();
  setInvoice(state.selectedInvoiceId);
  applyRoleVisibility();
}

function renderAccountsTable() {
  const filter = document.getElementById("accountsClassFilter")?.value || "";
  const list = filter ? state.data.accounts.filter((a) => a.statement_class === filter) : state.data.accounts;
  rows("accountsBody", list.map((a) => `<tr data-account-row="${a.code}"><td>${a.code}</td><td>${a.name}</td><td>${a.statement_class}</td><td>${a.account_group || "-"}</td><td>${a.normal_balance}</td></tr>`).join(""), 5);
}

function accountLabel(a) { return `${a.code} - ${a.name}`; }

function fillAccountSelect(id, items, blank = false) {
  const node = document.getElementById(id);
  if (!node) return;
  const previous = node.value;
  node.innerHTML = `${blank ? `<option value="">Auto-detect</option>` : ""}${items.map((item) => `<option value="${item.code}">${accountLabel(item)}</option>`).join("")}`;
  if (previous && items.some((item) => item.code === previous)) node.value = previous;
}

function populateAccountSelects() {
  const accounts = state.data.accounts;
  if (!accounts.length) return;
  const expenseLike = accounts.filter((a) => a.statement_class === "cogs" || a.statement_class === "expense");
  fillAccountSelect("tripExpenseGlAccount", expenseLike, true);
  fillAccountSelect("maintenanceGlAccount", expenseLike, true);
  const cashLike = accounts.filter((a) => a.account_group === "Bank" || a.account_group === "Cash on Hand");
  fillAccountSelect("paymentDepositAccount", cashLike, true);
  ["settingsCash", "settingsBank", "settingsReceivable", "settingsPayable", "settingsRevenue", "settingsDelay", "settingsRecovered", "settingsTripCogs", "settingsMaintenance", "settingsExpense"].forEach((id) => {
    if (document.getElementById(id)) fillAccountSelect(id, accounts, false);
  });
  if (state.ledgerSettings) applyLedgerSettingsToForm(state.ledgerSettings);
}

function applyLedgerSettingsToForm(settings) {
  const map = {
    settingsCash: settings.default_cash_account_code,
    settingsBank: settings.default_bank_account_code,
    settingsReceivable: settings.receivable_account_code,
    settingsPayable: settings.payable_account_code,
    settingsRevenue: settings.revenue_account_code,
    settingsDelay: settings.delay_income_account_code,
    settingsRecovered: settings.recovered_expense_income_code,
    settingsTripCogs: settings.default_trip_cogs_account_code,
    settingsMaintenance: settings.default_maintenance_account_code,
    settingsExpense: settings.default_expense_account_code,
  };
  Object.entries(map).forEach(([id, code]) => {
    const select = document.getElementById(id);
    if (select && code) select.value = code;
  });
}

async function loadLedgerSettings() {
  state.ledgerSettings = await api("/accounting/settings");
  applyLedgerSettingsToForm(state.ledgerSettings);
}

async function loadAccountLedger(code) {
  state.selectedLedgerAccountCode = code;
  const label = document.getElementById("ledgerLabel");
  if (!code) {
    if (label) label.textContent = "Select an account above to view its transaction history.";
    rows("ledgerBody", "", 6);
    return;
  }
  const account = state.data.accounts.find((a) => a.code === code);
  const ledger = await api(`/accounting/ledger/${code}`);
  if (label) label.textContent = `${account ? accountLabel(account) : code} | Opening ${money(ledger.opening_balance)} | Closing ${money(ledger.closing_balance)}`;
  rows("ledgerBody", ledger.rows.map((r) => `<tr><td>${r.entry_date}</td><td>${r.entry_number}</td><td>${escapeHtml(r.description || r.memo || "-")}</td><td>${r.debit ? money(r.debit) : "-"}</td><td>${r.credit ? money(r.credit) : "-"}</td><td>${money(r.running_balance)}</td></tr>`).join(""), 6);
}

async function loadJournal() {
  state.journal = await api("/accounting/journal");
  renderJournalTable();
}

function renderJournalTable() {
  rows("journalBody", state.journal.map((j) => {
    const totalDebit = j.lines.reduce((sum, l) => sum + l.debit, 0);
    return `<tr data-journal-row="${j.id}"><td>${j.entry_number}</td><td>${j.entry_date}</td><td>${j.source_type}</td><td>${escapeHtml(j.memo || "-")}</td><td>${money(totalDebit)}</td><td><div class="row-actions"><button type="button" data-journal-view="${j.id}">View</button></div></td></tr>`;
  }).join(""), 6);
}

function renderJournalDetail() {
  const entry = state.journal.find((j) => j.id === state.selectedJournalEntryId);
  const label = document.getElementById("selectedJournalLabel");
  const reverseBtn = document.getElementById("reverseJournalBtn");
  if (!entry) {
    if (label) label.textContent = "Select an entry from the register.";
    rows("journalLinesBody", "", 4);
    if (reverseBtn) reverseBtn.disabled = true;
    return;
  }
  if (label) label.textContent = `${entry.entry_number} | ${entry.entry_date} | ${entry.source_type}${entry.reversed_entry_id ? " | REVERSAL" : ""}`;
  rows("journalLinesBody", entry.lines.map((l) => `<tr><td>${l.account_code} - ${l.account_name}</td><td>${escapeHtml(l.description || "-")}</td><td>${l.debit ? money(l.debit) : "-"}</td><td>${l.credit ? money(l.credit) : "-"}</td></tr>`).join(""), 4);
  if (reverseBtn) {
    const alreadyReversed = state.journal.some((j) => j.reversed_entry_id === entry.id);
    reverseBtn.disabled = Boolean(entry.reversed_entry_id) || alreadyReversed;
    reverseBtn.textContent = entry.reversed_entry_id ? "This is a reversal entry" : (alreadyReversed ? "Already reversed" : "Reverse This Entry");
  }
}

function ensureJournalFormReady() {
  const container = document.getElementById("journalLinesContainer");
  if (container && !container.children.length && state.data.accounts.length) {
    addJournalLineRow(container);
    addJournalLineRow(container);
  }
}

function addJournalLineRow(container) {
  const row = document.createElement("div");
  row.className = "journal-line-row";
  const options = state.data.accounts.map((a) => `<option value="${a.code}">${accountLabel(a)}</option>`).join("");
  row.innerHTML = `
    <select class="journal-line-account"><option value="">Select account</option>${options}</select>
    <input class="journal-line-debit" type="number" step="0.01" placeholder="Debit">
    <input class="journal-line-credit" type="number" step="0.01" placeholder="Credit">
    <input class="journal-line-description" placeholder="Description">
    <button type="button" class="ghost-button journal-line-remove">Remove</button>`;
  row.querySelector(".journal-line-remove").onclick = () => { row.remove(); updateJournalBalanceHint(); };
  row.querySelector(".journal-line-debit").oninput = updateJournalBalanceHint;
  row.querySelector(".journal-line-credit").oninput = updateJournalBalanceHint;
  container.appendChild(row);
}

function updateJournalBalanceHint() {
  const hint = document.getElementById("journalBalanceHint");
  if (!hint) return;
  const rowsEls = document.querySelectorAll("#journalLinesContainer .journal-line-row");
  let debit = 0, credit = 0;
  rowsEls.forEach((row) => {
    debit += Number(row.querySelector(".journal-line-debit").value || 0);
    credit += Number(row.querySelector(".journal-line-credit").value || 0);
  });
  const diff = Math.round((debit - credit) * 100) / 100;
  hint.textContent = diff === 0 ? `Balanced: ${money(debit)}` : `Out of balance by ${money(Math.abs(diff))} (debit ${money(debit)} vs credit ${money(credit)})`;
  hint.style.color = diff === 0 ? "var(--ok)" : "var(--danger)";
}

function addBatchPaymentLineRow(container) {
  const row = document.createElement("div");
  row.className = "journal-line-row batch-payment-line-row";
  const openInvoices = state.data.invoices.filter((i) => i.status === "issued" || i.status === "partial");
  const options = openInvoices.map((i) => `<option value="${i.id}">${i.invoice_number} - ${money(i.amount, i.currency)}</option>`).join("");
  row.innerHTML = `
    <select class="batch-line-invoice"><option value="">Select invoice</option>${options}</select>
    <input class="batch-line-amount" type="number" step="0.01" placeholder="Amount">
    <button type="button" class="ghost-button batch-line-remove">Remove</button>`;
  row.querySelector(".batch-line-remove").onclick = () => row.remove();
  container.appendChild(row);
}

async function runTrialBalance() {
  const asOf = document.getElementById("tbAsOf")?.value || "";
  const report = await api(`/accounting/reports/trial-balance${asOf ? `?as_of=${asOf}` : ""}`);
  rows("trialBalanceBody", report.rows.map((r) => `<tr><td>${r.code}</td><td>${r.name}</td><td>${r.debit ? money(r.debit) : "-"}</td><td>${r.credit ? money(r.credit) : "-"}</td></tr>`).join("") + `<tr><td></td><td><strong>Total</strong></td><td><strong>${money(report.total_debit)}</strong></td><td><strong>${money(report.total_credit)}</strong></td></tr>`, 4);
  const status = document.getElementById("tbStatus");
  if (status) { status.textContent = report.balanced ? "Balanced" : "NOT balanced -- check postings"; status.style.color = report.balanced ? "var(--ok)" : "var(--danger)"; }
}

async function runProfitAndLoss() {
  const start = document.getElementById("plStart")?.value || "";
  const end = document.getElementById("plEnd")?.value || "";
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const report = await api(`/accounting/reports/profit-and-loss${params.toString() ? `?${params}` : ""}`);
  const summary = document.getElementById("plSummary");
  if (summary) {
    summary.innerHTML = [
      ["Income", money(report.total_income)], ["COGS", money(report.total_cogs)], ["Gross Profit", money(report.gross_profit)],
      ["Expenses", money(report.total_expense)], ["Net Profit", money(report.net_profit)],
    ].map(([l, v]) => `<div class="info-card"><span class="info-label">${l}</span><strong>${v}</strong></div>`).join("");
  }
  const body = [
    ...report.income.map((r) => ({ ...r, section: "Income" })),
    ...report.cogs.map((r) => ({ ...r, section: "Cost of Goods Sold" })),
    ...report.expense.map((r) => ({ ...r, section: "Expense" })),
  ];
  rows("profitLossBody", body.map((r) => `<tr><td>${r.code}</td><td>${r.section}: ${r.name}</td><td>${money(r.amount)}</td></tr>`).join(""), 3);
}

async function runBalanceSheet() {
  const asOf = document.getElementById("bsAsOf")?.value || "";
  const report = await api(`/accounting/reports/balance-sheet${asOf ? `?as_of=${asOf}` : ""}`);
  const summary = document.getElementById("bsSummary");
  if (summary) {
    summary.innerHTML = [
      ["Total Assets", money(report.total_assets)], ["Total Liabilities", money(report.total_liabilities)], ["Total Equity", money(report.total_equity)],
    ].map(([l, v]) => `<div class="info-card"><span class="info-label">${l}</span><strong>${v}</strong></div>`).join("");
  }
  const status = document.getElementById("bsStatus");
  if (status) { status.textContent = report.balanced ? "Balanced" : "NOT balanced -- check postings"; status.style.color = report.balanced ? "var(--ok)" : "var(--danger)"; }
  const body = [
    ...report.asset.map((r) => ({ ...r, section: "Asset" })),
    ...report.liability.map((r) => ({ ...r, section: "Liability" })),
    ...report.equity.map((r) => ({ ...r, section: "Equity" })),
  ];
  rows("balanceSheetBody", body.map((r) => `<tr><td>${r.code}</td><td>${r.section}: ${r.name}</td><td>${money(r.amount)}</td></tr>`).join(""), 3);
}

async function runArAging() {
  const report = await api("/accounting/reports/ar-aging");
  state.arAging = report;
  const asOf = document.getElementById("arAgingAsOf");
  if (asOf) asOf.textContent = `As of ${report.as_of}`;
  const bodyRows = report.rows.map((r) => `<tr><td>${r.client_name}</td>${report.bucket_labels.map((label) => `<td>${money(r.buckets[label] || 0)}</td>`).join("")}<td><strong>${money(r.total)}</strong></td></tr>`).join("");
  const totalsRow = `<tr><td><strong>Total</strong></td>${report.bucket_labels.map((label) => `<td><strong>${money(report.bucket_totals[label] || 0)}</strong></td>`).join("")}<td><strong>${money(report.grand_total)}</strong></td></tr>`;
  rows("arAgingBody", bodyRows + totalsRow, 7);
}

async function runApAging() {
  const report = await api("/accounting/reports/ap-aging");
  state.apAging = report;
  const asOf = document.getElementById("apAgingAsOf");
  if (asOf) asOf.textContent = `As of ${report.as_of}`;
  const bodyRows = report.rows.map((r) => `<tr><td>${r.vendor_name}</td>${report.bucket_labels.map((label) => `<td>${money(r.buckets[label] || 0)}</td>`).join("")}<td><strong>${money(r.total)}</strong></td></tr>`).join("");
  const totalsRow = `<tr><td><strong>Total</strong></td>${report.bucket_labels.map((label) => `<td><strong>${money(report.bucket_totals[label] || 0)}</strong></td>`).join("")}<td><strong>${money(report.grand_total)}</strong></td></tr>`;
  rows("apAgingBody", bodyRows + totalsRow, 6);
}

async function runClientStatement() {
  const clientId = Number(document.getElementById("statementClientId")?.value || 0);
  if (!clientId) return setFlash("Select a client first.", "error");
  const statement = await api(`/accounting/reports/client-statement/${clientId}`);
  state.statement = statement;
  const sendStatus = document.getElementById("statementSendStatus");
  if (sendStatus) sendStatus.textContent = "";
  rows("statementBody", statement.invoices.map((r) => `<tr><td>${r.invoice_number}</td><td>${r.issue_date || "-"}</td><td>${r.due_date || "-"}</td><td>${money(r.amount)}</td><td>${money(r.paid)}</td><td>${money(r.balance)}</td><td>${r.status}</td></tr>`).join(""), 7);
  const total = document.getElementById("statementTotal");
  if (total) total.textContent = `Total Outstanding: ${money(statement.total_outstanding)} as of ${statement.as_of}`;
}

async function refreshData() {
  if (!state.token) {
    state.me = null;
    state.data = { summary: null, users: [], clients: [], vehicles: [], assignments: [], drivers: [], routes: [], vendors: [], bookings: [], trips: [], invoices: [], payments: [], maintenance: [], accounts: [], complianceAlerts: [] };
    renderData();
    await loadTripDetail();
    return;
  }
  state.me = await api("/auth/me");
  setSessionStatus();
  buildNav();
  if (!canAccessPage(state.currentPage)) {
    state.currentPage = "dashboard";
    renderView();
  }
  const [summary, users, clients, vehicles, assignments, drivers, routes, vendors, bookings, trips, invoices, payments, maintenance, accounts, complianceAlerts] = await Promise.all([
    api("/dashboard/summary"),
    hasAnyRole(ROLE_BUNDLES.ADMIN) ? api("/master/users") : Promise.resolve([]),
    api("/master/clients"), api("/master/vehicles"), api("/master/assignments"), api("/master/drivers"),
    api("/master/routes"), api("/master/vendors?active_only=false"), api("/operations/bookings"), api("/operations/trips"), api("/operations/invoices"), api("/operations/payments"), api("/operations/maintenance"),
    api("/accounting/accounts?active_only=false"), api("/dashboard/compliance-alerts"),
  ]);
  state.data = { summary, users, clients, vehicles, assignments, drivers, routes, vendors, bookings, trips, invoices, payments, maintenance, accounts, complianceAlerts };
  renderData();
  await loadTripDetail();
  if (state.currentPage === "journal") { ensureJournalFormReady(); await loadJournal(); }
  if (state.currentPage === "accounts") await loadLedgerSettings();
}

function bindForm(id, path, message, transform = (p) => p, beforeSubmit = null, confirmSubmit = null) {
  const form = document.getElementById(id);
  if (!form) return;
  form.onsubmit = async (event) => {
    event.preventDefault();
    if (!state.token) return setFlash("Please sign in first.", "error");
    if (beforeSubmit && !beforeSubmit()) return;
    if (confirmSubmit && !confirmSubmit()) return;
    try {
      const payload = transform(formPayload(form));
      const basePath = typeof path === "function" ? path(payload) : path;
      const editIdField = form.querySelector("[data-edit-id-field]");
      const editId = editIdField ? editIdField.value : "";
      if (editId) {
        await api(`${basePath}/${editId}`, { method: "PUT", body: JSON.stringify(payload) });
      } else {
        await api(basePath, { method: "POST", body: JSON.stringify(payload) });
      }
      cancelEntityEdit(form);
      if (id === "tripForm") setBooking(null);
      await refreshData();
      setFlash(message, "success");
    } catch (error) { setFlash(error.message, "error"); }
  };
}

function bindDynamicForms() {
  bindForm("clientForm", "/master/clients", "Client saved.", (p) => p, null, () => confirmAction("Save this client?"));
  bindForm("assignmentForm", "/master/assignments", "Assignment saved.", (p) => ({
    tractor_id: Number(p.tractor_id),
    trailer_id: p.trailer_id ? Number(p.trailer_id) : null,
    dangler_id: p.dangler_id ? Number(p.dangler_id) : null,
    driver_id: p.driver_id ? Number(p.driver_id) : null,
    status: "active",
    allow_reassignment: Boolean(p.allow_reassignment),
  }), () => {
    const message = renderAssignmentConflictState();
    if (message) setFlash(message, "error");
    return !message;
  }, () => {
    const tractorLabel = document.getElementById("assignmentTractor")?.selectedOptions?.[0]?.textContent || "selected tractor";
    const driverLabel = document.getElementById("assignmentDriver")?.selectedOptions?.[0]?.textContent || "no driver";
    const trailerLabel = document.getElementById("assignmentTrailer")?.selectedOptions?.[0]?.textContent || "no trailer";
    const danglerLabel = document.getElementById("assignmentDangler")?.selectedOptions?.[0]?.textContent || "no dangler";
    return confirmAction(`Save this assignment?\n\nTractor: ${tractorLabel}\nDriver: ${driverLabel}\nTrailer: ${trailerLabel}\nDangler: ${danglerLabel}`);
  });
  bindForm("routeForm", "/master/routes", "Route saved.", (p) => p, null, () => confirmAction("Save this route?"));

  const routeMilestoneForm = document.getElementById("routeMilestoneForm");
  if (routeMilestoneForm) {
    routeMilestoneForm.onsubmit = async (event) => {
      event.preventDefault();
      if (!state.token) return setFlash("Please sign in first.", "error");
      if (!state.selectedRouteId) return setFlash("Select a route first.", "error");
      try {
        const payload = formPayload(routeMilestoneForm);
        await api(`/master/routes/${state.selectedRouteId}/milestones`, { method: "POST", body: JSON.stringify(payload) });
        routeMilestoneForm.reset();
        await loadRouteMilestones();
        setFlash("Route milestone added.", "success");
      } catch (error) { setFlash(error.message, "error"); }
    };
  }
  bindForm("vendorForm", "/master/vendors", "Vendor saved.", (p) => p, null, () => confirmAction("Save this vendor?"));
  bindForm("bookingForm", "/operations/bookings", "Booking saved.", (p) => ({
    client_id: Number(p.client_id),
    route_id: Number(p.route_id),
    tractor_id: Number(p.tractor_id),
    cargo_type: p.cargo_type,
    rate: Number(p.rate),
    currency: p.currency || "TZS",
    notes: p.notes || null,
  }), null, () => confirmAction("Save this booking?"));
  bindForm("userForm", "/master/users", "User saved.", (p) => p, null, () => confirmAction("Save this user?"));

  const changePasswordForm = document.getElementById("changePasswordForm");
  if (changePasswordForm) {
    changePasswordForm.onsubmit = async (event) => {
      event.preventDefault();
      if (!state.token) return setFlash("Please sign in first.", "error");
      try {
        const payload = formPayload(changePasswordForm);
        await api("/auth/change-password", { method: "POST", body: JSON.stringify(payload) });
        changePasswordForm.reset();
        setFlash("Password changed.", "success");
      } catch (error) { setFlash(error.message, "error"); }
    };
  }
  bindForm("maintenanceForm", "/operations/maintenance", "Maintenance record saved.", (p) => p, null, () => confirmAction("Save this maintenance record?"));
  bindForm("tripForm", "/operations/trips", "Trip created.", (p) => ({ ...p, booking_id: p.booking_id ? Number(p.booking_id) : null, client_id: Number(p.client_id), route_id: Number(p.route_id), tractor_id: Number(p.tractor_id), driver_id: p.driver_id ? Number(p.driver_id) : null, trailer_id: p.trailer_id ? Number(p.trailer_id) : null, dangler_id: p.dangler_id ? Number(p.dangler_id) : null }), () => {
    const tractorId = Number(document.getElementById("tripVehicle")?.value || 0);
    const assignment = state.data.assignments.find((item) => item.tractor_id === tractorId && item.status === "active");
    if (assignment && !assignment.driver_id) {
      setFlash("Selected tractor has no assigned driver. Complete the assignment first.", "error");
      return false;
    }
    return true;
  }, () => confirmAction("Create this trip?"));
  bindForm("tripEventForm", () => `/operations/trips/${state.selectedTripId}/events`, "Trip event added.", (p) => p, () => {
    if (!state.selectedTripId) setFlash("Select a trip first.", "error");
    return Boolean(state.selectedTripId);
  }, () => confirmAction("Add this trip event?"));
  bindForm("tripExpenseForm", () => `/operations/trips/${state.selectedTripId}/expenses`, "Trip expense added.", (p) => p, () => {
    if (!state.selectedTripId) setFlash("Select a trip first.", "error");
    return Boolean(state.selectedTripId);
  }, () => confirmAction("Add this trip expense?"));
  bindForm("tripMilestoneForm", () => `/operations/trips/${state.selectedTripId}/milestones`, "Milestone added.", (p) => p, () => {
    if (!state.selectedTripId) setFlash("Select a trip first.", "error");
    return Boolean(state.selectedTripId);
  }, () => confirmAction("Add this milestone to the trip?"));

  const fuelMileageForm = document.getElementById("fuelMileageForm");
  if (fuelMileageForm) {
    fuelMileageForm.onsubmit = async (event) => {
      event.preventDefault();
      if (!state.token) return setFlash("Please sign in first.", "error");
      if (!state.selectedTripId) return setFlash("Select a trip first.", "error");
      try {
        const payload = formPayload(fuelMileageForm);
        await api(`/operations/trips/${state.selectedTripId}/fuel-mileage`, { method: "PATCH", body: JSON.stringify(payload) });
        await refreshData();
        setFlash("Fuel and mileage recorded.", "success");
      } catch (error) { setFlash(error.message, "error"); }
    };
  }
  bindForm("invoiceFromTripForm", () => `/operations/trips/${state.selectedTripId}/invoice`, "Invoice created.", (p) => p, () => {
    if (!state.selectedTripId) setFlash("Select a trip first.", "error");
    return Boolean(state.selectedTripId);
  }, () => {
    const trip = state.data.trips.find((t) => t.id === state.selectedTripId);
    if (trip && !trip.pod_captured_at) {
      return confirmAction("No proof of delivery has been captured for this trip yet. Create the invoice anyway?");
    }
    return confirmAction("Create an invoice for this trip?");
  });
  bindForm("paymentForm", () => `/operations/invoices/${Number(document.getElementById("paymentInvoiceId").value || state.selectedInvoiceId)}/payments`, "Payment recorded.", (p) => { delete p.invoice_id; return p; }, () => {
    const invoiceId = Number(document.getElementById("paymentInvoiceId")?.value || state.selectedInvoiceId);
    if (!invoiceId) setFlash("Select an invoice first.", "error");
    return Boolean(invoiceId);
  }, () => confirmAction("Record this payment?"));
  const statusBtn = document.getElementById("updateTripStatusBtn");
  if (statusBtn) statusBtn.onclick = async () => {
    if (!state.selectedTripId) return setFlash("Select a trip first.", "error");
    const newStatus = document.getElementById("tripStatusSelect").value;
    if (newStatus === "cancelled" && !confirmAction("Cancel this trip? Its tractor and driver will be released back to the pool.")) return;
    try {
      await api(`/operations/trips/${state.selectedTripId}/status`, { method: "PATCH", body: JSON.stringify({ status: newStatus }) });
      await refreshData();
      setFlash("Trip status updated.", "success");
    } catch (error) { setFlash(error.message, "error"); }
  };

  const podForm = document.getElementById("podForm");
  if (podForm) {
    podForm.onsubmit = async (event) => {
      event.preventDefault();
      if (!state.token) return setFlash("Please sign in first.", "error");
      if (!state.selectedTripId) return setFlash("Select a trip first.", "error");
      if (!confirmAction("Save this proof of delivery?")) return;
      try {
        const formData = new FormData(podForm);
        const response = await fetch(`/operations/trips/${state.selectedTripId}/pod`, {
          method: "POST",
          headers: { Authorization: `Bearer ${state.token}` },
          body: formData,
        });
        if (!response.ok) {
          const payload = await response.json().catch(async () => ({ detail: await response.text() }));
          throw new Error(payload.detail || `Request failed (${response.status})`);
        }
        await refreshData();
        await loadTripDetail();
        setFlash("Proof of delivery saved.", "success");
      } catch (error) { setFlash(error.message, "error"); }
    };
  }

  const sendComplianceDigestBtn = document.getElementById("sendComplianceDigestBtn");
  if (sendComplianceDigestBtn) {
    sendComplianceDigestBtn.onclick = async () => {
      if (!confirmAction("Email the current compliance alert digest to every admin with an email on file?")) return;
      try {
        const result = await api("/dashboard/compliance-alerts/send-digest", { method: "POST" });
        setFlash(`Digest sent for ${result.alerts_count} alert(s) to ${result.deliveries.length} recipient(s).`, "success");
      } catch (error) { setFlash(error.message, "error"); }
    };
  }

  const runArAgingBtn = document.getElementById("runArAgingBtn");
  if (runArAgingBtn) runArAgingBtn.onclick = () => runArAging().catch((error) => setFlash(error.message, "error"));
  const runApAgingBtn = document.getElementById("runApAgingBtn");
  if (runApAgingBtn) runApAgingBtn.onclick = () => runApAging().catch((error) => setFlash(error.message, "error"));
  const viewStatementBtn = document.getElementById("viewStatementBtn");
  if (viewStatementBtn) viewStatementBtn.onclick = () => runClientStatement().catch((error) => setFlash(error.message, "error"));
  const sendStatementBtn = document.getElementById("sendStatementBtn");
  if (sendStatementBtn) {
    sendStatementBtn.onclick = async () => {
      const clientId = Number(document.getElementById("statementClientId")?.value || 0);
      if (!clientId) return setFlash("Select a client first.", "error");
      if (!confirmAction("Email the statement of accounts to this client?")) return;
      try {
        const result = await api(`/accounting/reports/client-statement/${clientId}/send`, { method: "POST" });
        const status = document.getElementById("statementSendStatus");
        if (status) status.textContent = `Delivery: ${result.delivery.status}${result.delivery.error ? ` (${result.delivery.error})` : ""}`;
        setFlash("Statement send attempted.", "success");
      } catch (error) { setFlash(error.message, "error"); }
    };
  }

  const tripVehicle = document.getElementById("tripVehicle");
  if (tripVehicle) tripVehicle.onchange = syncTripAssignment;
  const tripBooking = document.getElementById("tripBooking");
  if (tripBooking) {
    tripBooking.onchange = () => {
      setBooking(Number(tripBooking.value || 0));
      syncTripBooking();
      syncTripAssignment();
      document.getElementById("tripCargoType")?.dispatchEvent(new Event("change"));
    };
  }

  const tripCargoType = document.getElementById("tripCargoType");
  const tripRevenueLabel = document.getElementById("tripRevenueLabel");
  const tripRevenueInput = document.getElementById("tripRevenueInput");
  if (tripCargoType && tripRevenueLabel && tripRevenueInput) {
    const syncTripRevenueMode = () => {
      const isLooseCargo = tripCargoType.value === "loose cargo";
      tripRevenueLabel.textContent = isLooseCargo ? "Rate Per Ton" : "Agreed Revenue";
      tripRevenueInput.placeholder = isLooseCargo ? "Enter rate per ton" : "Enter agreed revenue";
    };
    tripCargoType.onchange = syncTripRevenueMode;
    syncTripRevenueMode();
  }

  const assignmentForm = document.getElementById("assignmentForm");
  if (assignmentForm) {
    const tractorField = document.getElementById("assignmentTractor");
    const driverField = document.getElementById("assignmentDriver");
    const trailerField = document.getElementById("assignmentTrailer");
    const danglerField = document.getElementById("assignmentDangler");
    if (tractorField) {
      tractorField.onchange = () => {
        if (driverField) driverField.value = "";
        if (trailerField) trailerField.value = "";
        if (danglerField) danglerField.value = "";
        syncAssignmentSelectors();
        renderAssignmentConflictState();
      };
    }
    [driverField, trailerField, danglerField].forEach((field) => {
      if (field) field.onchange = renderAssignmentConflictState;
    });
    const reassignField = document.getElementById("assignmentAllowReassignment");
    if (reassignField) {
      reassignField.onchange = () => {
        syncAssignmentSelectors();
        renderAssignmentConflictState();
      };
    }
    renderAssignmentConflictState();
  }

  const vehicleTypeSelect = document.getElementById("vehicleTypeSelect");
  if (vehicleTypeSelect) {
    const setFieldState = (field, show, required = show) => {
      if (!field) return;
      field.classList.toggle("hidden", !show);
      field.querySelectorAll("input, select").forEach((input) => {
        input.required = show && required;
        if (!show && input.type !== "hidden") input.value = "";
      });
    };

    const syncVehicleFields = () => {
      const type = vehicleTypeSelect.value;
      const capacityField = document.getElementById("capacityField");
      const tyreLayoutField = document.getElementById("tyreLayoutField");
      const c28ExpiryField = document.getElementById("c28ExpiryField");
      const c28CardField = document.getElementById("c28CardField");
      const registrationCardField = document.getElementById("registrationCardField");
      const capacityInput = document.querySelector('#capacityField input[name="capacity_tons"]');
      const tyreLayoutSelect = document.getElementById("tyreLayoutSelect");
      const c28ExpiryInput = document.querySelector('#c28ExpiryField input[name="c28_expiry"]');
      const c28CardInput = document.querySelector('#c28CardField input[name="c28_card"]');
      const registrationCardInput = document.querySelector('#registrationCardField input[name="registration_card"]');
      const showCapacity = type === "trailer" || type === "dangler";
      const showC28 = type === "trailer" || type === "dangler";
      const showTyreLayout = type === "trailer" || type === "dangler";
      const tyreOptions = type === "trailer"
        ? [
            { value: "222", label: "three axle double tyre" },
            { value: "111", label: "three axle super single tyre" },
          ]
        : type === "dangler"
            ? [
                { value: "2", label: "One Axle double tyre" },
                { value: "1", label: "One axle super single" },
                { value: "22", label: "two axle double tyre" },
                { value: "11", label: "Two axle super single tyre" },
              ]
            : [];

      setFieldState(capacityField, showCapacity);
      setFieldState(tyreLayoutField, showTyreLayout);
      setFieldState(c28ExpiryField, showC28);
      setFieldState(c28CardField, showC28);
      setFieldState(registrationCardField, showC28);

      if (tyreLayoutSelect) {
        const selectedValue = tyreLayoutSelect.value;
        tyreLayoutSelect.innerHTML = showTyreLayout
          ? `<option value="">Select layout</option>${tyreOptions.map((option) => `<option value="${option.value}">${option.label}</option>`).join("")}`
          : "";
        if (showTyreLayout && tyreOptions.some((option) => option.value === selectedValue)) tyreLayoutSelect.value = selectedValue;
      }

      if (!showCapacity && capacityInput) capacityInput.value = "";
      if (!showTyreLayout && tyreLayoutSelect) tyreLayoutSelect.value = "";
      if (!showC28 && c28ExpiryInput) c28ExpiryInput.value = "";
      if (!showC28 && c28CardInput) c28CardInput.value = "";
      if (!showC28 && registrationCardInput) registrationCardInput.value = "";
      renderTyreCapture("create", type, tyreLayoutSelect?.value || "", null);
    };

    const tyreLayoutSelect = document.getElementById("tyreLayoutSelect");
    vehicleTypeSelect.onchange = syncVehicleFields;
    if (tyreLayoutSelect) tyreLayoutSelect.onchange = () => renderTyreCapture("create", vehicleTypeSelect.value, tyreLayoutSelect.value, null);
    syncVehicleFields();
  }

  const driverForm = document.getElementById("driverForm");
  if (driverForm) {
    driverForm.onsubmit = async (event) => {
      event.preventDefault();
      if (!state.token) return setFlash("Please sign in first.", "error");
      const editIdField = driverForm.querySelector("[data-edit-id-field]");
      const editId = editIdField ? editIdField.value : "";
      if (!confirmAction(editId ? "Update this driver?" : "Save this driver?")) return;
      try {
        if (editId) {
          // Editing updates text/date fields only -- document uploads still go
          // through the dedicated create flow's file inputs, which a plain
          // JSON PUT can't carry.
          const payload = formPayload(driverForm);
          ["passport_copy", "photo", "license_copy", "gcla_certificate_copy"].forEach((k) => delete payload[k]);
          await api(`/master/drivers/${editId}`, { method: "PUT", body: JSON.stringify(payload) });
          cancelEntityEdit(driverForm);
          await refreshData();
          setFlash("Driver updated.", "success");
          return;
        }
        const formData = new FormData(driverForm);
        const response = await fetch("/master/drivers/upload", {
          method: "POST",
          headers: { Authorization: `Bearer ${state.token}` },
          body: formData,
        });
        if (!response.ok) {
          const payload = await response.json().catch(async () => ({ detail: await response.text() }));
          throw new Error(payload.detail || `Request failed (${response.status})`);
        }
        driverForm.reset();
        await refreshData();
        setFlash("Driver saved.", "success");
      } catch (error) {
        setFlash(error.message, "error");
      }
    };
  }

  const vehicleForm = document.getElementById("vehicleForm");
  if (vehicleForm) {
    vehicleForm.onsubmit = async (event) => {
      event.preventDefault();
      if (!state.token) return setFlash("Please sign in first.", "error");
      const editIdField = vehicleForm.querySelector("[data-edit-id-field]");
      const editId = editIdField ? editIdField.value : "";
      if (!confirmAction(editId ? "Update this vehicle?" : "Save this vehicle?")) return;
      try {
        if (editId) {
          // Editing updates the vehicle's own fields only -- tyre positions
          // and document uploads still go through their existing dedicated
          // flows, which a plain JSON PUT can't carry.
          const payload = formPayload(vehicleForm);
          // status is deliberately left out of generic edits -- the status
          // dropdown only lists active/idle/maintenance and would silently
          // clobber "assigned" or "grounded" vehicles back to "active".
          // Use the Ground/Reinstate buttons or the maintenance workflow instead.
          ["c28_card", "registration_card", "tyre_info_json", "status"].forEach((k) => delete payload[k]);
          await api(`/master/vehicles/${editId}`, { method: "PUT", body: JSON.stringify(payload) });
          cancelEntityEdit(vehicleForm);
          vehicleTypeSelect.value = "tractor";
          vehicleTypeSelect.dispatchEvent(new Event("change"));
          await refreshData();
          setFlash("Vehicle updated.", "success");
          return;
        }
        const formData = new FormData(vehicleForm);
        const type = formData.get("vehicle_type");
        const tyreLayout = formData.get("tyre_layout");
        formData.delete("fuel_type");
        if (type === "tractor") {
          formData.delete("capacity_tons");
          formData.delete("tyre_layout");
          formData.delete("tyre_info_json");
          formData.delete("c28_expiry");
          formData.delete("c28_card");
          formData.delete("registration_card");
        } else {
          if (!tyreLayout) throw new Error("Select a tyre layout for trailers and danglers.");
          const tyreInfoStatus = serializeTyreInfo("create", String(type), String(tyreLayout));
          if (tyreInfoStatus.json) formData.set("tyre_info_json", tyreInfoStatus.json);
          else formData.delete("tyre_info_json");
        }
        const response = await fetch("/master/vehicles/upload", {
          method: "POST",
          headers: { Authorization: `Bearer ${state.token}` },
          body: formData,
        });
        if (!response.ok) {
          const payload = await response.json().catch(async () => ({ detail: await response.text() }));
          throw new Error(payload.detail || `Request failed (${response.status})`);
        }
        vehicleForm.reset();
        vehicleTypeSelect.value = "tractor";
        vehicleTypeSelect.dispatchEvent(new Event("change"));
        await refreshData();
        setFlash("Vehicle saved.", "success");
      } catch (error) {
        setFlash(error.message, "error");
      }
    };
  }

  const invoiceStageSelect = document.getElementById("invoiceStageSelect");
  const invoiceStagePercentage = document.getElementById("invoiceStagePercentage");
  if (invoiceStageSelect && invoiceStagePercentage) {
    invoiceStageSelect.onchange = () => {
      const defaults = { full: 100, advance: 70, balance: 30, final: 20 };
      invoiceStagePercentage.value = String(defaults[invoiceStageSelect.value] ?? 100);
    };
  }

  const addBatchPaymentLineBtn = document.getElementById("addBatchPaymentLineBtn");
  const batchPaymentLinesContainer = document.getElementById("batchPaymentLinesContainer");
  if (addBatchPaymentLineBtn && batchPaymentLinesContainer) {
    if (!batchPaymentLinesContainer.children.length) { addBatchPaymentLineRow(batchPaymentLinesContainer); addBatchPaymentLineRow(batchPaymentLinesContainer); }
    addBatchPaymentLineBtn.onclick = () => addBatchPaymentLineRow(batchPaymentLinesContainer);
  }

  const batchPaymentForm = document.getElementById("batchPaymentForm");
  if (batchPaymentForm) {
    batchPaymentForm.onsubmit = async (event) => {
      event.preventDefault();
      if (!state.token) return setFlash("Please sign in first.", "error");
      const lineRows = Array.from(document.querySelectorAll("#batchPaymentLinesContainer .batch-payment-line-row"));
      const items = lineRows.map((row) => ({
        invoice_id: Number(row.querySelector(".batch-line-invoice").value || 0),
        amount: Number(row.querySelector(".batch-line-amount").value || 0),
      })).filter((item) => item.invoice_id && item.amount);
      if (items.length < 1) return setFlash("Add at least one invoice with an amount.", "error");
      if (!confirmAction(`Record a batch payment settling ${items.length} invoice(s)?`)) return;
      try {
        const formData = formPayload(batchPaymentForm);
        await api("/operations/payments/batch", { method: "POST", body: JSON.stringify({ ...formData, items }) });
        batchPaymentForm.reset();
        await refreshData();
        renderView();
        setFlash("Batch payment recorded.", "success");
      } catch (error) { setFlash(error.message, "error"); }
    };
  }

  bindForm("accountForm", "/accounting/accounts", "Account added.", (p) => p, null, () => confirmAction("Add this custom account?"));

  const ledgerSettingsForm = document.getElementById("ledgerSettingsForm");
  if (ledgerSettingsForm) {
    ledgerSettingsForm.onsubmit = async (event) => {
      event.preventDefault();
      if (!state.token) return setFlash("Please sign in first.", "error");
      try {
        const payload = formPayload(ledgerSettingsForm);
        state.ledgerSettings = await api("/accounting/settings", { method: "PUT", body: JSON.stringify(payload) });
        await refreshData();
        setFlash("Ledger settings saved.", "success");
      } catch (error) { setFlash(error.message, "error"); }
    };
  }

  const accountsClassFilter = document.getElementById("accountsClassFilter");
  if (accountsClassFilter) accountsClassFilter.onchange = renderAccountsTable;

  const addJournalLineBtn = document.getElementById("addJournalLineBtn");
  if (addJournalLineBtn) {
    const container = document.getElementById("journalLinesContainer");
    addJournalLineBtn.onclick = () => { if (container) addJournalLineRow(container); };
  }

  const journalEntryForm = document.getElementById("journalEntryForm");
  if (journalEntryForm) {
    journalEntryForm.onsubmit = async (event) => {
      event.preventDefault();
      if (!state.token) return setFlash("Please sign in first.", "error");
      const lineRows = Array.from(document.querySelectorAll("#journalLinesContainer .journal-line-row"));
      const lines = lineRows.map((row) => ({
        account_code: row.querySelector(".journal-line-account").value,
        debit: Number(row.querySelector(".journal-line-debit").value || 0),
        credit: Number(row.querySelector(".journal-line-credit").value || 0),
        description: row.querySelector(".journal-line-description").value || null,
      })).filter((line) => line.account_code && (line.debit || line.credit));
      if (lines.length < 2) return setFlash("Add at least two lines with an account and an amount.", "error");
      if (!confirmAction("Post this journal entry?")) return;
      try {
        const formData = formPayload(journalEntryForm);
        await api("/accounting/journal", { method: "POST", body: JSON.stringify({ entry_date: formData.entry_date || null, memo: formData.memo, lines }) });
        journalEntryForm.reset();
        await refreshData();
        await loadJournal();
        renderView();
        setFlash("Journal entry posted.", "success");
      } catch (error) { setFlash(error.message, "error"); }
    };
  }

  const reverseJournalBtn = document.getElementById("reverseJournalBtn");
  if (reverseJournalBtn) {
    reverseJournalBtn.onclick = async () => {
      if (!state.selectedJournalEntryId) return;
      if (!confirmAction("Post a reversal of this journal entry?")) return;
      try {
        await api(`/accounting/journal/${state.selectedJournalEntryId}/reverse`, { method: "POST" });
        await loadJournal();
        renderJournalDetail();
        setFlash("Reversal posted.", "success");
      } catch (error) { setFlash(error.message, "error"); }
    };
  }

  const runTrialBalanceBtn = document.getElementById("runTrialBalanceBtn");
  if (runTrialBalanceBtn) runTrialBalanceBtn.onclick = () => runTrialBalance().catch((error) => setFlash(error.message, "error"));
  const runProfitLossBtn = document.getElementById("runProfitLossBtn");
  if (runProfitLossBtn) runProfitLossBtn.onclick = () => runProfitAndLoss().catch((error) => setFlash(error.message, "error"));
  const runBalanceSheetBtn = document.getElementById("runBalanceSheetBtn");
  if (runBalanceSheetBtn) runBalanceSheetBtn.onclick = () => runBalanceSheet().catch((error) => setFlash(error.message, "error"));
  if (document.getElementById("trialBalanceBody") && state.token) runTrialBalance().catch(() => {});
  if (document.getElementById("profitLossBody") && state.token) runProfitAndLoss().catch(() => {});
  if (document.getElementById("balanceSheetBody") && state.token) runBalanceSheet().catch(() => {});
  if (document.getElementById("arAgingBody") && state.token) runArAging().catch(() => {});
  if (document.getElementById("apAgingBody") && state.token) runApAging().catch(() => {});
}

document.getElementById("loginForm").onsubmit = async (event) => {
  event.preventDefault();
  try {
    const result = await api("/auth/login", { method: "POST", body: JSON.stringify(formPayload(event.currentTarget)) });
    state.token = result.access_token;
    localStorage.setItem("tms_token", state.token);
    setSessionStatus();
    renderView();
    await refreshData();
    setFlash("Login successful.", "success");
  } catch (error) { setFlash(error.message, "error"); }
};

document.getElementById("logoutBtn").onclick = async () => {
  state.token = ""; state.selectedBookingId = null; state.selectedTripId = null; state.selectedInvoiceId = null; state.selectedVehicleTyreId = null;
  state.selectedJournalEntryId = null; state.selectedLedgerAccountCode = null; state.selectedRouteId = null; state.journal = [];
  localStorage.removeItem("tms_token");
  setSessionStatus();
  renderView();
  await refreshData();
  setFlash("Logged out.", "success");
};

document.addEventListener("click", async (event) => {
  const nav = event.target.closest("[data-page]");
  const bookingUse = event.target.closest("[data-booking-use]");
  const bookingAccept = event.target.closest("[data-booking-accept]");
  const bookingReject = event.target.closest("[data-booking-reject]");
  const trip = event.target.closest("[data-trip]");
  const invoice = event.target.closest("[data-invoice]");
  const invoiceReject = event.target.closest("[data-invoice-reject]");
  const vehicleTyre = event.target.closest("[data-vehicle-tyre]");
  const accountRow = event.target.closest("[data-account-row]");
  const journalRow = event.target.closest("[data-journal-view]");
  const cancelEdit = event.target.closest("[data-cancel-edit]");
  const editClient = event.target.closest("[data-edit-client]");
  const editVehicle = event.target.closest("[data-edit-vehicle]");
  const editDriver = event.target.closest("[data-edit-driver]");
  const editRoute = event.target.closest("[data-edit-route]");
  const routeMilestonesBtn = event.target.closest("[data-route-milestones]");
  const routeMilestoneDelete = event.target.closest("[data-route-milestone-delete]");
  const milestoneRecord = event.target.closest("[data-milestone-record]");
  const milestoneSkip = event.target.closest("[data-milestone-skip]");
  const editVendor = event.target.closest("[data-edit-vendor]");
  const editUser = event.target.closest("[data-edit-user]");
  const userDeactivate = event.target.closest("[data-user-deactivate]");
  const userReactivate = event.target.closest("[data-user-reactivate]");
  const userResetPassword = event.target.closest("[data-user-reset-password]");
  const clientDeactivate = event.target.closest("[data-client-deactivate]");
  const clientReactivate = event.target.closest("[data-client-reactivate]");
  const vendorDeactivate = event.target.closest("[data-vendor-deactivate]");
  const vendorReactivate = event.target.closest("[data-vendor-reactivate]");
  const vehicleGround = event.target.closest("[data-vehicle-ground]");
  const vehicleReinstate = event.target.closest("[data-vehicle-reinstate]");
  const maintenanceComplete = event.target.closest("[data-maintenance-complete]");
  const maintenanceSettle = event.target.closest("[data-maintenance-settle]");
  const expenseSettle = event.target.closest("[data-expense-settle]");
  if (nav) {
    const targetPage = nav.dataset.page;
    if (!canAccessPage(targetPage)) { setFlash("You do not have access to that page.", "error"); return; }
    state.currentPage = targetPage;
    renderView();
    return;
  }
  if (cancelEdit) { cancelEntityEdit(cancelEdit.closest("form")); return; }
  if (editClient) {
    const record = state.data.clients.find((c) => c.id === Number(editClient.dataset.editClient));
    if (record) startEntityEdit("clientForm", record, ["name", "contact_person", "phone", "email", "billing_email", "booking_email", "invoice_email", "loading_order_email", "statement_email", "address", "tin", "currency", "credit_days", "document_label", "invoice_number_format"]);
    return;
  }
  if (editVehicle) {
    const record = state.data.vehicles.find((v) => v.id === Number(editVehicle.dataset.editVehicle));
    if (record) startEntityEdit("vehicleForm", record, ["vehicle_type", "registration_no", "make", "model", "year", "capacity_tons", "tyre_layout", "c28_expiry", "insurance_expiry", "road_license_expiry"]);
    return;
  }
  if (editDriver) {
    const record = state.data.drivers.find((d) => d.id === Number(editDriver.dataset.editDriver));
    if (record) startEntityEdit("driverForm", record, ["first_name", "middle_name", "last_name", "phone", "national_id_no", "date_of_birth", "sex", "passport_no", "gcla_certificate_no", "date_of_employment", "home_address", "emergency_contact_name", "emergency_contact_relationship", "emergency_contact_phone", "referee1_first_name", "referee1_middle_name", "referee1_last_name", "referee1_phone", "referee2_first_name", "referee2_middle_name", "referee2_last_name", "referee2_phone", "license_no", "license_class", "license_expiry", "status"]);
    return;
  }
  if (editRoute) {
    const record = state.data.routes.find((r) => r.id === Number(editRoute.dataset.editRoute));
    if (record) startEntityEdit("routeForm", record, ["route_name", "origin", "destination", "distance_km", "expected_days", "border_charges", "driver_allowance", "delay_threshold_days", "demurrage_rate_per_day", "standard_fuel_liters", "standard_driver_mileage_km"]);
    return;
  }
  if (routeMilestonesBtn) {
    state.selectedRouteId = Number(routeMilestonesBtn.dataset.routeMilestones);
    await loadRouteMilestones();
    return;
  }
  if (routeMilestoneDelete) {
    if (!confirmAction("Delete this route milestone?")) return;
    try {
      await api(`/master/routes/${state.selectedRouteId}/milestones/${Number(routeMilestoneDelete.dataset.routeMilestoneDelete)}`, { method: "DELETE" });
      await loadRouteMilestones();
      setFlash("Route milestone deleted.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (editUser) {
    const record = state.data.users.find((u) => u.id === Number(editUser.dataset.editUser));
    if (record) {
      startEntityEdit("userForm", record, ["full_name", "email", "role"]);
      const pwField = document.getElementById("userPasswordField");
      if (pwField) {
        pwField.classList.add("hidden");
        const input = pwField.querySelector("input");
        if (input) input.required = false;
      }
    }
    return;
  }
  if (userDeactivate) {
    if (!confirmAction("Deactivate this user? They will no longer be able to sign in.")) return;
    try {
      await api(`/master/users/${Number(userDeactivate.dataset.userDeactivate)}/deactivate`, { method: "PATCH" });
      await refreshData();
      setFlash("User deactivated.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (userReactivate) {
    try {
      await api(`/master/users/${Number(userReactivate.dataset.userReactivate)}/reactivate`, { method: "PATCH" });
      await refreshData();
      setFlash("User reactivated.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (userResetPassword) {
    const newPassword = window.prompt("Enter a new password for this user (minimum 6 characters):");
    if (!newPassword) return;
    if (newPassword.length < 6) { setFlash("Password must be at least 6 characters.", "error"); return; }
    try {
      await api(`/master/users/${Number(userResetPassword.dataset.userResetPassword)}/reset-password`, { method: "PATCH", body: JSON.stringify({ new_password: newPassword }) });
      setFlash("Password reset.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (editVendor) {
    const record = state.data.vendors.find((v) => v.id === Number(editVendor.dataset.editVendor));
    if (record) startEntityEdit("vendorForm", record, ["name", "contact_person", "phone", "email", "tin", "address"]);
    return;
  }
  if (vendorDeactivate) {
    if (!confirmAction("Deactivate this vendor? They will no longer be selectable for new expenses or maintenance jobs.")) return;
    try {
      await api(`/master/vendors/${Number(vendorDeactivate.dataset.vendorDeactivate)}/deactivate`, { method: "PATCH" });
      await refreshData();
      setFlash("Vendor deactivated.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (vendorReactivate) {
    try {
      await api(`/master/vendors/${Number(vendorReactivate.dataset.vendorReactivate)}/reactivate`, { method: "PATCH" });
      await refreshData();
      setFlash("Vendor reactivated.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (expenseSettle) {
    if (!confirmAction("Settle this expense? This posts a payment from cash/bank against Accounts Payable and cannot be undone here.")) return;
    try {
      await api(`/operations/expenses/${Number(expenseSettle.dataset.expenseSettle)}/settle`, { method: "PATCH", body: JSON.stringify({}) });
      await refreshData();
      await loadTripDetail();
      setFlash("Expense settled.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (maintenanceSettle) {
    if (!confirmAction("Settle this maintenance bill? This posts a payment from cash/bank against Accounts Payable and cannot be undone here.")) return;
    try {
      await api(`/operations/maintenance/${Number(maintenanceSettle.dataset.maintenanceSettle)}/settle`, { method: "PATCH", body: JSON.stringify({}) });
      await refreshData();
      setFlash("Maintenance bill settled.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (clientDeactivate) {
    if (!confirmAction("Deactivate this client? They will no longer be selectable for new bookings or trips.")) return;
    try {
      await api(`/master/clients/${Number(clientDeactivate.dataset.clientDeactivate)}/deactivate`, { method: "PATCH" });
      await refreshData();
      setFlash("Client deactivated.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (clientReactivate) {
    try {
      await api(`/master/clients/${Number(clientReactivate.dataset.clientReactivate)}/reactivate`, { method: "PATCH" });
      await refreshData();
      setFlash("Client reactivated.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (vehicleGround) {
    if (!confirmAction("Ground this vehicle? It will be unavailable for bookings and trips until reinstated.")) return;
    try {
      await api(`/master/vehicles/${Number(vehicleGround.dataset.vehicleGround)}/ground`, { method: "PATCH" });
      await refreshData();
      setFlash("Vehicle grounded.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (vehicleReinstate) {
    try {
      await api(`/master/vehicles/${Number(vehicleReinstate.dataset.vehicleReinstate)}/reinstate`, { method: "PATCH" });
      await refreshData();
      setFlash("Vehicle reinstated.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (maintenanceComplete) {
    if (!confirmAction("Mark this maintenance job complete? The vehicle will be released back to active service.")) return;
    try {
      await api(`/operations/maintenance/${Number(maintenanceComplete.dataset.maintenanceComplete)}/complete`, { method: "PATCH" });
      await refreshData();
      setFlash("Maintenance marked complete.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (accountRow) {
    try { await loadAccountLedger(accountRow.dataset.accountRow); } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (journalRow) {
    state.selectedJournalEntryId = Number(journalRow.dataset.journalView);
    renderJournalDetail();
    return;
  }
  if (bookingAccept) {
    if (!confirmAction("Mark this booking as accepted by the client?")) return;
    try {
      await api(`/operations/bookings/${Number(bookingAccept.dataset.bookingAccept)}/status`, { method: "PATCH", body: JSON.stringify({ status: "accepted" }) });
      await refreshData();
      setFlash("Booking accepted.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (bookingReject) {
    if (!confirmAction("Mark this booking as rejected by the client?")) return;
    try {
      await api(`/operations/bookings/${Number(bookingReject.dataset.bookingReject)}/status`, { method: "PATCH", body: JSON.stringify({ status: "rejected" }) });
      await refreshData();
      setFlash("Booking rejected.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (bookingUse) {
    setBooking(Number(bookingUse.dataset.bookingUse));
    state.currentPage = "trips";
    renderView();
    syncTripBooking();
    syncTripAssignment();
    document.getElementById("tripCargoType")?.dispatchEvent(new Event("change"));
    setFlash("Accepted booking loaded into the Trip form.", "success");
    return;
  }
  if (trip) { state.selectedTripId = Number(trip.dataset.trip); state.currentPage = "trips"; renderView(); await loadTripDetail(); return; }
  if (invoiceReject) {
    const reason = window.prompt("Reason the client rejected this invoice (e.g. wrong route code, weight mismatch):");
    if (!reason) return;
    const ticket = window.prompt("Client rejection ticket number (optional):") || null;
    try {
      await api(`/operations/invoices/${Number(invoiceReject.dataset.invoiceReject)}/reject`, { method: "PATCH", body: JSON.stringify({ rejection_reason: reason, rejection_ticket: ticket }) });
      await refreshData();
      setFlash("Invoice marked rejected and its posting reversed.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (milestoneRecord) {
    if (!state.selectedTripId) return setFlash("Select a trip first.", "error");
    const notes = window.prompt("Notes for this arrival (optional):") || null;
    try {
      await api(`/operations/trips/${state.selectedTripId}/milestones/${Number(milestoneRecord.dataset.milestoneRecord)}/record`, { method: "PATCH", body: JSON.stringify({ notes }) });
      await refreshData();
      setFlash("Milestone recorded.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (milestoneSkip) {
    if (!state.selectedTripId) return setFlash("Select a trip first.", "error");
    if (!confirmAction("Mark this milestone as skipped?")) return;
    try {
      await api(`/operations/trips/${state.selectedTripId}/milestones/${Number(milestoneSkip.dataset.milestoneSkip)}/skip`, { method: "PATCH" });
      await refreshData();
      setFlash("Milestone skipped.", "success");
    } catch (error) { setFlash(error.message, "error"); }
    return;
  }
  if (invoice) { setInvoice(Number(invoice.dataset.invoice)); state.currentPage = "invoices"; renderView(); }
  if (vehicleTyre) { state.selectedVehicleTyreId = Number(vehicleTyre.dataset.vehicleTyre); state.currentPage = "trucks"; renderView(); }
});

window.addEventListener("hashchange", () => {
  const hashPage = location.hash.replace("#", "");
  if (pageLabels[hashPage] && hashPage !== state.currentPage) {
    if (!canAccessPage(hashPage)) {
      setFlash("You do not have access to that page.", "error");
      location.hash = `#${state.currentPage}`;
      return;
    }
    state.currentPage = hashPage;
    renderView();
  }
});

setSessionStatus();
const hashPage = location.hash.replace("#", "");
if (pageLabels[hashPage]) state.currentPage = hashPage;
buildNav();
renderView();
refreshData().then(() => setFlash("GUI ready.", "success")).catch((error) => setFlash(error.message, "error"));
