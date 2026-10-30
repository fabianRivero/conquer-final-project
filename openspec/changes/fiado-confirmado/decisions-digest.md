# Decisions Digest — `fiado-confirmado`

> **Condensed input, not a deliverable.** Compresses `openspec/changes/fiado-confirmado/exploration.md` (491 lines) and `evidence-annex.md` §4 for the design phase under a small context budget. Adds no decisions; the exploration record stays authoritative where abbreviated.

## 1. Owner's confirmed decisions

| # | Decision | Consequence |
| --- | --- | --- |
| O1 | Replanned from scratch: client-confirmed `fiado` is the central product, not an addendum. | New variant with own scope, not a feature of `tienda-barrio`. |
| O2 | `fiado-confirmado` **supersedes** `tienda-barrio`; proposal, specs and design abandoned, not amended. | Old folder untouched; new specs are delta specs of a new change, never edits in place. |
| O3 | Inventory tracked by movement: catalogue with prices, charge lines on every `cargo`, stock derived from recorded movements. | Catalogue + charge lines in scope; T1 bounds the "stock" claim. |
| O4 | Planning only. | No code, scaffolding, config change. |

**S1 — reading of the client's statement.** Confirmed charges: full detail, itemised. Unconfirmed charges: a **summary row** (date, amount, `Confirmar` action) whose itemisation is revealed **only inside the `Confirmar` action**. The client always sees what they owe. Rejected: show nothing until confirmed — that lets the statement understate the debt, the very misunderstanding the product exists to remove. To be confirmed with the owner (open item 2).

**S2 — no external research lane.** No external research was run; evidence = the interview instrument (the gate) + the internal exploration record. Public figures are context only, never evidence about the fiado practice (Regla 3).

## 2. Exploration decisions D1–D10

| # | T | Decision | Rationale |
| --- | --- | --- | --- |
| D1 | T1 | Keep catalogue; claim only a movement-derived ceiling `existencias_registradas`. Reject cash sales, reject a physical count. | Claim bounded by what is recorded. |
| D2 | T1 | Catalogue's load-bearing job = price snapshot on each `CargoLinea`, not the stock figure. | Charge priced at the moment of the charge. |
| D3 | T2 | One credential: per-client `codigo` on a slip, presented per request; shop's device at the counter primary, client's phone secondary. | Confirmation must happen at the counter, in the owner's presence. |
| D4 | T3 | Client is not a Django role, group or session: bearer credential scoped to one `Customer`, resolved server-side. | Keeps the `dependiente` 403 boundary structural. |
| D5 | T4 | A `cargo` never depends on the confirmation: counts as debt once recorded. | Otherwise a client could erase a debt by refusing to confirm. |
| D6 | T4 | A confirmation never expires; what ages = 7-day `sin_confirmar` escalation flag, derived on read. | An expiry would invalidate a real debt or need a re-issue mechanic. |
| D7 | T5 | A confirmed charge is immutable; corrections only by appending a `nota de crédito`. A disputed charge still counts as debt and still ages. | A dispute must not become a free cancellation. |
| D8 | T6 | Defensible on a served pain, a capped feature count and a named fallback — not on being a better-scoped project. | Same weights: 7.45 vs previous `fiado` 8.15; difference paid deliberately. |
| D9 | T6 | Two cut-lines declared now, before the timeline: the 30-day `serie_caja` chart, then `existencias_registradas`. | Scope discipline is graded; the cut must be declared in advance. |
| D10 | T7 | Six of six original questions survive; seven new ones become decisive; three new decision rules join the checklist. | Script must decide the confirmation flow, the catalogue and the stock claim. |

## 3. Resolution of T1–T7

D = decision · C = constraint · R = rejected alternative and why · → = consequence into design.

### T1 — Cash sales vs movement-derived stock

