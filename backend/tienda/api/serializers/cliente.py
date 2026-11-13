"""The client schema of design §9.2 — the allowlist of the client's own data.

This class is where the leak guarantee lives. It declares the client's own
statement and **none of the nine staff-only fields** — no `caja`, no
`fiado_pendiente`, no `posicion_real`, no `buckets`, no `credit_limit`, no
`antiguedad_max_dias`, no `suspended_reason`, no `codigo`, no `prefix` —
and it never carries another customer's data.

The guarantee is about **data, not names**. The client class shares
`total`, `lineas[]`, `producto`, `cantidad` and `precio_unitario` with the
staff classes, and that is correct: the client is entitled to see the
`desglose` of the charges it confirmed. What must never cross is the
information, and the class simply does not declare it.

DRF's `fields` is exhaustive, so this is a property of the schema rather
than a promise of the view: a field that is not declared cannot be in the
response, whatever the view hands over.

**The itemisation is always present.** Every charge in the statement is a
confirmed charge with a mandatory `desglose`, so every charge carries its
`lineas[]`. There is no "unconfirmed-charge rule" any more — a charge
without a confirmation does not exist, so it cannot appear and its lines
cannot leak.

**`pagado` and `saldo`.** The statement says how much of each charge the
client has already paid and how much is still owed. `pagado` is the sum of
the `ImputacionPago` rows against that charge; `saldo` is the amount minus
it. A charge of 15,00 € settled by 5,00 € reads `pagado: 5,00, saldo:
10,00` — the client sees "5/15" — and a charge of 8,00 € fully settled
reads `pagado: 8,00, saldo: 0,00`. Both are **derived on read** and
neither is stored: the imputations are the record.
"""

from __future__ import annotations

from rest_framework import serializers

from tienda.api.serializers.fields import fields_de
from tienda.api.serializers.staff import CAMPOS_SOLO_DE_PERSONAL


class LineaCargoSerializer(serializers.Serializer):
    """One line of a charge's `desglose`, as the client sees it.

    `producto`, `cantidad`, `precio_unitario` and `total`. The price is
    the **snapshot** the client confirmed: a later change to the catalogue
    never rewrites it (IC-08).
    """

    producto = serializers.CharField()
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=3)
    precio_unitario = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


class CargoClienteSerializer(serializers.Serializer):
    """One confirmed charge, as the client sees it in the statement.

    `id`, `fecha`, `amount`, `confirmado_en`, `pagado`, `saldo` and
    `lineas[]`.
    """

    id = serializers.IntegerField()
    fecha = serializers.DateTimeField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    confirmado_en = serializers.DateTimeField(allow_null=True, required=False)
    pagado = serializers.DecimalField(max_digits=12, decimal_places=2)
    saldo = serializers.DecimalField(max_digits=12, decimal_places=2)
    lineas = LineaCargoSerializer(many=True)


class EstadoClienteSerializer(serializers.Serializer):
    """The client's own statement: the alias, the total and the charges.

    This is the schema that carries CAC-10, and it is asserted rather
    than assumed: the class declares **none** of the nine staff-only
    fields, and the test of §15.2 reads its declared `fields` and fails if
    it names any of them.
    """

    alias = serializers.CharField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    cargos = CargoClienteSerializer(many=True)


def verificar_aislamiento_del_cliente() -> set:
    """The staff-only fields the client schema declares — it declares none.

    This is the check of §15.2, exposed as a function so the test and the
    code agree on one definition. It returns the offending names; an empty
    set is the guarantee.
    """
    declarados = fields_de(EstadoClienteSerializer)
    return declarados & CAMPOS_SOLO_DE_PERSONAL
