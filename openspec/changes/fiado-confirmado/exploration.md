# Exploration Record — `fiado-confirmado`

**Project:** `final` (PFM — Proyecto Final de Máster)
**Change slug:** `fiado-confirmado` — **supersedes** `tienda-barrio`
**Phase:** SDD explore → propose
**Date:** 2026-10-27
**Artifact store:** OpenSpec (`openspec/changes/fiado-confirmado/`) + Engram mirror (`sdd/fiado-confirmado/explore`, project `final`)
**Engram mirror note:** Engram caps one observation at 50,000 bytes, so the mirror is split in two — `sdd/fiado-confirmado/explore` (part 1, §1–§6) and `sdd/fiado-confirmado/explore-continued` (part 2, §7–§8). **This file is the authoritative full artifact.**
**Status:** exploration complete. **No proposal, no specs, no design, no tasks, no code.**

> This file is the **index and decision trail** for the new change. It is the internal engineering record, not a document handed to the teaching team. The team-facing artifact is `proposal.md` (Spanish), which does not exist yet.
> **Language contract (carried over verbatim from `tienda-barrio/design.md` §1):** prose in English; every domain identifier, field name, API field and diagram label stays in **Spanish** (`fiado`, `cargo`, `pago`, `nota de crédito`, `caja`, `dependiente`, `dueño`, `libreta`, `posición real`, `antiguedad_max_dias`, `suspended_reason`, `vigente`/`envejecido`/`viejo`/`cronico`) because these are the code identifiers and the diagram labels are pasted verbatim into the memoria.

---

## 1. Sources and prior art

### 1.1 What was read

| Source | Location | Read |
| --- | --- | --- |
| Domain exploration | `openspec/explorations/tienda-barrio-domain.md` | Part A (shop operating reality, pain map, structural constraints), Part B (three variants), Part C (scoring), Part D (week-1 evidence plan + verbatim interview script), Part E (proposal skeleton), Part F (deployment spine + `seed_demo` spec), Part G (risk register) |
| Decision trail | `openspec/changes/tienda-barrio/exploration.md` | Full |
| Previous scope statement | `openspec/changes/tienda-barrio/proposal.md` | Full |
| Previous design (1124 lines) | `openspec/changes/tienda-barrio/design.md` | §1.1–§1.3 (technical approach, the two resolved decisions, architecture diagram, language contract), §4 (data model), §7 (security architecture), §10 (deployment), §11 (15 ADRs) |
| Evidence template | `openspec/changes/tienda-barrio/evidence-annex.md` | Full |
| Submission notes | `openspec/changes/tienda-barrio/submission-notes.md` | §8 permission matrix, §9 data model + pure rules, §10 capability contract, §11 still-blocked items |
| Engram | obs #113 `pfm/requirements-brief` | Full — the delivery guide constraints that bound every variant |

### 1.2 Evidence versus abandoned design — the classification that governs this document

| Carried as **EVIDENCE** (facts about the world, reusable) | Carried as **ABANDONED DESIGN** (a candidate answer, revisable) |
| --- | --- |
| The shop operating reality: 100–400 transactions/day, cash-dominant, 1–3 staff, no manager, 300–1500 SKUs, the owner is the asset (Part A.1) | The three variants `fiado` / `mermas` / `margen` as scoped in Part B |
| The nine pains and which ones a generic POS already solves (Part A.2) | The **categorical** POS exclusion — "we have no `Product`/`Sale` table" — now reversed by the owner's decision |
| The three structural constraints (A.3): the shop will not adopt extra manual discipline; the shop does not know its cost; the owner will not be replaced | The **scope statement** of `proposal.md` and the 5-capability contract of `submission-notes.md` §10 |
| The nine-pain table's finding that credit disputes ("I paid you" / "you didn't") are real and unnamed | The 34 requirements / 47 scenarios in `openspec/changes/tienda-barrio/specs/` — they stay on disk as history and are **not** amended |
| The interview script and the capture sheet (Part D.2/D.3, `evidence-annex.md`) — the instrument that decides the product | The **two-role claim** as a statement about the whole system (see T3) |
| The verified deployment facts (Render free + Neon free + WhiteNoise, ephemeral FS, 15-min sleep, Render Postgres expiry) | The `Shop.usuarios` + `session["shop_id"]` scope as the *only* scope mechanism |
| The scoring weights (25 / 20 / 15 / 15 / 15 / 10) and the 8.15 / 7.70 / 6.55 scores | The 5-feature scope, the cut of `Product`/`Sale`, and the `evidence-annex.md` decision checklist as it stands |
| The risk register (Part G) and the landmine list (design §10.5) | The `fiado` variant **as a decision** — it is now the fallback, not the plan |

**Rule applied:** where this document reuses a previous decision, it says so explicitly and states whether it is reused as *fact*, as *mechanism* or as *rationale*. Where it reverses one, it names the reversal and its price (T6).

---

## 2. Decision trail

### 2.1 The owner's confirmed decisions (authoritative — this exploration does not relitigate them)

| # | Decision | Consequence for this exploration |
| --- | --- | --- |
| O1 | **The project is replanned from scratch.** The `fiado` confirmed by the client becomes the central product, not an addendum. | `fiado-confirmado` is a new variant with its own scope, not a feature of `tienda-barrio`. |
| O2 | **`fiado-confirmado` supersedes `tienda-barrio`.** The previous proposal, specs and design are abandoned rather than amended. | The previous folder stays on disk untouched. The new specs will be **delta specs of a new change**, not edits. |
| O3 | **Inventory is tracked by movement.** A product catalogue with prices, charge lines on every `cargo`, stock derived from the recorded movements. | The catalogue and the charge lines are in scope. T1 resolves what "stock" may honestly claim. |
| O4 | **Planning only.** | No code, no scaffolding, no configuration change. This document is the only artifact. |

### 2.2 What THIS exploration decided