D. Keep catalogue; claim only a movement-derived ceiling `existencias_registradas` (`Σ entradas − Σ salidas registradas`): upper bound on real stock, never a count.
C. No rule depends on it (no stock-based refusal, no price or suspension from it); qualifier travels with the data (machine-readable, in API); `stock` banned as a field name.
R. Cash sales — behaviour, not category: 100–400 hand-entered transactions/day is a POS without hardware; owner never recorded a cash sale and will not start (A.3.1). Physical count — the action the shop never adopts; drift has four sources (cash sales, breakage, supplier short-delivery, `consumo propio`): no count without a count.
→ True stock not knowable here (say so on screen + memoria); `DayClose` anchor not cut candidate (`caja` has a measuring ritual, `existencias` none: one calibrated, one ceiling); cut-line 2 drops the figure if N7 shows no tracking.

### T2 — How the client reaches their page without e-mail or SMS

D. One credential, two surfaces of the same page: per-client `codigo` on a printed slip, presented per request. Primary: the shop's own device at the counter, while the goods change hands and the owner stands there. Secondary: the client's own phone, for the remote consultation ("a page that shows what they owe"). Same credential, same URL, no session.
C. The slip can carry a long high-entropy token a spoken code cannot; the client spends ~10 seconds on a device already in hand; a smartphone is not guaranteed — the interviews must test it.
R. A spoken short code/PIN as sole mechanism — remembering is what the `libreta` is for, and a 4-digit code is guessable (needs a throttle). E-mail/SMS/native app — free tiers block outbound SMTP; the owner's instruction excludes them.
→ If the client never opens the page nothing breaks: the `cargo` exists, counts as debt, ages, can be suspended as before; statement shows a summary row, board `sin_confirmar` with its age. The product degrades to the previous `fiado` product, not to nothing.

### T3 — The third actor

D. Client = bearer credential scoped to exactly one `Customer`, resolved server-side on every request; never a Django group, a Django `User` or a session; scope from the credential only (never a URL segment, body field or session key).
C. A client scope may never exist inside a staff session, and a staff session may never be upgraded to a client scope. Staff scope = `session["shop_id"]`, client scope = the credential. Client payload = that customer's own data only: no other alias, no shop total, no `caja`, no `posición real`, no other `credit_limit`. A `dependiente` session reaches no client endpoint. A pending charge is shown as date + amount; line detail only if `confirmado`, otherwise only inside the confirmation action.
R. A third Django group — blast radius = the whole permission model (every `IsAuthenticated` passes for a client, every staff endpoint needs a special case, the allowlist needs a third schema plus a branch per view). A client session — helper logged in at the tablet, client types the code, one cookie then holds both a staff scope and a customer scope.
→ The serializer allowlist gains a third, disjoint schema class, so "no shop data in a client payload" is a schema property, not a promise. Wording amended, not deleted: "two **shop** roles enforced on the server; a third, external principal scoped to one customer"; "credit book owner-only **among the staff**". One bounded erosion of the 403 boundary: the `dependiente` may present the charge in hand and receive the confirmation — no list, balance or ageing; never holds a client scope (client types their own `codigo`); records `facilitado_por`. Rationale: "the notebook stays in the drawer, except for the one page the client is looking at right now" — only if the interviews require it (N5).

### T4 — Adoption friction and graceful degradation

D. A `cargo` never depends on the confirmation: it counts as debt the moment it is recorded; the confirmation is an attestation that enriches the record. A confirmation stays open indefinitely — no expiry. What ages instead is the flag: an unconfirmed charge older than 7 days escalates on the owner's ladder as *revisar*, derived on read (ADR-8: no worker, no Celery, no Redis). Only three things close it: the client confirms, the client disputes, the owner appends a `nota de crédito`.
C. Nothing about the balance depends on the confirmation — the load-bearing safety property. Friction ranked: the owner must ask (a social cost — "do you think I would cheat you?"), not solvable by software; the client must stop; the shop must have a device; the client may not have a browser (remote surface only).
R. An expiry — it would either invalidate a real debt or require a re-issue mechanic that adds owner work; both worse than a permanent visible flag.
→ Graceful degradation is a property: with no confirmations the product still delivers the append-only ledger, FIFO allocation, ageing, automatic suspension, the `posición real` equation and the `cierre del día`. An unconfirmed charge is an ordinary `cargo` — ages into `vigente`/`envejecido`/`viejo`/`cronico`, can trigger the automatic suspension, can be paid.

