"""The staff schemas of design §9.2 — the allowlists of the two audiences.

DRF's `fields` is **exhaustive**, so "no alias in ANY JSON path" is a
property of the schema, not a promise of the view. Every class here
declares exactly what it may carry, and the absence of a field is the
guarantee.

The five classes in this module are the owner's and the dependent's. They
are **not** pairwise disjoint, and they are not meant to be: the
`dependiente` is a shop role, not an outsider, and CP-05 requires it to
read the close. What the classes share is what a shop role may share —
`caja`, `clientes` and `cierre_hoy` for the two positions; `esperado`,
`contado` and `desviacion` for the two closes.

The `PosicionDependienteSerializer` is the one that carries a promise
rather than a shape: its `clientes` is a `SerializerMethodField` that
returns `[]` **without executing the customer query**. The dependent is
answered with an empty list, and the database is never asked for the
customer rows — so the 403 boundary of design §7.1 does not depend on
filtering a query afterwards, it never builds one.
"""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

#: The nine fields that are the staff's alone. The client class declares
#: **none** of them, and that is the assertion that carries CAC-10.
#:
#: The list is the same nine wherever it is enumerated — §7.2, §9.2's
#: opening prose, §9.2's field lists and the test of §15.2 — so a reader
#: or a test author never has to reconstruct it.
CAMPOS_SOLO_DE_PERSONAL = frozenset({
    "caja",
    "fiado_pendiente",
    "posicion_real",
    "buckets",
    "credit_limit",
    "antiguedad_max_dias",
    "suspended_reason",
    "codigo",
    "prefix",
})


class ClienteEscaleraSerializer(serializers.Serializer):
    """One row of the risk ladder: the owner's view of a customer.

    It carries the alias and the figures the ladder sorts by. The
    `dependiente` never sees it — it is declared only in
    `PosicionDuenoSerializer`.
    """

    alias = serializers.CharField()
    pendiente = serializers.DecimalField(max_digits=12, decimal_places=2)
    antiguedad_max_dias = serializers.IntegerField()
    suspendido = serializers.BooleanField()
    motivo = serializers.CharField(allow_null=True, required=False)


class SerieCajaSerializer(serializers.Serializer):
    """One day of the 30-day cash series.

    **Declared cut-line 1.** The chart is a React element, not a
    capability: dropping it changes no rule of the system.
    """

    fecha = serializers.DateField()
    caja = serializers.DecimalField(max_digits=12, decimal_places=2)


class PosicionDuenoSerializer(serializers.Serializer):
    """The owner's board: everything the owner may see.

    `caja`, `fiado_pendiente`, `posicion_real`, `buckets`, `clientes[]`,
    `serie_caja[]` and `cierre_hoy`.
    """

    caja = serializers.DecimalField(max_digits=12, decimal_places=2)
    fiado_pendiente = serializers.DecimalField(max_digits=12, decimal_places=2)
    posicion_real = serializers.DecimalField(max_digits=12, decimal_places=2)
    buckets = serializers.DictField(child=serializers.DecimalField(
        max_digits=12, decimal_places=2
    ))
    clientes = ClienteEscaleraSerializer(many=True)
    serie_caja = SerieCajaSerializer(many=True)
    cierre_hoy = serializers.DictField(required=False, allow_null=True)


class PosicionDependienteSerializer(serializers.Serializer):
    """The dependent's board: the reduced payload of design §7.

    It declares **only** `caja`, `clientes` and `cierre_hoy`. The ladder,
    `posicion_real`, `fiado_pendiente` and `buckets` are absent, and so are
    the alias, the `credit_limit`, the `antiguedad_max_dias` and the
    credential.

    The `clientes` is a `SerializerMethodField` that returns `[]` **without
    executing the customer query**. The guarantee is not "the rows are
    filtered afterwards" — it is "the rows are never asked for".
    """

    caja = serializers.DecimalField(max_digits=12, decimal_places=2)
    clientes = serializers.SerializerMethodField()
    cierre_hoy = serializers.DictField(required=False, allow_null=True)

    def get_clientes(self, obj) -> list:
        """The empty list, without touching the customer table.

        The dependent is answered with no customers at all. The method
        takes no query parameter, so there is nothing to filter and nothing
        to leak: the answer is empty by construction, not by omission.
        """
        return []


class CierreDuenoSerializer(serializers.Serializer):
    """The day's close, as the owner sees it.

    `date`, `esperado`, `contado` and `desviacion`. The `esperado` is the
    **derived** cash at the close instant; the `desviacion` is the derived
    difference. Neither is client-supplied.
    """

    date = serializers.DateField()
    esperado = serializers.DecimalField(max_digits=12, decimal_places=2)
    contado = serializers.DecimalField(max_digits=12, decimal_places=2)
    desviacion = serializers.DecimalField(max_digits=12, decimal_places=2)


class CierreDependienteSerializer(serializers.Serializer):
    """The day's close, as the dependent sees it.

    The same three figures as the owner's, **without the date**. The
    dependent may read the close — CP-05 requires it — but the date is
    the owner's, and the close of today is the one that is on the screen.
    """

    esperado = serializers.DecimalField(max_digits=12, decimal_places=2)
    contado = serializers.DecimalField(max_digits=12, decimal_places=2)
    desviacion = serializers.DecimalField(max_digits=12, decimal_places=2)


class LineaPropuestaSerializer(serializers.Serializer):
    """One line of a `FiadoPropuesto`, as the counter screen shows it.

    `producto`, `cantidad`, `precio_unitario` and `total`. The screen
    holds the `desglose` and nothing else: no balance, no ageing, no
    other customer.
    """

    producto = serializers.CharField()
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=3)
    precio_unitario = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


class PropuestaPantallaSerializer(serializers.Serializer):
    """The proposal on the counter screen.

    `total` and `lineas[]`. It shares the client's `total` and `lineas[]`
    names **on purpose**: it shows one proposal's `desglose` at the
    counter, and the client is entitled to see the `desglose` of the
    charges it confirmed.

    It does not declare `credit_limit`, `codigo` or `prefix`, and it never
    carries the customer's ageing or another proposal.
    """

    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    lineas = LineaPropuestaSerializer(many=True)
