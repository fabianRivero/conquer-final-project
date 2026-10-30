# Task Source Index — `fiado-confirmado`

**Machine-derived from `design.md` and `requirement-index.md`. Do not re-derive, re-count or re-enumerate the file inventory, the requirement set or the threat rows in your reasoning.**

Each group below becomes one task-group (or several tasks). §3 names the RED tests that must exist **before** the production work in the group. §5 gives the verification commands. Copy, do not derive.

## 1. File inventory (design §14) — 17 groups, 69 concrete files

| # | Path (expanded) | What | Reqs |
|---|---|---|---|
| 1 | `requirements.txt`<br>`.gitignore`<br>`render.yaml` | Pinned dependencies; the ignores; the Render blueprint (build and run commands, env vars, `sync: false`) | CP-01 |
| 2 | `.github/workflows/ci.yml` | A `postgres:16` service running the unit and integration suites | CP-04, CP-05, PA-11, IC-04 |
| 3 | `.github/workflows/keepalive.yml` | `curl -fsS "$PUBLIC_URL/health/"` every 8 minutes, plus `workflow_dispatch` | CP-04 |
| 4 | `backend/manage.py`<br>`backend/pytest.ini` | The entry point; the pytest configuration with the `unit`/`integration`/`e2e` markers | CP-04, PA-11 |
| 5 | `backend/config/settings.py`<br>`backend/config/urls.py`<br>`backend/config/wsgi.py` | `INSTALLED_APPS`, `REST_FRAMEWORK` with the 422 handler, `STATIC_ROOT`, env-only secrets, `DEBUG=False`, the strict CSP; the mounts; the WSGI app | CP-04, CAC-02, CC-02 |
| 6 | `backend/tienda/models.py`<br>`backend/tienda/migrations/0001_initial.py` | The twelve entities of §3; every `CHECK`, `UNIQUE` and partial index | CP-01, CP-02, CP-03, CP-04, CP-05, CP-06, CP-07, PA-01, PA-02, PA-03, PA-04, PA-05, PA-06, PA-07, PA-08, PA-09, PA-10, PA-11, IC-01, IC-02, IC-03, IC-04, IC-05, IC-06, IC-07, IC-08, IC-09, CAC-01, CAC-02, CAC-03, CAC-04, CAC-05, CAC-06, CAC-07, CAC-08, CAC-09, CAC-10, PC-01, PC-02, PC-03, CC-01, CC-02, CC-03, CC-04, CC-05, CC-06, CC-07, DR-01, DR-02, DR-03, DR-04, CF-01, CF-02 |
| 7 | `backend/tienda/domain/types.py`<br>`backend/tienda/domain/position.py`<br>`backend/tienda/domain/allocation.py`<br>`backend/tienda/domain/ageing.py`<br>`backend/tienda/domain/evaluation.py`<br>`backend/tienda/domain/charges.py`<br>`backend/tienda/domain/confirmation.py`<br>`backend/tienda/domain/stock.py`<br>`backend/tienda/domain/cash.py` | The pure rules of §10 — **no Django import anywhere in the package** | CP-01, CP-02, CP-03, CP-06, PA-01, PA-02, PA-03, PA-04, PA-05, PA-06, PA-11, IC-02, IC-04, IC-06, IC-07, IC-08, IC-09, CC-01, CC-03, CC-04, CC-06, CC-07, DR-01, DR-03, DR-04, PC-01, PC-02, PC-03 |
| 8 | `backend/tienda/services.py` | The only ORM-touching layer: rows → plain values → `domain/` → writes inside `transaction.atomic()` | CP-01, CP-02, CP-03, CP-04, CP-05, PA-01, PA-02, PA-03, PA-04, PA-05, PA-06, PA-07, PA-08, PA-09, PA-10, IC-01, IC-02, IC-03, IC-04, IC-05, IC-06, IC-09, CAC-01, CAC-05, CAC-08, CAC-09, CAC-10, PC-02, CC-01, CC-02, CC-03, CC-04, CC-05, CC-06, CC-07, DR-01, DR-02, DR-03, DR-04, CF-01, CF-02 |
| 9 | `backend/tienda/api/exceptions.py`<br>`backend/tienda/api/permissions.py`<br>`backend/tienda/api/client_auth.py`<br>`backend/tienda/api/throttle.py` | The 422/403 handler; `RoleRequired`/`IsDueno`/`EsCliente`; `resolver_credencial`; the throttle ledger | CAC-01, CAC-02, CAC-03, CAC-04, CAC-05, CAC-06, CAC-07, CAC-08, CAC-09, CAC-10, CC-01, CC-02, CC-03, CC-04, CC-05, CC-06, CC-07, DR-01, DR-02, DR-03, DR-04, CF-01, CF-02, CP-01, PA-10 |
| 10 | `backend/tienda/api/serializers/staff.py`<br>`backend/tienda/api/serializers/cliente.py` | The two staff allowlists, the two close allowlists and the client schema, which is disjoint from all of them | CAC-02, CAC-03, CAC-06, CAC-07, CAC-10, CC-02, CC-03, CC-06, CC-07, CP-04, CP-05 |
| 11 | `backend/tienda/api/views.py`<br>`backend/tienda/api/urls.py` | The routes of §9.1 and their URL map | CP-01, CP-02, CP-03, CP-04, CP-05, CP-06, CP-07, PA-01, PA-02, PA-03, PA-04, PA-05, PA-06, PA-07, PA-08, PA-09, PA-10, IC-01, IC-02, IC-03, IC-04, IC-05, IC-06, IC-07, IC-08, IC-09, CAC-01, CAC-02, CAC-03, CAC-04, CAC-05, CAC-06, CAC-07, CAC-08, CAC-09, CAC-10, PC-01, PC-02, PC-03, CC-01, CC-02, CC-03, CC-04, CC-05, CC-06, CC-07, DR-01, DR-02, DR-03, DR-04, CF-01, CF-02 |
| 12 | `backend/tienda/management/commands/seed_demo.py` | The idempotent demo dataset of §18.2 | CP-01, CP-02, CP-03, CP-04, CP-05, CP-06, CP-07, PA-01, PA-03, PA-04, PA-05, PA-06, PA-09, IC-01, IC-02, IC-03, CAC-01, CAC-05, CAC-08, CAC-09, CAC-10, PC-01, PC-02, PC-03, CC-01, CC-02, CC-03, CC-04, CC-05, DR-01, DR-02, DR-03, CF-01, CF-02 |
| 13 | `backend/tests/unit/test_domain_is_orm_free.py`<br>`backend/tests/unit/test_position.py`<br>`backend/tests/unit/test_allocation.py`<br>`backend/tests/unit/test_ageing.py`<br>`backend/tests/unit/test_evaluation.py`<br>`backend/tests/unit/test_charges.py`<br>`backend/tests/unit/test_confirmation.py`<br>`backend/tests/unit/test_stock.py`<br>`backend/tests/unit/test_cash.py` | `test_domain_is_orm_free` plus one file per pure rule, with no database | CP-06, PA-02, PA-11, IC-02, IC-04, IC-06, CC-01, CC-04, DR-03, PC-02, CP-03, PA-03, PA-04, PA-05, PA-06 |
| 14 | `backend/tests/integration/test_cash_api.py`<br>`backend/tests/integration/test_ledger_api.py`<br>`backend/tests/integration/test_catalogo_api.py`<br>`backend/tests/integration/test_permissions_api.py`<br>`backend/tests/integration/test_no_leak.py`<br>`backend/tests/integration/test_cliente_api.py`<br>`backend/tests/integration/test_facilitation_api.py`<br>`backend/tests/integration/test_constraints.py`<br>`backend/tests/integration/test_seed.py` | The cash, ledger, catalogue, permissions, no-leak, client, facilitation, constraints and seed suites | CP-01, CP-02, CP-03, CP-04, CP-05, PA-01, PA-02, PA-03, PA-04, PA-05, PA-06, PA-07, PA-08, PA-09, PA-10, IC-01, IC-02, IC-03, IC-04, IC-05, IC-06, IC-07, IC-08, IC-09, CAC-01, CAC-02, CAC-03, CAC-04, CAC-05, CAC-06, CAC-07, CAC-08, CAC-09, CAC-10, PC-01, PC-02, PC-03, CC-01, CC-02, CC-03, CC-04, CC-05, CC-06, CC-07, DR-01, DR-02, DR-03, DR-04, CF-01, CF-02 |
| 15 | `backend/tests/e2e/test_public_url.py` | The deployed URL: HTTPS, `DEBUG=False`, login, the same-origin fetch, the seeded accounts | CAC-01, CAC-06, CAC-07, CC-05, CC-06, CP-01 |
| 16 | `frontend/package.json`<br>`frontend/vite.config.ts`<br>`frontend/tsconfig.json`<br>`frontend/index.html` | The Vite + React + TypeScript build; the output lands in `STATIC_ROOT` | CAC-06, CAC-07, CC-02, CC-03, CC-05, CC-06, CC-07 |
| 17 | `frontend/src/main.tsx`<br>`frontend/src/router.tsx`<br>`frontend/src/api/http.ts`<br>`frontend/src/api/staff.ts`<br>`frontend/src/api/cliente.ts`<br>`frontend/src/surfaces/Posicion.tsx`<br>`frontend/src/surfaces/Cliente.tsx`<br>`frontend/src/components/Ecuacion.tsx`<br>`frontend/src/components/Escalera.tsx`<br>`frontend/src/components/Cinta.tsx`<br>`frontend/src/components/Cierre.tsx`<br>`frontend/src/components/ConfirmarAccion.tsx`<br>`frontend/src/components/Acceso.tsx`<br>`frontend/src/components/Disputar.tsx`<br>`frontend/src/components/Credenciales.tsx` | The mount, the two routes, the three fetch layers, the two surfaces and the components `Ecuacion`, `Escalera`, `Cinta`, `Cierre`, `ConfirmarAccion`, `Acceso`, `Disputar`, `Credenciales` | CP-01, CP-03, CP-04, CP-05, CAC-02, CAC-03, CAC-05, CAC-06, CAC-07, CAC-08, CAC-09, CAC-10, CC-02, CC-03, CC-04, CC-05, CC-06, CC-07, DR-04, CF-01, CF-02 |

