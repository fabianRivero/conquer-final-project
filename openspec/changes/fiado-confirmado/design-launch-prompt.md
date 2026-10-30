# Launch prompt — `sdd-design` para `fiado-confirmado`

> **Qué es este fichero.** El prompt exacto, listo para pegar, que lanza la fase `sdd-design`
> de este cambio. Existe porque el primer intento de la fase falló (`sdd_task_result_empty`)
> y el runtime latchea la fase para el resto de esa sesión. En una sesión nueva, el
> dispatcher despacha `sdd-design` con normalidad si se le da este prompt.
>
> **Por qué el prompt es diferente del primero.** El primer intento exigía leer doce
> artefactos (~220 KB, incluidos los 95 KB del diseño anterior en crudo) y luego emitir un
> diseño de 45 KB en una sola llamada. El segundo intento ya usaba los dos digests
> (~120 KB) y escribía por trozos de ~10 KB, y **murió igual**: los dos intentos terminan
> con `step-finish reason: "length"`, `reasoning=31999`, `output=1`. El modelo gasta sus
> 32.000 tokens de razonamiento antes de emitir un solo token visible y la generación
> aborta. El recorte de entrada y el troceado de salida **no** son la causa ni el arreglo.
>
> **Qué hace este prompt.** Elimina la derivación y reparte el peso:
> 1. `requirement-index.md` (5,8 KB, derivado por script de las 8 specs) ya lista los 53
>    requisitos con su ID, título, nivel de verificación y marca de condicional. El modelo
>    copia; no cuenta ni deduce nada.
> 2. **Una sección por turno de generación.** El primer turno escribe solo la sección
>    1. Nada de diseñar 19 secciones en un mismo turno.
> 3. El modelo de la fase debe tener asignado `agent.sdd-design.model`. Sin esa
>    asignación la fase hereda `minimax-coding-plan/MiniMax-M3.1-Flash`, que es
>    exactamente el presupuesto de razonamiento que se agotó.
>
> **Cómo usarlo.** En la sesión nueva, pide al orquestador que lance `sdd-design` con el
> contenido del bloque de abajo. El orquestador debe leer `state.yaml` antes de nada.

---

## Prompt para el agente `sdd-design`

