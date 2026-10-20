# Exploration Record — `tienda-barrio`

**Project:** `final` (PFM — Proyecto Final de Máster)
**Change slug:** `tienda-barrio`
**Phase:** SDD explore → propose
**Date:** 2026-10-19
**Artifact store:** OpenSpec (`openspec/`) + Engram mirror (project `final`)

> This file is the **index and decision trail** for the change. It is the internal engineering record, not a document handed to the teaching team. The team-facing artifact is `proposal.md` (Spanish).

---

## 1. Source explorations

| Source | Location | What it contains |
| --- | --- | --- |
| Generic candidate set | [`openspec/explorations/project-selection.md`](../../explorations/project-selection.md) | Five ranked PFM candidates (`hubdesk` 8.15, `huertacomun` 7.85, `tallerflow` 7.60, `ligabarrial` 7.20, `refugiomatch` 7.00), the verified platform facts (Render, Neon, Django 5.2 on Python 3.14) and the scoring weights reused by the domain exploration. |
| Domain exploration | [`openspec/explorations/tienda-barrio-domain.md`](../../explorations/tienda-barrio-domain.md) | The shop operating reality (Part A), the three domain variants (Part B), the scoring and recommendation (Part C), the week-1 evidence plan with the verbatim Spanish interview script (Part D), the filled one-page proposal skeleton (Part E), the deployment spine and `seed_demo` spec (Part F), and the risk register (Part G). |

**Engram references:** #113 `pfm/requirements-brief` (delivery-guide constraints, memoria §3.1–§3.8 list, gating process), #117 `sdd/pfm-selection/explore` (first ranked set), #119 `sdd/tienda-barrio/explore` (domain exploration), #120 `pfm/project-decision` (approved variant).

---

## 2. Decision trail

| Step | Decision | Outcome |
| --- | --- | --- |
| 1 | Five **generic** PFM candidates were explored and scored against the rubric weights (25 % need / 20 % scope fit / 15 % technical risk / 15 % deployability / 15 % defense / 10 % distinctiveness). | `hubdesk` led at 8.15, `huertacomun` second at 7.85. |
| 2 | The student **redirected the domain**: the base project must be an application for neighbourhood shops (*tiendas de barrio*). The pain point was delegated back to the exploration to be chosen "by the rubric". | Domain locked to the neighbourhood shop. `hubdesk` and the rest of the generic set were dropped. |
| 3 | A second, focused exploration profiled the shop, mapped nine pains and checked each against "does a generic POS already solve it?". | Nine pains; none solved by a generic POS. Three structural constraints emerged: the shop will not adopt extra manual discipline, the shop does not know its cost (so it cannot know its profit), and the owner is the asset and will not be replaced. |
| 4 | Three **domain** variants were built and scored with the same weights. | `fiado` **8.15**, `margen` 7.70, `mermas` 6.55. |
| 5 | The student **approved `fiado`** — "La libreta y la caja": a credit book and a real cash position for a neighbourhood shop. | Base project locked. `margen` retained as the **runner-up** and as the declared fallback if the evidence gate fires. |

### Why `fiado` won and `margen` lost

`fiado` is the only variant strong simultaneously on the two heaviest criteria: a pain the owner **feels every day** with money and social friction at stake (need 8), and a scope that fits 2–3 months solo — five entities, five features, one pure-function core, no extra infrastructure (scope 8, deployability 9).

`margen` is the **safer** build (best technical-risk score at 8/10, smallest entity count, most memorable visual — the 2×2 board). It loses on need strength for three concrete reasons:

1. **The pain is less felt.** "I don't know what makes money" is a question an owner is never asked and does not notice; "who owes me, how much, and for how long" is asked constantly and usually cannot be answered.
2. **It depends on a behaviour the shop does not have.** Every `margen` number requires that every delivery is recorded with its real cost. Miss one delivery and the revalued cost, margin, quadrant and reorder proposal are all silently wrong. `fiado` has no such dependency: the ledger is written *by* the very act the system records.
3. **Its distinctiveness is a presentation distinction, not a mechanism distinction.** The quadrant map is a familiar BI pattern; the ageing + credit line + auto-suspension + net-exposure model has no POS analogue.

`mermas` (6.55) was the weakest: the only variant whose core pain the owner **cannot feel**, plus the widest scope for the least rubric payoff, and it demands the one action a barrio owner will not adopt (counting stock).

---

## 3. Why the point of sale is out of scope

The point of sale is **deliberately excluded**, and that exclusion is the structural defence against the "products + sales + dashboard = acceptable" trap — the most common PFM archetype in the cohort.

- A POS's domain is *what was sold*. `fiado`'s subject is the shop's **money**: what has been given away, how old it is, whether it can grow, and what the owner's real liquidity is.
- Including `Product` and `Sale` tables would move the project into the POS category, where the ageing, the credit line, the automatic suspension and the net cash exposure simply do not exist.
- Serving at the till is well served by cheap tools and is **not** the shop's binding constraint. The binding constraint is the owner's memory and the owner's absence.
- The nearest incumbent is a **paper notebook**, and the notebook has exactly three defects — no ageing, no limit, no rule. That is the comparison the defense panel can verify in their own head.

Point of sale, products, prices, receipts, barcode, customer portal, online payments, debt collection, fiscal invoicing, supplier purchasing, multi-branch, uploads, e-mail/SMS and native mobile are therefore **explicit non-goals**.

---

## 4. Artifacts produced by this change

| Artifact | Path | Language | Audience |
| --- | --- | --- | --- |
| One-page proposal | `openspec/changes/tienda-barrio/proposal.md` | Spanish | Teaching team |
| Acceptance-criteria appendix | `openspec/changes/tienda-barrio/acceptance-criteria.md` | Spanish | Internal / panel prep |
| Evidence-annex template | `openspec/changes/tienda-barrio/evidence-annex.md` | Spanish | Student (to be filled with real interviews) |
| Exploration record | `openspec/changes/tienda-barrio/exploration.md` | English | Internal engineering |

**Engram mirror:** `sdd/tienda-barrio/proposal` (project `final`, scope `project`).

---

## 5. Open item carried forward

The week-1 interviews (three shop owners, six-question script) are an **evidence gate**, not decoration. They must be completed and the annex filled **before** the proposal goes to the teaching team. If they show that credit is not a real practice, the project switches to `margen` **before any code is written**. If the owner refuses to write anything down, the MVP shrinks to a single-tap charge record.

See `evidence-annex.md` for the script, the capture fields, the recruitment tracker and the decision checklist.
