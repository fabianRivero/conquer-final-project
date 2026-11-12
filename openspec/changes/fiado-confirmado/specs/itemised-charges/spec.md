# itemised-charges Specification

## Purpose

The `cargo` as an itemised obligation: the `CargoLinea` rows that name what was taken, the price snapshot that freezes it, and the `LedgerEntry` that carries the amount.

A charge is not an intention the owner records and hopes the client accepts. The owner prepares a `FiadoPropuesto`; the client confirms it; and only then does the charge exist, always with its itemisation.

## Requirements

### Requirement: IC-01 — The ledger is append-only

No `LedgerEntry`, `CargoLinea` or `Confirmacion` MUST ever be updated or deleted, and the API MUST expose no operation that could do so. A `FiadoPropuesto` is the one exception, and only in its own lifecycle: it moves **once** from `pendiente` to exactly one of `confirmado` or `cancelado`, recording when and by whom, and it is never edited after that. A confirmed charge is immutable in the same way.

**Verification:** integration

#### Scenario: A proposal is cancelled, never edited

- GIVEN a prepared `FiadoPropuesto` of 10,00 € for a client
- WHEN the owner cancels it
- THEN it reads cancelled and the client has no charge

#### Scenario: A row cannot be mutated

- GIVEN an existing ledger row
- WHEN a request attempts to modify or delete it
- THEN the operation is unavailable and the row is unchanged

### Requirement: IC-02 — The amount of a `cargo` equals its itemisation total

The amount recorded for a `cargo` MUST equal the total of its own itemisation, and the server MUST verify this inside the write transaction. A write whose declared amount differs MUST be refused with HTTP 422 carrying `codigo_error` `lineas_descuadradas` and MUST create no row.

**Verification:** integration

#### Scenario: Lines that do not add up are refused

- GIVEN a `cargo` of two lines totalling 6,40 € and a declared amount of 6,50 €
- WHEN it is written
- THEN the response is 422 with `codigo_error` `lineas_descuadradas` and no row is created

#### Scenario: The total is the sum of the lines

- GIVEN a confirmed proposal of two lines totalling 6,40 €
- WHEN the charge is written
- THEN the charge reads 6,40 € and its itemisation total equals it

### Requirement: IC-03 — A charge exists only after the client confirms it

A `cargo` MUST NOT be recorded before the client has confirmed the proposal it comes from. A charge that exists MUST count as debt, MUST age and MUST be able to trigger the suspension from the moment it is recorded; and no client act MAY remove an amount from the outstanding.

**Verification:** unit, integration

#### Scenario: A confirmed charge ages and can suspend

- GIVEN a confirmed `cargo` of 10,00 € dated 45 days ago
- WHEN the outstanding and the status are read
- THEN the outstanding includes 10,00 €, the charge ages and the customer reads `suspendido`

#### Scenario: A prepared proposal is not debt

- GIVEN a prepared `FiadoPropuesto` of 10,00 € that no client confirmed
- WHEN the outstanding is read
- THEN the outstanding does not include the 10,00 €

### Requirement: IC-04 — The effective confirmation state is derived

The effective state of a `cargo` MUST be computed on read from its `Confirmacion` rows, and no stored confirmation state MAY exist on the `cargo` or on the customer. A `cargo` that carries no confirmation reads `sin_confirmar`, and — because no unconfirmed charge can exist — that state is reachable only for a row written before its confirmation, never for a charge in normal operation.

**Verification:** unit, integration

#### Scenario: The state follows the confirmation

- GIVEN a `cargo` with one `Confirmacion` in state `confirmado`
- WHEN the charge's state is read
- THEN it is `confirmado` and no stored state field exists

### Requirement: IC-05 — The `cargo` write API is validated

The `cargo` write API MUST NOT accept `occurred_at`; the server MUST stamp it with the current instant, and a request carrying `occurred_at` MUST be refused with HTTP 422 carrying `codigo_error` `campo_no_admitido`, creating no row and no line.

**Verification:** integration

#### Scenario: A client-supplied date is refused

- GIVEN a `cargo` request that carries `occurred_at`
- WHEN it is submitted
- THEN the response is 422 with `codigo_error` `campo_no_admitido` and no row is created

### Requirement: IC-06 — The charge rules are pure and ORM-free

The amount check and the confirmation-state derivation MUST be pure functions over plain values with no ORM access, so each is verifiable by a unit test that runs without a database.

**Verification:** unit

#### Scenario: The amount check runs without a database

- GIVEN a fixture of lines and a declared amount
- WHEN the check is applied to them
- THEN it reports agreement or disagreement and no database is needed

## Conditional Requirements

### Requirement: IC-07 — A `cargo` carries `CargoLinea` rows

**Conditional:** Regla 5 — if it empties, the catalogue and the `CargoLinea` are cut, a proposal carries an amount only, and no price is drawn from the catalogue.

A `cargo` MUST carry one or more `CargoLinea` rows, each naming a `Producto`, a quantity and a `precio_unitario`; the total of the lines MUST be the total of the charge. A charge without itemisation MUST NOT be recorded: the client confirms a figure they can see broken down, and a figure they cannot see broken down is not a figure they can confirm.

**Verification:** integration

#### Scenario: A two-line charge creates two lines and one entry

- GIVEN a confirmed proposal of two lines totalling 6,40 €
- WHEN the charge is written
- THEN two `CargoLinea` rows and one `LedgerEntry` of 6,40 € exist

#### Scenario: A charge without itemisation is refused

- GIVEN a proposal with no lines and a declared amount of 4,20 €
- WHEN the owner tries to confirm it
- THEN the response is 422 with `codigo_error` `lineas_descuadradas` and no charge exists

### Requirement: IC-08 — `precio_unitario` is a snapshot

**Conditional:** Regla 5 — if it empties, there is no snapshot and no line; the charge keeps only its amount.

`precio_unitario` MUST be the price actually charged at the moment of the confirmation; a later change to the catalogue price MUST NOT rewrite a stored line, and the owner MAY override the catalogue price per proposal, in which case the line MUST hold the amount actually charged.

**Verification:** integration

#### Scenario: A later catalogue price change leaves the stored price alone

- GIVEN a `CargoLinea` recorded at 1,20 € and a `Producto` whose catalogue price later becomes 1,50 €
- WHEN the line is read again
- THEN it still holds 1,20 €

#### Scenario: An overridden price is the price charged

- GIVEN a `Producto` priced 1,20 € and a proposal line of 3 units the owner prices at 1,00 €
- WHEN it is confirmed
- THEN the line holds `precio_unitario` 1,00 € and its total is 3,00 €

### Requirement: IC-09 — Charge lines are immutable with their charge

**Conditional:** Regla 5 — if it empties, there are no lines to be immutable.

A `CargoLinea` MUST NOT be updated or deleted once its `cargo` is recorded, and MUST NOT be detached from it.

**Verification:** integration

#### Scenario: A recorded line cannot be edited

- GIVEN a recorded `cargo` with a line of 1,20 €
- WHEN a request attempts to change that line's price
- THEN the operation is unavailable and the line is unchanged
