---
name: idea-novelty
description: Deep novelty verification for a concrete research direction or method. Use AFTER idea-landscape when the user has a refined direction and wants to know if it has been done, what the closest prior work is, and what the exact delta is. Performs claim-by-claim assessment based on deep analysis of competitive papers. This is the SECOND stage of the idea-survey pipeline.
argument-hint: [concrete-research-direction-or-method]
---

# Idea Novelty Check

Research direction to verify: $ARGUMENTS

## Constants

- **OUTPUT_DIR = `idea-survey/`** — All outputs are written here.
- **DEEP_ANALYZE_MAX = 8** — Maximum number of NEW competitive papers to deep-analyze per run. Override via `— deep-analyze-max: N`.
- **DEEP_ANALYZE_CONCURRENCY = 4** — Maximum concurrent `paper-analyzer` subagents. Hard cap.
- **SUBAGENT_TIMEOUT = 3600** — Per-subagent timeout in seconds (1 hour).
- **OUTPUT_LANGUAGE = "auto"** — Follow the shared output-language protocol.
- **RESUME_FILE = `idea-survey/novelty-report.md`** — The report file that also stores user guidance.
- **UPSTREAM_CONTEXT = `idea-survey/landscape-report.md`** — Loaded by subagents for domain context and deduplication.
- **SHARED_DEEP_DIR = `idea-survey/literature-deep/`** — Shared deep-analysis directory.
- **TWO_PHASE_BYTES_THRESHOLD = 26214400** — 25 MB. Papers with preprocessed images whose total byte size exceeds this trigger Two-Phase Analysis.
- **TWO_PHASE_IMAGE_COUNT_MIN = 4** — Minimum image count for Two-Phase. Papers with fewer images fall back to degraded text-only analysis instead.
- **TEX_SOURCE_ONLY = false** — When true, only papers with available arXiv TeX source are selected and deep-analyzed. Papers without an arXiv ID, or whose TeX source cannot be downloaded, are skipped. No PDF fallback is attempted. Override via `— tex-only: true`.
- **PDF_PARSER = "auto"** — PDF backend when a paper has no arXiv TeX source. Allowed values: `auto` (MinerU if installed, else legacy), `full` (force MinerU), `legacy` (image-only, no captions/equations/tables), `vision` (PyMuPDF page render + multimodal subagent extraction; no MinerU, no GPU). Override via `— pdf-parser: vision`. The `vision` path triggers an extra subagent step (Step 3.5) between download and deep analysis.
- **VISION_PARSE_CONCURRENCY = 4** — Maximum concurrent vision-manifest subagents in Step 3.5. Hard cap.
- **LOOP_ENABLED = true** — When true, run Step 4.6 (Loop Expansion) after round-1 deep analysis. Round-2 search uses round-1 competitive papers as citation-graph seeds and mines their cards for named baselines and precise mechanism strings, biased toward **competitor discovery** rather than landscape breadth. Override via `— loop: false`.
- **EXPAND_BUDGET_FACTOR = 2** — Total NEW deep-analysis budget across both rounds = `DEEP_ANALYZE_MAX * EXPAND_BUDGET_FACTOR`. Round 1 may consume up to `DEEP_ANALYZE_MAX`; round 2 consumes the remaining budget. Override via `— expand-budget-factor: N`.
- **LOOP_MIN_SEEDS = 2** — Skip Step 4.6 when round 1 produced fewer than this many NEW deep analyses.
- **LOOP_REF_PER_SEED_MAX = 80** — Per-seed cap when fetching outgoing references for hub detection.
- **LOOP_CITE_PER_SEED_MAX = 80** — Per-seed cap when fetching incoming citations for recent-follower detection.
- **LOOP_MIN_OVERLAP = 2** — Cross-citation minimum-overlap K for citation-graph hub detection.

> 💡 Overrides:
> - `/skill:idea-novelty "direction" — deep-analyze-max: 10` — round 1 up to 10 competitive papers (total budget across rounds: 20)
> - `/skill:idea-novelty "direction" — deep-analyze-max: 4` — minimal run
> - `/skill:idea-novelty "direction" — language: zh` — output in Chinese
> - `/skill:idea-novelty "direction" — tex-only: true` — only use papers with arXiv TeX source
> - `/skill:idea-novelty "direction" — pdf-parser: vision` — use the vision-LLM PDF path (recommended for MacBook Air / CPU-only machines)
> - `/skill:idea-novelty "direction" — loop: false` — disable the round-2 citation-graph + named-baseline expansion
> - `/skill:idea-novelty "direction" — expand-budget-factor: 3` — allow round 2 to grow the total budget to 3× round-1

---

## 🚧 Main Agent Boundary Protocol — ORCHESTRATE ONLY 🚧

> **This section exists because earlier runs of upstream skills exhausted the main agent's context by directly reading papers, extracting claims, and writing assessment prose, then required a `/compact` that broke cross-step consistency.** It is the single most important rule in this file.

### What the main agent MAY do

1. Run **shell commands** (`mkdir`, `cp`, `find`, `ls`, `wc`, `grep`, `test`).
2. Run **Python tool scripts** in `tools/` (`arxiv_fetch.py`, `paper_analyzer_orchestrator.py`, `image_preprocessor.py`, `pdf_full_parser.py`, `pdf_vision_parser.py`).
3. Launch **subagents** via the `Agent` tool.
4. Apply the **polling protocol** (Phase 1–4) and collect subagent outputs.
5. **Audit** subagent outputs at the file-system level only.
6. Launch **search subagents** via the `Agent` tool to gather raw paper metadata.
7. Write **small structured files** (JSON, CSV lists) to pass data between subagents.
8. Surface failures and the precise next step to the user.

### What the main agent MUST NOT do — under any circumstance

The main agent is **STRICTLY FORBIDDEN** from:

- ❌ **Reading** any `deep_analysis.md`, `figure_manifest.json`, or figures under `literature-deep/paper_*/`. **Exception**: `paper_card.json` files are explicit small (<10 KB) derived indexes produced by Step 4.5 and ARE readable by the main agent for counting, manifest building, or audit. The exception does NOT extend to `deep_analysis.md`.
- ❌ **Reading** the body of `landscape-report.md` or `novelty-report.md` for synthesis purposes. (Mechanical extraction of `ARIS_GUIDANCE` blocks is OK.)
- ❌ **Analyzing** paper content, figures, tables, or equations directly.
- ❌ **Writing** any synthesis prose, claim statements, novelty assessments, or delta analysis — even one sentence.
- ❌ **Extracting** claims from the user input or upstream reports.
- ❌ **Selecting** competitive papers to analyze.
- ❌ **Downloading** or preparing paper sources directly.
- ❌ **"Falling back"** to direct work because a subagent is slow, timed out, or failed.

### The "I'll just peek" rule

| Tempted to read | Correct action |
|---|---|
| "Let me check what claims the synthesizer extracted." | Read `idea-survey/novelty-synthesis.md` — only the `selected_papers` JSON block. |
| "Let me see what this paper's figure manifest says." | Already prepared by download-preparer → the paper-analyzer subagent reads it. |
| "Let me verify this paragraph looks right." | Run `wc -l` / `grep` for mechanical checks. |
| "Let me just summarize this deep analysis for the next subagent." | Pass the file path; let the next subagent read it. |

**Bytes the main agent reads per run, target: < 50 KB total.**

### Consequence of breaking these rules

The run is compromised. Restart the violated step with a properly-scoped subagent.

