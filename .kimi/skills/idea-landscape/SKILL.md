---
name: idea-landscape
description: Map a fuzzy research inspiration onto the literature landscape. Use when the user has a vague direction or intuition and wants to understand the research terrain, identify gaps, and find concrete angles to refine. This is the FIRST stage of the idea-survey pipeline.
argument-hint: [fuzzy-research-inspiration]
---

# Idea Landscape Survey

Research inspiration: $ARGUMENTS

## Constants

- **OUTPUT_DIR = `idea-survey/`** — All outputs are written here.
- **DEEP_ANALYZE_MAX = 6** — Maximum number of papers to deep-analyze per run. Override via `— deep-analyze-max: N`.
- **DEEP_ANALYZE_CONCURRENCY = 4** — Maximum concurrent `paper-analyzer` subagents. Hard cap, do not exceed.
- **SUBAGENT_TIMEOUT = 3600** — Per-subagent timeout in seconds (1 hour).
- **OUTPUT_LANGUAGE = "auto"** — Follow the shared output-language protocol.
- **RESUME_FILE = `idea-survey/landscape-report.md`** — The report file that also stores user guidance for the next run.
- **SHARED_DEEP_DIR = `idea-survey/literature-deep/`** — Shared deep-analysis directory across all idea-survey skills.
- **TWO_PHASE_BYTES_THRESHOLD = 26214400** — 25 MB. Papers with preprocessed images whose total byte size exceeds this trigger Two-Phase Analysis.
- **TWO_PHASE_IMAGE_COUNT_MIN = 4** — Minimum image count for Two-Phase. Papers with fewer images fall back to degraded text-only analysis instead.
- **TEX_SOURCE_ONLY = false** — When true, only papers with available arXiv TeX source are selected and deep-analyzed. Papers without an arXiv ID, or whose TeX source cannot be downloaded, are skipped. No PDF fallback is attempted. Override via `— tex-only: true`.
- **PDF_PARSER = "auto"** — PDF backend when a paper has no arXiv TeX source. Allowed values: `auto` (MinerU if installed, else legacy), `full` (force MinerU), `legacy` (image-only, no captions/equations/tables), `vision` (PyMuPDF page render + multimodal subagent extraction; no MinerU, no GPU). Override via `— pdf-parser: vision`. The `vision` path triggers an extra subagent step (Step 3.5) between download and deep analysis.
- **VISION_PARSE_CONCURRENCY = 4** — Maximum concurrent vision-manifest subagents in Step 3.5. Hard cap, do not exceed. Shares the same `Agent` capacity as `paper-analyzer`.
- **LOOP_ENABLED = true** — When true, run Step 4.6 (Loop Expansion) after round-1 deep analysis. The expansion uses round-1 papers as citation-graph seeds + extracts precise terms from their cards to drive a second search round, then deep-reads the most promising new candidates. Override via `— loop: false`.
- **EXPAND_BUDGET_FACTOR = 2** — Total NEW deep-analysis budget across both rounds = `DEEP_ANALYZE_MAX * EXPAND_BUDGET_FACTOR`. Round 1 may consume up to `DEEP_ANALYZE_MAX`; round 2 consumes whatever budget remains. Override via `— expand-budget-factor: N`. Setting `N == 1` is equivalent to `— loop: false`.
- **LOOP_MIN_SEEDS = 2** — Loop expansion is skipped when round 1 produced fewer than this many NEW deep analyses (citation-graph hub detection needs at least 2 seeds to do anything meaningful).
- **LOOP_REF_PER_SEED_MAX = 80** — Per-seed cap when fetching outgoing references for hub detection.
- **LOOP_CITE_PER_SEED_MAX = 80** — Per-seed cap when fetching incoming citations for recent-follower detection.
- **LOOP_MIN_OVERLAP = 2** — A candidate paper must be referenced (or cited) by at least this many round-1 seeds to qualify as a citation-graph hub.

> 💡 Overrides:
> - `/skill:idea-landscape "inspiration" — deep-analyze-max: 8` — analyze up to 8 papers in round 1 (total budget across rounds becomes 8 × 2 = 16)
> - `/skill:idea-landscape "inspiration" — deep-analyze-max: 3` — minimal run, analyze only 3 papers in round 1
> - `/skill:idea-landscape "inspiration" — language: zh` — output in Chinese
> - `/skill:idea-landscape "inspiration" — tex-only: true` — only use papers with arXiv TeX source (skip PDF-only papers)
> - `/skill:idea-landscape "inspiration" — pdf-parser: vision` — use the vision-LLM PDF path instead of MinerU (recommended for MacBook Air / CPU-only machines)
> - `/skill:idea-landscape "inspiration" — loop: false` — disable the round-2 citation-graph + term-refinement expansion (one-shot search, like the pre-loop pipeline)
> - `/skill:idea-landscape "inspiration" — expand-budget-factor: 3` — allow round 2 to grow the total budget to 3× the round-1 cap

---

## 🚧 Main Agent Boundary Protocol — ORCHESTRATE ONLY 🚧

> **This section exists because earlier runs of upstream skills exhausted the main agent's context by directly reading papers, analyzing figures, and writing synthesis prose, then required a `/compact` that broke cross-step consistency.** It is the single most important rule in this file.

### What the main agent MAY do

1. Run **shell commands** (`mkdir`, `cp`, `find`, `ls`, `wc`, `grep`, `test`).
2. Run **Python tool scripts** in `tools/` (`arxiv_fetch.py`, `paper_analyzer_orchestrator.py`, `image_preprocessor.py`, `pdf_full_parser.py`, `pdf_vision_parser.py`).
3. Launch **subagents** via the `Agent` tool.
4. Apply the **polling protocol** (Phase 1–4) and collect subagent outputs.
5. **Audit** subagent outputs at the file-system level only:
   - File exists, non-empty: `test -s path`
   - JSON parses: `python3 -m json.tool < path > /dev/null`
   - Expected files present: `ls`, `wc -l`
6. Launch **search subagents** via the `Agent` tool to gather raw paper metadata.
7. Write **small structured files** (JSON, CSV lists) to pass data between subagents.
8. Surface failures and the precise next step to the user.

### What the main agent MUST NOT do — under any circumstance

The main agent is **STRICTLY FORBIDDEN** from any of the following, no matter how "quick", "small", or "just-to-check" the temptation looks:

- ❌ **Reading** any `deep_analysis.md`, `figure_manifest.json`, or figures under `literature-deep/paper_*/`. **Exception**: `paper_card.json` files are explicit small (<10 KB) derived indexes produced by Step 4.5 and ARE readable by the main agent for counting, manifest building, or audit. The exception does NOT extend to `deep_analysis.md`.
- ❌ **Reading** the body of `landscape-report.md`, `novelty-report.md`, or `feasibility-report.md` for synthesis purposes. (Mechanical extraction of `ARIS_GUIDANCE` blocks is OK.)
- ❌ **Analyzing** paper content, figures, tables, or equations directly.
- ❌ **Writing** any synthesis prose, route descriptions, gap statements, or directional analysis — even one sentence.
- ❌ **Identifying** technical routes, gaps, or refinable directions in its own head.
- ❌ **Computing** figure relevance scores or paper selection rankings.
- ❌ **Selecting** which papers to deep-analyze. This is delegated to the synthesizer subagent.
- ❌ **Downloading** or preparing paper sources directly. Delegated to the download-preparer subagent.
- ❌ **"Falling back"** to direct work because a subagent is "slow", "timed out", or "the user is waiting". Slow is fine; wrong is not. Retry per the polling protocol.

### The "I'll just peek" rule

If the main agent finds itself thinking "I'll just open this file briefly to check X" — **STOP**. There is always a delegation alternative:

| Tempted to read | Correct action |
|---|---|
| "Let me check what routes the synthesizer identified." | Read `idea-survey/landscape-synthesis.md` — but only the `selected_papers` JSON block at the top. |
| "Let me see what this paper's figure manifest says." | Already prepared by download-preparer → the paper-analyzer subagent reads it. |
| "Let me verify this paragraph looks right." | Launch a verify subagent, or run `wc -l` / `grep` for mechanical checks. |
| "Let me just summarize this deep analysis for the next subagent." | Pass the file path; let the next subagent read it. |

**Bytes the main agent reads per run, target: < 50 KB total.** Anything above means delegation discipline broke.

### Consequence of breaking these rules

The run is compromised. The correct action is to abandon the partial output, restart the violated step with a properly-scoped subagent, and log the violation.

---

## Language Determination

Before starting, determine `output_language`:
1. Parse `$ARGUMENTS` for `— language:` override (`zh`, `en`).
2. If no override, follow the Output Language Protocol.
3. Propagate `output_language` to all subagent prompts.

---

## Resume & Guidance Detection (Step 0)

At the start of EVERY run:

1. Check if `idea-survey/landscape-report.md` exists.
2. If it exists:
   - Read the file.
   - Extract content between `ARIS_GUIDANCE_START` and `ARIS_GUIDANCE_END` → `USER_GUIDANCE`.
   - Extract the list of already-analyzed papers (from the "Deep Analysis Index" section) → `EXISTING_PAPERS`.
   - Log to user: `"Resume detected. Loaded N guidance items. M papers already deep-analyzed."`
3. If it does not exist:
   - `USER_GUIDANCE = ""`
   - `EXISTING_PAPERS = []`
   - Ensure `idea-survey/` and `idea-survey/literature-deep/` directories exist.

---

## Common Subagent Patterns

Every subagent launch in this skill follows the same three-step pattern.

### Pattern 1: Launch

```yaml
Agent:
  description: "<short task name>"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    <task-specific prompt, see each Step>
```

### Pattern 2: Polling

```
PHASE 1 — Initial wait:    sleep 300 → TaskList → collect via TaskOutput
PHASE 2 — Second wait:     sleep 180 → TaskList → collect
PHASE 3 — Tight loop:      while active: sleep 60 → TaskList → collect
PHASE 4 — Failure handling:
    IF timeout or error:
        TaskStop
        Launch ONE retry with the IDENTICAL prompt
        If retry also fails: log "FINAL_FAILED", STOP this step
        Do NOT fall back to main-agent direct work
```

Maintain active subagent count <= 4 at all times.

### Pattern 3: Audit subagent output

```bash
# Expected outputs must exist and be non-empty
for f in $EXPECTED_OUTPUTS; do
    test -s "$f" || { echo "MISSING: $f"; exit 1; }
done

# If JSON: parse must succeed
for j in $EXPECTED_JSONS; do
    python3 -m json.tool < "$j" > /dev/null || { echo "INVALID JSON: $j"; exit 1; }
done
```

If audit fails: retry the subagent ONCE with the same prompt. If retry also fails, surface to the user and STOP.

---

## Deep Analysis Protocol — ABSOLUTE RULES

The following rules are **NON-NEGOTIABLE**. Violating any of them renders the output invalid.

### RULE 1: Main Agent NEVER Analyzes Papers Directly
The main orchestrator agent is **STRICTLY FORBIDDEN** from reading, summarizing, or analyzing paper content directly. ALL paper analysis MUST be performed by dedicated `paper-analyzer` subagents launched via the `Agent` tool.

**Why**: The main agent lacks the focused context and visual inspection capability required for rigorous paper analysis. Direct analysis by the main agent produces hallucinated claims, missed details, and superficial summaries.