| # | Tension | Decision | One-line rationale |
| --- | --- | --- | --- |
| D1 | T1 | **Keep the catalogue; claim only a movement-derived ceiling, honestly named `existencias_registradas`.** Reject recording cash sales and reject a physical count. | A shop that does not record its cash sales cannot have a stock count; the claim must be bounded by what is recorded. |
| D2 | T1 | **The catalogue's load-bearing job is the price snapshot on each `CargoLinea`, not the stock figure.** | The catalogue exists so a charge is itemised and priced *at the moment of the charge* — that is what removes the misunderstanding. |
| D3 | T2 | **One credential: a per-client `codigo`, delivered on a slip, presented per request. The shop's own device at the counter is the primary surface; the client's own phone is the secondary one.** | The confirmation must happen at the counter, in the owner's presence, or it will not happen at all. |
| D4 | T3 | **The client is not a Django role, not a Django group and not a session. It is a bearer credential scoped to exactly one `Customer`, resolved server-side.** | A third group would put a client-shaped principal through the whole staff permission model; a scoped credential keeps the `dependiente` 403 boundary structural. |
| D5 | T4 | **A `cargo` never depends on the confirmation.** It counts as debt the moment it is recorded; the confirmation is an attestation that enriches the record, not a precondition of it. | Otherwise a client could erase a debt by refusing to confirm. |
| D6 | T4 | **A confirmation stays open indefinitely; there is no expiry.** What ages instead is an escalation flag on the owner's board (`sin_confirmar` older than 7 days → *revisar*). | An expiry would either invalidate a real debt or require a re-issue mechanic — both are worse than a permanent, visible flag. |
| D7 | T5 | **A confirmed charge is immutable; corrections happen only by appending a `nota de crédito`. A disputed charge still counts as debt and still ages.** | Append-only already provides the correction path; a dispute must not become a free cancellation. |
| D8 | T6 | **The new scope is defensible on the grounds of a served pain, a capped feature count and a named fallback — not on the grounds of being a better-scoped project.** | On the same rubric weights the new scope scores **7.45**, below the previous `fiado` at **8.15**. The difference is paid deliberately and must be evidenced. |
| D9 | T6 | **Two cut-lines are declared now, before the timeline, not during it:** the 30-day `serie_caja` chart (a React element), then `existencias_registradas` (if the interviews show the owner does not track stock). | Scope discipline is graded; the cut must be declared in advance to be credible. |
| D10 | T7 | **Six of the original six questions survive; seven new questions become decisive; three new decision rules join the checklist.** | The script must decide the confirmation flow, the catalogue and the stock claim — the three things the previous script never asked about. |

---

## 3. The new variant — `fiado confirmado`

### 3.1 What it is

> **An append-only credit ledger for a neighbourhood shop where every `cargo` is itemised with products and prices, and where the debtor confirms each charge themselves — with a timestamp, an itemised list and an append-only audit trail — so that the two parties can never disagree about what was fiado.**

The non-obvious core, stated precisely enough to unit-test:

> **A charge is a *claim*; the confirmation is its *ratification*; the ledger records both, append-only, and derives the client's statement from the ratified set only.**

Three properties make it not a POS and not a notebook:

1. **The unit of record is an obligation, not an exchange.** There is no `venta`, no till, no receipt, no payment tender and no drawer. Every row corresponds to an act the owner *already performs* (writing a debt in the `libreta`, receiving a delivery, handing over change) or to a new act that is itself the product (the client confirming).
2. **The price is snapshotted at the moment of the charge.** `precio_unitario` on a `CargoLinea` is what was charged then, and a later catalogue change never rewrites it. This is what freezes the disagreement.
3. **The debtor is a first-class principal, but not a user.** The client can attest to their own debt and to nothing else, and the attestation is worth something precisely because it is *the client's* act.

### 3.2 What it replaces

| Replaced | By what |
| --- | --- |
| The free-text `description` of a `cargo` ("2 L de leche + pan") as the only record of what was fiado | A `cargo` with `CargoLinea` rows (product, quantity, `precio_unitario` snapshot) whose sum equals the `cargo` amount; the free text survives as optional context |
| The owner's memory as the arbiter of a dispute | The `Confirmacion` — an append-only attestation with `confirmado_en` |
| The previous scope's categorical "no products, no prices" defence | A behavioural defence: no sales are recorded, so there is no till (see T6) |

### 3.3 What it adds to the ledger

| New | Type | Fields | Rules |
| --- | --- | --- | --- |
| `Producto` | catalogue | `id, nombre, precio, unidad, activo` | The **vocabulary** of the ledger. Only the goods the owner puts on the tab — a seeded set of ~30, not the shop's 300–1500 assortment. `precio` is a **default**, not a constraint: the owner may charge a different amount and the line records what was actually charged. |
| `CargoLinea` | child of a `cargo` | `id, cargo FK, producto FK, cantidad, precio_unitario, total` | Immutable with its parent. `precio_unitario` is a **snapshot**. Invariant: `LedgerEntry.amount == Σ LineaCargo.total`, checked server-side inside the write transaction. |
| `Confirmacion` | append-only attestation | `id, cargo FK, estado (`confirmado` \| `en_disputa`), importe_reclamado (nullable), nota (nullable), confirmado_en, origen, facilitado_por FK (nullable)` | Never updates or deletes. The **effective state of a charge is derived** from its latest `Confirmacion` (consistent with ADR-2: nothing derived is stored). A charge with no `Confirmacion` is `sin_confirmar`. |
| `Customer.codigo` | new column | `codigo` (nullable, unique per shop) | The client's scoped credential. Issued and rotated by the `dueño`. Never returned by any staff-facing payload except to the owner. |

### 3.4 The two surfaces

| Surface | Actor | Credential | Content |
| --- | --- | --- | --- |
| `/app/posicion` — the owner's board | `dueño` | Django session + `X-CSRFToken` | The hero equation (`caja + Σ outstanding = posición real`), the risk ladder with ageing ribbons, now with a **confirmation state** per charge (`confirmado` / `sin_confirmar` / `en_disputa`) and an age flag on the old unconfirmed ones |
| `/app/cliente` — the client's page | `cliente` | The `codigo`, presented per request | `Confirmado` — the itemised fiado the client has ratified. `Sin confirmar` — a summary row (date, amount, a *Confirmar* action). The itemisation of an unconfirmed charge appears **only inside the confirmation action**, where it must be visible in order to be confirmed. |

---

## 4. Resolution of T1–T7

### T1 — Cash sales versus movement-derived stock

**Question.** With no point of sale, a cash sale never decrements stock. Only purchases in and fiado out get recorded, so a movement-derived stock drifts by exactly the cash sales.

**Recommendation — option (b), bounded and renamed.** `existencias_registradas` = `Σ entradas − Σ salidas registradas`. It is **an upper bound on the real stock, never a count**, and it is named that way in the field, in the API and on screen. Two rules make the honesty structural rather than cosmetic:

- **No rule anywhere depends on it.** A `cargo` is never refused for lack of stock; no price is derived from it; no suspension is derived from it. A number that cannot be trusted must not be allowed to act.
- **The qualifier travels with the data.** The API returns the figure together with a machine-readable qualifier so that no consumer — the React board, a future API, a seed — can read it as a count. `stock` is banned as a field name for exactly this reason.

