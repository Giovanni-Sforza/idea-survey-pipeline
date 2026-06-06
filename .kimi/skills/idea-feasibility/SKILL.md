---
name: idea-feasibility
description: Feasibility assessment for a research direction that has passed novelty check. Use AFTER idea-novelty when the user wants to know whether the direction is technically feasible, whether key assumptions hold, and whether claimed improvements are realistic. Based on deep analysis of supporting and contradictory evidence. This is the THIRD stage of the idea-survey pipeline.
argument-hint: [researched-direction-with-novelty-assessment]
---

# Idea Feasibility Assessment

Research direction to assess: $ARGUMENTS

## Constants

- **OUTPUT_DIR = `idea-survey/`** — All outputs are written here.
- **DEEP_ANALYZE_MAX = 6** — Maximum number of NEW evidence papers to deep-analyze per run. Override via `— deep-analyze-max: N`.
- **DEEP_ANALYZE_CONCURRENCY = 4** — Maximum concurrent `paper-analyzer` subagents. Hard cap.
- **SUBAGENT_TIMEOUT = 3600** — Per-subagent timeout in seconds (1 hour).
- **OUTPUT_LANGUAGE = "auto"** — Follow the shared output-language protocol.
- **RESUME_FILE = `idea-survey/feasibility-report.md`** — The report file that also stores user guidance.
- **UPSTREAM_NOVELTY = `idea-survey/novelty-report.md`** — Loaded by subagents for claims and competitive papers.
- **UPSTREAM_LANDSCAPE = `idea-survey/landscape-report.md`** — Loaded by subagents for domain context.
- **SHARED_DEEP_DIR = `idea-survey/literature-deep/`** — Shared deep-analysis directory.
- **TWO_PHASE_BYTES_THRESHOLD = 26214400** — 25 MB. Papers with preprocessed images whose total byte size exceeds this trigger Two-Phase Analysis.
- **TWO_PHASE_IMAGE_COUNT_MIN = 4** — Minimum image count for Two-Phase. Papers with fewer images fall back to degraded text-only analysis instead.
- **TEX_SOURCE_ONLY = false** — When true, only papers with available arXiv TeX source are selected and deep-analyzed. Papers without an arXiv ID, or whose TeX source cannot be downloaded, are skipped. No PDF fallback is attempted. Override via `— tex-only: true`.
- **PDF_PARSER = "auto"** — PDF backend when a paper has no arXiv TeX source. Allowed values: `auto` (MinerU if installed, else legacy), `full` (force MinerU), `legacy` (image-only, no captions/equations/tables), `vision` (PyMuPDF page render + multimodal subagent extraction; no MinerU, no GPU). Override via `— pdf-parser: vision`. The `vision` path triggers an extra subagent step (Step 3.5) between download and deep analysis.
- **VISION_PARSE_CONCURRENCY = 4** — Maximum concurrent vision-manifest subagents in Step 3.5. Hard cap.
- **LOOP_ENABLED = true** — When true, run Step 4.6 (Loop Expansion) after round-1 deep analysis. Round-2 search uses three signals: (i) citation-graph hubs from round-1 seeds, (ii) precise-term refinement, and **(iii) gap-driven queries built from round-1 cards' `gap_signals`, `limitations_acknowledged`, and `limitations_observed`** — feasibility-specific, because feasibility hinges on finding evidence that a failure mode does or doesn't recur. Override via `— loop: false`.
- **EXPAND_BUDGET_FACTOR = 2** — Total NEW deep-analysis budget across both rounds = `DEEP_ANALYZE_MAX * EXPAND_BUDGET_FACTOR`. Round 1 may consume up to `DEEP_ANALYZE_MAX`; round 2 consumes the remaining budget. Override via `— expand-budget-factor: N`.
- **LOOP_MIN_SEEDS = 2** — Skip Step 4.6 when round 1 produced fewer than this many NEW deep analyses.
- **LOOP_REF_PER_SEED_MAX = 80** — Per-seed cap when fetching outgoing references for hub detection.
- **LOOP_CITE_PER_SEED_MAX = 80** — Per-seed cap when fetching incoming citations for recent-follower detection.
- **LOOP_MIN_OVERLAP = 2** — Cross-citation minimum-overlap K for citation-graph hub detection.

> 💡 Overrides:
> - `/skill:idea-feasibility "direction" — deep-analyze-max: 8` — round 1 up to 8 evidence papers (total budget across rounds: 16)
> - `/skill:idea-feasibility "direction" — deep-analyze-max: 3` — minimal run
> - `/skill:idea-feasibility "direction" — language: zh` — output in Chinese
> - `/skill:idea-feasibility "direction" — tex-only: true` — only use papers with arXiv TeX source
> - `/skill:idea-feasibility "direction" — pdf-parser: vision` — use the vision-LLM PDF path (recommended for MacBook Air / CPU-only machines)
> - `/skill:idea-feasibility "direction" — loop: false` — disable the round-2 citation-graph + term + gap-driven expansion
> - `/skill:idea-feasibility "direction" — expand-budget-factor: 3` — allow round 2 to grow the total budget to 3× round-1

---

## 🚧 Main Agent Boundary Protocol — ORCHESTRATE ONLY 🚧

> **This section exists because earlier runs of upstream skills exhausted the main agent's context by directly reading papers, extracting assumptions, and writing assessment prose, then required a `/compact` that broke cross-step consistency.** It is the single most important rule in this file.

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
- ❌ **Reading** the body of `landscape-report.md`, `novelty-report.md`, or `feasibility-report.md` for synthesis purposes. (Mechanical extraction of `ARIS_GUIDANCE` blocks is OK.)
- ❌ **Analyzing** paper content, figures, tables, or equations directly.
- ❌ **Writing** any synthesis prose, assumption statements, feasibility assessments, or risk analysis — even one sentence.
- ❌ **Extracting** assumptions from the user input or upstream reports.
- ❌ **Selecting** evidence papers to analyze.
- ❌ **Downloading** or preparing paper sources directly.
- ❌ **"Falling back"** to direct work because a subagent is slow, timed out, or failed.

