# credit-book Specification

## Purpose

The `libreta`: its customers, their credit line, the append-only book of `cargo`, `pago` and `nota de crédito`, and the automatic suspension that stops the `fiado` from growing. Balances, ageing and status are derived, never stored.

## Requirements

### Requirement: CB-01 — The ledger is append-only

A `LedgerEntry` MUST never be updated or deleted and no update or delete operation MUST exist; a correction MUST be appended as a `nota de crédito`.

**Verification:** integration

#### Scenario: A correction is appended, never edited

- GIVEN a `cargo` of 10,00 € and a `pago` of 4,00 €
- WHEN a `nota de crédito` of 10,00 € is recorded
- THEN it is appended and both original rows are unchanged

#### Scenario: An entry cannot be mutated

- GIVEN an existing `LedgerEntry`
- WHEN a request attempts to modify or delete it
- THEN the operation is unavailable and the entry is unchanged

### Requirement: CB-02 — Balances are derived, never stored

`outstanding(customer, at)` MUST equal `sum(cagos) − sum(pagos) − sum(notas de crédito)` for entries with `occurred_at ≤ at`; no balance column MUST exist and a negative result MUST be a residual in the customer's favour, not an error.

**Verification:** unit, integration

#### Scenario: The balance matches the hand-computed fixture

- GIVEN a seeded customer with known entries
- WHEN the outstanding balance is read
- THEN it equals the hand-computed total and no stored balance exists

#### Scenario: An overpayment leaves a residual in the customer's favour

- GIVEN a customer owing 20,00 €
- WHEN a `pago` of 35,00 € is recorded
- THEN the outstanding is −15,00 €, the charges are unchanged and the response succeeds

### Requirement: CB-03 — Payments are allocated FIFO

A `pago` MUST retire the oldest unpaid `cargo` first and any surplus MUST remain as credit in the customer's favour.

**Verification:** unit

#### Scenario: The oldest charge is retired first

- GIVEN a `cargo` of 10,00 € on day 1 and one of 40,00 € on day 20, unpaid
- WHEN a `pago` of 30,00 € is applied
- THEN the outstanding falls by exactly 30,00 €, the 10,00 € charge is settled and 20,00 € stays pending

### Requirement: CB-04 — Ageing buckets are derived per charge

Each unpaid `cargo` principal MUST be bucketed by its own age and the four totals MUST sum exactly to the outstanding.

| Bucket | Age of the `cargo` |
| --- | --- |
| `vigente` | ≤ 7 d |
| `envejecido` | 8–30 d |
| `viejo` | 31–90 d |
| `cronico` | > 90 d |

`antiguedad_max_dias`, the age of the oldest unpaid charge, MUST be reported separately and MUST drive the suspension and the ladder order.

**Verification:** unit, integration

#### Scenario: Buckets are exact and sum to the outstanding

- GIVEN unpaid charges aged 5, 8, 30, 31 and 91 days and a customer with payments
- WHEN the ageing buckets are computed
- THEN they fall in `vigente`, `envejecido`, `envejecido`, `viejo` and `cronico` and the totals equal the outstanding exactly

### Requirement: CB-05 — The credit limit is an explicit state

`credit_limit` MUST be a non-negative amount or `null`, where `null` is the explicit state «sin límite» and never a missing value; changing it MUST persist the new value and leave every prior `LedgerEntry` untouched.

**Verification:** integration

#### Scenario: A null limit means no limit

- GIVEN a customer with `credit_limit = null`
- WHEN a `cargo` is recorded
- THEN the `cargo` is accepted and registered

#### Scenario: Changing the limit leaves the ledger untouched

- GIVEN a customer limited to 20,00 € with prior entries
- WHEN the owner sets the limit to 50,00 €
- THEN the limit reads 50,00 € and no prior entry changed

### Requirement: CB-06 — Suspension is automatic and evaluated on read

A customer MUST be `suspendido` when the oldest unpaid charge is older than 30 days OR the outstanding exceeds the credit limit; a `null` limit MUST never trigger the limit cause and no human action MUST be required.