**Consequence**: If the main agent directly analyzes a paper, the entire skill run is compromised and MUST be restarted.

### RULE 2: No Fallback to Main Agent — EVER
Under **NO circumstances** should the main agent "fall back" to direct analysis because:
- Subagents are "taking too long"
- Subagents "timed out"
- Subagents "failed"
- "To save time"
- "As a quick summary"
- "Just this one paper"

If a subagent fails or times out, the correct action is:
1. Log the failure
2. **Retry once with the identical prompt** (most failures are transient network issues)
3. If the retry also fails, mark the paper as `"FINAL_TIMEOUT"` or `"FINAL_FAILED"` in the report
4. Continue with other papers
5. **NEVER** fill the gap with main-agent direct analysis

### RULE 3: Main Agent ONLY Orchestrates
The main agent's role is strictly limited to:
1. Deciding WHICH papers need deep analysis (based on synthesizer output)
2. Launching `paper-analyzer` subagents via the `Agent` tool
3. Waiting for subagents to complete via the polling protocol
4. Collecting subagent outputs
5. Compiling subagent outputs into the final report (by delegating to report-writer)

The main agent MUST NOT:
- Read paper PDFs, TeX sources, or figure manifests
- Interpret figures, tables, or equations
- Write analysis paragraphs based on its own reading
- Summarize paper abstracts or introductions

### RULE 4: Subagent Polling Protocol (Anti-Shortcut Enforcement)
After launching a batch of `paper-analyzer` subagents:

```
PHASE 1 — Initial wait:
    Execute: sleep 300
    Check: TaskList (active_only=true)
    Collect any completed results via TaskOutput

PHASE 2 — Second wait (if not all complete):
    Execute: sleep 180
    Check: TaskList
    Collect any completed results

PHASE 3 — Tight polling loop (until all done):
    WHILE any subagent still active:
        Execute: sleep 60
        Check: TaskList
        Collect any completed results
        IF a slot opens (completed subagent) AND queue not empty:
            Launch next subagent from queue
            Maintain active count <= DEEP_ANALYZE_CONCURRENCY

PHASE 4 — Timeout / failure handling:
    IF any subagent exceeds SUBAGENT_TIMEOUT or returns an error:
        Call TaskStop on that subagent
        Log the failure reason
        Launch a NEW subagent with the IDENTICAL prompt for the same paper
        Continue waiting for all subagents (including the retry)
```

**Rationale**: Paper analysis takes ~5 minutes. Checking too early wastes API calls. The escalating wait (5min → 3min → 1min) balances efficiency with resource usage while **ensuring the main agent never has an excuse to directly analyze**.

### RULE 5: Shared Deep Analysis Deduplication
Before launching a subagent for any paper, check `idea-survey/literature-deep/`:
- If a deep analysis already exists for this paper (match by arXiv ID, DOI, or exact title), **reuse it**
- Do NOT launch a redundant subagent
- Record the existing analysis path in the report

---

## Workflow

### Step 1: Multi-Dimensional Search (Search Subagent)

> Main agent does NOT run web searches, arXiv queries, or Semantic Scholar calls. The search-agent subagent does.

**Inputs to search-agent**: user inspiration, `TEX_SOURCE_ONLY`, `output_language`, `EXISTING_PAPERS`.
**Expected output**: `idea-survey/.search_results.json`.

#### Launch search-agent (Pattern 1)

```yaml
Agent:
  description: "Search-agent: multi-dimensional literature search"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are a research search specialist. Perform ALL search and raw data gathering for the idea-landscape skill. The main orchestrator does NOT run any searches itself.

    ## File handling rules
    - Do NOT call ReadMediaFile. No images here.
    - Do NOT run any image-conversion tools.
    - Do NOT write synthesis prose, route descriptions, or gap analysis.
    - You MAY run shell commands and Python tools in `tools/`.

    ## Inputs
    - User inspiration: "{user_inspiration}"
    - Tex-source-only mode: {TEX_SOURCE_ONLY}
    - Output language: {output_language}
    - Existing papers (already analyzed): {EXISTING_PAPERS}
    - Per-query cap: 8 results
    - Post-merge cap: 30 unique papers

    ## Search Dimensions
    Generate 4-6 search queries covering these dimensions:
    1. **Problem dimension**: How is the core problem formulated?
    2. **Method dimension**: What methods have been proposed?
    3. **Benchmark/Setting dimension**: What datasets, metrics, or experimental settings are used?
    4. **Related/Adjacent dimension**: What neighboring fields might have relevant techniques?

    ## Sources
    Execute searches using:
    1. **WebSearch** (always) — run web searches for each query
    2. **arXiv API** (always) — `python3 tools/arxiv_fetch.py search "QUERY" --max 8`
    3. **Semantic Scholar API** (if `tools/semantic_scholar_fetch.py` exists) — use it for venue-published papers

    ## Execution Rules
    - Run searches sequentially or in small batches to avoid rate limits.
    - **Per-query cap**: Retrieve at most 8 results per query.
    - Collect: title, authors, year, venue, abstract, URL, arxiv_id.
    - Merge results across queries, deduplicate by title or arXiv ID.
    - **Post-merge cap**: After deduplication, retain at most 30 unique papers. If more, prioritize by: relevance, recency, venue quality, citation count.
    - Exclude papers already in EXISTING_PAPERS.

    ## arXiv Version Lookup (CRITICAL STEP)
    For EVERY paper in your merged results that does NOT have an `arxiv_id`:
    1. Take the paper's exact title.
    2. Run: `python3 tools/arxiv_fetch.py search "EXACT_TITLE" --max 3`
    3. Compare the returned results with the paper title (case-insensitive, allowing minor punctuation/wording differences).
    4. If a match is found, ADD the `arxiv_id` to the paper's record and update the URL to `https://arxiv.org/abs/{arxiv_id}`.
    5. Log: "Found arXiv version for: TITLE → arxiv:ID"

    ## TeX-Source-Only Filter
    If TEX_SOURCE_ONLY is true:
    - After the arXiv version lookup, filter `merged_papers` to retain ONLY those with a non-empty `arxiv_id`.
    - Log: "TeX-source-only mode: retained N arXiv papers, skipped M PDF-only papers."

    ## Output
    Save the final results to: `idea-survey/.search_results.json`

    Format:
    ```json
    {
      "user_inspiration": "...",
      "queries": [
        {"dimension": "Problem", "query": "...", "results": [{"title": "...", "authors": "...", "year": ..., "venue": "...", "abstract": "...", "url": "...", "arxiv_id": "..."}]}
      ],
      "merged_papers": [
        {"title": "...", "authors": "...", "year": ..., "venue": "...", "abstract": "...", "url": "...", "arxiv_id": "...", "sources": ["query1", "query2"]}
      ],
      "arxiv_lookup_summary": {
        "total_non_arxiv": 15,
        "found_arxiv_versions": 7,
        "still_non_arxiv": 8
      },
      "total_unique": 30
    }
    ```

    ## Forbidden
    - Do NOT analyze paper content, figures, or equations.
    - Do NOT identify technical routes, gaps, or refinable directions.
    - Do NOT select which papers to deep-analyze.
    - Do NOT write the final report or synthesis.
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

Audit:
```bash
test -s idea-survey/.search_results.json || exit 1
python3 -m json.tool < idea-survey/.search_results.json > /dev/null || exit 1
grep -q '"merged_papers"' idea-survey/.search_results.json || exit 1
```

---

### Step 2: Landscape Synthesis (Subagent — ALL Intellectual Work)

> Main agent does NOT decompose concepts, generate strategies, identify routes, or select papers. The synthesizer subagent does.

**Inputs to synthesizer**: paths to `.search_results.json`, `EXISTING_PAPERS` list, `USER_GUIDANCE`, `output_language`.
**Expected output**: `idea-survey/landscape-synthesis.md`.

#### Launch synthesizer (Pattern 1)

```yaml
Agent:
  description: "Landscape synthesizer: decomposition + route selection"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are a research landscape synthesizer. Perform ALL intellectual analysis
    for the idea-landscape skill. You read search results and produce structured
    synthesis — no deep paper reading, no figure analysis.

    ## File handling rules
    - Do NOT call ReadMediaFile. No images here.
    - Do NOT run any image-conversion tools.
    - Read ONLY the search results file. Do not browse the web.

    ## Output language
    All synthesis text: {output_language}.
    JSON keys: always English.
    Paper titles, author names, venue names, arXiv IDs: English.

    ## Inputs (read these in full)
    - Search results: idea-survey/.search_results.json
    - User guidance: "{USER_GUIDANCE}" (may be empty)
    - User inspiration: "{user_inspiration}"
    - Existing papers (already analyzed): {EXISTING_PAPERS}
    - Template: templates/IDEA_LANDSCAPE_TEMPLATE.md (for field reference)

    ## Deliverable: idea-survey/landscape-synthesis.md

    Write a structured Markdown file with the following sections.
    The first section MUST be a JSON code block with machine-readable selections.

    ### Section 1: Structured Selections (JSON)

    ```json
    {
      "search_hypotheses": [
        {"id": "H1", "question": "...", "method_families": ["..."], "confidence": "High|Medium|Low"}
      ],
      "search_strategy": [
        {"hypothesis": "H1", "dimension": "Problem", "query": "...", "rationale": "..."}
      ],
      "routes": [
        {"name": "Route A", "description": "...", "core_problem": "..."}
      ],
      "selected_papers": [
        {
          "safe_id": "arxiv_2301_07041",
          "title": "...",
          "authors": "...",
          "year": 2024,
          "venue": "...",
          "arxiv_id": "2301.07041",
          "abstract": "...",
          "url": "...",
          "route": "Route A",
          "selection_rationale": "Seminal work on X; first to propose Y.",
          "already_analyzed": false,
          "analysis_path": null
        }
      ],
      "gaps": [
        {"id": "G1", "description": "...", "supporting_evidence": "[{paper}] states ...", "related_route": "Route A"}
      ],
      "refinable_directions": [
        {"title": "...", "focus": "...", "borrow_from": "...", "differentiation": "...", "supporting_literature": ["..."]}
      ],
      "position_of_inspiration": {
        "problem_space": "...",
        "method_space": "...",
        "gap_alignment": "...",
        "narrative": "2-3 paragraphs"
      }
    }
    ```

    Rules for `selected_papers`:
    - Select at most {DEEP_ANALYZE_MAX} NEW papers (not in EXISTING_PAPERS).
    - If a paper is already in EXISTING_PAPERS, set `already_analyzed: true` and `analysis_path` to the existing directory.
    - Prioritize by: relevance to user inspiration, recency, venue quality.
    - Each selected paper MUST have a clear `selection_rationale`.
    - Include 1-2 representative papers per identified route.
    - **If TEX_SOURCE_ONLY is true**: ONLY select papers that have an arXiv ID. Skip any paper without an arXiv ID. Do NOT select PDF-only papers (no matter how relevant they appear).

    ### Section 2: Human-Readable Synthesis

    After the JSON block, write the same content in human-readable Markdown:
    - System Search Hypotheses (table)
    - Search Strategy (table)
    - Landscape Map (one subsection per route)
    - Gap Map (table)
    - Position of Your Inspiration
    - Refinable Directions

    This section is for human readers; the JSON block is consumed by the main orchestrator.

    ## Forbidden
    - Do NOT write the final `landscape-report.md`. That is the report-writer's job.
    - Do NOT invent papers not present in the search results.
    - Do NOT run web searches yourself.
    - Do NOT analyze figures or read paper sources.
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

Audit:
```bash
test -s idea-survey/landscape-synthesis.md || exit 1
grep -q '"selected_papers"' idea-survey/landscape-synthesis.md || exit 1
```

---

### Step 3: Source Preparation (Download-Preparer Subagent)

> Main agent does NOT download papers, run arxiv_fetch.py, or call image_preprocessor.py. The download-preparer subagent does.

**Inputs to download-preparer**: `landscape-synthesis.md` (reads the JSON block).
**Expected output**: `idea-survey/.download_status.json`.

#### Main agent extracts the paper list (shell only)

```bash
# Extract the JSON block from the synthesis file
python3 -c "
import re, json, sys
with open('idea-survey/landscape-synthesis.md') as f:
    text = f.read()
