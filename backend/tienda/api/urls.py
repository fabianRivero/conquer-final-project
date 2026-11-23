"""The URL map of design §9.1 — the API's shape, declared once.

Every route of the API is declared here, and **no route exposes a
`PUT`, a `PATCH` or a `DELETE`** for a ledger row. That is not a
convention: the book is append-only, and the absence of a mutating route
for `LedgerEntry`, `CargoLinea`, `Confirmacion`, `PropuestaLinea` or
`PagoPropuesto` is what makes it structurally impossible to edit a row
from the outside. The `api/permissions.py` boundary and the
`AppendOnlyModel` guard are the other two layers; this is the third.

**The views land in the next slices of the chain.** PR 4b delivers the
serializers and this map; PR 4c delivers the staff views; PR 4d the
credential machinery; PR 4e the leak walk. So the map below names every
route of §9.1 and resolves it to a view, and the views that do not exist
yet answer with a clear placeholder rather than with a 404 that would look
like a missing route.

That placeholder matters: a route that does not exist and a route that is
not built yet look the same from the outside, and the difference is the
difference between "the contract is broken" and "the work is pending". A
missing route answers **501**, with the name of the slice that owes it.

The two audiences keep their own prefixes: `/api/v1/…` for the staff, and
`/api/v1/cliente/…` for the client. There is no route that accepts both a
session and a credential — the design §8 invariant is structural, and the
map is where it is visible.
"""

from __future__ import annotations

from django.http import JsonResponse
from django.urls import path

from tienda.api.cuenta import (
    CuentaLoginView,
    CuentaLogoutView,
    CuentaRegistroView,
    PerfilClienteView,
    PerfilesView,
    PerfilTiendaView,
)
from tienda.api.personal import (
    LoginTiendaView,
    PersonalMiembroView,
    PersonalView,
)
from tienda.api.vinculos import (
    VinculoAceptarView,
    VinculoEliminarView,
    VinculoRechazarView,
    VinculosDelClienteView,
    VinculosDelDuenoView,
)
from tienda.api.views import (
    CajaView,
    CatalogoView,
    CierreView,
    ClienteCargoView,
    ClienteDetalleView,
    ClienteEstadoView,
    ClienteLibretaView,
    ClienteProponerPagoView,
    ClientesView,
    PagoRechazarView,
    PagosPropuestosView,
    PagoValidarView,
    PosicionView,
    PropuestaCancelarView,
    PropuestaConfirmarView,
    PropuestaPantallaView,
    PropuestasView,
)

#: The slices of the Phase 4 chain that owe the views. A route whose view
#: has not landed answers 501 with this map, so the answer says what is
#: missing and not merely that something is.
VIEWS_PENDIENTES = {
    "posicion": "PR 4c",
    "caja": "PR 4c",
    "cierre": "PR 4c",
    "catalogo": "PR 4c",
    "existencias": "PR 4c",
    "clientes": "PR 4c",
    "codigo": "PR 4c",
    "libreta": "PR 4c",
    "suspension": "PR 4c",
    "propuestas": "PR 5",
    "pantalla": "PR 5",
    "confirmar": "PR 5",
    "cancelar": "PR 5",
    "pagos_propuestos": "PR 6",
    "validar": "PR 6",
    "rechazar": "PR 6",
    "cliente_estado": "PR 6",
    "cliente_cargos": "PR 6",
    "cliente_proponer": "PR 6",
}


def vista_pendiente(nombre: str):
    """A placeholder for a view that has not landed yet.

    It answers **501 Not Implemented** and names the slice that owes the
    view. A 404 would say "this route does not exist", which is a
    statement about the contract; a 501 says "this contract exists and is
    not built yet", which is a statement about the work.
    """

    def _vista(request, *args, **kwargs):
        return JsonResponse(
            {
                "codigo_error": "vista_pendiente",
                "detail": f"La vista {nombre} todavia no esta construida.",
                "slice": VIEWS_PENDIENTES.get(nombre, "PR 4c"),
            },
            status=501,
        )

    return _vista


#: The namespace of the API. Django's `include()` of a urlconf module
#: needs an `app_name` for the routes inside it to be reversible, and the
#: namespace is what makes them so: `reverse("api:caja")`.
app_name = "api"


# ---------------------------------------------------------------------------
# The staff routes
# ---------------------------------------------------------------------------

