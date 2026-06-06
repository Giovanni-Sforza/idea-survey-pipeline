# Theory Synthesizer — Call type J (sister_derivation)

This is an addendum to `agents/subagents/theory-synthesizer.md`. You
were dispatched by the `derivation-refine-loop` skill (Step 3.6) with
ONE alternative axiom-set candidate from an earlier `axiom-explorer`
output. Your job is narrow: take that candidate's `replaces[]` and
`adds[]` axiom edits, apply them on TOP of the previous-round
`derivation_script.json` (replacing the targeted hypotheses, not
amending them), re-run SymPy end-to-end, and produce a SISTER
derivation trace.

You are NOT producing the main next-round derivation. The Call type H
synthesizer will MERGE Call-G fixer outputs into the main next round.
Sister derivations from Call J are SIDE-CARS for the
`sister-comparator` (Step 3.7) — they exist purely so the comparator
can decide whether a candidate axiom would have given a qualitatively
different answer.

You are dispatched ONCE per surviving candidate; concurrency is
bounded by `SISTER_DERIVATION_CONCURRENCY` (default 2). A typical
axiom-explore episode dispatches K = 3 of these in parallel.

---

## Boundary rules (in addition to the parent role)

### You MAY

- Read all files under `${PREV_DIR}/` (the previous accepted round).
- Read `${ROUND_DIR}/.axiom_explore/${EPISODE_ID}.json` (the
  axiom-explorer output that produced your candidate).
- Read `${ROUND_DIR}/router_decision.json` for context on the
  triggering issue.
- Run `python3 tools/symbolic_derive.py run --script ... --output ...`
  on YOUR per-sister script copy.
- Write exactly THREE files (and ONLY these):
  - `${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_${CANDIDATE_ID}_script.json`
  - `${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_${CANDIDATE_ID}_trace.json`
  - `${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_${CANDIDATE_ID}_sister.md`

### You MUST NOT

- Modify any file under `${PREV_DIR}/`.
- Modify any file outside `${ROUND_DIR}/.sister_outputs/`.
- Read or modify other sister scripts in `.sister_outputs/`. Each
  sister is independent. The `sister-comparator` (next stage) does
  the cross-reading.
- Promote your sister into the main round. That is a decision the
  `sister-comparator` recommends and the main agent (or the user)
  executes.
- Change anything outside the candidate's `replaces[]` and `adds[]`.
  Specifically: do NOT also "fix" other reviewer issues from this
  round (those go to Call G). Your job is to test ONE counterfactual.
- Change the chain's endpoints. If the candidate's edits would
  alter the source or sink class (this should have been blocked by
  axiom-explorer's isomorphism guard, but defensive coding: re-check),
  REFUSE and write a sister.md noting "endpoint violation: candidate
  axiom set changes source/sink class — should have been rejected
  upstream".

---

## Inputs read at startup

The main agent passes these context variables in the prompt:
- `ROUND_K` — round index (1-based)
- `EPISODE_ID` — axiom-explore episode that produced your candidate
- `CANDIDATE_ID` — your specific candidate id (e.g. `C1`)
- `PREV_DIR` — the previous accepted round directory
- `ROUND_DIR` — `${REFINE_DIR}/round_${ROUND_K}`
- `output_language`

---

## Workflow

### 1. Locate your candidate.

Read `${ROUND_DIR}/.axiom_explore/${EPISODE_ID}.json`. Find the
candidate with `candidate_id == "${CANDIDATE_ID}"`. Extract:
- `replaces[]` — list of {hypothesis_id, old_statement,
  new_statement, new_latex}
- `adds[]` — list of {new_id, statement, latex}
- `isomorphism_check` — read for sanity; reject if missing

If the candidate is not found or is malformed, write a
sister.md with status `SKIPPED: candidate not found or malformed`
and exit.

### 2. Re-confirm endpoint isomorphism (defensive).

Although axiom-explorer should have certified the candidate, re-verify
that:
- The hypotheses you'll add/replace do not touch any node referenced
  in `endpoint_isomorphism_anchors.source_endpoint` or
  `sink_endpoint` declared in the spec.
- They preserve `required_intermediates`.
- They do not invoke a `forbidden_detours` family.

If any check fails, write sister.md `REJECTED: endpoint guard
violation despite explorer certification` and exit. Surface upstream
to the `axiom-explorer`'s rejection log retroactively (by writing the
violation reason into the trace's `errors[]` so the audit picks it
up).

### 3. Build the sister script.

Copy `${PREV_DIR}/derivation_script.json` to
`${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_${CANDIDATE_ID}_script.json`.

Apply the candidate edits to your COPY:

1. For each entry in `replaces[]`:
   - Locate the script step(s) that introduce the targeted
     `hypothesis_id` (e.g. step that asserts `A1`).
   - REMOVE those steps from the script.
   - INSERT a new `assert` step(s) at the same position, using
     `new_latex` as the equation.
   - For any downstream step that referenced the old hypothesis by
     equation id, update the reference to point at the new
     assertion's id.

2. For each entry in `adds[]`:
   - INSERT a new `assert` step in topological position (after all
     steps it depends on, before all steps that depend on it).

3. If the candidate's edits invalidate a downstream substitution
   (e.g. the substituted symbol no longer exists), you MUST fix the
   downstream chain too — that is part of testing the counterfactual.
   You may need to:
   - Re-derive the affected steps under the new axiom set
   - Add new intermediate steps (e.g. an `expectation` step where the
     original chain had a `substitute` step, because the new axiom
     introduces an ensemble average)
   - Adjust the final-equation target step

   If the candidate axiom is genuinely incompatible with the
   downstream chain (e.g. the new axiom makes the final equation
   meaningless), record this in the trace's `errors[]` field as
   `chain_incompatible_with_candidate` — that itself is diagnostic
   information for sister-comparator.

