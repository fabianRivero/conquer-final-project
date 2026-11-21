"""The person's account - Slice A of the account rewrite.

The person is the account. She creates it, she owns it, and her
credentials are hers: the shop neither issues them nor changes them.

**Two principals, two mechanisms, and they never meet.** The staff signs
in at `/login/` with the credentials the shop gave them; the person signs
in at `/api/v1/cuenta/login/` with her own. The two sessions are of
different kinds and neither reaches the other's routes - that is the
whole point of the change, and the last two tests are the ones that
carry it.

The person carries **one** client profile and **several** shop profiles.
The shop profiles are the businesses she owns; the client profile is her
in the world of credit. She may be both at once: a shopkeeper who buys
on credit at another shop.

Nothing here touches the credit book, the `Customer`, the staff login or
the credential of the client. This slice is **additive**: a person's
account, and nothing else.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tienda.models import PerfilCliente, PerfilTienda

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api():
    return APIClient()


# ---------------------------------------------------------------------------
# A.1 - The registration
# ---------------------------------------------------------------------------


def test_una_persona_se_registra(api, db):
    """A person creates her account.

    The account is hers: she chose the username and the password, and
    the row holds the DIGEST, never the text.
    """
    respuesta = api.post(
        reverse("api:cuenta_registro"),
        {"username": "ana", "password": "secreta123"},
        format="json",
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["username"] == "ana"

    usuario = User.objects.get(username="ana")
    assert usuario.check_password("secreta123")
    # And the text is not in the row.
    assert "secreta123" not in usuario.password


def test_el_registro_rechaza_un_usuario_repetido(api, db):
    """The username is unique: two people cannot be the same one.

    The refusal says the username is taken, and it does NOT say anything
    about the other person's account beyond that.
    """
    User.objects.create_user(username="ana", password="x")

    respuesta = api.post(
        reverse("api:cuenta_registro"),
        {"username": "ana", "password": "secreta123"},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "usuario_duplicado"
    assert User.objects.filter(username="ana").count() == 1


def test_el_registro_exige_una_contrasena_de_mas_de_cinco_caracteres(api, db):
    """A password of five characters or fewer is refused.

    The minimum is the owner's decision: more than five characters.
    """
    for corta in ("12345", "abc", ""):
        respuesta = api.post(
            reverse("api:cuenta_registro"),
            {"username": "ana", "password": corta},
            format="json",
        )
        assert respuesta.status_code == 422, corta
        assert respuesta.json()["codigo_error"] == "contrasena_corta"


def test_el_registro_no_acepta_un_usuario_vacio(api, db):
    """A username is required."""
    respuesta = api.post(
        reverse("api:cuenta_registro"),
        {"username": "", "password": "secreta123"},
        format="json",
    )

    assert respuesta.status_code == 422
    assert User.objects.count() == 0


# ---------------------------------------------------------------------------
# A.2 - The login
# ---------------------------------------------------------------------------


def test_una_persona_entra_con_su_usuario_y_contrasena(api, db):
    """She signs in with her own credentials, and gets a session."""
    User.objects.create_user(username="ana", password="secreta123")

    respuesta = api.post(
        reverse("api:cuenta_login"),
        {"username": "ana", "password": "secreta123"},
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["username"] == "ana"
    # The session is written.
    assert api.session.get("_auth_user_id")


def test_el_login_refusa_una_contrasena_incorrecta(api, db):
    """A wrong password is refused, and it says nothing about which part
    was wrong: a message that says "no such user" is an oracle."""
    User.objects.create_user(username="ana", password="secreta123")

    respuesta = api.post(
        reverse("api:cuenta_login"),
        {"username": "ana", "password": "incorrecta"},
        format="json",
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["codigo_error"] == "credenciales_invalidas"
    # And no session was written.
    assert api.session.get("_auth_user_id") is None


def test_el_login_refusa_un_usuario_que_no_existe(api, db):
    """The same answer for a user that does not exist."""
    respuesta = api.post(
        reverse("api:cuenta_login"),
        {"username": "nadie", "password": "secreta123"},
        format="json",
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["codigo_error"] == "credenciales_invalidas"


def test_el_logout_cierra_la_sesion(api, db):
    """The sign-out flushes the session."""
    User.objects.create_user(username="ana", password="secreta123")
    api.post(
        reverse("api:cuenta_login"),
        {"username": "ana", "password": "secreta123"},
        format="json",
    )

    respuesta = api.post(reverse("api:cuenta_logout"), {}, format="json")

    assert respuesta.status_code == 200
    assert api.session.get("_auth_user_id") is None


# ---------------------------------------------------------------------------
# A.3 - The profiles
# ---------------------------------------------------------------------------


def test_una_persona_crea_su_perfil_de_cliente(api, db):
    """The client profile: "I am a client in the world of credit".

    There is at most ONE per person - she is one client, wherever she
    buys on credit.
    """
    User.objects.create_user(username="ana", password="secreta123")
    api.force_authenticate(User.objects.get(username="ana"))

    respuesta = api.post(reverse("api:perfiles_cliente"), {}, format="json")

    assert respuesta.status_code == 201
    perfil = PerfilCliente.objects.get()
    assert perfil.user.username == "ana"


def test_una_persona_solo_tiene_un_perfil_de_cliente(api, db):
    """The client profile is ONE per person.

    The uniqueness is a constraint, not a convention: two rows would be
    two clients, and she is one.
    """
    usuario = User.objects.create_user(username="ana", password="secreta123")
    PerfilCliente.objects.create(user=usuario, creado_en=timezone.now())
    api.force_authenticate(usuario)

    respuesta = api.post(reverse("api:perfiles_cliente"), {}, format="json")

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "perfil_ya_existe"
    assert PerfilCliente.objects.count() == 1


def test_una_persona_crea_varios_perfiles_de_tienda(api, db):
    """The shop profiles: the businesses she owns.

    SEVERAL - a person may own more than one shop, and each one is a
    profile with its own name and its own data.
    """
    usuario = User.objects.create_user(username="ana", password="secreta123")
    api.force_authenticate(usuario)

    primera = api.post(
        reverse("api:perfiles_tienda"),
        {"nombre": "Tienda de Ana", "direccion": "Calle Mayor 1"},
        format="json",
    )
    segunda = api.post(
        reverse("api:perfiles_tienda"),
        {"nombre": "El Kiosco de Ana", "direccion": "Calle Mayor 2"},
        format="json",
    )

    assert primera.status_code == 201
    assert segunda.status_code == 201
    assert PerfilTienda.objects.count() == 2


def test_el_perfil_de_tienda_exige_su_nombre(api, db):
    """The shop profile carries its own data, and the name is required."""
    usuario = User.objects.create_user(username="ana", password="secreta123")
    api.force_authenticate(usuario)

    respuesta = api.post(
        reverse("api:perfiles_tienda"), {"nombre": ""}, format="json"
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "nombre_requerido"
    assert PerfilTienda.objects.count() == 0


def test_los_perfiles_de_una_persona_son_suyos(api, db):
    """The list carries HER profiles and nobody else's."""
    ana = User.objects.create_user(username="ana", password="secreta123")
    User.objects.create_user(username="bruno", password="secreta123")
    PerfilTienda.objects.create(
        user=ana, nombre="Tienda de Ana", direccion="", creado_en=timezone.now()
    )
    api.force_authenticate(ana)

    respuesta = api.get(reverse("api:perfiles"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo["tiendas"]) == 1
    assert cuerpo["tiendas"][0]["nombre"] == "Tienda de Ana"
    assert cuerpo["cliente"] is None


# ---------------------------------------------------------------------------
# A.4 - The separation: the two sessions never meet
# ---------------------------------------------------------------------------


def test_la_sesion_de_persona_no_alcanza_una_ruta_de_tienda(api, db):
    """The person's session does not reach a staff route.

    **This is the boundary.** Two mechanisms, two session kinds, and
    neither reaches the other's routes. The staff session carries the
    `shop_id`; the person's session carries none, and a staff route
    without a shop scope is refused.
    """
    usuario = User.objects.create_user(username="ana", password="secreta123")
    api.force_authenticate(usuario)

    respuesta = api.get(reverse("api:posicion"))

    assert respuesta.status_code == 403


def test_la_sesion_de_tienda_no_alcanza_una_ruta_de_cliente(api, db):
    """And the staff session does not reach a client's route.

    The companion: without it, "the person's session is refused" would
    pass on a route that refuses everybody.
    """
    usuario = User.objects.create_user(username="dueno", password="secreta123")
    api.force_authenticate(usuario)

    respuesta = api.get(reverse("api:cliente_estado"))

    assert respuesta.status_code == 403


def test_una_persona_sin_sesion_no_alcanza_una_ruta_de_persona(api, db):
    """A request with no session reaches no account route."""
    respuesta = api.get(reverse("api:perfiles"))

    assert respuesta.status_code == 403
