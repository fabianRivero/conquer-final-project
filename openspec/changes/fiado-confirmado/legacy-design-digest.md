# Legacy design digest — condensed input for `fiado-confirmado`

**A CONDENSED INPUT, not a deliverable.** Compresses `tienda-barrio/design.md` (~95 KB) + `spec-traceability.md` for the `fiado-confirmado` design phase. **Change read:** `tienda-barrio` (ABANDONED) · **Traceability:** 34 requirements, 47 scenarios.

## 1. Section structure of the original design (mirror this shape)

1. Overview and architecture — 3 ideas; Decision A (DB backstop), B (422).
2. Repository structure — tree; pure-core location.
3. The domain core — types, timezone rule, 4 signatures + 2 helpers.
4. Data model — ER diagram, fields, constraints, indexes.
5. Transaction boundaries — `transaction.atomic()` + `select_for_update()`.
6. API contract — 12 routes, two payload shapes, 422 table.
7. Security architecture — 2×9 matrix layers, shop of the session.
8. The React board — tree, fetch, polling, SVG chart.
9. Testing strategy — pytest-django, unit-first ordering.
10. Deployment — spine, env vars, `seed_demo`, landmines.
11. ADRs — ADR-1 … ADR-15.
12. Threat matrix — shell rows + HTTP routing boundary.
13. Requirement coverage — 34 requirements → section → mechanism.
14. Risks and trade-offs — R1 … R12.
15. Open questions — all resolved 2026-10-20.

## 2. The ADRs — all 15, none omitted

| # | Title | Decision | Trade-off · consequence |
|---|---|---|---|
| 1 | One service + WhiteNoise | Bundle into `STATIC_ROOT`, served by WhiteNoise | One origin, no CORS. |
| 2 | Derived balances | Every balance computed from the ledger | Never desynchronises. |
| 3 | ORM-free domain module | `tienda/domain/` imports no Django | Unit-testable without a DB. |
| 4 | Session + CSRF, not JWT | Django session cookie + `X-CSRFToken` | No token in browser storage. |
| 5 | Django Groups + mixins | Two groups (`dueno`, `dependiente`) + `RoleRequired` | 2×9 matrix not runtime-editable. |
| 6 | Serializer-level allowlist | Two classes, disjoint fields; `dependiente` has no credit-book field | "No alias in ANY JSON path" is structural. |
| 7 | FIFO | Oldest charge first; surplus stays as credit | Oldest debt ages into suspension. |
| 8 | No worker; expiry on read | No Celery/Redis/cron; status derived on every read | No extra infrastructure. |
| 9 | `posicion_real` additive | `caja + outstanding sum`, everywhere | A `pago` converts money. |
| 10 | Polling, not WebSockets | `GET /api/v1/posicion/` every 20 s | The poll is also keep-alive. |
| 11 | Demo credentials public, real secrets env-only | `dueno@`/`dependiente@tienda.test` documented; `SECRET_KEY`/`DATABASE_URL` env-only | The demo password is not a secret. |
| 12 | Hand-rolled SVG chart | Plain SVG, fixed `viewBox="0 0 720 220"` | Small bundle, explainable line by line. |
| 13 | Decimal on the wire | `Decimal` in domain and ORM, JSON strings on the wire | No float drift. |
| 14 | Per-row DB constraints + transactional cross-row check | `CHECK` on `amount > 0`, `kind`, `credit_limit ≥ 0`, `occurred_at ≤ created_at`; `UNIQUE (shop, date)` | Aggregate rule only in `transaction.atomic()`. |
| 15 | Shop of the session, on `Shop` | `shop_id` in the session, written at login; `Shop.usuarios` M2M; `auth.User` unmodified | One source of scope. |

## 3. The data model