### T5 — Dispute resolution

D. The client cannot amend the owner's record — that would let a client erase a debt. Exactly two outcomes: Confirmar (append a `Confirmacion`, `estado = confirmado`; the itemisation becomes visible in the client's statement) and Disputar (append `estado = en_disputa` with optional `importe_reclamado` and `nota`). The owner arbitrates — his shop, his ledger, his commercial record — but the arbitration must be recorded and visible to the client, or the client is left in the dark, the failure mode the product is about.
C. A confirmed charge is immutable: no `PUT`, `PATCH` or `DELETE` on a `cargo` or a `Confirmacion`, ever; corrections only by appending. A disputed charge still counts as debt and still ages — the dispute is a flag, not a credit, otherwise disputing is a free cancellation. The client can always escalate: the statement shows the dispute and its history; the `Confirmacion` record is the client's recourse against a fabricated attestation, and that limit must be stated in the memoria.
R. No client-side amendment of the ledger, ever — it would let a client erase a debt.
→ Accept the discrepancy → append a `nota de crédito` for the difference (6,40 − 4,20 = 2,20 €), the `cargo` row unchanged and immutable beside it, outstanding 4,20 € via the normal FIFO/credit-note arithmetic; reject → no entry, the owner asserts the original figure, state stays `en_disputa`. Who may append: `dueño` (cargo, pago, nota de crédito; never edit or delete); `dependiente` (`CashMovement`, `DayClose`; never the credit book except the narrow T3 facilitator capability, which appends nothing); `cliente` (a `Confirmacion` on their own charges only). The amendment path is not new: the previous design already had the `nota de crédito`; the confirmation adds the evidence, not a second amendment path.

### T6 — Scope re-evaluation

D. The categorical POS exclusion ("no `Product`/`Sale` table, therefore not a POS") is FORFEIT — the catalogue exists by O3. The behavioural exclusion ("we record only what the shop already records") SURVIVES and is now load-bearing, stronger stated in data-entry volume rather than tables: ~5–15 recorded movements a day against 100–400 daily cash sales, none ever recorded.
C. What replaces the defence: the subject is the obligation, not the exchange (no `venta`, till, receipt, payment tender, drawer, barcode, purchase order); the catalogue is a vocabulary, not an inventory system (~30 seeded rows, not 1500; no supplier, cost, `coste_medio` or reorder point; `precio` is a default the owner may override); the price snapshot is the mechanism — `precio_unitario` frozen at the moment of the charge, so a catalogue with live prices is a price list while one producing immutable snapshots in an append-only ledger is a notary; the ratification has no analogue in the POS category (the strongest single line of the defence); the stock claim is bounded rather than hidden.
R. Nothing else: the scope does not resurrect the point of sale and does not become "products + sales + dashboard" — there are no sales, and the `cargo` (an obligation with a counterparty who can attest it) is the unit of record.
→ The whole score gap is scope fit (−2) and technical risk (−1): seven capabilities instead of five, a third principal class, a second surface, a second credential mechanism, three new entities, a dispute state machine. Cut-lines now, in order: (1) the 30-day `serie_caja` chart, a React element not a capability — hero equation and ladder survive; (2) `existencias_registradas`, only if N7 shows no stock tracking — the capability drops to one figure; (3) the remote client consultation — confirmation stays at the counter only. Not cuttable: the append-only ledger · the `dependiente` 403 boundary · the React view consuming the app's own API at the public URL · the public HTTPS URL with `DEBUG=False` and seeded data. `margen` remains the declared fallback if credit is not a real practice.

### T7 — Evidence: the delta to the existing script

