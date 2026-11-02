"""The position of the shop: what the drawer holds and what is owed (CP-02, CP-03).

Three rules live here, and all three are pure functions over plain values.

**`outstanding(lines, at)`** — the debt the customers owe right now. It is
`Σ cargos − Σ pagos − Σ notas de crédito` over the entries whose
`occurred_at ≤ at`. It is **derived, never stored** (PA-01): there is no
balance column anywhere in the schema, and this function is where the number
comes from. A negative result is **not an error** — it is a residual in the
customer's favour, `credit_a_favor`, and it is reported as it is.

A charge under an open dispute is **still debt** (PA-04): a dispute removes
no amount from the debt. Only a `nota de crédito` reduces it.

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

    `Σ cargos − Σ pagos − Σ notas de crédito` over the entries whose
    `occurred_at ≤ at`.

    A negative result is a **residual in the customer's favour**
    (`credit_a_favor`), not an error: the customer paid more than they owed
    and the surplus is theirs. The function returns it unchanged.

    A `nota_credito` reduces the debt whatever it reconciles, because a
    credit note is money given back (PA-09). A charge under an open dispute
    is still counted in full (PA-04).
    """
    total = CERO
    for line in lines:
        if line.occurred_at > at:
            continue
        if line.kind == EntryKind.CARGO:
            total += line.amount
        elif line.kind == EntryKind.PAGO:
            total -= line.amount
        elif line.kind == EntryKind.NOTA_CREDITO:
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