- **`Shop`** - `id`, `name` (unique), `opening_cash` (Decimal 12,2), `is_demo`, `usuarios` (M2M → `User`), `created_at`. CHECK `opening_cash ≥ 0`.
- **`Customer`** - `id`, `shop_id`, `alias`, `phone?`, `credit_limit?` (= «sin límite»), `status` (`activo`/`suspendido`), `suspended_at`, `suspended_reason`, `suspended_by_id`, `suspended_override_at`. UNIQUE(shop, alias).
- **`LedgerEntry`** (append-only) - `id`, `shop_id`, `customer_id`, `kind` (`cargo`/`pago`/`nota_credito`), `amount`, `occurred_at`. CHECK `amount > 0`, `kind` in set, `occurred_at ≤ created_at`; FK `customer_id` PROTECT.
- **`CashMovement`** - `id`, `shop_id`, `kind` (`entrada`/`salida`), `concept`, `amount`, `occurred_at`. CHECK `amount > 0`, `kind` in set.
- **`DayClose`** - `id`, `shop_id`, `date`, `expected_cash`, `counted_cash`, `variance` (= `esperado - contado`), `closed_at`. UNIQUE(shop, date).
- **`User`** — Django `auth.User`, **unmodified**; groups `dueno`, `dependiente`; `PBKDF2PasswordHasher` not overridden (`pbkdf2_sha256`, 1 000 000 iterations).

**Relations.** `User`<->`Shop` (M2M `usuarios`); `Shop` -> `Customer`, `LedgerEntry`, `CashMovement`, `DayClose` (CASCADE); `Customer` -> `LedgerEntry` (PROTECT); `User` authors entries and movements, closes `DayClose`, is `suspended_by`/`suspended_override_by`. **No owner FK on any data entity (D11)** - scope is `Shop` + role. Append-only (CB-01): `update()`/`delete()` raise `LedgerImmutableError`.

### 3.1 Which layer enforces what

- **DB per-row `CheckConstraint`:** `LedgerEntry.amount > 0`; `kind` ∈ {`cargo`,`pago`,`nota_credito`}; `CashMovement.amount > 0`, `kind` ∈ {`entrada`,`salida`}; `Customer.credit_limit ≥ 0` (NULL = `null` = «sin límite»); `LedgerEntry.occurred_at ≤ created_at`; `Customer.status`/`suspended_reason` in set. **Unique:** `DayClose.(shop, date)`; `Customer.(shop, alias)`.
- **Server, in `transaction.atomic()`:** `outstanding > credit_limit`; *the customer is `suspendido`*. A `CHECK` **cannot** express either - it sees one row, never an aggregate, never another table's rows. Violation -> `DomainValidationError` -> rollback, no row. **Serializer -> 422 `campo_no_admitido`** when the client sends `occurred_at`; the server stamps `now()`.

The DB is a **safety net for the per-row invariants only**; the cross-row rules live in the server, inside the write transaction (422, no row). The original flagged «una `CheckConstraint` es la red de seguridad» as **overstated**.

## 4. Security architecture

**Two independent layers.** (1) **View level** - `RoleRequired`/`IsDueno` on every view; a `dependiente` gets **403 with no partial data**; every queryset is scoped to `request.session["shop_id"]` via `current_shop(request)`. (2) **Serializer allowlist** - `PosicionDuenoSerializer` declares `caja, fiado_pendiente, posicion_real, buckets, clientes, serie_caja, cierre_hoy`; `PosicionDependienteSerializer` declares only `caja`, `clientes` (a `SerializerMethodField` returning `[]` **without executing a customer query**), `cierre_hoy`. DRF's `fields` list is exhaustive: only a schema-level allowlist makes "no alias in ANY JSON path" structural.

- **Session and CSRF:** Django session (`SessionMiddleware` + `AuthenticationMiddleware`) + DRF `SessionAuthentication`; unauthenticated -> **403**, no rows; a mutation without `X-CSRFToken` -> **403** and no row.
- **Data-protection failure modes:** nested-aggregate leak; metadata leak (pagination removed); error-body echo; the *silent query* (`clientes` returns `[]` **without executing** the customer query); the hand-maintained contract R2; the unvalidated `alias`.