**Rejected alternative (a) — record cash sales too.** Rejected on **behaviour, not on category**, and this is the important part of the answer: the shop runs 100–400 transactions a day (Part A.1). Hand-entering each one is a POS *without the hardware* — no barcode, no till button, no standing customer — against an owner who has never recorded a cash sale and who structural constraint A.3.1 says will not start. It would also re-create the exact thing the previous exploration excluded. The POS exclusion therefore **survives, re-founded on a behavioural argument** (no sale is ever recorded) rather than a categorical one (no `Product` table exists). That re-founding is what T6 buys with the owner's decision.

**Rejected alternative (c) — a periodic physical count as a correction movement.** Rejected for the reason already recorded in Part G and A.3.1: counting is the one action the shop will not adopt, and a *product-level* count of 30–1500 items is not something a 40 m² shop performs. **But** the reasoning is sharpened here: a count is not merely a discipline the shop lacks, it is *arithmetically necessary* — the drift has four sources (cash sales, breakage, supplier short-delivery, `consumo propio`) and **no software can produce a count without a count**. That sentence is the honest answer to the panel.

**Consequence and who bears it.** The shop's true stock is **not knowable from this product**, and the product says so on the screen and in the memoria §3.6/limitations. The owner bears this knowingly, with the label in front of him. The owner's reaction to a stockout will still be a surprise, and the product must not pretend otherwise.

**Inherited finding that changes the cut-lines.** The previous project had the *same* gap on `caja`: daily cash sales were never recorded there either, so `caja` was "recorded cash movements", and `posición real` was an approximation of the shop's true liquidity. The only instrument in the whole model that ever *measures* the shop's money is the **`cierre del día`**, where the owner counts the drawer and the variance is stored. That makes `DayClose` an **anchor**, not a candidate for the cut — cutting it would leave `caja` permanently uncalibrated. The same contrast is the answer to T1 in one line: **`caja` has a measuring ritual; `existencias` has none, so one is calibrated and the other is a ceiling.**

**What must confirm it.** Interview question N7 and decision rule 6 (§4, T7).

---

### T2 — How the client reaches their page without e-mail or SMS

**Options evaluated.**

| Option | How it works | Friction | Verdict |
| --- | --- | --- | --- |
| **Owner-issued short code/PIN** | The owner says "your code is 4821"; the client types it | The client must remember it, or the owner repeats it every time; a 4-digit code is guessable | **Rejected as the sole mechanism** — remembering is exactly what the `libreta` is for, and the guessability needs a throttle to be safe |
| **Printed slip with URL + code** | The owner hands over a slip; the client types the code | One slip per client, once; the slip is lost sometimes | **Accepted as the delivery mechanism** — a slip can carry a long high-entropy token, which a spoken code cannot |
| **The client uses the shop's own device** | The owner hands the tablet to the client for 10 seconds | None added to the owner; needs a device at the counter | **Accepted as the primary surface** — see below |
| **E-mail / SMS / native app** | — | — | **Out of scope** — free tiers block outbound SMTP, and the owner's instruction excludes them |

**Recommendation — one credential, two surfaces.** A per-client `codigo` (a printed slip), presented per request, on **two surfaces of the same page**:

- **Primary — the shop's own device, at the counter.** The confirmation must happen *at the moment the goods change hands*, while the owner is standing there. A confirmation that waits for the client to go home will mostly never happen, and the whole product rests on confirmations actually occurring.
- **Secondary — the client's own phone**, for the consultation the owner described: *"the client can reach a page that shows what they owe."* Same credential, same URL, no session.

**Why this beat the alternatives.** The confirmation's purpose is *evidentiary*, and its value depends on being contemporaneous and on being *the client's* act. That single fact decides the ranking: any mechanism that pushes the confirmation into the client's home, into the evening, into "I'll do it later" destroys the thing being built. The shop's device makes the confirmation a five-second event inside a transaction the client is already having.

**Adoption friction, honestly.**

| Who | What is added | Size of the ask |
| --- | --- | --- |
| Owner | One slip per client, once. Handing the device over for ten seconds. Asking the client to confirm. | **Asking is the hard part**, not the slip — see T4 |
| Client | Type a code, read a list, tap one button | ~10 seconds, on a device they are already being handed |
| Client (remote) | Open a URL, type the code | Requires a smartphone with a browser — **not guaranteed for every client**, and the interviews must test it |

**What happens when the client never opens the page.** Nothing breaks. The `cargo` exists, counts as debt, ages and can be suspended exactly as in the previous project; the client's statement shows it as an unconfirmed summary row; the owner's board shows it as `sin_confirmar` with its age. **The product degrades to the previous `fiado` product, not to nothing** — and that is the property that makes the confirmation safe to add.

---

### T3 — The third actor

**The previous claim.** *"Exactly two roles, enforced server-side (Django groups `dueno` and `dependiente`), with the credit book owner-only and a hard 403 for `dependiente`."*

**Decision — the client is not a role.** The client is **not** a Django group, **not** a Django `User`, and **not** a session. It is a **bearer credential scoped to exactly one `Customer`**, resolved server-side on every request, with the scope coming from the credential and from nothing else — never from a URL segment, never from a body field, never from a session key.

**Why not a third group.** A Django `User` implies a person with a password, a `staff` flag, groups, permissions and a session. The moment the client is a `User`, every `IsAuthenticated` check in the codebase passes for a client, every staff endpoint needs a new special case, and the serializer-allowlist guarantee (ADR-6) needs a third schema *plus* a third branch in every view. The blast radius is the whole permission model, in exchange for nothing the client needs.

**Why not a session.** The tempting design — the client exchanges the `codigo` for a session — creates a class of bug that the staff model does not have: the helper is logged in at the tablet, the client types the code, and now **one cookie holds both a staff scope and a customer scope**. The invariant that closes it: **a client scope may never exist inside a staff session, and a staff session may never be upgraded to a client scope.** The cheapest way to hold that invariant is to have **no client session at all**: the credential is presented per request and the scope is inherent in it. The cost is that the code is re-entered on a page reload — acceptable, and it is how a bank-PIN portal behaves.

**What breaks in the previous role matrix — precisely.**

| Previous artefact | What breaks | What replaces it |
| --- | --- | --- |
| RAC-01 *"Two roles exist and are enforced on the server"* | The **statement** breaks — the system now has a third principal class. The **mechanism** does not. | "Two **shop** roles are enforced on the server; a third, external principal is scoped to exactly one customer." The `dependiente` RED test still passes unchanged. |
| RAC-02 *"The credit book is owner-only"* | The unqualified word "only" | "The credit book is owner-only **among the staff**. The client sees their own confirmed charges and their own pending claim summary, and nothing else." |
| RAC-03 *"No credit-book data may leak into any payload"* | The test's **scope**: it walked the `dependiente` payload | It must additionally walk the **client** payload and assert it contains nothing but that one customer's own data — no other alias, no shop-wide total, no `caja`, no `posición real`, no `credit_limit` of anyone else |
| ADR-5 *"Django Groups + mixins, not a custom permission table"* | Nothing — but the matrix it encodes grows a column that is **not** a group | The staff matrix is enforced by groups; the client column is enforced by the credential's scope, which is a *different mechanism* on purpose |
| ADR-6 *"Serializer-level allowlist"* | Nothing — it **extends** | A third serializer class with a disjoint field list, so "no shop data in a client payload" is a property of the schema, not a promise |
| §7.4 *"the shop of the session is the one source of the data scope"* | The **client** endpoints do not use it | The staff scope stays `session["shop_id"]`; the client scope is the credential. Two scopes, two mechanisms, each with exactly one source |
| The rationale *"the notebook stays in the drawer"* | It needs one exception | See below |