### The "I'll just peek" rule

| Tempted to read | Correct action |
|---|---|
| "Let me check what assumptions the synthesizer extracted." | Read `idea-survey/feasibility-synthesis.md` — only the `selected_papers` JSON block. |
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

1. **Load resume & guidance** from `idea-survey/feasibility-report.md`:
   - If it exists: extract `ARIS_GUIDANCE_START...END` → `USER_GUIDANCE`.
   - Extract already-assessed assumptions → `EXISTING_CONTEXT`.
   - Log: `"Resume detected. Loaded N guidance items."`
   - If it does not exist: `USER_GUIDANCE = ""`.

2. **Note upstream report paths**:
   - `idea-survey/novelty-report.md` exists for subagents to read.
   - `idea-survey/landscape-report.md` exists for subagents to read.
   - Main agent does NOT read either report.
   - Main agent MAY do mechanical checks: `test -s idea-survey/novelty-report.md`.

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

Identical to all idea-survey skills. These rules are **NON-NEGOTIABLE**.

### RULE 1: Main Agent NEVER Analyzes Papers Directly
The main orchestrator agent is **STRICTLY FORBIDDEN** from reading, summarizing, or analyzing paper content directly. ALL paper analysis MUST be performed by dedicated `paper-analyzer` subagents launched via the `Agent` tool.

### RULE 2: No Fallback to Main Agent — EVER
Under **NO circumstances** should the main agent "fall back" to direct analysis. If a subagent fails or times out, **retry once with the identical prompt**. Most failures are transient network issues. If the retry also fails, log it as `"FINAL_FAILED"` or `"FINAL_TIMEOUT"` and continue. **NEVER** fill the gap with main-agent direct analysis.

### RULE 3: Main Agent ONLY Orchestrates
The main agent decides which papers to analyze (based on synthesizer output), launches subagents, waits via polling, collects outputs, and delegates report compilation. The main agent MUST NOT read papers, interpret figures, or write analysis.

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

### Step 1: Per-Assumption Evidence Search (Search Subagent)

> Main agent does NOT run web searches, arXiv queries, or Semantic Scholar calls. The search-agent subagent does.

**Inputs to search-agent**: user direction, `TEX_SOURCE_ONLY`, `output_language`, `EXISTING_CONTEXT`.
**Expected output**: `idea-survey/.feasibility_search_results.json`.

#### Launch search-agent (Pattern 1)

```yaml
Agent:
  description: "Search-agent: evidence literature search"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are a research search specialist. Perform ALL search and raw data gathering for the idea-feasibility skill. The main orchestrator does NOT run any searches itself.

    ## File handling rules
    - Do NOT call ReadMediaFile. No images here.
    - Do NOT run any image-conversion tools.
    - Do NOT extract assumptions, assess feasibility, or write assessment prose.
    - You MAY run shell commands and Python tools in `tools/`.

    ## Inputs
    - User direction: "{user_direction}"
    - Tex-source-only mode: {TEX_SOURCE_ONLY}
    - Output language: {output_language}
    - Existing context (already assessed): {EXISTING_CONTEXT}
    - Per-query cap: 8 results
    - Post-merge cap: 20 unique evidence papers

    ## Search Dimensions
    Generate 6-9 evidence search queries covering:
    1. **Supporting evidence**: papers that demonstrate the same or similar mechanism working.
    2. **Contradicting evidence**: papers that report failures, instabilities, or negative results.
    3. **Boundary evidence**: papers that show the mechanism works ONLY under specific conditions.
    Search scope: the mechanism itself, the specific application domain, comparable baselines.
    Run at least 2-3 queries per assumption aspect.

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
    - **Post-merge cap**: After deduplication, retain at most 20 unique evidence papers. If more, prioritize by: direct relevance, result clarity, recency.

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
    Save the final results to: `idea-survey/.feasibility_search_results.json`

    Format:
    ```json
    {
      "user_direction": "...",
      "queries": [
        {"type": "Supporting", "assumption_aspect": "A1", "query": "...", "results": [{"title": "...", "authors": "...", "year": ..., "venue": "...", "abstract": "...", "url": "...", "arxiv_id": "..."}]}
      ],
      "merged_papers": [
        {"title": "...", "authors": "...", "year": ..., "venue": "...", "abstract": "...", "url": "...", "arxiv_id": "...", "sources": ["query1"]}
      ],
      "arxiv_lookup_summary": {
        "total_non_arxiv": 10,
        "found_arxiv_versions": 4,
        "still_non_arxiv": 6
      },
      "total_unique": 20
    }
    ```

    ## Forbidden
    - Do NOT analyze paper content, figures, or equations.
    - Do NOT extract assumptions or perform feasibility assessment.
    - Do NOT select which evidence papers to deep-analyze.
    - Do NOT write the final report or synthesis.
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

Audit:
```bash
test -s idea-survey/.feasibility_search_results.json || exit 1
python3 -m json.tool < idea-survey/.feasibility_search_results.json > /dev/null || exit 1
grep -q '"merged_papers"' idea-survey/.feasibility_search_results.json || exit 1
```

---

### Step 2: Feasibility Synthesis (Subagent — ALL Intellectual Work)

> Main agent does NOT extract assumptions, select evidence papers, or assess feasibility. The synthesizer subagent does.

**Inputs to synthesizer**: paths to `.feasibility_search_results.json`, `USER_GUIDANCE`, upstream `novelty-report.md`, upstream `landscape-report.md`, `EXISTING_CONTEXT`, `output_language`.
**Expected output**: `idea-survey/feasibility-synthesis.md`.

#### Launch synthesizer (Pattern 1)

```yaml
Agent:
  description: "Feasibility synthesizer: assumption extraction + evidence selection"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are a feasibility synthesizer. Perform ALL intellectual analysis for the
    idea-feasibility skill. You read search results and upstream reports to
    produce structured synthesis.

    ## File handling rules
    - Do NOT call ReadMediaFile. No images here.
    - Do NOT run any image-conversion tools.
    - Do NOT run web searches.

    ## Output language
    All synthesis text: {output_language}.
    JSON keys: always English.
    Paper titles, author names, venue names, arXiv IDs: English.

    ## Inputs (read these in full)
    - Search results: idea-survey/.feasibility_search_results.json
    - Upstream novelty: idea-survey/novelty-report.md
    - Upstream landscape: idea-survey/landscape-report.md (for domain context)
    - User guidance: "{USER_GUIDANCE}" (may be empty)
    - User direction: "{user_direction}"
    - Existing context (already assessed): {EXISTING_CONTEXT}
    - Template: templates/IDEA_FEASIBILITY_TEMPLATE.md (for field reference)

    ## Deliverable: idea-survey/feasibility-synthesis.md

    Write a structured Markdown file. The first section MUST be a JSON code block
    with machine-readable selections.

    ### Section 1: Structured Selections (JSON)

    ```json
    {
      "key_assumptions": [
        {"id": "A1", "statement": "...", "if_false": "...", "prior_risk": "HIGH|MEDIUM|LOW", "related_claim": "C1"}
      ],
      "selected_evidence_papers": [
        {
          "safe_id": "arxiv_2301_07041",
          "title": "...",
          "authors": "...",
          "year": 2024,
          "venue": "...",
          "arxiv_id": "2301.07041",
          "abstract": "...",
          "url": "...",
          "supporting_assumptions": ["A1"],
          "evidence_type": "Supporting|Contradicting|Boundary",
          "selection_rationale": "Directly tests gating stability with ablations.",
          "already_analyzed": false,
          "analysis_path": null
        }
      ],
      "search_summary": {
        "total_assumptions": 4,
        "total_queries": 12,
        "total_unique_papers": 20,
        "new_selected": 5,
        "reused_from_upstream": 2
      }
    }
    ```

    Rules for `key_assumptions`:
    - Generate 3-5 assumptions.
    - Each assumption must be linked to at least one claim from the novelty report.
    - If USER_GUIDANCE asks to focus on or ignore specific assumptions, respect it.

    Rules for `selected_evidence_papers`:
    - Select at most {DEEP_ANALYZE_MAX} NEW papers.
    - Check against upstream novelty/landscape "Deep Analysis Index" and `literature-deep/`.
    - If already analyzed, set `already_analyzed: true` and `analysis_path`.
    - Prioritize by: risk level (assess HIGH-risk assumptions first), result clarity, recency.
    - Each selected paper MUST have a clear `selection_rationale` and `evidence_type`.
    - **If TEX_SOURCE_ONLY is true**: ONLY select papers that have an arXiv ID. Skip any paper without an arXiv ID. Do NOT select PDF-only evidence papers.

    ### Section 2: Human-Readable Synthesis

    After the JSON block, write:
    - Key Assumptions & Risk Points (table)
    - Evidence Search Summary (bullet list)

    ## Forbidden
    - Do NOT write the final `feasibility-report.md`. That is the report-writer's job.
    - Do NOT invent papers not present in the search results.
    - Do NOT perform feasibility assessment. That requires deep analysis.
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

