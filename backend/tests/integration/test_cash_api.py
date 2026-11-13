"""The cash and the close — tasks 4.3, CP-01, CP-02, CP-04, CP-05.

Two roles, one drawer. The `dueño` and the `dependiente` may both record a
cash movement and close the day — CP-01 says so — and they read the same
drawer. What differs is the **close payload**: the owner's carries the
date, the dependent's does not (CP-05).

The cases here are the ones the design fixes:

* a movement is recorded with the server's stamp, never a client-supplied
  one (rule 4);
* a movement stamped in the future is refused (rule 12);
* a refused write creates **no row**;
* the close stores the **derived** `esperado` and the server-computed
  `desviacion` — never a client-supplied figure (rules 13 and 14);
* a close request carrying `esperado` or `desviacion` is refused on the
  **presence** of the field (rule 14);
* a day is closed once per shop (rule 9).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tienda.models import CashMovement, DayClose

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
def cliente(owner):
    api = APIClient()
    api.force_authenticate(owner)
    return api


@pytest.fixture
def tienda(db, owner):
    """The shop of the acting session.

    The staff scope is `session["shop_id"]`, and a session without a shop
    has no scope at all (design §7.1). The login helper writes it.
    """
    from tienda.models import Shop

    return Shop.objects.create(
        name="Tienda de prueba", opening_cash=Decimal("150.00")
    )


@pytest.fixture
def cliente_con_tienda(cliente, tienda):
    """A client whose session names the shop."""
    from django.contrib.sessions.backends.db import SessionStore

    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    cliente.cookies["sessionid"] = sesion.session_key
    return cliente


@pytest.fixture
def customer(tienda):
    """A customer of the shop."""
    from tienda.models import Customer

    return Customer.objects.create(
        shop=tienda, alias="Ana", credit_limit=Decimal("100.00")
    )


@pytest.fixture
def cargo(tienda, customer, owner):
    """A charge of 30,00 € — the debt that puts the customer on the ladder."""
    from tienda.models import LedgerEntry

    return LedgerEntry.objects.create(
        shop=tienda,
        customer=customer,
        user=owner,
        kind="cargo",
        amount=Decimal("30.00"),
        occurred_at=timezone.now(),
    )


# ---------------------------------------------------------------------------
# The cash
# ---------------------------------------------------------------------------


def test_a_cash_movement_is_recorded(cliente_con_tienda):
    """CP-01: both roles may record a movement of the drawer."""
    respuesta = cliente_con_tienda.post(
        reverse("api:caja"),
        {"kind": "entrada", "concept": "caja inicial", "amount": "50.00"},
            format="json",
    )

    assert respuesta.status_code == 201
    assert CashMovement.objects.count() == 1
    movimiento = CashMovement.objects.get()
    assert movimiento.amount == Decimal("50.00")
    assert movimiento.kind == "entrada"


def test_the_dependiente_may_record_a_movement(tienda, helper):
    """CP-01: the `dependiente` records the cash too."""
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(helper)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key

    respuesta = api.post(
        reverse("api:caja"),
        {"kind": "salida", "concept": "compra", "amount": "5.00"},
        format="json",
    )

    assert respuesta.status_code == 201
    assert CashMovement.objects.count() == 1


def test_a_movement_may_not_carry_an_occurred_at(cliente_con_tienda):
    """Rule 4: the server stamps the movement, never the client.

    The refusal is on the **presence** of the field, not on its value.
    """
    respuesta = cliente_con_tienda.post(
        reverse("api:caja"),
        {
            "kind": "entrada",
            "concept": "caja",
            "amount": "50.00",
            "occurred_at": "2026-05-01T10:00:00Z",
        },
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "campo_no_admitido"
    assert CashMovement.objects.count() == 0


def test_a_movement_stamped_in_the_future_is_refused(cliente_con_tienda):
    """Rule 12: the server refuses a stamp in the future."""
    futuro = timezone.now() + timedelta(days=1)

    respuesta = cliente_con_tienda.post(
        reverse("api:caja"),
        {
            "kind": "entrada",
            "concept": "caja",
            "amount": "50.00",
            "occurred_at": futuro.isoformat(),
        },
        format="json",
    )

    assert respuesta.status_code == 422
    assert CashMovement.objects.count() == 0


def test_a_movement_of_a_non_positive_amount_is_refused(cliente_con_tienda):
    """PA-10: the amount must be greater than zero."""
    respuesta = cliente_con_tienda.post(
        reverse("api:caja"),
        {"kind": "entrada", "concept": "caja", "amount": "0.00"},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "importe_no_positivo"
    assert CashMovement.objects.count() == 0


def test_a_movement_of_an_unknown_kind_is_refused(cliente_con_tienda):
    """The kind is `entrada` or `salida`, nothing else."""
    respuesta = cliente_con_tienda.post(
        reverse("api:caja"),
        {"kind": "traspaso", "concept": "x", "amount": "5.00"},
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "tipo_desconocido"
    assert CashMovement.objects.count() == 0


def test_a_refused_movement_creates_no_row(cliente_con_tienda):
    """A refused write leaves the drawer exactly as it was."""
    cliente_con_tienda.post(
        reverse("api:caja"),
        {"kind": "entrada", "concept": "caja", "amount": "-1.00"},
        format="json",
    )

    assert CashMovement.objects.count() == 0


# ---------------------------------------------------------------------------
# The close
# ---------------------------------------------------------------------------


def test_the_close_stores_the_derived_expected_cash(cliente_con_tienda, tienda):
    """CP-04: `esperado` is the derived `caja`, never a client figure."""
    hoy = timezone.now().date()

    respuesta = cliente_con_tienda.post(
        reverse("api:cierre"), {"date": hoy.isoformat(), "contado": "150.00"}, format="json"
    )

    assert respuesta.status_code == 201
    cierre = DayClose.objects.get()
    assert cierre.esperado == Decimal("150.00")
    assert cierre.desviacion == Decimal("0.00")


def test_the_deviation_is_the_server_computed_one(cliente_con_tienda):
    """CP-04: `desviacion` is `esperado - contado`, computed by the server."""
    hoy = timezone.now().date()

    cliente_con_tienda.post(
        reverse("api:cierre"), {"date": hoy.isoformat(), "contado": "140.00"}, format="json"
    )

    assert DayClose.objects.get().desviacion == Decimal("10.00")


def test_a_close_request_may_not_carry_the_expected(cliente_con_tienda):
    """Rule 14: the request may not carry `esperado` or `desviacion`.

    The refusal is on the **presence** of the field. A close that carried
    its own `esperado` would be asserting the figure it is supposed to
    measure.
    """
    hoy = timezone.now().date()

    respuesta = cliente_con_tienda.post(
        reverse("api:cierre"),
        {
            "date": hoy.isoformat(),
            "contado": "150.00",
            "esperado": "999.00",
            "desviacion": "0.00",
        },
        format="json",
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "campo_no_admitido"
    assert DayClose.objects.count() == 0


def test_a_day_is_closed_once(cliente_con_tienda):
    """Rule 9: a day is closed once per shop."""
    hoy = timezone.now().date()

    cliente_con_tienda.post(
        reverse("api:cierre"), {"date": hoy.isoformat(), "contado": "150.00"}, format="json"
    )
    respuesta = cliente_con_tienda.post(
        reverse("api:cierre"), {"date": hoy.isoformat(), "contado": "150.00"}, format="json"
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo_error"] == "cierre_duplicado"
    assert DayClose.objects.count() == 1


def test_the_dependent_may_close_the_day(tienda, helper):
    """CP-05: the `dependiente` records the close."""
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(helper)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key

    hoy = timezone.now().date()
    respuesta = api.post(
        reverse("api:cierre"), {"date": hoy.isoformat(), "contado": "150.00"}, format="json"
    )

    assert respuesta.status_code == 201
    assert DayClose.objects.count() == 1


def test_the_dependent_close_payload_has_no_date(tienda, helper):
    """CP-05: the close payload holds the dependent only the three figures.

    The date is the owner's. The close of today is the one on the screen.
    """
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(helper)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key

    # The close has to exist: the route answers the close of today, and
    # there is none until the day is closed.
    hoy = timezone.now().date()
    api.post(
        reverse("api:cierre"), {"date": hoy.isoformat(), "contado": "150.00"}, format="json"
    )

    respuesta = api.get(reverse("api:cierre"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert sorted(cuerpo) == ["contado", "desviacion", "esperado"]
    assert "date" not in cuerpo


def test_the_owner_close_payload_carries_the_date(cliente_con_tienda):
    """The owner's close carries the date."""
    hoy = timezone.now().date()
    cliente_con_tienda.post(
        reverse("api:cierre"), {"date": hoy.isoformat(), "contado": "150.00"}, format="json"
    )

    respuesta = cliente_con_tienda.get(reverse("api:cierre"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert sorted(cuerpo) == ["contado", "date", "desviacion", "esperado"]


def test_the_close_of_a_day_that_was_not_closed_is_not_found(cliente_con_tienda):
    """A day with no close answers 404.

    There is no close to show, and the route does not invent one.
    """
    respuesta = cliente_con_tienda.get(reverse("api:cierre"))

    assert respuesta.status_code == 404


# ---------------------------------------------------------------------------
# The position — two payloads, one route
# ---------------------------------------------------------------------------


def test_the_owner_position_carries_the_whole_board(cliente_con_tienda, customer):
    """The owner's board: the ladder, the position, the buckets and the series."""
    respuesta = cliente_con_tienda.get(reverse("api:posicion"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert set(cuerpo) == {
        "buckets",
        "caja",
        "clientes",
        "cierre_hoy",
        "fiado_pendiente",
        "posicion_real",
        "serie_caja",
    }


def test_the_dependent_position_carries_only_three_fields(tienda, helper, customer):
    """The `dependiente` gets the REDUCED payload of design §7.

    The ladder, the `posicion_real`, the `fiado_pendiente` and the `buckets`
    are 403 for the `dependiente` — which means they are not in the response
    at all, because the schema does not declare them. This is the
    boundary of §7.1, and it is a property of the SCHEMA rather than a
    filter applied afterwards.
    """
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(helper)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key

    respuesta = api.get(reverse("api:posicion"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"caja", "clientes", "cierre_hoy"}


def test_the_dependent_position_never_lists_the_customers(tienda, helper, customer):
    """The dependent's `clientes` is `[]`, and the table is never asked.

    The guarantee is not "the rows are filtered afterwards" — it is "the
    rows are never requested". The `SerializerMethodField` returns the
    empty list and takes no query parameter, so there is nothing to filter
    and nothing to leak.
    """
    from django.contrib.sessions.backends.db import SessionStore

    api = APIClient()
    api.force_authenticate(helper)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key

    respuesta = api.get(reverse("api:posicion"))

    assert respuesta.json()["clientes"] == []


def test_the_dependent_position_does_not_query_the_customers(tienda, helper, customer):
    """No query reaches the customer table for the dependent's board.

    This is the stronger form of the previous test: it counts the queries
    the request makes, so a future change that starts filtering the
    customer rows instead of refusing to ask for them is caught.
    """
    from django.contrib.sessions.backends.db import SessionStore
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    api = APIClient()
    api.force_authenticate(helper)
    sesion = SessionStore()
    sesion["shop_id"] = tienda.id
    sesion.save()
    api.cookies["sessionid"] = sesion.session_key

    with CaptureQueriesContext(connection) as consultas:
        respuesta = api.get(reverse("api:posicion"))

    assert respuesta.status_code == 200
    sobre_clientes = [
        q for q in consultas.captured_queries
        if "tienda_customer" in q["sql"]
    ]
    assert sobre_clientes == [], (
        "the dependent's board queried the customer table: "
        + "; ".join(q["sql"] for q in sobre_clientes)
    )


def test_the_owner_position_does_list_the_customers(cliente_con_tienda, customer, cargo):
    """The owner's board does list them, so the previous test means something.

    Without this, "the dependent's board never queries the customers" would
    pass on a board that never shows anybody.

    The customer owes something: the ladder holds the customers with a
    pending balance, so a customer with no debt is not on it.
    """
    respuesta = cliente_con_tienda.get(reverse("api:posicion"))

    assert respuesta.status_code == 200
    assert [c["alias"] for c in respuesta.json()["clientes"]] == ["Ana"]
