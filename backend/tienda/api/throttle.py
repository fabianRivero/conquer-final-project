"""The throttle ledger — `throttle.py`, task 4.17.

A credential is a bearer secret, and a secret that can be guessed in
silence is a secret that will be guessed. The throttle counts the failed
presentations and refuses the ones that come too fast.

**The throttle is never an oracle.** This is the whole point of the
module. An unknown credential, a **revoked** credential and a **throttled**
credential all answer with the **byte-identical** `422 / codigo_invalido`
payload. A caller who could tell them apart could learn whether a
credential exists, and that is exactly the information an attacker is
after. The three cases are refused the same way because they mean the same
thing to the caller: *your credential did not work*.

The limits of design §5: **10 failures per IP every 15 minutes, 20 per
prefix every 15 minutes, and 500 per shop**. The first two are the ones
that stop a guess; the third is the backstop for a distributed attempt
that rotates its source address.

**The ledger holds the hash of what was presented, never the value.** It
counts attempts, and it is not a second credential store: the database
must not be a place where a credential can be read.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from tienda.api.client_auth import hash_presentado, registrar_intento
from tienda.models import CodigoIntento

#: How long the window of the per-IP and per-prefix limits is.
VENTANA = timedelta(minutes=15)

#: The failures allowed per source address in the window.
LIMITE_POR_IP = 10

#: The failures allowed per prefix in the window.
LIMITE_POR_PREFIJO = 20

#: The failures allowed per shop in the window.
LIMITE_POR_TIENDA = 500


def excede(shop, credencial: str, prefijo: str, source_ip: str, at=None) -> bool:
    """Whether this presentation must be refused.

    Three counters, and the presentation is refused when **any** of them is
    exhausted. The per-shop one is the backstop against a distributed
    attempt that rotates its address.

    The per-prefix counter counts the presentations of the **same**
    credential, by its digest — so the ledger counts them without ever
    holding the value.
    """
    momento = at or timezone.now()
    desde = momento - VENTANA

    fallos = CodigoIntento.objects.filter(shop=shop, at__gte=desde)

    por_ip = fallos.filter(source_ip=source_ip).count()
    if por_ip >= LIMITE_POR_IP:
        return True

    por_prefijo = fallos.filter(presented_hash=hash_presentado(credencial)).count()
    if por_prefijo >= LIMITE_POR_PREFIJO:
        return True

    por_tienda = fallos.count()
    if por_tienda >= LIMITE_POR_TIENDA:
        return True

    return False


def registrar(shop, credencial: str, source_ip: str, at=None):
    """Record a failed presentation in the ledger.

    It records the **digest** of what was presented. A throttle ledger that
    held the credentials would be a second credential store, and the whole
    point of the design is that the database is not one.
    """
    return registrar_intento(shop, credencial, source_ip, at=at)
