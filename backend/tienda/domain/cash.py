"""The close of the day: what the drawer should hold and what it held (CP-04).

Two rules, and the gap between them is the whole point.

**`caja_al_cierre(opening_cash, movements, pagos, at)`** — the cash the
drawer should hold at the close instant. It is the same computation as
`position.cash_at`, called with `at` = the close instant.

**The caller never supplies `esperado`.** There is no `esperado` parameter
here, and there cannot be one: `esperado` is *derived* from the movements and
the payments, so a client-supplied figure would be a client-supplied
balance. The signature makes that structurally impossible — the only way to
get a number out is to derive it.

**`desviacion_cierre(esperado, contado)`** — the difference between what
should have been there and what was counted: `esperado − contado`. This is
the value the `DayClose` stores as its deviation, and it is signed: a
positive deviation means the drawer holds more than it should, a negative one
means it holds less.
"""

from __future__ import annotations

from decimal import Decimal

from .position import cash_at


def caja_al_cierre(opening_cash, movements, pagos, at) -> Decimal:
    """The cash the drawer should hold at the close instant `at`.

    The same computation as `position.cash_at` — `inicial + Σ(entradas) −
    Σ(salidas) + Σ(pagos)` — called with `at` set to the close instant.

    The caller never supplies the expected figure: it is **derived** here,
    which is what makes it trustworthy. The `DayClose.esperado` column
    therefore holds a derived value and never a client-submitted one.
    """
    return cash_at(opening_cash, movements, pagos, at)


def desviacion_cierre(esperado, contado) -> Decimal:
    """The deviation of the close: `esperado − contado`.

    The value the `DayClose` stores. It is signed — positive when the
    drawer holds more than it should, negative when it holds less — and it
    is never an absolute value, because the sign is the information the
    owner needs.
    """
    return Decimal(esperado) - Decimal(contado)