---

## Language Determination

1. Parse `$ARGUMENTS` for `— language:` override (`zh`, `en`).
2. If no override, follow the Output Language Protocol.
3. Propagate `output_language` to all subagent prompts.

---

## Context Loading Protocol (Step 0)

At the start of EVERY run:

1. **Load resume & guidance** from `idea-survey/novelty-report.md`:
   - If it exists: extract `ARIS_GUIDANCE_START...END` → `USER_GUIDANCE`.
   - Extract already-assessed claims and competitive papers → `EXISTING_CONTEXT`.
   - Log: `"Resume detected. Loaded N guidance items."`
   - If it does not exist: `USER_GUIDANCE = ""`.

2. **Note upstream landscape path**: `idea-survey/landscape-report.md` exists for subagents to read.
   - Main agent does NOT read the landscape report.
   - Main agent MAY do a mechanical check: `test -s idea-survey/landscape-report.md`.

3. Ensure `idea-survey/` and `idea-survey/literature-deep/` exist.

---

## Common Subagent Patterns

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
for f in $EXPECTED_OUTPUTS; do test -s "$f" || exit 1; done
for j in $EXPECTED_JSONS; do python3 -m json.tool < "$j" > /dev/null || exit 1; done
```

If audit fails: retry ONCE. If retry also fails, surface to user and STOP.

---

## Deep Analysis Protocol — ABSOLUTE RULES

Identical to `idea-landscape`. These rules are **NON-NEGOTIABLE** across all idea-survey skills.

### RULE 1: Main Agent NEVER Analyzes Papers Directly
The main orchestrator agent is **STRICTLY FORBIDDEN** from reading, summarizing, or analyzing paper content directly. ALL paper analysis MUST be performed by dedicated `paper-analyzer` subagents launched via the `Agent` tool.

### RULE 2: No Fallback to Main Agent — EVER
Under **NO circumstances** should the main agent "fall back" to direct analysis because subagents are slow, timed out, failed, or for any other reason. If a subagent fails, log it as `"FAILED"` or `"TIMEOUT"` and continue. **NEVER** fill the gap with main-agent direct analysis.

### RULE 3: Main Agent ONLY Orchestrates
The main agent decides which papers to analyze (based on synthesizer output), launches subagents, waits via the polling protocol, collects outputs, and delegates report compilation. The main agent MUST NOT read papers, interpret figures, or write analysis.

### RULE 4: Subagent Polling Protocol
After launching subagents:

```
PHASE 1: Sleep 300s → Check TaskList → Collect completed
PHASE 2: Sleep 180s → Check TaskList → Collect completed
PHASE 3: Loop (sleep 60s → Check TaskList → Collect → launch from queue if slot opens) until all done
PHASE 4: Timeout > 3600s or error → TaskStop → Launch retry with identical prompt → Continue waiting for all subagents (including retry)
```

Maintain active subagent count <= 4 at all times.

### RULE 5: Shared Deep Analysis Deduplication
Before analyzing any paper, check `idea-survey/literature-deep/`:
- If deep analysis already exists, **reuse it**
- Do NOT launch a redundant subagent
- Record the existing analysis path

---

## Workflow

### Step 1: Per-Claim Competitive Search (Search Subagent)

> Main agent does NOT run web searches, arXiv queries, or Semantic Scholar calls. The search-agent subagent does.

**Inputs to search-agent**: user direction, `TEX_SOURCE_ONLY`, `output_language`, `EXISTING_CONTEXT`.
**Expected output**: `idea-survey/.novelty_search_results.json`.

#### Launch search-agent (Pattern 1)

```yaml
Agent:
  description: "Search-agent: competitive literature search"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are a research search specialist. Perform ALL search and raw data gathering for the idea-novelty skill. The main orchestrator does NOT run any searches itself.

    ## File handling rules
    - Do NOT call ReadMediaFile. No images here.
    - Do NOT run any image-conversion tools.
    - Do NOT extract claims, assess novelty, or write assessment prose.
    - You MAY run shell commands and Python tools in `tools/`.

    ## Inputs
    - User direction: "{user_direction}"
    - Tex-source-only mode: {TEX_SOURCE_ONLY}
    - Output language: {output_language}
    - Existing context (already assessed): {EXISTING_CONTEXT}
    - Per-query cap: 8 results
    - Post-merge cap: 25 unique competitive papers

    ## Search Dimensions
    Generate 6-9 competitive search queries covering:
    1. **Direct competition**: exact technical terms from the direction.
    2. **Implicit competition**: similar effect through different means.
    3. **Component competition**: each key technical component in isolation.
    Run at least 3 queries per direction aspect.

    ## Sources
    Execute searches using:
    1. **WebSearch** (always) — run web searches for each query
    2. **arXiv API** (always) — `python3 tools/arxiv_fetch.py search "QUERY" --max 8`
    3. **Semantic Scholar API** (if `tools/semantic_scholar_fetch.py` exists) — use it for venue-published papers

    ## Execution Rules
    - Run searches sequentially or in small batches to avoid rate limits.
    - **Per-query cap**: Retrieve at most 8 results per query.
    - Collect: title, authors, year, venue, abstract, URL, arxiv_id.
    - Merge results, deduplicate by title or arXiv ID.
    - **Post-merge cap**: After deduplication, retain at most 25 unique competitive papers. If more, prioritize by: directness of competition, recency, venue quality.

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
    Save the final results to: `idea-survey/.novelty_search_results.json`

    Format:
    ```json
    {
      "user_direction": "...",
      "queries": [
        {"type": "Direct", "query": "...", "results": [{"title": "...", "authors": "...", "year": ..., "venue": "...", "abstract": "...", "url": "...", "arxiv_id": "..."}]}
      ],
      "merged_papers": [
        {"title": "...", "authors": "...", "year": ..., "venue": "...", "abstract": "...", "url": "...", "arxiv_id": "...", "sources": ["query1"]}
      ],
      "arxiv_lookup_summary": {
        "total_non_arxiv": 10,
        "found_arxiv_versions": 4,
        "still_non_arxiv": 6
      },
      "total_unique": 25
    }
    ```

    ## Forbidden
    - Do NOT analyze paper content, figures, or equations.
    - Do NOT extract claims or perform novelty assessment.
    - Do NOT select which competitive papers to deep-analyze.
    - Do NOT write the final report or synthesis.
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

Audit:
```bash
test -s idea-survey/.novelty_search_results.json || exit 1
python3 -m json.tool < idea-survey/.novelty_search_results.json > /dev/null || exit 1
grep -q '"merged_papers"' idea-survey/.novelty_search_results.json || exit 1
```

---

### Step 2: Novelty Synthesis (Subagent — ALL Intellectual Work)

> Main agent does NOT extract claims, select competitive papers, or assess novelty. The synthesizer subagent does.

**Inputs to synthesizer**: paths to `.novelty_search_results.json`, `USER_GUIDANCE`, upstream `landscape-report.md`, `EXISTING_CONTEXT`, `output_language`.
**Expected output**: `idea-survey/novelty-synthesis.md`.

#### Launch synthesizer (Pattern 1)

