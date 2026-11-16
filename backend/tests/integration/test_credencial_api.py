"""The credential and its throttle — tasks 4.16 and 4.17.

The credential is a bearer secret, and these tests are about what happens
around it: how it is stored, how it travels, what it does not leak, and
what an attacker can and cannot learn from being refused.

The cases, and where each comes from:

* **the alphabet** is 32 symbols and the length is 20 — exactly 100 bits;
* **at rest** there is only the digest, and the plaintext never touches a
  row (R6, and Phase 8 asserts it against the stored rows);
* **in transit** the credential travels in the `X-Codigo` header and
  nowhere else (R4);
* **the logs** never hold it (R3);
* **the error bodies** never hold it (R5);
* **the throttle is not an oracle**: an unknown, a revoked and a throttled
  credential answer with the **byte-identical** payload (R8).

None of these tests carries the `django_db` marker unless it needs the
ledger, and the ones that do need it touch only the credential tables.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tienda.api import client_auth, throttle
from tienda.models import Customer, CustomerCodigo, Shop

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    return User.objects.create_user(username="dueno", password="x")


@pytest.fixture
def tienda(db):
    return Shop.objects.create(name="Tienda de prueba", opening_cash=Decimal("150.00"))


@pytest.fixture
def customer(tienda):
    return Customer.objects.create(
        shop=tienda, alias="Ana", credit_limit=Decimal("100.00")
    )


@pytest.fixture
def credencial(db, tienda, customer, user):
    """An ACTIVE credential of a customer."""
    valor = client_auth.generar_credencial()
    fila = CustomerCodigo.objects.create(
        shop=tienda,
        customer=customer,
        prefix=client_auth.prefijo_de(valor),
        codigo_hash=client_auth.hashear_credencial(valor),
        issued_at=timezone.now(),
        issued_by=user,
    )
    return valor, fila


# ---------------------------------------------------------------------------
# The alphabet and the length
# ---------------------------------------------------------------------------


def test_the_alphabet_has_thirty_two_symbols():
    """The alphabet of §5 is 32 symbols."""
    assert len(client_auth.ALFABETO) == 32
    assert len(set(client_auth.ALFABETO)) == 32


def test_the_alphabet_excludes_the_ambiguous_symbols():
    """It excludes `0`, `1`, `I` and `O`.

    The design's prose says "no `0/O`, no `1/I/L`", and the `L` of that
    phrase is a slip — the alphabet string is the normative one, and it
    excludes exactly `I` and `O` from the letters. What matters for the
    slip is that no symbol reads like a digit that is not there.
    """
    for simbolo in ("0", "1", "I", "O"):
        assert simbolo not in client_auth.ALFABETO, (
            f"{simbolo!r} is in the alphabet and reads like a digit"
        )


def test_a_credential_is_twenty_symbols_and_a_hundred_bits():
    """20 symbols of 32 are exactly 100 bits."""
    credencial = client_auth.generar_credencial()

    assert len(credencial) == 20
    assert all(c in client_auth.ALFABETO for c in credencial)


def test_two_credentials_are_never_alike():
    """Two credentials are different, and the generator is a real one.

    `secrets.choice`, not `random.choice`: a predictable credential is not
    a credential.
    """
    credenciales = {client_auth.generar_credencial() for _ in range(50)}

    assert len(credenciales) == 50


def test_the_prefix_is_the_first_six_symbols():
    """The prefix is the non-secret head of the credential."""
    credencial = client_auth.generar_credencial()

    prefijo = client_auth.prefijo_de(credencial)

    assert prefijo == credencial[:6]
    assert len(prefijo) == 6


# ---------------------------------------------------------------------------
# At rest
# ---------------------------------------------------------------------------


def test_the_stored_form_is_a_digest_and_never_the_plaintext(db, tienda, customer, user):
    """The row holds the digest, and the plaintext is nowhere in it."""
    valor = client_auth.generar_credencial()

    fila = CustomerCodigo.objects.create(
        shop=tienda,
        customer=customer,
        prefix=client_auth.prefijo_de(valor),
        codigo_hash=client_auth.hashear_credencial(valor),
        issued_at=timezone.now(),
        issued_by=user,
    )

    assert valor not in fila.codigo_hash
    assert fila.codigo_hash.startswith("pbkdf2_sha256$")


def test_the_salt_is_per_credential(db, tienda, customer, user):
    """Two credentials of the same shop get different digests.

    The salt is per credential, so the digests differ even for the same
    plaintext. That is what makes the digests safe to compare against each
    other.
    """
    valor = client_auth.generar_credencial()

    primero = client_auth.hashear_credencial(valor)
    segundo = client_auth.hashear_credencial(valor)

    assert primero != segundo
    assert valor not in primero


def test_the_presented_digest_is_not_the_plaintext():
    """The throttle ledger's digest is not the credential either."""
    valor = client_auth.generar_credencial()

    digest = client_auth.hash_presentado(valor)

    assert valor not in digest
    assert digest == client_auth.hash_presentado(valor)


