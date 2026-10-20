# cash-position Specification

## Purpose

The `caja`, the `posición real` once the `fiado` is counted, and the close of the day comparing expected with counted cash. Every figure is derived, never stored.

## Requirements

### Requirement: CP-01 — Cash movements are recorded and validated

A `CashMovement` MUST be an `entrada` or a `salida` with `amount > 0`, a concept, an `occurred_at` not in the future and a recorded author; both roles MUST record one.

**Verification:** integration

#### Scenario: The dependiente records a cash movement

- GIVEN a `dependiente` account
- WHEN an `entrada` of 20,00 € is recorded
- THEN it is accepted and attributed to that author

#### Scenario: A non-positive amount is rejected

- GIVEN a movement form with `amount = 0`
- WHEN it is submitted
- THEN the request is rejected and no `CashMovement` is created

### Requirement: CP-02 — The cash on hand is derived

`caja` MUST equal `opening_cash + Σ(entradas) − Σ(salidas) + Σ(pagos)`, recomputed on every read; a customer payment MUST be recorded once, as a `pago`, and MUST NOT also be a `CashMovement`.

**Verification:** unit, integration

#### Scenario: A payment raises the drawer

- GIVEN a `caja` of 412,35 € and a customer payment of 20,00 €
- WHEN the payment is recorded as a `pago`
- THEN `caja` is 432,35 € and no `CashMovement` was created for it

#### Scenario: The drawer follows the movements

- GIVEN an opening cash of 150,00 €, movements of +45,00 € and −20,00 €, no `pagos`
- WHEN the position is read
- THEN `caja` is 175,00 €

### Requirement: CP-03 — The real position is the cash plus the credit given away

`posicion_real` MUST equal `caja + Σ outstanding`, recomputed on every read, and the response MUST return the breakdown (`caja`, `fiado_pendiente`, ageing buckets) beside the total; a `pago` MUST raise `caja` and lower `fiado pendiente` equally, so `posicion_real` MUST stay unchanged.

**Verification:** unit, integration

#### Scenario: A payment converts money without creating it

- GIVEN a `cargo` of 20,00 € 45 days old, a `cargo` of 10,00 € 10 days old, `credit_limit = null`, `caja` 412,35 €
- WHEN the owner records a `pago` of 20,00 €
- THEN FIFO retires the 45-day charge, 10,00 € stays unpaid, `antiguedad_max_dias` is 10, the customer is `activo` again, `caja` is 432,35 € and `posicion_real` is unchanged at 442,35 €

#### Scenario: The seeded position adds up

- GIVEN `caja` of 412,35 € and `fiado pendiente` of 268,90 €
- WHEN the position is read
- THEN `posicion_real` is 681,25 € and the breakdown is returned with the total

### Requirement: CP-04 — The day close stores expected, counted and deviation

A `DayClose` MUST store `esperado`, `contado` and `desviacion`; `esperado` MUST be the derived `caja` at close time, `desviacion` MUST be the server-computed `esperado − contado`, neither MAY be client-supplied, and the date MUST be unique per shop.

**Verification:** integration

#### Scenario: The deviation is computed and stored

- GIVEN the derived `caja` of 412,35 €
- WHEN the owner saves a close with `contado` of 408,00 €
- THEN `esperado` is 412,35 € and `desviacion` is −4,35 €, visible in the owner's view

#### Scenario: A second close for the same date is rejected

- GIVEN a close already exists for that shop and date
- WHEN another close for the same date is saved
- THEN the database rejects it for uniqueness of the date

### Requirement: CP-05 — The day close is available to both roles

The `dependiente` MUST be able to record the day close, and the close endpoint MUST return to the `dependiente` only `esperado`, `contado` and `desviacion`.

**Verification:** integration

#### Scenario: The dependiente closes the day

- GIVEN a `dependiente` account
- WHEN the close for today is saved and read back
- THEN it succeeds and the payload holds only `esperado`, `contado` and `desviacion`

### Requirement: CP-06 — The position rule is pure and unit-testable

`real_position` MUST be a pure function over plain values with no ORM access, so it is verifiable by a unit test that runs without a database.

**Verification:** unit

#### Scenario: The position rule is exercised without a database

- GIVEN a `caja` value and a total outstanding value
- WHEN `real_position` is applied to them
- THEN the result is their sum and no database is needed
