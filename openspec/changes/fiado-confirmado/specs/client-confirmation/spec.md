# client-confirmation Specification

## Purpose

The confirmation a client gives to a charge the owner has prepared, and the statement that shows what they owe.

The client never writes to the credit book. The owner prepares a `FiadoPropuesto`; the client sees it on a screen prepared in the shop, in front of the owner, and confirms it there; the owner records the confirmation, and only then does the charge exist and become debt.

**This whole domain is conditional.** CC-01 through CC-05 depend on Regla 4: the client-facing surface exists only if the owner asks for the confirmation and the client gives it. A Regla-4 cut removes this directory entirely.

## Conditional Requirements

### Requirement: CC-01 — A charge exists only once the client has confirmed it

**Conditional:** Regla 4 — if it empties, the confirmation flow is cut, the client-facing surface disappears and the project becomes `fiado desglosado`.

A charge MUST NOT be recorded before the client has confirmed the proposal it comes from. The owner MUST prepare a `FiadoPropuesto` carrying the customer, its itemisation and its total; the client confirms that proposal on the shop's screen; and the confirmation MUST be recorded as a `Confirmacion` in state `confirmado` carrying `confirmado_en`. The `LedgerEntry` of kind `cargo` and its `CargoLinea` MUST be written in the same transaction that records the confirmation, so a charge without a confirmation cannot exist.

**Verification:** integration

#### Scenario: The confirmation creates the charge

- GIVEN an owner with a prepared `FiadoPropuesto` of 6,40 € for a client
- WHEN the client confirms it and the owner records the confirmation
- THEN a `Confirmacion` in state `confirmado` exists, a `cargo` of 6,40 € exists with its lines, and the client's outstanding grows by 6,40 €

#### Scenario: A proposal alone creates no debt

- GIVEN an owner with a prepared `FiadoPropuesto` of 6,40 € for a client
- WHEN no confirmation has been recorded
- THEN no `cargo` exists and the client's outstanding does not include the 6,40 €

#### Scenario: A proposal cannot be confirmed twice

- GIVEN a proposal already confirmed
- WHEN the owner records a second confirmation for it
- THEN the response is 422 with `codigo_error` `propuesta_ya_confirmada` and no second `Confirmacion` is appended

### Requirement: CC-02 — The statement shows every confirmed charge of that client

**Conditional:** Regla 4 — if it empties, the client-facing surface disappears and there is no statement.

The statement MUST list every confirmed charge of the presenting client with its amount, its date and its confirmation date and time; the total owed MUST be reported, and no charge of any other customer MUST appear. A charge that the client has not confirmed MUST NOT appear, because it does not exist.

**Verification:** integration

#### Scenario: The statement lists the client's own confirmed charges

- GIVEN a client with two confirmed charges
- WHEN the client reads the statement
- THEN both appear with their amounts and their confirmation dates and the total equals their sum

#### Scenario: A client with no charges reads an empty statement

- GIVEN a client with no confirmed charges
- WHEN the client reads the statement
- THEN the statement is empty, the total is zero and the request succeeds

#### Scenario: Each charge shows what was paid and what is still owed

- GIVEN a client with confirmed charges of 8,00 €, 7,00 € and 15,00 €, and a payment of 20,00 € already recorded
- WHEN the client reads the statement
- THEN the three charges read 8/8 paid, 7/7 paid and 5/15 paid, and the total owed is 10,00 €

### Requirement: CC-03 — The prepared proposal is shown on the shop's screen

**Conditional:** Regla 4 — if it empties, there is no screen to show and the project becomes `fiado desglosado`.

A prepared `FiadoPropuesto` MUST be shown to the client on a screen prepared in the shop, on the shop's own device, with its full itemisation — product, quantity and `precio_unitario` for every line — and its total. The client MUST be able to confirm that screen. The screen MUST NOT be reachable from the client's own portal: the client confirms in the shop, not at home.

**Verification:** integration

