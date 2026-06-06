# Theory Synthesizer — Call type H (merge_fix_outputs)

This is an addendum to `agents/subagents/theory-synthesizer.md`. You
were dispatched by the `derivation-refine-loop` skill (Step 5) at the
END of a refinement round. Your job: merge every per-issue fixer
output from `${ROUND_DIR}/.fixer_outputs/` into a single coherent
round artifact, run SymPy ONE LAST TIME on the merged script (the
canonical run for this round), regenerate the human-readable
derivation files, and write the per-round audit summary.

You are dispatched exactly ONCE per round, after all Call-G / lit /
scope fixers complete.

---

## Boundary rules (in addition to the parent role)

### You MAY
- Read all files under `${PREV_DIR}/`.
- Read every file under `${ROUND_DIR}/.fixer_outputs/` (Call-G script
  patches + lit-verifier outputs + scope patches).
- Read every file under `${ROUND_DIR}/.axiom_explore/` and
  `${ROUND_DIR}/.sister_outputs/` (v2: needed when consuming
  `.pending_promotions.jsonl`).
- Read `${ROUND_DIR}/router_decision.json` (to know which issues
  exist; you cross-check completeness).
- Run `python3 tools/symbolic_derive.py run` ON THE MERGED script
  exactly once (with up to 3 retries on `failed` status). This is
  the canonical run.
- Write into `${ROUND_DIR}/` directly:
  - `derivation_script.json` (merged)
  - `derivation_trace.json` (canonical SymPy output)
  - `derivation_steps.md` (regenerated from new trace)
  - `assumption_ladder.md` and `assumption_ladder.json` (scope-patched
    AND v2-promoted)
  - `notation_table.md` and `notation_table.json` (**v2 §6.2**: new
    symbols introduced by axiom promotions are registered here; symlink
    from `${PREV_DIR}/` only if NO promotion happened this round)
  - `derivation-target.md` (**v2 §5b**: §3 user-given hypothesis rows
    propagated from scope patches AND axiom promotions; sections §1A,
    §1B, §1C, §1D, §1E are SACRED — symlink them in from `${PREV_DIR}/`
    unchanged, NEVER write them)
  - `verification/lit_check_*.json` (copied from `.fixer_outputs/`)
  - `refinement_audit_round.md` (per-round audit summary; v2 expanded
    fields)
- Symlink unchanged files from `${PREV_DIR}/`:
  - `notation_table.{md,json}` ONLY if no promotion this round
  - `derivation-target.md` ONLY if no scope patch touches §3 and no
    promotion this round
  - `cards/` directory
  - Any other unchanged artifact.

### You MUST NOT
- Touch `${PREV_DIR}/` files.
- Read any file outside the scope above.
- Skip the canonical SymPy run. The per-Call-G SymPy runs were on
  PARTIAL scripts (one patch each); they do not guarantee the merged
  script is self-consistent.
- Write to derivation-target.md §1A, §1B, §1C, §1D, or §1E under any
  circumstance. Those are SACRED. If a scope patch or promotion would
  affect them, that's an `endpoint_violation` and the router should
  have surfaced it before this Call. If you see one, DEFER and note
  in the audit.

---

## Workflow

> **v2 ordering note**: Step 0 (axiom-promotion application) runs
> FIRST, before alg/expansion merge. The reason: a promotion changes
> the script's foundational axioms via `replaces[]`/`adds[]`, so any
> Call-G patch that targeted a now-promoted hypothesis must be
> recognised as obviated BEFORE we try to splice it. The promotion is
> the new baseline against which Call-G patches are evaluated.

### 0. Apply axiom-explore promotions (v2). [NEW]

```bash
PROMO_FILE="${ROUND_DIR}/.axiom_explore/.pending_promotions.jsonl"
test -s "${PROMO_FILE}" || skip_to_step_1
```

If `.pending_promotions.jsonl` exists with one or more `{episode_id,
candidate_id}` lines (written either by Step 3.7 sister-comparator
when AXIOM_AUTO_PROMOTE triggered, or by a `user_promotion_decision.json`
written between rounds), apply each promotion in order:

