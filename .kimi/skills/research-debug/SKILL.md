---
name: research-debug
description: Cheap, interactive, in-research literature query. Use when you are IN THE MIDDLE of a running project (not at the start) and hit a specific blocker — a confusing experimental result, an unfamiliar technique someone mentioned, a sub-problem that needs a precedent. Unlike `idea-landscape` / `idea-novelty` / `idea-feasibility`, this skill is INTERRUPTIVE by design: it crystallizes the question with you, sketches an answer from model knowledge first, shows a dry-run search plan, and only THEN burns API budget on light paper reads. Targets minutes, not hours. Reads `project-state.md` as ambient context. Designed for high-energy nuclear physics × deep learning crossover projects.
argument-hint: [in-progress-question]
---

# Research Debug — In-Progress Literature Query

User question: $ARGUMENTS

## Why This Skill Exists

The other four skills in this pipeline (`idea-landscape`, `idea-novelty`, `idea-feasibility`, `research-proposal`) are **project-start** tools — they run for hours and produce overnight reports. That is the WRONG shape for questions that arise mid-project:

> "Why did my v2{4} prediction go negative after I added gradient clipping?"
> "Has anyone used an SE(3)-equivariant GNN for inclusive jet substructure?"
> "What's the right way to do Bayesian posterior calibration when the simulator is itself a neural surrogate?"

These questions are **specific, context-heavy, and you want an answer NOW** — not in 4 hours. They are also the kind of question keyword search fails on, because the search engine can't see your project state. This skill solves both: it pulls your `project-state.md` in as ambient context, and it runs in cheap → expensive order with checkpoints, so a misunderstanding costs minutes, not hours.

## Constants

- **OUTPUT_DIR = `research-debug/`** — Each invocation creates `research-debug/{question_slug}/`.
- **PROJECT_STATE_PATH = `project-state.md`** — REQUIRED. If missing, skill bootstraps it from the template and exits (Step 0b).
- **PROJECT_STATE_TEMPLATE = `templates/PROJECT_STATE_TEMPLATE.md`** — Source for bootstrap.
- **REPORT_TEMPLATE = `templates/RESEARCH_DEBUG_REPORT_TEMPLATE.md`** — Final report layout.
- **DEPTH = "L1"** — Default depth ceiling. Allowed: `L0` (clarify only), `L1` (clarify + sketch, no search), `L2` (clarify + sketch + dry-run + light paper read). L3-equivalent work is NOT performed here; the skill prints a hand-off note for `/skill:research-lit` instead. Override via `— depth: L2`.
- **LIGHT_READ_MAX = 3** — Maximum papers to light-read in L2. Each light read is abstract + intro + ≤2 key figures, NOT a full `deep_analysis.md`.
- **LIGHT_READ_CONCURRENCY = 3** — Maximum concurrent light-reader subagents. Hard cap.
- **DRY_RUN_CANDIDATE_MAX = 8** — Candidate papers surfaced in the L2 dry-run (title + abstract only, no read).
- **SUBAGENT_TIMEOUT = 1800** — Per-subagent timeout (30 min). HALF of the idea-* skills' 3600 s because light reads must be fast — that's the whole point.
- **OUTPUT_LANGUAGE = "auto"** — Follows the shared output-language protocol.
- **REUSE_IDEA_SURVEY = true** — When `idea-survey/` exists, subagents may read upstream report bodies and reuse `literature-deep/` analyses. Override via `— reuse-idea-survey: false`.
- **CONTEXT_FROM_HEP_FRAMEWORK = `skills/shared-references/hep-research-framework.md`** — Loaded by subagents for HEP vocabulary.

> 💡 Overrides:
> - `/skill:research-debug "question" — depth: L1` — sketch only, no search (default; ~3–5 min)
> - `/skill:research-debug "question" — depth: L2` — sketch + dry-run + light-read (~15–25 min, max 3 papers)
> - `/skill:research-debug "question" — depth: L0` — clarify only (~1 min, no answer attempted)
> - `/skill:research-debug "question" — language: zh` — output in Chinese
> - `/skill:research-debug "question" — depth: L2 — light-read-max: 2` — narrower L2
> - `/skill:research-debug "question" — reuse-idea-survey: false` — ignore existing idea-survey/ files

---

## 🚧 Main Agent Boundary Protocol — ORCHESTRATE + DIALOGUE 🚧

