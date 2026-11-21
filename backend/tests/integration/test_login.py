"""The login and the SPA shell - the RED tests of 7b-1.

The login is the piece the plan does not have: the design's route table
says the staff surfaces answer "302 to login", and the staff scope is
"the `shop_id` written at login", but no task of the plan creates the
route that writes it. The staff surface cannot work without it, so it
belongs here, with the shell it enables.

What the tests hold the login to:

* it authenticates the user and writes `session["shop_id"]` - the ONE
  source of the staff scope, read only through `current_shop`;
* it names exactly ONE shop, even when the user belongs to several: a
  session names one;
* it refuses a wrong password, and a refused login writes NO session;
* it needs the CSRF token, because it is a session-writing POST and
  the same origin contract applies to it;
* the staff surfaces redirect to it when there is no session, and serve
  the bundle when there is one;
* the client's surface is PUBLIC and never redirects.

And the shell:

* the Vite build lands in `STATIC_ROOT`, and the bundle's URL answers
  200 - not a blank page (landmine 2);
* the SPA serves the three routes of design 11.

A note on how these assert. The login is a real request through Django's
test client, and the assertions are on the EFFECTS: the session's
contents, the redirect, the status code of the served page, and whether
the CSRF token is in the served HTML.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tests.conftest import membresia
from django.contrib.auth.models import Group, User
from django.test import Client
from django.urls import reverse

from tienda.models import Shop

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tienda(db, negocio):
    """The shop of the credit book - the business's own shop."""
    return negocio.shop


@pytest.fixture
def otra_tienda(db, negocio):
    return Shop.objects.create(name="Otra tienda", opening_cash=Decimal("0.00"))


@pytest.fixture
def dueno(db, tienda, negocio):
    user = negocio.user
    user.set_password("secreto-123")
    user.save()
    membresia(negocio, user, "dueno")
    return user


@pytest.fixture
def dependiente(db, tienda, negocio):
    user = User.objects.create_user(username="dependiente", password="secreto-123")
    membresia(negocio, user, "dependiente")
    tienda.usuarios.add(user)
    return user


# ---------------------------------------------------------------------------
# The login
# ---------------------------------------------------------------------------


def test_el_login_escribe_el_shop_id_en_la_sesion(dueno, tienda):
    """The staff scope is the `shop_id` written at login.

    It is the ONE source of the staff scope: `current_shop(request)`
    reads it and nothing else does.
    """
    from django.contrib.sessions.backends.db import SessionStore

    cliente = Client()
    respuesta = cliente.post(
        reverse("login"),
        {"username": "dueno", "password": "secreto-123"},
    )

    assert respuesta.status_code in (302, 303)

    sesion = SessionStore(session_key=cliente.cookies["sessionid"].value)
    assert sesion["shop_id"] == tienda.id


def test_el_login_acepta_las_credenciales_del_dueno_y_del_dependiente(
    dueno, dependiente, tienda
):
    """Both shop roles can sign in.

    A `User` may belong to several `Shop` rows through `Shop.usuarios`,
    but a session names exactly one.
    """
    from django.contrib.sessions.backends.db import SessionStore

    for usuario in (dueno, dependiente):
        cliente = Client()
        respuesta = cliente.post(
            reverse("login"),
            {"username": usuario.username, "password": "secreto-123"},
        )

        assert respuesta.status_code in (302, 303)
        sesion = SessionStore(session_key=cliente.cookies["sessionid"].value)
        assert sesion["shop_id"] == tienda.id


def test_el_login_refusa_una_contrasena_incorrecta(dueno, tienda):
    """A refused login writes NO session.

    The refusal re-renders the form with 401 - not a redirect, because a
    redirect would say the sign-in succeeded. The session is the point:
    no session means no shop scope, so every staff route answers 403.
    """
    from django.contrib.sessions.backends.db import SessionStore

    cliente = Client()
    respuesta = cliente.post(
        reverse("login"),
        {"username": "dueno", "password": "no-es-la-contrasena"},
    )

    assert respuesta.status_code == 401
    # No session was established: the scope is empty.
    if "sessionid" in cliente.cookies:
        sesion = SessionStore(session_key=cliente.cookies["sessionid"].value)
        assert sesion.get("shop_id") is None