### 4.1 Landmine list — traps a future implementer must not fall into

1. Render's filesystem is ephemeral and its free Postgres expires after 30 days -> SQLite data dies and the DB vanishes mid-project -> PostgreSQL from day one (Neon).
2. `collectstatic` misconfiguration -> a blank page, not an error -> smoke check: bundle URL 200. 3. Free tier sleeps after 15 minutes -> a loading page during the defense -> keep-alive under 10 min.
4. `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` missing -> every POST returns 403 -> both from env, set on first deploy. 5. `seed_demo` not idempotent -> duplicated data or a stale board -> the seed is in the build command, with an idempotency test.
6. A `dependiente` leaking a customer field -> data-protection failure -> allowlist + whole-tree walk. 7. Integration suite on SQLite -> `select_for_update` and `CHECK` semantics not exercised -> CI runs PostgreSQL.

## 5. The pure-rules module

**`backend/tienda/domain/` has zero Django imports** - no Django import of any kind - enforced by `tests/unit/test_domain_is_orm_free.py` (AST parse of every file). Types: `EntryKind`, `Bucket` (`vigente`/`envejecido`/`viejo`/`cronico`), `SuspensionReason`, plus `LedgerLine`, `CashLine`, `Allocation`, `CustomerState`. Plain values in, plain values out - no ORM type, no database, no request, no implicit clock (the caller passes `at`); the **service layer** alone converts UTC -> shop-local, so a "day" is a calendar day of the shop.

| Function (module) | Signature | Output / guarantee |
|---|---|---|
| `allocate_payments` (`allocation.py`) | `(charges: Sequence[LedgerLine], payments: Sequence[LedgerLine], *, credit_notes: Sequence[LedgerLine] = ()) -> Allocation` | FIFO by `(occurred_at, id)`; a credit only imputes to a charge with `charge.occurred_at ≤ credit.occurred_at`; surplus stays as `residual` |
| `bucket_of` (`ageing.py`) | `(age_days: int) -> Bucket` | `vigente` ≤ 7 d, `envejecido` 8-30, `viejo` 31-90, `cronico` > 90 |
| `age_in_days` (`ageing.py`) | `(occurred_at: datetime, at: datetime) -> int` | Calendar-day difference `(at.date() - occurred_at.date()).days`; values arrive shop-local |
| `evaluate_customer` (`evaluation.py`) | `(lines: Sequence[LedgerLine], *, credit_limit: Decimal \| None, at: datetime, suspension_age_days: int = 30, override: bool = False) -> CustomerState` | Derived state; `credit_limit=None` = «sin límite», never fires `limite_superado` |
| `real_position` (`position.py`) | `(caja: Decimal, outstanding_total: Decimal) -> Decimal` | `posicion_real = caja + Σ pending balances`, additive only |
| `outstanding` (`position.py`) | `(lines: Sequence[LedgerLine], at: datetime) -> Decimal` | Σ cargos − Σ pagos − Σ notas, `occurred_at ≤ at`; negative = `credit_a_favor` |
| `cash_at` (`position.py`) | `(opening_cash: Decimal, movements: Sequence[CashLine], pagos: Sequence[LedgerLine], at: datetime) -> Decimal` | `caja = inicial + Σ(entradas) − Σ(salidas) + Σ(pagos)`, `occurred_at ≤ at` |

## 6. The API route table

All `/api/v1/` endpoints require a **session**; all writes require `X-CSRFToken`; **no pagination anywhere** (bare JSON list). Outside `/api/v1/`: `/health/` (liveness) and `/app/posicion/` (the HTML mount point).

