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

#: The two shop roles, as the Django group names of design §7.
GRUPO_DUENO = "dueno"
GRUPO_DEPENDIENTE = "dependiente"


def _en_grupo(user, nombre: str) -> bool:
    """Whether `user` belongs to the Django group `nombre`.

    The check reads the group ids rather than the group objects, so it is
    one query per group and never touches a row of another shop.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return user.groups.filter(name=nombre).exists()


def es_dueno(user) -> bool:
    """Whether the user is in the `dueno` group."""
    return _en_grupo(user, GRUPO_DUENO)


def es_dependiente(user) -> bool:
    """Whether the user is in the `dependiente` group."""
    return _en_grupo(user, GRUPO_DEPENDIENTE)


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
    """The acting user must belong to one of the named shop roles.

    The message carries no request data: it says which role was required and
    nothing about who the request is.
    """

    def __init__(self, *roles: str):
        super().__init__()
        self.roles = roles

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        return any(_en_grupo(user, rol) for rol in self.roles)

    def has_object_permission(self, request, view, obj) -> bool:
        # The object-level check is the shop filter, and it lives in the
        # queryset: `current_shop(request)` scopes every row before it is
        # fetched, so there is never an unscoped object to check.
        return True


class IsDueno(BasePermission):
    """The acting user must be in the `dueno` group.

    The credit book is the owner's alone. The `dependiente` answers 403 on
    every credit-book route, with no partial data in any field
    (design §7.1).
    """

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        return es_dueno(user)

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