```yaml
Agent:
  description: "Novelty synthesizer: claim extraction + competitive selection"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are a novelty synthesizer. Perform ALL intellectual analysis for the
    idea-novelty skill. You read search results and upstream landscape context
    to produce structured synthesis.

    ## File handling rules
    - Do NOT call ReadMediaFile. No images here.
    - Do NOT run any image-conversion tools.
    - Do NOT run web searches.

    ## Output language
    All synthesis text: {output_language}.
    JSON keys: always English.
    Paper titles, author names, venue names, arXiv IDs: English.

    ## Inputs (read these in full)
    - Search results: idea-survey/.novelty_search_results.json
    - Upstream landscape: idea-survey/landscape-report.md (for domain context and deduplication)
    - User guidance: "{USER_GUIDANCE}" (may be empty)
    - User direction: "{user_direction}"
    - Existing context (already assessed): {EXISTING_CONTEXT}
    - Template: templates/IDEA_NOVELTY_TEMPLATE.md (for field reference)

    ## Deliverable: idea-survey/novelty-synthesis.md

    Write a structured Markdown file. The first section MUST be a JSON code block
    with machine-readable selections.

    ### Section 1: Structured Selections (JSON)

    ```json
    {
      "core_claims": [
        {"id": "C1", "statement": "...", "category": "Method|Problem/Setting|Mechanism"}
      ],
      "selected_competitive_papers": [
        {
          "safe_id": "arxiv_2301_07041",
          "title": "...",
          "authors": "...",
          "year": 2024,
          "venue": "...",
          "arxiv_id": "2301.07041",
          "abstract": "...",
          "url": "...",
          "overlapping_claims": ["C1", "C3"],
          "selection_rationale": "Directly proposes gating mechanism for attention routing.",
          "already_analyzed": false,
          "analysis_path": null
        }
      ],
      "search_summary": {
        "total_queries": 9,
        "total_unique_papers": 25,
        "new_selected": 5,
        "reused_from_landscape": 2
      }
    }
    ```

    Rules for `core_claims`:
    - Generate 3-5 claims.
    - Each claim must be a specific, falsifiable technical statement.
    - If USER_GUIDANCE specifies claims, respect them.

    Rules for `selected_competitive_papers`:
    - Select at most {DEEP_ANALYZE_MAX} NEW papers.
    - Check against EXISTING_CONTEXT and upstream landscape "Deep Analysis Index".
    - If already analyzed, set `already_analyzed: true` and `analysis_path`.
    - Prioritize by: directness of competition, recency, venue quality.
    - Each selected paper MUST have a clear `selection_rationale` linking it to specific claims.
    - **If TEX_SOURCE_ONLY is true**: ONLY select papers that have an arXiv ID. Skip any paper without an arXiv ID. Do NOT select PDF-only competitive papers.

    ### Section 2: Human-Readable Synthesis

    After the JSON block, write:
    - Core Claims (table)
    - Competitive Search Summary (bullet list)
    - Closest Prior Work Summary (table, preliminary)

    ## Forbidden
    - Do NOT write the final `novelty-report.md`. That is the report-writer's job.
    - Do NOT invent papers not present in the search results.
    - Do NOT perform claim-by-claim novelty assessment. That requires deep analysis.
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

Audit:
```bash
test -s idea-survey/novelty-synthesis.md || exit 1
grep -q '"selected_competitive_papers"' idea-survey/novelty-synthesis.md || exit 1
```

---

### Step 3: Source Preparation (Download-Preparer Subagent)

> Main agent does NOT download papers or run image_preprocessor.py.

**Inputs to download-preparer**: `novelty-synthesis.md` (reads the JSON block).
**Expected output**: `idea-survey/.download_status.json`.

#### Main agent extracts the paper list (shell only)

```bash
python3 -c "
import re, json, sys
with open('idea-survey/novelty-synthesis.md') as f:
    text = f.read()
match = re.search(r'\`\`\`json\n(.*?)\n\`\`\`', text, re.DOTALL)
if not match:
    print('No JSON block found', file=sys.stderr)
    sys.exit(1)
data = json.loads(match.group(1))
with open('idea-survey/.synthesis_selected.json', 'w') as out:
    json.dump(data.get('selected_competitive_papers', []), out)
"
```

#### Pool Resolution (shell only)

> Identical purpose to `idea-landscape` Pool Resolution: dedup each selected paper against the shared paper pool at `$ARIS_PAPERS_POOL`. Reuses prior analyses cross-project; no-op fallback when the pool is not configured.

```bash
# Replace <USER_DIRECTION> below with the verbatim $ARGUMENTS string
# (the research direction under verification). Recorded in pool provenance.
python3 tools/papers_pool.py resolve \
    --selected-papers idea-survey/.synthesis_selected.json \
    --project-dir . \
    --topic "<USER_DIRECTION>" \
    --output idea-survey/.synthesis_selected_resolved.json
```

The resolved JSON has a `pool_status` block on each entry (see `idea-landscape/SKILL.md` Pool Resolution for the full schema). After this step, `idea-survey/literature-deep/` already contains correct directories/symlinks for every selected paper; the download-preparer only fetches sources for `action == "analyze"` papers.

Audit:

```bash
test -s idea-survey/.synthesis_selected_resolved.json
python3 -m json.tool < idea-survey/.synthesis_selected_resolved.json > /dev/null
```

#### Launch download-preparer (Pattern 1)

Identical to `idea-landscape` download-preparer. The subagent reads `idea-survey/.synthesis_selected_resolved.json` and prepares each paper workspace.

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
    - Shared deep dir: idea-survey/literature-deep/ (may contain symlinks into ~/aris/papers-pool/)
    - Output language: {output_language}

    ## Per-paper workflow
    For each paper in the JSON:

    - **If `pool_status.action == "reuse"`**: skip download and preprocessing
      entirely. Record `status: "reuse"`, `workspace: pool_status.project_link`.
    - **If `pool_status.action == "analyze"`**: continue with steps 1–5 below,
      using `{paper_dir} = pool_status.project_link` as the workspace path.

    1. Workspace already exists (papers_pool.py created it). If you want to
       be defensive:
       ```bash
       mkdir -p {paper_dir}/
       ```

    2. If arXiv ID is available, prefer TeX source:
       ```bash
       python3 tools/arxiv_fetch.py download-source {arxiv_id} --dir {paper_dir}/
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

         After the run, leave any generated `parse_log.json` in place — it is the audit trail (heuristic captions, low-confidence equations) for later human review; it is **not** a gating signal for the main agent.

    4. Preprocess all images **only when status == "ready"** (i.e., a final manifest exists).  Skip this step for `vision_pending` papers — image preprocessing happens after Step 3.5 finishes.
       ```bash
       python3 tools/image_preprocessor.py {paper_dir}/ \
           --dpi 300 --max-dimension 1536 --max-filesize-mb 2 --recursive --delete-originals
       ```

    5. If any step fails, log the error and continue with the next paper.

    (Note: the "skip if already_analyzed" rule is subsumed by
    `pool_status.action == "reuse"` — the Pool Resolution step translates
    both project-local resume hits and cross-project pool hits into a
    single `reuse` action.)

    ## Deliverable: idea-survey/.download_status.json
    ```json
    {"papers": [{"safe_id": "...", "paper_key": "paper_arxiv_2301_07041", "status": "ready|vision_pending|reuse|failed|skipped", "mode": "tex|pdf-full|pdf-legacy|pdf-vision-pending|null", "workspace": "idea-survey/literature-deep/paper_arxiv_2301_07041", "error": "..."}]}
    ```

    ## Forbidden
    - Do NOT analyze papers. Do NOT write deep_analysis.md.
    - Do NOT run web searches. Do NOT call ReadMediaFile.
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