urlpatterns = [
    path("posicion/", PosicionView.as_view(), name="posicion"),
    path("caja/", CajaView.as_view(), name="caja"),
    path("cierre/", CierreView.as_view(), name="cierre"),
    path("catalogo/", CatalogoView.as_view(), name="catalogo"),
    path("existencias/", vista_pendiente("existencias"), name="existencias"),
    path("clientes/", ClientesView.as_view(), name="clientes"),
    path(
        "clientes/<int:cliente_id>/",
        ClienteDetalleView.as_view(),
        name="cliente_detalle",
    ),
    path(
        "clientes/<int:cliente_id>/codigo/",
        vista_pendiente("codigo"),
        name="cliente_codigo",
    ),
    path(
        "clientes/<int:cliente_id>/libreta/",
        ClienteLibretaView.as_view(),
        name="cliente_libreta",
    ),
    path(
        "clientes/<int:cliente_id>/suspension/anular/",
        vista_pendiente("suspension"),
        name="cliente_suspension",
    ),
    # The proposal routes. The N5 gate is closed, so the four proposal
    # routes answer 403 to the `dependiente` (design section 7.1).
    path("propuestas/", PropuestasView.as_view(), name="propuestas"),
    path(
        "propuestas/<int:propuesta_id>/pantalla/",
        PropuestaPantallaView.as_view(),
        name="propuesta_pantalla",
    ),
    path(
        "propuestas/<int:propuesta_id>/confirmar/",
        PropuestaConfirmarView.as_view(),
        name="propuesta_confirmar",
    ),
    path(
        "propuestas/<int:propuesta_id>/cancelar/",
        PropuestaCancelarView.as_view(),
        name="propuesta_cancelar",
    ),
    # The proposed payments.
    path(
        "pagos-propuestos/",
        PagosPropuestosView.as_view(),
        name="pagos_propuestos",
    ),
    path(
        "pagos-propuestos/<int:pago_id>/validar/",
        PagoValidarView.as_view(),
        name="pago_validar",
    ),
    path(
        "pagos-propuestos/<int:pago_id>/rechazar/",
        PagoRechazarView.as_view(),
        name="pago_rechazar",
    ),
    # The client routes. They live under their own prefix, and they never
    # share a route with a staff one.
    path("cliente/estado/", ClienteEstadoView.as_view(), name="cliente_estado"),
    path(
        "cliente/cargos/<int:cargo_id>/",
        ClienteCargoView.as_view(),
        name="cliente_cargo",
    ),
    path(
        "cliente/pagos/proponer/",
        ClienteProponerPagoView.as_view(),
        name="cliente_proponer_pago",
    ),
    # The PERSON's routes. They live under their own prefix and they
    # never share a route with a staff one: the person owns her account
    # and her credentials, and the shop neither issues them nor changes
    # them.
    path(
        "cuenta/registro/",
        CuentaRegistroView.as_view(),
        name="cuenta_registro",
    ),
    path("cuenta/login/", CuentaLoginView.as_view(), name="cuenta_login"),
    path("cuenta/logout/", CuentaLogoutView.as_view(), name="cuenta_logout"),
    path("perfiles/", PerfilesView.as_view(), name="perfiles"),
    path(
        "perfiles/cliente/",
        PerfilClienteView.as_view(),
        name="perfiles_cliente",
    ),
    path(
        "perfiles/tienda/",
        PerfilTiendaView.as_view(),
        name="perfiles_tienda",
    ),
    # The SHOP's routes. The shop gives its staff a user, and the role
    # lives in the membership - a `dependiente` of one shop is a
    # `dependiente` of that shop and of no other.
    path("tienda/login/", LoginTiendaView.as_view(), name="login_tienda"),
    path("tienda/personal/", PersonalView.as_view(), name="personal"),
    path(
        "tienda/personal/<int:user_id>/",
        PersonalMiembroView.as_view(),
        name="personal_miembro",
    ),
    # The LINK, and the client's consent. The shop asks; the client
    # answers from her own account.
    path(
        "cuenta/vinculos/",
        VinculosDelClienteView.as_view(),
        name="cuenta_vinculos",
    ),
    path(
        "cuenta/vinculos/aceptar/",
        VinculoAceptarView.as_view(),
        name="cuenta_vinculo_aceptar",
    ),
    path(
        "cuenta/vinculos/rechazar/",
        VinculoRechazarView.as_view(),
        name="cuenta_vinculo_rechazar",
    ),
    path(
        "tienda/vinculos/",
        VinculosDelDuenoView.as_view(),
        name="tienda_vinculos",
    ),
    path(
        "tienda/vinculos/<int:cliente_id>/",
        VinculoEliminarView.as_view(),
        name="tienda_vinculo_eliminar",
    ),
]
