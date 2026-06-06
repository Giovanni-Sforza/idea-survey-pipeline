---
name: analytic-derivation
description: Cross-paper symbolic derivation. Use when the user has a TARGET observable they want expressed as an analytic function of a TARGET control parameter, plus 2–5 anchor papers that each cover a different segment of the physics chain, plus optional user-given bridging assumptions. Unlike `idea-landscape` / `idea-novelty` / `idea-feasibility` (which produce SURVEYS) or `research-debug` (which answers ONE in-progress question from literature), this skill produces a STEP-BY-STEP SYMBOLIC DERIVATION executed by SymPy, with a literature-verification pass on uncertain assumptions, and a `hep-theory-reviewer` sanity audit. Designed for theoretical / phenomenological physics, especially the HEP × heavy-ion vorticity / polarization / initial-state-fluctuation domain.
argument-hint: [free-text derivation goal]
---

# Analytic Derivation — Cross-Paper Symbolic Synthesis

User goal: $ARGUMENTS

## Why This Skill Exists

The other six skills in this pipeline are **survey** tools or **single-question**
tools. None of them does what an advisor often actually wants:

> "Combine results from these four papers, under these bridging assumptions,
> and derive `<P_z²> - <P_z>²` as an analytic function of beta_2."

That is not a literature survey — the papers are already chosen.
It is not novelty checking — there is no concrete invention yet.
It is not single-paper debugging — the question lives ACROSS papers.
It is a **derivation**: a chain of equations from a free variable to a target
observable, with notation reconciled and assumptions tracked.

This kind of task fails for AI in three predictable ways:
1. **Hallucinated algebra.** LLMs skip steps, drop signs, or misapply
   `<XY> = <X><Y>` to non-independent variables. Fix: every step is executed
   by SymPy via `tools/symbolic_derive.py`, not by the LLM in prose.
2. **Notation collisions.** Each paper uses its own conventions; rho_2 in
   one paper is the matter density 2-point function in another. Fix: an
   explicit notation-reconciliation step (Step 3) before any substitution.
3. **Silent assumption inheritance.** A derivation can be algebraically
   correct but physically wrong because an unspoken assumption from
   paper A is incompatible with the regime of paper B. Fix: a three-tier
   `assumption_ladder.md` (Step 4) with a literature-verification pass
   (Step 4b) for items the synthesizer cannot self-verify.

## Constants

- **OUTPUT_DIR_BASE = `analytic-derivation/`** — Each invocation creates `analytic-derivation/{run_slug}/`.
- **TARGET_SPEC_PATH = `analytic-derivation/{run_slug}/derivation-target.md`** — REQUIRED. If missing, skill bootstraps it from the template and exits (Step 0b).
- **TARGET_SPEC_TEMPLATE = `templates/DERIVATION_TARGET_SPEC_TEMPLATE.md`** — Source for bootstrap.
- **DERIVATION_CARD_SCHEMA = `templates/PAPER_DERIVATION_CARD_SCHEMA.md`** — Schema for per-paper derivation cards (Step 2).
- **REPORT_TEMPLATE = `templates/DERIVATION_REPORT_TEMPLATE.md`** — Final report layout (Step 7).
- **SHARED_DEEP_DIR = `literature-deep/`** — Reused from idea-* skills. Anchor papers' `deep_analysis.md` and `paper_card.json` live here; existing analyses are reused at zero cost (paper-pool aware).
- **EXTRACT_CONCURRENCY = 4** — Maximum concurrent `theory-synthesizer` Call-A subagents (one per anchor paper). Hard cap.
- **LIT_VERIFY_CONCURRENCY = 3** — Maximum concurrent `lit-verifier` subagents in Step 4b. Hard cap, can be overridden via the target spec §7.
- **LIT_VERIFY_MAX = 6** — Maximum number of items the verifier queue may contain. Items beyond this cap are flagged in the report as "human verification required" without a Step 4b lit-verifier dispatch. Can be overridden via the target spec §7.
- **LIT_VERIFY_SKIP = false** — When true, skip Step 4b entirely (anchor papers trusted as-is). Set via target spec §7.
- **SUBAGENT_TIMEOUT_EXTRACT = 1800** — Per-paper extraction subagent timeout (30 min).
- **SUBAGENT_TIMEOUT_SYNTHESIS = 3600** — Synthesizer (chain sketch / notation / ladder / derivation) timeout (60 min).
- **SUBAGENT_TIMEOUT_VERIFY = 1800** — `lit-verifier` timeout (30 min hard).
- **SUBAGENT_TIMEOUT_REVIEW = 1800** — `hep-theory-reviewer` (Step 6) timeout.
- **SYMPY_SCRIPT_MAX_RETRIES = 3** — Hard cap on theory-synthesizer's SymPy debug-and-retry loop in Step 5.
- **OUTPUT_LANGUAGE = "auto"** — Follows the shared output-language protocol.
- **INTERACTIVE = true** — Default: interactive checkpoints after Step 2 (chain sketch), Step 4 (notation + assumption ladder), Step 5 (derivation steps). Override with `— interactive: false` for unattended overnight runs (e.g. you trust the spec completely).
- **MAX_ANCHOR_PAPERS = 8** — Refuse to start if the user supplied more than this many anchor papers in §2 of the target spec; that's a sign the chain is too vague to derive.