| Method | Path | Roles | Response · status |
|---|---|---|---|
| GET | `/health/` | public | `{"status":"ok"}` · 200 |
| GET | `/app/posicion/` | both (page) | HTML + React mount + CSRF token · 200; 302 to login |
| GET | `/api/v1/posicion/` | both, shape differs | owner or dependent payload · 200; 403 |
| POST | `/api/v1/caja/` | both | the movement · 201; 422; 403 |
| GET | `/api/v1/cierre/` | both | `{date, esperado, contado, desviacion}` · 200; 403 |
| POST | `/api/v1/cierre/` | both | `{date, esperado, contado, desviacion}` · 201; 422; 403 |
| GET | `/api/v1/clientes/` | `dueno` | `[customer, …]` · 200; **403** |
| POST | `/api/v1/clientes/` | `dueno` | customer · 201; 422; 403 |
| GET | `/api/v1/clientes/{id}/` | `dueno` | customer, `libreta`, state, `suspension` audit · 200; 403; 404 |
| PATCH | `/api/v1/clientes/{id}/` | `dueno` | customer · 200; 422; 403 |
| POST | `/api/v1/clientes/{id}/libreta/` | `dueno` | `{entry, estado, antiguedad_max_dias, outstanding}` · 201; **422**; 403 |
| POST | `/api/v1/clientes/{id}/suspension/anular/` | `dueno` | customer · 200; 403 |

- **403 boundary:** total and server-side - credit-book endpoints are unreachable and no `PUT`/`PATCH`/`DELETE` route exists for `LedgerEntry`: append-only at the URL surface. **Deliberate asymmetry:** the ledger is immutable in time, the cash box is not (back-dating a `cargo` re-assigns an earlier `pago`, R1).
- **Payload shapes:** `dueno` carries `caja`, `fiado_pendiente`, `posicion_real`, `buckets`, `clientes[]`, `serie_caja[]`, `cierre_hoy`; the ladder is sorted by `antiguedad_max_dias` **descending**, only customers with `pendiente > 0`, `serie_caja` = one entry per day for 30 days, carried forward on empty days. `dependiente` gets `caja`, `clientes: []`, `cierre_hoy` **only** (RAC-03).
- **Domain errors:** one file - `backend/tienda/api/exceptions.py` defines `DomainValidationError(ValidationError)` and an `exception_handler` returning `Response({"codigo": ..., "detail": ...}, status=422)`, wired through `REST_FRAMEWORK["EXCEPTION_HANDLER"]`. `detail` is a Spanish message that **names the limit**; `codigo` is a stable code: `limite_superado`, `antiguedad_superada`, `importe_no_positivo`, `campo_no_admitido`, `tipo_desconocido`, `cierre_duplicado`. **422** = every validation failure.

## 7. The deployment spine

```
GitHub (public) --push--> Render Web Service (free, managed TLS)
   build: pip install -r requirements.txt && npm --prefix frontend ci && npm --prefix frontend run build
          python manage.py collectstatic --noinput && python manage.py migrate --noinput && python manage.py seed_demo
   run:   gunicorn config.wsgi:application --workers 1 --threads 2
   -->   Neon PostgreSQL (free, permanent)  [DATABASE_URL]
frontend/dist --> STATIC_ROOT --> WhiteNoise --> SAME ORIGIN
```

- **Neon, not Render's Postgres:** Render's free PostgreSQL **expires 30 days** after creation. Neon free is permanent - a hard requirement.
- **Env vars:** `DATABASE_URL` (Neon, Render `sync: false`, mandatory in production); `SECRET_KEY` (Render `generateValue: true`); `DEBUG` (`False`); `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` (comma separated, latter **with scheme**); `PYTHON_VERSION` 3.14.7; `NODE_VERSION` 24.21.0.
- **`seed_demo` idempotency contract** (part of the build command): one `transaction.atomic()`; **Users** via `get_or_create(username=...)`, the dataset hangs off one `Shop` flagged `is_demo=True`, which the seed deletes and recreates - **9 customers** with distinct aliases and no locator, dates relative to the execution day; that deletion is the **only** deletion in the codebase, confined to `is_demo=True`.
- **Availability:** `.github/workflows/keepalive.yml` runs `curl -fsS "$PUBLIC_URL/health/"` on `cron: "*/8 * * * *"` (every 8 minutes, under the 10-minute requirement) plus `workflow_dispatch`. `/health/` touches **no database**, so a ping never exhausts the pool.

