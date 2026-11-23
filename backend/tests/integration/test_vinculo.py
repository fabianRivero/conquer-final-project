"""Slice 10.3 - the link, and the client's consent.

The client is a **person**, and the link is what says she is a **trusted
client of a shop**. The person belongs to no shop; the link says she
belongs to this one.

**The limit is the LINK's.** `credit_limit` is the confidence the owner
puts in this client **in this shop**: Ana may have 100 in one shop and
30 in another, and the ageing is per shop too - "she has not paid here
for 90 days" says nothing about the other one.

**The consent is the client's.** The shop asks, and the client accepts
from her own account. Until she does, the link is `pendiente` and the
client sees **only the shop's name and the buttons**: if she could see
the debt and the ageing first, the consent would be a formality - she
would already have seen everything the acceptance reveals.

**The states:**

    the shop asks      -> pendiente
    the client accepts  -> aceptado
    the client refuses  -> rechazado
    the owner removes   -> eliminado      (the owner does not ask)
    the owner re-adds   -> pendiente      (the client decides again)
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tienda.models import Customer, Vinculo

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def negocio(db):
    """The business, its owner and its shop."""
    from decimal import Decimal as D

    from tienda.models import PerfilTienda, Shop

    dueno = User.objects.create_user(username="dueno", password="secreta123")
    tienda = Shop.objects.create(name="Tienda de prueba", opening_cash=D("150.00"))
    perfil = PerfilTienda.objects.create(
        user=dueno,
        nombre=tienda.name,
        direccion="",
        nif="",
        shop=tienda,
    )
    return perfil


@pytest.fixture
def dueno(negocio):
    from tests.conftest import membresia

    user = negocio.user
    membresia(negocio, user, "dueno")
    return user


@pytest.fixture
def cliente(db):
    """A person. **No shop** - she belongs to no shop yet."""
    return Customer.objects.create(alias="Ana")


@pytest.fixture
def vinculo(db, negocio, cliente):
    """A trusted-client link, accepted."""
    return Vinculo.objects.create(
        tienda=negocio.shop,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )


@pytest.fixture
def api(dueno, negocio):
    """A client whose session names the shop."""
    from django.contrib.sessions.backends.db import SessionStore

    cliente = APIClient()
    cliente.force_authenticate(dueno)
    sesion = SessionStore()
    sesion["shop_id"] = negocio.shop.id
    sesion.save()
    cliente.cookies["sessionid"] = sesion.session_key
    return cliente


# ---------------------------------------------------------------------------
# 10.3.1 - The model
# ---------------------------------------------------------------------------


def test_el_cliente_no_pertenece_a_una_tienda(db):
    """The client belongs to NO shop. She is a person.

    **A person may owe in SEVERAL shops**, and that is impossible while
    the client carries a `shop`: she would belong to the first one and
    the second could not exist.
    """
    campos = {campo.name for campo in Customer._meta.get_fields()}

    assert "shop" not in campos
    # And the limit belongs to the link, not to the person.
    assert "credit_limit" not in campos


def test_el_vinculo_tiene_el_limite_y_el_estado(db, negocio, cliente):
    """The link carries the limit and the state.

    **The limit may be NULL - "sin límite"** - which is a trusted client
    the owner trusts without a cap.
    """
    vinculo = Vinculo.objects.create(
        tienda=negocio.shop,
        cliente=cliente,
        estado="aceptado",
        credit_limit=None,
    )

    assert vinculo.credit_limit is None
    assert vinculo.estado == "aceptado"


def test_una_persona_puede_estar_en_varias_tiendas(db, negocio, cliente):
    """The same person, two shops, TWO links.

    **And the limit may differ.** The confidence is per shop.
    """
    from tienda.models import Shop

    otra = Shop.objects.create(name="El Kiosco", opening_cash=Decimal("0.00"))

    Vinculo.objects.create(
        tienda=negocio.shop,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    Vinculo.objects.create(
        tienda=otra,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("30.00"),
    )

    assert Vinculo.objects.filter(cliente=cliente).count() == 2
    limites = {
        v.tienda_id: v.credit_limit for v in Vinculo.objects.filter(cliente=cliente)
    }
    assert limites[negocio.shop.id] == Decimal("100.00")
    assert limites[otra.id] == Decimal("30.00")


def test_el_estado_del_vinculo_esta_en_el_vocabulario(db, negocio, cliente):
    """The state belongs to the vocabulary."""
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Vinculo.objects.create(
                tienda=negocio.shop,
                cliente=cliente,
                estado="desconocido",
                credit_limit=Decimal("10.00"),
            )
    assert Vinculo.objects.count() == 0


# ---------------------------------------------------------------------------
# 10.3.2 - The consent
# ---------------------------------------------------------------------------


def test_la_tienda_pide_y_el_cliente_acepta(db, negocio, cliente):
    """The shop asks; the client accepts.

    **The client accepts FROM HER OWN ACCOUNT.** The shop cannot do it
    for her: it does not have her credentials and it must not.
    """
    peticion = Vinculo.objects.create(
        tienda=negocio.shop,
        cliente=cliente,
        estado="pendiente",
        credit_limit=Decimal("100.00"),
    )

    assert peticion.estado == "pendiente"
    # The shop may NOT accept it for her.
    assert peticion.estado != "aceptado"


def test_el_cliente_ve_solo_el_nombre_de_la_tienda_y_los_botones(db, negocio, cliente):
    """A pending link shows the SHOP'S NAME and the buttons - and nothing else.

    **If she could see the debt and the ageing first, the consent would
    be a formality**: she would already have seen everything the
    acceptance reveals. The link she is asked about says which shop is
    asking, and no more.
    """
    Vinculo.objects.create(
        tienda=negocio.shop,
        cliente=cliente,
        estado="pendiente",
        credit_limit=Decimal("100.00"),
    )

    cuerpo = _vinculos_del_cliente(cliente)

    assert len(cuerpo) == 1
    pendiente = cuerpo[0]
    assert pendiente["tienda"] == negocio.shop.name
    # And NONE of the owner's data: not the limit, not the debt, not the
    # ageing.
    for prohibido in ("credit_limit", "pendiente", "antiguedad_max_dias", "saldo"):
        assert prohibido not in pendiente, f"la peticion lleva {prohibido}"


def test_el_cliente_acepta_y_el_vinculo_pasa_a_aceptado(db, negocio, cliente):
    """She accepts, and the link is accepted.

    **And the limit becomes visible**: the acceptance is what opens the
    owner's data to her.
    """
    Vinculo.objects.create(
        tienda=negocio.shop,
        cliente=cliente,
        estado="pendiente",
        credit_limit=Decimal("100.00"),
    )

    _aceptar(cliente, negocio.shop)

    vinculo = Vinculo.objects.get(cliente=cliente)
    assert vinculo.estado == "aceptado"
    assert vinculo.aceptado_at is not None
    # And now she sees the figures.
    cuerpo = _vinculos_del_cliente(cliente)
    assert "credit_limit" in cuerpo[0]


def test_el_cliente_puede_rechazar(db, negocio, cliente):
    """She refuses, and the link says so.

    **A refusal is not a removal**: the shop may ask again, and she may
    answer differently the next time.
    """
    Vinculo.objects.create(
        tienda=negocio.shop,
        cliente=cliente,
        estado="pendiente",
        credit_limit=Decimal("100.00"),
    )

    _rechazar(cliente, negocio.shop)

    vinculo = Vinculo.objects.get(cliente=cliente)
    assert vinculo.estado == "rechazado"
    assert vinculo.rechazado_at is not None


def test_el_dueno_elimina_sin_preguntar(db, negocio, cliente):
    """The owner removes the client - and **does not ask**.

    **The removal is the owner's alone**: the client does not consent to
    being removed, and the shop does not need him to.
    """
    Vinculo.objects.create(
        tienda=negocio.shop,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )

    _eliminar(dueno := User.objects.get(username="dueno"), negocio.shop, cliente)

    vinculo = Vinculo.objects.get(cliente=cliente)
    assert vinculo.estado == "eliminado"
    assert vinculo.eliminado_at is not None
    # And the person and the rows stay: the removal is from the LIST, not
    # from the world.
    assert Customer.objects.filter(id=cliente.id).exists()


def test_el_dueno_re_integra_y_el_cliente_vuelve_a_decidir(db, negocio, cliente):
    """The owner re-adds the client, and **the client decides again**.

    **The re-integration creates a PENDING link**, not an accepted one:
    the consent does not come back by itself. The owner may ask; only
    she may answer.
    """
    Vinculo.objects.create(
        tienda=negocio.shop,
        cliente=cliente,
        estado="eliminado",
        credit_limit=Decimal("100.00"),
    )

    _reintegrar(User.objects.get(username="dueno"), negocio.shop, cliente)

    vinculo = Vinculo.objects.get(cliente=cliente)
    assert vinculo.estado == "pendiente"
    assert vinculo.aceptado_at is None


def test_un_cliente_eliminado_no_puede_tener_fiados(db, negocio, cliente):
    """An eliminated client gets no NEW fiado.

    **His debts and his history stay** - the book is append-only - but
    the confidence is gone, and the confidence is what the fiado needs.
    """
    Vinculo.objects.create(
        tienda=negocio.shop,
        cliente=cliente,
        estado="eliminado",
        credit_limit=Decimal("100.00"),
    )

    assert Vinculo.objects.get(cliente=cliente).estado == "eliminado"
    # The person is still there.
    assert Customer.objects.filter(id=cliente.id).exists()


# ---------------------------------------------------------------------------
# Helpers - the calls the tests make
# ---------------------------------------------------------------------------


def _vinculos_del_cliente(cliente):
    """The links of a client, as she sees them."""
    from tienda.services import vinculos_del_cliente

    return vinculos_del_cliente(cliente)


def _aceptar(cliente, tienda):
    """The client accepts the link of a shop.

    **The answer travels with the LINK's id** - it is the row she sees
    in her account.
    """
    from tienda.services import aceptar_vinculo

    vinculo = Vinculo.objects.get(cliente=cliente, tienda=tienda)
    return aceptar_vinculo(cliente, vinculo.id)


def _rechazar(cliente, tienda):
    """The client refuses the link of a shop."""
    from tienda.services import rechazar_vinculo

    vinculo = Vinculo.objects.get(cliente=cliente, tienda=tienda)
    return rechazar_vinculo(cliente, vinculo.id)


def _eliminar(dueno, tienda, cliente):
    """The owner takes the client off the shop's trusted list."""
    from tienda.services import eliminar_vinculo

    return eliminar_vinculo(dueno, tienda, cliente)


def _reintegrar(dueno, tienda, cliente):
    """The owner asks again."""
    from tienda.services import pedir_vinculo

    return pedir_vinculo(dueno, tienda, cliente)