D. The script is not rewritten: six of six questions survive (four become more decisive), seven are added (N1–N7), three decision rules join the checklist (Reglas 4–6). Recruitment plan and capture sheet unchanged — the sampling problem has not changed.
C. The gate stays a gate: interviews completed and the annex filled before the proposal goes to the teaching team. The new scope depends on a behaviour, not only on a practice, so the gate's stakes rise.
R. Nothing rejected; the original instrument is extended, not rewritten.
→ Placement: N1 after Q1; N3 after Q3 (never cold — it invites a polite "sí"); N6 after Q3; N2 and N7 after Q4; N5 after Q5; N4 after Q6. N3 is asked in the third person («un cliente aceptaría»), like Q1, so the owner is not put on the spot. The three new rules decide the confirmation, the catalogue and the stock claim — the three things the previous script never asked about.

### The thirteen questions (verbatim — read aloud)

| # | Pregunta | Decides |
| --- | --- | --- |
| 1 | «Cuando un cliente te pide fiado, ¿qué haces? ¿Lo anotas en algún sitio —la libreta, el móvil, una lista— o se queda en tu cabeza?» | KEEP+ — items or amounts; bridge to N1 |
| 2 | «¿Sabes siempre cuánto dinero te deben en total? ¿Y desde cuándo le deben cada uno?» | KEEP, core |
| 3 | «¿Te ha pasado que alguien te debe y no sabes cuánto, o que se pierde la libreta?» | KEEP — dispute motivation |
| 4 | «Si cierras la caja al final del día, ¿el dinero que hay en el cajón es el que esperabas? ¿Notas que falta algo?» | KEEP — `caja` anchor: ritual or fiction? |
| 5 | «Cuando te vas unos días —enfermo, vacaciones—, ¿alguien puede saber quién te debe o cuánto hay en el almacén?» | KEEP↑ decisive — who gives the fiado in the owner's absence |
| 6 | «¿Si una herramienta te dijera a quién hay que recordarle el pago hoy y cuánto dinero es de verdad el tuyo, ¿la usarías? ¿Qué te quitaría de cabeza?» | KEEP — adoption; N3 extends it |
| N1 | «Cuando anotas lo que se lleva un cliente, ¿anotas **qué productos** y el importe, o solo el importe?» | the catalogue |
| N2 | «¿Anotas las ventas que te pagan en efectivo, una por una, o solo el total del día?» | T1(a) vs T1(b); "one by one" reopens drift |
| N3 | «¿Crees que un cliente aceptaría **confirmar** en el momento lo que le has fiado, o lo vería como desconfianza?» | the whole confirmation flow |
| N4 | «¿Usaría tu cliente un móvil para esto, o lo harías en la tablet de la tienda?» | T2's surface; device presence |
| N5 | «Cuando tú no estás, ¿quién da el fiado: tú, un familiar o un ayudante?» | T3's facilitator capability |
| N6 | «¿Qué harías si un cliente te dice que le debes menos de lo que anotaste?» | T5 — dispute frequency and object |
| N7 | «¿Llevas las existencias de algún producto de forma aproximada, o las cuentas?» | T1's stock claim; cut-line 2 |
| — | Optional open: «¿Qué parte de tu negocio no controlas bien y te cuesta dinero?» | KEEP |

## 4. Capability list (the proposal is built from exactly this list)

Seven capabilities, inside the guide's 4–8 band, each with a grader-tickable acceptance idea.

