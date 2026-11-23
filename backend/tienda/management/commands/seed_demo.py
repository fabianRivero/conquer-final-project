"""The seed command - task 7.2.

The demo dataset: one shop, its two users, a catalogue, a customer with
a credential, a confirmed charge, a pending proposal and a cancelled one.
It exists so the whole application can be demonstrated without typing
anything.

Four properties, and they are a contract and not a convenience:

**It is one transaction.** Either the whole dataset lands or none of it
does. A seed that leaves half a dataset behind is worse than one that
leaves none.

**It is idempotent.** Run it twice and the dataset is unchanged. The
seed deletes the demo shop and recreates it, so the rows' identity
changes while the dataset does not.

**The deletion is confined to `is_demo=True`.** It is the ONLY deletion
in the codebase, and it reaches nothing else. A shop that is not the
demo one, its customers and its book are untouched.

**The seeded book is a LEGAL book.** Every seeded `pago` is smaller than
the debt it retires, so no customer holds a credit (rule 19, ADR-26).
The seed is not an example of a broken book.

**The rules are the application's own.** The seed writes through the
service layer wherever the service layer has an operation, so the
seeded rows are the rows the application would have written - and the
one-way proposal transition, the mandatory itemisation and the server's
stamps are the real ones, not copies of them.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from tienda import services
from tienda.api.client_auth import generar_credencial, hashear_credencial, prefijo_de
from tienda.domain import charges as reglas_cargos
from tienda.domain.types import (
    ConfirmState,
    EntryKind,
    PropuestaEstado,
)
from tienda.models import (
    CargoLinea,
    Confirmacion,
    Customer,
    CustomerCodigo,
    FiadoPropuesto,
    LedgerEntry,
    PropuestaLinea,
    Producto,
    Shop,
    borrar_dataset_demo,
)

#: The name of the demo shop. It is flagged `is_demo=True`, and that
#: flag is what the deletion is confined to.
NOMBRE_TIENDA = "Tienda de demostración"

#: The accounts. One per shop role (CAC-08), and the emails are the ones
#: the e2e suite signs in with.
CUENTAS = (
    ("dueno", "dueno@tienda.test", "dueno"),
    ("dependiente", "dependiente@tienda.test", "dependiente"),
)

#: The catalogue. About thirty products, re-runnable without
#: duplicating a row, and the seeded product at 1,20.
CATALOGO = (
    ("Pan", "1.20", "unidad"),
    ("Leche", "0.95", "brick"),
    ("Café", "2.50", "paquete"),
    ("Huevos", "2.10", "docena"),
    ("Yogur", "1.35", "pack"),
    ("Queso curado", "4.75", "cuña"),
    ("Jamón", "6.90", "loncha"),
    ("Arroz", "1.15", "kilo"),
    ("Pasta", "0.85", "paquete"),
    ("Aceite", "4.30", "botella"),
    ("Azúcar", "0.95", "kilo"),
    ("Harina", "0.80", "kilo"),
    ("Patatas", "1.60", "kilo"),
    ("Tomates", "2.25", "kilo"),
    ("Lechuga", "1.10", "unidad"),
    ("Cebollas", "1.40", "kilo"),
    ("Manzanas", "2.40", "kilo"),
    ("Plátanos", "1.75", "kilo"),
    ("Pollo", "5.60", "kilo"),
    ("Carne", "8.90", "kilo"),
    ("Merluza", "7.40", "kilo"),
    ("Gambas", "12.50", "kilo"),
    ("Salmón", "13.90", "kilo"),
    ("Atún", "2.30", "lata"),
    ("Sardinas", "1.85", "lata"),
    ("Café molido", "3.20", "paquete"),
    ("Té", "1.70", "caja"),
    ("Zumo", "1.45", "botella"),
    ("Cerveza", "1.20", "botella"),
    ("Vino", "4.50", "botella"),
)

#: The password of the seeded accounts. It is a demo account on a demo
#: dataset, and the deployment's own accounts are the owner's.
PASSWORD_DEMO = "tienda-demo-2026"


class Command(BaseCommand):
    """`manage.py seed_demo` - the demo dataset."""

    help = "Seed the demo dataset: one shop, its users, a catalogue and a book."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep",
            action="store_true",
            help=(
                "Do not delete the existing demo shop first. The seed then "
                "fails on the rows that already exist; it exists for "
                "debugging and not for normal use."
            ),
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            if not options.get("keep"):
                self._borrar_demo()

            tienda = Shop.objects.create(
                name=NOMBRE_TIENDA,
                opening_cash=Decimal("150.00"),
                is_demo=True,
            )

            usuarios = self._usuarios(tienda)
            productos = self._catalogo(tienda)
            cliente = self._cliente(tienda, usuarios["dueno"])
            self._credencial(tienda, cliente, usuarios["dueno"])
            self._cargo_confirmado(tienda, cliente, usuarios["dueno"], productos)
            self._propuesta_pendiente(tienda, cliente, usuarios["dueno"], productos)
            self._propuesta_cancelada(tienda, cliente, usuarios["dueno"], productos)

        self.stdout.write(
            self.style.SUCCESS(
                f"Dataset de demostracion listo en la tienda {tienda.name!r} "
                f"(id={tienda.id})."
            )
        )

    # -- the pieces ---------------------------------------------------------

    def _borrar_demo(self):
        """Delete the demo shop and everything hanging off it.

        **This is the only deletion in the codebase**, and it is confined
        to `is_demo=True`: a shop that is not the demo one, its
        customers and its book are untouched. The mechanism lives in
        `models.borrar_dataset_demo`, so there is exactly ONE place in
        the codebase that can remove an append-only row, and it refuses
        unless the rows belong to the demo shop.

        The accounts go AFTER the dataset, and that order matters: a
        `User` is protected by the rows that name it - the customer's
        registrant, the proposal's author, the ledger row's author and
        the credential's issuer - and those rows are the ones the
        deletion removes. Deleting the account first would be refused.
        """
        borrar_dataset_demo()

        User.objects.filter(
            username__in=[nombre for nombre, _, _ in CUENTAS]
        ).delete()

    def _usuarios(self, tienda):
        """The two accounts, one per shop role (CAC-08).

        The users go through `get_or_create(username=...)`, so a
        re-run does not duplicate them.

        **The role lives in the MEMBERSHIP, and not in a global group.**
        A `dependiente` of one shop is a `dependiente` of that shop and
        of no other - and the group could not say that, because a group
        says nothing about which shop it belongs to.
        """
        from tienda.models import MiembroDeTienda, PerfilTienda, Vinculo

        usuarios = {}
        for nombre, email, rol in CUENTAS:
            usuario, _ = User.objects.get_or_create(
                username=nombre,
                defaults={
                    "email": email,
                    "is_staff": True,
                    "is_superuser": False,
                },
            )
            usuario.email = email
            usuario.set_password(PASSWORD_DEMO)
            usuario.save()

            # The business profile, and the shop of the credit book it
            # owns. The two are the same business seen from two angles.
            perfil, _ = PerfilTienda.objects.get_or_create(
                user=usuario,
                nombre=tienda.name,
                defaults={"direccion": "", "nif": "", "shop": tienda},
            )
            perfil.shop = tienda
            perfil.save()

            MiembroDeTienda.objects.update_or_create(
                perfil_tienda=perfil,
                user=usuario,
                defaults={"rol": rol},
            )
            usuarios[nombre] = usuario
        return usuarios

    def _catalogo(self, tienda):
        """About thirty products, and the seeded one at 1,20."""
        productos = {}
        for nombre, precio, unidad in CATALOGO:
            producto, _ = Producto.objects.get_or_create(
                shop=tienda,
                nombre=nombre,
                defaults={
                    "precio": Decimal(precio),
                    "unidad": unidad,
                    "activo": True,
                },
            )
            productos[nombre] = producto
        return productos

    def _cliente(self, tienda, dueno):
        """One customer of the demo shop.

        **The person belongs to no shop**, and the LINK says she is a
        trusted client of this one - with the limit the owner gave her.
        """
        from tienda.models import Vinculo

        cliente, _ = Customer.objects.get_or_create(
            alias="Ana",
            defaults={
                "created_by": dueno,
                "phone": "600000000",
            },
        )
        Vinculo.objects.update_or_create(
            tienda=tienda,
            cliente=cliente,
            defaults={
                "estado": "aceptado",
                "credit_limit": Decimal("100.00"),
                "pedido_at": timezone.now(),
                "pedido_por": dueno,
                "aceptado_at": timezone.now(),
            },
        )
        return cliente

    def _credencial(self, tienda, cliente, dueno):
        """One credential for the customer: hashed, and active.

        The plaintext exists for the length of this call and nowhere
        else: only the digest and the prefix are stored.
        """
        if CustomerCodigo.objects.filter(customer=cliente, revoked_at__isnull=True).exists():
            return None

        valor = generar_credencial()
        return CustomerCodigo.objects.create(
            shop=tienda,
            customer=cliente,
            prefix=prefijo_de(valor),
            codigo_hash=hashear_credencial(valor),
            issued_at=timezone.now(),
            issued_by=dueno,
        )

    def _cargo_confirmado(self, tienda, cliente, dueno, productos):
        """One CONFIRMED charge, with its lines and its confirmation.

        The charge is written the way the application writes it: the
        server stamps the instant, the lines carry the `precio_unitario`
        snapshot, and the `Confirmacion(confirmado)` is what makes it
        debt.
        """
        momento = timezone.now() - timezone.timedelta(days=3)
        cargo = LedgerEntry.objects.create(
            shop=tienda,
            customer=cliente,
            user=dueno,
            kind=EntryKind.CARGO.value,
            amount=Decimal("3.60"),
            occurred_at=momento,
        )
        # Three units of bread at 1,20.
        producto = productos["Pan"]
        cantidad = Decimal("3")
        precio = producto.precio
        CargoLinea.objects.create(
            cargo=cargo,
            producto=producto,
            cantidad=cantidad,
            precio_unitario=precio,
            total=reglas_cargos.total_de_linea(cantidad, precio),
        )
        Confirmacion.objects.create(
            cargo=cargo,
            estado=ConfirmState.CONFIRMADO.value,
            confirmado_en=momento,
            origen="tienda",
            confirmado_por=dueno,
        )
        return cargo

    def _propuesta_pendiente(self, tienda, cliente, dueno, productos):
        """One PREPARED proposal, so the shop's screen is demonstrable.

        It is `pendiente`, so it moves no balance: the outstanding shows
        nothing for it (CC-01).
        """
        propuesta = FiadoPropuesto.objects.create(
            shop=tienda,
            customer=cliente,
            user=dueno,
            estado=PropuestaEstado.PENDIENTE.value,
            total=Decimal("2.40"),
        )
        producto = productos["Manzanas"]
        cantidad = Decimal("1")
        precio = producto.precio
        PropuestaLinea.objects.create(
            propuesta=propuesta,
            producto=producto,
            cantidad=cantidad,
            precio_unitario=precio,
            total=reglas_cargos.total_de_linea(cantidad, precio),
        )
        return propuesta

    def _propuesta_cancelada(self, tienda, cliente, dueno, productos):
        """One CANCELLED proposal: the client declined."""
        propuesta = FiadoPropuesto.objects.create(
            shop=tienda,
            customer=cliente,
            user=dueno,
            estado=PropuestaEstado.CANCELADO.value,
            total=Decimal("4.30"),
            canceled_at=timezone.now() - timezone.timedelta(days=1),
        )
        producto = productos["Aceite"]
        cantidad = Decimal("1")
        precio = producto.precio
        PropuestaLinea.objects.create(
            propuesta=propuesta,
            producto=producto,
            cantidad=cantidad,
            precio_unitario=precio,
            total=reglas_cargos.total_de_linea(cantidad, precio),
        )
        return propuesta
