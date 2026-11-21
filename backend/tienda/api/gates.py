"""The N5 gate - design §7.1, §2 D6, §18.3.

**The gate is OPEN.** The owner has decided that the `dependiente`
operates the counter: it prepares a fiado, confirms it, cancels it, reads
the credit book and collects the payments.

The decision is a **product decision under a declared hypothesis**, not
field evidence. The project's `knowledge_basis` stays
`design-hypothesis`: the validation round with the shop owners has not
been run, and the owner's decision does not pretend otherwise. What
changed is that the conditional capability is no longer *absent* - it is
present, and its boundary is written down here.

**What the gate does NOT decide.** The gate is about the ROLE, not about
the OBJECT. A `dependiente` that passes the gate reaches the four
proposal routes, and each of them filters by **ownership**: a
`dependiente` confirms and cancels only the proposals **it prepared**.
Nobody confirms somebody else's, and the refusal is a **404**, not a 403,
because a 403 would confirm that the proposal exists.

The ownership filter lives with the queryset that fetches the proposal,
because the shop scope and the ownership scope are filters on the same
read.

**What the gate does NOT open.** The gate is not a licence for the
`dependiente` to touch the owner's policy. The `credit_limit`, the
suspension, the catalogue and the credential stay the owner's, and the
`dependiente` reads the credit book through a **reduced schema** that
declares the debts and none of those fields.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from tienda.api.permissions import GRUPO_DEPENDIENTE, rol_en_la_tienda

#: Whether the N5 gate is open.
#:
#: It is **open**: the owner has decided that the `dependiente` prepares,
#: confirms and collects. The decision is recorded here because the gate
#: is a **named, single decision** rather than an `if` repeated in four
#: views - the four views must answer the same way, and a decision copied
#: four times is a decision that will drift.
#:
#: It is a decision under a DECLARED HYPOTHESIS (design §18.3): the
#: validation round with the shop owners has not been run, and the
#: project's `knowledge_basis` says so.
N5_ABIERTA = True


class PuertaN5(BasePermission):
    """The N5 gate, applied to the four proposal routes.

    While it is **closed**, the `dependiente` is refused with the total
    403 of design §7.1: no alias, no customer identifier, no `codigo`, no
    prefix, no count - not in the body, not in a header, not in the error
    message.

    While it is **open**, the `dependiente` passes the gate and the
    **object-level rule** takes over: it reaches the proposal it prepared
    and no other. The gate opens the ROUTE; the ownership filter guards
    the OBJECT. They are two different questions and they are answered in
    two different places.
    """

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        # The role is the MEMBERSHIP's, and the membership names the shop.
        from tienda.api.permissions import current_shop

        shop_id = current_shop(request)
        if shop_id is None:
            return False
        # The owner is never gated: the credit book is the owner's alone.
        if rol_en_la_tienda(user, shop_id) != GRUPO_DEPENDIENTE:
            return True
        # A `dependiente` passes only when the gate is open.
        return N5_ABIERTA