```
You are the SDD design executor for the change `fiado-confirmado`. Do the phase work
yourself. Do NOT launch sub-agents and do NOT call task/delegate. Write NO code and NO
implementation artifacts — `design.md` is a design document, not code.

A previous attempt at this phase died twice, both times identically: the generation was
terminated with finish reason `length` at `reasoning=31999` tokens and `output=1` — the
model spent its whole reasoning budget before emitting a single visible token, and the
abort happened on the very first generation turn, before any write call existed.

Three mitigations are in force and are NOT optional. They are grounded in the proven
cause, not in guesswork:

1. **Do not derive.** `requirement-index.md` already lists all 53 requirements.
2. **One section per generation turn.** Never design 19 sections in one turn.
3. **Run on the assigned model.** `agent.sdd-design.model` is set to
   `minimax-coding-plan/MiniMax-M3` in the global `opencode.jsonc`. Verify it with
   `opencode debug config` before launching. Without it the phase inherits
   `minimax-coding-plan/MiniMax-M3.1-Flash`, whose 32,000-token reasoning budget is
   exactly what both failed attempts exhausted.

Follow all three exactly.

## Skills to load before work

- `C:\Users\Desktop\.config\opencode\skills\sdd-design\SKILL.md`
- `C:\Users\Desktop\.config\opencode\skills\sdd-design\references\threat-matrix.md`
- `C:\Users\Desktop\.config\opencode\skills\_shared\sdd-phase-common.md`

## Artifact store

`openspec` (resolved by the native dispatcher; do not re-detect it), with an Engram mirror.

## Read — this bounded set only

1. `C:\proyectos\final\openspec\changes\fiado-confirmado\requirement-index.md` — **read this
   FIRST and read it fully.** It is the machine-derived index of all 53 requirements: ID,
   title, verification level, scenario count and conditional marker. It is the single
   source of truth for the traceability matrix. **Never re-count, never re-enumerate, never
   re-derive the requirement set in your reasoning.** Copy from this file.
2. `C:\proyectos\final\openspec\changes\fiado-confirmado\legacy-design-digest.md` — a
   condensed digest of the previous design: its section structure, its 15 ADRs, the data
   model, the security architecture, the landmine list, the pure-rules module, the API
   routes, the deployment spine, and a per-ADR verdict of what still holds, what is amended
   and what the new scope breaks. **Read it fully. Do NOT open the original
   `tienda-barrio\design.md`.**
3. `C:\proyectos\final\openspec\changes\fiado-confirmado\decisions-digest.md` — a condensed
   digest of the exploration: the owner's decisions, D1–D10, the T1–T7 resolutions with their
   constraints and rejected alternatives, the seven capabilities plus the conditional eighth,
   the out-of-scope list, the C1–C14 / A1–A9 inheritance map, the twelve open items, the
   interview decision rules and the scoring. **Read it fully. Do NOT open the original
   `exploration.md` or `evidence-annex.md`.**
4. The eight specs — read all of them, they are the contract. Read them for the requirement
   TEXT and the scenarios; the ID and title come from `requirement-index.md`.
   `...\fiado-confirmado\specs\cash-position\spec.md`, `payments-and-ageing`,
   `itemised-charges`, `client-accounts-and-credentials`, `product-catalogue`,
   `client-confirmation`, `dispute-resolution`, `confirmation-facilitation` — all under
   `C:\proyectos\final\openspec\changes\fiado-confirmado\specs\`.
5. `C:\proyectos\final\openspec\changes\fiado-confirmado\proposal.md` — read only these
   sections: "Alcance mínimo", "Entidades de datos", "El precio del alcance" and the
   "No negociables" line. **Skip the rest.**

That is the entire input. Roughly 120 KB. Do not open anything else.

## Write — ONE SECTION PER GENERATION TURN

This is the mitigation that matters. The previous failure was a reasoning-budget abort on
the FIRST turn, before any write call existed, so the document's total size never mattered.

- The design has the 19 sections listed under "What the design must contain" below, in that
  order.
- **Each generation turn writes exactly ONE section** and nothing else. Turn 1 writes
  section 1 only. Turn 2 writes section 2 only. And so on.
- The first turn appends with Write (creating `design.draft.md`); every later turn appends
  with Edit. **Never emit more than about 8 KB of text in a single tool call.**
- Your reasoning in a turn is limited to the section you are writing in that turn. Do NOT
  plan the whole document in advance. Do NOT enumerate requirement IDs in your reasoning —
  open `requirement-index.md` and copy the row you need.
- Your previous attempt died on turn 1 for exactly this reason: it spent 32,000 tokens
  planning the entire design before writing a single byte, and the generation was aborted
  with `reason: "length"`. If you catch yourself enumerating requirements or designing
  sections you have not reached yet, stop and write the section in front of you.
- The traceability matrix is a lookup, not a derivation: for each of the 53 rows in
  `requirement-index.md`, copy the ID and the title and name the design element that
  satisfies it. All 53, each exactly once.
- When the last section is written and you have re-read the file once to check it, rename it
  with `Move-Item -LiteralPath "C:\proyectos\final\openspec\changes\fiado-confirmado\design.draft.md"
  -Destination "C:\proyectos\final\openspec\changes\fiado-confirmado\design.md"`. **Only the
  renamed file counts.** A draft left behind means the design is incomplete and the change
  stays routed to `design`.
- Then mirror to Engram: `mem_save(title: "sdd/fiado-confirmado/design", topic_key:
  "sdd/fiado-confirmado/design", type: "architecture", project: "final", capture_prompt:
  false, content: <the final design markdown>)`. Engram caps one observation at 50,000 bytes;
  keep the design under that so it is one observation.
- **Target 26,000–34,000 bytes.** The previous design was 95 KB and that is not the target —
  the house structure and discipline are, the volume is not. Tables and diagrams, not prose.
  If you find yourself above 34,000 bytes, compress rather than continue.

## Your final text response must be COMPACT

Your final message is an envelope, **not** the design. At most about 40 lines: `status`,
`executive_summary`, `artifacts`, `next_recommended`, `risks`, `skill_resolution`, the byte
size, the ADR count, the file count, the traceability coverage out of 53, and the
`## Key Learnings` section. **Never repeat the design body inline.** Your final output MUST
be text, not a tool call — persist to Engram BEFORE it.

## What the design must contain

Follow the section structure of the legacy digest §1. It must carry:

1. **Technical approach** and the three ideas it hangs on.
2. **The ten decisions you must make**, each with choice, rejected alternatives and rationale:
   1. `Customer.status` — stored column or derived on read? The proposal's entity table lists
      it as a column; the specs derive the suspension status on read and store only the override.
   2. The client credential's **storage** — plaintext or hashed? State the operational
      consequence for the owner printing, re-printing and rotating a slip.
   3. Its **transport** — which HTTP mechanism carries it, why a query parameter is wrong, and
      how the client surface satisfies CSRF given it has no session.
   4. Its **entropy and brute-force defence** — length, alphabet, entropy, and a throttle
      implemented WITHOUT a new infrastructure dependency (no Redis, no Celery).
   5. The **stock movement model** — what an `entrada` is, given that suppliers, purchase
      costs and cash sales are all out of scope; state precisely how the ceiling drifts and
      who bears it.
   6. The **facilitator's leak boundary** — what the `dependiente` renders, including whether
      it sees the itemisation of the charge being presented.
   7. How "already confirmed" and "reconciled at most once" are enforced — constraint,
      transactional check, or both.
   8. The **`precio` deviation rule** — how the owner charges a different amount without extra
      friction.
   9. The **7-day escalation flag** — derived on read, no background worker.
   10. Whether the client sees **their own `credit_limit`**.
