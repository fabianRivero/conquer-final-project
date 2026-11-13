"""Reading the declared fields of a serializer — the check CAC-10 rests on.

DRF builds a serializer's `fields` when the class is declared. Reading it
does not need an instance, and an instance would need a database to be
meaningful. That matters: the assertion that the client schema declares
none of the nine staff-only fields must be readable **without** a
database, so it can live in the unit layer too.

This module is the single definition of that read. The test of §15.2 and
the code use the same one, so a reader and a test author never have to
reconstruct it.
"""

from __future__ import annotations


def fields_de(schema) -> set:
    """The names a serializer class declares.

    The read is the schema's own `_declared_fields`, which DRF fills when
    the class is declared. It is a class attribute, so no instance and no
    database are involved.
    """
    declarados = getattr(schema, "_declared_fields", None)
    if declarados:
        return set(declarados.keys())
    return set()
