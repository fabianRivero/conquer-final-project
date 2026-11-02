"""The close of the day: the expected cash and the deviation (CP-02, CP-04).

Three things are pinned here:

* `cash_at` — the drawer: `inicial + Σ(entradas) − Σ(salidas) + Σ(pagos)`;
* `caja_al_cierre` — the same computation at the close instant, and the
  caller **never supplies** the expected figure;
* `desviacion_cierre` — `esperado − contado`, the value the `DayClose`
  stores.

The "never supplied" boundary is the interesting one, so the test asserts it
**structurally**: the signature of `caja_al_cierre` has no parameter that
could carry a client-supplied `esperado`.

None of these tests carries the `django_db` marker: the rules read no
database.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from tienda.domain.cash import caja_al_cierre, desviacion_cierre
from tienda.domain.position import cash_at
from tienda.domain.types import CashLine, EntryKind, LedgerLine, MovementKind

DIA = timedelta(days=1)
BASE = datetime(2026, 3, 1, 9, 0, 0)


def entrada(identificador: int, importe: str, dias: int = 0) -> CashLine:
    """A cash `entrada` `dias` days after the base instant."""
    return CashLine(
        id=identificador,
        kind=MovementKind.ENTRADA,
        amount=Decimal(importe),
        occurred_at=BASE + dias * DIA,
    )


def salida(identificador: int, importe: str, dias: int = 0) -> CashLine:
    """A cash `salida` `dias` days after the base instant."""
    return CashLine(
        id=identificador,
        kind=MovementKind.SALIDA,
        amount=Decimal(importe),
        occurred_at=BASE + dias * DIA,
    )


def pago(identificador: int, importe: str, dias: int = 0) -> LedgerLine:
    """A `pago` ledger line `dias` days after the base instant."""
    return LedgerLine(
        id=identificador,
        kind=EntryKind.PAGO,
        amount=Decimal(importe),
        occurred_at=BASE + dias * DIA,
    )


@pytest.mark.unit
def test_the_cash_is_the_opening_plus_the_movements_plus_the_payments():
    """`inicial + Σ(entradas) − Σ(salidas) + Σ(pagos)` (CP-02)."""
    movimientos = [
        entrada(1, "100.00"),
        salida(2, "30.00", dias=1),
        entrada(3, "20.00", dias=2),
    ]
    pagos = [pago(10, "50.00", dias=3)]

    assert cash_at(Decimal("50.00"), movimientos, pagos, BASE + 5 * DIA) == Decimal("190.00")


@pytest.mark.unit
def test_a_payment_reaches_the_drawer_through_its_own_argument():
    """A `pago` is never a `CashMovement` — it is counted exactly once (CP-02)."""
    pagos = [pago(10, "50.00")]

    assert cash_at(Decimal("0"), [], pagos, BASE) == Decimal("50.00")


@pytest.mark.unit
def test_the_cash_ignores_what_happened_after_the_instant():
    """Only the movements whose `occurred_at ≤ at` are counted."""
    movimientos = [entrada(1, "100.00"), salida(2, "30.00", dias=5)]

    assert cash_at(Decimal("0"), movimientos, [], BASE) == Decimal("100.00")
    assert cash_at(Decimal("0"), movimientos, [], BASE + 5 * DIA) == Decimal("70.00")


@pytest.mark.unit
def test_the_close_is_the_same_computation_at_the_close_instant():
    """`caja_al_cierre` is `cash_at` with `at` set to the close instant."""
    movimientos = [entrada(1, "100.00"), salida(2, "30.00", dias=1)]
    pagos = [pago(10, "25.00", dias=2)]
    cierre = BASE + 3 * DIA

    assert caja_al_cierre(Decimal("50.00"), movimientos, pagos, cierre) == cash_at(
        Decimal("50.00"), movimientos, pagos, cierre
    )


@pytest.mark.unit
def test_the_caller_never_supplies_the_expected_figure():
    """`esperado` is derived — there is no parameter that could carry it.

    The check is structural: the signature of `caja_al_cierre` has no
    `esperado` and no `contado`. A client-supplied balance would be a
    client-supplied balance, whatever the caller called it.
    """
    parametros = inspect.signature(caja_al_cierre).parameters

    assert "esperado" not in parametros
    assert "contado" not in parametros
    assert list(parametros) == ["opening_cash", "movements", "pagos", "at"]


@pytest.mark.unit
def test_the_close_of_an_empty_day_is_the_opening():
    """No movements, no payments: the drawer holds what it opened with."""
    assert caja_al_cierre(Decimal("75.00"), [], [], BASE) == Decimal("75.00")


@pytest.mark.unit
def test_the_deviation_is_the_expected_minus_the_counted():
    """`esperado − contado` — the value the `DayClose` stores (CP-04)."""
    assert desviacion_cierre(Decimal("190.00"), Decimal("188.50")) == Decimal("1.50")


@pytest.mark.unit
def test_the_deviation_is_signed():
    """The sign is the information the owner needs.

    A positive deviation means the drawer holds more than it should; a
    negative one means it holds less.
    """
    sobra = desviacion_cierre(Decimal("190.00"), Decimal("188.50"))
    falta = desviacion_cierre(Decimal("190.00"), Decimal("192.00"))

    assert sobra == Decimal("1.50")
    assert falta == Decimal("-2.00")


@pytest.mark.unit
def test_the_deviation_of_an_exact_count_is_zero():
    """Nothing is missing and nothing is extra."""
    assert desviacion_cierre(Decimal("190.00"), Decimal("190.00")) == Decimal("0")


@pytest.mark.unit
def test_the_deviation_is_never_an_absolute_value():
    """A negative deviation stays negative — it is not turned into a
    magnitude."""
    assert desviacion_cierre(Decimal("100.00"), Decimal("120.00")) < 0
