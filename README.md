# Idea Survey Pipeline — Self-Contained Package

A **self-contained, portable** toolkit for AI-assisted research **idea validation** and **literature survey**, adapted for Kimi from [ARIS (Auto-Research-In-Sleep)](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep). Where ARIS targets **Claude Code**, this package is built for **Kimi CLI**, which is cheaper to run. It runs as a set of YAML-frontmatter *Skills* that orchestrate specialized *subagents*. The domain emphasis is theoretical / phenomenological physics — especially HEP × heavy-ion × deep-learning crossover — but the three `idea-*` survey skills work for general ML / LLM topics too.

Use this package to:

- **Map** a vague research inspiration onto the literature landscape (`idea-landscape`)
- **Verify** whether a concrete direction is novel, claim by claim (`idea-novelty`)
- **Assess** whether an idea is technically feasible before investing months (`idea-feasibility`)
- **Generate** a LaTeX research proposal from the completed survey (`research-proposal`)
- **Answer** a specific mid-project blocker fast and interactively (`research-debug`)
- **Deep-analyze** individual papers figure-by-figure, equation-by-equation (`research-lit`)
- **Derive** a target observable as an analytic function of a control parameter by symbolically chaining results across papers, SymPy-verified (`analytic-derivation`), then harden it through multi-reviewer adversarial rounds (`derivation-refine-loop`)

> **Built for Kimi CLI — invoke skills explicitly.** Kimi's keyword auto-triggering (the `description:` field in each `SKILL.md`) is unreliable. **Always call a skill by name with `/skill:<name>`.** The [Usage](#usage--every-invocation-in-one-place) section below is the single source of truth for every invocation and every argument; the rest of this README explains how things work internally and does not repeat invocation syntax.

---

## What's Inside

**8 Skills**, **17 Tools**, **14 Templates**, and **1 main-agent + 22 subagent role definitions**, all extracted from the main ARIS system.

The skills fall into three groups:

| Skill | Group | Purpose | Input |
|-------|-------|---------|-------|
| `idea-landscape` | survey (stage 1) | Decompose a fuzzy inspiration into hypotheses, search literature, identify technical routes and gaps | A vague idea or direction |
| `idea-novelty` | survey (stage 2) | Extract claims, search for competition, deep claim-by-claim novelty assessment | A concrete direction (often from stage 1) |
| `idea-feasibility` | survey (stage 3) | Evaluate key assumptions, find supporting / contradicting evidence, suggest an MVP experiment | A direction that passed the novelty check |
| `research-proposal` | survey (stage 4) | Read all three upstream reports as ground truth, emit a LaTeX proposal (10–20 pp) with embedded figures, equations, and a verified bibliography | A completed three-stage survey |
| `research-lit` | shared infra | Standalone deep paper analysis + literature search used by all stages | A paper topic, URL, or arXiv ID |
| `research-debug` | mid-project helper | **Interactive**, cheap-first in-progress query (L0 → L1 → L2). Reads `project-state.md` as ambient context. Tailored to HEP × DL | A specific in-progress question |
| `analytic-derivation` | derivation | Cross-paper symbolic derivation run by SymPy, with notation reconciliation, a three-tier assumption ladder, a lit-verifier pass, and an `hep-theory-reviewer` audit | A target observable + 2–8 anchor papers + endpoint declarations |
| `derivation-refine-loop` | derivation | Iterative multi-reviewer hardening of an existing derivation (rigor / physics / literature / adversarial), with the v2 axiom-explore pipeline | An existing `analytic-derivation/<run>/` directory |

### The survey pipeline (project start → proposal)

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  idea-landscape │ ──→ │   idea-novelty   │ ──→ │ idea-feasibility │ ──→ │ research-proposal│
└─────────────────┘     └──────────────────┘     └──────────────────┘     └──────────────────┘
   ↺ Step 4.6           ↺ Step 4.6              ↺ Step 4.6
   loop expansion       loop expansion          loop expansion
```

Each `idea-*` skill internally runs a one-shot **loop expansion** (Step 4.6) after round-1 deep reading: round-1 cards seed a second round of citation-graph + precise-term search, capped at `deep-analyze-max × expand-budget-factor` NEW papers. See [Loop Expansion](#loop-expansion-step-46).

### The mid-project helper

```
   (questions arising DURING ongoing research) ───→  research-debug  (quick in-progress lookup)
