# Spec Traceability — `tienda-barrio` (fiado — La libreta y la caja)

**Change:** `tienda-barrio` · **Phase:** SDD spec · **Source of scope:** `proposal.md` (approved), `acceptance-criteria.md` §1 (F1–F5, numbered in list order), `submission-notes.md` §10 (capability contract), `openspec/config.yaml` → `rules.specs`.

**Acceptance-criterion IDs** `F1-AC1 … F5-AC4` are the numbered criteria of `acceptance-criteria.md` §1, in list order. They are stable and unchanged by this pass. Delivery-guide items carry the fresh IDs `DG-1 … DG-8`; security items `SEC-1 … SEC-6`; the pure-core item `PURE-1`. Requirement IDs `CB-01 … PB-07` are stable; `CB-12` and `PB-07` are new in this pass.

**Verification levels:** `unit` = pure domain function, no ORM · `integration` = Django test client / DB · `e2e` = deployed public URL.

---

## 1. Requirement → capability → feature → acceptance criterion → verification

### `credit-book` — 12 requirements, 17 scenarios

| Req | Feature | Acceptance criterion | Verification |
|---|---|---|---|
| CB-01 | F3 | F3-AC4 (append-only; mutation impossible) | integration |
| CB-02 | F3 | F3-AC1 (derived = hand-computed), F3-AC3 (surplus), F2-AC4 (derived, not stored) | unit, integration |
| CB-03 | F3 | F3-AC2 (FIFO retires the oldest `cargo` first) | unit |
| CB-04 | F4 | F4-AC3 (bucket totals = outstanding exactly) | unit, integration |
| CB-05 | F2 | F2-AC2 (`null` = «sin límite»), F2-AC3 (limit change alters no entry) | integration |
| CB-06 | F4, F2 | F4-AC1 (45-day auto-suspension, no human action), F2-AC5 (`limite_superado`), F4-AC2 (cause reported) | unit, integration |
| CB-07 | F2, F4 | F2-AC1 (422 naming the limit, no row), F4-AC2 (refused, no entry) | integration |
| CB-08 | F4 | F4-AC4 (override → `activo`, who + when) | integration |
| CB-09 | F3 | F3-AC5 (the write API does not accept `occurred_at`; the server stamps it) | integration |
| CB-10 | F2 | F2 (data minimisation), SEC-3 | integration |
| CB-11 | F3, F4 | PURE-1 (`allocate_payments`, `bucket_of`, `evaluate_customer`) | unit |
| CB-12 | F4 | F4-AC4 (audit trail fields), D8 | integration |

### `cash-position` — 6 requirements, 10 scenarios

| Req | Feature | Acceptance criterion | Verification |
|---|---|---|---|
| CP-01 | F5 | Matrix #1 (cash movements, both roles) | integration |
| CP-02 | F5 | F5-AC2 (`caja` derived), D2 (a `pago` raises `caja`) | unit, integration |
| CP-03 | F5 | F5-AC2 (`posicion_real` = `caja` + Σ), F5-AC1 (corrected — see §3), D1, D3 | unit, integration |
| CP-04 | F5 | F5-AC3 (`desviacion` −4,35 € stored), F5-AC4 (date uniqueness) | integration |
| CP-05 | F5 | Matrix #2 (close for both roles; close endpoint returns only `esperado`/`contado`/`desviacion`) | integration |
| CP-06 | F5 | PURE-1 (`real_position`) | unit |

### `role-access-control` — 9 requirements, 12 scenarios

| Req | Feature | Acceptance criterion | Verification |
|---|---|---|---|
| RAC-01 | F1 | F1 (2 × 9 matrix enforced server-side), D11 | integration |
| RAC-02 | F1 | F1-AC1 (403 on the credit book), F1-AC3 (owner reads it), D11 | integration |
| RAC-03 | F1 | F1-AC2 (no alias, id, name, balance or ageing in any JSON path) | integration |
| RAC-04 | F1 | F1-AC4 (unauthenticated → 401/403, no rows) | integration |
| RAC-05 | F1 | SEC-1 (session + CSRF on every mutation) | integration |
| RAC-06 | F1 | SEC-2 (PBKDF2, 1 000 000 iterations) | integration |
| RAC-07 | F1 | SEC-5 (parameterised ORM), SEC-6 (template autoescaping) | integration, e2e |
| RAC-08 | F1 | DG-1 (`DEBUG=False`), DG-5 (no secrets in repo or history), DG-6 (pinned versions), DG-7 (env `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS`) | e2e |
| RAC-09 | F1 | DG-4 (one test account per role) | integration, e2e |