> **Only runs when at least one paper in `.vision_pending_papers.json` exists** (i.e., `PDF_PARSER == "vision"` and a competitive paper had no arXiv TeX source).  This step converts a `vision_stub.json` (rendered pages + extracted embedded images, produced by Step 3) into a complete `figure_manifest.json` that is schema-identical to the MinerU and TeX paths.
>
> **Why a separate step**: the `paper-editor` subagent used by Step 3 has no vision capability. The vision-LLM extraction must be performed by a `paper-analyzer` subagent (multimodal, already used in Step 4 for figure analysis).

**Inputs**: `idea-survey/.vision_pending_papers.json`.
**Expected output (per paper)**: `idea-survey/literature-deep/paper_{safe_id}/figure_manifest.json` and `vision_extraction.json` (resolved through the symlink to the pool when pool mode is enabled).

#### Launch vision-extractor subagents (Pattern 1, one per paper)

**CRITICAL**: Maintain concurrency <= VISION_PARSE_CONCURRENCY. If more than 4 papers are vision-pending, queue and launch new ones as slots free.

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
    - Output language: {output_language} (for caption text; do NOT translate
      equation LaTeX or table cells).

    ## Per-page workflow
    For each page from 1 to page_count:
      1. ReadMediaFile on the page's PNG path (relative to {workspace}).
      2. Identify all figures, tables, and display equations visible on the page.
      3. For each figure: find the matching `embed_id` in vision_stub.json's
         `embedded_images` (filter by page; if multiple, pick by reading order
         top-to-bottom). If no embedded image matches, leave `embed_id` as null.
         Read the caption verbatim.
      4. For each table: output as `table_markdown` (simple tables) or
         `table_html` (merged cells). Read the caption verbatim.
      5. For each display equation: output LaTeX in `latex`. If printed with a
         number, set `numbered: true`. Skip inline math.

    ## Output schema — write to {workspace}/vision_extraction.json

    Emit a single JSON object with exactly these top-level keys:

    ```json
    {
      "figures": [
        {"label": "fig1", "caption": "Verbatim caption.", "page": 3,
         "embed_id": "p03_001", "caption_provenance": "vision_llm",
         "context_paragraphs": [], "referenced_in_text": true}
      ],
      "tables": [
        {"label": "tab1", "caption": "Verbatim caption.", "page": 5,
         "table_markdown": "| a | b |\n|---|---|\n| 1 | 2 |",
         "table_html": null, "caption_provenance": "vision_llm"}
      ],
      "equations": [
        {"label": "eq:loss", "latex": "L = -\\sum_i y_i \\log \\hat{y}_i",
         "page": 2, "numbered": true}
      ]
    }
    ```

    ### Strict rules
    - Output the JSON object AND NOTHING ELSE in `vision_extraction.json`.
    - Sequential labels: figures `fig1, fig2, ...`; tables `tab1, ...`;
      equations `eq1, ...` unless the paper printed an explicit label.
    - If a caption is genuinely missing, set `caption: null` and
      `caption_provenance: "missing"`. Do NOT invent captions.
    - If uncertain about an equation's LaTeX, still output best-effort and add
      `"low_confidence": true`. Do NOT skip it.
    - `embed_id` MUST exactly match an id in `vision_stub.json` or be null.

    ## Finalize step (you run this after writing vision_extraction.json)
    ```bash
    python3 tools/pdf_vision_parser.py finalize --output-dir {workspace}
    python3 tools/image_preprocessor.py {workspace}/ \
        --dpi 300 --max-dimension 1536 --max-filesize-mb 2 --recursive --delete-originals
    ```

    ## Deliverable
    After both commands succeed, the workspace MUST contain:
      - `{workspace}/figure_manifest.json` (schema-identical to MinerU path)
      - `{workspace}/vision_extraction.json` (raw extraction, kept for audit)
      - `{workspace}/figures/` populated with the chosen embedded images.

    ## Forbidden
    - Do NOT write `deep_analysis.md`.
    - Do NOT analyze figures or compare against any external claims.
    - Do NOT invent captions, equations, tables, or numerical values.
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

For each vision-pending paper, audit at the file-system level only:

```bash
test -s idea-survey/literature-deep/paper_{safe_id}/vision_extraction.json || exit 1
python3 -m json.tool < idea-survey/literature-deep/paper_{safe_id}/vision_extraction.json > /dev/null || exit 1
test -s idea-survey/literature-deep/paper_{safe_id}/figure_manifest.json || exit 1
python3 -m json.tool < idea-survey/literature-deep/paper_{safe_id}/figure_manifest.json > /dev/null || exit 1
```

If audit fails for a paper, retry the subagent ONCE with the same prompt. If the retry also fails, mark the paper as `"FINAL_FAILED"` and exclude it from Step 4. Do NOT fall back to main-agent direct analysis.

#### After Step 3.5 completes — promote vision-pending papers to ready

```bash
python3 -c "
import json, os
with open('idea-survey/.download_status.json') as f:
    data = json.load(f)
ready = [p for p in data['papers'] if p['status'] == 'ready']
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

For each paper with `status == "ready"` that needs NEW analysis, launch `paper-analyzer` subagents.

**CRITICAL**: Maintain concurrency <= 4. Use the queue protocol from RULE 4.

Subagent prompt (novelty-focused variant):
```yaml
Agent:
  description: "Novelty analysis: {short_title}"
  subagent_type: "paper-analyzer"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are an expert academic paper analyst. Perform a deep reading of the following paper with a FOCUS on novelty comparison against a proposed method.

    **File handling rules**:
    - Do NOT run any image conversion tools.
    - All images have already been preprocessed into PNG format by the download-preparer.
    - Use `ReadMediaFile` directly to read the provided PNG files.

    ## Paper Metadata
    - Title: {title}
    - Authors: {authors}
    - Year: {year}
    - Venue: {venue}
    - arXiv/DOI: {id}
    - Abstract: {abstract}
    - Output language: {output_language}

    ## Proposed Method Claims to Compare Against
    {list_of_claims}

    ## Your Task
    Read this paper deeply and produce an analysis that answers:
    1. What is the EXACT problem this paper addresses?
    2. What is the EXACT method/mechanism proposed?
    3. What are the KEY experimental results?
    4. For EACH claim above, does this paper:
       a) Directly anticipate the same claim? (If yes, how exactly?)
       b) Address a related but different claim? (What is the difference?)
       c) Use a similar mechanism in a different setting? (What setting?)
       d) Have no overlap with this claim?
    5. What does the paper explicitly state as limitations or future work?
    6. What would be the STRONGEST argument that this paper is prior art?
    7. What would be the STRONGEST counterargument that it is NOT prior art?

    ## Extracted Figures, Tables & Equations
    Read the figure manifest: {figure_manifest_path}
    Image directory: {figures_dir}

    ### Graceful Degradation & Image Throttling
    **Throttling rule**: Read images ONE AT A TIME.
    **Degradation rule**: If you encounter an `LLM provider error`, SKIP remaining image analysis. Continue with text, equations, and tables.

    ### Figure Analysis — VISION-FIRST MANDATE
    For every figure in the manifest: ReadMediaFile, analyze visual content, correlate with text claims, explain WHY it matters.

    ### Table Analysis
    For each table: describe structure, explain which claim it supports, extract key data points.

    ### Equation Analysis
    For each important equation: explain mathematical meaning, define variables, identify assumptions.

    ## TeX Source — AUXILIARY USE ONLY
    If TeX source is available, read the main `.tex` file ONLY for narrative structure, captions, and exact equation LaTeX.

    ## Output
    Write a structured Markdown file to: {output_path}
    Follow `templates/PAPER_DEEP_ANALYSIS_TEMPLATE.md`. Include a "Novelty Comparison" section addressing the 7 questions above.

    Rules:
    - Every figure/table/equation in the manifest MUST be analyzed
    - Use `ReadMediaFile` for each image
    - Be BRUTALLY honest about overlap. If the paper directly anticipates a claim, say so explicitly.
    - Cite specific sections, sentences, or numbers from the paper as evidence.
    - Do NOT soften findings to make the proposed method look more novel.
    - Write output in {output_language}. Keep paper titles, author names, venue names, BibTeX, file paths, and JSON keys in English.