| `suspended_reason` | Cause |
| --- | --- |
| `limite_superado` | outstanding > `credit_limit` |
| `antiguedad_superada` | oldest unpaid charge older than 30 d |

**Verification:** unit, integration

#### Scenario: A 45-day debt suspends the customer automatically

- GIVEN a seeded customer with an unpaid charge 45 days old
- WHEN the status is read
- THEN it is `suspendido` with reason `antiguedad_superada` and no prior human action

#### Scenario: The limit cause fires only for a bounded limit

- GIVEN a customer limited to 20,00 € owing 25,00 €
- WHEN the status is read
- THEN the status is `suspendido` with reason `limite_superado`

#### Scenario: A payment that retires the oldest charge lifts the suspension

- GIVEN a customer with a `cargo` of 20,00 € dated 45 days ago and one of 10,00 € dated 10 days ago
- WHEN a `pago` of 20,00 € is recorded
- THEN the 45-day charge is retired, `antiguedad_max_dias` is 10 and the customer is `activo` again

### Requirement: CB-07 — A suspended customer cannot receive a new charge

While the customer is `suspendido` the server MUST refuse a new `cargo` with HTTP 422 naming the cause, MUST create NO `LedgerEntry`, and MUST be backed by a database-level `CheckConstraint`.

**Verification:** integration

#### Scenario: A refused charge creates no entry

- GIVEN a customer suspended for a 45-day charge or for exceeding the limit
- WHEN a new `cargo` is attempted
- THEN the response is 422 naming the cause and no `LedgerEntry` row is created

### Requirement: CB-08 — The owner can lift a suspension explicitly

The owner MUST be able to set a suspended customer back to `activo`; the override MUST record who and when and MUST NOT rewrite any `LedgerEntry`.

**Verification:** integration

#### Scenario: Lifting a suspension is auditable

- GIVEN a suspended customer
- WHEN the owner lifts the suspension
- THEN the status is `activo` and the acting user and timestamp are recorded

### Requirement: CB-09 — Ledger entries are validated

Every entry MUST have `amount > 0`, a `kind` in {`cargo`, `pago`, `nota_credito`}, an `occurred_at` not in the future and an author; a rejected entry MUST NOT be persisted and MUST be answered with HTTP 422.

**Verification:** integration

#### Scenario: A future-dated entry is rejected

- GIVEN a form dated after the current moment
- WHEN it is submitted
- THEN the response is 422 and no `LedgerEntry` is created

### Requirement: CB-10 — The credit book minimises personal data

A customer MUST be identified only by an `alias` and an optional `phone`; no national ID, address, photograph, bank detail or sensitive-category data MUST be stored or exposed.

**Verification:** integration

#### Scenario: Only alias and optional phone are held

- GIVEN a customer record
- WHEN its fields are inspected
- THEN the personal fields are limited to `alias` and the optional `phone`

### Requirement: CB-11 — The credit rules are pure and unit-testable

`allocate_payments`, `bucket_of` and `evaluate_customer` MUST be pure functions over plain values with no ORM access, so each is verifiable by a unit test that runs without a database.

**Verification:** unit

#### Scenario: The rules are exercised without a database

- GIVEN a fixture of entries and a reference date
- WHEN the three rules are applied to it
- THEN the results come from the fixture alone and no database is needed

### Requirement: CB-12 — Suspension state is recorded on the customer

`Customer` MUST carry the suspension audit fields and they MUST NOT live in the append-only ledger.

| Field | Holds |
| --- | --- |
| `suspended_at` | when the customer was suspended |
| `suspended_reason` | `limite_superado` or `antiguedad_superada` |
| `suspended_by` | the user who applied the suspension |
| `suspended_override_at` | when the owner lifted it |
| `suspended_override_by` | who lifted it |

**Verification:** integration

#### Scenario: The override leaves a readable trail

- GIVEN a customer suspended by the automatic rule
- WHEN the owner lifts the suspension
- THEN the override fields hold the override and the ledger is unchanged
