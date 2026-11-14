"""The 422 contract and the permission model — tasks 4.14 and 4.15.

Two things are under test, and they are different in kind.

**The 422 contract.** Every validation failure answers HTTP 422 with exactly
two keys, `codigo_error` and `detail`. The vocabulary is **closed**: seventeen
codes, and a code outside the list is a programming error, not a refusal.
The three properties that make the contract worth having:

* the code comes from the vocabulary;
* **no submitted value is echoed** — the `detail` is a fixed constant per
  code, never built from the request;
* the 403 carries no request data either, so the `dependiente`'s boundary
  is a *total* refusal (design §7.1).

**The permission model.** Three principals and two scopes that never mix: a
staff session, and a bearer credential scoped to one `Customer`. The tests
here cover the staff side and the two helpers; the client side needs the
credential machinery of task 4.16 and is covered in Phase 6.

None of these tests carries the `django_db` marker unless it needs the
database, and none of them may reach the ORM to decide an answer.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from rest_framework import status
from rest_framework.test import APIRequestFactory

from tienda.api import exceptions, permissions

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# The vocabulary
# ---------------------------------------------------------------------------


def test_the_vocabulary_has_the_seventeen_codes_of_the_design():
    """The vocabulary is the one of design §9.3, exactly.

    A code that is not in the design is a code a client cannot have seen
    documented, and a code in the design that is missing is a refusal that
    would fall through to a 500.
    """
    esperados = {
        "limite_superado",
        "antiguedad_superada",
        "importe_no_positivo",
        "campo_no_admitido",
        "tipo_desconocido",
        "cierre_duplicado",
        "lineas_descuadradas",
        "cargo_ya_confirmado",
        "propuesta_ya_confirmada",
        "propuesta_ya_cancelada",
        "pago_ya_resuelto",
        "pago_excede_deuda",
        "codigo_invalido",
        "codigo_duplicado",
        "cargo_ajeno",
        "producto_ajeno",
        "facilitador_invalido",
    }

    assert set(exceptions.CODIGOS_ERROR) == esperados


def test_the_codes_that_the_v2_model_removed_are_gone():
    """The dispute machinery's codes are not in the vocabulary.

    `disputa_abierta` and `importe_reclamado` died with the dispute, and
    `cargo_no_indicado` died with the client's ability to name a charge.
    """
    for codigo in ("disputa_abierta", "importe_reclamado", "cargo_no_indicado"):
        assert codigo not in exceptions.CODIGOS_ERROR


def test_every_code_has_a_fixed_message():
    """Each code carries a constant message.

    The message is never built from the request, so no submitted value can
    reach the body — and that is a property of the *shape* of the
    vocabulary, not of each caller.
    """
    for codigo, detalle in exceptions.CODIGOS_ERROR.items():
        assert detalle, f"{codigo} has no message"
        assert "{" not in detalle, (
            f"{codigo} has a message that looks like it interpolates"
        )


# ---------------------------------------------------------------------------
# The domain error
# ---------------------------------------------------------------------------


def test_a_code_outside_the_vocabulary_is_a_programming_error():
    """A code nobody documented raises, and does not reach the client."""
    with pytest.raises(ValueError):
        exceptions.DomainValidationError("codigo_inventado")


def test_a_code_in_the_vocabulary_is_accepted():
    """A code of the vocabulary builds the error."""
    error = exceptions.DomainValidationError("pago_excede_deuda")

    assert error.codigo_error == "pago_excede_deuda"
    assert error.detail == exceptions.CODIGOS_ERROR["pago_excede_deuda"]


def test_the_detail_defaults_to_the_fixed_message_of_the_code():
    """The detail is the code's own message unless one is given."""
    error = exceptions.DomainValidationError("lineas_descuadradas")

    assert error.detail == exceptions.CODIGOS_ERROR["lineas_descuadradas"]


# ---------------------------------------------------------------------------
# The handler
# ---------------------------------------------------------------------------


