"""The pure domain rules of `fiado-confirmado`.

Every rule in this package is a total function over plain values: no Django,
no DRF, no app module, no database and **no implicit clock** — the caller
always passes `at`.

The boundary is enforced, not merely intended:
`backend/tests/unit/test_domain_is_orm_free.py` AST-parses every file of this
package and fails on a forbidden import. Only the standard library and this
package's own sibling modules may be imported here.

The submodules are:

* `types` — the plain records and the closed vocabularies (design §10).
* `position` — `real_position`, `outstanding`, `cash_at` (CP-02, CP-03).
* `allocation` — `allocate_payments`, the FIFO retirement of debt, and
  `imputations_of`, the repartition it records (PA-02, ADR-27).
* `ageing` — `bucket_of`, `age_in_days` (PA-03).
* `evaluation` — `evaluate_customer`, `antiguedad_max_dias` (PA-06).
* `charges` — `total_de_linea`, `precio_unitario_de`,
  `charge_amount_matches`, `propuesta_amount_matches` (IC-02, IC-06, PC-02).
* `confirmation` — the derived confirmation state and the one-way proposal
  transition (IC-03, IC-04, ADR-18, ADR-19).
* `stock` — `existencias_registradas` (CP-07).
* `cash` — `caja_al_cierre`, `desviacion_cierre` (CP-04).
"""