match = re.search(r'\`\`\`json\n(.*?)\n\`\`\`', text, re.DOTALL)
if not match:
    print('No JSON block found', file=sys.stderr)
    sys.exit(1)
data = json.loads(match.group(1))
with open('idea-survey/.synthesis_selected.json', 'w') as out:
    json.dump(data.get('selected_papers', []), out)
"
```

#### Pool Resolution (shell only)

> **Why this step exists.** A paper analyzed in one project should not be re-analyzed in another project that happens to need it. The `papers_pool.py resolve` step checks every selected paper against the **shared paper pool** at `$ARIS_PAPERS_POOL` (default: `~/aris/papers-pool/`), marks each paper as either `reuse` (already in pool, will be symlinked into this project) or `analyze` (new, will be added to pool by Step 3/4). When `$ARIS_PAPERS_POOL` is unset or the directory does not exist, the step degrades to project-local mode and is functionally a no-op — every paper is marked `analyze`, no symlinks are created, no dedup happens. **This step is always run**; the conditional behavior is inside `papers_pool.py`.

```bash
# Replace <USER_INSPIRATION> below with the verbatim $ARGUMENTS string passed
# to this skill. The topic is recorded in each pool paper's analyzed_by.json
# so future projects can see what each paper has been used for.
python3 tools/papers_pool.py resolve \
    --selected-papers idea-survey/.synthesis_selected.json \
    --project-dir . \
    --topic "<USER_INSPIRATION>" \
    --output idea-survey/.synthesis_selected_resolved.json
```

The resolver writes `idea-survey/.synthesis_selected_resolved.json`, identical to the input plus a `pool_status` block on each entry:

```jsonc
{
  ...original fields (safe_id, title, arxiv_id, ...)...,
  "pool_status": {
    "paper_key": "paper_arxiv_2301_07041",
    "action": "reuse" | "analyze",
    "hit_via": "arxiv_id" | "doi" | "title_hash" | null,
    "pool_paper_dir": "/abs/path/to/.../paper_arxiv_2301_07041",
    "project_link":   "idea-survey/literature-deep/paper_arxiv_2301_07041",
    "pool_mode": true | false
  }
}
```

Audit:

```bash
test -s idea-survey/.synthesis_selected_resolved.json
python3 -m json.tool < idea-survey/.synthesis_selected_resolved.json > /dev/null
```

After this step, `idea-survey/literature-deep/` already contains the correct directories/symlinks for **every** selected paper. The download-preparer in the next subsection only needs to fetch source files for papers with `action == "analyze"`.

#### Launch download-preparer (Pattern 1)

```yaml
Agent:
  description: "Download and prepare paper sources"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are a download-preparer. For each selected paper, create a workspace,
    download the source (prefer TeX), run the unified orchestrator, and
    preprocess all images.

    ## Inputs
    - Selected papers JSON (pool-resolved): idea-survey/.synthesis_selected_resolved.json
    - Shared deep dir: idea-survey/literature-deep/
      (May contain symlinks into ~/aris/papers-pool/ when the paper pool is
      enabled. Treat symlinks as regular directories — writes through them
      transparently land in the pool.)
    - Output language: {output_language}

    ## Per-paper workflow
    For each paper in the JSON:

    - **If `pool_status.action == "reuse"`**: skip download, skip preprocessing.
      The paper is already prepared (either from a previous run of this
      project, or from a shared pool added by another project). Record
      status `"reuse"` and set `workspace` to `pool_status.project_link`.
      Proceed to the next paper.

    - **If `pool_status.action == "analyze"`**: continue with steps 1–5 below.
      Use the resolved path `pool_status.project_link` as the per-paper
      workspace — it is the canonical mount point of the paper's
      directory regardless of pool/no-pool mode. (When pool is enabled,
      it is a symlink to `pool_status.pool_paper_dir`; when pool is
      disabled, it is the real directory.) Below, `{paper_dir}` refers
      to this path.

    1. Workspace already exists (created by papers_pool.py in the previous
       Pool Resolution step). No `mkdir` needed; if you want to be defensive:
       ```bash
       mkdir -p {paper_dir}/
       ```

    2. If arXiv ID is available, prefer TeX source:
       ```bash
       python3 tools/arxiv_fetch.py download-source {arxiv_id} --dir {paper_dir}/
       ```
       Then run the unified orchestrator:
       ```bash
       python3 tools/paper_analyzer_orchestrator.py prepare \
           --arxiv-id {arxiv_id} \
           --source-dir {paper_dir}/{arxiv_id}_src/ \
           --output-dir {paper_dir}/ \
           --paper-info '{"title":"...","authors":"...","year":...,"venue":"...","abstract":"..."}' \
           --language {output_language}
       ```

    3. If TeX source is unavailable (or paper has no arXiv ID at all):
       - **If TEX_SOURCE_ONLY is true**: SKIP this paper. Record status as `"skipped"`, error as `"tex-only mode: no arXiv TeX source available"`. Do NOT attempt PDF download or PDF parsing.
       - **If TEX_SOURCE_ONLY is false** (default): Fall back to PDF. Pass `--pdf-parser {PDF_PARSER}`. The orchestrator routes to one of:
         - `pdf_full_parser.py` (MinerU) — when PDF_PARSER ∈ {"auto", "full"} and MinerU is on PATH
         - `pdf_figure_extractor.py` (legacy, image-only) — when PDF_PARSER ∈ {"auto", "legacy"} and MinerU is missing, or PDF_PARSER == "legacy"
         - `pdf_vision_parser.py render` — when PDF_PARSER == "vision".  This **does not** produce a complete `figure_manifest.json`; it writes a `vision_stub.json` and returns `mode == "pdf-vision-pending"`.  Record the paper status as `"vision_pending"` (not `"ready"`) so the main agent knows to dispatch Step 3.5.

         **Schema is identical for all paths once a manifest exists**, so the downstream `paper-analyzer` subagent does not need to know which path ran.
         ```bash
         python3 tools/arxiv_fetch.py download {arxiv_id} --dir {paper_dir}/
         python3 tools/paper_analyzer_orchestrator.py prepare \
             --pdf-path {paper_dir}/{arxiv_id}.pdf \
             --output-dir {paper_dir}/ \
             --paper-info '{"title":"...","authors":"...","year":...,"venue":"...","abstract":"..."}' \
             --language {output_language} \
             --pdf-parser {PDF_PARSER}
             # For Chinese papers (MinerU only): add --mineru-lang zh
         ```
         Capture the orchestrator's stdout — it is JSON with a `mode` field (`"tex"`, `"pdf-full"`, `"pdf-legacy"`, or `"pdf-vision-pending"`).  Copy that value into the paper's `mode` field in the deliverable below.

         If `mode == "pdf-vision-pending"`, set the paper's `status` to `"vision_pending"`.  Otherwise set it to `"ready"`.

         After the run, if `parse_log.json` exists in the paper directory, leave it untouched — it is the audit trail for figures whose captions came from heuristic attribution and equations the parser was uncertain about. Human reviewers consult it after the report is generated; it is not a gating signal for the main agent.

    4. Preprocess all images **only when status == "ready"** (i.e., a final manifest exists).  Skip this step for `vision_pending` papers — image preprocessing happens after Step 3.5 finishes.
       ```bash
       python3 tools/image_preprocessor.py {paper_dir}/ \
           --dpi 300 \
           --max-dimension 1536 \
           --max-filesize-mb 2 \
           --recursive \
           --delete-originals
       ```

    5. If any step fails, log the error and continue with the next paper.

    (Note: the "skip if already_analyzed" rule from earlier versions of this
    skill is now subsumed by `pool_status.action == "reuse"`. The
    Pool Resolution step before this subagent translates both project-local
    resume hits and cross-project pool hits into a single `reuse` action.)

    ## Deliverable: idea-survey/.download_status.json

    ```json
    {
      "papers": [
        {
          "safe_id": "...",
          "paper_key": "paper_arxiv_2301_07041",
          "status": "ready|vision_pending|reuse|failed|skipped",
          "mode": "tex|pdf-full|pdf-legacy|pdf-vision-pending|null",
          "workspace": "idea-survey/literature-deep/paper_arxiv_2301_07041",
          "error": "..."
        }
      ]
    }
    ```

    ## Forbidden
    - Do NOT analyze papers. Do NOT write deep_analysis.md.
    - Do NOT run web searches.
    - Do NOT call ReadMediaFile.
    - Do NOT attempt to finalize vision-pending manifests yourself. That is Step 3.5's job (a different subagent role with multimodal capability).
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

Audit:
```bash
test -s idea-survey/.download_status.json || exit 1
python3 -m json.tool < idea-survey/.download_status.json > /dev/null || exit 1
```

#### Main agent filters ready and vision-pending papers

```bash
python3 -c "
import json
with open('idea-survey/.download_status.json') as f:
    data = json.load(f)
ready = [p for p in data['papers'] if p['status'] == 'ready']
vision_pending = [p for p in data['papers'] if p['status'] == 'vision_pending']
with open('idea-survey/.ready_papers.json', 'w') as f:
    json.dump(ready, f)
with open('idea-survey/.vision_pending_papers.json', 'w') as f:
    json.dump(vision_pending, f)
print(f'Ready papers: {len(ready)}; Vision-pending papers: {len(vision_pending)}')
"
```

If `.vision_pending_papers.json` is empty, skip Step 3.5 and go directly to Step 4.

---

### Step 3.5: PDF Vision Manifest (paper-analyzer Subagents — Multimodal Extraction)

> **Only runs when at least one paper in `.vision_pending_papers.json` exists** (i.e., `PDF_PARSER == "vision"` and a paper had no arXiv TeX source).  This step converts a `vision_stub.json` (rendered pages + extracted embedded images, produced by Step 3) into a complete `figure_manifest.json` that is schema-identical to the MinerU and TeX paths.
>
> **Why a separate step**: the `paper-editor` subagent used by Step 3 has no vision capability. The vision-LLM extraction must be performed by a `paper-analyzer` subagent (multimodal, already used in Step 4 for figure analysis).

**Inputs**: `idea-survey/.vision_pending_papers.json`.
**Expected output (per paper)**: `idea-survey/literature-deep/paper_{safe_id}/figure_manifest.json` and `vision_extraction.json`.

