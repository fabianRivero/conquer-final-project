"""The itemised charge: its lines, its price and its declared amount.

Three rules, all pure functions over plain values.

**`total_de_linea(cantidad, precio_unitario)`** — the total of one line:
`round(cantidad × precio_unitario, 2)`. It is the same rounding the database
`CHECK` mirrors (IC-06), so a line and its stored total can never disagree:
the line is computed once and the constraint checks the same expression.

**`precio_unitario_de(precio_catalogo, precio_solicitado)`** — the price a
line actually carries (PC-02). The catalogue price is the **default**; an
explicit override **wins**. This is the whole deviation rule — the owner may
price a line away from the catalogue, and the line then holds the amount
actually charged, which is also a **snapshot**: a later change to the
catalogue price never rewrites a stored line (IC-08).

**`charge_amount_matches(lines, declared_amount)`** — whether the declared
amount of a charge equals the total of its own itemisation (IC-02). A
mismatch is the source of `lineas_descuadradas`.

The one boundary worth stating plainly: **a charge with no lines matches any
declared amount.** An empty `lines` sequence is a legal, line-less charge
whose whole total *is* its declared amount, so the comparison is vacuously
true and the charge is accepted as declared.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# The number of decimals a money figure carries. A `Decimal` quantised to two
# places is what the database stores, so the rules work in that scale.
DOS_DECIMALES = Decimal("0.01")


def total_de_linea(cantidad, precio_unitario) -> Decimal:
    """The total of one line: `round(cantidad × precio_unitario, 2)`.

    The rounding is half-up, which is the rounding PostgreSQL's `round()`
    applies to a numeric — the same one the `CHECK` constraint of IC-06
    mirrors. A quantity of 3 at a price of 1,00 € is 3,00 €; a quantity of
    2,5 at a price of 1,25 € is 3,13 €, not 3,12 €.
    """
    producto = Decimal(cantidad) * Decimal(precio_unitario)
    return producto.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


def precio_unitario_de(precio_catalogo, precio_solicitado) -> Decimal:
    """The price a line carries: the override when there is one.

    `precio_catalogo` is the price of the product in the catalogue.
    `precio_solicitado` is the price the owner asked for on this charge, and
    it is `None` when the owner did not override it.

    The override **wins** when it is present; otherwise the catalogue price
    is the price. There is no extra friction and no intermediate step — the
    function returns the price, and the line holds it as a snapshot.
    """
    if precio_solicitado is not None:
        return Decimal(precio_solicitado)
    return Decimal(precio_catalogo)


def charge_amount_matches(lines, declared_amount) -> bool:
    """Whether the declared amount equals the total of the charge's lines.

    `lines` are the `CargoLine` records of the charge and `declared_amount`
    is the amount the charge declares. The comparison is made on the
    **rounded** line totals, so it agrees with what the database stores.

    **A charge with no lines matches any declared amount.** An empty `lines`
    sequence is a legal, line-less charge: its whole total *is* its declared
    amount, so there is nothing to compare and the charge is accepted as
    declared. The empty case is therefore handled **before** the sum — the
    sum of no lines is zero, and comparing that against the declared amount
    would refuse a line-less charge that declares anything but zero.
    """
    if not lines:
        return True

    declarado = Decimal(declared_amount).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)
    total = sum(
        (Decimal(line.total).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP) for line in lines),
        Decimal("0"),
    )
    return total == declarado
