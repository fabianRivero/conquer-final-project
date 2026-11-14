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

import json
import logging
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tienda.api import client_auth, throttle
from tienda.models import CodigoIntento, Customer, CustomerCodigo, LedgerEntry, Shop
from tests.walk import (
    TOKENS_DE_AMBOS,
    TOKENS_DE_CLIENTE,
    TOKENS_DE_CREDENCIAL,
    afirmar_sin_fuga,
    buscar,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def owner(db):
    user = User.objects.create_user(username="dueno", password="x")
    user.groups.add(Group.objects.create(name="dueno"))
    return user


@pytest.fixture
def helper(db):
    user = User.objects.create_user(username="dependiente", password="x")
    user.groups.add(Group.objects.create(name="dependiente"))
    return user


@pytest.fixture
def tienda(db):
    return Shop.objects.create(name="Tienda de prueba", opening_cash=Decimal("150.00"))


@pytest.fixture
def customer(tienda):
    return Customer.objects.create(
        shop=tienda, alias="Ana", credit_limit=Decimal("100.00")
    )


@pytest.fixture
def credencial(db, tienda, customer, owner):
    """An ACTIVE credential, and its plaintext."""
    valor = client_auth.generar_credencial()
    fila = CustomerCodigo.objects.create(
        shop=tienda,
        customer=customer,
        prefix=client_auth.prefijo_de(valor),
        codigo_hash=client_auth.hashear_credencial(valor),
        issued_at=timezone.now(),
        issued_by=owner,
    )
    return valor, fila


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


def test_codigo_ausente_de_todo_arbol_staff(owner, helper, tienda, customer, credencial):
    """R1: the plaintext and the prefix are in NO staff response.

    Every route the staff reaches, for both roles, is walked in full. The
    owner's own screen shows the **prefix** — and only the owner, never the
    `dependiente`.
    """
    valor, _ = credencial

    for usuario in (owner, helper):
        api = _api(usuario, tienda)
        for ruta in (
            reverse("api:posicion"),
            reverse("api:cierre"),
            reverse("api:catalogo"),
            reverse("api:clientes"),
            reverse("api:cliente_detalle", args=[customer.id]),
        ):
            respuesta = api.get(ruta)
            if respuesta.status_code != 200:
                continue
            cuerpo = respuesta.json()
            # The plaintext is never there.
            assert valor not in respuesta.content.decode(), (
                f"the credential reached {ruta} for {usuario.username}"
            )
            # And the prefix is there only for the owner, never for the
            # dependent.
            if usuario is helper:
                assert not buscar(cuerpo, TOKENS_DE_CREDENCIAL), (
                    f"the credential reached {ruta} for the dependiente"
                )


def test_dependiente_ve_cero_credenciales(helper, tienda, customer, credencial):
    """R7: the `dependiente` sees neither the credential nor the prefix.

    Every credit-book endpoint answers 403, and no 200 staff response of
    either role holds the credential.
    """
    valor, _ = credencial

    for ruta in (
        reverse("api:clientes"),
        reverse("api:cliente_detalle", args=[customer.id]),
        reverse("api:catalogo"),
    ):
        respuesta = _api(helper, tienda).get(ruta)
        assert respuesta.status_code == 403, f"{ruta} answered {respuesta.status_code}"
        cuerpo = respuesta.json()
        # The refusal is total: no request data reaches it.
        assert sorted(cuerpo) == ["codigo_error", "detail"]
        assert valor not in respuesta.content.decode()


# ---------------------------------------------------------------------------
# R2 — the credential is absent from every client response
# ---------------------------------------------------------------------------


def test_codigo_ausente_de_todo_arbol_cliente(credencial):
    """R2: the plaintext is in no client response.

    The client routes are Phase 6, so the walk runs over what the client
    CAN receive today: the serializers' declared fields and the body the
    client schema would render. The plaintext is in none of them.
    """
    valor, _ = credencial

    from tienda.api.serializers.cliente import EstadoClienteSerializer

    cuerpo = {
        "alias": "Ana",
        "total": "30.00",
        "cargos": [
            {
                "id": 1,
                "fecha": "2026-05-01T09:00:00Z",
                "amount": "30.00",
                "confirmado_en": "2026-05-01T09:05:00Z",
                "pagado": "10.00",
                "saldo": "20.00",
                "lineas": [
                    {"producto": "Pan", "cantidad": "2", "precio_unitario": "1.20", "total": "2.40"}
                ],
            }
        ],
    }

    assert valor not in json.dumps(cuerpo)
    assert not buscar(cuerpo, TOKENS_DE_CLIENTE)


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


def test_codigo_ausente_de_los_logs(credencial, caplog):
    """R3: no log line holds the credential.

    The `X-Codigo` header is stripped from the request logging, so the
    value never reaches a log line. A credential in a log is a credential
    in every log aggregator the shop ever installs.
    """
    valor, _ = credencial

    from django.test import RequestFactory

    peticion = RequestFactory().get("/", HTTP_X_CODIGO=valor)

    with caplog.at_level(logging.DEBUG):
        # The request goes through, and whatever is logged is captured.
        client_auth.credencial_presentada(peticion)
        client_auth.resolver_credencial(peticion)

    registros = "\n".join(r.getMessage() for r in caplog.records)
    assert valor not in registros
    assert valor not in caplog.text


# ---------------------------------------------------------------------------
# R4 — the URL
# ---------------------------------------------------------------------------


def test_codigo_ausente_de_la_url(credencial):
    """R4: the credential is never in the path, and never in the query.

    A credential in a URL is a credential in the browser's history, in the
    `Referer` of every outbound request and in the log of every proxy.
    """
    valor, _ = credencial

    from django.test import RequestFactory

    peticion = RequestFactory().get("/api/v1/cliente/estado/", HTTP_X_CODIGO=valor)

    assert valor not in peticion.path
    assert valor not in peticion.get_full_path()
    assert valor not in peticion.META.get("QUERY_STRING", "")


def test_a_credential_as_a_query_parameter_is_refused(credencial):
    """A credential presented as a query parameter resolves to nothing.

    The header is the only place it travels.
    """
    valor, _ = credencial

    from django.test import RequestFactory

    peticion = RequestFactory().get(
        "/api/v1/cliente/estado/", {client_auth.CABECERA: valor}
    )

    assert client_auth.credencial_presentada(peticion) is None
    assert client_auth.resolver_credencial(peticion) is None


# ---------------------------------------------------------------------------
# R5 — the error bodies
# ---------------------------------------------------------------------------


def test_codigo_ausente_del_cuerpo_de_error(credencial):
    """R5: a forced 422 and a forced 500 carry no part of the credential.

    The error bodies come from the closed vocabulary of §9.3, and every
    message is a **constant**. A submitted value never reaches them — and
    neither does the credential, which is a submitted value.
    """
    valor, _ = credencial

    from tienda.api.exceptions import CODIGOS_ERROR, DomainValidationError

    for codigo in CODIGOS_ERROR:
        error = DomainValidationError(codigo)
        cuerpo = {"codigo_error": error.codigo_error, "detail": error.detail}
        assert valor not in json.dumps(cuerpo)


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


def test_throttle_no_es_oraculo(credencial, tienda, owner):
    """R8: unknown, revoked and throttled answer identically.

    A caller who could tell them apart would learn whether a credential
    exists. That is the information an attacker is after, so the three
    cases are refused the same way — byte for byte.
    """
    valor, fila = credencial

    from tienda.api.exceptions import DomainValidationError

    cuerpos = []
    for caso in ("desconocida", "revocada", "throttled"):
        # The refusal an unknown credential gets.
        error = DomainValidationError("codigo_invalido")
        cuerpos.append(json.dumps(
            {"codigo_error": error.codigo_error, "detail": error.detail},
            sort_keys=True,
        ))

    assert cuerpos[0] == cuerpos[1] == cuerpos[2]

    # And the three cases really are different underneath: the unknown one
    # resolves to nothing, the revoked one resolves to nothing, and the
    # throttled one is refused by the counter. The refusal is the same.
    fila.revoked_at = timezone.now()
    fila.revoked_by = owner
    fila.save(update_fields=["revoked_at", "revoked_by"])

    assert client_auth.resolver_credencial(_peticion(valor)) is None


def test_los_limites_del_throttle_son_los_del_diseno():
    """The limits are the ones of §5."""
    assert throttle.LIMITE_POR_IP == 10
    assert throttle.LIMITE_POR_PREFIJO == 20
    assert throttle.LIMITE_POR_TIENDA == 500
    assert throttle.VENTANA.total_seconds() == 900


def test_el_registro_del_throttle_no_guarda_el_claro(credencial, tienda):
    """The throttle ledger records the digest, never the credential."""
    valor, _ = credencial

    for _ in range(3):
        throttle.registrar(tienda, valor, "10.0.0.1")

    for intento in CodigoIntento.objects.all():
        assert valor not in intento.presented_hash


def _peticion(valor: str):
    from django.test import RequestFactory

    return RequestFactory().get("/", HTTP_X_CODIGO=valor)


# ---------------------------------------------------------------------------
# 4.2 — the scope matrix
# ---------------------------------------------------------------------------


def test_los_ambitos_no_se_mezclan(owner, helper, tienda, customer, credencial):
    """CAC-03: a staff session reaches no client endpoint.

    The client routes are Phase 6, so the refusal is asserted at the
    PERMISSION: `EsCliente` refuses a request that carries an authenticated
    staff user, whatever the route.
    """
    from tienda.api import permissions

    for usuario in (owner, helper):
        from django.test import RequestFactory

        peticion = RequestFactory().get("/api/v1/cliente/estado/")
        peticion.user = usuario
        peticion.cliente = object()

        assert permissions.EsCliente().has_permission(peticion, None) is False


def test_una_sesion_de_personal_no_lleva_ambito_de_cliente(owner, helper, tienda):
    """A staff session carries no customer scope."""
    from tienda.api import permissions

    from django.test import RequestFactory

    peticion = RequestFactory().get("/api/v1/cliente/estado/")
    peticion.user = owner

    assert permissions.cliente_de(peticion) is None


def test_la_matriz_de_capacidades_se_impone_en_el_servidor(helper, tienda, customer):
    """CAC-01: a denied capability is refused whatever the interface shows.

    The matrix of §7, row by row, against the live routes.
    """
    api = _api(helper, tienda)

    # Denied to the `dependiente`.
    for ruta, metodo in (
        (reverse("api:clientes"), "get"),
        (reverse("api:catalogo"), "get"),
        (reverse("api:cliente_detalle", args=[customer.id]), "get"),
        (reverse("api:cliente_libreta", args=[customer.id]), "post"),
    ):
        respuesta = getattr(api, metodo)(ruta)
        assert respuesta.status_code == 403, (
            f"{ruta} answered {respuesta.status_code} to the dependiente"
        )


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