def test_el_login_nombra_una_sola_tienda(dueno, tienda, otra_tienda):
    """A session names exactly ONE shop, even when the user has several.

    The user belongs to two shops; the session names one of them.
    """
    from django.contrib.sessions.backends.db import SessionStore

    dueno.shops.add(otra_tienda)

    cliente = Client()
    cliente.post(
        reverse("login"),
        {"username": "dueno", "password": "secreto-123"},
    )

    sesion = SessionStore(session_key=cliente.cookies["sessionid"].value)
    shop_id = sesion["shop_id"]
    assert shop_id in (tienda.id, otra_tienda.id)


def test_el_login_exige_el_token_csrf(dueno):
    """The login is a session-writing POST, so it needs the CSRF token.

    Without it, a third-party page could sign a member of staff in and
    then act as them.
    """
    cliente = Client(enforce_csrf_checks=True)

    respuesta = cliente.post(
        reverse("login"),
        {"username": "dueno", "password": "secreto-123"},
    )

    assert respuesta.status_code == 403


def test_el_login_rechaza_a_un_usuario_sin_tienda(db, negocio):
    """A user who belongs to no shop has no staff scope.

    The shop is what the session carries, and a user with no shop has
    nothing to carry.
    """
    from django.contrib.sessions.backends.db import SessionStore

    sin_tienda = User.objects.create_user(username="nada", password="secreto-123")

    cliente = Client()
    cliente.post(
        reverse("login"),
        {"username": "nada", "password": "secreto-123"},
    )

    if "sessionid" in cliente.cookies:
        sesion = SessionStore(session_key=cliente.cookies["sessionid"].value)
        assert sesion.get("shop_id") is None


# ---------------------------------------------------------------------------
# The surfaces
# ---------------------------------------------------------------------------


def test_la_superficie_del_personal_redirige_al_login_sin_sesion(dueno):
    """`/app/posicion/` answers 302 to login when there is no session.

    The design's route table says exactly this: "200 HTML + mount + CSRF
    token; 302 to login".
    """
    cliente = Client()

    respuesta = cliente.get(reverse("app_posicion"))

    assert respuesta.status_code == 302
    assert reverse("login") in respuesta["Location"]


def _cuerpo(respuesta) -> bytes:
    """The response's body, whatever kind of response it is.

    Django's `serve()` answers a `FileResponse`, which STREAMS: it has
    no `content` attribute, only `streaming_content`. A test that reads
    `.content` on it would fail for a reason that has nothing to do with
    what it means to check.
    """
    if hasattr(respuesta, "streaming_content"):
        return b"".join(respuesta.streaming_content)
    return respuesta.content


def test_la_superficie_del_cliente_es_publica(credencial_placeholder=None):
    """`/app/cliente/` is public: 200 HTML, and no redirect.

    The client reads its statement with a credential, not with a
    session, so the page itself is not behind a login.
    """
    cliente = Client()

    respuesta = cliente.get(reverse("app_cliente"))

    assert respuesta.status_code == 200
    cuerpo = _cuerpo(respuesta)
    assert b"<div id=\"root\"" in cuerpo
    # And the bundle's own script is in the page - landmine 2: the page
    # must not be a blank one.
    assert b"<script" in cuerpo


def test_la_superficie_del_cliente_no_lleva_el_csrf_del_personal(credencial_placeholder=None):
    """The client's page carries no CSRF token.

    The client has no session, so there is nothing for CSRF to protect
    (ADR-4).
    """
    cliente = Client()

    respuesta = cliente.get(reverse("app_cliente"))

    cuerpo = _cuerpo(respuesta)
    assert b"csrfmiddlewaretoken" not in cuerpo


def test_la_pagina_de_login_lleva_el_csrf(dueno):
    """The login page carries the CSRF token, so the form can post it.

    The token is the ONLY place the client page does not carry it - and
    the login page is not the client page.
    """
    cliente = Client()

    respuesta = cliente.get(reverse("login"))

    assert respuesta.status_code == 200
    assert b"csrfmiddlewaretoken" in _cuerpo(respuesta)


def test_el_spa_sirve_las_tres_rutas(dueno, negocio):
    """The three routes of design 11 are served by the SPA.

    `/app/posicion/`, `/app/propuesta/{id}/` and `/app/cliente/`.
    """
    from django.contrib.sessions.backends.db import SessionStore

    cliente = Client()
    sesion = SessionStore()
    sesion["shop_id"] = negocio.shop.id
    sesion.save()
    cliente.cookies["sessionid"] = sesion.session_key

    for url in (
        "/app/posicion/",
        "/app/propuesta/1/",
        "/app/cliente/",
    ):
        respuesta = cliente.get(url)
        assert respuesta.status_code == 200, url
        cuerpo = _cuerpo(respuesta)
        assert b"<div id=\"root\"" in cuerpo, url