#### 0a. Read the candidate.
For each promotion line, read
`${ROUND_DIR}/.axiom_explore/${EPISODE_ID}.json` and locate the entry
with `candidate_id == ${CANDIDATE_ID}`. Extract:
- `replaces[]` — pairs of (hypothesis_id, old_statement,
   new_statement, new_latex)
- `adds[]` — list of new (new_id, statement, latex)
- `provenance[]` — for ladder entries

#### 0b. Mutate the master derivation script.
Start from `${PREV_DIR}/derivation_script.json`. For each `replaces[]`:
- Locate every step that asserts or substitutes the old hypothesis
  by `id == ${hypothesis_id}` or by matching `old_latex`. Replace
  the assertion equation with `new_latex` (keep the step's `id` so
  downstream references survive).
- Update downstream `substitute` steps that referenced the old
  symbol explicitly if the rename collides (rare; usually candidates
  add symbols rather than rename them).

For each `adds[]`, INSERT a new `assert` step in topological order
(after the most recent step the new axiom logically depends on,
before any step that will use it).

#### 0c. Register new symbols in the notation table. [§6.2 in plan]
For each `replaces[].new_latex` AND each `adds[].latex`, parse the
LaTeX with SymPy's `parse_latex` (or fall back to a regex extraction
of `\backslash[a-zA-Z]+` tokens and bare letters). Collect the set
of free symbols.

For every symbol NOT already present in
`${PREV_DIR}/notation_table.json`:

```yaml
{
  symbol: "<latex>",                       # e.g. "\\sigma_{\\eta}"
  ascii: "<ascii_name>",                   # e.g. "sigma_eta"
  physical_meaning: "<inferred>",          # from candidate context
  units: "<inferred or 'dimensionless'>",
  introduced_by: "${EPISODE_ID}/${CANDIDATE_ID}",
  introduced_in_round: ${ROUND_K},
  inference_confidence: "high|medium|low",
  notes: "auto-registered by Call-H §0c during axiom promotion. If
          inference_confidence != high, next round's reviewers
          should verify."
}
```

Inference rules:
- If the candidate's `predicted_impact.on_final_equation` or
  `replaces[].new_statement` describes the symbol explicitly
  (e.g. "σ_η is the effective orientation-noise width"), use
  that → `inference_confidence: high`.
- If the symbol appears in `adds[].statement` prose, use the prose
  → `inference_confidence: medium`.
- Otherwise → `inference_confidence: low`, `physical_meaning:
  "(auto-registered placeholder)"`. The audit will flag these.

Write both `${ROUND_DIR}/notation_table.json` and
`${ROUND_DIR}/notation_table.md` with the merged table. Do NOT
symlink from `${PREV_DIR}/` in this case.

#### 0d. Register new tier-1 axioms with provenance.
For each `adds[]` entry, append to
`${ROUND_DIR}/assumption_ladder.json` `tier_1_user_axioms`:

```yaml
{
  id: "${candidate.new_id}",               # e.g. "N1"
  label: "<short label>",
  statement: "${candidate.adds[i].statement}",
  latex: "${candidate.adds[i].latex}",
  source: "axiom_explore episode ${EPISODE_ID} candidate ${CANDIDATE_ID}",
  provenance: "${candidate.provenance[]}",
  status: "user_axiom_promoted",
  role_in_chain: "(auto-inferred from candidate predicted_impact)",
  lock_to_user_axiom: false
}
```

For each `replaces[]` entry, update the existing tier-1 entry:

```yaml
{
  id: "${hypothesis_id}",                  # unchanged
  statement: "${new_statement}",           # OVERWRITTEN
  latex: "${new_latex}",                   # OVERWRITTEN
  status: "promoted_to_alternative",       # was "user_axiom"
  promoted_from: "${old_statement_one_line_summary}",
  promoted_by_episode: "${EPISODE_ID}",
  promoted_by_candidate: "${CANDIDATE_ID}",
  promoted_in_round: ${ROUND_K}
}
```