def test_the_handler_answers_422_with_exactly_two_keys():
    """The 422 body has `codigo_error` and `detail`, and nothing else."""
    factory = APIRequestFactory()
    request = factory.get("/api/v1/cualquiera/")

    response = exceptions.handler(
        exceptions.DomainValidationError("tipo_desconocido"), {"request": request}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert sorted(response.data) == ["codigo_error", "detail"]
    assert response.data["codigo_error"] == "tipo_desconocido"


def test_the_handler_never_echoes_a_submitted_value():
    """A submitted value does not reach the body.

    The detail is a constant per code, so a value that came in the request
    is nowhere in the response.
    """
    factory = APIRequestFactory()
    request = factory.post(
        "/api/v1/cualquiera/", {"alias": "ALIAS_SECRETO_DE_LA_TIENDA"}
    )

    response = exceptions.handler(
        exceptions.DomainValidationError("tipo_desconocido"), {"request": request}
    )

    cuerpo = str(response.data)
    assert "ALIAS_SECRETO_DE_LA_TIENDA" not in cuerpo


def test_the_handler_answers_403_with_no_request_data():
    """A refusal carries the fixed body and nothing else.

    This is the `dependiente`'s boundary of design §7.1: a 403 with no
    alias, no identifier and no count.
    """
    from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied

    factory = APIRequestFactory()
    request = factory.get("/api/v1/clientes/")

    response = exceptions.handler(
        DRFPermissionDenied("no puede"), {"request": request}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert sorted(response.data) == ["codigo_error", "detail"]
    assert response.data["codigo_error"] == exceptions.CODIGO_PERMISO_INSUFICIENTE


def test_the_403_body_is_the_fixed_one():
    """The 403 body is the constant, byte for byte."""
    from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied

    factory = APIRequestFactory()
    request = factory.get("/api/v1/clientes/")

    response = exceptions.handler(
        DRFPermissionDenied("no puede"), {"request": request}
    )

    assert response.data == exceptions.CUERPO_PERMISO_INSUFICIENTE


def test_a_not_found_answers_404_with_the_same_shape():
    """A missing resource answers 404 with the same two-key shape."""
    from django.http import Http404

    factory = APIRequestFactory()
    request = factory.get("/api/v1/clientes/999/")

    response = exceptions.handler(Http404("no existe"), {"request": request})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert sorted(response.data) == ["codigo_error", "detail"]


def test_an_unexpected_error_falls_through_to_drf():
    """An exception the contract does not cover is DRF's business."""
    factory = APIRequestFactory()
    request = factory.get("/api/v1/cualquiera/")

    response = exceptions.handler(ValueError("boom"), {"request": request})

    assert response is None


# ---------------------------------------------------------------------------
# The permission model
# ---------------------------------------------------------------------------


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="dueno", password="x")


@pytest.fixture
def helper(db):
    return User.objects.create_user(username="dependiente", password="x")


def test_the_two_roles_are_the_ones_of_the_design():
    """The shop roles are `dueno` and `dependiente`."""
    assert permissions.GRUPO_DUENO == "dueno"
    assert permissions.GRUPO_DEPENDIENTE == "dependiente"


def test_a_user_with_no_group_is_neither_role(db):
    """A user outside both groups is not staff."""
    user = User.objects.create_user(username="nadie", password="x")

    assert permissions.es_dueno(user) is False
    assert permissions.es_dependiente(user) is False


def test_an_anonymous_principal_is_neither_role():
    """An anonymous request is not staff."""
    from django.contrib.auth.models import AnonymousUser

    assert permissions.es_dueno(AnonymousUser()) is False
    assert permissions.es_dependiente(AnonymousUser()) is False


def test_role_required_refuses_a_user_outside_the_named_roles(db):
    """`RoleRequired` admits only the named groups.

    The roles live in the class attribute, because DRF **instantiates** the
    classes in `permission_classes` — a constructor argument would have
    made the permission uncallable.
    """
    from django.contrib.auth.models import Group

    class _Personal(permissions.RoleRequired):
        roles = ("dueno", "dependiente")

    user = User.objects.create_user(username="nadie", password="x")
    user.groups.add(Group.objects.create(name="dueno"))

    factory = APIRequestFactory()
    request = factory.get("/api/v1/clientes/")
    request.user = user

    permiso = _Personal()

    assert permiso.has_permission(request, None) is True

    user.groups.clear()
    assert permiso.has_permission(request, None) is False


def test_the_two_shop_roles_are_the_classes_the_views_use(db):
    """The views use `SoloPersonal` and `SoloDueno`.

    `SoloPersonal` admits the two shop roles — the cash, the close and the
    position are the shop's business. `SoloDueno` admits only the owner:
    the credit book is his alone (CAC-02).
    """
    from django.contrib.auth.models import Group

    owner = User.objects.create_user(username="dueno", password="x")
    owner.groups.add(Group.objects.create(name="dueno"))
    helper = User.objects.create_user(username="dependiente", password="x")
    helper.groups.add(Group.objects.create(name="dependiente"))

    factory = APIRequestFactory()
    request = factory.get("/api/v1/clientes/")
    request.user = owner

    assert permissions.SoloDueno().has_permission(request, None) is True
    assert permissions.SoloPersonal().has_permission(request, None) is True

    request.user = helper
    assert permissions.SoloDueno().has_permission(request, None) is False
    assert permissions.SoloPersonal().has_permission(request, None) is True


def test_is_dueno_refuses_the_dependiente(db):
    """The credit book is the owner's alone (design §7)."""
    from django.contrib.auth.models import Group

    helper = User.objects.create_user(username="dependiente", password="x")
    helper.groups.add(Group.objects.create(name="dependiente"))

    factory = APIRequestFactory()
    request = factory.get("/api/v1/clientes/")
    request.user = helper

    assert permissions.IsDueno().has_permission(request, None) is False


def test_es_cliente_refuses_a_staff_session(db):
    """A staff session never reaches a client route.

    This is invariant 1 of design 7.2: a request carrying a staff session
    cookie is refused, even if it also presents a valid credential.

    The credential IS resolved in this request, on purpose. Without it the
    assertion would pass for the wrong reason - no credential, no
    permission - and the guard that refuses a staff session would never be
    exercised. The request that proves the guard is the one that would
    otherwise be admitted.
    """
    owner = User.objects.create_user(username="dueno", password="x")

    factory = APIRequestFactory()
    request = factory.get("/api/v1/cliente/estado/")
    request.user = owner
    # The credential resolved fine. The staff session is the only reason
    # this request must be refused.
    request.cliente = object()

    assert permissions.EsCliente().has_permission(request, None) is False
def test_es_cliente_admits_a_credential_without_a_session(db):
    """A client route is served by the credential, not by a session."""
    factory = APIRequestFactory()
    request = factory.get("/api/v1/cliente/estado/")
    request.user = None
    request.cliente = object()

    assert permissions.EsCliente().has_permission(request, None) is True


def test_es_cliente_refuses_a_credential_with_no_customer(db):
    """A credential that resolved to no customer is not a client."""
    factory = APIRequestFactory()
    request = factory.get("/api/v1/cliente/estado/")
    request.user = None
    request.cliente = None

    assert permissions.EsCliente().has_permission(request, None) is False


# ---------------------------------------------------------------------------
# current_shop — the single reader of the staff scope
# ---------------------------------------------------------------------------


def test_current_shop_reads_the_session(db):
    """The shop of the staff scope is `session["shop_id"]`."""
    factory = APIRequestFactory()
    request = factory.get("/api/v1/posicion/")
    request.session = {"shop_id": 42}

    assert permissions.current_shop(request) == 42


def test_current_shop_is_none_without_a_session(db):
    """A request with no session has no staff scope."""
    factory = APIRequestFactory()
    request = factory.get("/api/v1/posicion/")
    request.session = {}

    assert permissions.current_shop(request) is None


def test_current_shop_is_none_when_the_session_names_no_shop(db):
    """A session with no shop is not a scope either.

    There is no default shop: a missing scope is a refusal, not an
    absence.
    """
    factory = APIRequestFactory()
    request = factory.get("/api/v1/posicion/")
    request.session = {"otra_cosa": 1}

    assert permissions.current_shop(request) is None


def test_exigir_shop_refuses_without_a_scope(db):
    """`exigir_shop` raises the refusal the handler turns into the 403."""
    factory = APIRequestFactory()
    request = factory.get("/api/v1/posicion/")
    request.session = {}

    with pytest.raises(PermissionDenied):
        permissions.exigir_shop(request)


def test_exigir_shop_returns_the_shop(db):
    """With a scope, it returns the shop id."""
    factory = APIRequestFactory()
    request = factory.get("/api/v1/posicion/")
    request.session = {"shop_id": 7}

    assert permissions.exigir_shop(request) == 7


def test_cliente_de_reads_the_resolved_customer(db):
    """`cliente_de` is the single reader of the client identity."""
    factory = APIRequestFactory()
    request = factory.get("/api/v1/cliente/estado/")
    request.cliente = "el-cliente"

    assert permissions.cliente_de(request) == "el-cliente"


def test_cliente_de_is_none_without_a_credential(db):
    """No credential, no customer."""
    factory = APIRequestFactory()
    request = factory.get("/api/v1/cliente/estado/")

    assert permissions.cliente_de(request) is None
