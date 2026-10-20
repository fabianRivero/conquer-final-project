# Skill Registry — project `final`

> **This file is an index, not a summary.** Every `SKILL.md` listed below remains the
> source of truth. Delegators must pass the exact `SKILL.md` path to sub-agents —
> never a paraphrase of the skill.

## Registry Contract

- **Resolution order**: session cache → Engram (`mem_search(query: "skill-registry", project: "final")`) → this file → stop and warn.
- **Selection**: match on code/file context first, then task/action context. Prefer the smallest useful set; keep at most five when more than five match.
- **Injection**: pass exact absolute paths. The sub-agent MUST read those files before task-specific work.
- **Reporting**: sub-agents report `skill_resolution` — `paths-injected`, `fallback-registry`, `fallback-path`, or `none`. Anything other than `paths-injected` forces the delegator to re-read this registry before the next delegation.
- **Refresh**: run `gentle-ai skill-registry refresh` after installing, removing, creating, moving, or renaming any skill.
- **Canonical copy**: `openspec/skill-registry.md` (versioned). `.atl/skill-registry.md` is the local resolver cache (git-ignored).

## Scanned Sources

### User / global skill roots

| Root | Exists | `SKILL.md` skills | Resolution |
| --- | --- | --- | --- |
| `C:\Users\Desktop\.pi\agent\skills` | no | 0 | — |
| `C:\Users\Desktop\.config\agents\skills` | no | 0 | — |
| `C:\Users\Desktop\.agents\skills` | no | 0 | — |
| `C:\Users\Desktop\.kimi\skills` | no | 0 | —| 
| **`C:\Users\Desktop\.config\opencode\skills`** | **yes** | **25** | **SELECTED — first in scan order** |
| `C:\Users\Desktop\.config\kilo\skills` | no | 0 | — |
| `C:\Users\Desktop\.claude\skills` | yes | 25 | duplicate — skipped (same names, later in scan order) |
| `C:\Users\Desktop\.gemini\skills` | yes | 25 | duplicate — skipped (same names, later in scan order) |
| `C:\Users\Desktop\.gemini\antigravity\skills` | no | 0 | — |
| `C:\Users\Desktop\.cursor\skills` | no | 0 | — |
| `C:\Users\Desktop\.copilot\skills` | yes | 25 | duplicate — skipped (same names, later in scan order) |
| `C:\Users\Desktop\.codex\skills` | yes | 0 | — |
| `C:\Users\Desktop\.codeium\windsurf\skills` | no | 0 | — |
| `C:\Users\Desktop\.qwen\skills` | no | 0 | — |
| `C:\Users\Desktop\.kiro\skills` | no | 0 | — |
| `C:\Users\Desktop\.openclaw\skills` | no | 0 | — |

### Project skill roots

All 14 project-level roots (`skills/`, `.opencode/skills/`, `.claude/skills/`, `.gemini/skills/`, `.cursor/skills/`, `.github/skills/`, `.codex/skills/`, `.qwen/skills/`, `.kiro/skills/`, `.openclaw/skills/`, `.pi/skills/`, `.agent/skills/`, `.agents/skills/`, `.atl/skills/`) were scanned under `C:\proyectos\final`.

**Result**: none exist. The repository is empty (only `.git`), so there are **no project-level skills**.

### Project convention files

