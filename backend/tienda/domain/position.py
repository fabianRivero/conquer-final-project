"""The position of the shop: what the drawer holds and what is owed (CP-02, CP-03).

Three rules live here, and all three are pure functions over plain values.

**`outstanding(lines, at)`** — the debt the customers owe right now. It is
`Σ cargos − Σ pagos` over the entries whose `occurred_at ≤ at`. It is
**derived, never stored** (PA-01): there is no balance column anywhere in
the schema, and this function is where the number comes from.

**The result is never negative.** A `pago` never exceeds the debt it retires
(rule 19): the shop returns the excess as change and it never enters the
book, so there is no credit to hold and no `credit_a_favor` state
(ADR-26).

**`cash_at(opening_cash, movements, pagos, at)`** — what the drawer holds.
It is `inicial + Σ(entradas) − Σ(salidas) + Σ(pagos)` over the movements
whose `occurred_at ≤ at`. A `pago` is **never** a `CashMovement`: it is a
`LedgerLine` of kind `pago`, and it reaches the drawer through the separate
`pagos` argument, so a payment is counted exactly once.

**`real_position(caja, outstanding_total)`** — what the owner actually has.
It is `caja + Σ pending balances`, **additive only**: the function adds the
two figures it is given and nothing else. It does not recompute either of
them, does not reach for a clock and does not consult a database, so it is
verifiable without one (CP-06).
"""

from __future__ import annotations

from decimal import Decimal

from .types import CashLine, EntryKind, LedgerLine, MovementKind

# The zero every money sum starts from. A `Decimal`, never a `float`: the
# figures are money and a binary float would not add up.
CERO = Decimal("0")


def outstanding(lines, at) -> Decimal:
    """The debt outstanding at `at`.

    `Σ cargos − Σ pagos` over the entries whose `occurred_at ≤ at`.

    **The result is never negative.** A `pago` larger than the debt it
    retires is refused at the transaction (rule 19), so a surplus never
    enters the book and there is no credit to hold. The v1 function returned
    a negative result as a residual in the customer's favour; that state
    does not exist any more (ADR-26).

    There is no third term: a `nota de crédito` is gone with the dispute
    machinery, and the itemisation is mandatory, so a charge always carries
    its lines and always carries its whole amount.
    """
    total = CERO
    for line in lines:
        if line.occurred_at > at:
            continue
        if line.kind == EntryKind.CARGO:
            total += line.amount
        elif line.kind == EntryKind.PAGO:
            total -= line.amount
    return total


def cash_at(opening_cash, movements, pagos, at) -> Decimal:
    """The cash in the drawer at `at`.

    `inicial + Σ(entradas) − Σ(salidas) + Σ(pagos)` over the movements whose
    `occurred_at ≤ at`.

    `movements` holds the `CashMovement` rows — an `entrada` adds to the
    drawer and a `salida` takes from it. `pagos` holds the `pago` ledger
    entries: a customer payment is money that came in, and it is a
    `LedgerEntry`, **never** a `CashMovement`, which is why it arrives
    through its own argument and is counted exactly once.
    """
    total = Decimal(opening_cash)
    for movement in movements:
        if movement.occurred_at > at:
            continue
        if movement.kind == MovementKind.ENTRADA:
            total += movement.amount
        elif movement.kind == MovementKind.SALIDA:
            total -= movement.amount
    for pago in pagos:
        if pago.occurred_at > at:
            continue
        total += pago.amount
    return total


def real_position(caja, outstanding_total) -> Decimal:
    """What the owner really has: the drawer plus the pending balances.

    `posicion_real = caja + Σ pending balances` — **additive only**.

    The function adds the two figures it is handed and does nothing else: it
    does not recompute the drawer, does not recompute the debt, does not
    reach for a clock and does not consult a database. That is what makes it
    verifiable without one (CP-06), and it is why a payment leaves the
    position unchanged — the payment moves money from the pending balances
    into the drawer, and the two cancel (CP-03).
    """
    return Decimal(caja) + Decimal(outstanding_total)
