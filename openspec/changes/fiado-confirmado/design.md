# Design: `fiado confirmado` — the charge that exists only after the client confirms it

> **Language contract.** Prose in English; every domain identifier, entity, field, API field and diagram label stays in the project's Spanish vocabulary (`fiado`, `cargo`, `pago`, `propuesta`, `linea`, `desglose`, `caja`, `dependiente`, `dueño`, `libreta`, `posición real`, `confirmación`, `existencias_registradas`, `codigo`, `posicion_real`, `confirmado_en`, `precio_unitario`, `facilitado_por`, `credit_limit`, `antiguedad_max_dias`, `suspended_reason`, `vigente`/`envejecido`/`viejo`/`cronico`, `pendiente`/`confirmado`/`cancelado`, `techo_no_conteo`).

## 1. Technical Approach

One Django 5.2 + DRF service on Render, one Neon PostgreSQL, one Vite/React bundle served by WhiteNoise from the same origin: no second host, no CORS, no worker, no Redis. The `cargo` — an obligation with a counterparty who has seen its `desglose` and said yes — is the unit of record; the catalogue is a vocabulary that prices it; the shop's screen is where the confirmation is given.

This supersedes the abandoned `tienda-barrio` design (its folder stays untouched) and reuses its spine: append-only ledger, FIFO, ageing, `credit_limit`, automatic suspension, the `dependiente` 403 boundary, session+CSRF staff surface, same-origin mount, additive `posicion_real`, `Decimal`-on-the-wire, the 422 contract, the `seed_demo` plan. It adds a catalogue, `CargoLinea`, a client credential, a proposal/confirmation state machine, a third React surface and a movement-derived stock ceiling.

| # | Idea | |
|---|---|---|
| 1 | **Nothing derived is stored.** | Balances, buckets, `antiguedad_max_dias`, the suspension status and its `suspended_reason`, the effective confirmation state and `existencias_registradas` are computed on every read. The one persisted exception is the `suspended_override_at` act: an override is an *event*, not a derived value. |
| 2 | **Two scopes, two mechanisms, never mixed.** | Staff scope = the session (`session["shop_id"]` plus a Django group). Client scope = a per-request `codigo` resolved to one `Customer`. No client `User`, group or session, and no upgrade path either way. |
| 3 | **A `cargo` is debt from the instant the client confirms it; the proposal before it is nothing.** | The `FiadoPropuesto` is a prepared figure, not an obligation: while it is `pendiente` it moves no balance, ages nothing and triggers nothing. The confirmation is the **gate**, not the attestation — the `cargo` and its `CargoLinea` rows are written in the same transaction that records the `Confirmacion`, so a charge without a confirmation cannot exist. A client who never comes to the shop leaves **no debt at all**, and the owner cancels the proposal. |
| 4 | **The client never writes to the book.** | The `codigo` grants **read** over the client's own statement and the right to **propose** a payment. It grants no write: no `LedgerEntry`, no `CargoLinea`, no `Confirmacion`, no `FiadoPropuesto`. The owner records every payment after validating the client's proposal. Less write surface is less attack surface (§8, §12). |
| 5 | **The `desglose` is mandatory.** | A `cargo` carries one or more `CargoLinea` rows. A proposal with no lines cannot be confirmed. The client confirms a figure they can see broken down; a figure they cannot see broken down is not a figure they can confirm. |

### 1.1 The lifecycle

```
dueño / dependiente                Tienda                        Libro
      | prepare FiadoPropuesto                              |   -- no row, no debt
      | (customer + lineas + total)                         |
      |----------------------------->|                      |
      |                              | GET .../pantalla/   |
      |                              |-------------------->|
      |                              |  lineas[] + total   |
      |<-----------------------------|                     |
      |                              | the client confirms (or declines)
      | record the confirmation      |                     |
      |---------------------------------------------------->|
      |                              |   atomic: FiadoPropuesto(confirmado)
      |                              |        + LedgerEntry(cargo) + CargoLinea[]
      |                              |        + Confirmacion(confirmado)   -- NOW it is debt
      | cancel (the client declined) |                     |
      |---------------------------------------------------->|
      |                              |   atomic: FiadoPropuesto(cancelado)
      |                              |                       -- no cargo, no debt
```

## 2. The Decisions

| # | Decision | Choice | Consequence |
|---|---|---|---|
| D1 | `Customer.status` | **Derived on read**; only `suspended_override_at`/`_by` persist (an act). | A derived state cannot desynchronise. A stored `status` drifts on the next `pago`. |
| D2 | Credential **storage** | Hashed one-way (PBKDF2-SHA256, per-credential salt) + a 6-symbol `prefix`; the plaintext lives only in the issuing response. | The DB is not a credential store. The slip prints **once**; a lost slip is **rotated**. |
| D3 | Credential **transport** | The `X-Codigo` header, every client request, memory only — never a query parameter (history, `Referer`, logs, cache keys), never a cookie (a cookie *is* a session). | **CSRF without a session:** a non-simple header a cross-origin form cannot set, and no CORS policy grants it. **Its scope has dropped:** read + propose, no write (§7). |
| D4 | Entropy and throttle | 20 symbols of a 32-symbol unambiguous alphabet = **100 bits**; a `CodigoIntento` ledger throttles at 10/IP, 20/prefix and 500/shop per 15 min, always with the byte-identical `codigo_invalido` payload. | Entropy a spoken code cannot carry; no new dependency; the throttle is never an oracle for which credentials exist. |
| D5 | **Stock movement model** | A separate `StockMovement` table; `existencias_registradas = Σ entradas − Σ salidas`; `CargoLinea` quantities are **not** stock movements. | The ceiling **drifts downward**, so the **owner bears the drift**. It carries a machine-readable qualifier; `stock` is a banned field name; no rule may depend on it and no endpoint may refuse a `cargo` for lack of stock. |
| D6 | The `dependiente`'s leak boundary | The `dependiente` sees **exactly one proposal, in full**: the customer, the `lineas` and its `total`. No list, balance, ageing, `credit_limit`, `codigo` or other proposal. | One bounded erosion of the 403 boundary: «the notebook stays in the drawer, except for the one page the client is looking at right now». |
| D7 | One charge per confirmed proposal | **A proposal yields at most one `cargo`, and that charge comes only from that proposal.** The confirmation copies the `lineas` into `CargoLinea` rows in the same transaction; a proposal may be confirmed **once**. | The amount shown and the amount recorded cannot drift apart. |
| D8 | `precio` deviation rule | The catalogue price is a default the server fills in; an explicit per-line `precio_unitario` wins; `total` is always server-computed. | The common case types nothing, the uncommon case edits one field, and a later catalogue change rewrites no stored line. |
| D9 | The client's write scope | **The `codigo` grants read + propose.** No `LedgerEntry`, `CargoLinea`, `Confirmacion` or `FiadoPropuesto` is written by the client. | The invariant «a client never writes to the ledger directly» survives intact. The shop's screen is the only place a confirmation is given. |
| D10 | The payment proof *(planned extension)* | **Not implemented.** The client may later attach a `comprobante` to a `PagoPropuesto`. | A bank receipt is personal data and binary storage is a whole capability, not a field. A planned extension with its own cut line (§12.2). |
| D11 | Client sees own `credit_limit`? | **No** — the field is absent from the client schema entirely. | CAC-10 is structural: the value cannot appear because the name cannot appear. |

### 2.1 The decisions that are gone, and why