3. **Data model** — every entity, fields, relations, per-row DB constraints, transactional
   cross-row checks, and what is explicitly NOT stored.
4. **ADRs** — numbered, in the previous design's shape: context, choice, trade-off, consequence.
   Use a table when it compresses better.
5. **The client credential** — its own section: entropy, storage, transport, throttling,
   rotation, leak surface, and the RED tests that prove it does not leak.
6. **The confirmation state machine** — states, transitions, who drives each, and which
   transition is refused with which error code.
7. **The permission matrix** — three columns: `dueño`, `dependiente`, `cliente`; the
   `dependiente`'s 403 boundary and the client scope as structural properties.
8. **The scope mechanisms** — the staff scope (session) and the client scope (credential),
   each with exactly one source, and the invariant that keeps them apart.
9. **API contracts** — routes, payload shapes, error codes, the serializer allowlist per audience.
10. **The pure rules module** — functions, signatures, inputs, outputs, and the guarantee that
    they touch no ORM.
11. **The two React surfaces** — routes, credential modes, the same-origin contract, the board's
    content.
12. **Security architecture** — the landmine list, including the new one: a `codigo` leaking
    through a staff payload is a data-protection failure, not a cosmetic bug.
13. **Data flow** — ASCII sequence diagrams for the confirmation flow, the dispute flow and the
    facilitator flow.
14. **File changes** — the concrete table of files to create, with real paths.
15. **Testing strategy** — mapped to the `**Verification:**` levels the specs declare
    (unit / integration / e2e).
16. **Requirement → design traceability matrix** — **all 53 requirements** mapped to the design
    element that satisfies each. A requirement with no design home is a defect in the design.
    This is hard-required. Build it from `requirement-index.md`: every one of its 53 rows
    becomes exactly one matrix row, with the ID and title copied verbatim from the index.
17. **Threat matrix** — apply `references/threat-matrix.md`; mark every row `Applicable` or
    explicit `N/A` with a reason. Do not manufacture irrelevant rows.
18. **Migration / rollout** — the deployment spine, the seed plan extension, and that this is
    all new creation.
19. **Open questions** — anything genuinely unresolved, with what would settle it.

## Constraints

- Prose in English. Every domain identifier, entity name, field name, API field and diagram
  label in the project's Spanish vocabulary (`fiado`, `cargo`, `pago`, `nota de crédito`, `caja`,
  `dependiente`, `dueño`, `libreta`, `posición real`, `confirmación`, `disputa`,
  `existencias_registradas`, `codigo`, `Producto`, `CargoLinea`, `Confirmacion`, `LedgerEntry`,
  `CashMovement`, `DayClose`, `Customer`, `Shop`, `antiguedad_max_dias`, `suspended_reason`,
  `vigente`/`envejecido`/`viejo`/`cronico`, `importe_reclamado`, `facilitado_por`,
  `confirmado_en`, `precio_unitario`, `credit_limit`, `posicion_real`). **Never translate an
  identifier into English.**
- Do NOT write `tasks.md`. Do not implement anything. No code files.
- Do NOT modify, move or delete anything under `openspec\changes\tienda-barrio\` or
  `openspec\explorations\`.
- Do NOT write to `openspec\specs\`.
- Do NOT launch sub-agents.
```

---

## Qué esperar al terminar

| Comprobación | Valor esperado |
| --- | --- |
| `design.md` existe | sí, y `design.draft.md` **no** (se renombró) |
| Tamaño de `design.md` | 26.000–34.000 bytes |
| Trazabilidad | 53 de 53 requisitos mapeados, copiados de `requirement-index.md` |
| Bloques `## Conditional Requirements` | los 19 requisitos condicionados, con su marcador `**Conditional:**` intacto |
| Espejo Engram | `sdd/fiado-confirmado/design`, una sola observación |
| Dispatcher | `nextRecommended: tasks` |

> **Antes de lanzar, comprueba el modelo.** `agent.sdd-design.model` debe ser
> `minimax-coding-plan/MiniMax-M3` en `opencode.jsonc` (global). Si no lo está, la fase
> hereda `minimax-coding-plan/MiniMax-M3.1-Flash` y vuelve a morir con
> `reason: "length"`. Es el mismo fallo, no uno nuevo: no lo reintentes sin cambiar el
> modelo. Ojo: la config **no se recarga en caliente** — hay que cerrar y reabrir opencode.

Si la fase vuelve a fallar, el fallo será de otra naturaleza y estará en el log del runtime
(`C:\Users\Desktop\.local\share\opencode\log\opencode.log`, líneas `message=loop
session.id=… step=N` y `message="exiting loop"`). Ese log dice exactamente en qué paso murió
el hijo.