**The new matrix.** The staff columns are unchanged; the third column is the client, and every entry in it is scoped to its own customer.

| # | Capability | `dueño` | `dependiente` | `cliente` (own customer only) |
| --- | --- | :---: | :---: | :---: |
| 1 | Registrar movimientos de caja / cierre del día | Sí | Sí | — |
| 2 | Ver el libro de crédito (alias, límites, saldos) | Sí | **No → 403** | — |
| 3 | Crear cliente, línea de crédito, **emitir o rotar el `codigo`** | Sí | No | — |
| 4 | Registrar `cargo` (con líneas) o `pago` | Sí | No | — |
| 5 | Ver antigüedad, escalera de riesgos, `posición real`, `existencias_registradas` | Sí | No | — |
| 6 | Anular una suspensión | Sí | No | — |
| 7 | Ver su propio cargo pendiente (resumen: fecha + importe) | — | — | **Sí** |
| 8 | Ver el **detalle de líneas** de un cargo | Sí | No | **Sí, solo si está `confirmado`**; el detalle de un cargo sin confirmar aparece únicamente dentro de la acción de confirmar |
| 9 | **Confirmar** un cargo | — | — | **Sí** |
| 10 | **Disputar** un cargo (con `importe_reclamado` y `nota`) | — | — | **Sí** |
| 11 | Resolver una disputa (`nota de crédito` o rechazo) | Sí | No | — |
| 12 | Gestionar usuarios y roles | Sí | No | — |

**The one real erosion of the 403 boundary, and how it is bounded.** The `dependiente` serves at the till while the owner is away, so in practice the person holding the device is often the helper. If only the `dueño` could operate the confirmation flow, the shop would stop working when the owner is absent — pain #7 in the pain map. So the helper needs **one narrow, purpose-bound capability**: *present a pending charge to the client and receive the client's confirmation*. The bounding rules:

- The helper's surface shows **only the charge currently presented**, never a list, never a balance, never the ageing.
- The helper **never holds a client scope** — the client presents their own `codigo`; the helper never types it on the client's behalf.
- Every confirmation records **who facilitated it** (`facilitado_por`), so the act is auditable.
- The rationale is amended from *"the notebook stays in the drawer"* to *"the notebook stays in the drawer, except for the one page the client is looking at right now."*

**This is evidence-conditional.** If the interviews show the owner personally gives every fiado, the helper never needs this capability and the boundary stays absolutely intact. That is interview question N5 and decision rule 4 (§4, T7).

---

### T4 — Adoption friction and graceful degradation

**The real friction, ranked.**

1. **The owner must ask.** Asking a neighbour to confirm a debt can read as distrust — "do you think I would cheat you?". This is a *social* cost, and in a barrio where the relationship is the shop's moat (A.1) it is the friction most likely to kill adoption. It is not solvable by software; it is solvable only by the framing (the confirmation is for *them*, not against them) and by the evidence.
2. **The client must stop.** Adding ten seconds to a twenty-second transaction.
3. **The device must exist.** A shop with no tablet cannot run the at-counter flow. This is a factual question for the interviews, and it is a *hard* dependency of the primary surface.
4. **The client may not have a browser.** Relevant to the remote surface only.

**How a `cargo` behaves with no confirmation.**

- It is an ordinary `cargo`: it counts in `fiado pendiente`, it ages into `vigente`/`envejecido`/`viejo`/`cronico`, it can trigger the automatic suspension, it can be paid.
- It carries the derived state `sin_confirmar` and appears on the owner's board with that marker and its age.
- It appears in the client's statement as a **summary row** — date, amount, a *Confirmar* action — with the itemisation revealed only inside the confirmation action. **Flagged as an interpretation** of the owner's sentence *"the list of fiado items can only appear there if the client confirmed it beforehand"*; it must be confirmed with the owner before the proposal (§8, item 2). The alternative literal reading — no amount, no items until confirmed — would let the client's statement understate the debt, which is the exact misunderstanding the product exists to remove.
- **Nothing about the balance depends on it.** This is D5, and it is the load-bearing safety property: a client who never confirms cannot erase a debt.

**How long a confirmation stays open — indefinitely.** No expiry. Two reasons: an expiry would either invalidate a real debt (unacceptable) or require a re-issue mechanic that adds owner work (worse than the problem). What ages instead is the **flag**: an unconfirmed charge older than **7 days** is escalated on the owner's ladder as *revisar* — an old unratified claim is more likely to become a dispute. The flag is **derived on read**, consistent with ADR-8 (no background worker, no Celery, no Redis). The only things that close a confirmation are the client confirming, the client disputing, or the owner appending a `nota de crédito`.

**Graceful degradation, stated as a property.** If no client ever confirms, the product still delivers: the append-only ledger, FIFO allocation, ageing, automatic suspension, the `posición real` equation, the day close. **The confirmation is an enrichment, never a precondition.** That property is what makes it safe to add to a project that already had a defensible scope — and it is the answer to the panel question "and if nobody confirms?".

---

### T5 — Dispute resolution

**The scenario.** The client is shown a charge of 6,40 € for two lines. The client says it was 4,20 €, or that they did not take one of the lines.

**Mechanism.** The client cannot amend the owner's record — that would let a client erase a debt. The confirmation flow therefore offers exactly two outcomes:

| Action | Effect |
| --- | --- |
| **Confirmar** | A `Confirmacion` with `estado = confirmado` is appended. The charge becomes `confirmado`; its itemisation becomes visible in the client's statement. |
| **Disputar** | A `Confirmacion` with `estado = en_disputa`, an optional `importe_reclamado` and an optional `nota` is appended. The charge's effective state becomes `en_disputa`. |

**Who arbitrates.** **The owner.** It is his shop, his ledger and his commercial record; the client has no authority over it. But the arbitration must be **recorded and visible to the client**, or the client is left in the dark — which is the failure mode this whole product is about.

**How the correction is recorded.**