#### Scenario: The screen shows the whole itemisation

- GIVEN a prepared `FiadoPropuesto` of two lines totalling 6,40 €
- WHEN the shop displays the proposal screen
- THEN it shows each line's product, quantity and price, and the total of 6,40 €

#### Scenario: The client confirms from the shop screen

- GIVEN the same proposal on the shop's screen
- WHEN the client confirms it
- THEN the owner's confirmation action records the confirmation and the charge exists

### Requirement: CC-04 — The client may cancel a proposal

**Conditional:** Regla 4 — if it empties, there is no screen and no proposal can be cancelled.

A client MUST be able to decline a proposal shown on the shop's screen; the owner MUST then be able to cancel the `FiadoPropuesto`, and a cancelled proposal MUST NOT become a charge and MUST NOT move the client's outstanding.

**Verification:** integration

#### Scenario: The client declines and the owner cancels

- GIVEN a prepared `FiadoPropuesto` of 6,40 € for a client
- WHEN the client declines it and the owner cancels the proposal
- THEN the proposal reads cancelled, no `cargo` exists and the client's outstanding does not include the 6,40 €

### Requirement: CC-05 — The client view consumes the application's own API

**Conditional:** Regla 4 — if it empties, the client-facing surface disappears; the non-negotiable itself survives in the owner surface, specified by CAC-06.

Every client-facing view MUST read the application's own API at the public URL, on the same origin, through relative paths, presenting the `codigo` per request; it MUST NOT use CORS, a second host, a second URL or hard-coded figures.

**Verification:** e2e

#### Scenario: The client page reads the same origin

- GIVEN a client with a `codigo` at the public URL
- WHEN `/app/cliente` is loaded
- THEN the request goes to the client API on the same origin and no cross-origin request is made

### Requirement: CC-06 — A confirmed charge shows its full itemisation

**Conditional:** Regla 5 — if it empties, the catalogue and the `CargoLinea` are cut and the statement shows the amount only.

A confirmed charge MUST show its full itemisation to the client: product, quantity and `precio_unitario` for every line. This is the itemisation the client confirmed, so it MUST be the itemisation the client sees.

**Verification:** integration

#### Scenario: The confirmed charge is itemised

- GIVEN a confirmed `cargo` of two lines totalling 6,40 €
- WHEN the client reads the statement
- THEN each line shows its product, its quantity and its price

### Requirement: CC-07 — The client may propose a payment and the owner records it

**Conditional:** Regla 4 — if it empties, the client-facing surface disappears and a client cannot propose a payment.

A client MUST be able to propose a payment from their portal, stating the amount and a reference to their payment; the proposal MUST NOT itself write to the credit book, and only the owner MUST record the payment in the ledger after validating it. A client MUST NOT write to the credit book by any route. The proposal MUST NOT name a charge: the payment imputes against the client's own open charges, oldest first.

**Verification:** integration

#### Scenario: The proposal does not touch the ledger

- GIVEN a client with a confirmed `cargo` of 20,00 €
- WHEN the client proposes a payment of 20,00 € from the portal
- THEN no `pago` exists and the client's outstanding still shows 20,00 €

#### Scenario: The owner records the validated payment

- GIVEN the same proposed payment
- WHEN the owner validates it and records it
- THEN a `pago` of 20,00 € exists and the client's outstanding drops by 20,00 €

#### Scenario: The payment imputes against the oldest charges first

- GIVEN a client with confirmed charges of 8,00 €, 7,00 € and 15,00 €, in that order
- WHEN the owner validates a proposed payment of 20,00 €
- THEN the `pago` of 20,00 € is recorded, and the three charges read 8/8 paid, 7/7 paid and 5/15 paid

#### Scenario: A proposed payment larger than the outstanding is refused

- GIVEN a client whose outstanding is 30,00 €
- WHEN the owner validates a proposed payment of 35,00 €
- THEN the request is refused, no `pago` exists and the outstanding still shows 30,00 €

