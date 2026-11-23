"""The person's account - the routes of design §9.1, the person side.

**The person owns her account.** She creates it, she chose the username
and the password, and she is the only one who changes them. The shop
neither issues them nor knows them.

**Two mechanisms, and they never meet.** The staff signs in at
`/login/` with the credentials the shop gave them; the person signs in
here, with her own. The two sessions are of different kinds:

* the STAFF session carries the `shop_id` - it is the scope of the shop;
* the PERSON session carries no shop, because a person is not in a shop.
  She has profiles, and the profiles are hers.

That is why the person session reaches no staff route: `current_shop`
reads the session's `shop_id`, and there is none. And the staff session
reaches no client's route: `EsCliente` refuses a request that carries a
staff session, even a valid one.

**The refusals say nothing about WHICH part was wrong.** "No such user"
is an oracle, and an oracle is a way to enumerate accounts.
"""

from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.models import User
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from tienda.api.exceptions import DomainValidationError
from tienda.models import PerfilCliente, PerfilTienda

#: The shortest password the owner accepted: **more than** five
#: characters. The rule lives here, next to the refusal that carries it.
CONTRASENA_MINIMA = 5


class SesionDePersona(BasePermission):
    """The request carries a PERSON's session.

    It is the person's own session - the one she opened with her
    username and her password - and it is not a staff session. A staff
    session names a shop; this one names a person, and the person is
    not in a shop.
    """

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        # A staff session is a session that names a shop. The person's
        # session does not, and the two never meet.
        return not request.session.get("shop_id")


class _ApiViewBase(APIView):
    """The base of the account's views.

    DRF's `APIView` accepts `put`, `patch` and `delete` by default, and
    an account route that would answer a `DELETE` if one were ever added
    is a route waiting for the accident. The base refuses them.
    """

    http_method_names = ["get", "post"]


class _RutaSinSesion(_ApiViewBase):
    """The base of the routes that AUTHENTICATE.

    They declare **no authentication class**, and they are **CSRF-exempt**
    - and both are the same decision.

    **Why no authentication class.** `SessionAuthentication` is what
    enforces the CSRF check, and it only runs when the session is what
    authenticated the request. A route whose whole job is to
    AUTHENTICATE has no session yet, so the check has nothing to
    protect.

    **Why CSRF-exempt.** The Django middleware checks every unsafe
    method, and it would refuse these routes before the view ever runs.
    That is correct for a **cookie**-based login - the staff's
    `login_view` carries `@csrf_protect` for exactly that reason, because
    a third-party page must not be able to sign a member of staff in.

    These routes are **not** cookie-based: the person sends her username
    and her password in the BODY, and the browser's cookies say nothing
    about who she is. A CSRF token would protect against a third-party
    page that makes the browser send a request **with her cookies** -
    and here there is nothing in the cookies to protect. The
    credentials in the body are the only thing that authenticates, and a
    third-party page cannot read them.

    The routes that act **with** a session - the profiles - use
    `SesionDePersona` and go through `SessionAuthentication`, so they
    carry the CSRF contract of every other mutation.
    """

    authentication_classes = []
    #: The route that AUTHENTICATES cannot demand an authenticated
    #: request: that is what it is for. The default permission of the API
    #: is `IsAuthenticated`, and this route is the one place where it
    #: cannot apply.
    permission_classes = []