| # | Capability | Acceptance idea |
| --- | --- | --- |
| 1 | Cuentas, roles y credenciales del cliente | `dependiente@tienda.test` → 403 on `/api/v1/clientes/`; no `codigo` in any `dependiente` payload; `dueño` issues a shop-unique, rotatable `codigo`. |
| 2 | Catálogo de productos y precios | Seeded `Producto` at 1,20 € returned by the catalogue API as the default price of a charge line; catalogue holds only goods eligible for fiado. |
| 3 | Cargos con líneas de producto | Two-line `cargo` of 6,40 € → two `CargoLinea` rows + one `LedgerEntry` of 6,40 €; later catalogue price change leaves `precio_unitario` untouched. |
| 4 | Pagos, notas de crédito, antigüedad y suspensión | €30 `pago` retires the oldest charge first and drops `antiguedad_max_dias` 45→10; a 45-day-old unpaid charge suspends the customer (reason in `suspended_reason`) with no human action; a new charge → 422, no row created. |
| 5 | Confirmación y disputa del cliente | Valid `codigo` → client confirms a pending charge, API returns `confirmado_en`, state becomes `confirmado`; itemised confirmed charges appear in the client's statement; a `dependiente` session reaches no client endpoint. |
| 6 | Disputas y corrección por `nota de crédito` | Disputed 6,40 € charge, `importe_reclamado` 4,20 €, `dueño` resolves with a 2,20 € `nota de crédito` → 4,20 € outstanding, `cargo` row unchanged; rejected dispute → 6,40 € and state `en_disputa`. |
| 7 | Posición real, cierre del día y existencias registradas | €30 `pago` raises `caja` by 30 € and leaves `posicion_real` unchanged; day close stores `esperado`, `contado`, `desviacion`; `existencias_registradas` carries its ceiling qualifier, and no endpoint refuses a `cargo` for lack of stock. |

**Conditional eighth, decided by interview N5:** *facilitar la confirmación por el `dependiente`* — the helper may present a pending charge and receive the client's confirmation, records `facilitado_por`, and reaches no list, no balance and no ageing. Added only if the interviews show the helper gives the fiado.

**Two React surfaces, one bundle.** `/app/posicion` (owner) and `/app/cliente` (client) — same Vite bundle, WhiteNoise, same origin, two credential modes (session + CSRF for the owner; per-request `codigo` for the client). No charting library (ADR-12 carries), no CORS, no second host.

## 5. Out of scope, and why

| Out of scope | Why |
| --- | --- |
| Point of sale, till, `venta` records, receipts, barcode, payment tender, drawer | ~100–400 hand-entered cash sales/day is a POS without the hardware; a shop that does not record its cash sales cannot have a POS, and a POS cannot ratify a debt |
| Physical stock count, `conteo`, inventory adjustments | A count requires a count; counting is the one action the shop will not adopt (A.3.1) |
| Purchase cost, `coste_medio`, margin, suppliers, purchase orders, reorder proposals | `margen`'s domain; the catalogue is a vocabulary, not a cost model |
| E-mail, SMS, push notifications, reminders | Outbound SMTP blocked on free tiers; the confirmation is designed to be in person |
| Client accounts with passwords, self-registration, password reset | The client has a scoped credential, not an account — keeps "customer accounts" out even while "customer portal" is in |
| Native mobile app, QR/barcode scanning | The credential is typed; the surface is a web page |
| Editing or deleting a `cargo`, a `Confirmacion` or any ledger row | Structurally impossible: append-only ledger, no `PUT`/`PATCH`/`DELETE` exposed |
| Background worker, Celery, Redis, WebSockets, a second infrastructure dependency, a separate SPA host | ADR-8 and ADR-1 carry over unchanged |
| Debtors seeing anything but their own data; the client seeing `caja`, `posición real` or another's balance | The client column of the matrix is scoped to one `Customer` by construction |
| Online payments, card, transfers · debt collection, interest, credit scoring, automated decisions, automated reminders · fiscal invoicing, tax reporting, multi-shop, multi-branch, SaaS billing · file uploads, photographs of the `libreta` | No reason recorded in the source |

**Now in scope that was out:** the catalogue with prices, the charge lines, the client-facing page, the confirmation, the dispute path, the per-client `codigo`.

## 6. Inheritance map for the abandoned change `tienda-barrio`

The previous folder is not modified and not deleted; it stays on disk as history.

### 6.1 Carries over (C1–C14)

