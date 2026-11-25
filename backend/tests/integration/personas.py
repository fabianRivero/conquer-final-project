"""Las fixtures de la persona, para las pruebas que ya no usan credencial.

**La credencial se fue.** Las pruebas que montaban un `CustomerCodigo` y
un header `X-Codigo` ahora **montan una cuenta y una sesion de
persona**: es el mismo mecanismo que usa la superficie de verdad.

**La persona existe antes que la ficha.** El registro crea la cuenta Y
la ficha (`Customer.user` es NOT NULL), asi que el fixture hace las dos
cosas en la misma transaccion - que es lo que hace la ruta de verdad.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from django.contrib.auth.models import User
from django.utils import timezone

from tienda.models import Customer, PerfilCliente, Vinculo


def crear_persona(
    username="ana.perez",
    *,
    password="secreta123",
    alias=None,
    shop=None,
    limite=Decimal("100.00"),
    vinculo="aceptado",
    dueno=None,
):
    """La persona: su cuenta, su perfil de cliente y su ficha.

    **La cuenta y la ficha nacen juntas**, como en la ruta de registro:
    el `Customer.user` es NOT NULL, asi que una ficha sin persona detras
    no es una persona.

    **El vinculo nace `aceptado`** o `pendiente`, segun lo que pida la
    prueba. El dueno lo crea con `pendiente` y ella lo acepta; una
    prueba que necesita a alguien de confianza lo pide `aceptado` de
    entrada, porque lo que prueba es OTRA cosa.
    """
    usuario = User.objects.create_user(
        username=username,
        password=password,
        last_login=timezone.now(),
    )
    PerfilCliente.objects.create(user=usuario)

    cliente = Customer.objects.create(
        user=usuario,
        alias=alias or username,
        created_by=dueno,
    )

    if shop is not None:
        Vinculo.objects.create(
            tienda=shop,
            cliente=cliente,
            estado=vinculo,
            credit_limit=limite,
            pedido_at=timezone.now(),
            **(
                {"aceptado_at": timezone.now()}
                if vinculo == "aceptado"
                else {}
            ),
        )

    return usuario, cliente


@pytest.fixture
def persona(db):
    """La persona y su ficha, sin vinculo con ninguna tienda."""
    return crear_persona()


@pytest.fixture
def persona_de_la_tienda(db, negocio):
    """La persona, con su vinculo ACEPTADO en la tienda del `negocio`.

    Es el caso general: una clienta de confianza con su cuenta.
    """
    usuario, cliente = crear_persona(
        shop=negocio.shop,
        dueno=negocio.user,
    )
    return usuario, cliente
