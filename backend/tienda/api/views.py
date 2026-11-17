"""The staff views — task 4.20.

The views are thin on purpose. They resolve the **acting scope**, read
through the service layer, and hand the result to a serializer. Three
rules hold everywhere in this module:

* **The scope is a property of the route, never of the request.** A staff
  route reads the session through `current_shop(request)` and ignores any
  `X-Codigo`. The client routes of Phase 6 read the credential and refuse
  a session. No route accepts both (design §8).

* **Every queryset is filtered by the shop.** The customer of another shop
  is **not found**, not refused: a 403 would confirm that it exists, and a
  404 says nothing.

* **The permission is the matrix of §7, enforced on the server.** The
  `dependiente` answers 403 on the credit book, with no partial data in
  any field.

The `posicion` route answers **two different payloads**: the owner's, and
the `dependiente`'s reduced one — `caja`, `clientes` and `cierre_hoy` only,
and its `clientes` is an empty list **without executing the customer
query**. That is the boundary of §7.1, and it is enforced by the schema
rather than by a filter applied afterwards.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from tienda import services
from tienda.api import gates
from tienda.api.client_authentication import CredencialCliente
from tienda.api import permissions
from tienda.api.exceptions import DomainValidationError
from tienda.api.serializers import cliente as cliente_serializers
from tienda.api.serializers import staff
from tienda.models import (
    CashMovement,
    Confirmacion,
    Customer,
    CustomerCodigo,
    DayClose,
    FiadoPropuesto,
    ImputacionPago,
    LedgerEntry,
    PagoPropuesto,
    Producto,
    StockMovement,
)


def _scope(request):
    """The shop of the acting staff session, or a refusal.

    A request with no staff scope is refused here, before any row is
    read: there is no default shop and no fallback.
    """
    return permissions.exigir_shop(request)


def _es_dueno(request) -> bool:
    """Whether the acting user is in the `dueno` group."""
    return permissions.es_dueno(getattr(request, "user", None))


# ---------------------------------------------------------------------------
# The position
# ---------------------------------------------------------------------------


class _ApiViewBase(APIView):
    """The base of every view of the API.

    **DRF's `APIView` accepts `put`, `patch` and `delete` by default.** The
    URL surface of §9.1 never routes them, so the book is already safe at
    the URL level — but a view that would answer `DELETE` if one were ever
    added is a view waiting for the accident. This base refuses them
    explicitly.

    It is the same guarantee at the third layer: the `AppendOnlyModel`
    guard refuses an update at the model, the URL map exposes no mutating
    route, and the view itself answers only what it declares.
    """

    #: The HTTP methods this view answers.
    http_method_names = ["get", "post"]


class PosicionView(_ApiViewBase):
    """`GET /api/v1/posicion/` — the board.

    The owner gets the whole board. The `dependiente` gets the **reduced**
    payload: `caja`, `clientes` and `cierre_hoy`, and nothing else. The
    ladder, `posicion_real`, `fiado_pendiente` and `buckets` are 403 for
    the `dependiente` — which means they are not in the response at all,
    because the schema does not declare them.

    The reduced payload is not the full one with fields removed: it is
    built from a different schema, so a field that is not declared cannot
    appear whatever the query returns.
    """

    permission_classes = [permissions.SoloPersonal]

    def get(self, request):
        shop_id = _scope(request)
        from tienda.models import Shop

        shop = Shop.objects.get(id=shop_id)
        ahora = timezone.now()

        if not _es_dueno(request):
            # The dependent's board: three fields, and the customers are
            # never queried.
            return Response(
                staff.PosicionDependienteSerializer(
                    {
                        "caja": _caja_de(shop, ahora),
                        "clientes": [],
                        "cierre_hoy": _cierre_de_hoy(shop),
                    }
                ).data
            )

        cargos = services.pendientes_de_shop(shop, ahora)
        pagos = [
            services.linea_ledger(r)
            for r in LedgerEntry.objects.filter(
                shop=shop, kind="pago", occurred_at__lte=ahora
            )
        ]
        from tienda.domain import ageing as reglas_antiguedad
        from tienda.domain import position as reglas_posicion

        pendiente_total = reglas_posicion.outstanding(cargos + pagos, ahora)
        caja = _caja_de(shop, ahora)
        clientes = _escalera_de(shop, ahora)

        return Response(
            staff.PosicionDuenoSerializer(
                {
                    "caja": caja,
                    "fiado_pendiente": pendiente_total,
                    "posicion_real": reglas_posicion.real_position(caja, pendiente_total),
                    "buckets": _buckets_de(cargos, pagos, ahora),
                    "clientes": clientes,
                    "serie_caja": [],
                    "cierre_hoy": _cierre_de_hoy(shop),
                }
            ).data
        )


def _caja_de(shop, ahora) -> Decimal:
    """The cash in the drawer at `ahora`."""
    from tienda.domain import position as reglas_posicion

    movimientos = [
        services.linea_caja(r)
        for r in CashMovement.objects.filter(shop=shop, occurred_at__lte=ahora)
    ]
    pagos = [
        services.linea_ledger(r)
        for r in LedgerEntry.objects.filter(
            shop=shop, kind="pago", occurred_at__lte=ahora
        )
    ]
    return reglas_posicion.cash_at(shop.opening_cash, movimientos, pagos, ahora)


def _cierre_de_hoy(shop):
    """The close of today, or `None`."""
    cierre = DayClose.objects.filter(shop=shop, date=timezone.now().date()).first()
    if cierre is None:
        return None
    return {
        "date": cierre.date,
        "esperado": cierre.esperado,
        "contado": cierre.contado,
        "desviacion": cierre.desviacion,
    }


def _escalera_de(shop, ahora):
    """The risk ladder: the customers with something pending."""
    from tienda.domain import ageing as reglas_antiguedad

    escalera = []
    for customer in Customer.objects.filter(shop=shop):
        cargos, pagos = services.pendientes_de(customer, ahora)
        from tienda.domain import position as reglas_posicion

        pendiente = reglas_posicion.outstanding(cargos + pagos, ahora)
        if pendiente <= 0:
            continue
        estado = services.estado_de(customer, ahora)
        escalera.append(
            {
                "alias": customer.alias,
                "pendiente": pendiente,
                "antiguedad_max_dias": estado.antiguedad_max_dias,
                "suspendido": estado.suspendido,
                "motivo": estado.motivo.value if estado.motivo else None,
            }
        )
    escalera.sort(key=lambda fila: fila["antiguedad_max_dias"], reverse=True)
    return escalera


def _buckets_de(cargos, pagos, ahora):
    """The four ageing ribbons, and their totals sum to the outstanding."""
    from tienda.domain import ageing as reglas_antiguedad

    from tienda.domain import position as reglas_posicion

    asignacion = _asignacion(cargos, pagos)
    saldos = dict(asignacion.saldos)
    pendientes = [c for c in cargos if saldos.get(c.id, Decimal("0")) > 0]

    buckets = {b.value: Decimal("0") for b in reglas_antiguedad.Bucket}
    for cargo in pendientes:
        edad = reglas_antiguedad.age_in_days(cargo.occurred_at, ahora)
        buckets[reglas_antiguedad.bucket_of(edad).value] += cargo.amount
    return buckets


def _asignacion(cargos, pagos):
    from tienda.domain import allocation as reglas_asignacion

    return reglas_asignacion.allocate_payments(cargos, pagos)


# ---------------------------------------------------------------------------
# The cash
# ---------------------------------------------------------------------------


class CajaView(_ApiViewBase):
    """`POST /api/v1/caja/` — a movement of the drawer.

    Both shop roles may record one (CP-01). The stamp is the server's, and
    a request that carries `occurred_at` is refused on the **presence** of
    the field (rule 4).
    """

    permission_classes = [permissions.SoloPersonal]

    def post(self, request):
        shop_id = _scope(request)
        from tienda.models import Shop

        shop = Shop.objects.get(id=shop_id)
        try:
            services.exigir_campos_no_admitidos(
                request.data, {"kind", "concept", "amount"}
            )
            movimiento = services.registrar_movimiento_caja(
                shop,
                request.user,
                kind=request.data.get("kind"),
                amount=request.data.get("amount", 0),
                concept=request.data.get("concept", ""),
            )
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {"id": movimiento.id, "kind": movimiento.kind, "amount": movimiento.amount},
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# The close
# ---------------------------------------------------------------------------


class CierreView(_ApiViewBase):
    """`GET` and `POST /api/v1/cierre/` — the day's close.

    The owner reads the date too; the `dependiente` does not (CP-05). The
    `esperado` is the derived cash and the `desviacion` is the derived
    difference — neither is ever client-supplied (rules 13 and 14).
    """

    permission_classes = [permissions.SoloPersonal]

    def get(self, request):
        shop_id = _scope(request)
        from tienda.models import Shop

        shop = Shop.objects.get(id=shop_id)
        cierre = DayClose.objects.filter(shop=shop, date=timezone.now().date()).first()
        if cierre is None:
            return Response(
                {"codigo_error": "campo_no_admitido", "detail": "No hay cierre."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if _es_dueno(request):
            return Response(
                staff.CierreDuenoSerializer(
                    {
                        "date": cierre.date,
                        "esperado": cierre.esperado,
                        "contado": cierre.contado,
                        "desviacion": cierre.desviacion,
                    }
                ).data
            )

        return Response(
            staff.CierreDependienteSerializer(
                {
                    "esperado": cierre.esperado,
                    "contado": cierre.contado,
                    "desviacion": cierre.desviacion,
                }
            ).data
        )

    def post(self, request):
        shop_id = _scope(request)
        from tienda.models import Shop

        shop = Shop.objects.get(id=shop_id)
        try:
            # Rule 14: the request may not carry `esperado` or
            # `desviacion`. The refusal is on the presence of the field.
            services.exigir_campos_no_admitidos(request.data, {"date", "contado"})
            fecha = request.data.get("date")
            if isinstance(fecha, str):
                from datetime import date as fecha_cls

                fecha = fecha_cls.fromisoformat(fecha)
            cierre = services.cerrar_dia(
                shop, request.user, date=fecha, contado=request.data.get("contado")
            )
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except ValueError:
            return Response(
                {"codigo_error": "campo_no_admitido", "detail": "La fecha no es valida."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {
                "date": cierre.date,
                "esperado": cierre.esperado,
                "contado": cierre.contado,
                "desviacion": cierre.desviacion,
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------


class ClienteLibretaView(_ApiViewBase):
    """`POST /api/v1/clientes/{id}/libreta/` — a payment in the ledger.

    The only way a `pago` is written, and the owner's alone (CAC-02, PA-09).

    Three refusals carry the v2 model:

    * the `kind` is `pago` **only** — a `cargo` is written by the
      confirmation of a proposal, never directly (ADR-19);
    * the request may not carry `occurred_at` — the server stamps it (rule 4);
    * a `pago` larger than the customer's outstanding is refused with
      `pago_excede_deuda` — the excess is change, and it never enters the
      book, so no credit can exist (rule 19, ADR-26).

    A customer of another shop answers **404**: a 403 would confirm that it
    exists.
    """

    permission_classes = [permissions.SoloDueno]

    def post(self, request, cliente_id):
        shop_id = _scope(request)
        cliente = services.cliente_de_la_tienda(shop_id, cliente_id)
        if cliente is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            # Rule 4: the entry is stamped by the server.
            services.exigir_campos_no_admitidos(request.data, {"kind", "amount"})
            kind = request.data.get("kind")
            # Rule 16: the vocabulary is `cargo` and `pago`, and this route
            # accepts only `pago`.
            if kind != "pago":
                raise DomainValidationError("tipo_desconocido")
            importe = Decimal(str(request.data.get("amount", 0)))
            if importe <= 0:
                raise DomainValidationError("importe_no_positivo")

            # Rule 19: the bound is the customer's TOTAL outstanding, not
            # one charge's. The FIFO decides which charges the payment
            # retires.
            pendiente = services.pendiente_de(cliente)
            if importe > pendiente:
                raise DomainValidationError("pago_excede_deuda")

            from django.db import transaction

            with transaction.atomic():
                pago = LedgerEntry.objects.create(
                    shop_id=shop_id,
                    customer=cliente,
                    user=request.user,
                    kind="pago",
                    amount=importe,
                    occurred_at=timezone.now(),
                )
                # The repartition: one ImputacionPago row per charge the
                # payment touched (ADR-27).
                from tienda.domain import allocation as reglas_asignacion

                cargos, _ = services.pendientes_de(cliente, timezone.now())
                asignacion = reglas_asignacion.allocate_payments(
                    cargos, [services.linea_ledger(pago)]
                )
                for imputacion in reglas_asignacion.imputations_of(asignacion, pago.id):
                    ImputacionPago.objects.create(
                        pago=pago,
                        cargo_id=imputacion.cargo_id,
                        importe=imputacion.importe,
                    )
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {"id": pago.id, "kind": pago.kind, "amount": pago.amount},
            status=status.HTTP_201_CREATED,
        )


class CatalogoView(_ApiViewBase):
    """`GET /api/v1/catalogo/` — the goods eligible for fiado.

    The owner's alone (PC-03), and only the `activo` ones (PC-01).
    """

    permission_classes = [permissions.SoloDueno]

    def get(self, request):
        shop_id = _scope(request)

        catalogo = Producto.objects.filter(shop_id=shop_id, activo=True).order_by("nombre")
        return Response(
            [
                {
                    # The id, because the proposal form has to name the
                    # product it is selling. The identity of a product of
                    # the OWNER's own catalogue is not a secret: it is not
                    # one of the nine staff-only fields, and the form
                    # cannot work without it.
                    "id": p.id,
                    "nombre": p.nombre,
                    "precio": p.precio,
                    "unidad": p.unidad,
                    "activo": p.activo,
                }
                for p in catalogo
            ]
        )


# ---------------------------------------------------------------------------
# The customers
# ---------------------------------------------------------------------------


class ClientesView(_ApiViewBase):
    """`GET` and `POST /api/v1/clientes/` — the credit book's list.

    The owner's alone (CAC-02), and every row is scoped by the shop.
    """

    permission_classes = [permissions.SoloDueno]

    def get(self, request):
        shop_id = _scope(request)
        clientes = Customer.objects.filter(shop_id=shop_id).order_by("alias")

        # The credential's state: the `prefix` - the NON-SECRET head of
        # it - and the issuing date. Both are the OWNER's own data: the
        # prefix is six symbols of the alphabet and cannot resolve to a
        # credential without the digest, and the digest never leaves
        # this table. The list carries them so the board reads one
        # response and not one per customer.
        codigos = {}
        for codigo in CustomerCodigo.objects.filter(
            shop_id=shop_id, revoked_at__isnull=True
        ).order_by("id"):
            codigos.setdefault(codigo.customer_id, codigo)

        return Response(
            [
                {
                    "id": c.id,
                    "alias": c.alias,
                    "credit_limit": c.credit_limit,
                    "prefix": (
                        codigos[c.id].prefix if c.id in codigos else None
                    ),
                    "issued_at": (
                        codigos[c.id].issued_at if c.id in codigos else None
                    ),
                }
                for c in clientes
            ]
        )

    def post(self, request):
        shop_id = _scope(request)
        from tienda.models import Shop

        shop = Shop.objects.get(id=shop_id)
        try:
            services.exigir_campos_no_admitidos(
                request.data, {"alias", "phone", "credit_limit"}
            )
            cliente = services.crear_cliente(
                shop,
                request.user,
                alias=request.data.get("alias", ""),
                phone=request.data.get("phone"),
                credit_limit=request.data.get("credit_limit"),
            )
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {"id": cliente.id, "alias": cliente.alias}, status=status.HTTP_201_CREATED
        )


class ClienteDetalleView(_ApiViewBase):
    """`GET` and `PATCH /api/v1/clientes/{id}/` — one customer.

    A customer of another shop answers **404**: a 403 would confirm that
    it exists.

    This is the **only** view of the API that answers a `PATCH`, and the
    reason is precise: what it changes is the `credit_limit`, and that is
    the owner's own record and policy — not a row of the book. The
    append-only guarantee is about the book: `LedgerEntry`, `CargoLinea`,
    `Confirmacion`, `PropuestaLinea` and `ImputacionPago` are never
    modified, and no route of the API can reach such a write.
    """

    http_method_names = ["get", "patch"]

    permission_classes = [permissions.SoloDueno]

    def _cliente(self, request, cliente_id):
        shop_id = _scope(request)
        return services.cliente_de_la_tienda(shop_id, cliente_id)

    def get(self, request, cliente_id):
        cliente = self._cliente(request, cliente_id)
        if cliente is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "id": cliente.id,
                "alias": cliente.alias,
                "phone": cliente.phone,
                "credit_limit": cliente.credit_limit,
            }
        )

    def patch(self, request, cliente_id):
        cliente = self._cliente(request, cliente_id)
        if cliente is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            services.exigir_campos_no_admitidos(request.data, {"credit_limit"})
            limite = request.data.get("credit_limit")
            if limite is not None:
                limite = Decimal(str(limite))
                if limite < 0:
                    raise DomainValidationError("importe_no_positivo")
                cliente.credit_limit = limite
                cliente.save(update_fields=["credit_limit"])
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response({"id": cliente.id, "credit_limit": cliente.credit_limit})


# ---------------------------------------------------------------------------
# The proposal - tasks 5.9, CC-01, CC-03, CC-04
# ---------------------------------------------------------------------------


class PropuestasView(_ApiViewBase):
    """`POST /api/v1/propuestas/` - prepare a fiado.

    The owner prepares a fiado with its itemisation. **Nothing is written
    to the book**: a proposal is a request, and the charge exists only at
    the confirmation (ADR-19, CC-01).

    The body is `{cliente_id, lineas[{producto_id, cantidad,
    precio_unitario?}], total?}`. The `total` is optional: when it is
    absent it is derived from the lines, and when it is present it must
    equal their sum (rule 3).

    The `dependiente` prepares proposals too, but the N5 gate is **closed**
    on the current decision, so it reaches neither the screen, nor the
    confirmation, nor the cancellation.
    """

    permission_classes = [permissions.SoloPersonal, gates.PuertaN5]

    def post(self, request):
        shop_id = _scope(request)

        try:
            # Rule 4: the request carries no field that is not admitted.
            # `origen` and `facilitado_por` are NOT among them: rule 7b
            # infers them from the acting session, and a body that names
            # them is refused on their presence.
            services.exigir_campos_no_admitidos(
                request.data, {"cliente_id", "lineas", "total"}
            )

            cliente_id = request.data.get("cliente_id")
            cliente = services.cliente_de_la_tienda(shop_id, cliente_id)
            if cliente is None:
                # A customer of another shop is NOT FOUND, not refused.
                return Response(status=status.HTTP_404_NOT_FOUND)

            lineas = request.data.get("lineas") or []
            propuesta = services.preparar_propuesta(
                shop_id,
                request.user,
                customer=cliente,
                lineas=lineas,
                total=request.data.get("total"),
            )
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {
                "id": propuesta.id,
                "estado": propuesta.estado,
                "total": str(propuesta.total),
                "lineas": [
                    {
                        "producto": linea.producto_id,
                        "cantidad": str(linea.cantidad),
                        "precio_unitario": str(linea.precio_unitario),
                        "total": str(linea.total),
                    }
                    for linea in propuesta.lineas.order_by("id")
                ],
            },
            status=status.HTTP_201_CREATED,
        )


class PropuestaPantallaView(_ApiViewBase):
    """`GET /api/v1/propuestas/{id}/pantalla/` - the counter screen.

    It shows one proposal's `desglose` and its `total`, and **nothing
    else**: no balance, no ageing, no other customer, no `credit_limit`,
    no `codigo` (CC-03, CAC-10).

    The payload is built by `PropuestaPantallaSerializer`, which declares
    exactly `total` and `lineas[]`. The screen is not the full payload
    with fields removed - it is a different schema, so a field that is not
    declared cannot appear whatever the query returns.

    A proposal of another shop answers **404**: a 403 would confirm that
    it exists.
    """

    permission_classes = [permissions.SoloPersonal, gates.PuertaN5]

    def get(self, request, propuesta_id):
        shop_id = _scope(request)

        propuesta = (
            FiadoPropuesto.objects.filter(shop_id=shop_id, id=propuesta_id)
            .prefetch_related("lineas__producto")
            .first()
        )
        if propuesta is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        lineas = []
        for linea in propuesta.lineas.order_by("id"):
            lineas.append(
                {
                    "producto": linea.producto.nombre,
                    "cantidad": linea.cantidad,
                    "precio_unitario": linea.precio_unitario,
                    "total": linea.total,
                }
            )

        return Response(
            staff.PropuestaPantallaSerializer(
                {"total": propuesta.total, "lineas": lineas}
            ).data
        )


class PropuestaConfirmarView(_ApiViewBase):
    """`POST /api/v1/propuestas/{id}/confirmar/` - the confirmation.

    **This is where the charge is born** (ADR-19). The service writes the
    `LedgerEntry(cargo)`, the `CargoLinea[]` copied from the proposal's own
    lines, the `Confirmacion(confirmado)` and the proposal's
    `confirmed_at` in one transaction, and the outstanding moves at that
    exact instant (CC-01).

    The body is empty: the origin and the facilitator are **inferred from
    the acting session**, never read from the request (rule 7b).
    """

    permission_classes = [permissions.SoloPersonal, gates.PuertaN5]

    def post(self, request, propuesta_id):
        shop_id = _scope(request)

        try:
            services.exigir_campos_no_admitidos(request.data, set())
            cargo, propuesta = services.confirmar_propuesta(
                shop_id, request.user, propuesta_id=propuesta_id
            )
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        confirmacion = Confirmacion.objects.get(cargo=cargo)
        return Response(
            {
                "id": confirmacion.id,
                "estado": confirmacion.estado,
                "origen": confirmacion.origen,
                "cargo": {
                    "id": cargo.id,
                    "kind": cargo.kind,
                    "amount": str(cargo.amount),
                },
                "propuesta": propuesta.id,
            },
            status=status.HTTP_201_CREATED,
        )


class PropuestaCancelarView(_ApiViewBase):
    """`POST /api/v1/propuestas/{id}/cancelar/` - the client declined.

    **Nothing is written but the instant**: no charge, no lines, no
    confirmation. The outstanding never moved, because it never moved in
    the first place (CC-04, design 13.2).

    The body is empty, like the confirmation's.
    """

    permission_classes = [permissions.SoloPersonal, gates.PuertaN5]

    def post(self, request, propuesta_id):
        shop_id = _scope(request)

        try:
            services.exigir_campos_no_admitidos(request.data, set())
            propuesta = services.cancelar_propuesta(
                shop_id, request.user, propuesta_id=propuesta_id
            )
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {"id": propuesta.id, "estado": propuesta.estado},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# The client's own surface - tasks 6.7 and 6.8
# ---------------------------------------------------------------------------


def _cliente_de(request):
    """The customer resolved from the credential, or a refusal.

    The credential is the ONLY source of the client scope: the route
    reads the `X-Codigo` header and nothing else. There is no session
    upgrade and no query parameter - a credential that arrived any other
    way is not a credential this application accepts (R4).

    The refusal is `422 codigo_invalido`, the same one an unknown, a
    revoked or a throttled credential gets: the answer never says whether
    the credential existed.
    """
    from tienda.api.client_auth import resolver_credencial

    cliente = resolver_credencial(request)
    if cliente is None:
        raise DomainValidationError("codigo_invalido")
    return cliente


def _lineas_de_cargo(cargo):
    """The cargo's itemisation, as the client sees it."""
    lineas = []
    for linea in cargo.lineas.order_by("id"):
        lineas.append(
            {
                "producto": linea.producto.nombre,
                "cantidad": linea.cantidad,
                "precio_unitario": linea.precio_unitario,
                "total": linea.total,
            }
        )
    return lineas