| Gone | Was | Why it is gone |
|---|---|---|
| The double-confirmation / double-reconciliation machinery | Partial unique indexes per confirmation state plus one per reconciliation. | There is one confirmation state and no reconciliation concept. The uniqueness that survives is one confirmation per **charge** (§3.2, rule 6) and one live proposal per **customer** (§3's partial unique index). A proposal is confirmed once by the one-way transition of §3.2, rule 7. |
| The 7-day escalation flag | `revisar` derived on read from `sin_confirmar` and `age > 7 d`. | A charge without a confirmation cannot exist, so there is nothing to escalate. |
| The dispute machinery | `en_disputa`, `importe_reclamado`, the `nota de crédito`, the arbitration. | The disagreement is prevented instead of resolved: the client sees the `desglose` before the charge exists. |
| `escalado_sin_confirmar`, `transicion_permitida` | Domain functions in `domain/confirmation.py`. | No transition has an object any more: the proposal has exactly two one-way transitions (§6). |

## 3. Data Model

All tables live in `backend/tienda/models.py`. Money `Decimal(12,2)`, quantities `Decimal(10,3)`, instants in UTC, converted to shop-local days in the service layer.

| Entity | Fields · relations |
|---|---|
| `Shop` | `name` (unique), `opening_cash` (≥ 0), `currency`, `is_demo`, `usuarios` M2M → `User` |
| `User` | Django `auth.User`, **unmodified**; groups `dueno`, `dependiente` |
| `Customer` | → `Shop` CASCADE, `User`? PROTECT (`created_by_id?`, the staff member who registered the customer; NULL when the customer predates the register), `User`? PROTECT (`suspended_override_by_id?`, the user who lifted the suspension): `alias`, `phone?`, `credit_limit?` (NULL = «sin límite»), `suspended_override_at?`; UNIQUE `(shop_id, alias)` |
| `FiadoPropuesto` | → `Shop` CASCADE, `Customer` CASCADE, `User` PROTECT (`user`, the preparer), `User`? PROTECT (`facilitado_por_id?`, the helper who presented it): `estado` ∈ {`pendiente`,`confirmado`,`cancelado`}, `total` (≥ 0), `created_at`, `confirmed_at?`, `canceled_at?` |
| `PropuestaLinea` | → `FiadoPropuesto` CASCADE, `Producto` PROTECT: `producto`, `cantidad` (> 0), `precio_unitario` (≥ 0), `total` = `round(cantidad × precio_unitario, 2)` |
| `LedgerEntry` | → `Shop` CASCADE, `Customer` PROTECT, `User` PROTECT (`user_id`, the author who recorded the entry — PA-10 requires an author on every entry): `kind` ∈ {`cargo`,`pago`}, `amount` (> 0), `occurred_at` (≤ `created_at`), `created_at`; **no `cargo_id`** |
| `CargoLinea` | → `LedgerEntry` CASCADE, `Producto` PROTECT: `producto`, `cantidad` (> 0), `precio_unitario` (≥ 0), `total` = `round(cantidad × precio_unitario, 2)` |
| `CashMovement` | → `Shop` CASCADE, `User` PROTECT (`user_id`, the author who recorded it — CP-01 requires a recorded author): `kind` ∈ {`entrada`,`salida`}, `amount` (> 0), `concept`, `occurred_at` — **server-stamped** |
| `StockMovement` \* | → `Producto` PROTECT: `kind` ∈ {`entrada`,`salida`}, `cantidad` (> 0), `concept`, `occurred_at` — **server-stamped** |
| `DayClose` | → `Shop` CASCADE, `User` PROTECT (`user_id`, the user who closed the day): `date`, `esperado` (≥ 0) — **the server-computed `caja` at close time**, `contado` (≥ 0), `desviacion` = `esperado − contado`; UNIQUE `(shop_id, date)` |
| `Producto` | → `Shop` CASCADE: `nombre`, `precio` (≥ 0), `unidad`, `activo`; UNIQUE `(shop_id, nombre)` |
| `Confirmacion` | → `LedgerEntry` PROTECT (`cargo`), `User`? PROTECT (`facilitado_por_id?`, the helper who presented the proposal; NULL when the owner recorded it directly): `estado` ∈ {`confirmado`} — **one state only**, `confirmado_en` (NOT NULL), `origen` ∈ {`tienda`,`facilitado`} (NOT NULL) |
| `PagoPropuesto` | → `Shop` CASCADE, `Customer` CASCADE, `User`? PROTECT (`resolved_by_id?`, the owner who validated or rejected it): `importe` (> 0), `referencia` (text), `estado` ∈ {`pendiente`,`validado`,`rechazado`}, `created_at`, `resolved_at?`; it writes **nothing** to the book and **names no `cargo`** — the payment imputes FIFO against the customer's open charges |
| `ImputacionPago` | → `LedgerEntry` PROTECT (`pago`, the payment that brought the money), `LedgerEntry` PROTECT (`cargo`, the charge it retires): `importe` (> 0). **One row per (payment, charge) pair that the payment touches.** A payment that retires three charges writes three rows |
| `CustomerCodigo` | → `Customer` CASCADE, `User` PROTECT (`issued_by_id`, the user who issued the credential), `User`? PROTECT (`revoked_by_id?`, the user who revoked it): `prefix` (6, non-secret), `codigo_hash`, `issued_at`, `revoked_at?` |
| `CodigoIntento` | → `Shop` CASCADE: `source_ip`, `presented_hash`, `at`; append-only |

\* conditional (Regla 6). `StockMovement` → `Producto` is a PROTECT foreign key, so Regla 6 can only be cut together with Regla 5.

**Per-row constraints.** `amount > 0` and `kind ∈ {cargo,pago}` on `LedgerEntry` · `cantidad > 0`, `precio_unitario ≥ 0`, `total = round(cantidad × precio_unitario, 2)` on `CargoLinea` and `PropuestaLinea` · `estado ∈ {confirmado}` and `confirmado_en NOT NULL` on `Confirmacion` · `origen='facilitado' ⇔ facilitado_por_id NOT NULL` · `credit_limit ≥ 0` or NULL on `Customer` · CHECK `confirmado ⇒ confirmed_at NOT NULL` and `cancelado ⇒ canceled_at NOT NULL` on `FiadoPropuesto` · CHECK `validado ⇒ resolved_at NOT NULL ∧ resolved_by_id NOT NULL` and `rechazado ⇒ resolved_at NOT NULL ∧ resolved_by_id NOT NULL` on `PagoPropuesto`.

**Unique and partial-unique constraints.** **partial UNIQUE `(customer_id) WHERE estado='pendiente'`** on `FiadoPropuesto` — at most one live proposal per customer · **partial UNIQUE `(cargo_id) WHERE estado='confirmado'`** on `Confirmacion` — at most one confirmation per charge · **partial UNIQUE `(customer_id) WHERE revoked_at IS NULL`** on `CustomerCodigo` · UNIQUE `(shop_id, alias)` on `Customer`, `(shop_id, nombre)` on `Producto`, `(shop_id, date)` on `DayClose`, `(shop_id, prefix)` on `CustomerCodigo`.

**Sixteen entities** (twelve before, plus `FiadoPropuesto`, `PropuestaLinea`, `PagoPropuesto` and `ImputacionPago`). `LEDGER_ENTRY_KINDS` has **two** values: `cargo`, `pago`. The five constraints that are gone - `uniq_confirmacion_one_disputa_per_cargo`, `uniq_ledgerentry_one_reconciliation_per_cargo`, `chk_ledgerentry_cargo_only_on_credit_note`, `chk_confirmacion_state_fields`, `chk_confirmacion_importe_non_negative` - and the two partial indexes that went with them. `LedgerEntry.cargo_id` and `Confirmacion.importe_reclamado` are gone.

### 3.1 Immutability and what is NOT stored

`LedgerEntry`, `CargoLinea`, `Confirmacion`, `PropuestaLinea` and `ImputacionPago` are append-only: `update()`/`delete()` raise `LedgerImmutableError` and no `PUT`/`PATCH`/`DELETE` route exists for them. There are exactly **two** mutable rows in the credit book. Each mutates only its own lifecycle — its state, the instant that state changed, and the act that caused it — and never anything else:

- `FiadoPropuesto` — `estado`, `confirmed_at`, `canceled_at` and `facilitado_por_id`. It moves from `pendiente` to exactly one of `confirmado` or `cancelado`, never back. `facilitado_por_id` is written **at INSERT**, when the proposal is prepared, by the same server-side inference as rule 7b: the preparing user belongs to the `dependiente` group → it is that user; otherwise it stays NULL. It is never written afterwards.
- `PagoPropuesto` — `estado`, `resolved_at` and `resolved_by_id`. It moves from `pendiente` to exactly one of `validado` or `rechazado`, never back. The owner's validation is an **act**, recorded on the row, exactly like the suspension override and the credential revocation.

The other mutable columns are `Customer.alias`/`phone`/`credit_limit` and `Customer.created_by_id` (the owner's own records and policy, through `PATCH /api/v1/clientes/{id}/` and the create route), `Customer.suspended_override_at`/`_by` and `CustomerCodigo.revoked_at`/`_by` — the last two record an **act**, never a derived value. Both `*_by_id` columns are written by the server from the acting session, never from a request body: the suspension override is stamped when the owner lifts it (`POST /api/v1/clientes/{id}/suspension/anular/`), and the credential revocation when the owner revokes it (`POST /api/v1/clientes/{id}/codigo/` with a rotation).

A `PagoPropuesto` that reaches `validado` is a record of the owner's decision, not a ledger row: the `pago` itself is a separate `LedgerEntry` appended by the owner, so the credit book stays append-only even though the request that preceded it is not.

**`ImputacionPago` is where the repartition lives.** A `pago` of 20,00 € that retires a cargo of 8,00 €, one of 7,00 € and 5,00 € of a third is **one** `LedgerEntry` and **three** `ImputacionPago` rows. The row for each charge is what says how much of that charge the payment settled, and it is the reason the owner can read "8/8 · 7/7 · 5/15" on the client's charges. The alternatives were both rejected: a mutable `pagado` column on the cargo would break the append-only guarantee of the book and would be a stored derived value — exactly what landmine 12 forbids — and recomputing the repartition on read would make the numbers move if the FIFO rule ever changed, which a credit book cannot do. The repartition is therefore **recorded**, and the remaining balance of a charge is derived on read as `cargo.amount − Σ ImputacionPago.importe` for that charge.

The grain is the **charge**, not the line. A charge of 15,00 € made of three `CargoLinea` rows is one debt of 15,00 €, and a payment that settles 5,00 € of it writes one `ImputacionPago` of 5,00 € against the charge. The design does not define how a partial payment splits across the lines of a single charge, and it does not need to: the `desglose` says what was bought, the debt says what is owed, and the repayment says what was paid against the debt.

Never stored: `saldo`/balance/`outstanding` · `antiguedad_max_dias` · ageing buckets · `status`/`suspended_reason`/`suspended_at` · any confirmation state on a `cargo` or `Customer` · `caja`/`posicion_real`/`fiado_pendiente`/`serie_caja` · `existencias_registradas` and any field named `stock` · `precio_origen` · a `reconciled` flag · a `revisar` flag · an `importe_reclamado` · a `nota de crédito` · a client `User`, group, session or plaintext `codigo` · a `venta`/`Sale` table, till, drawer balance, receipt, barcode, tender, supplier, purchase order, cost or reorder model · a `comprobante` attachment · **a customer credit** — a balance in the client's favour, a `credit_a_favor` state or any stored surplus. Rule 19 makes it structurally impossible rather than merely discouraged: a `pago` that would create one is refused (ADR-26).

### 3.2 Transactional cross-row checks

Server-side, inside `transaction.atomic()`; a `CHECK` sees one row, never an aggregate. Each raises `DomainValidationError` → 422, rolls back, and creates no row and no line.

**The cardinality of the `desglose` is enforced by the write path, not by a `CHECK`.** A `CHECK` cannot express "at least one row per charge" — that is a cardinality across rows, and PostgreSQL has no declarative constraint for it. Rule 3 and rule 5 therefore carry it, and the write transaction is the only path that creates a charge: the `LedgerEntry(cargo)` and its `CargoLinea` rows are written together, in one transaction, and the transaction refuses to commit without at least one line. A direct ORM write that bypassed the service would break the invariant — which is exactly why ADR-19 gives the ledger a single entry point and rule 5 states that a `cargo` written without a `Confirmacion` "is not reachable through the API".

| # | Refused when | `codigo_error` |
|---|---|---|
| 1 | The derived state is `suspendido` → a new `cargo` is refused | `limite_superado` / `antiguedad_superada` |
| 2 | The derived outstanding exceeds `credit_limit` | `limite_superado` |
| 3 | A `cargo` has `amount ≠ Σ CargoLinea.total`. **The itemisation is mandatory**: a proposal with no lines is refused with the same code — a figure the client cannot see broken down is not a figure the client confirmed | `lineas_descuadradas` |
| 4 | The request carries `occurred_at` | `campo_no_admitido` |
| 5 | A `cargo` is written without a `Confirmacion` in the same transaction. Not reachable through the API; it exists so no other write path can create a charge without a confirmation | — |
| 6 | A `Confirmacion` targets a charge that already carries one | `cargo_ya_confirmado` |
| 7 | A `FiadoPropuesto` is confirmed or cancelled twice. The first is the code the API contract names (CC-01); the second guards the one-way transition | `propuesta_ya_confirmada` / `propuesta_ya_cancelada` |
| 7b | **The proposal and the confirmation record who acted.** `origen` is **inferred by the server** from the acting session, never taken from the request body: the acting user belongs to the `dependiente` group → `origen='facilitado'` and `facilitado_por_id` is that user; otherwise `origen='tienda'` and `facilitado_por_id` stays NULL. The same inference writes `FiadoPropuesto.facilitado_por_id` when the proposal is prepared. A `facilitado_por` user outside the shop, or outside the `dependiente` group, is refused | `facilitador_invalido` |
| 8 | A `FiadoPropuesto` is confirmed while its customer is `suspendido` — **no charge exists** afterwards (PA-07) | `limite_superado` / `antiguedad_superada` |
| 9–11 | A `DayClose` repeats `(shop_id, date)` · a `CustomerCodigo` duplicates `(shop_id, prefix)` or gives a customer a second active credential · a line or movement names a `Producto` outside the shop | `cierre_duplicado` · `codigo_duplicado` · `producto_ajeno` |
| 12–14 | A `CashMovement` would be stamped in the future · a `DayClose` would store an `esperado` that is not the derived `caja` at close time · a close request carries `esperado` or `desviacion` (the previous rule rejects a wrong value; this one rejects the **presence** of the field) | — · — · `campo_no_admitido` |
| 15–18 | A ledger entry declares `amount ≤ 0` · a ledger entry declares a `kind` outside {`cargo`, `pago`} · a `PagoPropuesto` declares an amount ≤ 0 · a `PagoPropuesto` is validated or rejected twice | `importe_no_positivo` · `tipo_desconocido` · `importe_no_positivo` · `pago_ya_resuelto` |
| 19 | **A `pago` exceeds the outstanding it retires.** The shop returns the excess as change; it never enters the book, so no credit can exist and the outstanding can never be negative. The owner records only the amount that settles the debt — a client who hands over 35,00 € against a 20,00 € debt produces a `pago` of 20,00 €. **The outstanding is the customer's total**, not one charge's: the payment imputes FIFO against the customer's open charges, so the bound is the sum of what the customer owes | `pago_excede_deuda` |
| 20 | **An `ImputacionPago` names something that is not a charge.** The `cargo` side of the pair must be a `LedgerEntry` with `kind='cargo'`; the `pago` side must have `kind='pago'`. A pair that names a `pago` on the charge side, or a `cargo` on the payment side, is refused | `tipo_desconocido` |
| 21 | **The imputations of a payment do not add up to the payment.** The sum of `ImputacionPago.importe` over the rows of one `pago` MUST equal that `pago`'s `amount`, and no charge may be over-imputed: the sum of the imputations of one charge MUST NOT exceed that charge's `amount`. Both are checked in the same transaction that writes the rows | `lineas_descuadradas` |

**Rule 19 is what makes the absence of a credit structural.** The alternative — allowing a `pago` larger than the debt and holding the difference as a balance in the customer's favour — was rejected: a shop returns change, it does not run a credit ledger, and a stored credit is a derived value that would need its own ageing, its own limit and its own reconciliation. Refusing the overpayment at the transaction keeps three properties that would otherwise be lost: the outstanding is never negative, `allocate_payments` never leaves a residual, and the ageing buckets always sum exactly to the outstanding (PA-01, PA-02, PA-03). The excess never becomes a row; it leaves the counter as change.

**Rules 20 and 21 are what keep the repartition honest.** A repartition is only worth recording if it is arithmetically closed: every cent of the payment is placed in exactly one charge, and no charge is credited with more than it owes. Rule 21 is the transaction-level twin of the two `UNIQUE`/`CHECK` constraints that the `ImputacionPago` table carries — `UNIQUE (pago_id, cargo_id)` so one payment cannot touch the same charge twice, and `CHECK (importe > 0)` so a row always places something. The sums cannot be a `CHECK`, because a `CHECK` sees one row and never an aggregate; they are the aggregate checks of §3.2 and they run inside the same `transaction.atomic()` that writes the `LedgerEntry(pago)` and its imputations.

**Per-row checks and their codes.** The per-row invariants are DB `CHECK` constraints, but a `CHECK` raises an `IntegrityError`, not a `codigo_error`. Each one therefore has a service-level twin that validates the same condition **before** the write: `amount > 0` → `importe_no_positivo` · `kind ∈ {cargo, pago}` → `tipo_desconocido` · `cantidad > 0` and `precio_unitario ≥ 0` → `importe_no_positivo`. The `CHECK` is the backstop under a race; the service check is what the client sees.

## 4. Architecture Decision Records

Context → choice → trade-off → consequence. ADR-1…15 keep the shape of the abandoned `tienda-barrio` design; ADR-16…25 are new to this change.

| # | Context | Choice | Trade-off | Consequence |
|---|---|---|---|---|
| ADR-1 | One service, one origin | React in `STATIC_ROOT`, WhiteNoise | One build step | Three routes, no CORS |
| ADR-2 | Balances must not drift | Every balance is computed from the ledger | Every read pays | All figures are read-time derivations |
| ADR-3 | Testable without a database | `domain/` imports no Django | Plain-value signatures | Unit tests need no DB; an AST test enforces it |
| ADR-4 | Two audiences, one deployable | Session + CSRF for staff, **no** session for the client | Two auth mechanisms | The client is credential-per-request |
| ADR-5 | The permission model | Two groups + `RoleRequired`; the client is **not** a group | The matrix is not one table | The 2×8 shop matrix holds |
| ADR-6 | A leak is a data-protection failure | Serializer allowlist; `fields` is exhaustive | A schema class per audience | The client schema carries no staff-only field: no `caja`, `posicion_real`, `credit_limit`, ageing, `codigo` or `prefix`, and no other customer's data |
| ADR-7 | Fair debt retirement | FIFO by `(occurred_at, id)` | The oldest ages first | The oldest reaches `cronico` before a newer one leaves `vigente` |
| ADR-8 | Deadlines without infrastructure | No Celery, no Redis, no cron; derive on read | No persisted "due" state | The buckets and the suspension are read-time; there is no escalation flag to derive |
| ADR-9 | The business equation | `posicion_real = caja + Σ outstanding` | A `pago` moves money, not position | `caja` and `fiado_pendiente` move together |
| ADR-10 | Live figures | Poll `/api/v1/posicion/` every 20 s | Load doubles | No WebSockets; the poll is the keep-alive |
| ADR-11 | Secrets | Demo accounts public; real secrets env-only; the `codigo` is a third class | One more lifecycle | No real secret in the repository |
| ADR-12 | The chart | Hand-rolled SVG, fixed `viewBox` | No interactivity | Small bundle, explainable line by line |
| ADR-13 | Money and quantities | `Decimal`; JSON strings on the wire | The UI parses strings | No float drift |
| ADR-14 | Where a rule lives | Per-row `CHECK`/`UNIQUE`; aggregates in the transaction | Two places to look | The DB backstops rows; the server owns the aggregates |
| ADR-15 | One source of scope — now two | Staff = session; client = the `codigo` | The old rule no longer holds | No client session, no upgrade path |
| ADR-16 | **The `codigo` and its new scope** | Hashed at rest, `X-Codigo` in transit, throttled in PostgreSQL. It grants **read of the statement + propose a payment** and **no write** | The slip prints once; the client cannot confirm from the portal | Rotation is the re-print path; refusals indistinguishable. The invariant «a client never writes to the ledger directly» survives intact |
| ADR-17 | The client is a third actor | A credential scoped to one `Customer` | Every auth check needs a split | The 403 boundary survives |
| ADR-18 | **The confirmation state** | **One state only: `confirmado`.** The effective state of a `cargo` is computed on read from its `Confirmacion` rows; a charge with no row reads `sin_confirmar`, unreachable in normal operation. | No `en_disputa`, no second state, no transition table | The state machine of §6 collapses to one transition. The effective state is a read-time projection, never a write guard — the write guards use row presence |
| ADR-19 | **The charge exists only at the confirmation** | The `LedgerEntry(cargo)`, its `CargoLinea` rows and the `Confirmacion(confirmado)` are written **in one transaction**, and the `FiadoPropuesto` becomes `confirmado` in the same transaction. A prepared proposal writes nothing. | The owner cannot record a `cargo` directly any more; the ledger has one entry point | The disagreement the old design arbitrated is prevented instead of resolved: the client has already seen the `desglose`. A proposal is not debt at all |
| ADR-20 | **One charge per confirmed proposal** | A `FiadoPropuesto` carries its `lineas`; the confirmation copies them into `CargoLinea` rows. A proposal may be confirmed **once**: the one-way transition of §3.2, rule 7 — the transactional pre-check on the stored proposal `estado` returns `propuesta_ya_confirmada`, and the race test of §15.2 proves the transaction holds under concurrency. The charge therefore comes from that one proposal: the `CargoLinea` rows are copied from the proposal's own `lineas`, and the `Confirmacion` points at that `cargo`. A reverse link from the charge to its proposal is deliberately **not** stored — it would be a derived value, and nothing reads it. | The two write paths are coupled: the confirmation endpoint must create the lines too | The amount shown and the amount recorded cannot drift. The old double-confirmation machinery collapses to one index and one code |
| ADR-21 | Stock without a count | A separate `StockMovement` table | A second movement ledger | The ceiling drifts down and no rule depends on it |
| ADR-22 | The catalogue's job | A vocabulary with a default price; `precio_unitario` is a snapshot | A snapshot that can differ forever | Later price changes rewrite nothing |
| ADR-23 | **Adoption friction** | The confirmation **gates** the charge. A `fiado` that is not confirmed is not recorded; the owner cancels the proposal instead. | The shop must show the client the screen, and an unconfirmed proposal leaves no debt | The product delivers *confirmed* debt, not merely itemised debt. There is no fallback to plain `fiado` — that is the `fiado desglosado` cut |
| ADR-24 | The client's view of the limit | `credit_limit` absent from the client schema | The client cannot self-diagnose | CAC-10 is structural |
| ADR-25 | **The payment proof** | The `comprobante` is a **planned extension, not implemented**. A `PagoPropuesto` carries an `importe` and a text `referencia`; no file, no upload, no attachment model. | The client cannot show the owner a receipt image | Binary storage on an ephemeral server is a whole capability, and a bank receipt is personal data. When it lands it will need file storage, multipart upload, type and size validation, an attachment model and a retention rule |
| ADR-26 | **No customer credit** | **A `pago` never exceeds the debt it retires.** The shop returns the excess as change; it never enters the book. Rule 19 refuses the overpayment at the transaction | The owner must record the amount that settles the debt, not the cash handed over | The outstanding is never negative, `allocate_payments` never leaves a residual, the ageing buckets always sum exactly to the outstanding, and there is no credit to age, limit, reconcile or explain. A stored credit would have been a derived value with its own lifecycle — the thing §3.1 forbids |
| ADR-27 | **Where the repartition of a payment is recorded** | **A separate `ImputacionPago` table, one row per (payment, charge) pair.** The grain is the **charge**. | One more table, and a payment that retires three charges writes three rows | The book stays append-only: `LedgerEntry(pago)` plus the rows that say what it settled. The owner reads "8/8 · 7/7 · 5/15" off the client's charges. A mutable `pagado` column was rejected — it breaks the append-only guarantee and is a stored derived value; recomputing on read was rejected — a credit book's numbers must not move when a rule changes. The rejected alternative of naming the target charge on the `PagoPropuesto` was also rejected: the client does not choose which charge it pays, the FIFO does |

## 5. The Client Credential (`codigo`)

**Its scope has dropped.** The `codigo` opens **read** over the client's own statement and the right to **propose** a payment. It opens **no write**: no `LedgerEntry`, no `CargoLinea`, no `Confirmacion`, no `FiadoPropuesto`, no `PagoPropuesto` resolution. The confirmation is given on the shop's screen and recorded by the staff session; the payment is recorded by the owner.

| Property | Value |
|---|---|
| Alphabet | `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` — 32 symbols, no `0/O`, no `1/I/L` |
| Length | 20 symbols = **100 bits** (`32^20 ≈ 1.27 × 10^30`), blocked in fours for legibility |
| Presented as | The `X-Codigo` header, every client request, memory only |
| Stored as | PBKDF2-SHA256 hash with a per-credential salt, plus a 6-symbol `prefix` |
| Grants | `GET /api/v1/cliente/estado/`, `GET /api/v1/cliente/cargos/{id}/`, `POST /api/v1/cliente/pagos/proponer/` |
| Does **not** grant | confirming, cancelling, disputing, recording a payment, reading the credit book |

The `prefix` is the first 6 symbols, not independent entropy: a stolen hash plus the prefix leaves 70 bits — still infeasible. It is shown only on the owner's screen, never to a `dependiente` or a client.

**At rest** — only the digest; the plaintext exists solely in the issuing response. **In transit** — header only: never a query parameter, cookie, body field or URL fragment; client responses send `Cache-Control: no-store` and `Referrer-Policy: no-referrer` and set no `Set-Cookie`. **Verification** — `check_password` against the shop's candidate rows, found by `prefix`; every candidate is compared, so the work does not depend on which one matches. **Throttle** — a `CodigoIntento` ledger: 10 failures per IP / 15 min, 20 per prefix / 15 min, 500 per shop → refused with the **byte-identical** `422 / codigo_invalido` payload of an unknown code, so it is never an oracle.

### 5.1 Lifecycle

    issue ─► plaintext once ─► print the slip ─► the client presents it per request
    rotate ─► a new plaintext; the previous revoked at the same instant
    revoke ─► it stops resolving; the row survives only as a revoked fingerprint

Rotation is the re-print path: the slip is a consumable, not a re-printable document. A revoked value never authenticates; it is retained only so the **owner's** screen says «código rotado».

### 5.2 Leak surface

| Surface | Control |
|---|---|
| Staff payloads | The plaintext is never a serializer field; the owner sees the `prefix` only; the `dependiente` sees neither — CAC-02 |
| Client payloads | `codigo` is not a field of the client schema — CAC-10 |
| Logs and error reports | The `X-Codigo` header is stripped from request logging; the value never reaches a log line, a serializer or an error body |
| URLs and history | Header-only: never in a path, query string or fragment, so never a history entry, a `Referer` or a cache key |
| Browser storage | React state only; no `localStorage`/`sessionStorage`, `autocomplete="off"`, cleared on navigation |
| Error bodies | A fixed 422 vocabulary; no submitted value is echoed |
| Clipboard and slip | Inherent to a printed slip; mitigated by rotation, the throttle and handing the slip over at the counter |

### 5.3 RED tests

| # | Test | Assertion |
|---|---|---|
| R1 | `test_codigo_ausente_de_todo_arbol_staff` | The plaintext and the `prefix` are absent from **every** JSON path of every owner and `dependiente` response — a whole-tree walk, not a key check |
| R2 | `test_codigo_ausente_de_todo_arbol_cliente` | The plaintext is absent from every JSON path of every client response |
| R3 | `test_codigo_ausente_de_los_logs` | `caplog` over a client request cycle holds no occurrence |
| R4 | `test_codigo_ausente_de_la_url` | `path` and `get_full_path()` never contain it; a credential as a query parameter is refused |
| R5 | `test_codigo_ausente_del_cuerpo_de_error` | A forced 422 and a forced 500 carry no part of it |
| R6 | `test_codigo_en_claro_no_se_persiste` | No field of any model row holds the plaintext — and the only row a client request can create is the `PagoPropuesto` it proposed, whose `importe` and `referencia` are the client's own words, never the credential |
| R7 | `test_dependiente_ve_cero_credenciales` | Every credit-book endpoint answers 403; every 200 staff response holds neither `codigo` nor `prefix` |
| R8 | `test_throttle_no_es_oraculo` | Unknown, revoked and throttled credentials return byte-identical payloads |
| R9 | `test_credential_unicity` | Unique in the shop; one active credential per customer; a rotated value refuses the old one |

## 6. The Confirmation State Machine

The machine is now **one-way and has two branches**, and it starts on the **proposal**, not on the charge. There is no dispute, no reconciliation and no path back to a previous state.

    FiadoPropuesto.pendiente ──confirmar──► FiadoPropuesto.confirmado
          │                                        │
          │                                        └──► LedgerEntry(cargo) + CargoLinea[]
          │                                             + Confirmacion(confirmado)   [same transaction]
          │
          └──cancelar──► FiadoPropuesto.cancelado
                           └──► nothing is written; no cargo, no debt

**The `Confirmacion` has one state.** `estado ∈ {confirmado}` — no `en_disputa`, no `importe_reclamado`, no second row per charge. A `cargo` with no `Confirmacion` row reads `sin_confirmar`, but that state is **unreachable in normal operation**: rule 5 of §3.2 forbids a charge without a confirmation in the same transaction.

| From | To | Driver | Appended / written | Guard / refusal |
|---|---|---|---|---|
| `pendiente` | `confirmado` | `dueño`, or `dependiente` *(N5)* | `Confirmacion(confirmado, confirmado_en=now, origen=<server-inferred>, facilitado_por_id=<acting user if the dependiente presented it, else NULL>)` + `LedgerEntry(cargo)` + `CargoLinea[]`; `FiadoPropuesto.confirmed_at` | The proposal must be `pendiente` (else `propuesta_ya_confirmada`); the `desglose` must balance (else `lineas_descuadradas`); the customer must not be `suspendido` (else `limite_superado` / `antiguedad_superada`) |
| `pendiente` | `cancelado` | `dueño`, or `dependiente` *(N5)* | nothing but `FiadoPropuesto.canceled_at` | The proposal must be `pendiente` (else `propuesta_ya_cancelada`) |
| `confirmado` | — | — | — | **Refused** — `propuesta_ya_confirmada`; no second `Confirmacion`, no second `cargo` |
| `cancelado` | — | — | — | **Refused** — `propuesta_ya_cancelada`; a cancelled proposal never becomes a charge |

**Who drives what.** The `cliente` drives **no transition**: the client confirms on the shop's screen, and the staff session records it. The `dueño` prepares proposals, records confirmations, cancels them and records the payments. The `dependiente` prepares **one** proposal and records its confirmation, and nothing else (§7, CF-01) — and only when the N5 gate is open, which on the current decision it is not.

**Where the confirmation is given.** In the shop, on the shop's device, in front of the owner. The client's portal has no confirmation action — `POST /api/v1/cliente/confirmar/` does not exist. The screen is served by the **staff** session, so the client never authenticates to see the proposal and the `codigo` is not involved in the confirmation at all (CF-02).

**The client may decline.** A decline is not a client-side action: the client says no in the shop, and the owner records the cancellation. The proposal is then `cancelado` and the outstanding never moved, because it never moved in the first place (CC-04).

## 7. The Permission Matrix

Three principals: the two shop **roles** (Django groups `dueno`, `dependiente`) and the **client** (a bearer credential scoped to one `Customer`). The client is not a role: no `User`, no group, no session.

| Capability | Endpoints | `dueño` | `dependiente` | `cliente` |
|---|---|:---:|:---:|:---:|
| Cash movements and the day close | `POST /api/v1/caja/`, `/cierre/` | Yes | Yes | No |
| The credit book: list, detail, ledger, balances, ageing, `credit_limit` | `GET/POST/PATCH /api/v1/clientes/…` | Yes | **No → 403** | No |
| Create a customer, set `credit_limit`, issue or rotate a `codigo` | `POST /api/v1/clientes/`, `…/codigo/` | Yes | **No → 403** | No |
| Prepare a `FiadoPropuesto` | `POST /api/v1/propuestas/` | Yes | Yes — **one at a time**, *(N5)* | No |
| Record the confirmation of a proposal | `POST /api/v1/propuestas/{id}/confirmar/` | Yes | Yes — **the proposal presented**, *(N5)* | No |
| Cancel a proposal | `POST /api/v1/propuestas/{id}/cancelar/` | Yes | Yes — **the proposal presented**, *(N5)* | No |
| Record a `pago` | `POST …/libreta/` | Yes | **No → 403** | No |
| Validate a proposed payment and record the `pago` | `POST /api/v1/pagos-propuestos/{id}/validar/` | Yes | **No → 403** | No |
| Reject a proposed payment | `POST /api/v1/pagos-propuestos/{id}/rechazar/` | Yes | **No → 403** | No |
| Show the proposal's screen at the counter | `GET /api/v1/propuestas/{id}/pantalla/` | Yes | Yes — **only the proposal the `dependiente` presented**, *(N5)* | No |
| The risk ladder and the `posicion_real` | `GET /api/v1/posicion/` | Yes | **No** — the ladder, `posicion_real`, `fiado_pendiente` and `buckets` are 403 for the `dependiente`; the same route still answers it a **reduced** payload with `caja`, `clientes` and `cierre_hoy` only | No |
| Lift a suspension | `POST …/suspension/anular/` | Yes | **No → 403** | No |
| Users and roles | staff administration | Yes | **No → 403** | No |
| The catalogue (`Producto`) | `GET /api/v1/catalogo/` | Yes | No | No |
| A `StockMovement` | `POST /api/v1/existencias/` | Yes | No | No |
| The client's statement | `GET /api/v1/cliente/estado/` | No | No | Yes — own confirmed charges |
| The itemisation of an own confirmed charge | `GET /api/v1/cliente/cargos/{id}/` | No | No | Yes — own charges |
| Propose a payment | `POST /api/v1/cliente/pagos/proponer/` | No | No | Yes — own charges; writes no ledger row |
| Confirm or cancel a proposal | — | No | No | **No — the client never writes** |

**The two rows that changed.** The client lost `Confirmar` and `Disputar`: neither exists any more, on any route. The `dependiente` moved from "presents one charge and receives the confirmation" to "prepares one proposal and records its confirmation" — the same bounded erosion of the 403 boundary, now expressed over a proposal rather than over a charge (§2 D6, CF-01).

### 7.1 The `dependiente`'s 403 boundary

Every denied capability answers **403 with no partial data in any field**: no alias, no customer identifier, no `codigo`, no prefix, no count. The refusal is total and server-side — hiding a control is not enforcement. Three structural properties: (1) **scope** — every queryset is filtered by `current_shop(request)`; (2) **allowlist** — `PosicionDependienteSerializer` declares exactly `caja`, `clientes` and `cierre_hoy`, and `clientes` returns `[]` **without executing the customer query**; (3) **route shape** — only the `dueño` reaches any credit-book route, and no `PUT`/`PATCH`/`DELETE` exists for a ledger row. The conditional facilitation is the single bounded exception: one proposal, nothing else (§2 D6). **It is gated by N5 and, on the current decision, it is NOT added** — so the `dependiente` keeps the `403` over the whole credit book, including the proposal routes. The rows marked *(N5)* in the table above describe the capability **if** the gate opens; until then they answer 403 to the `dependiente` like every other credit-book route.

### 7.2 The client scope as a structural property

The scope comes **only** from the presented `codigo`, resolved to exactly one `Customer` — never from a URL segment, a body field or a session key. A missing or invalid `codigo` yields **422 `codigo_invalido`** with no customer data and no hint. Every client queryset is built from the resolved customer, so a charge outside the scope is refused with `cargo_ajeno` and appends nothing. The client serializer is a schema class of its own, and it declares **none** of the nine staff-only fields — `caja`, `fiado_pendiente`, `posicion_real`, `buckets`, `credit_limit`, `antiguedad_max_dias`, `suspended_reason`, `codigo`, `prefix` — and never another customer's data. A test asserts exactly that: the client field set contains none of those nine (CAC-10). The staff schemas are **not** pairwise disjoint among themselves, and the client schema shares harmless names with them (`total`, `lineas[]`, `producto`, `cantidad`, `precio_unitario`): what must never cross is *data*, not a *name*. The proposal-screen schema is a staff schema, so it legitimately carries the same shape the client sees for its own charges.

**Invariants:** (1) no client endpoint reads `request.session` for scope, and a request carrying a staff session cookie is refused with 403; (2) no staff endpoint accepts a `codigo` — there is no route where the two meet any more, because the confirmation no longer needs the client's credential; (3) no upgrade in either direction; (4) no response mixes two schema classes; (5) **no client endpoint writes to the credit book** — the only row a client request may create is its own `PagoPropuesto`, which is not a ledger row.

## 8. The Scope Mechanisms

Each principal class has **exactly one source of scope**, and the scope is a property of the **route**, never of the request.

| | Staff scope | Client scope |
|---|---|---|
| Mechanism | Server-side Django session | A per-request bearer credential in `X-Codigo` |
| Single source | `request.session["shop_id"]`, read only through `current_shop(request)` | The `X-Codigo` header, read only through `resolver_credencial(request)` |
| Identity | `auth.User` + the group `dueno` or `dependiente` | The `Customer` resolved from the credential |
| Shop | The `shop_id` written at login; a `User` may belong to several `Shop` rows through `Shop.usuarios`, but a session names exactly one | The `shop_id` carried by the matching `CustomerCodigo` — the credential itself names the shop |
| Lifetime | Until logout or expiry | The life of the request; nothing is stored server-side |
| When absent | 403 on every staff endpoint | 422 `codigo_invalido` on every client endpoint, with no customer data |
| Mutability | Not changeable by any request parameter or body field | Rotated only by the `dueño` |
| Writes | The only principal that writes to the credit book | **None** — read + propose only |

**The invariant that keeps them apart:** *a request resolves to exactly one **acting** scope, and the route decides which.* Staff routes read the session and ignore any `X-Codigo`; client routes read the header and refuse a request that carries a staff session cookie. There is **no route that accepts both**. The old documented exception — the facilitation route, where a session and a `codigo` met — **no longer exists**: the client confirms without presenting a credential, so the confirmation route is a pure staff route.

Two consequences: **the client never gets a cookie** — client responses set no `Set-Cookie`, so the browser holds no ambient client authority, which is also why the client surface has nothing for CSRF to protect (ADR-4). And **the staff session never names a customer** — the `shop_id` is the whole staff scope.

**A proposal is not a scope.** The `FiadoPropuesto` is a **prepared figure**, not an acting principal: no session, no credential, no scope of its own. The staff session that prepares it is its scope, and the staff session that confirms it is again the acting scope. It carries a `customer` because it *is about* a customer — the reference, not the authority.

**A proposed payment is a request, not a scope.** A `PagoPropuesto` is the client's *request* for the owner to record a payment. It creates no `LedgerEntry`, it moves no balance, and it grants the client nothing beyond the acknowledgement that it was received. The `pago` is written by the owner, in the owner's session, after validating it (PA-09, CC-07). **It names no charge**: the client proposes an amount and the FIFO decides which charges it retires, so the client cannot direct money at a particular debt and cannot learn anything about the order from the proposal's shape (ADR-27).

Enforcement is by test, not by discipline: a test asserts that `current_shop` and `resolver_credencial` are the only readers of their source, that no view calls both, that a request presenting both a session and a `codigo` is refused by the client routes and ignored by the staff routes, and that a client-authenticated request writes no `LedgerEntry`, no `CargoLinea` and no `Confirmacion`.
## 9. API Contracts

All routes live under `/api/v1/`. Outside it: `GET /health/` (liveness, touching no database) and the HTML mounts `/app/posicion/`, `/app/propuesta/{id}/` and `/app/cliente/`. **No pagination anywhere** — bare JSON lists. `Decimal` crosses the wire as a **string**, instants as ISO-8601.

### 9.1 Routes

| Method | Path | Who | Body | Result |
|---|---|---|---|---|
| GET | `/health/` | public | — | 200 `{"status":"ok"}` |
| GET | `/app/posicion/`, `/app/propuesta/{id}/` | staff | — | 200 HTML + mount + CSRF token; 302 to login |
| GET | `/app/cliente/` | public \* | — | 200 HTML + mount |
| GET | `/api/v1/posicion/` | staff | — | 200 the owner payload, or the **reduced** `dependiente` payload (`caja`, `clientes`, `cierre_hoy` only — no ladder, no `posicion_real`, no `fiado_pendiente`, no `buckets`); 403 |
| POST | `/api/v1/caja/` | staff | `{kind, concept, amount}` | 201; 422; 403 |
| GET | `/api/v1/cierre/` | staff | — | 200 `{date, esperado, contado, desviacion}` (`dueño`); 200 `{esperado, contado, desviacion}` (`dependiente`); 403 |
| POST | `/api/v1/cierre/` | staff | `{date, contado}` — `esperado`/`desviacion` refused (rule 14) | 201; 422 `cierre_duplicado`, `campo_no_admitido`; 403 |
| GET | `/api/v1/catalogo/` | `dueño` | — | 200 `Producto[]`, `activo` only; 403 |
| POST | `/api/v1/existencias/` | `dueño` \* | `{producto_id, kind, cantidad, concept}` | 201; 422; 403 |
| GET / POST | `/api/v1/clientes/` | `dueño` | `{alias, phone?, credit_limit?}` — the server stamps `created_by_id` with the acting user | 200/201; 422; 403 |
| GET / PATCH | `/api/v1/clientes/{id}/` | `dueño` | `{credit_limit}` | 200; 422; 403; 404 |
| POST | `/api/v1/clientes/{id}/codigo/` | `dueño` | — | 201 `{codigo, prefix, issued_at}` — the only time the plaintext exists; 422; 403; 404 |
| POST | `/api/v1/clientes/{id}/libreta/` | `dueño` | `{kind, amount}` - `kind` ∈ {`pago`} **only**: a `cargo` is written by the confirmation of a proposal, never directly. `amount` MUST NOT exceed the outstanding it retires — the excess is returned as change and never enters the book. A `pago` also writes its `ImputacionPago` rows, one per charge it retires | 201; 422 `pago_excede_deuda`; 403; 404 |
| POST | `/api/v1/clientes/{id}/suspension/anular/` | `dueño` | `{}` | 200; 403; 404 |
| POST | `/api/v1/propuestas/` | staff \* | `{cliente_id, lineas[{producto_id, cantidad, precio_unitario?}], total?}` | 201 `FiadoPropuesto` + `lineas`; 422 `lineas_descuadradas`, `producto_ajeno`; 403; 404 |
| GET | `/api/v1/propuestas/{id}/pantalla/` | staff \* | — | 200 the screen: `lineas[]` with `producto`, `cantidad`, `precio_unitario`, `total`, plus `total`; 403; 404 |
| POST | `/api/v1/propuestas/{id}/confirmar/` | staff \* | `{}` | 201 `Confirmacion(confirmado)` + the `cargo`; 422 `propuesta_ya_confirmada`, `lineas_descuadradas`, `limite_superado`, `antiguedad_superada`; 403; 404 |
| POST | `/api/v1/propuestas/{id}/cancelar/` | staff \* | `{}` | 200; 422 `propuesta_ya_cancelada`; 403; 404 |
| GET | `/api/v1/pagos-propuestos/` | `dueño` | — | 200 `PagoPropuesto[]` pending; 403 |
| POST | `/api/v1/pagos-propuestos/{id}/validar/` | `dueño` | `{}` | 201 the `pago`, whose `amount` is **exactly** the `PagoPropuesto.importe`, plus its `ImputacionPago` rows; 422 `pago_ya_resuelto`; 422 `pago_excede_deuda` — a proposed amount larger than the customer's outstanding is refused at validation; 403; 404 |
| POST | `/api/v1/pagos-propuestos/{id}/rechazar/` | `dueño` | `{}` | 200; 422 `pago_ya_resuelto`; 403; 404 |
| GET | `/api/v1/cliente/estado/` | `cliente` \* | `X-Codigo` | 200 statement: own **confirmed** charges with their `desglose` + `total`; 422; 403 |
| GET | `/api/v1/cliente/cargos/{id}/` | `cliente` \* | `X-Codigo` | 200 the charge with its full itemisation; 422; 403 |
| POST | `/api/v1/cliente/pagos/proponer/` | `cliente` \* | `X-Codigo` + `{importe, referencia}` | 201 `PagoPropuesto(pendiente)` — **writes no ledger row**; 422 `importe_no_positivo`, `pago_excede_deuda`; 403 |

\* conditional. The three client routes are gated by **Regla 4**; `POST /api/v1/existencias/` by **Regla 6**; the four proposal routes by **N5** — which on the current decision is closed, so those four answer 403 to the `dependiente`. No `PUT`, `PATCH` or `DELETE` route exists for `LedgerEntry`, `CargoLinea`, `Confirmacion`, `PropuestaLinea` or `PagoPropuesto`: the ledger is append-only at the URL surface too.

**The routes that are gone.** `POST /api/v1/cliente/confirmar/`, `POST /api/v1/cliente/disputar/` and `POST /api/v1/facilitar/{cargo_id}/` no longer exist. The client cannot reach a write, so the confirmation is a **staff** route over a proposal and the payment a staff route over a proposed payment.

### 9.2 The serializer allowlist per audience

Six schema classes; DRF's `fields` is exhaustive, so "no alias in ANY JSON path" is a schema property, not a promise. They are **not** pairwise disjoint: the two staff position classes share `caja`, `clientes` and `cierre_hoy`, and the two close classes share `esperado`, `contado` and `desviacion` — the `dependiente` is a shop role, not an outsider, and CP-05 requires it to read the close. The client class shares harmless names with the staff ones too (`total`, `lineas[]`, `producto`, `cantidad`, `precio_unitario`), because the client is entitled to see the `desglose` of the charges it confirmed. The property that carries the leak guarantee is therefore about **data, not names**, and it is the one tested: **the client class declares none of the staff-only fields** — no `caja`, `fiado_pendiente`, `posicion_real`, `buckets`, `credit_limit`, `antiguedad_max_dias`, `suspended_reason`, `codigo` or `prefix` — and never carries another customer's data (CAC-10).

| Class | Declared | Absent |
|---|---|---|
| `PosicionDuenoSerializer` | `caja`, `fiado_pendiente`, `posicion_real`, `buckets`, `clientes[]`, `serie_caja[]`, `cierre_hoy` | — |
| `PosicionDependienteSerializer` | `caja`, `clientes` (a `SerializerMethodField` returning `[]` **without executing the customer query**), `cierre_hoy` | `fiado_pendiente`, `posicion_real`, `buckets`, `alias`, `credit_limit`, `antiguedad_max_dias`, `codigo`, `prefix` |
| `EstadoClienteSerializer` | `alias`, `total`, `cargos[]` - each: `id`, `fecha`, `amount`, `confirmado_en`, `pagado`, `saldo`, `lineas[]` - each line: `producto`, `cantidad`, `precio_unitario`, `total` | `credit_limit`, `caja`, `posicion_real`, `buckets`, `antiguedad_max_dias`, `suspended_reason`, `codigo`, `prefix`, any other customer's data, any pagination metadata |
| `PropuestaPantallaSerializer` | `total`, `lineas[]` — each: `producto`, `cantidad`, `precio_unitario`, `total` | `credit_limit`, `codigo`, `prefix`, the customer's ageing, any other proposal |
| `CierreDuenoSerializer` | `date`, `esperado`, `contado`, `desviacion` | — |
| `CierreDependienteSerializer` | `esperado`, `contado`, `desviacion` | `date` |

The **staff-only fields** — the nine the client must never see — are `caja`, `fiado_pendiente`, `posicion_real`, `buckets`, `credit_limit`, `antiguedad_max_dias`, `suspended_reason`, `codigo` and `prefix`. The client class declares **none** of them; the other five staff classes declare some of them by design. `PropuestaPantallaSerializer` shares the client's `total`/`lineas[]` names on purpose: it shows one proposal's `desglose` at the counter, and the client is entitled to see the `desglose` of the charges it confirmed. This list is the **same nine** wherever it is enumerated — §7.2, §9.2's opening prose, §9.2's field list and the test of §15.2. §12.1 names the same property without repeating the list — so a reader or a test author never has to reconstruct it.

**The itemisation is always present.** Every charge in the statement carries its `lineas[]`, because every charge in the statement is a confirmed charge with a mandatory `desglose` (IC-07, CC-06). There is no "unconfirmed-charge rule" any more: a charge without a confirmation does not exist, so it cannot appear and its lines cannot leak. `PropuestaPantallaSerializer` is a **staff** schema holding the `desglose` of the one proposal presented.

**`pagado` and `saldo` on each charge.** The statement says how much of each charge the client has already paid and how much of it is still owed. `pagado` is `Σ ImputacionPago.importe` over the imputations of that charge; `saldo` is `amount − pagado`. A charge of 15,00 € settled by 5,00 € reads `pagado: 5,00, saldo: 10,00` — the client sees "5/15" — and a charge of 8,00 € fully settled reads `pagado: 8,00, saldo: 0,00`. Both are **derived on read** and neither is stored: the imputations are the record, and these two figures are read from them. The client is entitled to see them — it is the client's own debt, and the whole point of the confirmation is that the client knows exactly what it owes and what it has paid.

### 9.3 Error codes

Every validation failure is **HTTP 422** with the fixed shape `{"codigo_error": "<code>", "detail": "<Spanish message>"}`. The vocabulary: `limite_superado` · `antiguedad_superada` · `importe_no_positivo` · `campo_no_admitido` · `tipo_desconocido` · `cierre_duplicado` · `lineas_descuadradas` · `cargo_ya_confirmado` · `propuesta_ya_confirmada` · `propuesta_ya_cancelada` · `pago_ya_resuelto` · `pago_excede_deuda` · `codigo_invalido` · `codigo_duplicado` · `cargo_ajeno` · `producto_ajeno` · `facilitador_invalido`.

**The codes that are gone:** `disputa_abierta` and `importe_reclamado`. `cargo_ya_confirmado` survives as the DB-level twin of `propuesta_ya_confirmada` — the API contract names the proposal-level code (CC-01). `cargo_no_indicado` is gone with the client's ability to name a charge (ADR-27); `cargo_ajeno` survives, because the client still reads its own charges one at a time and must be refused on another's.

Every code is produced by a named rule of §3.2: `limite_superado` → rules 1–2 · `importe_no_positivo` → rules 15, 17 · `campo_no_admitido` → rules 4, 14 · `tipo_desconocido` → rules 16, 20 · `cierre_duplicado` → rule 9 · `lineas_descuadradas` → rules 3, 21 · `cargo_ya_confirmado` → rule 6 · `propuesta_ya_confirmada`/`propuesta_ya_cancelada` → rule 7 · `pago_ya_resuelto` → rule 18 · `pago_excede_deuda` → rule 19 · `codigo_duplicado` → rule 10 · `facilitador_invalido` → rule 7b · `producto_ajeno` → rule 11 · `antiguedad_superada` → rule 1 · `cargo_ajeno` → §7.2's client scope · `codigo_invalido` → §5's credential resolution.

**403 responses carry no request data:** a fixed `{"codigo_error": "permiso_insuficiente", "detail": "…"}` and nothing else.

## 10. The Pure Rules Module

`backend/tienda/domain/` imports **no Django, no DRF and no app module** — enforced by `backend/tests/unit/test_domain_is_orm_free.py`, which AST-parses every file in the package and fails on a forbidden import. Plain values in, plain values out: no ORM objects, no database, no request, and **no implicit clock** — the caller passes `at`. The service layer is the only place that converts UTC to shop-local calendar days.

**Types** (`domain/types.py`): `EntryKind` (`cargo`/`pago`), `Bucket` (`vigente`/`envejecido`/`viejo`/`cronico`), `SuspensionReason` (`limite_superado`/`antiguedad_superada`), `ConfirmState` (`sin_confirmar`/`confirmado`), `PropuestaEstado` (`pendiente`/`confirmado`/`cancelado`), `PagoPropuestoEstado` (`pendiente`/`validado`/`rechazado`), `StockQualifier` (`techo_no_conteo`), and the plain records `LedgerLine`, `CargoLine`, `PropuestaLine`, `CashLine`, `StockLine`, `Allocation`, `Imputacion`, `CustomerState`, `ConfirmacionRow`, `ChargeState`.

**`Imputacion`** is the plain record of one (payment, charge) pair: `pago_id`, `cargo_id` and `importe`. It mirrors the `ImputacionPago` row and is what `imputations_of` returns. **`ChargeState`** carries the derived view of a charge: its `saldo` — what is still owed on it — which is `cargo.amount − Σ Imputacion.importe` over the imputations of that charge, and it is **never stored**.

| Module | Function · signature | Guarantee |
|---|---|---|
| `allocation.py` | `allocate_payments(charges, payments) -> Allocation` | FIFO by `(occurred_at, id)`. **No residual is possible**: rule 19 refuses a `pago` larger than the debt it retires, so every cent is always placed. The `residual` field stays on the record and is always `0` — it is kept so a caller that reads it has one shape to read, not because a surplus is a legal state |
| `allocation.py` | `imputations_of(allocation, payment_id) -> tuple[Imputacion, ...]` | The rows to persist for one payment: one per charge the payment touched, in the order the allocation made them. **The grain is the charge**: a payment that retires 8,00 € of one charge, 7,00 € of a second and 5,00 € of a third produces three rows, and a charge of 15,00 € made of three `CargoLinea` rows produces **one** row of 5,00 € against the charge, not three rows against the lines |

| `ageing.py` | `bucket_of(age_days: int) -> Bucket` | `vigente` ≤ 7 d, `envejecido` 8–30, `viejo` 31–90, `cronico` > 90. Each unpaid charge is bucketed by **its own** age, and the four bucket totals **sum exactly to the outstanding** |
| `ageing.py` | `age_in_days(occurred_at, at) -> int` | The calendar-day difference; the values arrive shop-local |
| `evaluation.py` | `evaluate_customer(lines, *, credit_limit, at, suspension_age_days=30, override=False) -> CustomerState` | The derived state; `credit_limit=None` means «sin límite» and never fires `limite_superado`; `override=True` lifts the automatic suspension |
| `evaluation.py` | `antiguedad_max_dias(charges, payments, at) -> int` | The age of the oldest unpaid charge; drives the suspension and the ladder order |
| `position.py` | `real_position(caja, outstanding_total) -> Decimal` | `posicion_real = caja + Σ pending balances`, additive only |
| `position.py` | `outstanding(lines, at) -> Decimal` | `Σ cargos − Σ pagos` over `occurred_at ≤ at`. **The result is never negative**: rule 19 refuses a `pago` larger than the debt it retires, so there is no credit to hold and no `credit_a_favor` state. No third term: no `nota de crédito` exists |
| `position.py` | `cash_at(opening_cash, movements, pagos, at) -> Decimal` | `caja = inicial + Σ(entradas) − Σ(salidas) + Σ(pagos)` over `occurred_at ≤ at` |
| `charges.py` | `total_de_linea(cantidad, precio_unitario) -> Decimal` | `round(cantidad × precio_unitario, 2)` — the rounding rule the DB `CHECK` mirrors |
| `charges.py` | `precio_unitario_de(precio_catalogo, precio_solicitado) -> Decimal` | The override wins when present, otherwise the catalogue price |
| `charges.py` | `charge_amount_matches(lines, declared_amount) -> bool` | Whether the declared amount equals `Σ lineas.total` — the source of `lineas_descuadradas`. **An empty `lines` sequence never matches**: the `desglose` is mandatory (IC-07) |
| `charges.py` | `propuesta_amount_matches(lines, declared_total) -> bool` | The same rule for a `FiadoPropuesto`: the `total` must equal the sum of its `lineas`; no lines never matches |
| `confirmation.py` | `confirmacion_efectiva(rows) -> ConfirmacionRow \| None` | The latest row, or `None` |
| `confirmation.py` | `estado_cargo(rows) -> ChargeState` | `confirmado` when a confirmation row exists, otherwise `sin_confirmar`. **Two values only** — `en_disputa` is gone. A read-time projection only; never the guard for a write |
| `confirmation.py` | `propuesta_transicion_permitida(estado_actual, destino) -> str \| None` | `None` when allowed, otherwise the refusal `codigo_error`: `propuesta_ya_confirmada`, `propuesta_ya_cancelada`. The guard is the **stored proposal state**, not a projection of the ledger |
| `confirmation.py` | `confirmacion_requerida(charge_exists, confirmation_rows) -> bool` | Whether a charge may be written at all: a `cargo` requires its `Confirmacion` in the same transaction (rule 5) |
| `stock.py` | `existencias_registradas(movements) -> tuple[Decimal, StockQualifier]` | `Σ entradas − Σ salidas` and the qualifier `techo_no_conteo`; no rule is attached to it |
| `cash.py` | `desviacion_cierre(esperado, contado) -> Decimal` | `esperado − contado`, the value stored in the `DayClose` |
| `cash.py` | `caja_al_cierre(opening_cash, movements, pagos, at) -> Decimal` | The derived `caja` at the close instant — the value stored as `DayClose.esperado`. The same computation as `cash_at` with `at` = the close instant, so `esperado` cannot be client-supplied |

**The functions that are gone.** `transicion_permitida` (the old two-state transition table) and `escalado_sin_confirmar` (the 7-day flag on a charge that cannot exist) have no object and are removed. `allocate_payments` loses its `credit_notes` parameter, `outstanding` loses its third term, and `evaluate_customer` loses the dispute case.

**The guarantee.** Every rule above is a total function over plain values. A unit test may call any of them with a hand-computed fixture and no database at all — pytest-django raises `RuntimeError: Database access not allowed` for any ORM call in a test without the `django_db` marker, so the layer is DB-free **by construction**, not by convention.

## 11. The Three React Surfaces

One Vite bundle, one origin, three routes, two credential modes. No CORS, no second host, no second URL, no hard-coded figure, no charting library.

```
frontend/src/
├── main.tsx, router.tsx        the mount and the three routes
├── api/http.ts                 the ONLY place a URL is built; asserts a relative path
├── api/staff.ts                session + X-CSRFToken
├── api/cliente.ts              X-Codigo only; no credentials sent
├── surfaces/Posicion.tsx       /app/posicion
├── surfaces/Propuesta.tsx      /app/propuesta/{id}   the shop's screen
├── surfaces/Cliente.tsx        /app/cliente
└── components/                 Ecuacion, Escalera, Cinta, Cierre, PropuestaForm,
                                Pantalla, ProponerPago, Acceso, Estado,
                                Credenciales
```

**The same-origin contract.** Every request uses a **relative path** (`/api/v1/…`); the single fetch helper rejects any absolute URL, so a second host cannot be introduced by accident. Staff requests send `credentials: 'same-origin'` and `X-CSRFToken` on every mutation; client requests send `credentials: 'omit'` — the client has no cookie to send, and sending one would blur the two scopes. No third-party script, no external font, no analytics: the client page carries a credential, so a strict CSP (`default-src 'self'`) is set on its mount. The API is served by the same deployable service, over HTTPS.

**`/app/posicion` — the owner board.** `Ecuacion`: `caja + fiado_pendiente = posicion_real` with the bucket breakdown. `Escalera`: the risk ladder, customers with `pendiente > 0`, sorted by `antiguedad_max_dias` **descending**, each row with `alias`, `pendiente`, `antiguedad_max_dias`, the derived state and the `suspended_reason`. `Cinta`: the four ageing ribbons. `Cierre`: `esperado`, `contado`, `desviacion` and the close form. `Credenciales`: issue or rotate a `codigo`, show the `prefix` and the rotation date, the plaintext only in the issuing response. Two more **board sections** (not components): *Propuestas* — prepare a proposal and watch the pending ones, served by `PropuestaForm` and the proposal routes — and *PagosPropuestos* — the client's proposed payments, to validate or reject, served by the payment-proposal routes. `Serie`: the 30-day `serie_caja` chart — **declared cut-line 1**, droppable without touching a capability. The board polls `/api/v1/posicion/` every 20 s; the poll doubles as the keep-alive.

**`/app/propuesta/{id}` — the shop's screen.** The third surface, and the place the confirmation is given. `Pantalla` shows the full `desglose`: product, quantity and `precio_unitario` for every line, plus the `total` — nothing else, no balance, no ageing, no other customer. The screen's two actions are `Confirmar` and `Cancelar`: they post to `/api/v1/propuestas/{id}/confirmar/` and `…/cancelar/` respectively, and they are the two buttons of `Pantalla` rather than separate components. The client reads it from the counter; the client does **not** authenticate to it and holds no credential while doing so.

**`/app/cliente` — the client statement.** `Acceso`: one credential field, `autocomplete="off"`, React state only, cleared on navigation. `Estado`: the total owed, then one row per charge — date, amount, confirmation date, and its `desglose`. `ProponerPago`: the `cargo_id` of the charge it settles, an `importe` and a `referencia`; it proposes, and says plainly that the owner still records the payment. The client page does **not** poll — a poll would multiply the credential's exposure for no benefit.

## 12. Security Architecture

**Three independent layers.** A leak must fail all three; none relies on the others. (1) **View level** — `RoleRequired`/`IsDueno`/`EsCliente` on every view; a denied principal gets **403 with no partial data**; every queryset is scoped by `current_shop(request)` and every client queryset is built from the customer resolved from the credential. (2) **Serializer allowlist** — the client schema declares none of the staff-only fields, so "no alias in ANY JSON path" is a schema property, not a promise. (3) **Scope resolution** — two different helpers, and no view calls both, so a principal can never hold two scopes.

**Sessions and CSRF.** Django session + `SessionAuthentication` on the staff surface; every staff mutation carries `X-CSRFToken`, and a missing or invalid token is refused with 403 and creates no row. The client surface has no session, so there is nothing for CSRF to forge: `X-Codigo` is a non-simple header a cross-origin request cannot set, and no CORS policy grants it (§2 D3).

**Passwords and secrets.** Django's default `PBKDF2PasswordHasher` (`pbkdf2_sha256`, 1 000 000 iterations) is not overridden. `SECRET_KEY` and `DATABASE_URL` are environment-only; `DEBUG=False` in production; `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` come from the environment; every dependency is pinned to an exact version. The demo accounts are public by design.

### 12.1 Data-protection failure modes

| Failure mode | Control |
|---|---|
| Nested-aggregate leak | Allowlists that reach no related customer object; the client class declares none of the staff-only fields |
| Metadata leak — pagination counts, `total`, `next` | No pagination anywhere; bare JSON lists |
| Error-body echo | The 422 vocabulary is fixed; no submitted value is ever echoed |
| The silent query — clean payload, query still ran | The `dependiente` `clientes` field returns `[]` **without executing the customer query** |
| The hand-maintained contract | A test asserts the client field set declares none of the staff-only fields |
| The unvalidated `alias` | Validated and unique per shop; never in another customer's context |
| **A `codigo` leaking through a staff payload** | **A data-protection failure, not a cosmetic bug.** `codigo` is not a field of any staff schema; the owner sees the `prefix` only; the plaintext exists only in the issuing response. The whole-tree walk (R1, R2, R7) asserts it on every response |

### 12.2 The landmine list

1. Render's filesystem is ephemeral and its free Postgres expires after 30 days → the database vanishes mid-project → **PostgreSQL from day one (Neon)**.
2. A `collectstatic` misconfiguration gives a blank page, not an error → smoke check: the bundle URL returns 200.
3. The free tier sleeps after 15 minutes → a loading page during the defence → keep-alive under 10 minutes.
4. `ALLOWED_HOSTS` or `CSRF_TRUSTED_ORIGINS` missing → every POST returns 403 → both from the environment, set on the first deploy.
5. `seed_demo` not idempotent → duplicated data or a stale board → the seed runs in the build command, with an idempotency test.
6. A `dependiente` leaking a customer field → data-protection failure → the allowlist plus a whole-tree walk.
7. The integration suite on SQLite → `select_for_update`, partial unique indexes and `CHECK` semantics are not exercised → CI runs PostgreSQL.
8. **A `codigo` leaking through a staff payload → a data-protection failure, not a cosmetic bug** → it is not a serializer field; the whole-tree walk asserts it on every response of both staff audiences.
9. **The shared shop screen** → the client reads the owner's screen, in the shop, with the owner present. What is guaranteed: the screen carries **only** the one proposal's `desglose` and `total` — no balance, no ageing, no `credit_limit`, no other customer — and it is served by the staff session, so the client needs no credential to see it. What is **not** guaranteed: that the person at the counter is the customer the proposal names. That is a shop-floor protocol, stated here rather than implied away (§19, question 4).
10. **The `comprobante` (not implemented)** → if it lands without file storage, multipart upload, type and size validation, an attachment model and a retention rule, the shop accumulates personal data with no lifecycle. It stays cut until the extension declares all five (ADR-25).
11. **The two scopes bleeding into one request** → there is no route where a session and a `codigo` meet any more: the confirmation no longer needs the client's credential.
12. **A stored derived value creeping back** (`saldo`, `status`, `stock`, a confirmation state, a `sin_confirmar` charge) → the ORM-free AST test plus a test asserting the absence of every forbidden field name.
13. **A `CargoLinea` being detached or edited** → the model refuses updates and deletes, and no route exposes either.
14. **The throttle becoming an oracle** → unknown, revoked and throttled credentials return byte-identical payloads (§5.3 R8).
15. **A customer credit creeping back** → the temptation is to let a `pago` exceed the debt and hold the difference as a balance in the client's favour. That would resurrect a whole capability: a credit to age, to limit, to reconcile and to explain — a derived value stored in a place that forbids it. Rule 19 refuses the overpayment instead, and the excess leaves the counter as change (ADR-26).

## 13. Data Flow

### 13.1 The proposal and confirmation flow

```
dueño/dep.   Tienda            API (staff)                     DB
  | POST /api/v1/propuestas/ {cliente_id, lineas[]}            |
  |---------------------------------------------------------->|
  |                           | atomic: INSERT FiadoPropuesto(pendiente)
  |                           |        INSERT PropuestaLinea[]  -- no cargo, no debt
  |                           | GET .../pantalla/              |
  |                           |------------------------------>|
  |                           |  lineas[] + total              |
  |                           |<------------------------------|
  |                           | the client confirms (or declines)
  | POST .../confirmar/ {}    |                                |
  |---------------------------------------------------------->|
  |                           | atomic: the proposal is 'pendiente'
  |                           |   else 422 propuesta_ya_confirmada;
  |                           |  the customer is not suspendido;
  |                           |  total == sum(lineas);
  |                           |  INSERT LedgerEntry(cargo) + CargoLinea[]
  |                           |  INSERT Confirmacion(confirmado, confirmado_en=now,
  |                           |     origen=<server-inferred>, facilitado_por_id=<acting user if
  |                           |     the dependiente presented it, else NULL>)
  |                           |  UPDATE FiadoPropuesto(confirmado)
  |<----------------------------------------------------------|  -- NOW it is debt
```

The client's `codigo` is **not** involved: the client confirms in the shop, and the staff session records it. The outstanding moves at the exact instant of the confirmation.

### 13.2 The cancellation flow

```
dueño/dep.   Tienda            API (staff)                     DB
  | the client declines                                            |
  | POST .../cancelar/ {}                                          |
  |---------------------------------------------------------->|
  |                           | atomic: the proposal is 'pendiente'
  |                           |  else 422 propuesta_ya_cancelada;
  |                           |  UPDATE FiadoPropuesto(cancelado)
  |<----------------------------------------------------------|  -- no cargo, no debt
```

The outstanding never moved, because it never moved in the first place.

### 13.3 The payment flow

```
Cliente            API (cliente)         API (dueño)          DB
 | POST .../pagos/proponer/ {importe, referencia}          |
 |---------------------------->|                              |
 |                             | atomic: INSERT PagoPropuesto(pendiente)
 |                             |   -- NO LedgerEntry, NO pago yet
 |<----------------------------| 201 {estado: pendiente}        |
 |                             | POST .../pagos-propuestos/{id}/validar/
 |                             |------------------------------>|
  |                             |                 atomic: the proposal is 'pendiente'
  |                             |                  else 422 pago_ya_resuelto;
  |                             |                  the amount <= the customer's outstanding
  |                             |                  else 422 pago_excede_deuda;
  |                             |                  INSERT LedgerEntry(pago,
  |                             |                    amount = PagoPropuesto.importe,
  |                             |                    customer = the proposal's customer)
  |                             |                  INSERT ImputacionPago[] -- one per charge
  |                             |                    the payment retires, FIFO, by charge
  |                             |                  UPDATE PagoPropuesto(validado,
  |                             |                    resolved_at=now, resolved_by_id=<acting user>)
  |                             |                   -- the outstanding drops by exactly that amount
  | GET .../estado/ -> the new total                            |
```

The `pago` is written by the owner, in the owner's session, after validating the client's proposal. Its `amount` is **exactly** the `PagoPropuesto.importe` the client proposed — never a recomputed or rounded figure — and it is charged to the proposal's own customer, so the payment can only retire that customer's debt. The client's proposal never becomes a `pago` on its own (PA-09, CC-07).

**The client does not choose the charge.** The proposal names an amount, not a charge: the imputations are decided by the FIFO rule over the customer's open charges, and they are recorded as `ImputacionPago` rows in the same transaction as the `pago`. A client who owes 8,00 € of bread, 7,00 € of soda and 15,00 € of biscuits, and proposes 20,00 €, produces three imputations — 8,00 €, 7,00 € and 5,00 € — and the client's charges read 8/8, 7/7 and 5/15.

### 13.4 The client reading the statement

```
Cliente            API (cliente)                              DB
 | GET /api/v1/cliente/estado/  X-Codigo                     |
 |---------------------------->|                              |
 |                             | resolver_credencial -> check_password -> 1 Customer
 |                             | the queryset is built from THAT customer only
 |                             | only CONFIRMED charges exist, so only they appear
 |                             | each with its lineas[]
 |<----------------------------| 200 {alias, total, cargos[]}
```

### 13.5 The flows that are gone

The dispute flow, the reconciliation flow and the client-confirmation flow are deleted. What replaces the dispute is the prevention in §13.1: the client sees the `desglose` before the charge exists, so there is nothing to disagree about afterwards.

## 14. File Changes

The repository holds no implementation yet — this change creates the whole application. Every path below is **created**; nothing is modified and nothing is deleted.

| Path | What |
|---|---|
| `requirements.txt`, `.gitignore`, `render.yaml` | Pinned dependencies; the ignores; the Render blueprint (build and run commands, env vars, `sync: false`) |
| `.github/workflows/ci.yml` | A `postgres:16` service running the unit and integration suites |
| `.github/workflows/keepalive.yml` | `curl -fsS "$PUBLIC_URL/health/"` every 8 minutes, plus `workflow_dispatch` |
| `backend/manage.py`, `backend/pytest.ini` | The entry point; the pytest configuration with the `unit`/`integration`/`e2e` markers |
| `backend/config/{settings,urls,wsgi}.py` | `INSTALLED_APPS`, `REST_FRAMEWORK` with the 422 handler, `STATIC_ROOT`, env-only secrets, `DEBUG=False`, the strict CSP; the mounts; the WSGI app |
| `backend/tienda/models.py`, `backend/tienda/migrations/0001_initial.py` | The sixteen entities of §3 - `FiadoPropuesto`, `PropuestaLinea`, `PagoPropuesto` and `ImputacionPago` among them; every `CHECK`, `UNIQUE` and partial index |
| `backend/tienda/domain/{types,position,allocation,ageing,evaluation,charges,confirmation,stock,cash}.py` | The pure rules of §10 — **no Django import anywhere in the package** |
| `backend/tienda/services.py` | The only ORM-touching layer: rows → plain values → `domain/` → writes inside `transaction.atomic()` |
| `backend/tienda/api/{exceptions,permissions,client_auth,throttle}.py` | The 422/403 handler; `RoleRequired`/`IsDueno`/`EsCliente`; `resolver_credencial`; the throttle ledger |
| `backend/tienda/api/serializers/{staff,cliente}.py` | The staff allowlists, the close allowlists, the proposal-screen schema and the client schema, which declares none of the staff-only fields |
| `backend/tienda/api/{views,urls}.py` | The routes of §9.1 and their URL map |
| `backend/tienda/management/commands/seed_demo.py` | The idempotent demo dataset of §18.2 |
| `backend/tests/unit/test_*.py` | `test_domain_is_orm_free` plus one file per pure rule, with no database |
| `backend/tests/integration/test_*.py` | The cash, ledger, catalogue, permissions, no-leak, client, proposal-screen, payment-proposal, constraints and seed suites |
| `backend/tests/e2e/test_public_url.py` | The deployed URL: HTTPS, `DEBUG=False`, login, the same-origin fetch, the seeded accounts |
| `frontend/{package.json,vite.config.ts,tsconfig.json,index.html}` | The Vite + React + TypeScript build; the output lands in `STATIC_ROOT` |
| `frontend/src/{main.tsx,router.tsx,api/{http,staff,cliente}.ts,surfaces/{Posicion,Propuesta,Cliente}.tsx,components/}` | The mount, the three routes, the three fetch layers, the three surfaces and the components `Ecuacion`, `Escalera`, `Cinta`, `Cierre`, `PropuestaForm`, `Pantalla`, `ProponerPago`, `Acceso`, `Estado`, `Credenciales` |

Package markers (`__init__.py`) are implied. `openspec/changes/tienda-barrio/` and `openspec/explorations/` are not touched, and nothing is written under `openspec/specs/`.

## 15. Testing Strategy

The specs declare three verification levels; the suite has one layer per level, and every one of the 48 requirements is covered by the layer its index declares.

| Level | Where | Database |
|---|---|---|
| `unit` | `backend/tests/unit/` — the pure functions of §10 | **none**, by construction |
| `integration` | `backend/tests/integration/` | **PostgreSQL 16** |
| `e2e` | `backend/tests/e2e/` | the deployed public URL |

**15.1 Unit.** The pure functions of §10 run against hand-computed fixtures with **no database at all**: pytest-django raises `RuntimeError: Database access not allowed` for any ORM call in a test without the `django_db` marker, so the DB-free property is enforced, not asserted. The bucket boundaries, the FIFO order, the partial payment, **the absence of an overpayment residual**, the derived suspension and its lifting, the `precio` override, the `lineas_descuadradas` decision, the proposal transition table, the one-state `estado_cargo` and the stock ceiling are checked here; `test_domain_is_orm_free.py` AST-parses every file of `domain/`.

**15.2 Integration.** The Django test client against **PostgreSQL**, never SQLite — landmine 7. It proves: the 422 payload and every `codigo_error`, with a refused write creating no row and no line; the 2×8 matrix, the credit-book 403, the 403 for a staff session on a client route and the scoped 404; a recursive JSON walk searching **every key and every value** of every response of every audience for a forbidden token (another customer's `alias`, the `codigo` plaintext, the `prefix`, `caja`, `posicion_real`, `credit_limit`); **the field-set assertion that carries CAC-10** — `test_el_esquema_del_cliente_no_declara_campos_solo_de_personal`, which reads the `EstadoClienteSerializer`'s declared `fields` and fails if it names any of the nine staff-only fields (`caja`, `fiado_pendiente`, `posicion_real`, `buckets`, `credit_limit`, `antiguedad_max_dias`, `suspended_reason`, `codigo`, `prefix`); **the credential RED suite of §5.3, all nine** — `test_codigo_ausente_de_todo_arbol_staff` (R1, the plaintext and the `prefix` are absent from every JSON path of every owner and `dependiente` response), `test_codigo_ausente_de_todo_arbol_cliente` (R2, the plaintext is absent from every JSON path of every client response), `test_codigo_ausente_de_los_logs` (R3, `caplog` over a client request cycle holds no occurrence), `test_codigo_ausente_de_la_url` (R4, `path` and `get_full_path()` never contain the credential and a credential as a query parameter is refused), `test_codigo_ausente_del_cuerpo_de_error` (R5, a forced 422 and a forced 500 carry no part of the credential), `test_codigo_en_claro_no_se_persiste` (R6, no field of any model row holds the plaintext — the only row a client request can create is its own `PagoPropuesto`, whose `importe` and `referencia` are the client's own words), `test_dependiente_ve_cero_credenciales` (R7, every credit-book endpoint answers 403 and **every 200 staff response holds neither `codigo` nor `prefix`**), `test_throttle_no_es_oraculo` (R8, an unknown, a revoked and a throttled credential answer byte-identical payloads) and `test_credential_unicity` (R9, the credential is unique in the shop, one active credential exists per customer and a rotated value refuses the previous one); **plus** `test_cliente_no_crea_cookie`, which asserts the client surface sets no `Set-Cookie` on any response — the client holds no ambient authority; the real `CHECK`, `UNIQUE` and partial unique indexes raising, with the transaction rolling back and leaving no partial row; **the new invariants** — a proposal alone creates no charge and moves no outstanding; the confirmation creates the charge, the lines and the `Confirmacion` in one transaction; a second confirmation appends nothing and answers `propuesta_ya_confirmada`; a cancelled proposal never becomes a charge; a proposal with no lines is refused; a client request writes **no** `LedgerEntry`, `CargoLinea` or `Confirmacion`; a proposed payment writes no `pago`; the races — two concurrent confirmations append exactly **one** `Confirmacion` and one `cargo`; the scopes — a request with both a session and a `codigo` is refused by the client routes and ignored by the staff routes; and the seed, unchanged when run twice.

**15.3 End to end.** Against the **deployed public URL**: HTTPS; one service serving both the pages and the API; `DEBUG=False` and no debug information; the seeded `dueno@tienda.test` and `dependiente@tienda.test` both signing in and landing in their own capability set; the owner's board fetching `/api/v1/posicion/` on the same origin with no cross-origin request; the client page fetching the client API on the same origin; a 403 on the credit book for the `dependiente`; no alias and no `codigo` in any response; and the seeded figures matching.

**15.4 Ordering.** Tests are written **RED first**: the domain unit tests → the model constraints and partial indexes → the API contract → the leak walk → the concurrency tests → the e2e suite.

## 16. Requirement → Design Traceability Matrix

Every row of `requirement-index.md` appears exactly once. `C` marks a conditional requirement; the design element names the section, function, model or contract that satisfies it.

| ID | Requirement | | Design element |
|---|---|---|---|
| CP-01 | Cash movements are recorded and validated | | §3 `CashMovement`; §3.2 rule 12; §9.1 |
| CP-02 | `caja` is recorded cash movements | | §10 `cash_at` |
| CP-03 | `posicion_real` is additive | | §10 `real_position`; ADR-9 |
| CP-04 | The day close is the anchor of `caja` | | §3 `DayClose`; §3.2 rule 13; §10 `caja_al_cierre` |
| CP-05 | The day close is available to both shop roles | | §7 rows 1–2; §9.1 `GET /api/v1/cierre/`; §9.2 close serializers |
| CP-06 | The position rule is pure and ORM-free | | §10 `real_position`; ADR-3 |
| CP-07 | `existencias_registradas` is a ceiling, never a count | C | §2 D5; §10 `existencias_registradas` |
| PA-01 | `outstanding` is derived, never stored | | §10 `outstanding`; §3.1 not-stored; §3.2 rule 19 |
| PA-02 | Payments are allocated FIFO | | §10 `allocate_payments`, `imputations_of`; ADR-7; ADR-26; ADR-27 |
| PA-03 | Ageing buckets are derived per charge | | §10 `bucket_of`, `age_in_days` |
| PA-05 | The credit limit is an explicit state | | §3 `Customer.credit_limit` |
| PA-06 | Suspension is automatic and evaluated on read | | §10 `evaluate_customer`; §2 D1 |
| PA-07 | A suspended customer cannot receive a new charge | | §3.2 rules 1–2, 8; §9.3 |
| PA-08 | The owner can lift a suspension explicitly | | §3 `suspended_override_at`; §9.1 |
| PA-09 | A payment is recorded only by the owner | | §7 `pago` row; §8 (a proposal is a request); §13.3 |
| PA-10 | The ledger write API is validated | | §9.1; §9.3; §3.2 rules 4, 16, 17 |
| PA-11 | The credit rules are pure and ORM-free | | §10; ADR-3 |
| IC-01 | The ledger is append-only | | §3.1 immutability; §9.1 |
| IC-02 | The amount of a `cargo` equals its itemisation total | | §10 `charge_amount_matches`; §3.2 rule 3 |
| IC-03 | A charge exists only after the client confirms it | | §1 idea 3; §6; ADR-19; §3.2 rule 5 |
| IC-04 | The effective confirmation state is derived | | §10 `estado_cargo`; ADR-18 |
| IC-05 | The `cargo` write API is validated | | §9.1; §9.3 |
| IC-06 | The charge rules are pure and ORM-free | | §10 `charges.py`; ADR-3 |
| IC-07 | A `cargo` carries `CargoLinea` rows | C | §3 `CargoLinea`; §3.2 rule 3; §10 |
| IC-08 | `precio_unitario` is a snapshot | C | §3 `CargoLinea`; §2 D8 |
| IC-09 | Charge lines are immutable with their charge | C | §3.1 immutability |
| CAC-01 | Two shop roles exist and are enforced on the server | | §7; ADR-5 |
| CAC-02 | The credit book is owner-only among the staff | | §7.1; §9.2 |
| CAC-03 | No staff session reaches the client surface or gains a client scope | | §8; §7.2 |
| CAC-04 | Sessions and CSRF protect every staff mutation | | §12; §9.1 |
| CAC-05 | The customer record minimises personal data | | §3 `Customer`; §3.1 not-stored |
| CAC-06 | The views consume the application's own API at the public URL | | §11 same-origin; §15.3 |
| CAC-07 | Production is locked and secrets stay out of the repository | | §12; §18.1 |
| CAC-08 | One account per shop role is seeded | | §18.2; §15.3 |
| CAC-09 | The `codigo` is a scoped, per-shop credential | C | §5; §2 D2–D4 |
| CAC-10 | The client payload carries nothing but that customer's own data | C | §9.2 `EstadoClienteSerializer`; §12.1 |
| PC-01 | The catalogue holds only the goods eligible for fiado | | §3 `Producto.activo` |
| PC-02 | `precio` is a default, not a constraint | | §2 D8; §10 `precio_unitario_de` |
| PC-03 | The catalogue is readable and seeded | | §3 `Producto`; §18.2 |
| CC-01 | A charge exists only once the client has confirmed it | C | §6; §9.1 `…/confirmar/`; §13.1; ADR-19, ADR-20 |
| CC-02 | The statement shows every confirmed charge of that client | C | §9.2 `EstadoClienteSerializer` (`pagado`, `saldo`); §13.4; ADR-27 |
| CC-03 | The prepared proposal is shown on the shop's screen | C | §11 `/app/propuesta/{id}`; §9.1 `…/pantalla/`; §9.2 `PropuestaPantallaSerializer` |
| CC-04 | The client may cancel a proposal | C | §6; §9.1 `…/cancelar/`; §13.2 |
| CC-05 | The client view consumes the application's own API | C | §11 same-origin; §15.3 |
| CC-06 | A confirmed charge shows its full itemisation | C | §9.2 `EstadoClienteSerializer` (`lineas[]`); §13.4 |
| CC-07 | The client may propose a payment and the owner records it | C | §7 propose/validate rows; §8; §13.3; §3 `PagoPropuesto`, `ImputacionPago`; ADR-27 |
| CF-01 | The `dependiente` prepares one proposal and records its confirmation | C | §2 D6; §7 proposal rows; §6; §13.1 |
| CF-02 | The facilitator is recorded and holds no client scope | C | §3 `facilitado_por_id`; §8; §13.1 |

**Coverage: 48 of 48.** 15 rows carry the `C` marker, matching the index.

## 17. Threat Matrix

The reference matrix covers shell, subprocess, VCS/PR automation and executable-file classification. This change introduces none of those, so every reference row is an explicit N/A. The boundary it *does* introduce — HTTP routing carrying a bearer credential, and a screen the client reads without a credential — is stated in its place, with the same discipline.

| Reference boundary | Applicability | Reason |
|---|---|---|
| Documentation-like paths | **N/A** | No file, documentation or executable classification exists. `Producto.nombre` is a display string in a table; it is never resolved as a path, never fetched and never executed. |
| Git repository selection | **N/A** | The application invokes no git command and selects no repository; the deploy pipeline is a fixed Render build command. |
| Commit state | **N/A** | No commit, staging or index operation is performed by the application. |
| Push state | **N/A** | The application performs no push; the platform triggers the deployment, not the code. |
| PR commands | **N/A** | The application composes no PR arguments and opens no pull request. |

| Boundary | Expected safe behaviour | Expected failure behaviour | Planned RED tests |
|---|---|---|---|
| The client routes | The scope comes from `X-Codigo` alone; the queryset is built from the resolved customer; the response is built by the client allowlist; **no client route writes to the credit book**. | A missing, unknown, revoked or throttled credential → 422 `codigo_invalido` with no customer data and an identical body in all three cases. | R2, R8, `test_scopes_no_se_mezclan`, `test_cliente_no_escribe_en_la_libreta` |
| The staff routes | The scope comes from the session; `current_shop(request)` filters every queryset. | No session → 403; a `codigo` presented to a staff route is ignored; a customer id outside the shop → a scoped 404. | `test_staff_scope_ignores_codigo`, `test_credit_book_403` |
| A staff session reaching a client route | Refused before any customer data is read. | 403, and the session carries no customer scope. | `test_staff_session_reaches_no_client_endpoint` |
| The shop's screen | The acting scope is the staff session; the payload holds only the one proposal's `desglose` and `total`; the client needs no credential to read it. | A proposal of another shop → 404; a `dependiente` requesting a proposal it did not prepare → 403; a client session → 403. | `test_pantalla_solo_la_propuesta`, `test_pantalla_no_filtra_la_libreta` |
| The proposed payment | A `PagoPropuesto` writes no ledger row; only the owner's validation creates the `pago` and its `ImputacionPago` rows. The proposal names no charge — the FIFO decides. | A proposed amount larger than the customer's outstanding → 422 `pago_excede_deuda`; a double validation → 422 `pago_ya_resuelto` and no second `pago`; imputations that do not add up to the payment → 422 `lineas_descuadradas` and no row written | `test_propuesta_de_pago_no_escribe`, `test_pago_solo_del_dueno`, `test_las_imputaciones_cuadran_con_el_pago` |
| The credential in transit | Header-only; never a URL, a cookie or a body field. | A credential presented any other way is refused; a client response sets no `Set-Cookie`. | R4, `test_cliente_no_crea_cookie` |

## 18. Migration / Rollout

**No migration and no data migration.** The repository contains no application and no database: every table, model and route is created by this change. `migrate` runs the initial migration on an empty database and `seed_demo` populates the demo shop.

### 18.1 The deployment spine (carried from the inherited design)

    GitHub (public) --push--> Render Web Service (free, managed TLS)
       build: pip install -r requirements.txt && npm --prefix frontend ci && npm --prefix frontend run build
              python backend/manage.py collectstatic --noinput && python backend/manage.py migrate --noinput && python backend/manage.py seed_demo
       run:   gunicorn config.wsgi:application --chdir backend --workers 1 --threads 2
       -->   Neon PostgreSQL (free, permanent)   [DATABASE_URL]
    frontend/dist --> STATIC_ROOT --> WhiteNoise --> SAME ORIGIN

- **Neon, not Render's Postgres:** Render's free PostgreSQL expires 30 days after creation; Neon free is permanent — a hard requirement.
- **Env vars:** `DATABASE_URL` (Neon, `sync: false`, mandatory in production), `SECRET_KEY` (generated), `DEBUG=False`, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` (comma separated, the latter **with scheme**), `PYTHON_VERSION`, `NODE_VERSION`. **No new environment variable is introduced.**
- **Availability:** `.github/workflows/keepalive.yml` curls `$PUBLIC_URL/health/` every 8 minutes, under the 10-minute requirement. `/health/` touches **no database**, so a ping never exhausts the pool.

### 18.2 The seed plan extension

`seed_demo` keeps its idempotency contract — one `transaction.atomic()`; users through `get_or_create(username=…)`; the dataset hanging off one `Shop` flagged `is_demo=True`, which the seed deletes and recreates. That deletion is the **only** deletion in the codebase, confined to `is_demo=True`. The extension adds: the catalogue (~30 `Producto` rows, including the seeded product at **1,20 €**, re-runnable without duplicating a row); `CargoLinea` rows with `precio_unitario` snapshots; one `codigo` per seeded customer (hashed, one active each); **one confirmed charge** with its `Confirmacion(confirmado)` and its lines; **one prepared proposal** (`pendiente`) so the shop's screen is demonstrable and the outstanding shows nothing for it; **one cancelled proposal**; and one client with a `codigo`. The facilitation case is seeded only if N5 is confirmed. **Every seeded `pago` is smaller than the debt it retires**, so the seeded dataset obeys rule 19 and no customer holds a credit — the seed is a legal book, not an example of one.

### 18.3 Rollout order

1. The data model and its constraints, with the initial migration.
2. The domain module and its unit tests.
3. The staff surface: shop roles, cash, the ledger, the catalogue.
4. The proposal, the shop's screen and the confirmation.
5. The client credential and the client surface.
6. The proposed payment and, conditionally, the facilitation.
7. The e2e suite against the deployed URL.

Each step is independently deployable. **No feature flag is needed:** the conditional capabilities are absent from the code until their evidence gate closes, so their absence is the flag.

### 18.4 Rollback

Rollback is a redeployment of the previous image. Because the ledger rows — `LedgerEntry`, `CargoLinea`, `Confirmacion`, `PropuestaLinea` — are append-only and never edited, a rollback cannot corrupt a record; and because there are no pre-existing tables, the schema is forward-only with no destructive migration to reverse. `seed_demo` re-seeds the demo shop on the next build.

## 19. Open Questions

None of these blocks the design; each names what would settle it.

**The four Regla gates are decided, not pending.** The validation round with shop owners has not been run, so `proposal.md` takes the gates as **design decisions under a declared hypothesis**: the confirmation is built (Regla 4), the catalogue and `CargoLinea` are built (Regla 5), `existencias_registradas` is included as an optional ceiling (Regla 6), and the conditional facilitation is **not** added (N5). The cut mechanism stays live: a future validation round that contradicts any of these decisions applies exactly the stated reduction, and no rule of the system changes.

| # | Question | What would settle it |
|---|---|---|
| 1 | Does the confirmation survive? The gates are decided under hypothesis: Regla 4 builds the client surface, Regla 5 builds the catalogue and `CargoLinea`, Regla 6 keeps `existencias_registradas` as an optional ceiling, and N5 leaves the conditional facilitation out. | A validation round with shop owners — **not executed**. If Regla 4 empties, the scope becomes `fiado desglosado`: §5, §7.2, §9.1's client routes, §11 client statement, §13.4 and the **10 Regla-4 requirements** (CAC-09, CAC-10, CC-01, CC-02, CC-03, CC-04, CC-05, CC-07, CF-01, CF-02) are cut with it. If Regla 5 empties, `Producto` and `CargoLinea` leave the data model, the `specs/product-catalogue/` directory is deleted in full and the **4 Regla-5 requirements** (CC-06, IC-07, IC-08, IC-09) are cut with it — and the `desglose` becomes a single amount. If Regla 6 empties, `StockMovement` and `existencias_registradas` leave the data model with CP-07 — and because `StockMovement` → `Producto` is a PROTECT foreign key, **Regla 6 cannot be cut while Regla 5 survives**. |
| 2 | Is the shop's screen workable at the counter? The client confirms there, in the shop, in front of the owner. | The owner's reading of the flow: prepare, show, confirm, or decline and cancel. The screen is one route and one component; if the shop prefers a paper slip, the confirmation route stays the same and the UI changes. |
| 3 | Should the client be able to cancel the proposal themselves? Today the client declines in the shop and the **owner** records the cancellation, because the client holds no write scope. | The owner's view of the counter step. If the client must cancel from the portal, the `codigo` would gain a narrow write on `FiadoPropuesto` — an erosion of D9 that the design currently refuses. |
| 4 | The facilitator's human step: the server cannot verify that the person at the counter is the customer the proposal names. | The shop-floor protocol (§12.2, landmine 9) plus rotation. A stronger guarantee would need the client to scan the slip, which is out of scope. |
| 5 | Is rotation an acceptable substitute for re-printing a slip? Hashing makes the slip a consumable (§2 D2). | The owner's answer on whether a slip handed over at the counter can be re-issued on demand. If not, the credential would have to be stored reversibly, with the data-protection cost that implies. |
| 6 | Is the `prefix` worth its 30 bits of residual exposure? A stolen hash plus the prefix leaves 70 bits. | The threat model: one shop, one database, a local attacker. If the operator does not need the prefix, it is removed and the throttle keys on the IP and the shop only. |
| 7 | Should the client ever see their own `credit_limit`? The design says no (§2 D11). | The owner's view of showing a commercial figure to a debtor. CAC-10 stays satisfied either way as long as the field remains absent from the client schema. |
| 8 | When does the `comprobante` land? It is a declared extension, not built (§2 D10, ADR-25). | The owner's need to see a receipt image before validating a payment. When it lands, it must declare file storage, multipart upload, type and size validation, an attachment model and a retention rule (§12.2, landmine 10). |
| 9 | Is the 30-day `serie_caja` chart wanted? Declared cut-line 1 (§11 owner board). | The owner's preference for the chart against the risk ladder. Dropping it removes a React element and no capability. |
