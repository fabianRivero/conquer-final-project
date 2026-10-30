# Design: `fiado confirmado` — the client-ratified `fiado`

> **Language contract.** Prose in English; every domain identifier, entity, field, API field and diagram label stays in the project's Spanish vocabulary (`fiado`, `cargo`, `pago`, `nota de crédito`, `caja`, `dependiente`, `dueño`, `libreta`, `posición real`, `confirmación`, `disputa`, `existencias_registradas`, `codigo`, `posicion_real`, `confirmado_en`, `precio_unitario`, `importe_reclamado`, `facilitado_por`, `credit_limit`, `antiguedad_max_dias`, `suspended_reason`, `vigente`/`envejecido`/`viejo`/`cronico`).

## 1. Technical Approach

One Django 5.2 + DRF service on Render, one Neon PostgreSQL, one Vite/React bundle served by WhiteNoise from the same origin: no second host, no CORS, no worker, no Redis. The `cargo` — an obligation with a counterparty who can attest it — is the unit of record; the catalogue is a vocabulary that prices it; the client page is the attestation surface.

This supersedes the abandoned `tienda-barrio` design (its folder stays untouched) and reuses its spine: append-only ledger, FIFO, ageing, `credit_limit`, automatic suspension, the `dependiente` 403 boundary, session+CSRF staff surface, same-origin mount, additive `posicion_real`, `Decimal`-on-the-wire, the 422 contract, the `seed_demo` plan. It adds a catalogue, `CargoLinea`, a client credential, a confirmation/dispute state machine, a second route and a movement-derived stock ceiling.

**1 — Nothing derived is stored.** Balances, buckets, `antiguedad_max_dias`, the suspension status and its `suspended_reason`, the effective confirmation state and `existencias_registradas` are computed on every read. The one persisted exception is the `suspended_override_at` act: an override is an *event*, not a derived value.

**2 — Two scopes, two mechanisms, never mixed.** Staff scope = the session (`session["shop_id"]` plus a Django group). Client scope = a per-request `codigo` resolved to one `Customer`. No client `User`, group or session, and no upgrade path either way.

**3 — A `cargo` is debt the instant it is recorded; the confirmation is an attestation, never a precondition.** Outstanding, ageing and suspension never read the confirmation state. A client who never opens the page leaves an ordinary `cargo` that ages and suspends. The product degrades to plain `fiado`, never to nothing.

## 2. The Ten Decisions

| # | Decision | Choice | Rejected | Rationale |
|---|---|---|---|---|
| D1 | `Customer.status` | **Derived on read**; only `suspended_override_at`/`_by` persist (an act). | A stored `status` column drifts on the next `pago` and breaks PA-06/IC-04; a worker-reconciled status adds forbidden infrastructure. | A derived state cannot desynchronise. |
| D2 | Credential **storage** | Hashed one-way (PBKDF2-SHA256, per-credential salt) + a 6-symbol `prefix`; the plaintext lives only in the issuing response. | Plaintext — a DB read yields live bearer credentials; reversible encryption — same exposure plus key management. | The DB must not be a credential store. **Consequence:** the slip prints **once**; a lost slip is **rotated**. The revoked value survives only as a fingerprint, so the **owner's** screen says «código rotado». |
| D3 | Credential **transport** | The `X-Codigo` header, every client request, memory only. | A query parameter — history, `Referer`, logs, cache keys. A cookie — a cookie *is* a session and would reach staff routes. A GET body — bodies are not carried by GET. | **CSRF without a session:** the client holds no ambient authority, and `X-Codigo` is a non-simple header a cross-origin form cannot set, with no CORS policy granting it. Plus: client routes refuse a staff session cookie, send `no-store`/`no-referrer`, set no `Set-Cookie`; the staff surface keeps `X-CSRFToken`; a strict CSP covers XSS. |
| D4 | Entropy and throttle | 20 symbols of a 32-symbol unambiguous alphabet = **100 bits**. Throttle: a `CodigoIntento` ledger in PostgreSQL — 10 failures per IP / 15 min, 20 per prefix / 15 min, 500 per shop — always the byte-identical `codigo_invalido` payload. | A 4–6 digit PIN (~20 bits); 8 alphanumeric (~47 bits); a UUID (long fixed format). | The slip carries entropy a spoken code cannot. **No new dependency** — PostgreSQL is already there — and it is never an oracle for which credentials exist. A typo cannot reach 20. |
| D5 | **Stock movement model** | A separate `StockMovement` table; `existencias_registradas = Σ entradas − Σ salidas`; `CargoLinea` quantities are **not** stock movements. | Reusing `CashMovement` — CP-02 sums its amounts into `caja`, so a stock row would corrupt the cash equation. Deriving from `CargoLinea` — a `cargo` is an obligation, not a removal. A physical count — the shop will not adopt it. | The ceiling **drifts downward** (cash sales, breakage, short delivery, `consumo propio`), so the **owner bears the drift**: it over-states stock. It carries a machine-readable qualifier; `stock` is a banned field name; no rule, price, limit or suspension may depend on it, and no endpoint may refuse a `cargo` for lack of stock. |
| D6 | Facilitator's leak boundary | The `dependiente` sees **exactly one charge, in full**: date, amount, its `CargoLinea` itemisation — the artefact the client ratifies — plus that one `alias`. No list, balance, ageing, `credit_limit`, `codigo` or other charge. | The whole credit book for that customer — the 403 boundary the product rests on. A summary row — the helper could not show what the client ratifies. The helper typing the `codigo` — CF-02 forbids it. | One bounded erosion of the 403 boundary: «the notebook stays in the drawer, except for the one page the client is looking at right now». |
| D7 | Double confirmation / double reconciliation | **Both.** Partial unique indexes on `(cargo_id)`: on `Confirmacion` for `estado='confirmado'`, on `Confirmacion` for `estado='en_disputa'`, and on `LedgerEntry` for `kind='nota_credito'`; the service pre-checks in the write transaction to return `cargo_ya_confirmado` / `disputa_abierta`. | A transactional check only — a race double-appends. A DB constraint only — an IntegrityError cannot carry the stable code. A stored `reconciled` flag — a stored derived value. A single index on `Confirmacion` only — it cannot block a second reconciliation, which appends a `LedgerEntry`, not a `Confirmacion`. | The DB makes it impossible; the transaction decides how it is reported. |
| D8 | `precio` deviation rule | The catalogue price is a default the server fills in; an explicit per-line `precio_unitario` wins; `total` is always server-computed. | The catalogue constrains the charge (PC-02 forbids it); an override *mode* adds friction; a `precio_origen` column is a derived value. | No extra friction: the common case types nothing, the uncommon case edits one field. A later catalogue change rewrites no stored line. A non-`activo` `Producto` is not offered but may still be named and stays readable. |
| D9 | The 7-day escalation flag | `revisar` derived on read: `sin_confirmar` and `age_in_days > 7` — the `vigente`/`envejecido` edge; a badge on the owner's ladder. | A stored flag; a scheduled job (ADR-8); an expiry of the confirmation — which would invalidate a real debt or demand a re-issue mechanic. | ADR-8 holds: no worker, no cron. A confirmation never expires; what ages is the flag, and it never changes a balance. |
| D10 | Client sees own `credit_limit`? | **No** — the field is absent from the client schema entirely. | Show it — the limit is the owner's unilateral, revisable policy, so a standing number creates a standing expectation, the exact misunderstanding the product removes. A derived `saldo disponible` — leaks it by arithmetic. In a refusal body — CAC-10 forbids the error body. | Excluding the field makes CAC-10 structural: the value cannot appear because the name cannot appear. |

## 3. Data Model

All tables live in `backend/tienda/models.py`. Money is `Decimal(12,2)`, quantities `Decimal(10,3)`, instants stored in UTC and converted to shop-local calendar days in the service layer.