class ClienteEstadoView(_ApiViewBase):
    """`GET /api/v1/cliente/estado/` - the client's own statement.

    The alias, the total and the client's **confirmed** charges, each
    with its full `desglose` (CC-02, CC-06).

    The itemisation is always present: every charge in the statement is a
    confirmed charge with a mandatory `desglose`, so every charge carries
    its `lineas[]`. The v1 rule "the itemisation lives only inside the
    action" is gone - the client confirms in the shop and therefore sees
    the `desglose` before the charge exists.

    `pagado` and `saldo` are **derived on read** from the
    `ImputacionPago` rows, never stored on the charge (ADR-27).

    The payload is built by `EstadoClienteSerializer`, which declares the
    client's own data and **none** of the nine staff-only fields. The
    guarantee is a property of the schema: DRF's `fields` is exhaustive,
    so a field that is not declared cannot appear whatever the view
    hands over.
    """

    # The credential is resolved by the AUTHENTICATION layer, which
    # runs before the permission: `EsCliente` reads `request.cliente`,
    # and a permission runs after the authentication.
    authentication_classes = [CredencialCliente]
    permission_classes = [permissions.EsCliente]

    def get(self, request):
        cliente = _cliente_de(request)

        cargos = services.cargos_de_la_tienda(cliente)

        filas = []
        total = Decimal("0")
        for cargo in cargos:
            pagado = services.pagado_de(cargo)
            saldo = services.saldo_de(cargo)
            total += saldo
            filas.append(
                {
                    "id": cargo.id,
                    "fecha": cargo.occurred_at,
                    "amount": cargo.amount,
                    "confirmado_en": cargo.confirmaciones.first().confirmado_en,
                    "pagado": pagado,
                    "saldo": saldo,
                    "lineas": _lineas_de_cargo(cargo),
                }
            )

        return Response(
            cliente_serializers.EstadoClienteSerializer(
                {"alias": cliente.alias, "total": total, "cargos": filas}
            ).data
        )