| # | What | Where it lives now | Note for the design phase |
| --- | --- | --- | --- |
| C1 | Append-only ledger, derived balances, FIFO allocation, ageing buckets | `domain/allocation.py`, `domain/ageing.py`, `domain/evaluation.py`, `domain/position.py` | ADR-2: nothing derived is stored |
| C2 | ORM-free pure domain module | `backend/tienda/domain/` (no Django import) | ADR-3 carries; new pure functions `confirmacion_efectiva(cargos, confirmaciones)`, `estado_cargo(cargo, confirmaciones)` |
| C3 | Two shop roles + the `dependiente` 403 boundary | `api/permissions.py`, serializer allowlists | ADR-5, ADR-6 carry; allowlist gains a third, disjoint schema class |
| C4 | Session + CSRF for the staff surface | `SessionAuthentication`, `CsrfViewMiddleware` | ADR-4 carries for the staff surface only; client surface uses no session |
| C5 | Same-origin React mount | Vite → `STATIC_ROOT` → WhiteNoise | ADR-1 carries; one bundle, two routes |
| C6 | Deployment spine | Render free + Neon free + WhiteNoise + keep-alive + `seed_demo` | Carries verbatim: no new env var, no new infrastructure |
| C7 | Seed plan | `manage.py seed_demo` | Extends: catalogue, charge lines, per-client `codigo`, one `en_disputa`, one old `sin_confirmar`, most `confirmado` |
| C8 | Additive `posición real` (`caja + Σ outstanding`) | ADR-9 | A `pago` moves `caja`, not `posicion_real` |
| C9 | Decimal on the wire (JSON strings) | ADR-13 | Carries; "the four buckets sum exactly to the outstanding" stays checkable |
| C10 | Per-row DB constraints + transactional cross-row checks | ADR-14 | New rule `amount == Σ CargoLinea.total` joins the transactional set |
| C11 | The 422 domain-error contract | `api/exceptions.py` | New codes `codigo_invalido`, `disputa_abierta`, `lineas_descuadradas`, `cargo_ya_confirmado` |
| C12 | Hand-rolled SVG chart, no library | ADR-12 | Carries |
| C13 | Landmine list and risks | design §10.5, Part G | New landmine: a `codigo` leaking through a staff payload is a data-protection failure, not a cosmetic bug |
| C14 | Evidence discipline — interviews are a gate, no public source cited for the fiado practice | Part D.5 | Tightens: scope depends on a behaviour, not only on a practice |

### 6.2 Abandoned (A1–A9)

| # | What was abandoned | What replaces it |
| --- | --- | --- |
| A1 | The categorical POS exclusion ("no `Product`/`Sale` table") | The behavioural exclusion: no sale is ever recorded, catalogue = vocabulary with a price snapshot (T6) |
| A2 | The "exactly two roles" claim about the whole system | Two shop roles + one external, customer-scoped principal that is not a role (T3) |
| A3 | The 5-capability contract (`submission-notes.md` §10) | The 7-capability contract in §4 |
| A4 | The 34 requirements / 47 scenarios in `specs/` | New delta specs for the new change; nothing amended in place, old specs stay as history |
| A5 | `evidence-annex.md` and its checklist as they stand | A new annex for the new change (same instrument, six kept + seven added, three rules added); the old annex stays untouched in the old folder |
| A6 | `Shop.usuarios` + `session["shop_id"]` as the only scope mechanism | Two scopes, two mechanisms: staff scope = session, client scope = credential with no session |
| A7 | The single-view React plan | Two routes in one bundle, two credential modes |
| A8 | The rationale "the notebook stays in the drawer" | "… except for the one page the client is looking at right now" — only if the interviews require it |
| A9 | The proposal's scope statement | A new one, built from §4, in Spanish, for the teaching team |

### 6.3 Must NOT be silently reintroduced

- A `venta`/`Sale` table, a till, a receipt, a drawer balance — the defence depends on their absence.
- A stored `saldo` column — ADR-2.
- A `PUT`/`PATCH`/`DELETE` route on any ledger row.
- A third Django group, or a client in `auth_user`.
- A stored `stock` field with no qualifier.
- A second infrastructure dependency, a second origin, a CORS configuration.

## 7. Open items carried forward (all twelve)

