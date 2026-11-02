# Domain Rules Index — `fiado-confirmado` Phase 3

**Extracted verbatim from `design.md` §10, plus the acceptance criteria from the specs.**
This is the contract for the pure rules. Do not re-derive it, do not invent a rule, and do not add a
parameter the table does not list.

## The hard constraint

`backend/tienda/domain/` imports **no Django, no DRF and no app module**. This is not a convention: 
`backend/tests/unit/test_domain_is_orm_free.py` AST-parses every file of the package and fails on a
forbidden import. Plain values in, plain values out — no ORM objects, no database, no request, and **no
implicit clock**: the caller always passes `at`.

## Design §10, verbatim

```
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

```

## The acceptance criteria each rule must satisfy

Read the spec scenario before writing the rule. The column is the requirement the rule serves.

| Requirement | What it demands | Rule that serves it |
|---|---|---|
| CP-02 | `caja` equals `opening_cash + Σ(entradas) − Σ(salidas) + Σ(pagos)`; a `pago` is never a `CashMovement` | `position.cash_at` |
| CP-03 | `posicion_real` equals `caja + Σ outstanding`, recomputed on every read, and a `pago` leaves it unchanged | `position.real_position`, `position.outstanding` |
| CP-04 | the close stores the derived `caja` as `esperado` and `esperado − contado` as `desviacion` | `cash.caja_al_cierre`, `cash.desviacion_cierre` |
| CP-06 | `real_position` is a pure function over plain values, verifiable without a database | `position.real_position` |
| CP-07 | `existencias_registradas` is `Σ entradas − Σ salidas`, carries a ceiling qualifier, and no rule depends on it | `stock.existencias_registradas` |
| PA-01 | `outstanding` is derived, never stored | `position.outstanding` |
| PA-02 | payments are allocated FIFO by `(occurred_at, id)`; the surplus stays as a residual | `allocation.allocate_payments` |
| PA-03 | each unpaid charge is bucketed by its own age and the four totals sum exactly to the outstanding | `ageing.bucket_of`, `ageing.age_in_days` |
| PA-04 | a disputed charge is still debt, not a credit | `position.outstanding` |
| PA-05 | the credit limit is an explicit state, `NULL` meaning «sin límite» | `evaluation.evaluate_customer` |
| PA-06 | suspension is automatic and evaluated on read | `evaluation.evaluate_customer` |
| PA-11 | the credit rules are pure and ORM-free | the whole package |
| IC-02 | the amount of a `cargo` equals its itemisation total; a line-less charge keeps its declared amount | `charges.charge_amount_matches`, `charges.total_de_linea` |
| IC-03 | the confirmation state is derived from the `Confirmacion` rows | `confirmation.estado_cargo`, `confirmation.confirmacion_efectiva` |
| IC-04 | the effective state is derived, never stored | `confirmation.estado_cargo` |
| IC-06 | the `CargoLinea` total is `round(cantidad × precio_unitario, 2)`, the rule the DB `CHECK` mirrors | `charges.total_de_linea` |
| PC-02 | the catalogue price is the default and an explicit `precio_unitario` wins | `charges.precio_unitario_de` |

## The boundaries the tests must pin

- `ageing.bucket_of`: `vigente` ≤ 7 d, `envejecido` 8–30, `viejo` 31–90, `cronico` > 90. The test walks 7/8, 30/31 and 90/91.
- `charges.total_de_linea`: `round(cantidad × precio_unitario, 2)` — the same rounding the database `CHECK` uses, so a line and its total can never disagree.
- `charges.precio_unitario_de`: the override wins when present, otherwise the catalogue price.
- `charges.charge_amount_matches`: a charge with **no lines matches any declared amount** — an empty `lines` sequence is a legal line-less charge.
- `evaluation.evaluate_customer`: `credit_limit=None` never fires `limite_superado`; `override=True` lifts the automatic suspension.
- `confirmation.transicion_permitida`: the guard for a `confirmado` destination is the **presence of a `confirmado` row**, never the effective state alone. A charge whose rows are `[confirmado, en_disputa]` may not be confirmed again.
- `confirmation.estado_cargo`: a read-time projection only — it is never the guard for a write.
- `confirmation.escalado_sin_confirmar`: `estado is sin_confirmar and age_in_days(occurred_at, at) > dias`; the flag is derived, never stored.
- `position.outstanding`: `Σ cargos − Σ pagos − Σ notas` over `occurred_at ≤ at`; a negative result is `credit_a_favor`, not an error.
- `position.cash_at`: `caja = inicial + Σ(entradas) − Σ(salidas) + Σ(pagos)` over `occurred_at ≤ at`.
- `stock.existencias_registradas`: returns the figure **and** the `techo_no_conteo` qualifier; no rule is attached to it.
- `cash.caja_al_cierre`: the same computation as `cash_at` with `at` = the close instant; the caller never supplies `esperado`.

## The guard that the whole slice rests on

`pytest-django` raises `RuntimeError: Database access not allowed` for any ORM call in a test without the
`django_db` marker. The domain layer is therefore DB-free **by construction**, not by convention: if a
rule touched the ORM, its test would fail rather than pass silently.
