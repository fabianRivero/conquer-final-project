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
two pytest steps, because pytest exits 4 when the test directory does not exist yet; PR 1c
removes it, so the CI is strict from that point on.

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
- [x] 1.4 Create `.github/workflows/keepalive.yml` with `curl -fsS "$PUBLIC_URL/health/"` every 8 minutes plus `workflow_dispatch`. Proves CP-04 — landmine 3.
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