#### Launch vision-extractor subagents (Pattern 1, one per paper)

**CRITICAL**: Maintain concurrency <= VISION_PARSE_CONCURRENCY. If more than 4 papers are vision-pending:
- Launch first 4 subagents
- Wait for at least 1 to complete (via polling protocol)
- Launch the next from the queue
- Never exceed 4 concurrent

Subagent prompt template (one launch per vision-pending paper):

```yaml
Agent:
  description: "PDF vision manifest: {short_title}"
  subagent_type: "paper-analyzer"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are a PDF layout extractor.  Your job is NOT to analyze the paper —
    that happens in a later step.  Your job is to identify every figure,
    table, and display equation in the PDF and emit a structured JSON file.

    ## File handling rules
    - Use `ReadMediaFile` on each page PNG in `vision_pages/`.
    - Read pages ONE AT A TIME, in order. After each page, accumulate findings
      into an in-memory list before moving to the next page.
    - Do NOT call image-conversion tools.  PyMuPDF already rendered the pages.
    - Do NOT write `deep_analysis.md`.  Do NOT write any prose synthesis.

    ## Inputs (read these in full)
    - Stub file: {workspace}/vision_stub.json
      It contains: page_count, list of page PNGs (with paths), list of
      embedded images extracted by PyMuPDF (with `embed_id`, page, path, bytes).
    - Paper metadata: title="{title}", authors="{authors}", year={year},
      venue="{venue}", arxiv_id="{arxiv_id}".
    - Output language: {output_language} (for caption text in extraction;
      do NOT translate equation LaTeX or table cells).

    ## Per-page workflow
    For each page from 1 to page_count:
      1. ReadMediaFile on the page's PNG path (relative to {workspace}).
      2. Identify all figures, tables, and display equations visible on the page.
      3. For each figure on this page:
         - Find the matching `embed_id` in vision_stub.json's `embedded_images`
           (filter by page first; if multiple, pick by reading order top-to-bottom).
           If no embedded image matches (e.g., a vector figure rendered inline),
           leave `embed_id` as `null` — the page render itself will be used.
         - Read the caption verbatim from the page.  Preserve "Figure N" / "Fig. N" / "图 N"
           numbering exactly as printed.
      4. For each table:
         - Output the table content as `table_markdown` (preferred for simple tables)
           OR `table_html` (preferred for tables with merged cells / multi-row headers).
         - Read the caption verbatim.
      5. For each display equation (numbered or unnumbered, set off from prose):
         - Output the LaTeX source as `latex`.  Use standard LaTeX math syntax.
         - If the equation has a printed number (e.g., "(3)"), set `numbered: true`.
         - Inline math inside paragraphs is NOT a display equation — skip those.

    ## Output schema — write to {workspace}/vision_extraction.json

    You MUST emit a single JSON object with exactly these top-level keys:

    ```json
    {
      "figures": [
        {
          "label": "fig1",
          "caption": "Verbatim caption text including 'Figure 1.' prefix.",
          "page": 3,
          "embed_id": "p03_001",
          "caption_provenance": "vision_llm",
          "context_paragraphs": ["Optional: 1-2 sentences from text referring to this figure."],
          "referenced_in_text": true
        }
      ],
      "tables": [
        {
          "label": "tab1",
          "caption": "Verbatim caption text.",
          "page": 5,
          "table_markdown": "| col1 | col2 |\n|---|---|\n| a | b |",
          "table_html": null,
          "caption_provenance": "vision_llm"
        }
      ],
      "equations": [
        {
          "label": "eq:loss",
          "latex": "\\mathcal{L} = -\\sum_i y_i \\log \\hat{y}_i",
          "page": 2,
          "numbered": true
        }
      ]
    }
    ```

    ### Strict rules
    - Output the JSON object AND NOTHING ELSE in `vision_extraction.json`.
      No markdown fences, no prose explanation.
    - Sequential labels: figures are `fig1, fig2, ...` in reading order; tables
      `tab1, tab2, ...`; equations `eq1, eq2, ...` unless the paper printed an
      explicit label.
    - If a caption is genuinely missing (e.g., the figure was placed without a
      caption on a poster-style page), set `caption: null` and
      `caption_provenance: "missing"`.  Do NOT invent captions.
    - If you are uncertain about an equation's LaTeX (handwritten-looking,
      heavily decorated, or unreadable), still output a best-effort `latex`
      string and add `"low_confidence": true`.  Do NOT skip it.
    - `embed_id` MUST exactly match an id in `vision_stub.json` or be `null`.

    ## Finalize step (you run this after writing vision_extraction.json)
    Run:
    ```bash
    python3 tools/pdf_vision_parser.py finalize --output-dir {workspace}
    ```
    Then preprocess images:
    ```bash
    python3 tools/image_preprocessor.py {workspace}/ \
        --dpi 300 --max-dimension 1536 --max-filesize-mb 2 --recursive --delete-originals
    ```

    ## Deliverable
    After both commands succeed, the workspace MUST contain:
      - `{workspace}/figure_manifest.json` (schema-identical to MinerU path)
      - `{workspace}/vision_extraction.json` (raw extraction, kept for audit)
      - Optionally `{workspace}/parse_log.json` (only if any caption was missing
        or any equation was empty)
      - `{workspace}/figures/` populated with the chosen embedded images.

    ## Forbidden
    - Do NOT write `deep_analysis.md`.
    - Do NOT analyze figures or compare against any external claims.
    - Do NOT invent captions, equations, tables, or numerical values.
    - Do NOT call `pdf_vision_parser.py render` (Step 3 already did that).
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

For each vision-pending paper, audit at the file-system level only:

```bash
test -s idea-survey/literature-deep/paper_{safe_id}/vision_extraction.json || exit 1
python3 -m json.tool < idea-survey/literature-deep/paper_{safe_id}/vision_extraction.json > /dev/null || exit 1
test -s idea-survey/literature-deep/paper_{safe_id}/figure_manifest.json || exit 1
python3 -m json.tool < idea-survey/literature-deep/paper_{safe_id}/figure_manifest.json > /dev/null || exit 1
```

If audit fails for a paper, retry the subagent ONCE with the same prompt. If the retry also fails, mark the paper as `"FINAL_FAILED"` in the report and exclude it from Step 4. Do NOT fall back to main-agent direct analysis.

#### After Step 3.5 completes

Update `.ready_papers.json` to include all newly-finalized vision papers:

```bash
python3 -c "
import json
with open('idea-survey/.download_status.json') as f:
    data = json.load(f)
ready = [p for p in data['papers'] if p['status'] == 'ready']
# Re-check vision_pending papers — they are now 'ready' if figure_manifest.json exists
import os
for p in data['papers']:
    if p['status'] == 'vision_pending':
        manifest = os.path.join(p['workspace'], 'figure_manifest.json')
        if os.path.exists(manifest) and os.path.getsize(manifest) > 0:
            p['status'] = 'ready'
            ready.append(p)
        else:
            p['status'] = 'failed'
            p['error'] = 'vision finalize did not produce a manifest'
with open('idea-survey/.download_status.json', 'w') as f:
    json.dump(data, f, indent=2)
with open('idea-survey/.ready_papers.json', 'w') as f:
    json.dump(ready, f)
print(f'Ready papers after vision step: {len(ready)}')
"
```

---

### Step 4: Deep Analysis (paper-analyzer Subagents)

For each paper with `status == "ready"` that needs NEW analysis:

#### 4a: Launch paper-analyzer Subagents

Launch subagents using `Agent` with `run_in_background=true`.

**CRITICAL**: Maintain concurrency <= 4. If more than 4 papers need analysis:
- Launch first 4 subagents
- Wait for at least 1 to complete (via polling protocol)
- Launch the next from the queue
- Never exceed 4 concurrent

Subagent prompt template:
```yaml
Agent:
  description: "Deep analyze: {short_title}"
  subagent_type: "paper-analyzer"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are an expert academic paper analyst. Perform a deep reading of the following paper.

    **File handling rules**:
    - Do NOT run any image conversion tools (e.g., `arxiv_eps_converter.py`, `image_preprocessor.py`, `convert`, `gs`, `pdftoppm`) inside this subagent.
    - All images have already been preprocessed into PNG format by the download-preparer before your analysis begins.
    - Use `ReadMediaFile` directly to read the provided PNG files. Do not attempt to convert, resize, or reformat them.

    ## Paper Metadata
    - Title: {title}
    - Authors: {authors}
    - Year: {year}
    - Venue: {venue}
    - arXiv/DOI: {id}
    - Abstract: {abstract}
    - Research inspiration: {user_inspiration}
    - Output language: {output_language}

    ## Extracted Figures, Tables & Equations
    Read the figure manifest: {figure_manifest_path}
    Image directory: {figures_dir}

    ### Graceful Degradation & Image Throttling

    **Throttling rule**: Read images ONE AT A TIME. After each `ReadMediaFile`, write a brief analysis note before proceeding to the next image. Do NOT queue multiple `ReadMediaFile` calls in rapid succession.

    **Degradation rule**: If you encounter an `LLM provider error` or any failure while reading an image, SKIP the remaining image analysis for this paper. Continue with the analysis of text, equations, and tables. Write the report with whatever visual analysis you have completed so far. Partial analysis is better than no analysis.

    ### Figure Analysis — VISION-FIRST MANDATE
    For **every figure** in the manifest:
    1. Use `ReadMediaFile` to view the actual image file directly.
    2. Analyze the actual visual content: axes, curves, architecture diagrams, color maps, data trends, labels, annotations.
    3. Correlate visual observations with text claims.
    4. Explain WHY it matters: Which core claim does this figure support?
    5. If quantitative, extract key numbers and interpret them.

    ### Table Analysis
    For each table: describe structure, explain which claim it supports, extract key data points.

    ### Equation Analysis
    For each important equation: explain mathematical meaning, define variables, identify assumptions.

    ## TeX Source — AUXILIARY USE ONLY
    If TeX source is available, read the main `.tex` file ONLY for narrative structure, captions, and exact equation LaTeX.
    Do NOT perform figure analysis from TeX source.

    Prioritize sections:
    - Introduction (problem motivation)
    - Method section (how the approach works)
    - Experiments section (what results show)
    - Related Work (how authors position their work)
    - Limitations / Future Work (critical for gap identification)

    ## Output
    Write a structured Markdown file to: {output_path}

    Follow the template in `templates/PAPER_DEEP_ANALYSIS_TEMPLATE.md`. Read the template first and fill in all sections.

    Rules:
    - Every figure/table/equation in the manifest MUST be analyzed
    - Use `ReadMediaFile` for each image — do not skip visual inspection
    - Connect each visual element to specific claims in the text
    - Be precise about numbers, methods, and comparisons
    - Explicitly note the paper's stated limitations and future work
    - Write output in {output_language}. Keep paper titles, author names, venue names, BibTeX, file paths, and JSON keys in English.
