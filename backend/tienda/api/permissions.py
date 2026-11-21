"""The permission model of design §7 — two scopes, and they never mix.

Three principals, and only two of them are roles:

* the **staff** — a Django user in the group `dueno` or `dependiente`,
  resolved from the session;
* the **client** — a bearer credential scoped to one `Customer`, resolved
  from the `X-Codigo` header.

**Each principal class has exactly one source of scope, and the scope is a
property of the ROUTE, never of the request.** A staff route reads the
session and ignores any `X-Codigo`; a client route reads the header and
refuses a request that carries a staff session cookie. There is no route
that accepts both — the design §8.

Three mechanisms carry that invariant, and this module is two of them:

* `RoleRequired` and `IsDueno` — the staff side, by Django group;
* `EsCliente` — the client side, by credential;
* `current_shop(request)` — the **single reader** of the staff scope. Every
  staff queryset is filtered through it, so a request can never reach a row
  of another shop.

The third mechanism — `resolver_credencial` — lives in `client_auth.py`,
because it needs the credential machinery of task 4.16. The split is
deliberate: `permissions.py` knows about roles and shops, and nothing else.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from tienda.api.exceptions import (
    CODIGO_PERMISO_INSUFICIENTE,
    CUERPO_PERMISO_INSUFICIENTE,
)

#: The two shop roles. They live in the `MiembroDeTienda` - the
#: MEMBERSHIP - and not in a global Django group: a `dependiente` of one
#: shop is a `dependiente` of that shop and of no other, and a global
#: group said nothing about which shop it belonged to.
GRUPO_DUENO = "dueno"
GRUPO_DEPENDIENTE = "dependiente"


def rol_en_la_tienda(user, shop_id) -> str | None:
    """The role `user` holds in the shop `shop_id`, or `None`.

    **The role is the relation's, and the relation names the shop.** A
    `dependiente` of one shop is a `dependiente` of that shop and of no
    other, and the query says so: it filters by BOTH the person and the
    shop. The old check - a global group - answered "is this person a
    `dependiente`?" and the answer was the same in every shop.

    `None` means **no role in this shop**, and it is a refusal: there is
    no default role and no fallback.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if shop_id is None:
        return None

    from tienda.models import MiembroDeTienda

    return (
        MiembroDeTienda.objects.filter(
            user=user, perfil_tienda__shop_id=shop_id
        )
        .values_list("rol", flat=True)
        .first()
    )


def es_dueno(user, shop_id=None) -> bool:
    """Whether the user is the OWNER of the shop.

    The shop is the session's: the role belongs to a membership, and a
    membership belongs to a shop. When the caller has no shop - the
    login, which is choosing one - the answer is `False`.
    """
    return rol_en_la_tienda(user, shop_id) == GRUPO_DUENO


def es_dependiente(user, shop_id=None) -> bool:
    """Whether the user is a `dependiente` of the shop."""
    return rol_en_la_tienda(user, shop_id) == GRUPO_DEPENDIENTE


def current_shop(request):
    """The shop of the acting staff session — the **only** reader of it.

    The scope is `request.session["shop_id"]`, written at login and never
    read from a request parameter or a body field. The shop id itself is
    never taken from the URL: the URL names a customer, not a shop.

    A request with no staff session, or with a session that names no shop,
    has **no** staff scope, and every staff endpoint answers 403. There is
    no default shop and no fallback: a missing scope is a refusal, not an
    absence.
    """
    session = getattr(request, "session", None)
    if session is None:
        return None
    shop_id = session.get("shop_id")
    if shop_id is None:
        return None
    return shop_id


def exigir_shop(request):
    """The shop of the acting staff session, or a refusal.

    The refusal raises DRF's `PermissionDenied`, which the handler of
    `exceptions.py` turns into the fixed 403 body — no request data, no
    identifier, no count.
    """
    shop_id = current_shop(request)
    if shop_id is None:
        raise PermissionDenied(CUERPO_PERMISO_INSUFICIENTE["detail"])
    return shop_id


class RoleRequired(BasePermission):
    """The acting user must hold one of the named roles **in the session's shop**.

    DRF instantiates the classes in `permission_classes`, so the roles
    cannot be constructor arguments: a view declares
    `permission_classes = [RoleRequired]` and the roles live in the class
    attribute `roles`. A subclass names them:

        class CashView(APIView):
            permission_classes = [RoleRequired]
            roles = ("dueno", "dependiente")

    **The role is checked against the session's shop.** The membership
    names the shop, so a `dependiente` of one shop holds no role in
    another - and a request whose session names no shop is refused
    outright.

    The message carries no request data: it says which role was required and
    nothing about who the request is.
    """

    #: The roles that are admitted. Overridden by the subclass.
    roles: tuple[str, ...] = ()

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        shop_id = current_shop(request)
        if shop_id is None:
            return False
        return rol_en_la_tienda(user, shop_id) in self.roles

    def has_object_permission(self, request, view, obj) -> bool:
        # The object-level check is the shop filter, and it lives in the
        # queryset: `current_shop(request)` scopes every row before it is
        # fetched, so there is never an unscoped object to check.
        return True


class SoloPersonal(RoleRequired):
    """The two shop roles, and only them.

    The cash, the close and the position are the shop's business: the
    `dueno` and the `dependiente` may both take part in them, and the
    client may not.
    """

    roles = (GRUPO_DUENO, GRUPO_DEPENDIENTE)


class SoloDueno(RoleRequired):
    """The `dueno`, and only the `dueno`.

    The credit book's POLICY is the owner's alone: the `credit_limit`, the
    suspension, the catalogue and the credential answer 403 to the
    `dependiente`, with no partial data in any field (design §7.1).

    The `dependiente` READS the credit book - it collects the payments -
    and it does so through a **reduced schema** that declares the debts
    and none of these fields. The reading and the policy are two
    different capabilities.
    """

    roles = (GRUPO_DUENO,)


class IsDueno(BasePermission):
    """The acting user must be the OWNER of the session's shop.

    The credit book's POLICY is the owner's alone. The `dependiente`
    answers 403 on every credit-book route, with no partial data in any
    field (design §7.1).
    """

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        return es_dueno(user, current_shop(request))

    def has_object_permission(self, request, view, obj) -> bool:
        return True


class EsCliente(BasePermission):
    """The acting principal must be a client, resolved from the credential.

    The credential itself is resolved by `resolver_credencial` in
    `client_auth.py`; this permission only asserts the **shape** of the
    request: a client route must not be reached by a staff session.

    A request that carries a staff session cookie is **refused**, even if
    it also presents a valid `X-Codigo`. There is no upgrade in either
    direction (design §7.2, invariant 1).
    """

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            # A staff session reached a client route. Refused before any
            # customer data is read.
            return False
        return getattr(request, "cliente", None) is not None

    def has_object_permission(self, request, view, obj) -> bool:
        return True


def cliente_de(request):
    """The customer resolved from the credential, or `None`.

    The single reader of the client scope's identity. The customer is
    attached to the request by `resolver_credencial`; this reads it and
    nothing else, so a view cannot reach a customer by another route.
    """
    return getattr(request, "cliente", None)