| # | Open item | Decides |
| --- | --- | --- |
| 1 | Run the evidence gate: three semi-structured interviews, revised script (six kept, seven added, N1–N7), capture sheet extended, three new decision rules. No proposal to the teaching team before it closes. | The confirmation (R4), the catalogue (R5), the stock claim (R6) |
| 2 | Confirm the owner's sentence about the item list appearing only after confirmation (see S1). | The client statement's shape |
| 3 | Client-credential transport: per-request credential (recommended) vs a client-scoped session with an explicit no-coexistence rule. Invariant already fixed. | The client auth mechanism |
| 4 | `codigo` parameters: length, alphabet, entropy, expiry or rotation policy, rate limiting. The printed slip carries a long token, a spoken code cannot — delivery is part of the parameter. | The credential's shape and throttle |
| 5 | Whether the `dependiente` gets the facilitator capability (N5), and its exact bound if so. | The conditional eighth capability |
| 6 | Whether the client sees their own `credit_limit` — it explains a refused charge and is their own data, but a commercial figure. | The client payload's field list |
| 7 | `Confirmacion` derivation vs storage: derived from the append-only rows (ADR-2, recommended) or stored and reconciled (the previous `Customer.status` pattern). | The persistence of the confirmation state |
| 8 | The `precio` deviation rule: catalogue price is a default, the owner may charge another amount, the line records what was actually charged, no extra friction. | `CargoLinea` write rules |
| 9 | The `dia` of the escalation flag (`sin_confirmar` older than 7 days → *revisar*), derived on read with no background worker. | The ageing rule for unconfirmed charges |
| 10 | Re-score the variant choice against the interview results (new scope 7.45 vs previous `fiado` 8.15). | If R4 empties → `fiado desglosado` (7.80, no client portal), proposal rewritten against that scope; if R1 empties → `margen` (7.70), as it already was |
| 11 | Re-check the guide's 4–8 band against the final list of seven (plus the conditional eighth); publish the two cut-lines with the proposal. | The published scope and the declared cuts |
| 12 | Carry the `caja` finding into the honesty section: daily cash sales not recorded, so `caja` is the recorded movement total and the `cierre del día` its only anchor; `existencias_registradas` has no anchor, so it is a ceiling. | The memoria's limitations section |

## 8. Interview decision rules (the evidence gate)

Checked only against real interview notes. Empty boxes → the stated consequence.

| Rule | Condition (read in the notes) | If empty | Consequence for project scope |
| --- | --- | --- | --- |
| Regla 1 — ¿Es el crédito una práctica real? (unchanged) | One shop grants fiado and records it (libreta, WhatsApp list, photo) AND one shop mentions pending debts, their ageing or the difficulty of knowing what is owed. | Both boxes empty → the `fiado confirmado` variant is rejected. | → `margen` (7.70, "El margen real y el capital parado"), the second-ranked candidate; the pure-function architecture transfers 1:1, so no exploration work is lost. No line of code before this closes. |
| Regla 2 — ¿El dueño acepta escribir? (unchanged) | One shop sees recording what it already records by hand as reasonable OR answers favourably (or with acceptable caveats) to question 6 about a tool that says whom to chase for payment. | Both boxes empty → the owner accepts writing nothing. | MVP reduced to a one-tap `cargo` record: same ledger (`cargo`, `pago`, `nota de crédito`), minimum data entry; ageing, limit and risk ladder leave the first version's scope. |
| Regla 3 — Aviso sobre las fuentes públicas (unchanged) | Public figures cited as context only, never as a local statistic; no public source attributed to the fiado practice (none could be verified). | — (citation discipline, not a scope gate) | No scope change. Verified sources and limits live in `tienda-barrio/submission-notes.md` §1; nothing cited from memory. |
| Regla 4 — ¿El dueño pediría la confirmación? (new) | One shop considers it reasonable to ask the client to confirm; the owner's framing is not "desconfianza" but something equivalent to a guarantee for the client; AND one client-side answer suggests the client would do it at the counter. | All three empty → the confirmation flow is cut. | → `fiado desglosado` (7.80): catalogue + `CargoLinea`, no client portal — not `margen`, because the fiado itself is still real. Proposal rewritten against that scope and re-validated with the teaching team. |
| Regla 5 — ¿Se anota qué productos? (new) | One shop writes the products, not only the amount. | Empty → the catalogue and the `CargoLinea` are cut; the confirmation becomes amount-only, a materially weaker product. | Proposal rewritten and re-validated with the teaching team; the itemised confirmation is lost. |
| Regla 6 — ¿Se lleva el inventario? (new) | One shop tracks or approximates stock for some product. | Empty → `existencias_registradas` is cut (cut-line 2). | The drift problem leaves the scope; the capability drops to one figure. If kept: ceiling qualifier travels with the data, no rule depends on it. |
| Condición de la capacidad 8 — ¿da el fiado el `dependiente`? (N5) | One shop has a relative or an helper who grants the fiado when the owner is away. | Empty → the conditional capability is not added. | The `dependiente`'s 403 on the credit book stays absolutely intact; "the notebook stays in the drawer" needs no exception. |

