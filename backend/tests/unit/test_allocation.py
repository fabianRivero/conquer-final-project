"""The FIFO retirement of debt, and the repartition it records.

Two guarantees are under test here.

**The allocation.** `allocate_payments` walks the charges oldest first and
the money oldest first, and the pair `(occurred_at, id)` makes the order
total. A payment smaller than the oldest charge retires it in part; a
payment larger than the debt is refused at the transaction, so the
allocation never leaves a residual.

**The repartition.** `imputations_of` turns the allocation into the rows
the service layer persists: one per (payment, charge) pair, **with the grain
of the charge**. This is the mechanism behind the owner's charges reading
8/8, 7/7 and 5/15 after a payment of 20,00 € against charges of 8,00 €, 7,00
€ and 15,00 € (ADR-27).
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from tienda.domain.allocation import allocate_payments, imputations_of
from tienda.domain.types import CargoLine, EntryKind, LedgerLine

# The instant every fixture is stamped with. No implicit clock anywhere.
T0 = datetime(2026, 5, 1, 9, 0, 0)


def _cargo(id, amount, *, dias=0):
    """A charge line of the ledger."""
    return LedgerLine(
        id=id,
        kind=EntryKind.CARGO,
        amount=Decimal(amount),
        occurred_at=T0 + timedelta(days=dias),
    )


def _pago(id, amount, *, dias=0):
    """A payment line of the ledger."""
    return LedgerLine(
        id=id,
        kind=EntryKind.PAGO,
        amount=Decimal(amount),
        occurred_at=T0 + timedelta(days=dias),
    )


# ---------------------------------------------------------------------------
# The allocation
# ---------------------------------------------------------------------------


def test_the_oldest_charge_is_retired_first():
    """FIFO: the oldest charge is settled first."""
    cargo10 = _cargo(1, "10.00", dias=0)
    cargo40 = _cargo(2, "40.00", dias=19)
    pago = _pago(9, "30.00", dias=20)

    resultado = allocate_payments([cargo10, cargo40], [pago])

    saldos = dict(resultado.saldos)
    assert saldos[1] == Decimal("0.00")
    assert saldos[2] == Decimal("20.00")


def test_the_allocation_names_the_payment_and_the_charge():
    """Each assignment is a `(payment_id, charge_id, amount)` triple."""
    cargo = _cargo(1, "10.00")
    pago = _pago(9, "4.00")

    resultado = allocate_payments([cargo], [pago])

    assert resultado.asignaciones == ((9, 1, Decimal("4.00")),)


def test_a_payment_smaller_than_the_oldest_charge_retires_it_in_part():
    """A partial payment takes a slice and leaves the rest owed."""
    cargo10 = _cargo(1, "10.00", dias=0)
    cargo40 = _cargo(2, "40.00", dias=19)
    pago = _pago(9, "6.00", dias=20)

    resultado = allocate_payments([cargo10, cargo40], [pago])

    saldos = dict(resultado.saldos)
    assert saldos[1] == Decimal("4.00")
    assert saldos[2] == Decimal("40.00")


def test_the_order_is_by_occurred_at_and_then_by_id():
    """The identifier is the tie-breaker, so the order is total.

    Two charges recorded at the same instant are ordered by their
    identifier, so the same fixture always produces the same result.
    """
    cargo_a = _cargo(1, "10.00", dias=0)
    cargo_b = _cargo(2, "10.00", dias=0)
    pago = _pago(9, "15.00", dias=0)

    resultado = allocate_payments([cargo_a, cargo_b], [pago])

    assert resultado.asignaciones == (
        (9, 1, Decimal("10.00")),
        (9, 2, Decimal("5.00")),
    )


def test_several_payments_retire_the_charges_in_order():
    """Two payments retire in order, the second finishing the job."""
    cargo10 = _cargo(1, "10.00", dias=0)
    cargo40 = _cargo(2, "40.00", dias=19)
    pago_a = _pago(8, "10.00", dias=20)
    pago_b = _pago(9, "40.00", dias=21)

    resultado = allocate_payments([cargo10, cargo40], [pago_a, pago_b])

    saldos = dict(resultado.saldos)
    assert saldos[1] == Decimal("0.00")
    assert saldos[2] == Decimal("0.00")
    assert resultado.asignaciones == (
        (8, 1, Decimal("10.00")),
        (9, 2, Decimal("40.00")),
    )


def test_a_payment_may_not_retire_a_charge_that_is_younger_than_it():
    """A payment only reaches charges that are at least as old as it."""
    cargo = _cargo(1, "10.00", dias=10)
    pago = _pago(9, "10.00", dias=0)

    resultado = allocate_payments([cargo], [pago])

    assert resultado.asignaciones == ()
    assert dict(resultado.saldos)[1] == Decimal("10.00")


def test_an_empty_ledger_allocates_nothing():
    """Nothing in, nothing out."""
    resultado = allocate_payments([], [])

    assert resultado.asignaciones == ()
    assert resultado.saldos == ()
    assert resultado.residual == Decimal("0")


def test_the_allocation_never_leaves_a_residual():
    """A payment that fits leaves nothing unmatched.

    Rule 19 refuses a `pago` larger than the debt it retires, so the
    residual is always zero. The v1 model let a surplus through and
    reported it as a credit in the customer's favour; that state does not
    exist any more (ADR-26).
    """
    cargo = _cargo(1, "20.00")

    resultado = allocate_payments([cargo], [_pago(9, "20.00")])

    assert resultado.residual == Decimal("0")


def test_the_allocation_takes_no_credit_notes():
    """`allocate_payments` has no `credit_notes` parameter any more.

    The v1 function took one and applied the notes directly to the charges.
    With the dispute machinery gone there is no `nota de crédito` to apply,
    and a `pago` imputes only against a `cargo`.
    """
    from tienda.domain import allocation as modulo

    import inspect

    parametros = inspect.signature(modulo.allocate_payments).parameters
    assert "credit_notes" not in parametros
    assert list(parametros) == ["charges", "payments"]


# ---------------------------------------------------------------------------
# The repartition
# ---------------------------------------------------------------------------


def test_the_repartition_is_recorded_charge_by_charge():
    """A payment of 20,00 € writes three imputations: 8, 7 and 5.

    This is the owner's example: a client owes 8,00 € of bread, 7,00 € of
    soda and 15,00 € of biscuits, and pays 20,00 €. The repartition records
    8,00 € against the bread, 7,00 € against the soda and 5,00 € against the
    biscuits (ADR-27).
    """
    pan = _cargo(1, "8.00", dias=0)
    refresco = _cargo(2, "7.00", dias=1)
    galletas = _cargo(3, "15.00", dias=2)
    pago = _pago(9, "20.00", dias=3)

    resultado = allocate_payments([pan, refresco, galletas], [pago])
    imputaciones = imputations_of(resultado, 9)

    assert [(i.cargo_id, i.importe) for i in imputaciones] == [
        (1, Decimal("8.00")),
        (2, Decimal("7.00")),
        (3, Decimal("5.00")),
    ]


def test_the_repartition_leaves_the_charges_reading_8_8_7_7_and_5_15():
    """The three charges read 8/8, 7/7 and 5/15 after the payment.

    The `saldos` are what is still owed on each charge, and the derived
    `pagado` is the amount minus that. Both come from the same allocation.
    """
    pan = _cargo(1, "8.00", dias=0)
    refresco = _cargo(2, "7.00", dias=1)
    galletas = _cargo(3, "15.00", dias=2)
    pago = _pago(9, "20.00", dias=3)

    resultado = allocate_payments([pan, refresco, galletas], [pago])
    saldos = dict(resultado.saldos)
    pagado = {
        cargo.id: cargo.amount - saldos.get(cargo.id, Decimal("0"))
        for cargo in (pan, refresco, galletas)
    }

    assert pagado[pan.id] == Decimal("8.00")
    assert pagado[refresco.id] == Decimal("7.00")
    assert pagado[galletas.id] == Decimal("5.00")
    assert saldos[galletas.id] == Decimal("10.00")


def test_the_grain_of_the_repartition_is_the_charge_not_the_line():
    """A charge of 15,00 € made of three lines gets one imputation.

    The design defines no policy for splitting a partial payment across the
    lines of a single charge, and it does not need one: the `desglose` says
    what was bought, the debt says what is owed and the repayment says what
    was paid against the debt. So the imputation names the **charge**.
    """
    pan = _cargo(1, "15.00", dias=0)
    pago = _pago(9, "5.00", dias=1)

    resultado = allocate_payments([pan], [pago])
    imputaciones = imputations_of(resultado, 9)

    assert len(imputaciones) == 1
    assert imputaciones[0].cargo_id == pan.id
    assert imputaciones[0].importe == Decimal("5.00")


def test_the_imputations_of_one_payment_add_up_to_that_payment():
    """Rule 21: the imputations of a payment add up to the payment.

    The sum cannot be a database `CHECK` — a `CHECK` sees one row and never
    an aggregate — so it is the service layer's job. What the pure rule
    guarantees is that the allocation places every cent, and therefore that
    the rows it produces add up.
    """
    pan = _cargo(1, "8.00", dias=0)
    refresco = _cargo(2, "7.00", dias=1)
    galletas = _cargo(3, "15.00", dias=2)
    pago = _pago(9, "20.00", dias=3)

    resultado = allocate_payments([pan, refresco, galletas], [pago])
    imputaciones = imputations_of(resultado, 9)

    total = sum((i.importe for i in imputaciones), Decimal("0"))
    assert total == pago.amount


def test_the_imputations_of_several_payments_are_separate():
    """Each payment gets its own rows, and they do not mix."""
    cargo = _cargo(1, "30.00", dias=0)
    pago_a = _pago(8, "10.00", dias=1)
    pago_b = _pago(9, "20.00", dias=2)

    resultado = allocate_payments([cargo], [pago_a, pago_b])

    rows_a = imputations_of(resultado, 8)
    rows_b = imputations_of(resultado, 9)

    assert [(i.pago_id, i.importe) for i in rows_a] == [(8, Decimal("10.00"))]
    assert [(i.pago_id, i.importe) for i in rows_b] == [(9, Decimal("20.00"))]


def test_a_payment_that_touches_nothing_has_no_imputations():
    """A payment that placed nothing produces no rows."""
    cargo = _cargo(1, "10.00", dias=10)
    pago = _pago(9, "10.00", dias=0)

    resultado = allocate_payments([cargo], [pago])

    assert imputations_of(resultado, 9) == ()