`agents.md`, `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `GEMINI.md`, `copilot-instructions.md` were checked under `C:\proyectos\final`.

**Result**: none exist. The global `C:\Users\Desktop\.config\opencode\AGENTS.md` is a user-level runtime instruction file, not a project artifact.

### Skipped entries

- `_shared` — holds shared contracts (`openspec-convention.md`, `engram-convention.md`, `persistence-contract.md`, `skill-resolver.md`, …) and contains **no** `SKILL.md`. Not indexed as a skill.
- `sdd-*` and `skill-registry` are **deliberately indexed** here, overriding the skill-registry skill's default skip rule: the SDD orchestrator must be able to resolve phase sub-agent skill paths from this index.

---

## Indexed Skills (26)

Scope legend: `global` = user-level skill directory · `built-in` = provided by the opencode runtime, no file on disk.

| # | Skill | Trigger / description | Scope | Path |
| - | ----- | ---------------------- | ----- | ---- |
| 1 | `branch-pr` | Create Gentle AI pull requests with issue-first checks. Trigger: creating, opening, or preparing PRs for review. | global | `C:\Users\Desktop\.config\opencode\skills\branch-pr\SKILL.md` |
| 2 | `chained-pr` | Trigger: PRs over 400 lines, stacked PRs, review slices. Split oversized changes into chained PRs that protect review focus. | global | `C:\Users\Desktop\.config\opencode\skills\chained-pr\SKILL.md` |
| 3 | `cognitive-doc-design` | Design docs that reduce cognitive load. Trigger: writing guides, READMEs, RFCs, onboarding, architecture, or review-facing docs. | global | `C:\Users\Desktop\.config\opencode\skills\cognitive-doc-design\SKILL.md` |
| 4 | `comment-writer` | Write warm, direct collaboration comments. Trigger: PR feedback, issue replies, reviews, Slack messages, or GitHub comments. | global | `C:\Users\Desktop\.config\opencode\skills\comment-writer\SKILL.md` |
| 5 | `customize-opencode` | Use ONLY when the user is editing or creating opencode's own configuration: opencode.json, opencode.jsonc, files under .opencode/, or files under ~/.config/opencode/. Also use when creating or fixing opencode agents, subagents, skills, plugins, MCP servers, or permission rules. Do not use for the user's own application code, or for any project that is not configuring opencode itself. | built-in | `<built-in>` — runtime-provided; **no `SKILL.md` file exists on disk** |
| 6 | `gentle-ai-bench` | Trigger: bench, journey, journeys, driven mode, gentle-ai-bench, journey corpus, j-numbers, bench axis. Author and verify gentle-ai bench journeys; go test ./bench never proves driven execution. | global | `C:\Users\Desktop\.config\opencode\skills\gentle-ai-bench\SKILL.md` |
| 7 | `go-testing` | Trigger: Go tests, go test coverage, Bubbletea teatest, golden files. Apply focused Go testing patterns. | global | `C:\Users\Desktop\.config\opencode\skills\go-testing\SKILL.md` |
| 8 | `issue-creation` | Trigger: issue creation, bug reports, feature requests, or issue approval. Create and triage GitHub issues from repository evidence. | global | `C:\Users\Desktop\.config\opencode\skills\issue-creation\SKILL.md` |
| 9 | `judgment-day` | Trigger: judgment day, dual review, adversarial review, juzgar. Run explicit blind dual review with at most two scoped fix/re-judgment rounds. | global | `C:\Users\Desktop\.config\opencode\skills\judgment-day\SKILL.md` |
| 10 | `rdd-defect-workflow` | Trigger: RDD, receipt-driven development, review authority, receipt/lineage, correction/recovery, delivery gate/kill switch, bounded review defects. Guide work. | global | `C:\Users\Desktop\.config\opencode\skills\rdd-defect-workflow\SKILL.md` |
| 11 | `sdd-apply` | Implement SDD tasks from specs and design. Trigger: orchestrator launches apply for one or more change tasks. | global | `C:\Users\Desktop\.config\opencode\skills\sdd-apply\SKILL.md` |
| 12 | `sdd-archive` | Archive a completed SDD change by syncing delta specs. Trigger: orchestrator launches archive after implementation and verification. | global | `C:\Users\Desktop\.config\opencode\skills\sdd-archive\SKILL.md` |
| 13 | `sdd-design` | Create the SDD technical design and architecture approach. Trigger: orchestrator launches design for a change. | global | `C:\Users\Desktop\.config\opencode\skills\sdd-design\SKILL.md` |
| 14 | `sdd-explore` | Explore SDD ideas before committing to a change. Trigger: orchestrator launches exploration or requirement clarification. | global | `C:\Users\Desktop\.config\opencode\skills\sdd-explore\SKILL.md` |
| 15 | `sdd-init` | Trigger: sdd init, iniciar sdd, openspec init. Initialize SDD context, testing capabilities, registry, and persistence. | global | `C:\Users\Desktop\.config\opencode\skills\sdd-init\SKILL.md` |
| 16 | `sdd-onboard` | Walk users through the SDD workflow on the real codebase. Trigger: orchestrator launches onboarding for the full SDD cycle. | global | `C:\Users\Desktop\.config\opencode\skills\sdd-onboard\SKILL.md` |
| 17 | `sdd-propose` | Create an SDD change proposal with intent, scope, and approach. Trigger: orchestrator launches proposal work for a change. | global | `C:\Users\Desktop\.config\opencode\skills\sdd-propose\SKILL.md` |
| 18 | `sdd-research` | Trigger: SDD research, external evidence, source-backed research. Produce auditable evidence for a selected research lane. | global | `C:\Users\Desktop\.config\opencode\skills\sdd-research\SKILL.md` |
| 19 | `sdd-spec` | Write SDD delta specs with requirements and scenarios. Trigger: orchestrator launches spec work for a change. | global | `C:\Users\Desktop\.config\opencode\skills\sdd-spec\SKILL.md` |
| 20 | `sdd-tasks` | Break an SDD change into implementation tasks. Trigger: orchestrator launches task planning for a change. | global | `C:\Users\Desktop\.config\opencode\skills\sdd-tasks\SKILL.md` |
| 21 | `sdd-verify` | Trigger: SDD verification phase, verify change. Execute tests and prove implementation matches specs, design, and tasks. | global | `C:\Users\Desktop\.config\opencode\skills\sdd-verify\SKILL.md` |
| 22 | `skill-creator` | Trigger: new skills, agent instructions, documenting AI usage patterns. Create LLM-first skills with valid frontmatter. | global | `C:\Users\Desktop\.config\opencode\skills\skill-creator\SKILL.md` |
| 23 | `skill-improver` | Trigger: improve skills, audit skills, refactor skills, skill quality. Audit and upgrade existing LLM-first skills. | global | `C:\Users\Desktop\.config\opencode\skills\skill-improver\SKILL.md` |
| 24 | `skill-registry` | Trigger: update skills, skill registry, actualizar skills, after skill changes. Index available skills by trigger and path. | global | `C:\Users\Desktop\.config\opencode\skills\skill-registry\SKILL.md` |
| 25 | `systemic-issue-triage` | Trigger: new issue, bug report, triage, backlog, issue flood, community report, root cause, dead-end, blocked user. Attack issues by root class, never one-by-one; fixes must shrink the system, not grow it. | global | `C:\Users\Desktop\.config\opencode\skills\systemic-issue-triage\SKILL.md` |
| 26 | `work-unit-commits` | Plan commits as reviewable work units. Trigger: implementation, commit splitting, chained PRs, or keeping tests and docs with code. | global | `C:\Users\Desktop\.config\opencode\skills\work-unit-commits\SKILL.md` |

---

## Stack-Relevance Notes for Project `final`

Target stack: Django + PostgreSQL/SQLite + React + Git/GitHub + public deployment.

- `go-testing` is **not applicable** — the target stack contains no Go code.
- No Python-specific or React-specific skill is installed globally; `skill-creator` / `skill-improver` cover skill authoring only.
- `work-unit-commits`, `branch-pr`, `chained-pr`, and `issue-creation` apply directly to the Git/GitHub portion of the brief.
- `cognitive-doc-design` applies to any README/architecture documentation produced for the public deployment.
