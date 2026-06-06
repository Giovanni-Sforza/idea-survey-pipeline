---
name: derivation-refine-loop
description: Iterative multi-reviewer refinement loop for an existing analytic derivation. Use when a derivation produced by `/skill:analytic-derivation` (or composed by hand and stored in the same on-disk layout) has passed its first sanity pass but you want it hardened the way a real advisor would harden it — multiple rounds of independent adversarial review, each round dispatched in parallel by reviewers wearing different "hats" (symbolic rigor, physical assumption, literature consistency, devil's advocate), with automatic routing of each surfaced issue to (a) a `theory-synthesizer` revision call that re-runs SymPy, (b) a fresh `lit-verifier` call when a reviewer demands new literature evidence, or (c) a `paper-editor` clarification when only the assumption ladder needs tightening. Convergence is declared when one full round produces no new FATAL/CRITICAL issues. Designed for theoretical / phenomenological physics derivations where the weakness sequence is empirically dominated by "one new class of error per round" — exactly the pattern that wastes a senior advisor's time and the pattern that a less-capable LLM cannot break on its own from a single-shot review.
argument-hint: [path to existing derivation run directory, e.g. analytic-derivation/derive-spin-polarization-fluctuation-as-function-of-beta-2-0524-1616]
---

# Derivation Refinement Loop — Multi-Reviewer Iterative Hardening

User goal: refine `$ARGUMENTS`

## Why This Skill Exists

`/skill:analytic-derivation` produces a complete derivation with a
single-pass `hep-theory-reviewer` audit in Step 6. In practice — and the
empirical record of refining real derivations bears this out — **one
round of review is not enough**. Each round of human-style adversarial
critique catches a *different class* of error, in a roughly monotone
schedule:

| Round | Class of error typically caught |
|---|---|
| 1 | Wrong ensemble definitions, deterministic-vs-fluctuating confusion, missing canonical scaling laws |
| 2 | Implicit linearisation, mean-vs-fluctuation conflation, real-vs-complex bait-and-switch |
| 3 | Single-channel attribution that ignores parallel physical contributions, over-strong claims |
| 4 | Dimensional inconsistency inside error estimates, over-strong independence claims, missed universality ratios |

A senior advisor catches these in sequence. A one-shot AI reviewer with
a single prompt catches **at most one or two**. The fix is not a smarter
single reviewer — it is **N independent reviewers wearing different
hats, run for several rounds, with automatic routing to the right
downstream fixer.**

This skill encodes that pattern.

### What it does NOT replace

- It does **not** re-extract anchor-paper cards (those come from
  `/skill:analytic-derivation`).
- It does **not** change the user's research question. The
  **causal-graph endpoints** declared in spec §1A (source) and §1B
  (sink) — i.e. the CLASSES of physical quantities being related —
  are sacred and never auto-revised.
- It does **not** replace the human in the loop forever. The skill
  surfaces residual FATAL/CRITICAL issues, axiom-explore episodes
  whose sister-comparator marks `main_axiom_suspect`, and any
  proposed endpoint changes, so a human can decide whether to
  promote an alternative axiom set, tighten the spec, or invest in
  more derivation work.

### What changed in v2 (read before re-running on an old derivation)

v1 of this skill treated all tier-1 user_axioms (the rows of spec
§3) as sacred — the router would mark CRITICAL issues on them as
`user_axiom_locked` and remove them from the new_critical count,
which allowed the loop to declare `converged` even when the axioms
were known-bad. Empirical case study (spin-pol-fluctuation, May
2026) demonstrated this failure mode: a fundamentally wrong tier-1
axiom (ρ_2 = C_ρ β_2, missing orientation DOF) was flagged at
CRITICAL in rounds 2 and 3, locked both times, and the loop
"converged" in round 4 with the bug present.

v2 fixes this by **redefining sacred at the causal-graph endpoint
level**, not the bridging-edge level:

- **Sacred**: spec §1A source endpoint, §1B sink endpoint, §1C
  required intermediates, §1D forbidden detours
- **Revisable** (NEW): spec §3 initial bridging hypotheses, unless a
  specific row has `lock_to_user_axiom: true`

When a CRITICAL issue now targets a revisable tier-1 hypothesis,
the router dispatches an `axiom-explore` episode (Step 3.5), which
runs literature search → produces K alternative axiom-set
candidates → each candidate is exercised in a `sister-derivation`
(Step 3.6, theory-synthesizer Call type J) → results are
adjudicated by a `sister-comparator` (Step 3.7). The convergence
rule now requires `open_axiom_explore_count == 0` in addition to
`new_critical == 0`.

---

## Constants

- **INPUT_DIR**: First positional argument. Must be an existing
  directory with at least: `derivation-target.md`,
  `derivation_trace.json`, `derivation_steps.md`, `assumption_ladder.md`,
  `notation_table.md`, `verification_report.md`, `cards/paper_*.json`.
  Bootstrap step fails fast if these are missing.
- **OUTPUT_SUBDIR**: `refine/` under `INPUT_DIR`. Per-round subdirs
  `refine/round_1/`, `refine/round_2/`, …
- **MAX_ROUNDS = 4** — Hard cap on the number of refinement rounds.
  Matches the empirical convergence horizon. Override via
  `— max-rounds: N`.
- **REVIEWER_ROLES**: A fixed list `["rigor", "physics", "literature", "adversarial"]`
  dispatched in parallel each round. Override via
  `— reviewers: rigor,physics` to skip roles when a derivation is too
  early-stage to benefit from all four.
- **REVIEW_CONCURRENCY = 4** — Parallel reviewer subagents per round
  (one per role).
- **ROUTER_CONCURRENCY = 1** — Only one router subagent per round
  (issue aggregation must be serialised).
- **FIX_CONCURRENCY = 3** — Parallel downstream fixers (synthesizer
  revisions, lit-verifier dispatches, paper-editor clarifications) per
  round.
- **LIT_VERIFY_BUDGET_PER_ROUND = 3** — Per-round cap on fresh
  `lit-verifier` invocations. Round-level only; the total across all
  rounds may reach `MAX_ROUNDS × LIT_VERIFY_BUDGET_PER_ROUND` (default
  12).
- **SUBAGENT_TIMEOUT_REVIEW = 1800** — 30 min per reviewer.
- **SUBAGENT_TIMEOUT_ROUTE = 900** — 15 min for the router.
- **SUBAGENT_TIMEOUT_FIX_SYNTH = 3600** — 60 min for each
  theory-synthesizer revision (includes a fresh SymPy run).
- **SUBAGENT_TIMEOUT_FIX_LIT = 1800** — 30 min per lit-verifier.
- **SYMPY_SCRIPT_MAX_RETRIES = 3** — Hard cap on the synthesizer's
  internal SymPy debug-and-retry loop (same as analytic-derivation).
- **CONVERGENCE_DELTA = 0** — A round converges when its router
  reports `new_fatal == 0 AND new_critical == 0 AND endpoint_violation_count == 0 AND open_axiom_explore_count == 0`.
  The default is strict; set `— convergence-delta: 1` to tolerate
  one new critical issue per round (useful when reviewers keep
  finding the same issue re-stated). Note the convergence rule in
  v2 also requires `open_axiom_explore_count == 0` — see
  "What changed in v2" above.
- **AXIOM_EXPLORE_BUDGET = 2** — Per-round cap on `axiom_explore`
  dispatches. The cap is low because each episode triggers up to
  `SISTER_DERIVATION_MAX` full SymPy re-runs, making it the most
  expensive route. Override via `— axiom-explore-budget: N`.
- **AXIOM_EXPLORE_CONCURRENCY = 2** — Parallel `axiom-explorer`
  subagents per round.
- **AXIOM_EXPLORE_MAX_CANDIDATES = 3** — Maximum candidates an
  axiom-explorer may return per episode. Each is exercised as a
  sister-derivation downstream.
- **SISTER_DERIVATION_MAX = 3** — Maximum sister-derivations
  dispatched per axiom-explore episode (one per candidate).
- **SISTER_DERIVATION_CONCURRENCY = 2** — Parallel
  theory-synthesizer Call-J subagents.
- **AXIOM_AUTO_PROMOTE = false** — When the sister-comparator
  verdict is `main_axiom_suspect`, the default is to surface to the
  user with the top alternative candidate named. Set to `true` only
  for unattended overnight runs where you accept that a strongly
  supported alternative may be auto-promoted into the next round's
  main derivation. Sister-comparator still enforces the
  ≥2-independent-papers + qualitative-sister-agreement gate before
  auto-promotion takes effect.
- **AUTONOMY_MODE = "normal"** — Governs the loop's behaviour on
  partial-information halts. Two values:
  - `"normal"` (default): the loop pauses with
    `paused_pending_*` on any of: `endpoint_class_change_count > 0`
    (§1A/B/C/D class proposal), `endpoint_form_drift_count > 0`
    (§1E math-form mismatch), `axiom_explore_exhausted_count > 0`
    (no viable candidate in literature), `duplicate_count >= 3`
    (reviewer divergence), `max_rounds_reached`. Use this when you
    want to actively own every research-shaping decision.
  - `"max"`: only the truly research-question-level halts remain
    (`endpoint_class_change`, `reviewer_divergence`,
    `max_rounds_reached` after the bumped cap). The loop:
    (a) **auto-syncs §1E** of `derivation-target.md` to the actual
        derived final equation via Call-H §5d when
        `endpoint_form_drift` fires, logs `spec_form_auto_synced`
        in the audit;
    (b) **graceful-degrades** any axiom_explore episode that returns
        `no_viable_candidates` — the triggering CRITICAL is
        auto-routed to `scope` with a caveat new_statement
        ("Tier-1 hypothesis <id> in sector <X> is not independently
        verifiable in the literature; result is conditional on
        this hypothesis"), the original severity is preserved in
        audit but the episode no longer blocks convergence;
    (c) **auto-bumps `MAX_ROUNDS`** from 4 to 8 unless the user
        explicitly set `— max-rounds: N`.
  Set via `— autonomy: max`. CANNOT be combined with
  `— interactive: true` (autonomy:max implies no checkpoints;
  the skill refuses the combination at Step 0a).
- **AUTONOMY_MAX_MAX_ROUNDS = 8** — The auto-bumped default when
  `AUTONOMY_MODE == "max"` and no explicit `— max-rounds:` override.
- **SUBAGENT_TIMEOUT_AXIOM_EXPLORE = 1800** — 30 min per
  axiom-explorer (literature search + isomorphism guard + candidate
  authoring).
- **SUBAGENT_TIMEOUT_SISTER_DERIVATION = 3600** — 60 min per Call-J.
- **SUBAGENT_TIMEOUT_SISTER_COMPARATOR = 1200** — 20 min for the
  cross-sister verdict.
- **INTERACTIVE = true** — Default: pause before each round to let the
  user inspect the previous round's audit. Override
  `— interactive: false` for unattended overnight runs. Even in
  unattended mode, every round writes a full audit, so post-hoc review
  is always possible.
- **OUTPUT_LANGUAGE = "auto"** — Follows the shared output-language protocol.
- **PRESERVE_ORIGINAL = true** — The original derivation files in
  `INPUT_DIR/` are never overwritten. All revised versions live under
  `INPUT_DIR/refine/round_N/`. The "current" pointer is a symlink
  `INPUT_DIR/refine/current → round_N/` that the next round reads.

> 💡 Overrides:
> - `— max-rounds: 6` — allow more rounds if you expect deeper iteration
> - `— reviewers: rigor,physics` — skip literature and adversarial passes
> - `— interactive: false` — overnight unattended mode
> - `— lit-verify-budget: 5` — more lit searches per round
> - `— convergence-delta: 1` — tolerate one critical re-statement per round before declaring divergence
> - `— axiom-explore-budget: 3` — allow more axiom-explore episodes per round (default 2; raise cautiously, each episode runs K SymPy chains)
> - `— axiom-auto-promote: true` — let sister-comparator auto-promote a strongly supported alternative axiom set (only in unattended mode; off by default)
> - `— autonomy: max` — full unattended mode: §1E auto-syncs on form drift, axiom-explore-exhausted graceful-degrades, max-rounds bumps to 8. Only `endpoint_class_change` and `reviewer_divergence` can still halt. Cannot be combined with `— interactive: true`. Strongly recommended to also pass `— axiom-auto-promote: true` in this mode.

---

## 🚧 Main Agent Boundary Protocol — ORCHESTRATE + DIALOGUE 🚧

Same posture as `analytic-derivation`. The main agent dispatches
subagents, polls them, audits their outputs at the filesystem level,
and writes small structured JSON files. It NEVER reads derivation
prose, NEVER does algebra, NEVER writes equations.

### What the main agent MAY do

1. **Read `derivation-target.md`** — small (≤ 10 KB), user-supplied
   spec.
2. **Read small structured JSON files** for routing decisions only:
   - `refine/round_N/router_decision.json` — to decide how many fixers
     to dispatch and of which type
   - `refine/round_N/convergence.json` — to decide whether to stop
   - `refine/round_N/.fixer_outputs/*.status` — for orchestration
   - `refine/round_N/.axiom_explore/*.json` `summary` field only — to
     decide whether to dispatch sister-derivations and how many
   - `refine/round_N/.axiom_explore/*_comparison.json` — to read the
     `overall_verdict` and `recommendation` fields for cross-round
     convergence tracking; per-sister content is NOT read by main
3. **Read `paper_card.json`** under `literature-deep/paper_*/`
   (≤ 10 KB structured index, explicit exception consistent with all
   other skills in this pipeline).
4. **Print user-facing checkpoint messages** between rounds.
5. Run **shell commands** (`mkdir`, `cp`, `ln -s`, `find`, `ls`, `wc`,
   `grep`, `jq`, `test`, `sed`, `mtime` comparisons).
6. Run **Python tool scripts** — `tools/symbolic_derive.py check-deps`
   only. NEVER `tools/symbolic_derive.py run` (synthesizer's job).
7. Launch **subagents** via `Agent` (types:
   `derivation-reviewer`, `refinement-router`, `theory-synthesizer`
   (Call types G, H, J), `lit-verifier`, `paper-editor`,
   `axiom-explorer` (v2), `sister-comparator` (v2)).
8. Apply the Pattern 2 polling protocol.
9. Write **the per-round directory skeleton** and the **convergence
   summary** (`refine/refinement_audit.md` — assembled from per-round
   audits, NOT new content).
10. Update the `refine/current` symlink at the end of each accepted
    round.

### What the main agent MUST NOT do

- ❌ Read any `*_review.json`, `*_review.md`, `router_decision.md`,
  revised `derivation_steps.md`, or revised `verification_report.md`
  body. The router subagent does this. The main agent reads only the
  `verdict` / `new_fatal` / `new_critical` counts in the structured
  JSON sidecars.
- ❌ Decide whether a reviewer's issue is valid. That's the router's
  job. The main agent only counts.
- ❌ Edit any derivation file — never. All revisions flow through the
  synthesizer.
- ❌ Invoke `tools/symbolic_derive.py run`. Only the synthesizer does.
- ❌ Chain to another skill. The final report's "Suggested next
  actions" are user-facing text only.

**Bytes the main agent reads per run, target: < 100 KB total** (the
spec + N × ~5 KB router decisions + N × ~3 KB convergence JSONs +
paper_card.json reads for paper-pool resolution).

---

## Common Subagent Patterns

Same as `analytic-derivation`.

### Pattern 1 (Launch), Pattern 2 (Polling), Pattern 3 (Audit)

Refer to `analytic-derivation/SKILL.md`. The only differences:
- Polling cycle: `sleep 120 → TaskList → collect` (reviewers are
  faster than full extraction); tight loop sleep is 30 s.
- Retry budget: ONE retry on each subagent failure. On second failure,
  log `FINAL_FAILED` for that role and **continue** the round with the
  remaining reviewers. The router treats a missing reviewer as
  `verdict: skipped` (does NOT promote to accept).

---

## Workflow

The skill is **eight steps**. Steps 0–1 are one-shot bootstrap. Steps
2–6 form the body of one refinement round; they execute up to
`MAX_ROUNDS` times. Step 7 is the final report.

### Step 0a: Argument parsing & input validation [shell]

Parse `$ARGUMENTS`:
- Positional: `INPUT_DIR` (required, must exist)
- `— max-rounds: N` (default 4; auto-bumped to `AUTONOMY_MAX_MAX_ROUNDS` = 8 if `— autonomy: max` AND user did not explicitly set this)
- `— reviewers: <csv>` (default `rigor,physics,literature,adversarial`)
- `— interactive: true|false` (default `true`; FORCED to `false` if `— autonomy: max`)
- `— lit-verify-budget: N` (default 3)
- `— axiom-explore-budget: N` (default 2)
- `— axiom-auto-promote: true|false` (default `false`)
- `— autonomy: normal|max` (default `normal`; v2.1)
- `— convergence-delta: N` (default 0)
- `— language: zh|en|auto` (default `auto`)

After parsing, apply autonomy-mode coupling:

```bash
# v2.1: autonomy:max forces unattended + bumps max-rounds default
if [ "${AUTONOMY_MODE}" = "max" ]; then
    if [ "${INTERACTIVE_EXPLICITLY_SET}" = "true" ] && [ "${INTERACTIVE}" = "true" ]; then
        echo "❌ — autonomy: max cannot be combined with — interactive: true"
        echo "    autonomy:max implies unattended; the two are mutually exclusive."
        exit 1
    fi
    INTERACTIVE=false
    if [ "${MAX_ROUNDS_EXPLICITLY_SET}" != "true" ]; then
        MAX_ROUNDS=8
        echo "ℹ️  — autonomy: max: max-rounds auto-bumped from 4 to 8"
    fi
    if [ "${AXIOM_AUTO_PROMOTE}" != "true" ]; then
        echo "⚠️  — autonomy: max: AXIOM_AUTO_PROMOTE is still false."
        echo "    For true hands-off operation, also pass — axiom-auto-promote: true"
        echo "    Otherwise, every axiom-explore episode will still surface (just"
        echo "    won't block convergence on no_viable_candidates / endpoint_form_drift)."
    fi
fi
```

Validate `INPUT_DIR`:

```bash
REQUIRED=(
    "derivation-target.md"
    "derivation_trace.json"
    "derivation_steps.md"
    "assumption_ladder.md"
    "notation_table.md"
    "verification_report.md"
)
for f in "${REQUIRED[@]}"; do
    test -s "${INPUT_DIR}/${f}" || {
        echo "❌ Missing required input: ${INPUT_DIR}/${f}"
        echo "    This skill consumes the output of /skill:analytic-derivation."
        echo "    Run that skill first, or compose the directory by hand."
        exit 1
    }
done
test -d "${INPUT_DIR}/cards" && ls "${INPUT_DIR}/cards/"*.json > /dev/null 2>&1 || {
    echo "❌ ${INPUT_DIR}/cards/paper_*.json not found."
    echo "    Run /skill:analytic-derivation first."
    exit 1
}
```

### Step 0b: SymPy self-audit [shell]

```bash
python3 tools/symbolic_derive.py check-deps || {
    echo "❌ symbolic_derive.py dependency check failed."
    echo "    Fix: pip install sympy --upgrade --break-system-packages"
    exit 1
}
```

### Step 0c: Workspace setup [shell]

```bash
REFINE_DIR="${INPUT_DIR}/refine"
mkdir -p "${REFINE_DIR}"

# Anchor round_0 := the original derivation, as a frozen baseline.
# We symlink the originals; round_1 will be the first revision.
if [ ! -d "${REFINE_DIR}/round_0" ]; then
    mkdir -p "${REFINE_DIR}/round_0"
    for f in derivation-target.md derivation_trace.json derivation_steps.md \
             assumption_ladder.md notation_table.md verification_report.md \
             derivation_script.json chain_sketch.md; do
        if [ -s "${INPUT_DIR}/${f}" ]; then
            ln -sf "../../${f}" "${REFINE_DIR}/round_0/${f}"
        fi
    done
    ln -sf "../../cards" "${REFINE_DIR}/round_0/cards"
    ln -sf "../../verification" "${REFINE_DIR}/round_0/verification" 2>/dev/null || true
fi

# Point "current" at round_0 to start.
ln -sfn "round_0" "${REFINE_DIR}/current"
```

### Step 1: Round bookkeeping & convergence-state init [shell]

```bash
echo '{
  "rounds": [],
  "converged": false,
  "convergence_reason": null,
  "started_at": "'"$(date -u +%FT%TZ)"'",
  "max_rounds": '${MAX_ROUNDS}',
  "reviewers": '$(echo "${REVIEWERS}" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip().split(',')))")',
  "lit_verify_budget_per_round": '${LIT_VERIFY_BUDGET}'
}' > "${REFINE_DIR}/convergence_state.json"
```

For each `ROUND_K` from 1 to `MAX_ROUNDS`, the main agent loops over
Steps 2–6. The loop exits early on convergence.

---

### Step 2 (loop body, per round): Multi-reviewer parallel pass [Subagents: derivation-reviewer × |REVIEWERS|]

Setup:

```bash
PREV_DIR="${REFINE_DIR}/current"        # The previous accepted round
ROUND_DIR="${REFINE_DIR}/round_${ROUND_K}"
mkdir -p "${ROUND_DIR}/reviews/" "${ROUND_DIR}/.fixer_outputs/"
```

For each role in `REVIEWERS`, dispatch ONE `derivation-reviewer`
subagent (Pattern 1, concurrency `REVIEW_CONCURRENCY`). Prompt
template:

```yaml
Agent:
  description: "Round ${ROUND_K} review — role: ${ROLE}"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are operating as a `derivation-reviewer` subagent with the
    role specialisation: **${ROLE}**.

    Read your full role definition at:
        agents/subagents/derivation-reviewer.md
    Then read the role-specific addendum at:
        agents/subagents/derivation-reviewer-${ROLE}.md
    (rigor | physics | literature | adversarial)

    ## Inputs (read these in order)
    - Derivation target:    ${PREV_DIR}/derivation-target.md
    - Notation table:       ${PREV_DIR}/notation_table.md
    - Assumption ladder:    ${PREV_DIR}/assumption_ladder.md
    - Derivation steps:     ${PREV_DIR}/derivation_steps.md
    - Symbolic trace JSON:  ${PREV_DIR}/derivation_trace.json
    - Previous review:      ${PREV_DIR}/verification_report.md
    - Cards directory:      ${PREV_DIR}/cards/paper_*.json
    - All previous-round audits, if any:
        ls ${REFINE_DIR}/round_*/router_decision.json 2>/dev/null
        ls ${REFINE_DIR}/round_*/refinement_audit_round.md 2>/dev/null
      (read so you don't re-raise issues that were already addressed)

    ## Output (two files, mandatory)
    - ${ROUND_DIR}/reviews/${ROLE}_review.md
    - ${ROUND_DIR}/reviews/${ROLE}_review.json

    The MD file follows templates/DERIVATION_REVIEW_REPORT_TEMPLATE.md.
    The JSON file follows the schema in that template's appendix
    (issues[], verdict, score, role).

    ## Forbidden
    - Do NOT modify any derivation file. You are reviewing, not fixing.
    - Do NOT re-run symbolic_derive.py.
    - Do NOT chain to another subagent.
    - Do NOT skim previous-round audits and re-issue an already-fixed
      complaint. If you do, the router will tag it `duplicate` and you
      will lose convergence credit.

    ## Output language: ${output_language}
```

Polling: Pattern 2. Per-role retry: at most ONE.

Audit (Pattern 3):

```bash
EXPECTED_ROLES=( $(echo "${REVIEWERS}" | tr ',' ' ') )
for ROLE in "${EXPECTED_ROLES[@]}"; do
    F_MD="${ROUND_DIR}/reviews/${ROLE}_review.md"
    F_JSON="${ROUND_DIR}/reviews/${ROLE}_review.json"
    test -s "${F_MD}" || echo "MISSING_REVIEW: ${ROLE}"
    python3 -m json.tool < "${F_JSON}" > /dev/null || echo "INVALID_JSON: ${ROLE}"
done
```

If a role's output is `MISSING_REVIEW` after retry: write a stub JSON
`{ "role": "${ROLE}", "verdict": "skipped", "reason": "subagent FINAL_FAILED" }`
and continue.

### Step 3 (loop body): Aggregation + routing [Subagent: refinement-router × 1]

Dispatch ONE `refinement-router` subagent:

```yaml
Agent:
  description: "Round ${ROUND_K} issue routing"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 900
  prompt: |
    You are operating as a `refinement-router` subagent. Read your full
    role definition at:
        agents/subagents/refinement-router.md

    ## Inputs
    - Reviews directory: ${ROUND_DIR}/reviews/   (all *_review.json)
    - Previous-round router decisions, if any:
        ls ${REFINE_DIR}/round_*/router_decision.json 2>/dev/null
    - Per-round budget cap on lit-verifier dispatches:
        ${LIT_VERIFY_BUDGET}
    - Per-round budget cap on axiom-explore episodes:
        ${AXIOM_EXPLORE_BUDGET}
    - Autonomy mode (v2.1): ${AUTONOMY_MODE}
      Affects convergence rule: in `max`, endpoint_form_drift and
      axiom_explore_exhausted are graceful-degraded (do NOT halt);
      in `normal`, both halt as paused_pending_*. See your role
      definition §Step 6 for the full rule.
    - Original derivation context (for routing decisions):
        ${PREV_DIR}/derivation-target.md
        ${PREV_DIR}/assumption_ladder.json
        ${PREV_DIR}/derivation_trace.json   (final_equations only)

    ## Output (two files, mandatory)
    - ${ROUND_DIR}/router_decision.md    (human-readable)
    - ${ROUND_DIR}/router_decision.json  (machine-actionable)

    The JSON schema must contain, at minimum:
      {
        "round": ${ROUND_K},
        "verdict_summary": {
          "rigor": "...", "physics": "...", "literature": "...",
          "adversarial": "..."
        },
        "merged_issues": [
          {
            "issue_id": "R${ROUND_K}-I01",
            "severity": "FATAL|CRITICAL|MAJOR|MINOR",
            "raised_by": ["rigor", "physics"],
            "is_duplicate_of_round": null | <round_int>,
            "is_already_addressed": true | false,
            "summary": "...",
            "route": "alg" | "lit" | "scope" | "expansion" | "ignore",
            "fix_input": {
              # For route="alg" / "expansion":
              "synthesizer_patch": "<plain-text instruction>",
              # For route="lit":
              "claim_to_verify": "...",
              "search_terms": [...],
              # For route="scope":
              "assumption_to_revise": "<assumption_id>",
              "new_statement": "..."
            }
          },
          ...
        ],
        "new_fatal":    <int>,    # count of issues new in this round, severity FATAL
        "new_critical": <int>,    # count of issues new in this round, severity CRITICAL
        "duplicate_count": <int>,
        "lit_dispatch_count": <int>,  # MUST be <= ${LIT_VERIFY_BUDGET}
        "alg_dispatch_count": <int>,
        "scope_dispatch_count": <int>,
        "convergence_recommendation": "stop" | "continue" | "halt_for_human"
      }

    ## Routing rules (mandatory — v2; see agents/subagents/refinement-router.md for full taxonomy)
    - Issues already addressed in a prior round (check via mtime of
      assumption_ladder.json + diff of derivation_trace.json against
      previous rounds): mark `is_already_addressed: true`,
      route: "ignore". These do NOT count toward new_fatal /
      new_critical.
    - At most ${LIT_VERIFY_BUDGET} issues per round may be routed
      "lit". Above that cap, demote to "ignore" with a one-line
      "deferred_to_next_round_or_human" note.
    - At most ${AXIOM_EXPLORE_BUDGET} issues per round may be routed
      "axiom_explore". Above that cap, demote the lowest-severity
      overflow to "ignore" with note "deferred: axiom_explore
      budget exhausted".
    - When two roles raise the same issue, merge into one entry with
      raised_by:[role1, role2]. Severity = max of inputs.
    - **v2 axiom-routing rules** (replace v1's user_axiom_locked):
      1. If a row in assumption_ladder.json tier_1 has
         `lock_to_user_axiom: true`, route any CRITICAL targeting it
         to "ignore" with note "user_axiom_locked_by_explicit_request".
      2. If a reviewer's fix would change spec §1A source endpoint,
         §1B sink endpoint, §1C required intermediates, or §1D
         forbidden detours, route to "endpoint_violation" with
         `human_decision_required: true`.
      3. Otherwise, if a CRITICAL/FATAL issue targets a (revisable)
         tier-1 hypothesis, route to "axiom_explore". The fix_input
         MUST contain the full axiom_explore payload (see the JSON
         schema in agents/subagents/refinement-router.md §Step 7).
      4. Tier-2 / tier-3 issues and tier-1 MAJOR / MINOR issues
         continue to use "scope".
    - convergence_recommendation (v2 — requires all four conditions):
        - "stop" if new_fatal == 0 AND new_critical == 0 AND
                   endpoint_violation_count == 0 AND
                   open_axiom_explore_count == 0
          (open_axiom_explore_count includes cross-round episodes
           whose sister-comparator verdict file is missing OR has
           overall_verdict=="main_axiom_suspect" without an
           actioned promotion)
        - "halt_for_human" if endpoint_violation_count > 0
                          OR duplicate_count >= 3
        - "continue" otherwise (including the case where open
                                axiom_explore episodes are still
                                pending; another round will action
                                their comparator verdicts)

    ## Forbidden
    - Do NOT modify derivation files.
    - Do NOT dispatch subagents yourself; you produce JSON
      instructions, the main agent dispatches.

    ## Output language: ${output_language}
```

Polling: Pattern 2.
Audit: `router_decision.json` parses; required fields present.

#### Convergence check [shell]

> v2: convergence now also requires that no axiom_explore episode is
> still pending (i.e. its sister-comparator either has not run or
> returned `main_axiom_suspect`). The router computes
> `open_axiom_explore_count` based on the cross-round comparison
> verdict files; the shell here cross-checks for paranoia.

```bash
NEW_FATAL=$(jq '.new_fatal' "${ROUND_DIR}/router_decision.json")
NEW_CRIT=$(jq '.new_critical' "${ROUND_DIR}/router_decision.json")

# v2.1: separate class-change (always halts) from form-drift (graceful in autonomy:max)
EP_CLASS=$(jq '.endpoint_class_change_count // 0' "${ROUND_DIR}/router_decision.json")
EP_FORM=$(jq '.endpoint_form_drift_count // 0' "${ROUND_DIR}/router_decision.json")
AE_EXHAUSTED=$(jq '.axiom_explore_exhausted_count // 0' "${ROUND_DIR}/router_decision.json")
OPEN_AE=$(jq '.open_axiom_explore_count // 0' "${ROUND_DIR}/router_decision.json")
REC=$(jq -r '.convergence_recommendation' "${ROUND_DIR}/router_decision.json")
NOTE=$(jq -r '.convergence_note // ""' "${ROUND_DIR}/router_decision.json")
DUP=$(jq '.duplicate_count' "${ROUND_DIR}/router_decision.json")

# Shell-side double-check of axiom-explore open status across all rounds
PENDING_AE=$(find "${REFINE_DIR}" -path '*/.axiom_explore/*_comparison.json' \
                  -exec jq -r 'select(.overall_verdict=="main_axiom_suspect") | .episode_id' {} \; 2>/dev/null | wc -l)
MISSING_VERDICTS=$(find "${REFINE_DIR}" -path '*/.axiom_explore/*_input.json' \
                  -exec sh -c 'EID=$(basename "$1" _input.json); COMP="$(dirname "$1")/${EID}_comparison.json"; [ -s "$COMP" ] || echo "$EID"' _ {} \; 2>/dev/null | wc -l)
EFFECTIVE_OPEN_AE=$(( PENDING_AE + MISSING_VERDICTS ))

# v2.1: autonomy:max relaxes form-drift and axiom-exhausted
if [ "${AUTONOMY_MODE}" = "max" ]; then
    EFFECTIVE_EP_BLOCKERS=${EP_CLASS}        # class-change still blocks
    # form_drift handled by Call-H §5d, no convergence block
    # axiom_explore_exhausted handled by Call-H §6.5, subtract from open-AE
    EFFECTIVE_OPEN_AE=$(( EFFECTIVE_OPEN_AE - AE_EXHAUSTED ))
    [ "${EFFECTIVE_OPEN_AE}" -lt 0 ] && EFFECTIVE_OPEN_AE=0
else
    EFFECTIVE_EP_BLOCKERS=$(( EP_CLASS + EP_FORM ))
fi

if [ "${REC}" = "stop" ] \
   && [ "${NEW_FATAL}" -le "${CONVERGENCE_DELTA}" ] \
   && [ "${NEW_CRIT}" -le "${CONVERGENCE_DELTA}" ] \
   && [ "${EFFECTIVE_EP_BLOCKERS}" -eq 0 ] \
   && [ "${EFFECTIVE_OPEN_AE}" -eq 0 ]; then
    echo "✅ Convergence reached at round ${ROUND_K}"
    SHOULD_BREAK=1
elif [ "${EP_CLASS}" -gt 0 ]; then
    echo "🛑 Endpoint-CLASS change proposed (count=${EP_CLASS}); halting for human."
    echo "    Note: this halt is NEVER overridden, even with — autonomy: max,"
    echo "          because it changes the research question itself."
    echo "    Reason: ${NOTE}"
    SHOULD_BREAK=1
elif [ "${EP_FORM}" -gt 0 ] && [ "${AUTONOMY_MODE}" != "max" ]; then
    echo "🛑 Endpoint FORM drift detected (count=${EP_FORM}); halting for human."
    echo "    §1E math form is stale relative to derived final equation."
    echo "    To auto-sync §1E and continue automatically, re-run with — autonomy: max."
    SHOULD_BREAK=1
elif [ "${AE_EXHAUSTED}" -gt 0 ] && [ "${AUTONOMY_MODE}" != "max" ]; then
    echo "🛑 Axiom-explore exhausted (count=${AE_EXHAUSTED}); halting for human."
    echo "    No viable alternative axioms exist in independent literature."
    echo "    To graceful-degrade these to scope caveats and continue, re-run with — autonomy: max."
    SHOULD_BREAK=1
elif [ "${EFFECTIVE_OPEN_AE}" -gt 0 ]; then
    echo "⚠️  ${EFFECTIVE_OPEN_AE} axiom-explore episode(s) still open (suspect or missing verdict)."
    echo "    Convergence blocked; one more round will run to action sister-comparator recommendations."
    SHOULD_BREAK=0   # do NOT break; one more round resolves it
elif [ "${REC}" = "halt_for_human" ] && [ "${DUP}" -ge 3 ]; then
    echo "🛑 Reviewer divergence at round ${ROUND_K}: same issue raised ${DUP} times across rounds."
    echo "    Note: this halt is NEVER overridden, even with — autonomy: max,"
    echo "          because reviewer divergence signals a real unresolvable issue."
    SHOULD_BREAK=1
fi
```

The exit headline at the end of the loop is then one of (v2.1):

| Condition | Headline | Audit `converged` field | Overridable by `— autonomy: max`? |
|---|---|---|---|
| `stop` + all blockers zero | `converged` | `true` | n/a |
| endpoint_class_change present | `paused_pending_endpoint_class_decision` | `false` | **NO — always halts** |
| endpoint_form_drift present (normal mode only) | `paused_pending_endpoint_form_drift` | `false` | YES — autonomy:max auto-syncs §1E |
| axiom_explore_exhausted present (normal mode only) | `paused_pending_axiom_exhausted` | `false` | YES — autonomy:max graceful-degrades |
| Open AE episodes (suspect or unverdictful) | continues to next round | n/a | n/a |
| Open AE still after MAX_ROUNDS | `paused_pending_axiom_review` | `false` | partial — autonomy:max bumps MAX_ROUNDS to 8 |
| Reviewer divergence (`duplicate_count >= 3`) | `paused_pending_reviewer_divergence` | `false` | **NO — always halts** |
| MAX_ROUNDS reached, no other blocker | `max_rounds_reached_without_convergence` | `false` | partial — autonomy:max bumps to 8 |

Only the first condition produces a `true` for `converged`. The
"NEVER overridden" halts are the deliberate human-in-the-loop
checkpoints: changing the research question (§1A/B/C/D) and
unresolvable reviewer divergence are not engineering problems, so
no autonomy flag relaxes them.

If `SHOULD_BREAK=1`, the round's fixers are still dispatched (to
process the non-FATAL nice-to-haves), then the loop terminates after
this round. If we converged with zero issues at all, fixers are
trivially empty and the round dir just contains the all-clear
verdict.

#### Checkpoint (interactive, unless INTERACTIVE=false)

Main agent prints:

> ✦ **Round ${ROUND_K} review summary**
>
> Reviews completed: ${N_OK}/${N_TOTAL}
> New FATAL issues:    ${NEW_FATAL}
> New CRITICAL issues: ${NEW_CRIT}
> Duplicates (already addressed): ${DUP}
> Router recommendation: **${REC}**
>
> Issues to be fixed in this round:
> {compact list of merged_issues, one line each: "[severity] [route] summary"}
>
> Please reply with:
> - **go** — dispatch fixers and proceed
> - **skip lit** — proceed without dispatching lit-verifier (e.g. you
>   know the literature claim is settled)
> - **skip N** — skip a specific issue (note: this is a deferral, the
>   final report will list it as user-deferred)
> - **stop** — terminate the loop now (write the report with what we
>   have)
> - **edit router: <change>** — patch the router decision JSON (rare;
>   use when the router classified an issue wrong)

Wait for user response. In non-interactive mode, default to `go`.

### Step 3.5 (loop body, v2): Axiom-explore dispatch [Subagents: axiom-explorer × N]

> **NEW in v2.** This step runs only if the router routed at least
> one issue to `axiom_explore` (which it does for CRITICAL/FATAL
> issues targeting a revisable tier-1 hypothesis — see
> `refinement-router.md` for the routing rules). When triggered, it
> precedes the regular Step 4 fixer dispatch because its output
> (sister-comparator verdicts in Step 3.7) may downgrade an issue
> from CRITICAL to MAJOR before Step 4 runs.

Prepare per-episode input files [shell]:

```bash
N_EPISODES=$(jq '[.merged_issues[] | select(.route=="axiom_explore")] | length' \
             "${ROUND_DIR}/router_decision.json")

if [ "${N_EPISODES}" -eq 0 ]; then
    echo "Step 3.5: no axiom_explore episodes this round; skipping."
else
    mkdir -p "${ROUND_DIR}/.axiom_explore/"

    python3 << 'PYEOF'
import json, os
ROUND_DIR = os.environ["ROUND_DIR"]
PREV_DIR  = os.environ["PREV_DIR"]
INPUT_DIR = os.environ["INPUT_DIR"]

with open(f"{ROUND_DIR}/router_decision.json") as f:
    decision = json.load(f)
with open(f"{PREV_DIR}/derivation-target.md") as f:
    spec_md = f.read()
with open(f"{PREV_DIR}/assumption_ladder.json") as f:
    ladder = json.load(f)
with open(f"{PREV_DIR}/derivation_trace.json") as f:
    main_trace = json.load(f)

# Parse endpoint blocks from the spec MD. The skill provides a
# helper at tools/spec_parser.py (extracts the §1A / §1B / §1C / §1D
# tagged blocks); if the tool is missing, fall back to a permissive
# regex parser that yields the four blocks as raw markdown.
try:
    from tools.spec_parser import parse_endpoint_blocks
    endpoints = parse_endpoint_blocks(spec_md)
except ImportError:
    endpoints = {"source_endpoint": None, "sink_endpoint": None,
                 "required_intermediates": [],
                 "forbidden_detours": [],
                 "warning": "spec_parser unavailable; explorer will read spec MD directly"}

# Anchor papers to ignore (same as Step 4b in analytic-derivation)
with open(f"{INPUT_DIR}/.selected_papers.json") as f:
    anchors = ["arXiv:"+p["arxiv_id"] for p in json.load(f) if p.get("arxiv_id")]

# Final equation from main trace
final_eq_latex = main_trace.get("final_equations", [{}])[-1].get("latex", "")

for issue in decision.get("merged_issues", []):
    if issue.get("route") != "axiom_explore":
        continue
    episode_id = issue["fix_input"]["axiom_explore_episode_id"]
    payload = {
        "schema_version": "1",
        "episode_id": episode_id,
        "triggered_by_issue": issue["issue_id"],
        "reviewer_summary": issue["fix_input"]["reviewer_summary"],
        "target_hypothesis_ids": issue["fix_input"]["target_hypothesis_ids"],
        "current_hypothesis_statements": {
            # The ladder schema (from analytic-derivation Call type D)
            # uses `tier_1_user_axioms` as the key, and each entry has
            # fields {id, label, statement, source, status,
            # role_in_chain}. `latex` and `provenance` may be absent in
            # older runs; fall back gracefully.
            h_id: {
                "statement": next((a["statement"]
                                   for a in ladder.get("tier_1_user_axioms", [])
                                   if a["id"] == h_id), None),
                "latex":     next((a.get("latex", "")
                                   for a in ladder.get("tier_1_user_axioms", [])
                                   if a["id"] == h_id), None),
                "provenance": next((a.get("provenance",
                                          a.get("source", "phenomenological"))
                                    for a in ladder.get("tier_1_user_axioms", [])
                                    if a["id"] == h_id), "phenomenological"),
                "lock_to_user_axiom": next((a.get("lock_to_user_axiom", False)
                                            for a in ladder.get("tier_1_user_axioms", [])
                                            if a["id"] == h_id), False),
            }
            for h_id in issue["fix_input"]["target_hypothesis_ids"]
        },
        "endpoint_isomorphism_anchors": endpoints,
        "anchor_papers_to_ignore": anchors,
        "max_candidates_to_return": int(os.environ.get("AXIOM_EXPLORE_MAX_CANDIDATES", 3)),
        "current_final_equation_latex": final_eq_latex,
        "output_paths": {
            "json": f"{ROUND_DIR}/.axiom_explore/{episode_id}.json",
            "md":   f"{ROUND_DIR}/.axiom_explore/{episode_id}.md",
        },
        "output_language": os.environ.get("output_language", "auto"),
    }
    with open(f"{ROUND_DIR}/.axiom_explore/{episode_id}_input.json", "w") as f:
        json.dump(payload, f, indent=2)
    print("prepared input for episode", episode_id)
PYEOF
fi
```

Dispatch one `axiom-explorer` subagent per episode, concurrency
`AXIOM_EXPLORE_CONCURRENCY`:

```yaml
Agent:
  description: "Axiom-explore: ${EPISODE_ID}"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are operating as an `axiom-explorer` subagent. Read your full
    role definition at:
        agents/subagents/axiom-explorer.md

    ## Inputs
    - Your input file: ${ROUND_DIR}/.axiom_explore/${EPISODE_ID}_input.json
      (contains target hypothesis IDs, endpoint isomorphism anchors,
       anchor papers to ignore, output paths)
    - The current target spec: ${PREV_DIR}/derivation-target.md
      (read §1A–§1E and §3 for context)
    - The current assumption ladder JSON: ${PREV_DIR}/assumption_ladder.json
      (for the targeted tier-1 hypothesis statements)
    - The current main derivation trace's final_equations only:
        ${PREV_DIR}/derivation_trace.json

    ## Tools you may invoke (self-contained — no skill chaining)
    - WebSearch (built-in)
    - python3 tools/arxiv_fetch.py search "..." --max 8
    - python3 tools/semantic_scholar_fetch.py search "..." --max 8
      (skip silently if tool missing)
    - python3 tools/exa_search.py "..." --max 6
      (skip silently if tool missing)

    ## Outputs (both mandatory, paths in the input file)
    - ${ROUND_DIR}/.axiom_explore/${EPISODE_ID}.json
    - ${ROUND_DIR}/.axiom_explore/${EPISODE_ID}.md
      (follows templates/AXIOM_CANDIDATES_TEMPLATE.md)

    ## Forbidden
    - Do NOT read literature-deep/ (those are the anchor papers).
    - Do NOT invoke symbolic_derive.py (that's Call J).
    - Do NOT chain to another subagent.
    - Do NOT exceed 30 min wall clock.

    ## Output language: ${output_language}
```

Polling: Pattern 2 with `AXIOM_EXPLORE_CONCURRENCY` instead of 4.

Audit:

```bash
for EPISODE_ID in $(jq -r '.merged_issues[] | select(.route=="axiom_explore") | .fix_input.axiom_explore_episode_id' "${ROUND_DIR}/router_decision.json"); do
    F_JSON="${ROUND_DIR}/.axiom_explore/${EPISODE_ID}.json"
    F_MD="${ROUND_DIR}/.axiom_explore/${EPISODE_ID}.md"
    test -s "$F_JSON" || { echo "MISSING: $F_JSON"; FAIL=1; }
    test -s "$F_MD"   || { echo "MISSING: $F_MD"; FAIL=1; }
    python3 -m json.tool < "$F_JSON" > /dev/null || { echo "INVALID JSON: $F_JSON"; FAIL=1; }
done
```

For each episode, read ONLY the `summary` field of the JSON:
- If `explorer_verdict == "candidates_found"`: proceed to Step 3.6
  for this episode.
- If `explorer_verdict == "no_viable_candidates"`:
  - In `AUTONOMY_MODE == "normal"`: skip Step 3.6 for this episode;
    record the episode in
    `${REFINE_DIR}/.axiom_explore_exhausted.jsonl` (one line per
    exhausted episode: `{episode_id, target_hypothesis_ids,
    round_K, triggering_issue}`); the convergence check will surface
    this as `paused_pending_axiom_exhausted`.
  - In `AUTONOMY_MODE == "max"` (v2.1 graceful degrade): record in
    `${REFINE_DIR}/.axiom_explore_exhausted.jsonl` AS ABOVE, but
    ALSO write a follow-on scope patch directly to
    `${ROUND_DIR}/.fixer_outputs/${TRIGGERING_ISSUE_ID}_scope_patch.json`
    with the schema:
    ```json
    {
      "schema_version": "1",
      "issue_id": "${TRIGGERING_ISSUE_ID}",
      "assumption_id": "<U1|U3|... — the targeted tier-1 id>",
      "old_statement": "<verbatim from current ladder>",
      "new_statement": "<old statement> [v2.1 graceful-degrade: tier-1 hypothesis is not independently verifiable in the literature for the sector covered by spec §5; result is therefore conditional on this hypothesis. Axiom-explore episode ${EPISODE_ID} returned no_viable_candidates.]",
      "new_status": "user_axiom_conditional",
      "graceful_degrade_from_axiom_explore": "${EPISODE_ID}",
      "auto_generated_by": "SKILL Step 3.5 autonomy:max graceful-degrade"
    }
    ```
    The downstream Step 4c paper-editor fixer is then a no-op (the
    patch is already prepared); Call-H §5 will apply this patch like
    any other scope patch. The triggering CRITICAL issue is recorded
    in audit as `auto-degraded` (original severity preserved for
    traceability) and the episode counts toward
    `axiom_explore_exhausted_count` in the router output. The
    convergence rule in `max` mode subtracts this count from
    `open_axiom_explore_count` so it does not block.
- If `explorer_verdict == "endpoint_underspecified"`: HALT the
  loop in BOTH modes (this is a real spec gap, not an autonomy
  question), surface to user: spec §1A or §1B is too narrow for
  exploration; user must broaden or lock the hypothesis explicitly.

### Step 3.6 (loop body, v2): Sister-derivation dispatch [Subagent: theory-synthesizer × K, Call type J]

For each episode where `explorer_verdict == "candidates_found"`,
dispatch one Call-J synthesizer per candidate (up to
`SISTER_DERIVATION_MAX`), concurrency `SISTER_DERIVATION_CONCURRENCY`:

```yaml
Agent:
  description: "Sister-derivation: ${EPISODE_ID}/${CANDIDATE_ID}"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are operating as a `theory-synthesizer` subagent, Call type J
    (sister_derivation). Read your full role definition at:
        agents/subagents/theory-synthesizer.md
    Read the Call-J addendum at:
        agents/subagents/theory-synthesizer-call-j.md

    ## Inputs
    - Axiom-explorer episode output:
        ${ROUND_DIR}/.axiom_explore/${EPISODE_ID}.json
      (locate your candidate by candidate_id="${CANDIDATE_ID}";
       read its replaces[] and adds[] blocks)
    - Previous-round derivation script: ${PREV_DIR}/derivation_script.json
    - Previous-round trace:             ${PREV_DIR}/derivation_trace.json
    - Notation table JSON:              ${PREV_DIR}/notation_table.json
    - Assumption ladder JSON:           ${PREV_DIR}/assumption_ladder.json
    - Target spec (for endpoint sanity re-check):
        ${PREV_DIR}/derivation-target.md
    - SymPy tool: tools/symbolic_derive.py

    ## Outputs (three files, all mandatory)
    - ${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_${CANDIDATE_ID}_script.json
    - ${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_${CANDIDATE_ID}_trace.json
    - ${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_${CANDIDATE_ID}_sister.md

    ## Forbidden
    - Do NOT modify PREV_DIR files.
    - Do NOT read other sister scripts in .sister_outputs/.
    - Do NOT also try to fix other reviewer issues (those go to Call G).
    - Do NOT change endpoint classes; refuse if the candidate would.

    ## Output language: ${output_language}
```

Audit per sister:

```bash
test -s "${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_${CANDIDATE_ID}_trace.json" || FAIL=1
test -s "${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_${CANDIDATE_ID}_sister.md"  || FAIL=1
# Note: overall_status: failed is a VALID outcome for Call J.
# Only file-presence is required for audit pass.
```

### Step 3.7 (loop body, v2): Sister-comparator [Subagent: sister-comparator × N_episodes]

For each episode where Step 3.6 ran, dispatch ONE sister-comparator:

```yaml
Agent:
  description: "Sister-comparator: ${EPISODE_ID}"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1200
  prompt: |
    You are operating as a `sister-comparator` subagent. Read your
    full role definition at:
        agents/subagents/sister-comparator.md

    ## Inputs
    - Main trace:           ${PREV_DIR}/derivation_trace.json
    - All sister traces:    ${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_*_trace.json
    - All sister narratives: ${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_*_sister.md
    - Axiom-explorer output: ${ROUND_DIR}/.axiom_explore/${EPISODE_ID}.json
    - Router decision:       ${ROUND_DIR}/router_decision.json
    - Spec for endpoint context:  ${PREV_DIR}/derivation-target.md (§1A–§1E)
    - Assumption ladder JSON:     ${PREV_DIR}/assumption_ladder.json

    ## Auto-promote setting
    AXIOM_AUTO_PROMOTE = ${AXIOM_AUTO_PROMOTE}

    ## Outputs (two files, mandatory)
    - ${ROUND_DIR}/.axiom_explore/${EPISODE_ID}_comparison.json
    - ${ROUND_DIR}/.axiom_explore/${EPISODE_ID}_comparison.md

    ## Forbidden
    - Do NOT re-run SymPy.
    - Do NOT dispatch any subagent.
    - Do NOT auto-promote when AXIOM_AUTO_PROMOTE=false; in that
      case the recommendation is always `surface_to_user_with_top_alternative`.

    ## Output language: ${output_language}
```

Audit + post-processing:

```bash
for EPISODE_ID in $(jq -r '.merged_issues[] | select(.route=="axiom_explore") | .fix_input.axiom_explore_episode_id' "${ROUND_DIR}/router_decision.json"); do
    F="${ROUND_DIR}/.axiom_explore/${EPISODE_ID}_comparison.json"
    test -s "$F" || { echo "MISSING: $F"; continue; }
    VERDICT=$(jq -r '.overall_verdict' "$F")
    REC=$(jq -r '.recommendation' "$F")
    echo "Episode ${EPISODE_ID}: verdict=${VERDICT}, recommendation=${REC}"

    # If auto-promote triggered, queue the promotion for Call H (Step 5)
    if [ "${REC}" = "auto_promote_to_main_next_round" ]; then
        CAND_ID=$(jq -r '.recommended_alternative_candidate_id' "$F")
        echo "{\"episode_id\":\"${EPISODE_ID}\",\"candidate_id\":\"${CAND_ID}\"}" \
            >> "${ROUND_DIR}/.axiom_explore/.pending_promotions.jsonl"
    fi
done
```

The comparison verdicts feed into:
- This round's `open_axiom_explore_count` calculation (for
  convergence: any episode without a comparison verdict OR with
  `overall_verdict: main_axiom_suspect` and recommendation not
  actioned counts as OPEN).
- The Step 5 (Call H) merge: pending promotions in
  `.pending_promotions.jsonl` are applied to the next round's
  main derivation.
- The final refinement_audit (Step 7): every episode appears with
  its candidates, sister traces, and verdict.

---

### Step 4 (loop body): Dispatch fixers in parallel [Subagents: synthesizer / lit-verifier / paper-editor]

Read `router_decision.json`. For each merged issue with
`is_already_addressed: false` and `route` ∈ {`alg`, `expansion`,
`lit`, `scope`} (NOT `axiom_explore` — those were handled in
Step 3.5–3.7), dispatch the corresponding subagent. Maintain
`FIX_CONCURRENCY` cap across all fixer types.

#### 4a. Algorithmic / expansion fixers → theory-synthesizer

```yaml
Agent:
  description: "Round ${ROUND_K} alg fix: ${ISSUE_ID}"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are operating as a `theory-synthesizer` subagent, Call type G
    (revise_for_review). Read your full role definition at:
        agents/subagents/theory-synthesizer.md
    Read the Call-G addendum:
        agents/subagents/theory-synthesizer-call-g.md

    ## Inputs
    - Previous-round derivation script: ${PREV_DIR}/derivation_script.json
    - Previous-round trace:             ${PREV_DIR}/derivation_trace.json
    - Notation table JSON:              ${PREV_DIR}/notation_table.json
    - Assumption ladder JSON:           ${PREV_DIR}/assumption_ladder.json
    - Router's instruction for this issue:
        ${ROUND_DIR}/router_decision.json
        (locate the entry with issue_id="${ISSUE_ID}", read its
         "fix_input.synthesizer_patch" field)
    - SymPy tool: tools/symbolic_derive.py

    ## Workflow
    1. Apply the patch to derivation_script.json. The patch is a
       plain-text instruction like:
         "After step S2, insert a step that splits rho_2 into
          rho_bar + delta_rho, then propagate delta_rho through
          the rest of the chain. Drop rho_bar from the variance
          computation."
       Use the schema you already know from Call type F.
    2. Run:
         python3 tools/symbolic_derive.py run \\
             --script ${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_script.json \\
             --output ${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_trace.json
    3. If trace.overall_status == "failed", diagnose, fix, re-run.
       Up to ${SYMPY_SCRIPT_MAX_RETRIES} attempts.
    4. Write a short markdown summary:
         ${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_fix.md
       with sections:
         ## Issue (one paragraph)
         ## Change applied (script diff, prose, ≤ 5 lines)
         ## Verification (SymPy checks added or that now pass)

    ## Forbidden
    - Do NOT modify any file outside ${ROUND_DIR}/.fixer_outputs/.
    - Do NOT touch tier-1 user_axioms in the assumption ladder.
    - Do NOT chain to another subagent.

    ## Output language: ${output_language}
```

Audit:

```bash
test -s "${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_script.json" || FAIL=1
test -s "${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_trace.json"  || FAIL=1
test -s "${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_fix.md"      || FAIL=1
```

#### 4b. Literature fixers → lit-verifier

```yaml
Agent:
  description: "Round ${ROUND_K} lit verify: ${ISSUE_ID}"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are operating as a `lit-verifier` subagent (same as Step 4b of
    /skill:analytic-derivation). Read your full role definition at:
        agents/subagents/lit-verifier.md

    ## Inputs
    - The router's claim-to-verify and search-terms:
        Read ${ROUND_DIR}/router_decision.json
        Locate entry issue_id="${ISSUE_ID}"; use its fix_input.claim_to_verify
        and fix_input.search_terms.
    - Anchor papers to IGNORE (these were already the basis for the
      derivation and by definition cannot verify a gap):
        $(jq -r '.[].arxiv_id' ${INPUT_DIR}/.selected_papers.json)

    ## Output (mandatory)
    - ${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_lit_check.json
    Schema: same as analytic-derivation Step 4b output
    (see agents/subagents/lit-verifier.md "Write output" section).

    ## Forbidden
    - Same as in analytic-derivation Step 4b.
    - Time budget: 25 minutes hard.

    ## Output language: ${output_language}
```

Audit: file exists, parses, has `status` ∈ {`confirmed`, `partial`,
`refuted`, `not_found`, `verifier_error`, `timeout`}.

#### 4c. Scope / assumption-ladder fixers → paper-editor

```yaml
Agent:
  description: "Round ${ROUND_K} scope fix: ${ISSUE_ID}"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 900
  prompt: |
    You are a `paper-editor` subagent making a SCOPE-ONLY edit to the
    assumption ladder. You are NOT writing algebra; you are tightening
    a regime statement, weakening a claim, or adding an explicit
    caveat.

    ## Inputs
    - Existing ladder MD:   ${PREV_DIR}/assumption_ladder.md
    - Existing ladder JSON: ${PREV_DIR}/assumption_ladder.json
    - Router's instruction:
        Read ${ROUND_DIR}/router_decision.json
        Locate entry issue_id="${ISSUE_ID}"; use its fix_input.assumption_to_revise
        and fix_input.new_statement.

    ## Output (mandatory)
    - ${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_scope.md
      A diff-style summary: old statement → new statement.
    - ${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_scope_patch.json
      A JSON object:
        {
          "assumption_id": "...",
          "old_statement": "...",
          "new_statement": "...",
          "old_status": "...",
          "new_status": "needs_human_review" | "partially_verified" | "user_axiom"
        }

    ## Forbidden
    - Do NOT touch tier-1 user_axiom statements (only their status).
    - Do NOT add new mathematical steps (that's a synthesizer fix).
    - Do NOT chain to another subagent.

    ## Output language: ${output_language}
```

### Step 5 (loop body): Merge fixers → new round artifact [Subagent: theory-synthesizer — Call type H]

After all fixers complete, dispatch ONE synthesizer to MERGE every
patch into a single coherent revised derivation:

```yaml
Agent:
  description: "Round ${ROUND_K} merge"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are operating as a `theory-synthesizer` subagent, Call type H
    (merge_fix_outputs). Read:
        agents/subagents/theory-synthesizer.md
        agents/subagents/theory-synthesizer-call-h.md

    ## Inputs
    - Previous round full artifacts: ${PREV_DIR}/*.{md,json}
    - All per-issue fixer outputs:   ${ROUND_DIR}/.fixer_outputs/*
    - Router decision:                ${ROUND_DIR}/router_decision.json
    - Autonomy mode (v2.1):           ${AUTONOMY_MODE}
      In `max`: Call-H §5d auto-syncs derivation-target.md §1E for any
      endpoint_form_drift routes, AND §6.5 graceful-degrades any
      axiom_explore_exhausted episodes to scope caveats. In `normal`:
      §5d and §6.5 are no-ops (the SKILL halts before Call-H is
      reached for those routes; defensive coding here in case the
      router emits them anyway).

    ## Outputs (mandatory — all rebuilt for this round)
    - ${ROUND_DIR}/derivation_script.json   (merged of all *_script.json)
    - ${ROUND_DIR}/derivation_trace.json    (RE-RUN sympy on the merged script)
    - ${ROUND_DIR}/derivation_steps.md      (regenerated from new trace)
    - ${ROUND_DIR}/assumption_ladder.md     (with scope-fix patches applied)
    - ${ROUND_DIR}/assumption_ladder.json
    - ${ROUND_DIR}/verification/lit_check_*.json (newly added items copied
      into a flat dir for compatibility with downstream readers)
    - ${ROUND_DIR}/refinement_audit_round.md  (per-round audit:
        for each issue: what was claimed, what was done, what was deferred)

    Also COPY-FORWARD the files that did not change this round
    (notation_table.md, derivation-target.md, cards/) by symlinking
    from PREV_DIR.

    ## Workflow
    1. Start from PREV_DIR's derivation_script.json.
    2. **(v2)** Check for pending axiom-promotions:
       `${ROUND_DIR}/.axiom_explore/.pending_promotions.jsonl`
       If present, for each line {episode_id, candidate_id}:
       - Read the corresponding sister script:
           ${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_${CANDIDATE_ID}_script.json
       - Promote it: replace the targeted tier-1 hypothesis steps in
         the master script with the candidate's `replaces[]` + `adds[]`
         edits. The sister script's downstream chain is the new
         baseline for those steps.
       - Update the assumption ladder JSON: mark the replaced
         hypothesis as `promoted_to_alternative`, with provenance
         pointing at the axiom_candidates.json entry.
       - Note in refinement_audit_round.md: "Promoted candidate C{ID}
         from episode {EID}: A{N} replaced — see axiom_candidates.json
         provenance for citation chain."
    3. For each `_script.json` fixer in `.fixer_outputs/`, splice its
       step(s) into the master script, preserving step numbering
       continuity. If a Call-G fixer's target hypothesis was just
       promoted in step 2 (i.e. the original hypothesis no longer
       exists), SKIP that fixer with a note in the audit
       ("issue {ID} obviated by axiom promotion").
    4. Run SymPy ONCE on the merged script (the per-fixer SymPy runs
       were partial; only this merge run is canonical).
    5. Write derivation_steps.md from the new trace (verbatim, same
       discipline as Call type F).
    6. Merge scope patches into assumption_ladder.{md,json}.
    7. Aggregate lit_check_*.json files into ${ROUND_DIR}/verification/.
    8. **(v2)** Copy axiom_explore episode outputs to
       ${ROUND_DIR}/.axiom_explore_archive/ for the final report's
       provenance trail.
    9. Write refinement_audit_round.md including a §A "Axiom-explore
       episodes this round" section listing each episode's verdict
       and (if any) the promoted candidate.

    ## Forbidden
    - Do NOT modify PREV_DIR files. Only write into ROUND_DIR.
    - Do NOT silently drop an issue. If a fixer's output is missing or
      corrupt, write a "DEFERRED: <issue_id> — reason" line in the
      audit.

    ## Output language: ${output_language}
```

Audit:

```bash
EXPECTED=(
    "${ROUND_DIR}/derivation_script.json"
    "${ROUND_DIR}/derivation_trace.json"
    "${ROUND_DIR}/derivation_steps.md"
    "${ROUND_DIR}/assumption_ladder.md"
    "${ROUND_DIR}/assumption_ladder.json"
    "${ROUND_DIR}/refinement_audit_round.md"
)
for f in "${EXPECTED[@]}"; do
    test -s "$f" || { echo "MISSING: $f"; FAIL=1; }
done
[ -z "$FAIL" ] && \
    [ "$(jq -r '.overall_status' "${ROUND_DIR}/derivation_trace.json")" = "ok" ]
```

If the merged SymPy run fails (`overall_status: failed`), the round
is INVALID — surface to the user with the trace excerpt and STOP.
The previous round remains the canonical answer.

### Step 6 (loop body): Update current pointer + verify regression-free [shell]

If Step 5 passed audit:

```bash
ln -sfn "round_${ROUND_K}" "${REFINE_DIR}/current"

# Append to the convergence log
python3 -c "
import json
with open('${REFINE_DIR}/convergence_state.json') as f: state = json.load(f)
with open('${ROUND_DIR}/router_decision.json') as f: rd = json.load(f)
state['rounds'].append({
    'round': ${ROUND_K},
    'new_fatal': rd['new_fatal'],
    'new_critical': rd['new_critical'],
    'duplicate_count': rd['duplicate_count'],
    'issues_addressed': rd['alg_dispatch_count'] + rd['lit_dispatch_count'] + rd['scope_dispatch_count'],
    'convergence_recommendation': rd['convergence_recommendation'],
})
# v2.1: convergence + autonomy:max headline computation
autonomy = '${AUTONOMY_MODE}'
open_ae = rd.get('open_axiom_explore_count', 0)
ep_class = rd.get('endpoint_class_change_count', 0)
ep_form  = rd.get('endpoint_form_drift_count', 0)
ae_exhausted = rd.get('axiom_explore_exhausted_count', 0)

# Effective blockers after autonomy:max relaxations
if autonomy == 'max':
    eff_ep_blockers = ep_class                       # class still blocks
    eff_open_ae = max(0, open_ae - ae_exhausted)     # exhausted are graceful-degraded
else:
    eff_ep_blockers = ep_class + ep_form
    eff_open_ae = open_ae

if (rd['convergence_recommendation'] == 'stop'
        and rd['new_fatal'] == 0
        and rd['new_critical'] == 0
        and eff_ep_blockers == 0
        and eff_open_ae == 0):
    state['converged'] = True
    state['convergence_reason'] = 'no new FATAL/CRITICAL, no open axiom-explore, no endpoint blocker'
    state['convergence_headline'] = 'converged'
    state['autonomy_mode'] = autonomy
elif ep_class > 0:
    # NEVER overridable by autonomy:max
    state['converged'] = False
    state['convergence_reason'] = (
        f'endpoint_class_change_proposed (count={ep_class}); '
        'user must decide on §1A/§1B/§1C/§1D revision. '
        'Not overridable by autonomy:max.'
    )
    state['convergence_headline'] = 'paused_pending_endpoint_class_decision'
elif ep_form > 0 and autonomy != 'max':
    state['converged'] = False
    state['convergence_reason'] = (
        f'endpoint_form_drift (count={ep_form}); §1E does not match '
        'derived final equation. Re-run with — autonomy: max to '
        'auto-sync §1E and continue.'
    )
    state['convergence_headline'] = 'paused_pending_endpoint_form_drift'
elif ae_exhausted > 0 and autonomy != 'max':
    state['converged'] = False
    state['convergence_reason'] = (
        f'axiom_explore_exhausted (count={ae_exhausted}); literature '
        'has no viable alternative for one or more tier-1 hypotheses. '
        'Re-run with — autonomy: max to graceful-degrade to scope caveats.'
    )
    state['convergence_headline'] = 'paused_pending_axiom_exhausted'
elif eff_open_ae > 0:
    state['converged'] = False
    state['convergence_reason'] = (
        f'{eff_open_ae} axiom-explore episode(s) still open: '
        'sister-comparator returned main_axiom_suspect or no verdict yet'
    )
    state['convergence_headline'] = 'paused_pending_axiom_review'
elif rd['convergence_recommendation'] == 'halt_for_human' and rd.get('duplicate_count', 0) >= 3:
    # NEVER overridable by autonomy:max
    state['converged'] = False
    state['convergence_reason'] = (
        f'reviewer divergence: same issue raised {rd["duplicate_count"]} times '
        'across rounds. Not overridable by autonomy:max.'
    )
    state['convergence_headline'] = 'paused_pending_reviewer_divergence'

state['autonomy_mode'] = autonomy

if ${ROUND_K} >= ${MAX_ROUNDS} and not state.get('converged'):
    state['convergence_reason'] = state.get('convergence_reason') or 'max_rounds_reached'
    state['convergence_headline'] = state.get('convergence_headline') or 'max_rounds_reached_without_convergence'
with open('${REFINE_DIR}/convergence_state.json', 'w') as f: json.dump(state, f, indent=2)
"
```

If converged or max rounds: break out of the loop, go to Step 7.

---

### Step 7: Final refinement report [Subagent: paper-editor]

Dispatch ONE paper-editor to compose the consolidated refinement
report:

```yaml
Agent:
  description: "Compose refinement audit report"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are the report writer for the derivation-refine-loop skill.

    ## Inputs (every file that exists)
    - ${REFINE_DIR}/convergence_state.json
      (read the v2 convergence_headline field — it determines TL;DR)
    - ${REFINE_DIR}/round_*/router_decision.md
    - ${REFINE_DIR}/round_*/router_decision.json
    - ${REFINE_DIR}/round_*/refinement_audit_round.md
    - ${REFINE_DIR}/round_*/reviews/*_review.md
    - ${REFINE_DIR}/round_*/derivation_steps.md (only the LATEST one,
      for the "Current derivation" section)
    - ${REFINE_DIR}/round_*/assumption_ladder.md (only the LATEST one)
    - ${REFINE_DIR}/round_*/verification/lit_check_*.json (all rounds)
    - **v2 NEW**: ${REFINE_DIR}/round_*/.axiom_explore/*.{json,md}
      (every episode's candidate catalog and comparison verdict)
    - **v2 NEW**: ${REFINE_DIR}/round_*/.sister_outputs/*_sister.md
      (sister-derivation narratives; do NOT load the trace JSONs —
      use the sister.md side-by-side equation block instead)
    - Template: templates/REFINEMENT_AUDIT_TEMPLATE.md
    - Output language: ${output_language}

    ## Output (mandatory)
    - ${REFINE_DIR}/refinement_audit.md (the consolidated report)

    Required sections (follow template; v2 sections marked NEW):
      §0 TL;DR — use convergence_state.convergence_headline VERBATIM
                 as the headline state ("converged" /
                 "paused_pending_axiom_review" / etc.); do NOT
                 paraphrase it as "converged" if the headline says
                 otherwise.
      §1 Convergence narrative (round-by-round)
      §2 Per-round summary table
      §3 Issue heat map (which reviewer caught what)
      §4 Current derivation (cite latest derivation_steps.md by symlink)
      §5 Open issues (anything still flagged at the final round) —
         INCLUDES axiom-explore episodes whose verdict was
         `main_axiom_suspect` and not auto-promoted; each such item
         must show the recommended alternative candidate and the
         papers cited as its provenance.
      §6 Literature evidence added during the loop (both lit_check
         results AND axiom_candidates provenance citations, listed
         separately so the human knows which papers were used to
         VERIFY existing claims vs which were used to PROPOSE
         alternative claims).
      §7 **v2 NEW**: Axiom-explore audit — per-episode subsection
         with: triggering issue, candidates returned (with
         confidence + provenance), sister-derivation outcomes,
         comparator verdict, and whether the candidate was promoted,
         surfaced, or rejected. This is the v2 version's most
         important diagnostic — readers should be able to see at a
         glance which axioms were challenged, what alternatives were
         considered, and what evidence settled it.
      §8 Suggested next actions (user-facing; never auto-invoked)

    ## Forbidden
    - Do NOT introduce any equation that did not appear in some round's
      derivation_trace.json.
    - Do NOT chain to another skill (Suggested next actions are
      user-facing text only).
```

Audit:

```bash
test -s "${REFINE_DIR}/refinement_audit.md" || exit 1
grep -q '^## 0. TL;DR'              "${REFINE_DIR}/refinement_audit.md" || exit 1
grep -q '^## 2. Per-round summary'  "${REFINE_DIR}/refinement_audit.md" || exit 1
grep -q '^## 5. Open issues'        "${REFINE_DIR}/refinement_audit.md" || exit 1
# v2: §7 axiom-explore audit must be present even if no episodes ran
# (in which case it says "no axiom-explore episodes this run").
grep -q '^## 7. Axiom-explore audit' "${REFINE_DIR}/refinement_audit.md" || exit 1
# v2: TL;DR headline must verbatim quote convergence_state.convergence_headline
HL=$(jq -r '.convergence_headline' "${REFINE_DIR}/convergence_state.json")
grep -q "${HL}" "${REFINE_DIR}/refinement_audit.md" || {
    echo "❌ §0 TL;DR did not include the convergence_headline '${HL}' verbatim"
    exit 1
}
```

#### Final print to user

```
✦ Done — derivation refined through ${N_ROUNDS} rounds.

  Headline state:        ${CONVERGENCE_HEADLINE}
  Convergence reason:    ${CONVERGENCE_REASON}
  Total FATAL    fixed:  ${TOTAL_FATAL_FIXED}
  Total CRITICAL fixed:  ${TOTAL_CRITICAL_FIXED}
  Lit-verifier dispatches:  ${TOTAL_LIT}
  Axiom-explore episodes:   ${TOTAL_AE}
    └─ candidates considered: ${TOTAL_AE_CANDIDATES}
    └─ sister derivations:    ${TOTAL_SISTERS}
    └─ promoted to main:      ${TOTAL_AE_PROMOTED}
    └─ surfaced for human:    ${TOTAL_AE_SURFACED}
  Open issues still flagged: ${N_OPEN}

  Final derivation: ${REFINE_DIR}/current/derivation_steps.md
  Audit report:     ${REFINE_DIR}/refinement_audit.md

  {one-line TL;DR — must include the headline state verbatim if it is
   anything other than "converged"}

  Suggested next actions are in §8 of the audit. They are
  USER-FACING text only; this skill never invokes them.
```

> ⚠️ **v2 behavioural note**: If the headline state is anything other
> than `converged`, the user should NOT treat the current derivation
> as a finished product. Specifically:
> - `paused_pending_axiom_review`: open axiom-explore episodes have
>   surfaced alternative axioms; user should review §7 of the audit
>   and decide whether to re-run with `— axiom-auto-promote: true`
>   or to manually replace the affected §3 hypothesis.
> - `paused_pending_endpoint_decision`: at least one reviewer
>   proposed changing the research question itself (§1A/§1B); this
>   is by design never auto-actioned.
> - `paused_pending_reviewer_divergence`: same issue keeps being
>   re-raised; either the issue is genuinely hard or the reviewer
>   prompts need tuning.
> - `max_rounds_reached_without_convergence`: raise `— max-rounds`
>   and resume.

---

## Key Rules Summary

1. **Original is sacrosanct.** `INPUT_DIR/*` files are read-only.
   Every revision lives under `INPUT_DIR/refine/round_N/`. The
   `current` symlink advances atomically after each successful round.
2. **Multiple reviewers, one round.** All reviewer roles in
   `REVIEWERS` are dispatched in parallel each round; the router
   merges their outputs. A missing reviewer (FINAL_FAILED) does not
   block convergence — it's treated as `verdict: skipped` and the
   remaining roles continue.
3. **Issues are routed mechanically.** The router classifies each
   issue into `alg / lit / scope / expansion / ignore`. The main
   agent does not interpret reviewer prose — it dispatches whatever
   the router says.
4. **Sacred = causal-graph endpoints (v2).** Spec §1A source
   endpoint, §1B sink endpoint, §1C required intermediates, and §1D
   forbidden detours are PROTECTED — the router never auto-revises
   them; any reviewer issue that would change them is routed to
   `endpoint_violation` and surfaces to the human. Spec §3 bridging
   hypotheses are REVISABLE — a CRITICAL issue on a tier-1
   hypothesis is routed to `axiom_explore`, which triggers the
   axiom-explorer → sister-derivation → sister-comparator pipeline
   (Steps 3.5 → 3.6 → 3.7). A specific §3 row can still be locked
   on a per-row basis via `lock_to_user_axiom: true`.
5. **Convergence requires four conditions (v2).** A round converges
   when its router reports
   `new_fatal == 0 AND new_critical == 0 AND endpoint_violation_count == 0 AND open_axiom_explore_count == 0`.
   The fourth condition is new in v2: an open axiom-explore
   episode (no sister-comparator verdict yet, or verdict =
   `main_axiom_suspect` with no promotion actioned) blocks
   convergence. Override new_critical tolerance via
   `— convergence-delta: N`.
6. **Hard caps prevent runaway.** Max rounds, max reviewers,
   max lit-verifier dispatches per round, max SymPy retries per
   fixer.
7. **Main agent NEVER reads review prose.** Same boundary as
   analytic-derivation. The main agent reads `verdict` and counts;
   the router reads review bodies.
8. **No skill chaining.** Final report's "Suggested next actions"
   are user-facing text.
9. **Resume-friendly.** Re-invoking the skill on the same
   `INPUT_DIR` picks up at the highest existing round and proceeds.
   To force a clean re-run from round 1, delete
   `INPUT_DIR/refine/`.
10. **Pre-flight SymPy self-audit.** Step 0b runs
    `check-deps` before any subagent spend.

---

## Relationship to the rest of the pipeline

| When you are… | Use this skill | Or this OTHER skill |
|---|---|---|
| Building a derivation from scratch | — | `/skill:analytic-derivation` |
| Hardening an existing derivation through multi-round adversarial review | **`/skill:derivation-refine-loop`** | — |
| Writing the formal proposal that consumes a refined derivation | — | `/skill:research-proposal` |
| Mid-experiment, need a literature precedent NOW | — | `/skill:research-debug` |

`derivation-refine-loop` is the only skill in this pipeline that runs
**multiple consecutive subagent rounds on the same artifact**, with
automatic routing of reviewer findings to symbolic fixers,
literature verifiers, or scope-tightening edits. It exists because
empirical evidence shows that one-shot reviews of long derivation
chains miss roughly N - 1 of the first N classes of errors, where
N ≈ 4 in practice.

---

## Pattern reference: why four reviewer roles and not one

A single "expert reviewer" prompt is poorly suited to the
multi-faceted nature of theoretical-physics derivations. The four
roles in this skill each catch a class of error that the others
systematically miss:

| Role | Catches | Misses (without other roles) |
|---|---|---|
| `rigor` | Algebraic mistakes, dimensional inconsistencies, validity-domain of identities, dropped signs, mis-applied independence | Whether the chosen ensemble is the right one; whether claimed scaling laws agree with literature |
| `physics` | Wrong ensemble, hidden assumptions, single-source vs multi-source attribution, double counting, regime extrapolation | Whether the algebra is internally consistent; whether the literature evidence supports the claim |
| `literature` | Missing canonical references, mis-attributed scaling laws, inconsistency with published results | Mathematical sloppiness; physical assumption errors that the literature also makes |
| `adversarial` | Edge cases, alternative interpretations, hidden universality structures, missed dimensionless ratios | Routine bookkeeping; literature consistency |

The four roles are intentionally redundant in some areas — that's
how the router catches "raised by both rigor and physics" and treats
them as higher confidence.

---

*This skill is designed to run for hours per derivation. Start it before
you sleep; review the round-by-round audit in the morning.*