```

Unlike the four pipeline skills — which run for hours and target overnight execution — `research-debug` is **interactive** and targets minutes. It is for when you are mid-experiment, hit a blocker, and need a literature precedent or mechanism explanation NOW, without paying a 4-hour cost just to discover the AI misread your question.

### The derivation track

`analytic-derivation` produces a single-pass SymPy-verified derivation; `derivation-refine-loop` then hardens it across multiple adversarial rounds. The loop's **v2 axiom-explore pipeline** is the headline feature — see [Symbolic Derivation Track](#symbolic-derivation-track).

> **What's new — v2 of `derivation-refine-loop` (May 2026).** The refinement loop's "sacred" object was redefined from v1 "tier-1 user axioms" to v2 "causal-graph endpoints" (the *classes* of the control parameter and observable being related). When a reviewer flags a tier-1 bridging hypothesis as CRITICAL, the loop now dispatches an `axiom-explorer` to search the literature for alternatives, runs K parallel sister-derivations under each candidate, then a `sister-comparator` decides whether the main axiom is robust, surfaces the strongest alternative, or auto-promotes it. This fixes the v1 "converged with a known bug" failure mode. Full architecture and a worked case study live in `.kimi/skills/derivation-refine-loop/{SKILL.md,CASE_STUDY_spin_polarization.md}`.

---

## Directory Layout

```
.
├── README.md                          # This file
├── .kimi/
│   └── skills/                        # The 8 Skills (loaded by Kimi CLI) — canonical location
│       ├── idea-landscape/SKILL.md
│       ├── idea-novelty/SKILL.md
│       ├── idea-feasibility/SKILL.md
│       ├── research-proposal/SKILL.md
│       ├── research-lit/SKILL.md
│       ├── research-debug/SKILL.md
│       ├── analytic-derivation/SKILL.md
│       ├── derivation-refine-loop/
│       │   ├── SKILL.md
│       │   └── CASE_STUDY_spin_polarization.md
│       └── shared-references/         # Cross-skill docs (output-language, venue checklists, citation discipline, …)
├── agents/
│   ├── aris-kimi.md / aris-kimi.yaml  # Main executor agent; registers the custom subagents below
│   └── subagents/                     # 22 subagent role definitions (.md); 9 also ship a .yaml registration
│       ├── paper-analyzer.{md,yaml}         # Per-paper deep analysis worker
│       ├── paper-editor.{md,yaml}           # Generic editor / synthesizer
│       ├── novelty-checker.{md,yaml}        # Stage-2 competitive search
│       ├── experiment-auditor.{md,yaml}     # Empirical-claim auditor
│       ├── hep-reviewer.{md,yaml}           # HEP-experiment senior reviewer
│       ├── hep-theory-reviewer.{md,yaml}    # HEP-theory senior reviewer
│       ├── proof-reviewer.{md,yaml}         # Mathematical proof reviewer
│       ├── research-reviewer.{md,yaml}      # Research-design reviewer
│       ├── patent-examiner.{md,yaml}        # Patent-novelty examiner
│       ├── theory-synthesizer.md            # Symbolic derivation author
│       ├── theory-synthesizer-call-g.md     # Call G: revise-for-review
│       ├── theory-synthesizer-call-h.md     # Call H: merge per-round fixes
│       ├── theory-synthesizer-call-j.md     # Call J (v2): sister-derivation under alternative axioms
│       ├── derivation-reviewer.md           # Base reviewer role for the refine loop
│       ├── derivation-reviewer-{rigor,physics,literature,adversarial}.md
│       ├── refinement-router.md             # Aggregates reviewer outputs → routing decision
│       ├── lit-verifier.md                  # Single-shot literature verification
│       ├── axiom-explorer.md                # v2: literature-driven alternative-axiom generator
│       └── sister-comparator.md             # v2: cross-sister derivation comparator
├── tools/                             # 17 Python tools (see Tool Reference) + tools/tests/ self-test fixtures
└── templates/                         # 14 output templates (see Templates)
```

---

## Usage — Every Invocation in One Place

This is the single source of truth for how to run everything.

### Invocation syntax

```
/skill:<skill-name> "free-text argument"  — param1: value1  — param2: value2
```

- The quoted free-text argument becomes `$ARGUMENTS` (the idea, topic, question, or run directory).
- Override any parameter inline with the **em-dash** form `— param: value` (em-dash `—`, *not* hyphen `-`). Chain as many as you like.
- A few `research-lit` parameters use a comma-grouped form, e.g. `— deep analyze: true, max: 3, source: false`.
- **Always invoke explicitly.** Do not rely on Kimi keyword triggering — name the skill.

### Global parameter (all skills)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `language` | `zh` / `en` / `auto` | `auto` | Output language. `auto` detects from the user message or `CLAUDE.md`; `zh` forces Chinese; `en` forces English. Paper titles, venues, BibTeX, and file paths stay English regardless. Protocol: [`.kimi/skills/shared-references/output-language.md`](.kimi/skills/shared-references/output-language.md). |

### Pipeline at a glance

| Skill | Minimal call | Primary output |
|-------|--------------|----------------|
| `idea-landscape` | `/skill:idea-landscape "fuzzy idea"` | `idea-survey/landscape-report.md` |
| `idea-novelty` | `/skill:idea-novelty "concrete direction"` | `idea-survey/novelty-report.md` |
| `idea-feasibility` | `/skill:idea-feasibility "direction"` | `idea-survey/feasibility-report.md` |
| `research-proposal` | `/skill:research-proposal "title" — language: zh` | `proposal/main.tex` (+ `main.pdf`) |
| `research-lit` | `/skill:research-lit "topic or arXiv URL"` | `literature-deep/paper_*/` |
| `research-debug` | `/skill:research-debug "in-progress question"` | `research-debug/<slug>/report.md` |
| `analytic-derivation` | `/skill:analytic-derivation "derive X as f(p)"` | `analytic-derivation/<run>/derivation-report.md` |
| `derivation-refine-loop` | `/skill:derivation-refine-loop "analytic-derivation/<run>"` | `analytic-derivation/<run>/refine/refinement_audit.md` |

Stages 2–4 auto-load their upstream reports from `idea-survey/`, so run the survey stages in order. Two skills bootstrap a template file on first invocation and then stop (fill it in, re-invoke): `research-debug` writes `project-state.md`, and `analytic-derivation` writes `derivation-target.md`.

---

### `idea-landscape` — map the terrain

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `deep-analyze-max` | int | `6` | Max **NEW** papers to deep-analyze in **round 1**. Already-analyzed papers (prior runs / upstream stages) are reused for free and do not count. |
| `loop` | `true` / `false` | `true` | Run [Step 4.6 Loop Expansion](#loop-expansion-step-46) after round 1. |
| `expand-budget-factor` | int | `2` | Total NEW deep-analysis budget across both rounds = `deep-analyze-max × expand-budget-factor`. Defaults → ≤ 6 in round 1, ≤ 6 in round 2 (hard total 12). `1` is equivalent to `loop: false`. |
| `tex-only` | `true` / `false` | `false` | Only select papers with an arXiv ID (TeX source). PDF-only papers are skipped, no PDF fallback. Useful when MinerU is unavailable. |
| `pdf-parser` | `auto` / `full` / `legacy` / `vision` | `auto` | PDF backend for non-arXiv papers. `auto` = MinerU if installed else `legacy`; `full` forces MinerU; `legacy` = PyMuPDF image-only; `vision` = local render + multimodal subagent. See [Non-arXiv PDF Parsing](#non-arxiv-pdf-parsing-three-backends). Use `vision` on a MacBook Air. |

```bash
# Default: round-1 cap 6, round-2 cap 6 (≤ 12 NEW papers)
/skill:idea-landscape "Dynamic sparse attention for long-document LLMs"

# Analyze up to 10 in round 1; quick run with no loop; triple the budget
/skill:idea-landscape "..." — deep-analyze-max: 10
/skill:idea-landscape "..." — deep-analyze-max: 3 — loop: false
/skill:idea-landscape "..." — expand-budget-factor: 3