| Entity | Fields · relations · per-row constraints |
|---|---|
| `Shop` | `name` (unique), `opening_cash` (≥ 0), `currency`, `is_demo`, `usuarios` M2M → `User` |
| `User` | Django `auth.User`, **unmodified**; groups `dueno`, `dependiente`; default `PBKDF2PasswordHasher` |
| `Customer` | → `Shop` CASCADE: `alias`, `phone?`, `credit_limit?` (NULL = «sin límite», else ≥ 0), `suspended_override_at?`, `suspended_override_by_id?`; UNIQUE `(shop_id, alias)` |
| `LedgerEntry` | → `Shop` CASCADE, `Customer`/`User`/`cargo_id` PROTECT: `kind` ∈ {`cargo`,`pago`,`nota_credito`}, `amount` (> 0), `occurred_at` (≤ `created_at`), `cargo_id?` — set **only** by a `nota de crédito` that reconciles a dispute, and omitted by a plain credit note that reduces the outstanding without touching a charge; **partial UNIQUE `(cargo_id) WHERE kind='nota_credito'`** — a charge is reconciled at most once |
| `CargoLinea` | → `LedgerEntry` CASCADE, `Producto` PROTECT: `cantidad` (> 0), `precio_unitario` (≥ 0), `total` = `round(cantidad × precio_unitario, 2)` |
| `CashMovement` | → `Shop` CASCADE, `User` PROTECT: `kind` ∈ {`entrada`,`salida`}, `amount` (> 0), `concept`, `occurred_at` — **server-stamped, never client-supplied** (rule 4 rejects a request that carries it), and the server refuses a stamp in the future |
| `StockMovement` \* | → `Producto` PROTECT: `kind` ∈ {`entrada`,`salida`}, `cantidad` (> 0), `concept`, `occurred_at` — **server-stamped, never client-supplied** (rule 4 rejects a request that carries it) |
| `DayClose` | → `Shop` CASCADE, `User` PROTECT: `date`, `esperado` (≥ 0) — **the server-computed `caja` at close time**, never client-supplied, `contado` (≥ 0), `desviacion` = `esperado − contado`, also server-computed; UNIQUE `(shop_id, date)` |
| `Producto` | → `Shop` CASCADE: `nombre`, `precio` (≥ 0), `unidad`, `activo`; UNIQUE `(shop_id, nombre)` |
| `Confirmacion` | → `LedgerEntry` PROTECT (`cargo_id`, the charge this row ratifies), `User`? PROTECT: `estado` ∈ {`confirmado`,`en_disputa`}, `importe_reclamado?`, `nota?`, `confirmado_en?`, `origen`, `facilitado_por_id?`; `confirmado ⇒ confirmado_en NOT NULL ∧ importe_reclamado IS NULL`; `en_disputa ⇒ importe_reclamado NOT NULL ∧ confirmado_en IS NULL`; `origen='facilitado' ⇔ facilitado_por_id NOT NULL`; **partial UNIQUE `(cargo_id) WHERE estado='confirmado'`** and **partial UNIQUE `(cargo_id) WHERE estado='en_disputa'`** — at most one row per cargo per state, for the whole life of the charge |
| `CustomerCodigo` | → `Customer` CASCADE: `prefix` (6, non-secret), `codigo_hash`, `issued_at`, `issued_by_id`, `revoked_at?`, `revoked_by_id?`; UNIQUE `(shop_id, prefix)`; **partial UNIQUE `(customer_id) WHERE revoked_at IS NULL`** |
| `CodigoIntento` | → `Shop` CASCADE: `source_ip`, `presented_hash`, `at`; append-only |

\* conditional (Regla 6). `StockMovement` → `Producto` is a PROTECT foreign key, so Regla 6 can only be cut together with Regla 5: the catalogue is retained whenever the stock ceiling is.