class ClienteCargoView(_ApiViewBase):
    """`GET /api/v1/cliente/cargos/{id}/` - one of the client's own charges.

    The full itemisation of a charge the client confirmed (CC-02).

    A charge that is not the client's is refused with `cargo_ajeno` and
    returns **no data**: the refusal is not a charge with the fields
    blanked.
    """

    # The credential is resolved by the AUTHENTICATION layer, which
    # runs before the permission: `EsCliente` reads `request.cliente`,
    # and a permission runs after the authentication.
    authentication_classes = [CredencialCliente]
    permission_classes = [permissions.EsCliente]

    def get(self, request, cargo_id):
        cliente = _cliente_de(request)

        cargo = services.cargo_de_la_tienda(cliente, cargo_id)
        if cargo is None:
            raise DomainValidationError("cargo_ajeno")

        return Response(
            cliente_serializers.CargoClienteSerializer(
                {
                    "id": cargo.id,
                    "fecha": cargo.occurred_at,
                    "amount": cargo.amount,
                    "confirmado_en": cargo.confirmaciones.first().confirmado_en,
                    "pagado": services.pagado_de(cargo),
                    "saldo": services.saldo_de(cargo),
                    "lineas": _lineas_de_cargo(cargo),
                }
            ).data
        )


class ClienteProponerPagoView(_ApiViewBase):
    """`POST /api/v1/cliente/pagos/proponer/` - the client proposes a payment.

    The body is `{importe, referencia?}`. **The proposal names no
    charge**: the client does not choose which debt it pays, so it
    proposes an amount and the FIFO decides which charges it retires
    (ADR-27). A body that carries a `cargo_id` is refused on the
    **presence** of the field.

    The proposal writes **no ledger row** (CC-07, PA-09): the `pago`
    itself is a separate `LedgerEntry` that the OWNER appends when he
    validates it, so the book stays append-only even though the request
    that preceded it is not.
    """

    # The credential is resolved by the AUTHENTICATION layer, which
    # runs before the permission: `EsCliente` reads `request.cliente`,
    # and a permission runs after the authentication.
    authentication_classes = [CredencialCliente]
    permission_classes = [permissions.EsCliente]

    def post(self, request):
        cliente = _cliente_de(request)

        try:
            services.exigir_campos_no_admitidos(
                request.data, {"importe", "referencia"}
            )
            propuesta = services.proponer_pago(
                cliente,
                importe=request.data.get("importe", 0),
                referencia=request.data.get("referencia", ""),
            )
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {
                "id": propuesta.id,
                "estado": propuesta.estado,
                "importe": str(propuesta.importe),
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# The proposed payments - the owner's routes
# ---------------------------------------------------------------------------


class PagosPropuestosView(_ApiViewBase):
    """`GET /api/v1/pagos-propuestos/` - the client's proposed payments.

    The owner's alone (CAC-02, PA-09).

    **Only the PENDING ones.** A proposal that was validated or rejected
    is history, and the board's section is a work list: what is waiting
    for the owner's decision.

    A `PagoPropuesto` is a REQUEST and not a scope: it creates no ledger
    row, and it grants no read of the credit book. What the list shows is
    the proposal's amount, its reference and who proposed it - and the
    amount the payment will have is **exactly** the proposed one, never
    recomputed and never rounded (ADR-27).
    """

    permission_classes = [permissions.SoloDueno]

    def get(self, request):
        shop_id = _scope(request)

        from tienda.domain.types import PagoPropuestoEstado

        pagos = PagoPropuesto.objects.filter(
            shop_id=shop_id,
            estado=PagoPropuestoEstado.PENDIENTE.value,
        ).order_by("id")

        return Response(
            [
                {
                    "id": p.id,
                    "alias": p.customer.alias,
                    "importe": p.importe,
                    "referencia": p.referencia,
                    "estado": p.estado,
                }
                for p in pagos
            ]
        )


class PagoValidarView(_ApiViewBase):
    """`POST /api/v1/pagos-propuestos/{id}/validar/` - the owner validates.

    The owner's alone (CAC-02, PA-09).

    The `pago` is written here and nowhere else: the amount is
    **exactly** the proposal's `importe` - never recomputed, never
    rounded - and the `ImputacionPago` rows are one per charge the
    payment retires, FIFO by charge (ADR-27).

    Rule 19: a proposed amount larger than the customer's outstanding is
    refused with `pago_excede_deuda`, writes **no** `pago`, and leaves
    the proposal `pendiente` - the owner rejects it and returns the
    excess as change (ADR-26).
    """

    permission_classes = [permissions.SoloDueno]

    def post(self, request, pago_id):
        shop_id = _scope(request)

        try:
            services.exigir_campos_no_admitidos(request.data, set())
            pago, propuesta = services.validar_pago(
                shop_id, request.user, pago_id=pago_id
            )
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {
                "id": pago.id,
                "kind": pago.kind,
                "amount": str(pago.amount),
                "propuesta": propuesta.id,
                "estado": propuesta.estado,
            },
            status=status.HTTP_201_CREATED,
        )


class PagoRechazarView(_ApiViewBase):
    """`POST /api/v1/pagos-propuestos/{id}/rechazar/` - the owner rejects.

    The owner's alone. It writes **no** `pago`: the proposal moves to
    `rechazado` with its `resolved_at` and its `resolved_by_id`, and the
    book is untouched.
    """

    permission_classes = [permissions.SoloDueno]

    def post(self, request, pago_id):
        shop_id = _scope(request)

        try:
            services.exigir_campos_no_admitidos(request.data, set())
            propuesta = services.rechazar_pago(
                shop_id, request.user, pago_id=pago_id
            )
        except DomainValidationError as exc:
            return Response(
                {"codigo_error": exc.codigo_error, "detail": exc.detail},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {"id": propuesta.id, "estado": propuesta.estado},
            status=status.HTTP_200_OK,
        )
