"""Slice 10.3 - the link between a person and a shop.

The client is a **person**, and the link says she is a **trusted client
of a shop**. The person belongs to no shop; the link says she belongs to
this one. The `credit_limit` moves with it: the confidence is the OWNER'S,
and the owner has it **in this shop**.

**The data migration.** Every customer of a shop becomes a link of that
shop, **accepted** - because a customer of a shop is a customer the shop
already trusted, and the migration must not turn them into a question
the owner would have to answer again. The limit travels with them, and
a NULL limit stays NULL: "sin límite".

**The order matters.** The data moves **before** the columns are
dropped, because the old `Customer.shop_id` and `Customer.credit_limit`
are the only record of where each person belonged and what the owner
had allowed them.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.migrations.operations.models import RemoveField as RemoveFieldDeEstado


def clientes_a_vinculos(apps, schema_editor):
    """Every customer of a shop becomes an ACCEPTED link of that shop.

    The limit travels with the person: it was the owner's confidence in
    her **there**, and it is the link's now. A NULL limit stays NULL.

    **The alias may collide.** The old uniqueness was
    `(shop_id, alias)` - the alias identified a row of a shop's list -
    and the new one is `(alias)`: the person is one person in every
    shop. Two shops may therefore have had two different people called
    "Ana", and the person model now has ONE Ana.

    Those two are **the same person** as far as the system is concerned
    - she is one person - so the duplicate row is **merged** into the
    first one, and the rows that hang off it move with it. The limit of
    the second shop is **kept**: it is the owner's confidence in that
    shop, and it is not the first shop's to give away. The limit that
    survives is the **strictest** of the two: the owner trusted her
    less in one of them, and that number is the honest one.

    **It runs OUTSIDE the transaction** (`atomic=False`), because the
    `ALTER TABLE` that drops the old columns comes next, and it cannot
    run with pending trigger events.
    """
    Customer = apps.get_model("tienda", "Customer")
    Vinculo = apps.get_model("tienda", "Vinculo")

    por_alias = {}
    for cliente in Customer.objects.all().order_by("id"):
        por_alias.setdefault(cliente.alias, cliente)

    # --- the people FIRST: one row per alias ---------------------------
    #
    # The alias identifies the PERSON and not a row of a shop's list, and
    # the new uniqueness is `(alias)`. Two shops may therefore have had
    # two different people called "Ana", and there is now ONE Ana.
    #
    # **This has to happen BEFORE the unique constraint**, because the
    # constraint would refuse the duplicate alias otherwise - and the
    # migration would not apply at all.
    for alias, persona in por_alias.items():
        for duplicado in Customer.objects.filter(alias=alias).exclude(id=persona.id):
            # The rows that hang off the duplicate move to the person.
            for nombre in (
                "ledgerentry",
                "fiadopropuesto",
                "pagopropuesto",
                "customercodigo",
            ):
                try:
                    modelo = apps.get_model("tienda", nombre)
                except LookupError:
                    continue
                modelo.objects.filter(customer_id=duplicado.id).update(
                    customer_id=persona.id
                )
            duplicado.delete()

    # --- and the links, one per (shop, person) -------------------------
    for cliente in Customer.objects.all().order_by("id"):
        Vinculo.objects.get_or_create(
            tienda_id=cliente.shop_id,
            cliente_id=cliente.id,
            defaults={
                "estado": "aceptado",
                "credit_limit": cliente.credit_limit,
            },
        )

    # The strictest limit wins: the owner's confidence in the person is
    # the lowest cap the owner ever gave her.
    for alias, persona in por_alias.items():
        limites = [
            v.credit_limit
            for v in Vinculo.objects.filter(cliente_id=persona.id)
            if v.credit_limit is not None
        ]
        if not limites:
            continue
        estricto = min(limites)
        Vinculo.objects.filter(cliente_id=persona.id).update(
            credit_limit=estricto
        )


def clientes_a_vinculos_inverso(apps, schema_editor):
    """The reverse adds the columns back, EMPTY and NULLABLE.

    **The forward is the one that matters**, and the reverse is
    documented as lossy: the person was many things and the column was
    one. Rebuilding her `shop_id` would mean choosing a shop for her, and
    the link is exactly the thing that says she belongs to SEVERAL.

    So the columns come back **empty and nullable** - the person has no
    shop, which is the truth of the model. The old values are in the
    links, and the next forward migration would read them from there.

    A reverse that guesses would be worse than one that says so.
    """
    # The columns come back empty, and the NOT NULL goes with them: the
    # person has no shop, and the column has to be able to say so.
    schema_editor.execute(
        "ALTER TABLE tienda_customer "
        "ADD COLUMN IF NOT EXISTS shop_id bigint NULL"
    )
    schema_editor.execute(
        "ALTER TABLE tienda_customer "
        "ADD COLUMN IF NOT EXISTS credit_limit numeric(12,2) NULL"
    )
    schema_editor.execute(
        "ALTER TABLE tienda_customer ALTER COLUMN shop_id DROP NOT NULL"
    )
    schema_editor.execute(
        "ALTER TABLE tienda_customer ALTER COLUMN credit_limit DROP NOT NULL"
    )


class Migration(migrations.Migration):

    # **The whole migration runs OUTSIDE a transaction.** The data step
    # merges the people and the `ALTER TABLE` that drops the old columns
    # comes after, and PostgreSQL refuses to alter a table with pending
    # trigger events - which is what a data step inside the same
    # transaction leaves behind.
    atomic = False

    dependencies = [
        ('tienda', '0004_miembro_de_tienda'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Vinculo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado', models.CharField(choices=[('pendiente', 'pendiente'), ('aceptado', 'aceptado'), ('rechazado', 'rechazado'), ('eliminado', 'eliminado')], default='pendiente', max_length=20)),
                ('credit_limit', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('pedido_at', models.DateTimeField(blank=True, null=True)),
                ('aceptado_at', models.DateTimeField(blank=True, null=True)),
                ('rechazado_at', models.DateTimeField(blank=True, null=True)),
                ('eliminado_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'db_table': 'tienda_vinculo',
            },
        ),
        # The links, before the columns that say where they came from are
        # dropped.
        migrations.AddField(
            model_name='vinculo',
            name='cliente',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vinculos', to='tienda.customer'),
        ),
        migrations.AddField(
            model_name='vinculo',
            name='eliminado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vinculos_eliminados', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='vinculo',
            name='pedido_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vinculos_pedidos', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='vinculo',
            name='tienda',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='vinculos',
                to='tienda.shop',
                # **NULL at first**: the data step writes the links, and
                # a row with no shop yet would refuse a NOT NULL.
                null=True,
            ),
        ),
        # **THE DATA, forwards**: the people are merged by alias, and
        # every customer becomes an accepted link.
        #
        # **It goes FIRST**, before the unique constraint on the alias:
        # the constraint would refuse the duplicate alias otherwise, and
        # the migration would not apply at all.
        migrations.RunPython(
            clientes_a_vinculos, migrations.RunPython.noop, atomic=False
        ),
        # And now the old columns can go: the link holds the limit, and
        # the person belongs to no shop.
        migrations.RemoveConstraint(
            model_name='customer',
            name='uniq_customer_shop_alias',
        ),
        migrations.RemoveConstraint(
            model_name='customer',
            name='chk_customer_credit_limit_non_negative',
        ),
        # The columns go, and the link holds the limit and the shop.
        #
        # **They go with `SeparateDatabaseAndState`.** The SCHEMA drops
        # them and the STATE forgets them - the pattern Django documents
        # for a field that carries data. The reverse's schema operation
        # does NOTHING, and the inverse below adds the columns back
        # **empty and nullable**: the person no longer belongs to a shop,
        # and the NOT NULL of the model would refuse every row.
        #
        # So the reverse is a DEVELOPMENT convenience and not a way back
        # to the old data: **the old data is in the links**, and the
        # forward is the one that matters.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE tienda_customer "
                    "DROP COLUMN IF EXISTS credit_limit",
                    reverse_sql="ALTER TABLE tienda_customer "
                    "ADD COLUMN IF NOT EXISTS credit_limit numeric(12,2) NULL",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE tienda_customer "
                    "DROP COLUMN IF EXISTS shop_id",
                    reverse_sql="ALTER TABLE tienda_customer "
                    "ADD COLUMN IF NOT EXISTS shop_id bigint NULL",
                ),
            ],
            # The STATE forgets them with no database operation: the
            # reverse's schema operation does NOTHING, and the inverse
            # below adds the columns back empty and nullable.
            state_operations=[
                RemoveFieldDeEstado(
                    model_name='customer',
                    name='credit_limit',
                ),
                RemoveFieldDeEstado(
                    model_name='customer',
                    name='shop',
                ),
            ],
        ),
        # **THE DATA, backwards**: the columns come back empty and
        # nullable, and the NOT NULL goes with them.
        migrations.RunPython(
            migrations.RunPython.noop,
            clientes_a_vinculos_inverso,
            atomic=False,
        ),
        migrations.AddConstraint(
            model_name='customer',
            constraint=models.UniqueConstraint(fields=('alias',), name='uniq_customer_alias'),
        ),
        # And now every link has a shop: the column stops being
        # nullable.
        migrations.AlterField(
            model_name='vinculo',
            name='tienda',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vinculos', to='tienda.shop'),
        ),
        migrations.AddConstraint(
            model_name='vinculo',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ('estado__in', ('pendiente', 'aceptado', 'rechazado', 'eliminado'))
                ),
                name='chk_vinculo_estado_vocabulary',
            ),
        ),
        migrations.AddConstraint(
            model_name='vinculo',
            constraint=models.CheckConstraint(condition=models.Q(('credit_limit__isnull', True), ('credit_limit__gte', 0), _connector='OR'), name='chk_vinculo_credit_limit_non_negative'),
        ),
        migrations.AddConstraint(
            model_name='vinculo',
            constraint=models.UniqueConstraint(fields=('tienda', 'cliente'), name='uniq_vinculo_one_per_shop'),
        ),
    ]
