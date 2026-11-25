"""Slice 10.6, T4 - **la persona tiene su perfil de cliente**.

**El hueco que el despliegue mostro.** La migracion `0008` da cuenta a
las fichas que no tienen persona, y crea el `User` - pero **no crea el
`PerfilCliente`**. Y el permiso de las rutas de la persona lo exige:
\`EsClienteConVinculo\` dice "la sesion de una persona **y** su perfil
de cliente".

Asi que la persona **entra** - su cuenta existe y su contrasena es la
suya - y despues **no alcanza nada**: sus rutas contestan 403.

**Y el perfil es lo que dice "soy clienta en el mundo del credito".**
Una cuenta sin perfil es una cuenta de persona, y la persona todavia no
ha dicho que compra fiado: eso lo dice el vinculo, y el vinculo lo
contesta ella.

**La migracion `0008` ya esta aplicada en Neon**, asi que esto NO se
toca: se anade una `0009` que da el perfil que le faltaba. Editar una
migracion aplicada es reescribir la historia.

**Y el seed tambien lo garantiza**, porque el demo tiene que poder
entrar y ver sus cosas: el perfil se crea si no esta.
"""

from django.db import migrations


def dar_el_perfil(apps, schema_editor):
    """Every account that has a customer row gets its client profile.

    **The profile is what says "I am a client in the world of
    credit".** An account without one is a person's account, and the
    person has not said she buys on credit yet: that is the link, and
    the link is hers to answer.

    The `0008` created the accounts of the rows that had no person and
    **did not create the profile** - so those people could sign in and
    reach nothing.
    """
    Customer = apps.get_model("tienda", "Customer")
    PerfilCliente = apps.get_model("tienda", "PerfilCliente")

    for cliente in Customer.objects.filter(user__isnull=False).order_by("id"):
        if PerfilCliente.objects.filter(user_id=cliente.user_id).exists():
            continue
        PerfilCliente.objects.create(user_id=cliente.user_id)


class Migration(migrations.Migration):
    # **NOT atomic**, and the reason is PostgreSQL: the data step writes
    # rows and the constraint that comes after is a schema operation.
    # The `0004` failed a deploy for exactly this reason.
    atomic = False

    dependencies = [
        ("tienda", "0008_la_persona_es_la_unica"),
    ]

    operations = [
        migrations.RunPython(
            dar_el_perfil, migrations.RunPython.noop, atomic=False
        ),
    ]