Every path above is **created** — nothing is modified, nothing is deleted. Package markers (`__init__.py`) are implied. `openspec/changes/tienda-barrio/` and `openspec/explorations/` are **not** touched; nothing is written under `openspec/specs/`.

## 2. Requirement → verification layer (53) → design home

| ID | Requirement | Layer | Design home |
|---|---|---|---|
| CP-01 | Cash movements are recorded and validated | integration | §3 `CashMovement`; §3 rule 13 (the future stamp); §9.1 |
| CP-02 | `caja` is recorded cash movements | unit, integration | §10 `cash_at` |
| CP-03 | `posicion_real` is additive | unit, integration | §10 `real_position`; ADR-9 |
| CP-04 | The day close is the anchor of `caja` | integration | §3 `DayClose`; §3 rule 14 (the derived `esperado`); §10 `caja_al_cierre`, `desviacion_cierre` |
| CP-05 | The day close is available to both shop roles | integration | §7 rows 1–2; §9.1 `GET /api/v1/cierre/`; §9.2 `CierreDuenoSerializer`, `CierreDependienteSerializer` |
| CP-06 | The position rule is pure and ORM-free | unit | §10 `real_position`; ADR-3 |
| CP-07 | `existencias_registradas` is a ceiling, never a count | unit, integration | §2 D5; §10 `existencias_registradas` |
| PA-01 | `outstanding` is derived, never stored | unit, integration | §10 `outstanding`; §3 not-stored |
| PA-02 | Payments are allocated FIFO | unit | §10 `allocate_payments`; ADR-7 |
| PA-03 | Ageing buckets are derived per charge | unit, integration | §10 `bucket_of` (per-charge age; the four totals sum exactly to the outstanding), `age_in_days` |
| PA-04 | A disputed charge is debt, not a credit | unit, integration | §10 `outstanding`; §6 |
| PA-05 | The credit limit is an explicit state | integration | §3 `Customer.credit_limit` |
| PA-06 | Suspension is automatic and evaluated on read | unit, integration | §10 `evaluate_customer`; §2 D1 |
| PA-07 | A suspended customer cannot receive a new charge | integration | §3 rules 1–2; §9.3 |
| PA-08 | The owner can lift a suspension explicitly | integration | §3 `suspended_override_at`; §9.1 |
| PA-09 | A correction is appended as a `nota de crédito` | integration | §3 `LedgerEntry.kind`; ADR-19 |
| PA-10 | The ledger write API is validated | integration | §9.1; §9.3; §3 rules 4, 16 and 17 (`occurred_at` refused, `importe_no_positivo`, `tipo_desconocido`) |
| PA-11 | The credit rules are pure and ORM-free | unit | §10; ADR-3 |
| IC-01 | The ledger is append-only | integration | §3 immutability; §9.1 |
| IC-02 | The amount of a `cargo` equals its itemisation total | integration | §10 `charge_amount_matches`; §3 rule 3 (and the line-less cargo it preserves) |
| IC-03 | A `cargo` never depends on the confirmation | unit, integration | §1 idea 3; ADR-23 |
| IC-04 | The effective confirmation state is derived | unit, integration | §10 `estado_cargo`, `confirmacion_efectiva`; ADR-18 |
| IC-05 | The `cargo` write API is validated | integration | §9.1; §9.3 |
| IC-06 | The charge rules are pure and ORM-free | unit | §10 `charges.py`; ADR-3 |
| IC-07 | A `cargo` carries `CargoLinea` rows | integration | §3 `CargoLinea`; §10 |
| IC-08 | `precio_unitario` is a snapshot | integration | §3 `CargoLinea`; §2 D8 |
| IC-09 | Charge lines are immutable with their charge | integration | §3 immutability |
| CAC-01 | Two shop roles exist and are enforced on the server | integration | §7; ADR-5 |
| CAC-02 | The credit book is owner-only among the staff | integration | §7.1; §9.2 |
| CAC-03 | No staff session reaches the client surface or gains a client scope | integration | §8; §7.2; §13.3 |
| CAC-04 | Sessions and CSRF protect every staff mutation | integration | §12; §9.1 |
| CAC-05 | The customer record minimises personal data | integration | §3 `Customer`; §3 not-stored |
| CAC-06 | The views consume the application's own API at the public URL | e2e | §11 same-origin contract; §15.3 |
| CAC-07 | Production is locked and secrets stay out of the repository | e2e | §12; §18.1 |
| CAC-08 | One account per shop role is seeded | integration, e2e | §18.2; §15.3 |
| CAC-09 | The `codigo` is a scoped, per-shop credential | integration | §5; §2 D2–D4 |
| CAC-10 | The client payload carries nothing but that customer's own data | integration | §9.2 `EstadoClienteSerializer` |
| PC-01 | The catalogue holds only the goods eligible for fiado | integration | §3 `Producto.activo` |
| PC-02 | `precio` is a default, not a constraint | integration | §2 D8; §10 |
| PC-03 | The catalogue is readable and seeded | integration | §3 `Producto`; §18.2 |
| CC-01 | The client confirms their own charge | integration | §6; §9.1 |
| CC-02 | The statement shows every charge of that client | integration | §9.2; §13.1 |
| CC-03 | An unconfirmed charge is a summary row with a `Confirmar` action | integration | §9.2; §11 client statement |
| CC-04 | The client may dispute a charge | integration | §6; §9.1 |
| CC-05 | The client view consumes the application's own API | e2e | §11 same-origin contract; §15.3 |
| CC-06 | A confirmed charge shows its full itemisation | integration | §9.2 `EstadoClienteSerializer` (`lineas[]` when the charge carries a `confirmado` row) |
| CC-07 | The itemisation of an unconfirmed charge is revealed only inside the action | integration | §9.2 (the unconfirmed-charge rule: the key is omitted, not emptied); §9.1; landmine 9 |
| DR-01 | A dispute is recorded without touching the charge | integration | §6; §13.2 |
| DR-02 | The owner arbitrates the dispute | integration | §6; §13.2 |
| DR-03 | A dispute is reconciled at most once | integration | §2 D7; ADR-20 |
| DR-04 | The client sees the dispute and its resolution | integration | §9.2; §13.2 |
| CF-01 | The `dependiente` presents one charge and receives the confirmation | integration | §2 D6; §7; §13.3 |
| CF-02 | The facilitator is recorded and holds no client scope | integration | §3 `facilitado_por`; §8; §13.3 |

