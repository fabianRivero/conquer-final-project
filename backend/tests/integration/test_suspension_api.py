"""PA-08 - the owner lifts a suspension.

**The suspension is DERIVED and the override is an ACT.** The state is
computed on read (PA-05, PA-06): a customer is suspended because the
outstanding exceeds the limit, or because the oldest debt is older than
the suspension age. This route records the owner's act, and the act is
what lifts it - **nothing of the book is touched**, and nothing derived
is ever written.

**The owner's alone.** The `dependiente` reads the credit book but does
not set the policy (design §7.1), so he gets a total 403 and no data.

Every assertion here is on the **effect** - the rows written, the rows
NOT written, the fields present and absent - never on a status code
alone.
"""

from __future__ import annotations

from tests.integration.personas import crear_persona


from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tests.conftest import membresia

from tienda.models import LedgerEntry, Shop, Vinculo

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
    """The `dependiente`: he reads the book and does not set the policy."""
    user = User.objects.create_user(username="dependiente", password="x")
    membresia(negocio, user, "dependiente")
    return user


@pytest.fixture
def tienda(db, negocio):
    return negocio.shop


def _api_de(user, tienda):
    """An API client whose session names the shop."""
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(user)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key
    return api


@pytest.fixture
def api_owner(owner, tienda):
    return _api_de(owner, tienda)


@pytest.fixture
def api_dependiente(helper, tienda):
    return _api_de(helper, tienda)


@pytest.fixture
def cliente(tienda):
    """A trusted client of the shop, with a limit of 100."""
    _usuario, cliente = crear_persona("ana", alias="Ana")
    Vinculo.objects.create(
        tienda=tienda,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    return cliente


@pytest.fixture
def suspendido(cliente, tienda, owner):
    """A debt OVER the limit: the derived state reads `suspendido`."""
    LedgerEntry.objects.create(
        shop=tienda,
        customer=cliente,
        user=owner,
        kind="cargo",
        amount=Decimal("150.00"),
        occurred_at=timezone.now() - timedelta(days=5),
    )
    return cliente


# ---------------------------------------------------------------------------
# PA-08
# ---------------------------------------------------------------------------


def test_el_dueno_levanta_la_suspension(api_owner, suspendido, cliente, tienda):
    """The owner lifts it, and the customer reads `activo` again.

    **The act is recorded, not the state**: the override names who did
    it and when, and the derived state follows.
    """
    from tienda import services

    antes = services.estado_de(cliente, tienda=tienda)
    assert antes.suspendido is True
    assert antes.motivo == "limite_superado"

    respuesta = api_owner.post(
        reverse("api:cliente_suspension", args=[cliente.id]),
        {},
        format="json",
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["suspendido"] is False
    assert cuerpo["motivo"] is None

    cliente.refresh_from_db()
    assert cliente.suspended_override_at is not None
    assert cliente.suspended_override_by_id is not None

    # And the state on read agrees.
    despues = services.estado_de(cliente, tienda=tienda)
    assert despues.suspendido is False


def test_el_override_deja_el_libro_intacto(api_owner, suspendido, cliente, tienda):
    """**The override touches nothing of the book.**

    PA-08's second scenario: no prior entry changed, and the outstanding
    is unchanged. The act is the owner's own record, not a row of the
    ledger.
    """
    from tienda import services

    antes = services.estado_de(cliente, tienda=tienda)
    entradas_antes = list(LedgerEntry.objects.all().values())

    api_owner.post(
        reverse("api:cliente_suspension", args=[cliente.id]),
        {},
        format="json",
    )

    despues = services.estado_de(cliente, tienda=tienda)
    assert despues.total == antes.total
    assert list(LedgerEntry.objects.all().values()) == entradas_antes


def test_el_dependiente_no_levanta_una_suspension(api_dependiente, suspendido, cliente):
    """**The owner's policy is not the `dependiente`'s.**

    He reads the credit book, but the policy is not his: the refusal is
    a total 403 and carries no data.
    """
    respuesta = api_dependiente.post(
        reverse("api:cliente_suspension", args=[cliente.id]),
        {},
        format="json",
    )

    assert respuesta.status_code == 403
    assert "credit_limit" not in respuesta.content.decode()
    cliente.refresh_from_db()
    assert cliente.suspended_override_at is None


def test_un_cliente_de_otra_tienda_no_se_encuentra(api_owner, suspendido, db):
    """**A customer of another shop answers 404.**

    A 403 would confirm that the customer exists, and the answer is
    about this shop's book, not about who exists.
    """
    otra = Shop.objects.create(name="Tienda de al lado", opening_cash=Decimal("150.00"))
    _usuario, cliente = crear_persona("bob", alias="Bob")
    Vinculo.objects.create(
        tienda=otra,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )

    respuesta = api_owner.post(
        reverse("api:cliente_suspension", args=[cliente.id]),
        {},
        format="json",
    )

    assert respuesta.status_code == 404
