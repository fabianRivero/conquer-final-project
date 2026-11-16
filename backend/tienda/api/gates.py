"""The N5 gate - design §7.1, §2 D6, §18.3.

**The gate is closed.** On the current decision the `dependiente` reaches
none of the four proposal routes, and the refusal is total: 403 with no
partial data in any field (design §7.1).

The gate exists as a **named, single decision** rather than as an `if`
repeated in four views, for two reasons:

* the four views must answer the same way, and a decision copied four
  times is a decision that will drift;
* the gate is a **decision under a declared hypothesis**, not a permanent
  fact. The design names the hypothesis: when the shop owners validate the
  flow, the `dependiente` may gain exactly one capability - the proposal
  **it** prepared, and no more. Flipping the gate is therefore a one-line
  change here, and no view is touched when it opens.

The gate governs the `dependiente` only. The `dueno` owns the credit book
and is never gated: preparing, confirming and cancelling a proposal are
the owner's acts.

What the gate does NOT do: it does not decide *which* proposal a
`dependiente` may reach. That is the object-level rule - a `dependiente`
reaches the proposal it prepared and no other - and it lives with the
queryset that fetches the proposal, because the shop scope and the
ownership scope are both filters on the same read.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from tienda.api.permissions import GRUPO_DEPENDIENTE, _en_grupo

#: Whether the N5 gate is open.
#:
#: It is **closed**: the validation round with the shop owners has not been
#: run, and the design takes the gate as a decision under a declared
#: hypothesis (§18.3). When that round opens the gate, this constant is the
#: ONLY thing that changes - the four views read it and never hard-code a
#: refusal.
N5_ABIERTA = False


class PuertaN5(BasePermission):
    """The N5 gate, applied to the four proposal routes.

    While the gate is **closed**, the `dependiente` is refused with the
    total 403 of design §7.1: no alias, no customer identifier, no
    `codigo`, no prefix, no count - not in the body, not in a header, not
    in the error message.

    While it is **open**, the `dependiente` passes the gate and the
    object-level rule takes over: it reaches the proposal it prepared and
    no other.
    """

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        # The owner is never gated: the credit book is the owner's alone.
        if not _en_grupo(user, GRUPO_DEPENDIENTE):
            return True
        # A `dependiente` passes only when the gate is open.
        return N5_ABIERTA