# Force Chinese; skip PDF-only papers; vision PDF path (MacBook Air)
/skill:idea-landscape "..." — language: zh
/skill:idea-landscape "..." — tex-only: true
/skill:idea-landscape "..." — pdf-parser: vision
```

### `idea-novelty` — check novelty

Auto-loads `idea-survey/landscape-report.md` for domain context and dedup. Same parameters as `idea-landscape`, with a higher default cap and a competitor-biased loop:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `deep-analyze-max` | int | `8` | Max NEW **competitive** papers to deep-analyze in round 1. Papers already analyzed upstream are reused and do not count. |
| `loop` | `true` / `false` | `true` | Loop expansion biased toward **competitor discovery** (citation hubs + named baselines mined from `core_claims` / `key_tables.what_compared`). |
| `expand-budget-factor` | int | `2` | Defaults → round-1 ≤ 8, round-2 ≤ 8 (total 16). |
| `tex-only` | `true` / `false` | `false` | As above. |
| `pdf-parser` | `auto` / `full` / `legacy` / `vision` | `auto` | As above. |

```bash
/skill:idea-novelty "Gumbel-softmax gating for per-layer sparse attention selection"
/skill:idea-novelty "..." — deep-analyze-max: 12
/skill:idea-novelty "..." — deep-analyze-max: 4 — loop: false
/skill:idea-novelty "..." — pdf-parser: vision
```

### `idea-feasibility` — assess feasibility

Auto-loads both upstream reports. Same parameters; its loop adds a **gap-driven** third signal:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `deep-analyze-max` | int | `6` | Max NEW **evidence** papers in round 1. Upstream papers reused for free. |
| `loop` | `true` / `false` | `true` | Loop expansion adds **gap-driven search** built from round-1 cards' `gap_signals`, `limitations_acknowledged`, `limitations_observed`, and `feasibility_signals.reported_failure_modes` — the most direct way to learn whether a failure mode recurs. |
| `expand-budget-factor` | int | `2` | Defaults → round-1 ≤ 6, round-2 ≤ 6 (total 12). |
| `tex-only` | `true` / `false` | `false` | As above. |
| `pdf-parser` | `auto` / `full` / `legacy` / `vision` | `auto` | As above. |

```bash
/skill:idea-feasibility "Gumbel-softmax gating for per-layer sparse attention selection"
/skill:idea-feasibility "..." — deep-analyze-max: 10
/skill:idea-feasibility "..." — deep-analyze-max: 3 — loop: false
/skill:idea-feasibility "..." — pdf-parser: vision
```

### `research-proposal` — generate the LaTeX proposal

Reads the three upstream reports + `literature-deep/` and emits a Type-B LaTeX proposal. See [How `research-proposal` works](#how-research-proposal-works) for the internal 11-step pipeline and anti-fabrication design.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `literature-dir` | path | `idea-survey/` | Root with the three reports + `literature-deep/`. Fails fast if missing — run stages 1–3 first. |
| `output` | path | `proposal/` | Where the LaTeX project, audits, and JSON state are written. |
| `language` | `zh` / `en` / `auto` | `auto` | `zh` triggers the mandatory Chinese "Research Features and Innovations" section + `\usepackage{ctex}`; `en` keeps an optional "Innovation Points" section + standard preamble. |
| `author` | string | empty | Author on the title page. Empty renders a visible red `\needfix{}` placeholder. |
| `compile` | `true` / `false` | `true` | Run `xelatex` + `biber` after generating source. Chinese path auto-skips if `ctex.sty` is missing — the `.tex` source is always the primary deliverable. |

```bash
# Chinese-language proposal with defaults
/skill:research-proposal "Physics-constrained Schrödinger Bridge calibration for heavy-ion collisions" — language: zh

# English proposal, custom paths and named author
/skill:research-proposal "Physics-constrained SB for HIC calibration" \
    — literature-dir: my-survey/  — output: my-proposal/  — author: "Jane Doe"

# Source only (no LaTeX toolchain on the machine)
/skill:research-proposal "topic" — compile: false
```

Tuning constants (`MAX_FIGURES_PER_PAPER=3`, `MAX_TOTAL_FIGURES=10`, `SUPPORTING_LIT_HIGH=12`, `SUPPORTING_LIT_MEDIUM=8`, `SUPPORTING_LIT_MAX=20`, `SUBAGENT_TIMEOUT=3600`) are **not** command-line overridable — edit the `## Constants` block in `.kimi/skills/research-proposal/SKILL.md`.

### `research-lit` — standalone deep paper analysis

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `deep analyze` | `true` / `false` | `false` | Enable per-paper deep analysis with dedicated subagents (auto-downloads source, extracts figures/tables). |
| `max` (with `deep analyze: true`) | int | `5` | Number of papers to deep-analyze **and** download source for. |
| `source` (with `deep analyze: true`) | `true` / `false` | `true` | `true` prefers TeX source (better figures); `false` uses PDF image extraction only (faster). |
| `arxiv download` | `true` / `false` | `false` | Download top-N arXiv PDFs after search (only when `deep analyze` is `false`). |
| `arxiv download source` | `true` / `false` | `false` | Download TeX tarball instead of PDF (only with `arxiv download`). |
| `paper library` | path | (none) | Local PDF collection, checked alongside online sources. |
| `sources` | comma-list | `all` | Any of `arxiv`, `semantic-scholar`, `deepxiv`, `exa`, `local`, `zotero`, or `all`. |

```bash
/skill:research-lit "Sparse attention mechanisms for long documents"
/skill:research-lit "..." — deep analyze: true
/skill:research-lit "..." — deep analyze: true, max: 3, source: false
/skill:research-lit "..." — paper library: ~/my_papers/ — sources: local, arxiv
/skill:research-lit "..." — arxiv download: true — arxiv download: 5
/skill:research-lit "..." — deep analyze: true, max: 4, source: false — language: zh
```

### `research-debug` — interactive in-progress query

First run in a project copies `templates/PROJECT_STATE_TEMPLATE.md` to `project-state.md` and exits — fill it in (especially §1 Physics Context, §2 ML Context, §3 Cross-Domain Bridge, §7 Glossary), then re-invoke. Subsequent runs walk three interactive checkpoints — **L0** (question crystallization) → **L1** (knowledge-only sketch) → **L2** (dry-run + light paper read) — and stop as soon as the answer is good enough. It never chains to another skill; if a full deep dive is needed, the report prints a `/skill:research-lit` hand-off you run yourself.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `depth` | `L0` / `L1` / `L2` | `L1` | Depth ceiling. `L0` ≈ 1 min (clarify only); `L1` ≈ 3–5 min (sketch from model knowledge, no search); `L2` ≈ 15–25 min (sketch + dry-run plan + light-read up to N papers). |
| `light-read-max` | int 1–5 | `3` | With `depth: L2`, max papers to light-read in parallel (abstract + intro + ≤ 2 figures each). |
| `reuse-idea-survey` | `true` / `false` | `true` | When `idea-survey/` exists, reuse upstream report headers + already-analyzed `deep_analysis.md`. Set `false` to ignore prior project context. |
| `language` | `zh` / `en` / `auto` | `auto` | As global, plus: `project-state.md` §8 `language_for_output` wins if set. |

```bash
/skill:research-debug "Why does my v2{4} prediction go negative after gradient clipping?"
/skill:research-debug "Why is my EGNN-predicted v2 negative?" — depth: L0
/skill:research-debug "How do people Bayesian-calibrate when the simulator IS a neural surrogate?" — depth: L2
/skill:research-debug "..." — depth: L2 — light-read-max: 2
/skill:research-debug "..." — reuse-idea-survey: false
```

### `analytic-derivation` — cross-paper symbolic chain

