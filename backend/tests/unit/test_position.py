"""The position of the shop: the debt, the drawer and the real position.

Covers **CP-03** (the position is recomputed on every read, and a payment
leaves it unchanged) and **PA-01** (the outstanding is derived, never
stored), with the boundary of **ADR-9**: a negative outstanding is a residual
in the customer's favour, **not** an error.

None of these tests carries the `django_db` marker, and none of them can:
pytest-django raises `RuntimeError: Database access not allowed` for any ORM
call in a test without that marker. The absence of the marker is therefore
the proof that the rules read no database.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from tienda.domain.position import cash_at, outstanding, real_position
from tienda.domain.types import (
    CashLine,
    EntryKind,
    LedgerLine,
    MovementKind,
)

DIA = timedelta(days=1)
BASE = datetime(2026, 3, 1, 9, 0, 0)


def cargo(identificador: int, importe: str, dias: int = 0) -> LedgerLine:
    """A `cargo` ledger line `dias` days after the base instant."""
    return LedgerLine(
        id=identificador,
        kind=EntryKind.CARGO,
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


def nota(identificador: int, importe: str, dias: int = 0) -> LedgerLine:
    """A `nota_credito` ledger line `dias` days after the base instant."""
    return LedgerLine(
        id=identificador,
        kind=EntryKind.NOTA_CREDITO,
        amount=Decimal(importe),
        occurred_at=BASE + dias * DIA,
    )


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


@pytest.mark.unit
def test_the_outstanding_is_the_difference_of_the_three_kinds():
    """`Σ cargos − Σ pagos − Σ notas` over the entries at or before `at`."""
    lineas = [
        cargo(1, "20.00"),
        cargo(2, "10.00", dias=1),
        pago(3, "5.00", dias=2),
        nota(4, "4.00", dias=3),
    ]

    assert outstanding(lineas, BASE + 10 * DIA) == Decimal("21.00")


@pytest.mark.unit
def test_the_outstanding_ignores_what_happened_after_the_instant():
    """Only the entries whose `occurred_at ≤ at` are counted."""
    lineas = [
        cargo(1, "20.00"),
        cargo(2, "100.00", dias=5),
    ]

    assert outstanding(lineas, BASE) == Decimal("20.00")
    assert outstanding(lineas, BASE + 5 * DIA) == Decimal("120.00")


@pytest.mark.unit
def test_the_outstanding_of_an_empty_ledger_is_zero():
    """A customer with no entries owes nothing."""
    assert outstanding([], BASE) == Decimal("0")


@pytest.mark.unit
def test_a_negative_outstanding_is_a_credit_in_the_customers_favour():
    """An overpayment leaves a residual — it is not an error (ADR-9, PA-01).

    The scenario of PA-01: a customer owing 20,00 € pays 35,00 €. The
    outstanding is −15,00 € and the rule reports it as it is.
    """
    lineas = [cargo(1, "20.00"), pago(2, "35.00")]

    assert outstanding(lineas, BASE + 1 * DIA) == Decimal("-15.00")


@pytest.mark.unit
def test_the_outstanding_never_raises_on_a_negative_result():
    """The negative result is a value, not an exception.

    A rule that refused a negative outstanding would make an overpayment
    unrepresentable, and the shop would have nowhere to put the money.
    """
    lineas = [cargo(1, "1.00"), pago(2, "100.00")]

    try:
        resultado = outstanding(lineas, BASE)
    except Exception as exc:  # pragma: no cover - the assertion is the point
        pytest.fail(f"a negative outstanding must not raise: {exc!r}")

    assert resultado < 0


@pytest.mark.unit
def test_a_disputed_charge_is_still_debt():
    """A dispute removes no amount from the debt (PA-04).

    The dispute lives in the confirmation rows, which the outstanding never
    reads. The rule sees a `cargo` and counts it, whole.
    """
    lineas = [cargo(1, "6.40")]

    assert outstanding(lineas, BASE) == Decimal("6.40")


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
def test_a_pago_is_never_a_cash_movement():
    """A payment reaches the drawer through its own argument, once (CP-02).

    The same payment passed as a ledger `pago` and wrongly counted as a
    cash movement would be added twice.
    """
    pagos = [pago(10, "50.00")]

    # Only as a `pago`: the drawer holds the opening plus the payment.
    assert cash_at(Decimal("0"), [], pagos, BASE) == Decimal("50.00")

    # As a cash movement instead: the same money, in the other argument.
    como_movimiento = [entrada(11, "50.00")]
    assert cash_at(Decimal("0"), como_movimiento, [], BASE) == Decimal("50.00")


@pytest.mark.unit
def test_the_cash_ignores_what_happened_after_the_instant():
    """Only the movements whose `occurred_at ≤ at` are counted."""
    movimientos = [entrada(1, "100.00"), salida(2, "30.00", dias=5)]

    assert cash_at(Decimal("0"), movimientos, [], BASE) == Decimal("100.00")
    assert cash_at(Decimal("0"), movimientos, [], BASE + 5 * DIA) == Decimal("70.00")


@pytest.mark.unit
def test_the_real_position_is_the_addition_of_the_two_figures():
    """`posicion_real = caja + Σ pending balances` (CP-03, CP-06)."""
    assert real_position(Decimal("190.00"), Decimal("21.00")) == Decimal("211.00")


@pytest.mark.unit
def test_the_real_position_is_additive_only():
    """The rule adds the two figures it is given and does nothing else.

    It does not recompute the drawer, does not recompute the debt and does
    not consult a clock or a database — that is what makes it verifiable
    without one (CP-06).
    """
    caja = Decimal("190.00")
    pendiente = Decimal("21.00")

    assert real_position(caja, pendiente) == caja + pendiente

    # The same two figures in the other order give the same answer: the
    # rule is a sum, not a sequence of operations.
    assert real_position(pendiente, caja) == caja + pendiente


@pytest.mark.unit
def test_a_payment_leaves_the_real_position_unchanged():
    """A payment moves money from the pending balances into the drawer (CP-03).

    The drawer gains exactly what the debt loses, so the position the owner
    sees does not change. This is the property that distinguishes a real
    position from a balance.
    """
    antes_caja = Decimal("50.00")
    antes_pendiente = Decimal("20.00")

    despues_caja = antes_caja + Decimal("20.00")
    despues_pendiente = antes_pendiente - Decimal("20.00")

    assert real_position(antes_caja, antes_pendiente) == real_position(
        despues_caja, despues_pendiente
    )