> Same spirit as the idea-* skills' boundary protocol, with **one explicit difference**: the main agent IS allowed to read `project-state.md` and to print user-facing dialogue messages between steps. It still must NOT read paper content or write paper analysis directly.

### What the main agent MAY do

1. **Read `project-state.md` in full.** This is the user's own context file, not a paper. The main agent uses it to populate dialogue prompts and the L0 clarification. (Size cap: the file is hand-maintained and typically < 20 KB. If it exceeds 50 KB, the main agent reads only sections 0–4 and §6.)
2. **Read `idea-survey/landscape-report.md`, `novelty-report.md`, `feasibility-report.md` AT THE METADATA LEVEL ONLY** — i.e., the first 100 lines of each (title, deep-analysis index table). Do NOT read paragraph-level synthesis prose for the main-agent's own reasoning.
3. **Print user-facing checkpoint messages** and **wait for user response** between sub-stages. This skill is interactive on purpose.
4. Run **shell commands** (`mkdir`, `cp`, `find`, `ls`, `wc`, `grep`, `test`, `sed`).
5. Run **Python tool scripts** in `tools/`.
6. Launch **subagents** via the `Agent` tool.
7. Apply the **polling protocol** and collect subagent outputs.
8. **Audit** subagent outputs at the file-system level only.
9. Write **small structured files** (JSON, the final report file).

### What the main agent MUST NOT do

