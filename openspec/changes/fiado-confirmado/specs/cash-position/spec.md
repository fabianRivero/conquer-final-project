# cash-position Specification

## Purpose

The `caja`, the `posición real` once the `fiado` is counted, the day close that anchors the drawer, and — conditionally — the `existencias_registradas` ceiling. Every figure is derived on read.

## Requirements

### Requirement: CP-01 — Cash movements are recorded and validated

A `CashMovement` MUST be an `entrada` or a `salida` with `amount > 0`, a concept, an `occurred_at` not in the future and a recorded author; both shop roles MUST be able to record one.

**Verification:** integration

#### Scenario: The `dependiente` records a cash movement

- GIVEN a `dependiente` account
- WHEN an `entrada` of 20,00 € is recorded
- THEN it is accepted and attributed to that author

#### Scenario: A non-positive amount is rejected

- GIVEN a movement form with `amount = 0`
- WHEN it is submitted
- THEN the request is refused with HTTP 422 and no `CashMovement` is created

### Requirement: CP-02 — `caja` is recorded cash movements

`caja` MUST equal `opening_cash + Σ(entradas) − Σ(salidas) + Σ(pagos)`, recomputed on every read; a customer payment MUST be recorded once, as a `pago`, and MUST NOT also be a `CashMovement`.

**Verification:** unit, integration

#### Scenario: A payment raises the drawer exactly once

- GIVEN a `caja` of 412,35 € and a customer payment of 20,00 €
- WHEN the payment is recorded as a `pago`
- THEN `caja` is 432,35 € and no `CashMovement` was created for it

#### Scenario: The drawer follows the movements

- GIVEN an opening cash of 150,00 €, movements of +45,00 € and −20,00 €, no `pagos`
- WHEN the position is read
- THEN `caja` is 175,00 €

### Requirement: CP-03 — `posicion_real` is additive

`posicion_real` MUST equal `caja + Σ outstanding`, recomputed on every read, and the response MUST return the breakdown (`caja`, `fiado_pendiente`, ageing buckets) beside the total; a `pago` MUST raise `caja` and lower `fiado_pendiente` by the same amount, so `posicion_real` MUST stay unchanged.

**Verification:** unit, integration

#### Scenario: A payment converts money without creating it

- GIVEN `caja` of 412,35 €, a `cargo` of 20,00 € and a `pago` of 20,00 €
- WHEN the position is read
- THEN `caja` is 432,35 €, `fiado_pendiente` is 0,00 € and `posicion_real` is unchanged at 432,35 €

#### Scenario: The seeded position adds up

- GIVEN `caja` of 412,35 € and `fiado_pendiente` of 268,90 €
- WHEN the position is read
- THEN `posicion_real` is 681,25 € and the breakdown is returned with the total

### Requirement: CP-04 — The day close is the anchor of `caja`

A `DayClose` MUST store `esperado`, `contado` and `desviacion`; `esperado` MUST be the derived `caja` at close time, `desviacion` MUST be the server-computed `esperado − contado`, neither MAY be client-supplied, and the date MUST be unique per shop. It is the only instrument that measures the shop's money and MUST NOT be removed while `caja` remains.

**Verification:** integration

#### Scenario: The deviation is computed and stored

- GIVEN the derived `caja` of 412,35 €
- WHEN the owner saves a close with `contado` of 408,00 €
- THEN `esperado` is 412,35 €, `desviacion` is −4,35 € and both are readable

#### Scenario: A second close for the same date is rejected

- GIVEN a close already exists for that shop and date
- WHEN another close for the same date is saved
- THEN it is refused with HTTP 422 `cierre_duplicado` and no `DayClose` is created

### Requirement: CP-05 — The day close is available to both shop roles

The `dependiente` MUST be able to record the day close, and the close payload MUST hold to the `dependiente` only `esperado`, `contado` and `desviacion`.

**Verification:** integration

#### Scenario: The `dependiente` closes the day

- GIVEN a `dependiente` account
- WHEN the close for today is saved and read back
- THEN it succeeds and the payload holds only `esperado`, `contado` and `desviacion`

### Requirement: CP-06 — The position rule is pure and ORM-free

`real_position` MUST be a pure function over plain values with no ORM access, so it is verifiable by a unit test that runs without a database.

**Verification:** unit

#### Scenario: The position rule is exercised without a database

- GIVEN a `caja` value and a total outstanding value
- WHEN `real_position` is applied to them
- THEN the result is their sum and no database is needed

## Conditional Requirements

### Requirement: CP-07 — `existencias_registradas` is a ceiling, never a count

**Conditional:** Regla 6 — if it empties, `existencias_registradas` is cut entirely and the drift problem leaves the scope.

`existencias_registradas` MUST equal `Σ entradas − Σ salidas registradas` over the recorded product movements; it MUST travel with a machine-readable qualifier stating that it is an upper bound; NO rule, price, limit or suspension anywhere MAY depend on it; NO endpoint MAY refuse a `cargo` for lack of stock; and the field name `stock` MUST NOT be used for it.

**Verification:** unit, integration

#### Scenario: The ceiling travels with its qualifier

- GIVEN recorded movements giving `existencias_registradas` of 12
- WHEN the figure is read
- THEN it is returned with its ceiling qualifier and no field named `stock` exists

#### Scenario: A `cargo` is never refused for lack of stock

- GIVEN a `Producto` whose `existencias_registradas` is 0
- WHEN a `cargo` naming it is recorded
- THEN the `cargo` is accepted and no row is refused for stock