## 8. The testing strategy shape

`backend/pytest.ini`: `DJANGO_SETTINGS_MODULE = config.settings`, `testpaths = tests`, markers `unit`, `integration`, `e2e`.

- **`unit`** (`backend/tests/unit/`) - the pure functions against hand-computed fixtures + the AST architecture test. **No database:** pytest-django raises `RuntimeError: Database access not allowed` for any ORM call in a test lacking `django_db`, so the layer is DB-free **by construction**.
- **`integration`** (`backend/tests/integration/`) — Django test client against **PostgreSQL**: the API contract, the 2×9 matrix, the 422 payloads, the no-leak JSON walk, the real `CHECK`/`UNIQUE` constraints, the rollback, seed idempotency.
- **`e2e`** (`backend/tests/e2e/`) - against the **deployed public URL**: HTTPS, login, 403 on the credit book, no alias leak, seeded figures, `DEBUG=False`. **Landmine:** the integration suite must run on **PostgreSQL**; CI provides a `postgres:16` container. **Evidence discipline:** every requirement id maps to a section, a mechanism and a verification level - 34 of 34.

## 9. The language contract — reproduced verbatim from the original

> **Language contract:** prose in English; **every domain identifier, field name, API field and diagram label stays in Spanish** (`fiado`, `cargo`, `pago`, `nota de crédito`, `caja`, `dependiente`, `dueño`, `libreta`, `posición real`, `antiguedad_max_dias`, `suspended_reason`, `vigente`/`envejecido`/`viejo`/`cronico`) because these are the code identifiers and the diagram labels are pasted verbatim into la memoria.

## 10. Verdict — what still holds and what breaks under `fiado-confirmado`

**New scope.** Keeps: append-only ledger, FIFO allocation, credit limit, automatic suspension, the `dependiente` 403 boundary, session+CSRF staff surface, same-origin React mount, seed plan, additive `posicion_real`, `Decimal`-on-the-wire, the 422 contract, the evidence discipline. **Adds:** a product catalogue, charge lines, a client-facing credential, a confirmation/dispute state machine, a second React surface, a movement-derived stock figure.

### 10.1 Per-ADR verdict (the primary output)

| ADR | Verdict · what changes |
|---|---|
| 1 One service + WhiteNoise | **Holds with amendment** - second bundle in `STATIC_ROOT`. |
| 2 Derived balances | **Holds unchanged in principle; scope extends** - stock figure must be derived. |
| 3 ORM-free domain module | **Holds unchanged** - pricing, state machine, stock go in `domain/`. |
| 4 Session + CSRF, not JWT | **Holds with amendment - largest change** - a second auth principal; needs its own call. |
| 5 Django Groups + mixins | **Holds with amendment** - 2×N plus a client principal. |
| 6 Serializer-level allowlist | **Holds unchanged in principle; must be extended** - one allowlist per audience. |
| 7 FIFO | **Holds with amendment** - granularity changes to charge lines. |
| 8 No worker, expiry on read | **Holds with amendment - most at risk** - a scheduled deadline breaks it; derive on read. |
| 9 `posicion_real` additive | **Holds unchanged** - additive; must not reach the client payload. |
| 10 Polling, not WebSockets | **Holds with amendment** - a second surface doubles the load. |
| 11 Demo credentials public, real secrets env-only | **Holds with amendment** - a third class: issued, hashed, revocable. |
| 12 Hand-rolled SVG chart | **Holds unchanged** - no charting library by inertia. |
| 13 Decimal on the wire | **Holds with amendment** - money only; quantities need a non-float type. |
| 14 Per-row constraints + transactional check | **Holds unchanged; widened** - catalogue invariants become `CHECK`/`UNIQUE`. |
| 15 The shop of the session | **Holds with amendment - structurally** - "one source of scope" stops holding. |
