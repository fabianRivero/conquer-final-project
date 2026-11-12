"""The 422 contract of design §9.3 — one shape for every validation failure.

Every validation failure is **HTTP 422** with exactly two keys:

    {"codigo_error": "<code>", "detail": "<Spanish message>"}

The vocabulary is **closed**. Seventeen codes, and a code that is not in the
list is not a code this application may emit: an unknown vocabulary entry is
a programming error, and it is raised as one rather than being sent to the
client.

Three properties this module exists to guarantee:

* **The code is from the vocabulary.** `CODIGOS_ERROR` is the single source
  of truth, and `DomainValidationError` refuses a code that is not in it.
* **No submitted value is echoed.** The `detail` is a fixed Spanish message
  per code, never a string built from the request. A submitted value that
  reaches the body is a value that can reach a log, a traceback or a
  screenshot.
* **The 403 carries no request data either.** A refusal says `permiso_insuficiente`
  and nothing else — no alias, no identifier, no count. The dependent's
  403 boundary of design §7.1 is a *total* refusal.

The codes that are gone are gone: `disputa_abierta` and `importe_reclamado`
died with the dispute machinery, and `cargo_no_indicado` died with the
client's ability to name a charge (ADR-27).
"""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

# ---------------------------------------------------------------------------
# The vocabulary
# ---------------------------------------------------------------------------

#: Every code this application may answer with, and the fixed Spanish message
#: that goes with it. The message is a CONSTANT: it is never built from the
#: request, so no submitted value can reach the response body.
CODIGOS_ERROR = {
    "limite_superado": "El cliente supera su limite de credito.",
    "antiguedad_superada": "El cliente tiene una deuda demasiado antigua.",
    "importe_no_positivo": "El importe debe ser mayor que cero.",
    "campo_no_admitido": "El campo enviado no se admite.",
    "tipo_desconocido": "El tipo enviado no se admite.",
    "cierre_duplicado": "Ese dia ya esta cerrado.",
    "lineas_descuadradas": "El total no cuadra con las lineas.",
    "cargo_ya_confirmado": "Ese cargo ya esta confirmado.",
    "propuesta_ya_confirmada": "Esa propuesta ya esta confirmada.",
    "propuesta_ya_cancelada": "Esa propuesta ya esta cancelada.",
    "pago_ya_resuelto": "Esa propuesta de pago ya esta resuelta.",
    "pago_excede_deuda": "El pago no puede exceder la deuda pendiente.",
    "codigo_invalido": "La credencial no es valida.",
    "codigo_duplicado": "Ese prefijo de credencial ya existe.",
    "cargo_ajeno": "Ese cargo no es de este cliente.",
    "producto_ajeno": "Ese producto no es de esta tienda.",
    "facilitador_invalido": "El facilitador no es valido.",
}

#: The code a refusal answers with. It is NOT part of the validation
#: vocabulary: a 403 is not a validation failure.
CODIGO_PERMISO_INSUFICIENTE = "permiso_insuficiente"

#: The fixed message of the 403. No request data reaches it.
DETALLE_PERMISO_INSUFICIENTE = "No tienes permiso para esta operacion."

#: The 403 body, exactly as it goes on the wire.
CUERPO_PERMISO_INSUFICIENTE = {
    "codigo_error": CODIGO_PERMISO_INSUFICIENTE,
    "detail": DETALLE_PERMISO_INSUFICIENTE,
}


# ---------------------------------------------------------------------------
# The domain error
# ---------------------------------------------------------------------------


class DomainValidationError(Exception):
    """A rule of design §3.2 refused the operation.

    The service layer raises it with a `codigo_error` from `CODIGOS_ERROR`
    and no payload. The exception handler turns it into the 422 body.

    A code outside the vocabulary is a **programming error**, not a client
    error: it raises `ValueError` here rather than travelling to the client
    as a code nobody documented.
    """

    def __init__(self, codigo_error: str, detail: str | None = None):
        if codigo_error not in CODIGOS_ERROR:
            raise ValueError(
                f"{codigo_error!r} is not in the error vocabulary of design "
                f"section 9.3. The vocabulary is closed: a code that is not "
                f"in it is a bug, not a refusal."
            )
        self.codigo_error = codigo_error
        # The detail defaults to the fixed message of the code. A caller MAY
        # pass a more specific one, but it must never contain a submitted
        # value: the handler does not check that, and the rule is the
        # author's.
        self.detail = detail or CODIGOS_ERROR[codigo_error]
        super().__init__(f"{codigo_error}: {self.detail}")


# ---------------------------------------------------------------------------
# The handler
# ---------------------------------------------------------------------------


def _cuerpo_422(codigo_error: str, detail: str) -> dict:
    """The 422 body: exactly two keys."""
    return {"codigo_error": codigo_error, "detail": detail}


def _manejador_dominio(exc: DomainValidationError, context) -> Response:
    """Turn a `DomainValidationError` into the 422 body."""
    return Response(
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        data=_cuerpo_422(exc.codigo_error, exc.detail),
    )


def handler(exc, context):
    """The DRF exception handler of design §9.3.

    The order matters:

    1. a `DomainValidationError` is the 422 of the contract;
    2. a DRF `ValidationError` — a malformed body — is also a 422, and its
       code is `campo_no_admitido` unless the caller named one;
    3. a `PermissionDenied` is a 403 with the fixed body and **no request
       data**;
    4. a `NotFound` is a 404 with the same two-key shape;
    5. anything else falls through to DRF's own handler.
    """
    if isinstance(exc, DomainValidationError):
        return _manejador_dominio(exc, context)

    if isinstance(exc, DjangoValidationError):
        # Django's own validation error, raised by the ORM or by a model.
        # The per-row codes are the service's job; this is the fallback for
        # a constraint the service did not translate.
        codigo = getattr(exc, "codigo_error", None) or "campo_no_admitido"
        if codigo not in CODIGOS_ERROR:
            codigo = "campo_no_admitido"
        return Response(
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            data=_cuerpo_422(codigo, CODIGOS_ERROR[codigo]),
        )

    if isinstance(exc, Http404):
        return Response(
            status=status.HTTP_404_NOT_FOUND,
            data=_cuerpo_422("campo_no_admitido", "El recurso no existe."),
        )

    response = drf_exception_handler(exc, context)

    if response is not None and response.status_code == status.HTTP_403_FORBIDDEN:
        # A 403 carries no request data. The dependent's 403 boundary is a
        # total refusal: no alias, no identifier, no count, and nothing that
        # could be read as "this customer exists".
        return Response(
            status=status.HTTP_403_FORBIDDEN,
            data=dict(CUERPO_PERMISO_INSUFICIENTE),
        )

    return response