## 3. RED tests required BEFORE their production task

Every row is an explicit test-first task. The threat matrix is already decided: the five reference rows are explicit `N/A` and **must not** become tasks; only the five real boundaries do.

| # | Test | Asserts | Boundary |
|---|---|---|---|
| R1 | `test_codigo_ausente_de_todo_arbol_staff` | The plaintext and the `prefix` are absent from every JSON path of every owner and `dependiente` response | staff payloads |
| R2 | `test_codigo_ausente_de_todo_arbol_cliente` | The plaintext is absent from every JSON path of every client response | the client routes |
| R3 | `test_codigo_ausente_de_los_logs` | `caplog` over a client request cycle holds no occurrence | logs |
| R4 | `test_codigo_ausente_de_la_url` | `path` and `get_full_path()` never contain the credential | the credential in transit |
| R5 | `test_codigo_ausente_del_cuerpo_de_error` | A forced 422 and a forced 500 carry no part of the credential | error bodies |
| R6 | `test_codigo_en_claro_no_se_persiste` | No field of any model row holds the plaintext | storage |
| R7 | `test_dependiente_ve_cero_credenciales` | Every credit-book endpoint answers 403; no 200 staff response holds `codigo` or `prefix` | the staff routes |
| R8 | `test_throttle_no_es_oraculo` | Unknown, revoked and throttled credentials return byte-identical payloads | the throttle |
| R9 | `test_credential_unicity` | Unique in the shop; one active credential per customer; a rotated value refuses the old one | the credential lifecycle |