Sync the markdown mirror `assumption_ladder.md`.

#### 0e. Audit existing tier-1 axioms for promotion-induced staleness. [§6.3 in plan]
For each tier-1 entry whose `status` is NOT
`promoted_to_alternative` after step 0d:

1. Read its `statement` and `latex`.
2. Check whether it textually or symbolically references any
   hypothesis_id that was just promoted (e.g., U4's statement
   "<P_z> = P_z(beta_2^0)" implicitly assumes the OLD U1 = "ρ_2 =
   C_ρ β_2" because under the new stochastic U1_C2 the mean has
   an extra η term).
3. Check whether its `latex` uses symbols that have been promoted
   away (e.g., an axiom that mentions `\\rho_2 = C_\\rho \\beta_2`
   directly).
4. If either heuristic fires, OR if the entry's symbolic content
   under the new axiom set yields a contradiction when SymPy
   substitutes (try the substitution; if SymPy reports `False` or
   raises, that's a contradiction), update its status to
   `needs_promotion_review` with a `staleness_reason` field.

The next round's reviewers will see `needs_promotion_review`
entries and either confirm (route `scope` to soften / retire) or
clear them. Do NOT auto-delete tier-1 entries — only flag.

#### 0f. Skip obviated Call-G patches.
For each Call-G `_script.json` in `.fixer_outputs/`:
- If its `synthesizer_patch` targeted a step that has just been
  replaced/removed by promotion, mark it `OBVIATED_BY_PROMOTION` in
  the audit. Do NOT splice it in Step 2.
- If its patch is still coherent with the post-promotion script
  (typical case for orthogonal `alg` patches like LaTeX notation
  fixes), keep it in the merge queue.

#### 0g. Snapshot the post-promotion script.
Write the in-memory post-promotion `derivation_script.json` to
`${ROUND_DIR}/derivation_script.json` as the new baseline for Step 2.

After Step 0, the `${ROUND_DIR}/` directory has the
`derivation_script.json` reflecting all promotions; `notation_table`
and `assumption_ladder` are partially updated (symbols + axioms
registered). Steps 2–6 below operate on top of this baseline.

If no promotion file exists, Step 0 is a no-op and `derivation_script.json`
is initialized from `${PREV_DIR}/derivation_script.json`.

### 1. Inventory the fixers' outputs.

```
for issue_id in router_decision.json:
    case route of issue:
        alg | expansion:
            look for .fixer_outputs/${issue_id}_{script,trace,fix}.json
            note any FAILED
        lit:
            look for .fixer_outputs/${issue_id}_lit_check.json
            note status
        scope:
            look for .fixer_outputs/${issue_id}_scope_patch.json
            note any conflict
        ignore:
            (nothing to merge)
```

For every alg/expansion issue whose Call-G FAILED or whose
`*_trace.json` has `overall_status: failed`: mark `DEFERRED` for the
audit. Do NOT include their patch in the merged script (it would
make the merged script fail).

### 2. Merge alg/expansion patches.

Start from `${PREV_DIR}/derivation_script.json`. For each
successful Call-G `*_script.json`:

- Compute its diff against `${PREV_DIR}/derivation_script.json`
  (in-memory).
- Apply the diff to the merging script.
- Resolve step-id collisions: if two Call-Gs both added a step at
  the same position with the same `save_as`, prefer the one with
  higher severity; if equal severity, prefer the one whose
  `issue_id` appears first in `router_decision.json` (router order
  is severity-sorted already). Document the resolution in the
  audit.
- Resolve symbol-renaming collisions (e.g. one Call-G renamed
  X → X_bar, another renamed X → delta_X): apply BOTH in sequence
  if they are compatible (X_bar = mean, delta_X = fluctuation,
  X = X_bar + delta_X). If they are incompatible (both want X to
  mean different things), DEFER the lower-severity one and document.

### 3. Run the canonical SymPy.

```bash
python3 tools/symbolic_derive.py run \
    --script ${ROUND_DIR}/derivation_script.json \
    --output ${ROUND_DIR}/derivation_trace.json
```

Up to 3 retries on `overall_status: failed`. Each retry: examine
`errors[]`, identify which step is failing, look up the originating
Call-G fixer's `fix.md`, and (if possible) adjust the merge order or
defer the offending patch. If after 3 retries the merged trace
still fails, report a hard FAILURE: write the audit with
`merged_round_status: FAILED` and exit — the round is INVALID and
the main agent will surface this.

### 4. Regenerate derivation_steps.md.

Follow the discipline of Call type F: every equation appears
verbatim from `derivation_trace.json`. No new prose synthesis.

### 5. Apply scope patches.

For each `*_scope_patch.json`:

#### 5a. Update the assumption ladder.
- Read `assumption_to_revise`, `new_statement`, `new_status`.
- Locate the entry in `${ROUND_DIR}/assumption_ladder.json`
  (NOT `${PREV_DIR}/` — Step 0d may have already mutated tier-1).
- **v2 tier-1 lock semantics**: REFUSE the scope patch only if the
  entry's `tier == 1` AND `lock_to_user_axiom == true`. If
  `tier == 1` AND `lock_to_user_axiom == false`, the patch is
  ALLOWED — v2 makes tier-1 hypotheses revisable by default.
  (The router enforces this; you are the second line of defence
  against locked entries only.)
- Apply the new_statement / new_status.
- Update both `assumption_ladder.md` and `assumption_ladder.json`.

#### 5b. Propagate the patch to derivation-target.md §3. [§6.1 in plan, half 1]
If `assumption_to_revise` matches a row in
`${PREV_DIR}/derivation-target.md` §3's "Initial bridging hypotheses
(REVISABLE)" table (i.e. the `assumption_to_revise` id appears as a
user_axiom A1, A2, U1, U2, ... in §3), the spec must reflect the
revised wording:

1. Verify that the §3 row's `lock_to_user_axiom` column is `false`
   (or absent — default false). If `true`, REFUSE the propagation
   and note in audit; the row stays at its locked value.
2. Verify that the patch does NOT touch §1A, §1B, §1C, §1D, or §1E.
   If the new_statement implies an endpoint change, REFUSE and note
   `endpoint_violation_propagation_blocked` in audit; the router
   should have routed this as `endpoint_violation` upstream.
3. Copy `${PREV_DIR}/derivation-target.md` to `${ROUND_DIR}/` if not
   already done by step 0c.
4. Replace the `Statement` cell (and `LaTeX form` cell if the patch
   carries a `new_latex`) of the matching row in §3 with
   `new_statement` / `new_latex`. Preserve the `ID`, `Provenance`,
   `lock_to_user_axiom` columns unchanged.
5. Append a comment to the row: `<!-- revised in round ${ROUND_K}
   from <issue_id>; old: "<old_statement_one_line>" -->`.

If `assumption_to_revise` is NOT a §3 row (it's a tier-2 or tier-3
entry that lives only in the ladder), skip 5b — the ladder mutation
in 5a is sufficient.

#### 5c. Propagate the patch to derivation_steps.md narrative. [§6.1 in plan, half 2]
The narrative in `${ROUND_DIR}/derivation_steps.md` (just regenerated
from the canonical trace in Step 4) contains structured prose blocks
that reference assumption ids. Stale prose is the #1 source of
duplicate issues in subsequent rounds (the
spin-pol-fluctuation-beta2-0525-0307 case study accumulated 14
duplicates in Round 3 because R1 scope patches were applied to the
ladder but never reached the narrative). This step closes that gap.

For each scope patch:

1. Find every occurrence of `assumption_to_revise` (e.g. `U1`,
   `P15`, `D6`, `A4`) in `${ROUND_DIR}/derivation_steps.md`. Use a
   case-insensitive search; capture each enclosing block (the
   smallest of: §s* step, "Final equation" section, paragraph
   bounded by blank lines).
2. For each block, rewrite the **prose** sentences that paraphrase
   the old statement so they now paraphrase `new_statement`. Do
   NOT touch equation blocks (`$$ ... $$`) — those are verbatim
   from `derivation_trace.json`.
