"""The shop's login, and the staff the shop gives a user.

**The login has three steps, and they are three questions:**

1. **Which shop?** The owner's list of the shops he owns. A
   `dependiente` has exactly one, so his list has one entry and the step
   disappears.
2. **Which role?** The owner, or one of the staff members the shop gave
   a user. The owner may act as a `dependiente` - and then he writes
   **that member's own credentials**, so the row that records the act
   says **the member acted** and not "the owner was at the counter".
3. **The credentials.** A username and a password.

**A username is globally unique.** A `dependiente` who works in two
shops has **two** users - one per shop - because each shop gives its
own. That is what makes the login unambiguous: the username already says
which shop he belongs to, and the login asks for no shop name.

**The refusal is byte-identical** for an unknown user and for a wrong
password: *"no such user" is an oracle*, and an oracle is a way to
enumerate accounts.

**The role is the MEMBERSHIP's.** The `MiembroDeTienda` names the shop,
and the role check filters by both - so a `dependiente` of one shop
holds no role in another.
"""

from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth import login as django_login
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from tienda.api.exceptions import DomainValidationError
from tienda.models import MiembroDeTienda, PerfilTienda


class _RutaSinSesion(APIView):
    """The base of the routes that AUTHENTICATE.

    They declare **no authentication class** and **no permission**, and
    that is the same decision twice over: `SessionAuthentication` is what
    enforces the CSRF check and it only runs when the session is what
    authenticated the request, and a route whose whole job is to
    AUTHENTICATE has no session yet and cannot demand one.

    They are **CSRF-exempt** because their authority is the BODY: the
    username and the password travel in the request, and a cookie says
    nothing about who the person is.
    """

    authentication_classes = []
    permission_classes = []
    http_method_names = ["get", "post"]


class _ApiViewBase(APIView):
    """The base of the routes that act WITH a session."""

    http_method_names = ["get", "post"]


class _ApiViewConBorrado(APIView):
    """The base of the routes that may also remove a row.

    **Only the membership is removed.** The `DELETE` takes the staff
    member OFF the shop - the user and every row the member wrote in the
    book stay exactly where they are. It is a removal from the shop, not
    a deletion of a person.
    """

    http_method_names = ["get", "post", "delete"]


class EsDuenoDelNegocio(BasePermission):
    """The acting user is the OWNER of the session's business.

    **Only the owner gives staff.** Administrating the staff is the
    shop's POLICY - the same policy as the `credit_limit` and the
    catalogue - and the N5 gate did not open it.
    """

    def has_permission(self, request, view) -> bool:
        from tienda.api.permissions import current_shop, es_dueno

        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        return es_dueno(user, current_shop(request))

    def has_object_permission(self, request, view, obj) -> bool:
        return True


