# Task Source Index — `fiado-confirmado` (v2 model)

**Machine-derived from `requirement-index.md` and `design.md`. Do not re-derive, re-count or re-enumerate the requirement set in your reasoning.**

Each row is one requirement. The `Design home` column is already resolved from the design's own traceability matrix — copy it, do not derive it.

| ID | Requirement | Verif. | Scen. | Cond. | Design home |
|---|---|---|---|---|---|
| CP-01 | Cash movements are recorded and validated | integration | 2 |  | §3 `CashMovement`; §3.2 rule 12; §9.1 |
| CP-02 | `caja` is recorded cash movements | unit, integration | 2 |  | §10 `cash_at` |
| CP-03 | `posicion_real` is additive | unit, integration | 2 |  | §10 `real_position`; ADR-9 |
| CP-04 | The day close is the anchor of `caja` | integration | 2 |  | §3 `DayClose`; §3.2 rule 13; §10 `caja_al_cierre` |
| CP-05 | The day close is available to both shop roles | integration | 1 |  | §7 rows 1–2; §9.1 `GET /api/v1/cierre/`; §9.2 close serializers |
| CP-06 | The position rule is pure and ORM-free | unit | 1 |  | §10 `real_position`; ADR-3 |
| CP-07 | `existencias_registradas` is a ceiling, never a count | unit, integration | 2 | C | §2 D5; §10 `existencias_registradas` |
| PA-01 | `outstanding` is derived, never stored | unit, integration | 3 |  | §10 `outstanding`; §3.1 not-stored; §3.2 rule 19 |
| PA-02 | Payments are allocated FIFO | unit | 4 |  | §10 `allocate_payments`; ADR-7; ADR-26; ADR-27 |
| PA-03 | Ageing buckets are derived per charge | unit, integration | 1 |  | §10 `bucket_of`, `age_in_days` |
| PA-05 | The credit limit is an explicit state | integration | 2 |  | §3 `Customer.credit_limit` |
| PA-06 | Suspension is automatic and evaluated on read | unit, integration | 2 |  | §10 `evaluate_customer`; §2 D1 |
| PA-07 | A suspended customer cannot receive a new charge | integration | 2 |  | §3.2 rules 1–2, 8; §9.3 |
| PA-08 | The owner can lift a suspension explicitly | integration | 2 |  | §3 `suspended_override_at`; §9.1 |
| PA-09 | A payment is recorded only by the owner | integration | 2 |  | §7 `pago` row; §8 (a proposal is a request); §13.3 |
| PA-10 | The ledger write API is validated | integration | 2 |  | §9.1; §9.3; §3.2 rules 4, 16, 17 |
| PA-11 | The credit rules are pure and ORM-free | unit | 1 |  | §10; ADR-3 |
| IC-01 | The ledger is append-only | integration | 2 |  | §3.1 immutability; §9.1 |
| IC-02 | The amount of a `cargo` equals its itemisation total | integration | 2 |  | §10 `charge_amount_matches`; §3.2 rule 3 |
| IC-03 | A charge exists only after the client confirms it | unit, integration | 2 |  | §1 idea 3; §6; ADR-19; §3.2 rule 5 |
| IC-04 | The effective confirmation state is derived | unit, integration | 1 |  | §10 `estado_cargo`; ADR-18 |
| IC-05 | The `cargo` write API is validated | integration | 1 |  | §9.1; §9.3 |
| IC-06 | The charge rules are pure and ORM-free | unit | 1 |  | §10 `charges.py`; ADR-3 |
| IC-07 | A `cargo` carries `CargoLinea` rows | integration | 2 | C | §3 `CargoLinea`; §3.2 rule 3; §10 |
| IC-08 | `precio_unitario` is a snapshot | integration | 2 | C | §3 `CargoLinea`; §2 D8 |
| IC-09 | Charge lines are immutable with their charge | integration | 1 | C | §3.1 immutability |
| CAC-01 | Two shop roles exist and are enforced on the server | integration | 1 |  | §7; ADR-5 |
| CAC-02 | The credit book is owner-only among the staff | integration | 3 |  | §7.1; §9.2 |
| CAC-03 | No staff session reaches the client surface or gains a client scope | integration | 1 |  | §8; §7.2 |
| CAC-04 | Sessions and CSRF protect every staff mutation | integration | 1 |  | §12; §9.1 |
| CAC-05 | The customer record minimises personal data | integration | 2 |  | §3 `Customer`; §3.1 not-stored |
| CAC-06 | The views consume the application's own API at the public URL | e2e | 2 |  | §11 same-origin; §15.3 |
| CAC-07 | Production is locked and secrets stay out of the repository | e2e | 2 |  | §12; §18.1 |
| CAC-08 | One account per shop role is seeded | integration, e2e | 2 |  | §18.2; §15.3 |
| CAC-09 | The `codigo` is a scoped, per-shop credential | integration | 2 | C | §5; §2 D2–D4 |
| CAC-10 | The client payload carries nothing but that customer's own data | integration | 1 | C | §9.2 `EstadoClienteSerializer`; §12.1 |
| PC-01 | The catalogue holds only the goods eligible for fiado | integration | 2 |  | §3 `Producto.activo` |
| PC-02 | `precio` is a default, not a constraint | integration | 2 |  | §2 D8; §10 `precio_unitario_de` |
| PC-03 | The catalogue is readable and seeded | integration | 1 |  | §3 `Producto`; §18.2 |
| CC-01 | A charge exists only once the client has confirmed it | integration | 3 | C | §6; §9.1 `…/confirmar/`; §13.1; ADR-19, ADR-20 |
| CC-02 | The statement shows every confirmed charge of that client | integration | 3 | C | §9.2 `EstadoClienteSerializer` (`pagado`, `saldo`); §13.4; ADR-27 |
| CC-03 | The prepared proposal is shown on the shop's screen | integration | 2 | C | §11 `/app/propuesta/{id}`; §9.1 `…/pantalla/`; §9.2 `PropuestaPantallaSerializer` |
| CC-04 | The client may cancel a proposal | integration | 1 | C | §6; §9.1 `…/cancelar/`; §13.2 |
| CC-05 | The client view consumes the application's own API | e2e | 1 | C | §11 same-origin; §15.3 |
| CC-06 | A confirmed charge shows its full itemisation | integration | 1 | C | §9.2 `EstadoClienteSerializer` (`lineas[]`); §13.4 |
| CC-07 | The client may propose a payment and the owner records it | integration | 4 | C | §7 propose/validate rows; §8; §13.3; §3 `PagoPropuesto`, `ImputacionPago`; ADR-27 |
| CF-01 | The `dependiente` prepares one proposal and records its confirmation | integration | 2 | C | §2 D6; §7 proposal rows; §6; §13.1 |
| CF-02 | The facilitator is recorded and holds no client scope | integration | 2 | C | §3 `facilitado_por_id`; §8; §13.1 |