@method_decorator(csrf_exempt, name="dispatch")
class CuentaRegistroView(_RutaSinSesion):
    """`POST /api/v1/cuenta/registro/` - the person creates her account.

    The account is hers: she chose the username and the password, and
    the row holds the **digest**, never the text.

    The username is unique, and the refusal says it is taken - which
    reveals nothing about the other person's account beyond that. It is
    a public name, like an email address, and it is not a secret: the
    secret is the password, and the password is hers alone.
    """

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""

        if not username:
            return Response(
                {"codigo_error": "usuario_requerido", "detail": "El usuario es obligatorio."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        if len(password) <= CONTRASENA_MINIMA:
            return Response(
                {
                    "codigo_error": "contrasena_corta",
                    "detail": "La contrasena debe tener mas de cinco caracteres.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            with transaction.atomic():
                usuario = User.objects.create_user(
                    username=username, password=password
                )
        except IntegrityError:
            # The username is taken. The refusal says WHICH it was and
            # nothing else: "that user exists" is an oracle.
            return Response(
                {
                    "codigo_error": "usuario_duplicado",
                    "detail": "Ese nombre de usuario ya esta en uso.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {"id": usuario.id, "username": usuario.username},
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class CuentaLoginView(_RutaSinSesion):
    """`POST /api/v1/cuenta/login/` - the person signs in.

    The refusal is **byte-identical** for an unknown user and for a
    wrong password: a message that says "no such user" is an oracle, and
    an oracle is a way to enumerate accounts.

    The session is written WITHOUT a `shop_id`: a person is not in a
    shop, and the absence is what keeps this session away from the
    staff routes.
    """

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""

        usuario = authenticate(request, username=username, password=password)

        if usuario is None:
            return Response(
                {
                    "codigo_error": "credenciales_invalidas",
                    "detail": "Usuario o contrasena incorrectos.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        django_login(request, usuario)
        # No `shop_id`: this session is a person's, not a shop's.
        request.session.pop("shop_id", None)

        return Response({"id": usuario.id, "username": usuario.username})


@method_decorator(csrf_exempt, name="dispatch")
class CuentaLogoutView(_RutaSinSesion):
    """`POST /api/v1/cuenta/logout/` - the person signs out."""

    def post(self, request):
        django_logout(request)
        return Response({"ok": True})


class PerfilesView(_ApiViewBase):
    """`GET /api/v1/perfiles/` - the person's own profiles.

    The client profile is **one** - she is one client, wherever she buys
    on credit - and the shop profiles are **several**, the businesses she
    owns.
    """

    permission_classes = [SesionDePersona]

    def get(self, request):
        cliente = PerfilCliente.objects.filter(user=request.user).first()

        tiendas = [
            {
                "id": perfil.id,
                "nombre": perfil.nombre,
                "direccion": perfil.direccion,
                "nif": perfil.nif,
            }
            for perfil in PerfilTienda.objects.filter(user=request.user).order_by("id")
        ]

        return Response(
            {
                "cliente": (
                    {"id": cliente.id} if cliente is not None else None
                ),
                "tiendas": tiendas,
            }
        )


class PerfilClienteView(_ApiViewBase):
    """`POST /api/v1/perfiles/cliente/` - the person creates her client
    profile.

    **One per person.** The uniqueness is a constraint, not a
    convention: two rows would be two clients, and she is one.
    """

    permission_classes = [SesionDePersona]

    def post(self, request):
        if PerfilCliente.objects.filter(user=request.user).exists():
            return Response(
                {
                    "codigo_error": "perfil_ya_existe",
                    "detail": "Ya tenes un perfil de cliente.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        perfil = PerfilCliente.objects.create(user=request.user)

        return Response(
            {"id": perfil.id}, status=status.HTTP_201_CREATED
        )


class ClienteReclamarView(_ApiViewBase):
    """`POST /api/v1/cuenta/reclamar/` - she claims the row the shop
    created for her.

    **The shop registers a person before she has an account.** She is a
    customer of the shop and of nobody else, and the row carries the
    ALIAS the shop calls her by. Then she registers herself, she chose
    her username, and the username is not the alias - so the row and the
    account have to be MEET.

    **The alias is what the shop typed, and she confirms it.** The row
    is not claimed because it looks like hers: it is claimed because she
    named the alias the shop gave her, and the row is a row of a shop's
    list of people that nobody has claimed yet.

    The body is `{alias}`. The refusal does not say whether the row
    does not exist or belongs to somebody else: the answer is the same
    either way, so nothing can be learned from it.
    """

    permission_classes = [SesionDePersona]
    http_method_names = ["post"]

    def post(self, request):
        from tienda.services import reclamar_cliente

        try:
            cliente = reclamar_cliente(request.user, request.data.get("alias"))
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {"id": cliente.id, "alias": cliente.alias},
            status=status.HTTP_201_CREATED,
        )


class PerfilTiendaView(_ApiViewBase):
    """`POST /api/v1/perfiles/tienda/` - the person creates a business.

    **Several**: a person may own more than one business, and each one
    carries its own name and its own data.
    """

    permission_classes = [SesionDePersona]

    def post(self, request):
        nombre = (request.data.get("nombre") or "").strip()
        if not nombre:
            return Response(
                {
                    "codigo_error": "nombre_requerido",
                    "detail": "El nombre del negocio es obligatorio.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        perfil = PerfilTienda.objects.create(
            user=request.user,
            nombre=nombre,
            direccion=(request.data.get("direccion") or "").strip(),
            nif=(request.data.get("nif") or "").strip(),
        )

        return Response(
            {
                "id": perfil.id,
                "nombre": perfil.nombre,
                "direccion": perfil.direccion,
                "nif": perfil.nif,
            },
            status=status.HTTP_201_CREATED,
        )
