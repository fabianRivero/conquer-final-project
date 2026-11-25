"""The Slice 10.4: the ageing is PER SHOP, and the book is per shop too.

**The bug this file pins.** `validar_pago` computed rule 19's bound and
the FIFO allocation **over every shop the person owes in**: it called
`pendiente_de(customer)` and `pendientes_de(customer)` with no shop. The
person became ONE debt across every shop when the 10.3 landed, and the
payment code still read her that way.

So a client who owed 30 in one shop and 20 in another could propose a
50,00 payment at the FIRST shop: rule 19 saw 50,00 of total debt and
allowed it, and the FIFO then allocated part of that payment against
the charges of the SECOND shop - imputations pointing at charges of a
book the payment never entered.

The debt of a shop is the debt of a shop. "She owes 30 here" and "she
owes 20 there" are two facts, and a payment at this counter pays THIS
one.
"""

from __future__ import annotations

from tests.integration.personas import crear_persona


from decimal import Decimal

import pytest

from tests.conftest import membresia

from django.contrib.auth.models import User
from django.utils import timezone

from tienda.models import (
    CargoLinea,
    Confirmacion,
    Customer,
    ImputacionPago,
    LedgerEntry,
    PagoPropuesto,
    PerfilTienda,
    Producto,
    Shop,
    Vinculo,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def owner(db, negocio):
    membresia(negocio, negocio.user, "dueno")
    return negocio.user


@pytest.fixture
def tienda(db, negocio):
    return negocio.shop


@pytest.fixture
def otra_tienda(db):
    """A SECOND shop, with its own owner and its own book.

    The person owes in both, and that is the whole point: one person,
    two shops, two debts.
    """
    dueno = User.objects.create_user(username="dueno2", password="secreta123")
    perfil = PerfilTienda.objects.create(
        user=dueno,
        nombre="Otra tienda",
        direccion="",
        nif="",
        shop=Shop.objects.create(
            name="Otra tienda", opening_cash=Decimal("0.00")
        ),
    )
    membresia(perfil, dueno, "dueno")
    return perfil.shop


@pytest.fixture
def customer(tienda, otra_tienda):
    """A person, and a LINK to EACH shop: she is trusted in both."""
    cliente_usuario, cliente = crear_persona("ana", alias="Ana")
    Vinculo.objects.create(
        tienda=tienda,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    Vinculo.objects.create(
        tienda=otra_tienda,
        cliente=cliente,
        estado="aceptado",
        credit_limit=Decimal("100.00"),
    )
    return cliente


@pytest.fixture
def producto(tienda):
    return Producto.objects.create(
        shop=tienda, nombre="Pan", precio=Decimal("1.00"), unidad="unidad"
    )


@pytest.fixture
def producto_otra(otra_tienda):
    return Producto.objects.create(
        shop=otra_tienda, nombre="Leche", precio=Decimal("1.00"), unidad="unidad"
    )


def _cargo(tienda, customer, owner, producto, *, importe="8.00", when=None):
    momento = when or timezone.now()
    cargo = LedgerEntry.objects.create(
        shop=tienda,
        customer=customer,
        user=owner,
        kind="cargo",
        amount=Decimal(importe),
        occurred_at=momento,
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
        confirmado_en=momento,
        origen="tienda",
        confirmado_por=owner,
    )
    return cargo


# ---------------------------------------------------------------------------
# The bound is the debt of THIS shop
# ---------------------------------------------------------------------------


def test_a_payment_may_not_exceed_the_debt_of_its_own_shop(
    db, owner, tienda, otra_tienda, customer, producto, producto_otra
):
    """Rule 19's bound is the debt of the SHOP, not the person's total.

    The person owes 30,00 in this shop and 20,00 in the other one. A
    payment of 50,00 at THIS counter is larger than the debt it retires:
    the 20,00 of the other shop is not in this book, and this payment
    will not enter that one.

    **Before the fix the payment was ACCEPTED**: the bound was read over
    every shop, and 50,00 was not larger than 50,00.
    """
    _cargo(tienda, customer, owner, producto, importe="30.00")
    _cargo(otra_tienda, customer, owner, producto_otra, importe="20.00")

    propuesta = PagoPropuesto.objects.create(
        shop=tienda,
        customer=customer,
        importe=Decimal("50.00"),
        referencia="",
        estado="pendiente",
        created_at=timezone.now(),
    )

    from tienda import services

    with pytest.raises(services.DomainValidationError) as error:
        services.validar_pago(tienda.id, owner, pago_id=propuesta.id)

    assert error.value.codigo_error == "pago_excede_deuda"

    # And nothing was written: the refusal appends nothing.
    assert LedgerEntry.objects.filter(kind="pago").count() == 0
    assert ImputacionPago.objects.count() == 0


def test_a_payment_within_the_debt_of_its_own_shop_is_accepted(
    db, owner, tienda, otra_tienda, customer, producto, producto_otra
):
    """The bound is not tightened by the OTHER shop's debt.

    She owes 30,00 here and 20,00 there. A payment of 30,00 at THIS
    counter is exactly this shop's debt, and it is allowed - the other
    shop's 20,00 does not make this one's smaller.
    """
    _cargo(tienda, customer, owner, producto, importe="30.00")
    _cargo(otra_tienda, customer, owner, producto_otra, importe="20.00")

    propuesta = PagoPropuesto.objects.create(
        shop=tienda,
        customer=customer,
        importe=Decimal("30.00"),
        referencia="",
        estado="pendiente",
        created_at=timezone.now(),
    )

    from tienda import services

    services.validar_pago(tienda.id, owner, pago_id=propuesta.id)

    pago = LedgerEntry.objects.get(kind="pago")
    assert pago.shop_id == tienda.id
    assert pago.amount == Decimal("30.00")

    # The imputations point at THIS shop's charge, and only at it.
    imputaciones = list(ImputacionPago.objects.all())
    assert len(imputaciones) == 1
    cargo_imputado = LedgerEntry.objects.get(id=imputaciones[0].cargo_id)
    assert cargo_imputado.shop_id == tienda.id
    assert imputaciones[0].importe == Decimal("30.00")

    # The other shop's charge is untouched.
    cargo_ajeno = LedgerEntry.objects.get(
        shop=otra_tienda, kind="cargo"
    )
    assert cargo_ajeno.amount == Decimal("20.00")
    assert ImputacionPago.objects.filter(cargo=cargo_ajeno).count() == 0


def test_the_payment_never_allocates_against_another_shops_charge(
    db, owner, tienda, otra_tienda, customer, producto, producto_otra
):
    """**The imputation is the leak.** It points at a `cargo`, and a
    `cargo` belongs to a shop.

    The other shop's charge is the **OLDER** one, and that is what makes
    the leak visible: the FIFO sorts by date, so the allocation reached
    the other shop's charge FIRST and settled this shop's money against
    a debt that is in another book.

    The `ImputacionPago` row says so permanently, in a book that is
    append-only: shop T1's payment would appear to retire shop T2's
    debt, and no later correction could erase the row.

    This is the assertion that pins the allocation itself, and not only
    the bound that precedes it.
    """
    _cargo(tienda, customer, owner, producto, importe="5.00")
    _cargo(
        otra_tienda,
        customer,
        owner,
        producto_otra,
        importe="30.00",
        when=timezone.now() - timezone.timedelta(days=10),
    )

    propuesta = PagoPropuesto.objects.create(
        shop=tienda,
        customer=customer,
        importe=Decimal("5.00"),
        referencia="",
        estado="pendiente",
        created_at=timezone.now(),
    )

    from tienda import services

    services.validar_pago(tienda.id, owner, pago_id=propuesta.id)

    cargo_ajeno = LedgerEntry.objects.get(shop=otra_tienda, kind="cargo")
    assert ImputacionPago.objects.filter(cargo=cargo_ajeno).count() == 0

    # Every imputation of this payment points at a charge of ITS shop.
    pago = LedgerEntry.objects.get(kind="pago")
    for imputacion in ImputacionPago.objects.filter(pago=pago):
        cargo = LedgerEntry.objects.get(id=imputacion.cargo_id)
        assert cargo.shop_id == tienda.id
