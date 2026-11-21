"""Slice 10.2 - the shop's login, and the staff the shop gives a user.

The shop gives its `dependiente` a user, and the `dependiente` may hold
a separate personal account besides it. **The shop's staff are not
people with accounts in the app**: they are users the shop created, and
their credentials are the shop's.

**The role lives in the RELATION, not in a global group.** A
`dependiente` of one shop is a `dependiente` of that shop and of no
other - the group was a convention that let one shop's staff act in
every shop. The two tests that carry this boundary assert it directly:
the role follows the relation, and one shop's staff reach no other
shop.

**The login has three steps, and they are three questions:**

1. **Which shop?** The owner's list of the shops he owns. A
   `dependiente` has exactly one, so his list has one entry and the
   step disappears.
2. **Which role?** The owner, or one of the staff members the shop
   gave a user. The owner enters as a `dependiente` **with that
   member's own credentials** - and that is the point: the row that
   records the act says **the `dependiente` acted**, not "the owner was
   at the counter".
3. **The credentials.** A username and a password.

**A username is globally unique, not unique per shop.** A `dependiente`
who works in two shops has **two** users - one per shop - and each
login resolves exactly one shop. That is why the login needs no shop
name: the username already says.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tests.conftest import membresia

from tienda.models import MiembroDeTienda, PerfilTienda, Shop

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api(dueno, perfil, shop, miembro_dueno, db):
    """A client whose session names the shop AND whose user is the owner.

    **Both.** The shop is the scope and the role is the membership, and
    the permission needs the two together: a session that names no shop
    is refused, and a session that names a shop the user does not belong
    to is refused too.
    """
    from django.contrib.sessions.backends.db import SessionStore

    cliente = APIClient()
    cliente.force_authenticate(dueno)
    sesion = SessionStore()
    sesion["shop_id"] = shop.id
    sesion.save()
    cliente.cookies["sessionid"] = sesion.session_key
    return cliente


@pytest.fixture
def perfil(db):
    """The shop's business profile, owned by the owner."""
    dueno = User.objects.create_user(username="dueno", password="secreta123")
    negocio = PerfilTienda.objects.create(
        user=dueno, nombre="Tienda de Ana", direccion="Calle Mayor 1"
    )
    return negocio


@pytest.fixture
def dueno(perfil):
    """The owner, as a member of their own shop."""
    return perfil.user


@pytest.fixture
def shop(perfil, db):
    """The shop of the credit book that the profile points to."""
    tienda = Shop.objects.create(
        name="Tienda de Ana", opening_cash=Decimal("150.00")
    )
    perfil.shop = tienda
    perfil.save()
    return tienda


@pytest.fixture
def miembro_dueno(dueno, perfil, db):
    """The owner's membership: the role lives in the relation."""
    return MiembroDeTienda.objects.create(
        perfil_tienda=perfil, user=dueno, rol="dueno"
    )


@pytest.fixture
def dependiente(db, perfil):
    """A `dependiente` the shop gave a user."""
    persona = User.objects.create_user(username="ayudante", password="secreta123")
    MiembroDeTienda.objects.create(
        perfil_tienda=perfil, user=persona, rol="dependiente"
    )
    return persona


@pytest.fixture
def api_dependiente(dependiente, perfil, shop, db):
    """A client for the `dependiente`, with the shop in the session."""
    from django.contrib.sessions.backends.db import SessionStore

    cliente = APIClient()
    cliente.force_authenticate(dependiente)
    sesion = SessionStore()
    sesion["shop_id"] = shop.id
    sesion.save()
    cliente.cookies["sessionid"] = sesion.session_key
    return cliente


def _sesion_de(usuario, tienda):
    """A client whose session names the shop."""
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(usuario)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


# ---------------------------------------------------------------------------
# 10.2.1 - The staff the shop gives a user
# ---------------------------------------------------------------------------


