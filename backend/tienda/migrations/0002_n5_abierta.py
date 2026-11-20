"""The N5 gate opens: the `dependiente` operates the counter.

Four changes, and one of them is a data migration:

* `Confirmacion.confirmado_por` replaces `Confirmacion.facilitado_por`.
  The new column is **NOT NULL**, so it cannot be added in one step: it is
  added nullable, the existing rows are backfilled with the user who
  wrote the charge - the same person who confirmed it, because until now
  only the owner could confirm - and only then is it made NOT NULL.

  The backfill is not a guess. Until the gate opened, the ONLY user who
  could confirm was the owner, and the owner wrote the charge in the same
  transaction, so `cargo.user` and the confirmer are the same row.

* `Confirmacion.origen` changes its vocabulary from `('tienda',
  'facilitado')` to `('tienda', 'dependiente')`. The existing rows are all
  `tienda`, which is still in the vocabulary, and no row is `facilitado` -
  the only confirmer was the owner.

* `FiadoPropuesto.facilitado_por` is removed. Every row has it NULL: the
  column was written only when the preparer was a `dependiente`, and the
  `dependiente` could not prepare anything while the gate was closed. So
  the column holds no data and removing it loses nothing.

* The partial UNIQUE index `uniq_fiadopropuesto_one_pendiente_per_customer`
  is removed. A customer may have SEVERAL pending fiados at once: the
  client buys on credit more than once, and each proposal is its own
  purchase. The rule that stays is the one that always held - one
  confirmation per charge, `uniq_confirmacion_one_confirmado_per_cargo`.
"""

from django.db import migrations, models
import django.db.models.deletion
import django.db.models.expressions


def confirmar_actor_por_el_cargo(apps, schema_editor):
    """Backfill `confirmado_por` with the user who wrote the charge.

    The charge and its confirmation are written in the same transaction by
    the same actor, so the charge's `user` IS the confirmer. The rows
    whose charge has no user cannot be backfilled and are refused by the
    NOT NULL constraint that follows - which is the correct outcome: a
    confirmation without an actor is a false record.
    """
    Confirmacion = apps.get_model("tienda", "Confirmacion")
    for confirmacion in Confirmacion.objects.select_related("cargo").all():
        confirmacion.confirmado_por_id = confirmacion.cargo.user_id
        confirmacion.save(update_fields=["confirmado_por"])


class Migration(migrations.Migration):

    dependencies = [
        ("tienda", "0001_initial"),
    ]

    operations = [
        # 1. The new column, nullable for now.
        migrations.AddField(
            model_name="confirmacion",
            name="confirmado_por",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="confirmaciones_registradas",
                to="auth.user",
                null=True,
            ),
        ),
        # 2. The backfill, before the NOT NULL.
        migrations.RunPython(confirmar_actor_por_el_cargo, migrations.RunPython.noop),
        # 3. Now it is NOT NULL.
        migrations.AlterField(
            model_name="confirmacion",
            name="confirmado_por",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="confirmaciones_registradas",
                to="auth.user",
            ),
        ),
        # 4. The origin's vocabulary: the third actor is gone.
        migrations.AlterField(
            model_name="confirmacion",
            name="origen",
            field=models.CharField(
                choices=[("tienda", "tienda"), ("dependiente", "dependiente")],
                default="tienda",
                max_length=20,
            ),
        ),
        # 5. The biconditional CHECK has no columns to guard: the actor is
        #    always present, so there is nothing left to contradict.
        migrations.RemoveConstraint(
            model_name="confirmacion",
            name="chk_confirmacion_facilitador_iff_origen",
        ),
        # 6. The old facilitator column.
        migrations.RemoveField(
            model_name="confirmacion",
            name="facilitado_por",
        ),
        # 7. And the proposal's: it held no data at all.
        migrations.RemoveField(
            model_name="fiadopropuesto",
            name="facilitado_por",
        ),
        # 8. Several pending fiados per customer.
        migrations.RemoveConstraint(
            model_name="fiadopropuesto",
            name="uniq_fiadopropuesto_one_pendiente_per_customer",
        ),
    ]
