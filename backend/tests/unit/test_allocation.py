"""How the money that came back retires the debt (PA-02 — ADR-7).

Three properties of the FIFO retirement, and the boundary of the credit
note:

* the **oldest charge is retired first**;
* a payment **smaller** than the oldest charge retires it only in part, and
  leaves the newer charge untouched;
* the **surplus stays as a residual** in the customer's favour;
* a credit note imputes **only** to a charge with
  `charge.occurred_at ≤ credit.occurred_at`.

None of these tests carries the `django_db` marker: the rule reads no
database, and pytest-django would raise `RuntimeError: Database access not
allowed` if it did.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from tienda.domain.allocation import allocate_payments
from tienda.domain.types import EntryKind, LedgerLine

DIA = timedelta(days=1)
BASE = datetime(2026, 3, 1, 9, 0, 0)


def cargo(identificador: int, importe: str, dias: int = 0) -> LedgerLine:
    """A `cargo` of `importe`, `dias` days after the base instant."""
    return LedgerLine(
        id=identificador,
        kind=EntryKind.CARGO,
        amount=Decimal(importe),
        occurred_at=BASE + dias * DIA,
    )


def pago(identificador: int, importe: str, dias: int = 0) -> LedgerLine:
    """A `pago` of `importe`, `dias` days after the base instant."""
    return LedgerLine(
        id=identificador,
        kind=EntryKind.PAGO,
        amount=Decimal(importe),
        occurred_at=BASE + dias * DIA,
    )


def nota(identificador: int, importe: str, dias: int = 0) -> LedgerLine:
    """A `nota_credito` of `importe`, `dias` days after the base instant."""
    return LedgerLine(
        id=identificador,
        kind=EntryKind.NOTA_CREDITO,
        amount=Decimal(importe),
        occurred_at=BASE + dias * DIA,
    )


def saldos_de(resultado) -> dict[int, Decimal]:
    """The `saldos` of an allocation as a dictionary."""
    return dict(resultado.saldos)


@pytest.mark.unit
def test_the_oldest_charge_is_retired_first():
    """The scenario of PA-02: 10,00 € on day 1 and 40,00 € on day 20.

    A payment of 30,00 € settles the 10,00 € charge and leaves 20,00 € of
    the 40,00 € charge pending.
    """
    cargos = [cargo(1, "10.00", dias=0), cargo(2, "40.00", dias=19)]
    pagos = [pago(10, "30.00", dias=25)]

    resultado = allocate_payments(cargos, pagos)

    saldos = saldos_de(resultado)
    assert saldos[1] == Decimal("0")
    assert saldos[2] == Decimal("20.00")
    assert resultado.residual == Decimal("0")


@pytest.mark.unit
def test_the_allocation_names_the_payment_and_the_charge():
    """Every allocation names the payment that made it and the charge it hit."""
    cargos = [cargo(1, "10.00", dias=0), cargo(2, "40.00", dias=19)]
    pagos = [pago(10, "30.00", dias=25)]

    resultado = allocate_payments(cargos, pagos)

    assert resultado.asignaciones == (
        (10, 1, Decimal("10.00")),
        (10, 2, Decimal("20.00")),
    )


@pytest.mark.unit
def test_a_payment_smaller_than_the_oldest_charge_retires_it_in_part():
    """The second scenario of PA-02: 6,00 € against a 10,00 € charge.

    4,00 € of the oldest charge stays pending and the newer charge is
    untouched.
    """
    cargos = [cargo(1, "10.00", dias=0), cargo(2, "40.00", dias=19)]
    pagos = [pago(10, "6.00", dias=25)]

    resultado = allocate_payments(cargos, pagos)

    saldos = saldos_de(resultado)
    assert saldos[1] == Decimal("4.00")
    assert saldos[2] == Decimal("40.00")
    assert resultado.residual == Decimal("0")


@pytest.mark.unit
def test_the_order_is_by_occurred_at_and_then_by_id():
    """FIFO by `(occurred_at, id)` — the identifier is the tie-breaker.

    Two charges recorded at the same instant are ordered by their
    identifier, so the allocation is total and the same fixture always
    produces the same result.
    """
    cargos = [
        cargo(2, "10.00", dias=0),
        cargo(1, "10.00", dias=0),
    ]
    pagos = [pago(10, "10.00", dias=5)]

    resultado = allocate_payments(cargos, pagos)

    assert resultado.asignaciones == ((10, 1, Decimal("10.00")),)
    assert saldos_de(resultado)[2] == Decimal("10.00")


@pytest.mark.unit
def test_an_overpayment_leaves_a_residual():
    """The surplus stays as a residual in the customer's favour (PA-02)."""
    cargos = [cargo(1, "20.00", dias=0)]
    pagos = [pago(10, "35.00", dias=1)]

    resultado = allocate_payments(cargos, pagos)

    assert resultado.asignaciones == ((10, 1, Decimal("20.00")),)
    assert resultado.residual == Decimal("15.00")
    assert saldos_de(resultado)[1] == Decimal("0")


