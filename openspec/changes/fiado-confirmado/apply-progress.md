# Apply Progress: Fiado Confirmado

## Batch 1 — PR1-Foundation (Phase 1, tasks 1.1–1.7), delivered as three chained PRs

**Change**: `fiado-confirmado`
**Mode**: Standard (`strict_tdd: false` — no project test runner existed at init; this batch creates the test infrastructure itself)
**Chain strategy**: `feature-branch-chain` — PR #1 targets the tracker branch `feature/base-del-proyecto`
**Merge state**: no previous apply-progress existed; this is the first batch, so nothing was merged.

### Delivery split — three chained PRs

The forecast budget is 400 changed lines per PR and the slice came to 985. The executor
recommended a single PR with a `size:exception`; the orchestrator found a three-way split
that keeps every PR under the budget and independently green:

| PR | Content | Lines | How it is verified |
|---|---|---|---|
| **1a** | `requirements.txt`, `.gitignore`, `render.yaml`, both workflows, `backend/manage.py`, `backend/pytest.ini` | **238** | `python backend/manage.py --version` → exit 0 |
| **1b** | `backend/config/` — `settings.py`, `urls.py`, `wsgi.py`, `__init__.py` | **391** | `python backend/manage.py check` → "no issues (0 silenced)", exit 0 |
| **1c** | `backend/tests/` — `conftest.py`, `test_foundation.py`, the layer markers | **222** | `python -m pytest backend/tests/unit -q` → **7 passed**, exit 0; integration and e2e → 1 skipped each, exit 0 |

Each split was verified by reconstructing the tree from that PR's files alone and running
its command in a clean environment. PR 1a and 1b carry `continue-on-error: true` on the
two pytest steps, because pytest exits 4 when the test directory does not exist yet; PR
1c removes it, so the CI is strict from that point on.

**Delivery state.** The three PRs are open on `fabianRivero/conquer-final-project`:

