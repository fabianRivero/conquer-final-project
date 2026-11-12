"""The derived state of a customer: the debt, the suspension and its cause.

Covers **PA-06** (the suspension is automatic and evaluated on read), with
the two boundaries the design calls out:

* `credit_limit=None` — «sin límite» — **never** fires `limite_superado`;
* `override=True` lifts the automatic suspension.

And the one boundary rule 19 added: the outstanding is never negative,
because a `pago` never exceeds the debt it retires and the excess leaves
the counter as change (ADR-26).

None of these tests carries the `django_db` marker, and none of them can:
the rule reads no database, and pytest-django would raise `RuntimeError:
Database access not allowed` if it did.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from tienda.domain.evaluation import antiguedad_max_dias, evaluate_customer
from tienda.domain.types import EntryKind, LedgerLine, SuspensionReason

DIA = timedelta(days=1)
BASE = datetime(2026, 3, 1, 9, 0, 0)


def cargo(identificador: int, importe: str, dias: int = 0) -> LedgerLine:
    """A `cargo` of `importe`, `dias` days before the base instant."""
    return LedgerLine(
        id=identificador,
        kind=EntryKind.CARGO,
        amount=Decimal(importe),
        occurred_at=BASE - dias * DIA,
    )


def pago(identificador: int, importe: str, dias: int = 0) -> LedgerLine:
    """A `pago` of `importe`, `dias` days before the base instant."""
    return LedgerLine(
        id=identificador,
        kind=EntryKind.PAGO,
        amount=Decimal(importe),
        occurred_at=BASE - dias * DIA,
    )


@pytest.mark.unit
def test_a_customer_with_no_debt_is_active():
    """Nothing owed, nothing to suspend."""
    estado = evaluate_customer([], credit_limit=None, at=BASE)

    assert estado.total == Decimal("0")
    assert estado.suspendido is False
    assert estado.motivo is None
    assert estado.antiguedad_max_dias == 0


@pytest.mark.unit
def test_a_fresh_debt_does_not_suspend_the_customer():
    """A charge of ten days is well inside the suspension age."""
    estado = evaluate_customer(
        [cargo(1, "20.00", dias=10)], credit_limit=None, at=BASE
    )

    assert estado.suspendido is False
    assert estado.motivo is None
    assert estado.antiguedad_max_dias == 10


@pytest.mark.unit
def test_an_old_debt_suspends_the_customer_automatically():
    """The scenario of PA-06: a 45-day debt.

    The customer reads `suspendido` with reason `antiguedad_superada`, and
    no prior human action was required.
    """
    estado = evaluate_customer(
        [cargo(1, "10.00", dias=45)], credit_limit=None, at=BASE
    )

    assert estado.suspendido is True
    assert estado.motivo is SuspensionReason.ANTIGUEDAD_SUPERADA


@pytest.mark.unit
def test_the_suspension_age_is_the_strict_boundary():
    """Exactly 30 days does not suspend; 31 days does."""
    activo = evaluate_customer(
        [cargo(1, "10.00", dias=30)], credit_limit=None, at=BASE
    )
    suspendido = evaluate_customer(
        [cargo(1, "10.00", dias=31)], credit_limit=None, at=BASE
    )

    assert activo.suspendido is False
    assert suspendido.suspendido is True


@pytest.mark.unit
def test_exceeding_the_limit_suspends_the_customer():
    """The outstanding above the limit fires `limite_superado`."""
    estado = evaluate_customer(
        [cargo(1, "50.00", dias=1)], credit_limit=Decimal("20.00"), at=BASE
    )

    assert estado.suspendido is True
    assert estado.motivo is SuspensionReason.LIMITE_SUPERADO


@pytest.mark.unit
def test_a_limit_that_is_not_exceeded_does_not_suspend():
    """The outstanding exactly at the limit is not above it."""
    estado = evaluate_customer(
        [cargo(1, "20.00", dias=1)], credit_limit=Decimal("20.00"), at=BASE
    )

    assert estado.suspendido is False
    assert estado.motivo is None


@pytest.mark.unit
def test_a_null_limit_never_fires_the_limit_cause():
    """`credit_limit=None` is «sin límite» — an explicit state (PA-05).

    A customer with no limit can owe as much as the shop allows: the limit
    cause never fires, no matter how large the outstanding is.
    """
    estado = evaluate_customer(
        [cargo(1, "1000000.00", dias=1)], credit_limit=None, at=BASE
    )

    assert estado.suspendido is False
    assert estado.motivo is None
    assert estado.credit_limit is None


@pytest.mark.unit
def test_a_null_limit_still_lets_the_age_suspend_the_customer():
    """«Sin límite» removes the limit cause, not the age cause."""
    estado = evaluate_customer(
        [cargo(1, "1000000.00", dias=45)], credit_limit=None, at=BASE
    )

    assert estado.suspendido is True
    assert estado.motivo is SuspensionReason.ANTIGUEDAD_SUPERADA


@pytest.mark.unit
def test_the_override_lifts_the_automatic_suspension():
    """`override=True` lifts the suspension (PA-08).

    The override is an appended act by the owner. It rewrites no entry and
    changes no figure — it only lifts the derived suspension.
    """
    lineas = [cargo(1, "10.00", dias=45)]

    sin_override = evaluate_customer(lineas, credit_limit=None, at=BASE)
    con_override = evaluate_customer(
        lineas, credit_limit=None, at=BASE, override=True
    )

    assert sin_override.suspendido is True
    assert con_override.suspendido is False
    assert con_override.motivo is None
    # The figures are untouched by the override.
    assert con_override.total == sin_override.total
    assert con_override.antiguedad_max_dias == sin_override.antiguedad_max_dias


@pytest.mark.unit
def test_the_override_lifts_the_limit_suspension_too():
    """The override lifts the automatic suspension whatever its cause."""
    estado = evaluate_customer(
        [cargo(1, "500.00", dias=1)],
        credit_limit=Decimal("20.00"),
        at=BASE,
        override=True,
    )

    assert estado.suspendido is False
    assert estado.motivo is None


@pytest.mark.unit
def test_the_oldest_unpaid_charge_drives_the_age():
    """`antiguedad_max_dias` is the age of the oldest unpaid charge."""
    estado = evaluate_customer(
        [cargo(1, "20.00", dias=45), cargo(2, "10.00", dias=10)],
        credit_limit=None,
        at=BASE,
    )

    assert estado.antiguedad_max_dias == 45


@pytest.mark.unit
def test_a_payment_that_retires_the_oldest_charge_lifts_the_suspension():
    """The scenario of PA-06: a 45-day charge retired by a 20,00 € payment.

    The 45-day charge is retired, `antiguedad_max_dias` is 10 and the
    customer reads active.
    """
    lineas = [
        cargo(1, "20.00", dias=45),
        cargo(2, "10.00", dias=10),
        pago(10, "20.00", dias=1),
    ]

    estado = evaluate_customer(lineas, credit_limit=None, at=BASE)

    assert estado.antiguedad_max_dias == 10
    assert estado.suspendido is False
    assert estado.total == Decimal("10.00")


@pytest.mark.unit
def test_a_confirmed_charge_is_still_debt():
    """A confirmed charge is debt in full, and ages in its own bucket.

    The rule never reads the confirmation rows: a charge's confirmation is
    about whether it exists, not about how much it is worth.
    """
    estado = evaluate_customer(
        [cargo(1, "6.40", dias=40)], credit_limit=None, at=BASE
    )

    assert estado.total == Decimal("6.40")
    assert estado.antiguedad_max_dias == 40


@pytest.mark.unit
def test_the_antiguedad_is_zero_when_nothing_is_owed():
    """A retired debt has no age — it cannot suspend anyone.

    `antiguedad_max_dias` takes the charges and the payments separately,
    the signature design §10 fixes.
    """
    cargos = [cargo(1, "20.00", dias=45)]
    pagos = [pago(10, "20.00", dias=1)]

    assert antiguedad_max_dias(cargos, pagos, BASE) == 0


@pytest.mark.unit
def test_the_antiguedad_ignores_a_charge_that_is_not_yet_owed():
    """A charge dated after `at` has not happened yet."""
    lineas = [cargo(1, "20.00", dias=-5)]

    assert antiguedad_max_dias(lineas, [], BASE) == 0


@pytest.mark.unit
def test_a_payment_that_retires_the_debt_lifts_the_suspension():
    """A payment reduces the debt and the age with it.

    There is no `nota de crédito` any more: the v1 version of this test
    proved that a credit note reduced the debt and lifted the suspension.
    The only money that retires debt now is a `pago` (ADR-19).
    """
    lineas = [
        cargo(1, "20.00", dias=45),
        pago(10, "20.00", dias=1),
    ]

    estado = evaluate_customer(lineas, credit_limit=None, at=BASE)

    assert estado.total == Decimal("0")
    assert estado.antiguedad_max_dias == 0
    assert estado.suspendido is False


@pytest.mark.unit
def test_the_outstanding_is_never_negative():
    """The outstanding never goes below zero.

    A `pago` never exceeds the debt it retires (rule 19): the shop returns
    the excess as change and it never enters the book. So there is no
    `credit_a_favor` state, and the rule has no third term to subtract
    (ADR-26).
    """
    from tienda.domain.types import EntryKind as _EntryKind

    assert not hasattr(_EntryKind, "NOTA_CREDITO")

    # A payment that fits exactly leaves nothing owed.
    estado = evaluate_customer(
        [cargo(1, "20.00", dias=1), pago(10, "20.00", dias=1)],
        credit_limit=None,
        at=BASE,
    )
    assert estado.total == Decimal("0")


@pytest.mark.unit
def test_the_suspension_age_is_configurable():
    """The age at which the debt suspends is a parameter, not a constant."""
    lineas = [cargo(1, "10.00", dias=10)]

    por_defecto = evaluate_customer(lineas, credit_limit=None, at=BASE)
    estricto = evaluate_customer(
        lineas, credit_limit=None, at=BASE, suspension_age_days=5
    )

    assert por_defecto.suspendido is False
    assert estricto.suspendido is True
    assert estricto.motivo is SuspensionReason.ANTIGUEDAD_SUPERADA
