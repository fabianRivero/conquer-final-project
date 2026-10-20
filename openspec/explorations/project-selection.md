# PFM Project Selection — Ranked Candidate Set

**Project:** `final` (PFM — Proyecto Final de Máster)
**Phase:** SDD exploration / product selection
**Date:** 2026-10-19
**Artifact store:** OpenSpec (`openspec/`, repo-local) + Engram mirror (`sdd/pfm-selection/explore`, project `final`)
**Status:** Candidate set ready for student decision. No change directory, proposal, spec, design or tasks created yet — the OpenSpec change name is the slug of the chosen candidate (`hubdesk`, `tallerflow`, `huertacomun`, `ligabarrial`, `refugiomatch`).

> Note on location: this artifact lives in `openspec/explorations/` (not `openspec/changes/<change>/exploration.md`) because no change has been selected yet. Once the student picks a candidate, this file is referenced from `openspec/changes/<chosen-slug>/exploration.md`.

---

## 1. Decision summary (read this first)

**Recommendation: `hubdesk` — HubDesk, co-working space desk & meeting-room booking with a live floor map.**

It is the only candidate that simultaneously (a) solves a problem with a measurable daily cost, (b) has a React view that is unmistakably a *product* rather than a table dump, (c) contains exactly one interesting algorithmic core that is explainable in 30 seconds and testable in a unit test, and (d) fits 4–6 features in a 2–3 month solo window without needing infrastructure the student must pay for.

**Runner-up: `huertacomun` — HuertaComún, community allotment management.** Lowest-risk build of the five; it loses on *reflection/value* (no money, conflict or service failure at stake) and its React view is the closest of the five to "a CRUD screen with colours".

**Explicitly not recommended: `tallerflow`, `ligabarrial`, `refugiomatch`** — see §7 for the full scoring table and the reasoning.

---

## 2. Constraints applied to every candidate

