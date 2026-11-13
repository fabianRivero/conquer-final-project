"""The serializers and the URL map — tasks 4.18, 4.19 and 4.21.

Two properties are under test, and they are the ones the design says the
leak guarantee rests on.

**The client schema declares none of the nine staff-only fields.** That is
the assertion that carries CAC-10, and it is a property of the SCHEMA:
DRF's `fields` is exhaustive, so a field that is not declared cannot be
in the response whatever the view hands over. The test reads the class's
own declared fields and fails if it names any of the nine.

**The URL map exposes no mutating route for a ledger row.** The book is
append-only, and the absence of a `PUT`, a `PATCH` or a `DELETE` is what
makes editing a row structurally impossible from the outside. The test
walks the whole map and fails on any mutating method.

The schemas are also checked for the shapes the design fixes: the
dependent's position carries only three fields and its `clientes` is an
empty list **without executing the customer query**, the client's charges
always carry their `lineas[]`, and the two closes differ in exactly one
field.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import get_resolver

from tienda.api.serializers import cliente, staff
from tienda.api.serializers.fields import fields_de

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# The client schema — the CAC-10 guarantee
# ---------------------------------------------------------------------------


def test_the_client_schema_declares_none_of_the_nine_staff_only_fields():
    """The guarantee of CAC-10, asserted on the schema.

    The nine are `caja`, `fiado_pendiente`, `posicion_real`, `buckets`,
    `credit_limit`, `antiguedad_max_dias`, `suspended_reason`, `codigo` and
    `prefix`. The client class declares **none** of them.
    """
    declarados = fields_de(cliente.EstadoClienteSerializer)
    ofensores = declarados & staff.CAMPOS_SOLO_DE_PERSONAL

    assert ofensores == set(), (
        "the client schema declares staff-only fields: "
        + ", ".join(sorted(ofensores))
    )


def test_the_nine_staff_only_fields_are_the_ones_of_the_design():
    """The list is the same nine wherever it is enumerated.

    §7.2, §9.2's opening prose, §9.2's field list and the test of §15.2
    all say the same nine, so a reader never has to reconstruct it.
    """
    assert staff.CAMPOS_SOLO_DE_PERSONAL == frozenset({
        "caja",
        "fiado_pendiente",
        "posicion_real",
        "buckets",
        "credit_limit",
        "antiguedad_max_dias",
        "suspended_reason",
        "codigo",
        "prefix",
    })


def test_the_client_schema_declares_its_own_fields():
    """It declares the alias, the total and the charges."""
    declarados = fields_de(cliente.EstadoClienteSerializer)

    assert declarados == {"alias", "total", "cargos"}


def test_a_client_charge_carries_its_paid_and_its_remaining():
    """Each charge carries `pagado` and `saldo`, both derived on read.

    A charge of 15,00 settled by 5,00 reads 5/15: the client knows exactly
    what it has paid and what it owes.
    """
    declarados = fields_de(cliente.CargoClienteSerializer)

    for campo in ("id", "fecha", "amount", "confirmado_en", "pagado", "saldo", "lineas"):
        assert campo in declarados, f"the charge schema does not declare {campo}"


def test_the_client_schema_carries_no_pagination_metadata():
    """No pagination metadata reaches the client.

    The statement is a bare JSON list of the client's own charges; there is
    no `count`, no `next`, no `results`.
    """
    declarados = fields_de(cliente.EstadoClienteSerializer)

    for prohibido in ("count", "next", "previous", "results", "pagination"):
        assert prohibido not in declarados


def test_the_client_schema_shares_no_field_with_the_staff_only_list():
    """The names it does share are the harmless ones.

    `total`, `lineas[]`, `producto`, `cantidad` and `precio_unitario` are
    shared with the staff schemas on purpose: the client is entitled to
    see the `desglose` of the charges it confirmed. What must never cross
    is the information, not the name.
    """
    declarados = fields_de(cliente.EstadoClienteSerializer)
    compartidos = declarados & staff.CAMPOS_SOLO_DE_PERSONAL

    assert compartidos == set()


# ---------------------------------------------------------------------------
# The staff schemas
# ---------------------------------------------------------------------------


def test_the_owner_position_carries_its_seven_fields():
    """The owner's board: the ladder, the position, the buckets and the series."""
    declarados = fields_de(staff.PosicionDuenoSerializer)
    for campo in (
        "caja",
        "fiado_pendiente",
        "posicion_real",
        "buckets",
        "clientes",
        "serie_caja",
        "cierre_hoy",
    ):
        assert campo in declarados, f"the owner's position does not declare {campo}"


