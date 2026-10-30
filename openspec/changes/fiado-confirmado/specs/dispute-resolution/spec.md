# dispute-resolution Specification

## Purpose

What happens when the two parties disagree: the client disputes, the owner arbitrates, and the correction is appended — never edited into the record.

## Conditional Requirements

### Requirement: DR-01 — A dispute is recorded without touching the charge

**Conditional:** Regla 4 — if it empties, the client-facing surface disappears, no dispute can be raised and the project becomes `fiado desglosado`.

A dispute MUST be appended as a `Confirmacion` in state `en_disputa`, carrying `importe_reclamado` and an optional note; it MUST NOT change the amount of the charge it disputes, and the effective state of that charge MUST become `en_disputa`.

**Verification:** integration

#### Scenario: The dispute is appended, the charge is not

- GIVEN a `cargo` of 6,40 €
- WHEN a dispute claiming 4,20 € is appended
- THEN a `Confirmacion` in state `en_disputa` exists and the `cargo` still reads 6,40 €

### Requirement: DR-02 — The owner arbitrates the dispute

**Conditional:** Regla 4 — if it empties, there is no dispute to arbitrate.

Only the `dueño` MUST be able to resolve a dispute, and the resolution MUST be one of two recorded outcomes: accepting the discrepancy by appending a `nota de crédito` for the difference, or rejecting it by appending no entry and asserting the original figure.

**Verification:** integration

#### Scenario: The owner accepts the discrepancy

- GIVEN a disputed `cargo` of 6,40 € with `importe_reclamado` 4,20 €
- WHEN the owner appends a `nota de crédito` of 2,20 €
- THEN the outstanding is 4,20 € and the `cargo` row is unchanged

#### Scenario: The owner rejects the discrepancy

- GIVEN the same dispute
- WHEN the owner rejects it
- THEN no entry is appended, the outstanding stays 6,40 € and the state stays `en_disputa`

#### Scenario: A `dependiente` cannot resolve a dispute

- GIVEN a `dependiente` account and an open dispute
- WHEN it tries to append a `nota de crédito` for that charge
- THEN the response is 403 and no entry is created

### Requirement: DR-03 — A dispute is reconciled at most once

**Conditional:** Regla 4 — if it empties, no dispute can be open.

Once a `nota de crédito` has reconciled a dispute, any further `nota de crédito` for the same charge MUST be refused with HTTP 422 carrying `codigo_error` `disputa_abierta`, and no entry MUST be created.

**Verification:** integration

#### Scenario: A second reconciliation is refused

- GIVEN a disputed `cargo` of 6,40 € already reconciled with a `nota de crédito` of 2,20 €
- WHEN the owner appends another one for that charge
- THEN the response is 422 with `codigo_error` `disputa_abierta` and no entry is created

### Requirement: DR-04 — The client sees the dispute and its resolution

**Conditional:** Regla 4 — if it empties, the client-facing surface disappears.

The client's statement MUST show the state of a disputed charge and the record of its resolution, so that the client sees the outcome of the arbitration that concerns them.

**Verification:** integration

#### Scenario: The client reads the outcome

- GIVEN a dispute resolved with a `nota de crédito` of 2,20 €
- WHEN the client reads the statement
- THEN the charge shows the dispute and the appended correction
