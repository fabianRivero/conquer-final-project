# client-confirmation Specification

## Purpose

The client-facing surface: the confirmation a debtor gives their own charge, the statement that shows what they owe, and the rule that a debt is never hidden from the person who carries it.

**This whole domain is conditional.** CC-01 through CC-05 depend on Regla 4: the client-facing surface exists only if the owner asks for the confirmation and the client confirms. CC-06 and CC-07 additionally depend on Regla 5, which cuts the catalogue and the `CargoLinea`. A Regla-4 cut removes this directory entirely.

## Conditional Requirements

### Requirement: CC-01 — The client confirms their own charge

**Conditional:** Regla 4 — if it empties, the confirmation flow is cut, the client-facing surface disappears and the project becomes `fiado desglosado`.

A client presenting a valid `codigo` MUST be able to confirm one of their own charges; the confirmation MUST be appended as a `Confirmacion` in state `confirmado`, MUST carry `confirmado_en`, and the effective state of the charge MUST become `confirmado`. A confirmation MUST NOT be accepted for a charge that is not the presenting client's, and a charge MUST NOT be confirmed twice.

**Verification:** integration

#### Scenario: The client confirms a pending charge

- GIVEN a client with a `codigo` and one unconfirmed `cargo` of 6,40 €
- WHEN the client confirms it
- THEN the response carries `confirmado_en` and the charge's effective state is `confirmado`

#### Scenario: A second confirmation is refused

- GIVEN a `cargo` the client already confirmed
- WHEN the client confirms it again
- THEN the response is 422 with `codigo_error` `cargo_ya_confirmado` and no second `Confirmacion` is appended

#### Scenario: Another client's charge cannot be confirmed

- GIVEN a `cargo` belonging to a different `Customer`
- WHEN the client presents their own `codigo` and tries to confirm it
- THEN the request is refused and no `Confirmacion` is appended

### Requirement: CC-02 — The statement shows every charge of that client

**Conditional:** Regla 4 — if it empties, the client-facing surface disappears and there is no statement.

The statement MUST list every charge of the presenting client with its amount, its date and its effective state; a confirmed charge MUST also show the date and time of its confirmation. The total owed MUST be reported, and no charge of any other customer MUST appear.

**Verification:** integration

#### Scenario: The statement lists the client's own charges

- GIVEN a client with one `confirmado` and one `sin_confirmar` charge
- WHEN the client reads the statement
- THEN both appear with their amounts and states and the total equals their sum

#### Scenario: A client with no charges reads an empty statement

- GIVEN a client with no charges
- WHEN the client reads the statement
- THEN the statement is empty, the total is zero and the request succeeds

### Requirement: CC-03 — An unconfirmed charge is a summary row with a `Confirmar` action

**Conditional:** Regla 4 — if it empties, the client-facing surface disappears and there is no statement and no `Confirmar` action.

An unconfirmed charge MUST appear in the statement as a summary row holding its date and its amount, together with a `Confirmar` action; its detail MUST NOT be disclosed anywhere outside that action. The amount MUST NOT be withheld: the client always sees what they owe.

**Verification:** integration

#### Scenario: The summary row hides the detail but not the amount

- GIVEN an unconfirmed `cargo` of 6,40 € with two lines
- WHEN the client reads the statement
- THEN the row shows the date and 6,40 € and no line of the charge is disclosed

#### Scenario: The detail is disclosed inside the action

- GIVEN the same unconfirmed `cargo`
- WHEN the client opens the `Confirmar` action
- THEN the charge's detail is disclosed there

### Requirement: CC-04 — The client may dispute a charge

**Conditional:** Regla 4 — if it empties, the client-facing surface disappears and no dispute can be raised by a client.

A client MUST be able to dispute one of their own charges, stating `importe_reclamado` and an optional note; the dispute MUST be appended as a `Confirmacion` in state `en_disputa` and MUST NOT change the amount of the charge.

**Verification:** integration

#### Scenario: The client disputes the amount

- GIVEN a `cargo` of 6,40 € the client has not confirmed
- WHEN the client disputes it claiming 4,20 €
- THEN a `Confirmacion` in state `en_disputa` with `importe_reclamado` 4,20 € is appended and the charge still reads 6,40 €

#### Scenario: Another client's charge cannot be disputed

- GIVEN a `cargo` belonging to a different `Customer`
- WHEN the client presents their own `codigo` and tries to dispute it
- THEN the request is refused and no `Confirmacion` is appended

### Requirement: CC-05 — The client view consumes the application's own API

**Conditional:** Regla 4 — if it empties, the client-facing surface disappears; the non-negotiable itself survives in the owner surface, specified by CAC-06.

Every client-facing view MUST read the application's own API at the public URL, on the same origin, through relative paths, presenting the `codigo` per request; it MUST NOT use CORS, a second host, a second URL or hard-coded figures.

**Verification:** e2e

#### Scenario: The client page reads the same origin

- GIVEN a client with a `codigo` at the public URL
- WHEN `/app/cliente` is loaded
- THEN the request goes to the client API on the same origin and no cross-origin request is made

### Requirement: CC-06 — A confirmed charge shows its full itemisation

**Conditional:** Regla 5 — if it empties, the catalogue and the `CargoLinea` are cut and the confirmation and the statement show the amount only.

A confirmed charge MUST show its full itemisation to the client: product, quantity and `precio_unitario` for every line.

**Verification:** integration

#### Scenario: The confirmed charge is itemised

- GIVEN a confirmed `cargo` of two lines totalling 6,40 €
- WHEN the client reads the statement
- THEN each line shows its product, its quantity and its price

### Requirement: CC-07 — The itemisation of an unconfirmed charge is revealed only inside the action

**Conditional:** Regla 5 — if it empties, there is no itemisation to reveal and the `Confirmar` action shows the amount only.

The itemisation of an unconfirmed charge MUST be disclosed only inside the `Confirmar` action and MUST NOT appear in the statement, in any aggregate or in any error body.

**Verification:** integration

#### Scenario: The statement carries no line of an unconfirmed charge

- GIVEN an unconfirmed `cargo` with two lines
- WHEN the client reads the statement
- THEN no line of that charge appears anywhere in the response
