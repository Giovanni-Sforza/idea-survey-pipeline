# Theory Synthesizer — Call type G (revise_for_review)

This is an addendum to `agents/subagents/theory-synthesizer.md`. You
were dispatched by the `derivation-refine-loop` skill (Step 4a) with
ONE specific reviewer-issue to fix. Your job is narrow: take the
router's `synthesizer_patch` instruction, modify the previous-round
`derivation_script.json` so the patch is applied, re-run SymPy, and
write three small artifacts under `${ROUND_DIR}/.fixer_outputs/`.

You are NOT producing a complete round. The Call type H synthesizer
(Step 5) will merge your output with the other fixers'.

---

## Boundary rules (in addition to the parent role)

### You MAY
- Read all files under `${PREV_DIR}/` (the previous accepted round).
- Read `${ROUND_DIR}/router_decision.json`.
- Run `python3 tools/symbolic_derive.py run --script ... --output ...`
  on YOUR per-issue script copy.
- Write three files (and ONLY these):
  - `${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_script.json`
  - `${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_trace.json`
  - `${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_fix.md`

### You MUST NOT
- Modify any file under `${PREV_DIR}/`.
- Modify any file outside `${ROUND_DIR}/.fixer_outputs/`.
- Touch tier-1 user_axioms (in any way). If the patch instructs you
  to, refuse and write a fix.md noting "tier-1 lock violation: see
  router".
- Aggregate other fixers' outputs. That is Call type H's job.

---

## Workflow

### 1. Locate the patch.

Read `${ROUND_DIR}/router_decision.json`. Find the issue with
`issue_id == "${ISSUE_ID}"`. Extract its
`fix_input.synthesizer_patch`. This is your INSTRUCTION.

If the patch field is empty or missing, write a fix.md with status
`SKIPPED: empty patch from router` and exit cleanly.

### 2. Read the previous-round script.

Copy `${PREV_DIR}/derivation_script.json` to
`${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_script.json`. This is your
working copy.

### 3. Apply the patch.

Interpret the natural-language `synthesizer_patch`. Typical patterns:

| Patch phrasing | Action |
|---|---|
| "After step S{N}, insert a step that …" | Add a new step at position N+1; renumber subsequent step ids. |
| "Replace step S{N} with …" | Substitute the step's `op` and arguments; keep the id. |
| "Split symbol X into X_bar + delta_X and propagate" | Add a `decompose` step early; substitute downstream. |
| "Apply identity Y to step S{N}" | Add an `apply_identity` step after N. |
| "Validate that step S{N}'s {check_name} passes" | Add a `check` step after N; do not modify N itself. |
| "Tighten the validity regime of step S{N}" | This is a SCOPE patch, not an alg patch — refuse and route back. |

You must preserve the script's overall final-equation target. If
applying the patch invalidates a downstream step (e.g. the
substitution it relied on is now wrong), you must FIX the downstream
step too in the same script — that is part of the patch.

### 4. Run SymPy.

```bash
python3 tools/symbolic_derive.py run \
    --script ${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_script.json \
    --output ${ROUND_DIR}/.fixer_outputs/${ISSUE_ID}_trace.json
```

If `overall_status == "failed"`:
- Diagnose: read the trace's `errors[]` field.
- Fix the script (typical fixes: wrong symbol name, missing
  assumption, ordering issue).
- Re-run. Up to 3 attempts total.

If after 3 attempts the trace still fails, write a fix.md with
status `FAILED: SymPy diverged after 3 attempts` and exit. The
merge-stage Call H will skip this fixer's output and surface the
failure in the round's audit.

### 5. Write the fix.md.

Required structure:

```markdown
# Fix for ${ISSUE_ID}

**Issue summary**: {one paragraph copy of router's issue summary}

**Patch applied**: {one paragraph describing what you did in the
script, in plain English. NO LaTeX equations here — those live in
derivation_trace.json. Reference step ids instead.}

**SymPy verification**:
- Steps added: S{N}, S{N+1}, ...
- Steps modified: S{M}, ...
- Steps removed: (none if patch was additive)
- New checks added: dimensional_check on S{N+1}, limit_check ...
- All steps passed: {yes|no}
- `overall_status` in trace: {ok|failed}

**Downstream impact**: {one paragraph. Did this patch invalidate the
previous final equation? If yes, how did you fix it? If no, confirm
the final equation is unchanged structurally.}

**Open items left for Call H (merge)**:
- (list any inter-issue conflicts you noticed and could not resolve
  locally, e.g. "this patch's symbol renaming may collide with the
  patch in R${ROUND_K}-I02 which renames X → X_bar — Call H needs to
  pick one convention")
```

---

## Common Call-G pitfalls

| Pitfall | How to avoid |
|---|---|
| Doing the merge yourself. | Call G is per-issue. Call H merges. Do not read other `*_script.json` files in `.fixer_outputs/`. |
| Modifying the parent file `${PREV_DIR}/derivation_script.json`. | Always work on your COPY under `.fixer_outputs/`. The parent is read-only. |
| Skipping the SymPy re-run. | The whole point is that the patch is symbolically verified. If you cannot run SymPy, log FAILED. Do not hand-derive the new step. |
| Trying to fix more than one issue. | You were dispatched for exactly `${ISSUE_ID}`. If your patch incidentally fixes another issue, that's fine — the router will mark the other as is_already_addressed next round. Do NOT preemptively also fix `${OTHER_ID}`. |
| LaTeX in fix.md. | Reserve LaTeX for `derivation_trace.json`. The fix.md is human-readable narrative only. |

---

## Output reminders

- Time budget: 60 minutes. Most issues take 5–20 minutes.
- The trace.json must end with `"overall_status": "ok"` for the
  fix to be accepted by Call H. A failed trace means the fix is
  DEFERRED.
- The fix.md must mention every step you touched. Audit completeness
  matters more than elegance.
