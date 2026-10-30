# client-accounts-and-credentials Specification

## Purpose

The two shop roles and the server-side enforcement of the capability matrix, the hard 403 that keeps the credit book away from the `dependiente`, and — conditionally — the scoped credential that lets one client see one statement and nothing else.

## Requirements

### Requirement: CAC-01 — Two shop roles exist and are enforced on the server

The application MUST provide exactly two shop roles, carried by the groups `dueno` and `dependiente`, and MUST enforce the matrix below server-side on every URL and every API view; hiding a control in the interface MUST NOT count as enforcement.

**Verification:** integration

| # | Capability | `dueno` | `dependiente` |
| --- | --- | :---: | :---: |
| 1 | Cash movements and the day close | Yes | Yes |
| 2 | The credit book (alias, limits, balances, ageing) | Yes | No → 403 |
| 3 | Create a customer, set a limit, issue or rotate a `codigo` | Yes | No |
| 4 | Record a `cargo` or a `pago` | Yes | No |
| 5 | The risk ladder and the `posicion_real` | Yes | No |
| 6 | Lift a suspension | Yes | No |
| 7 | Resolve a dispute | Yes | No |
| 8 | Users and roles | Yes | No |

#### Scenario: A denied capability is refused at the server

- GIVEN a `dependiente` account
- WHEN it attempts a denied capability of the matrix
- THEN the server refuses the request whatever the interface shows

### Requirement: CAC-02 — The credit book is owner-only among the staff

Every endpoint of the credit book — customer list and detail, ledger entries, balances, ageing and the credit limit — MUST answer HTTP 403 to a `dependiente`, with no partial data and no `codigo` in any field of the response, and MUST scope its queryset to the shop of the session.

**Verification:** integration

#### Scenario: The owner reads the credit book

- GIVEN `dueno@tienda.test`
- WHEN it requests `GET /api/v1/clientes/`
- THEN the response is 200 and returns the seeded customers

#### Scenario: The `dependiente` is refused on the credit book

- GIVEN `dependiente@tienda.test`
- WHEN it requests `GET /api/v1/clientes/`
- THEN the response is 403 and the body holds no alias, no customer identifier and no `codigo`

#### Scenario: The whole credit book is refused, not only the list

- GIVEN `dependiente@tienda.test`
- WHEN it requests a customer detail, a ledger entry, a balance, the ageing or a credit limit
- THEN every response is 403 with no partial data in any field

### Requirement: CAC-03 — No staff session reaches the client surface or gains a client scope

Every client-facing endpoint MUST answer HTTP 403 to any staff session, `dueno` or `dependiente`; a staff session MUST NOT carry a client scope and MUST NOT be upgradable to one.

**Verification:** integration

#### Scenario: A staff session reaches no client endpoint

- GIVEN `dependiente@tienda.test` signed in
- WHEN it requests a client endpoint
- THEN the response is 403 and the session carries no customer scope

### Requirement: CAC-04 — Sessions and CSRF protect every staff mutation

Authentication MUST use a server-side session; every state-changing request on the staff surface MUST carry a valid CSRF token, and a request with a missing or invalid token MUST be refused with HTTP 403 and MUST create no row.

**Verification:** integration

#### Scenario: A mutation without a CSRF token is refused

- GIVEN an authenticated `dueno` session
- WHEN a `cargo` is posted without `X-CSRFToken`
- THEN the response is 403 and no ledger row is created

### Requirement: CAC-05 — The customer record minimises personal data

A customer MUST be identified only by an `alias` and an optional `phone`; no national ID, address, photograph, bank detail or sensitive-category data MUST be stored or exposed.

**Verification:** integration

#### Scenario: Only alias and optional phone are held

- GIVEN a customer record
- WHEN its fields are inspected
- THEN the personal fields are limited to the `alias` and the optional `phone`

#### Scenario: A customer with no phone holds only the alias