**Immutability and what is NOT stored.** `LedgerEntry`, `CargoLinea` and `Confirmacion` are append-only: `update()`/`delete()` raise `LedgerImmutableError` and no `PUT`/`PATCH`/`DELETE` route exists for them, so a `CargoLinea` cannot be detached from its `cargo`. The mutable columns are `Customer.alias`/`phone`/`credit_limit` (the owner's own records and policy, edited through `PATCH /api/v1/clientes/{id}/`), `Customer.suspended_override_at`/`_by` and `CustomerCodigo.revoked_at`/`_by` — the last two record an **act** (an override, a rotation), never a derived value. Never stored: `saldo`/balance/`outstanding` · `antiguedad_max_dias` · ageing buckets · `status`/`suspended_reason`/`suspended_at` · any confirmation state on a `cargo` or `Customer` · `caja`/`posicion_real`/`fiado_pendiente`/`serie_caja` · `existencias_registradas` and any field named `stock` · `precio_origen` · a `reconciled` flag · a `revisar` flag · a client `User`, group, session or plaintext `codigo` · a `venta`/`Sale` table, till, drawer balance, receipt, barcode, tender, supplier, purchase order, cost or reorder model.

**Transactional cross-row checks** — server-side, inside `transaction.atomic()`; a `CHECK` sees one row, never an aggregate. Each raises `DomainValidationError` → 422, rolls back, and creates no row and no line.

1. The derived state is `suspendido` → a new `cargo` is refused — `limite_superado` / `antiguedad_superada`.
2. The derived outstanding exceeds `credit_limit` → refused — `limite_superado`.
3. A `cargo` **that declares lines** has `amount ≠ Σ CargoLinea.total` — `lineas_descuadradas`. The check applies only when the charge carries an itemisation: a `cargo` with **no lines** holds its declared amount as its whole total and is accepted as declared, so a line-less charge of 4,20 € is recorded at 4,20 € and its (empty) itemisation total equals it.
4. The request carries `occurred_at` — `campo_no_admitido`.
5. A `nota de crédito` carries a `cargo_id` whose charge carries no `en_disputa` row, or is already reconciled — `disputa_abierta`. Both checks are **row-based**: the charge must hold an `en_disputa` row (not merely read `en_disputa` — a charge whose rows are `[en_disputa, confirmado]` still holds that row and may be reconciled), and reconciliation is read from the `LedgerEntry` side: a `nota de crédito` with that `cargo_id` exists.
6. A `confirmado` targets a charge that already carries a `confirmado` row — `cargo_ya_confirmado`. The check is on the **presence of a `confirmado` row**, not on the charge's effective state: a charge whose rows are `[confirmado, en_disputa]` still carries a `confirmado` row, so it is refused, while a charge whose only row is `en_disputa` may still be confirmed (it appends the first `confirmado` row).
7. An `en_disputa` targets a charge that already carries an `en_disputa` row — `disputa_abierta`.
8. A `DayClose` repeats `(shop_id, date)` — `cierre_duplicado`.
9. A `CustomerCodigo` duplicates `(shop_id, prefix)` or gives a customer a second active credential — `codigo_duplicado`.
10. A `facilitado_por` user is outside the shop or outside the `dependiente` group — `facilitador_invalido`.
11. A client `Confirmacion` targets a `cargo` of another customer — `cargo_ajeno`.
12. A `StockMovement` or `CargoLinea` names a `Producto` outside the shop — `producto_ajeno`.
13. A `CashMovement` would be stamped with an `occurred_at` in the future — refused. The stamp is the server's own clock, so the refusal closes a clock-skew or typo hole rather than a client input; the row is never created.
14. A `DayClose` would store an `esperado` that is not the derived `caja` at close time — refused. `esperado` is computed inside the same transaction from the movements and payments read at that instant, so the close and the figure it anchors can never disagree.
15. A close request carries `esperado` or `desviacion` — refused, `campo_no_admitido`. Rule 14 rejects a value that does not match; this rule rejects the **presence** of the field, so a client-supplied-but-correct `esperado` is refused as well. The close body holds `date` and `contado` only.
16. A ledger entry declares `amount ≤ 0` — refused, `importe_no_positivo`. The DB `CHECK (amount > 0)` on `LedgerEntry` is the backstop; the service validates before writing so the refusal carries this code instead of a bare `IntegrityError`.
17. A ledger entry declares a `kind` outside {`cargo`, `pago`, `nota_credito`} — refused, `tipo_desconocido`. Same two-layer arrangement as rule 16: the service checks the kind against the vocabulary and the DB `CHECK` on the column is the backstop.

**Per-row checks and their codes.** The per-row invariants of §3 are DB `CHECK` constraints, but a `CHECK` raises an `IntegrityError`, not a `codigo_error`. Each one therefore has a service-level twin that validates the same condition **before** the write and raises the contractual code: `amount > 0` → `importe_no_positivo` (rule 16) · `kind ∈ {cargo, pago, nota_credito}` → `tipo_desconocido` (rule 17) · `cantidad > 0` → `importe_no_positivo` · `precio_unitario ≥ 0` → `importe_no_positivo`. The `CHECK` is the backstop under a race; the service check is what the client sees.

## 4. Architecture Decision Records

Context → choice → trade-off → consequence. ADR-1…15 keep the shape of the abandoned `tienda-barrio` design; ADR-16…24 are new to this change.

| # | Context | Choice | Trade-off | Consequence |
|---|---|---|---|---|
| ADR-1 | One service, one origin | React in `STATIC_ROOT`, WhiteNoise | One build step | Two routes, no CORS |
| ADR-2 | Balances must not drift | Every balance is computed from the ledger | Every read pays | All figures are read-time derivations |
| ADR-3 | Testable without a database | `domain/` imports no Django | Plain-value signatures | Unit tests need no DB; an AST test enforces it |
| ADR-4 | Two audiences, one deployable | Session + CSRF for staff, **no** session for the client | Two auth mechanisms | The client is credential-per-request |
| ADR-5 | The permission model | Two groups + `RoleRequired`; the client is **not** a group | The matrix is not one table | The 2×8 shop matrix holds |
| ADR-6 | A leak is a data-protection failure | Serializer allowlist; `fields` is exhaustive | A schema class per audience | The client schema is disjoint from every staff schema; no alias in any path |
| ADR-7 | Fair debt retirement | FIFO by `(occurred_at, id)` | The oldest ages first | The oldest reaches `cronico` before a newer one leaves `vigente` |
| ADR-8 | Deadlines without infrastructure | No Celery, no Redis, no cron; derive on read | No persisted "due" state | The 7-day flag, the buckets and the suspension are read-time |
| ADR-9 | The business equation | `posicion_real = caja + Σ outstanding` | A `pago` moves money, not position | `caja` and `fiado_pendiente` move together |
| ADR-10 | Live figures | Poll `/api/v1/posicion/` every 20 s | Load doubles | No WebSockets; the poll is the keep-alive |
| ADR-11 | Secrets | Demo accounts public; real secrets env-only; the `codigo` is a third class | One more lifecycle | No real secret in the repository |
| ADR-12 | The chart | Hand-rolled SVG, fixed `viewBox` | No interactivity | Small bundle, explainable line by line |
| ADR-13 | Money and quantities | `Decimal`; JSON strings on the wire | The UI parses strings | No float drift |
| ADR-14 | Where a rule lives | Per-row `CHECK`/`UNIQUE`; aggregates in the transaction | Two places to look | The DB backstops rows; the server owns the aggregates |
| ADR-15 | One source of scope — now two | Staff = session; client = the `codigo` | The old rule no longer holds | No client session, no upgrade path |
| ADR-16 | The `codigo` is a bearer secret | Hashed at rest, `X-Codigo` in transit, throttled in PostgreSQL | The slip prints once | Rotation is the re-print path; refusals indistinguishable |
| ADR-17 | The client is a third actor | A credential scoped to one `Customer` | Every auth check needs a split | The 403 boundary survives |
| ADR-18 | The confirmation state | Derived from the `Confirmacion` rows; the latest wins | Every read re-derives it | No drift from the ledger |
| ADR-19 | Reconciling a dispute | A `nota de crédito` carrying `cargo_id` | One nullable FK | No `reconciled` flag; the client sees the correction |
| ADR-20 | Double-appending under a race | Partial unique indexes per state (`Confirmacion.estado='confirmado'`, `Confirmacion.estado='en_disputa'`, `LedgerEntry.kind='nota_credito'`) + transactional pre-checks | Two mechanisms | Impossible in the DB; a stable code from the transaction |
| ADR-21 | Stock without a count | A separate `StockMovement` table | A second movement ledger | The ceiling drifts down and no rule depends on it |
| ADR-22 | The catalogue's job | A vocabulary with a default price; `precio_unitario` is a snapshot | A snapshot that can differ forever | Later price changes rewrite nothing |
| ADR-23 | Adoption friction | The confirmation gates nothing | The confirmation is optional | Without it the product still delivers ledger, FIFO, ageing, suspension |
| ADR-24 | The client's view of the limit | `credit_limit` absent from the client schema | The client cannot self-diagnose | CAC-10 is structural |

## 5. The Client Credential (`codigo`)

| Property | Value |
|---|---|
| Alphabet | `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` — 32 symbols, no `0/O`, no `1/I/L` |
| Length | 20 symbols = **100 bits** (`32^20 ≈ 1.27 × 10^30`), blocked in fours for legibility |
| Presented as | The `X-Codigo` header, every client request, memory only |
| Stored as | PBKDF2-SHA256 hash with a per-credential salt, plus a 6-symbol `prefix` |

The `prefix` is the first 6 symbols, not independent entropy: a stolen hash plus the prefix leaves 70 bits — still infeasible. It is shown only on the owner's screen, never to a `dependiente` or a client.

**At rest** — only the digest; the plaintext exists solely in the issuing response, never persisted, logged or re-rendered. **In transit** — header only: never a query parameter, cookie, body field or URL fragment; client responses send `Cache-Control: no-store` and `Referrer-Policy: no-referrer` and set no `Set-Cookie`. **Verification** — `check_password` against the shop's candidate rows, found by `prefix`; every candidate is compared, so the work does not depend on which one matches. **Throttle** — a `CodigoIntento` ledger (append-only: `shop_id`, `source_ip`, `presented_hash`, `at`): 10 failures per IP / 15 min, 20 per prefix / 15 min, 500 per shop → refused, always with the **byte-identical** `422 / codigo_invalido` payload of an unknown code, so it is never an oracle.

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
| R6 | `test_codigo_en_claro_no_se_persiste` | No field of any model row holds the plaintext |
| R7 | `test_dependiente_ve_cero_credenciales` | Every credit-book endpoint answers 403; every 200 staff response holds neither `codigo` nor `prefix` |
| R8 | `test_throttle_no_es_oraculo` | Unknown, revoked and throttled credentials return byte-identical payloads |
| R9 | `test_credential_unicity` | Unique in the shop; one active credential per customer; a rotated value refuses the old one |

## 6. The Confirmation State Machine

The **effective state** of a `cargo` is derived on read from its `Confirmacion` rows: the **latest** row wins (`confirmacion_efectiva`), and a charge with no row reads `sin_confirmar`. Nothing about this state touches the outstanding, the ageing or the suspension — a `cargo` is debt from the instant it is recorded. A confirmation never expires.

    sin_confirmar ──confirmar──► confirmado
          │                          │
          │_disputar──► en_disputa ◄┘_disputar (a second dispute is refused)
                          │
                          │_confirmar──► confirmado (only if no `confirmado` row yet)
                          │
                          └──reconciliar (dueño: nota de crédito)──► en_disputa + a visible correction

Each arrow appends a row of its own state, and a charge holds **at most one row per state**: a second `confirmado` and a second `en_disputa` are refused, not appended.

| From | To | Driver | Appended | Guard / refusal |
|---|---|---|---|---|
| `sin_confirmar` | `confirmado` | `cliente` | `Confirmacion(confirmado, confirmado_en=now)` | The `cargo` must belong to the customer resolved from the `codigo`, else `cargo_ajeno` |
| `sin_confirmar` | `en_disputa` | `cliente` | `Confirmacion(en_disputa, importe_reclamado, nota?)` | `importe_reclamado` is required; the charge must belong to the customer |
| `en_disputa` | `confirmado` | `cliente` | `Confirmacion(confirmado, …)` | The client accepts the owner's figure and attests to it. **Legal only when the charge holds no `confirmado` row yet** — it appends the first one. A charge that was already confirmed and later disputed cannot be confirmed again (`cargo_ya_confirmado`), so at most one `confirmado` row exists per charge. |
| `confirmado` | `en_disputa` | `cliente` | `Confirmacion(en_disputa, …)` | The dispute is the latest row, so the state becomes `en_disputa`; the earlier `confirmado_en` is kept and shown. Legal only when the charge holds no `en_disputa` row yet — it appends the first one. |
| `en_disputa` | `en_disputa` | `cliente` | — | **Refused** — the dispute slot is occupied: `disputa_abierta` |
| `confirmado` | `confirmado` | `cliente` | — | **Refused** — `cargo_ya_confirmado`; no second `Confirmacion` is appended |
| `en_disputa` | reconciled | `dueño` | `LedgerEntry(nota_credito, cargo_id)` | The amount is `cargo.amount − importe_reclamado`; a second reconciliation is **refused** with `disputa_abierta` |
| `en_disputa` | rejected | `dueño` | **nothing** | The owner asserts the original figure; the state stays `en_disputa` and the outstanding is unchanged |

**Who drives what.** The `cliente` drives only the two client transitions, on their own charges. The `dueño` drives the `cargo`, the `pago`, the `nota de crédito` and the arbitration. The `dependiente` drives **no transition**: it may present exactly one charge and receive the confirmation, recorded with `facilitado_por`, but the `Confirmacion` is still the client's act.

**`disputa_abierta` carries one meaning:** the charge already carries a dispute or a reconciliation, so the requested dispute operation is refused. It covers the second dispute and the second reconciliation, and **each is blocked by its own partial unique index**: a second dispute would append a second `Confirmacion` with `estado='en_disputa'` for the same `cargo_id`, which the index `partial UNIQUE (cargo_id) WHERE estado='en_disputa'` forbids; a second reconciliation would append a second `LedgerEntry` with `kind='nota_credito'` for the same `cargo_id`, which the index `partial UNIQUE (cargo_id) WHERE kind='nota_credito'` forbids. Both refusals are therefore race-proof in the database, and the transactional pre-check supplies the stable `codigo_error` the API contract names.

**Reconciliation never changes the effective state.** A charge reconciled with a `nota de crédito` still reads `en_disputa`; what the client sees instead is the appended correction — exactly the rejection case DR-02 fixes.

## 7. The Permission Matrix

Three principals: the two shop **roles** (Django groups `dueno`, `dependiente`) and the **client** (a bearer credential scoped to one `Customer`). The client is not a role: no `User`, no group, no session.

| Capability | Endpoints | `dueño` | `dependiente` | `cliente` |
|---|---|:---:|:---:|:---:|
| Cash movements and the day close | `POST /api/v1/caja/`, `/cierre/` | Yes | Yes | No |
| The credit book: list, detail, ledger, balances, ageing, `credit_limit` | `GET/POST/PATCH /api/v1/clientes/…` | Yes | **No → 403** | No |
| Create a customer, set `credit_limit`, issue or rotate a `codigo` | `POST /api/v1/clientes/`, `…/codigo/` | Yes | **No → 403** | No |
| Record a `cargo` or a `pago` | `POST …/libreta/` | Yes | **No → 403** | No |
| The risk ladder and `posicion_real` | `GET /api/v1/posicion/` | Yes | **No → 403** | No |
| Lift a suspension | `POST …/suspension/anular/` | Yes | **No → 403** | No |
| Resolve a dispute | `POST …/libreta/` (`nota_credito`) | Yes | **No → 403** | No |
| Users and roles | staff administration | Yes | **No → 403** | No |
| The catalogue (`Producto`) | `GET /api/v1/catalogo/` | Yes | No | No |
| A `StockMovement` | `POST /api/v1/existencias/` | Yes | No | No |
| The client's statement | `GET /api/v1/cliente/estado/` | No | No | Yes — own charges |
| Confirm a charge | `POST /api/v1/cliente/confirmar/` | No | No | Yes — own charges |
| Dispute a charge | `POST /api/v1/cliente/disputar/` | No | No | Yes — own charges |
| Present one charge, receive the confirmation | `POST /api/v1/facilitar/{id}/` | No | Yes — **conditional** (N5) | No |

### 7.1 The `dependiente`'s 403 boundary

Every denied capability answers **403 with no partial data in any field**: no alias, no customer identifier, no `codigo`, no prefix, no count, no distinguishing payload. The refusal is total and server-side — hiding a control is not enforcement. Three structural properties: (1) **scope** — every queryset is filtered by `current_shop(request)`; (2) **allowlist** — `PosicionDependienteSerializer` declares exactly `caja`, `clientes` and `cierre_hoy`, and `clientes` returns `[]` **without executing the customer query**, because the silent query is the classic leak vector; (3) **route shape** — only the `dueño` reaches any credit-book route, and no `PUT`/`PATCH`/`DELETE` exists for a ledger row, so the ledger is append-only at the URL surface too. The conditional facilitation is the single bounded exception: one charge, nothing else (§2 D6).

### 7.2 The client scope as a structural property

The scope comes **only** from the presented `codigo`, resolved to exactly one `Customer` — never from a URL segment, a body field or a session key. A missing or invalid `codigo` yields **422 `codigo_invalido`** with no customer data, no count and no hint. Every client queryset is built from the resolved customer, so a charge outside the scope is refused with `cargo_ajeno` and appends nothing. The client serializer is a **third, disjoint schema class**; a field name shared with either staff schema is a defect, and a test asserts the three field sets are pairwise disjoint. **Invariants:** (1) no client endpoint reads `request.session` for scope, and a request carrying a staff session cookie is refused with 403; (2) no staff endpoint accepts a `codigo` — the only exception is the conditional facilitation route of §13.3, where it is an **attestation input** consumed to attribute a confirmation, never an acting scope; (3) no upgrade in either direction; (4) no response mixes two schema classes.

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

**The invariant that keeps them apart:** *a request resolves to exactly one **acting** scope, and the route decides which.* Staff routes read the session and ignore any `X-Codigo`; client routes read the header and refuse outright a request that carries a staff session cookie. There is no route that accepts both, and no code path merges the two into one principal. The single documented exception is the conditional facilitation route (§13.3): its acting scope is the `dependiente`'s and the `codigo` it carries is an attestation input, never a scope.

Two consequences: **the client never gets a cookie** — client responses set no `Set-Cookie`, so the browser holds no ambient client authority, which is also why the client surface has nothing for CSRF to protect (ADR-4). And **the staff session never names a customer** — the `shop_id` is the whole staff scope; no customer id, no `codigo` and no credit-book selector is ever placed in the session.

Enforcement is by test, not by discipline: a test asserts that `current_shop` and `resolver_credencial` are the only readers of their source, that no view calls both, and that a request presenting both a session and a `codigo` is refused by the client routes and ignored by the staff routes.

## 9. API Contracts

All routes live under `/api/v1/`. Outside it: `GET /health/` (liveness, touching no database) and the HTML mounts `/app/posicion/` and `/app/cliente/`. **No pagination anywhere** — bare JSON lists. `Decimal` crosses the wire as a **string**, instants as ISO-8601.

### 9.1 Routes

| Method | Path | Who | Body | Result |
|---|---|---|---|---|
| GET | `/health/` | public | — | 200 `{"status":"ok"}` |
| GET | `/app/posicion/` | staff | — | 200 HTML + mount + CSRF token; 302 to login |
| GET | `/app/cliente/` | public \* | — | 200 HTML + mount |
| GET | `/api/v1/posicion/` | staff | — | 200 owner or `dependiente` payload; 403 |
| POST | `/api/v1/caja/` | staff | `{kind, concept, amount}` | 201; 422; 403 |
| GET | `/api/v1/cierre/` | staff | — | 200 `{date, esperado, contado, desviacion}` for the `dueño`; 200 `{esperado, contado, desviacion}` for the `dependiente` — the close payload holds to the `dependiente` only those three fields; 403 |
| POST | `/api/v1/cierre/` | staff | `{date, contado}` — a body carrying `esperado` or `desviacion` is refused (rule 15) | 201; 422 `cierre_duplicado`, `campo_no_admitido`; 403 |
| GET | `/api/v1/catalogo/` | `dueño` | — | 200 `Producto[]`, `activo` only; 403 |
| POST | `/api/v1/existencias/` | `dueño` \* | `{producto_id, kind, cantidad, concept}` | 201; 422; 403 |
| GET | `/api/v1/clientes/` | `dueño` | — | 200 `Customer[]`; 403 |
| POST | `/api/v1/clientes/` | `dueño` | `{alias, phone?, credit_limit?}` | 201; 422; 403 |
| GET | `/api/v1/clientes/{id}/` | `dueño` | — | 200 customer + `libreta` + state + override audit; 403; 404 |
| PATCH | `/api/v1/clientes/{id}/` | `dueño` | `{credit_limit}` | 200; 422; 403; 404 |
| POST | `/api/v1/clientes/{id}/codigo/` | `dueño` | — | 201 `{codigo, prefix, issued_at}` — the only time the plaintext exists; 422; 403; 404 |
| POST | `/api/v1/clientes/{id}/libreta/` | `dueño` | `{kind, amount, lineas?[], cargo_id?}` | 201; 422; 403; 404 |
| POST | `/api/v1/clientes/{id}/suspension/anular/` | `dueño` | `{}` | 200; 403; 404 |
| POST | `/api/v1/facilitar/{cargo_id}/` | `dependiente` \* | `{codigo}` — the code the **client** typed | 201 `Confirmacion` with `facilitado_por`; 422; 403; 404 |
| GET | `/api/v1/cliente/estado/` | `cliente` \* | `X-Codigo` | 200 statement; 422; 403 |
| GET | `/api/v1/cliente/cargos/{id}/` | `cliente` \* | `X-Codigo` | 200 the `Confirmar` action payload, with the itemisation; 422; 403 |
| POST | `/api/v1/cliente/confirmar/` | `cliente` \* | `X-Codigo` + `{cargo_id}` | 201 `{confirmado_en, estado}`; 422; 403 |
| POST | `/api/v1/cliente/disputar/` | `cliente` \* | `X-Codigo` + `{cargo_id, importe_reclamado, nota?}` | 201; 422; 403 |

\* conditional. The five client routes are gated by **Regla 4** (the whole client surface); `POST /api/v1/existencias/` by **Regla 6**; `POST /api/v1/facilitar/{cargo_id}/` by **N5**. No `PUT`, `PATCH` or `DELETE` route exists for `LedgerEntry`, `CargoLinea` or `Confirmacion`: the ledger is append-only at the URL surface too.

### 9.2 The serializer allowlist per audience

Five schema classes; DRF's `fields` is exhaustive, so "no alias in ANY JSON path" is a schema property, not a promise. They are **not** pairwise disjoint: the two staff position classes share `caja`, `clientes` and `cierre_hoy`, and the two close classes share `esperado`, `contado` and `desviacion` — the `dependiente` is a shop role, not an outsider, and CP-05 requires it to read the close. The property that carries the leak guarantee is narrower and is the one tested: **the client class is disjoint from every staff class** — `EstadoClienteSerializer` shares no field with `PosicionDuenoSerializer`, `PosicionDependienteSerializer`, `CierreDuenoSerializer` or `CierreDependienteSerializer`. That is what CAC-10 requires, and it is what §12's test asserts.

| Class | Declared | Absent |
|---|---|---|
| `PosicionDuenoSerializer` | `caja`, `fiado_pendiente`, `posicion_real`, `buckets`, `clientes[]`, `serie_caja[]`, `cierre_hoy` | — |
| `PosicionDependienteSerializer` | `caja`, `clientes` (a `SerializerMethodField` returning `[]` **without executing the customer query**), `cierre_hoy` | `fiado_pendiente`, `posicion_real`, `buckets`, `alias`, `credit_limit`, `antiguedad_max_dias`, `codigo`, `prefix` |
| `EstadoClienteSerializer` | `alias`, `total`, `cargos[]` — each: `id`, `fecha`, `amount`, `estado`, `confirmado_en` (only when the charge carries a `confirmado` row), `lineas[]` (**only** when the charge carries a `confirmado` row) — each line: `producto` (the `Producto.nombre`), `cantidad`, `precio_unitario`, `total`; `disputa` (only when disputed) — `importe_reclamado`, `nota?`, and `correccion` (the appended `nota de crédito` amount, when the owner has reconciled the dispute) | `credit_limit`, `caja`, `posicion_real`, `buckets`, `antiguedad_max_dias`, `suspended_reason`, `codigo`, `prefix`, any other customer's data, any pagination metadata |
| `CierreDuenoSerializer` | `date`, `esperado`, `contado`, `desviacion` | — |
| `CierreDependienteSerializer` | `esperado`, `contado`, `desviacion` | `date` — the close payload holds to the `dependiente` only those three fields |

**The unconfirmed-charge rule.** The `lineas` key is **omitted entirely** — not returned empty — for any charge that carries **no `confirmado` row**, so no line of that charge appears in the statement, in any aggregate or in any error body. The itemisation is disclosed only through `GET /api/v1/cliente/cargos/{id}/` and through the statement once the charge carries a `confirmado` row.

The gate is on the **presence of a `confirmado` row**, not on the effective state, for the same reason every other guard in §3 is row-based: a charge whose rows are `[confirmado, en_disputa]` was ratified by the client and keeps its itemisation visible — §6 keeps the earlier `confirmado_en` visible for the same reason — while a charge whose rows are `[en_disputa]` alone has never been ratified and its lines stay hidden. The effective state alone would strip the lines of an already-ratified charge, contradicting CC-06.

### 9.3 Error codes

Every validation failure is **HTTP 422** with the fixed shape `{"codigo_error": "<code>", "detail": "<Spanish message>"}`. The vocabulary: `limite_superado` (the outstanding exceeds `credit_limit`) · `antiguedad_superada` (the oldest unpaid charge is over 30 days) · `importe_no_positivo` (a non-positive amount, quantity or price — §3 rules 16 and the per-row checks) · `campo_no_admitido` (the request carried `occurred_at`, `esperado`, `desviacion` or another forbidden field — §3 rules 4, 15) · `tipo_desconocido` (a `kind` outside the vocabulary — §3 rule 17) · `cierre_duplicado` · `lineas_descuadradas` · `cargo_ya_confirmado` · `disputa_abierta` (the charge already carries a dispute or a reconciliation) · `codigo_invalido` (missing, unknown, revoked or throttled) · `codigo_duplicado` · `cargo_ajeno` · `producto_ajeno` · `facilitador_invalido`.

Every code in that list is produced by a named rule: `limite_superado` → rules 1–2 · `importe_no_positivo` → rule 16 · `campo_no_admitido` → rules 4 and 15 · `tipo_desconocido` → rule 17 · `cierre_duplicado` → rule 8 · `lineas_descuadradas` → rule 3 · `cargo_ya_confirmado` → rule 6 · `disputa_abierta` → rules 5 and 7 · `codigo_duplicado` → rule 9 · `facilitador_invalido` → rule 10 · `cargo_ajeno` → rule 11 · `producto_ajeno` → rule 12 · `antiguedad_superada` → rule 1 · `codigo_invalido` → §5's credential resolution.

**403 responses carry no request data:** a fixed `{"codigo_error": "permiso_insuficiente", "detail": "…"}` and nothing else — no alias, no customer identifier, no `codigo`, no count.

## 10. The Pure Rules Module

`backend/tienda/domain/` imports **no Django, no DRF and no app module** — enforced by `backend/tests/unit/test_domain_is_orm_free.py`, which AST-parses every file in the package and fails on a forbidden import. Plain values in, plain values out: no ORM objects, no database, no request, and **no implicit clock** — the caller passes `at`. The service layer is the only place that converts UTC to shop-local calendar days, so a "day" is a calendar day of the shop.

**Types** (`domain/types.py`): `EntryKind` (`cargo`/`pago`/`nota_credito`), `Bucket` (`vigente`/`envejecido`/`viejo`/`cronico`), `SuspensionReason` (`limite_superado`/`antiguedad_superada`), `ConfirmState` (`sin_confirmar`/`confirmado`/`en_disputa`), `StockQualifier` (`techo_no_conteo`), and the plain records `LedgerLine`, `CargoLine`, `CashLine`, `StockLine`, `Allocation`, `CustomerState`, `ConfirmacionRow`, `ChargeState`.

| Module | Function · signature | Guarantee |
|---|---|---|
| `allocation.py` | `allocate_payments(charges, payments, *, credit_notes=()) -> Allocation` | FIFO by `(occurred_at, id)`; a credit imputes only to a charge with `charge.occurred_at ≤ credit.occurred_at`; the surplus stays as `residual` |
| `ageing.py` | `bucket_of(age_days: int) -> Bucket` | `vigente` ≤ 7 d, `envejecido` 8–30, `viejo` 31–90, `cronico` > 90. Each unpaid charge is bucketed by **its own** age, and the four bucket totals **sum exactly to the outstanding** — the buckets are a partition of the same charges, never a separate figure |
| `ageing.py` | `age_in_days(occurred_at, at) -> int` | The calendar-day difference; the values arrive shop-local |
| `evaluation.py` | `evaluate_customer(lines, *, credit_limit, at, suspension_age_days=30, override=False) -> CustomerState` | The derived state; `credit_limit=None` means «sin límite» and never fires `limite_superado`; `override=True` lifts the automatic suspension |
| `evaluation.py` | `antiguedad_max_dias(charges, payments, at) -> int` | The age of the oldest unpaid charge; drives the suspension and the ladder order |
| `position.py` | `real_position(caja, outstanding_total) -> Decimal` | `posicion_real = caja + Σ pending balances`, additive only |
| `position.py` | `outstanding(lines, at) -> Decimal` | `Σ cargos − Σ pagos − Σ notas` over `occurred_at ≤ at`; a negative result is `credit_a_favor`, not an error |
| `position.py` | `cash_at(opening_cash, movements, pagos, at) -> Decimal` | `caja = inicial + Σ(entradas) − Σ(salidas) + Σ(pagos)` over `occurred_at ≤ at` |
| `charges.py` | `total_de_linea(cantidad, precio_unitario) -> Decimal` | `round(cantidad × precio_unitario, 2)` — the rounding rule the DB `CHECK` mirrors |
| `charges.py` | `precio_unitario_de(precio_catalogo, precio_solicitado) -> Decimal` | The override wins when present, otherwise the catalogue price — the deviation rule, with no extra friction |
| `charges.py` | `charge_amount_matches(lines, declared_amount) -> bool` | Whether the declared amount equals `Σ lineas.total` — the source of `lineas_descuadradas`. **A charge with no lines matches any declared amount**: an empty `lines` sequence is a legal, line-less charge whose whole total is its declared amount, so the comparison is vacuously true and the charge is accepted as declared |
| `confirmation.py` | `confirmacion_efectiva(rows) -> ConfirmacionRow \| None` | The latest row, or `None` |
| `confirmation.py` | `estado_cargo(rows) -> ChargeState` | `confirmado`, `en_disputa` or `sin_confirmar`; no stored state is consulted. **A read-time projection only** — it is never the guard for a write; the write guards use the row presence, per `transicion_permitida` |
| `confirmation.py` | `transicion_permitida(origen, destino, *, filas, ya_reconciliada) -> str \| None` | `None` when allowed, otherwise the refusal `codigo_error`. `filas` is the charge's full `Confirmacion` history: the guard for a `confirmado` destination is the **presence of a `confirmado` row**, and for an `en_disputa` destination the presence of an `en_disputa` row — never the effective state alone, because a charge whose rows are `[confirmado, en_disputa]` still reads `en_disputa` yet may not be confirmed again |
| `confirmation.py` | `escalado_sin_confirmar(estado, occurred_at, at, *, dias=7) -> bool` | `estado is sin_confirmar and age_in_days(occurred_at, at) > dias`; the flag is derived, never stored |
| `stock.py` | `existencias_registradas(movements) -> tuple[Decimal, StockQualifier]` | `Σ entradas − Σ salidas` and the qualifier `techo_no_conteo`; no rule is attached to it |
| `cash.py` | `desviacion_cierre(esperado, contado) -> Decimal` | `esperado − contado`, the value stored in the `DayClose` |
| `cash.py` | `caja_al_cierre(opening_cash, movements, pagos, at) -> Decimal` | The derived `caja` at the close instant — the value stored as `DayClose.esperado`. It is the same computation as `cash_at`, called with `at` = the close instant; the caller never supplies it, so `esperado` cannot be client-supplied |

**The guarantee.** Every rule above is a total function over plain values. A unit test may call any of them with a hand-computed fixture and no database at all — pytest-django raises `RuntimeError: Database access not allowed` for any ORM call in a test without the `django_db` marker, so the layer is DB-free **by construction**, not by convention.

## 11. The Two React Surfaces

One Vite bundle, one origin, two routes, two credential modes. No CORS, no second host, no second URL, no hard-coded figure, no charting library.

```
frontend/src/
├── main.tsx, router.tsx        the mount and the two routes
├── api/http.ts                 the ONLY place a URL is built; asserts a relative path
├── api/staff.ts                session + X-CSRFToken
├── api/cliente.ts              X-Codigo only; no credentials sent
├── surfaces/Posicion.tsx       /app/posicion
├── surfaces/Cliente.tsx        /app/cliente
└── components/                 Ecuacion, Escalera, Cinta, Cierre, ConfirmarAccion, Acceso, Disputar, Credenciales
```

**The same-origin contract.** Every request uses a **relative path** (`/api/v1/…`); the single fetch helper rejects any absolute URL, so a second host cannot be introduced by accident. Staff requests send `credentials: 'same-origin'` and `X-CSRFToken` on every mutation; client requests send `credentials: 'omit'` — the client has no cookie to send, and sending one would blur the two scopes. No third-party script, no external font, no analytics: the client page carries a credential, so a strict CSP (`default-src 'self'`) is set on its mount. The API is served by the same deployable service, over HTTPS.

**`/app/posicion` — the owner board.** `Ecuacion`: `caja + fiado_pendiente = posicion_real` with the bucket breakdown. `Escalera`: the risk ladder, customers with `pendiente > 0`, sorted by `antiguedad_max_dias` **descending**, each row with `alias`, `pendiente`, `antiguedad_max_dias`, the derived state, the `suspended_reason` and the per-charge confirmation states. `Cinta`: the four ageing ribbons. `Revisar`: the badge on a `sin_confirmar` charge older than 7 days — derived on read, never stored. `Cierre`: `esperado`, `contado`, `desviacion` and the close form. `Serie`: the 30-day `serie_caja` chart — **declared cut-line 1**, droppable without touching a capability. `Credenciales`: issue or rotate a `codigo`, show the `prefix` and the rotation date, the plaintext only in the issuing response. The board polls `/api/v1/posicion/` every 20 s; the poll doubles as the keep-alive.

**`/app/cliente` — the client statement.** `Acceso`: one credential field, `autocomplete="off"`, React state only, cleared on navigation. `Estado`: the total owed, then one row per charge — date, amount, effective state. `ConfirmarAccion`: opens `/api/v1/cliente/cargos/{id}/` and shows the itemisation **there**, then posts the confirmation; the statement itself never carries the lines of an unconfirmed charge. `Disputar`: `importe_reclamado` and an optional note. `Historial`: the dispute, its claim and the appended correction. The client page does **not** poll — a poll would multiply the credential's exposure for no benefit.

## 12. Security Architecture

**Three independent layers.** A leak must fail all three; none relies on the others. (1) **View level** — `RoleRequired`/`IsDueno`/`EsCliente` on every view; a denied principal gets **403 with no partial data**; every queryset is scoped by `current_shop(request)` and every client queryset is built from the customer resolved from the credential. (2) **Serializer allowlist** — the client schema is disjoint from every staff schema, so "no alias in ANY JSON path" is a schema property, not a promise. (3) **Scope resolution** — two different helpers, and no view calls both, so a principal can never hold two scopes.

**Sessions and CSRF.** Django session + `SessionAuthentication` on the staff surface; every staff mutation carries `X-CSRFToken`, and a missing or invalid token is refused with 403 and creates no row. The client surface has no session, so there is nothing for CSRF to forge: `X-Codigo` is a non-simple header a cross-origin request cannot set, and no CORS policy grants it (§2 D3).

**Passwords and secrets.** Django's default `PBKDF2PasswordHasher` (`pbkdf2_sha256`, 1 000 000 iterations) is not overridden. `SECRET_KEY` and `DATABASE_URL` are environment-only; `DEBUG=False` in production; `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` come from the environment; every dependency is pinned to an exact version. The demo accounts are public by design — the demo password is not a secret.

### 12.1 Data-protection failure modes

| Failure mode | Control |
|---|---|
| Nested-aggregate leak | Disjoint allowlists; no staff serializer reaches a related customer object |
| Metadata leak — pagination counts, `total`, `next` | No pagination anywhere; bare JSON lists |
| Error-body echo | The 422 vocabulary is fixed; no submitted value is ever echoed |
| The silent query — clean payload, query still ran | The `dependiente` `clientes` field returns `[]` **without executing the customer query** |
| The hand-maintained contract | A test asserts the client field set is disjoint from each of the four staff field sets |
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
9. **The itemisation of an unconfirmed charge leaking into the statement** → the `lineas` key is **omitted**, not emptied; the test asserts the key's absence.
10. **The two scopes bleeding into one request** → the facilitation route is the only place a session and a `codigo` meet; it returns no client payload and creates no client scope.
11. **A stored derived value creeping back** (`saldo`, `status`, `stock`, a confirmation state) → the ORM-free AST test plus a test asserting the absence of every forbidden field name.
12. **A `CargoLinea` being detached or edited** → the model refuses updates and deletes, and no route exposes either.
13. **The throttle becoming an oracle** → unknown, revoked and throttled credentials return byte-identical payloads (§5.3 R8).

## 13. Data Flow

### 13.1 The confirmation flow

```
Cliente           API (cliente)                DB
 | teclea el codigo |                            |
 |---------------->| resolver_credencial -> check_password
 |                 | 1 Customer; estado_cargo(rows)
 |<----------------| statement; `lineas` OMITTED if unconfirmed
 | abre Confirmar  | GET .../cargos/{id}/ -> the itemisation
 |---------------->|                              |
 | confirma        | POST .../confirmar/ {cargo_id}
  |---------------->| atomic: no 'confirmado' row for this cargo_id else 422 cargo_ya_confirmado;
  |                 |        cargo.customer==resolved else 422 cargo_ajeno;
  |                 |        INSERT Confirmacion(confirmado, confirmado_en=now)
 |<----------------| 201 {confirmado_en, estado}
```

The `cargo` row is never touched and the outstanding is unchanged.

### 13.2 The dispute flow

```
Cliente          API (cliente)        API (dueño)              DB
 | POST .../disputar/ {cargo_id, importe_reclamado, nota?}      |
 |------------------------->|                                   |
  |                          | atomic: no 'en_disputa' row for this cargo_id else 422 disputa_abierta;
  |                          |   INSERT Confirmacion(en_disputa,
  |                          |   importe_reclamado); the cargo is NOT modified
 |<-------------------------| 201 dispute                        |
 |                          | GET /clientes/{id}/ -> en_disputa + claim
 |                          | POST .../libreta/ {kind:nota_credito,
 |                          |   amount: 6,40-4,20=2,20, cargo_id}
 |                          |---------------------------------->|
  |                          | atomic: an 'en_disputa' row exists for this cargo_id and it is
  |                          |   not already reconciled, else 422 disputa_abierta;
  |                          |   INSERT LedgerEntry(nota_credito, cargo_id)
 |                          | 201 -> outstanding 4,20; the cargo row unchanged
 | GET .../estado/ -> en_disputa + the appended correccion 2,20
```

The rejection path appends **nothing**: the owner asserts the original figure, the outstanding stays 6,40 € and the state stays `en_disputa`.

### 13.3 The facilitator flow *(conditional, N5)*

```
dependiente (shop device)    Cliente         API (staff route)     DB
 | session: shop_id + grupo dependiente |                        |
 | presenta UN cargo ---------> ve el cargo |                     |
 |-----------------------------------------|-------->|             |
 |                             | teclea SU codigo              |
 | POST .../facilitar/{cargo_id}/ {codigo} + session               |
 |------------------------------------------------>|             |
  |                                             | resolver_credencial -> 1 Customer;
  |                                             | the session NEVER becomes a client scope;
  |                                             | atomic: cargo.customer==resolved else 422 cargo_ajeno;
  |                                             |   no 'confirmado' row for this cargo_id else 422 cargo_ya_confirmado;
  |                                             |   INSERT Confirmacion(confirmado,
  |                                             |   origen=facilitado, facilitado_por=<user>)
 |                                             | 201: only THAT charge; no list, no balance,
 |                                             |   no ageing, no codigo
```

The facilitator's session never acquires a client scope: the `codigo` is an **attestation input** consumed to attribute the confirmation, never an acting scope. Without the client's credential no confirmation can be created — the helper cannot fabricate one. The client is the one who types the code on the shop's device, in front of the facilitator; that human step is a shop-floor protocol the server cannot verify, and it is stated here rather than implied away.

## 14. File Changes

The repository holds no implementation yet — this change creates the whole application. Every path below is **created**; nothing is modified and nothing is deleted.

| Path | What |
|---|---|
| `requirements.txt`, `.gitignore`, `render.yaml` | Pinned dependencies; the ignores; the Render blueprint (build and run commands, env vars, `sync: false`) |
| `.github/workflows/ci.yml` | A `postgres:16` service running the unit and integration suites |
| `.github/workflows/keepalive.yml` | `curl -fsS "$PUBLIC_URL/health/"` every 8 minutes, plus `workflow_dispatch` |
| `backend/manage.py`, `backend/pytest.ini` | The entry point; the pytest configuration with the `unit`/`integration`/`e2e` markers |
| `backend/config/{settings,urls,wsgi}.py` | `INSTALLED_APPS`, `REST_FRAMEWORK` with the 422 handler, `STATIC_ROOT`, env-only secrets, `DEBUG=False`, the strict CSP; the mounts; the WSGI app |
| `backend/tienda/models.py`, `backend/tienda/migrations/0001_initial.py` | The twelve entities of §3; every `CHECK`, `UNIQUE` and partial index |
| `backend/tienda/domain/{types,position,allocation,ageing,evaluation,charges,confirmation,stock,cash}.py` | The pure rules of §10 — **no Django import anywhere in the package** |
| `backend/tienda/services.py` | The only ORM-touching layer: rows → plain values → `domain/` → writes inside `transaction.atomic()` |
| `backend/tienda/api/{exceptions,permissions,client_auth,throttle}.py` | The 422/403 handler; `RoleRequired`/`IsDueno`/`EsCliente`; `resolver_credencial`; the throttle ledger |
| `backend/tienda/api/serializers/{staff,cliente}.py` | The two staff allowlists, the two close allowlists and the client schema, which is disjoint from all of them |
| `backend/tienda/api/{views,urls}.py` | The routes of §9.1 and their URL map |
| `backend/tienda/management/commands/seed_demo.py` | The idempotent demo dataset of §18.2 |
| `backend/tests/unit/test_*.py` | `test_domain_is_orm_free` plus one file per pure rule, with no database |
| `backend/tests/integration/test_*.py` | The cash, ledger, catalogue, permissions, no-leak, client, facilitation, constraints and seed suites |
| `backend/tests/e2e/test_public_url.py` | The deployed URL: HTTPS, `DEBUG=False`, login, the same-origin fetch, the seeded accounts |
| `frontend/{package.json,vite.config.ts,tsconfig.json,index.html}` | The Vite + React + TypeScript build; the output lands in `STATIC_ROOT` |
| `frontend/src/{main.tsx,router.tsx,api/{http,staff,cliente}.ts,surfaces/{Posicion,Cliente}.tsx,components/}` | The mount, the two routes, the three fetch layers, the two surfaces and the components `Ecuacion`, `Escalera`, `Cinta`, `Cierre`, `ConfirmarAccion`, `Acceso`, `Disputar`, `Credenciales` |

Package markers (`__init__.py`) are implied. `openspec/changes/tienda-barrio/` and `openspec/explorations/` are not touched, and nothing is written under `openspec/specs/`.

## 15. Testing Strategy

The specs declare three verification levels; the suite has one layer per level, and every one of the 53 requirements is covered by the layer its index declares.

| Level | Requirements | Where | Database |
|---|---|---|---|
| `unit` | CP-02, CP-03, CP-06, CP-07, IC-03, IC-04, IC-06, PA-01, PA-02, PA-03, PA-04, PA-06, PA-11 — **13** | `backend/tests/unit/` | **none**, by construction |
| `integration` | CAC-01…CAC-05, CAC-08…CAC-10, CC-01…CC-04, CC-06, CC-07, CF-01, CF-02, CP-01…CP-05, CP-07, DR-01…DR-04, IC-01…IC-05, IC-07…IC-09, PA-01, PA-03…PA-10, PC-01…PC-03 — **46** | `backend/tests/integration/` | **PostgreSQL 16** |
| `e2e` | CAC-06, CAC-07, CAC-08, CC-05 — **4** | `backend/tests/e2e/` | the deployed public URL |

**53 distinct requirements, 63 layer entries.** The suite has one layer per level, and every one of the 53 requirements is covered by the layer its index declares. Ten requirements legitimately span two layers — the nine `unit, integration` ones (CP-02, CP-03, CP-07, IC-03, IC-04, PA-01, PA-03, PA-04, PA-06) and CAC-08 (`integration, e2e`) — so the entries sum to 63 while the requirements covered are 53, each covered at least once.

**15.1 Unit.** The pure functions of §10 run against hand-computed fixtures with **no database at all**: pytest-django raises `RuntimeError: Database access not allowed` for any ORM call in a test without the `django_db` marker, so the DB-free property is enforced, not asserted. The bucket boundaries, the FIFO order, the partial payment, the overpayment residual, the disputed-charge ageing, the derived suspension and its lifting, the `precio` override, the `lineas_descuadradas` decision, the state machine, the 7-day flag and the stock ceiling are checked here; `test_domain_is_orm_free.py` AST-parses every file of `domain/`.

**15.2 Integration.** The Django test client against **PostgreSQL**, never SQLite — landmine 7. It proves: the 422 payload and every `codigo_error`, with a refused write creating no row and no line; the 2×8 matrix, the credit-book 403, the 403 for a staff session on a client route and the scoped 404; a recursive JSON walk searching **every key and every value** of every response of every audience for a forbidden token (another customer's `alias`, the `codigo` plaintext, the `prefix`, `caja`, `posicion_real`, `credit_limit`); the real `CHECK`, `UNIQUE` and partial unique indexes raising, with the transaction rolling back and leaving no partial row; the races — two concurrent confirmations append exactly **one** `Confirmacion`, two concurrent disputes append exactly **one** `Confirmacion(en_disputa)`, two concurrent reconciliations exactly **one** `nota de crédito`, and a confirmation racing a dispute on the same charge leaves at most one row per state, which is what ADR-20 exists for; the scopes — a request with both a session and a `codigo` is refused by the client routes and ignored by the staff routes; and the seed, unchanged when run twice.

**15.3 End to end.** Against the **deployed public URL**: HTTPS; one service serving both the pages and the API; `DEBUG=False` and no debug information; the seeded `dueno@tienda.test` and `dependiente@tienda.test` both signing in and landing in their own capability set; the owner's board fetching `/api/v1/posicion/` on the same origin with no cross-origin request; the client page fetching the client API on the same origin; a 403 on the credit book for the `dependiente`; no alias and no `codigo` in any response; and the seeded figures matching.

**15.4 Ordering.** Tests are written **RED first**: the domain unit tests → the model constraints and partial indexes → the API contract → the leak walk → the concurrency tests → the e2e suite. Each RED test names the requirement it proves.

## 16. Requirement → Design Traceability Matrix

Every row of `requirement-index.md` appears exactly once. `C` marks a conditional requirement; the design element names the section, function, model or contract that satisfies it.

| ID | Requirement | | Design element |
|---|---|---|---|
| CP-01 | Cash movements are recorded and validated | | §3 `CashMovement`; §3 rule 13 (the future stamp); §9.1 |
| CP-02 | `caja` is recorded cash movements | | §10 `cash_at` |
| CP-03 | `posicion_real` is additive | | §10 `real_position`; ADR-9 |
| CP-04 | The day close is the anchor of `caja` | | §3 `DayClose`; §3 rule 14 (the derived `esperado`); §10 `caja_al_cierre`, `desviacion_cierre` |
| CP-05 | The day close is available to both shop roles | | §7 rows 1–2; §9.1 `GET /api/v1/cierre/`; §9.2 `CierreDuenoSerializer`, `CierreDependienteSerializer` |
| CP-06 | The position rule is pure and ORM-free | | §10 `real_position`; ADR-3 |
| CP-07 | `existencias_registradas` is a ceiling, never a count | C | §2 D5; §10 `existencias_registradas` |
| PA-01 | `outstanding` is derived, never stored | | §10 `outstanding`; §3 not-stored |
| PA-02 | Payments are allocated FIFO | | §10 `allocate_payments`; ADR-7 |
| PA-03 | Ageing buckets are derived per charge | | §10 `bucket_of` (per-charge age; the four totals sum exactly to the outstanding), `age_in_days` |
| PA-04 | A disputed charge is debt, not a credit | | §10 `outstanding`; §6 |
| PA-05 | The credit limit is an explicit state | | §3 `Customer.credit_limit` |
| PA-06 | Suspension is automatic and evaluated on read | | §10 `evaluate_customer`; §2 D1 |
| PA-07 | A suspended customer cannot receive a new charge | | §3 rules 1–2; §9.3 |
| PA-08 | The owner can lift a suspension explicitly | | §3 `suspended_override_at`; §9.1 |
| PA-09 | A correction is appended as a `nota de crédito` | | §3 `LedgerEntry.kind`; ADR-19 |
| PA-10 | The ledger write API is validated | | §9.1; §9.3; §3 rules 4, 16 and 17 (`occurred_at` refused, `importe_no_positivo`, `tipo_desconocido`) |
| PA-11 | The credit rules are pure and ORM-free | | §10; ADR-3 |
| IC-01 | The ledger is append-only | | §3 immutability; §9.1 |
| IC-02 | The amount of a `cargo` equals its itemisation total | | §10 `charge_amount_matches`; §3 rule 3 (and the line-less cargo it preserves) |
| IC-03 | A `cargo` never depends on the confirmation | | §1 idea 3; ADR-23 |
| IC-04 | The effective confirmation state is derived | | §10 `estado_cargo`, `confirmacion_efectiva`; ADR-18 |
| IC-05 | The `cargo` write API is validated | | §9.1; §9.3 |
| IC-06 | The charge rules are pure and ORM-free | | §10 `charges.py`; ADR-3 |
| IC-07 | A `cargo` carries `CargoLinea` rows | C | §3 `CargoLinea`; §10 |
| IC-08 | `precio_unitario` is a snapshot | C | §3 `CargoLinea`; §2 D8 |
| IC-09 | Charge lines are immutable with their charge | C | §3 immutability |
| CAC-01 | Two shop roles exist and are enforced on the server | | §7; ADR-5 |
| CAC-02 | The credit book is owner-only among the staff | | §7.1; §9.2 |
| CAC-03 | No staff session reaches the client surface or gains a client scope | | §8; §7.2; §13.3 |
| CAC-04 | Sessions and CSRF protect every staff mutation | | §12; §9.1 |
| CAC-05 | The customer record minimises personal data | | §3 `Customer`; §3 not-stored |
| CAC-06 | The views consume the application's own API at the public URL | | §11 same-origin contract; §15.3 |
| CAC-07 | Production is locked and secrets stay out of the repository | | §12; §18.1 |
| CAC-08 | One account per shop role is seeded | | §18.2; §15.3 |
| CAC-09 | The `codigo` is a scoped, per-shop credential | C | §5; §2 D2–D4 |
| CAC-10 | The client payload carries nothing but that customer's own data | C | §9.2 `EstadoClienteSerializer` |
| PC-01 | The catalogue holds only the goods eligible for fiado | | §3 `Producto.activo` |
| PC-02 | `precio` is a default, not a constraint | | §2 D8; §10 |
| PC-03 | The catalogue is readable and seeded | | §3 `Producto`; §18.2 |
| CC-01 | The client confirms their own charge | C | §6; §9.1 |
| CC-02 | The statement shows every charge of that client | C | §9.2; §13.1 |
| CC-03 | An unconfirmed charge is a summary row with a `Confirmar` action | C | §9.2; §11 client statement |
| CC-04 | The client may dispute a charge | C | §6; §9.1 |
| CC-05 | The client view consumes the application's own API | C | §11 same-origin contract; §15.3 |
| CC-06 | A confirmed charge shows its full itemisation | C | §9.2 `EstadoClienteSerializer` (`lineas[]` when the charge carries a `confirmado` row) |
| CC-07 | The itemisation of an unconfirmed charge is revealed only inside the action | C | §9.2 (the unconfirmed-charge rule: the key is omitted, not emptied); §9.1; landmine 9 |
| DR-01 | A dispute is recorded without touching the charge | C | §6; §13.2 |
| DR-02 | The owner arbitrates the dispute | C | §6; §13.2 |
| DR-03 | A dispute is reconciled at most once | C | §2 D7; ADR-20 |
| DR-04 | The client sees the dispute and its resolution | C | §9.2; §13.2 |
| CF-01 | The `dependiente` presents one charge and receives the confirmation | C | §2 D6; §7; §13.3 |
| CF-02 | The facilitator is recorded and holds no client scope | C | §3 `facilitado_por`; §8; §13.3 |

**Coverage: 53 of 53.** 19 rows carry the `C` marker, matching the index.

## 17. Threat Matrix

The reference matrix covers shell, subprocess, VCS/PR automation and executable-file classification. This change introduces none of those, so every reference row is an explicit N/A. The boundary it *does* introduce — HTTP routing carrying a bearer credential — is stated in its place, with the same discipline: expected safe behaviour, expected failure behaviour and a planned RED test.

| Reference boundary | Applicability | Reason |
|---|---|---|
| Documentation-like paths | **N/A** | No file, documentation or executable classification exists. `Producto.nombre` is a display string in a table; it is never resolved as a path, never fetched and never executed. |
| Git repository selection | **N/A** | The application invokes no git command and selects no repository; the deploy pipeline is a fixed Render build command. |
| Commit state | **N/A** | No commit, staging or index operation is performed by the application. |
| Push state | **N/A** | The application performs no push; the platform triggers the deployment, not the code. |
| PR commands | **N/A** | The application composes no PR arguments and opens no pull request. |

| Boundary | Expected safe behaviour | Expected failure behaviour | Planned RED tests |
|---|---|---|---|
| The client routes | The scope comes from `X-Codigo` alone; the queryset is built from the resolved customer; the response is built by the client allowlist. | A missing, unknown, revoked or throttled credential → 422 `codigo_invalido` with no customer data and an identical body in all three cases. | R2, R8, `test_scopes_no_se_mezclan` |
| The staff routes | The scope comes from the session; `current_shop(request)` filters every queryset. | No session → 403; a `codigo` presented to a staff route is ignored; a customer id outside the shop → a scoped 404. | `test_staff_scope_ignores_codigo`, `test_credit_book_403` |
| A staff session reaching a client route | Refused before any customer data is read. | 403, and the session carries no customer scope. | `test_staff_session_reaches_no_client_endpoint` |
| The facilitation route *(conditional)* | The acting scope is the `dependiente`'s; the `codigo` is an attestation input only; the response carries that one charge and nothing else. | No credential, or one belonging to another customer → 422 and no `Confirmacion`; a charge already confirmed → 422 `cargo_ya_confirmado` and no `Confirmacion`; a `dependiente` of another shop → 403. | `backend/tests/integration/test_facilitation_api.py` |
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

`seed_demo` keeps its idempotency contract — one `transaction.atomic()`; users through `get_or_create(username=…)`; the dataset hanging off one `Shop` flagged `is_demo=True`, which the seed deletes and recreates. That deletion is the **only** deletion in the codebase, confined to `is_demo=True`. The extension adds: the catalogue (~30 `Producto` rows, including the seeded product at **1,20 €**, re-runnable without duplicating a row); `CargoLinea` rows with `precio_unitario` snapshots; one `codigo` per seeded customer (hashed, one active each); one `en_disputa` charge; one `sin_confirmar` charge older than 7 days, so the `revisar` badge is visible; and most charges `confirmado`. The facilitation case is seeded only if N5 is confirmed — otherwise the capability is not built at all.

### 18.3 Rollout order

1. The data model and its constraints, with the initial migration.
2. The domain module and its unit tests.
3. The staff surface: shop roles, cash, the ledger, the catalogue.
4. The client credential and the client surface.
5. The dispute path and, conditionally, the facilitation.
6. The e2e suite against the deployed URL.

Each step is independently deployable. **No feature flag is needed:** the conditional capabilities are absent from the code until their evidence gate closes, so their absence is the flag.

### 18.4 Rollback

Rollback is a redeployment of the previous image. Because the ledger is append-only and no row is ever edited, a rollback cannot corrupt a record — and because there are no pre-existing tables, the schema is forward-only with no destructive migration to reverse. `seed_demo` re-seeds the demo shop on the next build.

## 19. Open Questions

None of these blocks the design; each names what would settle it.

**The four Regla gates are decided, not pending.** The validation round with shop owners has not been run, so `proposal.md` takes the gates as **design decisions under a declared hypothesis** rather than as interview findings: the confirmation is built (Regla 4), the catalogue and `CargoLinea` are built (Regla 5), `existencias_registradas` is included as an optional ceiling (Regla 6), and the conditional facilitation capability is **not** added (N5). The cut mechanism below stays live: a future validation round that contradicts any of these decisions applies exactly the stated reduction, and no rule of the system changes.

| # | Question | What would settle it |
|---|---|---|
| 1 | Does the confirmation survive? The gates are decided under hypothesis: Regla 4 builds the client surface, Regla 5 builds the catalogue and `CargoLinea`, Regla 6 keeps `existencias_registradas` as an optional ceiling, and N5 leaves the conditional facilitation out. | A validation round with shop owners, using the instrument in `evidence-annex.md` — **not executed**. If Regla 4 empties, the scope becomes `fiado desglosado` and §5, §6, §7.2, §9.1's client routes, §11 client statement, §13.1, §13.3 and the 13 Regla-4 requirements are cut with it. If Regla 5 empties, `Producto` and `CargoLinea` leave the data model, the `specs/product-catalogue/` directory is deleted in full and the 5 Regla-5 requirements are cut with it. If Regla 6 empties, `StockMovement` and `existencias_registradas` leave the data model with CP-07 — and because `StockMovement` → `Producto` is a PROTECT foreign key, **Regla 6 cannot be cut while Regla 5 survives**: the two gates are ordered, and the catalogue is kept whenever the stock ceiling is. |
| 2 | Is 7 days the right escalation threshold? The design fixes it at the `vigente`/`envejecido` edge. | The owner's reading of a week without a confirmation. The constant lives in one pure function, so changing it is one edit. |
| 3 | Is rotation an acceptable substitute for re-printing a slip? Hashing makes the slip a consumable (§2 D2). | The owner's answer on whether a slip handed over at the counter can be re-issued on demand. If not, the credential would have to be stored reversibly, with the data-protection cost that implies. |
| 4 | The facilitator's human step: the server cannot verify who typed the `codigo`. | The shop-floor protocol plus rotation (§13.3). A stronger guarantee would need the client to scan the slip, which is out of scope. |
| 5 | Is the `prefix` worth its 30 bits of residual exposure? A stolen hash plus the prefix leaves 70 bits. | The threat model: one shop, one database, a local attacker. If the operator does not need the prefix, it is removed and the throttle keys on the IP and the shop only. |
| 6 | Should the client ever see their own `credit_limit`? The design says no (§2 D10). | The owner's view of showing a commercial figure to a debtor. CAC-10 stays satisfied either way as long as the field remains absent from the client schema. |
| 7 | Is the 30-day `serie_caja` chart wanted? Declared cut-line 1 (§11 owner board). | The owner's preference for the chart against the risk ladder. Dropping it removes a React element and no capability. |
