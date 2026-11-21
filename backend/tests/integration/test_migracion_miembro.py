"""The DATA migration of the Slice 10.2: the staff become memberships.

**The role lives in the relation, and not in a global group.** Until now
the role was the Django group and `Shop.usuarios` said only who
belonged to which shop - and a group said nothing about which shop it
belonged to, so one shop's `dependiente` was a `dependiente` in every
shop.

This converts what exists into what the model says. The test runs the
migration's own function against a database in the OLD state, and
asserts what it produced.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.db import connection

from tienda.models import MiembroDeTienda, PerfilTienda, Shop


def _migrar():
    """The migration's own data function, against the current database."""
    import importlib

    from django.apps import apps

    mod = importlib.import_module("tienda.migrations.0004_miembro_de_tienda")
    mod.Shop_usuarios_a_membresias(apps, connection)


@pytest.mark.django_db
def test_la_migracion_convierte_el_personal_en_membresias():
    """The staff of a shop become memberships, with the role they had.

    The role came from the Django group and the shop from
    `Shop.usuarios`. The membership says both - the person AND the
    business - and that is what makes the role per shop.
    """
    dueno = User.objects.create_user(username="dueno", password="x")
    dependiente = User.objects.create_user(username="dependiente", password="x")
    dueno.groups.add(Group.objects.create(name="dueno"))
    dependiente.groups.add(Group.objects.create(name="dependiente"))

    tienda = Shop.objects.create(
        name="Tienda de prueba", opening_cash=Decimal("150.00")
    )
    tienda.usuarios.add(dueno, dependiente)

    _migrar()

    membresias = {
        (m.user.username, m.rol): m for m in MiembroDeTienda.objects.all()
    }

    assert ("dueno", "dueno") in membresias
    assert ("dependiente", "dependiente") in membresias

    # And the two name the SAME business: the shop's.
    negocios = list(PerfilTienda.objects.filter(shop=tienda))
    assert len(negocios) == 1
    assert membresias[("dueno", "dueno")].perfil_tienda_id == negocios[0].id
    assert (
        membresias[("dependiente", "dependiente")].perfil_tienda_id
        == negocios[0].id
    )

    # The business belongs to the owner, and names the shop.
    assert negocios[0].user_id == dueno.id
    assert negocios[0].shop_id == tienda.id


@pytest.mark.django_db
def test_la_migracion_crea_el_negocio_si_no_existe():
    """The business is CREATED when it does not exist.

    A shop that has staff has a business, and the membership names it:
    without the business the membership would have nothing to point at.
    """
    dueno = User.objects.create_user(username="dueno", password="x")
    dueno.groups.add(Group.objects.create(name="dueno"))

    tienda = Shop.objects.create(
        name="Tienda de prueba", opening_cash=Decimal("150.00")
    )
    tienda.usuarios.add(dueno)

    assert PerfilTienda.objects.count() == 0

    _migrar()

    assert PerfilTienda.objects.count() == 1
    negocio = PerfilTienda.objects.get()
    assert negocio.user_id == dueno.id
    assert negocio.shop_id == tienda.id
    assert MiembroDeTienda.objects.count() == 1


@pytest.mark.django_db
def test_un_usuario_en_dos_tiendas_tiene_dos_membresias():
    """The same person in two shops has TWO memberships.

    **And the role may differ.** The group could never say that: a
    group is global, so it made the person the same role in both shops.
    """
    dueno = User.objects.create_user(username="dueno", password="x")
    ayudante = User.objects.create_user(username="ayudante", password="x")
    ayudante.groups.add(Group.objects.create(name="dependiente"))

    una = Shop.objects.create(name="Una", opening_cash=Decimal("0.00"))
    otra = Shop.objects.create(name="Otra", opening_cash=Decimal("0.00"))
    una.usuarios.add(dueno, ayudante)
    otra.usuarios.add(dueno, ayudante)

    _migrar()

    membresias = list(MiembroDeTienda.objects.select_related("perfil_tienda"))

    # Two memberships for the SAME person - one per shop.
    del_ayudante = [m for m in membresias if m.user_id == ayudante.id]
    assert len(del_ayudante) == 2
    assert {m.perfil_tienda.shop_id for m in del_ayudante} == {una.id, otra.id}

    # And two for the owner - one per shop.
    del_dueno = [m for m in membresias if m.user_id == dueno.id]
    assert len(del_dueno) == 2
    assert all(m.rol == "dueno" for m in del_dueno)
