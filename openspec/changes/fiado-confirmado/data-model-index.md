# Data Model Index — `fiado-confirmado` Phase 2

**Extracted verbatim from `design.md` §3. This is the contract for the models. Do not re-derive it, do not invent fields, and do not add a field the table does not list.**

## The twelve entities, with their fields and constraints

```
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

```

## Rules that the model must enforce

The seventeen transactional rules live in the same block. Every one that concerns a
per-row constraint is marked below with the constraint it implies, so the model
carries it as a database guarantee and not only as a service check.

| # | Rule | Per-row implication |
|---|---|---|
| 1 | see the rules block above | none — derived state, checked in the service |
| 2 | see the rules block above | none — derived, checked in the service |
| 3 | see the rules block above | CHECK on the cargo amount against the sum of its lines |
| 4 | see the rules block above | none — the field is refused at the API boundary |
| 5 | see the rules block above | partial UNIQUE on the reconciling credit note per cargo |
| 6 | see the rules block above | partial UNIQUE on the confirmed row per cargo |
| 7 | see the rules block above | partial UNIQUE on the disputed row per cargo |
| 8 | see the rules block above | UNIQUE (shop, date) on the day close |
| 9 | see the rules block above | UNIQUE (shop, prefix) and partial UNIQUE per customer |
| 10 | see the rules block above | foreign key to a user in the shop |
| 11 | see the rules block above | foreign key to the customer of the charge |
| 12 | see the rules block above | foreign key to the product of the line |
| 13 | see the rules block above | none — the stamp is refused at the service boundary |
| 14 | see the rules block above | none — the close computes it |
| 15 | see the rules block above | none — the field is refused at the API boundary |
| 16 | see the rules block above | CHECK (amount > 0) |
| 17 | see the rules block above | CHECK (kind IN the vocabulary) |

## What the model must NOT store

`saldo`, `balance`, `outstanding`, `antiguedad_max_dias`, ageing buckets, `status`,
`suspended_reason`, `suspended_at`, any confirmation state on a `cargo` or a
`Customer`, `caja`, `posicion_real`, `fiado_pendiente`, `serie_caja`,
`existencias_registradas` and any field named `stock`, `precio_origen`, a
`reconciled` flag, a `revisar` flag, a client `User`, group, session or plaintext
`codigo`, and any sale, till, receipt, barcode, tender, supplier or purchase-order
model.

## The three immutable tables

`LedgerEntry`, `CargoLinea` and `Confirmacion` are append-only: `save()` refuses an
update and `delete()` raises. No `PUT`, `PATCH` or `DELETE` route exists for them.

## The credential is not a column of `Customer`

`CustomerCodigo` holds it: `prefix` (6, non-secret), `codigo_hash`, `issued_at`,
`issued_by_id`, `revoked_at?`, `revoked_by_id?`, with UNIQUE (shop, prefix) and a
partial UNIQUE per customer that admits only one unrevoked credential.

## `CodigoIntento`

The append-only throttle ledger: `source_ip`, `presented_hash`, `at`.
