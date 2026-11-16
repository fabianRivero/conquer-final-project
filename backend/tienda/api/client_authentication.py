"""The client authentication - the class that resolves the credential.

`client_auth.py` resolves the IDENTITY: the one `Customer` the presented
credential belongs to. It deliberately does not decide what may be done
with it - that is the route's business, and `permissions.py` decides it.

The wiring problem: DRF's `EsCliente` permission reads `request.cliente`,
and a permission runs AFTER the authentication. So the credential has to
be resolved and ATTACHED to the request by something that runs earlier.
An **authentication class** is exactly that place: DRF calls
`authenticate()` before it checks the permissions.

**The recursion, and why this module avoids it.** DRF's `request.user`
and `request.headers` are LAZY: the first access calls
`_authenticate()`, which calls this class's `authenticate()` again. So
reading `request.user` from inside `authenticate()` is an infinite
recursion - and so is reading `request.headers`, because the header
property touches the same lazy machinery.

The rule this module follows: **inside `authenticate()`, the request is
read through `request._request`**, the plain Django `HttpRequest` under
the DRF wrapper. It carries the same headers and the same session, and
it has no lazy authentication of its own.

The class does two things and no more:

* it resolves the credential and attaches the customer to the request;
* it refuses a presentation that the throttle must refuse.

**The refusal is byte-identical in all three cases** - unknown, revoked
and throttled - because the throttle must not be an oracle. The class
returns `None` (no authentication) rather than raising, so the answer
is the route's 422 `codigo_invalido`, and a client route never falls
through to a staff route's answer.

**A staff session is not a client.** When the request carries an
authenticated staff session, the class does not authenticate it as a
client: the two principals never mix, and `EsCliente` refuses a staff
session anyway.
"""

from __future__ import annotations

from rest_framework.authentication import BaseAuthentication


def _peticion_plana(request):
    """The plain Django request under the DRF wrapper.

    Inside `authenticate()` this is the only safe way to read the
    request: the DRF wrapper's `user` and `headers` are lazy and would
    call `authenticate()` again.
    """
    return getattr(request, "_request", request)


class CredencialCliente(BaseAuthentication):
    """The client credential, resolved before the permissions run.

    It attaches the resolved customer to `request.cliente`, which is
    what `EsCliente` and `cliente_de(request)` read.
    """

    def authenticate(self, request):
        from tienda.api.client_auth import resolver_credencial
        from tienda.api.exceptions import DomainValidationError

        # The plain request: reading the DRF wrapper's lazy properties
        # here would call this method again, and the recursion would
        # never end.
        peticion = _peticion_plana(request)

        # A staff session is a different principal. It is not
        # authenticated here, and `EsCliente` refuses it anyway.
        usuario = getattr(peticion, "user", None)
        if usuario is not None and getattr(usuario, "is_authenticated", False):
            return None

        cliente = resolver_credencial(peticion)
        if cliente is None:
            # The refusal is the DOMAIN one: `422 codigo_invalido`, the
            # same answer an unknown, a revoked and a throttled
            # credential get. The throttle must not be an oracle, and a
            # 401 would say "this endpoint needs authentication" - a
            # statement about the route rather than about the
            # credential.
            #
            # Raising here rather than returning `None` matters: a
            # `None` would let DRF mark the request unauthenticated, and
            # the PERMISSION would then answer 401. The contract names
            # 422.
            raise DomainValidationError("codigo_invalido")

        # The customer is attached to the DRF request, because that is
        # what the permission and the view read.
        request.cliente = cliente
        # DRF's authentication contract is a (user, auth) pair. The
        # client is not a Django user, so the first element is `None`
        # and the credential is the second - and the pair is never
        # turned into a session, because no session framework is
        # involved.
        return (None, cliente)

    def authenticate_header(self, request):
        """The header the credential travels in, for the 401 answer."""
        from tienda.api.client_auth import CABECERA

        return CABECERA