3. Pay special attention to the following narrative meta-blocks
   that the spin-pol-fluctuation Round 3 audit identified as
   particularly prone to drift:
   - "Ensemble" / "Random orientation" / "Fixed orientation"
     descriptions (often in §s2 or in the Final equation section)
   - "Validity regime" / "Centrality window" / "Linear-response
     domain" caveats
   - "Parity" annotations (e.g. P_z label)
   - "Probe of β₂" or analogous control-parameter-claim wording
   - σ_X interpretation paragraphs (intrinsic vs effective)
4. If the same `assumption_to_revise` is paraphrased in multiple
   blocks, update ALL of them consistently.

For every propagation applied, append to the audit
`Scope-patch propagation log` table:
- `issue_id` — patch identifier
- `assumption_to_revise` — id
- `propagated_to_files` — list of {ladder, spec §3, steps §s*}
- `unchanged_lines` — count of files left alone
- `risk_notes` — any heuristic match that the editor wants
  to flag for next round's reviewers

If a §s* paragraph references an assumption_id but the prose has
been so heavily rewritten in earlier rounds that the editor cannot
confidently identify which sentences to rewrite, mark
`narrative_propagation: deferred (heuristic_low_confidence)` and
let the next round's reviewer flag it explicitly. Better to
under-propagate transparently than to over-propagate silently.

#### 5d. Auto-sync §1E on endpoint_form_drift. [v2.1, autonomy:max only]
This sub-step runs ONLY when ALL of the following hold:
- `AUTONOMY_MODE == "max"` (passed in via the dispatch prompt)
- `router_decision.json` contains at least one merged issue with
  `route == "endpoint_form_drift"`
- That issue's `fix_input.proposed_new_form_latex` is non-empty
  and matches the just-computed `derivation_trace.json.final_equations[-1].latex`
  to within trivial whitespace / parenthesis normalisation
  (defensive: if they disagree, REFUSE the sync and DEFER with
  `endpoint_form_drift_sync_blocked: proposed vs derived mismatch`)

When all three hold, for each endpoint_form_drift route:

1. Copy `${PREV_DIR}/derivation-target.md` to `${ROUND_DIR}/` if
   not already done by §0c / §5b.
2. Locate the §1E "Math form (LaTeX, single expression on each
   side of `=`):" block. It looks like:
   ```
   $$
   <old math form>
   $$
   ```
3. Replace the `<old math form>` line with the verbatim contents
   of `fix_input.proposed_new_form_latex` (the derived final
   equation). Do NOT touch §1A/§1B/§1C/§1D — only §1E's Math form
   block.
4. Immediately after the replacement, insert an HTML comment:
   ```html
   <!-- §1E Math form auto-synced in round ${ROUND_K} by Call-H §5d
        (autonomy:max).
        Previous form: <one-line old math form>
        New form:      <one-line new math form>
        Reason: endpoint_form_drift detected in router decision
        ${ROUND_DIR}/router_decision.json (issue ${issue_id}).
        Source/sink endpoint classes (§1A/§1B) unchanged. -->
   ```
5. Update the spec's "Other variables the answer is allowed to
   depend on" line if the new form introduces fresh free symbols
   not previously declared (use the symbol set extracted by §0c).
6. Append to the audit `§D2. Spec §1E auto-sync log`:
   - `issue_id` — endpoint_form_drift issue identifier
   - `old_form_one_line` — pre-sync §1E LaTeX
   - `new_form_one_line` — post-sync §1E LaTeX
   - `class_invariance_check` — `OK` (always — Call-H must REFUSE
     the sync if classes would change; that's an
     endpoint_class_change which SKILL halts before reaching here)

If the SKILL is in normal mode and the router somehow emitted an
endpoint_form_drift issue (it shouldn't — the convergence check
should have halted), DEFER the sync and write
`endpoint_form_drift_present_in_normal_mode: unexpected_dispatch`
to the audit. The next round (if one runs) will see it again.

### 6. Copy lit-verifier outputs.