```

#### Polling, retry, and Two-Phase protocol

Identical to `idea-landscape` Step 4b/4c. Execute RULE 4 polling protocol exactly.

For failed/timed-out subagents:
1. Classify failure, retry once with identical prompt.
2. Second retry (repeated `LLM provider error`): degraded subagent, skips images.
3. If all retries fail: check `figure_manifest.json` → trigger Two-Phase if thresholds met.
4. Two-Phase: text-analyzer → image shards → assembly.
5. NEVER analyze directly.

---

### Step 4.5: Paper Card Distillation (Subagent — ALL Distillation)

> **Why this step exists.** The report-writer in Step 5 used to read every `deep_analysis.md` directly. With 6+ papers, that exceeded the subagent's context window and forced compaction, which broke claim-by-claim consistency in the final report. This step compresses each `deep_analysis.md` (50–150 KB) into a small structured `paper_card.json` (3–10 KB) that the report-writer reads instead. Full schema in [templates/PAPER_CARD_SCHEMA.md](../../templates/PAPER_CARD_SCHEMA.md).
>
> **Scope: every paper in `idea-survey/literature-deep/`**, not just papers selected for this run's claim assessment. Cards are a project-wide derived artifact shared across `idea-landscape`, `idea-novelty`, and `idea-feasibility`. Cards distilled in upstream `idea-landscape` are reused here at zero cost (mtime check).

#### 4.5a: Enumerate all deep analyses

Main agent runs shell:

```bash
mkdir -p idea-survey/.tmp
find idea-survey/literature-deep -mindepth 2 -maxdepth 2 -name deep_analysis.md -type f -size +0 \
  | sort \
  > idea-survey/.tmp/all_deep_analyses.txt
echo "Discovered $(wc -l < idea-survey/.tmp/all_deep_analyses.txt) deep_analysis files."
```

#### 4.5b: Identify stale cards (need re-distillation)

A `paper_card.json` is **stale** if any of:
1. It does not exist.
2. It exists but does not JSON-parse.
3. `provenance.card_schema_version` ≠ `"1.1"`.
4. `provenance.deep_analysis_mtime_utc` ≠ current mtime of `deep_analysis.md`.

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

If `stale` is empty, skip 4.5c entirely and proceed to Step 5.

#### 4.5c: Launch one distiller subagent per stale paper

For each entry in `idea-survey/.tmp/stale_cards.json`, launch a distiller using **Pattern 1**:

```yaml
Agent:
  description: "Distill card: {paper_dir_basename}"
  subagent_type: "paper-analyzer"
  run_in_background: true
  timeout: 1200
  prompt: |
    You are a paper-card distiller. Read ONE `deep_analysis.md`
    and produce a compact, machine-readable `paper_card.json`
    next to it.

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
    - provenance.card_generated_at_utc     = current UTC time, ISO-8601
    - provenance.deep_analysis_status      = derive from deep_analysis.md (Completed / COMPLETED_2PHASE / PARTIAL).

    **paper_key**:
    Derive from the paper directory basename. If the directory is
    `paper_arxiv_2301_07041`, use `paper_key = "paper_arxiv_2301_07041"`.

    **Reading discipline**:
    - Use ReadFile with `line_offset` to chunk if `deep_analysis.md`
      exceeds the 1000-line ReadFile cap. Walk the file in order.
    - Do NOT call ReadMediaFile.
    - Do NOT read any other paper's deep_analysis.md.
    - Do NOT read figures, manifests, TeX source, or any
      cross-paper reports.

    **Anti-fabrication rule**:
    - If a field can't be supported from the source, leave it
      empty. Half-remembered details are worse than empty slots.
    - For `novelty_signals.specific_mechanism`: if the source is
      vague, write `"underspecified in source"` rather than guess.
      `idea-novelty` depends heavily on this field, so be honest
      about precision.

    **Output validation (the main agent will re-check)**:
    - The file you write MUST parse with `python3 -m json.tool`.
    - It MUST contain `schema_version`, `paper_key`, `metadata`,
      `one_line_thesis`, and the full `provenance` block.

    **Output language**:
    Write all free-form text fields in {output_language}. Keep
    `metadata.title`, `metadata.authors`, `metadata.venue`,
    `metadata.arxiv_id`, `metadata.doi`, `metadata.url`, `paper_key`,
    `*_id` fields, schema-defined enum values (`Method`, `Problem`,
    `Mechanism`, `Result`, `Core`, `Related`, `Tangential`, `low`,
    `medium`, `high`), and `relative_path` / file-path fields in English.
```

Launch under the standard concurrency cap of 4.

#### 4.5d: Wait, then verify outputs

Apply Pattern 2 polling until all dispatched distillers finish. Then verify:

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

Retry each failed card's distiller subagent once. If the second attempt also fails, log the paper directory and reason, and proceed — Step 5 will see only the cards that succeeded.

> The main agent **MAY** read `paper_card.json` files (small structured JSON, < 10 KB each) at any point. The boundary protocol's ban on reading `deep_analysis.md` directly is unchanged.

---

### Step 4.6: Loop Expansion — Citation-Graph + Named-Baseline Refinement (Subagents — ALL Intellectual Work)

> **Why this step exists.** Round-1 competitive search starts from the user's specific direction in *their phrasing*, which is often slightly off from the field's vocabulary and structurally blind to citation hubs. After round-1 deep reading we have much sharper signal: each round-1 paper card exposes (a) the paper's arxiv_id / DOI as a citation-graph seed, and (b) the named baselines / methods that paper compared against, plus the specific mechanism language the field actually uses.
>
> For **novelty verification** specifically the expansion is biased toward *competitors*: papers cited by ≥ K round-1 papers are very likely the closest prior work for the user's specific mechanism, and the named-baseline strings inside `novelty_signals.specific_mechanism` and `core_claims[*].claim` are the most precise queries possible. **Exactly one expansion round** is performed.

#### 4.6.0: Main agent computes budget and decides whether to skip (shell only)

```bash
python3 - <<'PY'
import json, pathlib

LOOP_ENABLED = {LOOP_ENABLED}                # injected from constants
EXPAND_BUDGET_FACTOR = {EXPAND_BUDGET_FACTOR}
DEEP_ANALYZE_MAX = {DEEP_ANALYZE_MAX}
LOOP_MIN_SEEDS = {LOOP_MIN_SEEDS}

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
        "overlapping_claims": paper.get("overlapping_claims") or [],
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

**If `skip_reason` is non-null**, the main agent logs the reason, writes a sentinel `idea-survey/.loop_skipped` with the reason, and **jumps directly to Step 5**. Otherwise, continue.

Substitute `{LOOP_ENABLED}`, `{EXPAND_BUDGET_FACTOR}`, `{DEEP_ANALYZE_MAX}`, `{LOOP_MIN_SEEDS}` with the constants resolved against any user override.