Plus the scope/leak tests named in §17: `test_scopes_no_se_mezclan`, `test_staff_scope_ignores_codigo`, `test_credit_book_403`, `test_staff_session_reaches_no_client_endpoint`, `test_cliente_no_crea_cookie`, `test_domain_is_orm_free`, and `backend/tests/integration/test_facilitation_api.py`.

## 4. Verification commands available to a task

| Command | What it proves | Database |
|---|---|---|
| `python -m pytest backend/tests/unit -q` | the pure rules of §10 | **none**, by construction |
| `python -m pytest backend/tests/integration -q` | the API contract, the constraints, the leak walk | **PostgreSQL 16** — never SQLite (landmine 7) |
| `python -m pytest backend/tests/e2e -q` | the deployed public URL | the deployed service |

`pytest` is **not** on PATH: the form is `python -m pytest`. Python is at `C:\Python314\python.exe`. `black`, `ruff`, `vitest` and `playwright` are **not** installed.

## 5. Size budget — READ THIS

The sdd-tasks skill states: *"Tasks artifact MUST be under 530 words"*. That target is **arithmetically unreachable** for this change: 17 file groups / 69 concrete files, 53 requirements across 8 capabilities, 9 credential RED tests plus 7 scope/leak tests, 3 test layers and a deployment spine floor the checklist far above 530 words.

The precedent set by the design phase: the mandated content set was kept and the **deviation was stated plainly** in the artifact rather than dropping mandated content. Do the same here — write the complete actionable checklist and state the deviation from the 530-word target in the artifact itself, with the measured word count.