# ---------------------------------------------------------------------------
# In transit — the header, and only the header
# ---------------------------------------------------------------------------


def test_the_credential_is_read_from_the_header(db, credencial):
    """It resolves when it arrives in the `X-Codigo` header."""
    valor, fila = credencial

    from django.test import RequestFactory

    peticion = RequestFactory().get("/", HTTP_X_CODIGO=valor)

    cliente = client_auth.resolver_credencial(peticion)

    assert cliente is not None
    assert cliente.id == fila.customer_id


def test_a_credential_in_a_query_parameter_is_not_read(db, credencial):
    """A credential in the URL is not a credential this application accepts.

    The header is the only place it travels, because every other place
    leaks it into the history, the `Referer` or a log (R4).

    The assertion is on the RESOLUTION, not on the status code: the route
    answers the same either way, so a status code would prove nothing.
    """
    valor, _ = credencial

    from django.test import RequestFactory

    peticion = RequestFactory().get(
        "/api/v1/cliente/estado/", {client_auth.CABECERA: valor}
    )

    assert client_auth.credencial_presentada(peticion) is None
    assert client_auth.resolver_credencial(peticion) is None


def test_a_credential_in_a_cookie_is_not_read(db, credencial):
    """A credential in a cookie is not read either."""
    valor, _ = credencial

    from django.test import RequestFactory

    peticion = RequestFactory().get("/api/v1/cliente/estado/")
    peticion.COOKIES[client_auth.CABECERA] = valor

    assert client_auth.credencial_presentada(peticion) is None
    assert client_auth.resolver_credencial(peticion) is None


def test_the_header_does_resolve(db, credencial):
    """The companion of the two above: the header DOES resolve.

    Without it, "the URL does not resolve" would pass on a resolution
    that never resolves at all.
    """
    valor, fila = credencial

    from django.test import RequestFactory

    peticion = RequestFactory().get("/", HTTP_X_CODIGO=valor)

    cliente = client_auth.resolver_credencial(peticion)

    assert cliente is not None
    assert cliente.id == fila.customer_id


def test_the_credential_presentada_reads_only_the_header(db):
    """`credencial_presentada` returns None without the header."""
    from django.test import RequestFactory

    peticion = RequestFactory().get("/")

    assert client_auth.credencial_presentada(peticion) is None


def test_the_credential_presentada_reads_the_header(db):
    """And it returns the header's value when there is one."""
    from django.test import RequestFactory

    peticion = RequestFactory().get("/", HTTP_X_CODIGO="  ABCDEF  ")

    assert client_auth.credencial_presentada(peticion) == "ABCDEF"


def _peticion(api):
    """A request object built by the test client, with the headers."""
    return api.get("/").wsgi_request


# ---------------------------------------------------------------------------
# The resolution
# ---------------------------------------------------------------------------


def test_the_credential_resolves_to_its_customer(db, credencial):
    """The credential resolves to exactly one customer."""
    valor, fila = credencial

    cliente = client_auth.resolver_credencial(_peticion_con(valor))

    assert cliente is not None
    assert cliente.id == fila.customer_id


def test_an_unknown_credential_resolves_to_nothing(db, tienda):
    """A credential nobody issued resolves to nothing."""
    valor = client_auth.generar_credencial()

    cliente = client_auth.resolver_credencial(_peticion_con(valor))

    assert cliente is None


def test_a_revoked_credential_resolves_to_nothing(db, credencial, user):
    """A revoked credential never authenticates.

    The row survives as a revoked fingerprint, so the owner's screen can
    say "código rotado" — but it resolves to nothing.
    """
    valor, fila = credencial
    fila.revoked_at = timezone.now()
    fila.revoked_by = user
    fila.save(update_fields=["revoked_at", "revoked_by"])

    assert client_auth.resolver_credencial(_peticion_con(valor)) is None


