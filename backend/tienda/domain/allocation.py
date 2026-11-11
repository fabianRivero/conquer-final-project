"""How the money that came back retires the debt (PA-02).

`allocate_payments` is the FIFO retirement of a customer's charges. One
rule, three parts, and one guarantee each.

**FIFO by `(occurred_at, id)`.** The oldest charge is settled first. The
order is the pair `(occurred_at, id)`, not `occurred_at` alone: two charges
recorded on the same instant are ordered by their identifier, so the
allocation is **total** — there is no tie left to chance, and the same
fixture always produces the same result.

**A partial payment retires a charge in part.** A payment smaller than the
oldest charge does not skip it and does not settle it: it takes a slice out
of it and the remainder stays owed.

**No residual is possible.** A payment larger than the outstanding is
refused at the transaction (rule 19): the shop returns the excess as change
and it never enters the book, so every cent of every payment is always
placed. The `residual` field stays on the `Allocation` record and is always
zero — it is kept so a caller that reads it has one shape to read, not
because a surplus is a legal state (ADR-26).

**The repartition is recorded, not recomputed.** `imputations_of` turns the
allocation into the rows the service layer persists: one per (payment,
charge) pair, **with the grain of the charge**. A payment of 20,00 € that
retires charges of 8,00 €, 7,00 € and 15,00 € produces three imputations —
8,00 €, 7,00 € and 5,00 € — and the charges read 8/8, 7/7 and 5/15
(ADR-27).
"""

from __future__ import annotations

from decimal import Decimal

from .types import Allocation, EntryKind, Imputacion, LedgerLine

CERO = Decimal("0")


def allocate_payments(charges, payments) -> Allocation:
    """Retire `charges` with `payments`, oldest charge first.

    `charges` are the `cargo` ledger lines and `payments` the `pago` ledger
    lines. All of them are plain `LedgerLine` records.

    The allocation walks the charges in `(occurred_at, id)` order and the
    money in `(occurred_at, id)` order as well, so the result is
    deterministic.

    The returned `Allocation` carries:

    * `asignaciones` — one `(payment_id, charge_id, amount)` triple per
      allocation, in the order it was made;
    * `saldos` — the `(charge_id, amount)` still owed on each charge;
    * `residual` — always zero; a surplus is refused before it can exist.

    There is **no `credit_notes` parameter** any more. The v1 function took
    one and applied the notes directly to the charges; with the dispute
    machinery gone there is no `nota de crédito` to apply, and a `pago`
    imputes only against a `cargo`.
    """
    # The money, oldest first.
    pagos = _ordered(payments, EntryKind.PAGO)
    cargos = sorted(charges, key=_order_key)

    # How much of each charge is still owed. A charge starts fully owed.
    pendiente: dict[int, Decimal] = {c.id: c.amount for c in cargos}

    asignaciones: list[tuple[int, int, Decimal]] = []

    # The payments retire the charges, oldest first.
    for pago in pagos:
        restante = pago.amount
        for cargo in cargos:
            if restante <= CERO:
                break
            if pendiente[cargo.id] <= CERO:
                continue
            if cargo.occurred_at > pago.occurred_at:
                # A payment may only retire a charge that is at least as old
                # as the payment itself.
                break
            toma = min(restante, pendiente[cargo.id])
            if toma <= CERO:
                continue
            asignaciones.append((pago.id, cargo.id, toma))
            pendiente[cargo.id] -= toma
            restante -= toma

    # The money that matched nothing would be the customer's. Rule 19 makes
    # it impossible: a `pago` larger than the debt it retires is refused
    # before it reaches this function. The residual is therefore always zero,
    # and it is computed here rather than assumed so that a caller which
    # passes an overpayment learns the truth instead of a stale field.
    total_pagado = sum((p.amount for p in pagos), CERO)
    asignado = sum((a[2] for a in asignaciones), CERO)
    residual = total_pagado - asignado

    saldos = tuple((cargo.id, pendiente[cargo.id]) for cargo in cargos)

    return Allocation(asignaciones=tuple(asignaciones), residual=residual, saldos=saldos)


def imputations_of(allocation, payment_id) -> tuple[Imputacion, ...]:
    """The rows to persist for one payment, one per charge it touched.

    `allocation` is the result of `allocate_payments` and `payment_id` the
    identifier of the payment whose rows are wanted. The result is the
    tuple of `Imputacion` records the service layer writes to the
    `ImputacionPago` table.

    **The grain is the charge.** A charge of 15,00 € made of three
    `CargoLinea` rows is one debt of 15,00 €, and a payment that settles
    5,00 € of it produces **one** imputation against the charge — not three
    against the lines. The design defines no policy for splitting a partial
    payment across the lines of a single charge, and it does not need one:
    the `desglose` says what was bought, the debt says what is owed and the
    repayment says what was paid against the debt (ADR-27).

    The rows come out in the order the allocation made them, which is FIFO
    by charge, so the persisted repartition reads in the same order the
    money was applied.
    """
    return tuple(
        Imputacion(pago_id=payment_id, cargo_id=cargo_id, importe=importe)
        for (pago, cargo_id, importe) in allocation.asignaciones
        if pago == payment_id
    )


def _ordered(lines, kind: EntryKind):
    """The lines of `kind`, oldest first by `(occurred_at, id)`."""
    return sorted(
        (line for line in lines if line.kind == kind),
        key=_order_key,
    )


def _order_key(line: LedgerLine):
    """The FIFO order key of a line: `(occurred_at, id)`.

    The identifier is the tie-breaker, so two lines recorded at the same
    instant are still totally ordered and the allocation is deterministic.
    """
    return (line.occurred_at, line.id)
