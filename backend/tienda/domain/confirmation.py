"""The derived confirmation state of a charge (IC-03, IC-04).

No stored state exists anywhere: not on the charge, not on the customer. The
effective state is computed **on read** from the charge's `Confirmacion`
rows, and this module is where that computation lives.

**`confirmacion_efectiva(rows)`** — the latest row of the charge's history,
or `None` when the charge carries no row at all. "Latest" is the last row by
`(confirmado_en, id)`: the instant the row was appended, with the identifier
as the tie-breaker so the answer is total.

**`estado_cargo(rows)`** — the projection: `confirmado` or `sin_confirmar`.
It reads the rows and **no stored state**, and it is a **read-time projection
only** — it is never the guard for a write.

**`propuesta_transicion_permitida(estado_actual, destino)`** — the guard for
the one-way transition of §6. It reads the **stored** proposal state, not a
projection of the ledger, because the proposal *is* the state: a proposal
moves from `pendiente` to exactly one of `confirmado` or `cancelado`, and
never back. The v1 `transicion_permitida` — a two-state transition table
over the charge's confirmation history — has no object any more.

**`confirmacion_requerida(charge_exists, confirmation_rows)`** — whether a
charge may be written at all. Rule 5 of §3.2 forbids a `cargo` without a
`Confirmacion` in the same transaction, so the write path refuses it. The
charge exists only at the confirmation (ADR-19): a prepared proposal writes
nothing at all.
"""

from __future__ import annotations

from .types import ChargeState, ConfirmacionRow, ConfirmState, PropuestaEstado

# The refusal codes of the proposal transition guard. They are the
# `codigo_error` values the API answers with (design §9.3).
PROPUESTA_YA_CONFIRMADA = "propuesta_ya_confirmada"
PROPUESTA_YA_CANCELADA = "propuesta_ya_cancelada"


def confirmacion_efectiva(rows) -> ConfirmacionRow | None:
    """The latest confirmation row of a charge, or `None`.

    The latest row is the one with the greatest `(confirmado_en, id)`. A row
    that carries no `confirmado_en` — which the database forbids for
    `confirmado`, but which a hand-built fixture may hold — sorts first, so a
    dated row always wins over an undated one.

    A charge with no rows at all has no effective confirmation, and `None`
    is returned.
    """
    if not rows:
        return None
    return max(rows, key=_row_key)


def estado_cargo(rows) -> ChargeState:
    """The effective state of a charge, derived from its rows.

    `confirmado` or `sin_confirmar`. **No stored state is consulted**: the
    function reads the rows and nothing else.

    The result is a **read-time projection only**. It is never the guard for
    a write — `confirmacion_requerida` is, and it looks at the presence of
    the rows rather than at this projection.

    A charge with no rows reads `sin_confirmar`, and that state is
    **unreachable in normal operation**: rule 5 of §3.2 forbids a charge
    without a confirmation in the same transaction. It is the value a
    hand-built fixture reads, and the value a partially-written charge would
    read — but the write path never lets that happen.
    """
    efectiva = confirmacion_efectiva(rows)
    if efectiva is None:
        return ChargeState(estado=ConfirmState.SIN_CONFIRMAR, confirmacion=None)
    return ChargeState(estado=efectiva.estado, confirmacion=efectiva)


def propuesta_transicion_permitida(estado_actual, destino) -> str | None:
    """Whether a proposal may move from `estado_actual` to `destino`.

    Returns `None` when the transition is allowed, and the refusal
    `codigo_error` otherwise.

    The machine is **one-way and has two branches** (§6):

    * `pendiente -> confirmado` — the owner (or the `dependiente`, if the N5
      gate opens) confirms it. The charge and its lines are written in the
      same transaction.
    * `pendiente -> cancelado` — the client declined. Nothing is written
      except the instant; no charge, no debt.

    Every other pair is refused. A confirmed proposal may not be confirmed
    again (`propuesta_ya_confirmada`) and a cancelled one may not be
    cancelled again (`propuesta_ya_cancelada`); neither can go back to
    `pendiente`, because the transition is one-way.

    **The guard is the stored proposal state**, not a projection of the
    ledger. The proposal *is* the state: there is no second source of truth
    to reconcile.
    """
    if estado_actual == PropuestaEstado.PENDIENTE:
        if destino == PropuestaEstado.CONFIRMADO:
            return None
        if destino == PropuestaEstado.CANCELADO:
            return None
        # Moving to `pendiente` from `pendiente` is not a transition the
        # shop performs; the proposal is already pending.
        return PROPUESTA_YA_CONFIRMADA

    if estado_actual == PropuestaEstado.CONFIRMADO:
        return PROPUESTA_YA_CONFIRMADA

    if estado_actual == PropuestaEstado.CANCELADO:
        return PROPUESTA_YA_CANCELADA

    return PROPUESTA_YA_CONFIRMADA


def confirmacion_requerida(charge_exists, confirmation_rows) -> bool:
    """Whether a charge may be written at all.

    Rule 5 of §3.2: a `cargo` requires its `Confirmacion` in the **same
    transaction**. The function answers that question from two plain values —
    whether the charge exists, and whether the confirmation rows carry one —
    and never from a stored flag.

    The answer is `True` when the write is allowed: either the charge does
    not exist yet (and the confirmation will be written with it), or the
    confirmation is already there.

    It is `False` when a charge exists with no confirmation at all, which is
    the shape rule 5 forbids. That state is unreachable through the API —
    ADR-19 gives the ledger a single entry point — and the check exists so
    no other write path can create a charge without a confirmation.
    """
    if not charge_exists:
        # The charge is being written now, and the confirmation goes with it.
        return True
    return bool(confirmation_rows)


def _row_key(row: ConfirmacionRow):
    """The order key of a confirmation row: `(confirmado_en, id)`.

    An undated row sorts before every dated one, so a dated row always wins
    the "latest" comparison.
    """
    return (row.confirmado_en is not None, row.confirmado_en, row.id)