#### 4.6a: Launch the expansion-search subagent (Pattern 1)

```yaml
Agent:
  description: "Loop expansion: citation graph + named-baseline refinement"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are the **loop expansion search subagent** for idea-novelty. Round-1
    competitive papers are already deep-read; their cards give you (a)
    citation-graph seeds and (b) the *names* of the methods they compete
    against. Your job is to convert those into a second round of search
    candidates focused on **competitor discovery**.

    ## File handling rules
    - Do NOT call ReadMediaFile.
    - Do NOT run image-conversion tools.
    - Do NOT extract claims, write novelty assessment prose, or compute deltas.
    - Read ONLY: paper_card.json files for the round-1 seeds (small JSONs)
      and the search-results JSON you produce yourself.

    ## Inputs
    - User direction: "{user_direction}"
    - Output language: {output_language}
    - Round-1 seed list: idea-survey/.loop_budget.json → field `round1_new_seeds`
    - Round-2 budget K2: idea-survey/.loop_budget.json → field `round2_budget`
    - Round-1 core claims: from idea-survey/novelty-synthesis.md (the JSON block's
      `core_claims` field). Each round-1 seed also has `overlapping_claims`,
      indicating which claims that seed competes on.
    - Known set: all directories under idea-survey/literature-deep/paper_*/
    - Tex-source-only mode: {TEX_SOURCE_ONLY}
    - Per-seed reference cap: {LOOP_REF_PER_SEED_MAX}
    - Per-seed citation cap: {LOOP_CITE_PER_SEED_MAX}
    - Cross-citation minimum overlap K: {LOOP_MIN_OVERLAP}

    ## Phase A — Mine round-1 cards for citation-graph seeds and named baselines

    For each seed in `round1_new_seeds`:
      1. Read `{workspace}/paper_card.json` (skip silently if missing).
      2. Build a citation-graph "seed_id":
         - Prefer `ARXIV:{arxiv_id}` when present.
         - Else use the DOI verbatim.
         - Else fall back to title (less reliable; flag).
      3. Extract **named-baseline signal** (this is the novelty-specific bit):
         - From `novelty_signals.specific_mechanism`: any verbatim noun-phrase
           that looks like a method name (e.g. "Sparse Transformer",
           "Longformer", "GShard", "DeepMoE"). Heuristic: Title-cased
           multi-word phrase, possibly with a hyphen or trailing version
           number.
         - From `core_claims[*].claim`: same extraction.
         - From `key_tables[*].what_compared`: the "Method A vs Method B vs
           Ours" string usually lists every competitor by name — pull all
           non-"Ours" names.
         - From `technical_route.method_family` and `route_label`: the
           method-family vocabulary.

    Write the mined intermediate to: `idea-survey/.loop_mined.json`

    ```json
    {
      "seeds_with_ids": [
        {"safe_id": "...", "seed_id": "ARXIV:2301.07041", "paper_key": "...",
         "title": "...", "arxiv_id": "2301.07041", "doi": null,
         "overlapping_claims": ["C1", "C3"]}
      ],
      "seeds_without_ids": [...],
      "named_baselines": ["Sparse Transformer", "Longformer", "GShard", ...],
      "method_families": ["mixture-of-experts attention", ...],
      "specific_mechanisms": [
        "Gumbel-softmax gating for per-layer sparse vs full attention",
        ...
      ]
    }
    ```

    If `seeds_with_ids` is empty, skip Phase B and run Phase C only.

    ## Phase B — Citation-graph expansion (the main novelty signal)

    B1. **Hub references** — predecessors cited by ≥ K seeds:
        ```bash
        python3 tools/semantic_scholar_fetch.py cross-cited \
            "{comma_joined_seed_ids}" \
            --direction references \
            --per-seed-max {LOOP_REF_PER_SEED_MAX} \
            --min-overlap {LOOP_MIN_OVERLAP} \
            --top 60 \
            > idea-survey/.loop_hubs_refs.json
        ```
        For novelty verification, these are typically the seminal works your
        round-1 competitors all built on — i.e. the foundational claims you'd
        need to differentiate from.

    B2. **Hub citations** — newer competitors building on multiple seeds:
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
        `{min_follower_year}` = max(year over all round-1 seeds) - 1. These
        are recent papers that *also* cite multiple of your competitors — i.e.
        the freshest competitors of your direction.

    B3. **Fallback**: if cross-cited returns 0 candidates in either direction,
        retry once with `--min-overlap 1 --top 30` for the references direction
        and save to `.loop_hubs_refs_fallback.json`.

    ## Phase C — Named-baseline + mechanism search

    Generate 3–5 search queries from the mined named-baselines and mechanism
    strings. Strategy:
      - For each top-3 most-cited `named_baselines` not already in the known
        set, run a query like `"<baseline name> <user_direction's task keyword>"`.
      - Take 1 query from a `specific_mechanisms` string verbatim if it
        contains a named operation.
      - 1 query combining two method-family terms to find papers that lie
        at the intersection.

    For each query, run BOTH WebSearch AND arXiv API:
    ```bash
    python3 tools/arxiv_fetch.py search "QUERY" --max 6
    ```

    If TEX_SOURCE_ONLY is true, drop any non-arXiv results.
    Run the arXiv-version-lookup as in Step 1 for non-arxiv hits.

    Save to: `idea-survey/.loop_term_search.json`.

    ## Phase D — Merge + dedup against known set

    Build the known set:
    ```bash
    ls -d idea-survey/literature-deep/paper_*/ 2>/dev/null \
      | sed 's|.*/paper_|paper_|' | sed 's|/$||' > idea-survey/.tmp/known_paper_keys.txt
    ```

    Merge `.loop_hubs_refs.json` (or fallback), `.loop_hubs_cites.json`, and
    `.loop_term_search.json`. For each candidate derive its `paper_key` and
    drop any candidate already in the known set.

    Also drop any candidate whose title is a near-duplicate of a known title
    (lowercased + alphanumeric-only exact match is enough).

    ## Deliverable: idea-survey/.expansion_candidates.json

    ```json
    {
      "round2_budget": <K2 from .loop_budget.json>,
      "phases_run": ["A", "B", "C"],
      "phase_notes": {
        "seeds_with_ids_count": ...,
        "seeds_without_ids_count": ...,
        "named_baselines_used_as_queries": [...],
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
            "named_baseline_match": "Sparse Transformer",
            "term_match_query": "..."
          },
          "citation_count": 487,
          "overlapping_seeds": ["safe_id1", "safe_id2"],
          "claims_potentially_overlapping": ["C1", "C3"]
        }
      ]
    }
    ```

    Cap `candidates` at 60. Rank by (overlap_count desc, influential_overlap_count
    desc, is_recent_follower desc, citation_count desc).

    `claims_potentially_overlapping`: for each candidate, infer which of the
    round-1 `core_claims` it might compete on, based on its overlapping seeds'
    `overlapping_claims` (union). This is a hint for the synthesizer in 4.6b
    and the eventual report-writer.

    ## Forbidden
    - Do NOT deep-read any paper. You are doing metadata aggregation only.
    - Do NOT decide which candidates to deep-analyze. That's 4.6b's job.
    - Do NOT write claim-by-claim novelty assessment.
```

Apply Pattern 2 polling and Pattern 3 audit:

```bash
test -s idea-survey/.expansion_candidates.json
python3 -m json.tool < idea-survey/.expansion_candidates.json > /dev/null
grep -q '"candidates"' idea-survey/.expansion_candidates.json
```