class LoginTiendaView(_RutaSinSesion):
    """`POST /api/v1/tienda/login/` - the shop's sign-in.

    The body carries the credentials and, for the owner, the business.
    The **username alone resolves the shop** for a `dependiente`, because
    each shop gives its own users and the username is globally unique.

    The session that comes out carries the `shop_id` - the staff scope -
    and the role comes from the membership, never from a group.
    """

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        perfil_id = request.data.get("perfil_tienda")

        usuario = authenticate(request, username=username, password=password)
        if usuario is None:
            return Response(
                {
                    "codigo_error": "credenciales_invalidas",
                    "detail": "Usuario o contrasena incorrectos.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # The shop: the one the owner named, or the one the username
        # belongs to.
        #
        # **The profile is the SHOP's, and not the owner's.** The owner
        # may enter as one of his staff members - and that member does
        # not own the profile. So the profile is resolved by the
        # MEMBERSHIP of the acting user, and the membership names the
        # profile.
        membresias = list(
            MiembroDeTienda.objects.filter(user=usuario).select_related(
                "perfil_tienda"
            )
        )
        if perfil_id is not None:
            perfil = next(
                (
                    m.perfil_tienda
                    for m in membresias
                    if m.perfil_tienda_id == perfil_id
                ),
                None,
            )
        elif len(membresias) == 1:
            perfil = membresias[0].perfil_tienda
        else:
            # No membership, or more than one: the username alone does
            # not resolve the shop.
            perfil = None

        if perfil is None or perfil.shop_id is None:
            return Response(
                {
                    "codigo_error": "credenciales_invalidas",
                    "detail": "Usuario o contrasena incorrectos.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        django_login(request, usuario)
        request.session["shop_id"] = perfil.shop_id
        request.session.pop("perfil_tienda_id", None)

        return Response(
            {
                "usuario": usuario.username,
                "rol": MiembroDeTienda.objects.filter(
                    user=usuario, perfil_tienda=perfil
                ).values_list("rol", flat=True).first(),
                "perfil_tienda": perfil.id,
                "shop": perfil.shop_id,
            }
        )


class PersonalView(_ApiViewBase):
    """`GET` and `POST /api/v1/tienda/personal/` - the shop's staff.

    `POST` gives a staff member a user: the owner creates the `User` and
    the membership that says the role and the shop. `GET` lists them.
    """

    permission_classes = [EsDuenoDelNegocio]

    def _perfil(self, request):
        from tienda.api.permissions import current_shop

        shop_id = current_shop(request)
        if shop_id is None:
            return None
        return PerfilTienda.objects.filter(shop_id=shop_id).first()

    def get(self, request):
        perfil = self._perfil(request)
        if perfil is None:
            return Response([])
        return Response(
            [
                {
                    "id": miembro.id,
                    "username": miembro.user.username,
                    "rol": miembro.rol,
                    "creado_en": miembro.creado_en,
                }
                for miembro in MiembroDeTienda.objects.filter(
                    perfil_tienda=perfil, rol="dependiente"
                ).select_related("user").order_by("id")
            ]
        )

    def post(self, request):
        perfil = self._perfil(request)
        if perfil is None:
            return Response(status=status.HTTP_403_FORBIDDEN)

        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        rol = request.data.get("rol") or "dependiente"

        if not username:
            return Response(
                {
                    "codigo_error": "usuario_requerido",
                    "detail": "El nombre de usuario es obligatorio.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if len(password) <= 5:
            return Response(
                {
                    "codigo_error": "contrasena_corta",
                    "detail": "La contrasena debe tener mas de cinco caracteres.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if rol not in MiembroDeTienda.MIEMBRO_ROLES:
            return Response(
                {
                    "codigo_error": "rol_desconocido",
                    "detail": "El rol no es valido.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        if MiembroDeTienda.objects.filter(
            perfil_tienda=perfil, user__username=username
        ).exists():
            return Response(
                {
                    "codigo_error": "personal_ya_existe",
                    "detail": "Ese usuario ya esta en el personal de la tienda.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            with transaction.atomic():
                usuario, _ = User.objects.get_or_create(username=username)
                usuario.set_password(password)
                usuario.save()
                miembro = MiembroDeTienda.objects.create(
                    perfil_tienda=perfil, user=usuario, rol=rol
                )
        except IntegrityError:
            return Response(
                {
                    "codigo_error": "personal_ya_existe",
                    "detail": "Ese usuario ya esta en el personal de la tienda.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {
                "id": miembro.id,
                "username": usuario.username,
                "rol": miembro.rol,
            },
            status=status.HTTP_201_CREATED,
        )

class PersonalMiembroView(_ApiViewConBorrado):
    """`DELETE /api/v1/tienda/personal/{user_id}/` - the owner takes a
    staff member off the shop.

    It is a **removal from the shop**, not a deletion: the user and its
    rows stay, and the person keeps whatever account of her own she had.
    """

    permission_classes = [EsDuenoDelNegocio]

    def delete(self, request, user_id):
        from tienda.api.permissions import current_shop

        shop_id = current_shop(request)
        if shop_id is None:
            return Response(status=status.HTTP_403_FORBIDDEN)

        perfil = PerfilTienda.objects.filter(shop_id=shop_id).first()
        if perfil is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        miembro = MiembroDeTienda.objects.filter(
            perfil_tienda=perfil, user_id=user_id
        ).first()
        if miembro is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        miembro.delete()
        return Response({"ok": True})