### `position-board` — 7 requirements, 8 scenarios

| Req | Feature | Acceptance criterion | Verification |
|---|---|---|---|
| PB-01 | board | Proposal §Vista React (four elements, no tables), D4 (seed figures), D5 (gap = `fiado pendiente`) | e2e |
| PB-02 | board | DG-8 (React view consuming the app's own API at the public URL) | e2e |
| PB-03 | board, F5 | F5-AC1 (corrected — see §3), D3 (ladder and drawer change, `Posición real` does not) | e2e |
| PB-04 | board | DG-2 (public HTTPS URL) | e2e |
| PB-05 | board | DG-3 (idempotent seed, dates relative to the run date) | integration, e2e |
| PB-06 | F1 | F1-AC2 (no credit-book data in the board) | e2e |
| PB-07 | board | D10 (keep-alive ≤ 10 min, documented manual wake-up) | e2e |

---

## 2. Counts

| Capability | Requirements | Scenarios | unit | integration | e2e |
|---|---|---|---|---|---|
| `credit-book` | 12 | 17 | 5 | 11 | 0 |
| `cash-position` | 6 | 10 | 3 | 6 | 0 |
| `role-access-control` | 9 | 12 | 0 | 7 | 4 |
| `position-board` | 7 | 8 | 0 | 1 | 6 |
| **Total** | **34** | **47** | 8 | 25 | 10 |

(A requirement may carry more than one verification level; the columns count requirements whose declared level includes that level.)

---

## 3. Corrected readings of the acceptance criteria (D1–D11)

| Decision | Where it lands | What changed for the acceptance criteria |
|---|---|---|
| D1 — `posicion_real` is additive | CP-03, PB-01, PB-03 | F5-AC2 is now literally `caja + Σ outstanding`. The subtractive reading is removed. |
| D2 — a `pago` raises `caja` | CP-02 | `caja` = `opening_cash + Σ(entradas) − Σ(salidas) + Σ(pagos)`. A payment is never double-counted as a `CashMovement`. |
| D3 — a payment converts money | CP-03, CB-06, PB-03 | **F5-AC1 is corrected**: the `posicion_real` does NOT change when a `pago` is recorded. The observable changes are `caja` +30,00, `fiado pendiente` −30,00, the ladder band and the status chip. The canonical scenario (20,00 € 45-day `cargo` + 10,00 € 10-day `cargo`, `pago` of 20,00 €) is specified in CP-03. |
| D4 — seed figures | CP-03, CP-04, PB-01 | `caja` 412,35 · `fiado pendiente` 268,90 · `posicion_real` 681,25 · `desviacion` −4,35. The former subtractive seed total (the drawer minus the `fiado pendiente`) is removed from every artifact in this set. |
| D5 — two-series chart | PB-01 | Series 1 = `Caja`; series 2 = `Posición real`; the gap = `fiado pendiente`. |
| D6 — ageing per charge | CB-04 | Buckets by each `cargo`'s own age; `antiguedad_max_dias` is a separate metric driving suspension and ladder order. |
| D7 — `suspended_reason` values | CB-06, CB-12 | `limite_superado` · `antiguedad_superada`. |
| D8 — audit fields | CB-12 (new) | `Customer` carries `suspended_at`, `suspended_reason`, `suspended_by`, `suspended_override_at`, `suspended_override_by`. No new entity; the ledger stays append-only. |
| D9 — HTTP 422 | CB-07, CB-09 | Credit-operation validation failures answer 422, not DRF's default 400. |
| D10 — availability | PB-07 (new) | Keep-alive every ≤ 10 minutes + a documented manual wake-up before the defense. |
| D11 — queryset scoping | RAC-01, RAC-02 | No owner FK exists: scoping is by `Shop` + role. |

---

## 4. New requirement IDs added in this pass

| ID | Capability | Why it is new |
|---|---|---|
| `CB-12` | `credit-book` | D8 — the `Customer` suspension-audit fields. Closes the data-model gap that CB-08 previously flagged without adding an entity. |
| `PB-07` | `position-board` | D10 — the deployed board's availability during the review period and the defense. |

No existing requirement ID was renumbered, renamed or removed: `CB-01 … CB-11`, `CP-01 … CP-06`, `RAC-01 … RAC-09` and `PB-01 … PB-06` keep their identifiers and their behaviour.