If the candidates list is empty, write `.loop_skipped` with reason `"no_expansion_candidates"` and jump to Step 5.

#### 4.6b: Launch the expansion synthesizer (Pattern 1)

```yaml
Agent:
  description: "Loop expansion synthesizer: select round-2 competitive papers"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are the loop expansion synthesizer for idea-novelty. Pick which of
    the expansion candidates are worth deep-reading in round 2, given the
    novelty-verification goal.

    ## File handling rules
    - Do NOT call ReadMediaFile.
    - Read only the small JSONs listed below. No web search.

    ## Inputs
    - Candidates: idea-survey/.expansion_candidates.json
    - Budget: idea-survey/.loop_budget.json → field `round2_budget`
    - Round-1 paper cards in `literature-deep/paper_*/paper_card.json`
    - Round-1 synthesis: idea-survey/novelty-synthesis.md (read only the JSON
      block — `core_claims`, `selected_competitive_papers`)
    - User direction: "{user_direction}"
    - Output language: {output_language}
    - Tex-source-only mode: {TEX_SOURCE_ONLY}

    ## Selection rules (novelty-specific priorities)

    Pick at most `round2_budget` candidates. Use these priorities, in order:

    1. **Candidates that potentially compete on multiple claims**
       (`claims_potentially_overlapping` length >= 2): these are the highest-
       value novelty checks because one paper resolves multiple claim
       assessments.

    2. **Influential hubs** (`hub_influential_overlap_count >= 2`): when the S2
       graph says the round-1 seeds *meaningfully* built on this paper (not
       just cited it in passing), it almost certainly contains the closest
       mechanism your direction needs to differentiate from.

    3. **Hub references with high overlap** (`hub_overlap_count >= 3`): the
       seminal predecessors of your competitors.

    4. **Recent followers** (`source == "hub_cites"`, `is_recent_follower == true`,
       `hub_overlap_count >= 2`): newer competitors. Important for novelty
       because the field may have moved past round-1's selection during your
       project lifetime.

    5. **Named-baseline term-search matches** (`source == "term_search"` and
       `signal_strength.named_baseline_match != null`): when a paper your
       round-1 competitors explicitly compared against is now reachable, it's
       almost certainly relevant.

    If TEX_SOURCE_ONLY is true: drop any candidate without an `arxiv_id`.

    Aim to cover **each round-1 `core_claim` with at least one round-2
    paper** where possible — `claims_potentially_overlapping` is the matching
    signal. Diversity across claims is more valuable than depth on any one
    claim.

    ## Deliverable: idea-survey/.expansion_selected.json

    Schema matches Step 2's `selected_competitive_papers` exactly:

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
        "overlapping_claims": ["C1", "C3"],
        "selection_rationale": "Influential hub: cited as `isInfluential` by 2 of 4 round-1 seeds [seed1, seed3]. Round-1 cards' `key_tables.what_compared` named this paper directly. Likely the closest mechanism to claim C1.",
        "expansion_source": "hub_refs|hub_cites|term_search",
        "expansion_signal": {
          "hub_overlap_count": 2,
          "hub_influential_overlap_count": 2,
          "overlapping_seeds": ["safe_id1", "safe_id3"],
          "named_baseline_match": "Sparse Transformer"
        },
        "already_analyzed": false,
        "analysis_path": null
      }
    ]
    ```

    All selected papers MUST have `already_analyzed == false` (candidates were
    deduplicated against literature-deep/ in 4.6a; drop anything that looks
    known).

    If after applying all rules zero candidates make the cut, emit `[]` and
    write a one-line explanation to `idea-survey/.expansion_selected_notes.md`.

    ## Forbidden
    - Do NOT exceed `round2_budget` selections.
    - Do NOT deep-read any paper.
    - Do NOT write the novelty report.
```

Audit:

```bash
test -e idea-survey/.expansion_selected.json
python3 -m json.tool < idea-survey/.expansion_selected.json > /dev/null
SELECTED=$(python3 -c "import json; print(len(json.load(open('idea-survey/.expansion_selected.json'))))")
echo "Round-2 selected: $SELECTED competitive papers"
```

If `SELECTED == 0`: log, write `.loop_skipped` with reason `"synthesizer_selected_zero"`, jump to Step 5.

#### 4.6c: Round-2 download + deep analysis (reuses Step 3 / Step 3.5 / Step 4 prompts unchanged)

Identical mechanics to `idea-landscape`'s Step 4.6c: rotate round-1 state files out, copy `.expansion_selected.json` into the `.synthesis_selected.json` slot, then re-run Pool Resolution → Step 3 download-preparer → (optional Step 3.5) → Step 4 paper-analyzer with **unchanged prompts**.

```bash
for f in .synthesis_selected.json \
         .synthesis_selected_resolved.json \
         .download_status.json \
         .ready_papers.json \
         .vision_pending_papers.json ; do
  src="idea-survey/$f"
  dst="idea-survey/${f%.json}.round1.json"
  [ -f "$src" ] && mv "$src" "$dst"
done

cp idea-survey/.expansion_selected.json idea-survey/.synthesis_selected.json

# Pool Resolution (identical to Step 3, USER_DIRECTION = $ARGUMENTS verbatim)
python3 tools/papers_pool.py resolve \
    --selected-papers idea-survey/.synthesis_selected.json \
    --project-dir . \
    --topic "<USER_DIRECTION>" \
    --output idea-survey/.synthesis_selected_resolved.json