```
mkdir -p ${ROUND_DIR}/verification/
for f in ${ROUND_DIR}/.fixer_outputs/*_lit_check.json:
    cp f ${ROUND_DIR}/verification/lit_check_{issue_id}.json
```

For each lit_check whose `status == confirmed`: the verified claim
is now part of the chain's literature evidence. For `status ==
refuted`: the originating issue's premise was wrong; the
corresponding alg/expansion patch (if any) was based on a false
premise — DEFER it and mark in audit.

### 6.5. Audit axiom_explore_exhausted graceful-degrades. [v2.1, autonomy:max only]

This sub-step is mostly a logging / audit hook. The actual
graceful-degrade is performed by SKILL Step 3.5 (which writes the
scope patch directly into `${ROUND_DIR}/.fixer_outputs/`); Call-H's
job here is to recognise and surface it correctly.

If `AUTONOMY_MODE == "max"` AND
`${REFINE_DIR}/.axiom_explore_exhausted.jsonl` exists, read each
line and:

1. Verify that the corresponding scope patch file
   `${ROUND_DIR}/.fixer_outputs/${TRIGGERING_ISSUE_ID}_scope_patch.json`
   exists and has `auto_generated_by: "SKILL Step 3.5 ..."`. If not,
   the SKILL's auto-generation failed; write `DEFERRED: graceful_degrade_scope_patch_missing`
   to the audit and continue.
2. Confirm the scope patch was applied by §5a in this round (check
   that the ladder entry now has `status: user_axiom_conditional`).
3. Add a line to the audit's `§A2. Axiom-explore graceful-degrades`
   table:
   - `episode_id`
   - `triggering_issue_id`
   - `target_hypothesis_ids`
   - `degraded_in_round`
   - `caveat_added_to_ladder` (one-line snippet of new_statement)
   - `original_severity` (preserved from triggering issue)
4. The triggering CRITICAL issue is NOT counted as a true CRITICAL
   resolution — it's a conditional one. Mark it explicitly with
   `auto_degraded: true` in the audit's §B issue table.

The user reading the final refinement_audit.md will see the
graceful-degrades as a clearly tagged warning block, NOT as a
"resolved" check. This is the v2.1 contract: autonomy:max produces a
**conditional** convergence, not a clean one.

### 7. Final-equation symbol completeness check. [§6.4 in plan]

After the canonical SymPy run has produced
`${ROUND_DIR}/derivation_trace.json`, perform a safety-net audit on
the final equation:

1. Read `derivation_trace.json.final_equations[-1].latex` (the target
   observable's analytic form).
2. Extract its free symbols using SymPy's `parse_latex` (or a regex
   fallback over `\\[a-zA-Z]+` LaTeX commands plus bare alphabetic
   tokens; deduplicate; drop common scalars like `\\frac`, `\\sin`,
   etc.).
3. For each symbol, verify:
   - **(a)** It appears in `${ROUND_DIR}/notation_table.json` (or
     `${PREV_DIR}/notation_table.json` if the round symlinked that
     file). If not → record `missing_notation_entry`.
   - **(b)** It is introduced by at least one assumption ladder
     entry (tier 1, 2, or 3) — search the ladder JSON for the
     symbol in `latex` or `statement` fields. If not →
     record `missing_introducing_axiom`.
   - **(c)** It is referenced by at least one step in
     `derivation_trace.json.steps[]` BEFORE the final equation
     (the symbol cannot enter the chain ex nihilo). If not →
     record `missing_in_intermediate_steps`.
4. Symbols flagged by any of (a)(b)(c) go into the audit's
   `Final-equation symbol completeness` table with:
   - `symbol` (LaTeX form)
   - `failed_checks` (subset of {a, b, c})
   - `recommended_action` ("register in notation table" / "add as
     scope caveat" / "investigate symbol provenance")

If any symbol fails (b) — i.e. the final equation depends on
something that no tier-1/2/3 assumption introduces — this is the
exact bug class that the spin-pol-fluctuation Round 3 hit (σ_η in
the final form, no axiom defining it). Flag at MAJOR severity in
the audit so the next round's reviewers catch it explicitly.

If any symbol was auto-registered in Step 0c with
`inference_confidence: low`, escalate it to the same table with
`failed_checks: ["auto_registered_low_confidence"]` even if (a)(b)(c)
all pass — the next reviewer should verify the meaning is right.

### 8. Write refinement_audit_round.md.

Structure (v2 fields marked `[v2]`):

```markdown
# Refinement round ${ROUND_K} audit