@pytest.mark.unit
def test_several_payments_retire_the_charges_in_order():
    """Two payments retire the charges in the order the money arrived."""
    cargos = [cargo(1, "10.00", dias=0), cargo(2, "40.00", dias=19)]
    pagos = [pago(10, "15.00", dias=25), pago(11, "15.00", dias=26)]

    resultado = allocate_payments(cargos, pagos)

    saldos = saldos_de(resultado)
    assert saldos[1] == Decimal("0")
    assert saldos[2] == Decimal("20.00")
    assert resultado.residual == Decimal("0")


@pytest.mark.unit
def test_a_credit_note_imputes_only_to_a_charge_that_is_at_least_as_old():
    """`charge.occurred_at ≤ credit.occurred_at` (ADR-7).

    The note is dated before the second charge, so it may impute to the
    first one only. The second charge stays fully owed.
    """
    cargos = [cargo(1, "10.00", dias=0), cargo(2, "40.00", dias=19)]
    notas = [nota(20, "10.00", dias=10)]

    resultado = allocate_payments(cargos, [], credit_notes=notas)

    saldos = saldos_de(resultado)
    assert saldos[1] == Decimal("0")
    assert saldos[2] == Decimal("40.00")


@pytest.mark.unit
def test_a_credit_note_may_impute_to_a_charge_of_the_same_instant():
    """The boundary is inclusive: `≤`, not `<`.

    A note recorded at the very instant of the charge may impute to it.
    """
    cargos = [cargo(1, "10.00", dias=0)]
    notas = [nota(20, "4.00", dias=0)]

    resultado = allocate_payments(cargos, [], credit_notes=notas)

    assert saldos_de(resultado)[1] == Decimal("6.00")


@pytest.mark.unit
def test_a_credit_note_that_matches_no_eligible_charge_stays_credit():
    """A note younger than every charge cannot impute, and stays residual.

    The note is dated **before** the only charge, so the condition
    `charge.occurred_at ≤ credit.occurred_at` does not hold and the note
    may not impute to it. The money stays as residual credit.
    """
    cargos = [cargo(1, "10.00", dias=10)]
    notas = [nota(20, "4.00", dias=5)]

    resultado = allocate_payments(cargos, [], credit_notes=notas)

    assert resultado.asignaciones == ()
    assert saldos_de(resultado)[1] == Decimal("10.00")
    assert resultado.residual == Decimal("4.00")


@pytest.mark.unit
def test_a_payment_may_not_retire_a_charge_that_is_younger_than_it():
    """The mirror boundary: money that arrived first cannot clear a later
    charge.

    A charge dated after the payment is not yet owed at the moment the
    payment was made, so the payment cannot retire it. The money stays as
    residual credit, to be applied to it later.
    """
    cargos = [cargo(1, "10.00", dias=10)]
    pagos = [pago(10, "10.00", dias=0)]

    resultado = allocate_payments(cargos, pagos)

    assert resultado.asignaciones == ()
    assert saldos_de(resultado)[1] == Decimal("10.00")
    assert resultado.residual == Decimal("10.00")


@pytest.mark.unit
def test_an_empty_ledger_allocates_nothing():
    """No charges, no money, nothing to do."""
    resultado = allocate_payments([], [])

    assert resultado.asignaciones == ()
    assert resultado.saldos == ()
    assert resultado.residual == Decimal("0")
