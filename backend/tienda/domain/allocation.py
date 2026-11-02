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

**The surplus stays as a residual.** A payment larger than the outstanding
leaves the excess in the customer's favour. It is not an error and it is not
silently dropped: it is reported as `residual` on the `Allocation`.

**A credit note imputes only to an older charge.** A `nota_credito` reduces
the debt of a charge that happened **at or before** the note itself
(`charge.occurred_at ≤ credit.occurred_at`). A note cannot retroactively
cancel a charge that is younger than it, and a note that matches no eligible
charge stays as residual credit.

The result is an `Allocation`: the per-pair assignments, the residual and
what is still owed on each charge.
"""

from __future__ import annotations

from decimal import Decimal

from .types import Allocation, EntryKind, LedgerLine

CERO = Decimal("0")


def allocate_payments(charges, payments, *, credit_notes=()) -> Allocation:
    """Retire `charges` with `payments`, oldest charge first.

    `charges` are the `cargo` ledger lines, `payments` the `pago` ledger
    lines and `credit_notes` the `nota_credito` ledger lines. All three are
    plain `LedgerLine` records.

    The allocation walks the charges in `(occurred_at, id)` order and the
    money in `(occurred_at, id)` order as well, so the result is
    deterministic.

    The returned `Allocation` carries:

    * `asignaciones` — one `(payment_id, charge_id, amount)` triple per
      allocation, in the order it was made;
    * `saldos` — the `(charge_id, amount)` still owed on each charge;
    * `residual` — the money that matched nothing, in the customer's favour.
    """
    # The money, oldest first. A credit note is money too, but it is not
    # fungible with a payment: it may only impute to a charge that is at
    # least as old as the note itself, so the two kinds are kept apart.
    pagos = _ordered(payments, EntryKind.PAGO)
    notas = _ordered(credit_notes, EntryKind.NOTA_CREDITO)
    cargos = sorted(charges, key=_order_key)

    # How much of each charge is still owed. A charge starts fully owed.
    pendiente: dict[int, Decimal] = {c.id: c.amount for c in cargos}

    asignaciones: list[tuple[int, int, Decimal]] = []

    # The credit notes reduce the debt **directly**. A `nota de crédito` is
    # money given back, not money received: it does not need a payment to
    # fund it, and it does not draw on the payments. It imputes to the
    # charges it is eligible for, oldest first, exactly like a payment
    # does — with the one restriction that it may only reach a charge that
    # is at least as old as the note itself.
    #
    # The notes go first because they are the most constrained money: a note
    # can never take from a charge that is younger than it, while a payment
    # can only reach charges that are older than it. Processing them first
    # keeps both guarantees exact.
    for nota in notas:
        restante = nota.amount
        for cargo in cargos:
            if restante <= CERO:
                break
            if nota.occurred_at < cargo.occurred_at:
                # The note is younger than this charge: it may not impute to
                # it, and it may not impute to any younger charge either.
                break
            if pendiente[cargo.id] <= CERO:
                continue
            toma = min(restante, pendiente[cargo.id])
            if toma <= CERO:
                continue
            asignaciones.append((nota.id, cargo.id, toma))
            pendiente[cargo.id] -= toma
            restante -= toma
        # Whatever the note could not place stays as residual.

    # The payments retire what the notes left.
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

    # The money that matched nothing is the customer's.
    total_pagado = sum((p.amount for p in pagos), CERO)
    total_notado = sum((n.amount for n in notas), CERO)
    asignado = sum((a[2] for a in asignaciones), CERO)
    residual = total_pagado + total_notado - asignado

    saldos = tuple((cargo.id, pendiente[cargo.id]) for cargo in cargos)

    return Allocation(asignaciones=tuple(asignaciones), residual=residual, saldos=saldos)


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