```

#### 4b: Polling & Collection (MANDATORY)

Execute the polling protocol from RULE 4 exactly.

For each completed subagent:
- Read the output file from `literature-deep/paper_<id>/deep_analysis.md`
- Verify the file exists and is non-empty
- Record the path in the manifest

For each failed/timed-out subagent:

1. **Classify the failure** by reading the subagent's `output` file and/or checking `wire.jsonl` for the error type:
   - `LLM provider error` → transient, worth retrying
   - `Timeout` → worth retrying once
   - `Max number of steps reached` → do NOT retry identically; reduce scope
   - `Tool execution error` (e.g., file not found) → no retry; log and skip

2. **First retry**: Launch a retry subagent with the **identical prompt**.
   - If the retry succeeds, treat as normal completion.

3. **Second retry (only for repeated `LLM provider error`)**: If the first retry also fails with `LLM provider error`, launch a **degraded subagent** with a lighter prompt that:
   - Skips all `ReadMediaFile` image analysis
   - Analyzes only text, equations, tables, and captions from the TeX source / manifest
   - Marks the output as "Partial Analysis — images skipped due to provider error"
   - If the degraded subagent succeeds, record status as `"PARTIAL"` and use the output.

4. **If all retries fail**: Check whether the paper's content volume caused the timeout.
   - Read `figure_manifest.json` and count: figures, tables, equations.
   - Read `figure_manifest.json` → `image_stats`.
   - **Trigger Two-Phase if BOTH**:
     a) `image_stats.total_bytes > TWO_PHASE_BYTES_THRESHOLD` (images are large enough to risk context overflow),
     b) `image_stats.count >= TWO_PHASE_IMAGE_COUNT_MIN` (enough images to justify parallel sharding).
   - Otherwise, record as `"FINAL_FAILED"` or `"FINAL_TIMEOUT"` and stop.

5. **Two-Phase Analysis** (only for high-volume papers that failed all retries):

   **Phase 1 — Text/Equation/Table Analysis** (strictly sequential, no images):
   - Launch a `text-analyzer` subagent with the following prompt:
     ```yaml
     Agent:
       description: "Text analysis: {short_title}"
       subagent_type: "paper-analyzer"
       run_in_background: true
       timeout: 3600
       prompt: |
         Analyze the TEXT, EQUATIONS, and TABLES of this paper only.
         Do NOT call ReadMediaFile. Skip all image analysis.

         **File handling rules**:
         - Do NOT run any image conversion tools (e.g., `arxiv_eps_converter.py`, `image_preprocessor.py`, `convert`, `gs`, `pdftoppm`) inside this subagent.
         - All images have already been preprocessed into PNG format by the download-preparer.

         Tasks:
         1. Read the TeX source (if available) or figure manifest for captions.
         2. Write a structured outline of the paper.
         3. Analyze every equation: meaning, variables, assumptions.
         4. Analyze every table: structure, key data points, what claim it supports.
         5. Catalog all figures: for each figure, record its filename, caption, and inferred importance (High/Medium/Low).
         6. Suggest how to split figures into 2-3 thematic groups for parallel image analysis.

         Output to: {phase1_output_path}
     ```
   - Wait for Phase 1 to complete using the polling protocol.
   - If Phase 1 also fails, record `"FINAL_FAILED"` and stop.

   **Phase 2 — Image Sharding** (sequential trigger, parallel execution within paper):
   - Read Phase 1 output to extract the figure catalog and suggested groups.
   - Divide figures into 2-3 groups (thematic or by quantity).
   - For each group, launch an `image-shard` subagent:
     ```yaml
     Agent:
       description: "Image shard {N}: {short_title}"
       subagent_type: "paper-analyzer"
       run_in_background: true
       timeout: 3600
       prompt: |
         Analyze ONLY the assigned subset of images for this paper.

         **File handling rules**:
         - Do NOT run any image conversion tools (e.g., `arxiv_eps_converter.py`, `image_preprocessor.py`, `convert`, `gs`, `pdftoppm`) inside this subagent.
         - All images have already been preprocessed into PNG format by the download-preparer.
         - Use `ReadMediaFile` directly to read the provided PNG files. Do not attempt to convert, resize, or reformat them.

         Assigned images: {image_file_list}
         Figure manifest: {figure_manifest_path}
         Image directory: {figures_dir}

         For each assigned figure:
         1. ReadMediaFile (one at a time)
         2. Describe visual content
         3. Correlate with the paper's text claims
         4. Extract key numbers

         Context from text analysis: {phase1_summary}

         Output a Markdown fragment to: {shard_output_path}
     ```
   - Launch all image-shard subagents in parallel (counts toward concurrency cap of 4).
   - Wait for all shards to complete using the polling protocol.
   - If any shard fails, retry it once with the identical prompt. If it still fails, record the missing images and continue.

   **Phase 3 — Assembly**:
   - Read Phase 1 output (`phase1_text_analysis.md`) and all Phase 2 shard outputs (`phase2_shard_*.md`).
   - Merge them into a single `deep_analysis.md` following `templates/PAPER_DEEP_ANALYSIS_TEMPLATE.md`.
   - Record status as `"COMPLETED_2PHASE"`.

6. **Log the paper title, failure type, retry history, and any two-phase steps taken**.

7. **Do NOT attempt to analyze it yourself**.

---

### Step 4.5: Paper Card Distillation (Subagent — ALL Distillation)

> **Why this step exists.** The report-writer in Step 5 used to read every `deep_analysis.md` directly. With 6+ papers, that exceeded the subagent's context window and forced compaction, which broke cross-paper consistency in the final report. This step compresses each `deep_analysis.md` (50–150 KB) into a small structured `paper_card.json` (3–10 KB) that the report-writer reads instead. Full schema in [templates/PAPER_CARD_SCHEMA.md](../../templates/PAPER_CARD_SCHEMA.md).
>
> **Scope: every paper in `idea-survey/literature-deep/`**, not just papers selected for this run's synthesis. Cards are a project-wide derived artifact; downstream skills (`idea-novelty`, `idea-feasibility`, future runs) reuse them.

#### 4.5a: Enumerate all deep analyses

Main agent runs shell:

```bash
mkdir -p idea-survey/.tmp
find idea-survey/literature-deep -mindepth 2 -maxdepth 2 -name deep_analysis.md -type f -size +0 \
  | sort \
  > idea-survey/.tmp/all_deep_analyses.txt