| The owner's resolution | Effect on the ledger | The charge row |
| --- | --- | --- |
| **Accept the discrepancy** | Append a `nota de crédito` for the difference (6,40 − 4,20 = **2,20 €**). The outstanding becomes 4,20 € through the normal FIFO/credit-note arithmetic. | **unchanged** — the 6,40 € `cargo` is still there, immutable, next to the credit note that corrects it |
| **Reject the discrepancy** | No entry. The owner asserts the original figure. | unchanged; the effective state stays `en_disputa` until the client accepts the figure or a `nota de crédito` reconciles it |

**Three rules that make this safe.**

1. **A confirmed charge is immutable.** Not by a new constraint — by the append-only rule that already governs the ledger. **Amendments happen only by appending.** No `PUT`, no `PATCH`, no `DELETE` on a `cargo` or a `Confirmacion`, ever. The previous design already had the correction instrument (`nota de crédito`); the confirmation adds the *evidence*, not a new amendment path.
2. **A disputed charge still counts as debt and still ages.** Otherwise disputing is a free cancellation and the client simply never confirms. The dispute is a **flag, not a credit**. The owner's board shows it as `en_disputa` in the ladder, where an old disputed charge is precisely what needs chasing.
3. **The client can always escalate.** The client's statement shows the dispute and its history. A client who believes a confirmation was fabricated, or who was charged a price different from the one confirmed, sees the `Confirmacion` record — that is the client's recourse against a fabricated attestation, and it must be stated in the memoria as the honest limit of the mechanism.

**Who may amend what.**

| Actor | May append | May never |
| --- | --- | --- |
| `dueño` | `cargo`, `pago`, `nota de crédito`, a `Confirmacion` on behalf of nobody (there is no such thing) | Edit or delete any `cargo`, `pago`, `nota de crédito` or `Confirmacion` |
| `dependiente` | `CashMovement`, `DayClose` | Touch the credit book at all — except the narrow facilitator capability of T3, which appends nothing on the client's behalf |
| `cliente` | A `Confirmacion` (`confirmado` or `en_disputa`) against **their own** charges only | Amend the ledger in any way; confirm a charge that is not theirs; see any other customer, any total, or the shop's money |

---

### T6 — Scope re-evaluation, honestly

#### T6.1 What is lost in the POS defence

The previous exploration's defence had two prongs:

| Prick | Status now |
| --- | --- |
| **Categorical** — "we have no `Product`/`Sale` table, therefore we are not a POS" | **FORFEIT.** The catalogue exists, by the owner's decision (O3). The categorical argument can no longer be made. |
| **Behavioural** — "we record only what the shop already records" | **SURVIVES, and is now the load-bearing one.** It is also *stronger* than before, because T1 forced it to be stated in terms of data-entry volume rather than tables: ~5–15 recorded movements a day (fiado charges, deliveries, occasional payments) against the shop's 100–400 daily cash sales, none of which are ever recorded. |

#### T6.2 What replaces the defence

1. **The subject is the obligation, not the exchange.** A POS records what was sold; this records what was **given away and ratified**. There is no `venta`, no till, no receipt, no payment tender, no drawer, no barcode, no purchase order.
2. **The catalogue is a vocabulary, not an inventory system.** It holds only the goods eligible for fiado (~30 rows in the seed, not 1500), it has no supplier, no cost, no `coste_medio`, no reorder point, and its price is a *default* the owner may override. It exists for one job: to name and price the items inside a `cargo`.
3. **The price snapshot is the mechanism, not the catalogue.** `precio_unitario` is frozen at the moment of the charge. A catalogue with live prices would be a price list; a catalogue that produces **immutable snapshots inside an append-only ledger** is a notary. That is a mechanism distinction, not a presentation one.
4. **The ratification has no analogue in the POS category.** No point of sale, and no generic accounting tool, lets the debtor attest a debt with a timestamp and an itemisation. This is the strongest single line of the defence.
5. **The stock claim is bounded rather than hidden.** The product states out loud that `existencias_registradas` is an upper bound, because a shop that does not record its cash sales cannot have a stock count. A product that *says* its number is a ceiling is more defensible than one that quietly lies.

**The defence to the tribunal, in the honest version:**

> "This is not a point of sale because we never record a sale. The catalogue has one job: to name and price the items inside a `cargo`, and to freeze that price at the moment of the charge. We record the movements of the goods that go on the tab — the ones that create a debt — and the deliveries that replenish them. We do not record the two hundred cash sales a day, we have no till, no receipt, no drawer and no barcode. And we are not an inventory system: our stock figure is derived from recorded movements and is explicitly an upper bound, because a shop that does not record its cash sales cannot have a stock count. What a point of sale cannot do — and what is the core of this project — is let the debtor confirm the debt, with a timestamp, an itemisation and an append-only audit trail."

#### T6.3 Is the new scope defensible, and on exactly what grounds?

**The honest finding, on the previous rubric weights (25 / 20 / 15 / 15 / 15 / 10), scored against the same criteria:**

| Criterion | W | `fiado` (previous) | `fiado desglosado` (catalogue, no client portal) | `margen` | **`fiado confirmado` (new scope)** | `mermas` |
| --- | --- | --- | --- | --- | --- | --- |
| Real-world need strength | 25 % | 8 | 8 | 7 | **8** | 6 |
| Scope fit for 2–3 months solo | 20 % | 8 | 7 | 7 | **6** | 6 |
| Technical risk (lower is better) | 15 % | 7 | 7 | 8 | **6** | 6 |
| Deployability | 15 % | 9 | 9 | 9 | **9** | 8 |
| Defence defensibility | 15 % | 9 | 8 | 8 | **8** | 7 |
| Distinctiveness / memorability | 10 % | 8 | 8 | 8 | **8** | 7 |
| **Weighted total / 10** | | **8.15** | **7.80** | **7.70** | **7.45** | **6.55** |

**`fiado confirmado` is no longer the strongest variant by score.** It scores **7.45**, below the previous `fiado` (8.15), below `fiado desglosado` (7.80) and below `margen` (7.70). The entire gap is in **scope fit (−2)** and **technical risk (−1)**: seven capabilities instead of five, a third principal class, a second surface, a second credential mechanism, three new entities and a dispute state machine.

That is the finding, and it must not be hidden. **The new scope cannot be defended as "a better-scoped project".** It is defensible on exactly these grounds, and only these:

1. **It serves a pain the previous scope did not touch at all.** The previous `fiado` optimised the owner's *memory problem*; this one addresses the *misunderstanding between the two parties*, which is pain #2 of the pain map and which the previous scope could only mitigate (by ageing and suspension) but never resolve. The confirmation mechanism is the only candidate answer to that pain in the whole explored set.
2. **The mechanism is new, not repackaged.** No POS, no notebook and no spreadsheet can produce a ratified, timestamped, itemised debt. That is a mechanism distinction, and it is what the 10 % distinctiveness and 10 % reflection axes are for.
3. **The scope is capped, not open-ended.** Seven capabilities against the guide's 4–8 band, **two cut-lines declared in advance** (D9), two non-negotiables, and a **named fallback** (`fiado desglosado`) that is itself a scored candidate. Scope discipline is demonstrated by the cut, not by the count.
4. **The cost is acknowledged and paid deliberately.** The rubric's scope-fit and technical-risk axes lose three points between them. The proposal must state that price openly rather than hope the panel does not compute it.
5. **The decision is gated by evidence, not by taste.** The interviews decide whether the confirmation survives. If they say the owner would never ask, the confirmation is cut and the project becomes `fiado desglosado` (7.80) — which is a strict superset of the previous `fiado` minus nothing, and still better than `margen`.

**And the uncomfortable corollary, stated plainly:** `margen` is now genuinely competitive (7.70 against 8.15 before). It was never competitive before because the `fiado` variant was strong on *two* heavy axes at once. Now it is strong on only one. `margen` remains the declared fallback if the interviews show that credit is not a real practice — a rule that already existed and has not changed.

**What the new scope does NOT do:** it does not resurrect the point of sale, and it does not make the project "products + sales + dashboard". The catalogue is a vocabulary for the ledger, there are no sales, and the `cargo` — an obligation with a counterparty who can attest it — is the unit of record.

#### T6.4 Cut-lines, declared now