> 💡 Overrides:
> - `/skill:analytic-derivation "goal" — interactive: false` — run end-to-end without stopping at checkpoints (overnight mode; uses spec verbatim)
> - `/skill:analytic-derivation "goal" — language: zh` — output in Chinese (equations + JSON keys remain English)
> - `/skill:analytic-derivation "goal" — lit-verify: false` — skip Step 4b literature verification (uses anchor papers' assumptions verbatim)
> - `/skill:analytic-derivation "goal" — lit-verify-max: 10` — allow up to 10 verification items (default 6)
> - `/skill:analytic-derivation "goal" — pdf-parser: vision` — for anchor papers without arXiv TeX, use the vision PDF path (MacBook Air friendly)
> - `/skill:analytic-derivation "goal" — run-slug: pz-variance-beta2` — set the per-run subdirectory name explicitly (default: derived from $ARGUMENTS + timestamp)

---

## 🚧 Main Agent Boundary Protocol — ORCHESTRATE + DIALOGUE 🚧

> Same spirit as `research-debug` and the idea-* skills: the main agent
> DISPATCHES subagents and runs shell/Python tools, but never reads paper
> bodies, never does the algebra, never writes synthesis prose. Reason:
> derivation chains of even moderate length blow the main agent's context
> within one paper; the only way to stay under budget is rigorous
> delegation.

### What the main agent MAY do

1. **Read `derivation-target.md` in full.** This is the user's own spec
   file, not a paper. Size cap: typically < 10 KB; if it exceeds 50 KB,
   it has been used as a scratchpad and the main agent should read only
   sections 1–6.
2. **Read small structured JSON files** produced by subagents, when
   needed for orchestration decisions:
   - `verification_queue.json` (Step 4a output) — to know how many
     lit-verifier subagents to dispatch
   - `chain_sketch.md` `next_action` line — to decide whether to block
     or proceed
   - `derivation_trace.json` `overall_status` field only — to decide
     whether Step 5 succeeded
   The main agent MUST NOT read these files for synthesis content; it
   reads them for routing.
3. **Read `paper_card.json` files** under `literature-deep/paper_*/`
   for the standard reasons (counting, manifest building, audit). Same
   exception as in the idea-* skills.
4. **Print user-facing checkpoint messages** and **wait for user
   response** at three checkpoints (after Step 2, after Step 4b,
   between Step 5 and Step 6). This skill is interactive by default.
5. Run **shell commands** (`mkdir`, `cp`, `find`, `ls`, `wc`, `grep`,
   `test`, `sed`, `jq`).
6. Run **Python tool scripts** in `tools/` — including
   `tools/symbolic_derive.py check-deps` / `selftest` for the
   self-audit step, but NEVER `tools/symbolic_derive.py run` (that's
   the synthesizer's job).
7. Launch **subagents** via the `Agent` tool (types:
   `theory-synthesizer`, `lit-verifier`, `paper-analyzer` for
   downloads, `hep-theory-reviewer`, `paper-editor` for the final
   report).
8. Apply the **polling protocol** (Pattern 2 below) and collect subagent
   outputs.
9. **Audit** subagent outputs at the file-system level only.
10. Write **small structured files** (per-run status JSON, the bootstrap
    target spec).

### What the main agent MUST NOT do — under any circumstance

- ❌ **Read** any `deep_analysis.md`, `figure_manifest.json`, or figures
  under `literature-deep/paper_*/`. Delegate to the relevant subagent.
- ❌ **Read** any `derivation_card.json`, `chain_sketch.md`,
  `notation_table.md`, `assumption_ladder.md`, `derivation_steps.md`,
  `verification_report.md`, or `derivation-report.md` body for
  synthesis purposes. Read ONLY the explicit small fields enumerated
  in "What the main agent MAY do" #2.
- ❌ **Read** the *content* of `derivation_trace.json` past the
  `overall_status` and `errors[]` fields. The full trace is the
  synthesizer's working memory, not the main agent's.
- ❌ **Write** any equation, derivation step, notation table entry,
  assumption, or chain sketch — even one. The synthesizer does this.
- ❌ **Invoke** `tools/symbolic_derive.py run`. The synthesizer
  invokes it from inside its subagent run.
- ❌ **Fall back** to direct paper reading or direct algebra when a
  subagent is slow / fails / times out. Apply Pattern 2 retries.
- ❌ **Chain to another skill.** Kimi does not allow skill-to-skill
  invocation. The Step 7 report's "Suggested next actions" section
  contains user-facing `/skill:` strings; the main agent NEVER
  attempts to invoke them.

### The "I'll just peek" rule

| Tempted to read | Correct action |
|---|---|
| "Let me look at this paper to check what equation 3 says." | Dispatch a fresh `theory-synthesizer` Call-A on that paper (re-extraction) or, if the card already exists, re-read the card via a synthesizer call — never directly. |
| "Let me check if the chain sketch makes sense." | The user did. That's what Checkpoint #1 was for. |
| "Let me just simplify this final equation by hand." | Edit `derivation_script.json` to add a `simplify` step, re-run via the synthesizer. |
| "Let me verify the dimensional check by hand." | Already done by `dimensional_check` in `derivation_trace.json`'s `checks[]`. |

**Bytes the main agent reads per run, target: < 80 KB total.** Higher
than the idea-* skills' 50 KB because the spec is larger; still small
enough that no synthesis content can leak in.

### Interaction model — three rules

| Checkpoint | When | Default user options |
|---|---|---|
| #1 | After Step 2 (chain sketch ready) | `ok` / `edit` / `restart` |
| #2 | After Step 4b (assumption ladder + verification log ready) | `ok` / `fix N: <change>` / `restart` |
| #3 | After Step 5 (derivation script + steps ready) | `ok` / `fix step N: <change>` / `restart` |

If `INTERACTIVE == false`, no checkpoint is shown. The skill runs end
to end and the final report includes a "checkpoints skipped" warning
at the top.

---

## Language Determination

1. Parse `$ARGUMENTS` for `— language:` override (`zh`, `en`).
2. If no override, follow the [Output Language Protocol](../shared-references/output-language.md).
3. If `derivation-target.md` declares a language preference in section 4
   (e.g. "请用中文输出"), use that.
4. Propagate `output_language` to every subagent prompt and the report file.

---

## Common Subagent Patterns

These follow the exact same patterns as `research-debug` and the
idea-* skills. Do not improvise.

### Pattern 1: Launch

```yaml
Agent:
  description: "<short task name>"
  subagent_type: "<theory-synthesizer | lit-verifier | paper-analyzer | hep-theory-reviewer | paper-editor>"
  run_in_background: true
  timeout: <as per Constants>
  prompt: |
    <task-specific prompt — see each Step>
```

### Pattern 2: Polling

```
PHASE 1 — Initial wait:    sleep 180 → TaskList → collect via TaskOutput
PHASE 2 — Second wait:     sleep  90 → TaskList → collect
PHASE 3 — Tight loop:      while active: sleep 45 → TaskList → collect
                           If a slot opens AND queue not empty: launch next
                           Maintain active count ≤ relevant concurrency cap
PHASE 4 — Failure handling:
    IF timeout or error:
        TaskStop
        Launch ONE retry with the IDENTICAL prompt
        If retry also fails: log FINAL_FAILED for that task
                              continue with the rest
                              never fall back to main-agent direct work
```

(Cycles are tighter than the idea-* skills because this skill's
subagents are smaller per-task: extracting one paper takes ~10 min, a
SymPy script run takes seconds.)

### Pattern 3: Audit

```bash
for f in $EXPECTED_OUTPUTS; do
    test -s "$f" || { echo "MISSING: $f"; exit 1; }
done
for j in $EXPECTED_JSONS; do
    python3 -m json.tool < "$j" > /dev/null || { echo "INVALID JSON: $j"; exit 1; }
done
```

If audit fails: retry the subagent ONCE with the same prompt. If retry
also fails, surface to the user and STOP (do not silently proceed with
missing data).

---

## Workflow

The skill is **seven steps**, plus a checkpointed bootstrap. Steps that
launch subagents say "[Subagent: X]". Steps the main agent runs say
"[shell]" or "[main-agent dialogue]".

### Step 0a: Argument parsing & workspace setup [shell]

Parse `$ARGUMENTS` for:
- Free-text goal (required; non-empty)
- `— interactive: true|false` (default `true`)
- `— language: zh|en` (default `auto`)
- `— lit-verify: true|false` (default `true`)
- `— lit-verify-max: N` (default `LIT_VERIFY_MAX`)
- `— pdf-parser: auto|full|legacy|vision` (default `auto`)
- `— run-slug: <slug>` (default derived)

Compute `run_slug`:

```bash
python3 -c "
import re, sys
q = sys.argv[1].strip().lower()
slug = re.sub(r'[^a-z0-9]+', '-', q)[:60].strip('-')
print(slug or 'derivation')
" "$USER_GOAL"
```

Append timestamp suffix and create the per-run workspace:

```bash
SUFFIX=$(date +%m%d-%H%M)
SLUG="${SLUG}-${SUFFIX}"
RUN_DIR="analytic-derivation/${SLUG}"
mkdir -p "${RUN_DIR}/cards/" "${RUN_DIR}/verification/"
```

### Step 0b: Self-audit of dependencies [shell]

```bash
python3 tools/symbolic_derive.py check-deps || {
    echo "❌ symbolic_derive.py dependency check failed."
    echo "    Fix: pip install sympy --upgrade --break-system-packages"
    exit 1
}
```

If this fails, abort with a user-facing error. Do NOT proceed.

Optional: also run `python3 tools/symbolic_derive.py selftest`; on
failure abort. This catches a broken SymPy install before any
subagent spend.

### Step 0c: Target spec bootstrap (if needed) [shell + dialogue]

```bash
if [ ! -s "${RUN_DIR}/derivation-target.md" ]; then
    cp templates/DERIVATION_TARGET_SPEC_TEMPLATE.md "${RUN_DIR}/derivation-target.md"
    BOOTSTRAP=1
fi
```

If bootstrap happened, main agent prints:

> 📋 No `derivation-target.md` was found in this run directory, so I copied the template into place at:
>   `${RUN_DIR}/derivation-target.md`
> Please open it and fill in at least sections 1 through 6:
>   1. Target observable
>   2. Anchor papers (2–8 arXiv IDs)
>   3. User-given bridging assumptions
>   4. Physical-picture sketch
>   5. Validity regime
>   6. Desired form of the final answer
> Then re-invoke this skill with the same arguments — the spec persists,
> so the skill will pick up where it left off.

…and STOPS. Do NOT proceed to Step 1.

### Step 0d: Target spec validation [shell]

If `derivation-target.md` exists, validate the user filled it in by
running a small Python script that checks each required section has a
non-default value (i.e. is not just the placeholder template). Schema
sketch:

```bash
python3 -c "
import re, sys, json
with open('${RUN_DIR}/derivation-target.md') as f:
    text = f.read()
required = [
    ('## 1. Target observable', r'Math form.*\\\$\\\$.*\\\$\\\$', 'target observable math form'),
    ('## 2. Anchor papers', r'arXiv:\d{4}\.\d{4,5}', 'at least one anchor arXiv ID'),
    ('## 3. User-given bridging assumptions', r'A\d.*\|.*\|.*\|', 'at least one bridging assumption row'),
    ('## 4. Physical-picture sketch', r'\\\{[^}]+\\\}', 'physical picture sketch'),
    ('## 5. Validity regime', r'Collision system', 'validity regime'),
    ('## 6. Desired form of the final answer', r'Form.*:', 'desired form'),
]
missing = [name for marker, pat, name in required
           if marker not in text or not re.search(pat, text, re.S)]
n_anchors = len(re.findall(r'arXiv:\d{4}\.\d{4,5}', text))
if missing:
    print('MISSING_SPEC_SECTIONS: ' + json.dumps(missing))
    sys.exit(2)
if n_anchors > ${MAX_ANCHOR_PAPERS}:
    print('TOO_MANY_ANCHORS: %d' % n_anchors)
    sys.exit(3)
print('SPEC_OK n_anchors=%d' % n_anchors)
"
```

If missing sections: abort with a user-facing message listing exactly
which sections are still default.

### Step 1: Anchor paper resolution + reuse-or-download [Subagent: paper-editor]

> Main agent does NOT download or parse papers. The download-preparer
> subagent does — the same one used by the idea-* skills.

The main agent extracts the anchor arXiv IDs from
`derivation-target.md` via grep (shell-only), writes them to
`${RUN_DIR}/.selected_papers.json` in the same schema the idea-*
download-preparer expects, then runs:

```bash
python3 tools/papers_pool.py resolve \
    --selected-papers ${RUN_DIR}/.selected_papers.json \
    --project-dir . \
    --topic "$USER_GOAL" \
    --output ${RUN_DIR}/.selected_papers_resolved.json
```

Then dispatch the download-preparer subagent using the SAME prompt
shape as `idea-landscape` Step 3 (see
`skills/idea-landscape/SKILL.md` lines 550–670). Key differences:

- `tex-only` mode is auto-enabled if every anchor in the spec is an
  arXiv ID — this is the common case for theory/HEP-pheno papers.
- `pdf-parser` follows the user's `— pdf-parser:` override.

For each anchor paper that has no existing `paper_card.json` (i.e. was
not already analyzed by an idea-* run), dispatch a `paper-analyzer`
subagent that produces `deep_analysis.md` AND `paper_card.json`. This
re-uses Step 4 + Step 4.5 of the idea-* skills verbatim — do not
re-implement.

After this step, every anchor paper has a `literature-deep/paper_*/`
directory with `deep_analysis.md` AND `paper_card.json`.

### Step 2: Per-paper derivation card extraction [Subagent: theory-synthesizer — Call type A, one per paper]

For each anchor paper, dispatch ONE `theory-synthesizer` Call-A
subagent (Pattern 1, `subagent_type: paper-editor` because we re-use
that role; the `theory-synthesizer.md` agent definition serves as the
prompt template).

Concurrency: maintain ≤ `EXTRACT_CONCURRENCY`.

Prompt template:

```yaml
Agent:
  description: "Extract derivation card: {short_title}"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are operating as a `theory-synthesizer` subagent, Call type A
    (extract). Read your full role definition at:
        agents/subagents/theory-synthesizer.md

    ## Inputs (read these)
    - Target spec: {RUN_DIR}/derivation-target.md
    - Paper directory: literature-deep/paper_{safe_id}/
      Read in this order:
        1. paper_card.json
        2. deep_analysis.md
        3. figure_manifest.json (only the captions of equations/figures
           referenced in deep_analysis.md — do NOT ReadMediaFile unless
           an equation's LaTeX is unreadable from text alone)
    - Schema: templates/PAPER_DERIVATION_CARD_SCHEMA.md
    - Output language: {output_language}

    ## Output
    Write exactly one file:
        {RUN_DIR}/cards/paper_{safe_id}.json

    Conform to the schema. Use null/[] for fields you cannot
    substantiate — never invent.

    ## Forbidden
    - Do NOT read other anchor papers' deep_analysis.md.
    - Do NOT write any prose synthesis or report content.
    - Do NOT invoke symbolic_derive.py (that's Call type F).
    - Do NOT chain to another subagent.
```

Polling: Pattern 2.
Audit: each `${RUN_DIR}/cards/paper_*.json` exists, parses, has key
`schema_version == "1"`, `card_kind == "derivation_card"`.

### Step 2.5: Chain sketch [Subagent: theory-synthesizer — Call type B, one]

Dispatch ONE synthesizer subagent (Call type B). Prompt template:

```yaml
Agent:
  description: "Build derivation chain sketch"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are operating as a `theory-synthesizer` subagent, Call type B
    (chain_sketch). Read your full role definition at:
        agents/subagents/theory-synthesizer.md

    ## Inputs
    - Cards directory: {RUN_DIR}/cards/  (read every paper_*.json)
    - Target spec: {RUN_DIR}/derivation-target.md (sections 1, 4, 6)
    - Output language: {output_language}

    ## Output
    Write exactly one file:
        {RUN_DIR}/chain_sketch.md

    Required sections:
        # Chain sketch
        ## DAG
        (ASCII or mermaid; start at user's control_parameter, end at user's
        target observable; label each edge with paper_key:local_eq_id)
        ## Unresolved segments
        (zero or more items; each becomes a Step 4b verification item if it
        is on the critical path)
        ## next_action
        proceed_to_notation | block_on_unresolved | chain_impossible_from_anchors

    ## Forbidden
    - Do NOT begin building the notation table — that is Call type C.
    - Do NOT do any algebra in chain_sketch.md.
```

Polling, audit as Pattern 2/3.

#### Checkpoint #1 (interactive, unless INTERACTIVE=false)

Main agent prints:

> ✦ **Checkpoint #1 — chain sketch**
>
> {full content of `${RUN_DIR}/chain_sketch.md`}
>
> Please reply with:
> - **ok** — chain is right, proceed to notation + assumption ladder
> - **edit: <free text>** — describe what's wrong; I'll re-dispatch chain sketch with your hint as additional input
> - **restart** — back to step 1 with a fresh card extraction (use if a card is fundamentally wrong)
> - **stop** — abort

Wait for user response.

Edit branch: append the user's edit text to a new file
`${RUN_DIR}/.chain_edit_hint.txt`, re-dispatch Call type B with the
hint included in the prompt. ONE retry only — if a second edit is
requested, the user is asked to instead edit `chain_sketch.md`
directly and confirm.

### Step 3: Notation reconciliation [Subagent: theory-synthesizer — Call type C]

Dispatch ONE synthesizer subagent. Prompt:

```yaml
Agent:
  description: "Build unified notation table"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are operating as a `theory-synthesizer` subagent, Call type C
    (notation_table). See: agents/subagents/theory-synthesizer.md

    ## Inputs
    - Cards directory: {RUN_DIR}/cards/  (every paper_*.json)
    - Chain sketch: {RUN_DIR}/chain_sketch.md
    - Output language: {output_language}

    ## Outputs (both files mandatory)
    - {RUN_DIR}/notation_table.md   — human-readable, follows the table in
      DERIVATION_REPORT_TEMPLATE.md §4
    - {RUN_DIR}/notation_table.json — schema in
      agents/subagents/theory-synthesizer.md "Call type C"

    ## Forbidden
    - Do NOT modify any card.
    - Do NOT begin the assumption ladder (that is Call D).
```

Polling, audit.

### Step 4: Assumption ladder draft + verification queue [Subagent: theory-synthesizer — Call type D]

Dispatch ONE synthesizer subagent:

```yaml
Agent:
  description: "Draft assumption ladder + verification queue"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are operating as a `theory-synthesizer` subagent, Call type D
    (assumption_ladder_draft). See: agents/subagents/theory-synthesizer.md

    ## Inputs
    - Cards directory: {RUN_DIR}/cards/
    - Chain sketch: {RUN_DIR}/chain_sketch.md
    - Notation table JSON: {RUN_DIR}/notation_table.json
    - Target spec: {RUN_DIR}/derivation-target.md (especially §3 user axioms)
    - Output language: {output_language}

    ## Outputs (all three files mandatory)
    - {RUN_DIR}/assumption_ladder.md   — tiers 1/2/3, status = `pending`
                                          for tier-2/3 items, `user_axiom`
                                          for tier 1
    - {RUN_DIR}/assumption_ladder.json — JSON mirror with tier + status
    - {RUN_DIR}/verification_queue.json — schema in
      agents/subagents/theory-synthesizer.md "Call type D"
      Hard cap on items: {LIT_VERIFY_MAX}. If you have more items than
      the cap, keep the {LIT_VERIFY_MAX} most-critical (those on the
      critical path of the chain), and add the remainder to
      assumption_ladder.md with status `needs_human_review` so the
      user sees them in the final report.

    ## Forbidden
    - Do NOT run any web search yourself. The lit-verifier does that.
    - Do NOT proceed to the derivation script.
```

Polling, audit.

### Step 4b: Literature verification of uncertain items [Subagent: lit-verifier × N]

> This is the step the user explicitly asked for. Many cards' equations
> are stated without rigorous derivation in their source paper; before
> we plug them into a chain that supports a physics claim, we run a
> targeted independent literature search per item.

#### 4b.1 — Decide what to dispatch [shell]

```bash
if [ "${LIT_VERIFY_SKIP}" = "true" ]; then
    echo "Step 4b skipped per — lit-verify: false"
    touch "${RUN_DIR}/.lit_verify_skipped"
    # synthesizer Call E will mark all items as 'user_axiom_trust' instead
else
    N_ITEMS=$(jq '.items | length' "${RUN_DIR}/verification_queue.json")
    echo "Step 4b: ${N_ITEMS} items to verify (cap ${LIT_VERIFY_MAX})"
fi
```

#### 4b.2 — Prepare per-item input files [shell]

For each item in `verification_queue.json`, write a small input file
`${RUN_DIR}/.lit_verify_input_<item_id>.json` containing exactly the
schema documented in `agents/subagents/lit-verifier.md` "Input schema".

```bash
python3 -c "
import json, os
RUN_DIR = '${RUN_DIR}'
with open(os.path.join(RUN_DIR, 'verification_queue.json')) as f:
    queue = json.load(f)
anchors = []  # read anchor arXiv IDs from .selected_papers.json
with open(os.path.join(RUN_DIR, '.selected_papers.json')) as f:
    for p in json.load(f):
        if p.get('arxiv_id'):
            anchors.append('arXiv:' + p['arxiv_id'])
for item in queue['items']:
    input_path = os.path.join(RUN_DIR, '.lit_verify_input_' + item['item_id'] + '.json')
    output_path = os.path.join(RUN_DIR, 'verification', 'lit_check_' + item['item_id'] + '.json')
    payload = {
        **item,
        'anchor_papers_to_ignore': anchors,
        'output_path': output_path,
        'output_language': '${output_language}',
    }
    with open(input_path, 'w') as g:
        json.dump(payload, g, indent=2)
print('wrote', len(queue['items']), 'lit-verifier input files')
"
```

#### 4b.3 — Dispatch lit-verifier subagents [Subagent: lit-verifier × N]

Concurrency: maintain ≤ `LIT_VERIFY_CONCURRENCY`.

Prompt template (one per item):

```yaml
Agent:
  description: "Lit-verify: {item_id}"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are operating as a `lit-verifier` subagent (single-shot
    literature verification). See full role definition:
        agents/subagents/lit-verifier.md

    ## Inputs
    - Input file: {RUN_DIR}/.lit_verify_input_{item_id}.json
      (read this first; it contains the claim, search terms, and
       output path)

    ## Output
    Write exactly the file path given by `output_path` in your input.
    Schema: see lit-verifier.md "Write output" section.

    ## Forbidden
    - Do NOT read any file under literature-deep/.
    - Do NOT write any file other than your output file.
    - Do NOT chain to another subagent.
    - Time budget: 25 minutes hard. If you haven't produced a verdict
      by then, write status="timeout" and stop.
```

Polling: Pattern 2 with `LIT_VERIFY_CONCURRENCY` instead of 4.
Per-item retries: at most ONE. On second failure, write a stub
`verification/lit_check_<item_id>.json` with `status: verifier_error`
and continue with the rest.

#### 4b.4 — Audit [shell]

```bash
EXPECTED=$(jq -r '.items[].item_id' "${RUN_DIR}/verification_queue.json")
for ITEM in $EXPECTED; do
    F="${RUN_DIR}/verification/lit_check_${ITEM}.json"
    test -s "$F" || { echo "MISSING: $F"; FAIL=1; }
    python3 -m json.tool < "$F" > /dev/null || { echo "INVALID JSON: $F"; FAIL=1; }
done
[ -z "$FAIL" ] || echo "WARN: some verifications missing; continuing with degraded ladder"
```

Missing or invalid items become `verifier_error` in the merge step.

### Step 4c: Assumption ladder merge [Subagent: theory-synthesizer — Call type E]

Dispatch ONE synthesizer subagent:

```yaml
Agent:
  description: "Merge lit-verifier results into assumption ladder"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are operating as a `theory-synthesizer` subagent, Call type E
    (assumption_ladder_merge). See: agents/subagents/theory-synthesizer.md

    ## Inputs
    - Existing ladder MD:   {RUN_DIR}/assumption_ladder.md
    - Existing ladder JSON: {RUN_DIR}/assumption_ladder.json
    - Verification directory: {RUN_DIR}/verification/
      (every lit_check_*.json file; read each in full — they are small)
    - Skip flag: {RUN_DIR}/.lit_verify_skipped (existence => treat all
      tier-2/3 items as `user_axiom_trust` and add a header banner to
      assumption_ladder.md saying Step 4b was skipped)

    ## Outputs (overwrite the existing files)
    - {RUN_DIR}/assumption_ladder.md
    - {RUN_DIR}/assumption_ladder.json
    Both must end with a "### Step 4b verification log" section.

    ## Forbidden
    - Do NOT modify a verification result's content.
    - Do NOT begin the derivation script.
```

Polling, audit.

#### Checkpoint #2 (interactive, unless INTERACTIVE=false)

Main agent prints:

> ✦ **Checkpoint #2 — notation + assumption ladder + verification results**
>
> **Notation table**:
> {full content of `${RUN_DIR}/notation_table.md`}
>
> **Assumption ladder** (with Step 4b verification status):
> {full content of `${RUN_DIR}/assumption_ladder.md`}
>
> Verification summary: {N_confirmed} confirmed, {N_partial} partial,
> {N_not_found} not_found, {N_disputed} disputed, {N_error} errors.
>
> Please reply with:
> - **ok** — proceed to symbolic derivation
> - **fix N: <change>** — describe a change to assumption #N (e.g.
>   "fix D3: weaken to 'beta_2 fluctuation is symmetric about its mean'");
>   I'll re-dispatch Call type D with the patch
> - **add: <new assumption>** — add a missing assumption
> - **restart** — back to Step 2 (often needed if Verification surfaces
>   that a card was misextracted)
> - **stop** — abort

Wait for user response.

### Step 5: Symbolic derivation [Subagent: theory-synthesizer — Call type F]

Dispatch ONE synthesizer subagent:

```yaml
Agent:
  description: "Build + run symbolic derivation"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are operating as a `theory-synthesizer` subagent, Call type F
    (derivation_script + derivation_steps). See:
        agents/subagents/theory-synthesizer.md

    ## Inputs
    - Cards directory: {RUN_DIR}/cards/
    - Chain sketch: {RUN_DIR}/chain_sketch.md
    - Notation table JSON: {RUN_DIR}/notation_table.json
    - Assumption ladder JSON: {RUN_DIR}/assumption_ladder.json
    - Target spec: {RUN_DIR}/derivation-target.md (especially §6 desired
      form of the final answer)
    - Output language: {output_language}
    - SymPy tool: tools/symbolic_derive.py (you CALL it from inside this
      subagent; the main agent will not)
    - SymPy schema: `python3 tools/symbolic_derive.py schema`

    ## Outputs (all three mandatory)
    - {RUN_DIR}/derivation_script.json
    - {RUN_DIR}/derivation_trace.json
    - {RUN_DIR}/derivation_steps.md

    ## Workflow
    1. Build derivation_script.json from cards + notation + ladder.
       Every equation in the script must trace back to either a card
       candidate_equation OR a tier-1 user_axiom from the ladder.
    2. Run:
         python3 tools/symbolic_derive.py run \\
             --script {RUN_DIR}/derivation_script.json \\
             --output {RUN_DIR}/derivation_trace.json
    3. If trace.overall_status == "failed", diagnose, fix the script,
       re-run. Repeat at most {SYMPY_SCRIPT_MAX_RETRIES} times.
    4. Write derivation_steps.md enumerating each step verbatim from
       the trace, plus a `## Final equation` section showing the
       target observable's analytic form.

    ## Forbidden
    - Do NOT write any equation in derivation_steps.md that is not
      verbatim from derivation_trace.json.
    - Do NOT do any algebra "by hand" outside the script.
    - Do NOT proceed to the hep-theory review.
```

Polling, audit.

After the subagent returns, the main agent reads only the
`overall_status` field of `derivation_trace.json` (small JSON, this is
an explicit boundary exception for routing). If `overall_status ==
"failed"`, surface to user and STOP — do not proceed to Step 6 on a
broken derivation.

#### Checkpoint #3 (interactive, unless INTERACTIVE=false)

Main agent prints:

> ✦ **Checkpoint #3 — symbolic derivation**
>
> {full content of `${RUN_DIR}/derivation_steps.md`}
>
> Trace: `${RUN_DIR}/derivation_trace.json` (SymPy-auditable).
>
> Please reply with:
> - **ok** — proceed to hep-theory review + report
> - **fix step N: <change>** — describe a change to step N (e.g.
>   "fix step 3: substitute eq_omega_beta2 BEFORE expanding"); I'll
>   re-dispatch Call type F with the patch
> - **add check: <check>** — add a sanity check (e.g.
>   "add check: limit_check beta_2 -> 0 expected 0")
> - **restart from N** — re-run from step N onward (keeps steps 1..N-1)
> - **stop** — abort

Wait for user response.

### Step 6: hep-theory review [Subagent: hep-theory-reviewer]

Dispatch the existing `hep-theory-reviewer` subagent
(`agents/subagents/hep-theory-reviewer.md`) — no new agent role.

```yaml
Agent:
  description: "hep-theory review of derivation"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are operating as a `hep-theory-reviewer`. Read your full role:
        agents/subagents/hep-theory-reviewer.md

    ## Inputs
    - Derivation steps: {RUN_DIR}/derivation_steps.md
    - Derivation trace: {RUN_DIR}/derivation_trace.json (especially
      checks[] — read these first)
    - Notation table: {RUN_DIR}/notation_table.md
    - Assumption ladder: {RUN_DIR}/assumption_ladder.md (with Step 4b
      verification status)
    - Target spec: {RUN_DIR}/derivation-target.md (especially §5
      validity regime and §9 acceptance criteria)
    - Cards: {RUN_DIR}/cards/  (for cross-checking equation provenance)

    ## Output
    Write {RUN_DIR}/verification_report.md following the
    hep-theory-reviewer output format (Score / Verdict / Critical
    weaknesses / Minimum fix). Add a per-step audit table:

    | Step | Operation | Verdict | Comment |
    |---|---|---|---|

    And a section "Acceptance criteria audit" mapping each criterion in
    derivation-target.md §9 to PASS / FAIL / NOT_TESTED with a
    one-line rationale.

    ## Forbidden
    - Do NOT modify the derivation (you are reviewing, not fixing).
    - Do NOT re-run symbolic_derive.py.
    - Do NOT chain to another subagent.
```

Polling, audit.

### Step 7: Final report [Subagent: paper-editor]

```yaml
Agent:
  description: "Compose derivation report"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are the report writer for the analytic-derivation skill.

    ## Inputs (read every file that exists)
    - {RUN_DIR}/derivation-target.md
    - {RUN_DIR}/cards/paper_*.json
    - {RUN_DIR}/chain_sketch.md
    - {RUN_DIR}/notation_table.md
    - {RUN_DIR}/assumption_ladder.md
    - {RUN_DIR}/derivation_steps.md
    - {RUN_DIR}/derivation_trace.json (for final_equations + checks)
    - {RUN_DIR}/verification_report.md
    - {RUN_DIR}/verification/lit_check_*.json (for §8 summary table)
    - Template: templates/DERIVATION_REPORT_TEMPLATE.md
    - Output language: {output_language}

    ## Output
    Write {RUN_DIR}/derivation-report.md following the template
    exactly. Specifically:

    - §0 TL;DR: filled from derivation_trace.final_equations and
      verification_report acceptance audit
    - §1: verbatim echo of derivation-target.md sections 1, 3, 4, 5, 6
    - §2: one subsection per card; condense its
      `candidate_equations[]` table and `stated_assumptions[]`
    - §3: copy chain_sketch.md verbatim (just the DAG, not the
      unresolved-segments scratchpad)
    - §4: copy notation_table.md verbatim
    - §5: copy assumption_ladder.md verbatim
    - §6: render derivation_steps.md as the report's Step section.
      Every equation MUST be verbatim from derivation_trace.json.
    - §7: condense verification_report.md
    - §8: build the table from lit_check_*.json files
    - §9: Human verification checklist — assemble from:
          * every assumption whose status is in
            {not_found, disputed, verifier_error, needs_human_review}
          * every check in derivation_trace.json whose status != "ok"
          * every acceptance criterion in §9 of target spec that
            verification_report.md marked FAIL or NOT_TESTED
    - §10: suggested next actions (template defaults are fine)
    - §11: resume hints (template defaults)

    ## Forbidden
    - Do NOT invent any equation, number, or paper.
    - Do NOT chain to another skill (Suggested next actions strings
      are USER-FACING text only).
```

Polling, audit:

```bash
test -s "${RUN_DIR}/derivation-report.md" || exit 1
grep -q '^## 0. TL;DR' "${RUN_DIR}/derivation-report.md" || exit 1
grep -q '^## 6. Derivation steps' "${RUN_DIR}/derivation-report.md" || exit 1
grep -q '^## 9. Human verification checklist' "${RUN_DIR}/derivation-report.md" || exit 1
```

#### Final print to user

Main agent prints:

> ✦ **Done — analytic derivation report written**
>
> File: `${RUN_DIR}/derivation-report.md`
> Wall-clock used: {minutes} min
> Steps executed: {step_count}; checks passed: {n_ok}/{n_total}
> Items still on the human verification checklist: {N_needfix}
>
> {one-line TL;DR copied from §0 of the report}
>
> Suggested next actions are at §10 of the report.
>
> ⚠ One-shot reviews catch at most one or two classes of error per
> derivation. If this derivation is load-bearing for downstream work,
> consider running:
>   - `/skill:derivation-refine-loop "${RUN_DIR}"` — multi-round
>     adversarial review with automatic synthesizer / lit-verifier
>     routing; default 4 rounds × 4 reviewer roles in parallel.
>
> Reminder: this skill is INTERACTIVE on purpose. If a future
> derivation is more like a literature query or a single-paper question,
> use the lighter skills:
>   - `/skill:research-debug "<question>"` — for in-progress questions
>   - `/skill:research-lit "<topic>" — deep analyze: true` — for single-paper deep reads
>
> These are USER commands. This skill does NOT invoke them
> automatically.

---

## Key Rules Summary

1. **Main agent NEVER does algebra.** Every equation flows through
   SymPy via the synthesizer subagent. The main agent reads only
   `overall_status` of `derivation_trace.json`, never the equations
   themselves.
2. **Main agent NEVER reads paper bodies.** Same boundary as the
   idea-* and research-debug skills. Main agent MAY read `paper_card.json`
   (≤10 KB structured index) but not `deep_analysis.md`.
3. **Interactive by default.** Three checkpoints (after chain sketch,
   after assumption ladder, after derivation). Override with `—
   interactive: false` only when you've done at least one interactive
   pass and trust the spec.
4. **User axioms are sacred.** Tier-1 ladder entries (the user's
   bridging assumptions from §3 of the spec) are never sent to the
   lit-verifier — they are taken as given, by definition. Only tier-2
   (paper-stated) and tier-3 (derivation-implied) go through Step 4b.
5. **Literature verification gates the final report.** Items that
   return `not_found` / `disputed` / `verifier_error` from Step 4b are
   automatically promoted to §9 of the final report as "human
   verification required". They do NOT silently dissolve into the
   derivation as if confirmed.
6. **No fabricated equations.** `derivation_steps.md` and §6 of the
   final report contain only equations that appear verbatim in
   `derivation_trace.json`. If the synthesizer wants a cleaner form,
   it adds a `simplify` or `expand` step and re-runs.
7. **No skill chaining.** The "Suggested next actions" strings in the
   report are USER-FACING — the skill never invokes them.
8. **Resume-friendly.** A second invocation in the same `run_slug`
   directory reuses every existing artifact whose mtime is recent.
   Deleting a single card forces re-extraction; deleting the
   assumption ladder forces re-verification.
9. **Hard cap of 8 anchor papers.** More than that is a sign the
   chain is too vague to derive; the skill refuses to start.
10. **SymPy self-audit before every run.** Step 0b calls
    `check-deps` and `selftest`; a broken SymPy install aborts the
    skill before any subagent spend.

---

## Relationship to the rest of the pipeline

| When you are… | Use this skill | Use this OTHER skill |
|---|---|---|
| At the very start, with a fuzzy idea | — | `/skill:idea-landscape` |
| About to commit to a concrete direction | — | `/skill:idea-novelty` |
| Considering whether key assumptions hold (pre-investment) | — | `/skill:idea-feasibility` |
| Mid-project, stuck on a specific question | — | `/skill:research-debug` |
| Need a single paper read deeply | — | `/skill:research-lit "..." — deep analyze: true` |
| Writing the formal proposal | — | `/skill:research-proposal` |
| **Have a target observable + anchor papers + bridging assumptions and want an analytic formula** | **`/skill:analytic-derivation`** | — |
| Have an existing derivation and want it hardened by multi-round adversarial review | — | `/skill:derivation-refine-loop` |

`analytic-derivation` is the only skill in this pipeline that produces
an executable SymPy script as a primary artifact. It is also the only
skill that integrates a literature-verification pass inline with
derivation construction.