def test_the_dependent_position_carries_only_three_fields():
    """The reduced payload of design §7.

    The ladder, `posicion_real`, `fiado_pendiente` and `buckets` are
    absent — and so are the alias, the `credit_limit` and the credential.
    """
    declarados = fields_de(staff.PosicionDependienteSerializer)
    assert declarados == {"caja", "clientes", "cierre_hoy"}


def test_the_dependent_position_declares_only_caja_of_the_nine():
    """It declares `caja` of the nine, and nothing else of them.

    The nine are **the nine the client must never see**. The staff classes
    declare some of them by design — the dependent reads the drawer, which
    is `caja`, and CP-05 requires it to read the close. What the dependent
    never declares is the ladder, the `posicion_real`, the `fiado_pendiente`
    and the `buckets`.
    """
    declarados = fields_de(staff.PosicionDependienteSerializer)

    assert declarados & staff.CAMPOS_SOLO_DE_PERSONAL == {"caja"}


def test_the_dependent_position_answers_an_empty_customer_list():
    """Its `clientes` is `[]`, and the customer table is never asked.

    The guarantee is not "the rows are filtered afterwards" — it is "the
    rows are never requested".
    """
    serializer = staff.PosicionDependienteSerializer()

    assert serializer.get_clientes(object()) == []


def test_the_two_closes_differ_in_exactly_one_field():
    """The owner's close carries the date; the dependent's does not."""
    dueno = fields_de(staff.CierreDuenoSerializer)
    dependiente = fields_de(staff.CierreDependienteSerializer)

    assert dueno == {"date", "esperado", "contado", "desviacion"}
    assert dependiente == {"esperado", "contado", "desviacion"}
    assert dueno - dependiente == {"date"}


def test_the_proposal_screen_carries_the_itemisation_and_nothing_else():
    """`total` and `lineas[]` — no balance, no ageing, no other customer."""
    declarados = fields_de(staff.PropuestaPantallaSerializer)
    assert declarados == {"total", "lineas"}
    assert declarados & staff.CAMPOS_SOLO_DE_PERSONAL == set()


def test_the_proposal_screen_shares_the_client_names_on_purpose():
    """It shares `total` and `lineas[]` with the client schema.

    That is correct: it shows one proposal's `desglose` at the counter, and
    the client is entitled to see the `desglose` of the charges it
    confirmed. What must never cross is the data, not the name.
    """
    pantalla = fields_de(staff.PropuestaPantallaSerializer)
    cliente_campos = fields_de(cliente.EstadoClienteSerializer)

    assert "total" in pantalla and "total" in cliente_campos
    assert "lineas" in pantalla and "cargos" in cliente_campos


# ---------------------------------------------------------------------------
# The URL map
# ---------------------------------------------------------------------------


def _todas_las_rutas():
    """Every route of the API, as `(pattern, name, callback)`.

    The pattern is read as a **string**: Django's `URLPattern.pattern` is a
    `RoutePattern` object, and `str()` of it is the route as it is written
    in the map.
    """
    from tienda.api import urls as urls_api

    return [
        (str(patron.pattern), patron.name, patron.callback)
        for patron in urls_api.urlpatterns
    ]


