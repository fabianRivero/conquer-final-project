# Requirement Index — `fiado-confirmado`

**Machine-derived from the specs. Do not re-derive, re-count or re-enumerate these in your reasoning.**

Each row is one requirement. The `Design home` column is yours to fill; the ID, title, conditional marker and verification level are already decided and must be copied exactly.

Legend: `C` = conditional requirement (it carries a `**Conditional:**` marker in its spec).

| ID | Requirement | Verif. | Scen. | Cond. | Design home |
|---|---|---|---|---|---|
| CP-01 | Cash movements are recorded and validated | integration | 2 |  |  |
| CP-02 | `caja` is recorded cash movements | unit, integration | 2 |  |  |
| CP-03 | `posicion_real` is additive | unit, integration | 2 |  |  |
| CP-04 | The day close is the anchor of `caja` | integration | 2 |  |  |
| CP-05 | The day close is available to both shop roles | integration | 1 |  |  |
| CP-06 | The position rule is pure and ORM-free | unit | 1 |  |  |
| CP-07 | `existencias_registradas` is a ceiling, never a count | unit, integration | 2 | C |  |
| PA-01 | `outstanding` is derived, never stored | unit, integration | 3 |  |  |
| PA-02 | Payments are allocated FIFO | unit | 4 |  |  |
| PA-03 | Ageing buckets are derived per charge | unit, integration | 1 |  |  |
| PA-05 | The credit limit is an explicit state | integration | 2 |  |  |
| PA-06 | Suspension is automatic and evaluated on read | unit, integration | 2 |  |  |
| PA-07 | A suspended customer cannot receive a new charge | integration | 2 |  |  |
| PA-08 | The owner can lift a suspension explicitly | integration | 2 |  |  |
| PA-09 | A payment is recorded only by the owner | integration | 2 |  |  |
| PA-10 | The ledger write API is validated | integration | 2 |  |  |
| PA-11 | The credit rules are pure and ORM-free | unit | 1 |  |  |
| IC-01 | The ledger is append-only | integration | 2 |  |  |
| IC-02 | The amount of a `cargo` equals its itemisation total | integration | 2 |  |  |
| IC-03 | A charge exists only after the client confirms it | unit, integration | 2 |  |  |
| IC-04 | The effective confirmation state is derived | unit, integration | 1 |  |  |
| IC-05 | The `cargo` write API is validated | integration | 1 |  |  |
| IC-06 | The charge rules are pure and ORM-free | unit | 1 |  |  |
| IC-07 | A `cargo` carries `CargoLinea` rows | integration | 2 | C |  |
| IC-08 | `precio_unitario` is a snapshot | integration | 2 | C |  |
| IC-09 | Charge lines are immutable with their charge | integration | 1 | C |  |
| CAC-01 | Two shop roles exist and are enforced on the server | integration | 1 |  |  |
| CAC-02 | The credit book is owner-only among the staff | integration | 3 |  |  |
| CAC-03 | No staff session reaches the client surface or gains a client scope | integration | 1 |  |  |
| CAC-04 | Sessions and CSRF protect every staff mutation | integration | 1 |  |  |
| CAC-05 | The customer record minimises personal data | integration | 2 |  |  |
| CAC-06 | The views consume the application's own API at the public URL | e2e | 2 |  |  |
| CAC-07 | Production is locked and secrets stay out of the repository | e2e | 2 |  |  |
| CAC-08 | One account per shop role is seeded | integration, e2e | 2 |  |  |
| CAC-09 | The `codigo` is a scoped, per-shop credential | integration | 2 | C |  |
| CAC-10 | The client payload carries nothing but that customer's own data | integration | 1 | C |  |
| PC-01 | The catalogue holds only the goods eligible for fiado | integration | 2 |  |  |
| PC-02 | `precio` is a default, not a constraint | integration | 2 |  |  |
| PC-03 | The catalogue is readable and seeded | integration | 1 |  |  |
| CC-01 | A charge exists only once the client has confirmed it | integration | 3 | C |  |
| CC-02 | The statement shows every confirmed charge of that client | integration | 3 | C |  |
| CC-03 | The prepared proposal is shown on the shop's screen | integration | 2 | C |  |
| CC-04 | The client may cancel a proposal | integration | 1 | C |  |
| CC-05 | The client view consumes the application's own API | e2e | 1 | C |  |
| CC-06 | A confirmed charge shows its full itemisation | integration | 1 | C |  |
| CC-07 | The client may propose a payment and the owner records it | integration | 4 | C |  |
| CF-01 | The `dependiente` prepares one proposal and records its confirmation | integration | 2 | C |  |
| CF-02 | The facilitator is recorded and holds no client scope | integration | 2 | C |  |

## Totals

- Requirements: **48** (all 48 must appear in the traceability matrix, each exactly once).
- Conditional requirements: **15**.
- Scenarios across the specs: **88**.

## Per-domain ranges

- `cash-position`: CP-01 -> CP-07 (7 requirements)
- `payments-and-ageing`: PA-01 -> PA-11 (10 requirements)
- `itemised-charges`: IC-01 -> IC-09 (9 requirements)
- `client-accounts-and-credentials`: CAC-01 -> CAC-10 (10 requirements)
- `product-catalogue`: PC-01 -> PC-03 (3 requirements)
- `client-confirmation`: CC-01 -> CC-07 (7 requirements)
- `confirmation-facilitation`: CF-01 -> CF-02 (2 requirements)

## Rule for the traceability matrix

Copy the ID and the requirement text from this index into the matrix. Do not invent, renumber, merge or drop a row. If a requirement has no natural home in the design, that is a design defect to fix in the design body, not a row to delete.
