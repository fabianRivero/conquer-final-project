# confirmation-facilitation Specification

## Purpose

The one narrow capability that lets the shop keep working when the owner is away: the `dependiente` prepares a proposal in front of the client and records the client's confirmation of it — and nothing else.

The client confirms on the shop's screen. The helper never holds a client scope and never acts on the client's behalf.

## Conditional Requirements

### Requirement: CF-01 — The `dependiente` prepares one proposal and records its confirmation

**Conditional:** Condición de la capacidad 8 (N5) — if the interviews show that the owner personally gives every `fiado`, this capability is not added and the 403 of the `dependiente` over the credit book stays intact.
**Conditional:** Regla 4 — if it empties, the confirmation flow is cut and this capability disappears with it.

The `dependiente` MUST be able to prepare exactly one `FiadoPropuesto` at a time for a client and to record that client's confirmation of it. It MUST NOT see a list of charges, a balance, the ageing or any charge other than the one presented, and every other credit-book endpoint MUST answer it with HTTP 403.

**Verification:** integration

#### Scenario: The helper prepares and confirms in front of the client

- GIVEN a `dependiente` account and a proposal of 6,40 € for a client
- WHEN the helper presents it on the shop's screen, the client confirms it, and the helper records the confirmation
- THEN a `Confirmacion` in state `confirmado` exists, the charge of 6,40 € exists, and the helper saw only that proposal

#### Scenario: The helper cannot reach the rest of the credit book

- GIVEN a `dependiente` account
- WHEN it requests the customer list, a balance, the ageing or another charge
- THEN every response is 403 with no partial data

### Requirement: CF-02 — The facilitator is recorded and holds no client scope

**Conditional:** Condición de la capacidad 8 (N5) — if the interviews show that the owner personally gives every `fiado`, this capability is not added and the `dependiente` 403 boundary stays intact.
**Conditional:** Regla 4 — if it empties, the confirmation flow is cut and this capability disappears with it.

Every confirmation received through this capability MUST record `facilitado_por`, the user who presented the proposal. The `dependiente` MUST NOT hold a client scope: the client confirms on the shop's screen, and no client credential passes through the helper's session.

**Verification:** integration

#### Scenario: The facilitation is auditable

- GIVEN a confirmation received through the helper
- WHEN it is read
- THEN it carries `facilitado_por` naming the `dependiente`

#### Scenario: No client credential passes through the helper

- GIVEN a `dependiente` preparing a proposal
- WHEN the client confirms it
- THEN no client scope exists in the helper's session and no client credential was presented by the helper
