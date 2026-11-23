"""The seed and its contract - tasks 7.1 and 7.2.

The seed is the demo dataset: one shop, its users, a catalogue, a
customer with a credential, a confirmed charge, a pending proposal and a
cancelled one. It exists so the whole application can be demonstrated
without typing anything.

The contract, and it is a contract and not a convenience:

* **It is idempotent.** Run it twice and the dataset is unchanged. The
  seed deletes the demo shop and recreates it, and that deletion is the
  ONLY deletion in the codebase - confined to `is_demo=True`.
* **It is one transaction.** Either the whole dataset lands or none of
  it does.
* **It obeys the model's own rules.** Every seeded `pago` is smaller than
  the debt it retires, so the seeded book is a LEGAL book and not an
  example of one (rule 19, ADR-26).

What the seed must produce, from design 18.2 and task 7.1:

* the accounts `dueno@tienda.test` and `dependiente@tienda.test`, in the
  `dueno` and `dependiente` groups;
* a catalogue of about thirty `Producto` rows, including one at 1,20;
* `CargoLinea` rows with their `precio_unitario` snapshots;
* one hashed `codigo` per seeded customer, one active each;
* **one confirmed charge** with its `Confirmacion(confirmado)` and its
  lines;
* **one prepared proposal** (`pendiente`), so the shop's screen is
  demonstrable and the outstanding shows nothing for it;
* **one cancelled proposal**.

A note on how these tests assert. The seeded figures are checked by
COUNTING and by reading the rows, not by a status code: there is no
endpoint here to answer. And the idempotency test compares the dataset
before and after, because "the seed ran twice" is a claim about the
DATA and not about the command's exit code.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import connection

from tienda.api import client_auth
from tienda.models import (
    CargoLinea,
    Confirmacion,
    Customer,
    CustomerCodigo,
    FiadoPropuesto,
    LedgerEntry,
    PagoPropuesto,
    Producto,
    PropuestaLinea,
    Shop,
    Vinculo,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded(db):
    """The seed, run once."""
    call_command("seed_demo", verbosity=0)
    return Shop.objects.get(is_demo=True)


def _estado():
    """A snapshot of the seeded dataset, as comparable plain values.

    The idempotency test compares the dataset before and after, so the
    snapshot must be about the DATA and not about the rows' identity: a
    delete-and-recreate seed produces different primary keys and the
    same dataset.
    """
    return {
        "usuarios": sorted(u.username for u in User.objects.all()),
        "grupos": sorted(
            (u.username, g.name)
            for u in User.objects.all()
            for g in u.groups.all()
        ),
        "tiendas": sorted(
            (s.name, s.is_demo, str(s.opening_cash))
            for s in Shop.objects.all()
        ),
        "clientes": sorted(
            # The limit belongs to the LINK: the owner's confidence, and
            # the owner has it in the shop.
            (
                v.cliente.alias,
                str(v.credit_limit) if v.credit_limit is not None else None,
            )
            for v in Vinculo.objects.select_related("cliente")
        ),
        "productos": sorted(
            (p.nombre, str(p.precio), p.unidad, p.activo)
            for p in Producto.objects.all()
        ),
        "codigos": sorted(
            # The PREFIX is not part of the comparison: it is six
            # random symbols of the credential, so a reseed produces a
            # different one. What the contract says is that the seed
            # leaves ONE active credential per customer, and that the
            # plaintext is never stored - so the comparison is on the
            # shape and not on the secret.
            (c.customer.alias, c.revoked_at is not None)
            for c in CustomerCodigo.objects.all()
        ),
        "cargos": sorted(
            (
                c.customer.alias,
                c.kind,
                str(c.amount),
                c.confirmaciones.filter(estado="confirmado").count(),
            )
            for c in LedgerEntry.objects.all()
        ),
        "lineas": sorted(
            (l.cargo.customer.alias, l.producto.nombre, str(l.cantidad),
             str(l.precio_unitario), str(l.total))
            for l in CargoLinea.objects.all()
        ),
        "propuestas": sorted(
            (p.customer.alias, p.estado, str(p.total), p.confirmed_at is not None,
             p.canceled_at is not None)
            for p in FiadoPropuesto.objects.all()
        ),
        "lineas_propuesta": sorted(
            (l.propuesta.customer.alias, l.producto.nombre, str(l.cantidad),
             str(l.precio_unitario), str(l.total))
            for l in PropuestaLinea.objects.all()
        ),
    }


# ---------------------------------------------------------------------------
# 7.1 - The dataset
# ---------------------------------------------------------------------------


def test_the_seed_creates_one_demo_shop(seeded):
    """The dataset hangs off ONE shop, flagged `is_demo=True`."""
    assert seeded.is_demo is True
    assert seeded.name
    assert Shop.objects.filter(is_demo=True).count() == 1


def test_the_seed_creates_the_two_accounts(seeded):
    """CAC-08: one account per shop role is seeded.

    The accounts are `dueno@tienda.test` and `dependiente@tienda.test`,
    and **the role lives in the MEMBERSHIP** - the relation with the
    business - and not in a global Django group. A `dependiente` of one
    shop is a `dependiente` of that shop and of no other.
    """
    from tienda.models import MiembroDeTienda

    dueno = User.objects.get(username="dueno")
    assert dueno.email == "dueno@tienda.test"

    dependiente = User.objects.get(username="dependiente")
    assert dependiente.email == "dependiente@tienda.test"

    # The roles, in the relation.
    membresias = {
        (m.user.username, m.rol)
        for m in MiembroDeTienda.objects.select_related("user")
    }
    assert ("dueno", "dueno") in membresias
    assert ("dependiente", "dependiente") in membresias

    # And neither of them is in the other role.
    assert (
        MiembroDeTienda.objects.filter(user=dueno, rol="dependiente").count() == 0
    )
    assert (
        MiembroDeTienda.objects.filter(user=dependiente, rol="dueno").count() == 0
    )


def test_the_seed_creates_the_catalogue(seeded):
    """PC-03: the catalogue exists, and the seeded product is at 1,20.

    About thirty products, re-runnable without duplicating a row.
    """
    productos = Producto.objects.filter(shop=seeded)
    assert productos.count() >= 30

    pan = productos.get(nombre="Pan")
    assert pan.precio == Decimal("1.20")
    assert pan.activo is True


def test_the_seed_creates_a_customer_with_a_credential(seeded):
    """CAC-08: one credential per seeded customer, hashed, one active.

    The plaintext never touches a row: only the digest and the prefix.
    """
    cliente = Vinculo.objects.get(tienda=seeded).cliente

    codigos = CustomerCodigo.objects.filter(customer=cliente)
    assert codigos.count() == 1
    codigo = codigos.get()
    assert codigo.revoked_at is None
    assert codigo.prefix
    assert codigo.codigo_hash

    # The stored form is a HASH and not the credential: it does not
    # verify against itself as a plaintext would, and it does not look
    # like the alphabet's symbols. The check that matters is the one
    # that says the hash is not the value - so the probe is that
    # storing the plaintext changes the answer.
    assert codigo.codigo_hash != codigo.prefix
    assert not all(
        c in client_auth.ALFABETO for c in codigo.codigo_hash[:20]
    ), "the stored form looks like the plaintext"

    # And the stored digest verifies a credential, not itself.
    assert not client_auth.hash_presentado(codigo.codigo_hash) == codigo.codigo_hash


def test_the_seed_creates_one_confirmed_charge_with_its_lines(seeded):
    """CC-01: one confirmed charge, with its confirmation and its lines.

    The charge carries its `CargoLinea` rows with the `precio_unitario`
    snapshot, and the `Confirmacion(confirmado)` that makes it debt.
    """
    cargos = LedgerEntry.objects.filter(shop=seeded, kind="cargo")
    assert cargos.count() == 1
    cargo = cargos.get()

    assert cargo.confirmaciones.count() == 1
    assert cargo.confirmaciones.get().estado == "confirmado"

    lineas = CargoLinea.objects.filter(cargo=cargo)
    assert lineas.count() >= 1
    for linea in lineas:
        assert linea.precio_unitario >= 0
        assert linea.total == linea.cantidad * linea.precio_unitario


def test_the_seed_creates_one_pending_and_one_cancelled_proposal(seeded):
    """CC-01, CC-03: one prepared and one cancelled proposal.

    The pending one is what makes the shop's screen demonstrable, and
    the outstanding shows NOTHING for it: a proposal is a request, not a
    debt.
    """
    propuestas = FiadoPropuesto.objects.filter(shop=seeded)
    assert propuestas.count() == 2

    pendiente = propuestas.get(estado="pendiente")
    assert pendiente.confirmed_at is None
    assert pendiente.canceled_at is None
    assert PropuestaLinea.objects.filter(propuesta=pendiente).count() >= 1

    cancelada = propuestas.get(estado="cancelado")
    assert cancelada.canceled_at is not None
    assert cancelada.confirmed_at is None


def test_the_pending_proposal_moves_no_outstanding(seeded):
    """CC-01: a pending proposal is not debt.

    The outstanding is the confirmed charge and nothing else.

    **The companion matters.** The pending proposal has to EXIST for the
    assertion to mean anything: a dataset with no proposal at all also
    has an outstanding that the proposal did not move. The two
    assertions together say what the test means.
    """
    from tienda.services import estado_de

    cliente = Vinculo.objects.get(tienda=seeded).cliente
    cargo = LedgerEntry.objects.filter(shop=seeded, kind="cargo").get()
    pendiente = FiadoPropuesto.objects.get(shop=seeded, estado="pendiente")

    # The proposal is there, and it is the shop's screen waiting.
    assert pendiente.customer_id == cliente.id
    assert PropuestaLinea.objects.filter(propuesta=pendiente).count() >= 1

    # And the outstanding is the charge and not the proposal.
    assert estado_de(cliente).total == cargo.amount
    assert cargo.amount > Decimal("0.00")


def test_the_seeded_book_is_legal(seeded):
    """Rule 19, ADR-26: no customer holds a credit.

    Every seeded `pago` is smaller than the debt it retires, so the
    seeded dataset is a legal book and not an example of one.

    **The state is per shop**: the person belongs to no shop, and the
    debt that holds her is the one of the shop she is trusted in.
    """
    from tienda.services import estado_de

    for vinculo in Vinculo.objects.filter(tienda=seeded):
        assert estado_de(vinculo.cliente, tienda=seeded).total >= Decimal("0.00")


# ---------------------------------------------------------------------------
# 7.1 - The idempotency
# ---------------------------------------------------------------------------


def test_the_seed_run_twice_leaves_the_dataset_unchanged(db):
    """The seed is idempotent.

    Run twice and the dataset is the same. The comparison is on the DATA
    and not on the rows' identity: the seed deletes the demo shop and
    recreates it, so the primary keys differ while the dataset does not.
    """
    call_command("seed_demo", verbosity=0)
    antes = _estado()

    call_command("seed_demo", verbosity=0)
    despues = _estado()

    assert despues == antes


def test_the_seed_does_not_duplicate_the_catalogue(db):
    """About thirty products, re-runnable without duplicating a row."""
    call_command("seed_demo", verbosity=0)
    primera = Producto.objects.count()

    call_command("seed_demo", verbosity=0)

    assert Producto.objects.count() == primera


def test_the_seed_does_not_duplicate_the_accounts(db):
    """The users go through `get_or_create(username=...)`."""
    call_command("seed_demo", verbosity=0)

    call_command("seed_demo", verbosity=0)

    assert User.objects.filter(username="dueno").count() == 1
    assert User.objects.filter(username="dependiente").count() == 1


def test_the_seed_does_not_touch_a_real_shop(db):
    """The deletion is confined to `is_demo=True`.

    It is the ONLY deletion in the codebase, and it must not reach a
    shop that is not the demo one.
    """
    real = Shop.objects.create(name="Tienda real", opening_cash=Decimal("10.00"))
    cliente = Customer.objects.create(alias="Real")
    Vinculo.objects.create(
        tienda=real,
        cliente=cliente,
        estado="aceptado",
    )

    call_command("seed_demo", verbosity=0)

    assert Shop.objects.filter(id=real.id).exists()
    assert Customer.objects.filter(id=cliente.id).exists()
    assert Customer.objects.filter(alias="Real").count() == 1


def test_the_seed_is_one_transaction(db):
    """The seed is one `transaction.atomic()`.

    A seed that leaves half a dataset behind is worse than one that
    leaves none.
    """
    from django.db import transaction as tx

    calls = []
    original = tx.atomic

    def espia(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    tx.atomic = espia
    try:
        call_command("seed_demo", verbosity=0)
    finally:
        tx.atomic = original

    assert len(calls) >= 1