echo "Discovered $(wc -l < idea-survey/.tmp/all_deep_analyses.txt) deep_analysis files."
```

Each line is the absolute or repo-relative path to a paper's `deep_analysis.md`. The paper directory is its parent.

#### 4.5b: Identify stale cards (need re-distillation)

A `paper_card.json` is **stale** if any of:
1. It does not exist.
2. It exists but does not JSON-parse.
3. `provenance.card_schema_version` ≠ `"1.1"`.
4. `provenance.deep_analysis_mtime_utc` ≠ current mtime of `deep_analysis.md` (the card is out of date).

Compute the stale list:

```bash
python3 - <<'PY'
import json, pathlib, datetime
SCHEMA_VERSION = "1.1"
paths = [l.strip() for l in pathlib.Path("idea-survey/.tmp/all_deep_analyses.txt").read_text().splitlines() if l.strip()]
stale = []
for da_path in paths:
    da = pathlib.Path(da_path)
    paper_dir = da.parent
    card = paper_dir / "paper_card.json"
    da_mtime = datetime.datetime.fromtimestamp(da.stat().st_mtime, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    reason = None
    if not card.exists():
        reason = "missing"
    else:
        try:
            c = json.loads(card.read_text())
        except Exception:
            reason = "unparseable"
        else:
            if c.get("provenance", {}).get("card_schema_version") != SCHEMA_VERSION:
                reason = "schema_version_mismatch"
            elif c.get("provenance", {}).get("deep_analysis_mtime_utc") != da_mtime:
                reason = "mtime_mismatch"
    if reason:
        stale.append({
            "deep_analysis_path": str(da),
            "paper_dir": str(paper_dir),
            "target_card_path": str(card),
            "deep_analysis_mtime_utc": da_mtime,
            "reason": reason,
        })
pathlib.Path("idea-survey/.tmp/stale_cards.json").write_text(json.dumps(stale, indent=2))
print(f"stale: {len(stale)} / total: {len(paths)}")
PY
```

If `stale` is empty, skip Step 4.5c entirely and proceed to Step 5.

#### 4.5c: Launch one distiller subagent per stale paper

For each entry in `idea-survey/.tmp/stale_cards.json`, launch a distiller using **Pattern 1**:

```yaml
Agent:
  description: "Distill card: {paper_dir_basename}"
  subagent_type: "paper-analyzer"
  run_in_background: true
  timeout: 1200
  prompt: |
    You are a paper-card distiller. Your job is to read ONE
    `deep_analysis.md` and produce a compact, machine-readable
    `paper_card.json` next to it.

    **Source file (read this and ONLY this for paper content)**:
    {deep_analysis_path}

    **Output file (write JSON here, overwrite if it exists)**:
    {target_card_path}

    **Schema specification (READ FIRST)**:
    templates/PAPER_CARD_SCHEMA.md
    Follow the canonical structure exactly. Every top-level field
    must be present; use `null` / `""` / `[]` for fields the paper
    does not support. Total card size target: under 10 KB.

    **Provenance you MUST emit verbatim**:
    - schema_version            = "1.1"
    - provenance.deep_analysis_path        = "{deep_analysis_path}"
    - provenance.deep_analysis_mtime_utc   = "{deep_analysis_mtime_utc}"
    - provenance.card_schema_version       = "1.1"
    - provenance.card_generated_at_utc     = current UTC time, ISO-8601 (e.g. "2026-05-23T08:15:00Z")
    - provenance.deep_analysis_status      = derive from deep_analysis.md (Completed / COMPLETED_2PHASE / PARTIAL); read the closing lines of the file if needed.

    **paper_key**:
    Derive from the paper directory basename. If the directory is
    `paper_arxiv_2301_07041`, use `paper_key = "paper_arxiv_2301_07041"`.

    **Reading discipline**:
    - Use ReadFile with `line_offset` to chunk if `deep_analysis.md`
      exceeds the 1000-line ReadFile cap. Walk the file in order;
      do not re-read pages already covered.
    - Do NOT call ReadMediaFile — figure image inspection is not
      needed for distillation. Figure captions and "Why it matters"
      sentences are extracted from the deep analysis text only.
    - Do NOT read any other paper's deep_analysis.md.
    - Do NOT read figures, manifests, TeX source, or any
      cross-paper reports.

    **Anti-fabrication rule**:
    - If a field can't be supported from the source, leave it
      empty (`null` / `""` / `[]`). Half-remembered details are
      worse than empty slots.
    - For `novelty_signals.specific_mechanism`: if the deep analysis
      itself is vague, set the string to `"underspecified in source"`
      rather than guessing.

    **Output validation (the main agent will re-check)**:
    - The file you write MUST parse with `python3 -m json.tool`.
    - It MUST contain `schema_version`, `paper_key`, `metadata`,
      `one_line_thesis`, and the full `provenance` block.

    **Output language**:
    Write all free-form text fields (`one_line_thesis`,
    `method_summary`, prose `claim` strings, etc.) in {output_language}.
    Keep `metadata.title`, `metadata.authors`, `metadata.venue`,
    `metadata.arxiv_id`, `metadata.doi`, `metadata.url`,
    `paper_key`, all `*_id` fields, all schema-defined enum values
    (`Method`, `Problem`, `Mechanism`, `Result`, `Core`, `Related`,
    `Tangential`, `low`, `medium`, `high`), and all `relative_path`
    / file-path fields in English.
```

Launch with the standard concurrency cap of 4 (see Pattern 2 polling). Subagents are independent — each one touches only its own paper directory.

#### 4.5d: Wait, then verify outputs

Apply Pattern 2 polling until every dispatched distiller finishes. Then the main agent (shell only) verifies:

```bash
python3 - <<'PY'
import json, pathlib, sys
stale = json.loads(pathlib.Path("idea-survey/.tmp/stale_cards.json").read_text())
failures = []
for entry in stale:
    card = pathlib.Path(entry["target_card_path"])
    if not card.exists():
        failures.append((str(card), "missing after distillation")); continue
    try:
        c = json.loads(card.read_text())
    except Exception as e:
        failures.append((str(card), f"unparseable: {e}")); continue
    for k in ("schema_version", "paper_key", "metadata", "one_line_thesis", "provenance"):
        if k not in c:
            failures.append((str(card), f"missing top-level field: {k}")); break
    if c.get("schema_version") != "1.1":
        failures.append((str(card), "wrong schema_version"))
print(f"distillation failures: {len(failures)}")
for f in failures:
    print("  -", f)
sys.exit(1 if failures else 0)
PY
```

For each failed card, retry that paper's distiller subagent **once** with the identical prompt (per Pattern 3 retry). If the retry also fails:
- Log the paper directory and failure reason.
- Do NOT block the run. Step 5's report-writer will gracefully handle a missing card by treating that paper as "card unavailable; full deep analysis must be consulted" — but the boundary still forbids the main agent itself from opening `deep_analysis.md`.

> The main agent **MAY** read `paper_card.json` files (small structured JSON, < 10 KB each) at any point — they are explicit derived indexes. The boundary protocol's ban on reading `deep_analysis.md` directly is unchanged.

---

### Step 4.6: Loop Expansion — Citation-Graph + Term Refinement (Subagents — ALL Intellectual Work)

> **Why this step exists.** The Step 1 search-agent fires its queries against the user's *original fuzzy inspiration* — wording that almost always lags the field's actual vocabulary and that is structurally blind to citation hubs (a seminal paper everyone in the field cites may not surface from a keyword search if its title uses an older or different term). After round-1 deep reading, however, we have a much richer signal: the round-1 paper cards expose the field's precise mechanism names, method-family labels, and (crucially) every round-1 paper's arxiv_id/DOI as citation-graph seeds.
>
> This step launches **one focused expansion subagent** to combine two signals — (1) citation-graph hub detection across the round-1 seeds, and (2) precise-term search using vocabulary mined from round-1 cards — then a synthesizer to pick which expansion candidates are worth deep-reading, then re-uses Step 3 / Step 4 / Step 4.5 to download, analyze, and distill the newcomers. **Exactly one expansion round** is performed; the pipeline does not loop again.

#### 4.6.0: Main agent computes budget and decides whether to skip (shell only)

Before launching any subagent, the main agent runs the following shell to decide whether the loop should fire at all and how much budget round 2 has:

```bash
python3 - <<'PY'
import json, pathlib, os

LOOP_ENABLED = {LOOP_ENABLED}                # injected from constants
EXPAND_BUDGET_FACTOR = {EXPAND_BUDGET_FACTOR}
DEEP_ANALYZE_MAX = {DEEP_ANALYZE_MAX}
LOOP_MIN_SEEDS = {LOOP_MIN_SEEDS}

# 1. Count round-1 NEW deep analyses produced in this run.
#    A "new" paper in the round-1 sense is one whose pool_status.action == "analyze"
#    AND which actually succeeded (status == "ready" in .download_status.json, AND
#    .ready_papers.json kept it, AND its deep_analysis.md exists).
status_path = pathlib.Path("idea-survey/.download_status.json")
ready_path = pathlib.Path("idea-survey/.ready_papers.json")
selected_resolved = pathlib.Path("idea-survey/.synthesis_selected_resolved.json")

if not (status_path.exists() and ready_path.exists() and selected_resolved.exists()):
    raise SystemExit("required round-1 state files missing — cannot compute loop budget")

resolved = json.loads(selected_resolved.read_text())
ready = json.loads(ready_path.read_text())
ready_workspaces = {p.get("workspace") for p in ready}

round1_new_seeds = []
for paper in resolved:
    ps = paper.get("pool_status") or {}
    if ps.get("action") != "analyze":
        continue
    ws = ps.get("project_link")
    if ws not in ready_workspaces:
        continue
    deep_md = pathlib.Path(ws) / "deep_analysis.md"
    if not deep_md.exists() or deep_md.stat().st_size == 0:
        continue
    round1_new_seeds.append({
        "safe_id": paper.get("safe_id"),
        "arxiv_id": paper.get("arxiv_id"),
        "doi": paper.get("doi") or paper.get("DOI"),
        "title": paper.get("title"),
        "workspace": ws,
        "paper_key": ps.get("paper_key"),
    })

K1_new = len(round1_new_seeds)
total_budget = DEEP_ANALYZE_MAX * EXPAND_BUDGET_FACTOR
K2 = max(0, total_budget - K1_new)

skip_reason = None
if not LOOP_ENABLED:
    skip_reason = "LOOP_ENABLED=false"
elif K1_new < LOOP_MIN_SEEDS:
    skip_reason = f"round-1 produced only {K1_new} new deep analyses (< LOOP_MIN_SEEDS={LOOP_MIN_SEEDS})"
elif K2 <= 0:
    skip_reason = f"round-2 budget exhausted (K1_new={K1_new}, total={total_budget})"

out = {
    "loop_enabled": LOOP_ENABLED,
    "round1_new_count": K1_new,
    "round1_new_seeds": round1_new_seeds,
    "deep_analyze_max": DEEP_ANALYZE_MAX,
    "expand_budget_factor": EXPAND_BUDGET_FACTOR,
    "total_budget": total_budget,
    "round2_budget": K2,
    "skip_reason": skip_reason,
}
pathlib.Path("idea-survey/.loop_budget.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
PY
```

**If `skip_reason` is non-null**, the main agent logs the reason, writes a sentinel `idea-survey/.loop_skipped` file containing the reason, and **jumps directly to Step 5**. All of 4.6a–4.6d are skipped. Otherwise, continue.

Substitute `{LOOP_ENABLED}`, `{EXPAND_BUDGET_FACTOR}`, `{DEEP_ANALYZE_MAX}`, `{LOOP_MIN_SEEDS}` with the constants resolved against any user override.

#### 4.6a: Launch the expansion-search subagent (Pattern 1)

> One subagent, not a fleet. It is doing data gathering — citation-graph calls and a few targeted searches — not intellectual synthesis.

```yaml
Agent:
  description: "Loop expansion: citation graph + term refinement"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are the **loop expansion search subagent** for idea-landscape.
    The user's round-1 deep analyses already exist. Your job is NOT to read
    those papers' content — that's already been distilled into paper cards.
    Your job is to use round-1 cards as a launch pad for a second round of
    literature search that surfaces (a) citation-graph hubs that any keyword
    search would miss, and (b) papers matching the field's precise vocabulary
    once it's known.

    ## File handling rules
    - Do NOT call ReadMediaFile. No images here.
    - Do NOT run image-conversion tools.
    - Do NOT write synthesis prose, route descriptions, or paper assessments.
    - Read ONLY: paper_card.json files for the round-1 seeds (small JSONs,
      <10 KB each) and the search-results JSON you produce yourself.
    - You MAY run shell commands and Python tools in `tools/`.

    ## Inputs
    - User inspiration: "{user_inspiration}"
    - Output language: {output_language}
    - Round-1 seed list: idea-survey/.loop_budget.json → field `round1_new_seeds`
      Each seed has: safe_id, arxiv_id (may be null), doi (may be null),
      title, workspace (the literature-deep/paper_*/ directory containing
      paper_card.json), paper_key.
    - Round-2 budget K2: idea-survey/.loop_budget.json → field `round2_budget`
      (informational — you do NOT need to enforce it; the synthesizer in 4.6b will).
    - All paper cards already in literature-deep/ (used as a "known set" for
      deduplication):
      ```bash
      ls idea-survey/literature-deep/paper_*/paper_card.json
      ```
    - Tex-source-only mode: {TEX_SOURCE_ONLY}
    - Per-seed reference cap: {LOOP_REF_PER_SEED_MAX}
    - Per-seed citation cap: {LOOP_CITE_PER_SEED_MAX}
    - Cross-citation minimum overlap K: {LOOP_MIN_OVERLAP}

    ## Phase A — Mine round-1 cards for seeds & precise terms

    For each seed in `round1_new_seeds`:
      1. Read `{workspace}/paper_card.json` (skip if missing — it's fine,
         the card distiller may have failed for this paper).
      2. Build a citation-graph "seed_id" for the Semantic Scholar API:
         - Prefer `ARXIV:{arxiv_id}` when arxiv_id is non-null.
         - Else use the DOI verbatim.
         - Else use the title (less reliable; record but flag).
      3. Extract precise-term signal:
         - `technical_route.method_family` (e.g. "mixture-of-experts attention")
         - `technical_route.route_label`
         - `novelty_signals.specific_mechanism` (the "what they actually do" sentence)
         - `experimental_setting.task` (e.g. "long-document language modeling")
         - `experimental_setting.datasets` (named datasets)
         - Any verbatim named-method strings inside `core_claims[*].claim`
           that look like "Method X", "Algorithm Y", etc. (heuristic — match
           Title-cased multi-word noun phrases.)

    Write the mined intermediate to: `idea-survey/.loop_mined.json`

    ```json
    {
      "seeds_with_ids": [
        {"safe_id": "...", "seed_id": "ARXIV:2301.07041", "paper_key": "...",
         "title": "...", "arxiv_id": "2301.07041", "doi": null}
      ],
      "seeds_without_ids": [
        {"safe_id": "...", "title": "...",
         "reason": "no arxiv_id, no doi — citation graph unavailable"}
      ],
      "precise_terms": {
        "method_families": ["...", "..."],
        "route_labels": ["...", "..."],
        "specific_mechanisms": ["...", "..."],
        "named_methods": ["...", "..."],
        "tasks": ["...", "..."],
        "datasets": ["...", "..."]
      }
    }
    ```

    If `seeds_with_ids` is empty (e.g. all round-1 papers had no arxiv_id / doi),
    skip Phase B and go directly to Phase C — the loop is purely term-refinement
    in that degenerate case.

    ## Phase B — Citation-graph expansion

    B1. **Hub detection (references = predecessors).** Run:
        ```bash
        python3 tools/semantic_scholar_fetch.py cross-cited \
            "{comma_joined_seed_ids}" \
            --direction references \
            --per-seed-max {LOOP_REF_PER_SEED_MAX} \
            --min-overlap {LOOP_MIN_OVERLAP} \
            --top 60 \
            > idea-survey/.loop_hubs_refs.json
        ```
        This finds papers cited by ≥ K of the round-1 seeds — i.e. the
        seminal predecessors and shared methodological roots that any one
        keyword search would have missed.

    B2. **Follower detection (citations = recent papers building on the seeds).**
        Run:
        ```bash
        python3 tools/semantic_scholar_fetch.py cross-cited \
            "{comma_joined_seed_ids}" \
            --direction citations \
            --per-seed-max {LOOP_CITE_PER_SEED_MAX} \
            --min-overlap {LOOP_MIN_OVERLAP} \
            --top 40 \
            --min-year {min_follower_year} \
            > idea-survey/.loop_hubs_cites.json
        ```
        where `{min_follower_year}` = max(year over all round-1 seeds) - 1.
        This finds recent papers that build on multiple of your round-1 seeds
        — the freshest competitive landscape.

    B3. **Fallback when cross-citation returns 0 candidates** (small fields, sparse
        graph): re-run cross-cited with `--min-overlap 1` and `--top 30` for the
        references direction only. This degrades from "hub" to "any cited paper",
        but is still better than nothing. Save to `.loop_hubs_refs_fallback.json`.

    For each command, capture stderr / non-zero exits and record the seed IDs
    that failed (e.g. S2 didn't resolve the DOI). Do not abort — continue with
    whatever cross-citation results came back.

    ## Phase C — Precise-term search

    Generate 3–5 search queries from the mined precise terms. Strategy:
      - Take 2 distinct `method_families` or `route_labels` and combine each
        with the user's task domain (extracted from `tasks`).
      - Take 1 query from `specific_mechanisms` verbatim if it contains a
        named operation (e.g. "Gumbel-softmax routing for attention selection").
      - Take 1 query targeting a dataset + competing method-family pair
        (e.g. "PG-19 long-context Transformer attention pattern").
      - Avoid re-running queries that are obviously identical to round-1's
        original search (they would just re-find round-1 papers).

    For each query, run BOTH WebSearch (in your search tool, if available) AND
    arXiv API:
    ```bash
    python3 tools/arxiv_fetch.py search "QUERY" --max 6
    ```
    Cap each query at 6 results; merge and deduplicate by title + arxiv_id.

    If TEX_SOURCE_ONLY is true, drop any non-arXiv results.

    Run the same arXiv-version-lookup as Step 1 for any non-arxiv result:
    `python3 tools/arxiv_fetch.py search "EXACT_TITLE" --max 3`.

    Save to: `idea-survey/.loop_term_search.json`.

    ## Phase D — Merge + dedup against known set

    Build the "known set" (papers we already know about, must be excluded):
    ```bash
    # All papers already in literature-deep/ (round-1 + any historic runs +
    # pool-shared papers from other projects).
    ls -d idea-survey/literature-deep/paper_*/ 2>/dev/null \
      | sed 's|.*/paper_|paper_|' | sed 's|/$||' > idea-survey/.tmp/known_paper_keys.txt
    ```

    Merge the three candidate sources into a single list:
      - `.loop_hubs_refs.json` (or `.loop_hubs_refs_fallback.json` if used)
      - `.loop_hubs_cites.json`
      - `.loop_term_search.json`

    For each candidate, derive its paper_key (`paper_arxiv_{normalized_arxiv_id}`
    if arxiv_id present, else `paper_doi_{normalized_doi}`, else `paper_title_{slug}`)
    and drop any candidate whose paper_key matches `.tmp/known_paper_keys.txt`.

    Also drop any candidate whose title is a Levenshtein-near-duplicate of an
    existing known title (cheap check: exact-match on lowercase + alphanumeric
    only is enough).

    ## Deliverable: idea-survey/.expansion_candidates.json

    ```json
    {
      "round2_budget": <K2 from .loop_budget.json>,
      "phases_run": ["A", "B", "C"],
      "phase_notes": {
        "seeds_with_ids_count": ...,
        "seeds_without_ids_count": ...,
        "hub_refs_count": ...,
        "hub_cites_count": ...,
        "term_search_count": ...,
        "fallback_used": false,
        "known_set_size": ...,
        "deduplicated_to": ...
      },
      "candidates": [
        {
          "title": "...",
          "authors": "...",
          "year": 2024,
          "venue": "...",
          "abstract": "...",
          "url": "...",
          "arxiv_id": "2301.07041",
          "doi": null,
          "paper_key_proposal": "paper_arxiv_2301_07041",
          "source": "hub_refs|hub_cites|term_search",
          "signal_strength": {
            "hub_overlap_count": 3,
            "hub_influential_overlap_count": 2,
            "is_recent_follower": true,
            "term_match_query": "Gumbel-softmax routing attention"
          },
          "citation_count": 487,
          "overlapping_seeds": ["safe_id1", "safe_id2", ...]
        }
      ]
    }
    ```

    Cap `candidates` at 60 entries (the synthesizer will pick at most K2 of these).
    Rank candidates by: (overlap_count desc, influential_overlap_count desc,
    is_recent_follower desc, citation_count desc).

    ## Forbidden
    - Do NOT deep-read any paper. You are doing metadata aggregation only.
    - Do NOT decide which candidates to deep-analyze. That's the synthesizer's
      job in 4.6b.
    - Do NOT write the final report or any prose.
```

Apply Pattern 2 polling and Pattern 3 audit:

```bash
test -s idea-survey/.expansion_candidates.json
python3 -m json.tool < idea-survey/.expansion_candidates.json > /dev/null
grep -q '"candidates"' idea-survey/.expansion_candidates.json
```

If the candidates list ends up empty (`.candidates == []`), log the reason, write a sentinel `idea-survey/.loop_skipped` with reason `"no_expansion_candidates"`, and **skip 4.6b–4.6d, jumping to Step 5.**

#### 4.6b: Launch the expansion synthesizer (Pattern 1)

```yaml
Agent:
  description: "Loop expansion synthesizer: select round-2 papers"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are the loop expansion synthesizer. Pick which of the expansion
    candidates are worth deep-reading in round 2, respecting the budget.

    ## File handling rules
    - Do NOT call ReadMediaFile.
    - Read only the small JSONs listed below. No web search, no paper reading.

    ## Inputs
    - Candidates: idea-survey/.expansion_candidates.json
    - Budget: idea-survey/.loop_budget.json → field `round2_budget`
    - Round-1 paper cards (for context — same vocabulary, technical routes):
      ls idea-survey/literature-deep/paper_*/paper_card.json
    - Synthesis from round 1: idea-survey/landscape-synthesis.md
      (read only the JSON `routes`, `gaps`, and `search_hypotheses` blocks;
      do NOT re-read the human-readable Markdown sections)
    - User inspiration: "{user_inspiration}"
    - Output language: {output_language}
    - Tex-source-only mode: {TEX_SOURCE_ONLY}

    ## Selection rules

    Pick at most `round2_budget` candidates. Use these priorities, in order:

    1. **Hub papers with high overlap** (`source == "hub_refs"`,
       `signal_strength.hub_overlap_count >= 3`): these are the most likely
       seminal predecessors. Pick first.

    2. **Influential hubs** (`hub_influential_overlap_count >= 2`): the S2
       "isInfluential" flag is the API's own judgment that the seed paper
       genuinely depends on the cited work, not just a courtesy citation.

    3. **Recent followers** (`source == "hub_cites"`,
       `signal_strength.is_recent_follower == true`,
       `hub_overlap_count >= 2`): newer papers building on multiple seeds.

    4. **Term-refinement matches** (`source == "term_search"`) that fill an
       unaddressed `route` from round-1 synthesis (use `landscape-synthesis.md`
       to check).

    5. **High citation count** (>=100) as tiebreaker, but never as a primary
       criterion (citation count biases toward old papers).

    If TEX_SOURCE_ONLY is true: drop any candidate without an `arxiv_id`.

    Aim to keep at least 1 hub_refs paper and 1 hub_cites paper in the final
    selection when both sources have at least one passing candidate (diversity
    over pure ranking).

    ## Deliverable: idea-survey/.expansion_selected.json

    Schema matches Step 2's `selected_papers` exactly (so Step 3's
    download-preparer can consume it unchanged):

    ```json
    [
      {
        "safe_id": "arxiv_2401_99999",
        "title": "...",
        "authors": "...",
        "year": 2024,
        "venue": "...",
        "arxiv_id": "2401.99999",
        "abstract": "...",
        "url": "...",
        "route": "Route A | Route B | (expansion: hub) | (expansion: follower) | (expansion: term)",
        "selection_rationale": "Hub: referenced by 3 of 4 round-1 seeds incl. [seed1, seed2, seed3]. Likely the seminal precursor of the per-layer gating family.",
        "expansion_source": "hub_refs|hub_cites|term_search",
        "expansion_signal": {
          "hub_overlap_count": 3,
          "hub_influential_overlap_count": 2,
          "overlapping_seeds": ["safe_id1", "safe_id2", "safe_id3"]
        },
        "already_analyzed": false,
        "analysis_path": null
      }
    ]
    ```

    Notes:
    - All selected papers MUST have `already_analyzed == false`. The candidate
      list was already deduplicated against literature-deep/ in 4.6a; if you
      see a candidate that looks like a known paper, drop it rather than
      passing it through with `already_analyzed: true`.
    - `route` may be one of the existing round-1 routes (if the paper extends
      an existing route) OR a new "expansion: …" label when the paper does not
      fit any route. Do not invent new technical routes — those will be added
      to the final report by the report-writer using the deeper analysis.

    If after applying all rules zero candidates make the cut, emit `[]` and
    write a one-line explanation to `idea-survey/.expansion_selected_notes.md`.

    ## Forbidden
    - Do NOT exceed `round2_budget` selections.
    - Do NOT deep-read any paper.
    - Do NOT write the final report.
```

Audit:

```bash
test -e idea-survey/.expansion_selected.json   # may be []
python3 -m json.tool < idea-survey/.expansion_selected.json > /dev/null
SELECTED=$(python3 -c "import json; print(len(json.load(open('idea-survey/.expansion_selected.json'))))")
echo "Round-2 selected: $SELECTED papers"
```

If `SELECTED == 0`: log, write `idea-survey/.loop_skipped` with reason `"synthesizer_selected_zero"`, and jump to Step 5.

#### 4.6c: Round-2 download + deep analysis (reuses Step 3 / Step 3.5 / Step 4 prompts unchanged)

The round-2 pipeline reuses the exact same subagent prompts from Step 3 (download-preparer), Step 3.5 (vision manifest, if PDF_PARSER == "vision"), and Step 4 (paper-analyzer). The only thing that changes is the **input file** they consume.

Rotate the round-1 state files out of the way so the existing prompts find the round-2 input under their expected paths:

```bash
# Archive round-1 state. (These files are intermediate and not referenced after Step 4.5.)
for f in .synthesis_selected.json \
         .synthesis_selected_resolved.json \
         .download_status.json \
         .ready_papers.json \
         .vision_pending_papers.json ; do
  src="idea-survey/$f"
  dst="idea-survey/${f%.json}.round1.json"
  [ -f "$src" ] && mv "$src" "$dst"
done

# Promote round-2 selection into the slot the Step-3 download-preparer expects.
cp idea-survey/.expansion_selected.json idea-survey/.synthesis_selected.json
```

Now re-run, **in order, with the prompts from this same SKILL.md**:

1. **Step 3 — Pool Resolution** (shell, identical to Step 3):
   ```bash
   python3 tools/papers_pool.py resolve \
       --selected-papers idea-survey/.synthesis_selected.json \
       --project-dir . \
       --topic "<USER_INSPIRATION>" \
       --output idea-survey/.synthesis_selected_resolved.json
   ```

2. **Step 3 — Download-preparer subagent**: launch with the prompt from Step 3 unchanged. Inputs and outputs land in the same `.download_status.json` / workspace paths.

3. **Step 3.5 — Vision manifest subagents**: only if any paper came back as `vision_pending`. Same prompt and concurrency cap.

4. **Step 4 — Paper-analyzer subagents** for every ready paper, with the standard concurrency cap (4) and the full retry / Two-Phase Analysis ladder. New deep analyses land in `literature-deep/paper_*/deep_analysis.md` alongside the round-1 ones.

The round-2 deep-analysis subagents are launched with the **same** prompt as round-1 paper-analyzer (`{user_inspiration}` is still the original user inspiration — round-2 papers are analyzed against the same research goal, not against the expansion query). This keeps `relevance_at_first_analysis` consistent across rounds for the same project.

After this step:

```bash
test -s idea-survey/.download_status.json
python3 -m json.tool < idea-survey/.download_status.json > /dev/null
NEW_DEEP=$(find idea-survey/literature-deep -mindepth 2 -maxdepth 2 -name deep_analysis.md -newer idea-survey/.loop_budget.json -type f | wc -l)
echo "Round-2 new deep analyses on disk: $NEW_DEEP"
```

#### 4.6d: Round-2 paper-card distillation (re-run Step 4.5 logic)

Step 4.5's distillation step is deliberately scope-wide ("every paper in `literature-deep/`") and idempotent (cards are mtime-keyed against `deep_analysis.md`). The cleanest way to bring the round-2 papers into the card index is therefore to **re-run Step 4.5 exactly as written**:

- 4.5a — enumerate all `deep_analysis.md` files.
- 4.5b — compute stale cards (the new round-2 deep_analysis.md files have no card yet → marked stale → re-distilled; round-1 cards are mtime-equal to their source and are skipped).
- 4.5c — launch one `paper-analyzer` distiller per stale entry, concurrency cap 4.
- 4.5d — verify.

No new prompt is needed; the main agent simply re-invokes the same shell + subagent batch from Step 4.5. Round-1 cards are reused for free; only the new round-2 papers actually get distilled.

After 4.6d completes, every paper in `literature-deep/` (round-1 + round-2 + any historic) has a current `paper_card.json`, and Step 5 will see the union.

#### 4.6 audit summary

The main agent writes a small audit JSON so Step 5's report-writer can mention the loop in its run-log:

```bash
python3 - <<'PY'
import json, pathlib
audit = {
    "loop_ran": True,
    "round1_new": json.loads(pathlib.Path("idea-survey/.loop_budget.json").read_text())["round1_new_count"],
    "round2_selected": len(json.loads(pathlib.Path("idea-survey/.expansion_selected.json").read_text())),
    "round2_new_deep_analyses": int(__import__("subprocess").check_output(
        "find idea-survey/literature-deep -mindepth 2 -maxdepth 2 -name deep_analysis.md "
        "-newer idea-survey/.loop_budget.json -type f | wc -l", shell=True).strip()),
    "phases_in_expansion": json.loads(pathlib.Path("idea-survey/.expansion_candidates.json").read_text()).get("phases_run", []),
    "phase_notes": json.loads(pathlib.Path("idea-survey/.expansion_candidates.json").read_text()).get("phase_notes", {}),
}
pathlib.Path("idea-survey/.loop_audit.json").write_text(json.dumps(audit, indent=2))
print(json.dumps(audit, indent=2))
PY
```

If Step 4.6 was skipped (sentinel `.loop_skipped` present), `loop_audit.json` is not written; Step 5 detects the skip via the sentinel.

---

### Step 5: Report Writing (Subagent — ALL Synthesis)

> Main agent does NOT read deep analyses, identify gaps, or write report prose. The report-writer subagent does.

#### 5a: Prepare inputs

1. Build the paper-card index for the report-writer:
   ```bash
   ls idea-survey/literature-deep/paper_*/paper_card.json 2>/dev/null \
     | sort \
     > idea-survey/.tmp/paper_card_index.txt
   echo "Report-writer will consume $(wc -l < idea-survey/.tmp/paper_card_index.txt) paper cards."
   ```
   This is the result of Step 4.5. One small JSON per paper, ~3–10 KB each.

2. Build a fallback list of `deep_analysis.md` paths for papers whose card failed to distill in Step 4.5 (used as last-resort on-demand reads, NOT for default reading):
   ```bash
   comm -23 \
     <(sort idea-survey/.tmp/all_deep_analyses.txt) \
     <(sed 's|/paper_card.json$|/deep_analysis.md|' idea-survey/.tmp/paper_card_index.txt | sort) \
     > idea-survey/.tmp/cardless_deep_analyses.txt
   ```

3. Note existing report path for guidance preservation (if resuming): `idea-survey/landscape-report.md`

4. Prepare key metadata for the subagent prompt:
   - Original user inspiration
   - Output language
   - Synthesis file path: `idea-survey/landscape-synthesis.md`
   - `{paper_card_index}`: contents of `idea-survey/.tmp/paper_card_index.txt`
   - `{cardless_deep_analyses}`: contents of `idea-survey/.tmp/cardless_deep_analyses.txt` (usually empty)

#### 5b: Launch report-writer subagent

```yaml
Agent:
  description: "Report writer: landscape"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are a research report writer. Read the synthesis and the
    paper cards to produce the final structured landscape report.

    **Context from main orchestrator**:
    - Original inspiration: {user_inspiration}
    - Output language: {output_language}
    - Synthesis file: idea-survey/landscape-synthesis.md
    - User guidance applied: {user_guidance}
    - Loop audit: idea-survey/.loop_audit.json (present iff Step 4.6 ran);
      idea-survey/.loop_skipped (present iff Step 4.6 was skipped, with a
      `reason` field).

    **Files you MUST read (in this order)**:
    1. `templates/PAPER_CARD_SCHEMA.md` — the schema definition for the
       JSON cards listed below. Read this FIRST so you know what each
       field means and where to find what you need.
    2. `idea-survey/landscape-synthesis.md` — synthesized hypotheses,
       routes, gaps, and refinable directions.
    3. `idea-survey/.loop_audit.json` if it exists. This tells you which
       papers were added by Step 4.6 (round 2). When writing the
       Deep Analysis Index section of the report, mark round-2 entries
       with their `expansion_source` (`hub_refs` / `hub_cites` /
       `term_search`) and the seeds that triggered them. If
       `.loop_skipped` exists instead, briefly note in the Run Log
       footer that the loop was skipped and why — but do NOT treat the
       skip as a failure.
    4. Every paper card in this list (one JSON per paper, all small):
{paper_card_index}
    5. `templates/IDEA_LANDSCAPE_TEMPLATE.md` — the report structure.
    6. If resuming, `idea-survey/landscape-report.md` — read only to
       preserve the User Guidance Section at the bottom.

    **Files you MAY read on demand (NOT by default)**:
    - The following papers FAILED card distillation in Step 4.5 and
      have no `paper_card.json`. Treat their `deep_analysis.md` as a
      last-resort fallback if and only if the report cannot be
      grounded without it:
{cardless_deep_analyses}
    - Any other `deep_analysis.md` may be opened ONLY for a single
      targeted lookup (verbatim quote, missing number, equation
      LaTeX). Use `ReadFile` with a narrow `line_offset` — never read
      a full deep_analysis.md to "be safe". The consumer rules in
      `templates/PAPER_CARD_SCHEMA.md` are binding.

    **Output**: Write the complete report to `idea-survey/landscape-report.md`

    **Rules**:
    - Read every paper card in `{paper_card_index}`. Do not skip any.
    - Do NOT read `deep_analysis.md` files by default. Cards exist
      precisely to avoid that. Targeted on-demand reads are allowed
      only as defined above.
    - Do NOT call `ReadMediaFile`. No image analysis.
    - Do NOT run file conversion tools.
    - Follow the template structure exactly.
    - All claims about paper content MUST reference a specific paper
      card (the card itself links back to its `deep_analysis.md` via
      `provenance.deep_analysis_path`, which is what the report's
      "Deep Analysis" links should point to — write the link to the
      `deep_analysis.md`, not to the card).
    - Preserve the User Guidance Section at the bottom (copy
      existing guidance if resuming, else create empty).
    - Write the report in {output_language}. Keep paper titles,
      author names, venue names, BibTeX, file paths, and JSON keys
      in English.
    - The synthesis file already contains hypotheses, routes, gaps,
      and refinable directions. You MUST ground every claim in the
      paper cards. Do not copy the synthesis uncritically — verify
      and enrich it with evidence from the cards.
    - **Cross-project relevance**: some paper cards may have been
      distilled by another project that used the shared paper pool.
      Each card's `relevance_at_first_analysis` block records the
      topic, direct_relevance verdict, and reusable_elements as of
      THAT first analysis — NOT the current project's inspiration.
      Treat that block as a HINT only:
        - If `relevance_at_first_analysis.topic` is identical or near-
          identical to the current inspiration ({user_inspiration}),
          the block is a reliable starting point.
        - Otherwise, RE-EVALUATE direct relevance and reusable
          elements against the current inspiration in your own
          reasoning when writing the "Position of Your Inspiration"
          and route sections. Do not copy the cached verdict
          verbatim into the report. Paper-intrinsic fields
          (`core_claims`, `technical_route`, `gap_signals`,
          `quantitative_results`, `experimental_setting`,
          `limitations_*`) ARE project-agnostic and can be used as-is.
```

#### 5c: Verify output

- Wait for the report-writer subagent to complete using the polling protocol.
- Verify that `idea-survey/landscape-report.md` exists and is non-empty.
- If the subagent fails or produces an empty file, retry once with the identical prompt.
- If the retry also fails, log the failure and proceed. Do NOT write the report yourself in the main agent.

---

## Key Rules Summary

1. **Zero-interruption execution**: Never ask the user for confirmation mid-run. The skill runs from start to finish automatically.
2. **Main agent NEVER analyzes papers**: All analysis is delegated to `paper-analyzer` subagents.
3. **Main agent NEVER synthesizes**: All conceptual work (routes, gaps, directions) is delegated to subagents.
4. **Main agent NEVER downloads or prepares sources**: Delegated to `download-preparer` subagent.
5. **Strict polling protocol**: 5min → 3min → 1min loop. No shortcuts.
6. **Concurrency cap**: Maximum 4 concurrent subagents. Queue the rest.
7. **Deduplication**: Reuse existing deep analyses in `literature-deep/`. Do not re-analyze.
8. **Guidance-aware resume**: Automatically read user guidance from the previous report on re-run.
9. **Language propagation**: Respect `output_language` in all subagent prompts and report sections.
10. **Stateless between runs**: All state is in the report file and `literature-deep/` directory. No memory beyond files.
11. **Loop expansion is fixed at one round**: Step 4.6 fires exactly once per run, gated by `LOOP_ENABLED`, `LOOP_MIN_SEEDS`, and the residual budget `DEEP_ANALYZE_MAX * EXPAND_BUDGET_FACTOR - round1_new`. There is no nested loop and no third round, by design. The audit sentinel (`.loop_audit.json` or `.loop_skipped`) records the outcome for the report-writer.
