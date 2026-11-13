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


# ---------------------------------------------------------------------------
# The staff routes
# ---------------------------------------------------------------------------

urlpatterns = [
    path("posicion/", vista_pendiente("posicion"), name="posicion"),
    path("caja/", vista_pendiente("caja"), name="caja"),
    path("cierre/", vista_pendiente("cierre"), name="cierre"),
    path("catalogo/", vista_pendiente("catalogo"), name="catalogo"),
    path("existencias/", vista_pendiente("existencias"), name="existencias"),
    path("clientes/", vista_pendiente("clientes"), name="clientes"),
    path("clientes/<int:cliente_id>/", vista_pendiente("clientes"), name="cliente_detalle"),
    path(
        "clientes/<int:cliente_id>/codigo/",
        vista_pendiente("codigo"),
        name="cliente_codigo",
    ),
    path(
        "clientes/<int:cliente_id>/libreta/",
        vista_pendiente("libreta"),
        name="cliente_libreta",
    ),
    path(
        "clientes/<int:cliente_id>/suspension/anular/",
        vista_pendiente("suspension"),
        name="cliente_suspension",
    ),
    # The proposal routes. The N5 gate is closed, so the four proposal
    # routes answer 403 to the `dependiente` (design section 7.1).
    path("propuestas/", vista_pendiente("propuestas"), name="propuestas"),
    path(
        "propuestas/<int:propuesta_id>/pantalla/",
        vista_pendiente("pantalla"),
        name="propuesta_pantalla",
    ),
    path(
        "propuestas/<int:propuesta_id>/confirmar/",
        vista_pendiente("confirmar"),
        name="propuesta_confirmar",
    ),
    path(
        "propuestas/<int:propuesta_id>/cancelar/",
        vista_pendiente("cancelar"),
        name="propuesta_cancelar",
    ),
    # The proposed payments.
    path(
        "pagos-propuestos/",
        vista_pendiente("pagos_propuestos"),
        name="pagos_propuestos",
    ),
    path(
        "pagos-propuestos/<int:pago_id>/validar/",
        vista_pendiente("validar"),
        name="pago_validar",
    ),
    path(
        "pagos-propuestos/<int:pago_id>/rechazar/",
        vista_pendiente("rechazar"),
        name="pago_rechazar",
    ),
    # The client routes. They live under their own prefix, and they never
    # share a route with a staff one.
    path("cliente/estado/", vista_pendiente("cliente_estado"), name="cliente_estado"),
    path(
        "cliente/cargos/<int:cargo_id>/",
        vista_pendiente("cliente_cargos"),
        name="cliente_cargo",
    ),
    path(
        "cliente/pagos/proponer/",
        vista_pendiente("cliente_proponer"),
        name="cliente_proponer_pago",
    ),
]
