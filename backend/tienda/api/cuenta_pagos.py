"""The person's payment proposal - the one the credential used to make.

**The proposal writes NO ledger row** (CC-07, PA-09): the `pago` itself
is a separate `LedgerEntry` that the OWNER appends when he validates
it, so the book stays append-only even though the request that
preceded it is not.

**The body is `{importe, referencia?}` and it names NO charge.** The
person does not choose which debt it pays: she proposes an amount and
the FIFO decides which charges it retires (ADR-27). A body that carries
a `cargo_id` is refused on the **presence** of the field.

**The scope is the PERSON's**, not the shop's: she may owe in several
shops, and each of them is hers. The proposal names a shop - the one
the money is for - and that is the shop whose debt the FIFO retires.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from tienda.api.exceptions import DomainValidationError
from tienda.api.vinculos import EsClienteConVinculo
from tienda.models import Vinculo


class PagoProponerView(APIView):
    """`POST /api/v1/cuenta/pagos/proponer/` - **she proposes a payment**.

    The body is `{importe, referencia?, tienda_id?}` and it names **no
    charge**: the person does not choose which debt it pays, so she
    proposes an amount and the FIFO decides which charges it retires
    (ADR-27). A body that carries a `cargo_id` is refused on the
    **presence** of the field.

    **The `tienda_id` is the shop the money is for**, and it is not a
    guess: a person may owe in several shops, and a payment belongs to
    ONE of them. It is optional, and when it is absent the payment goes
    to the only shop she owes in - but if she owes in several, the
    refusal is `tienda_requerida`, because guessing would pay the wrong
    shop's debt.

    **It writes nothing to the book.** The proposal creates no ledger
    row: the `pago` itself is a separate `LedgerEntry` that the OWNER
    appends when he validates it, so the book stays append-only even
    though the request that preceded it is not.
    """

    permission_classes = [EsClienteConVinculo]
    http_method_names = ["post"]

    def post(self, request):
        from tienda.services import proponer_pago

        from tienda.api.vinculos import _cliente_de

        cliente = _cliente_de(request.user)
        if cliente is None:
            return Response(
                {"codigo_error": "cliente_requerido", "detail": "Falta la cliente."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            from tienda import services

            services.exigir_campos_no_admitidos(
                request.data, {"importe", "referencia", "tienda_id"}
            )

            # **La tienda, si ella no debe en una sola.** Si debe en
            # varias, tiene que decir en cual: adivinar seria pagar la
            # deuda de otra tienda.
            tienda_id = request.data.get("tienda_id")
            if tienda_id is None:
                vinculos = list(
                    Vinculo.objects.filter(
                        cliente=cliente, estado="aceptado"
                    ).values_list("tienda_id", flat=True)
                )
                if len(vinculos) == 1:
                    tienda_id = vinculos[0]
                elif not vinculos:
                    tienda_id = -1  # ninguna: la refusara el servicio
                # Con varias, `tienda_id` queda None y el servicio dice
                # que hay que elegir.

            propuesta = proponer_pago(
                cliente,
                importe=request.data.get("importe", 0),
                referencia=request.data.get("referencia", ""),
                shop_id=tienda_id,
            )
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {
                "id": propuesta.id,
                "estado": propuesta.estado,
                "importe": str(propuesta.importe),
                "referencia": propuesta.referencia,
            },
            status=status.HTTP_201_CREATED,
        )
