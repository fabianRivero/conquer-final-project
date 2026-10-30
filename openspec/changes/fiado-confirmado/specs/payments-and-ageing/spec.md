# payments-and-ageing Specification

## Purpose

The money that comes back: `pago` and `nota de crédito`, how they retire debt (FIFO), how the debt ages, the `credit_limit`, and the automatic suspension. Every balance, bucket and status is derived on read.

## Requirements

### Requirement: PA-01 — `outstanding` is derived, never stored

`outstanding(customer, at)` MUST equal `sum(cargos) − sum(pagos) − sum(notas de crédito)` for the entries with `occurred_at ≤ at`; no balance column MUST exist, and a negative result MUST be a residual in the customer's favour, not an error.

**Verification:** unit, integration

#### Scenario: The balance matches the hand-computed fixture

- GIVEN a seeded customer with known entries
- WHEN the outstanding is read
- THEN it equals the hand-computed total and no stored balance exists

#### Scenario: An overpayment leaves a residual in the customer's favour

- GIVEN a customer owing 20,00 €
- WHEN a `pago` of 35,00 € is recorded
- THEN the outstanding is −15,00 €, the charges are unchanged and the request succeeds

### Requirement: PA-02 — Payments are allocated FIFO

A `pago` MUST retire the oldest unpaid `cargo` first, and any surplus MUST remain as credit in the customer's favour.

**Verification:** unit

#### Scenario: The oldest charge is retired first

- GIVEN a `cargo` of 10,00 € on day 1 and one of 40,00 € on day 20, both unpaid
- WHEN a `pago` of 30,00 € is applied
- THEN the 10,00 € charge is settled and 20,00 € stays pending

#### Scenario: A payment smaller than the oldest charge retires it only in part

- GIVEN a `cargo` of 10,00 € on day 1 and one of 40,00 € on day 20, both unpaid
- WHEN a `pago` of 6,00 € is applied
- THEN 4,00 € of the oldest charge stays pending and the newer charge is untouched

### Requirement: PA-03 — Ageing buckets are derived per charge

Each unpaid `cargo` MUST be bucketed by its own age, and the four bucket totals MUST sum exactly to the outstanding.

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

### Requirement: PA-04 — A disputed charge is debt, not a credit

A `cargo` under an open dispute MUST still count in the outstanding and age in its own bucket; a dispute MUST never remove an amount from the debt. Only a `nota de crédito` reduces it.

**Verification:** unit, integration

#### Scenario: A disputed charge still ages

- GIVEN a disputed `cargo` of 6,40 € dated 40 days ago
- WHEN the outstanding and the ageing are read
- THEN the outstanding includes 6,40 € and the charge sits in the `viejo` bucket

### Requirement: PA-05 — The credit limit is an explicit state

`credit_limit` MUST be a non-negative amount or `null`, where `null` is the explicit state «sin límite» and never a missing value; changing it MUST persist the new value and leave every prior entry untouched.

**Verification:** integration

#### Scenario: A null limit means no limit

- GIVEN a customer with `credit_limit = null`
- WHEN a `cargo` is recorded
- THEN the `cargo` is accepted and registered

#### Scenario: Changing the limit leaves the ledger untouched

- GIVEN a customer limited to 20,00 € with prior entries
- WHEN the owner sets the limit to 50,00 €
- THEN the limit reads 50,00 € and no prior entry changed

### Requirement: PA-06 — Suspension is automatic and evaluated on read

A customer MUST be `suspendido` when the oldest unpaid charge is older than 30 days OR the outstanding exceeds the credit limit; a `null` limit MUST never trigger the limit cause, and no human action MUST be required. The status and its `suspended_reason` (`limite_superado` | `antiguedad_superada`) MUST be computed on read from the outstanding and the ageing, never read from a stored status.

**Verification:** unit, integration

#### Scenario: A 45-day debt suspends the customer automatically

- GIVEN a seeded customer with an unpaid charge 45 days old
- WHEN the status is read
- THEN it is `suspendido` with reason `antiguedad_superada` and no prior human action

#### Scenario: A payment that retires the oldest charge lifts the suspension

- GIVEN a customer with a `cargo` of 20,00 € dated 45 days ago and one of 10,00 € dated 10 days ago
- WHEN a `pago` of 20,00 € is recorded
- THEN the 45-day charge is retired, `antiguedad_max_dias` is 10 and the customer reads `activo`

### Requirement: PA-07 — A suspended customer cannot receive a new charge

While the customer is `suspendido`, the server MUST refuse a new `cargo` with HTTP 422 naming the cause, MUST create NO entry and MUST create no charge line either.

**Verification:** integration

#### Scenario: A refused charge creates no entry

- GIVEN a customer suspended for a 45-day charge or for exceeding the limit
- WHEN a new `cargo` is attempted
- THEN the response is 422 with `codigo_error` `limite_superado` or `antiguedad_superada` and no entry is created

### Requirement: PA-08 — The owner can lift a suspension explicitly

The owner MUST be able to return a suspended customer to `activo`; the override MUST be an appended act carrying who and when, MUST be consulted by the derived evaluation, and MUST NOT rewrite any entry.

**Verification:** integration

#### Scenario: Lifting a suspension is auditable

- GIVEN a suspended customer
- WHEN the owner lifts the suspension
- THEN the status is `activo` and the acting user and timestamp are recorded

#### Scenario: The override leaves the ledger untouched

- GIVEN a suspended customer with prior entries
- WHEN the owner lifts the suspension
- THEN no prior entry changed and the outstanding is unchanged

### Requirement: PA-09 — A correction is appended as a `nota de crédito`

A `nota de crédito` MUST reduce the outstanding by its amount and MUST NOT modify the `cargo` it corrects; the corrected `cargo` MUST remain exactly as it was recorded.

**Verification:** integration

#### Scenario: The credit note reduces the debt without touching the charge

- GIVEN a `cargo` of 10,00 €
- WHEN a `nota de crédito` of 4,00 € is recorded
- THEN the outstanding is 6,00 € and the `cargo` row is unchanged

### Requirement: PA-10 — The ledger write API is validated

Every entry MUST have `amount > 0`, a `kind` in {`cargo`, `pago`, `nota_credito`} and an author; a rejected entry MUST NOT be persisted and MUST be answered with HTTP 422 carrying a machine-readable `codigo_error`. The ledger write API MUST NOT accept `occurred_at` — the server MUST stamp it — and a request carrying it MUST be refused and MUST create no row.

**Verification:** integration

#### Scenario: A client-supplied date is refused

- GIVEN a request that carries an `occurred_at`
- WHEN it is submitted
- THEN the response is 422 with `codigo_error` `campo_no_admitido` and no entry is created

#### Scenario: A non-positive amount is refused

- GIVEN a request with `amount = 0`
- WHEN it is submitted
- THEN the response is 422 with `codigo_error` `importe_no_positivo` and no entry is created

### Requirement: PA-11 — The credit rules are pure and ORM-free

`allocate_payments`, `bucket_of` and `evaluate_customer` MUST be pure functions over plain values with no ORM access, so each is verifiable by a unit test that runs without a database.

**Verification:** unit

#### Scenario: The rules are exercised without a database

- GIVEN a fixture of entries and a reference date
- WHEN the three rules are applied to it
- THEN the results come from the fixture alone and no database is needed
