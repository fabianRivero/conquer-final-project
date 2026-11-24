"""The Slice 10.5, T4: **the counter identifies the person**.

**The attendant asks her for her username and types it.** The system
finds her. The person is identified with the account she owns, not with
a slip of paper the shop keeps.

**The password is typed by HER, and the owner does not see it.** That
is a **supposition of the process, not a technical guarantee**: the
attendant is behind the counter and she is in front of it. What the
code guarantees is the other half: **the counter's search never asks
for a password and never authenticates anybody.**

**The search is by username ALONE.** The username is her public name,
like an email address. A search that asked for the password would put
a secret the owner does not have into a request the owner can read.

**The scope is the shop.** The owner of one shop does not look for the
customers of another, and a person may be a client of several shops -
each of them asks her separately.

**The counter finds her; it does not answer for her.** The answer to
the fiado is hers, from her own account, and the counter has no way to
pretend she gave it.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from tienda.api.exceptions import DomainValidationError
from tienda.api.permissions import SoloPersonal


class MostradorBuscarView(APIView):
    """`GET /api/v1/mostrador/buscar/?username=...` - **the counter finds
    the person**.

    **It is a SEARCH, and not an authentication.** It finds a person and
    it does not sign her in: the answer to the fiado is hers, from her
    own account, and the counter has no way to answer for her - so it
    has no way to pretend she did.

    **The username ALONE.** The password is typed by her, on her own
    device, and it never travels to the counter. A body that carries
    one is REFUSED, not ignored: a mistake that is silently ignored is
    a mistake that happens again.

    **The scope is the shop.** The owner of one shop does not look for
    the customers of another one.

    **Only a person with an ACCOUNT is found.** The counter identifies
    the person by the account she owns; a customer row without one is
    not identified that way - the shop still has her in its list, by her
    alias.
    """

    permission_classes = [SoloPersonal]
    http_method_names = ["get", "post"]

    def get(self, request):
        from tienda.api.permissions import current_shop
        from tienda.services import buscar_en_el_mostrador

        return self._buscar(request, request.query_params.get("username"), current_shop)

    def post(self, request):
        from tienda.api.permissions import current_shop
        from tienda.services import buscar_en_el_mostrador

        try:
            # The password is NOT one of the fields a body may carry.
            # The counter's search asks for the username alone.
            from tienda import services

            services.exigir_campos_no_admitidos(
                request.data, {"username"}
            )
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return self._buscar(request, request.data.get("username"), current_shop)

    def _buscar(self, request, username, current_shop):
        from tienda.services import buscar_en_el_mostrador

        shop_id = current_shop(request)
        if shop_id is None:
            return Response(
                {
                    "codigo_error": "permiso_insuficiente",
                    "detail": "No tienes permiso para esta operacion.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(buscar_en_el_mostrador(shop_id, username))