```

Then re-launch the Step 3 download-preparer subagent, Step 3.5 (if any paper is `vision_pending`), and Step 4 paper-analyzer subagents — all with the same prompts and concurrency cap (4). The round-2 deep analyses land in `literature-deep/paper_*/deep_analysis.md` alongside round-1.

#### 4.6d: Round-2 paper-card distillation (re-run Step 4.5 logic)

Re-invoke the Step 4.5 enumeration + stale-card calculation + distiller subagent launches. Round-1 cards are mtime-equal to their source and are skipped; only round-2 papers actually get distilled.

#### 4.6 audit summary

```bash
python3 - <<'PY'
import json, pathlib, subprocess
audit = {
    "loop_ran": True,
    "round1_new": json.loads(pathlib.Path("idea-survey/.loop_budget.json").read_text())["round1_new_count"],
    "round2_selected": len(json.loads(pathlib.Path("idea-survey/.expansion_selected.json").read_text())),
    "round2_new_deep_analyses": int(subprocess.check_output(
        "find idea-survey/literature-deep -mindepth 2 -maxdepth 2 -name deep_analysis.md "
        "-newer idea-survey/.loop_budget.json -type f | wc -l", shell=True).strip()),
    "phases_in_expansion": json.loads(pathlib.Path("idea-survey/.expansion_candidates.json").read_text()).get("phases_run", []),
    "phase_notes": json.loads(pathlib.Path("idea-survey/.expansion_candidates.json").read_text()).get("phase_notes", {}),
}
pathlib.Path("idea-survey/.loop_audit.json").write_text(json.dumps(audit, indent=2))
print(json.dumps(audit, indent=2))
PY
```

---

### Step 5: Report Writing (Subagent — ALL Synthesis)

> Main agent does NOT read deep analyses, assess claims, or write report prose. The report-writer subagent does.

#### 5a: Prepare inputs

1. Build the paper-card index for the report-writer:
   ```bash
   ls idea-survey/literature-deep/paper_*/paper_card.json 2>/dev/null \
     | sort \
     > idea-survey/.tmp/paper_card_index.txt
   echo "Report-writer will consume $(wc -l < idea-survey/.tmp/paper_card_index.txt) paper cards."
   ```
   These cards were produced by Step 4.5 (small JSON, ~3–10 KB each).

2. Build a fallback list of `deep_analysis.md` paths for papers whose card failed to distill in Step 4.5 (last-resort on-demand reads, NOT default reading):
   ```bash
   comm -23 \
     <(sort idea-survey/.tmp/all_deep_analyses.txt) \
     <(sed 's|/paper_card.json$|/deep_analysis.md|' idea-survey/.tmp/paper_card_index.txt | sort) \
     > idea-survey/.tmp/cardless_deep_analyses.txt
   ```

3. Note existing report path for guidance preservation: `idea-survey/novelty-report.md`

4. Prepare key metadata:
   - User input direction
   - Output language
   - Synthesis file path: `idea-survey/novelty-synthesis.md`
   - `{paper_card_index}`: contents of `idea-survey/.tmp/paper_card_index.txt`
   - `{cardless_deep_analyses}`: contents of `idea-survey/.tmp/cardless_deep_analyses.txt`

#### 5b: Launch report-writer subagent

```yaml
Agent:
  description: "Report writer: novelty"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are a research report writer. Read the synthesis and the
    paper cards to produce the final novelty assessment report.

    **Context from main orchestrator**:
    - Research direction: {user_input}
    - Output language: {output_language}
    - Synthesis file: idea-survey/novelty-synthesis.md
    - User guidance applied: {user_guidance}
    - Loop audit: idea-survey/.loop_audit.json (present iff Step 4.6 ran);
      idea-survey/.loop_skipped (present iff Step 4.6 was skipped).

    **Files you MUST read (in this order)**:
    1. `templates/PAPER_CARD_SCHEMA.md` — schema for the JSON cards
       below. For novelty work the key fields are `core_claims`,
       `novelty_signals.specific_mechanism`,
       `novelty_signals.setting_constraints`,
       `novelty_signals.what_authors_claim_is_novel`,
       `experimental_setting`, and `quantitative_results`.
    2. `idea-survey/novelty-synthesis.md` — extracted claims and
       selected papers.
    3. `idea-survey/.loop_audit.json` if present. Lists round-2 papers
       added by Step 4.6. When you write the "Closest Prior Work" and
       claim-by-claim sections, weight round-2 hub papers heavily: they
       are statistically more likely to contain the closest mechanism
       to the user's direction than any single round-1 keyword search
       could have surfaced. Mark each round-2 paper's row with its
       `expansion_source` and the round-1 seeds that pulled it in.
       If `.loop_skipped` is present instead, briefly note it in the
       Run Log footer with the recorded reason.
    4. Every paper card in this list:
{paper_card_index}
    5. Upstream landscape: `idea-survey/landscape-report.md`.
    6. `templates/IDEA_NOVELTY_TEMPLATE.md`.
    7. If resuming, `idea-survey/novelty-report.md` — only to
       preserve the User Guidance Section.

    **Files you MAY read on demand (NOT by default)**:
    - The following papers FAILED card distillation in Step 4.5;
      treat their `deep_analysis.md` as last-resort:
{cardless_deep_analyses}
    - Any other `deep_analysis.md` may be opened ONLY when a
      paper card's `novelty_signals.specific_mechanism` is set to
      `"underspecified in source"` AND that paper is the closest
      prior work for one of the user's claims. Use `ReadFile` with
      a narrow `line_offset`; never read a full deep_analysis.md
      to "be safe". The consumer rules in
      `templates/PAPER_CARD_SCHEMA.md` are binding.

    **Output**: Write the complete report to `idea-survey/novelty-report.md`

    **Rules**:
    - Read every paper card in `{paper_card_index}`. Do not skip any.
    - Do NOT read `deep_analysis.md` files by default. Cards exist
      precisely to avoid that. Targeted on-demand reads are allowed
      only as defined above.
    - Do NOT call `ReadMediaFile`. No image analysis.
    - Do NOT run file conversion tools.
    - Follow the template structure exactly.
    - All claims MUST reference a specific paper card. Report links
      that point to "Deep Analysis" should use the card's
      `provenance.deep_analysis_path` (the path to `deep_analysis.md`),
      not the card file itself.
    - Preserve the User Guidance Section at the bottom.
    - Write in {output_language}. Keep paper titles, author names,
      venue names, BibTeX, file paths, and JSON keys in English.
    - The synthesis file contains extracted claims and selected
      papers. You MUST perform the claim-by-claim novelty assessment
      yourself, grounding every rating in the paper cards.
    - Be BRUTALLY honest. Do not soften findings. False novelty
      claims waste months of research time. If a card's
      `novelty_signals.specific_mechanism` is too vague to support a
      MEDIUM/LOW novelty verdict for one of the user's claims, lower
      the verdict to "UNCERTAIN" and flag it in the report rather
      than guessing.
    - **Cross-project relevance**: some paper cards may have been
      distilled by another project that used the shared paper pool.
      Each card's `relevance_at_first_analysis` block records the
      original analysis project's topic, not the current direction
      under verification. For novelty work, this is rarely the bottleneck
      because the fields you actually need
      (`core_claims`, `novelty_signals.specific_mechanism`,
      `novelty_signals.setting_constraints`,
      `quantitative_results`, `experimental_setting`) are
      project-agnostic and can be consumed as-is. However, if a card
      flags itself as "Tangential" under
      `relevance_at_first_analysis.direct_relevance`, do NOT treat
      that as a signal to skip — the original topic may have been
      different from the current direction. Always assess novelty
      using paper-intrinsic fields.
```

#### 5c: Verify output

- Wait for the report-writer subagent to complete using the polling protocol.
- Verify that `idea-survey/novelty-report.md` exists and is non-empty.
- If the subagent fails or produces an empty file, retry once with the identical prompt.
- If the retry also fails, log the failure. Do NOT write the report yourself in the main agent.

---

## Key Rules Summary

1. **Zero-interruption execution**: Run from start to finish without asking the user.
2. **Main agent NEVER analyzes papers**: All analysis is delegated to `paper-analyzer` subagents.
3. **Main agent NEVER synthesizes**: Claim extraction, paper selection, and novelty assessment are delegated to subagents.
4. **Main agent NEVER downloads**: Source preparation is delegated to `download-preparer` subagent.
5. **Strict polling protocol**: 5min → 3min → 1min loop. No shortcuts.
6. **Concurrency cap**: Maximum 4 concurrent subagents.
7. **Deduplication**: Reuse analyses from `literature-deep/` and upstream landscape.
8. **Claim-by-claim granularity**: Assess each claim independently. A direction can be partially novel.
9. **Brutal honesty**: Do not soften findings. False novelty claims waste months of research time.
10. **Guidance-aware resume**: Automatically read user guidance from the previous report on re-run.
11. **Loop expansion is fixed at one round**: Step 4.6 fires exactly once per run, gated by `LOOP_ENABLED`, `LOOP_MIN_SEEDS`, and the residual budget `DEEP_ANALYZE_MAX * EXPAND_BUDGET_FACTOR - round1_new`. Round-2 expansion is biased toward competitor discovery (citation-graph hubs + named baselines) — not landscape breadth. The audit sentinel (`.loop_audit.json` or `.loop_skipped`) records the outcome for the report-writer.