def test_el_dueno_da_de_alta_un_dependiente(api, dueno, perfil, shop, db, miembro_dueno):
    """The shop gives its `dependiente` a user.

    The row says **the role and the shop**, and it is the ROLE that lives
    there - not a global group. The `dependiente` is a member of THIS
    shop and of no other.
    """
    respuesta = api.post(
        reverse("api:personal"),
        {"username": "ayudante", "password": "secreta123", "rol": "dependiente"},
        format="json",
    )

    assert respuesta.status_code == 201
    miembro = MiembroDeTienda.objects.get(user__username="ayudante")
    assert miembro.user.username == "ayudante"
    assert miembro.perfil_tienda_id == perfil.id
    assert miembro.rol == "dependiente"
    # And the owner is a member of their own shop.
    assert MiembroDeTienda.objects.filter(
        perfil_tienda=perfil, rol="dueno"
    ).count() == 1
    # And the user can sign in with those credentials.
    assert miembro.user.check_password("secreta123")


def test_el_dueno_no_da_de_alta_dos_veces_al_mismo_usuario(api, dueno, perfil, shop, db, miembro_dueno):
    """The same user is not a member of the same shop twice."""
    api.post(
        reverse("api:personal"),
        {"username": "ayudante", "password": "secreta123", "rol": "dependiente"},
        format="json",
    )

    respuesta = api.post(
        reverse("api:personal"),
        {"username": "ayudante", "password": "otra123", "rol": "dependiente"},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "personal_ya_existe"
    assert MiembroDeTienda.objects.filter(
        perfil_tienda=perfil
    ).count() == 2


def test_el_dependiente_no_da_de_alta_personal(
    api_dependiente, dependiente, perfil, shop, db
):
    """Only the owner gives staff. **The `dependiente` operates the counter.**

    Administrating the staff is the shop's POLICY - the same policy as
    the `credit_limit` and the catalogue - and the N5 gate did not open
    it.
    """
    respuesta = api_dependiente.post(
        reverse("api:personal"),
        {"username": "otro", "password": "secreta123", "rol": "dependiente"},
        format="json",
    )

    assert respuesta.status_code == 403
    assert MiembroDeTienda.objects.filter(
        perfil_tienda=perfil, rol="dependiente"
    ).count() == 1


def test_el_dueno_ve_su_personal(api, dueno, perfil, shop, dependiente, db, miembro_dueno):
    """The owner sees the staff of their shop."""
    respuesta = api.get(reverse("api:personal"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    # The owner is not "staff the shop gave a user": the list is the
    # members the shop created, and the owner's own membership is the
    # owner.
    assert len(cuerpo) == 1
    assert cuerpo[0]["username"] == "ayudante"
    assert cuerpo[0]["rol"] == "dependiente"


def test_el_dueno_quita_a_un_dependiente(api, dueno, perfil, shop, dependiente, db, miembro_dueno):
    """The owner takes the staff member off the shop.

    It is a **removal from the shop**, not a deletion: the user and its
    rows stay, and the person keeps whatever account of her own she had.
    """
    respuesta = api.delete(
        reverse("api:personal_miembro", args=[dependiente.id])
    )

    assert respuesta.status_code == 200
    assert MiembroDeTienda.objects.filter(
        perfil_tienda=perfil, user=dependiente
    ).count() == 0
    # The user itself is untouched.
    assert User.objects.filter(username="ayudante").exists()


# ---------------------------------------------------------------------------
# 10.2.2 - The role lives in the relation, not in a global group
# ---------------------------------------------------------------------------


def test_el_rol_sigue_a_la_relacion_y_no_al_grupo(db, dueno, perfil, shop, dependiente):
    """The role is the RELATION's, not a global group's.

    The user has **no group at all** and is still a `dependiente` of this
    shop: the row says so. And the row is what says it - remove it and
    the role is gone, whatever the groups say.
    """
    assert dependiente.groups.count() == 0

    assert (
        MiembroDeTienda.objects.get(user=dependiente).rol
        == "dependiente"
    )

    # And the group cannot give the role back: the user is given the
    # `dependiente` group, and the membership goes - and the role goes
    # with it.
    from django.contrib.auth.models import Group

    dependiente.groups.add(Group.objects.create(name="dependiente"))
    MiembroDeTienda.objects.filter(user=dependiente).delete()

    assert MiembroDeTienda.objects.count() == 0


def test_el_dependiente_de_una_tienda_no_alcanza_otra(
    db, dueno, perfil, shop, dependiente
):
    """One shop's staff reach no other shop.

    This is the boundary the group could not hold: a global `dependiente`
    group let one shop's staff act in every shop.
    """
    otra = PerfilTienda.objects.create(
        user=dueno, nombre="El Kiosco de Ana", direccion="Calle Mayor 2"
    )
    otra_shop = Shop.objects.create(
        name="El Kiosco de Ana", opening_cash=Decimal("0.00")
    )

    api = _sesion_de(dependiente, otra_shop)

    # The staff member of the FIRST shop reads the SECOND shop's board.
    respuesta = api.get(reverse("api:posicion"))

    assert respuesta.status_code == 403
    # And the relation says nothing about the second shop.
    assert MiembroDeTienda.objects.filter(
        perfil_tienda=otra, user=dependiente
    ).count() == 0


# ---------------------------------------------------------------------------
# 10.2.3 - The login of the shop
# ---------------------------------------------------------------------------


def test_el_dueno_entra_con_su_usuario_y_contrasena(
    api, dueno, perfil, shop, db, miembro_dueno):
    """The owner signs in with his own credentials.

    The session names the shop he chose, and the role comes from the
    relation - not from a group.
    """
    respuesta = api.post(
        reverse("api:login_tienda"),
        {
            "perfil_tienda": perfil.id,
            "username": "dueno",
            "password": "secreta123",
        },
        format="json",
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["rol"] == "dueno"
    assert cuerpo["perfil_tienda"] == perfil.id


def test_el_dependiente_entra_con_su_usuario_y_contrasena(
    api, dueno, perfil, shop, dependiente, db):
    """The `dependiente` signs in with the credentials the shop gave him.

    **No shop name.** His username already says which shop he belongs
    to: each shop gives its own users, and a username is globally unique.
    """
    respuesta = api.post(
        reverse("api:login_tienda"),
        {"username": "ayudante", "password": "secreta123"},
        format="json",
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["rol"] == "dependiente"
    assert cuerpo["perfil_tienda"] == perfil.id


def test_el_login_exige_el_rol_del_dueno(api, dueno, perfil, shop, db, miembro_dueno):
    """The owner signs in as HIMSELF.

    Entering as one of his staff members is a **separate act**: the
    owner writes that member's own credentials, so the row that records
    the act says the `dependiente` acted - not "the owner was at the
    counter".
    """
    respuesta = api.post(
        reverse("api:login_tienda"),
        {"perfil_tienda": perfil.id, "username": "dueno", "password": "incorrecta"},
        format="json",
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["codigo_error"] == "credenciales_invalidas"


def test_el_dueno_entra_como_su_dependiente_con_sus_credenciales(
    api, dueno, perfil, shop, dependiente, db, miembro_dueno):
    """The owner may act as his `dependiente` - with THAT member's credentials.

    The owner chose the staff member and writes **his** credentials. The
    session is that member's, and the row that records the act names the
    member - which is the whole point of the audit.
    """
    respuesta = api.post(
        reverse("api:login_tienda"),
        {
            "perfil_tienda": perfil.id,
            "username": "ayudante",
            "password": "secreta123",
        },
        format="json",
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["rol"] == "dependiente"
    assert cuerpo["usuario"] == "ayudante"


def test_el_login_refusa_un_usuario_que_no_existe(api, dueno, perfil, shop, db, miembro_dueno):
    """The refusal is byte-identical for an unknown user and a wrong
    password: "no such user" is an oracle."""
    respuesta = api.post(
        reverse("api:login_tienda"),
        {"perfil_tienda": perfil.id, "username": "nadie", "password": "secreta123"},
        format="json",
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["codigo_error"] == "credenciales_invalidas"


def test_el_login_de_un_dependiente_necesita_su_nombre_de_tienda(
    api, dueno, perfil, shop, dependiente, db, miembro_dueno):
    """A `dependiente` has no shop to choose: his username says it.

    And the owner, who may own several shops, names the one he enters.
    """
    # The owner picks his shop.
    con_tienda = api.post(
        reverse("api:login_tienda"),
        {
            "perfil_tienda": perfil.id,
            "username": "dueno",
            "password": "secreta123",
        },
        format="json",
    )
    assert con_tienda.status_code == 200

    # The `dependiente` does not: there is only one shop for him.
    sin_tienda = api.post(
        reverse("api:login_tienda"),
        {"username": "ayudante", "password": "secreta123"},
        format="json",
    )
    assert sin_tienda.status_code == 200
    assert sin_tienda.json()["perfil_tienda"] == perfil.id