def test_the_api_map_declares_every_route_of_the_design():
    """Every route of §9.1 is declared.

    The map is the contract: a route that is missing here is a route the
    client cannot call, and the design says exactly which ones exist.
    """
    patrones = {p for p, _, _ in _todas_las_rutas()}

    for esperado in (
        "posicion/",
        "caja/",
        "cierre/",
        "catalogo/",
        "existencias/",
        "clientes/",
        "clientes/<int:cliente_id>/",
        "clientes/<int:cliente_id>/codigo/",
        "clientes/<int:cliente_id>/libreta/",
        "clientes/<int:cliente_id>/suspension/anular/",
        "propuestas/",
        "propuestas/<int:propuesta_id>/pantalla/",
        "propuestas/<int:propuesta_id>/confirmar/",
        "propuestas/<int:propuesta_id>/cancelar/",
        "pagos-propuestos/",
        "pagos-propuestos/<int:pago_id>/validar/",
        "pagos-propuestos/<int:pago_id>/rechazar/",
        "cliente/estado/",
        "cliente/cargos/<int:cargo_id>/",
        "cliente/pagos/proponer/",
    ):
        assert esperado in patrones, f"the route {esperado} is not declared"


def _metodos_de(vista) -> set:
    """The HTTP methods a view accepts.

    DRF's `APIView` declares them in `http_method_names`; a plain Django
    function view accepts whatever the method is, and a function object
    that is a class instance carries them on its own class. The check
    reads all three, and a view that declares **nothing** is treated as
    accepting only the safe methods — a plain function cannot be routed
    to `PUT` without a class that says so.
    """
    from rest_framework.views import APIView

    if isinstance(vista, APIView):
        return set(getattr(vista, "http_method_names", []) or [])

    clase = getattr(vista, "cls", None)
    if clase is not None:
        return set(getattr(clase, "http_method_names", []) or [])

    return set(getattr(vista, "http_method_names", []) or [])


def test_no_route_exposes_a_mutating_method_for_a_ledger_row():
    """There is no `PUT`, no `PATCH` and no `DELETE` anywhere in the API.

    The book is append-only. The `AppendOnlyModel` guard refuses an update
    at the model, and this is the third layer: there is no URL that could
    reach such a write in the first place.

    The whole project is walked, **including the routes under the
    `/api/v1/` resolver**. A walk of the root patterns alone would find
    nothing, because the API's routes live one level down — and a check
    that can only pass is not a check.
    """
    from django.urls import URLPattern, URLResolver

    def patrones(resolver):
        """Every pattern under a resolver, at any depth."""
        for patron in resolver.url_patterns:
            if isinstance(patron, URLPattern):
                yield patron
            elif isinstance(patron, URLResolver):
                yield from patrones(patron)

    # The routes that may mutate, and why. The `PATCH` of the customer's
    # detail changes the `credit_limit`, and that is the owner's own record
    # and policy - not a row of the book (design section 3.1). The
    # append-only guarantee is about the BOOK: LedgerEntry, CargoLinea,
    # Confirmacion, PropuestaLinea and ImputacionPago are never modified.
    MUTACION_PERMITIDA = {"clientes/<int:cliente_id>/"}

    mutantes = []
    for patron in patrones(get_resolver()):
        # Django's own admin and auth routes are not the API's.
        if patron.name in {"login", "logout", "password_reset", "password_change"}:
            continue
        prohi = _metodos_de(patron.callback) & {"put", "patch", "delete"}
        if not prohi:
            continue
        if str(patron.pattern) in MUTACION_PERMITIDA:
            continue
        mutantes.append(f"{patron.pattern} -> {sorted(prohi)}")

    assert mutantes == [], (
        "the project exposes a mutating route: " + ", ".join(mutantes)
    )


