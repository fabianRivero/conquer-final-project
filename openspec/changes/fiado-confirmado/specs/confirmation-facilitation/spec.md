# confirmation-facilitation Specification

## Purpose

The one narrow capability that lets the shop keep working when the owner is away: the `dependiente` presents the charge in front of the client and receives the confirmation — and nothing else.

## Conditional Requirements

### Requirement: CF-01 — The `dependiente` presents one charge and receives the confirmation

**Conditional:** Condición de la capacidad 8 (N5) — if the interviews show that the owner personally gives every `fiado`, this capability is not added and the 403 of the `dependiente` over the credit book stays intact.
**Conditional:** Regla 4 — if it empties, the confirmation flow is cut and this capability disappears with it.

The `dependiente` MUST be able to present exactly one charge at a time to a client and to receive that client's confirmation. It MUST NOT see a list of charges, a balance, the ageing or any charge other than the one presented, and every other credit-book endpoint MUST answer it with HTTP 403.

**Verification:** integration

#### Scenario: The helper presents the charge in front of the client

- GIVEN a `dependiente` account and a pending `cargo` of 6,40 €
- WHEN the helper presents it and the client confirms it with their own `codigo`
- THEN the charge is `confirmado` and the helper sees only that charge

#### Scenario: The helper cannot reach the rest of the credit book

- GIVEN a `dependiente` account
- WHEN it requests the customer list, a balance, the ageing or another charge
- THEN every response is 403 with no partial data

### Requirement: CF-02 — The facilitator is recorded and holds no client scope

**Conditional:** Condición de la capacidad 8 (N5) — if the interviews show that the owner personally gives every `fiado`, this capability is not added and the `dependiente` 403 boundary stays intact.
**Conditional:** Regla 4 — if it empties, the confirmation flow is cut and this capability disappears with it.

Every confirmation received through this capability MUST record `facilitado_por`, the user who presented the charge. The `dependiente` MUST NOT hold a client scope and MUST NOT present the client's `codigo` on the client's behalf: the client presents their own credential.

**Verification:** integration

#### Scenario: The facilitation is auditable

- GIVEN a confirmation received through the helper
- WHEN it is read
- THEN it carries `facilitado_por` naming the `dependiente`

#### Scenario: The client presents their own credential

- GIVEN a `dependiente` presenting a charge
- WHEN the client confirms it
- THEN the client presented their own `codigo` and no client scope exists in the helper's session
