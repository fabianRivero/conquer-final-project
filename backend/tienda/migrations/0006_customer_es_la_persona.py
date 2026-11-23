"""Slice 10.4 - the customer row and the person's account are the SAME
human, and the model has to say so.

The `Customer` gains a nullable `user`: the account of the person whose
row this is. It is nullable because the shop may register a customer
who has no account yet - she is a customer of the shop and of nobody
else - and she may register herself later and claim the row.

**The data migration.** The rows that can be matched are matched by the
**alias**: the person registered with a username, and the shop called her
by an alias, and in the common case the two are the same string. A
customer row whose alias is not any person's username is left alone: the
row is the shop's, and the shop's list of people is not the account's
list.

**The `alias` is not a `username`.** The person chooses her username and
the shop chooses the alias, and they may differ. The `user` field is
what says which is which, and the migration can only guess - so it
guesses CONSERVATIVELY: it matches the alias to the username and leaves
every doubt alone.

**It runs OUTSIDE the transaction** (`atomic=False`), because the
`ALTER TABLE` that adds the unique constraint comes next.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def enlazar_personas(apps, schema_editor):
    """The customer rows that carry a person's username are linked to her.

    The match is by the **alias**, and it is the only match available:
    before this field, the two were the same string by coincidence and
    nothing else tied them together.

    **A row that no username matches is left alone.** The person may
    have registered under a different username - she chose it, and the
    shop calls her by something else - and guessing would link her
    account to somebody else's debt. An unlinked row is safe: the
    person claims it from her own account when she recognises herself.
    """
    Customer = apps.get_model("tienda", "Customer")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    # The usernames, lowercased: Django's username is case-sensitive on
    # the way IN and the alias is what the shop typed.
    por_usuario = {u.username.lower(): u.id for u in User.objects.all()}

    for cliente in Customer.objects.filter(user__isnull=True).order_by("id"):
        usuario_id = por_usuario.get(cliente.alias.lower())
        if usuario_id is None:
            continue
        # One person claims ONE row: if the user already has one, this
        # row is somebody's else and it stays unlinked.
        if Customer.objects.filter(user_id=usuario_id).exclude(
            id=cliente.id
        ).exists():
            continue
        Customer.objects.filter(id=cliente.id).update(user_id=usuario_id)


class Migration(migrations.Migration):
    dependencies = [
        ("tienda", "0005_vinculo_con_consentimiento"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # The column comes FIRST and nullable: the data step fills it,
        # and a row that no username matches keeps it NULL.
        migrations.AddField(
            model_name="customer",
            name="user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customer",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # The DATA, forwards: the rows that carry a person's username are
        # linked to her.
        migrations.RunPython(
            enlazar_personas, migrations.RunPython.noop, atomic=False
        ),
        # And then the constraint: a person claims ONE customer row.
        migrations.AddConstraint(
            model_name="customer",
            constraint=models.UniqueConstraint(
                fields=["user"], name="uniq_customer_one_per_user"
            ),
        ),
    ]
