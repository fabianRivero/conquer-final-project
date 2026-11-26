"""The leak surface and the scope matrix — tasks 4.1, 4.2 and 4.6 to 4.12.

The credential is a bearer secret. These tests are the surface of design
§5.2 walked end to end: the staff payloads, the client payloads, the logs,
the URLs, the error bodies, and the throttle.

**The walk is over the whole tree.** It visits every key and every value
of a response, recursively. A check of the top-level keys would miss a
credential nested three levels down, and a credential that reaches a
response is a credential that reaches a log, a cache and a browser's
developer console.

**The scope matrix is enforced on the server.** CAC-01 says a denied
capability is refused *whatever the interface shows*: hiding a control is
not enforcement. CAC-03 says a staff session reaches no client endpoint.
CAC-04 says a mutation without a CSRF token is refused and creates no row.
"""

from __future__ import annotations

from tests.integration.personas import crear_persona


import json
import logging
from decimal import Decimal

import pytest

from tests.conftest import membresia
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tienda.models import (
    Customer,
    LedgerEntry,
    Shop,
    Vinculo,
)
from tests.walk import (
    TOKENS_DE_AMBOS,
    afirmar_sin_fuga,
    buscar,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def owner(db, negocio):
    user = negocio.user
    membresia(negocio, user, "dueno")
    return user


@pytest.fixture
def helper(db, negocio):
    user = User.objects.create_user(username="dependiente", password="x")
    membresia(negocio, user, "dependiente")
    return user


@pytest.fixture
def tienda(db, negocio):
    """The shop of the credit book - the business's own shop."""
    return negocio.shop


@pytest.fixture
def customer(tienda):
    """A person, and the LINK that says she is a trusted client of the shop."""
    cliente_usuario, cliente = crear_persona("ana", alias="Ana")
    Vinculo.objects.create(
        tienda=tienda,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    return cliente



def _api(user, tienda):
    """A client whose session names the shop."""
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(user)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


def _cargo_de_una_deuda(customer, user, importe="10.00"):
    """One confirmed charge, so the customer has a debt to pay.

    Rule 19 refuses a payment larger than the outstanding, so a test
    that records a payment needs a debt first - otherwise the 422 says
    "there is nothing to pay" and not "the payment was refused".

    **The shop is the LINK's**: the person belongs to no shop, and the
    debt is of the shop she is a trusted client of.
    """
    from decimal import Decimal

    from django.utils import timezone

    from tienda.models import CargoLinea, Confirmacion, Producto, Vinculo

    vinculo = Vinculo.objects.filter(cliente=customer).first()
    tienda = vinculo.tienda

    cargo = LedgerEntry.objects.create(
        shop=tienda,
        customer=customer,
        user=user,
        kind="cargo",
        amount=Decimal(importe),
        occurred_at=timezone.now(),
    )
    producto = Producto.objects.create(
        shop=tienda,
        nombre="Pan",
        precio=Decimal(importe),
        unidad="unidad",
    )
    CargoLinea.objects.create(
        cargo=cargo,
        producto=producto,
        cantidad=Decimal("1"),
        precio_unitario=Decimal(importe),
        total=Decimal(importe),
    )
    Confirmacion.objects.create(
        cargo=cargo,
        estado="confirmado",
        confirmado_en=timezone.now(),
        origen="tienda",
        confirmado_por=user,
    )
    return cargo


# ---------------------------------------------------------------------------
# 4.1 — the walk itself
# ---------------------------------------------------------------------------


def test_the_walk_visits_every_key_and_every_value():
    """The walk reaches into the whole tree.

    A credential nested three levels down is as leaked as one at the top,
    and a check of the top-level keys would miss it.
    """
    cuerpo = {
        "alias": "Ana",
        "cargos": [
            {"id": 1, "lineas": [{"producto": "Pan", "total": "1.20"}]},
        ],
    }

    from tests.walk import recorrer

    rutas = {ruta for ruta, _ in recorrer(cuerpo)}

    assert "cargos.0.lineas.0.producto" in rutas
    assert "cargos.0.id" in rutas
    assert "alias" in rutas


def test_the_walk_finds_a_token_in_a_value():
    """A token inside a value is found."""
    cuerpo = {"detalle": "la clave es ABCDEFGH"}

    hallazgos = buscar(cuerpo, ("abcdefgh",))

    assert len(hallazgos) == 1
    assert hallazgos[0][0] == "detalle"


def test_the_walk_finds_a_token_in_a_key():
    """A token inside a KEY is found too.

    A credential hidden in a key is as leaked as one in a value.
    """
    cuerpo = {"ABCDEFGH": 1}

    hallazgos = buscar(cuerpo, ("abcdefgh",))

    assert len(hallazgos) == 1


def test_the_walk_finds_a_token_in_a_nested_list():
    """A token three levels down is found."""
    cuerpo = {"a": {"b": [{"c": "ABCDEFGH"}]}}

    hallazgos = buscar(cuerpo, ("abcdefgh",))

    assert len(hallazgos) == 1
    assert hallazgos[0][0] == "a.b.0.c"


def test_the_walk_reports_the_path_of_the_leak():
    """The report says WHERE, not merely that there was one.

    "there is a leak" is not actionable: "the credential is at
    cargos.0.lineas.2.producto" is.
    """
    cuerpo = {"cargos": [{"lineas": [{"producto": "ABCDEFGH"}]}]}

    with pytest.raises(AssertionError) as exc:
        afirmar_sin_fuga(cuerpo, ("abcdefgh",), "the staff tree")

    assert "cargos.0.lineas.0.producto" in str(exc.value)


def test_a_clean_body_passes_the_walk():
    """A body with no token passes."""
    afirmar_sin_fuga({"alias": "Ana", "total": "30.00"}, ("abcdefgh",), "the tree")


# ---------------------------------------------------------------------------
# R1 — the credential is absent from every staff response
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# R2 — the credential is absent from every client response
# ---------------------------------------------------------------------------



def test_the_client_schema_declares_no_staff_only_field():
    """CAC-10: the client's schema declares none of the nine.

    The schema is the guarantee: DRF's `fields` is exhaustive, so a field
    that is not declared cannot be in the response whatever the view hands
    over.
    """
    from tienda.api.serializers.cliente import EstadoClienteSerializer
    from tienda.api.serializers.fields import fields_de
    from tienda.api.serializers.staff import CAMPOS_SOLO_DE_PERSONAL

    declarados = fields_de(EstadoClienteSerializer)

    assert declarados & CAMPOS_SOLO_DE_PERSONAL == set()


# ---------------------------------------------------------------------------
# R3 — the logs
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# R4 — the URL
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# R5 — the error bodies
# ---------------------------------------------------------------------------



def test_the_error_messages_are_constants():
    """Every message of the vocabulary is a constant.

    A message built from the request would carry the request.
    """
    from tienda.api.exceptions import CODIGOS_ERROR

    for codigo, detalle in CODIGOS_ERROR.items():
        assert detalle
        assert "{" not in detalle, f"the message of {codigo} looks interpolated"


# ---------------------------------------------------------------------------
# R8 — the throttle is not an oracle
# ---------------------------------------------------------------------------





def _peticion(valor: str):
    from django.test import RequestFactory

    return RequestFactory().get("/", HTTP_X_CODIGO=valor)


# ---------------------------------------------------------------------------
# 4.2 — the scope matrix
# ---------------------------------------------------------------------------




def test_la_matriz_de_capacidades_se_impone_en_el_servidor(helper, tienda, customer):
    """CAC-01: a denied capability is refused whatever the interface shows.

    The matrix of §7, row by row, against the live routes - **both**
    directions, because the matrix changed when the N5 gate opened.

    With the gate open the `dependiente` READS the credit book and
    RECORDS the payments. What stays the owner's is the POLICY: the
    catalogue, the `credit_limit`, the suspension and the credential.
    """
    api = _api(helper, tienda)

    # Granted to the `dependiente`: the credit book, read and collected.
    for ruta, metodo in (
        (reverse("api:clientes"), "get"),
        (reverse("api:cliente_detalle", args=[customer.id]), "get"),
    ):
        respuesta = getattr(api, metodo)(ruta)
        assert respuesta.status_code == 200, (
            f"{ruta} answered {respuesta.status_code} to the dependiente"
        )

    # And the payment: it needs a debt to pay, so one is created first.
    _cargo_de_una_deuda(customer, helper)
    respuesta = api.post(
        reverse("api:cliente_libreta", args=[customer.id]),
        {"kind": "pago", "amount": "1.00"},
        format="json",
    )
    assert respuesta.status_code == 201

    # Denied to the `dependiente`: the owner's policy.
    for ruta, metodo in (
        (reverse("api:catalogo"), "get"),
    ):
        respuesta = getattr(api, metodo)(ruta)
        assert respuesta.status_code == 403, (
            f"{ruta} answered {respuesta.status_code} to the dependiente"
        )

    # The `credit_limit` is the owner's, and so is creating a customer.
    respuesta = api.patch(
        reverse("api:cliente_detalle", args=[customer.id]),
        {"credit_limit": "500.00"},
        format="json",
    )
    assert respuesta.status_code == 403

    respuesta = api.post(
        reverse("api:clientes"), {"alias": "Bruno"}, format="json"
    )
    assert respuesta.status_code == 403
    assert Customer.objects.count() == 1


def test_una_mutacion_sin_csrf_es_rechazada(owner, tienda, customer):
    """CAC-04: a mutation without a CSRF token is refused and creates no row.

    A staff mutation carries a valid `X-CSRFToken`, and a request without
    one is refused with 403 **and writes nothing**.

    The request authenticates with a REAL session, not with
    `force_authenticate`: DRF's `SessionAuthentication.enforce_csrf` runs only
    when the session is what authenticated the request, and
    `force_authenticate` bypasses the authentication machinery entirely —
    CSRF and all. A test that used it would prove nothing about the CSRF.
    """
    api = APIClient(enforce_csrf_checks=True)
    sesion = _sesion_con(tienda, owner)
    api.cookies["sessionid"] = sesion.session_key

    respuesta = api.post(
        reverse("api:caja"),
        {"kind": "entrada", "concept": "caja", "amount": "50.00"},
        format="json",
    )

    assert respuesta.status_code == 403
    from tienda.models import CashMovement

    assert CashMovement.objects.count() == 0
    assert LedgerEntry.objects.count() == 0


def test_una_mutacion_con_csrf_valido_pasa(owner, tienda, customer):
    """The companion of the previous test: a valid token IS admitted.

    Without it, "the request is refused" would pass on a route that refuses
    everything — including the owner.
    """
    api = APIClient(enforce_csrf_checks=True)
    sesion = _sesion_con(tienda, owner)
    api.cookies["sessionid"] = sesion.session_key

    # The cookie carries the secret and the header its masked form; Django
    # unmasks the header and compares it with the cookie.
    token = _csrf_para(api)

    respuesta = api.post(
        reverse("api:caja"),
        {"kind": "entrada", "concept": "caja", "amount": "50.00"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )

    assert respuesta.status_code == 201
    from tienda.models import CashMovement

    assert CashMovement.objects.count() == 1




def _sesion_con(tienda, usuario=None):
    """A session that names the shop, and signs the user in.

    The three keys of an authenticated session are the user's id, the
    backend that authenticated it and the hash of its password. Writing the
    id into the **backend** slot signs nobody in, and the request answers
    403 for a reason that has nothing to do with the permission.
    """
    from django.contrib.auth import (
        BACKEND_SESSION_KEY,
        HASH_SESSION_KEY,
        SESSION_KEY,
    )
    from django.contrib.sessions.backends.db import SessionStore

    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    if usuario is not None:
        sesion[SESSION_KEY] = str(usuario.pk)
        sesion[BACKEND_SESSION_KEY] = (
            "django.contrib.auth.backends.ModelBackend"
        )
        sesion[HASH_SESSION_KEY] = usuario.get_session_auth_hash()
    sesion.save()
    return sesion
def _csrf_para(api):
    """The CSRF cookie and the matching token, minted the way Django does.

    Django's check compares the header against the **cookie's secret**. The
    cookie carries the secret - 32 characters - and the header carries the
    **masked** form of that same secret - 64 characters. The check unmasks
    the header and compares it with the cookie.

    So the two are NOT the same string, and a test that puts the same value
    in both places is refused. This helper mints the pair the way a view
    does, with `get_token`.
    """
    from django.middleware.csrf import _unmask_cipher_token, get_token
    from django.test import RequestFactory

    peticion = RequestFactory().get("/")
    token = get_token(peticion)
    # The COOKIE carries the secret, not the masked form.
    api.cookies["csrftoken"] = _unmask_cipher_token(token)
    return token
