"""The derived confirmation state of a charge (IC-03, IC-04).

No stored state exists anywhere: not on the charge, not on the customer. The
effective state is computed **on read** from the charge's `Confirmacion`
rows, and this module is where that computation lives.

**`confirmacion_efectiva(rows)`** — the latest row of the charge's history,
or `None` when the charge carries no row at all. "Latest" is the last row by
`(confirmado_en, id)`: the instant the row was appended, with the identifier
as the tie-breaker so the answer is total.

**`estado_cargo(rows)`** — the projection: `confirmado`, `en_disputa` or
`sin_confirmar`. It reads the rows and **no stored state**, and it is a
**read-time projection only** — it is never the guard for a write.

**`transicion_permitida(origen, destino, *, filas, ya_reconciliada)`** — the
guard for a write, and the reason the projection is not the guard. The guard
for a `confirmado` destination is the **presence of a `confirmado` row**, and
for an `en_disputa` destination the presence of an `en_disputa` row — never
the effective state alone. A charge whose rows are `[confirmado, en_disputa]`
reads `en_disputa`, yet it may not be confirmed again, and a state-only guard
would let that through.

**`escalado_sin_confirmar(estado, occurred_at, at, *, dias=7)`** — the
escalation flag of a charge nobody confirmed. It is `estado is sin_confirmar
and age_in_days(occurred_at, at) > dias`, and it is **derived, never stored**.
"""

from __future__ import annotations

from .ageing import age_in_days
from .types import ChargeState, ConfirmacionRow, ConfirmState

# The refusal codes of the transition guard. They are the `codigo_error`
# values the API answers with (design §9.3).
CARGO_YA_CONFIRMADO = "cargo_ya_confirmado"
DISPUTA_ABIERTA = "disputa_abierta"
CARGO_YA_RECONCILIADO = "cargo_ya_reconciliado"


def confirmacion_efectiva(rows) -> ConfirmacionRow | None:
    """The latest confirmation row of a charge, or `None`.

    The latest row is the one with the greatest `(confirmado_en, id)`. A row
    that carries no `confirmado_en` — which the database forbids for
    `confirmado` and `en_disputa` alike, but which a hand-built fixture may
    hold — sorts first, so a dated row always wins over an undated one.

    A charge with no rows at all has no effective confirmation, and `None`
    is returned.
    """
    if not rows:
        return None
    return max(rows, key=_row_key)


def estado_cargo(rows) -> ChargeState:
    """The effective state of a charge, derived from its rows.

    `confirmado`, `en_disputa` or `sin_confirmar`. **No stored state is
    consulted**: the function reads the rows and nothing else.

    The result is a **read-time projection only**. It is never the guard for
    a write — `transicion_permitida` is, and it looks at the presence of the
    rows rather than at this projection.

    A charge with no rows reads `sin_confirmar`, and it is still debt: the
    outstanding does not depend on the confirmation at all (IC-03).
    """
    efectiva = confirmacion_efectiva(rows)
    if efectiva is None:
        return ChargeState(estado=ConfirmState.SIN_CONFIRMAR, confirmacion=None)
    return ChargeState(estado=efectiva.estado, confirmacion=efectiva)


def transicion_permitida(origen, destino, *, filas, ya_reconciliada) -> str | None:
    """Whether a write may move a charge from `origen` to `destino`.

    Returns `None` when the transition is allowed, and the refusal
    `codigo_error` otherwise.

    `filas` is the charge's **full** `Confirmacion` history. The guard for a
    `confirmado` destination is the **presence of a `confirmado` row**, and
    for an `en_disputa` destination the presence of an `en_disputa` row —
    never the effective state alone. A charge whose rows are
    `[confirmado, en_disputa]` still reads `en_disputa`, but it may not be
    confirmed again.

    `ya_reconciliada` says whether the charge has already been reconciled by
    a `nota de crédito`; a reconciled charge may not be disputed.

    `origen` is the state the write reads as the current one. It is
    accepted for the caller's convenience, but the guard itself does not
    rely on it: the rows decide.
    """
    if destino == ConfirmState.CONFIRMADO:
        if _has_state(filas, ConfirmState.CONFIRMADO):
            return CARGO_YA_CONFIRMADO
        return None

    if destino == ConfirmState.EN_DISPUTA:
        if _has_state(filas, ConfirmState.EN_DISPUTA):
            return DISPUTA_ABIERTA
        if ya_reconciliada:
            return CARGO_YA_RECONCILIADO
        return None

    # Moving *to* `sin_confirmar` is never a write the shop performs: the
    # state is derived, so it cannot be set.
    return CARGO_YA_CONFIRMADO


def escalado_sin_confirmar(estado, occurred_at, at, *, dias: int = 7) -> bool:
    """Whether a charge nobody confirmed must be escalated.

    `estado is sin_confirmar and age_in_days(occurred_at, at) > dias`.

    The comparison is **strictly greater** than `dias`: a charge exactly
    `dias` old has not crossed the threshold yet, and one a day older has.

    The flag is **derived, never stored**. A charge that *is* confirmed or
    under dispute is never escalated, however old it is.
    """
    if estado != ConfirmState.SIN_CONFIRMAR:
        return False
    return age_in_days(occurred_at, at) > dias


def _has_state(filas, state: ConfirmState) -> bool:
    """Whether the history holds a row in `state`.

    The **presence** of the row is the guard — not the effective state, and
    not the recency of the row. A charge that was confirmed and then
    disputed holds both rows, and the `confirmado` row still blocks a second
    confirmation.
    """
    return any(row.estado == state for row in filas)


def _row_key(row: ConfirmacionRow):
    """The order key of a confirmation row: `(confirmado_en, id)`.

    An undated row sorts before every dated one, so a dated row always wins
    the "latest" comparison.
    """
    return (row.confirmado_en is not None, row.confirmado_en, row.id)
