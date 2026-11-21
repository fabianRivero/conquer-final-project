"""The login - the piece the plan does not have.

The design's route table says the staff surfaces answer "302 to login",
and the staff scope is "the `shop_id` written at login" - but no task of
the plan creates the route that writes it. The staff surface cannot work
without it, so it lives here, with the shell it enables.

Four properties, and they are the ones the design already assumes:

**It writes exactly ONE shop into the session.** A `User` may belong to
several `Shop` rows through `Shop.usuarios`, but a session names exactly
one, and `current_shop(request)` reads that one and nothing else. The
session's `shop_id` IS the staff scope.

**It authenticates the user with Django's own machinery.**
`django.contrib.auth.authenticate` checks the password against the
hashed one; the seed's accounts go through `set_password` like any
other.

**It needs the CSRF token.** It is a session-writing POST, and the same
origin contract that protects the API's mutations protects it: a
third-party page must not be able to sign a member of staff in and then
act as them.

**It refuses a user with no shop.** A user who belongs to no shop has
no staff scope, and a session with no shop names nothing: every staff
route answers 403. The login does not create a session for such a user,
because a session that carries no scope would look like a login and
behave like a refusal.
"""

from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect


def _tienda_del_usuario(usuario):
    """The shop the session will name, or `None`.

    A `User` may belong to several shops, and a session names exactly
    one. The first of them is chosen - the shop's own order, which is
    the one the owner registered the staff member in - and the session
    carries that one id.

    The shop is looked up through the MEMBERSHIP, NOT through a field
    of the user: the role lives in the relation, and the relation names
    the business, and the business names its shop.
    """
    if usuario is None:
        return None
    return (
        usuario.miembros_de_tienda.order_by("perfil_tienda__id")
        .values_list("perfil_tienda__shop_id", flat=True)
        .first()
    )


@csrf_protect
def login_view(
    request: HttpRequest, template_name: str = "tienda/login.html"
) -> HttpResponse:
    """`GET`/`POST /login/` - the staff sign-in.

    On a successful sign-in it writes `session["shop_id"]` and redirects
    to the owner's board. On a refusal it re-renders the form and writes
    NO session.
    """
    if request.method == "POST":
        usuario = authenticate(
            request,
            username=request.POST.get("username", ""),
            password=request.POST.get("password", ""),
        )
        tienda = _tienda_del_usuario(usuario)

        if usuario is None or tienda is None:
            # The refusal says nothing about WHICH part was wrong: a
            # message that says "no such user" is an oracle.
            return render(
                request,
                template_name,
                {"error": "Usuario o contrasena incorrectos."},
                status=401,
            )

        django_login(request, usuario)
        request.session["shop_id"] = tienda
        return redirect(reverse("app_posicion"))

    return render(request, template_name)


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    """`POST /logout/` - the staff sign-out.

    The session is flushed, so the shop scope goes with it.
    """
    django_logout(request)
    return redirect(reverse("login"))
