"""The client credential — `client_auth.py`, task 4.16.

The `codigo` is a **bearer credential** scoped to exactly one `Customer`. It
opens **read** over the client's own statement and the right to **propose**
a payment. It opens **no write**: no `LedgerEntry`, no `CargoLinea`, no
`Confirmacion`, no `FiadoPropuesto`, no `PagoPropuesto` resolution.

**The credential is presented in the `X-Codigo` header, and only there.**
Never in a query parameter, a cookie, a body field or a URL fragment. A
credential in a URL is a credential in the browser's history, in the
`Referer` of every outbound request and in every proxy's log — and the
credential never resolves to a customer of another shop, so leaking it
leaks exactly one client's statement.

**At rest there is only the digest.** The plaintext exists for the length
of one response — the issuing response — and nowhere else. The hash is
Django's `PBKDF2PasswordHasher`, whose encoded form carries the
**per-credential salt** itself, so `check_password` verifies against it
without the salt ever being a column.

**The verification compares every candidate.** The prefix narrows the
search, but the work does not depend on which row matched: every candidate
with that prefix is compared, so the time taken does not reveal which one
was the right one.

**The credential does not resolve into a scope on its own.** The client
scope is a property of the ROUTE. This module resolves the identity — the
one `Customer` — and the route decides what may be done with it.
"""

from __future__ import annotations

import hashlib
import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from tienda.api.exceptions import DomainValidationError
from tienda.models import CodigoIntento, CustomerCodigo

#: The alphabet of design §5: 32 symbols, 100 bits at 20 symbols.
#:
#: It excludes `I` and `O` — the letters that read like a one and a zero —
#: and it excludes the digits `0` and `1`. The design's prose says "no
#: `0/O`, no `1/I/L`", and the `L` of that phrase is a slip: the alphabet
#: string itself is the normative one, and it has 32 symbols and excludes
#: exactly `I` and `O` from the letters. The string is what this module
#: uses, so the credential and the design agree on the same 32 symbols.
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

#: The length of a credential, in symbols. 20 symbols are 100 bits.
LONGITUD = 20

#: The length of the non-secret `prefix`: the first six symbols.
LONGITUD_PREFIJO = 6

#: The header the credential is presented in. It is the only place it travels.
CABECERA = "X-Codigo"


def generar_credencial() -> str:
    """A fresh credential: 20 symbols of the 32-symbol alphabet.

    The choice is `secrets.choice`, never `random.choice`: the credential
    is a secret, and a predictable one is not a credential.

    The symbols come out in blocks of four for legibility on the printed
    slip — the grouping is a property of the PRINTING, not of the value.
    The value stored and presented is the ungrouped string.
    """
    return "".join(secrets.choice(ALFABETO) for _ in range(LONGITUD))


def prefijo_de(credencial: str) -> str:
    """The non-secret head of a credential: its first six symbols.

    The prefix is **not** independent entropy. A stolen hash plus the prefix
    leaves 70 bits of the 100 — still infeasible to brute force — and the
    prefix narrows the candidates the server has to compare.
    """
    return credencial[:LONGITUD_PREFIJO]


def hashear_credencial(credencial: str) -> str:
    """The stored form of a credential: the PBKDF2 digest.

    Django's default `PBKDF2PasswordHasher` is **not** overridden, and its
    encoded form carries the per-credential salt and the iteration count
    beside the digest. The salt is therefore never a column: it lives
    inside the hash, which is what makes it per-credential.
    """
    return make_password(credencial)


def hash_presentado(credencial: str) -> str:
    """The digest of a **presented** credential, for the throttle ledger.

    The throttle records what was PRESENTED so that a repeated attempt can
    be counted. It records the hash, never the plaintext: a throttle ledger
    that held the credentials would be a second credential store, and the
    whole point of the design is that the database is not a credential store.
    """
    return hashlib.sha256(credencial.encode("utf-8")).hexdigest()


def candidates_para(prefijo: str):
    """The active credentials of EVERY shop with that prefix.

    The prefix is unique **inside a shop**, not across shops: the database
    constraint is `UNIQUE (shop_id, prefix)`. So the same six symbols may
    name a credential in two different shops, and the resolution has to
    consider both.

    That is not a weakness — it is the reason every candidate is compared.
    The work does not depend on which one matched, so the time taken
    reveals nothing about the credential.
    """
    return CustomerCodigo.objects.filter(
        prefix=prefijo,
        revoked_at__isnull=True,
    )


def resolver_credencial(request):
    """The `Customer` the presented credential belongs to, or `None`.

    The credential travels in the `X-Codigo` header and **only** there. A
    credential presented any other way — a query parameter, a cookie, a
    body field — is refused, and the refusal is the same one an unknown
    credential gets: `422 / codigo_invalido`. The answer never says whether
    the credential existed, was revoked, or was throttled.

    The credential names its own shop: the shop is the one of the matching
    `CustomerCodigo`, and the client scope it opens is that shop's. It is
    never taken from the request — the URL does not name a shop, and the
    staff session's `shop_id` has nothing to do with a client request.
    """
    credencial = credencial_presentada(request)
    if credencial is None:
        return None

    prefijo = prefijo_de(credencial)
    for fila in candidates_para(prefijo):
        if check_password(credencial, fila.codigo_hash):
            return fila.customer
    return None


def tienda_de_la_credencial(credencial: str):
    """The shop a credential belongs to, or `None`.

    It is the shop of the matching `CustomerCodigo`. When several shops
    share a prefix, the one whose credential actually matches is the one —
    so the shop is resolved from the **credential**, never guessed from the
    prefix.
    """
    prefijo = prefijo_de(credencial)
    for fila in candidates_para(prefijo):
        if check_password(credencial, fila.codigo_hash):
            return fila.shop
    return None


def credencial_presentada(request) -> str | None:
    """The credential the request presents, or `None`.

    It is read from the header and from **nowhere else**. A credential in
    the query string, in a cookie or in the body is not a credential this
    application accepts: the header is the only place it travels, because
    every other place leaks it into the history, the `Referer` or a log.
    """
    valor = request.headers.get(CABECERA)
    if not valor:
        return None
    valor = valor.strip()
    if not valor:
        return None
    return valor


def registrar_intento(shop, credencial: str, source_ip: str, at=None) -> CodigoIntento:
    """Record a presented credential in the throttle ledger.

    The ledger holds the **hash** of what was presented, never the value:
    it counts attempts, and it is not a second credential store.
    """
    return CodigoIntento.objects.create(
        shop=shop,
        source_ip=source_ip,
        presented_hash=hash_presentado(credencial),
        at=at or timezone.now(),
    )