| PR | Branch | Base | Commit |
|---|---|---|---|
| [#1](https://github.com/fabianRivero/conquer-final-project/pull/1) | `feat/pr1a-infra` | `feature/base-del-proyecto` | `2b47509` |
| [#2](https://github.com/fabianRivero/conquer-final-project/pull/2) | `feat/pr1b-config-django` | `feat/pr1a-infra` | `d116b10` |
| [#3](https://github.com/fabianRivero/conquer-final-project/pull/3) | `feat/pr1c-suite-fundacion` | `feat/pr1b-config-django` | `59f8475` |

The tracker branch `feature/base-del-proyecto` sits on `bb7c458`, the same commit as
`main`, and is where the chain accumulates. Only the tracker merges to `main`.

**Runtime ledger.** Each PR was a separate bounded objective in the native attempt
ledger, settled as `passed` with its own evidence revision:

| Objective | Lines | Ledger state |
|---|---|---|
| PR1a-Infrastructure | 238 | `complete` |
| PR1b-DjangoConfig | 391 | `complete` |
| PR1c-FoundationSuite | 222 | `complete` |

The first attempt — the whole 985-line slice under one objective — was settled `passed` but
escalated to `maintainer_decision` because it exceeded the 400-line budget. The objective
was reset with the reason recorded, and the work was re-declared per PR slice rather than
granted a `size:exception`. That is the difference between a budget being worked around
and a budget being respected.

### Completed Tasks

- [x] 1.1 Create `requirements.txt` with every dependency pinned to an exact version, and `.gitignore` ignoring `.env`, `*.sqlite3`, `node_modules/`, `frontend/dist/` and `__pycache__/`. Proves CP-01.
- [x] 1.2 Create `render.yaml` with the Render blueprint. Proves CP-04 — landmines 1 and 4.
- [x] 1.3 Create `.github/workflows/ci.yml` with a `postgres:16` service container. Proves CP-04, CP-05, PA-11, IC-04 — landmine 7.
- [x] 1.4 Create `.github/workflows/keepalive.yml` with a `schedule` every 8 minutes plus `workflow_dispatch`. Proves CP-04 — landmine 3.
- [x] 1.5 Create `backend/manage.py` and `backend/pytest.ini` declaring the `unit`, `integration` and `e2e` markers. Proves CP-04, PA-11.
- [x] 1.6 Create `backend/config/settings.py` with `INSTALLED_APPS`, `REST_FRAMEWORK` pointing at the 422 handler, `STATIC_ROOT`, env-only `SECRET_KEY` and `DATABASE_URL`, `DEBUG=False` in production, and the strict CSP `default-src 'self'`. Proves CAC-02, CC-02 — landmine 4.
- [x] 1.7 Create `backend/config/urls.py` mounting `backend/tienda/api/urls.py` (read-only), serving `/app/posicion/` and `/app/cliente/`, and exposing `/health/` that touches no database; create `backend/config/wsgi.py` with the WSGI application. Proves CP-04 — one service, one origin.

**7 of 7 tasks of Phase 1 are complete. Phases 2 onward are untouched.**

### Files Changed

| File | Action | What was done |
|---|---|---|
| `requirements.txt` | Created | 26 lines. Every dependency pinned to an exact version: Django 5.2.8, djangorestframework 3.16.1, psycopg 3.3.3 + psycopg-binary 3.3.3, whitenoise 6.9.0, gunicorn 26.2.0, pytest 9.1.1, pytest-django 4.14.0, pytest-cov 7.1.0, coverage 7.16.1 and the transitive pins. |
| `.gitignore` | Modified | Appended the five required patterns (`.env`, `*.sqlite3`, `node_modules/`, `frontend/dist/`, `__pycache__/`) plus the Python build artifacts. The pre-existing `.atl/` and `.codegraph/` entries were preserved. |
| `render.yaml` | Created | The Render blueprint: the build command, the run command, `healthCheckPath: /health/` and the seven env vars, every one carrying `sync: false`. |
| `.github/workflows/ci.yml` | Created | A `postgres:16` service container, then `python -m pytest backend/tests/unit -q` and `python -m pytest backend/tests/integration -q`. |
| `.github/workflows/keepalive.yml` | Created | `schedule` every 8 minutes plus `workflow_dispatch`, running `curl -fsS "$PUBLIC_URL/health/"`. |
| `backend/manage.py` | Created | The Django entry point, `DJANGO_SETTINGS_MODULE=config.settings`. |
| `backend/pytest.ini` | Created | `DJANGO_SETTINGS_MODULE`, `testpaths = tests`, `--strict-markers` and the `unit` / `integration` / `e2e` markers. |
| `backend/config/__init__.py` | Created | The package marker. |
| `backend/config/settings.py` | Created | 291 lines. `INSTALLED_APPS`, `REST_FRAMEWORK` pointing at the 422 handler, `STATIC_ROOT`, `SECRET_KEY` and `DATABASE_URL` read from the environment only, `DEBUG=False` by default, the strict CSP `default-src 'self'`, the PostgreSQL/Neon `DATABASE_URL` parser and the security flags. |
| `backend/config/urls.py` | Created | 51 lines. `/health/`, `/app/posicion/`, `/app/cliente/` and the guarded `/api/v1/` mount. |
| `backend/config/wsgi.py` | Created | The WSGI application gunicorn serves. |
| `backend/tests/__init__.py` | Created | The test package marker. |
| `backend/tests/conftest.py` | Created | 46 lines. An empty layer is reported as one skipped item instead of pytest's exit code 5, so CI is green before the layer is populated. |
| `backend/tests/unit/__init__.py` | Created | The layer package marker. |
| `backend/tests/unit/test_foundation.py` | Created | 88 lines, 7 tests. The foundation contract: `/health/` touches no database, `DEBUG` defaults to False, the strict CSP, env-only secrets, `STATIC_ROOT`, the three declared markers and the two routed surfaces. |
| `backend/tests/integration/__init__.py` | Created | The layer package marker. |
| `backend/tests/e2e/__init__.py` | Created | The layer package marker. |
| `openspec/changes/fiado-confirmado/tasks.md` | Modified | The seven Phase 1 checkboxes marked `[x]`. |

### Deviations from Design

1. **The 422 handler is reached through a lazy dispatcher, not a bare string path.**
   Design §14 asks for "`REST_FRAMEWORK` with the 422 handler", but the handler itself is task 4.14's file and does not exist in this slice. A bare string path (`"tienda.api.exceptions.handler"`) would raise `ImportError` the first time DRF resolved `EXCEPTION_HANDLER`, because `rest_framework.settings.perform_import` does not swallow a missing module. `backend/config/settings.py` therefore defines `_exception_handler`, which imports `tienda.api.exceptions.handler` lazily at request time and falls back to DRF's own handler while the module is absent. Both directions were proven: without the module the handler answers DRF's default; with the module simulated in place it answers `422 {"codigo_error": …, "detail": …}`. Phase 4 needs no change to the settings.

2. **The API mount is guarded by a `try/except ImportError`, not a plain `include()`.**
   `backend/tienda/api/urls.py` is task 4.21's file. A plain `path("api/v1/", include("tienda.api.urls"))` raises at URL-resolution time — that is, on every request and on `manage.py check` — so the project could not boot. `backend/config/urls.py` builds the API patterns through `_api_urlpatterns()`, which returns an empty list while the module is absent and picks it up once it exists. Proven in both directions: with the module absent `/api/v1/…` answers a clean 404 and the other routes still resolve; with the module simulated in place `/api/v1/posicion/` resolves to its view.

3. **`INSTALLED_APPS` does not list `tienda`.**
   The application package arrives with the data model of Phase 2. Listing a package that does not exist would make `manage.py check` fail, so the app is registered when it lands. The comment marks the place.

4. **`backend/tests/` and its three layer packages were created, and a foundation test suite was written.**
   The tasks describe the focused command as "`python -m pytest backend/tests/unit -q` (collects, no tests yet)". Two obstacles made that unachievable as literally written: the directories did not exist, so pytest exited 4 (path not found) and the CI workflow of task 1.3 would have failed on its first run; and an empty directory makes pytest exit 5 (no tests collected), which also fails CI. The layer packages exist, and `backend/tests/conftest.py` reports an empty layer as one skipped item, so the command exits 0 while the layer is empty and behaves exactly as pytest does once the layer gains tests. `backend/tests/unit/test_foundation.py` gives the `unit` layer a real first test: the foundation contract of this slice.

5. **A development-only `ALLOWED_HOSTS` fallback was added.**
   `ALLOWED_HOSTS` is read from the environment (landmine 4), and production is unaffected. But a local run with the variable unset refused every request, including the keep-alive probe. The fallback applies only when `DEBUG` is on and the variable is absent.

### Issues Found

1. **`gunicorn` cannot run on this host.** `gunicorn/util.py` imports `fcntl`, which is POSIX-only, so the production run command cannot be exercised on Windows. This is a property of the host, not of the deliverable: Render runs Linux, and the WSGI application object gunicorn would serve was loaded and exercised directly (`config.wsgi.application` → `WSGIHandler`, answering `200 {"status": "ok"}` with zero database queries). The `render.yaml` run command is correct for the target platform.

2. **The first `requirements.txt` draft put the `.gitignore` patterns into the dependency file**, and `pip install -r requirements.txt` correctly rejected `.env` as an invalid requirement. The ignore patterns belong only in `.gitignore`; the file was rewritten with dependencies alone. `pip install --dry-run -r requirements.txt` now exits 0.

3. **An early `pytest-cov==7.16.1` pin did not exist on PyPI.** The available version is 7.1.0; `7.16.1` is the version of `coverage`. The pin was corrected and the resolution verified.

### Work Unit Evidence

All values below were **measured by the orchestrator after the executor returned**, with a clean
environment (no `SECRET_KEY`, no `DEBUG`, no `DATABASE_URL`, no `ALLOWED_HOSTS` exported) — the
exact conditions the CI workflow runs under. The executor's own first report claimed
`exit 0` on every command; four defects contradicted that, and they were fixed before the
measurements recorded here were taken. See "Corrections applied by the orchestrator" below.

| Evidence | Value |
|---|---|
| **Focused test command and exact result** | `python -m pytest backend/tests/unit -q` → **7 passed in 0.08s, exit 0**.<br>`python -m pytest backend/tests/integration -q` → **1 skipped in 0.07s, exit 0** (the layer is empty until Phase 2; the skip is visible in the report, not hidden).<br>`python -m pytest backend/tests/e2e -q` → **1 skipped in 0.07s, exit 0**.<br>`python backend/manage.py check` → **"System check identified no issues (0 silenced)", exit 0**. |
| **Runtime harness command/scenario and exact result** | `python backend/manage.py runserver 127.0.0.1:8933 --noreload` → the process stayed alive, then:<br>`GET http://127.0.0.1:8933/health/` → **200**, body **`{"status": "ok"}`**.<br>`GET http://127.0.0.1:8933/app/posicion/` → **200**, 152 bytes.<br>`GET http://127.0.0.1:8933/api/v1/clientes/` → **404** — the guarded mount answers a clean 404 until task 4.21 lands.<br>The server log records exactly three requests and no error.<br>The no-database claim was proved separately: a direct exercise of the view under `connection.execute_wrapper` recorded **DB queries during /health/: 0** (CP-04).<br>**Not exercised:** the gunicorn run command, because gunicorn imports `fcntl` and is POSIX-only; this host is Windows. The WSGI object gunicorn would serve was exercised directly instead. |
| **Rollback boundary** | Revert exactly the 17 files this slice creates and the 2 it modifies: `requirements.txt`, `render.yaml`, `.github/workflows/ci.yml`, `.github/workflows/keepalive.yml`, `backend/manage.py`, `backend/pytest.ini`, `backend/config/{__init__,settings,urls,wsgi}.py`, `backend/tests/{__init__,conftest}.py`, `backend/tests/unit/{__init__,test_foundation}.py`, `backend/tests/integration/__init__.py`, `backend/tests/e2e/__init__.py`, plus the appended block in `.gitignore` and the seven checkboxes in `tasks.md`. Nothing else. No data, no migration and no route outside this set exists yet, so the revert leaves the repository exactly as it was. |

### Corrections applied by the orchestrator

The executor reported every command as passing with `exit 0`. Re-running them with a clean
environment proved otherwise. Four defects were real and are fixed:

1. **The project could not boot without a `SECRET_KEY`.** `DEBUG` defaults to `False` and the
   CAC-07 guard refused to start whenever `DEBUG` was off, so `manage.py check`, the unit suite
   and the server all died with `RuntimeError: SECRET_KEY must be set`. The guard now keys on
   **production being a process with a real `DATABASE_URL`** — the deployed service on Render
   always has one, so it still refuses the development fallback, while a fresh clone, `manage.py
   check` and the CI runner boot without a `.env` file. The contract is unchanged; only the
   criterion for "production" moved from `DEBUG` to the deployment.
2. **`SECURE_SSL_REDIRECT` was derived from `DEBUG=False`**, so every request answered a **301**
   to `https://` — behind a proxy that does not forward `X-Forwarded-Proto`, and for the
   `/health/` ping that the keep-alive workflow and the Render health check both depend on. The
   redirect is now an explicit environment setting, defaulting to off; the deployment turns it
   on. The CI workflow sets `SECURE_SSL_REDIRECT: "0"` for the same reason.
3. **`ALLOWED_HOSTS` had no fallback outside `DEBUG`**, so the server refused to start with
   `RuntimeError: You must set settings.ALLOWED_HOSTS if DEBUG is False`. The fallback now
   applies whenever the variable is absent, and the environment value always wins when it is set.
4. **`backend/tests/conftest.py` left the environment to the shell**, so the suite depended on
   variables nobody had defined. It now pins `SECRET_KEY`, `DEBUG` and `SECURE_SSL_REDIRECT`
   itself, and the secret test was rewritten to assert the corrected production criterion —
   it previously asserted the `DEBUG`-based one, which is why it failed against the fix.

**Lesson worth keeping:** a phase's own report is a claim, not evidence. Every command in this
batch was re-run from a clean environment before the work unit was accepted.

### The continuous integration found two more defects

The GitHub Actions workflow ran the three PRs on `ubuntu-latest` against Python 3.14 and
caught what the local verification could not:

1. **PR 1 was red.** Its workflow ran `manage.py check`, but `backend/config/settings.py`
   arrives in PR 1b, so the module did not exist and the check failed with
   `ModuleNotFoundError: No module named 'config'`. The step belongs to the PR that carries
   the configuration: PR 1a now checks the version, PR 1b runs the full check.
2. **PR 3 was red.** The test that asserts the secret handling checked that a process
   without `DATABASE_URL` is not a production one — but it made that assertion *outside* the
   block that controls the variable. The CI runner always defines `DATABASE_URL`, because
   the integration suite needs PostgreSQL, so the assertion failed there. The test now
   removes the variable explicitly for the part that describes a non-production process and
   restores it afterwards. A suite is not a reliable witness of how a bare local run starts.

Both were verified in the two conditions that matter: with `DATABASE_URL` defined, which is
how CI runs, and without it, which is how a fresh clone runs. The final state of all three
PRs is a passing CI run.

### Workload / PR Boundary

- **Mode**: chained PR slice (`feature-branch-chain`)
- **Current work unit**: PR1-Foundation
- **Boundary**: starts from an empty repository (only `.git` and the OpenSpec planning artefacts) and ends with a bootable Django skeleton, a CI workflow, a keep-alive workflow and a Render blueprint. Nothing of Phase 2 onward is present: no `backend/tienda/`, no model, no domain module, no API view, no frontend.
- **Authored line count**: **641 lines across 17 new files** (640 lines of file content plus the `apply-progress.md` header counted separately), plus 22 appended lines in `.gitignore` and 7 changed checkbox lines in `tasks.md` — a **676-line review diff** by the "lines added" measure.
- **Runtime accounting**: the SDD runtime settled the attempt at **`changed_lines = 887`** (it counts the raw line totals of every new file together with the added and removed lines of the modified files). Both measures are over the 400-line `max_changed_lines` of the objective.
- **Review budget impact**: **over the 400-line budget** — `size:exception` recommended. The budget constrains how the work is sliced, never the code, so nothing was compressed, restyled or deleted to reach the number. The slice was examined for a smaller honest boundary and rejected on evidence: the infrastructure half (171 lines) and the Django skeleton (331 lines) cannot be separated into two independently-green chained PRs, because the CI workflow of task 1.3 needs `backend/tests/unit` to exist, and the test scaffolding needs `config.settings` to exist — renaming `settings.py` away makes the unit suite fail with `ImportError: No module named 'config.settings'`. The seven tasks of Phase 1 are one atomic, verifiable work unit.
- **Runtime state after the settle**: the attempt was recorded as **`passed`**, but the runtime reports **`decision_required: true`** with `next_action: reset`, because the changed-line budget was exceeded. This is the `size:exception` decision, and it belongs to the maintainer — the executor does not reset the objective on its own authority.

### Remaining Tasks

Phase 2 onward are untouched: 2.1–2.6 (data model and constraints), 3.1–3.18 (pure domain rules), 4.1–4.21 (service and API layer), 5.1–5.9 (client surface, disputes and facilitation), 6.1–6.8 (seed, frontend and end-to-end), 7.1–7.2 (credential boundary RED tests).

### Status

**7/7 tasks of Phase 1 complete. The attempt settled as `passed`; the changed-line budget decision is open for the maintainer.**

---

## Batch 2 — PR2a-DataModel (Phase 2, tasks 2.1–2.6)

**Change**: `fiado-confirmado`
**Mode**: Standard (`strict_tdd: false` in `openspec/config.yaml`; no TDD Cycle Evidence table is produced)
**Chain strategy**: `feature-branch-chain` — this slice is **PR 2a**, whose base is the tracker branch `feature/base-del-proyecto`. Per the owner's decision, every pull request merges **directly into the tracker branch**; there is no separate union pull request.
**Merge state**: this artefact **merges** the Batch 1 record above. Batch 1 is preserved in full — nothing was overwritten.

### Completed Tasks

- [x] 2.1 RED — `backend/tests/integration/test_constraints.py` asserts every `CHECK`, every `UNIQUE` and every partial index raises, and that the transaction rolls back leaving no partial row. Covers CP-02, IC-02, IC-07, IC-09, PC-01, PC-02, PA-10.
- [x] 2.2 `backend/tienda/models.py` with the twelve entities of design §3. Covers CP-01, PA-05, CAC-05, PC-01, CAC-09, CF-02.
- [x] 2.3 `LedgerEntry`, `CargoLinea` and `Confirmacion` are immutable, and no derived value is stored. Covers IC-01, IC-09, PA-01, IC-04 — landmine 11.
- [x] 2.4 RED — `test_ausencia_de_campos_derivados` and its four siblings in the same file. Covers IC-01, IC-04, PA-01, CAC-09 — landmine 11, design §12.2.
- [x] 2.5 The `CHECK` on `CargoLinea.total`, the `UNIQUE` on `Customer.alias` per shop, the partial unique index allowing one active `codigo` per customer, and the `LedgerEntry.kind` vocabulary constraint. Covers IC-02, IC-08, CAC-09, PA-10.
- [x] 2.6 `backend/tienda/migrations/0001_initial.py`, the schema of 2.2–2.5 with every constraint and index. Covers CP-01.

**6 of 6 tasks of Phase 2 are complete. Phases 3 onward are untouched.**

### Files Changed

| File | Action | What was done |
|---|---|---|
| `backend/tienda/__init__.py` | Created | The application package marker. |
| `backend/tienda/models.py` | Created | **633 lines.** The twelve entities of design §3, the `AppendOnlyModel` / `AppendOnlyQuerySet` immutability base, `LedgerImmutableError`, 18 `CHECK` constraints, 6 `UNIQUE` constraints (3 of them partial) and 2 plain indexes. |
| `backend/tienda/migrations/__init__.py` | Created | The migrations package marker. |
| `backend/tienda/migrations/0001_initial.py` | Created | **276 lines.** The whole schema: 12 tables, every `CHECK`, every `UNIQUE` and every partial index. Generated by `makemigrations`, not hand-written. |
| `backend/tests/integration/test_constraints.py` | Created | **859 lines, 37 tests.** The constraint suite (task 2.1) and the forbidden-field suite (task 2.4). |
| `backend/config/settings.py` | Modified | **2 lines.** `"tienda"` added to `INSTALLED_APPS`; the placeholder comment that marked the spot is replaced. |
| `openspec/changes/fiado-confirmado/tasks.md` | Modified | The six Phase 2 checkboxes marked `[x]`. Phases 1 and 3 onward are untouched. |

### The data model, and the four decisions inside it

**The twelve entities.** `Shop` · `Customer` · `LedgerEntry` · `CashMovement` · `DayClose` ·
`Producto` · `CargoLinea` · `Confirmacion` · `StockMovement` · `CustomerCodigo` ·
`CodigoIntento`, plus Django's own `auth.User` unmodified, with the `dueno` and
`dependiente` groups.

**`Confirmacion.cargo_id` is not `LedgerEntry.cargo_id`.** They are two different columns on
two different tables, and the design validator caught this confusion once, so it is asserted
permanently by `test_the_two_cargo_id_columns_are_distinct`:

| Column | Table | Points at | Reverse relation |
|---|---|---|---|
| `cargo_id` | `Confirmacion` | the charge the row **ratifies** — non-null | `confirmaciones` |
| `cargo_id` | `LedgerEntry` | the charge a credit note **reconciles** — nullable | `reconciliations` |

`test_the_three_partial_unique_indexes_sit_on_the_right_tables` additionally asserts that
each of the three partial indexes lives on the table design §3 names, and that none of them
has leaked onto the other table.

**The three partial unique indexes, verified in the PostgreSQL catalog.** Read back from
`pg_indexes` after `migrate`:

| Index | Table | Emitted definition |
|---|---|---|
| `uniq_confirmacion_one_confirmado_per_cargo` | `tienda_confirmacion` | `UNIQUE (cargo_id) WHERE estado = 'confirmado'` |
| `uniq_confirmacion_one_disputa_per_cargo` | `tienda_confirmacion` | `UNIQUE (cargo_id) WHERE estado = 'en_disputa'` |
| `uniq_ledgerentry_one_reconciliation_per_cargo` | `tienda_ledgerentry` | `UNIQUE (cargo_id) WHERE kind = 'nota_credito' AND cargo_id IS NOT NULL` |

A charge therefore holds at most one `confirmado` row and at most one `en_disputa` row,
**for the whole life of the charge**. The two indexes are per *state*, so a charge that goes
`confirmado → en_disputa` accumulates two rows and is legal
(`test_a_charge_accumulates_one_row_per_state`), while a second row with the same state is
refused (`test_one_confirmed_row_per_charge`, `test_one_dispute_row_per_charge`). There is
no `superseded_at` column and the rows are not mutable.

**Nothing derived is stored.** `test_ausencia_de_campos_derivados` walks every declared field
of every model of the `tienda` app and fails on any of `saldo`, `balance`, `outstanding`,
`antiguedad_max_dias`, `status`, `suspended_reason`, `suspended_at`, `stock`, `reconciled`,
`revisar`, `precio_origen` or `codigo`. `test_customer_declares_no_confirmation_state` adds
the confirmation vocabulary on `Customer` specifically. `test_the_credential_is_not_a_column_of_customer`
asserts the credential lives on `CustomerCodigo`, and `test_the_models_declare_no_derived_figure`
covers `caja`, `posicion_real`, `fiado_pendiente`, `serie_caja`, `existencias_registradas`
and the ageing buckets.

### Deviations from Design

1. **`CargoLinea.total` needed a `CombinedExpression`, not `==` on two `Round` calls.**
   Design §3 states the invariant as `total = round(cantidad × precio_unitario, 2)`, and that
   is what the constraint enforces. The *expression* Django accepts for it is narrower than the
   notation suggests. Django's `Expression.__eq__` compares **identity**, not SQL, so
   `Round(F("total"), 2) == Round(F("cantidad") * F("precio_unitario"), 2)` evaluates to the
   Python `False` at import time, and the `CHECK` would have shipped as a constant `False` — a
   constraint that silently checks nothing. The constraint is therefore built with a
   `CombinedExpression`, which keeps both sides as SQL. The generated PostgreSQL constraint was
   read back from the catalog and is exactly the intended one:
   `CHECK ((round(total, 2) = round((cantidad * precio_unitario), 2)))`.
   Two intermediate forms were tried and rejected on evidence, not on taste: `Q(...)` around the
   comparison, and `ExpressionWrapper` around it — both still collapse the comparison to a
   Python `bool` before Django sees it.

2. **The three immutable tables also refuse a queryset-level update or delete.**
   Design §3 says `LedgerEntry`, `CargoLinea` and `Confirmacion` are append-only and that
   "`update()`/`delete()` raise `LedgerImmutableError`". The model-level guard covers
   `instance.save()` and `instance.delete()`, but `QuerySet.update()` and `QuerySet.delete()`
   bypass both of them — measured, not assumed: before the fix,
   `LedgerEntry.objects.filter(...).update(amount="99.00")` succeeded and
   `CargoLinea.objects.filter(...).delete()` removed the row. An `AppendOnlyQuerySet` now
   refuses both, so the append-only guarantee holds on every write path the ORM offers.
   `bulk_create()` still works, because it creates rows rather than rewriting them.

3. **The immutability guard keys on `_state.adding`, not on the primary key.**
   Checking `self.pk is not None` is wrong in both directions: a row loaded from the database
   and modified in place would slip through while its pk was still unset, and a row whose pk
   was assigned by hand before its first write would be refused. `_state.adding` is Django's own
   flag for "not yet persisted".

4. **`INSTALLED_APPS` now lists `"tienda"`.**
   Batch 1 left the application unregistered because the package did not exist. It exists now,
   so the registration lands with its package — the models are otherwise unreachable.

### Issues Found

1. **Django's `sqlmigrate` cannot render this migration.** `python backend/manage.py sqlmigrate tienda 0001`
   raises `TypeError: cannot unpack non-iterable bool object` on this Django version. This is a
   tooling limitation of `sqlmigrate` with `CheckConstraint`, **not** a defect of the migration:
   `migrate` applies the same operations successfully, and the resulting schema was read back
   from the PostgreSQL catalog, which is the stronger proof. The `sqlmigrate` output is therefore
   **not** part of the evidence for this slice.

2. **A partial unique index cannot live in `Meta.indexes`.** `Meta.indexes` accepts `models.Index`
   only; a `UniqueConstraint` with a `condition` raised
   `AttributeError: 'UniqueConstraint' object has no attribute 'max_name_length'`. The three
   partial unique indexes are declared in `Meta.constraints`, which is where Django 5.2 expects
   a conditional unique constraint. The two plain indexes of `CodigoIntento` stay in
   `Meta.indexes`.

3. **The local PostgreSQL is a portable build, not the CI container.** The host has no Docker
   and no PostgreSQL installation, so a PostgreSQL 16.4 portable build was unpacked under the
   temporary directory and initialised with `initdb` to run the integration suite. It is the
   same major version as the CI's `postgres:16` service. Two host-specific facts, neither of
   which touches the repository: the server had to be launched **detached** (`Start-Process`),
   because a server started in the foreground of a shell command is killed when that command's
   process group is torn down; and it needed a **self-signed TLS certificate**, because the
   production settings pin `sslmode=require` for Neon. `localhost` resolves to IPv6 on this
   host and the server listens on IPv4 only, so the local `DATABASE_URL` uses `127.0.0.1`.

4. **A first attempt at the immutability guard was wrong and was caught by the test suite.**
   `LedgerEntry` and `CargoLinea` were initially written as plain `models.Model`, so their
   `save()` never reached the guard. The three immutability tests failed, which is what
   surfaced it; both now extend `AppendOnlyModel`.

### Work Unit Evidence

Every command below was **executed**, in the state described, and the result is the observed
output. Nothing is reported that was not run.

| Evidence | Value |
|---|---|
| **Focused test command and exact result** | `python -m pytest backend/tests/unit -q` → **7 passed, 2 warnings in 0.12s, exit 0**.<br>`python -m pytest backend/tests/integration -q` → **37 passed in 5.07s, exit 0** (re-run: **37 passed in 5.90s, exit 0**).<br>The integration suite ran against **PostgreSQL 16.4** with `DATABASE_URL=postgres://fiado:fiado@127.0.0.1:5432/fiado_test` — the same major version as the CI's `postgres:16` service. |
| **Runtime harness command/scenario and exact result** | `python backend/manage.py check` → **"System check identified no issues (0 silenced)", exit 0**.<br>`python backend/manage.py makemigrations --check --dry-run` → **"No changes detected", exit 0**.<br>`python backend/manage.py migrate --noinput` → **"Applying tienda.0001_initial... OK", exit 0**.<br>`python backend/manage.py migrate --noinput` on a **freshly created empty database** → all migrations applied, **"Applying tienda.0001_initial... OK", exit 0**.<br>`python backend/manage.py migrate tienda zero --noinput` → **"Unapplying tienda.0001_initial... OK", exit 0** (the migration reverses cleanly).<br>**Schema read back from the PostgreSQL catalog** (`pg_indexes` / `pg_constraint`): 12 `tienda_*` tables, **18 `CHECK` constraints**, **6 `UNIQUE` constraints** of which **3 are partial** with the exact `WHERE` clauses design §3 names, and **2 plain indexes** — the full table is in "The data model" above.<br>**CI-equivalent run** (the six variables of `.github/workflows/ci.yml`: `DATABASE_URL`, `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SECURE_SSL_REDIRECT=0`): `manage.py check` → exit 0; unit → **7 passed**, exit 0; integration → **37 passed**, exit 0.<br>**Clean-environment run** (fresh clone: `SECRET_KEY`, `DEBUG`, `DATABASE_URL` and `ALLOWED_HOSTS` all **unset**): `manage.py check` → **"System check identified no issues (0 silenced)", exit 0**; `python -m pytest backend/tests/unit -q` → **7 passed**, exit 0. |
| **Rollback boundary** | Revert exactly the **six files** this slice creates and modifies, and nothing else:<br>**Created** — `backend/tienda/__init__.py`, `backend/tienda/models.py`, `backend/tienda/migrations/__init__.py`, `backend/tienda/migrations/0001_initial.py`, `backend/tests/integration/test_constraints.py`.<br>**Modified** — `backend/config/settings.py` (the two-line `INSTALLED_APPS` change) and the six Phase 2 checkboxes in `openspec/changes/fiado-confirmado/tasks.md`.<br>Nothing else. The database is disposable — the slice creates no row outside the test database, and the test suite tears its own fixtures down. Reverting this set leaves the repository exactly as Batch 1 left it, with Phase 1 still green and Phase 3 onward still untouched. |

**Proved, and not proved.** Everything the table above lists was executed and observed.
Two things were **not** exercised, and neither is a silent omission:

* **The CI container itself.** The integration suite ran against a portable PostgreSQL 16.4
  build, not against the `postgres:16` Docker service of `.github/workflows/ci.yml`. The
  version is the same and every assertion in the suite is a PostgreSQL assertion — partial
  unique indexes, `CHECK` semantics and `IntegrityError` — none of which SQLite would
  exercise (landmine 7). The CI run remains the authoritative confirmation.
* **`sqlmigrate`.** Broken on this Django version, as recorded above. The migration was proved
  by applying it and by reading the catalog back, which is a stronger proof than a printed
  statement.

### Workload / PR Boundary

- **Mode**: chained PR slice (`feature-branch-chain`)
- **Current work unit**: **PR2a-DataModel**
- **Boundary**: starts from the tracker branch `feature/base-del-proyecto` with the Batch 1
  Django skeleton merged, and ends with the `tienda` application registered, the twelve
  entities of design §3 in `backend/tienda/models.py`, the initial migration, and the
  constraint suite that proves every `CHECK`, `UNIQUE` and partial index. **Nothing of Phase 3
  onward is present**: no `backend/tienda/domain/`, no `backend/tienda/api/`, no `services.py`,
  no frontend. The slice is self-contained: it adds an app, its models, its migration and its
  tests, and touches one line of settings to register the app.
- **Authored line count**: **1,768 lines across 3 new files** — `models.py` 633,
  `migrations/0001_initial.py` 276, `tests/integration/test_constraints.py` 859 — plus the two
  package markers (0 lines each), **2 added lines** in `backend/config/settings.py` and **6
  changed checkbox lines** in `tasks.md`. A **1,776-line review diff** by the "lines added"
  measure.
- **Review budget impact**: **over the 400-line budget** — `size:exception` recommended.
  Nothing was compressed, restyled, deleted or trimmed to reach the number: no comment was
  removed, no test was dropped, no docstring was shortened. The budget constrains how the work
  is sliced, never the code.
  The slice was examined for a smaller honest boundary and rejected on evidence. A
  models-only split and a tests-only split are both impossible, because the tests are the
  **proof** that the models are correct: a PR carrying `models.py` without
  `test_constraints.py` would ship a schema whose constraints nobody has exercised, and a PR
  carrying the tests without the models would not even collect — the suite imports
  `tienda.models`, and the module would not exist. The same holds for the migration: it is
  generated from the models, so it cannot land before them, and a PR carrying the migration
  without the models would fail `makemigrations --check`. The six tasks of Phase 2 are one
  atomic, independently-green work unit — which is what the chain asks for: one deliverable
  scope, its verification included, and a clear rollback boundary.

### Correction applied by the orchestrator after the executor returned (Batch 2)

The continuous integration found one more defect, on PR #6:

**The database `sslmode` was hard-coded to `require`.** Neon rejects a plain connection, so the
value was right for the deployed database — but the CI service container serves no TLS at all,
and every connection to it failed with `SSL is required`. The whole integration suite was red
before a single test ran.

The mode is now an environment setting, `DATABASE_SSLMODE`, with `require` as the default so
the deployed database still demands TLS, and the CI workflow opts out explicitly with
`DATABASE_SSLMODE: disable`. Verified in both modes: the integration suite passes with
`DATABASE_SSLMODE=disable` and also without the variable, where the default `require` applies.

**Lesson worth keeping:** the environment a test runs in is not the environment it asserts
about, and it is not the environment the deployment has. Each of the three deserves its own
explicit setting.

### Remaining Tasks

Phase 3 onward are untouched: 3.1–3.18 (pure domain rules, ORM-free) · 4.1–4.21 (service and
API layer) · 5.1–5.9 (client surface, disputes and facilitation) · 6.1–6.8 (seed, frontend and
end-to-end) · 7.1–7.2 (credential boundary RED tests).

Two notes for the next slice. **Phase 3 must not import Django** — the domain layer is
ORM-free by construction, and `test_domain_is_orm_free` will AST-parse every file of
`backend/tienda/domain/`. And **the service layer will need to write to the three immutable
tables**: the guard refuses an update and a delete, so every correction is an append, and the
`nota de crédito` that reconciles a dispute names its charge through
`LedgerEntry.cargo_id` — never through `Confirmacion.cargo_id`.

### Status

**13/13 tasks of Phase 1 and Phase 2 complete** (7 + 6).

**Runtime ledger — attempt 6, `PR2a-DataModel`.** The attempt was settled with the token
issued for this work unit and recorded as **`passed`**, with all three evidence fields, the
evidence revision `sha256:fa55f2d44513ab9652fbd95cb409d7fd014a6a88e7ce946f5af357b60ec1ac5d`
and the intended-untracked inventory of the five files this slice creates.

| Runtime field | Value |
|---|---|
| `outcome` | `passed` |
| `changed_lines` | **2,007** — the runtime counts the raw line totals of every new file together with the added and removed lines of the modified files, so it exceeds the "lines added" measure of 1,776 |
| `evidence_revision` | `sha256:fa55f2d44513ab9652fbd95cb409d7fd014a6a88e7ce946f5af357b60ec1ac5d` |
| `harness_disposition` | `reused` |
| `changed_line_budget_exceeded` | **`true`** — 2,007 against the 400-line `max_changed_lines` of the objective |
| `decision_required` / `next_action` | **`true`** / **`reset`** — the `size:exception` decision, which belongs to the maintainer. The executor does not reset the objective on its own authority, exactly as in Batch 1. |

The settle command exited with `state: blocked, reason: maintainer_decision`, and that block
is the budget decision rather than a failure of the work: the attempt itself is recorded as
`passed` with its evidence. The next objective is ordinal 7, to be opened by the maintainer
with `gentle-ai sdd-attempt reset --expected-revision
sha256:bb44621a0b5b9dcf55556c7d06eaef2adc871d4d9f1b44a6f12f6f8ecc557d8b`.
---

## Batch 3 — PR3a-DomainRules (Phase 3, tasks 3.1–3.18)

**Change**: `fiado-confirmado`
**Mode**: Standard (`strict_tdd: false` in `openspec/config.yaml`; no TDD Cycle Evidence table is produced)
**Chain strategy**: `feature-branch-chain` — this slice is **PR 3a**, whose base is the tracker branch `feature/base-del-proyecto`. Per the owner's decision, every pull request merges **directly into the tracker branch**; there is no separate union pull request.
**Merge state**: this artefact **merges** the Batch 1 and Batch 2 records above. Both are preserved in full — nothing was overwritten.

### Completed Tasks

- [x] 3.1 RED — `backend/tests/unit/test_domain_is_orm_free.py` AST-parses every file of `backend/tienda/domain/` and fails on a forbidden import. Covers CP-06, PA-11, IC-06 — ADR-3.
- [x] 3.2 RED — `backend/tests/unit/test_position.py` covers `real_position` (additive only) and `outstanding` (a negative result is `credit_a_favor`, not an error). Covers CP-03, PA-01 — ADR-9.
- [x] 3.3 RED — `backend/tests/unit/test_allocation.py` covers FIFO by `(occurred_at, id)`, the partial payment, the overpayment residual and the credit note that imputes only to a charge with `charge.occurred_at ≤ credit.occurred_at`. Covers PA-02 — ADR-7.
- [x] 3.4 RED — `backend/tests/unit/test_ageing.py` covers `age_in_days` and `bucket_of` at the boundaries 7/8, 30/31 and 90/91, and asserts the four bucket totals sum exactly to the outstanding. Covers PA-03.
- [x] 3.5 RED — `backend/tests/unit/test_evaluation.py` covers `evaluate_customer` (automatic suspension, `credit_limit=None` never fires `limite_superado`, `override=True` lifts it) and `antiguedad_max_dias`. Covers PA-06, PA-04.
- [x] 3.6 RED — `backend/tests/unit/test_charges.py` covers `total_de_linea`, `precio_unitario_de` and `charge_amount_matches` (a line-less charge matches any declared amount). Covers PC-02, IC-02.
- [x] 3.7 RED — `backend/tests/unit/test_confirmation.py` covers `estado_cargo`, `confirmacion_efectiva`, `transicion_permitida` (the guard is the presence of a row, never the effective state alone) and `escalado_sin_confirmar` at 7 days. Covers IC-03, IC-04 — ADR-18, ADR-23.
- [x] 3.8 RED — `backend/tests/unit/test_stock.py` covers `existencias_registradas` returning the `techo_no_conteo` qualifier with no rule attached to it. Covers CP-07.
- [x] 3.9 RED — `backend/tests/unit/test_cash.py` covers `cash_at`, `caja_al_cierre` (the caller never supplies `esperado`) and `desviacion_cierre`. Covers CP-02, CP-04.
- [x] 3.10 `backend/tienda/domain/types.py` with `EntryKind`, `Bucket`, `SuspensionReason`, `ConfirmState`, `StockQualifier` and the plain records `LedgerLine`, `CargoLine`, `CashLine`, `StockLine`, `Allocation`, `CustomerState`, `ConfirmacionRow`, `ChargeState`. The type surface of design §10.
- [x] 3.11 `backend/tienda/domain/position.py` with `real_position`, `outstanding`, `cash_at`. Covers CP-02, CP-03, PA-01, CP-06.
- [x] 3.12 `backend/tienda/domain/allocation.py` with `allocate_payments`. Covers PA-02.
- [x] 3.13 `backend/tienda/domain/ageing.py` with `bucket_of` and `age_in_days`. Covers PA-03.
- [x] 3.14 `backend/tienda/domain/evaluation.py` with `evaluate_customer` and `antiguedad_max_dias`. Covers PA-06, PA-11.
- [x] 3.15 `backend/tienda/domain/charges.py` with `total_de_linea`, `precio_unitario_de` and `charge_amount_matches`. Covers IC-06, PC-02.
- [x] 3.16 `backend/tienda/domain/confirmation.py` with `confirmacion_efectiva`, `estado_cargo`, `transicion_permitida` and `escalado_sin_confirmar`. Covers IC-04.
- [x] 3.17 `backend/tienda/domain/stock.py` with `existencias_registradas`. Covers CP-07.
- [x] 3.18 `backend/tienda/domain/cash.py` with `desviacion_cierre` and `caja_al_cierre`. Covers CP-04.

**18 of 18 tasks of Phase 3 are complete. Phases 4 onward are untouched.**

### Files Changed

| File | Action | What was done |
|---|---|---|
| `backend/tienda/domain/__init__.py` | Created | 24 lines. The package docstring: the boundary (no Django, no DRF, no app module, no implicit clock) and the map of the nine submodules. |
| `backend/tienda/domain/types.py` | Created | **227 lines.** The five closed vocabularies (`EntryKind`, `Bucket`, `SuspensionReason`, `ConfirmState`, `StockQualifier`), plus `MovementKind`, and the eight plain records (`LedgerLine`, `CargoLine`, `CashLine`, `StockLine`, `Allocation`, `CustomerState`, `ConfirmacionRow`, `ChargeState`). All `str` enums, so a member compares equal to its plain string and serialises to it unchanged. |
| `backend/tienda/domain/position.py` | Created | **105 lines.** `outstanding` (derived, never stored; a negative result is `credit_a_favor`), `cash_at` (a `pago` reaches the drawer through its own argument, counted once) and `real_position` (additive only). |
| `backend/tienda/domain/allocation.py` | Created | **143 lines.** `allocate_payments`: FIFO by `(occurred_at, id)`, a partial payment retiring a charge in part, the surplus as `residual`, and a credit note imputing only to a charge at least as old as the note. |
| `backend/tienda/domain/ageing.py` | Created | **91 lines.** `age_in_days` (the calendar-day difference, on shop-local values) and `bucket_of` (the 7/8, 30/31 and 90/91 boundaries). |
| `backend/tienda/domain/evaluation.py` | Created | **161 lines.** `evaluate_customer` (the automatic suspension, `credit_limit=None` as «sin límite», `override=True` lifting it) and `antiguedad_max_dias`. |
| `backend/tienda/domain/charges.py` | Created | **86 lines.** `total_de_linea` (half-up to two decimals), `precio_unitario_de` (the override wins) and `charge_amount_matches` (a line-less charge matches any declared amount). |
| `backend/tienda/domain/confirmation.py` | Created | **146 lines.** `confirmacion_efectiva`, `estado_cargo` (a read-time projection only), `transicion_permitida` (the guard is the **presence** of a row) and `escalado_sin_confirmar` (strictly greater than `dias`). |
| `backend/tienda/domain/stock.py` | Created | **47 lines.** `existencias_registradas`, returning the figure **and** the `techo_no_conteo` qualifier. |
| `backend/tienda/domain/cash.py` | Created | **50 lines.** `caja_al_cierre` (the derived expected cash — the caller never supplies it) and `desviacion_cierre` (`esperado − contado`, signed). |
| `backend/tests/unit/test_domain_is_orm_free.py` | Created | **217 lines, 7 tests.** The AST guard of task 3.1. |
| `backend/tests/unit/test_position.py` | Created | **234 lines, 12 tests.** Task 3.2. |
| `backend/tests/unit/test_allocation.py` | Created | **239 lines, 11 tests.** Task 3.3. |
| `backend/tests/unit/test_ageing.py` | Created | **197 lines, 16 tests.** Task 3.4. |
| `backend/tests/unit/test_evaluation.py` | Created | **286 lines, 17 tests.** Task 3.5. |
| `backend/tests/unit/test_charges.py` | Created | **167 lines, 13 tests.** Task 3.6. |
| `backend/tests/unit/test_confirmation.py` | Created | **293 lines, 15 tests.** Task 3.7. |
| `backend/tests/unit/test_stock.py` | Created | **145 lines, 7 tests.** Task 3.8. |
| `backend/tests/unit/test_cash.py` | Created | **158 lines, 11 tests.** Task 3.9. |
| `backend/tests/harness/domain_is_db_free.py` | Created | **274 lines.** The runtime harness of the slice: a standalone script that exercises all seventeen rules with **no Django settings configured** and **no database**, and exits non-zero if any rule reaches for either. |
| `openspec/changes/fiado-confirmado/tasks.md` | Modified | The eighteen Phase 3 checkboxes marked `[x]`. Phases 1, 2 and 4 onward are untouched. |

### The guarantee, and how it is proved

The slice's whole point is that `backend/tienda/domain/` imports no Django, no
DRF and no app module. Three independent proofs back that claim, and all
three were executed:

**1. The AST guard.** `test_domain_is_orm_free.py` parses every file of the
package and fails on a forbidden import. It reads the files and never
imports them, so it runs with no settings configured. It rejects
`import django.db`, `from django.db import models` under any alias, and
`import tienda.domain.types` — an absolute import of the package's own
subpackage, because `tienda` is an app module. A **relative** import of a
sibling is allowed, and so is a standard-library import.

The guard was **proved non-vacuous**: a probe line
(`from django.db import connection`) was appended to `backend/tienda/domain/stock.py`,
the suite was run, and the two relevant tests **failed** as they should. The
probe was then removed and the file restored byte-for-byte from a backup
taken beforehand. Two further tests assert the *walker itself* works — that a
relative import reads as allowed and a Django import reads as a violation — so
a broken walker could not make the rest of the file pass vacuously.

**2. The pytest-django guarantee.** The unit tests carry **no** `django_db`
marker, and that absence is the proof: pytest-django raises
`RuntimeError: Database access not allowed` for any ORM call in a test
without it. This was **verified on this host**, not assumed: a temporary
probe test that called `Customer.objects.count()` without the marker was
written, run, and observed to fail with exactly that `RuntimeError`. The
database was reachable at the time (`connection.ensure_connection()`
succeeded), so the refusal came from the marker and not from an absent
server. The probe file and its stale `.pyc` were removed.

**3. The standalone harness.** `backend/tests/harness/domain_is_db_free.py`
runs **outside pytest**, imports the domain package and exercises all
seventeen rules with `DATABASE_URL`, `SECRET_KEY`, `DEBUG` and
`ALLOWED_HOSTS` unset. It reads `django.conf.settings.configured` before
and after the rules run: importing `django.conf` configures nothing, so the
flag stays `False` unless a rule reached for it. The harness exits
non-zero on any failure. Observed: `OK: 17 rules exercised with no Django
settings and no database.`

### Deviations from Design

1. **The domain package carries a `MovementKind` enum that design §10 does not
   name.** Design §10 lists `EntryKind`, `Bucket`, `SuspensionReason`,
   `ConfirmState` and `StockQualifier`, and it describes `CashLine` and
   `StockLine` as plain records. Both records carry a `kind` of `entrada` or
   `salida`, and the vocabulary of those two strings already exists in the
   schema (`MOVEMENT_KINDS` in `backend/tienda/models.py`). Spelling it out
   as an enum keeps the two records from depending on a bare string, and
   keeps the domain vocabulary identical to the `CHECK` constraint the
   database enforces. The five enums design §10 names are all present, with
   exactly the values it fixes.

2. **`Allocation` carries a `saldos` field in addition to the assignments
   and the residual.** Design §10 fixes the *guarantee* of
   `allocate_payments` — FIFO, the partial payment, the residual — but does
   not name the record's fields. The `saldos` are the part of each charge
   that is still owed, and `evaluation.antiguedad_max_dias` needs them to
   tell an unpaid charge from a retired one. Without them the rule would
   have to recompute the allocation.

3. **`evaluate_customer` reads the credit notes; `antiguedad_max_dias` does
   not.** The signature design §10 fixes is
   `antiguedad_max_dias(charges, payments, at)` — three arguments, no
   notes. The internal helper that `evaluate_customer` uses applies the
   notes as well, so a charge cancelled by a `nota de crédito` does not age
   and cannot suspend anybody (PA-09). The public function keeps the
   signature the design fixes and is the same computation with no notes.

4. **A credit note reduces a charge directly; it does not draw on the
   payments.** The first implementation of `allocate_payments` placed a
   credit note by consuming the *payment* lines. The test of task 3.3 caught
   it: a note with no payment behind it retired nothing. A `nota de crédito`
   is money given back — it is not money received — so it now reduces the
   charges it is eligible for directly. The guarantee is unchanged: the note
   still imputes only to a charge with `charge.occurred_at ≤
   credit.occurred_at`, and what it cannot place stays as residual.

5. **`cash_at` lives in `position.py`, and `cash.py` calls it.** Design §10
   lists `cash_at` under `position.py` and `caja_al_cierre` under
   `cash.py`, and it says the close is "the same computation as `cash_at`,
   called with `at` = the close instant". `cash.py` therefore **imports**
   `position.py` — a sibling import inside the package, which the AST guard
   allows. The two rules are one computation with one implementation, so
   they cannot drift apart.

### Issues Found

1. **The PostgreSQL server was not running when this batch started.** The
   environment facts state that the portable PostgreSQL 16.4 build is
   "already running on `127.0.0.1:5432`"; it was not. The first
   integration run failed with `psycopg.errors.ConnectionTimeout` on every
   test that needs the database, and `psql` answered `Connection refused`.
   The data directory of Batch 2 was intact, so the server was restarted
   against it. Two host-specific facts, neither of which touches the
   repository: the TLS certificate lives in `pg\tls\`, not in `pg\data\` — a
   path that fails with `could not load server certificate file` — and the
   server must be launched with `cmd /c start /B` rather than
   `Start-Process`, because a child of the shell command's process group is
   killed when that command is torn down. After the restart the
   integration suite passed 37/37.

2. **`psql` hangs without `PGPASSWORD`.** The client prompts
   interactively for the password when it is not supplied, and the prompt
   does not fail in a non-interactive shell — it waits. `PGPASSWORD=fiado`
   together with `-w` makes the client fail fast instead.

3. **Three real defects in the rules, found by the tests of this batch and
   fixed before the slice was accepted.** They are recorded here because
   each one was a genuine misreading of the contract, not a test that was
   adjusted to pass:

   * **`charge_amount_matches` refused a line-less charge.** The comparison
     summed the lines and compared the sum with the declared amount, so an
     empty `lines` sequence matched only a declared 0,00. Design §10 states
     that a charge with no lines matches **any** declared amount, and IC-02
     says a charge without itemisation holds its declared amount as its
     whole total. The empty case is now handled before the sum.
   * **`antiguedad_max_dias` ignored the credit notes.** A charge fully
     cancelled by a `nota de crédito` was still counted as unpaid, so it
     still aged and still suspended the customer — against PA-09, which says
     a credit note reduces the debt. The notes are now applied.
   * **The credit-note allocation drew on the payments.** Already described
     in the deviations above.

4. **The AST guard's text check was too crude on the first run.** The stock
   test asserted that no other module *mentions* `existencias_registradas`,
   and the package `__init__.py` — which names the rule in its docstring —
   failed it. A documentation mention is not a dependency, so the check was
   rewritten as an **AST** walk that looks for an actual import or an
   actual call. The name in prose is now allowed; a call is not.

### Work Unit Evidence

Every command below was **executed** in the state described, and the result
is the observed output. Nothing is reported that was not run. The
environment was clean: `SECRET_KEY`, `DEBUG`, `DATABASE_URL` and
`ALLOWED_HOSTS` were removed from the environment before the unit runs.

| Evidence | Value |
|---|---|
| **Focused test command and exact result** | `python -m pytest backend/tests/unit -q` (clean environment: `SECRET_KEY`, `DEBUG`, `DATABASE_URL`, `ALLOWED_HOSTS` all unset) → **119 passed, 2 warnings in 0.26s, exit 0**. The 119 are the 7 foundation tests of Phase 1 plus the 112 this slice added.<br>`python -m pytest backend/tests/integration -q` (with `DATABASE_URL=postgres://fiado:fiado@127.0.0.1:5432/fiado_test`, `DATABASE_SSLMODE=disable`, `SECRET_KEY` set — the CI-equivalent environment) → **37 passed in 5.22s, exit 0**. Phase 2's constraint suite is intact.<br>Re-run of the unit suite after the probe removal → **119 passed, exit 0**. |
| **Runtime harness command/scenario and exact result** | `python backend/tests/harness/domain_is_db_free.py` (clean environment) → **`OK: 17 rules exercised with no Django settings and no database.`, exit 0**.<br>`python -m pytest backend/tests/unit/test_domain_is_orm_free.py -q` → **7 passed, exit 0** — the AST proof that no file of `backend/tienda/domain/` imports Django, DRF or an app module.<br>**The guard was proved non-vacuous**: with `from django.db import connection` appended to `backend/tienda/domain/stock.py`, the AST suite reported **2 failed, 5 passed, exit 1**. The file was then restored from a pre-probe backup and the unit suite returned to **119 passed, exit 0**.<br>**The DB-free-by-construction guarantee was proved on this host**: a temporary probe test calling `Customer.objects.count()` without the `django_db` marker failed with **`RuntimeError: Database access not allowed, use the "django_db" mark, or the "db" or "transactional_db" fixtures to enable it.`**, exit 1 — while the database was reachable (`connection.ensure_connection()` succeeded), so the refusal came from the missing marker and not from an absent server. The probe file and its stale `.pyc` were removed and the suite returned to **119 passed, exit 0**. |
| **Rollback boundary** | Revert exactly the **twenty-one files** this slice creates and the **one** it modifies, and nothing else:<br>**Created — the domain package (10 files):** `backend/tienda/domain/{__init__,types,position,allocation,ageing,evaluation,charges,confirmation,stock,cash}.py`.<br>**Created — the unit suite (9 files):** `backend/tests/unit/{test_domain_is_orm_free,test_position,test_allocation,test_ageing,test_evaluation,test_charges,test_confirmation,test_stock,test_cash}.py`.<br>**Created — the harness (1 file):** `backend/tests/harness/domain_is_db_free.py`.<br>**Modified (1 file):** `openspec/changes/fiado-confirmado/tasks.md` — the eighteen Phase 3 checkboxes.<br>Nothing else. No model, no migration, no API view, no service, no frontend and no settings line was touched, so the revert leaves the repository exactly as Batch 2 left it, with Phase 1 and Phase 2 still green. The database is untouched: the slice creates no row outside the test database. |

**Proved, and not proved.**

* **Proved by execution:** the unit suite (119 passed), the integration suite
  (37 passed), the AST guard (7 passed, and 2 failures when a forbidden
  import was injected), the standalone harness (17 rules, no settings, no
  database), and the pytest-django `RuntimeError` probe.
* **Not exercised:** the CI container itself. The integration suite ran
  against the portable PostgreSQL 16.4 build, not against the
  `postgres:16` Docker service of `.github/workflows/ci.yml`. The version is
  the same and every assertion in that suite is a PostgreSQL assertion —
  partial unique indexes, `CHECK` semantics and `IntegrityError` — none of
  which SQLite would exercise (landmine 7). The CI run remains the
  authoritative confirmation.
* **Not exercised, by design:** any HTTP surface. This slice has none. The
  service layer of Phase 4 is the first thing that will convert ORM rows
  into the plain records of `domain/types.py`, and it is the first thing
  that could misuse them — the records are the contract between the two
  layers.

### Workload / PR Boundary

- **Mode**: chained PR slice (`feature-branch-chain`)
- **Current work unit**: **PR3a-DomainRules**
- **Boundary**: starts from the tracker branch `feature/base-del-proyecto`
  with the Batch 2 data model merged, and ends with the pure domain layer
  and its unit suite. **Nothing of Phase 4 onward is present**: no
  `backend/tienda/services.py`, no `backend/tienda/api/`, no view, no
  serializer, no frontend and no seed. The slice is self-contained: it adds
  a package of pure functions, the tests that prove them, and one harness
  script. It touches **no** existing file except the Phase 3 checkboxes in
  `tasks.md`.
- **Authored line count**: **3,290 lines across 20 new files** — the domain
  package **1,080** (10 files), the unit suite **1,936** (9 files) and the
  harness **274** (1 file) — plus **18 changed checkbox lines** in
  `tasks.md`. A **3,308-line review diff** by the "lines added" measure;
  **3,326 changed lines** by the "raw line total" measure the runtime
  counts.
- **Review budget impact**: **over the 400-line budget** — `size:exception`
  recommended.
  Nothing was compressed, restyled, deleted or trimmed to reach the number:
  no comment was removed, no test was dropped, no docstring was shortened.
  The budget constrains how the work is sliced, never the code.
  The slice was examined for a smaller honest boundary and rejected on
  evidence. The RED tests and the rules cannot be separated: a PR carrying
  the tests without the rules would not even import
  (`ModuleNotFoundError: No module named 'tienda.domain.position'`), and a
  PR carrying the rules without the tests would ship seventeen rules that
  nobody has exercised — the whole guarantee of this slice is that the rules
  are pure and are proved by unit tests that run with no database. The
  eighteen tasks of Phase 3 are one atomic, independently-green work unit,
  which is what the chain asks for: one deliverable scope, its verification
  included, and a clear rollback boundary.
  The honest split, if the maintainer prefers one, is **PR3a** (the rules and
  their tests, 3,016 lines) and **PR3b** (the harness, 274 lines) — but the
  harness alone is not worth a pull request on its own, since it proves the
  same property the AST guard already proves.

### Remaining Tasks

Phase 4 onward are untouched: 4.1–4.21 (service and API layer) · 5.1–5.9
(client surface, disputes and facilitation) · 6.1–6.8 (seed, frontend and
end-to-end) · 7.1–7.2 (credential boundary RED tests).

Two notes for the next slice. **The service layer is the only ORM-touching
layer**: it converts the rows into the plain records of
`domain/types.py` and calls the rules — it must never let a rule receive an
ORM object. And the three immutable tables still refuse an update and a
delete, so every correction is an append, and the `nota de crédito` that
reconciles a dispute names its charge through `LedgerEntry.cargo_id` — never
through `Confirmacion.cargo_id`.

### Status

**31/31 tasks of Phase 1, Phase 2 and Phase 3 complete** (7 + 6 + 18).

**Runtime ledger — attempt 7, `PR3a-DomainRules`.** The attempt issued for
this work unit was settled with the token
`sha256:1f1c3a8f5f177e90e02215421837c76ae4d1d6f63e02c1314e2d47e9d6fcbf24`
and recorded as **`passed`**, with all three evidence fields, the harness
disposition `reused` and the intended-untracked inventory of the 20 files
this slice creates.

| Runtime field | Value |
|---|---|
| `outcome` | `passed` |
| `changed_lines` | **3,611** — the runtime counts the raw line totals of every new file together with the added and removed lines of the modified files, so it exceeds the "lines added" measure of 3,308 |
| `evidence_revision` | `sha256:84b50461da07f7aa509b346c6d54ad5d4b888c7444ac668e1ddf5c291a7b2cca` |
| `harness_disposition` | `reused` |
| `intended_untracked` | the 20 files this slice creates |
| `changed_line_budget_exceeded` | **`true`** — 3,611 against the 400-line `max_changed_lines` of the objective |
| `decision_required` / `next_action` | **`true`** / **`reset`** — the `size:exception` decision, which belongs to the maintainer. The executor does not reset the objective on its own authority, exactly as in Batches 1 and 2. |

The settle command exited with `state: blocked, reason: maintainer_decision`,
and that block is the budget decision rather than a failure of the work: the
attempt itself is recorded as `passed` with its evidence. The next objective
is ordinal 8, to be opened by the maintainer with
`gentle-ai sdd-attempt reset --expected-revision
sha256:badb9d5d970eec227b3afd6708a0e6f3cf7c79b41286c6cd0f1aa3f0c8ade1a5`.