- ❌ **Read** any `deep_analysis.md`, `figure_manifest.json`, or figures under `literature-deep/paper_*/`. Delegate to a `paper-analyzer` subagent.
- ❌ **Read** PDF / TeX / abstract bodies of papers found in L2 search. The light-reader subagent does that.
- ❌ **Write** synthesis prose that summarizes paper content. (Synthesis from `project-state.md` plus its own model knowledge for L1 IS allowed — that's the sketch.)
- ❌ **Chain to another skill.** Kimi does not allow skill-to-skill invocation. The main agent may PRINT to the user "now run /skill:research-lit yourself", but it MUST NOT attempt to invoke another `/skill:` itself.
- ❌ **Fall back to direct paper reading** when a subagent is slow.

### The interaction model — clear rules

| Sub-stage | Interactive? | Main agent reads | Subagent type |
|---|---|---|---|
| Step 0 (bootstrap) | No (exits if state missing) | `project-state.md` (if it exists) | none |
| Step 1 (L0 clarify) | YES — prints + waits | `project-state.md`, idea-survey headers | none |
| Step 2 (L1 sketch) | YES — prints + waits | nothing additional | none |
| Step 3 (L2 dry-run plan) | YES — prints + waits | nothing additional | 1 search subagent |
| Step 4 (L2 light read) | No (runs to completion) | nothing | up to {LIGHT_READ_MAX} light-reader subagents |
| Step 5 (final report) | No | nothing additional | 1 report-writer subagent |

If the user is in a batch mode (e.g., they pre-answered all checkpoints), the main agent treats their original `$ARGUMENTS` as the sole input and proceeds without printing checkpoint prompts. Otherwise, it prints and waits.

---

## Language Determination

1. Parse `$ARGUMENTS` for `— language:` override (`zh`, `en`).
2. If no override, follow the [Output Language Protocol](../shared-references/output-language.md).
3. If the user's `project-state.md` §8 specifies `language_for_output`, use that.
4. Propagate `output_language` to all subagent prompts and the report file.

---

## Workflow

### Step 0a: Argument parsing

Parse `$ARGUMENTS` for:
- The free-text question (required, non-empty)
- `— depth: L0|L1|L2` (default L1)
- `— language: zh|en` (default auto)
- `— light-read-max: N` (default `LIGHT_READ_MAX`, max 5)
- `— reuse-idea-survey: true|false` (default true)

Compute `question_slug` from the question:
```bash
python3 -c "
import re, sys
q = sys.argv[1].strip().lower()
slug = re.sub(r'[^a-z0-9]+', '-', q)[:60].strip('-')
if not slug:
    slug = 'question'
print(slug)
" "$USER_QUESTION"
```

Append a short timestamp suffix so repeated similar questions don't collide:
```bash
SUFFIX=$(date +%m%d-%H%M)
SLUG="${SLUG}-${SUFFIX}"
mkdir -p "research-debug/${SLUG}/"
```

### Step 0b: Project-state bootstrap (if needed)

```bash
if [ ! -s project-state.md ]; then
    cp templates/PROJECT_STATE_TEMPLATE.md project-state.md
    echo "BOOTSTRAP" > research-debug/.bootstrap_flag
fi
```

If `.bootstrap_flag` was created, the main agent prints:

> 📋 No `project-state.md` was found in this project, so I copied the template into place. This file is the ambient context for every future `/skill:research-debug` run — please fill it in once, then re-invoke the skill with your question. Sections that matter most for in-progress queries: §1 Physics Context, §2 ML Context, §3 Cross-Domain Bridge, §6 Open Questions, §7 Glossary.

…and STOPS. Do not run L0/L1/L2. The user must fill project-state.md first.

If `project-state.md` exists but is too sparse (a heuristic: fewer than 40 non-comment non-blank lines), the main agent prints a soft warning and continues anyway:

```bash
LIVE_LINES=$(grep -v '^[[:space:]]*<!--' project-state.md | grep -v '^[[:space:]]*$' | wc -l)
if [ "$LIVE_LINES" -lt 40 ]; then
    echo "⚠️  project-state.md is unusually sparse ($LIVE_LINES non-blank, non-comment lines)."
    echo "    The L0 clarification will work with less context. Consider filling more of it later."
fi
```

### Step 0c: Context loading

Main agent reads:
1. `project-state.md` (full file, capped at 50 KB)
2. `idea-survey/landscape-report.md` (first 100 lines only) — if exists and `REUSE_IDEA_SURVEY` is true
3. `idea-survey/novelty-report.md` (first 100 lines only) — same condition
4. `idea-survey/feasibility-report.md` (first 100 lines only) — same condition

Cache as in-memory strings for prompt building. **Do NOT** read upstream report bodies past line 100 — that's the synthesis prose, which is the subagent's input, not the main agent's.

Also enumerate (paths only, no read) what's already in `idea-survey/literature-deep/` if it exists:
```bash
ls idea-survey/literature-deep/ 2>/dev/null > research-debug/${SLUG}/.existing_deep.txt || true
```

---

### Step 1: L0 — Question Crystallization (interactive)

> Main agent does this directly. NO subagent is launched. Cost: ~30 seconds of model output. Goal: surface misreadings BEFORE any expensive work.

The main agent writes — directly into `research-debug/${SLUG}/L0_clarify.md` — its restatement of the question, 2 or 3 alternative readings, the glossary terms it had to disambiguate, and the inferred "type of help" each reading implies. It then PRINTS this content to the user verbatim and asks for a selection.

Prompt template for the main agent's own L0 production (NOT a subagent):

```
Using project-state.md and the user's question, produce a short L0 clarification:

1. ONE-LINE RESTATEMENT — in your own words, no jargon the user did not use first.
2. 2–3 ALTERNATIVE INTERPRETATIONS labeled (A), (B), [(C)]. For each, name:
   - the wording you used to disambiguate;
   - which "type of help" it implies, chosen from:
     literature-precedent / mechanism-explanation / SOTA-pointer /
     experimental-suggestion / debug-strategy / sanity-check
3. AMBIGUOUS TERMS detected — pull from project-state.md §7 Glossary if present.
   For each term, state the reading you would use AND the reading you would reject.
4. DO NOT attempt to answer the question itself in L0. Stop at the restatement.
5. Output language: {output_language}.
```

Write the L0 deliverable to `research-debug/${SLUG}/L0_clarify.md`.

**User checkpoint #1**:

The main agent prints to chat:

> ✦ **L0 — question crystallization**
>
> {full content of L0_clarify.md}
>
> Please reply with:
> - **A**, **B**, or **C** to pick an interpretation, OR
> - a short rewording of the question, OR
> - **stop** to abort here.
>
> (If you want to skip clarification next time for a similar question, prepend `— depth: L1` and your reworded question to the next invocation.)

Wait for user response.

- If user picks (A)/(B)/(C): record `chosen_branch` and proceed.
- If user provides reworded question: replace `USER_QUESTION` with the rewording, re-run L0 ONCE with the new wording. If they reword a second time, just accept the wording without re-running L0 (avoid infinite ping-pong).
- If user says "stop" or `depth=L0`: write the final report at L0 only and exit.

Save the chosen branch into `research-debug/${SLUG}/.l0_selection.json`:
```json
{"chosen_branch": "A", "user_comment": "...", "final_question": "..."}
```

If `DEPTH == "L0"`, jump to Step 5 (Report) and stop there.

---

### Step 2: L1 — Knowledge-Only Sketch (interactive)

> Main agent writes the sketch using ITS OWN model knowledge — NO web search, NO paper reads. This is the "sketch-before-search" pattern. If the sketch is wrong, the search would also be wrong; catching it here costs seconds.

Main agent produces `research-debug/${SLUG}/L1_sketch.md` directly. Prompt template (main agent self-prompting):

```
You are answering the user's clarified question using ONLY:
  - your training-time knowledge,
  - the contents of project-state.md (passed inline below),
  - the metadata-level summaries from idea-survey/ (first 100 lines of each report).

You may NOT use WebSearch, arxiv_fetch.py, or any tool that retrieves paper content.

Produce:

1. ONE-PARAGRAPH ANSWER (4–8 sentences). Speak in concrete domain terms. Use
   the chosen interpretation from L0.

2. SELF-ASSESSED CONFIDENCE, four lines:
   - Domain framing correct          : HIGH / MEDIUM / LOW + one-line reason
   - Specific technique referenced is real
                                     : HIGH / MEDIUM / LOW + one-line reason
   - Numbers / scaling quoted from memory
                                     : HIGH / MEDIUM / LOW + one-line reason
       (If you quoted any number, FLAG it. Numbers from training memory are
        the single most common fabrication mode.)
   - Translation between HEP and ML vocabulary
                                     : HIGH / MEDIUM / LOW + one-line reason

3. CANDIDATE SEARCH TERMS for the optional L2 stage — 3 to 6 terms with a
   one-line justification each. These are the terms you would put into arXiv
   if you were promoted.

4. KEYWORD LANDMINES — 1 to 3 terms that LOOK relevant but would mislead the
   search. Name what wrong topic they would surface.

5. CAVEATS — explicit list of things you are NOT sure of in the sketch.

Output language: {output_language}.
```

Write the L1 deliverable to `research-debug/${SLUG}/L1_sketch.md`.

**User checkpoint #2**:

The main agent prints:

> ✦ **L1 — knowledge-only sketch**
>
> {full content of L1_sketch.md}
>
> Please reply with:
> - **good** — sketch is enough, stop here (most common; ~80% target)
> - **L2** — promote to dry-run + light paper read (~15–25 min)
> - **restart** — sketch is off, take me back to L0 with a new wording
> - **stop** — abort

Wait for user response.

- If `good`: jump to Step 5 (Report) with L1 only.
- If `L2`: proceed to Step 3.
- If `restart`: clear `.l0_selection.json`, return to Step 1 with the user's new wording.
- If `stop`: abort cleanly.

If `DEPTH == "L1"` AND the user explicitly chose `L2`, override `DEPTH` to `L2`
(user choice wins). If `DEPTH == "L2"` from the start, the prompt is still
shown but the default branch is `L2`.

---

### Step 3: L2 — Dry-Run Search Preview (interactive)

> Main agent does NOT run searches. The dry-run-search-agent subagent does. This step generates a SEARCH PLAN and a list of CANDIDATE PAPERS by title + abstract only — no paper bodies are read yet. The user approves the plan before any light read happens.

**Inputs to dry-run-search-agent**:
- The clarified question (from `.l0_selection.json`)
- The L1 sketch (`L1_sketch.md`) — for candidate search terms
- The candidate search terms list (from L1)
- `project-state.md` (for domain disambiguation)
- `output_language`
- Already-analyzed papers list (`.existing_deep.txt`)

**Expected output**: `research-debug/${SLUG}/L2_dryrun.json` AND `research-debug/${SLUG}/L2_dryrun.md`.

#### Launch dry-run-search-agent

```yaml
Agent:
  description: "L2 dry-run search plan"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are an L2 dry-run search planner for the research-debug skill. Your job
    is to produce a SEARCH PLAN and a CANDIDATE PAPER LIST. You do NOT read any
    paper body. You do NOT write any synthesis. You do NOT decide what is the
    answer — that's the user's call in the next checkpoint.

    ## File handling rules
    - Do NOT call ReadMediaFile. No images here.
    - Do NOT extract paper figures, equations, or tables.
    - Do NOT write deep_analysis.md.

    ## Inputs (read these in full)
    - Clarified question: "{final_question}"
    - L1 sketch: research-debug/{question_slug}/L1_sketch.md
    - Project state: project-state.md
    - HEP vocabulary reference: skills/shared-references/hep-research-framework.md
    - Already-deep-analyzed papers list: research-debug/{question_slug}/.existing_deep.txt
    - Output language: {output_language}

    ## Search plan (produce 4–6 queries)
    Build 4–6 queries that cover:
      - the literal phrasing of the question,
      - the L1 candidate search terms (verbatim),
      - 1 query specifically aimed at HEP-side precedents (use INSPIRE-HEP-style phrasing),
      - 1 query specifically aimed at ML-side precedents (use NeurIPS/ICML-style phrasing).
    For each query record: query string, target source ("arxiv" | "inspire-hep" |
    "semantic-scholar" | "websearch"), one-line rationale.

    ## Execute searches
    For EACH query in the plan:
      - arXiv: `python3 tools/arxiv_fetch.py search "QUERY" --max 6`
      - INSPIRE-HEP: WebSearch with `site:inspirehep.net QUERY` (or direct API if
        you can construct it)
      - Semantic Scholar: `python3 tools/semantic_scholar_fetch.py search "QUERY" --max 6`
        (if the tool exists; else skip silently)
      - Plain web: WebSearch

    ## Merge & rank
    Deduplicate by arXiv ID first, normalized title second.
    Cap the merged list at {DRY_RUN_CANDIDATE_MAX} papers.
    Rank each paper as relevance HIGH / MEDIUM / LOW by reading the ABSTRACT
    ONLY (no PDF). Recommend YES / NO for light-reading.
    Mark already-deep-analyzed papers as `reused: true` with the existing
    analysis path; these still count toward HIGH/MEDIUM ranking but should
    automatically be `recommend_light_read: false` since a deeper analysis
    already exists.

    ## Targeted questions
    Produce 3 TARGETED QUESTIONS that the L2 light-read step will ask each
    paper. Each question should be answerable from a paper's abstract + intro +
    1–2 key figures. If a question requires a full deep-read, REPHRASE it
    (or flag it for the user to consider promoting to /skill:research-lit
    instead).

    ## Output
    Write TWO files:

    ### File A: research-debug/{question_slug}/L2_dryrun.json
    ```json
    {
      "final_question": "...",
      "queries": [
        {"id": 1, "query": "...", "source": "arxiv", "rationale": "..."},
        ...
      ],
      "candidates": [
        {
          "rank": 1,
          "title": "...",
          "first_author": "...",
          "year": 2024,
          "venue": "...",
          "arxiv_id": "2401.xxxxx",
          "abstract_gist": "≤1 line",
          "relevance": "HIGH|MEDIUM|LOW",
          "recommend_light_read": true,
          "reused": false,
          "existing_analysis_path": null,
          "found_via_query_ids": [1, 3]
        }
      ],
      "targeted_questions": [
        "1. ...",
        "2. ...",
        "3. ..."
      ]
    }
    ```

    ### File B: research-debug/{question_slug}/L2_dryrun.md
    Human-readable version of the JSON, formatted as in the
    "L2 — Dry-Run Preview" section of templates/RESEARCH_DEBUG_REPORT_TEMPLATE.md.

    ## Forbidden
    - Do NOT read any paper PDF or TeX.
    - Do NOT write a synthesis or an answer to the user's question.
    - Do NOT light-read any paper at this stage.
```

#### Apply polling (Pattern 2 — identical to the idea-* skills' protocol)

```
PHASE 1: sleep 120 → TaskList → collect completed
PHASE 2: sleep  60 → TaskList → collect
PHASE 3: while active: sleep 30 → TaskList → collect
PHASE 4: timeout or error → TaskStop → ONE retry with identical prompt
                 If retry also fails: log FINAL_FAILED, print failure to user, abort L2.
```

#### Audit:
```bash
test -s research-debug/${SLUG}/L2_dryrun.json || exit 1
python3 -m json.tool < research-debug/${SLUG}/L2_dryrun.json > /dev/null || exit 1
test -s research-debug/${SLUG}/L2_dryrun.md || exit 1
grep -q '"candidates"' research-debug/${SLUG}/L2_dryrun.json || exit 1
```

**User checkpoint #3**:

The main agent prints:

> ✦ **L2 — dry-run search plan**
>
> {full content of L2_dryrun.md}
>
> The above is the PLAN, not the answer. No paper bodies have been read yet.
>
> Please reply with:
> - **go** — plan looks right, run the light-read on the YES-marked papers
> - **edit** — tell me which queries / papers / questions to change; I'll re-run the dry-run
> - **narrow N1,N2,N3** — only light-read papers with these rank numbers (overrides YES/NO)
> - **cancel** — sketch was actually enough; finalize report with L1 only
> - **promote** — this needs a full deep read; print a `/skill:research-lit` hand-off and stop

Wait for user response.

- `go`: proceed to Step 4 with `recommend_light_read == true` candidates, capped at LIGHT_READ_MAX.
- `edit ...`: pass the edit instructions back to dry-run-search-agent as a new prompt (single retry, same subagent type).
- `narrow N1,N2,N3`: filter candidates by rank to those IDs; proceed to Step 4.
- `cancel`: jump to Step 5 with L0+L1 only.
- `promote`: skip Step 4, print hand-off and finalize report.

Save the selection into `research-debug/${SLUG}/.l2_selection.json`:
```json
{"action": "go|narrow|cancel|promote",
 "selected_papers": [{"rank": 1, "arxiv_id": "...", ...}, ...]}
```

---

### Step 4: L2 — Light Paper Read (subagents, no interruption)

> Main agent does NOT read papers. Up to {LIGHT_READ_MAX} `paper-analyzer` subagents do the light reads in parallel. Each light read is **abstract + intro + ≤2 key figures**, NOT a full deep_analysis.md.

#### Pre-flight per paper

For each selected paper:

1. **If `reused == true`** (paper was already deep-analyzed in `idea-survey/literature-deep/paper_*/deep_analysis.md`):
   - Do NOT relaunch a subagent for figure-by-figure analysis.
   - Launch a "lightweight extractor" subagent that reads the EXISTING `deep_analysis.md` and answers only the 3 targeted questions, writing to `research-debug/${SLUG}/light/paper_{rank}.md`.

2. **Else** (new paper):
   - Create workspace: `mkdir -p research-debug/${SLUG}/light/paper_{rank}_workspace/`
   - If arXiv ID is available: download metadata + PDF only (no TeX source, no MinerU, no PyMuPDF figure extraction — light reads do NOT need figure manifests).
     ```bash
     python3 tools/arxiv_fetch.py download {arxiv_id} \
         --dir research-debug/${SLUG}/light/paper_{rank}_workspace/
     ```
   - If no arXiv ID: log `"status": "skipped — no arxiv id, skipping for L2 light read"`.

#### Launch light-reader subagents (one per selected paper)

CRITICAL: Maintain `LIGHT_READ_CONCURRENCY <= 3`. Queue and launch as slots free.

```yaml
Agent:
  description: "L2 light read: {short_title}"
  subagent_type: "paper-analyzer"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are a LIGHT paper reader for the research-debug skill. Your job is
    fast, focused, and narrow: answer THREE specific questions about this
    paper using only its abstract, introduction, and at most TWO key figures.
    You are NOT writing a deep_analysis.md. You are NOT analyzing every figure.

    ## File handling rules
    - Time budget: 30 minutes hard. Stop early if you have the answers.
    - Read the PDF using your existing PDF-handling capability (text first).
      You MAY use ReadMediaFile on the PDF's first two pages if rendered, but
      LIMIT yourself to ≤2 figures total — pick the figure(s) most relevant to
      the targeted questions.
    - Do NOT download TeX source. Do NOT run MinerU. Do NOT extract every figure.

    ## Inputs
    - Paper PDF: {pdf_path}
    - Paper metadata: title="{title}", authors="{authors}", year={year},
      venue="{venue}", arxiv_id="{arxiv_id}"
    - Targeted questions (from the dry-run):
      Q1: {targeted_q1}
      Q2: {targeted_q2}
      Q3: {targeted_q3}
    - Original user question (for context): "{final_question}"
    - Project state: project-state.md (read sections §1, §2, §3, §6 ONLY)
    - Output language: {output_language}

    ## Per-question protocol
    For each Q in [Q1, Q2, Q3]:
      1. Find the part of the abstract + intro that addresses it (or note "the
         paper does not directly address Q").
      2. If a figure or table is essential to the answer AND you have not yet
         used your 2-figure budget, use ReadMediaFile on that figure.
      3. Write a one-line FINDING grounded in a verbatim phrase from the paper.
         Cite the section name and rough location ("§3.2", "Table 2").
      4. Mark `directly_addresses: YES / PARTIAL / NO`.

    ## Output: research-debug/{question_slug}/light/paper_{rank}.md
    Structure:
      # {title} — light read for question "{final_question_short}"
      - arxiv_id: ...
      - first_author / year / venue
      - light_read_time_used_minutes: ...
      - figures_consulted: [list of figure labels, ≤2]

      ## Q1: {targeted_q1}
      - finding: ...
      - quoted_evidence: "..." (verbatim, ≤2 sentences, with section ref)
      - directly_addresses: YES|PARTIAL|NO

      ## Q2: ...
      ## Q3: ...

      ## Honest caveats
      - {what_you_did_not_check_due_to_time_budget}
      - {what_would_need_a_full_deep_read_to_resolve}

      ## Recommendation
      - suggest_full_deep_read: YES | NO + one-line reason

    ## Forbidden
    - Do NOT invent numbers or section references.
    - Do NOT write a full deep_analysis.md.
    - Do NOT read every figure.
    - Do NOT answer the user's ORIGINAL question synthetically — only answer
      Q1/Q2/Q3 paper-by-paper. Synthesis is done by the report-writer subagent
      in Step 5.
```

#### Polling, retry

Pattern 2 with timeouts adjusted (PHASE 1: sleep 180, PHASE 2: sleep 60, PHASE 3: sleep 30).

If a paper's subagent fails twice, mark `"status": "FINAL_FAILED"` in `.light_status.json` and continue with the remaining papers. Do NOT fall back to main-agent direct reading.

#### Audit:
```bash
for r in $(jq '.selected_papers[].rank' research-debug/${SLUG}/.l2_selection.json); do
    test -s research-debug/${SLUG}/light/paper_${r}.md \
        || echo "paper_${r}.md missing — recording as FINAL_FAILED"
done
```

Build `research-debug/${SLUG}/.light_status.json` listing each paper's status (`ok`, `FINAL_FAILED`, `skipped`).

---

### Step 5: Report Writing (one subagent — does ALL synthesis)

> Main agent does NOT write the synthesis paragraph. The report-writer subagent does. The main agent's job here is to gather inputs and dispatch.

**Inputs to report-writer**:
- `research-debug/${SLUG}/L0_clarify.md`
- `research-debug/${SLUG}/L1_sketch.md`
- `research-debug/${SLUG}/L2_dryrun.md` (if Step 3 ran)
- All `research-debug/${SLUG}/light/paper_*.md` files (if Step 4 ran)
- `research-debug/${SLUG}/.l0_selection.json`, `.l2_selection.json`, `.light_status.json`
- `project-state.md`
- Original user question
- Final depth reached (`L0` / `L1` / `L2` / `handed-off`)

#### Launch report-writer

```yaml
Agent:
  description: "Research-debug report writer"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are the report writer for the research-debug skill. Assemble the final
    report by combining the L0 clarification, the L1 sketch, the L2 dry-run
    (if any), and the L2 light-read findings (if any).

    ## File handling rules
    - Do NOT call ReadMediaFile.
    - Do NOT read any paper PDF / TeX. Light-read files already exist; use them.
    - Do NOT run web searches.

    ## Inputs (read all that exist)
    - L0 clarification: research-debug/{question_slug}/L0_clarify.md
    - L1 sketch: research-debug/{question_slug}/L1_sketch.md
    - L2 dry-run: research-debug/{question_slug}/L2_dryrun.md  (may not exist)
    - Light-read directory: research-debug/{question_slug}/light/  (may be empty)
    - Status JSONs: .l0_selection.json, .l2_selection.json, .light_status.json
    - Project state: project-state.md (for cross-domain vocabulary checks)
    - Template: templates/RESEARCH_DEBUG_REPORT_TEMPLATE.md

    ## Output: research-debug/{question_slug}/report.md
    Follow the template exactly. Specifically:

    1. Reproduce L0 selections from .l0_selection.json + L0_clarify.md.
    2. Reproduce L1 sketch from L1_sketch.md, including confidence table,
       candidate terms, landmines, caveats.
    3. If L2 ran, reproduce dry-run table.
    4. If light reads ran, fill the "Light-Read Findings" section by reading
       each paper_N.md and copying its Q1/Q2/Q3 findings.
    5. SYNTHESIS — ONE paragraph (4–8 sentences) answering the user's original
       question, combining L1 sketch with L2 light findings.
       - Every factual claim that came from a light-read paper MUST cite that
         paper's light_analysis_path.
       - Every claim still grounded only in L1 sketch knowledge MUST be marked
         "[from sketch, unverified]".
       - Do NOT fabricate numbers. If a number appeared in the sketch but no
         light-read paper confirmed it, either drop it or mark it "[from
         sketch, unverified]".
    6. "Did this resolve the blocker?" — pick one of YES/PARTIAL/NO based on
       the light-read papers' `directly_addresses` field aggregate.
    7. "Suggested next action" — copy the four standard branches from the
       template and add a specific recommendation. If `directly_addresses` was
       NO across the board, recommend reformulation. If PARTIAL on a specific
       paper, recommend `/skill:research-lit "<that paper's topic>" — deep
       analyze: true, max: 1` (this is a USER command; do not invoke it).
    8. "Updates pushed back into project-state.md" — propose 0–3 small edits:
       new glossary terms detected in L0 ambiguity, observation-log entries
       suggested by the findings, open questions that can now be marked
       resolved. These are PROPOSALS — write them as a checklist for the user
       to accept manually. DO NOT edit project-state.md yourself.

    Output language: {output_language}.

    ## Forbidden
    - Do NOT invent papers, numbers, or section references.
    - Do NOT chain to another skill — the "Suggested next action" section
      contains user-facing `/skill:...` strings that the USER will type. The
      report writer must NOT attempt to invoke them.
```

#### Polling (Pattern 2)
PHASE 1: sleep 120, PHASE 2: sleep 60, PHASE 3: sleep 30.

#### Audit
```bash
test -s research-debug/${SLUG}/report.md || exit 1
grep -q '## Synthesis' research-debug/${SLUG}/report.md || exit 1
```

#### Final print to user

The main agent prints:

> ✦ **Done — research-debug report written**
>
> File: `research-debug/{question_slug}/report.md`
> Final depth reached: {L0|L1|L2|handed-off}
> Wall-clock used: {minutes} min
>
> Synthesis: {first 3 sentences of the Synthesis section}
>
> Suggested next actions are listed at the bottom of the report.
>
> Reminder: this skill is INTERACTIVE on purpose — the trial-and-error cost is
> at most one checkpoint (a few minutes of model output) before any expensive
> work runs. If a future question is more like a novelty / landscape / full
> feasibility query, run the dedicated skill instead:
>   - `/skill:idea-landscape "<topic>"` — for fuzzy direction surveys
>   - `/skill:idea-novelty "<concrete direction>"` — for novelty check
>   - `/skill:idea-feasibility "<direction>"` — for full feasibility assessment
>   - `/skill:research-lit "<topic>" — deep analyze: true` — for in-depth single-paper / multi-paper deep dive
>
> These are USER commands. This skill does NOT invoke them automatically.

---

## Key Rules Summary

1. **Interactive on purpose** — Unlike the idea-* skills, `research-debug` PAUSES between L0, L1, L2-plan stages and waits for user input. This is the whole reason the skill exists.
2. **Cheap-first** — L1 (no search) is the default and answers ~80% of in-progress questions. L2 is opt-in.
3. **Sketch-before-search** — L1 always runs before L2 so a misunderstanding is caught before any API spend on paper retrieval.
4. **Dry-run before light-read** — In L2, the search plan and candidate list are surfaced and approved BEFORE any paper is downloaded.
5. **Project-state.md is mandatory ambient context** — The skill bootstraps it if missing and exits; it does not run on a blank slate.
6. **Main agent never reads paper bodies** — Same boundary as the idea-* skills. Main agent CAN read project-state.md and idea-survey/ report headers (≤100 lines).
7. **Hard time budget** — Each subagent timeout is 1800 s (vs. 3600 s upstream). Light reads must STOP early if the answer is found early.
8. **No skill chaining** — Hand-off references like `/skill:research-lit` are USER-FACING text only. The skill never invokes another skill.
9. **No fabricated numbers** — Any number from the L1 sketch that no light-read paper confirmed must be either dropped or marked `[from sketch, unverified]` in the synthesis paragraph.
10. **Resume-friendly** — Re-running the skill with the same question slug picks up `research-debug/{slug}/` and re-uses already-generated L0/L1/L2 files unless the user explicitly asks to redo a stage.

---

## Relationship to the rest of the pipeline

| When you are… | Use this skill | Use this OTHER skill |
|---|---|---|
| At the very start, with a fuzzy idea | — | `/skill:idea-landscape` |
| About to commit to a concrete direction | — | `/skill:idea-novelty` |
| Considering whether key assumptions hold (pre-investment) | — | `/skill:idea-feasibility` |
| **Mid-project, stuck on a specific question** | **`/skill:research-debug`** | — |
| Need a single paper read deeply (overnight OK) | — | `/skill:research-lit "..." — deep analyze: true` |
| Writing the formal proposal | — | `/skill:research-proposal` |

`research-debug` is the ONLY interactive skill in this pipeline. It is also the only one whose default wall-clock target is minutes, not hours.
