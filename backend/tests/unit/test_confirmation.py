"""The derived confirmation state of a charge (IC-03, IC-04 — ADR-18, ADR-23).

Four rules, and the one that matters most is the **guard**:

* `confirmacion_efectiva` — the latest row, or `None`;
* `estado_cargo` — the projection: `confirmado`, `en_disputa` or
  `sin_confirmar`, computed on read and **never** consulted as a stored
  state;
* `transicion_permitida` — the guard for a write, which looks at the
  **presence of a row**, never at the effective state alone;
* `escalado_sin_confirmar` — the derived escalation flag.

None of these tests carries the `django_db` marker: the rules read no
database.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from tienda.domain.confirmation import (
    CARGO_YA_CONFIRMADO,
    CARGO_YA_RECONCILIADO,
    DISPUTA_ABIERTA,
    confirmacion_efectiva,
    escalado_sin_confirmar,
    estado_cargo,
    transicion_permitida,
)
from tienda.domain.types import ConfirmacionRow, ConfirmState

DIA = timedelta(days=1)
BASE = datetime(2026, 3, 1, 9, 0, 0)


def fila(
    identificador: int,
    estado: ConfirmState,
    dias: int = 0,
    importe_reclamado=None,
) -> ConfirmacionRow:
    """A `Confirmacion` row dated `dias` days before the base instant."""
    return ConfirmacionRow(
        id=identificador,
        estado=estado,
        importe_reclamado=None if importe_reclamado is None else Decimal(importe_reclamado),
        confirmado_en=BASE - dias * DIA,
        origen="cliente",
    )


@pytest.mark.unit
def test_a_charge_with_no_rows_has_no_effective_confirmation():
    """No rows, no effective confirmation."""
    assert confirmacion_efectiva([]) is None


@pytest.mark.unit
def test_the_effective_confirmation_is_the_latest_row():
    """The latest row is the one with the greatest `(confirmado_en, id)`."""
    filas = [
        fila(1, ConfirmState.CONFIRMADO, dias=10),
        fila(2, ConfirmState.EN_DISPUTA, dias=2),
    ]

    efectiva = confirmacion_efectiva(filas)

    assert efectiva is not None
    assert efectiva.id == 2


@pytest.mark.unit
def test_a_charge_with_a_confirmed_row_reads_confirmed():
    """The scenario of IC-04: one `Confirmacion` in state `confirmado`."""
    estado = estado_cargo([fila(1, ConfirmState.CONFIRMADO, dias=1)])

    assert estado.estado is ConfirmState.CONFIRMADO
    assert estado.confirmacion is not None
    assert estado.confirmacion.id == 1


@pytest.mark.unit
def test_a_charge_with_no_rows_reads_sin_confirmar():
    """The scenario of IC-04: a charge with no `Confirmacion`."""
    estado = estado_cargo([])

    assert estado.estado is ConfirmState.SIN_CONFIRMAR
    assert estado.confirmacion is None


@pytest.mark.unit
def test_a_disputed_charge_reads_en_disputa():
    """A dispute row is the latest one, so the charge reads `en_disputa`."""
    estado = estado_cargo([fila(1, ConfirmState.EN_DISPUTA, dias=1, importe_reclamado="4.00")])

    assert estado.estado is ConfirmState.EN_DISPUTA


@pytest.mark.unit
def test_the_state_follows_the_latest_confirmation():
    """The state is derived from the rows, in order (IC-03, IC-04)."""
    filas = [
        fila(1, ConfirmState.CONFIRMADO, dias=10),
        fila(2, ConfirmState.EN_DISPUTA, dias=5),
    ]

    assert estado_cargo(filas).estado is ConfirmState.EN_DISPUTA

    # And the other way round: a dispute that came first, a confirmation
    # after it, reads `confirmado`.
    filas_invertidas = [
        fila(1, ConfirmState.EN_DISPUTA, dias=10),
        fila(2, ConfirmState.CONFIRMADO, dias=5),
    ]

    assert estado_cargo(filas_invertidas).estado is ConfirmState.CONFIRMADO


@pytest.mark.unit
def test_a_charge_without_rows_may_be_confirmed():
    """The guard lets the first confirmation through."""
    refusal = transicion_permitida(
        ConfirmState.SIN_CONFIRMAR,
        ConfirmState.CONFIRMADO,
        filas=[],
        ya_reconciliada=False,
    )

    assert refusal is None


@pytest.mark.unit
def test_a_confirmed_charge_may_not_be_confirmed_again():
    """The presence of a `confirmado` row blocks a second confirmation."""
    filas = [fila(1, ConfirmState.CONFIRMADO, dias=1)]

    refusal = transicion_permitida(
        ConfirmState.CONFIRMADO,
        ConfirmState.CONFIRMADO,
        filas=filas,
        ya_reconciliada=False,
    )

    assert refusal == CARGO_YA_CONFIRMADO


@pytest.mark.unit
def test_a_charge_may_not_be_confirmed_again_after_a_dispute():
    """The guard is the presence of the row, never the effective state.

    A charge whose rows are `[confirmado, en_disputa]` still reads
    `en_disputa` — but it may not be confirmed again, because the
    `confirmado` row is there. A state-only guard would let this through.
    """
    filas = [
        fila(1, ConfirmState.CONFIRMADO, dias=10),
        fila(2, ConfirmState.EN_DISPUTA, dias=5),
    ]

    # The effective state is `en_disputa`...
    assert estado_cargo(filas).estado is ConfirmState.EN_DISPUTA

    # ...and the guard still refuses the confirmation.
    refusal = transicion_permitida(
        ConfirmState.EN_DISPUTA,
        ConfirmState.CONFIRMADO,
        filas=filas,
        ya_reconciliada=False,
    )

    assert refusal == CARGO_YA_CONFIRMADO


@pytest.mark.unit
def test_a_charge_may_not_be_disputed_twice():
    """The presence of an `en_disputa` row blocks a second dispute."""
    filas = [fila(1, ConfirmState.EN_DISPUTA, dias=1)]

    refusal = transicion_permitida(
        ConfirmState.EN_DISPUTA,
        ConfirmState.EN_DISPUTA,
        filas=filas,
        ya_reconciliada=False,
    )

    assert refusal == DISPUTA_ABIERTA


@pytest.mark.unit
def test_a_charge_may_be_disputed_after_it_was_confirmed():
    """A confirmed charge may still be disputed — the states are separate."""
    filas = [fila(1, ConfirmState.CONFIRMADO, dias=5)]

    refusal = transicion_permitida(
        ConfirmState.CONFIRMADO,
        ConfirmState.EN_DISPUTA,
        filas=filas,
        ya_reconciliada=False,
    )

    assert refusal is None


@pytest.mark.unit
def test_a_reconciled_charge_may_not_be_disputed():
    """A charge already reconciled by a `nota de crédito` is closed."""
    refusal = transicion_permitida(
        ConfirmState.EN_DISPUTA,
        ConfirmState.EN_DISPUTA,
        filas=[],
        ya_reconciliada=True,
    )

    assert refusal == CARGO_YA_RECONCILIADO


@pytest.mark.unit
def test_the_guard_does_not_consult_the_effective_state():
    """The guard reads the rows, not the projection.

    The same rows and the same origin produce the same refusal whatever
    the origin says: the rows decide.
    """
    filas = [fila(1, ConfirmState.CONFIRMADO, dias=5)]

    como_confirmado = transicion_permitida(
        ConfirmState.CONFIRMADO,
        ConfirmState.CONFIRMADO,
        filas=filas,
        ya_reconciliada=False,
    )
    como_sin_confirmar = transicion_permitida(
        ConfirmState.SIN_CONFIRMAR,
        ConfirmState.CONFIRMADO,
        filas=filas,
        ya_reconciliada=False,
    )

    assert como_confirmado == como_sin_confirmar == CARGO_YA_CONFIRMADO


@pytest.mark.unit
def test_a_charge_is_escalated_after_seven_days_without_confirmation():
    """`estado is sin_confirmar and age_in_days(occurred_at, at) > dias`.

    The comparison is strictly greater: at exactly seven days the charge
    has not crossed the threshold yet.
    """
    ocurrido = BASE - 8 * DIA

    assert escalado_sin_confirmar(ConfirmState.SIN_CONFIRMAR, ocurrido, BASE) is True


@pytest.mark.unit
def test_a_charge_of_exactly_seven_days_is_not_escalated():
    """The threshold is exclusive: seven days is not yet eight."""
    ocurrido = BASE - 7 * DIA

    assert escalado_sin_confirmar(ConfirmState.SIN_CONFIRMAR, ocurrido, BASE) is False


@pytest.mark.unit
def test_a_fresh_charge_is_not_escalated():
    """A charge of today has no age to escalate."""
    assert escalado_sin_confirmar(ConfirmState.SIN_CONFIRMAR, BASE, BASE) is False


@pytest.mark.unit
def test_a_confirmed_charge_is_never_escalated():
    """The flag is about a charge nobody confirmed."""
    ocurrido = BASE - 30 * DIA

    assert escalado_sin_confirmar(ConfirmState.CONFIRMADO, ocurrido, BASE) is False


@pytest.mark.unit
def test_a_disputed_charge_is_never_escalated():
    """A dispute is an answer, even if it is not a confirmation."""
    ocurrido = BASE - 30 * DIA

    assert escalado_sin_confirmar(ConfirmState.EN_DISPUTA, ocurrido, BASE) is False


@pytest.mark.unit
def test_the_escalation_days_are_configurable():
    """The threshold is a parameter, not a constant."""
    ocurrido = BASE - 10 * DIA

    assert escalado_sin_confirmar(ConfirmState.SIN_CONFIRMAR, ocurrido, BASE, dias=7) is True
    assert escalado_sin_confirmar(ConfirmState.SIN_CONFIRMAR, ocurrido, BASE, dias=20) is False
