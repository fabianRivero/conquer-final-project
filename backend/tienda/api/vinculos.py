"""The link, and the client's consent.

**The shop asks; the client answers.** The shop creates a `pendiente`
link, and the client accepts or refuses it **from her own account**. The
shop cannot do it for her: it does not have her credentials, and it must
not decide for her.

**A pending link shows the shop's name and nothing else.** If she could
see the debt and the ageing first, the consent would be a formality - she
would already have seen everything the acceptance reveals. The link she
is asked about says which shop is asking, and no more.

**The owner removes without asking.** The removal is the owner's alone:
the client does not consent to being removed. Her debts and her history
stay - the book is append-only - but the confidence is gone, and no new
fiado can be made.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from tienda.api.exceptions import DomainValidationError
from tienda.api.personal import EsDuenoDelNegocio
from tienda.models import Customer, PerfilCliente, Shop, Vinculo


class EsClienteConVinculo(BasePermission):
    """The request carries a PERSON's session - the client's own.

    **And she has a client profile.** The session that identifies a
    person is not enough: the link's routes are the client's, and the
    client is the one with the profile.
    """

    def has_permission(self, request, view) -> bool:
        from tienda.api.cuenta import SesionDePersona

        if not SesionDePersona().has_permission(request, view):
            return False
        return PerfilCliente.objects.filter(user=request.user).exists()

    def has_object_permission(self, request, view, obj) -> bool:
        return True


class VinculosDelClienteView(APIView):
    """`GET /api/v1/cuenta/vinculos/` - the client's own links.

    **A pending link shows the shop's name and the buttons - and nothing
    else.** The acceptance is what opens the owner's figures to her.
    """

    permission_classes = [EsClienteConVinculo]
    http_method_names = ["get"]

    def get(self, request):
        from tienda.services import vinculos_del_cliente

        return Response(vinculos_del_cliente(_cliente_de(request.user)))


class VinculoAceptarView(APIView):
    """`POST /api/v1/cuenta/vinculos/aceptar/` - she accepts.

    **Only she may do it.** The shop does not have her credentials, and
    it must not decide for her.
    """

    permission_classes = [EsClienteConVinculo]
    http_method_names = ["post"]

    def post(self, request):
        from tienda.services import aceptar_vinculo

        cliente = _cliente_de(request.user)
        vinculo_id = request.data.get("vinculo_id")
        if vinculo_id is None:
            return Response(
                {"codigo_error": "vinculo_requerido", "detail": "Falta el vinculo."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            vinculo = aceptar_vinculo(cliente, vinculo_id)
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {
                "id": vinculo.id,
                "tienda": vinculo.tienda.name,
                "estado": vinculo.estado,
                "credit_limit": vinculo.credit_limit,
            }
        )


class VinculoRechazarView(VinculoAceptarView):
    """`POST /api/v1/cuenta/vinculos/rechazar/` - she refuses.

    **A refusal is not a removal**: the shop may ask again, and she may
    answer differently the next time.
    """

    def post(self, request):
        from tienda.services import rechazar_vinculo

        cliente = _cliente_de(request.user)
        vinculo_id = request.data.get("vinculo_id")
        if vinculo_id is None:
            return Response(
                {"codigo_error": "vinculo_requerido", "detail": "Falta el vinculo."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            vinculo = rechazar_vinculo(cliente, vinculo_id)
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response({"id": vinculo.id, "estado": vinculo.estado})


class VinculosDelDuenoView(APIView):
    """`GET` and `POST /api/v1/tienda/vinculos/` - the shop's links.

    `POST` is the shop ASKING: the link is created `pendiente`, and only
    the client may answer it.
    """

    permission_classes = [EsDuenoDelNegocio]
    http_method_names = ["get", "post"]

    def _vinculos(self, request):
        """The links of the shop of the session.

        **The link names the SHOP** - and the business that owns it is
        what the owner manages. So the links of the session's shop are
        the ones the owner sees.
        """
        from tienda.api.permissions import current_shop

        shop_id = current_shop(request)
        if shop_id is None:
            return []
        return list(
            Vinculo.objects.filter(tienda_id=shop_id)
            .select_related("cliente")
            .order_by("id")
        )

    def get(self, request):
        return Response(
            [
                {
                    "id": vinculo.id,
                    "cliente_id": vinculo.cliente_id,
                    "alias": vinculo.cliente.alias,
                    "estado": vinculo.estado,
                    "credit_limit": vinculo.credit_limit,
                    "pedido_at": vinculo.pedido_at,
                    "aceptado_at": vinculo.aceptado_at,
                    "rechazado_at": vinculo.rechazado_at,
                    "eliminado_at": vinculo.eliminado_at,
                }
                for vinculo in self._vinculos(request)
            ]
        )

    def post(self, request):
        from tienda.api.permissions import current_shop
        from tienda.services import pedir_vinculo

        shop_id = current_shop(request)
        if shop_id is None:
            return Response(status=status.HTTP_403_FORBIDDEN)

        cliente_id = request.data.get("cliente_id")
        alias = (request.data.get("alias") or "").strip()
        credit_limit = request.data.get("credit_limit")

        cliente = None
        if cliente_id is not None:
            cliente = Customer.objects.filter(id=cliente_id).first()
        elif alias:
            # The shop may NAME the person: she is one person in every
            # shop, so the alias finds her and the link says she is
            # trusted HERE.
            cliente = Customer.objects.filter(alias=alias).first()

        if cliente is None:
            return Response(
                {
                    "codigo_error": "cliente_no_existe",
                    "detail": "No hay ninguna persona con ese alias.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            vinculo = pedir_vinculo(
                request.user,
                Shop.objects.get(id=shop_id),
                cliente,
                credit_limit=credit_limit,
            )
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {
                "id": vinculo.id,
                "cliente_id": vinculo.cliente_id,
                "alias": vinculo.cliente.alias,
                "estado": vinculo.estado,
                "credit_limit": vinculo.credit_limit,
            },
            status=status.HTTP_201_CREATED,
        )


class VinculoEliminarView(APIView):
    """`DELETE /api/v1/tienda/vinculos/{cliente_id}/` - the owner removes.

    **The owner does not ask.** The client does not consent to being
    removed, and the shop does not need her to. Her debts and her
    history stay - the book is append-only - but the confidence is gone.
    """

    permission_classes = [EsDuenoDelNegocio]
    http_method_names = ["delete"]

    def delete(self, request, cliente_id):
        from tienda.api.permissions import current_shop
        from tienda.services import eliminar_vinculo

        shop_id = current_shop(request)
        if shop_id is None:
            return Response(status=status.HTTP_403_FORBIDDEN)

        cliente = Customer.objects.filter(id=cliente_id).first()
        if cliente is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            vinculo = eliminar_vinculo(
                request.user, Shop.objects.get(id=shop_id), cliente
            )
        except Exception:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response({"id": vinculo.id, "estado": vinculo.estado})


def _cliente_de(user):
    """The customer row of a person.

    **The person and the customer are the same human**, and the link
    joins them: the link names the person, and the person is the one
    who has the debts.
    """
    vinculo = (
        Vinculo.objects.select_related("cliente")
        .filter(cliente__alias=user.username)
        .first()
    )
    if vinculo is not None:
        return vinculo.cliente
    return Customer.objects.filter(alias=user.username).first()