First invocation copies `templates/DERIVATION_TARGET_SPEC_TEMPLATE.md` to `analytic-derivation/<run_slug>/derivation-target.md` and stops. Edit the spec (§1A source endpoint, §1B sink endpoint, §1C/§1D required/forbidden intermediates — all SACRED; §1E math form; §2 anchor arXiv IDs; §3 bridging hypotheses, revisable by default), then re-invoke. See [Symbolic Derivation Track](#symbolic-derivation-track).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `interactive` | `true` / `false` | `true` | Interactive checkpoints after the chain sketch, notation + assumption ladder, and derivation steps. Set `false` for unattended overnight runs (uses the spec verbatim). |
| `lit-verify` | `true` / `false` | `true` | Run the literature-verification pass on uncertain assumptions. |
| `lit-verify-max` | int | `6` | Cap on verification items. |
| `pdf-parser` | `auto` / `full` / `legacy` / `vision` | `auto` | For anchor papers without arXiv TeX. Use `vision` on a MacBook Air. (`tex-only` auto-enables if every anchor already has TeX.) |
| `run-slug` | string | derived | Per-run subdirectory name (default: from `$ARGUMENTS` + timestamp). |
| `language` | `zh` / `en` / `auto` | `auto` | As global. |

```bash
# 1) Bootstrap the spec (copies the template, then stops)
/skill:analytic-derivation "derive Var(P_z) as a function of beta_2"
# 2) Edit derivation-target.md, then re-invoke to run the derivation
/skill:analytic-derivation "derive Var(P_z) as a function of beta_2"

# Overnight unattended; wider verification budget; vision PDFs; explicit run name
/skill:analytic-derivation "goal" — interactive: false
/skill:analytic-derivation "goal" — lit-verify-max: 10
/skill:analytic-derivation "goal" — pdf-parser: vision
/skill:analytic-derivation "goal" — run-slug: pz-variance-beta2
```

### `derivation-refine-loop` — multi-reviewer hardening

Takes an existing `analytic-derivation/<run>/` directory as `$ARGUMENTS`. It is **resumable** — re-invoking on the same directory picks up at the highest existing round. For autonomy modes, halt conditions, outputs, and feedback channels see [Symbolic Derivation Track](#symbolic-derivation-track).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max-rounds` | int | `4` | Hard cap on refinement rounds. Auto-bumped to `8` under `autonomy: max` unless set explicitly. |
| `reviewers` | comma-list | `rigor,physics,literature,adversarial` | Which reviewer "hats" to dispatch each round. Drop roles you don't trust on a given derivation. |
| `interactive` | `true` / `false` | `true` | Checkpoint between rounds. **Forced to `false`** under `autonomy: max`. |
| `lit-verify-budget` | int | `3` | Per-round cap on fresh `lit-verifier` dispatches. |
| `axiom-explore-budget` | int | `2` | Per-round cap on `axiom_explore` episodes (each runs K SymPy sister-chains — raise cautiously). |
| `axiom-auto-promote` | `true` / `false` | `false` | Let the sister-comparator auto-promote a strongly-supported alternative axiom set (unattended mode only). |
| `autonomy` | `normal` / `max` | `normal` | `max` = full hands-off: §1E auto-syncs on form drift, axiom-explore-exhausted graceful-degrades, max-rounds bumps to 8; only `endpoint_class_change` and `reviewer_divergence` still halt. Cannot combine with `interactive: true`. |
| `convergence-delta` | int | `0` | Tolerated new-critical issues per round before declaring divergence. `1` tolerates one re-statement. |
| `language` | `zh` / `en` / `auto` | `auto` | As global. |

```bash
# Default: 4 rounds × 4 reviewers × axiom-explore on tier-1 CRITICALs
/skill:derivation-refine-loop "analytic-derivation/<run_slug>"

# More rounds; fewer reviewers; tolerate one re-statement; bigger axiom budget
/skill:derivation-refine-loop "<run>" — max-rounds: 6
/skill:derivation-refine-loop "<run>" — reviewers: rigor,physics
/skill:derivation-refine-loop "<run>" — convergence-delta: 1
/skill:derivation-refine-loop "<run>" — axiom-explore-budget: 3

# Full overnight hands-off mode
/skill:derivation-refine-loop "<run>" — autonomy: max — axiom-auto-promote: true
```

---

## How the Survey Pipeline Works

### How `deep-analyze-max` actually counts

`deep-analyze-max` counts **NEW** papers only, never reused ones. Example: run `idea-landscape` (cap 6) → 6 papers saved to `literature-deep/`. Then run `idea-novelty` (cap 8); of 10 competitive papers found, 3 were already analyzed in stage 1. The system **reuses** those 3 at zero cost and analyzes only **5 NEW** papers (5 < 8 cap), for 11 papers in the report. Each paper takes ~5 min; with 4 concurrent subagents, 8 papers ≈ 10–15 min wall-clock. Rule of thumb: `3–4` = quick sanity check, `6–8` = default thoroughness, `10–12` = very thorough.

`literature-deep/` is **shared across stages** — if `idea-novelty` needs a paper `idea-landscape` already analyzed, it reuses the existing `deep_analysis.md` and `paper_card.json` automatically.

### Loop Expansion (Step 4.6)

A single keyword search built from the user's fuzzy phrasing reliably misses (a) citation hubs (papers everyone in the sub-field cites but whose title uses an older term) and (b) the field's precise mechanism vocabulary, which only becomes visible after reading a few representative papers. So after round-1 deep analysis and card distillation, **Step 4.6** fires once:

1. **Mine round-1 cards** for citation-graph seeds (`arxiv_id` / `doi`) and precise terms (`technical_route.method_family`, `novelty_signals.specific_mechanism`, named methods in `core_claims`).
2. **Surface candidates** via up to three signals: **citation-graph hubs** (all skills — papers referenced or cited by ≥ 2 round-1 seeds, via `semantic_scholar_fetch.py cross-cited`); **precise-term search** (all skills); and **gap-driven search** (`idea-feasibility` only — queries built from each card's gap/limitation/failure-mode fields).
3. **Round-2 deep analysis** of up to `(expand-budget-factor − 1) × deep-analyze-max` newly-surfaced papers, reusing the same Step 3/4/4.5 prompts.

**Per-skill flavor:** `idea-landscape` weights hubs + term refinement equally (field coverage); `idea-novelty` weights hubs + **named baselines** heavily (find the closest competitor); `idea-feasibility` adds gap-driven search (evidence saturation around failure modes).

**Termination** (any one → `.loop_skipped`, jump to report): `loop: false`; round 1 produced < 2 NEW analyses; round-2 budget ≤ 0; zero new candidates surfaced; or the synthesizer rejected every candidate. The loop runs **exactly once** — no nested loop, no third round. The audit (`idea-survey/.loop_audit.json`) records seeds, selections, and per-candidate `expansion_source` (`hub_refs` / `hub_cites` / `term_search` / `gap_search`), which the report-writer uses to tag round-2 entries.

### Progressive disclosure via `paper_card.json` (Step 4.5)

Right before each report-writer, every paper in `literature-deep/` is distilled by a `paper-analyzer` subagent into a compact `paper_card.json` (~3–10 KB) following `templates/PAPER_CARD_SCHEMA.md`. The report-writer then consumes only the small JSON cards, reading a full `deep_analysis.md` only on demand for a verbatim quote or number. This shrinks the report-writer's input from O(MB) of paper text to O(100 KB) of structured JSON — the single biggest fix for the "compaction at final report" failure mode with 6+ papers. Cards are cached by `deep_analysis.md` mtime + schema version, so re-running a downstream skill regenerates nothing, and cards from `idea-landscape` are reused by `idea-novelty` / `idea-feasibility` for free.

### How `research-proposal` works

The skill runs an 11-step pipeline. **The main agent never reads paper files directly** — steps marked [Subagent] delegate to a `paper-editor`; [shell] steps run mechanical commands.

| # | Step | Owner | Output |
|---|------|-------|--------|
| 0 | Directory setup | shell | `proposal/{body,figures,supporting_papers}/` |
| 1 | Extract upstream metadata + consistency audit | Subagent A | `upstream_metadata.json` + `CONSISTENCY_NOTES.md` |
| 2 | Index paper assets (figures, equations, tex source dirs) | Subagent B | `paper_index.json` |
| 3 | Copy selected figures | shell | `paperN_figM.png` |
| 4a | Identify supporting claims, classify HIGH / MEDIUM | Subagent C | `supporting_queue.json` |
| 4b–4d | Fetch + index + dedup BibTeX (`bibtex_fetch.py`) | shell | `references.bib`, `bib_index.json` |
| 5 | Draft 9 body files (abstract + 8 sections) | Subagent D | `body/*.tex` |
| 6 | **Rigor audit** (7 checks; revises body) | Subagent E | revised body + `rigor_audit.md` |
| 7 | **Language audit** (strictly AFTER rigor, never parallel) | Subagent F | revised body + `language_audit.md` |
| 8 | Assemble `main.tex` from template | shell | `main.tex` |
| 9 | Compile `xelatex` + `biber` (optional) | shell | `main.pdf` |
| 10 | Final verification (citations, undefined refs, `??`, group-author artifacts) | shell | go/no-go |

**Anti-fabrication** closes four modes: (1) hallucinated BibTeX — every entry is fetched and validated against expected year / first author / title tokens; (2) hallucinated arXiv IDs — every ID is HEAD-probed against `arxiv.org/abs/{id}` (a 404 rejects it; a network error is "unknown", not "fail"); (3) mismatched author/year in prose — Subagent D is fed `bib_index.json` and must look up every "(YYYY)" and surname there; (4) fabricated numbers — every number in prose must be grep-locatable in the cited paper's arXiv TeX source, its `deep_analysis.md`, or the upstream reports, else it is rewritten qualitatively or marked `\needfix{}`.

The two audit files (`rigor_audit.md`, `language_audit.md`) are the human-review surface — each change shows `old → new` and the reason; items the subagent could not auto-fix appear under "require human decision". Stage originals are archived under `body/.archive/{draft,after_rigor}/` for A/B comparison.

---

## Symbolic Derivation Track

### `analytic-derivation` flow

Given a target observable, 2–8 anchor papers, and bridging hypotheses, the skill builds a chain of SymPy substitutions / expansions / limits / dimensional checks and executes it, producing a `derivation_trace.json` with `overall_status` and per-step `checks[]`. It reconciles notation across papers, maintains a three-tier assumption ladder, runs a `lit-verifier` pass on uncertain items, and ends with an `hep-theory-reviewer` audit.

The **v2 spec** (`derivation-target.md`) declares the *causal-graph endpoints* as the SACRED contract — §1A source class, §1B sink class, §1C required intermediates, §1D forbidden detours — plus §1E (math form) and §2 (anchors). §3 bridging hypotheses are **revisable by default**; set `lock_to_user_axiom: true` per row to opt out. The sacred object is now **the research question** ("relate this control-parameter class to this observable class"), not the specific functional forms.

### Axiom-Explore Loop (v2)

**The problem v1 had.** On the spin-polarization-variance derivation, the four reviewers correctly identified a fundamentally wrong tier-1 hypothesis at CRITICAL severity in rounds 2 and 3 — but v1 could only mark it `user_axiom_locked` and drop it from the `new_critical` count, so by round 4 the loop reported `converged` while the bug was still present. Detection-only is wasted information when the model has no way to *propose* alternatives.

**The v2 fix** inserts three orchestration steps between the router (Step 3) and the regular fixers (Step 4):

- **Step 3.5 `axiom-explorer`** (one per `axiom_explore` route) — a self-contained literature search (WebSearch + arxiv + semantic-scholar + exa; Kimi forbids skill-to-skill calls) that reads the §1A–§1D endpoints (via `tools/spec_parser.py`), searches *independent* literature for alternative formulations of the challenged bridge, runs an **endpoint isomorphism guard** on each, and returns up to K=3 candidate axiom sets with provenance and a predicted-impact category.
- **Step 3.6 sister-derivation** (theory-synthesizer Call J, ≤ K per episode) — runs the full SymPy chain under each *candidate's* axioms. A sister with `overall_status: failed` is a valid, diagnostic outcome (the candidate is internally inconsistent).
- **Step 3.7 `sister-comparator`** (one per episode) — compares main vs. all sisters' final equations and classifies each disagreement: `parametric_dependence_order` / `sign_change` / `dimension_change` (→ **main suspect**), `regime_of_applicability_change` (→ tighten §5 validity), `none_*` (→ main robust), `chain_incompatible_with_candidate` (→ candidate rejected). Verdict: `main_axiom_robust` / `main_axiom_suspect` / `..._within_declared_regime` / `mixed`, with a recommendation up to `auto_promote_to_main_next_round` (gated by `axiom-auto-promote` + ≥ 2 independent papers + ≥ 2 sisters in the same category).

**Convergence policy.** v1 declared convergence on `new_fatal == 0 AND new_critical == 0`. v2 requires `new_fatal == 0 AND new_critical == 0 AND endpoint_violation_count == 0 AND open_axiom_explore_count == 0`. The last term is cross-round: any prior episode whose verdict is `main_axiom_suspect` and whose promotion was not actioned stays OPEN — this is what blocks the v1 "converge with a known bug" mode.

### Autonomy modes (v2.1)

`autonomy: normal` (default) halts on five conditions, each producing a distinct `paused_pending_*` headline: `endpoint_class_change`, `endpoint_form_drift`, `axiom_explore_exhausted`, `reviewer_divergence`, `max_rounds_reached`. You read the audit, act, re-invoke.

`autonomy: max` (hands-off) auto-handles three and protects two:

| Halt | Behaviour under `autonomy: max` |
|------|---------------------------------|
| `endpoint_class_change` | **Still halts** — changing the research question is not an engineering decision. |
| `endpoint_form_drift` | Call-H §5d auto-rewrites §1E to match the derived form; logs `spec_form_auto_synced`; continues. |
| `axiom_explore_exhausted` | Writes a scope-caveat patch (result conditional on the unverifiable hypothesis); ladder status → `user_axiom_conditional`; continues. |
| `reviewer_divergence` | **Still halts** — signals a real unresolvable issue. |
| `max_rounds_reached` | `max-rounds` auto-bumps 4 → 8. |

`autonomy: max` forces `interactive: false` and strongly recommends `axiom-auto-promote: true`. The trade-off is **conditional convergence**: a `converged` headline then means "no engineering blockers remain" — always read audit §A2 (axiom-explore graceful-degrades) and §D2 (§1E auto-sync log) before treating the result as production-ready.

### Reading the refine-loop output

When the loop finishes (converged OR paused), artifacts live under `<run>/refine/`. Read in this order:

| Priority | File | Purpose |
|----------|------|---------|
| 1st | `convergence_state.json` | Headline state + per-round timeline. The `convergence_headline` field is authoritative. |
| 2nd | `refinement_audit.md` | Consolidated narrative: §0 TL;DR, §5 open issues, §7 axiom-explore audit. |
| 3rd | `current/derivation_steps.md` + `current/derivation_trace.json` | The current best derivation (symlink to the latest accepted round) + SymPy-auditable trace. |
| 4th | `current/assumption_ladder.md` | What's still assumed / verified / `needs_promotion_review`. |
| 5th | per-round `router_decision.md` | Why each round routed what it did. |
| as needed | `.axiom_explore/${EPISODE}.md`, `_comparison.md`, `.sister_outputs/*` | Alternatives considered, comparator verdict, side-by-side sister equations. |

Headline cheat sheet: `converged` (done — read §A2/§D2 if you ran `autonomy: max`); `paused_pending_endpoint_class_decision` (reviewer proposes changing §1A–§1D); `paused_pending_endpoint_form_drift` (§1E mismatch); `paused_pending_axiom_exhausted` (no literature alternatives); `paused_pending_axiom_review` (sister-comparator flagged `main_axiom_suspect`, needs your pick); `paused_pending_reviewer_divergence` (same issue ≥ 3× across rounds); `max_rounds_reached_without_convergence` (bump `— max-rounds: N` and resume). Downstream consumers (e.g. `research-proposal`) MUST check this headline — "all paths produce a green report" is no longer safe.

### Course-correcting the loop (feedback channels)

The loop is resumable; every feedback pattern is "make a change, then re-invoke":

1. **Spec edits (strongest control)** — edit `<run>/derivation-target.md`: tighten/broaden §1A/§1B classes (addresses `endpoint_class_decision`); set `lock_to_user_axiom: true` on a §3 row to stop it being axiom-explored; edit §1E to override a previous auto-sync; add anchors in §2 to widen the axiom-explorer's base.
2. **Promotion decision** — on `paused_pending_axiom_review`, write `<run>/refine/user_promotion_decision.json` with your chosen `candidate_id`, then re-invoke; Call-H Step 0 applies it.
3. **Interactive checkpoints** (normal mode) — reply `go` / `skip lit` / `skip N` / `edit router: <change>` / `stop` between rounds.
4. **Re-invocation flags** — `— convergence-delta: 1`, `— max-rounds: 8`, `— reviewers: rigor,physics`, `— axiom-explore-budget: 3`, `— autonomy: max — axiom-auto-promote: true`.
5. **Manual ladder / notation edits (escape hatch)** — fix a wrong `auto-registered placeholder` in `current/notation_table.json`, or set a `needs_promotion_review` axiom's `status` to `verified_compatible` / `retired` in `current/assumption_ladder.json`. Reviewers respect explicit status fields next round.

**Do NOT** hand-edit `derivation_trace.json` or `derivation_steps.md` (regenerated by SymPy every round), and do not delete `refine/round_0/` (the frozen baseline) or `refine/` (resumption depends on it).

---

## Non-arXiv PDF Parsing (three backends)

Many physics papers — older PRL/PRD/PRC/PRB issues, collaboration internal notes (ATLAS/CMS/ALICE/STAR/PHENIX), national-lab reports, Chinese-language journals, conference proceedings — never get an arXiv preprint. For these the pipeline ships three PDF parsers, selected with the `pdf-parser` skill argument (see [Usage](#usage--every-invocation-in-one-place)) or auto-selected by the orchestrator:

| Backend | When to use | Local cost | Output quality |
|---------|-------------|-----------|----------------|
| `full` (MinerU) | GPU available; want highest fidelity | ~5 GB weights, 30 s/page CPU, ~1 s/page GPU | figures + tables + equations + caption attribution |
| `vision` (LLM) | CPU-only laptop; full schema without MinerU | seconds locally + LLM API quota | figures + tables + equations via a multimodal subagent |
| `legacy` (PyMuPDF) | Last-resort offline fallback | seconds, no API | image-only, no captions / tables / equations |

All three emit a `figure_manifest.json` whose schema is **byte-for-byte identical** to the TeX-source path, so every paper-analyzer and `research-proposal` consume all paths transparently. Each figure/table carries a `caption_provenance` field; `parse_log.json` flags every heuristic caption and every suspect equation. Caption correctness is prioritized over equation precision (a hand-curated figure is the primary unit of comprehension; a garbled equation is a one-minute fix): MinerU's native caption first → ±3-block `Figure N` / `Fig. N` (or the Chinese figure label `图 N`) heuristic with index verification → nearest caption-shaped neighbor → `null` + logged.

### Direct tool usage

```bash
# Install (one-time)
pip install -U "mineru[core]"          # ~5 GB model on first run
pip install "pix2tex"                  # optional equation fallback

python3 tools/pdf_full_parser.py check-deps                 # what's available here
python3 tools/pdf_full_parser.py parse --pdf paper.pdf --output-dir literature-deep/paper_x/
python3 tools/pdf_vision_parser.py finalize --output-dir literature-deep/paper_x/   # after the vision subagent writes vision_extraction.json

# Self-test without a PDF or MinerU (bundled fixture):
python3 tools/pdf_full_parser.py parse --pdf /dev/null \
    --output-dir /tmp/selftest/ \
    --mock-mineru-output tools/tests/fixtures/mineru_minimal/ --no-pix2tex
# Expect: figure_count=2, table_count=1, equation_count=3
```

### Low-spec machines (MacBook Air / CPU-only)

MinerU is the heaviest dependency — on a fan-less laptop it can pin all cores and freeze the machine for the duration of a parse. **Don't run MinerU there.** In order of preference: (1) **`— pdf-parser: vision`** — full schema (captions, tables, equations) with no local model, offloaded to the same multimodal subagent that already reads figures; (2) **`— tex-only: true`** — skip PDF-only papers entirely (fine for most ML/LLM topics); (3) **`— pdf-parser: legacy`** — figures-only, no API spend; (4) **`pip uninstall mineru`** — the orchestrator then auto-falls-back to legacy; (5) for `research-lit`, **`— deep analyze: true, source: false`**. Never run MinerU on battery.

---

## Multi-Project Shared Paper Pool

If several projects share overlapping literature, configure a **shared paper pool** so each paper is analyzed exactly once and later projects mount it by symlink for free. The pool is **opt-in and fully backward compatible**: if `ARIS_PAPERS_POOL` is unset, the pipeline runs project-local exactly as before — no shared state, no symlinks, no dedup.

```
~/aris/papers-pool/                      ← shared paper database
├── index.json                           ← arxiv_id / DOI / title-hash → paper_key
└── paper_arxiv_2301_07041/
    ├── deep_analysis.md, paper_card.json, figure_manifest.json, figures/, 2301.07041_src/
    └── analyzed_by.json                  ← which projects/topics used this paper

~/research/<project>/idea-survey/literature-deep/
    └── paper_arxiv_2301_07041 -> ~/aris/papers-pool/paper_arxiv_2301_07041   ← symlink
```

```bash
# 1. First-time setup (once per machine)
export ARIS_PAPERS_POOL=$HOME/aris/papers-pool
python3 tools/papers_pool.py init
echo 'export ARIS_PAPERS_POOL=$HOME/aris/papers-pool' >> ~/.zshrc   # make permanent
python3 tools/papers_pool.py status                                 # verify

# 2. Day-to-day: nothing extra per project — just run skills as usual.
#    After Step 2 selects papers, each idea-* skill runs `papers_pool.py resolve`
#    automatically: pool hit → symlink (zero cost); miss → new pool dir, then Step 3/4/4.5 fill it.

# 3. Migrate an existing pre-pool project into the pool (always dry-run first)
python3 tools/papers_pool.py migrate --project-dir ~/research/old-project \
    --topic "Dynamic sparse attention" --dry-run
python3 tools/papers_pool.py migrate --project-dir ~/research/old-project \
    --topic "Dynamic sparse attention"            # add --on-conflict skip if conflicts > 0

# 4. Management
python3 tools/papers_pool.py status               # pool stats
python3 tools/papers_pool.py selftest             # end-to-end check in a throwaway dir
```

**Resolution:** for each paper the resolver computes a canonical `paper_key` (first of `arxiv_id` → `DOI` → title-hash) and looks it up across all three sub-indices. Hit → `reuse` (symlink, skip download + deep analysis); miss → `analyze` (new pool dir). `migrate` is idempotent and atomic; pool writes are serialized by an exclusive `fcntl` lock so parallel Kimi terminals are safe. **Caveats:** disk format is symlinks (keep the pool path stable; moving it requires re-linking); two synthesizers naming the same paper differently (arXiv vs. DOI-only) may fail to dedup; the pool is single-user. `paper_card.json` is project-agnostic except `relevance_at_first_analysis`, which a reusing project treats as a *hint* and re-evaluates against its own topic. To detach a project from the pool, replace each symlink with a copy of its target (`cp -RL`).

---

## Tool Reference

17 Python tools under `tools/`. None are invoked by the main agent directly except mechanical shell steps; paper-reading tools are driven by subagents.

| Tool | Role | Key deps |
|------|------|----------|
| `paper_analyzer_orchestrator.py` | Prepares the analysis workspace (figures from PDF or TeX + manifest). Auto-selects `pdf_full_parser` if MinerU installed, else `pdf_figure_extractor`. | latex/pdf parsers |
| `image_preprocessor.py` | Converts EPS/PDF/TIFF → PNG, downsamples to ≤ 1536 px / ≤ 2 MB | Pillow, ghostscript*, pdf2image* |
| `latex_source_parser.py` | Extracts figures / equations / tables from arXiv TeX source | stdlib |
| `pdf_full_parser.py` | Full-spectrum non-arXiv PDF parser (MinerU): figures + tables + equations + caption attribution; pix2tex fallback on suspect equations; writes `parse_log.json` | MinerU, pix2tex*, Pillow |
| `pdf_vision_parser.py` | Vision-LLM PDF parser. `render` (PyMuPDF page render + image extraction) then `finalize` (assemble manifest from the subagent's `vision_extraction.json`). Layout understanding is done by a multimodal subagent | PyMuPDF; a multimodal model |
| `pdf_figure_extractor.py` | Legacy image-only PDF extractor (degenerate manifest) | PyMuPDF |
| `papers_pool.py` | Multi-project paper pool: `init` / `resolve` / `status` / `migrate` / `selftest`. No-op when `$ARIS_PAPERS_POOL` is unset | stdlib |
| `arxiv_fetch.py` | arXiv search + PDF / source-tarball download | — |
| `bibtex_fetch.py` | BibTeX for `research-proposal`: `fetch` (DBLP → DOI → arXiv, with year/author/title validation + arXiv HEAD probe), `build-index`, `verify-tex`. Handles group-author surnames | — |
| `semantic_scholar_fetch.py` | Semantic Scholar client: `search`, `search-bulk`, `paper`, `references`, `citations`, `cross-cited` (citation-graph hub detection for Step 4.6) | — |
| `exa_search.py` | AI web search beyond academic databases | exa-py |
| `deepxiv_fetch.py` | Progressive paper retrieval (brief → head → section) | deepxiv |
| `research_wiki.py` | Paper relationship graph, slugs, query packs, evidence links | — |
| `figure_renderer.py` | SVG/HTML figure rendering for reports | — |
| `symbolic_derive.py` | SymPy derivation runner for `analytic-derivation` Step 5 and refine-loop Calls G/H/J: `run`, `check-deps`, `selftest`. Reads a `derivation_script.json`, writes `derivation_trace.json`. Subagent-only | sympy |
| `spec_parser.py` | v2 helper for refine-loop Step 3.5: parses spec §1A/§1B/§1C/§1D endpoint blocks. `parse`, `selftest`. Optional (refine-loop has a try/except fallback) | stdlib |
| `arxiv_eps_converter.py` | Legacy EPS→PNG; superseded by `image_preprocessor.py` | ghostscript, Pillow |

(* = optional dependency)

---

## Templates

14 strict output templates under `templates/`.

**Survey + paper analysis:** `PAPER_DEEP_ANALYSIS_TEMPLATE.md` (figure/equation/table-by-table; used by every paper-analyzer), `PAPER_CARD_SCHEMA.md` (compact JSON distillation — Step 4.5 output), `IDEA_LANDSCAPE_TEMPLATE.md`, `IDEA_NOVELTY_TEMPLATE.md`, `IDEA_FEASIBILITY_TEMPLATE.md`, `RESEARCH_PROPOSAL_TEMPLATE.tex` (Type-B LaTeX skeleton with `<<...>>` placeholders), `PROJECT_STATE_TEMPLATE.md` (research-debug ambient context), `RESEARCH_DEBUG_REPORT_TEMPLATE.md`.

**Symbolic derivation:** `DERIVATION_TARGET_SPEC_TEMPLATE.md` (v2: §1A–§1D SACRED endpoints, §1E math form, §3 with `lock_to_user_axiom`), `PAPER_DERIVATION_CARD_SCHEMA.md`, `DERIVATION_REPORT_TEMPLATE.md`, `DERIVATION_REVIEW_REPORT_TEMPLATE.md`, `REFINEMENT_AUDIT_TEMPLATE.md` (v2 §7 axiom-explore audit), `AXIOM_CANDIDATES_TEMPLATE.md` (v2 axiom-explorer output schema).

Idea-survey templates include an `ARIS_GUIDANCE_START/END` block for human-in-the-loop refinement; derivation templates carry the human signal in the spec's §3 `lock_to_user_axiom` column instead.

---

## Output Structure

```
idea-survey/
├── landscape-report.md / novelty-report.md / feasibility-report.md   # stage reports + user guidance
├── .loop_*.json                # Step 4.6 state: budget, mined terms, hubs, term/gap search, candidates, audit
├── .loop_skipped               # sentinel + reason when the loop is skipped
└── literature-deep/            # SHARED across stages and rounds
    └── paper_arxiv_2301.xxxx/
        ├── deep_analysis.md        # full per-paper analysis (50–150 KB)
        ├── paper_card.json         # compact distillation (3–10 KB)
        ├── figure_manifest.json + figures/
        └── phase1_*.md / phase2_*.md   # if Two-Phase analysis was used

proposal/
├── main.tex (+ main.pdf)
├── body/{abstract,sec1..sec8}.tex + .archive/{draft,after_rigor}/
├── figures/  supporting_papers/
├── references.bib  bib_index.json
├── upstream_metadata.json  paper_index.json  supporting_queue.json
├── CONSISTENCY_NOTES.md  rigor_audit.md  language_audit.md
└── bibtex_fetch_failures.json    # only if HIGH-priority fetches failed

analytic-derivation/<run>/
├── derivation-target.md  derivation-report.md  derivation_trace.json
└── refine/                       # written by derivation-refine-loop
    ├── convergence_state.json    # ★ read FIRST
    ├── refinement_audit.md
    ├── current -> round_N/
    └── round_K/ { reviews/, router_decision.*, .axiom_explore/, .sister_outputs/,
                   .fixer_outputs/, derivation_*, assumption_ladder.*, notation_table.* }
```

---

## Step Budget (`--max-steps-per-turn`)

Every skill is a long-running orchestration: each subagent dispatch, poll, JSON read, and audit write counts as one step in kimi-cli's `max_steps_per_turn` budget. When exhausted, the CLI pauses for a manual `continue` — fine interactively, fatal for overnight runs.

| Skill | Suggested `--max-steps-per-turn` | Why |
|-------|----------------------------------|-----|
| `research-debug` (L0/L1/L2) | default (1000) | Short interactive; ≤ 200 steps |
| `research-lit` (deep analyze) | `2000` | One deep-analysis dispatch + polling + write |
| `idea-landscape` / `idea-novelty` / `idea-feasibility` | `3000` | Round-1 deep analysis on ≤ 12 papers + Step 4.6 |
| `research-proposal` | `3000` | 11-step pipeline, 6 subagents, bibtex loops |
| `analytic-derivation` | `2000` | 7 steps, ≤ 8 dispatches + checkpoints |
| `derivation-refine-loop` | `5000` | Up to 4 rounds × (4 reviewers + router + N fixers + merge) |

```bash
kimi --max-steps-per-turn 5000 /skill:derivation-refine-loop "..."
echo 'alias kimi="kimi --max-steps-per-turn 5000"' >> ~/.zshrc   # or set max_steps_per_turn in kimi-cli config
```

Old kimi-cli defaulted to 100 steps, which pauses virtually every skill here — upgrade to the latest (default 1000) and pass `5000` for the long ones. The budget is a **runaway-loop circuit-breaker, not a performance limit**: every skill has its own hard caps (`MAX_ROUNDS`, `LIT_VERIFY_BUDGET`, …) that bound work long before the step budget. Do **not** auto-inject `continue` via expect/tmux — that removes the last circuit-breaker; for genuinely unattended runs use `kimi-agent-sdk` with a supervisor that reads `convergence_state.json` / `.loop_audit.json`.

---

## Design Principles

1. **Zero interruption.** Each pipeline skill runs start-to-finish without asking questions (`research-debug` is the deliberate interactive exception).
2. **Main agent orchestrates, never reads papers.** All paper analysis, prose, claim extraction, and rigor/language auditing is delegated to subagents. The main agent's file-reading budget is < 50 KB per run; the only allowed exception is `paper_card.json` (< 10 KB, an explicit derived index). Full `deep_analysis.md` files are off-limits to the main agent.
3. **Progressive disclosure across subagent layers.** The Step 5 report-writer reads compact `paper_card.json` cards (Step 4.5), not 6–10 full `deep_analysis.md` files, falling back to a targeted read only for a specific quote or number.
4. **No false precision.** Verdicts are qualitative (`PROCEED` / `CAUTION` / `REFRAME` / `ABANDON`), not fake-numerical scores.
5. **Resume-friendly.** Each stage re-runs with updated guidance; previously analyzed papers are reused via the shared `literature-deep/`.
6. **Graceful degradation.** If image analysis hits transient LLM errors, the system falls back to text-only (`PARTIAL`) rather than failing.
7. **Rigor before language** (`research-proposal`). The rigor audit and language audit run strictly sequentially — polishing un-corrected rigor entrenches half-true prose with prettier wording.
8. **Zero numerical fabrication** (`research-proposal`). Every number in prose must be grep-locatable in the cited paper's arXiv TeX source, its `deep_analysis.md`, or the upstream reports; unverified numbers are rewritten qualitatively or marked `\needfix{}` (numbers inside `\needfix{}` are themselves stripped).

---

## Status Codes (Deep Analysis Index)

| Status | Meaning |
|--------|---------|
| `Completed` | Full single-subagent analysis succeeded |
| `COMPLETED_2PHASE` | Paper too large; analyzed via Phase 1 (text) + Phase 2 (parallel image shards) |
| `PARTIAL` | Images skipped after repeated LLM provider errors; text / equations / tables usable |
| `FINAL_TIMEOUT` | Subagent exceeded 1 h twice; paper skipped |
| `FINAL_FAILED` | Subagent failed twice; paper skipped |

---

## Relationship to the Main ARIS System

This package is a **portable, Kimi-adapted snapshot** of the idea-survey + derivation capability from the ARIS codebase. ARIS itself targets Claude Code; this package is adapted for Kimi CLI (cheaper to run) and is self-contained: the 8 skills (`.kimi/skills/`), their tools (`tools/`), templates (`templates/`), the main-agent definition (`agents/aris-kimi.{md,yaml}`), and all subagent role definitions (`agents/subagents/`, including the `.md` roles and the 9 `.yaml` registrations) are all present and runnable on Kimi CLI.

It does **not** include other ARIS skills (e.g. `research-refine`, `experiment-plan`, `paper-write`) or the full ARIS orchestrator runtime. If you are running inside the full ARIS system, use the skills from there; use this package when you need a standalone copy for review, modification, or deployment elsewhere.

> Note: `agents/aris-kimi.yaml` registers the 9 subagents that the survey skills dispatch (paper-analyzer, paper-editor, novelty-checker, experiment-auditor, hep-reviewer, hep-theory-reviewer, proof-reviewer, research-reviewer, patent-examiner). The derivation-track subagents (`theory-synthesizer*`, `derivation-reviewer*`, `refinement-router`, `lit-verifier`, `axiom-explorer`, `sister-comparator`) are dispatched by name from within the derivation skills and have `.md` role definitions only.

---

## Citation & License

This project is a derivative and Kimi adaptation of [ARIS (Auto-Research-In-Sleep)](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep). ARIS is built on **Claude Code**; this package is adapted for **Kimi CLI**, which is cheaper to run.

- **Upstream repository**: https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep
- **License**: [MIT License](LICENSE)

If you use this work, please cite the upstream project:

```bibtex
@software{aris2026,
  author = {wanshuiyin},
  title  = {ARIS: Auto Research Intelligence System},
  url    = {https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep},
  year   = {2026}
}
```

### Acknowledgments

Sincere thanks to **wanshuiyin**, author of the upstream ARIS project, on which this package is based.

---

*This pipeline is designed for overnight runs. Start a stage before you sleep, review the report in the morning.*
