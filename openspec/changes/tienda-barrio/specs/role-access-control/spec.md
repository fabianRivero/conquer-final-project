# role-access-control Specification

## Purpose

The two roles of the shop — `dueño` and `dependiente` — and the server-side enforcement of the 2 × 9 capability matrix. The credit book is the `dueño`'s private ledger: the `dependiente` works the `caja` and the close and must not reach customer data.

## Requirements

### Requirement: RAC-01 — Two roles exist and are enforced on the server

The application MUST provide exactly two roles, carried by the Django groups `dueno` and `dependiente`, and MUST enforce the matrix below server-side on every URL and every API view; hiding a control in the interface MUST NOT count as enforcement.

**Verification:** integration

| # | Capability | `dueno` | `dependiente` |
| --- | --- | :---: | :---: |
| 1 | Cash movements (`entrada` / `salida`) | Yes | Yes |
| 2 | The day close | Yes | Yes |
| 3 | The credit book (alias, limits, balances) | Yes | No → 403 |
| 4 | Create a customer or set a limit | Yes | No |
| 5 | Record a `cargo` or a `pago` | Yes | No |
| 6 | Ageing buckets and the risk ladder | Yes | No |
| 7 | Lift a suspension | Yes | No |
| 8 | The `posicion_real` | Yes | No |
| 9 | Users and roles | Yes | No |

#### Scenario: A denied capability is refused at the server

- GIVEN a `dependiente` account
- WHEN it attempts a denied capability of the matrix
- THEN the server refuses the request whatever the interface shows

### Requirement: RAC-02 — The credit book is owner-only

Every endpoint of the credit book — customer list and detail, ledger entries, balances, ageing and the credit limit — MUST return HTTP 403 to a `dependiente` with no partial data, and MUST scope its queryset to the `Shop` of the session: there is no owner field, so scoping is by `Shop` and role.

**Verification:** integration

#### Scenario: The owner reads the credit book

- GIVEN `dueno@tienda.test`
- WHEN it requests `GET /api/v1/clientes/`
- THEN the response is 200 and returns the seeded customers

#### Scenario: The dependiente is refused on the credit book

- GIVEN `dependiente@tienda.test`
- WHEN it requests `GET /api/v1/clientes/`
- THEN the response is 403 and the body holds no alias and no customer identifier

### Requirement: RAC-03 — No credit-book data may leak into any payload

For a `dependiente`, NO path of ANY response payload — pagination metadata, close aggregates, bucket totals, cash series — MAY contain an `alias`, a customer identifier, a name, a credit-book balance, a credit limit or ageing data; a leak in one nested field MUST be a data-protection failure, not a cosmetic defect. The position payload of the `dependiente` MUST carry only `caja` and the close figures.

**Verification:** integration

#### Scenario: The position payload of the dependiente carries no customer data

- GIVEN a `dependiente` account and a shop with customers
- WHEN it requests `GET /api/v1/posicion/`
- THEN the response is 200 with `clientes` empty and no path holding an alias, an id, a name, a balance or an ageing value

#### Scenario: Customer-derived totals are absent for the dependiente

- GIVEN a `dependiente` account
- WHEN it requests `GET /api/v1/posicion/`
- THEN `fiado_pendiente`, the ageing buckets and `posicion_real` are absent

### Requirement: RAC-04 — Unauthenticated access is refused

Any request to `/api/v1/` without a valid session MUST be answered with 401 or 403 and MUST NOT return any row.

**Verification:** integration

#### Scenario: An anonymous request returns no data

- GIVEN no session cookie
- WHEN any `/api/v1/` endpoint is requested
- THEN the response is 401 or 403 and the body holds no row

### Requirement: RAC-05 — Sessions and CSRF protect every mutation

Authentication MUST use a server-side session; every state-changing request MUST require a valid CSRF token and a request with a missing or invalid token MUST be refused.

**Verification:** integration

#### Scenario: A mutation without a CSRF token is refused

- GIVEN an authenticated `dueno` session
- WHEN a `cargo` is posted without `X-CSRFToken`
- THEN the response is 403 and no `LedgerEntry` is created

### Requirement: RAC-06 — Passwords are hashed with PBKDF2

Stored passwords MUST be PBKDF2 hashes with 1 000 000 iterations (the Django 5.2 default) and plaintext passwords MUST never be stored, logged or returned.

**Verification:** integration

#### Scenario: The stored password is a PBKDF2 hash

- GIVEN a created user
- WHEN the password field is inspected
- THEN it holds a PBKDF2 hash, not the plaintext

### Requirement: RAC-07 — Data access is parameterised and output escaped

All database access MUST go through the ORM's parameterised query API, never raw string-built SQL, and user-supplied values rendered in HTML MUST be autoescaped by the template engine.

**Verification:** integration, e2e

#### Scenario: A hostile alias is rendered as inert text

- GIVEN a customer whose `alias` contains a script tag
- WHEN the owner opens that customer page
- THEN the value is rendered as text, not as markup

### Requirement: RAC-08 — Production configuration is locked and secrets stay out of the repository

The deployed configuration MUST run with `DEBUG=False`; `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` MUST be read from the environment; no secret, key or credential MUST appear in the repository or in its history; and every dependency version MUST be pinned.

**Verification:** e2e

#### Scenario: The public deployment is not in debug mode

- GIVEN the deployed public URL
- WHEN it is requested
- THEN no Django debug information is exposed and `DEBUG` is False

#### Scenario: The repository history holds no secret

- GIVEN the full Git history
- WHEN it is scanned for keys, passwords and tokens
- THEN no secret is found and every dependency is pinned to an exact version

### Requirement: RAC-09 — One test account per role is seeded

The demo dataset MUST provide exactly one account per role — `dueno@tienda.test` and `dependiente@tienda.test` — so both roles can be demonstrated at the public URL.

**Verification:** integration, e2e

#### Scenario: Both seeded accounts can sign in

- GIVEN the seeded dataset
- WHEN each account signs in
- THEN both are authenticated and each lands in the capability set of its own role
