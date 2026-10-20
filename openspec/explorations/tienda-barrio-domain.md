# Domain Exploration — `tienda-barrio` (Neighbourhood Shop Management)

**Project:** `final` (PFM — Proyecto Final de Máster)
**Phase:** SDD exploration, second and focused pass (the product decision was already taken by the student)
**Date:** 2026-10-19
**Artifact store:** OpenSpec (`openspec/explorations/`) + Engram mirror (`sdd/tienda-barrio/explore`, project `final`)
**Change slug:** `tienda-barrio` — **no change directory created yet**; the student must approve the variant first.

**Inputs reused (not re-verified):** Engram #117 (`sdd/pfm-selection/explore`) — the first ranked candidate set, its §3 verified platform facts and its §7 scoring weights; Engram #113 (`pfm/requirements-brief`) — the distilled delivery-guide constraints; `openspec/explorations/project-selection.md` §3 and §7.

**Student's non-negotiable product decision:** the base project is *an application for neighbourhood shops ("tiendas de barrio") to manage their shop*. The student has **no direct access to a shop** but can seek interviews with shop owners. The pain point was delegated to this exploration ("you decide, by the rubric").

**Session decisions:** execution mode `interactive` · artifact store `openspec` + Engram mirror · delivery strategy `ask-on-risk` · budget **2–3 months, solo developer**.

**Correction (2026-10-19, raised by the spec phase):** the figures and the demo narrative in PART B.1 originally used a **subtractive** `posicion_real` (`caja − fiado pendiente`, €143.45). The authoritative rule is **additive**: `posicion_real = caja + Σ outstanding` (€681.25). A customer `pago` raises `caja` and lowers `fiado pendiente` by the same amount, so `posicion_real` is **unchanged** by a payment — the money converts, it is neither created nor lost. The affected passages in this file have been corrected in place; the superseded wording was the origin of a sign error, caught in the spec phase before any code was written.

---

## 0. Executive summary (read this first)

**Recommended variant: `fiado` — "La libreta y la caja": a credit book and a real cash position for a neighbourhood shop.**

Its non-obvious core is **not** products, prices or sales. It is an **append-only credit ledger whose balances and ageing are derived, never stored**, plus **a per-customer credit line with an automatic suspension rule**, plus **the shop's net cash exposure** (`caja + fiado pendiente`). A generic POS has none of the three: it stores a price and a receipt, not an aged debt, not a limit, and not a rule that stops lending.

The runner-up is `margen` (real margin and trapped capital). It is *safer to build* (lowest technical risk, a memorable 2×2 board) but it loses on the heaviest criterion: the pain it addresses ("I don't know what makes money") is less *felt* by a shop owner than "who owes me, and for how long". The third variant, `mermas` (stock truth and cash close), is the weakest: that pain is invisible to the owner and its scope is the widest.

**The one thing that decides the whole project:** the week-1 interviews are a **gate, not decoration**. If the three shop owners say that credit is not a problem for them, variant `fiado` is dead on arrival and the project switches to `margen` — the evidence, not the enthusiasm, picks the product.

---

# PART A — The domain: how a *tienda de barrio* actually operates

> This is the core value of this exploration. The variants in Part B are only defensible if the operating reality behind them is described accurately.

## A.1 Operational profile of the shop this project targets

| Dimension | Realistic value for a *tienda de barrio* |
| --- | --- |
| Size / staff | 30–120 m²; family-owned; 1–3 people (owner + a family member or one hired helper) |
| Ownership | The owner is on the floor 6–7 days a week, ~13 h/day. There is **no manager** and no shift handover protocol |
| Basket size | Very low (€1–€15), very high count (100–400 transactions/day) |
| Payment mix | Cash-dominant; a card terminal arrives late and many shops still run without one |
| Assortment | 300–1 500 SKUs: staples, household, fresh, tobacco/alcohol if licensed, plus a few high-margin oddities |
| The real moat | **The owner knows the customer by name** — preferences, who pays on credit, who gets a break, who is behind. The supermarket 20 minutes away is cheaper and has parking |
| The real constraint | Not software. It is **the owner's memory and the owner's absence** |
| Accounting maturity | Almost none. Purchase costs are often not recorded; stock is counted "when it looks empty"; "profit" is what is in the drawer at closing |

## A.2 The pain map

For each pain: **who feels it**, **what it costs today**, and **whether a generic POS already solves it**.

| # | Pain | Who feels it | What it costs today | Does a generic POS solve it? |
| --- | --- | --- | --- | --- |
| 1 | **Physical stock truth ≠ recorded stock.** Mermas (expiry), breakage, theft, unrecorded consumption ("that one was for me"), supplier short-delivery, and the owner's *eyeball* estimate. | Owner (100%), supplier (reputational) | Stockouts of fast movers on Friday evening, exactly when the neighbouring shops are shut → the customer goes to the supermarket and does not come back. Over-ordering of the wrong thing. Cash locked in stock that is not there. | **No.** A POS records *movements*, not *truth*. It cannot know what is on the shelf unless a human counts — and "count your stock" is a feature no barrio owner will use daily |
| 2 | **Informal credit ("fiado", "la libreta", "el cuaderno").** | Owner, the customer, and the shop's *cash position* | Money lent out that the owner cannot total, cannot age, and sometimes cannot recover. Disputes with neighbours ("I paid you" / "you didn't"). No forecasting: the shop's true liquidity is `caja + lo que deben`, and the second term is invisible. | **No.** Most POS systems have no credit concept at all; the ones that do have a "balance" field with no ageing, no limit, no automatic consequence |
| 3 | **Per-product profitability vs volume.** | Owner | The shop does not know which products actually make money because **it does not know its own purchase cost**. Staples bring people in but earn little; a few high-margin slow movers may be the profit. Without cost, margin is a guess and repricing is guesswork | **No.** A POS reports revenue. Margin needs a *cost* per unit, which changes with every delivery, and a POS never revalues it |
| 4 | **Dead stock and trapped capital.** | Owner | 20–30 % of the working capital sits in slow movers that must be discounted or written off, and that occupy the best shelf space | **Partly.** A POS can report "slow moving" only if it knows unit cost and days of cover. Without cost revaluation, the report is wrong |
| 5 | **Pricing: wholesale vs retail, margin erosion.** | Owner | Retail prices are set "what people expect to pay" and are **never recomputed when the supplier raises prices** (fuel, energy, logística). The shop silently eats the difference for months | **No.** Price is a static field in a POS. Nothing links the delivery price to the shelf price |
| 6 | **Cash reconciliation at close.** | Owner (alone) | "Expected" vs "counted" is always different. A persistent −1.5 % variance is a *systematic* leak (a habit of freebies, an unrecorded fiado, a miscount at receiving) but nobody analyses it because a POS reports a single number and stops | **No.** A POS gives you the variance and no decomposition. There is no way to ask "how much of this was breakage vs. theft vs. my own error?" |
| 7 | **Trust and record-keeping when the owner is absent.** | Owner, the family helper, the customer | The shop cannot really take a week off: all knowledge is in one person's head and one paper notebook in one drawer. Disputes cannot be resolved and stock cannot be counted without the owner present | **No.** A POS has no notion of *handover*. This is the real reason the notebook never becomes a database |
| 8 | **Supplier reordering.** | Owner | Reorder decisions come from memory plus the wholesaler's visit schedule. Stockouts of fast movers (lost sale + lost customer) and over-ordering (trapped cash) both come from the same ignorance | **No.** A POS does not know the consumption rate or the supplier lead time, so it cannot propose a reorder point |
| 9 | **Customer loyalty: the owner knowing each customer by name.** | Owner, customer | This is the shop's entire competitive advantage over the supermarket — and it is completely undocumented, so it is fragile, non-transferable and lost the moment the owner is ill | **Partly.** A loyalty program records *points*, not *the relationship*. It also threatens the owner (a database of "loyal customers" is the opposite of a neighbourhood relationship) |

## A.3 Three structural facts that constrain every product in this domain

These are why a generic POS fails here, and they are the design constraints for all three variants.

1. **The shop will not adopt extra manual discipline.** Every feature that asks the owner to do something he does not already do (count stock weekly, reconcile deliveries, categorise 800 SKUs) will not be used. A product here must either *remove* a step or *piggyback on a step the shop already performs* (serving a customer, handing over change, closing the till, calling a debtor).
2. **The shop does not know its cost, so it cannot know its profit.** Any accounting model that assumes a maintained `cost` field assumes the shop already runs an accounting system. It does not.
3. **The owner is the asset, and the owner will not be replaced.** The moat of the shop is personal knowledge; a product that looks like it replaces the owner will be rejected, and a product that *protects the relationship* will be adopted. The literature agrees: in LAC, 55 % of workers are in informality and self-employment is a **rational choice** for autonomy and flexibility — the owner does not adopt tools that take control away.

## A.4 What follows for the product (and for the student's evidence)

- The winning product must be something the owner does **already** and wants to do **better**: writing down what a debtor owes, counting the money at closing, knowing what to reorder.
- It must produce a **number the owner did not have** (a real cash position, the age of the oldest debt, the euros lost to shrinkage) — that number is the demo.
- It must be **defensible in 30 minutes**: one rule, explained in one sentence, testable in one unit test.
- The pain must be **felt**, not merely real. A pain the owner cannot feel (a shrinkage he does not know about) makes for a weak "valor aportado" argument (rubric 10 %) and a weak memoria §3.1.

