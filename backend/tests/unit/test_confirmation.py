"""The derived confirmation state and the one-way proposal transition.

Two families of test live here, and they are different in kind.

The **confirmation** tests are about a *projection*: the effective state of a
charge is computed on read from its `Confirmacion` rows, and no stored state
exists anywhere. The v1 suite had a third family here — the two-state
transition table over a charge's history and the 7-day escalation flag for a
charge nobody confirmed. **Both are gone.** The dispute machinery is gone
with them (ADR-18), and the escalation flag had no object left: a charge
without a confirmation cannot exist, so there is nothing to escalate.

The **proposal** tests are about the *guard*: a `FiadoPropuesto` moves from
`pendiente` to exactly one of `confirmado` or `cancelado`, never back. The
guard reads the **stored** proposal state, because the proposal *is* the
state (ADR-19, design §6).
"""

from datetime import datetime, timedelta

import pytest

from tienda.domain.confirmation import (
    PROPUESTA_YA_CANCELADA,
    PROPUESTA_YA_CONFIRMADA,
    confirmacion_efectiva,
    confirmacion_requerida,
    estado_cargo,
    propuesta_transicion_permitida,
)
from tienda.domain.types import ConfirmacionRow, ConfirmState, PropuestaEstado

# The instant every fixture is stamped with. No implicit clock anywhere.
T0 = datetime(2026, 5, 1, 9, 0, 0)


def _row(estado, *, id=1, minutos=0, origen="tienda"):
    """A `Confirmacion` row as a plain value."""
    return ConfirmacionRow(
        id=id,
        estado=estado,
        confirmado_en=T0 + timedelta(minutes=minutos),
        origen=origen,
    )


# ---------------------------------------------------------------------------
# The projection — the effective state of a charge
# ---------------------------------------------------------------------------


def test_a_charge_with_no_rows_has_no_effective_confirmation():
    """No rows means no effective confirmation."""
    assert confirmacion_efectiva([]) is None


def test_a_charge_with_a_confirmed_row_reads_confirmed():
    """A charge carrying a `confirmado` row reads `confirmado`."""
    rows = [_row(ConfirmState.CONFIRMADO)]

    estado = estado_cargo(rows)

    assert estado.estado == ConfirmState.CONFIRMADO
    assert estado.confirmacion is rows[0]


def test_a_charge_with_no_rows_reads_sin_confirmar():
    """A charge with no rows reads `sin_confirmar`.

    That state is **unreachable in normal operation**: rule 5 of §3.2
    forbids a charge without a confirmation in the same transaction. It is
    the value a hand-built fixture reads and the value a partially-written
    charge would read — but the write path never lets that happen.
    """
    estado = estado_cargo([])

    assert estado.estado == ConfirmState.SIN_CONFIRMAR
    assert estado.confirmacion is None


def test_the_effective_confirmation_is_the_latest_row():
    """The latest row wins, by `(confirmado_en, id)`."""
    primera = _row(ConfirmState.CONFIRMADO, id=1, minutos=0)
    segunda = _row(ConfirmState.CONFIRMADO, id=2, minutos=10)

    efectiva = confirmacion_efectiva([primera, segunda])

    assert efectiva is segunda


def test_the_effective_confirmation_breaks_a_tie_by_id():
    """Two rows with the same instant are ordered by their identifier.

    The tie-breaker makes the answer total: there is never a tie left to
    chance.
    """
    primera = _row(ConfirmState.CONFIRMADO, id=7, minutos=0)
    segunda = _row(ConfirmState.CONFIRMADO, id=8, minutos=0)

    efectiva = confirmacion_efectiva([primera, segunda])

    assert efectiva is segunda


def test_the_state_vocabulary_has_exactly_two_values():
    """`ConfirmState` has two values: `sin_confirmar` and `confirmado`.

    The v1 model carried a third, `en_disputa`, and with it the whole dispute
    machinery. A charge either carries its confirmation or it does not exist
    (ADR-18).
    """
    values = {estado.value for estado in ConfirmState}

    assert values == {"sin_confirmar", "confirmado"}
    assert "en_disputa" not in values


# ---------------------------------------------------------------------------
# The guard — the one-way proposal transition
# ---------------------------------------------------------------------------


def test_a_pending_proposal_may_be_confirmed():
    """`pendiente -> confirmado` is allowed."""
    assert (
        propuesta_transicion_permitida(
            PropuestaEstado.PENDIENTE, PropuestaEstado.CONFIRMADO
        )
        is None
    )