## 9. Scoring — the new scope is NOT the highest-scoring variant

Previous rubric weights, scored against the same criteria.

| Criterion | W | `fiado` (previous) | `fiado desglosado` | `margen` | `fiado confirmado` (new) | `mermas` |
| --- | --- | --- | --- | --- | --- | --- |
| Real-world need strength | 25 % | 8 | 8 | 7 | 8 | 6 |
| Scope fit for 2–3 months solo | 20 % | 8 | 7 | 7 | 6 | 6 |
| Technical risk (lower is better) | 15 % | 7 | 7 | 8 | 6 | 6 |
| Deployability | 15 % | 9 | 9 | 9 | 9 | 8 |
| Defence defensibility | 15 % | 9 | 8 | 8 | 8 | 7 |
| Distinctiveness / memorability | 10 % | 8 | 8 | 8 | 8 | 7 |
| Weighted total / 10 | | 8.15 | 7.80 | 7.70 | 7.45 | 6.55 |

`fiado confirmado` scores 7.45 — below the previous `fiado` (8.15), below `fiado desglosado` (7.80) and below `margen` (7.70). The whole gap is scope fit (−2) and technical risk (−1): seven capabilities instead of five, a third principal class, a second surface, a second credential mechanism, three new entities, a dispute state machine. This must not be hidden.

**The four grounds on which the new scope is still defensible, and only these:**

| # | Ground |
| --- | --- |
| G1 | It serves a pain the previous scope did not touch at all: the misunderstanding between the two parties (pain #2 of the pain map), which the previous `fiado` could only mitigate (ageing, suspension) but never resolve. The confirmation mechanism is the only candidate answer to it in the whole explored set. |
| G2 | The mechanism is new, not repackaged: no POS, notebook or spreadsheet produces a ratified, timestamped, itemised debt. That is what the distinctiveness axis is for. |
| G3 | The scope is capped, not open-ended: seven capabilities against the guide's 4–8 band, two cut-lines declared in advance (D9), two non-negotiables, and a named fallback (`fiado desglosado`) that is itself a scored candidate. Scope discipline is shown by the cut, not the count. |
| G4 | The decision is gated by evidence, not by taste: the interviews decide whether the confirmation survives; if the owner would never ask, the confirmation is cut and the project becomes `fiado desglosado` (7.80) — a strict superset of the previous `fiado`, still better than `margen`. |

**The price, paid deliberately (not a ground):** the rubric's scope-fit and technical-risk axes lose three points between them; the proposal must state that price openly. `margen` is now genuinely competitive (7.70 against 8.15) — never competitive before because `fiado` was strong on two heavy axes at once — and remains the declared fallback if the interviews show credit is not a real practice.

**What the new scope does NOT do:** it does not resurrect the point of sale, and it does not make the project "products + sales + dashboard". The catalogue is a vocabulary for the ledger, there are no sales, and the `cargo` — an obligation with a counterparty who can attest it — is the unit of record.