Taken from the distilled PFM delivery guide (Engram `pfm/requirements-brief`, obs #113) and the session decisions.

| Constraint | Source | Non-negotiable |
| --- | --- | --- |
| Django backend, related models, migrations, views, templates, validated forms, auth with ≥2 roles, real persistence | PFM guide | Yes |
| ≥1 React view consuming the app's OWN API, working at the public URL | PFM guide | Yes |
| Public HTTPS URL, `DEBUG=False`, seeded demo data, test account per role | PFM guide | Yes |
| Public GitHub repo, README, pinned dependency versions, no secrets, progressive commits | PFM guide | Yes |
| 4–8 features (target 4–6 for a 2–3 month solo budget) | PFM guide | Yes |
| Demonstrable in a 30-minute defense incl. a small live code change | PFM guide | Yes |
| Deliverable in 2–3 months by one developer still consolidating backend/frontend skills | Session decision | Yes |
| Out of scope | Session decision | WebSockets, ML/AI models, paid third-party APIs, scraping, video/audio, IoT, payments, multi-tenant SaaS billing, mobile-native, unaffordable VPS, >6 core entities |

**Hard exclusions applied to all five candidates:** no payment processing, no Celery/Redis, no external SaaS API, no file-upload storage (deliberately excluded to avoid a second storage dependency), no ML of any kind, ≤5 core entities each.

---

## 3. Evidence base — verified platform facts (as of 2026-10-19)

These were verified against vendor pages, not recalled. They materially change the deployment answer.

| Platform | Verified facts | Consequence for this project |
| --- | --- | --- |
| **Render** (Hobby, $0) | Free web service = 0.1 CPU / 512 MB RAM. Spins down after 15 min without inbound traffic; spins back up in ~1 min with a "loading" page. **Ephemeral filesystem** — local SQLite is destroyed on spin-down/redeploy. 750 free instance hours/month. Managed TLS + HTTPS-only. 5 GB bandwidth, 500 build minutes/month. | Usable as the API host, but **Postgres must be external** and the app needs a keep-alive ping or it is cold during the defense. |
| **Render Free Postgres** | 256 MB RAM / 1 GB storage, **expires 30 days after creation** (14-day grace, then data is deleted). No backups. | **Do not use.** A project defended in 2–3 months would lose its database. |
| **Neon** (Free) | Permanent (not a trial), **no card required**, 1 GB storage/project, 100 CU-hours/project/month, scale-to-zero after 5 min, 6-hour history window, 1 manual snapshot. | **Chosen production database.** No expiry ⇒ survives the whole academic cycle. |
| **Supabase** (Free) | 500 MB DB, paused after 1 week of inactivity (pausing is reversible, data persists), 2 projects, no automatic backups on Free, no connection pooling on Free. | Acceptable fallback for Neon. Pause/resume adds a first-request latency that must be explained. |
| **Railway** | Free = $0 with only **$1/month** of usage credit, 1 vCPU / 0.5 GB, 1 project, 3 services, 0 custom domains, 3-day log retention. Hobby = $5/month with $5 credit, 2 custom domains, no spin-down. | Free plan is too tight for Django + a Node build. **Hobby ($5/mo) is the "stability upgrade"** to enable in the final month — same service, same URL. |
| **Django 5.2** | Django 5.2 supports Python 3.10–3.13 **and 3.14 (as of 5.2.8)**. Django 5.2 requires PostgreSQL 14+. PBKDF2 iteration count raised to 1,000,000. | The declared stack (Python 3.14 + Django 5.2.8) is officially supported. Postgres must be ≥14 — Neon satisfies this. |

### 3.1 Deployment spine shared by all five candidates

```
GitHub (public)  ──push──▶  Render Web Service (free, 0.1 CPU / 512 MB, managed TLS)
                                │  build: pip install -r requirements.txt
                                │          npm ci && npm run build   →  frontend/dist
                                │          python manage.py collectstatic →  staticfiles/
                                │  run:   gunicorn config.wsgi:application
                                └──▶  Neon Postgres (free, 1 GB, permanent)   [DATABASE_URL env]

frontend/dist  →  copied into Django static/ →  served by WhiteNoise at the SAME origin
React page mounted at /app/...  →  fetches /api/v1/...  →  same origin, no CORS
```

**Why one service and not Vercel/Netlify for the frontend:** one origin removes CORS entirely, one deploy to keep alive, one URL for the memoria, and it keeps the whole project inside the free tier. The trade-off (Django serves static assets) is documented in the design phase with its rationale.

**Why session + CSRF and not a token library:** the React view is served by a Django template, so `{% csrf_token %}` and the `csrftoken` cookie are already in play. `fetch(..., { credentials: 'same-origin', headers: { 'X-CSRFToken': ... } })` gives cookie-session auth with CSRF protection and **zero extra dependencies** — one fewer thing to explain in the defense and one fewer thing to get wrong.

**Known deployment landmines (pre-identified, each a future memoria §3.8 entry):**
1. `CSRF_TRUSTED_ORIGINS` must include the Render URL, otherwise every POST returns 403 in production but works locally. Same for `ALLOWED_HOSTS`.
2. Ephemeral filesystem ⇒ SQLite data is lost on every redeploy ⇒ Postgres is mandatory in production even though local dev uses SQLite.
3. The free web service sleeps after 15 min ⇒ the defense demo must start with a wake-up, and a keep-alive ping is part of the deployment story.
4. `collectstatic` must run at build time; `STATIC_ROOT`/`STATICFILES_DIRS` misconfiguration produces a blank page, not an error — needs a smoke check.
5. Seed data must be idempotent (`manage.py seed_demo` must be safe to re-run on every deploy).

---

## 4. Candidate set

### 4.1 `hubdesk` — HubDesk: Co-working Desk & Meeting-Room Booking  ★ RECOMMENDED

**The real problem.** Small co-working operators (10–60 desks) run their whole space out of a WhatsApp group and a whiteboard. Rooms get double-booked because the reservation lives in a message that scrolls away; members walk in and discover their desk is taken; and nobody — including the owner — can answer "how full is the space right now?" or "which room is free at 4 pm?" without phoning around. The operator pays fixed rent on every desk, so an empty desk at 3 pm is money burned, and an argument about who booked the room is a support incident that costs staff time. The current workaround (chat + whiteboard) keeps no history at all, so the operator cannot even measure utilisation to justify the next rent increase.

**Users and roles**

| Capability | Member | Community Manager |
| --- | :---: | :---: |
| See live floor map with state colours | ✔ (occupants anonymised) | ✔ (full detail) |
| Create / cancel own booking (desk or room, time slot) | ✔ | ✔ |
| Check in / release own booking | ✔ | ✔ |
| Check in / release anyone's booking | ✖ | ✔ |
| Create a blocking period (maintenance, private event) | ✖ | ✔ |
| Create / edit / deactivate spaces (desks, rooms) | ✖ | ✔ |
| Report an incident on a space | ✔ | ✔ |
| Resolve incidents | ✖ | ✔ |
| See occupancy counters (today) | ✔ (aggregate) | ✔ (detail + history) |

**Main entities (5)**

- `Space` — `id, kind (desk|room), label, zone, capacity, is_active` — the bookable resource; zones drive the floor-map layout.
- `MemberProfile` — `OneToOne → User, plan, home_zone, joined_at` — per-user extension (plan is a **label only**, no billing).
- `Booking` — `FK Space, FK User, starts_at, ends_at, status (reserved|checked_in|released|expired|no_show), created_at` — reservation with an explicit lifecycle.
- `SpaceBlock` — `FK Space, starts_at, ends_at, reason, created_by` — manager-level blackouts (maintenance, private event).
- `Incident` — `FK Space, FK reporter, category, description, status (open|resolved), created_at` — room problems reported from the map.

**Scope — 5 features, each grader-tickable**

1. **Accounts and two roles.** Signup/login with Django groups `member` and `manager`; manager-only URLs return 403 for a member. *DoD: logging in as `member@hubdesk.test` and opening a manager URL yields 403; the seeded manager can open it.*
2. **Spaces and availability.** A manager creates desks/rooms with zone and capacity; a member queries availability for a chosen day. *DoD: a desk created by the manager appears in the availability grid and in the React floor map on the next load, without a redeploy.*
3. **Conflict-free booking.** A member books a space for a slot; overlapping reservations are rejected server-side with a clear message and a DB constraint as backstop. *DoD: booking a slot that overlaps an existing reservation returns a form error, creates no second row, and the error is visible in the UI.*
4. **Occupancy lifecycle and no-show expiry.** Check-in marks a booking occupied; reservations not checked in within the grace window are released **lazily at read time** (no worker, no cron). *DoD: a seeded reservation older than the grace window reports `expired` in the API and frees the tile in the map, with no background job running anywhere.*
5. **Incidents and manager overview.** A member reports an incident on a space; the manager lists and resolves them and sees the day's occupancy counters. *DoD: a reported incident appears in the manager queue, is counted as an open issue, and stops being counted once resolved.*

**The React view — "Live floor map" at `/app/floor`**
- **What it renders:** a CSS-grid floor plan — rows are zones, cells are desks and rooms — where each tile is colour-coded by live state (free / reserved / occupied / blocked / incident) with an icon and a legend, plus a header with "occupied now: X of Y" counters, the server clock, and an "updated Ns ago" freshness indicator. Clicking a tile opens a detail card (label, zone, status, until when, occupant first name for managers only).
- **Endpoint:** `GET /api/v1/spaces/?at=<ISO timestamp>` → `[{id, label, kind, zone, status, occupant, until}]`, re-fetched every 30 s.
- **Why it is visibly more than a table dump:** it is a *spatial* representation of the room, not a list — the grader sees the layout of a real space and the state of every tile at a glance; the counters and the auto-refresh prove it is live; and the demo is a two-second action: check in from a second browser window and watch a tile flip colour within 30 seconds.
- It also satisfies the brief's requirement that the React view consumes the app's **own** API at the **public** URL (same origin, session cookie, CSRF header).

**Explicit non-goals.** No payments, invoices, subscriptions or plan enforcement (the plan is a label). No QR/badge printing or hardware. No Google Calendar / iCal sync. No occupancy sensors or IoT. No email/SMS notifications (free tiers block outbound SMTP on port 25). No native mobile app. No multi-tenant billing.

**Deployment path.** Render Hobby free web service (managed TLS, `onrender.com` HTTPS URL) + Neon Free Postgres (`DATABASE_URL` env var). `DEBUG=False`, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` set from env. Frontend built by Vite at deploy time into Django `static/` via WhiteNoise. Seed: `python manage.py seed_demo` (idempotent) creates 2 users (`member@hubdesk.test`, `manager@hubdesk.test`, password documented in the README), 24 desks, 4 rooms, ~40 bookings across the current day, 2 blocking periods, 3 incidents. Keep-alive: a scheduled HTTP ping to `/health/` every ~10 minutes from GitHub Actions (free for public repos), plus a manual wake-up before the defense; the "cold start" trade-off and the $5/month Railway Hobby alternative are documented in memoria §3.8.

**Hardest technical part + de-risking plan.**
*Conflict-free booking and no-show expiry without any background worker.*
- (a) Overlap detection is a **pure function over a queryset**: `Booking.objects.filter(space=s, status__in=[reserved, checked_in], starts_at__lt=end, ends_at__gt=start)` — unit-testable in isolation, no locks required for this scale.
- (b) A `UniqueConstraint` on `(space, starts_at)` is the DB-level backstop for identical slots; the query handles partial overlaps.
- (c) Expiry is a pure `expire_stale_bookings(now)` helper invoked inside the API view/queryset, so "the state you read is always correct" without Celery, Redis or cron. The cost — a read-time write — is written down as a conscious trade-off.
- (d) **De-risk in week 1 (2 hours, before any React):** a throwaway management command that creates overlapping bookings, asserts the error path, and asserts a stale booking expires on read. If that command is green, the risky part is done.

**Defense panel — 6 most likely questions**

1. *"Why no Celery/Redis for expiring reservations?"* → The rule is a pure function of the current time, so evaluating it lazily at read time gives identical behaviour with zero extra infrastructure; the trade-off (a write inside a read) is documented and bounded.
2. *"How do you stop two members double-booking the same desk?"* → Server-side overlap query inside a transaction plus a unique-constraint backstop; the client is never trusted.
3. *"What stops a member from reading another member's bookings?"* → Django groups + per-view permission mixins + owner-scoped querysets; the map anonymises other members and only managers see names.
4. *"Why WhiteNoise and not Vercel/Netlify for the React app?"* → One origin, no CORS, one deploy to keep alive, one URL for the memoria, everything inside the free tier; the trade-off is documented in design.md.
5. *"How would it scale to 50 desks and 500 members?"* → Same schema; the map endpoint is one query with `select_related`; the known N+1 and its fix (prefetch) are named in the memoria.
6. *"What is your security posture?"* → Session + CSRF on every mutation, PBKDF2 (1M iterations), role checks on every view, validated forms, ORM parameterised queries, template autoescaping, `DEBUG=False`, secrets in env only, HTTPS enforced, `ALLOWED_HOSTS` locked.

**Rubric fit**

- **Backend correctness (30%)** — 5 related models with real constraints, migrations, validated forms, transactional booking logic, and a unit-tested rules layer: strong.
- **React data consumption (15%)** — a live spatial map with counters and auto-refresh from the app's own API, not a static table: strong.
- **Architecture (15%)** — one deployable service, layered Django apps, DRF serializers, an explicit rules/service layer, WhiteNoise; every decision has a written rationale: strong.
- **Security & data integrity (15%)** — two roles enforced server-side, CSRF, hashing, no secrets in git, `DEBUG=False`, HTTPS, unique-constraint backstop: strong.
- **Documentation & presentation (15%)** — README (install, env vars, tests, public URL, credentials), memoria §3.1–3.8 with ER + architecture diagrams and a real "errors found and fixed" section: strong.
- **Reflection & contributed value (10%)** — quantifies the operator's losses (double-booking disputes, idle desks, walk-around time) and states limitations honestly: strong.

---

### 4.2 `tallerflow` — TallerFlow: Repair-Shop Work-Order Tracking

**The real problem.** A small repair shop (mobiles, bicycles, electronics) takes jobs on paper tickets or a whiteboard. The customer phones to ask "¿cómo va mi móvil?" and the receptionist has to physically hunt for the ticket. Nobody can see which job is blocked on a part, who promised which date, or how much work is actually in progress, so the owner cannot tell whether the backlog is growing or whether it is time to hire. WhatsApp status updates scroll away, and with no written record of what was done, every warranty dispute becomes an argument.

**Users and roles**

| Capability | Front Desk | Technician | Customer (read-only portal) |
| --- | :---: | :---: | :---: |
| Create a work order from intake | ✔ | ✖ | ✖ |
| View all orders | ✔ | ✔ (all, for the workshop wall) | ✖ |
| View own orders | ✔ | ✔ | ✔ (via reference code) |
| Advance order status | ✔ (receive → diagnose → repair → ready → delivered) | ✔ (repair stages only) | ✖ |
| Assign a technician | ✔ | ✖ | ✖ |
| Reserve / consume parts from stock | ✔ | ✔ | ✖ |
| See WIP counters and overdue list | ✔ | ✔ | ✖ |

**Main entities (5)**

- `Customer` — `id, name, phone, email, created_at` — the person who brings the device.
- `RepairOrder` — `id, code (public reference), FK Customer, device, symptom, diagnosis, status, priority, promised_at, FK technician, created_at, delivered_at` — the work order and its state machine.
- `Part` — `id, sku, name, stock, unit_price_estimate` — the parts inventory.
- `OrderPart` — `FK RepairOrder, FK Part, quantity, consumed` — the order-to-parts line, the place stock changes.
- `StatusEvent` — `FK RepairOrder, from_status, to_status, note, at, FK actor` — an auditable history of the order.

**Scope — 5 features**

1. **Intake and work order creation.** Front desk records customer, device and symptom into a validated form that generates a human-readable order code. *DoD: a valid intake creates an order with a unique code shown to the customer; an invalid phone/empty symptom is rejected with field errors.*
2. **Status workflow with priority and promised date.** Orders move through a validated state machine with priority and a promised date; overdue orders are flagged. *DoD: an illegal transition (e.g. delivered → received) is rejected server-side, and overdue orders are visibly flagged.*
3. **Technician assignment and workload.** A manager assigns a technician; each technician sees their own queue. *DoD: an assigned order appears in that technician's filtered list and only in it.*
4. **Parts stock with atomic consumption.** Consuming a part decrements stock atomically; insufficient stock is rejected without corrupting inventory. *DoD: consuming more units than exist leaves the stock value unchanged and returns a clear error.*
5. **Customer tracking and WIP dashboard.** The customer sees status/history via an order code; staff see counters by status and an overdue list. *DoD: entering an order code on the public tracking page shows its status and history and nothing else.*

**The React view — "Workshop Kanban" at `/app/board`**
- **What it renders:** columns = order statuses; each card shows the order code, customer surname, device, a priority chip, a stepper of the current stage, and a "days vs promised date" badge that turns red when overdue; a header row shows per-column WIP counters and a filter by technician.
- **Endpoint:** `GET /api/v1/orders/?status=&technician=` → orders with joined customer/technician names and a computed `days_open`, `overdue`.
- **Why it is more than a table dump:** the board encodes the *flow* of the workshop; the WIP counters and the overdue badge make the business problem (backlog, promises kept) visible at a glance; the demo is "move a card from Diagnose to Repair and watch the counters change".

**Explicit non-goals.** No invoicing, quotes-to-invoice or payments. No warranty/insurance contracts. No barcode or QR scanning. No device photos or attachments. No email/SMS notifications. No stock-purchase workflow or supplier management. No multi-workshop tenancy. No native mobile app.

**Deployment path.** Identical spine: Render free web service + Neon Free Postgres, `DEBUG=False`, WhiteNoise-served Vite build, `seed_demo` creating 2 staff users + 1 customer account, ~30 orders across all statuses, ~10 parts, deterministic historical `StatusEvent`s so the timeline is non-empty. Credentials in the README. Same keep-alive ping.

**Hardest technical part + de-risking plan.** *Atomic stock consumption under concurrent requests.* Plan: `transaction.atomic()` + `select_for_update()` on the `Part` row, re-check the quantity inside the transaction, and a unit test that attempts to consume beyond available stock and asserts stock is unchanged. **De-risk experiment:** a 1-hour shell script doing the concurrent/over-consume test before any UI work.

**Defense panel — 6 questions**

1. *"How do you prevent the stock from going negative?"* → Row-level lock inside a transaction + re-check after the lock; demonstrated by a test that leaves stock untouched.
2. *"What is the value of the state machine?"* → It encodes the real workshop process, makes illegal states unrepresentable, and produces the WIP counters the owner lacked.
3. *"How do you know the order code is not guessable?"* → Randomised, long, non-sequential reference codes, and the tracking page exposes only status/history for that code.
4. *"Why not just a spreadsheet?"* → Spreadsheets cannot enforce a state machine, cannot make stock decrements atomic, and give no audit trail; that is precisely what was being lost.
5. *"How is this multi-user safe?"* → Per-user querysets and role checks; two staff can work concurrently without overwriting each other's state changes.
6. *"What would you add next?"* → PDF quote generation, supplier purchase orders, technician productivity metrics — deliberately excluded to protect the deadline.

**Rubric fit**

- **Backend correctness (30%)** — strong: state machine, transactional stock, audit trail, validated forms.
- **React data consumption (15%)** — a real kanban with live counters, but kanban boards are the single most common PFM visual: acceptable, not distinctive.
- **Architecture (15%)** — strong: app layering, a rules module for transitions, transaction boundaries.
- **Security & data integrity (15%)** — strong: roles, non-guessable codes, atomic stock, no data leakage in the tracking view.
- **Documentation & presentation (15%)** — strong.
- **Reflection & contributed value (10%)** — solid: idle-technician time, unkept promises, warranty disputes; but "another ticketing system" is a harder sell to a panel that has seen many.

---

### 4.3 `huertacomun` — HuertaComún: Community Allotment & Parcel Management

**The real problem.** A neighbourhood association or a school that runs a shared allotment keeps the parcel list on paper and the coordination on a WhatsApp group. Nobody can tell which parcel has been abandoned for two seasons (and is quietly being used by someone else), who waters when, or what was actually harvested and shared, so volunteers stop coming and the whole space degrades while the association still believes it is fully allocated. Disputes about watering turns are settled by whoever argues loudest.

**Users and roles**

| Capability | Gardener (parcelero) | Coordinator (coordinación) |
| --- | :---: | :---: |
| See the parcel map with crop and state | ✔ | ✔ |
| Claim / request a free parcel | ✔ | ✔ |
| Assign or reassign a parcel | ✖ | ✔ |
| Register plantings (crop, sowing date, expected harvest) | ✔ (own parcels) | ✔ (any) |
| Register harvests (weight, date) | ✔ | ✔ |
| Generate the watering rota for a week | ✖ | ✔ |
| Mark a watering turn as done | ✔ (own turns) | ✔ |
| See season totals and per-parcel yield | ✔ (aggregate) | ✔ (detail) |

**Main entities (5)**

- `Plot` — `id, code, area, location_row, location_col, status (free|assigned|resting), FK holder` — a physical parcel with grid coordinates.
- `Season` — `id, name, starts_at, ends_at, is_active` — the growing campaign that plots and plantings belong to.
- `Planting` — `FK Plot, FK Season, crop, sown_at, expected_harvest_at, status (sown|growing|harvested|failed)` — what is growing where.
- `Task` (watering turn) — `FK Plot, kind (watering|weeding|harvest), due_at, FK assignee, done_at` — the shared rota.
- `Harvest` — `FK Plot, FK Season, weight_kg, harvested_at, shared_with` — the yield record behind the totals.

**Scope — 5 features**

1. **Parcels and assignment.** The coordinator defines parcels on a grid and assigns them; members request free ones. *DoD: a new parcel appears on the map at the right grid position and is claimable exactly once.*
2. **Planting calendar.** Members register what they sow and when it will be ready. *DoD: a planting with a sowing date produces a correct "days to harvest" figure on the map and in the API.*
3. **Fair watering rota.** The coordinator generates a weekly rota that distributes turns evenly across the gardeners holding plantings. *DoD: for 6 gardeners over 7 turns, no gardener receives more than one extra turn and every planting week has a turn.*
4. **Harvest log and season totals.** Members log harvests; totals are aggregated per plot and per season. *DoD: two logged harvests sum correctly in the dashboard and in the API payload.*
5. **Coordinator dashboard and member view.** The coordinator sees occupancy (assigned/free/resting), upcoming harvests and rota compliance; members see only their own parcels. *DoD: a member requesting another member's plot gets 403/404; the coordinator sees the full picture.*

**The React view — "Parcel map and rota" at `/app/map`**
- **What it renders:** an SVG/CSS grid reproducing the allotment's physical layout, each plot coloured by crop state (empty / sown / growing / harvested / resting) with the crop name and "ready in N days"; a side panel shows the current week's watering rota as a list of turns with owner and completion state; a header shows "X of Y parcels in use" and "this week's turns: N done / M".
- **Endpoint:** `GET /api/v1/plots/season/<id>/` → plots with plot code, holder, plantings and aggregated state, plus `GET /api/v1/tasks/?week=` for the rota.
- **Why it is more than a table dump:** the grid is a *map of a real place*, colours encode crop state rather than data types, and the rota panel turns a distributed chore into something the panel can see happening.

**Explicit non-goals.** No payment for parcels or water. No IoT/soil sensors. No produce marketplace or orders. No photo-heavy plant tracking. No weather API integration. No accounting of association membership fees. No native mobile app.

**Deployment path.** Same spine: Render free web service + Neon Free Postgres, seeded with 18 plots, 12 gardeners, one active season with plantings across different crops, two weeks of rota tasks and a few harvests. Two seeded accounts (`parcelero@huertacomun.test`, `coordinador@huertacomun.test`). Same keep-alive ping and `seed_demo` idempotency.

**Hardest technical part + de-risking plan.** *Fair, deterministic rota generation.* Plan: implement `build_rota(plantings, turns, week)` as a **pure function** with no DB access — it takes the plantings and returns the assignments — so it can be unit-tested exhaustively (even distribution, no double-booking, respects rest days). **De-risk experiment:** write the function and its tests on day 2, before any model or view exists; it is pure logic and cannot be derailed later.

**Defense panel — 6 questions**

1. *"Why not a shared spreadsheet?"* → A spreadsheet cannot generate a fair rota, cannot detect abandoned parcels, and produces no yield history the association can show back to its members.
2. *"How do you decide who waters what?"* → A deterministic, tested pure function that distributes turns by plantings per gardener; the rules are in the code and in the test suite, not in someone's head.
3. *"What if a member abandons a parcel?"* → Plantings with no activity for a season are flagged as `resting` by the coordinator view; automatic reclamation is explicitly out of scope.
4. *"Is any personal data handled?"* → Only names and contact details of association members; role-based access; no sensitive data category; stated in memoria §3.6.
5. *"How is this monetised — it is free for members?"* → It is not a SaaS: the value is the association's time and the space's productivity; the memoria frames it as a tool for a community, with future work on (optional, out-of-scope) contributions.
6. *"What is the weakest part of your solution?"* → Answer honestly: rota generation is fair but not optimal, and abandonment detection is manual — this is the seed of the future-work section.

**Rubric fit**

- **Backend correctness (30%)** — strong: models, pure-function rules with tests, aggregates, role-scoped querysets.
- **React data consumption (15%)** — a genuine spatial map, but the colour set encodes few states and the panel can read it as "a CRUD screen with colours": acceptable, weaker than the leader.
- **Architecture (15%)** — strong: the pure-function core is a good architecture story.
- **Security & data integrity (15%)** — strong: role scoping, minimal personal data, no payments.
- **Documentation & presentation (15%)** — strong.
- **Reflection & contributed value (10%)** — the weakest of the five: the problem is real but the cost of the current workaround is mostly social (volunteer dropout), with no measurable money or service failure at stake.

---

### 4.4 `ligabarrial` — LigaBarrial: Amateur 7-a-Side League Fixtures, Venues and Referees

**The real problem.** An amateur football league organises every weekend over WhatsApp: fixtures, pitch availability, referee assignment and last-minute cancellations. Two clubs regularly get scheduled on the same pitch at the same hour; referees are assigned by personal contacts, so a cancellation on match day leaves the league scrambling and sometimes unplayed; and the league has no trustworthy table, so the "champion" of the season is whoever's manager kept the best spreadsheet. Because results are entered the night before, half the clubs see a wrong table.

**Users and roles**

| Capability | Coach | League Organiser | Referee |
| --- | :---: | :---: | :---: |
| See the fixture calendar and the standings | ✔ | ✔ | ✔ |
| Enter a result for own club's fixtures | ✔ | ✔ | ✖ |
| Request / accept a fixture | ✔ (propose) | ✔ (schedule) | ✖ |
| Assign referees | ✖ | ✔ | ✖ |
| Declare referee availability | ✖ | ✖ | ✔ |
| Register venue availability blocks | ✖ | ✔ | ✖ |
| Publish notices to all clubs | ✖ | ✔ | ✖ |
| View referee assignment history | ✖ | ✔ | ✔ (own) |

**Main entities (5)**

- `Team` — `id, name, short_name, home_venue, FK coach_user` — a club in the league.
- `Player` — `FK Team, name, shirt_number, position` — the roster that makes stats meaningful.
- `Venue` — `id, name, pitch_count, address` — a sports complex with one or more pitches.
- `Fixture` — `FK home_team, FK away_team, FK venue, FK referee, kickoff_at, status, home_goals, away_goals, round` — the match, with its conflict surface.
- `VenueBlock` — `FK Venue, starts_at, ends_at, reason` — pitch unavailability (maintenance, league clash).

**Scope — 5 features**

1. **Round-robin fixture generation.** The organiser generates a double round-robin schedule for the teams. *DoD: for 6 teams the generated calendar has 30 fixtures, each team plays every other team exactly twice, and no team plays on two different days in the same round.*
2. **Venue conflict detection.** Scheduling a fixture on a pitch that is already occupied by another fixture or a block is rejected with an explanation. *DoD: attempting to schedule two fixtures on the same pitch and overlapping time returns an error and creates no second fixture.*
3. **Referee assignment and availability.** The organiser assigns referees; referees declare their unavailability windows; the assignment view warns when assigning an unavailable referee. *DoD: assigning a referee inside their declared unavailable window raises a warning and is blocked.*
4. **Results and live standings.** Coaches enter results; the standings table (played, won, drawn, lost, goals, points) is computed from results, never stored by hand. *DoD: after entering a 2-1 result the standings update for both teams, including goal difference and points.*
5. **Notices and organiser overview.** The organiser publishes a notice to all clubs; the dashboard shows upcoming fixtures, unassigned referees and round status. *DoD: a published notice appears on the logged-in coach's home page and in the league notice list.*

**The React view — "Fixture calendar + standings" at `/app/fixtures`**
- **What it renders:** a week/month fixture grid (rows = pitches, columns = time slots) where each fixture is a chip showing teams, the score once played, and a red badge when the slot conflicts with another booking; a standings table beside it with position, team, P/W/D/L, GF/GA and points, updating when a result is entered; a "referee coverage" strip showing which matches still need an official.
- **Endpoint:** `GET /api/v1/fixtures/?from=&to=` → fixtures with joined team/venue/referee names, computed scores and a `conflict` flag; `GET /api/v1/standings/` → computed rows.
- **Why it is more than a table dump:** the calendar is spatial (pitch × time) and carries conflict badges — the exact failure the league suffers from — while the standings animate when a result is entered.

**Explicit non-goals.** No registration fees or payments. No live scores / websockets (the panel refreshes explicitly). No player statistics beyond goals. No draw generation, no knock-out bracket. No email/SMS result notifications. No club logos or file uploads. No multi-league tenancy with different rule sets.

**Deployment path.** Same spine: Render free web service + Neon Free Postgres, seeded with 6 teams, ~20 players, 2 venues (one with 2 pitches), a full round-robin calendar, one pre-seeded conflict scenario, a set of referees with unavailability windows and some fixtures without a referee, and 3 seeded accounts (`entrenador@`, `comision@`, `arbitro@ligabarrial.test`). Same keep-alive ping.

**Hardest technical part + de-risking plan.** *Round-robin generation plus venue conflict detection.* Plan: implement the circle-method scheduler as a **pure function** (`round_robin(team_ids)`) with property-style unit tests (symmetry, count, one match per team per round); implement conflict detection as an overlap query identical in shape to the `hubdesk` booking rule. **De-risk experiment:** write `round_robin` and its tests on day 2 — the algorithm is well known and is the single place where a subtle off-by-one could poison the whole dataset.

**Defense panel — 6 questions**

1. *"How do you avoid two matches on the same pitch at once?"* → Overlap query plus a documented validation error; a pre-seeded conflicting fixture is visible in the demo on purpose.
2. *"How is the standings table computed?"* → Derived from the results in the database on every read — never hand-maintained, which was the actual source of the wrong table.
3. *"What happens when a match is postponed?"* → Status `postponed` excludes the fixture from the standings but keeps it in the calendar and the fixture history.
4. *"Why not just a Google Sheet?"* → A sheet cannot detect conflicts, cannot enforce referee availability, and silently becomes wrong — it was the workaround that produced the problem.
5. *"How is a referee prevented from being assigned to two matches at once?"* → Availability windows plus the same overlap check applied to the referee resource.
6. *"How would you scale to 40 teams and 3 divisions?"* → Same schema, recursive divisions as a FK on `Team`; fixture generation is already parameterised by team count.

**Rubric fit**

- **Backend correctness (30%)** — strong: algorithm with tests, derived standings, conflict rules.
- **React data consumption (15%)** — good: spatial calendar with conflict badges and derived standings, but the standings half is a table, so it is not the strongest of the five.
- **Architecture (15%)** — strong: pure functions separated from the ORM layer.
- **Security & data integrity (15%)** — strong: three roles, coach-scoped writes, organiser-only assignment.
- **Documentation & presentation (15%)** — strong.
- **Reflection & contributed value (10%)** — moderate: real community pain, but the clearest economic value ("the league loses games and referees") is less tangible than an operator's lost revenue or disputes.

---

### 4.5 `refugiomatch` — RefugioMatch: Explainable Adoption Matching for an Animal Shelter

**The real problem.** Shelters publish animals on social media and receive dozens of adoption requests through WhatsApp, answered one by one from memory. Staff spend hours repeating the same questions ("is it good with children?", "how big does it get?"), adopters withdraw because the real constraints were never told up front, and the shelter has no record of who asked for what or why a particular pairing was proposed. The result is mismatches, animals that stay longer, and hours of staff time spent on questions the data already contains.

**Users and roles**

| Capability | Shelter Staff | Volunteer | Adopter |
| --- | :---: | :---: | :---: |
| Create / edit animal profiles | ✔ | ✔ (drafts, staff publish) | ✖ |
| Publish / archive an animal | ✔ | ✖ | ✖ |
| Configure the matching criteria and their weights | ✔ | ✖ | ✖ |
| Submit an adoption request | ✖ | ✖ | ✔ |
| See matched pairs with a per-criterion explanation | ✔ | ✔ (read) | ✔ (own requests) |
| Propose a match / record the outcome | ✔ | ✖ | ✖ |
| Accept or decline a proposal | ✖ | ✖ | ✔ |
| See the shelter dashboard (animals by state, pending proposals) | ✔ | ✔ | ✖ |

**Main entities (5)**

- `Animal` — `id, name, species, breed, age_bucket, size, energy_level, good_with_children, good_with_dogs, status (available|reserved|adopted|unavailable), photo_url` — the animal profile (photos by URL only; no upload pipeline).
- `MatchCriterion` — `id, code, label, weight, direction (must_match|prefer|informational)` — the **admin-editable, explicit** criteria matrix that drives scoring.
- `AdoptionRequest` — `FK adopter_user, species, size, energy_level, has_children, has_other_pets, household_notes, status` — what the adopter is looking for.
- `Match` — `FK AdoptionRequest, FK Animal, score, computed_breakdown (JSON), proposed_by, status (proposed|accepted|declined|expired), created_at` — the proposal and its **auditable explanation**.
- `Adoption` — `FK Animal, FK AdoptionRequest, FK staff, agreed_at, notes` — the final outcome; writing it flips the animal's status.

**Scope — 5 features**

1. **Animal profile management with two authoring roles.** Volunteers prepare a draft, staff publish it; publishing requires the required attributes. *DoD: a profile missing a required attribute cannot be published; a volunteer's draft is visible to staff for approval.*
2. **Adopter request form with validation.** Adopters state what they are looking for; the form validates species/size/energy combinations. *DoD: an impossible combination (e.g. "small" + "high energy" for a species defined as calm-only) is rejected with a field error.*
3. **Explainable matching engine.** A deterministic weighted rules engine scores every (request, animal) pair and returns a **per-criterion breakdown**. *DoD: the API returns the total score together with each criterion's contribution, and the same input always produces the same output (no randomness).*
4. **Proposal workflow.** Staff propose a pair; the adopter accepts or declines; accepting creates an adoption and marks the animal `reserved`. *DoD: accepting a proposal sets the animal to `reserved`, creates the adoption row and records the decision history.*
5. **Shelter dashboard.** Counts of animals by state, pending proposals, and average time from availability to proposal. *DoD: the dashboard counters change when a proposal is accepted and match the API payload exactly.*

**The React view — "Match board" at `/app/matches`**
- **What it renders:** two columns — adopters on the left, animals on the right — with connector lines between candidate pairs whose thickness reflects the score; the selected pair opens an **explanation card** listing every criterion as a chip (`Good with children ✔ +25`, `Size ✖ −30`, `Energy ✔ +15`) and the resulting percentage, plus a "why" summary. A panel below shows the animals with no candidate match, which is the shelter's most actionable output.
- **Endpoint:** `GET /api/v1/matches/?request=<id>` → `[{animal, score, breakdown: [{criterion, label, weight, passed, delta}]}]`.
- **Why it is more than a table dump:** it visualises *relationships between two populations* and makes the reasoning of the system visible and inspectable — the panel can see exactly why a pairing was suggested, and why another was rejected. The "animals with no match" panel is the operational payoff.

**Explicit non-goals.** **No machine learning of any kind** — scoring is a transparent weighted rules engine, with the weights visible and editable in the UI. No photo upload pipeline (photos are URLs). No adoption payments or donations. No vet-record or medical-history management. No messaging/chat between adopter and staff. No public animal catalogue (the API requires auth). No volunteer shift scheduling. No native mobile app.

**Deployment path.** Same spine: Render free web service + Neon Free Postgres, seeded with 12 animals across species and sizes, 3 adopters with distinct preferences, a criteria matrix of 6 weighted criteria, and pre-computed matches so the board is populated on first load (scores are computed server-side at read time, so seed data stays consistent). Seeded accounts: `staff@refugiomatch.test`, `voluntario@refugiomatch.test`, `adoptante@refugiomatch.test`.

**Hardest technical part + de-risking plan.** *Making the scoring explainable and the state transitions consistent.* Plan: `score_pair(animal, request, criteria)` is a **pure function** returning `(total, breakdown)` — fully unit-testable, deterministic, with no randomness and no learned parameters; the UI renders exactly what the API returns rather than recomputing anything. The state transition (accept → adoption + animal status) is done inside a `transaction.atomic()` block. **De-risk experiment:** implement the pure function and 10 unit tests on day 2, including the edge case of a request with no matching animal (empty breakdown, score 0) — it is pure logic and cannot break later.

**Defense panel — 6 questions**

1. *"Is this AI? Why is there no model?"* → No: it is a deterministic weighted rules engine with weights stored in the database and shown in the UI; the same inputs always give the same score and every score is explained criterion by criterion. Machine learning would be less explainable, and shelter staff need to justify a pairing to a family.
2. *"How do you avoid matching a dog to a home with small children?"* → `good_with_children` is a `must_match` criterion with a weight that makes the pair ineligible, so it never surfaces as a proposal.
3. *"What if two adopters want the same animal?"* → The proposal workflow keeps one active proposal per pair; a second proposal is flagged as a conflict for staff to resolve, and only one adoption can exist per animal (DB constraint).
4. *"Does the system decide? Or do humans?"* → The system only proposes and explains; a staff member proposes and an adopter decides. The board explicitly shows unmatched animals, which is a human work list.
5. *"How do you protect adopters' personal data?"* → Role-scoped views (adopters only see their own requests), no public endpoints, minimal stored data, and the story is written into memoria §3.6.
6. *"What would you improve with more time?"* → Per-anomaly weights learned from outcomes — but only after collecting enough data, and only if the staff still trust the explanation; the honest answer is that transparency beats accuracy here.

**Rubric fit**

- **Backend correctness (30%)** — strong: admin-configurable criteria, transactional state transitions, DB constraints, pure-function tests.
- **React data consumption (15%)** — the strongest of the five in distinctiveness: a relationship board with an explicit per-criterion explanation.
- **Architecture (15%)** — strong: the rules engine is isolated as a pure domain module, clearly separated from persistence and presentation.
- **Security & data integrity (15%)** — strong: three roles, self-scoping for adopters, no public catalogue.
- **Documentation & presentation (15%)** — strong.
- **Reflection & contributed value (10%)** — good: staff time saved, fewer mismatches, and a genuinely interesting design question (explainability vs. accuracy). The economic value is less concrete than the operator stories.

---

## 5. Comparison at a glance

| | `hubdesk` | `tallerflow` | `huertacomun` | `ligabarrial` | `refugiomatch` |
| --- | --- | --- | --- | --- | --- |
| Real problem | Workspace double-booking, idle desks | Lost track of repair orders | Abandoned parcels, no rota | Fixture/venue/referee chaos | Adoptions answered from memory |
| Roles | 2 | 3 | 2 | 3 | 3 |
| Core entities | 5 | 5 | 5 | 5 | 5 |
| Features | 5 | 5 | 5 | 5 | 5 |
| React visualisation | Live spatial floor map | Kanban with WIP counters | Parcel map + rota | Pitch×time calendar + standings | Two-population match board with explanation |
| Algorithmic core | Overlap rules + lazy expiry | Atomic stock consumption | Fair rota distribution | Round-robin + conflict detection | Weighted explainable scoring |
| Extra infrastructure | None | None | None | None | None |
| Upload/storage needed | No | No | No | No | No (URLs only) |

---

## 6. Risk register (all candidates)

| Risk | Affects | Mitigation baked into the design |
| --- | --- | --- |
| Free web service sleeps after 15 min → cold app during the defense | All | Health endpoint + scheduled keep-alive ping + manual wake-up; Railway Hobby ($5/mo) as the final-month upgrade; the trade-off is written into memoria §3.8 |
| Render free Postgres expires at 30 days | All | Use Neon (permanent, no card). Render's free Postgres is explicitly rejected |
| Local SQLite data lost on redeploy | All | Postgres in production from day one; SQLite only for local dev; `DATABASE_URL` parsed in `settings.py` without extra dependencies |
| `CSRF_TRUSTED_ORIGINS` / `ALLOWED_HOSTS` not set → 403 in production | All | Set both from env at scaffold time, not on the day of the deploy; verified with a smoke test after every deploy |
| The React view is the most likely place to lose the 15% | All | Build the React ↔ API vertical slice in the **first 48 hours**; serve the bundle through Django from the start |
| Scope creep past 5 features | All | The 5 features are frozen in the proposal; anything else becomes "future work" in the memoria |
| The "real need" is judged as invented | All | Mandatory evidence step: 3 interviews + 5-question survey before the proposal is submitted (see §8) |

---

## 7. Scoring matrix and recommendation

**Weights (and why).** The PFM rubric grades comprehension and shipped quality, not size, and there is one defense attempt per academic quarter. So the weighting favours *a real, defensible problem that can actually be finished and deployed*, and only then rewards originality:

| Criterion | Weight | Rationale |
| --- | --- | --- |
| Real-world need strength | 25% | Rubric: "reflexión y valor aportado" (10%) plus the guide's rule "parte siempre de una necesidad real"; a panel that cannot believe the problem will not award depth anywhere else |
| Scope fit for 2–3 months solo | 20% | Rubric: backend correctness (30%) + architecture (15%) are lost entirely if the app is unfinished; one defense attempt per quarter makes a late failure fatal |
| Technical risk (lower is better) | 15% | Rubric: security (15%) and documentation (15%) both degrade when the core algorithm is flaky or unexplained |
| Deployability | 15% | Rubric: documentation/presentation (15%) requires a live public URL; a deployment that dies before the defense is an automatic loss |
| Defense defensibility | 15% | The 30-minute panel is where the 70% of the rubric that depends on explanation is actually cashed in |
| Distinctiveness / memorability | 10% | The tie-breaker: among equally sound candidates, the one the panel remembers scores higher on "notable" vs "acceptable" |

**Scores (1–10, 10 = best; technical risk is inverted so 10 = lowest risk).**

| Criterion | W | `hubdesk` | `tallerflow` | `huertacomun` | `ligabarrial` | `refugiomatch` |
| --- | --- | --- | --- | --- | --- | --- |
| Real-world need strength | 25% | **8** | 8 | 6 | 6 | 7 |
| Scope fit for 2–3 months solo | 20% | **8** | 7 | 9 | 7 | 6 |
| Technical risk (lower better) | 15% | 7 | 7 | **9** | 8 | 5 |
| Deployability | 15% | **9** | 9 | 9 | 9 | 8 |
| Defense defensibility | 15% | **9** | 8 | 7 | 7 | 8 |
| Distinctiveness / memorability | 10% | 8 | 6 | 8 | 7 | **9** |
| **Weighted total / 10** | | **8.15** | 7.60 | 7.85 | 7.20 | 7.00 |

**Recommendation: `hubdesk` (8.15).**
It wins on the two heaviest criteria *simultaneously* — a need with a measurable daily cost (double-booked rooms, idle desks, walk-around time, disputes) and a scope that fits 2–3 months solo — and it does not rely on winning anywhere else. Its React view (a live spatial floor map with counters and auto-refresh) is the most clearly "a product, not a table" of the five, which protects the 15% that is hardest to earn. Its hard part (conflict-free booking plus no-show expiry with **no** background worker) is a single, pure, unit-testable rule set with a well-known, honest answer to "why no Celery?" — the kind of question that makes a panel lean in rather than check the clock. And it needs zero extra infrastructure: no uploads, no external API, no workers, no payments, five entities, five features.

**Runner-up: `huertacomun` (7.85).**
**Why it lost:** it is the safest build in the set (lowest technical risk, fastest to a working demo), but it loses on the heaviest criterion. Its pain — abandoned parcels and watering disputes — is real but the cost of the current workaround is mostly social (volunteer dropout) with no money, service failure or conflict at stake, so the "valor aportado" argument is thin. Its React view, a coloured parcel grid, is also the closest of the five to "a CRUD screen with colours", which puts the 15% React criterion at risk. **Pick it instead if the priority is maximising the probability of a finished, deployed project rather than maximising the grade.** Its "pure function for the rota" architecture story is a genuinely good one and is fully transferable to `hubdesk`.

**Why the other three lost:**
- `tallerflow` (7.60) — a real problem and a clean build, but a work-order system with a kanban is the most familiar artefact in every PFM cohort; the panel has seen it dozens of times, so "distinctiveness" and "memorability" both land at "acceptable" rather than "notable".
- `ligabarrial` (7.20) — good problem, but the value is community-level (lost fixtures, cancelled games) and its React view is half table (the standings). It also carries the widest scope for the least rubric payoff: player rosters and three roles inflate the build without strengthening any criterion.
- `refugiomatch` (7.00) — the most memorable and the best React story, but the highest technical risk for a student who is still consolidating backend and frontend skills: three roles, admin-configurable weights, a JSON breakdown column, photo URLs, a proposal workflow and an adoption state machine. The panel will also ask "why not machine learning?", and the honest answer ("we chose deterministic transparency") is strong — but only if the student can defend it without hesitation. It is the right choice for a confident student, not the safest one.

---

## 8. One-page proposal skeleton (filled with the recommended candidate)

Use this verbatim as the skeleton of the one-page proposal the teaching team validates before any code is written.

---

### PROPOSAL — HubDesk: Booking and Live Occupancy for a Co-working Space

**1. Problem** *(max ~120 words)*
Small co-working operators (10–60 desks) manage desks and meeting rooms through a WhatsApp group and a whiteboard. Reservations live in messages that scroll away, so rooms are double-booked; members arrive at an occupied desk; and the operator cannot answer "how full is the space right now?" without walking the floor. The cost is measurable: double-booked rooms become disputes, unused desks are paid-for capacity, and walking the floor to check occupancy is staff time. The current workaround keeps **no history at all**, so utilisation cannot even be measured to justify the next rent increase.

**2. Evidence of need** *(this block is what makes section 1 credible)*
- 3 semi-structured interviews with co-working operators / space managers (30 min each, script of 6 questions).
- 5-question survey of 10 members of one local space.
- Teardown of 2 existing tools (e.g. a generic booking app and a paper workflow) with a short "what each fails to do" table.
- Attachment: one-page annex with notes, anonymised quotes and the two screens that are painful.

**3. Users and roles**
- **Member** — books and checks in to desks/rooms, sees own bookings and the anonymised floor map, reports incidents.
- **Community Manager** — manages spaces and blocking periods, releases any booking, resolves incidents, sees detailed occupancy.
- Permission matrix attached (Member vs Manager × 9 capabilities).

**4. Minimum scope — 5 features** (each with its acceptance criterion)
1. **Accounts and two roles** — signup/login, Django groups `member`/`manager`; manager URLs return 403 for members. *AC: a member opening a manager URL gets 403; the seeded manager does not.*
2. **Spaces and availability** — the manager creates desks/rooms with zone and capacity; members query availability by day. *AC: a desk created in the manager UI appears in the availability grid and on the React map without a redeploy.*
3. **Conflict-free booking** — bookings are validated server-side against overlapping reservations, with a DB constraint as backstop. *AC: an overlapping booking returns a form error, creates no row, and the message is visible.*
4. **Occupancy lifecycle and no-show expiry** — check-in marks occupancy; unclaimed reservations expire at read time with no background worker. *AC: a stale seeded booking reports `expired` and frees its tile with no job running.*
5. **Incidents and manager overview** — members report space incidents; the manager resolves them and reads the day's occupancy counters. *AC: an open incident appears in the manager queue and leaves the open counter once resolved.*

**5. Main data-model entities**
| Entity | Key fields | Relations |
| --- | --- | --- |
| `Space` | kind (desk\|room), label, zone, capacity, is_active | 1—N Booking, 1—N SpaceBlock, 1—N Incident |
| `MemberProfile` | plan (label only), home_zone, joined_at | 1—1 User |
| `Booking` | starts_at, ends_at, status | N—1 Space, N—1 User |
| `SpaceBlock` | starts_at, ends_at, reason | N—1 Space, N—1 User (manager) |
| `Incident` | category, description, status | N—1 Space, N—1 User (reporter) |

**6. React view(s)**
**`/app/floor` — Live floor map.** A spatial floor plan (CSS grid: rows = zones, cells = desks and rooms) where each tile is colour-coded by live state — free / reserved / occupied / blocked / incident — with a legend, "occupied now: X of Y" counters, a server clock and an "updated Ns ago" freshness indicator; clicking a tile opens a detail card (status, until when, occupant first name for managers only). Data comes from the application's own API, `GET /api/v1/spaces/?at=<ISO timestamp>`, re-fetched every 30 seconds from the **same origin** (session cookie + CSRF header, no CORS, no second host).

**7. Technical approach**
- Backend: Django 5.2 + Django REST Framework; session authentication with CSRF; role checks via Django groups and permission mixins; business rules isolated in a testable service layer; PostgreSQL in production (Neon), SQLite locally.
- Frontend: React + TypeScript + Vite, built at deploy time into Django's static files and served by WhiteNoise — a single deployable service, one origin, no CORS.
- Deployment: Render free web service (managed TLS, public HTTPS) + Neon free Postgres; `DEBUG=False`, secrets in environment variables; `manage.py seed_demo` provides deterministic demo data and one test account per role; a scheduled keep-alive ping handles the free tier's 15-minute sleep.
- Out of scope: payments/invoicing, calendar sync, hardware badges, e-mail/SMS notifications, native mobile app.

**8. Success criteria for the project**
- A public HTTPS URL where the seeded member and manager accounts log in and the live map reflects the database.
- A documented README (install, environment variables, tests, public URL, credentials) and a repository with pinned dependency versions and no secrets in history.
- A memoria covering sections 3.1–3.8 with the ER diagram, the architecture diagram, the security checklist and the real errors encountered and how they were fixed.
- A 30-minute defense in which the live map updates after a check-in, plus one small code change performed on request.

---

## 9. Risks of this selection and the earliest cheap experiment for each

**Risk 1 — The panel may not believe the problem is real.**
The student has no domain background, so "a co-working operator told me" is the only thing that separates this from a generic CRUD project, and the guide explicitly demands starting from a real need. If the evidence is thin, section 3.1 of the memoria ("definición del problema") and the 10% reflection criterion both collapse.
*Earliest cheap experiment (week 1, ~4 hours):* write a 6-question interview script, book three 30-minute calls with co-working operators or space managers (LinkedIn, local coworking websites, the operator of a space near the university), and run one 5-question survey with 10 members of a single space. Deliverable: a one-page annex with anonymised quotes. **Do this before writing the proposal** — it is also the evidence the proposal needs.

**Risk 2 — The free-tier deployment fails or sleeps at the wrong moment.**
Render's free web service spins down after 15 minutes and takes about a minute to wake; the filesystem is ephemeral; Render's own free Postgres expires after 30 days. A demo that opens on a "loading" page, or a database that vanished, costs the 30-minute defense.
*Earliest cheap experiment (day 1, ~2 hours):* deploy a bare "hello world" Django to Render pointed at a Neon database, set `CSRF_TRUSTED_ORIGINS` and `ALLOWED_HOSTS`, add the `/health/` endpoint and the keep-alive ping, then measure the cold-start time and the ping cadence. Decide then — not in week 9 — whether the final month moves to Railway Hobby ($5/month) for a no-sleep instance on the same URL.

**Risk 3 — The React view is the weakest link and it is 15% of the grade.**
The student is still consolidating frontend skills. The classic failure mode is a backend that works and a React view that fetches nothing, fetches once, or breaks behind the deployment's authentication. This is the most common way a strong backend project still scores "acceptable" overall.
*Earliest cheap experiment (day 2, ~3 hours):* build the vertical slice before anything else — one DRF endpoint returning the space states, one React component rendering the floor grid from it, the bundle served through Django via WhiteNoise, and the session+CSRF fetch working **in the deployed URL**, not just in `localhost`. If the deployed round trip works, the risk is retired; if it does not, the failure mode is discovered in week 1 rather than week 8.

**Watch list (not top-3, but keep them visible):**
- *Scope freeze.* The five features above are the ceiling. Anything else is "future work" in the memoria, not a task.
- *Two roles are not enough if they are cosmetic.* Every one of the nine capabilities in the matrix must be enforced server-side and be visible in the demo; the panel will ask how `member` is prevented from doing something.
- *The no-show expiry reads like a shortcut.* Present it as a deliberate, tested trade-off (no Celery, no Redis, no second service), not as an omission.
- *The `hubdesk` domain must be told, not shown.* The narrative is that the operator's problem is invisible without history; the floor map is the proof, and the counters are the sentence.

---

## 10. What happens after the decision

1. The student picks one candidate. The slug becomes the OpenSpec change name (`hubdesk`, `tallerflow`, `huertacomun`, `ligabarrial`, `refugiomatch`).
2. `openspec/changes/<slug>/` is created and this exploration is referenced from `openspec/changes/<slug>/exploration.md`.
3. The proposal phase (`sdd-propose`) drafts the one-page proposal from §8 (or the equivalent block for the chosen candidate), including the evidence annex.
4. Only after the teaching team validates the proposal does implementation begin.

**Do not create the change directory before the student chooses.**