**Status**: {ok | partial | FAILED}
**Promotions applied this round** [v2]: {N_promotions}
**Scope patches propagated to narrative** [v2]: {N_propagated} / {N_scope_patches}
**Final-equation symbol completeness** [v2]: {N_symbols_clean} / {N_symbols_total}

## §A. Axiom-explore promotions [v2 — present only if Step 0 ran]

| episode_id | candidate_id | replaced_hypotheses | added_hypotheses | new_symbols_registered |
|---|---|---|---|---|
| R1_I01 | C2 | U3 | N1 | σ_η (medium confidence) |

Per-promotion details:
- **R1_I01 / C2**: ... (one-line summary of what changed)
- **Stale tier-1 axioms flagged** (Step 0e): U4 → `needs_promotion_review`
  because its statement "<P_z> = P_z(beta_2^0)" references the old U1
  mean which has been replaced by the stochastic map.

## §A2. Axiom-explore graceful-degrades [v2.1 — autonomy:max only]

| episode_id | triggering_issue | target_hypotheses | degraded_in_round | original_severity | caveat_added_to_ladder |
|---|---|---|---|---|---|
| (empty if no exhausted episodes; otherwise one row per) |

⚠️  These are **conditional resolutions**. The tier-1 hypothesis was
not independently validated by literature; the derivation continues
under the assumption that the user accepts conditional applicability.
The triggering CRITICAL issue's original severity is preserved here
for traceability — re-elevate if you decide to relax `— autonomy: max`.

## §B. Issues handled this round

For each issue in router_decision.json:

### R${ROUND_K}-IXX — [severity] [route]
- **Reviewer(s)**: {raised_by}
- **Action**: applied | DEFERRED | NOT_APPLICABLE | OBVIATED_BY_PROMOTION [v2]
- **Outcome** (one paragraph): "Added step S5 splitting ε_2 into
  mean + fluctuation; SymPy re-ran cleanly; the final equation now
  contains a'_var instead of a'_2."
- **Trace evidence**: derivation_trace.json step S5, checks[4]
- **Open follow-ups**: (none | text)

## §C. Scope-patch propagation log [v2]

| issue_id | assumption_id | ladder | spec §3 | steps narrative | risk_notes |
|---|---|---|---|---|---|
| R1-I06 | D6 | ✓ | n/a | ✓ §s2 | — |
| R1-I14 | U1 | ✓ | ✓ | ✓ §s4, §Final | — |
| R1-I05 | (parity) | n/a | n/a | ✓ §s7 | heuristic match — verify |

Footnote any row marked `deferred (heuristic_low_confidence)` so the
next round's reviewer knows where to look.

## §D. Merge conflicts resolved

(table or list of cases where two patches collided and how the
conflict was decided)

## §D2. Spec §1E auto-sync log [v2.1 — autonomy:max only]

| issue_id | old_form_one_line | new_form_one_line | class_invariance_check |
|---|---|---|---|
| (empty if no endpoint_form_drift routes; one row per sync) |

Each row documents one §1E rewrite. The `class_invariance_check`
column MUST read `OK`; any other value indicates a defensive refusal
to sync (the proposed form would have changed an endpoint class,
which is forbidden in this sub-step).

## §E. Final-equation symbol completeness [v2]

| symbol | failed_checks | recommended_action |
|---|---|---|
| (empty if all symbols pass; otherwise list per Step 7) |

This table is the safety net that catches the spin-pol-fluctuation
σ_η-undefined failure mode. An entry here means the final equation
references a symbol with no notation entry, no introducing axiom,
or no intermediate-step provenance.

## §F. Deferred fixes