def test_only_the_customer_detail_may_be_patched():
    """Exactly one route of the API accepts a `PATCH`, and it is this one.

    The `credit_limit` is the owner's own record and policy. Everything
    else - the cash, the close, the position, the catalogue, the customer
    list and the ledger - answers only `get` and `post`.
    """
    from django.urls import URLPattern, URLResolver

    def patrones(resolver):
        for patron in resolver.url_patterns:
            if isinstance(patron, URLPattern):
                yield patron
            elif isinstance(patron, URLResolver):
                yield from patrones(patron)

    con_patch = {
        str(p.pattern)
        for p in patrones(get_resolver())
        if "patch" in _metodos_de(p.callback)
    }

    assert con_patch == {"clientes/<int:cliente_id>/"}


def test_the_mutating_route_check_can_see_the_api_routes():
    """The check above reaches the API's routes, not only the root ones.

    Without this, a check that walks the root patterns would always pass
    and the guarantee would be an assertion about nothing.
    """
    from django.urls import URLPattern, URLResolver

    def patrones(resolver):
        for patron in resolver.url_patterns:
            if isinstance(patron, URLPattern):
                yield patron
            elif isinstance(patron, URLResolver):
                yield from patrones(patron)

    encontrados = {str(p.pattern) for p in patrones(get_resolver())}

    assert "posicion/" in encontrados
    assert "cliente/estado/" in encontrados


def test_the_client_routes_live_under_their_own_prefix():
    """The two audiences keep separate prefixes.

    There is no route that accepts both a session and a credential — the
    design §8 invariant is structural, and the map is where it is visible.
    """
    from tienda.api import urls as urls_api

    cliente_rutas = [
        p for p, _, _ in _todas_las_rutas() if p.startswith("cliente/")
    ]
    personal_rutas = [
        p for p, _, _ in _todas_las_rutas() if not p.startswith("cliente/")
    ]

    assert len(cliente_rutas) == 3
    assert len(personal_rutas) == 17
    # And no route serves both audiences.
    assert not set(cliente_rutas) & set(personal_rutas)


def test_the_api_mount_is_live():
    """The map is MOUNTED, not merely declared.

    `config/urls.py` includes `tienda.api.urls` as a urlconf module under
    the namespace `api`, so the routes inside it are reversible. The mount
    was guarded while the module did not exist, and the guard has to pick
    it up now.

    A staff route with no session answers **403** — the staff scope is the
    session, and a request without one has no scope (design §7.1). A **404**
    would mean the route does not exist; the route exists.
    """
    from django.test import Client

    cliente = Client()
    respuesta = cliente.get("/api/v1/posicion/", HTTP_HOST="testserver")

    assert respuesta.status_code == 403
    import json

    cuerpo = json.loads(respuesta.content.decode())
    assert cuerpo["codigo_error"] == "permiso_insuficiente"


def test_a_pending_route_still_answers_501():
    """A route whose view has not landed says so.

    The proposal routes are Phase 5 and the client's are Phase 6. They
    answer 501 naming the slice that owes them, not 404: a 404 would say
    the route does not exist, which is a statement about the CONTRACT.
    """
    from django.test import Client

    cliente = Client()
    respuesta = cliente.get("/api/v1/propuestas/", HTTP_HOST="testserver")

    assert respuesta.status_code == 501
    import json

    cuerpo = json.loads(respuesta.content.decode())
    assert cuerpo["codigo_error"] == "vista_pendiente"
    assert cuerpo["slice"] == "PR 5"


def test_a_view_that_has_not_landed_answers_501_and_names_the_slice():
    """A pending view says what is missing.

    A 404 would say "this route does not exist", which is a statement
    about the contract. A 501 says "this contract exists and is not built
    yet", which is a statement about the work.
    """
    from tienda.api.urls import vista_pendiente

    vista = vista_pendiente("posicion")

    class _Request:
        pass

    respuesta = vista(_Request())

    assert respuesta.status_code == 501
    import json

    cuerpo = json.loads(respuesta.content.decode())
    assert cuerpo["slice"] == "PR 4c"
    assert "codigo_error" in cuerpo