---

# PART B — Three concrete MVP variants

## B.0 Common frame (applies to all three)

**Non-negotiables (inherited from the delivery guide, Engram #113):** Django backend with related models, migrations, views, templates, validated forms, auth with ≥2 roles, real persistence · ≥1 React view consuming the app's **own** API at the **public** URL · public HTTPS URL, `DEBUG=False`, seeded demo data, one test account per role · public GitHub repo with README, pinned versions, no secrets · 4–8 features (all three variants below sit at **5**) · 30-minute defense including a small live code change · 2–3 months, solo.

**Global non-goals (all variants):** WebSockets · ML/AI of any kind · paid third-party APIs · web scraping · video/audio · IoT · payment processing · multi-tenant SaaS billing · native mobile · a second infrastructure dependency (no Celery/Redis, no external API) · file uploads (no storage backend) · fiscal invoicing / tax reporting.

**Shared deployment spine (verified facts reused, see §F).** Render free web service (0.1 CPU / 512 MB, managed TLS, sleeps after 15 min idle, ephemeral FS) + **Neon** Free Postgres (permanent, no card; **Render's own free Postgres is rejected — it expires at 30 days**). Vite build → Django static → **WhiteNoise → same origin**, so the React view calls `/api/v1/...` on the same public host with the session cookie and the `X-CSRFToken` header. No CORS, no second host, no second URL.

**Why all three avoid being "a POS":** a POS's domain is *what was sold*. Each variant below deliberately leaves the till out of scope and takes the shop's **money** as its subject. That is the structural defence against the "products + sales + dashboard = acceptable" trap.

---

## B.1 Variant A — `fiado` ★ RECOMMENDED

### Name and pitch

**`fiado` — "La libreta y la caja" (the credit book and the cash box).**
*A credit ledger and a real cash position for a neighbourhood shop: who owes you, how old the debt is, how much money is really yours — and a rule that stops the shop from lending more to a customer who is 45 days late.*

### The non-obvious core (stated precisely enough to unit-test)

> **An append-only credit ledger whose balances and ageing are *derived*, never stored, combined with a per-customer credit line that automatically suspends credit, and the shop's net cash exposure.**

Five rules, all implemented as **pure functions over a list of entries** (no ORM inside, fully unit-testable):

1. **Derived balance.**
   `outstanding(customer, at) = Σ charges(occurred_at ≤ at) − Σ payments(occurred_at ≤ at) − Σ credit_notes(occurred_at ≤ at)`
   There is **no stored balance column**. Any past date can be recomputed.
2. **FIFO allocation of payments.** A payment retires the **oldest unpaid charges first**; the residual (payment > total charges) stays as *credit in the customer's favour*. Rule: `allocate_payments(charges, payments) → (unpaid_per_charge, residual)`.
3. **Ageing by charge date.** The unpaid principal of each charge is bucketed by the age of the charge it belongs to:
   `vigente ≤ 7 d` · `envejecido 8–30 d` · `viejo 31–90 d` · `crónico > 90 d`.
   Bucket totals must sum exactly to `outstanding`.
4. **Automatic suspension.**
   `suspended(customer, at) = (age of oldest unpaid charge > 30 days) OR (outstanding > credit_limit)`.
   A suspended customer **cannot receive new credit**: the server rejects the charge (validation error, HTTP 422) and creates **no** ledger entry. A DB-level `CheckConstraint` is the backstop.
5. **Net cash exposure.**
   `posicion_real(at) = caja(at) + Σ outstanding(customer, at)` — the money in the drawer **plus** the money already given away. `caja(at)` = opening cash + Σ cash movements (entradas − salidas).

**Why this is not generic.** A POS stores a *price*, a *receipt* and, at most, a flat "customer balance" field. It has **no ageing**, so it cannot prioritise who to chase; **no line**, so credit never ends; **no rule**, so nothing stops the bleeding; and **no exposure**, so the shop's real liquidity stays invisible. The closest existing instrument is a **paper notebook** — which has the same three defects. The whole product is the digitisation of the notebook *plus the three things the notebook cannot do*, and the notebook is the incumbent we can point at in the defense.

### Roles (2) and the permission matrix

| Capability | `Dueño` (owner) | `Dependiente` (helper) |
| --- | :---: | :---: |
| Record cash movements (entradas / salidas) | ✔ | ✔ |
| Record the day close (esperado vs contado) | ✔ | ✔ |
| See the customer book (aliases, limits, balances) | ✔ | **✖ (403)** |
| Create a customer / set a credit limit | ✔ | ✖ |
| Record a charge (fiado) or a payment | ✔ | ✖ |
| See ageing buckets and the risk ladder | ✔ | ✖ |
| Override a suspension (unblock a customer) | ✔ | ✖ |
| See the real cash position | ✔ | ✖ |
| Manage users and roles | ✔ | ✖ |

**Server-side enforcement (exact):** Django groups `dueno` / `dependiente` · per-view permission mixins on every URL and every DRF view · **owner-scoped querysets** (the credit-book endpoints filter to the owner regardless of role) · the `dependiente` payload of `/api/v1/posicion/` returns `clientes: []` and **no aliases anywhere in the JSON** (not even inside counts) · the day-close endpoint returns only `esperado`, `contado`, `desviacion` for the helper. *Domain rationale (this is the defense answer): the notebook stays in the drawer — it is the owner's private commercial ledger, not operational data for the person who serves at the till.*

### Main entities (5 + the Django `User`)

| Entity | Key fields | Relations |
| --- | --- | --- |
| `Shop` | `id, name, opening_cash, currency, created_at` (exactly one row in the MVP) | 1—N all below |
| `Customer` | `id, FK shop, alias, phone (optional), credit_limit (nullable = "sin límite"), status (activo\|suspendido), suspended_at, suspended_reason, created_at` | 1—N `LedgerEntry` |
| `LedgerEntry` | `id, FK shop, FK customer, kind (cargo\|pago\|nota_credito), amount, description, occurred_at, FK author, created_at` — **append-only, never updated or deleted** | N—1 `Customer`, N—1 `User` |
| `CashMovement` | `id, FK shop, kind (entrada\|salida), concept, amount, occurred_at, FK author, created_at` | N—1 `User` |
| `DayClose` | `id, FK shop, date (unique), expected_cash, counted_cash, variance, FK closed_by, closed_at` | N—1 `User` |

Constraints: `LedgerEntry` is immutable (no `UPDATE`/`DELETE` in the service layer) · `DayClose.date` unique per shop · `amount > 0` checked · `occurred_at ≤ now` enforced in the form (no future-dated entries) · `credit_limit ≥ 0`.

### Scope — exactly 5 features, each with a grader-tickable acceptance criterion

1. **Cuentas y dos roles.** Signup/login, Django groups `dueno` and `dependiente`; the credit book is owner-only.
   *AC:* `dependiente@tienda.test` requesting `/api/v1/clientes/` receives **403**, and the JSON of `/api/v1/posicion/` contains **no alias and no customer id**; the seeded `dueno@tienda.test` sees both.
2. **Libro de clientes y línea de crédito.** The owner creates a customer (alias, optional phone) and sets or changes the credit limit; `credit_limit = null` is an explicit, labelled state ("sin límite").
   *AC:* with a limit of €20, a charge of €25 is **refused server-side** with a validation error naming the limit, and **no `LedgerEntry` row is created**.
3. **Cargos y pagos (la libreta).** Append-only entries: cargo, pago, nota de crédito, each with date, amount and free-text description ("2 L de leche + pan").
   *AC:* the outstanding balance returned by the API for a seeded customer equals the **hand-computed** fixture total, and a €30 payment reduces it by exactly €30 while retiring the **oldest** charge first (asserted in the API test, not only in the unit test).
4. **Antigüedad y suspensión automática.** Ageing buckets computed from charge dates; a customer is auto-suspended when the oldest unpaid charge is older than 30 days **or** the outstanding exceeds the limit.
   *AC:* a seeded customer with a 45-day-old unpaid charge reports `status = "suspendido"` in the API **without any human action**, and a new charge for that customer is rejected with a clear error and creates no entry.
5. **Posición real de la caja y cierre del día.** Cash movements + outstanding credit → the real position; the day close stores expected vs counted cash and the deviation.
   *AC:* after recording a €30 payment, `caja` in the API **and** on the React board rises by exactly €30, `fiado_pendiente` falls by exactly €30, and `posicion_real` is **unchanged** — the money converts, it is neither created nor lost; a day close stores `esperado`, `contado` and computes `desviacion` (seeded: `−4.35 €`), and the deviation is visible in the owner view.

### The React view — "La posición real" at `/app/posicion`

**What it renders** (four composed elements, **no table anywhere**):

1. **Hero: the equation of the shop.** Three large figures on a strip — `Caja` (€412.35) + `Fiado pendiente` (€268.90) = **`Posición real`** (€681.25) — the third labelled *"todo el dinero que es tuyo: en el cajón y pendiente de cobrar"*, plus a delta chip versus yesterday. This number does not exist in any till.
2. **La escalera de riesgos.** One horizontal row per customer with an outstanding balance, **sorted by the age of the oldest unpaid charge, descending** (not by amount). Each row is an **ageing ribbon**: a stacked horizontal bar split into `Vigente / Envejecido / Viejo / Crónico` segments sized in euros, with a **marker line showing the credit limit** and a status chip `Activo` / `Suspendido`. A right-hand chip shows the suggested action (`Recordar`, `Suspender`, `Cobrar hoy`). Clicking a row opens a side drawer with that customer's full ledger.
3. **"El efecto del fiado en la caja."** A two-series area chart over the last 30 days: `Caja` (solid) versus `Posición real` = `Caja + fiado pendiente` (outline). **The gap between the two lines is the story** — it is the money the shop has already given away, drawn to scale; the upper line stays roughly flat because the money converts, it does not vanish.
4. **Cierre de hoy.** A compact card: `Esperado` / `Contado` / `Desviación`, with the deviation chip turning amber when it is not zero.

**Endpoint and payload (the app's own API, same origin, session cookie + `X-CSRFToken`):**

```
GET /api/v1/posicion/
{
  "caja": 412.35,
  "fiado_pendiente": 268.90,
  "posicion_real": 681.25,
  "buckets": { "vigente": 120.00, "envejecido": 78.90, "viejo": 55.00, "cronico": 15.00 },
  "clientes": [
    { "id": 3, "alias": "Marta (Pº 2)", "pendiente": 42.10, "limite": 50.00,
      "antiguedad_max_dias": 45,
      "ribbon": [ { "bucket": "vigente", "importe": 0.00 },
                  { "bucket": "viejo",  "importe": 42.10 } ],
      "estado": "suspendido", "accion": "cobrar" }
  ],
  "serie_caja": [ { "dia": "2026-10-13", "caja": 430.00, "posicion": 585.40 } ],
  "cierre_hoy": { "esperado": 412.35, "contado": 408.00, "desviacion": -4.35 }
}
```

**The 10-second demo at the public URL.** Open the public URL and log in as `dueno@tienda.test` → the board shows `Caja 412.35 + Fiado pendiente 268.90 = Posición real 681.25`. In a second browser window (or a private window) log in again and record a €20 payment from "Marta (Pº 2)", whose ledger holds a €20.00 charge dated 45 days ago and a €10.00 charge dated 10 days ago. Switch back: **FIFO retires the 45-day charge**, her ribbon loses its €20 band, her `antiguedad_max_dias` drops to 10 and her status chip flips `Suspendido` → `Activo` — **within one auto-refresh cycle (20 s) or immediately on reload**. The drawer rises €20.00 and `Posición real` **does not move**: the money changed form, it was never created and never lost. *None of this requires a product tour.*

**Why it is not a table dump.** There is no grid anywhere: the customers are a **ranked ladder of risk** whose encoding is a stacked ageing bar with a limit marker and a decision chip; the money is a **hero equation**; the third element is a **two-series chart whose whole purpose is to draw the gap** between what is in the drawer and what is out there; the fourth is a single-card close. Every element answers "what do I do today?", not "show me rows".

**Why it is not generic.** A POS renders *goods, prices and receipts*. This renders *money the owner has already given away, aged, capped, and — because of a rule — no longer extendable*. None of that exists in the POS category. The nearest artefacts in the world are a **paper notebook** and a **spreadsheet**, and both fail in the same three ways; that is the comparison the panel will hear.

### Non-goals

No point of sale, no products, no prices, no receipts, no barcode, no till (deliberate: the MVP is the money, not the sale) · no customer portal and no online payments · no debt collection, no interest, no e-mail/SMS reminders (free tiers block outbound SMTP on port 25) · no accounting/tax/invoicing · no supplier purchasing · no multi-shop / multi-branch · no file uploads, no photos of the notebook · no native mobile · no bank integration · no background worker (the ageing rule is evaluated on read).

### Hardest technical part + cheapest de-risking experiment

**Hardest part — (a) the derived-ledger correctness.** FIFO allocation, ageing buckets and the auto-suspension rule must be exactly right: one off-by-one corrupts the hero number, the risk ladder and the suspension decisions at the same time. **(b) The permission model must be airtight** — the helper must not reach customer data through *any* route, including DRF pagination metadata, error payloads, the day-close aggregates or the `serie_caja` series. **(c) The number must be explainable**: the API must return the breakdown, not only the total, or the owner cannot trust `Posición real`.

**Cheapest de-risking experiment (week 1, ~3 h, before any model or view).** Write the pure functions in a standalone module with a fixture of 3 customers (mixed cargos and pagos, one 45-day-old unpaid cargo, one payment exceeding the debt, one over-limit customer) and assert: bucket totals sum exactly to the outstanding balance; FIFO retires the oldest cargo first; the 45-day customer is `suspendido` with no human action; the over-limit customer is refused; the position equals the hand-computed number. **If the module is green, the product's core is proven; if it is not, nothing else matters.** Then one permission test: the helper gets 403 on `/api/v1/clientes/` and the `/api/v1/posicion/` payload contains no alias.

### The 5–6 questions the defense panel will ask

1. **"¿Por qué no una libreta de papel o un Excel?"** → A notebook has no ageing, so you cannot prioritise who to ask; no limit, so credit never ends; no rule, so nothing stops the bleeding; and it dies with the owner, so the shop cannot take a week off. Excel can age a list but cannot enforce a rule and cannot survive the owner's absence — re-typing a notebook into a sheet is exactly the manual step that makes it stale.
2. **"¿Esto no es una simple tabla de saldos?"** → A balance is a number; this is a ledger with **derived** balances, ageing by charge date, a credit line with an **automatic suspension rule**, and the shop's **net cash exposure**. No POS in this category ages a balance, caps it, or stops credit on its own.
3. **"¿Cómo garantizáis que un cliente con 40 días de deuda no recibe más fiado?"** → The rule is evaluated server-side inside the same transaction as the charge, returns a validation error and creates no entry; a `CheckConstraint` is the DB backstop; it is not a UI-only check. Demo: try to charge a suspended customer and the API refuses.
4. **"¿Y la protección de datos? Guardáis deudas de clientes con nombre."** → We store an alias, an optional phone and amounts: no DNI/NIE, no addresses, no bank data, no photographs of the notebook. The credit book is visible **only to the owner** (the helper role is a hard 403); every write records its author; deletion on request is one admin action; documented in memoria §3.6. Legally this is the shop's **internal record of a commercial credit relationship** — no interest, no collections, no automated decision, no credit scoring.
5. **"¿Cómo se calcula la posición real y por qué me fiáis de ella?"** → It is a sum over immutable entries with one explicit FIFO allocation rule, recomputed on read, so it cannot drift (there is no stored balance to drift). The API returns the **breakdown** (`caja`, `fiado pendiente`, buckets) and a single pure function is the single source of truth, covered by unit tests.
6. **"¿Por qué no incluye producto, precio y punto de venta?"** → Deliberate scope: the MVP answers *the money question*; serving at the till is well served by cheap tools and is not the shop's binding constraint. Excluding the till is also what makes this project *not* a generic POS. It is the first entry of the future-work section, not an omission.
7. **"¿Qué harías con más tiempo?"** → Promised-payment dates and a weekly collection plan; a handover mode for a second owner; exporting the ledger into the accounting the shop eventually adopts; and a *cautionary* decision-support layer on limits (still deterministic, still explainable, never automatic).

### Rubric fit

- **Backend correctness (30%) — strong.** 5 related models with real constraints; an append-only ledger with a migration-safe schema; a pure, unit-tested rules layer (`allocate_payments`, `bucket_of`, `evaluate_customer`, `real_position`); derived state instead of stored state (the classic "the number is always right" backend story); validated forms; role-scoped querysets; transactions around every write.
- **React data consumption (15%) — strong.** A risk ladder with ageing ribbons, a hero equation and a two-series chart — a decision board, not a table — consuming the app's **own** API at the public URL with session + CSRF and no CORS.
- **Architecture (15%) — strong.** One deployable service; layered Django apps; DRF serializers; the domain rules isolated in an **ORM-free** module; WhiteNoise single origin; every decision (no POS, no worker, no token library) documented with rationale.
- **Security & data integrity (15%) — strong.** A genuinely domain-specific permission rule (the notebook is not for the helper), session + CSRF on every mutation, PBKDF2 (1 M iterations), no secrets in git, `DEBUG=False`, HTTPS, `ALLOWED_HOSTS` locked, data minimisation, immutable ledger.
- **Documentation & presentation (15%) — strong.** README with install/env/tests/public URL/credentials; memoria §3.1–3.8 with the interview annex, ER and architecture diagrams, the personal-data section and a real "errors found and fixed" section.
- **Reflection & contributed value (10%) — strong.** Quantifies cash tied in credit, the age of the oldest debt, disputes avoided and days of "cash blindness"; states honestly the adoption risk (the owner must write down what he used to keep in his head) and the legal/privacy limits.

---

## B.2 Variant B — `mermas` — "La caja real: verdad de stock y cierre del día"

### Name and pitch

**`mermas` — "La caja real".** *A stock-truth and cash-close app for a neighbourhood shop: every difference between what the book says and what is on the shelf must get a **name** — merma, hurto, error de recepción — and it is priced in euros, and the month does not close while there is money without a name.*

### The non-obvious core

> **The attribution model ("toda diferencia tiene un nombre") plus the moving-average cost revaluation that turns it into euros.**

- **Attribution:** the difference between *expected* stock (from the movement ledger) and *counted* stock must be classified into a fixed taxonomy: `merma`, `hurto`, `error_recepcion`, `consumo_propio`, `regalo`, `descuente`, `sin_explicar`. The headline metric is **`dinero sin explicar`**. The month **cannot be closed** while `dinero sin explicar` exceeds a tolerance (proposed: 1 % of the period's sales) — the owner must either explain the difference or explicitly accept it.
- **Revaluation:** on every delivery, `coste_medio = (valor_anterior + valor_entrada) / (unidades_anteriores + unidades_entrada)` — a weighted moving average recomputed per unit, so a product bought last week at a different price carries that price. The euro value of a merma is therefore the price *actually paid*, not a stale manual field.
- **Cash close:** `esperado = apertura + ventas − devoluciones`; `contado` entered by the owner; `desviacion = esperado − contado`, decomposed with the same cause taxonomy (fiado no anotado, cambio mal dado, merma no registrada…).

**Why it is not generic.** A POS records movements and reports a variance **number**; it never reconstructs truth, never attributes a difference to a cause, never revalues cost, and never blocks a close. The closest known discipline is warehouse cycle counting — which assumes a warehouse, a scanner and a person whose job it is. The rule "every difference must have a name, and the month does not close with unnamed money" has no analogue in shop software.

### Roles (2) and the permission matrix

| Capability | `Dueño` | `Dependiente` |
| --- | :---: | :---: |
| Register products and deliveries (with real unit cost) | ✔ | ✔ |
| Perform a physical count and submit counted quantities | ✔ | ✔ |
| **Classify a difference (assign its cause)** | ✔ | **✖** |
| Register a sale | ✔ | ✔ |
| Close the day and close the month | ✔ | **✖** |
| See the loss board and the "dinero sin explicar" | ✔ | ✖ |
| Adjust a stock level manually | ✔ | ✖ |

*Domain rationale: **quien cuenta no explica y quien explica no cuenta** — separation of duties, because a difference that the counter also classifies is a difference nobody classifies.*

### Main entities (5)

`Product` (`id, name, category, unit, price_sale, stock_booked, cost_avg, supplier, is_active`) · `Movement` (`id, FK product, kind (entrada|salida|ajuste), qty, unit_cost, occurred_at, reason`) · `Count` (`id, FK product, counted_qty, counted_at, FK counted_by, note`) · `Difference` (`id, FK product, expected_qty, counted_qty, delta, cause, note, FK attributed_by, attributed_at`) · `CashSession` (`id, opened_at, opening_cash, expected_cash, counted_cash, variance, FK closed_by, closed_at`).

### Scope — exactly 5 features

1. **Catálogo y entregas.** *AC:* registering a delivery of 24 units at €0.85 recomputes `cost_avg` for that product, and the recomputed value is returned by the API.
2. **Conteo físico guiado.** *AC:* counting a product with expected 12 and physical 10 creates a difference with `delta = −2`, and the API returns its euro value at `cost_avg`.
3. **Atribución obligatoria de diferencias.** *AC:* a difference saved without a cause appears as `sin_explicar`, and the month-close endpoint returns **409** while the total unexplained money exceeds the tolerance; assigning a cause moves it out of that bucket.
4. **Cierre de caja.** *AC:* a close with expected €412.35 and counted €408.00 stores `desviacion = −4.35`, and the value is visible in the owner view.
5. **Tablero de mermas.** *AC:* the board's total equals the sum of its per-cause rows and of its per-product rows; the "sin explicar" figure changes exactly when a cause is assigned.

### The React view — "El conteo" at `/app/conteo`

**What it renders:** a **guided count sheet** — one card per product with a large numeric input, the expected quantity, a live delta chip and the euro value of the difference, plus a running total for the session — plus a **money waterfall** for the period (`ventas − mermas − hurtos − errores − sin explicar = resultado`) and a panel listing the products with the largest **unnamed** money. **Endpoint:** `GET /api/v1/conteo/sesion/<id>/` and `GET /api/v1/mermas/resumen/?desde=&hasta=`. **Demo:** count 8 products, attribute 3 differences, watch the "sin explicar" bar shrink and the waterfall rebalance; then attempt to close the month while unnamed money remains → the action is refused with an explanation.

**Why it is not a table:** a guided flow with a running variance, plus a waterfall that shows *where the money went*. **Why it is not generic:** the product's headline is a *refusal to close* — a POS never blocks anything.

### Non-goals

No point of sale, no receipts, no barcode/QR scanning, no purchase orders to suppliers, no customer credit (variant A's domain), no fiscal invoicing, no photo uploads, no multi-shop, no mobile, no e-mail/SMS, no integrations.

### Hardest technical part + cheapest de-risking experiment

**Hardest:** computing *expected* stock correctly over a movement ledger (`esperado = apertura + Σ entradas − Σ salidas`) while the revaluation changes the cost used to price the difference; and building a count flow quick enough to be used (a 300-SKU count is useless if it takes an hour). **De-risk (~3 h, day 1):** write `expected_qty(movements)` and `revalue_cost(movements)` as pure functions with a hand-checked fixture, before any model.

### The 5–6 questions the defense panel will ask

1. *"¿Por qué no un inventario en Excel?"* → An Excel sheet cannot reconstruct expected stock from movements, cannot revalue cost on delivery, and cannot refuse to close with unnamed money — it can only show a number the owner already doubts. 2. *"¿No es esto gestión de almacén?"* → Warehouse cycle counting assumes a scanner, a WMS and a dedicated operator; a 40 m² shop has none of the three, and the rule that matters here — *every difference must have a name* — is a discipline, not a feature of any warehouse tool. 3. *"¿Y si el dueño no cuenta?"* → That is exactly what the interviews must answer; if counting is not viable, this variant dies and we switch to `margen`. 4. *"¿Cómo sé que el coste medio es el precio real?"* → Weighted moving average recomputed on each delivery, unit-tested against a hand-computed fixture; it is an approximation by design and the memoria says so. 5. *"¿Cómo evitas que el dependiente clasifique una merma para que el dueño no la vea?"* → Separation of duties: the counter submits quantities, only the owner attributes causes, and the audit trail stores both actors. 6. *"¿Qué harías después?"* → Supplier comparison by delivered cost, waste-by-category trends, and a reorder proposal (which is variant C's core).

### Rubric fit

Backend **strong** (reconciliation + revaluation + transactions, 5 models) · React **good** (guided flow + waterfall, but the underlying data is tabular and the "count sheet" is the most common WMS screen in the market) · Architecture **strong** · Security **good** (separation of duties is a real, demonstrable rule) · Documentation **strong** · Reflection **the weakest of the three** — the owner cannot feel a shrinkage he does not know about, so "valor aportado" rests on a number the software invents rather than a pain the owner reports.

---

## B.3 Variant C — `margen` — "El margen real y el capital parado"

### Name and pitch

**`margen` — "El margen real y el capital parado".** *A profit-and-capital app for the shop: it revalues your stock at the price you actually paid at the last delivery, tells you which products are the traffic that brings people in, which ones are profit, and which ones are **dead capital** — and then tells you exactly what to order tomorrow and how much cash that will tie up.*

### The non-obvious core

> **A revalued-cost margin model, a traffic-versus-profit classification, and a capital-aware reorder rule — three pure functions over the movement history.**

1. **Revalued cost:** `coste_medio` (weighted moving average) recomputed on every delivery; `margen_% = (precio_venta − coste_medio) / precio_venta`. The shop never maintains a cost field — it cannot.
2. **Classification (quadrant), using the shop's own medians as thresholds** (volume threshold = median units sold in 30 d; margin threshold = 20 %):
   `ancla` (high volume, low margin — **keep it: it brings people in**) · `estrella` (high volume, high margin) · `margen` (low volume, high margin — protect it) · `carga` (low volume, low margin **and** capital tied up — the candidate for a discount or a delist).
3. **Reorder rule:** `tasa_diaria = units_sold_30d / 30`; `punto_de_pedido = tasa_diaria × plazo_proveedor_días + stock_seguridad`; `stock_seguridad = tasa_diaria × 2`; `sugerencia = max(0, punto_de_pedido − stock_actual)`, rendered with its **capital outlay** (`sugerencia × coste_medio`).

**Why it is not generic.** A POS reports revenue and stores a price; to compute margin it would need a cost the shop does not have and never updates. It therefore cannot produce a margin, cannot value the capital sitting on the shelf, cannot compute days-of-cover, and cannot propose a reorder — it can only count what already left. The nearest equivalents live in ERP/retail-analytics products for chains with barcode infrastructure and a finance department.

### Roles (2) and the permission matrix

| Capability | `Dueño` | `Ayudante` |
| --- | :---: | :---: |
| Register products, price, supplier, lead time | ✔ | ✖ |
| Register deliveries (quantity, real unit cost) | ✔ | ✔ |
| Register sales | ✔ | ✔ |
| See margins, cost averages and capital tied up | ✔ | **✖** |
| See the reorder proposal | ✔ | ✖ |
| Accept / reject a reorder proposal | ✔ | ✖ |
| See the daily sales figures | ✔ | ✔ |

*Domain rationale: margins are the owner's commercial information; you do not discuss margins with the person who stacks the shelf.*

### Main entities (5)

`Product` (`id, name, category, unit, price_sale, stock, cost_avg, FK supplier, lead_time_days, is_active`) · `Supplier` (`id, name, lead_time_days, contact`) · `DeliveryLine` (`id, FK product, qty, unit_cost, received_at, FK supplier`) · `SaleLine` (`id, FK product, qty, unit_price, occurred_at`) · `Proposal` (`id, FK product, qty_suggested, unit_cost, capital, created_at, accepted_at, FK accepted_by`).

### Scope — exactly 5 features

1. **Catálogo, proveedores y entregas.** *AC:* a delivery of 24 units at €0.85 recomputes `cost_avg` and the API returns it; a second delivery at a different price recomputes it again (weighted).
2. **Ventas y rotación.** *AC:* 30 recorded sales produce a daily rate and a `dias_sin_rotar` figure that matches a hand-computed value.
3. **Clasificación margen × volumen.** *AC:* a product with high volume and low margin is classified `ancla`, and a low-volume/low-margin product with stock on hand is classified `carga`; the API returns the classification *and* the threshold values used.
4. **Propuesta de pedido.** *AC:* for a product below its reorder point the proposal returns a quantity and a capital outlay equal to `qty × cost_avg`.
5. **Tablero de capital.** *AC:* the capital tied up in the board equals the sum of `cost_avg × stock` over the products it lists, and the "dinero parado" total excludes products that rotated in the last 30 days.

### The React view — "El tablero del margen" at `/app/margen`

**What it renders:** a **2×2 map** (x-axis = units sold in 30 d, y-axis = margin %), one bubble per product **sized by the capital tied up**, positioned by its two axes, with the four quadrants labelled (`Anclas de tráfico`, `Estrellas`, `Margen`, `Carga muerta`); clicking a bubble opens a card with its cost average, days without rotation and its capital; a right-hand panel **"Pedido de mañana"** lists the reorder proposals with quantity and euros; a bottom strip shows **"Capital parado: €X en Y productos"**. **Endpoint:** `GET /api/v1/margen/tablero/`. **Demo:** point at the bubble in "Carga muerta" ("14 unidades, €118 inmovilizados, 74 días sin rotar"), then show the proposal panel ("12 L de leche, coste €0.85, €34 de capital") — a concrete tomorrow-morning action.

**Why it is not a table:** a 2×2 position map with sized bubbles encodes two dimensions plus a third (capital) in a way a grid cannot; the reorder panel is a decision, not a report. **Why it is not generic:** the axes and the proposal are computable only from revalued cost — the thing a POS does not have.

### Non-goals

No point of sale/receipts, no customers, no credit (variant A's domain), no shrinkage counting (variant B's domain), no barcode, no fiscal invoicing, no supplier ordering integration, no multi-shop, no BI dashboard beyond this board, no mobile, no e-mail/SMS.

### Hardest technical part + cheapest de-risking experiment

**Hardest:** (a) the revaluation must stay correct when deliveries arrive at different prices and sales interleave; (b) the classification thresholds must be **defensible and shop-relative** (medians, not arbitrary constants) or the panel will call it a gimmick. **De-risk (~2 h, day 1):** write `revalue_cost(movements)`, `classify(product, thresholds)` and `reorder_suggestion(rate, lead_time, stock)` as pure functions with a hand-checked fixture.

### The 5–6 questions the defense panel will ask

1. *"¿Por qué no un TPV normal con un informe de beneficios?"* → A TPV knows the price but not the cost; the shop's cost changes with every delivery and is never maintained. Without a revalued cost there is no margin, no capital tied up and no reorder point — the report would be a revenue report wearing a margin label. 2. *"¿Por qué `ancla` y no subirle el precio?"* → High-volume, low-margin products are the traffic that brings people in; raising them prices the shop out of its own neighbourhood. The model makes that trade-off explicit instead of leaving it to intuition — and it is a hypothesis to test in the interviews, not a law. 3. *"¿De dónde sale el coste medio?"* → Weighted moving average recomputed on each delivery; unit-tested against a hand-computed fixture; it is an approximation and the memoria says so explicitly. 4. *"¿Cómo defines los umbrales?"* → Medians of the shop's own 30-day history, not external constants; the API returns the thresholds used, so the board is self-explaining. 5. *"¿Y si el dueño no registra las entregas?"* → Then there is no cost and no margin; that is a real adoption dependency and the first interview question — the MVP asks for deliveries because the shop receives deliveries anyway. 6. *"¿Qué harías después?"* → Supplier price comparison, waste trends, and (if the interviews support it) the credit book of variant A.

### Rubric fit

Backend **strong but read-mostly** (pure analytic layer, very low risk, few writes) · React **strong** (a memorable 2×2 board) · Architecture **strong** (pure functions, clean layering) · Security **good** (two roles, margins hidden from the assistant) · Documentation **strong** · Reflection **good** — capital trapped and unknown profitability are real, but the owner's felt pain ("I don't know what makes money") is less sharp than the felt pain in variant A.

---

## B.4 Comparison at a glance

| | `fiado` (A) | `mermas` (B) | `margen` (C) |
| --- | --- | --- | --- |
| Real problem | Nobody knows who owes what, for how long; credit never ends | Recorded stock ≠ real stock; differences have no name and no price | The shop does not know its cost, its margin or its trapped capital |
| Roles | 2 (owner / helper) | 2 (owner / helper, separation of duties) | 2 (owner / assistant) |
| Core entities | 5 | 5 | 5 |
| Features | 5 | 5 | 5 |
| Non-obvious core | Derived ageing ledger + credit line with auto-suspension + net cash exposure | Mandatory cause attribution of every difference + moving-average cost revaluation + a close that can be refused | Revalued cost + traffic/profit quadrant + capital-aware reorder rule |
| React visualisation | Ageing-ribbon risk ladder + hero cash equation + "fiado vs caja" area chart | Guided count sheet + money waterfall by cause | 2×2 margin×volume map with capital-sized bubbles + reorder proposal |
| Is the pain *felt* by the owner? | **Yes** (money + disputes + neighbours) | No (a shrinkage they cannot see) | Partly (trapped capital is felt; unknown margin is not) |
| Extra infrastructure | None | None | None |
| Upload/storage needed | No | No | No |
| Main risk | Personal-data sensitivity; the owner must write down what he keeps in his head | The owner must count; scope is the widest | Cost data quality depends on the owner recording every delivery |

---

# PART C — Scoring and recommendation

**Weights reused from the first exploration** (Engram #117 §7 / `openspec/explorations/project-selection.md` §7) so that both decisions are comparable:

| Criterion | Weight | Rationale (unchanged) |
| --- | --- | --- |
| Real-world need strength | 25 % | Rubric "reflexión y valor aportado" (10 %) + the guide's rule "parte siempre de una necesidad real"; a panel that cannot believe the problem awards depth nowhere |
| Scope fit for 2–3 months solo | 20 % | Backend correctness (30 %) + architecture (15 %) are lost entirely if the app is unfinished; there is one defense attempt per quarter, so a late failure is fatal |
| Technical risk (lower is better; 10 = lowest risk) | 15 % | Security (15 %) and documentation (15 %) both degrade when the core rule is flaky or cannot be explained |
| Deployability | 15 % | Documentation/presentation (15 %) requires a live public URL; a deployment that dies before the defense is an automatic loss |
| Defense defensibility | 15 % | The 30-minute panel is where the 70 % of the rubric that depends on explanation is actually cashed in |
| Distinctiveness / memorability | 10 % | Tie-breaker: among equally sound candidates, the memorable one lands "notable" instead of "acceptable" |

**Scores (1–10, 10 = best; technical risk inverted so 10 = lowest risk).**

| Criterion | W | `fiado` (A) | `mermas` (B) | `margen` (C) |
| --- | --- | --- | --- | --- |
| Real-world need strength | 25 % | **8** | 6 | 7 |
| Scope fit for 2–3 months solo | 20 % | **8** | 6 | 7 |
| Technical risk (lower better) | 15 % | 7 | 6 | **8** |
| Deployability | 15 % | **9** | 8 | **9** |
| Defense defensibility | 15 % | **9** | 7 | 8 |
| Distinctiveness / memorability | 10 % | 8 | 7 | **8** |
| **Weighted total / 10** | | **8.15** | 6.55 | 7.70 |

## C.1 Winner: `fiado` (8.15)

`fiado` wins because it is the only variant that is strong **simultaneously on the two heaviest criteria**: a pain the owner *feels every day* with money and social friction at stake (need = 8), and a scope that fits comfortably in 2–3 months solo with five entities, five features, one pure-function core and no extra infrastructure (scope = 8, deployability = 9). It also carries the most memorable defense story in the set: *"the incumbent is a paper notebook, and here is the three things a notebook cannot do"* — a comparison the panel can verify in their own head, and a rule (`suspend credit automatically after 30 days`) that is one sentence to explain and one function to test.

Its React view is the second-strongest of the three but the most *domain-specific*: a risk ladder with ageing ribbons, a hero equation (`caja + fiado pendiente = posición real`) and a chart whose only purpose is to draw the gap between the drawer and the money already lent. Nothing in the POS category produces any of the three.

## C.2 Runner-up: `margen` (7.70) — precisely why it lost

`margen` is the **safest** of the three to build: a read-mostly analytic layer over pure functions (technical risk 8/10 — the best score in the table), the smallest entity count, and the most memorable visual (a 2×2 board). It loses on the **heaviest** criterion, need strength (7 vs 8), for three concrete reasons:

1. **The pain is less felt.** "I don't know what makes money" is a question a shop owner has never been asked and does not notice. "Who owes me, how much, and for how long" is a question the owner asks *constantly* and usually cannot answer. The rubric's "valor aportado" is easier to defend with a number the owner was already missing.
2. **It depends on a behaviour the shop does not have.** Every number in `margen` requires that **every delivery is recorded with its real cost**. If the owner misses one delivery, the revalued cost, the margin, the quadrant and the reorder proposal are all silently wrong. `fiado` has no such dependency: the ledger is written *by* the very act the system records (handing over goods), so the data is captured as a by-product of the shop's normal work. In the interviews this is a one-line difference; in the demo it is the difference between a number that is always right and a number that is right if the shop behaves.
3. **Its distinctiveness is a *presentation* distinction, not a *mechanism* distinction.** The quadrant map is a familiar BI pattern. The ageing + credit line + auto-suspension + exposure model has **no POS analogue at all** — a POS has no ageing, no limit, no automatic consequence and no exposure concept.

**When to pick `margen` instead:** if the week-1 interviews show that the owner **does not extend credit at all** (some shops do not, and that is a real possibility — see the evidence plan's decision rule), variant `fiado` collapses and `margen` becomes the correct choice immediately. Its pure-function architecture is fully transferable, and the 2×2 board is the safest React view to defend.

## C.3 Why `mermas` (6.55) lost

It is the only variant whose **core pain the owner cannot feel** — nobody misses a 1.6 % shrinkage they cannot see — so the "valor aportado" argument would rest on a number the software invents rather than a complaint the owner can report. It also carries the **widest scope for the least rubric payoff**: two mechanisms (reconciliation *and* cash close) plus a guided count flow, and it makes the most invasive demand of the shop — count your stock. Its "every difference must have a name" rule is genuinely good, but it is a discipline borrowed from warehouse cycle counting, which assumes a scanner and a dedicated operator; a 40 m² shop has neither.

---

# PART D — Week-1 evidence plan (student with NO direct shop access)

> The interviews are a **gate**, not decoration. Deliverable: a one-page annex with anonymised notes, verbatim quotes and the numbers — the evidence block of the one-page proposal and the backbone of memoria §3.1.

## D.1 How to recruit three shop owners (concrete channels, ordered by expected yield per hour)

1. **Street rounds (highest yield, cheapest — do this first).** Pick three streets or neighbourhoods within 20 minutes of where the student lives. Walk 12–15 shops and speak **at the door**, between **9:00 and 10:30** (before the rush, before the deliveries, and while the owner is not alone with a queue). Ask the six questions in D.2 — 12–15 minutes each. Bring a **printed one-pager** and no laptop: the first question must be asked face to face, and the point of the first visit is to get the second one. Target: 3 conversations, ~2 hours of walking + talking.
2. **The neighbourhood / merchants' association (highest volume per minute).** The town's *asociación de vecinos* and *asociación de comerciantes* both run WhatsApp groups with dozens of shop owners. One message to the president, offering a 6-question form for their members, can return 30–50 responses. This is also the best single piece of *quantitative* evidence in the plan (e.g. "X % de las tiendas llevan libreta").
3. **The wholesaler / "almacén de ultramarinos" salesperson.** Whoever restocks the local shops visits every one of them each week and knows their situation — including who is good for credit. A 20-minute conversation with one salesperson is cheap, high-signal evidence **and** a recruitment channel (the rep can introduce the student to three owners).
4. **The market and the street market (puestos).** Market stallholders are exactly this kind of small retailer, are usually talkative, and know other shopkeepers. Also the *feria* on weekdays.
5. **Fallback (remote student or short on time).** Publish the same six questions as a Google Form: a local Facebook/WhatsApp neighbourhood group, the municipal commerce office's mailing list, a university noticeboard, a town subreddit/Threads post. Target **≥15 responses** so that one proportion (e.g. "X % keep a notebook") is defensible, and treat the form responses as a *quantitative* complement to the three interviews (which provide depth and quotes).

**Consent (important for memoria §3.6 and for the rubric):** ask permission to quote **anonymously**; do not record names, exact debt amounts, or photographs of the notebook; state that the goal is a university project, not an audit.

## D.2 The interview script (plain, neutral Spanish — use it verbatim)

**Opening (30 seconds):**
> "Hola, soy estudiante y estoy preparando un proyecto de universidad sobre herramientas para tiendas de barrio. No es una auditoría ni quiero ver tus cuentas: solo me interesa cómo llevas el día a día. ¿Tienes 10 minutos?"

**The six questions:**

1. "Cuando un cliente te pide fiado, ¿qué haces? ¿Lo anotas en algún sitio —la libreta, el móvil, una lista— o se queda en tu cabeza?"
2. "¿Sabes siempre cuánto dinero te deben en total? ¿Y desde cuándo le deben cada uno?"
3. "¿Te ha pasado que alguien te debe y no sabes cuánto, o que se pierde la libreta?"
4. "Si cierras la caja al final del día, ¿el dinero que hay en el cajón es el que esperabas? ¿Notas que falta algo?"
5. "Cuando te vas unos días —enfermo, vacaciones—, ¿alguien puede saber quién te debe o cuánto hay en el almacén?"
6. "Si una herramienta te dijera a quién hay que recordarle el pago hoy y cuánto dinero es de verdad el tuyo, ¿la usarías? ¿Qué te quitaría de cabeza?"

**Optional open question (use it if the interview is going well):**
> "¿Qué parte de tu negocio no controlas bien y te cuesta dinero?"

**Closing:** "Gracias, te escribo con el resumen y te digo si tu tienda sale en la anonymous annex. ¿Puedo llamarte otra vez si me surge una duda?" (leave your contact details)

**Note on the ordering:** question 1 is asked **third-person** ("un cliente te pide fiado") so that an owner who does *not* extend credit can still answer it, and so that an owner who does is not put on the spot in the first minute. Question 6 is the one that reveals the *willingness to adopt*, which is as important as the pain.

## D.3 What to capture (per interview)

| What | Why it matters |
| --- | --- |
| Whether they keep a notebook / WhatsApp list / photo of a list, and what the "record" actually is | Establishes the incumbent we will replace |
| The **approximate total outstanding** (a number, a range, or "no sé") | The gap between "no sé" and a number is the product's value proposition |
| **The age of the oldest debt they can recall** ("¿cuál es la deuda más vieja que te rememberás?") | Converts "no sé" into a data point; this is the question that makes the ageing model credible |
| What happens at closing (does the owner count the drawer? compare with anything?) | Decides whether variant B is even viable |
| Who can serve/answer when the owner is away | The absence-of-the-owner pain (§A.2 row 7) |
| Verbatim quotes, anonymised | Exactly what the panel wants in memoria §3.1 |
| Which product they would *not* stop selling because it brings people in | Tests variant C's `ancla` hypothesis before building it |
| Whether they would accept a tool that *stops* them from giving credit | Tests whether variant A's automatic suspension is welcome or hostile |

## D.4 How the evidence feeds the proposal (and the decision rule)

- The proposal's §1 cites **three interviews** with two or three **anonymised verbatim quotes** and **one number** (e.g. "en 2 de 3 tiendas el saldo pendiente se conoce 'a ojo' y ninguna sabía la antigüedad de la deuda más vieja").
- §2 of the proposal becomes an **evidence annex**: notes, quotes, the interview dates, and the recruitment channel used (so the panel can judge how the sample was obtained).
- The memoria §3.1 uses the same annex; §3.8 will list the interview round as the first "error found and corrected" (the first hypothesis — that owners would keep a precise ledger — was wrong, and the project was re-scoped around what they actually do).
- **Decision rule (state it in the proposal):** if the three interviews show that **credit is not a real practice** in the shops visited (all cash, no notebook, no debts), then variant `fiado` is **rejected** and the project switches to `margen`, with the interview evidence as the reason. If the interviews show the opposite but also show that **the owner refuses to write anything down**, the correct MVP is a **single-tap charge record** (the same ledger, with the *minimum* possible data entry) rather than a full notebook. If the interviews show that **counting is routine** and the owner already reconciles the drawer, variant `mermas` becomes viable — but it stays third in the ranking.

## D.5 Verified public sources (all fetched and read on 2026-10-19; none invented)

| # | Source | URL | What it supports | Limits |
| --- | --- | --- | --- | --- |
| S1 | **World Bank — "Rationalizing Informality"** (publication page, LAC) | https://www.worldbank.org/en/region/lac/publication/rationalizing-informality (Spanish: https://www.bancomundial.org/es/region/lac/publication/rationalizing-informality) | "Fifty-five percent of workers in Latin America and the Caribbean work in the informal economy, a figure that has remained high for nearly two decades"; and "most informal activity thrives in **micro-businesses and family enterprises** geared toward maintaining a local, close-knit scale rather than a trajectory of high corporate growth". → The family-scale neighbourhood shop **is** the regional norm, and its informal operating model is the default, not an anecdote. | Regional aggregate; it does not describe the *fiado* practice itself |
| S2 | **World Bank Blogs (LAC) — "Data story: what informal workers really value"**, 25 Aug 2026, Maloney, Beylis, Gonzalez Prieto, Zambrano | https://blogs.worldbank.org/en/latinamerica/historia-de-datos-lo-que-los-trabajadores-informales-realmente-valoran | 55 % informality "for nearly two decades"; self-employment is a **rational choice** — informal workers value flexibility, autonomy and independence, "would be willing to give up as much as half their income to hold a job with these features". → **Design constraint:** the owner will not adopt a tool that replaces his personal control; the product must *amplify* his memory. This is why variant A leaves the till out and never "automates" the relationship. | Same population; does not cover shop credit |
| S3 | **World Bank — "The Long Shadow of Informality: Challenges and Policies"** (Ohnsorge & Yu, 2021) | https://thedocs.worldbank.org/en/doc/37511318c092e6fd4ca3c60f0af0bea3-0350012021/long-shadow-of-informality-challenges-and-policies | "A large percentage of workers and firms operate in the informal economy, outside the line of sight of governments… pervasive informality is associated with significantly weaker economic outcomes — including … **less financial development**, and weaker investment and productivity." → The environment in which a shop's own notebook **is** the financial instrument: formal credit is not an option for this population. | Emerging markets broadly, not Spain/Latin America only |
| S4 | **NRF / Loss Prevention Research Council — 2023 National Retail Security Survey** (press release, 26 Sep 2023) | https://lpresearch.org/2023-nrss-release-9-26-23/ (official landing page: https://nrf.com/research/national-retail-security-survey-2023) | Industry shrink rose from 1.4 % to **1.6 % of sales** in FY2022 (≈ $112 bn). Composition of shrink: **36 % external theft, 29 % employee theft, 27 % process/control failures and errors, 6 % unknown, 1 % other**; pharmacy, grocery, department stores and mass merchants averaged **over 2 %**. → Two things: (a) shrinkage is a real and measurable leak; (b) **most of it is not theft but process and recording error** — the same "recorded vs real" gap that variant A formalises. | **US retail, not Spain/LatAm.** Use only as a structural benchmark for the *size and nature* of the gap, never as a local statistic |
| S5 | **Eurostat — "Business demography statistics"** (data from October 2026) | https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Business_demography_statistics | The EU business economy had **34 million active enterprises in 2024**; **Spain 3.6 million** (4th largest in the EU). 'Wholesale and retail trade; repair of motor vehicles' is one of **five** sectors that together comprised almost half of enterprise births and their employment. EU enterprise birth rate 10.4 % vs death rate 9.2 %; only **29 %** of active enterprises are five-year survivors. → The population of neighbourhood shops is dominated by very young, very small firms with thin margins, where a leak in cash is material; and the churn is high, so a shop dies before it ever gets organised. | EU/Spain aggregates; says nothing about credit practices |

**Explicit gap, stated honestly:** **no verifiable public source documenting the "fiado" (informal shop-to-customer credit) practice itself could be confirmed in this phase.** Several search engines rate-limited or blocked the relevant queries, and no authoritative dataset on shop-level informal credit was located. Therefore: **the fiado practice must be evidenced by the student's own interviews**, and the proposal **must not cite a statistic for it**. S1–S3 establish the *informal context* in which the practice lives; the interviews establish the practice itself. Inventing a URL or a figure here would be the single fastest way to lose the panel's trust.

---

# PART E — One-page proposal skeleton (filled with the winner: `fiado`)

> Use this as the skeleton of the one-page proposal the teaching team validates before any code is written. Section order and headings match the shape the guide asks for.

---

### PROPOSAL — `fiado` — "La libreta y la caja": credit book and real cash position for a neighbourhood shop

**1. Problem** (max ~120 words)
A neighbourhood shop keeps its informal credit — the "fiado", the money a customer takes home and pays later — in the owner's head and in a paper notebook in a drawer. The owner cannot total what they are owed, cannot tell how old each debt is, cannot stop the credit from growing, and cannot answer "how much money is really mine?" when they close the till. The consequences are concrete: bad debts that are never written off, disputes with neighbours over a 12 € debt, and a cash position that is invisible because the money already lent out is not in the drawer. The current workaround — a notebook — keeps **no ageing, no limit and no rule**, and it disappears with the owner. The shop's real liquidity, `caja + fiado pendiente`, is therefore never computed.

**2. Evidence of need** (this block makes §1 credible)
Three semi-structured interviews with shop owners (30 min each, 6-question script), plus one short survey distributed through the local merchants' association for a quantitative complement. Annex: anonymised notes, verbatim quotes, recruitment channels and the numbers found. The evidence is a **gate**: if the interviews show that credit is not a real practice for these shops, the project is re-scoped to the second-ranked variant (real margin and trapped capital) before any code is written.

**3. Users and roles**
- **Dueño (owner)** — full access: customer book, credit lines, charges and payments, ageing, automatic suspension and its override, real cash position, day close.
- **Dependiente (helper)** — records cash movements and the day close only. **Cannot see the credit book at all**: no aliases, no balances, no ageing, not even aggregate names. *Rationale: the notebook stays in the drawer — it is the owner's private commercial ledger.*
- Permission matrix attached (Dueño vs Dependiente × 9 capabilities), every row enforced **server-side** (Django groups + per-view mixins + owner-scoped querysets), and one row is explicitly a 403.

**4. Minimum scope — 5 features (each with its acceptance criterion)**
1. **Cuentas y dos roles** — signup/login, groups `dueno`/`dependiente`; the credit book is owner-only. *AC: `dependiente@tienda.test` gets 403 on `/api/v1/clientes/` and the `/api/v1/posicion/` payload contains no alias; the seeded owner sees both.*
2. **Libro de clientes y línea de crédito** — create a customer (alias, optional phone), set/change the limit; "sin límite" is an explicit state. *AC: with a €20 limit a €25 charge is refused server-side and creates no `LedgerEntry` row.*
3. **Cargos y pagos (la libreta)** — append-only entries (cargo, pago, nota de crédito) with date, amount and free-text description. *AC: the outstanding balance equals the hand-computed fixture, and a €30 payment reduces it by exactly €30 while retiring the oldest charge first.*
4. **Antigüedad y suspensión automática** — ageing buckets from charge dates; automatic suspension when the oldest unpaid charge is > 30 days or the outstanding exceeds the limit. *AC: a seeded customer with a 45-day-old unpaid charge reports `suspendido` with no human action, and a new charge for them is rejected and creates no entry.*
5. **Posición real y cierre del día** — cash movements + outstanding credit = the real position; the day close stores expected vs counted cash and the deviation. *AC: after a €30 payment the `posicion_real` drops/rises by exactly €30 in both the API and the React board; a close stores `esperado`, `contado` and `desviacion` (−4.35 € seeded) visible in the owner view.*

**5. Main data-model entities**

| Entity | Key fields | Relations |
| --- | --- | --- |
| `Shop` | `name, opening_cash, currency` | 1—N all below |
| `Customer` | `alias, phone?, credit_limit (nullable), status, suspended_at, suspended_reason` | 1—N `LedgerEntry` |
| `LedgerEntry` | `kind (cargo\|pago\|nota_credito), amount, description, occurred_at, author` — **append-only** | N—1 `Customer`, N—1 `User` |
| `CashMovement` | `kind (entrada\|salida), concept, amount, occurred_at, author` | N—1 `User` |
| `DayClose` | `date (unique), expected_cash, counted_cash, variance, closed_by` | N—1 `User` |

**6. React view(s)**
**`/app/posicion` — "La posición real".** Four composed elements, no table: (1) a **hero equation strip** — `Caja` €412.35 + `Fiado pendiente` €268.90 = **`Posición real`** €681.25, with the delta versus yesterday; (2) **"la escalera de riesgos"** — one row per debtor sorted by the age of the oldest unpaid charge, each row an **ageing ribbon** (stacked bars for `Vigente / Envejecido / Viejo / Crónico`, sized in euros) with a marker line for the credit limit, a status chip (`Activo`/`Suspendido`) and a suggested action (`Recordar`/`Suspender`/`Cobrar hoy`), clicking through to that customer's ledger; (3) **"El efecto del fiado en la caja"** — a two-series area chart of `Caja` versus `Posición real` (= `Caja + fiado pendiente`) over 30 days, where the **gap is the money already given away**; (4) a compact **"Cierre de hoy"** card (`Esperado`/`Contado`/`Desviación`). Data comes from the application's **own** API, `GET /api/v1/posicion/`, re-fetched every 20 s from the **same origin** (session cookie + `X-CSRFToken` header; no CORS, no second host).

**7. Technical approach**
- **Backend:** Django 5.2 + Django REST Framework; session authentication with CSRF; roles via Django groups and per-view permission mixins plus shop-scoped, role-gated querysets (there is no owner foreign key); **the domain rules live in an ORM-free module of pure functions** (`allocate_payments`, `bucket_of`, `evaluate_customer`, `real_position`) with unit tests; every write in a transaction; validated forms; `DEBUG=False`; secrets in environment variables only; PostgreSQL in production (Neon), SQLite locally.
- **Frontend:** React + TypeScript + Vite, built at deploy time into Django's static files and served by **WhiteNoise** — a single deployable service, one origin, no CORS.
- **Deployment:** Render free web service (managed TLS, public HTTPS) + **Neon** free Postgres (`DATABASE_URL`); `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` from env; `manage.py seed_demo` (idempotent) produces realistic shop data and **one test account per role**; a scheduled keep-alive ping handles the free tier's 15-minute sleep.
- **Out of scope:** point of sale, products, prices and receipts · barcode/scanner · customer portal and online payments · debt collection, interest and reminders · fiscal invoicing and tax · supplier purchasing · multi-branch · file uploads · e-mail/SMS · native mobile · any second infrastructure dependency.

**8. Success criteria**
- A public HTTPS URL where the seeded `dueno@tienda.test` logs in and sees the board reflect the database, and `dependiente@tienda.test` demonstrably cannot see the credit book.
- The three acceptance criteria that carry the grade are demonstrable live: a refused charge over the limit, an automatic suspension of a 45-day-old debt, and the €30 payment moving the real position by exactly €30.
- A README (install, environment variables, tests, public URL, credentials) and a repository with pinned dependency versions and no secrets in history.
- A memoria covering §3.1–3.8 with the interview annex, ER and architecture diagrams, the personal-data section (§3.6) and the real errors encountered and how they were fixed (§3.8).
- A 30-minute defense in which the board updates live after a payment, plus one small code change performed on request.

---

# PART F — Deployment spine for `fiado`

Reuses the **verified** platform facts from the first exploration (Engram #117 §3) without re-verification.

```
GitHub (public)  ──push──▶  Render Web Service (free, 0.1 CPU / 512 MB, managed TLS)
                                 │  build: pip install -r requirements.txt   (pinned)
                                 │          npm ci && npm run build           → frontend/dist
                                 │          python manage.py collectstatic   → staticfiles/
                                 │  run:   gunicorn config.wsgi:application
                                 └──▶  Neon Postgres (free, 1 GB, permanent)   [DATABASE_URL env]

frontend/dist → Django static/ → WhiteNoise → SAME ORIGIN
React page at /app/posicion → fetches /api/v1/posicion/ → same origin, no CORS
```

**Verified facts that shape this spine (reused, not re-checked):**
- Render's free web service **sleeps after 15 min** of inactivity and takes ~1 min to wake with a "loading" page ⇒ a keep-alive ping to `/health/` every ~10 min from GitHub Actions (free for public repos) **plus a manual wake-up before the defense**.
- Render's free service has an **ephemeral filesystem** ⇒ SQLite data dies on every spin-down/redeploy ⇒ **Postgres is mandatory in production from day one** (Neon), SQLite only for local development.
- **Render's own free Postgres expires 30 days after creation** (14-day grace, then data deleted) ⇒ **rejected**. Neon free is permanent and requires no card ⇒ chosen.
- Django 5.2.8 supports **Python 3.14** and requires PostgreSQL 14+ ⇒ Neon satisfies it. PBKDF2 iterations raised to 1 000 000.

**`seed_demo` must produce realistic shop data and one test account per role.** Specification:

| What | Content |
| --- | --- |
| Accounts | `dueno@tienda.test` (Dueño) and `dependiente@tienda.test` (Dependiente) — exactly one per role; password documented in the README |
| `Shop` | "Despensa La Plaza" — opening cash **€150.00**, currency EUR |
| `Customer` | 9 customers with plausible **aliases, not real names** ("Marta (Pº 2)", "Hassan", "Carmen — panadería", "Familia Ruiz", "Javi del taller", "Lucía", "Sr. Ramos", "Nuria", "Kiosco 24h"), mixed limits (one `null` = sin límite, one €50, one €20, others €30–€80) and mixed states (one auto-suspended by the rule) |
| `LedgerEntry` | ~65 entries spread over the last 120 days: cargos with realistic free-text descriptions ("2 L de leche + pan", "caja de refrescos", "gasolina 5 L"), pagos on ~70 % of the customers, one nota de crédito, **one customer with a 45-day-old unpaid cargo** (auto-suspends), one payment exceeding the debt (residual "a favor del cliente"), one customer over the limit |
| `CashMovement` | ~45 movements: entradas (cobro del proveedor, cambio de un billete) and salidas (compra de newspapers, gasolina,Pack de agua) |
| `DayClose` | 6 past closes with `esperado`/`contado`/`desviacion`, one of them −€4.35 |
| Determinism | All dates computed **relative to the run date** (today − N days), never hard-coded calendar dates, so the board always looks "current". Re-running the command must not duplicate entries: wrap it in `transaction.atomic()`, delete the demo dataset (flagged `is_demo=True`) and recreate it |

**Landmines to write into memoria §3.8 (each one is a future entry):** (1) `CSRF_TRUSTED_ORIGINS` + `ALLOWED_HOSTS` must include the Render URL or every POST 403s in production; (2) ephemeral FS ⇒ Postgres mandatory; (3) 15-minute sleep ⇒ keep-alive + manual wake-up; (4) a `collectstatic` misconfiguration yields a **blank page, not an error** ⇒ smoke check after each deploy; (5) `seed_demo` must be idempotent and re-run on every deploy; (6) **new in this variant:** the `dependiente` role must be checked against *every* JSON path of `/api/v1/posicion/` — a leak in one nested field is a data-protection failure, not a cosmetic bug.

---

# PART G — Risks and the cheapest de-risking experiment for each

| # | Risk | Why it hurts | Cheapest de-risking experiment | Cost |
| --- | --- | --- | --- | --- |
| R1 | **The interviews say credit is not a real practice** for the shops reachable | Variant A collapses and the whole proposal is void | Recruit 3 owners **before** writing the proposal (Part D); the form fallback in D.1.5 gives ≥15 responses in days | ~6 h |
| R2 | **Personal-data exposure.** Storing neighbours' debts with aliases | A panel question on GDPR/privacy that an unprepared student cannot answer | Decide the data-minimisation rules **now** (alias, optional phone, no DNI, no photos), write the `dependiente` 403 rule into the permission matrix, and put the personal-data section of memoria §3.6 in place before the first model | ~1 h |
| R3 | **The owner refuses to write down what he keeps in his head** (adoption risk) | The ledger stays empty and the demo becomes fake | Ask question 6 in every interview ("¿usarías una herramienta que te dijera a quién recordarle el pago?"); if the answer is lukewarm, the MVP must reduce data entry to a **single-tap charge record** | included in R1 |
| R4 | **The derived-ledger logic is subtly wrong** | The hero number, the ladder and the suspensions are all wrong at once — a fatal backend failure (30 % of the grade) | Write the four pure functions + a hand-checked fixture **before any model or view** (B.1); green ⇒ the core is proven | ~3 h |
| R5 | **The React view is the weakest link** (15 % of the grade) and the classic failure is "the board fetches nothing at the deployed URL" | A strong backend still scores "aceptable" | Build the vertical slice in the **first 48 h**: one DRF endpoint returning the position payload, one React component rendering the ribbon ladder, the bundle served through WhiteNoise, and the session+CSRF fetch working **at the deployed URL**, not on localhost | ~3 h |
| R6 | **The free tier sleeps at the wrong moment** | A "loading" page during the defense | Deploy a hello-world Django to Render + Neon in **day 1** (~2 h), set the env vars, add `/health/`, measure the cold start and the ping cadence; decide then — not in week 9 — whether the final month moves to Railway Hobby ($5/mo, same URL) | ~2 h |
| R7 | **Scope creep past 5 features** | The guide freezes the scope; extra features cost the grade | The five features above are the ceiling; the till, products and prices are explicitly **future work** in the memoria | 0 |

**Watch list.** *Do not let the project become a POS* — the moment a `Product` table and a `Sale` table appear, the distinctiveness argument dies and the project becomes the most common archetype in the cohort. *The helper role must be a real 403, not a hidden button* — the panel will ask. *The automatic suspension must be explained as the owner's own rule, formalised* — "I already know I shouldn't lend to them, I just forget" is the sentence that makes it land. *Seed data must look like a real shop* (Spanish aliases, real descriptions, realistic amounts), because the panel reads the demo as a screenshot of the product.

---

# PART H — What happens next

1. **The student approves a variant** (or sends this back with a different priority). Until then, **no change directory is created**.
2. If `fiado` is approved → create `openspec/changes/tienda-barrio/` and reference this file from `openspec/changes/tienda-barrio/exploration.md`.
3. **Run the week-1 evidence plan** (Part D) — the three interviews — because the proposal cannot be submitted without it and because it can still overturn the choice.
4. `sdd-propose` drafts the one-page proposal from Part E, with the interview annex attached.
5. Only after the teaching team validates the proposal does implementation begin (and the React ↔ API vertical slice goes in first).

**Status of this artifact:** exploration complete. **No proposal, spec, design, tasks or code has been written.** The change directory `openspec/changes/tienda-barrio/` does **not** exist yet, by design.