Audit:
```bash
test -s idea-survey/feasibility-synthesis.md || exit 1
grep -q '"selected_evidence_papers"' idea-survey/feasibility-synthesis.md || exit 1
```

---

### Step 3: Source Preparation (Download-Preparer Subagent)

> Main agent does NOT download papers or run image_preprocessor.py.

**Inputs to download-preparer**: `feasibility-synthesis.md` (reads the JSON block).
**Expected output**: `idea-survey/.download_status.json`.

#### Main agent extracts the paper list (shell only)

```bash
python3 -c "
import re, json, sys
with open('idea-survey/feasibility-synthesis.md') as f:
    text = f.read()
match = re.search(r'\`\`\`json\n(.*?)\n\`\`\`', text, re.DOTALL)
if not match:
    print('No JSON block found', file=sys.stderr)
    sys.exit(1)
data = json.loads(match.group(1))
with open('idea-survey/.synthesis_selected.json', 'w') as out:
    json.dump(data.get('selected_evidence_papers', []), out)
"
```

#### Pool Resolution (shell only)

> Identical purpose to `idea-landscape` Pool Resolution: dedup each selected paper against the shared paper pool at `$ARIS_PAPERS_POOL`. Reuses prior analyses cross-project; no-op fallback when the pool is not configured.

```bash
# Replace <USER_DIRECTION> below with the verbatim $ARGUMENTS string
# (the research direction whose feasibility is being assessed).
python3 tools/papers_pool.py resolve \
    --selected-papers idea-survey/.synthesis_selected.json \
    --project-dir . \
    --topic "<USER_DIRECTION>" \
    --output idea-survey/.synthesis_selected_resolved.json
```

See `idea-landscape/SKILL.md` Pool Resolution for the full `pool_status` schema. After this step, `idea-survey/literature-deep/` already contains correct directories/symlinks for every selected evidence paper; the download-preparer only fetches sources for `action == "analyze"` papers.

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

    - **If `pool_status.action == "reuse"`**: skip download and preprocessing.
      Record `status: "reuse"`, `workspace: pool_status.project_link`.
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
         Capture the orchestrator's stdout — it is JSON with a `mode` field.  Copy that value into the paper's `mode` field.  If `mode == "pdf-vision-pending"`, set `status` to `"vision_pending"`; otherwise `"ready"`.

         After the run, leave any generated `parse_log.json` in place — it is the audit trail (heuristic captions, low-confidence equations) for later human review; it is **not** a gating signal for the main agent.

    4. Preprocess all images **only when status == "ready"**.  Skip this step for `vision_pending` papers — image preprocessing happens after Step 3.5 finishes.
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
    - Do NOT attempt to finalize vision-pending manifests yourself. That is Step 3.5's job.
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

> **Only runs when at least one paper in `.vision_pending_papers.json` exists** (i.e., `PDF_PARSER == "vision"` and an evidence paper had no arXiv TeX source).  This step converts a `vision_stub.json` (rendered pages + extracted embedded images, produced by Step 3) into a complete `figure_manifest.json` that is schema-identical to the MinerU and TeX paths.
>
> **Why a separate step**: the `paper-editor` subagent used by Step 3 has no vision capability. The vision-LLM extraction must be performed by a `paper-analyzer` subagent (multimodal, already used in Step 4 for figure analysis).

