# Data Model Index — `fiado-confirmado` Phase 2 (v2 model)

**Extracted verbatim from `design.md` §3. The contract for the models. Do not re-derive it and do not invent a field.**

## The entity table, verbatim

```
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
| `ImputacionPago` | → `LedgerEntry` PROTECT (`pago`, the payment that brought the money), `LedgerEntry` PROTECT (`cargo`, the charge it retires): `importe` (> 0). **One row per (payment, charge) pair the payment touches.** A payment that retires three charges writes three rows |
| `CustomerCodigo` | → `Customer` CASCADE, `User` PROTECT (`issued_by_id`, the user who issued the credential), `User`? PROTECT (`revoked_by_id?`, the user who revoked it): `prefix` (6, non-secret), `codigo_hash`, `issued_at`, `revoked_at?` |
| `CodigoIntento` | → `Shop` CASCADE: `source_ip`, `presented_hash`, `at`; append-only |

\* conditional (Regla 6). `StockMovement` → `Producto` is a PROTECT foreign key, so Regla 6 can only be cut together with Regla 5.

**Per-row constraints.** `amount > 0` and `kind ∈ {cargo,pago}` on `LedgerEntry` · `cantidad > 0`, `precio_unitario ≥ 0`, `total = round(cantidad × precio_unitario, 2)` on `CargoLinea` and `PropuestaLinea` · `estado ∈ {confirmado}` and `confirmado_en NOT NULL` on `Confirmacion` · `origen='facilitado' ⇔ facilitado_por_id NOT NULL` · `credit_limit ≥ 0` or NULL on `Customer` · CHECK `confirmado ⇒ confirmed_at NOT NULL` and `cancelado ⇒ canceled_at NOT NULL` on `FiadoPropuesto` · CHECK `validado ⇒ resolved_at NOT NULL ∧ resolved_by_id NOT NULL` and `rechazado ⇒ resolved_at NOT NULL ∧ resolved_by_id NOT NULL` on `PagoPropuesto` · CHECK `importe > 0` on `ImputacionPago`.

**Unique and partial-unique constraints.** **partial UNIQUE `(customer_id) WHERE estado='pendiente'`** on `FiadoPropuesto` — at most one live proposal per customer · **partial UNIQUE `(cargo_id) WHERE estado='confirmado'`** on `Confirmacion` — at most one confirmation per charge · **partial UNIQUE `(customer_id) WHERE revoked_at IS NULL`** on `CustomerCodigo` · **UNIQUE `(pago_id, cargo_id)`** on `ImputacionPago` — one payment cannot touch the same charge twice · UNIQUE `(shop_id, alias)` on `Customer`, `(shop_id, nombre)` on `Producto`, `(shop_id, date)` on `DayClose`, `(shop_id, prefix)` on `CustomerCodigo`.

**Sixteen entities** (twelve before, plus `FiadoPropuesto`, `PropuestaLinea`, `PagoPropuesto` and `ImputacionPago`). `LEDGER_ENTRY_KINDS` has **two** values: `cargo`, `pago`. The five constraints that are gone — `uniq_confirmacion_one_disputa_per_cargo`, `uniq_ledgerentry_one_reconciliation_per_cargo`, `chk_ledgerentry_cargo_only_on_credit_note`, `chk_confirmacion_state_fields`, `chk_confirmacion_importe_non_negative` — and the two partial indexes that went with them. `LedgerEntry.cargo_id` and `Confirmacion.importe_reclamado` are gone.

```

## The transactional rules, verbatim

```
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
| 19 | **A `pago` exceeds the outstanding it retires.** The shop returns the excess as change; it never enters the book, so no credit can exist and the outstanding can never be negative. **The outstanding is the customer's total**, not one charge's: the payment imputes FIFO against the customer's open charges, so the bound is the sum of what the customer owes | `pago_excede_deuda` |
| 20 | **An `ImputacionPago` names something that is not a charge.** The `cargo` side must be a `LedgerEntry` with `kind='cargo'`; the `pago` side must have `kind='pago'` | `tipo_desconocido` |
| 21 | **The imputations of a payment do not add up to the payment.** `Σ ImputacionPago.importe` over one payment MUST equal that payment's `amount`, and `Σ` over one charge MUST NOT exceed that charge's `amount`. Both are checked in the transaction that writes the rows | `lineas_descuadradas` |

**Per-row checks and their codes.** The per-row invariants are DB `CHECK` constraints, but a `CHECK` raises an `IntegrityError`, not a `codigo_error`. Each one therefore has a service-level twin that validates the same condition **before** the write: `amount > 0` → `importe_no_positivo` · `kind ∈ {cargo, pago}` → `tipo_desconocido` · `cantidad > 0` and `precio_unitario ≥ 0` → `importe_no_positivo`. The `CHECK` is the backstop under a race; the service check is what the client sees.

```

## What the model must NOT store

```
Never stored: `saldo`/balance/`outstanding` · `antiguedad_max_dias` · ageing buckets · `status`/`suspended_reason`/`suspended_at` · any confirmation state on a `cargo` or `Customer` · `caja`/`posicion_real`/`fiado_pendiente`/`serie_caja` · `existencias_registradas` and any field named `stock` · `precio_origen` · a `reconciled` flag · a `revisar` flag · an `importe_reclamado` · a `nota de crédito` · a client `User`, group, session or plaintext `codigo` · a `venta`/`Sale` table, till, drawer balance, receipt, barcode, tender, supplier, purchase order, cost or reorder model · a `comprobante` attachment.
```

## The two mutable rows

```
```