| Priority | Cut | Consequence if cut |
| --- | --- | --- |
| 1 | The 30-day `serie_caja` area chart (a **React element**, not a capability) | The hero equation and the ladder survive; the board loses its third element |
| 2 | `existencias_registradas` (only if interview N7 shows the owner does not track stock) | The capability drops to one figure; the drift problem disappears with the feature |
| 3 | The remote client consultation (client's own phone) | The confirmation stays at the counter only; the client's statement is seen at the counter |
| — | **Not cuttable:** the append-only ledger · the `dependiente` 403 boundary · the React view consuming the app's own API at the public URL · the public HTTPS URL with `DEBUG=False` and seeded data |

---

### T7 — Evidence: the delta to the existing script

**The script is not rewritten.** Six of the six questions survive and four of them become *more* decisive; seven questions are added; three decision rules join the checklist. The recruitment plan (Part D.1 — street rounds, the merchants' association, the wholesaler's salesperson, the market, the form fallback) and the capture sheet are **unchanged**, because the sampling problem has not changed.

#### T7.1 The original six questions — status under the new scope

| # | Question (verbatim, from `evidence-annex.md`) | Status under the new scope |
| --- | --- | --- |
| 1 | «Cuando un cliente te pide fiado, ¿qué haces? ¿Lo anotas en algún sitio —la libreta, el móvil, una lista— o se queda en tu cabeza?» | **KEEP — now more decisive.** It must also reveal *what* is written: amounts only, or the items. This is the bridge to the catalogue question N1. |
| 2 | «¿Sabes siempre cuánto dinero te deben en total? ¿Y desde cuándo le deben cada uno?» | **KEEP — unchanged and core.** |
| 3 | «¿Te ha pasado que alguien te debe y no sabes cuánto, o que se pierde la libreta?» | **KEEP — now the dispute motivation.** The confirmation flow exists to prevent this; the question establishes whether it happens. |
| 4 | «Si cierras la caja al final del día, ¿el dinero que hay en el cajón es el que esperabas? ¿Notas que falta algo?» | **KEEP — demoted in priority but now load-bearing for `caja`.** It decides whether the `cierre del día` is a real ritual (the only anchor for `caja`) or a fiction. |
| 5 | «Cuando te vas unos días —enfermo, vacaciones—, ¿alguien puede saber quién te debe o cuánto hay en el almacén?» | **KEEP — PROMOTED to decisive.** It decides who gives the fiado when the owner is away, which decides the facilitator capability and the `dependiente` boundary (T3). |
| 6 | «Si una herramienta te dijera a quién hay que recordarle el pago hoy y cuánto dinero es de verdad el tuyo, ¿la usarías? ¿Qué te quitaría de cabeza?» | **KEEP — the adoption question**, now extended by N3 to cover the confirmation itself. |
| — | Optional open: «¿Qué parte de tu negocio no controlas bien y te cuesta dinero?» | **KEEP** |

#### T7.2 The delta — seven new questions, in Spanish, verbatim, to be asked in the same 10–15 minute slot

| # | Question | Decides |
| --- | --- | --- |
| **N1** | «Cuando anotas lo que se lleva un cliente, ¿anotas **qué productos** y el importe, o solo el importe?» | **The catalogue.** If owners write only amounts, the catalogue, the charge lines and the itemised confirmation are unjustified — the product collapses to amount-only, which is much weaker. |
| **N2** | «¿Anotas las ventas que te pagan en efectivo, una por una, o solo el total del día?» | **T1(a) vs T1(b).** The expected answer is "only the total" or "nothing"; if the answer is "one by one", the drift question reopens and the scope changes. |
| **N3** | «¿Crees que un cliente aceptaría **confirmar** en el momento lo que le has fiado, o lo vería como desconfianza?» | **The whole confirmation flow.** Asked in the third person so the owner is not put on the spot — the same device used for question 1. |
| **N4** | «¿Usaría tu cliente un móvil para esto, o lo harías en la tablet de la tienda?» | **T2's surface.** Also reveals whether the shop even *has* a device. |
| **N5** | «Cuando tú no estás, ¿quién da el fiado: tú, un familiar o un ayudante?» | **T3's facilitator capability** and therefore the exact shape of the `dependiente` boundary. |
| **N6** | «¿Qué harías si un cliente te dice que le debes menos de lo que anotaste?» | **T5.** The real dispute frequency, the real dispute object (amount or items), and whether the owner already has a way to settle one. |
| **N7** | «¿Llevas las existencias de algún producto de forma aproximada, o las cuentas?» | **T1's stock claim** and whether `existencias_registradas` survives at all (cut-line 2). |

**Placement note.** N3 must not be asked before questions 1–3 have established that the fiado is a real practice; asking it cold invites a polite "sí". It follows question 3, and N1 follows question 1.

#### T7.3 The delta to the decision checklist

Rules 1–3 of `evidence-annex.md` carry over unchanged. Three rules are added:

| Rule | Question | If the boxes are empty |
| --- | --- | --- |
| **Regla 4 — ¿El dueño pediría la confirmación?** | Read in the notes: at least one shop considers it reasonable to ask the client to confirm *and* the owner's framing is not "desconfianza"; **and** at least one client-side answer suggests the client would do it at the counter | **The confirmation flow is cut** and the project becomes **`fiado desglosado`** (catalogue + charge lines, no client portal, 7.80) — *not* `margen`, because the fiado itself is still real |
| **Regla 5 — ¿Se anota qué productos?** | At least one shop writes the items, not only the amount | **The catalogue and the `CargoLinea` are cut**; the confirmation becomes amount-only, which is a materially weaker product — the proposal must be rewritten and re-validated with the teaching team |
| **Regla 6 — ¿Se lleva el inventario?** | At least one shop tracks or approximates stock for some product | **`existencias_registradas` is cut** (cut-line 2) and the drift problem leaves the scope entirely |

**The gate is unchanged and remains a gate:** the interviews must be completed and the annex filled **before** the proposal goes to the teaching team. The new scope raises the stakes of the gate rather than lowering them — the proposal is now conditional on a *behaviour* (the owner asking, the client confirming) that the previous scope never depended on.

---

## 5. Candidate capability list for the new project

Seven capabilities, inside the guide's 4–8 band, each with a grader-tickable acceptance idea. The proposal will be built from exactly this list.

| # | Capability | Acceptance idea (one line) |
| --- | --- | --- |
| 1 | **Cuentas, roles y credenciales del cliente** | `dependiente@tienda.test` gets **403** on `/api/v1/clientes/` and no `codigo` appears in any `dependiente` payload; the `dueño` issues a `codigo` that is unique within the shop and rotatable. |
| 2 | **Catálogo de productos y precios** | A seeded `Producto` priced 1,20 € is returned by the catalogue API and is offered as the default price of a charge line; the catalogue holds only the goods eligible for fiado. |
| 3 | **Cargos con líneas de producto** | A two-line `cargo` totalling 6,40 € creates two `CargoLinea` rows and one `LedgerEntry` of 6,40 €; changing the catalogue price afterwards leaves the stored `precio_unitario` untouched. |
| 4 | **Pagos, notas de crédito, antigüedad y suspensión** | A €30 `pago` retires the **oldest** charge first and drops `antiguedad_max_dias` from 45 to 10; a 45-day-old unpaid charge suspends the customer with no human action, and a new charge is refused with **422** and creates no row. |
| 5 | **Confirmación y disputa del cliente** | With a valid `codigo`, the client confirms a pending charge; the API returns `confirmado_en` and the charge's state becomes `confirmado`; the itemised list of **confirmed** charges appears in the client's statement; a `dependiente` session reaches no client endpoint. |
| 6 | **Disputas y corrección por `nota de crédito`** | A disputed 6,40 € charge with `importe_reclamado` 4,20 €, resolved by the `dueño` with a `nota de crédito` of 2,20 €, leaves an outstanding of 4,20 € with the `cargo` row unchanged; a rejected dispute leaves the outstanding at 6,40 € and the state at `en_disputa`. |
| 7 | **Posición real, cierre del día y existencias registradas** | A €30 `pago` raises `caja` by 30 € and leaves `posicion_real` unchanged; the day close stores `esperado`, `contado` and `desviacion`; `existencias_registradas` is returned with its ceiling qualifier and **no** endpoint refuses a `cargo` for lack of stock. |

**Conditional eighth, decided by interview N5:** *facilitar la confirmación por el `dependiente`* — the helper may present a pending charge and receive the client's confirmation, records `facilitado_por`, and reaches no list, no balance and no ageing. **Added only if the interviews show the helper gives the fiado.**

**Two React surfaces, one bundle.** `/app/posicion` (the owner) and `/app/cliente` (the client) — the same Vite bundle served by WhiteNoise at the same origin, with two credential modes (session + CSRF for the owner; per-request `codigo` for the client). No charting library (ADR-12 carries), no CORS, no second host.

---

## 6. What is explicitly out of scope now, and why

| Out of scope | Why |
| --- | --- |
| Point of sale, till, `venta` records, receipts, barcode, payment tender, drawer | ~100–400 hand-entered cash sales a day is a POS without the hardware; a shop that does not record its cash sales cannot have a POS, and a POS cannot ratify a debt |
| Physical stock count, `conteo`, inventory adjustments | A count requires a count; counting is the one action the shop will not adopt (A.3.1) |
| Purchase cost, `coste_medio`, margin, suppliers, purchase orders, reorder proposals | That is `margen`'s domain; the catalogue is a vocabulary, not a cost model |
| E-mail, SMS, push notifications, reminders | Outbound SMTP is blocked on free tiers; the confirmation is designed to be in person |
| Online payments, card, transfers | — |
| Native mobile app, QR/barcode scanning | The credential is typed; the surface is a web page |
| **Client accounts with passwords, self-registration, password reset** | The client has a **scoped credential**, not an account — this keeps "customer accounts" out even while "customer portal" is in |
| Editing or deleting a `cargo`, a `Confirmacion` or any ledger row | Structurally impossible: the ledger is append-only and the API exposes no `PUT`/`PATCH`/`DELETE` on it |
| Debt collection, interest, credit scoring, automated decisions, automated reminders | — |
| Fiscal invoicing, tax reporting, multi-shop, multi-branch, SaaS billing | — |
| File uploads, photographs of the `libreta` | — |
| Background worker, Celery, Redis, WebSockets, a second infrastructure dependency, a separate SPA host | ADR-8 and ADR-1 carry over unchanged |
| Debtors seeing anything but their own data; the client seeing `caja`, `posición real` or another's balance | The client column of the matrix is scoped to one `Customer` by construction |

**Now in scope that was out:** the catalogue with prices, the charge lines, the client-facing page, the confirmation, the dispute path, the per-client `codigo`.

---

## 7. Impact on the abandoned change `tienda-barrio`

**The previous folder is not modified and not deleted.** It stays on disk as history. This section is the *inheritance map* for the new change.

### 7.1 Carries over

| # | What | Where it lives now | Note for the design phase |
| --- | --- | --- | --- |
| C1 | The append-only ledger with **derived** balances, **FIFO** allocation and ageing buckets | `domain/allocation.py`, `domain/ageing.py`, `domain/evaluation.py`, `domain/position.py` | ADR-2 carries unchanged: no stored balance, no stored ageing, no stored confirmation state |
| C2 | The **ORM-free pure domain module** | `backend/tienda/domain/` importing nothing from Django | ADR-3 carries; the new pure functions are `confirmacion_efectiva(cargos, confirmaciones)` and `estado_cargo(cargo, confirmaciones)` |
| C3 | The **two shop roles** and the `dependiente` 403 boundary | `api/permissions.py`, the serializer allowlists | ADR-5 and ADR-6 carry; the allowlist gains a third, disjoint schema class |
| C4 | **Session + CSRF** for the staff surface | `SessionAuthentication`, `CsrfViewMiddleware` | ADR-4 carries **for the staff surface only**; the client surface deliberately uses no session |
| C5 | The **same-origin React mount** | Vite → `STATIC_ROOT` → WhiteNoise | ADR-1 carries; one bundle, two routes |
| C6 | The **deployment spine** | Render free + Neon free + WhiteNoise + keep-alive + `seed_demo` | Carries **verbatim**: no new environment variable, no new infrastructure |
| C7 | The **seed plan** | `manage.py seed_demo` | Extends: the catalogue, the charge lines, per-client `codigo`, one `en_disputa`, one old `sin_confirmar`, most `confirmado` |
| C8 | The **additive** `posición real` (`caja + Σ outstanding`) | ADR-9 | Carries unchanged: a `pago` still moves `caja` and does **not** move `posicion_real` |
| C9 | **Decimal on the wire** (JSON strings) | ADR-13 | Carries; the cent-level invariant "the four buckets sum exactly to the outstanding" stays checkable |
| C10 | Per-row DB constraints + **transactional cross-row checks** | ADR-14 | Carries; the new rule `amount == Σ CargoLinea.total` joins the transactional set |
| C11 | The **422 domain-error contract** | `api/exceptions.py` | Carries; new codes: `codigo_invalido`, `disputa_abierta`, `lineas_descuadradas`, `cargo_ya_confirmado` |
| C12 | The hand-rolled **SVG** chart, no library | ADR-12 | Carries |
| C13 | The **landmine list** and the risks | design §10.5, Part G | Carries; one new landmine: a `codigo` leaking through a staff payload is a data-protection failure, not a cosmetic bug |
| C14 | The **evidence discipline** — the interviews are a gate, and no public source may be cited for the fiado practice | Part D.5 | Carries and tightens: the new scope depends on a *behaviour*, not only on a practice |

### 7.2 Abandoned

| # | What was abandoned | What replaces it |
| --- | --- | --- |
| A1 | The **categorical POS exclusion** ("no `Product`/`Sale` table") | The behavioural exclusion: no sale is ever recorded, and the catalogue is a vocabulary with a price snapshot (T6) |
| A2 | The **"exactly two roles"** claim as a description of the whole system | Two **shop** roles plus one external, customer-scoped principal that is not a role (T3) |
| A3 | The 5-capability contract (`submission-notes.md` §10) | The 7-capability contract in §5 |
| A4 | The 34 requirements / 47 scenarios in `specs/` | New delta specs for the new change. **Nothing is amended in place**; the old specs stay as history |
| A5 | `evidence-annex.md` and its decision checklist as they stand | A **new** annex for the new change (same instrument, revised script, six questions kept + seven added, three rules added). The old annex stays untouched in the old folder |
| A6 | `Shop.usuarios` + `session["shop_id"]` as the **only** scope mechanism | Two scopes, two mechanisms: the staff scope stays the session; the client scope is the credential and has no session |
| A7 | The single-view React plan | Two routes in one bundle, two credential modes |
| A8 | The rationale *"the notebook stays in the drawer"* | *"The notebook stays in the drawer, except for the one page the client is looking at right now"* — and only if the interviews require it |
| A9 | The proposal's scope statement | A new one, built from §5, in Spanish, for the teaching team |

### 7.3 What must **not** be silently reintroduced

- A `venta`/`Sale` table, a till, a receipt, a drawer balance — the defence depends on their absence.
- A stored `saldo` column — ADR-2.
- A `PUT`/`PATCH`/`DELETE` route on any ledger row.
- A third Django group, or a client in `auth_user`.
- A stored `stock` field with no qualifier.
- A second infrastructure dependency, a second origin, a CORS configuration.

---

## 8. Open items carried forward to the proposal

1. **Run the evidence gate.** Three semi-structured interviews with the revised script (six questions kept, seven added, N1–N7), the capture sheet extended with the new fields, and the three new decision rules. The proposal does not go to the teaching team before this is closed. **Decides:** the confirmation (R4), the catalogue (R5), the stock claim (R6).
2. **Confirm the interpretation of the owner's sentence** about the item list appearing only after confirmation (§4, T4): the client's statement shows the itemised fiado for **confirmed** charges, and an unconfirmed charge appears as a summary row with its itemisation revealed only inside the confirmation action. The literal alternative (nothing shown until confirmed) would let the client's statement understate the debt.
3. **Decide the client-credential transport** at design time: per-request credential (recommended — no client session, no scope bleed) versus a client-scoped session with an explicit rule against coexisting with a staff session. The **invariant** is already fixed: no client scope inside a staff session, and no staff scope upgradeable to a client scope.
4. **Fix the `codigo` parameters**: length, alphabet, entropy, expiry or rotation policy, and the rate-limiting mechanism. The printed slip can carry a long token; a spoken code cannot, so the delivery mechanism is part of the parameter.
5. **Confirm whether the `dependiente` gets the facilitator capability** (interview N5) and, if so, bound it exactly as in T3 — including what the helper may see of the presented charge.
6. **Decide whether the client sees their own `credit_limit`** — it explains a refused charge, and it is their own data, but it is a commercial figure.
7. **Decide `Confirmacion` derivation versus storage**: derived from the append-only rows (consistent with ADR-2, recommended) or stored and reconciled (the previous design's `Customer.status` pattern, §5.c).
8. **Decide the `precio` deviation rule**: the catalogue price is a default; the owner may charge a different amount and the line records what was actually charged. Confirm that a deviation is allowed without any extra friction.
9. **Fix the `dia` of the escalation flag** (`sin_confirmar` older than 7 days → *revisar*) and confirm it is derived on read with no background worker.
10. **Re-score and re-confirm the variant choice against the interview results.** The new scope scores **7.45** against the previous `fiado` at **8.15** (T6.3). If rule 4 empties, the project becomes **`fiado desglosado`** (7.80) — catalogue and charge lines without the client portal — and the proposal is rewritten against that scope. If rule 1 empties, it becomes **`margen`** (7.70), as it already was.
11. **Re-check the guide's 4–8 band** against the final list of seven (plus the conditional eighth), and publish the two cut-lines with the proposal.
12. **Carry the `caja` finding into the proposal's honesty section**: daily cash sales are not recorded, so `caja` is the recorded movement total and the `cierre del día` is its only anchor; `existencias_registradas` has no anchor and is therefore a ceiling. Both statements belong in the memoria's limitations.

---

**Status of this artifact:** exploration complete. **No proposal, no specs, no design, no tasks and no code have been written.** The change `fiado-confirmado` is ready for the proposal phase, **conditional on the evidence gate of §4/T7 being run**, with `fiado desglosado` and `margen` as the declared fallbacks.