**Inputs**: `idea-survey/.vision_pending_papers.json`.
**Expected output (per paper)**: `idea-survey/literature-deep/paper_{safe_id}/figure_manifest.json` and `vision_extraction.json`.

#### Launch vision-extractor subagents (Pattern 1, one per paper)

**CRITICAL**: Maintain concurrency <= VISION_PARSE_CONCURRENCY. Queue and launch new ones as slots free.

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

If audit fails for a paper, retry the subagent ONCE with the same prompt. If retry fails, mark `"FINAL_FAILED"` and exclude from Step 4. Do NOT fall back to main-agent direct analysis.

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

Subagent prompt (feasibility-focused variant):
```yaml
Agent:
  description: "Feasibility analysis: {short_title}"
  subagent_type: "paper-analyzer"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are an expert academic paper analyst. Perform a deep reading of the following paper with a FOCUS on extracting evidence for or against specific technical assumptions.

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

    ## Assumptions to Evaluate
    {list_of_assumptions}

    ## Your Task
    Read this paper deeply and produce an analysis that answers:
    1. What is the main contribution of this paper?
    2. What EXACT experiments were run? (datasets, model sizes, hyperparameters, metrics)
    3. What were the KEY numerical results? Extract exact numbers with units/baselines.
    4. For EACH assumption above:
       a) Does this paper provide SUPPORTING evidence? (If yes, quote the exact finding/number.)
       b) Does this paper provide CONTRADICTING evidence? (If yes, quote the exact finding/number.)
       c) Does this paper establish BOUNDARY CONDITIONS? (Under what settings does it work/fail?)
       d) Is this paper NOT relevant to the assumption? (State clearly.)
    5. What limitations, failure modes, or negative results does the paper report?
    6. What is the STRONGEST piece of evidence in this paper for feasibility assessment?

    ## Extracted Figures, Tables & Equations
    Read the figure manifest: {figure_manifest_path}
    Image directory: {figures_dir}

    ### Graceful Degradation & Image Throttling
    **Throttling rule**: Read images ONE AT A TIME.
    **Degradation rule**: If you encounter an `LLM provider error`, SKIP remaining image analysis. Continue with text, equations, and tables.

    ### Figure Analysis — VISION-FIRST MANDATE
    For every figure in the manifest: ReadMediaFile, analyze visual content, correlate with text claims, explain WHY it matters, extract key numbers.

    ### Table Analysis
    For each table: describe structure, explain which claim it supports, extract key data points.

    ### Equation Analysis
    For each important equation: explain mathematical meaning, define variables, identify assumptions.

    ## TeX Source — AUXILIARY USE ONLY
    If TeX source is available, read the main `.tex` file ONLY for narrative structure, captions, and exact equation LaTeX.

    ## Output
    Write a structured Markdown file to: {output_path}
    Follow `templates/PAPER_DEEP_ANALYSIS_TEMPLATE.md`. Include a "Feasibility Evidence" section addressing the 6 questions above.

    Rules:
    - Every figure/table/equation in the manifest MUST be analyzed
    - Use `ReadMediaFile` for each image
    - Be precise about numbers. Quote exact values, not approximations.
    - Clearly distinguish between what the paper CLAIMS and what it actually DEMONSTRATES.
    - Note any gap between the paper's experimental setting and the proposed method's setting.
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

> **Why this step exists.** The report-writer in Step 5 used to read every `deep_analysis.md` directly. With 6+ papers, that exceeded the subagent's context window and forced compaction, which broke assumption-by-assumption consistency in the final report. This step compresses each `deep_analysis.md` (50–150 KB) into a small structured `paper_card.json` (3–10 KB) that the report-writer reads instead. Full schema in [templates/PAPER_CARD_SCHEMA.md](../../templates/PAPER_CARD_SCHEMA.md).
>
> **Scope: every paper in `idea-survey/literature-deep/`**, not just papers selected for this run's evidence assessment. Cards are a project-wide derived artifact shared across `idea-landscape`, `idea-novelty`, and `idea-feasibility`. Cards distilled in upstream stages are reused here at zero cost (mtime check). The `feasibility_signals` and `quantitative_results` blocks are this skill's primary input.

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

    **Feasibility-specific emphasis**:
    `quantitative_results` and `feasibility_signals` are the
    primary inputs to the downstream feasibility assessment.
    For each `quantitative_results` entry, the `setting` field
    must include the exact experimental context (dataset, scale,
    hyperparameter regime) — a bare number is useless. For
    `feasibility_signals.demonstrated_to_work_when` and
    `demonstrated_to_fail_when`, quote the deep_analysis section
    you derived the assertion from (in `evidence_pointer`-style
    pointers if no native field exists).

    **Anti-fabrication rule**:
    - If a field can't be supported from the source, leave it
      empty. Half-remembered details are worse than empty slots.

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

Retry each failed card's distiller subagent once. If the second attempt also fails, log and proceed — Step 5 will see only the cards that succeeded.

> The main agent **MAY** read `paper_card.json` files (small structured JSON, < 10 KB each) at any point. The boundary protocol's ban on reading `deep_analysis.md` directly is unchanged.

---

### Step 4.6: Loop Expansion — Citation-Graph + Term Refinement + Gap-Driven (Subagents — ALL Intellectual Work)

> **Why this step exists.** Round-1 evidence search builds queries from the user's *assumptions* in their wording, which is structurally unable to surface (a) the field's citation hubs and (b) the *specific failure modes* mentioned only in round-1 papers' limitations sections. After round-1 deep reading, however, we know precisely which assumptions stalled, where the mechanism broke, and what the field's consensus on those failure modes is.
>
> For **feasibility assessment** the round-2 expansion uses three signals, in order of importance: (1) citation-graph hubs, which surface the seminal works supporting / contradicting your mechanism; (2) precise-term refinement, which retrofits round-1's queries with the actual field vocabulary; and (3) **gap-driven queries**, built from each round-1 paper card's `gap_signals`, `limitations_acknowledged`, and `limitations_observed` — these turn "this method fails when X" into a search for "what's known about X". **Exactly one expansion round** is performed.

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
        "evidence_role": paper.get("evidence_role"),
        "addresses_assumption_ids": paper.get("addresses_assumption_ids") or [],
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

**If `skip_reason` is non-null**, log the reason, write the `idea-survey/.loop_skipped` sentinel, and **jump directly to Step 5**.

Substitute `{LOOP_ENABLED}`, `{EXPAND_BUDGET_FACTOR}`, `{DEEP_ANALYZE_MAX}`, `{LOOP_MIN_SEEDS}` with the constants resolved against any user override.

> Note: the schema field `evidence_role` may be `"Supporting"`, `"Contradicting"`, or `"Boundary"` (matching round-1's evidence-role tagging). This is preserved through to round 2 so the expansion knows whether each seed's gap_signals describe a *failure of the supporting mechanism* (high-value for finding contradicting follow-ups) or a *failure of an adversary* (informative but lower priority).

#### 4.6a: Launch the expansion-search subagent (Pattern 1)

```yaml
Agent:
  description: "Loop expansion: citation graph + term refinement + gap-driven (feasibility)"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are the **loop expansion search subagent** for idea-feasibility.
    Round-1 evidence papers are already deep-read; their cards give you
    citation-graph seeds, precise field vocabulary, AND explicit
    failure-mode statements. Your job is to convert all three into a second
    round of candidates focused on **evidence saturation** — finding papers
    that confirm, contradict, or bound the mechanism your round-1 papers
    examined.

    ## File handling rules
    - Do NOT call ReadMediaFile.
    - Do NOT run image-conversion tools.
    - Do NOT assess assumptions or write feasibility prose.
    - Read ONLY: paper_card.json files for round-1 seeds, and the search-
      result JSONs you produce.

    ## Inputs
    - User direction: "{user_direction}"
    - Output language: {output_language}
    - Round-1 seed list: idea-survey/.loop_budget.json → field `round1_new_seeds`
      (each seed carries `evidence_role` ∈ {Supporting, Contradicting, Boundary}
       and `addresses_assumption_ids`)
    - Round-2 budget K2: idea-survey/.loop_budget.json → field `round2_budget`
    - Known set: all directories under idea-survey/literature-deep/paper_*/
    - Round-1 synthesis: idea-survey/feasibility-synthesis.md (read only the
      JSON block — `key_assumptions`, `selected_evidence_papers`)
    - Tex-source-only mode: {TEX_SOURCE_ONLY}
    - Per-seed reference cap: {LOOP_REF_PER_SEED_MAX}
    - Per-seed citation cap: {LOOP_CITE_PER_SEED_MAX}
    - Cross-citation minimum overlap K: {LOOP_MIN_OVERLAP}

    ## Phase A — Mine round-1 cards for seeds, precise terms, AND gap statements

    For each seed in `round1_new_seeds`:
      1. Read `{workspace}/paper_card.json` (skip silently if missing).
      2. Build a citation-graph seed_id (ARXIV:..., DOI, or title-fallback).
      3. Extract **precise-term signal**: `technical_route.method_family`,
         `route_label`, `novelty_signals.specific_mechanism`,
         `experimental_setting.task`, `experimental_setting.datasets`,
         named methods in `core_claims[*].claim`.
      4. Extract **gap signal** (the feasibility-specific bit):
         - `gap_signals` (verbatim "what is left undone" statements).
         - `limitations_acknowledged` (what the authors admitted).
         - `limitations_observed` (what the round-1 paper-analyzer flagged
           that the authors did not admit).
         - `feasibility_signals.reported_failure_modes` (named instabilities).
         - `feasibility_signals.demonstrated_to_fail_when` (specific settings).
         Pair each gap statement with the seed's `evidence_role`:
           * Supporting seed → its failure mode is a high-priority gap
             query (we want to know whether other papers report the same
             failure or have engineered around it).
           * Contradicting seed → its failure mode IS the contradiction;
             a search around it surfaces other contradictions.
           * Boundary seed → its failure mode IS the boundary; a search
             around it surfaces other boundary conditions.

    Write the mined intermediate to: `idea-survey/.loop_mined.json`

    ```json
    {
      "seeds_with_ids": [
        {"safe_id": "...", "seed_id": "ARXIV:2301.07041", "paper_key": "...",
         "title": "...", "arxiv_id": "2301.07041", "doi": null,
         "evidence_role": "Supporting", "addresses_assumption_ids": ["A1", "A2"]}
      ],
      "seeds_without_ids": [...],
      "precise_terms": {
        "method_families": [...],
        "route_labels": [...],
        "specific_mechanisms": [...],
        "tasks": [...],
        "datasets": [...]
      },
      "gap_statements": [
        {"seed_safe_id": "...",
         "evidence_role": "Supporting",
         "addresses_assumption_ids": ["A2"],
         "kind": "gap_signal|limitation_acknowledged|limitation_observed|failure_mode",
         "text": "Verbatim statement, <= 30 words.",
         "priority": "high|medium|low"}
      ]
    }
    ```

    Priority assignment: gap_statements from Supporting seeds → high; from
    Contradicting seeds → high (they ARE the contradiction); from Boundary
    seeds → medium; limitations_observed by the round-1 paper-analyzer (i.e.
    not author-admitted) → high regardless of seed role (more likely to be
    untracked by the field).

    Cap gap_statements at 20 (highest priority first).

    If `seeds_with_ids` is empty, skip Phase B; run Phase C and D only.

    ## Phase B — Citation-graph expansion

    B1. **Hub references** — supporting predecessors:
        ```bash
        python3 tools/semantic_scholar_fetch.py cross-cited \
            "{comma_joined_seed_ids}" \
            --direction references \
            --per-seed-max {LOOP_REF_PER_SEED_MAX} \
            --min-overlap {LOOP_MIN_OVERLAP} \
            --top 60 \
            > idea-survey/.loop_hubs_refs.json
        ```

    B2. **Hub citations** — recent papers building on multiple seeds:
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
        For feasibility, hub_cites is especially valuable when at least one
        round-1 seed is a Contradicting paper: papers that cite the
        contradiction AND something else are likely "we addressed this
        failure mode by …" engineering papers — i.e. the boundary papers.

    B3. **Fallback** with `--min-overlap 1 --top 30` for references direction
        if cross-cited returns 0.

    ## Phase C — Precise-term search

    3–5 queries combining method-family + task + dataset terms (similar to
    landscape's Phase C). Use WebSearch + arXiv API, cap 6 per query,
    same arxiv-version-lookup as Step 1.

    Save to: `idea-survey/.loop_term_search.json`.

    ## Phase D — Gap-driven search (feasibility-specific)

    For each `high`-priority `gap_statement` (up to 8 of them — that's the
    budget that fits within the search subagent's runtime):

    1. Convert the verbatim text into a search query. Strip dataset / method
       names that would over-constrain it; keep the *mechanism term* and the
       *failure modifier*. Example:
       - "Diffusion sampling becomes unstable when t→0 with cosine schedule"
         → query: "diffusion model sampling instability cosine schedule"
       - "EGNN v2 prediction goes negative in high-multiplicity events"
         → query: "equivariant GNN flow prediction negative high multiplicity"

    2. Run WebSearch + arXiv API for each gap-driven query. Cap at 5
       results per query.

    3. **Tag each gap-driven hit** with the originating gap_statement:
       ```json
       {"gap_originating_seed": "safe_id", "gap_priority": "high",
        "gap_kind": "limitation_observed", "gap_text": "..."}
       ```

    4. Run the arXiv-version-lookup as in Step 1.

    Save to: `idea-survey/.loop_gap_search.json`.

    If TEX_SOURCE_ONLY is true, drop any non-arXiv hits across all phases.

    ## Phase E — Merge + dedup against known set

    Build the known set:
    ```bash
    ls -d idea-survey/literature-deep/paper_*/ 2>/dev/null \
      | sed 's|.*/paper_|paper_|' | sed 's|/$||' > idea-survey/.tmp/known_paper_keys.txt
    ```

    Merge `.loop_hubs_refs.json` (or fallback), `.loop_hubs_cites.json`,
    `.loop_term_search.json`, AND `.loop_gap_search.json`. Drop known papers.
    Drop near-duplicate titles.

    ## Deliverable: idea-survey/.expansion_candidates.json

    ```json
    {
      "round2_budget": <K2>,
      "phases_run": ["A", "B", "C", "D"],
      "phase_notes": {
        "seeds_with_ids_count": ...,
        "seeds_without_ids_count": ...,
        "gap_statements_used": ...,
        "hub_refs_count": ...,
        "hub_cites_count": ...,
        "term_search_count": ...,
        "gap_search_count": ...,
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
          "arxiv_id": "...",
          "doi": null,
          "paper_key_proposal": "paper_arxiv_2401_99999",
          "source": "hub_refs|hub_cites|term_search|gap_search",
          "signal_strength": {
            "hub_overlap_count": 3,
            "hub_influential_overlap_count": 2,
            "is_recent_follower": true,
            "term_match_query": "...",
            "gap_originating_seed": "safe_id1",
            "gap_priority": "high",
            "gap_kind": "limitation_observed"
          },
          "citation_count": 487,
          "overlapping_seeds": ["safe_id1", "safe_id2"],
          "addresses_assumption_ids_proposed": ["A2"]
        }
      ]
    }
    ```

    Cap `candidates` at 70 (one extra slot for the gap-search channel).

    Rank by:
      1. gap_search with gap_priority == "high" (highest)
      2. hub_overlap_count desc + hub_influential_overlap_count desc
      3. hub_cites recent_followers
      4. term_search

    `addresses_assumption_ids_proposed`: for each candidate, the union of
    `addresses_assumption_ids` from its overlapping seeds (for hub_refs /
    hub_cites) or from its originating seed (for gap_search). Hint for 4.6b.

    ## Forbidden
    - Do NOT deep-read any paper.
    - Do NOT decide which candidates to deep-analyze.
    - Do NOT write assumption-by-assumption assessment.
```

Apply Pattern 2 polling and Pattern 3 audit. If `candidates == []`, write `.loop_skipped` with reason `"no_expansion_candidates"` and jump to Step 5.

#### 4.6b: Launch the expansion synthesizer (Pattern 1)

```yaml
Agent:
  description: "Loop expansion synthesizer: select round-2 evidence papers"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 1800
  prompt: |
    You are the loop expansion synthesizer for idea-feasibility. Pick
    which expansion candidates are worth deep-reading in round 2, given
    the feasibility-assessment goal.

    ## File handling rules
    - Do NOT call ReadMediaFile.
    - Read only the small JSONs listed below.

    ## Inputs
    - Candidates: idea-survey/.expansion_candidates.json
    - Budget: idea-survey/.loop_budget.json → field `round2_budget`
    - Round-1 paper cards under `literature-deep/paper_*/paper_card.json`
    - Round-1 synthesis: idea-survey/feasibility-synthesis.md (read only the
      JSON `key_assumptions` and `selected_evidence_papers` blocks)
    - User direction: "{user_direction}"
    - Output language: {output_language}
    - Tex-source-only mode: {TEX_SOURCE_ONLY}

    ## Selection rules (feasibility-specific priorities)

    Pick at most `round2_budget` candidates. Use these priorities, in order:

    1. **Gap-driven high-priority hits** (`source == "gap_search"` AND
       `signal_strength.gap_priority == "high"`): these directly probe a
       failure mode identified by round-1 reading. They are the most
       informative evidence type for the feasibility verdict — they can
       turn a CAUTION into a PROCEED or an ABANDON.

    2. **Influential hubs** (`hub_influential_overlap_count >= 2`): the
       S2 "isInfluential" flag is the API's own judgment of substantive
       dependence.

    3. **Hub references with high overlap** (`hub_overlap_count >= 3`):
       seminal works supporting the mechanism (or its negation).

    4. **Hub citations covering uncovered assumptions**: pick hub_cites
       candidates whose `addresses_assumption_ids_proposed` includes a
       round-1 `key_assumptions` ID that has zero or only weakly-tagged
       evidence in round 1.

    5. **Term-refinement matches** that cover an uncovered assumption.

    Diversity guarantee: try to keep at least one gap_search and one
    hub_refs paper in the final selection when both sources have a
    passing candidate.

    If TEX_SOURCE_ONLY is true: drop candidates without `arxiv_id`.

    Aim to cover **each round-1 `key_assumption` with at least one
    round-2 paper** where possible — `addresses_assumption_ids_proposed`
    is the matching signal. Spreading coverage across assumptions is more
    valuable than piling on the most-cited one.

    ## Deliverable: idea-survey/.expansion_selected.json

    Schema matches Step 2's `selected_evidence_papers` exactly:

    ```json
    [
      {
        "safe_id": "arxiv_2401_99999",
        "title": "...",
        "authors": "...",
        "year": 2024,
        "venue": "...",
        "arxiv_id": "...",
        "abstract": "...",
        "url": "...",
        "evidence_role": "Supporting|Contradicting|Boundary",
        "addresses_assumption_ids": ["A2"],
        "selection_rationale": "Gap-driven (high): originating seed [safe_id1] (Supporting, addresses A2) reported that ABC fails when X→0. This paper's title + abstract describe a stabilization technique for exactly that regime — high-value boundary evidence.",
        "expansion_source": "hub_refs|hub_cites|term_search|gap_search",
        "expansion_signal": {
          "hub_overlap_count": 2,
          "hub_influential_overlap_count": 1,
          "overlapping_seeds": ["safe_id1"],
          "gap_originating_seed": "safe_id1",
          "gap_priority": "high"
        },
        "already_analyzed": false,
        "analysis_path": null
      }
    ]
    ```

    The `evidence_role` field is your **best initial guess** from the
    candidate's signal_strength + abstract — the round-2 deep-read will
    confirm or revise it. Use these defaults:
      - gap_search candidates → "Boundary" if the originating seed was
        Supporting; "Contradicting" if originating seed was Contradicting.
      - hub_refs candidates → "Supporting" (predecessors usually support).
      - hub_cites candidates → "Boundary" (followers tend to refine
        boundaries).
      - term_search candidates → infer from abstract; default "Supporting".

    All selected papers MUST have `already_analyzed == false`. Drop any
    candidate that looks already-known.

    If after all rules zero candidates make the cut, emit `[]` and write
    `idea-survey/.expansion_selected_notes.md`.

    ## Forbidden
    - Do NOT exceed `round2_budget` selections.
    - Do NOT deep-read any paper.
    - Do NOT write the feasibility report.
```

Audit:

```bash
test -e idea-survey/.expansion_selected.json
python3 -m json.tool < idea-survey/.expansion_selected.json > /dev/null
SELECTED=$(python3 -c "import json; print(len(json.load(open('idea-survey/.expansion_selected.json'))))")
echo "Round-2 selected: $SELECTED evidence papers"
```

If `SELECTED == 0`: write `.loop_skipped` with reason `"synthesizer_selected_zero"`, jump to Step 5.

#### 4.6c: Round-2 download + deep analysis (reuses Step 3 / Step 3.5 / Step 4 prompts unchanged)

Same mechanic as the other idea-* skills: rotate round-1 state files out, promote `.expansion_selected.json` into the `.synthesis_selected.json` slot, then re-run Pool Resolution → Step 3 download-preparer → (optional Step 3.5) → Step 4 paper-analyzer with **unchanged prompts**.

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

python3 tools/papers_pool.py resolve \
    --selected-papers idea-survey/.synthesis_selected.json \
    --project-dir . \
    --topic "<USER_DIRECTION>" \
    --output idea-survey/.synthesis_selected_resolved.json
```

Then re-launch Step 3 download-preparer, Step 3.5 (if any paper is `vision_pending`), and Step 4 paper-analyzer subagents with their original prompts.

#### 4.6d: Round-2 paper-card distillation (re-run Step 4.5 logic)

Re-invoke the Step 4.5 enumeration + stale-card calculation + distiller subagent launches. Round-1 cards are mtime-equal to their source and skipped; only round-2 papers get distilled.

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

> Main agent does NOT read deep analyses, assess assumptions, or write report prose. The report-writer subagent does.

#### 5a: Prepare inputs

1. Build the paper-card index for the report-writer:
   ```bash
   ls idea-survey/literature-deep/paper_*/paper_card.json 2>/dev/null \
     | sort \
     > idea-survey/.tmp/paper_card_index.txt
   echo "Report-writer will consume $(wc -l < idea-survey/.tmp/paper_card_index.txt) paper cards."
   ```
   Cards were produced by Step 4.5 (small JSON, ~3–10 KB each).

2. Build a fallback list of `deep_analysis.md` paths for papers whose card failed to distill in Step 4.5 (last-resort on-demand reads, NOT default reading):
   ```bash
   comm -23 \
     <(sort idea-survey/.tmp/all_deep_analyses.txt) \
     <(sed 's|/paper_card.json$|/deep_analysis.md|' idea-survey/.tmp/paper_card_index.txt | sort) \
     > idea-survey/.tmp/cardless_deep_analyses.txt
   ```

3. Note existing report path for guidance preservation: `idea-survey/feasibility-report.md`

4. Prepare key metadata:
   - User input direction
   - Output language
   - Synthesis file path: `idea-survey/feasibility-synthesis.md`
   - `{paper_card_index}`: contents of `idea-survey/.tmp/paper_card_index.txt`
   - `{cardless_deep_analyses}`: contents of `idea-survey/.tmp/cardless_deep_analyses.txt`

#### 5b: Launch report-writer subagent

```yaml
Agent:
  description: "Report writer: feasibility"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are a research report writer. Read the synthesis and the
    paper cards to produce the final feasibility assessment report.

    **Context from main orchestrator**:
    - Research direction: {user_input}
    - Output language: {output_language}
    - Synthesis file: idea-survey/feasibility-synthesis.md
    - User guidance applied: {user_guidance}
    - Loop audit: idea-survey/.loop_audit.json (present iff Step 4.6 ran);
      idea-survey/.loop_skipped (present iff Step 4.6 was skipped).

    **Files you MUST read (in this order)**:
    1. `templates/PAPER_CARD_SCHEMA.md` — schema for the JSON cards
       below. For feasibility work the key fields are
       `quantitative_results` (with their `setting` context),
       `feasibility_signals.demonstrated_to_work_when`,
       `feasibility_signals.demonstrated_to_fail_when`,
       `feasibility_signals.reported_failure_modes`,
       `experimental_setting`, and `limitations_*`.
    2. `idea-survey/feasibility-synthesis.md` — assumptions and
       selected evidence papers.
    3. `idea-survey/.loop_audit.json` if present. Lists round-2 papers
       added by Step 4.6. Round-2 papers' `expansion_source` is
       diagnostic for how to weight them:
         * `gap_search` papers were retrieved specifically to probe a
           failure mode reported by a round-1 paper — these are the
           strongest evidence for whether an assumption holds at the
           boundary.
         * `hub_refs` / `hub_cites` papers are citation-graph hubs and
           should be cross-referenced against the assumption they
           plausibly cover.
       If `.loop_skipped` is present instead, briefly note it in the
       Run Log footer with the recorded reason.
    4. Every paper card in this list:
{paper_card_index}
    5. Upstream landscape: `idea-survey/landscape-report.md`.
    6. Upstream novelty: `idea-survey/novelty-report.md`.
    7. `templates/IDEA_FEASIBILITY_TEMPLATE.md`.
    8. If resuming, `idea-survey/feasibility-report.md` — only to
       preserve the User Guidance Section.

    **Files you MAY read on demand (NOT by default)**:
    - The following papers FAILED card distillation in Step 4.5;
      treat their `deep_analysis.md` as last-resort:
{cardless_deep_analyses}
    - Any other `deep_analysis.md` may be opened ONLY when a
      specific quantitative claim (e.g. "X GPU-hours", "Y% accuracy
      drop") must be reproduced verbatim from the original paper and
      is not already in `paper_card.quantitative_results`. Use
      `ReadFile` with a narrow `line_offset`; never read a full
      `deep_analysis.md` to "be safe".

    **Output**: Write the complete report to `idea-survey/feasibility-report.md`

    **Rules**:
    - Read every paper card in `{paper_card_index}`. Do not skip any.
    - Do NOT read `deep_analysis.md` files by default. Cards exist
      precisely to avoid that. Targeted on-demand reads are allowed
      only as defined above.
    - Do NOT call `ReadMediaFile`. No image analysis.
    - Do NOT run file conversion tools.
    - Follow the template structure exactly.
    - All claims MUST reference a specific paper card. Report links
      pointing to "Deep Analysis" should use the card's
      `provenance.deep_analysis_path`.
    - Preserve the User Guidance Section at the bottom.
    - Write in {output_language}. Keep paper titles, author names,
      venue names, BibTeX, file paths, and JSON keys in English.
    - The synthesis file contains assumptions and selected papers.
      You MUST perform the assumption-by-assumption feasibility
      assessment yourself, grounding every rating in the paper cards.
    - Be honest about gaps. If a card's `quantitative_results` does
      not include the setting the user proposes, say so explicitly
      ("evidence does not transfer") rather than asserting transfer.
      If evidence is absent or the relevant fields are empty/null in
      every card, mark the assumption's Evidence Strength as NONE.
    - **Cross-project relevance**: some paper cards may have been
      distilled by another project that used the shared paper pool.
      Each card's `relevance_at_first_analysis` block records the
      original analysis project's topic, not the current direction.
      Feasibility assessment relies primarily on project-agnostic
      fields (`quantitative_results`, `feasibility_signals`,
      `experimental_setting`, `limitations_*`) which transfer
      cleanly. However, `relevance_at_first_analysis.gaps_left_for_user`
      records gaps relative to the FIRST project's topic and may
      not apply here — re-evaluate gap transfer against the current
      direction when assessing whether evidence transfers.
```

#### 5c: Verify output

- Wait for the report-writer subagent to complete using the polling protocol.
- Verify that `idea-survey/feasibility-report.md` exists and is non-empty.
- If the subagent fails or produces an empty file, retry once with the identical prompt.
- If the retry also fails, log the failure. Do NOT write the report yourself in the main agent.

---

## Key Rules Summary

1. **Zero-interruption execution**: Run from start to finish without asking the user.
2. **Main agent NEVER analyzes papers**: All analysis is delegated to `paper-analyzer` subagents.
3. **Main agent NEVER synthesizes**: Assumption extraction, paper selection, and feasibility assessment are delegated to subagents.
4. **Main agent NEVER downloads**: Source preparation is delegated to `download-preparer` subagent.
5. **Strict polling protocol**: 5min → 3min → 1min loop. No shortcuts.
6. **Concurrency cap**: Maximum 4 concurrent subagents.
7. **Deduplication**: Reuse analyses from `literature-deep/` and upstream reports.
8. **Evidence-based assessment**: Every risk rating must cite specific paper findings.
9. **Honest about gaps**: If evidence is absent or does not transfer to the proposed setting, say so.
10. **Guidance-aware resume**: Automatically read user guidance from the previous report on re-run.
11. **Loop expansion is fixed at one round**: Step 4.6 fires exactly once per run, gated by `LOOP_ENABLED`, `LOOP_MIN_SEEDS`, and the residual budget `DEEP_ANALYZE_MAX * EXPAND_BUDGET_FACTOR - round1_new`. Round-2 expansion uses three signals: citation-graph hubs, precise-term refinement, AND gap-driven queries built from round-1 cards' failure-mode statements (the feasibility-specific signal). The audit sentinel (`.loop_audit.json` or `.loop_skipped`) records the outcome for the report-writer.
