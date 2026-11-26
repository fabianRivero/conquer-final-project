"""The person's own figures — and the owner's, which she never sees.

**The owner's decision of '2026-11-25'**: the implementation wins. The
person MAY see her own per-shop figures on an ACCEPTED link — the
`credit_limit` the owner gave her there, and the age of her oldest debt
there. The other seven staff-only figures never reach her, and neither
does another shop's limit.

**The guarantee lives here, on the routes that actually run.** The
schema that used to carry CAC-10 (`EstadoClienteSerializer`) belongs to
the retired credential surface: no live route renders it, so a test that
only read it protected nothing. The person reads hand-built rows, and
the guarantee belongs where the rows are.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tests.integration.personas import crear_persona
from tests.walk import (
    FIGURAS_PROPIAS_DE_LA_PERSONA,
    TOKENS_DE_CLIENTE,
    afirmar_sin_fuga,
)

from tienda.models import LedgerEntry, Shop, Vinculo

pytestmark = pytest.mark.integration


@pytest.fixture
def persona_con_dos_tiendas(db, negocio):
    """A person with TWO shops: one that trusts her, one that is asking.

    **The two links are the two halves of the rule**: the accepted one
    may show her own figures, and the pending one may show nothing.
    """
    usuario, cliente = crear_persona(
        username="ana.perez",
        alias="Ana",
        shop=negocio.shop,
        dueno=negocio.user,
    )
    otra = Shop.objects.create(
        name="Tienda de al lado", opening_cash=Decimal("150.00")
    )
    Vinculo.objects.create(
        tienda=otra,
        cliente=cliente,
        estado="pendiente",
        credit_limit=Decimal("25.00"),
        pedido_at=timezone.now(),
        pedido_por=negocio.user,
    )
    # A debt of FORTY days in the shop that trusts her: the ageing has to
    # be a real number, not a zero that every test would pass.
    LedgerEntry.objects.create(
        shop=negocio.shop,
        customer=cliente,
        user=negocio.user,
        kind="cargo",
        amount=Decimal("30.00"),
        occurred_at=timezone.now() - timedelta(days=40),
    )
    return usuario, cliente, negocio.shop, otra


@pytest.fixture
def api_persona(persona_con_dos_tiendas):
    """A client whose session is the PERSON's."""
    usuario, _cliente, _tienda, _otra = persona_con_dos_tiendas
    api = APIClient()
    api.force_authenticate(usuario)
    return api


def test_las_rutas_de_la_persona_no_traen_las_cifras_del_dueno(api_persona):
    """CAC-10, asserted on the routes that actually run.

    **The seven never reach her**, on any route of hers: not the cash,
    not the position, not the buckets, not the suspension reason, and
    never the credential.
    """
    for nombre, url in (
        ("los vinculos", reverse("api:cuenta_vinculos")),
        ("los fiados", reverse("api:cuenta_fiados")),
        ("los cargos", reverse("api:cuenta_cargos")),
    ):
        respuesta = api_persona.get(url)

        assert respuesta.status_code == 200, nombre
        afirmar_sin_fuga(respuesta.json(), TOKENS_DE_CLIENTE, nombre)


def test_sus_cifras_propias_solo_en_el_vinculo_aceptado(
    api_persona, persona_con_dos_tiendas
):
    """Her own figures are hers, per shop, and only on an accepted link.

    **The accepted link shows the limit the owner gave her in THAT
    shop, what she owes there, and how old her oldest debt there is.**

    The pending link shows the shop's name and nothing else: if she
    could see the figures first, the consent would be a formality — she
    would already have seen everything the acceptance reveals.
    """
    _usuario, _cliente, _tienda, _otra = persona_con_dos_tiendas

    cuerpo = api_persona.get(reverse("api:cuenta_vinculos")).json()

    aceptados = [v for v in cuerpo if v["estado"] == "aceptado"]
    pendientes = [v for v in cuerpo if v["estado"] == "pendiente"]
    assert len(aceptados) == 1, cuerpo
    assert len(pendientes) == 1, cuerpo

    assert Decimal(aceptados[0]["credit_limit"]) == Decimal("100.00")
    assert aceptados[0]["antiguedad_max_dias"] == 40
    assert Decimal(aceptados[0]["pendiente"]) == Decimal("30.00")

    for figura in FIGURAS_PROPIAS_DE_LA_PERSONA:
        assert figura not in pendientes[0], figura


def test_el_limite_que_ve_es_el_suyo(api_persona, persona_con_dos_tiendas):
    """The number is the one of HER link, in THIS shop.

    **The limit belongs to the link, and the link names the shop**: a
    person may have 100 in one shop and 25 in another, and those are two
    facts — an account that mixed them would be lying about both.
    """
    _usuario, cliente, _tienda, _otra = persona_con_dos_tiendas

    cuerpo = api_persona.get(reverse("api:cuenta_vinculos")).json()

    for fila in cuerpo:
        vinculo = Vinculo.objects.get(cliente=cliente, tienda__name=fila["tienda"])
        if vinculo.estado == "aceptado":
            assert Decimal(fila["credit_limit"]) == vinculo.credit_limit
        else:
            assert "credit_limit" not in fila