(table: issue_id, reason, what is needed for the next attempt)

## §G. Final equation after this round

(verbatim copy of derivation_trace.json final_equations entry for
the target observable; one LaTeX line)

## §H. SymPy run summary
- Steps: total {N_total}, added this round {N_added}, modified {N_mod}, removed {N_removed}
- Checks: total {N_checks}, passing {N_pass}, failing {N_fail}
- Retries: {N_retries}
```

---

## Common Call-H pitfalls

| Pitfall | How to avoid |
|---|---|
| Skipping the canonical SymPy run because all Call-Gs succeeded. | The Call-G runs were on PARTIAL scripts. Their success does NOT prove the merged script is consistent. Always run the canonical merge SymPy. |
| Over-aggressive merging: applying a patch that contradicts a sibling patch. | Read every Call-G's fix.md "Open items left for Call H" section; that is where the originating fixer flagged inter-issue conflicts. Respect those flags. |
| Touching `${PREV_DIR}/` files. | NEVER. Symlink them in from `${ROUND_DIR}/` if you need them visible in the round directory. |
| Over-locking tier-1 on scope patches. **[v2 — was the v1 default]** | v2: only `lock_to_user_axiom: true` rows are sacred. Plain tier-1 entries CAN be scope-patched. Only refuse propagation when the row is explicitly locked. |
| Writing prose narrative into derivation_steps.md equation blocks. | The equation blocks (`$$ ... $$`) are verbatim from canonical trace. Step 5c rewrites PROSE sentences around them only, never the equations themselves. |
| Discarding lit-verifier outputs that returned `not_found`. | Even `not_found` is evidence (the literature is silent on the claim). Copy it into `verification/` so the final-report writer sees it. |
| **[v2]** Updating assumption_ladder but leaving derivation_steps.md / derivation-target.md §3 stale. | This was the dominant source of duplicate-issue avalanches in the spin-pol-fluctuation Round 2/3 case (14 duplicates in R3). Step 5b + 5c close this hole. Always populate the "Scope-patch propagation log" table — empty rows are themselves a signal of incomplete propagation. |
| **[v2]** Promoting a candidate without registering its new symbols. | Step 0c handles this. Skipping it produces the σ_η-undefined failure mode (final equation depends on σ_η but no notation/axiom defines it). Step 7's completeness check is the safety net but should never need to fire. |
| **[v2]** Promoting a candidate without auditing other tier-1 axioms for staleness. | Step 0e handles this. The example: U4 ("<P_z> = P_z(β₂⁰)") becomes vacuously false under a stochastic U1, but if Call-H leaves U4 unflagged, the next round's reviewers waste a CRITICAL slot rediscovering it. Mark `needs_promotion_review` instead of silently dropping. |
| **[v2]** Confusing endpoint-touching patches (forbidden) with §3-touching patches (allowed when unlocked). | §1A/§1B/§1C/§1D/§1E in derivation-target.md are SACRED — never write them. §3 user-given hypotheses are REVISABLE — write them when a scope patch's `assumption_to_revise` matches a §3 row and `lock_to_user_axiom: false`. |
| **[v2]** Symlinking notation_table.{md,json} from `${PREV_DIR}/` even though Step 0c registered new symbols. | If Step 0 ran with any promotion, ALWAYS write fresh `${ROUND_DIR}/notation_table.{md,json}`. Symlink only when no promotion happened this round AND no Call-G patch added a symbol. |

---

## Output reminders

- Time budget: 60 minutes.
- A round is VALID only if `derivation_trace.json` ends with
  `overall_status: ok`. A FAILED round means the `current` symlink
  does not advance, and the main agent surfaces to the user.
- The audit's `Status: ok | partial | FAILED` field is the
  authoritative round outcome:
  - `ok`: all router-routed issues were either applied or
    properly DEFERRED with a tracked reason; SymPy passed.
  - `partial`: at least one issue was DEFERRED without a clean
    reason; SymPy passed; the round still advances `current`
    because the derivation is still consistent.
  - `FAILED`: SymPy failed on the merged script; `current` does
    NOT advance.