def test_a_pending_proposal_may_be_cancelled():
    """`pendiente -> cancelado` is allowed.

    A cancellation writes nothing but the instant: no charge, no debt.
    """
    assert (
        propuesta_transicion_permitida(
            PropuestaEstado.PENDIENTE, PropuestaEstado.CANCELADO
        )
        is None
    )


def test_a_confirmed_proposal_may_not_be_confirmed_again():
    """A confirmed proposal is refused with `propuesta_ya_confirmada`."""
    assert (
        propuesta_transicion_permitida(
            PropuestaEstado.CONFIRMADO, PropuestaEstado.CONFIRMADO
        )
        == PROPUESTA_YA_CONFIRMADA
    )


def test_a_cancelled_proposal_may_not_be_cancelled_again():
    """A cancelled proposal is refused with `propuesta_ya_cancelada`."""
    assert (
        propuesta_transicion_permitida(
            PropuestaEstado.CANCELADO, PropuestaEstado.CANCELADO
        )
        == PROPUESTA_YA_CANCELADA
    )


def test_the_transition_is_one_way():
    """Neither terminal state goes back to `pendiente`.

    The machine has two branches and no way back: a confirmed proposal stays
    confirmed and a cancelled one stays cancelled.
    """
    for estado in (PropuestaEstado.CONFIRMADO, PropuestaEstado.CANCELADO):
        refusals = {
            propuesta_transicion_permitida(estado, destino)
            for destino in PropuestaEstado
        }
        assert None not in refusals, (
            f"a {estado.value} proposal must not be able to move anywhere"
        )


def test_a_confirmed_proposal_may_not_be_cancelled():
    """A confirmed proposal is already a charge; it cannot be withdrawn."""
    assert (
        propuesta_transicion_permitida(
            PropuestaEstado.CONFIRMADO, PropuestaEstado.CANCELADO
        )
        == PROPUESTA_YA_CONFIRMADA
    )


def test_a_cancelled_proposal_may_not_be_confirmed():
    """A cancelled proposal never becomes a charge."""
    assert (
        propuesta_transicion_permitida(
            PropuestaEstado.CANCELADO, PropuestaEstado.CONFIRMADO
        )
        == PROPUESTA_YA_CANCELADA
    )


def test_the_guard_reads_the_stored_state_not_a_projection():
    """The guard is the proposal's own state.

    A proposal is a stored row with a stored `estado`; the transition guard
    reads it and nothing else. There is no projection of the ledger to
    reconcile — the proposal *is* the state.
    """
    # The same destination, two different stored states, two different
    # answers. The guard consults the stored state, never the destination
    # alone.
    assert (
        propuesta_transicion_permitida(
            PropuestaEstado.PENDIENTE, PropuestaEstado.CONFIRMADO
        )
        is None
    )
    assert (
        propuesta_transicion_permitida(
            PropuestaEstado.CONFIRMADO, PropuestaEstado.CONFIRMADO
        )
        == PROPUESTA_YA_CONFIRMADA
    )


def test_the_v1_transition_table_is_gone():
    """The v1 `transicion_permitida` no longer exists.

    It was a two-state transition table over a charge's confirmation
    history, and the dispute machinery it served is gone (ADR-18). The
    proposal transition replaced it.
    """
    from tienda.domain import confirmation as modulo

    assert not hasattr(modulo, "transicion_permitida")
    assert not hasattr(modulo, "escalado_sin_confirmar")
    assert not hasattr(modulo, "DISPUTA_ABIERTA")
    assert not hasattr(modulo, "CARGO_YA_RECONCILIADO")


# ---------------------------------------------------------------------------
# The rule — a charge requires its confirmation
# ---------------------------------------------------------------------------


def test_a_charge_that_does_not_exist_yet_may_be_written():
    """A new charge may be written: its confirmation goes with it."""
    assert confirmacion_requerida(charge_exists=False, confirmation_rows=[]) is True


def test_a_charge_with_a_confirmation_may_be_written():
    """A charge that already carries its confirmation is consistent."""
    filas = [_row(ConfirmState.CONFIRMADO)]

    assert confirmacion_requerida(charge_exists=True, confirmation_rows=filas) is True


def test_a_charge_without_a_confirmation_may_not_be_written():
    """Rule 5: a charge without a confirmation is refused.

    This is the shape the write path must never let exist. It is
    unreachable through the API — ADR-19 gives the ledger a single entry
    point — and the check exists so no other write path can create it.
    """
    assert confirmacion_requerida(charge_exists=True, confirmation_rows=[]) is False
