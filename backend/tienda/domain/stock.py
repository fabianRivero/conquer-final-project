"""The recorded movements of the shelf (CP-07).

`existencias_registradas` returns the figure **and** the qualifier that
says what the figure is worth.

The figure is `Σ entradas − Σ salidas` over the recorded stock movements.
It is derived on read — no field named `stock` exists anywhere in the
schema.

The qualifier is `techo_no_conteo`: a **ceiling**, not a count. What the
shop logged is not a verified inventory, so the number is an upper bound on
what is really there, never a promise about it.

**No rule depends on it.** Not a price, not a limit, not a suspension, not
the position — nothing in this package reads the figure. The qualifier is
returned so that whoever displays it can say what it means, and so that a
future rule that did depend on it would have to name the dependency
explicitly.
"""

from __future__ import annotations

from decimal import Decimal

from .types import MovementKind, StockLine, StockQualifier

CERO = Decimal("0")


def existencias_registradas(movements) -> tuple[Decimal, StockQualifier]:
    """The recorded stock of a product, and the qualifier that bounds it.

    `movements` are the `StockLine` records of the product — the `entrada`
    and `salida` rows. The result is the tuple `(Σ entradas − Σ salidas,
    techo_no_conteo)`.

    The qualifier is returned **with** the figure, not beside it: it is part
    of the answer, because a caller that receives the number without it would
    read it as a count.
    """
    total = CERO
    for movement in movements:
        if movement.kind == MovementKind.ENTRADA:
            total += movement.cantidad
        elif movement.kind == MovementKind.SALIDA:
            total -= movement.cantidad
    return total, StockQualifier.TECHO_NO_CONTEO
