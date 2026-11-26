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

#: The service layer, for the rules that are the same in every route:
#: the fields a body may carry.
from tienda import services


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

        from tienda.services import vinculo_para_la_persona

        return Response(vinculo_para_la_persona(vinculo, cliente))


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


class FiadosDelClienteView(APIView):
    """`GET /api/v1/cuenta/fiados/` - **her own fiados**, with their
    state.

    Every fiado of every shop she is trusted in, and the state says
    what happened: `pendiente` (the shop asked and she has not
    answered), `aceptado` (she said yes) or `rechazado` (she said no,
    with the reason she gave).

    **A pending fiado carries its lines and its total.** A figure she
    cannot see broken down is not a figure she confirmed - and the lines
    are there BEFORE she answers, because the answer is about those
    lines.
    """

    permission_classes = [EsClienteConVinculo]
    http_method_names = ["get"]

    def get(self, request):
        from tienda.services import fiados_del_cliente

        cliente = _cliente_de(request.user)
        if cliente is None:
            return Response([])

        return Response(fiados_del_cliente(cliente))


class CargosDelClienteView(APIView):
    """`GET /api/v1/cuenta/cargos/` - **her own charges**, with the
    state each one is in.

    The state is a WORD - `pendiente`, `parcial` or `pagado` - and it
    is derived on read, never stored.

    **The charges of EVERY shop she is trusted in.** A person may owe
    in several, and her account is the one place where all of them are
    hers together.
    """

    permission_classes = [EsClienteConVinculo]
    http_method_names = ["get"]

    def get(self, request):
        from tienda.services import cargos_del_cliente

        cliente = _cliente_de(request.user)
        if cliente is None:
            return Response([])

        return Response(cargos_del_cliente(cliente))


class FiadoAceptarView(APIView):
    """`POST /api/v1/cuenta/fiados/aceptar/` - **she accepts the fiado**.

    **The shop asks; she answers.** The owner prepared the figure and it
    waits for HER: the answer is given from her own account, and the
    shop may not answer for her. A shop that could accept for her would
    be a shop that could decide for her, and the consent of the 10.3
    would be worth nothing.

    **The body is `{fiado_id}` and nothing else.** The figure is the
    shop's, and the shop's figure is what the proposal already holds: a
    body that carries the charge's own fields is refused, because the
    person says yes or no and she does not write the charge.

    **Only she may do it**, and only her own fiados: the scope is the
    PERSON, not the shop - a person may have fiados in several shops,
    and each of them is hers. A fiado of another person is **NOT FOUND**,
    not refused: a 403 would confirm that it exists.
    """

    permission_classes = [EsClienteConVinculo]
    http_method_names = ["post"]

    def post(self, request):
        from tienda.services import aceptar_fiado

        cliente = _cliente_de(request.user)
        if cliente is None:
            return Response(
                {"codigo_error": "fiado_requerido", "detail": "Falta el fiado."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            services.exigir_campos_no_admitidos(
                request.data, {"fiado_id"}
            )
            cargo, propuesta = aceptar_fiado(cliente, request.data.get("fiado_id"))
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {
                "id": propuesta.id,
                "estado": propuesta.estado,
                "total": propuesta.total,
                "cargo_id": cargo.id,
            }
        )


class FiadoRechazarView(APIView):
    """`POST /api/v1/cuenta/fiados/rechazar/` - **she refuses the fiado**.

    **The body is `{fiado_id, motivo?}`.** The reason is her text, and
    it is **free text that may be empty**: a refusal without an
    explanation is not an answer, and an empty explanation is still an
    answer - she is not obliged to justify herself to the shop.

    **Nothing is written but the instant and her reason.** No charge, no
    lines, no confirmation: the outstanding never moved, because it never
    moved in the first place.
    """

    permission_classes = [EsClienteConVinculo]
    http_method_names = ["post"]

    def post(self, request):
        from tienda.services import rechazar_fiado

        cliente = _cliente_de(request.user)
        if cliente is None:
            return Response(
                {"codigo_error": "fiado_requerido", "detail": "Falta el fiado."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            services.exigir_campos_no_admitidos(
                request.data, {"fiado_id", "motivo"}
            )
            propuesta = rechazar_fiado(
                cliente,
                request.data.get("fiado_id"),
                motivo=request.data.get("motivo") or "",
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
                "motivo": propuesta.motivo_rechazo,
            }
        )


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

    **The person and the customer row are the same human**, and the
    `Customer.user` field says so. The person chose her username and
    the shop calls her by an ALIAS - "Ana" - and the two are NOT the
    same string: a person who registered as "ana.perez" is called "Ana"
    by every shop she buys in.

    So the lookup is **the link**, and never the alias:

    * the row the account claims - `Customer.user` - is hers;
    * and if the row is not claimed yet, the alias may name it, because
      a shop registers a person before she has an account and she claims
      the row later.

    **The old lookup was the alias alone**, and it worked only because
    the test forced the username to BE the alias. A real person - the
    one who chose her username, which is the whole point of the 10.1 -
    saw no links at all, and could never answer the shop's question.
    """
    from tienda.models import Customer

    cliente = Customer.objects.filter(user=user).first()
    if cliente is not None:
        return cliente

    return Customer.objects.filter(alias=user.username).first()