- GIVEN a customer created without a phone
- WHEN its fields are inspected
- THEN it holds the `alias` and no empty or placeholder personal field

### Requirement: CAC-06 — The views consume the application's own API at the public URL

Every view MUST read the application's own API at the public URL, on the same origin, through relative paths, with `credentials: 'same-origin'` and the `X-CSRFToken` header; no view MAY use CORS, a second host, a second URL or hard-coded figures. The application MUST be reachable at a public HTTPS URL served by the same deployable service as the API.

**Verification:** e2e

#### Scenario: The owner's board reads the same origin

- GIVEN the owner signed in at the public URL
- WHEN `/app/posicion` is loaded
- THEN the request goes to `/api/v1/posicion/` on the same origin and no cross-origin request is made

#### Scenario: The public URL is encrypted and serves the API

- GIVEN the public URL and an authenticated owner
- WHEN `/app/posicion` is requested
- THEN the connection is HTTPS and the page and the API come from one service

### Requirement: CAC-07 — Production is locked and secrets stay out of the repository

The deployed configuration MUST run with `DEBUG=False`; `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` MUST be read from the environment; no secret, key or credential MUST appear in the repository or in its history; and every dependency version MUST be pinned.

**Verification:** e2e

#### Scenario: The public deployment is not in debug mode

- GIVEN the deployed public URL
- WHEN it is requested
- THEN no debug information is exposed and `DEBUG` is False

#### Scenario: The repository history holds no secret

- GIVEN the full Git history
- WHEN it is scanned for keys, passwords and tokens
- THEN no secret is found and every dependency is pinned to an exact version

### Requirement: CAC-08 — One account per shop role is seeded

The demo dataset MUST provide exactly one account per shop role — `dueno@tienda.test` and `dependiente@tienda.test` — so both roles can be demonstrated at the public URL.

**Verification:** integration, e2e

#### Scenario: Both seeded accounts can sign in

- GIVEN the seeded dataset
- WHEN each account signs in
- THEN both are authenticated and each lands in the capability set of its own role

#### Scenario: The seed holds exactly one account per role

- GIVEN the seeded dataset
- WHEN the accounts are counted per role
- THEN there is one `dueno` account and one `dependiente` account

## Conditional Requirements

### Requirement: CAC-09 — The `codigo` is a scoped, per-shop credential

**Conditional:** Regla 4 — if it empties, the client-facing surface disappears and no credential is issued.

The `dueño` MUST issue one `codigo` per `Customer`, unique within the shop, and MUST be able to rotate it; a rotated `codigo` MUST invalidate the previous one. The `codigo` MUST be presented per request and MUST resolve to exactly one `Customer`; there MUST be no client user, no client group and no client session. An unknown or invalid `codigo` MUST be refused with HTTP 422 carrying `codigo_error` `codigo_invalido`.

**Verification:** integration

#### Scenario: The owner issues and rotates a `codigo`

- GIVEN a customer without a `codigo`
- WHEN the owner issues one and later rotates it
- THEN the new value differs from the old one and the old one is refused

#### Scenario: An invalid `codigo` is refused

- GIVEN a `codigo` that belongs to no customer
- WHEN it is presented with a client request
- THEN the response is 422 with `codigo_error` `codigo_invalido` and no customer data is returned

### Requirement: CAC-10 — The client payload carries nothing but that customer's own data

**Conditional:** Regla 4 — if it empties, the client-facing surface disappears and there is no client payload.

No path of ANY client response — nested field, pagination metadata, aggregate or error body — MAY carry another customer's alias or identifier, a shop-wide total, the `caja`, the `posicion_real`, another customer's `credit_limit` or ageing. A leak in one nested field MUST be treated as a data-protection failure, not a cosmetic defect.

**Verification:** integration

#### Scenario: The client payload holds only its own customer

- GIVEN two customers with different aliases, limits and ageing
- WHEN the client of one of them reads its statement
- THEN the whole JSON tree holds that customer only and no shop-wide figure
