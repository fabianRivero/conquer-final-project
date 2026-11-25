"""Slice 10.6 - la persona es la unica que puede deber.

**The owner's rule**: *a client without an account cannot have a fiado*.
And without a fiado there is no debt to pay - which is what made the
`codigo` credential pointless.

**Three things happen here.**

1. **`Customer.user` becomes NOT NULL.** A row without a person behind
   it is not a person: it is a row the owner wrote and nobody can
   answer. The owner registers her and the LINK waits for her.

2. **The client rows that have no account get one.** The rows that
   exist were created by the shop, before the person had an account -
   that was the whole point of the claim of the 10.4. **The migration
   creates the account for them**: a `User` with the alias as its
   username and a **random, unusable password**, so the person can
   claim it and set her own.

   **Why the password is unusable, not empty.** An empty password would
   be a credential that anyone could use. A random one that nobody knows
   is a LOCKED account: the person resets it and takes it.

3. **`CustomerCodigo` and `CodigoIntento` go.** The credential is the
   third audience, and there is no case left for it: the person has an
   account, the account is her account, and the shop's counter
   identifies her by her username.

**NOT atomic**, and the reason is PostgreSQL: the data step writes
rows and the constraints that come after are schema operations, and
PostgreSQL refuses to create an index with pending trigger events. The
`0004` failed a deploy for exactly this reason.

**The order matters.** The data step runs BEFORE the `user` column
becomes NOT NULL - it is what fills it - and the accounts are created
with the alias as the username, which is unique in `auth_user`.
"""

import django.db.models.deletion
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations, models


def dar_cuenta_a_los_clientes(apps, schema_editor):
    """The client rows that have no account get one.

    **The account is created LOCKED.** The password is a random digest
    that nobody knows: an empty password would be a credential anybody
    could use, and a real one would be a secret the shop chose for the
    person - which is the thing the 10.1 removed.

    **The username is the alias**, because it is the name the shop
    knows her by and it is unique: the alias is unique in the
    `Customer`, and `auth_user.username` is unique too.

    **A row whose alias is taken by an existing user keeps its NULL
    `user`** - and the `NOT NULL` that comes after would refuse it. So
    the account is created with a suffixed username when the alias is
    taken, and the person finds hers by the alias on her account.
    """
    Customer = apps.get_model("tienda", "Customer")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    for cliente in Customer.objects.filter(user__isnull=True).order_by("id"):
        # Un username libre, derivado del alias.
        base = cliente.alias
        username = base
        sufijo = 1
        while User.objects.filter(username=username).exists():
            sufijo += 1
            username = "%s-%d" % (base, sufijo)

        usuario = User.objects.create(
            username=username,
            # **A LOCKED account**: a random password that nobody knows.
            password=make_password(None),
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        Customer.objects.filter(id=cliente.id).update(user_id=usuario.id)


def def_links_aceptados_a_pendientes(apps, schema_editor):
    """**The links that were `aceptado` go back to `pendiente`.**

    A link that the owner created `aceptado` - on the spot, without
    asking - is a link the PERSON never answered. And the answer is
    hers: a person who never said yes is not a trusted client.

    **The `aceptado_at` goes with it**, because the instant has to
    match the state: a link that is `pendiente` cannot carry the
    instant of an acceptance that never happened.
    """
    Vinculo = apps.get_model("tienda", "Vinculo")

    Vinculo.objects.filter(estado="aceptado").update(
        estado="pendiente", aceptado_at=None
    )


class Migration(migrations.Migration):
    # **NOT atomic**, and the reason is PostgreSQL: the data step writes
    # rows and the constraints that come after are schema operations,
    # and PostgreSQL refuses to create an index with pending trigger
    # events. The `0004` failed a deploy for exactly this reason.
    atomic = False

    dependencies = [
        ("tienda", "0007_la_persona_decide"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # --- THE DATA: the rows that have no account get one ----------
        # It goes FIRST, because it is what fills the column that the
        # NOT NULL below demands.
        migrations.RunPython(
            dar_cuenta_a_los_clientes,
            migrations.RunPython.noop,
            atomic=False,
        ),
        # --- THE DATA: the links that nobody answered go back ----------
        migrations.RunPython(
            def_links_aceptados_a_pendientes,
            migrations.RunPython.noop,
            atomic=False,
        ),
        # --- And now the column is NOT NULL --------------------------
        migrations.AlterField(
            model_name="customer",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customer",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # --- And the credential goes ---------------------------------
        # `CustomerCodigo` holds a FK to the `Customer`, and
        # `CodigoIntento` a FK to the `Shop`. **The intents go first**,
        # because they are the throttle ledger of a credential that is
        # about to stop existing.
        migrations.DeleteModel(
            name="CodigoIntento",
        ),
        migrations.DeleteModel(
            name="CustomerCodigo",
        ),
    ]
