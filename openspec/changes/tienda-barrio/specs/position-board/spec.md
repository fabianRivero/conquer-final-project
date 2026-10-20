# position-board Specification

## Purpose

The React view `/app/posicion` — «La posición real» — where the owner sees the equation of the shop, the ladder of debtors by age, the gap between the `caja` and the `posición real`, and today's close. It renders the application's own API, at the public URL, same origin.

## Requirements

### Requirement: PB-01 — The board renders the four composed elements

`/app/posicion` MUST render, with no data table anywhere: (1) the equation `Caja + Fiado pendiente = Posición real`; (2) the risk ladder, one row per debtor ordered by `antiguedad_max_dias` descending, each an ageing ribbon split into `vigente` / `envejecido` / `viejo` / `cronico`, with the limit marker and the status chip; (3) the two-series area of `Caja` against `Posición real`; (4) the close card `Esperado` / `Contado` / `Desviación`.

**Verification:** e2e

#### Scenario: The four elements are present at the public URL

- GIVEN the owner signed in at the public URL
- WHEN `/app/posicion` is opened
- THEN the equation, the ladder, the two-series area and the close card render and no table appears

#### Scenario: The gap between the two series is the money already given away

- GIVEN a `caja` of 412,35 € and a `fiado pendiente` of 268,90 €
- WHEN the two-series area renders
- THEN the lower band is `Caja` and the upper line is `Posición real` at 681,25 €, and the distance between them is the `fiado pendiente`

### Requirement: PB-02 — The board consumes the application's own API

The board MUST read `GET /api/v1/posicion/` of the same application, at the public URL, on the same origin, using the session cookie and the `X-CSRFToken` header; it MUST NOT use CORS, a second host, a second URL or hard-coded figures.

**Verification:** e2e

#### Scenario: The board's figures come from the API

- GIVEN the owner signed in at the public URL
- WHEN the browser loads `/app/posicion`
- THEN the request goes to `/api/v1/posicion/` on the same origin and no cross-origin request is made

### Requirement: PB-03 — The board reflects the database, live

Every figure MUST equal the value served by the API and a write made in another session MUST be visible; a `pago` MUST change the ladder and the drawer, never the `Posición real`.

**Verification:** e2e

#### Scenario: A payment retires the oldest band and lifts the suspension

- GIVEN the owner signed in at the public URL in two windows and a customer suspended with a 20,00 € charge 45 days old
- WHEN a `pago` of 20,00 € is recorded in the second window
- THEN the first window drops that 20,00 € band, the chip flips `Suspendido` → `Activo`, `Caja` is 20,00 € higher and `Posición real` is unchanged

### Requirement: PB-04 — The board is served over HTTPS at the public URL

The board MUST be reachable at a public HTTPS URL, served by the same deployable service as the API, with no CORS and no second host.

**Verification:** e2e

#### Scenario: The board is public and encrypted

- GIVEN the public URL and an authenticated owner
- WHEN `/app/posicion` is requested
- THEN the connection is HTTPS and the page renders from the API's service

### Requirement: PB-05 — The seeded dataset is idempotent

The demo seed MUST be re-runnable without duplicating anything, and the seeded dates MUST be computed relative to the day of execution so the board always shows current data.

**Verification:** integration, e2e

#### Scenario: Re-running the seed changes nothing

- GIVEN the demo dataset has been seeded
- WHEN the seed command runs a second time
- THEN the counts of shops, customers, entries, movements and closes are unchanged and each seed account exists once per role

### Requirement: PB-06 — The board shows no credit-book data to a dependiente

If a `dependiente` opens the board, the page MUST contain no alias, no customer identifier, no credit-book balance and no ageing data, and MUST NOT show the `Posición real`.

**Verification:** e2e

#### Scenario: The dependiente board exposes no customer data

- GIVEN a `dependiente` signed in at the public URL
- WHEN `/app/posicion` is opened
- THEN no alias, identifier, balance or ageing figure appears and no `Posición real` is displayed

### Requirement: PB-07 — The deployed board stays reachable during the review period

The deployed service MUST answer a keep-alive request every ≤ 10 minutes, and a documented manual wake-up MUST exist for the moment before the defense.

**Verification:** e2e

#### Scenario: The service is awake when the panel opens it

- GIVEN the deployed public URL and a keep-alive schedule of ≤ 10 minutes
- WHEN the panel opens the board during the review period
- THEN the page renders instead of a cold-start placeholder