## Totals

- Requirements: **48**, each mapped to a design home.
- Conditional requirements: **15** (marked `C`).
- Scenarios: **88**.

## The entities the models must declare

Sixteen, per `design.md` §3: `Shop`, `User`, `Customer`, `FiadoPropuesto`, `PropuestaLinea`,
`LedgerEntry`, `CargoLinea`, `CashMovement`, `StockMovement`, `DayClose`, `Producto`,
`Confirmacion`, `PagoPropuesto`, `ImputacionPago`, `CustomerCodigo`, `CodigoIntento`.

`LEDGER_ENTRY_KINDS` has **two** values: `cargo`, `pago`. `Confirmacion` has **one** state:
`confirmado`. The itemisation is **mandatory**: a charge without lines cannot exist.

`ImputacionPago` records the repartition of a payment: one row per (payment, charge) pair the
payment touches, with the grain of the **charge**. A `pago` of 20,00 € that retires charges of
8,00 €, 7,00 € and 15,00 € writes three rows — 8,00 €, 7,00 € and 5,00 €. `PagoPropuesto` names
**no** charge: the client proposes an amount and the FIFO decides which debts it retires.

## The two mutable rows

`FiadoPropuesto` and `PagoPropuesto` only, each moving once from `pendiente` to exactly one of
`confirmado`/`cancelado` and `validado`/`rechazado`. Every other row is append-only.

## The client never writes to the ledger

The `codigo` grants **read** over the client's own statement and the right to **propose** a
payment. It grants no write: no `LedgerEntry`, no `CargoLinea`, no `Confirmacion`, no
`FiadoPropuesto`, no `PagoPropuesto` resolution. The confirmation is given on the shop's
screen and recorded by the staff session; the payment is recorded by the owner.
