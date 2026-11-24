"""Slice 10.5, T1 - the states of the `FiadoPropuesto` are the PERSON's
answer.

The proposal's vocabulary moves from `pendiente`/`confirmado`/`cancelado`
to `pendiente`/`aceptado`/`rechazado`, and the rejection carries a
**reason**: free text, and it may be empty.

**The rows that already exist are MIGRATED, not dropped.** The old
vocabulary said the SHOP acted; the new one says what the PERSON did.
The rows say the same thing in the new words:

* `confirmado` becomes `aceptado` - the shop recorded a confirmation,
  and the person is who confirmed it;
* `cancelado` becomes `rechazado` - the shop recorded a cancellation,
  and the person is who refused it.

**The reason of a migrated rejection is EMPTY, and that is honest.** The
shop did not ask her why, so there is no reason to record: the column
is nullable and the migrated rows leave it NULL. A reason appears when
SHE gives one.

**NOT atomic**, and the reason is PostgreSQL: the `RunPython` writes
rows and the constraint that comes after is a schema operation, and
PostgreSQL refuses to create an index with pending trigger events. The
`0004` failed a deploy for exactly this reason.

**The constraint names change too.** The old ones were named after the
old words - `chk_fiadopropuesto_confirmado_fields` - and a name that
carries a word the vocabulary no longer has is a lie in the schema.
Django cannot rename a constraint, so the old ones are removed and the
new ones are added.

**The `Confirmacion.estado` does NOT move.** It is the state of the
CHARGE and it has one value only, `confirmado`: the charge that exists
because she accepted is `confirmado`, and the proposal she accepted is
`aceptado`. Two rows, two vocabularies, two questions.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrar_los_vocabulario(apps, schema_editor):
    """The rows that exist say the same thing in the new words.

    `confirmado` becomes `aceptado` and `cancelado` becomes `rechazado`.

    **The reason of a migrated rejection stays NULL.** The shop did not
    ask her why, so there is nothing to record - and a made-up reason
    would be worse than none.
    """
    FiadoPropuesto = apps.get_model("tienda", "FiadoPropuesto")

    FiadoPropuesto.objects.filter(estado="confirmado").update(
        estado="aceptado"
    )
    FiadoPropuesto.objects.filter(estado="cancelado").update(
        estado="rechazado"
    )


def migrar_los_vocabulario_inverso(apps, schema_editor):
    """**Backwards**: the rows say the same thing in the old words.

    The reverse has to move the rows BEFORE the old vocabulary constraint
    comes back, because that constraint holds the old words in its
    CONDITION: a row that says `aceptado` violates it.

    And the reason is dropped on the way back: the old model has no
    column for it, and a reason that the model cannot hold would be a
    value nothing could read.
    """
    FiadoPropuesto = apps.get_model("tienda", "FiadoPropuesto")

    FiadoPropuesto.objects.filter(estado="aceptado").update(
        estado="confirmado"
    )
    FiadoPropuesto.objects.filter(estado="rechazado").update(
        estado="cancelado"
    )


class Migration(migrations.Migration):
    # **NOT atomic**, and the reason is PostgreSQL: the data step writes
    # rows and the constraints that come after are schema operations, and
    # PostgreSQL refuses to create an index with pending trigger events.
    # The `0004` failed a deploy for exactly this reason.
    atomic = False

    dependencies = [
        ("tienda", "0006_customer_es_la_persona"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # The column comes FIRST and nullable: the data step does not
        # fill it - the shop never asked her why - and the rows that
        # exist keep it NULL.
        migrations.AddField(
            model_name="fiadopropuesto",
            name="motivo_rechazo",
            field=models.TextField(blank=True, null=True),
        ),
        # **The vocabulary constraint goes BEFORE the data step.** It
        # holds the words in its CONDITION - `estado__in=('pendiente',
        # 'confirmado', 'cancelado')` - so the rows the data step is
        # about to write as `aceptado` would violate it.
        #
        # It is replaced by the new one BEFORE the data, and not after:
        # the constraint is the vocabulary, and the vocabulary has to be
        # the new one for the migration to write anything.
        migrations.RemoveConstraint(
            model_name="fiadopropuesto",
            name="chk_fiadopropuesto_estado_vocabulary",
        ),
        # The old constraints carry the old words in their NAMES, and a
        # name that says a word the vocabulary no longer has is a lie in
        # the schema. Django cannot rename a constraint, so the old ones
        # go and the new ones come.
        migrations.RemoveConstraint(
            model_name="fiadopropuesto",
            name="chk_fiadopropuesto_confirmado_fields",
        ),
        migrations.RemoveConstraint(
            model_name="fiadopropuesto",
            name="chk_fiadopropuesto_cancelado_fields",
        ),
        # The field's own `choices` carry the vocabulary, and they change
        # with it. Django reads the `choices` out of the migration state,
        # so the field has to be altered here or the state would carry
        # the old words.
        migrations.AlterField(
            model_name="fiadopropuesto",
            name="estado",
            field=models.CharField(
                choices=[
                    ("pendiente", "pendiente"),
                    ("aceptado", "aceptado"),
                    ("rechazado", "rechazado"),
                ],
                default="pendiente",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="fiadopropuesto",
            constraint=models.CheckConstraint(
                condition=(
                    ~models.Q(estado="aceptado")
                    | (
                        models.Q(confirmed_at__isnull=False)
                        & models.Q(canceled_at__isnull=True)
                    )
                ),
                name="chk_fiadopropuesto_aceptado_fields",
            ),
        ),
        migrations.AddConstraint(
            model_name="fiadopropuesto",
            constraint=models.CheckConstraint(
                condition=(
                    ~models.Q(estado="rechazado")
                    | (
                        models.Q(canceled_at__isnull=False)
                        & models.Q(confirmed_at__isnull=True)
                    )
                ),
                name="chk_fiadopropuesto_rechazado_fields",
            ),
        ),
        # A `pendiente` proposal has no answer yet: no confirmation, no
        # rejection, and no reason.
        migrations.AddConstraint(
            model_name="fiadopropuesto",
            constraint=models.CheckConstraint(
                condition=(
                    ~models.Q(estado="pendiente")
                    | (
                        models.Q(confirmed_at__isnull=True)
                        & models.Q(canceled_at__isnull=True)
                        & models.Q(motivo_rechazo__isnull=True)
                    )
                ),
                name="chk_fiadopropuesto_pendiente_sin_respuesta",
            ),
        ),
        # Only a rejection carries a reason. The reason is NOT required
        # on a rejection, because there are two rejections and only one
        # of them has a reason: the PERSON's, which she writes from her
        # own account. The shop's cancellation is a different act and it
        # has no explanation to give - and the migrated rejections have
        # none either, because the shop never asked her why.
        migrations.AddConstraint(
            model_name="fiadopropuesto",
            constraint=models.CheckConstraint(
                condition=(
                    ~models.Q(motivo_rechazo__isnull=False)
                    | models.Q(estado="rechazado")
                ),
                name="chk_fiadopropuesto_motivo_solo_en_el_rechazo",
            ),
        ),
        # **The DATA, and it goes LAST.**
        #
        # Django undoes the operations **backwards**, so the inverse of
        # the LAST one runs FIRST. And the inverse has to move the rows
        # back to the old words **before** the old vocabulary constraint
        # comes back - that constraint holds the old words in its
        # CONDITION, and a row that says `aceptado` violates it.
        #
        # The forward does the opposite and it is also last: the
        # constraint is replaced BEFORE the data, and the data is
        # written with the new words.
        migrations.RunPython(
            migrar_los_vocabulario,
            migrar_los_vocabulario_inverso,
            atomic=False,
        ),
        # **And the new vocabulary constraint goes AFTER the data.**
        #
        # The old constraint holds the old words in its CONDITION, so it
        # has to go BEFORE the data is written - and the new one holds
        # the NEW words, so it has to come AFTER. The data is written in
        # between, and that is the only order in which both the forward
        # and the reverse work.
        #
        # **The reverse undoes the list backwards**, so the constraint
        # comes off first, then the rows go back to the old words, and
        # then the old constraint comes back - and it accepts the old
        # words, which is what the rows say by then.
        migrations.AddConstraint(
            model_name="fiadopropuesto",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    estado__in=("pendiente", "aceptado", "rechazado")
                ),
                name="chk_fiadopropuesto_estado_vocabulary",
            ),
        ),
    ]