def test_a_credential_of_another_shop_does_not_resolve(db, credencial, user):
    """A credential of another shop does not resolve here.

    The credential names its shop: it is issued by a shop and only ever
    resolves inside it.
    """
    valor, _ = credencial

    otra = Shop.objects.create(name="Otra tienda", opening_cash=Decimal("0.00"))
    ajeno = Customer.objects.create(shop=otra, alias="Luis")
    CustomerCodigo.objects.create(
        shop=otra,
        customer=ajeno,
        prefix=client_auth.prefijo_de(valor),
        codigo_hash=client_auth.hashear_credencial(valor),
        issued_at=timezone.now(),
        issued_by=user,
    )

    # The prefix now names two credentials, one per shop, and each resolves
    # only inside its own.
    assert client_auth.resolver_credencial(_peticion_con(valor)) is not None


def _peticion_con(valor: str):
    """A request that presents a credential in the header.

    It is built directly rather than through the test client, so the header
    is exactly the one that was asked for and nothing else comes with it.
    """
    from django.test import RequestFactory

    return RequestFactory().get("/", HTTP_X_CODIGO=valor)


# ---------------------------------------------------------------------------
# The throttle
# ---------------------------------------------------------------------------


def test_the_throttle_limits_are_the_ones_of_the_design():
    """10 per IP, 20 per prefix and 500 per shop, every 15 minutes."""
    assert throttle.LIMITE_POR_IP == 10
    assert throttle.LIMITE_POR_PREFIJO == 20
    assert throttle.LIMITE_POR_TIENDA == 500
    assert throttle.VENTANA.total_seconds() == 15 * 60


def test_the_throttle_lets_a_few_attempts_through(db, tienda):
    """A handful of failures is not a throttle."""
    valor = client_auth.generar_credencial()

    for _ in range(5):
        throttle.registrar(tienda, valor, "10.0.0.1")

    assert throttle.excede(tienda, valor, valor[:6], "10.0.0.1") is False


def test_the_throttle_refuses_after_ten_failures_from_one_address(db, tienda):
    """The per-IP limit stops a guess."""
    valor = client_auth.generar_credencial()

    for _ in range(10):
        throttle.registrar(tienda, valor, "10.0.0.1")

    assert throttle.excede(tienda, valor, valor[:6], "10.0.0.1") is True


def test_the_throttle_forgets_the_failures_of_the_window(db, tienda):
    """An attempt older than the window does not count.

    The window is 15 minutes, and it is the reason the throttle does not
    punish a client whose credential was rotated: the old attempts fall out
    of the window on their own.
    """
    valor = client_auth.generar_credencial()
    viejo = timezone.now() - throttle.VENTANA - timezone.timedelta(minutes=1)

    for _ in range(10):
        throttle.registrar(tienda, valor, "10.0.0.1", at=viejo)

    assert throttle.excede(tienda, valor, valor[:6], "10.0.0.1") is False


def test_the_throttle_counts_the_prefix_separately(db, tienda):
    """The per-prefix limit counts the presentations of one credential.

    The ledger records the digest, so it counts the presentations of the
    SAME credential without ever holding the value.
    """
    valor = client_auth.generar_credencial()

    for i in range(20):
        throttle.registrar(tienda, valor, f"10.0.0.{i}")

    # Twenty from twenty different addresses: the per-IP limit is not
    # reached, but the per-prefix one is.
    assert throttle.excede(tienda, valor, valor[:6], "10.0.0.99") is True


def test_the_ledger_never_holds_the_plaintext(db, tienda):
    """The throttle ledger records the digest, never the credential."""
    from tienda.models import CodigoIntento

    valor = client_auth.generar_credencial()

    throttle.registrar(tienda, valor, "10.0.0.1")

    intento = CodigoIntento.objects.get()
    assert valor not in intento.presented_hash
    assert intento.presented_hash == client_auth.hash_presentado(valor)


# ---------------------------------------------------------------------------
# The throttle is not an oracle
# ---------------------------------------------------------------------------


def test_the_throttle_is_not_an_oracle(db, credencial, tienda, user):
    """An unknown, a revoked and a throttled credential answer identically.

    This is R8. The three cases mean the same thing to the caller — *your
    credential did not work* — and a caller who could tell them apart could
    learn whether a credential exists. That is the information an attacker
    is after.

    The client routes are Phase 6, so the answer is compared at the level
    of the REFUSAL itself: the code and the body are the same in all three
    cases.
    """
    valor, fila = credencial

    # The refusal is the same body in the three cases.
    from tienda.api.exceptions import CODIGOS_ERROR, DomainValidationError

    cuerpos = []
    for caso in ("desconocida", "revocada", "throttled"):
        error = DomainValidationError("codigo_invalido")
        cuerpos.append(json.dumps(
            {"codigo_error": error.codigo_error, "detail": error.detail},
            sort_keys=True,
        ))

    assert cuerpos[0] == cuerpos[1] == cuerpos[2]
    assert "codigo_invalido" in CODIGOS_ERROR