### 4. Run SymPy.

```bash
python3 tools/symbolic_derive.py run \
    --script ${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_${CANDIDATE_ID}_script.json \
    --output ${ROUND_DIR}/.sister_outputs/${EPISODE_ID}_${CANDIDATE_ID}_trace.json
```

If `overall_status == "failed"`:
- Diagnose: read `errors[]`.
- Fix only the **mechanical** issues (typos, ordering, missing assumptions
  introduced by the substitution). Do NOT try to "rescue" a candidate
  that is fundamentally incompatible — recording the failure IS the
  diagnostic.
- Re-run. Up to **3 attempts total**.

A sister trace with `overall_status: failed` is a VALID output for
this call type. It means the candidate axiom doesn't survive symbolic
self-consistency, which is itself information for the comparator
(category: `chain_incompatible_with_candidate`).

### 5. Write sister.md.

Required structure:

```markdown
# Sister derivation: ${EPISODE_ID} / ${CANDIDATE_ID}

**Candidate short_label**: {copy from axiom_candidates.json}

**Replaces / Adds (summary)**:
- A{N} replaced by: {new_statement}
- New hypothesis added: {statement}

**Sister derivation result**:
- SymPy `overall_status`: {ok | failed | partial}
- Number of steps: {N}
- Number of checks passed: {M}/{K}
- Sister final equation: $$ ... $$
   (verbatim from the trace's final_equations)

**Comparison hooks** (for sister-comparator to fill in):
- Main final equation:    $$ ... $$  (copy from PREV_DIR/derivation_trace.json)
- Sister final equation:  $$ ... $$
- Pre-classification of difference (axiom-explorer's prediction):
  `difference_category: {parametric_dependence_order | sign_change | ...}`
- Sister's actual observed difference: {one line — what the SymPy
  trace actually produced, e.g. "Var(P_z) gained an explicit
  +b'_2 β_2² term and lost the σ_β_2 dependence"}
- Does the actual difference match the predicted category?
  {yes | no | partial}

**Downstream impact on assumption ladder**:
- Hypotheses now inactive (replaced or rendered moot): {list of A IDs}
- New hypotheses added: {list of C{ID}.A_new IDs}
- Tier-2 / tier-3 assumptions that became invalid under the new
  axioms: {list, or "none"}

**Open items for sister-comparator**:
- (list any anomalies the comparator should pay attention to, e.g.
  "the sister trace ran successfully but the final equation lost a
  factor of 1/2 — needs investigation whether this is real physics
  difference or a derivation-level symmetry-factor accident")
```

---

## What the sister-comparator does with your output

After ALL K sister synthesizers complete, the main agent dispatches
ONE `sister-comparator` subagent (Step 3.7). The comparator reads:
- `${PREV_DIR}/derivation_trace.json` — the MAIN trace
- All `${ROUND_DIR}/.sister_outputs/*_trace.json` — K sister traces
- All `${ROUND_DIR}/.sister_outputs/*_sister.md` — your narratives
- `${ROUND_DIR}/.axiom_explore/${EPISODE_ID}.json` — explorer's
  predicted impacts

…and produces a `${ROUND_DIR}/.axiom_explore/${EPISODE_ID}_comparison.json`
that decides whether:
1. all sisters agree with main qualitatively → main axiom robust;
   the triggering issue can be downgraded from CRITICAL to MAJOR
2. one or more sisters disagree qualitatively → main axiom suspect;
   surface to user (or, if `AXIOM_AUTO_PROMOTE: true`, promote the
   highest-confidence disagreeing sister into the next round)

Your job in Call J is purely to provide the symbolic evidence; the
adjudication is the comparator's.

---

## Common Call-J pitfalls

| Pitfall | How to avoid |
|---|---|
| Trying to make the sister "succeed" by mechanically rescuing it. | A sister failure is valuable diagnostic information. Don't paper over it. The only fixes allowed are mechanical (typos, ordering, mid-chain symbol propagation). |
| Reading other sister scripts to "see what they did". | Each sister is independent. Cross-reading defeats the purpose of an independent counterfactual. The comparator does the cross-reading. |
| Doing Call-G fixes inside Call J. | Call J is purely "swap axioms, re-run, report". Other reviewer issues from this round are NOT in scope. They go through Call G separately. |
| Promoting the sister yourself. | You write to `.sister_outputs/` only. Promotion is the main agent's call after seeing the comparator. |
| Spending more than 60 min. | Hard cap. A failing sister at minute 60 is still useful data — write the trace's failure mode and stop. |
| Skipping the sister.md "comparison hooks" section. | Those fields are what the sister-comparator parses to make its verdict. Without them the comparator has to re-do the diff itself. |

---

## Output reminders

- Time budget: 60 minutes. Most sisters take 15–40 minutes (they
  reuse most of the original chain; only the changed-axiom region
  needs re-derivation).
- The trace.json's `overall_status` may legitimately be `failed`.
  That is a VALID Call-J outcome. Do not retry forever to make it
  pass — if SymPy says the new axioms produce an inconsistent chain,
  log it.
- The sister.md must include both the main final equation AND the
  sister final equation side by side. The comparator depends on this
  side-by-side layout.
- Do not chain to another subagent. The main agent dispatches the
  sister-comparator after all K sisters complete.
