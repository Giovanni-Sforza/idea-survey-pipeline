---
name: research-proposal
description: Generate a LaTeX research proposal (dissertation proposal) from an existing idea-survey literature directory. Consumes the outputs of idea-landscape, idea-novelty, and idea-feasibility to produce a publication-ready proposal with embedded figures, equations, and a verified bibliography. Use when the user says "write research proposal", "开题报告", "dissertation proposal", "generate proposal from survey", or wants to turn a completed literature survey into a structured LaTeX document.
argument-hint: "title / topic — literature-dir: path — language: zh|en — author: Name"
---

# Research Proposal Generator

Research proposal topic: $ARGUMENTS

This skill is **Stage 4** of the idea-survey pipeline. It generates an **academic research proposal** (10–20 pages, dissertation / project proposal format) from the completed outputs of Stages 1–3.

**It reads the three upstream reports as ground truth and cross-checks them for consistency before writing any prose.** All reading, extraction, and drafting happens inside subagents; the main agent only orchestrates and audits.

**Inputs consumed:**
- `idea-survey/landscape-report.md` → Introduction, gap statement, technical routes
- `idea-survey/novelty-report.md` → Research objectives, claims, competitive positioning
- `idea-survey/feasibility-report.md` → Feasibility analysis, risk assessment, MVP
- `idea-survey/literature-deep/paper_*/deep_analysis.md` → Related Work synthesis, figures, equations
- `idea-survey/literature-deep/paper_*/figures/*.png` → Embedded figures

**Output**: A complete LaTeX project under `proposal/`, ready to compile with `xelatex` + `biber`.

---

## Constants

- **LITERATURE_DIR = `idea-survey/`** — Root directory containing landscape/novelty/feasibility reports and `literature-deep/`. Override via `— literature-dir:`.
- **OUTPUT_DIR = `proposal/`** — Where the LaTeX project is written.
- **FIGURES_DIR = `proposal/figures/`** — Copied and renamed figures.
- **BODY_DIR = `proposal/body/`** — Per-section `.tex` files written by the drafting subagent. `main.tex` includes them via `\input{body/...}`.
- **OUTPUT_LANGUAGE = "auto"** — `zh` or `en`. Auto-detection follows [shared-references/output-language.md](../shared-references/output-language.md). Override via `— language:`.
- **AUTHOR = ""** — Proposal author. Parse from `$ARGUMENTS` (`— author: "Name"`).
- **TITLE = ""** — Proposal title. Parse from `$ARGUMENTS` (free text before any `—`).
- **TEMPLATE = `templates/RESEARCH_PROPOSAL_TEMPLATE.tex`** — Base LaTeX template (`<<PLACEHOLDER>>` markers, substituted via `sed`).
- **MAX_FIGURES_PER_PAPER = 3** — Per-paper figure cap.
- **MAX_TOTAL_FIGURES = 10** — Global cap across all papers.
- **SUBAGENT_TIMEOUT = 3600** — Per-subagent timeout in seconds (matches upstream idea-* skills).
- **SUPPORTING_LIT_HIGH = 12** — HIGH-priority supporting citations (named SOTA model, specific performance number, key benchmark). Must be successfully fetched OR explicitly marked `\needfix{}` — never silently dropped.
- **SUPPORTING_LIT_MEDIUM = 8** — MEDIUM-priority citations ("widely used", "standard"). Best-effort fetch; fallback to `\needfix{}` is acceptable.
- **SUPPORTING_LIT_MAX = 20** — Hard cap = HIGH + MEDIUM. Additional claims become `\needfix{}` placeholders.
- **COMPILE = true** — Attempt xelatex/biber after generation. Override via `— compile: false`.

> 💡 Overrides:
> - `/skill:research-proposal "Efficient transformers for long docs" — language: zh`
> - `/skill:research-proposal "topic" — literature-dir: my-survey/ — output: my-proposal/`
> - `/skill:research-proposal "topic" — author: "Zhang San" — compile: false`

---

## Required Protocols

Every subagent prompt **MUST** surface these shared references. The main agent is responsible for inlining the relevant pointers when launching subagents.

1. **[shared-references/citation-discipline.md](../shared-references/citation-discipline.md)** — citation verification. Priority: DBLP `.bib` → DOI content negotiation → arXiv BibTeX. **Never write a BibTeX entry from memory.**
2. **[shared-references/writing-principles.md](../shared-references/writing-principles.md)** — abstract / introduction / related-work / figure-caption guidance (Karpathy / Lipton / Gopen-Swan). **Required reading for the drafting subagent before it touches Abstract or Introduction.**
3. **[shared-references/output-language.md](../shared-references/output-language.md)** — language detection and what-not-to-localize.

---

## 🚧 Main Agent Boundary Protocol — ORCHESTRATE ONLY 🚧

> **This section exists because earlier runs of this skill exhausted the main agent's context by directly reading paper files, then required a `/compact` that broke cross-step consistency.** It is the single most important rule in this file.

### What the main agent MAY do

1. Run **shell commands** (`mkdir`, `cp`, `find`, `ls`, `wc`, `grep`, `test`, `sed`).
2. Run **Python tool scripts** in `tools/` (`bibtex_fetch.py`, `arxiv_fetch.py`, …).
3. Launch **subagents** via the `Agent` tool.
4. Apply the **polling protocol** (Phase 1–4) and collect subagent outputs.
5. **Audit** subagent outputs at the file-system level only:
   - File exists, non-empty: `test -s path`
   - JSON parses: `python3 -m json.tool < path > /dev/null`
   - Expected files present: `ls`, `wc -l`
   - Citation integrity: `bibtex_fetch.py verify-tex`
   - Placeholder residue: `grep "<<" main.tex`
6. Surface failures and the precise next step to the user.

### What the main agent MUST NOT do — under any circumstance

The main agent is **STRICTLY FORBIDDEN** from any of the following, no matter how "quick", "small", or "just-to-check" the temptation looks:

- ❌ **Reading** `landscape-report.md`, `novelty-report.md`, or `feasibility-report.md`.
- ❌ **Reading** any file under `literature-deep/paper_*/` (`deep_analysis.md`, `figure_manifest.json`, figures, manifests).
- ❌ **Reading** any PDF in `supporting_papers/`.
- ❌ **Reading** any `body/*.tex` file produced by the drafting subagent for the purpose of summarizing, judging, or rewriting prose. (Mechanical checks like `grep` or `wc` are fine.)
- ❌ **Drafting** any prose, section, abstract, or figure caption — even one sentence.
- ❌ **Writing** any BibTeX entry by hand or from memory.
- ❌ **Inventing** any author surname, year, venue, or numeric result.
- ❌ **Computing** figure relevance scores or claim-vs-evidence consistency in its own head.
- ❌ **Identifying** supporting literature claims by inspection (delegate to Step 4a).
- ❌ **"Falling back"** to direct work because a subagent is "slow", "timed out", or "the user is waiting". Slow is fine; wrong is not. Retry per the polling protocol.

### The "I'll just peek" rule

If the main agent finds itself thinking "I'll just open this file briefly to check X" — **STOP**. There is always a delegation alternative:

| Tempted to read | Correct action |
|---|---|
| "Let me check what claims the novelty report makes." | Already extracted by Subagent A → read `upstream_metadata.json` (small structured JSON, OK to read). |
| "Let me see which figures this paper has." | Already indexed by Subagent B → read `paper_index.json`. |
| "Let me verify this paragraph looks right." | Launch a verify subagent, or run `bibtex_fetch.py verify-tex`. |
| "Let me just summarize this for the next subagent." | Pass the file path; let the next subagent read it. |
| "Let me see what year BERT was published." | Read `bib_index.json[devlin_2019_bert].year`. |

**Bytes the main agent reads per run, target: < 50 KB total.** Anything above means delegation discipline broke.

### Consequence of breaking these rules

The run is compromised, exactly as upstream idea-* skills state. The correct action is to abandon the partial output, restart the violated step with a properly-scoped subagent, and log the violation so it doesn't repeat.

---

## Anti-Fabrication Protocol — ABSOLUTE RULES

The most common failure mode for previous runs was **plausible-looking but wrong citation details**: a real BibTeX key but the in-prose "Vaswani et al. (2017)" had the wrong year/author/venue. These rules close that gap.

### RULE A1: All BibTeX comes from `tools/bibtex_fetch.py`

Main agent and any subagent are forbidden from writing BibTeX entries by hand or from memory. All entries come from `tools/bibtex_fetch.py fetch`, which fetches from DBLP / DOI / arXiv and validates against caller-supplied expected metadata.

### RULE A2: Every author / year / venue in prose comes from `bib_index.json`

Step 4c runs `bibtex_fetch.py build-index` to produce `proposal/bib_index.json`, mapping each cite key to ground-truth `{year, first_author_surname, title, venue}`. The drafting subagent receives `bib_index.json` inline and **MUST** look up every author surname, year, and venue from it instead of from memory.

### RULE A3: Verification before "done"

Step 8 runs `bibtex_fetch.py verify-tex`. Non-zero exit means the run is NOT complete; the violation list is surfaced to the user.

### RULE A4: When in doubt, `\needfix{}`

Unknown citation → `\needfix{Need citation for: <exact claim>}` (renders bright red). Never guess.

### RULE A5: Subagent does prose; main agent does shell

See **Main Agent Boundary Protocol** above. This rule is restated here for emphasis: **all prose generation, all paper reading, all claim extraction happens inside subagents.**

---

## Common Subagent Patterns (referenced by every Step)

Every subagent launch in this skill follows the same three-step pattern. Each Step below says "launch Subagent X" — that means apply these three steps verbatim.

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

`subagent_type` is always `paper-editor` (matches the working pattern in `idea-landscape` Step 6). Task-specific behavior comes from the prompt, not from a new subagent file.

### Pattern 2: Polling (identical to upstream idea-* skills)

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

### Pattern 3: Audit subagent output

For every subagent, the main agent verifies output at the file-system level only:

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

## Workflow

### Step 0: Directory Setup (main agent, shell only)

1. Parse `$ARGUMENTS` into `{title, author, literature_dir, output_dir, language, compile}`.
   - Title = free text before the first `—`.
   - Each `— key: value` becomes a named override.
2. Resolve `output_language`:
   - If `— language:` was passed, use it.
   - Otherwise follow `shared-references/output-language.md`.
3. Create directories:
   ```bash
   mkdir -p {OUTPUT_DIR}/{figures,body,supporting_papers}
   ```
4. Verify `{LITERATURE_DIR}/` exists. If not, fail fast:
   `"Literature directory {LITERATURE_DIR} not found. Run /skill:idea-landscape first."`

---

### Step 1: Extract Upstream Metadata & Cross-Check (Subagent A)

> Main agent does NOT read `landscape-report.md` / `novelty-report.md` / `feasibility-report.md`. Subagent A does.

**Inputs to subagent A**: the three report paths (just paths — no contents).
**Expected outputs**:
- `{OUTPUT_DIR}/upstream_metadata.json`
- `{OUTPUT_DIR}/CONSISTENCY_NOTES.md`

#### Launch Subagent A (Pattern 1)

```yaml
Agent:
  description: "Upstream report extractor + consistency audit"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are extracting structured metadata from three upstream literature-survey
    reports and performing a cross-report consistency audit. You write structured
    outputs only — no prose, no LaTeX.

    ## File handling rules
    - Do NOT call ReadMediaFile. No images here.
    - Do NOT run any image-conversion tools.
    - Read ONLY the three files listed below. Do not browse `literature-deep/`.

    ## Output language
    Status messages / commentary in CONSISTENCY_NOTES.md: {output_language}.
    JSON keys: always English (machine-parsed).

    ## Inputs (read these in full)
    - {LITERATURE_DIR}/landscape-report.md  (may not exist — proceed gracefully)
    - {LITERATURE_DIR}/novelty-report.md     (may not exist)
    - {LITERATURE_DIR}/feasibility-report.md (may not exist)
    - Templates used by the upstream skills (for field reference):
        templates/IDEA_LANDSCAPE_TEMPLATE.md
        templates/IDEA_NOVELTY_TEMPLATE.md
        templates/IDEA_FEASIBILITY_TEMPLATE.md

    ## Deliverable 1: {OUTPUT_DIR}/upstream_metadata.json

    Exact schema:
    ```json
    {
      "landscape": {
        "gap_statement": "<single sentence from Gap Map section, or null>",
        "routes": [
          {"name": "<route name>", "description": "<one-line summary>"}
        ],
        "search_hypotheses": ["<H1 question>", "<H2 question>", ...],
        "user_guidance": "<contents of ARIS_GUIDANCE block, or empty string>"
      },
      "novelty": {
        "claims": [
          {"id": "C1", "statement": "<claim>", "novelty_level": "HIGH|MEDIUM|LOW",
           "closest_prior": [{"title": "...", "deep_analysis_path": "..."}]}
        ]
      },
      "feasibility": {
        "assumptions": [
          {"id": "A1", "statement": "<assumption>", "if_false": "<consequence>",
           "prior_risk": "HIGH|MEDIUM|LOW", "related_claim": "C1",
           "evidence_strength": "STRONG|MIXED|WEAK|NONE",
           "supporting_evidence": ["<paper title>: <finding>"],
           "contradicting_evidence": ["..."],
           "updated_risk": "HIGH|MEDIUM|LOW"}
        ],
        "mvp_suggestion": "<text of MVP plan>"
      }
    }
    ```

    For any missing report, set the corresponding top-level field to null and
    note it in CONSISTENCY_NOTES.md.

    ## Deliverable 2: {OUTPUT_DIR}/CONSISTENCY_NOTES.md

    Perform a four-check audit and write findings in {output_language}:

    1. **Gap ↔ Claims alignment** — Does novelty Claim 1 address the exact gap
       stated in landscape's Gap Map? If a claim drifts to a different problem,
       describe the drift.
    2. **Claims ↔ Assumptions alignment** — Every claim should have at least
       one supporting/risk-mitigating assumption. Flag orphans on both sides.
    3. **Route ↔ Prior consistency** — Does novelty's "Closest Prior Work" for
       each claim match papers discussed under the corresponding landscape route?
    4. **Risk-novelty tension** — HIGH-risk assumption + "obviously novel" claim
       is a red flag.

    Format:
    ```markdown
    # Consistency Notes
    Generated: <ISO timestamp>

    ## Check 1: Gap ↔ Claims
    - ✅ Aligned, OR
    - ⚠️ Tension: <description>

    ## Check 2: Claims ↔ Assumptions
    ...

    ## Check 3: Route ↔ Prior
    ...

    ## Check 4: Risk ↔ Novelty
    ...

    ## Tensions the proposal must acknowledge
    - <bulleted list of unresolved tensions; the drafting subagent will read this>
    ```

    If no tensions exist, the file should still be created with all four
    sections marked "✅ Aligned" and an empty "Tensions" list.

    ## Forbidden
    - Do NOT write any prose for the proposal body.
    - Do NOT invent metadata not present in the source reports.
    - Do NOT proceed past the four checks; this is metadata extraction only.
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

Audit:
```bash
test -s {OUTPUT_DIR}/upstream_metadata.json || exit 1
test -s {OUTPUT_DIR}/CONSISTENCY_NOTES.md   || exit 1
python3 -m json.tool < {OUTPUT_DIR}/upstream_metadata.json > /dev/null || exit 1
```

---

### Step 2: Index Literature Assets (Subagent B)

> Main agent does NOT read any `deep_analysis.md` or `figure_manifest.json`. Subagent B does.

**Inputs to subagent B**: list of paper directory paths under `literature-deep/`.
**Expected output**: `{OUTPUT_DIR}/paper_index.json`.

#### Main agent prepares the file list (shell only)

```bash
find {LITERATURE_DIR}/literature-deep/ -maxdepth 1 -mindepth 1 -type d > {OUTPUT_DIR}/.paper_dirs.txt
PAPER_COUNT=$(wc -l < {OUTPUT_DIR}/.paper_dirs.txt)
test "$PAPER_COUNT" -gt 0 || { echo "No deep analyses found in {LITERATURE_DIR}/literature-deep/"; exit 1; }
```

#### Launch Subagent B (Pattern 1)

```yaml
Agent:
  description: "Literature asset indexer"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You build a master index of all per-paper assets from the deep-analysis
    workspace. You write structured JSON only — no prose, no LaTeX.

    ## File handling rules
    - Do NOT call ReadMediaFile. You read text files only.
    - Do NOT run image-conversion tools.
    - Read `deep_analysis.md` and `figure_manifest.json` per paper directory.

    ## Output language
    All output is JSON; keys and string values are English.

    ## Inputs
    Paper directories to index (one per line):
    {paper_dirs_list_content}

    For each directory, the expected files / subdirs are:
    - {dir}/deep_analysis.md         (always present)
    - {dir}/figure_manifest.json     (always present)
    - {dir}/figures/*.png            (zero or more)
    - {dir}/<arxiv_id>_src/          (ORIGINAL arXiv TeX source; usually present
                                       when the paper came from arXiv. Contains
                                       the authors' raw .tex files with exact
                                       numerical values.)

    The deep_analysis.md follows templates/PAPER_DEEP_ANALYSIS_TEMPLATE.md.

    ## Per-paper extraction

    For each paper directory:

    1. **Read metadata** from the "Paper Information" table in deep_analysis.md:
       `title`, `authors`, `year`, `venue`, `arxiv_id`, `doi` (if present).
       Also extract `first_author_surname` (last token of the first author name,
       or the part before the comma if "Last, First" format).

    1b. **Locate the TeX source directory.** Use the shell:
       ```bash
       ls -d {dir}/*_src/ 2>/dev/null | head -1
       ```
       If a directory matches, record its absolute path as `tex_source_dir`.
       Otherwise set `tex_source_dir` to null. This path is consumed by the
       drafting / rigor subagents to verify specific numerical claims against
       the authors' original LaTeX — the authoritative source for any number
       that appears in prose.

    2. **List figures** from `figures/*.png` + `figure_manifest.json`.

    3. **Score each figure** using this EXACT formula. Do not improvise.
       For each figure, count:
       - `referenced_in_key_takeaways` (1 if figure name/number appears in any
         "Key takeaways" bullet of deep_analysis.md, else 0)
       - `caption_keyword` (1 if the figure's caption matches any of:
         architecture | overview | framework | pipeline | system; else 0)
       - `referenced_in_why_it_matters` (1 if figure appears in any "Why it
         matters" paragraph, else 0)
       - `referenced_in_text` (1 if figure name appears anywhere else in
         deep_analysis.md, else 0)

       Then:
       ```
       score = 2.0*referenced_in_key_takeaways
             + 1.5*caption_keyword
             + 1.0*referenced_in_why_it_matters
             + 0.5*referenced_in_text
       ```

       Tie-break: lower figure number wins.

       Keep at most {MAX_FIGURES_PER_PAPER} per paper, sorted by score descending.

       Each selected figure's `dest` should follow the rename:
         `figures/paper{PAPER_INDEX}_{ORIGINAL_BASENAME}.png`
       where PAPER_INDEX is this paper's 1-based index in the output list.

    4. **Pick up to 5 important equations** from the "Equation-by-Equation
       Analysis" section. Importance heuristic: equations whose explanation
       paragraph is longer than 100 characters and mentions a "key", "main",
       "core", or "central" property of the method.

    ## Deliverable: {OUTPUT_DIR}/paper_index.json

    Exact schema:
    ```json
    {
      "papers": [
        {
          "index": 1,
          "safe_id": "<dir name without leading 'paper_'>",
          "title": "...",
          "authors": "...",
          "first_author_surname": "...",
          "year": 2017,
          "venue": "...",
          "arxiv_id": "1706.03762",
          "doi": null,
          "deep_analysis_path": "{LITERATURE_DIR}/literature-deep/paper_xxx/deep_analysis.md",
          "tex_source_dir": "{LITERATURE_DIR}/literature-deep/paper_xxx/1706.03762_src/",
          "source_type": "deep",
          "selected_figures": [
            {
              "orig": "figures/fig1.png",
              "dest": "figures/paper1_fig1.png",
              "caption": "<from manifest>",
              "score": 3.5
            }
          ],
          "selected_equations": [
            "\\text{Attention}(Q,K,V) = \\softmax(QK^T/\\sqrt{d})V"
          ]
        }
      ]
    }
    ```

    `source_type` is always `"deep"` for entries produced by this subagent.
    (Supporting literature added later in Step 4a gets `source_type: "supporting"`.)

    ## Global figure cap
    Do NOT apply the MAX_TOTAL_FIGURES = {MAX_TOTAL_FIGURES} cap yourself.
    Leave that to the main agent post-processing (it needs the full ranked
    list to drop low-score figures globally).

    ## Forbidden
    - Do NOT call ReadMediaFile.
    - Do NOT invent metadata not present in the source files.
    - Do NOT write prose, captions, or analysis paragraphs.
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

Audit:
```bash
test -s {OUTPUT_DIR}/paper_index.json || exit 1
python3 -m json.tool < {OUTPUT_DIR}/paper_index.json > /dev/null || exit 1
PAPER_COUNT_OUT=$(python3 -c "import json; print(len(json.load(open('{OUTPUT_DIR}/paper_index.json'))['papers']))")
test "$PAPER_COUNT_OUT" -gt 0 || exit 1
```

#### Main agent post-processing: apply global figure cap

```bash
python3 - <<'PY'
import json
from pathlib import Path
idx = json.loads(Path("{OUTPUT_DIR}/paper_index.json").read_text())

# Flatten figures with back-reference, rank globally, keep top MAX_TOTAL_FIGURES
all_figs = []
for p in idx["papers"]:
    for f in p["selected_figures"]:
        all_figs.append((f["score"], p["index"], f))
all_figs.sort(key=lambda t: (-t[0], t[1]))
keep = {(t[1], t[2]["orig"]) for t in all_figs[:{MAX_TOTAL_FIGURES}]}

for p in idx["papers"]:
    p["selected_figures"] = [f for f in p["selected_figures"]
                             if (p["index"], f["orig"]) in keep]

Path("{OUTPUT_DIR}/paper_index.json").write_text(
    json.dumps(idx, ensure_ascii=False, indent=2))
PY
```

---

### Step 3: Copy Figures (main agent, shell only)

Read `paper_index.json` (small structured file — OK for main agent), copy each `selected_figures[*].orig` to `selected_figures[*].dest`:

```bash
python3 - <<'PY'
import json, shutil
from pathlib import Path
idx = json.loads(Path("{OUTPUT_DIR}/paper_index.json").read_text())
for p in idx["papers"]:
    src_root = Path(p["deep_analysis_path"]).parent
    for f in p["selected_figures"]:
        src = src_root / f["orig"]
        dst = Path("{OUTPUT_DIR}") / f["dest"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
PY
```

---

### Step 4a: Identify Supporting Literature (Subagent C)

> Main agent does NOT re-read the three reports here. Subagent C uses the
> already-extracted `upstream_metadata.json` (small JSON) plus the reports
> themselves for context.

**Inputs**: `upstream_metadata.json`, paths of three reports.
**Expected output**: `{OUTPUT_DIR}/supporting_queue.json`.

#### Launch Subagent C (Pattern 1)

```yaml
Agent:
  description: "Supporting literature extractor"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You scan the three upstream literature-survey reports for factual claims
    that need external citations beyond what is already in `paper_index.json`.
    Output is a queue file consumed by the next BibTeX-fetching step.

    ## File handling rules
    - Do NOT call ReadMediaFile.
    - Do NOT run image tools.
    - Read the three report files + the two JSON files listed below.

    ## Inputs
    - {OUTPUT_DIR}/upstream_metadata.json        (already-extracted structure)
    - {OUTPUT_DIR}/paper_index.json              (papers already in the deep index)
    - {LITERATURE_DIR}/landscape-report.md
    - {LITERATURE_DIR}/novelty-report.md
    - {LITERATURE_DIR}/feasibility-report.md

    ## Required reading
    - shared-references/citation-discipline.md  (priority ordering for sources)

    ## What counts as a "supporting literature" claim

    A factual statement that:
    (a) Names a specific model / architecture / method (BERT, GPT-4, ResNet, LoRA, ...)
    (b) Cites a specific number (94.5% on GLUE, BLEU 41.2, 175B parameters, ...)
    (c) Makes a technical assertion about a known property
        (attention scales O(n²), Transformers need positional encoding, ...)
    (d) Uses "widely used", "standard", "state-of-the-art", "common"

    AND for which there is no matching paper in paper_index.json.

    ## Priority classification

    Classify each claim as HIGH or MEDIUM:

    - **HIGH**: claim (a) — named model, OR claim (b) — specific number.
      These MUST be cited or marked \needfix{} in the proposal. Cap = {SUPPORTING_LIT_HIGH}.

    - **MEDIUM**: claim (c) or (d) — technical fact or "widely used" claim.
      Nice-to-have citations; falling back to \needfix{} is acceptable. Cap = {SUPPORTING_LIT_MEDIUM}.

    If you find more than the cap allows, keep the ones most central to the
    proposal's argument. Drop or down-prioritize peripheral claims.

    ## Expected metadata per claim

    For each claim, you must propose:
    - `expected_year` (integer, your best inference from context)
    - `expected_first_author` (surname only, if known from context)
    - `expected_title_tokens` (3–5 distinctive title words for matching)
    - `search_query` (a DBLP-friendly query: title + first author)
    - `arxiv_id` (if you happen to know it; null otherwise — do NOT guess)
    - `doi`       (null unless explicitly mentioned in a report)

    If you cannot confidently propose expected_year or expected_first_author
    for a claim, set those fields to null. The BibTeX-fetching step will then
    fall back to a fuzzier search and may produce a \needfix{}.

    ## Deliverable: {OUTPUT_DIR}/supporting_queue.json

    Exact schema:
    ```json
    {
      "queue": [
        {
          "claim_text": "<verbatim claim from the report>",
          "claim_source": "landscape|novelty|feasibility",
          "priority": "HIGH|MEDIUM",
          "search_query": "Attention Is All You Need Vaswani",
          "arxiv_id": "1706.03762",
          "doi": null,
          "expected_year": 2017,
          "expected_first_author": "Vaswani",
          "expected_title_tokens": ["Attention", "All", "Need"]
        }
      ],
      "counts": {"high": <int>, "medium": <int>, "total": <int>}
    }
    ```

    The queue MUST satisfy:
      counts.high   <= {SUPPORTING_LIT_HIGH}
      counts.medium <= {SUPPORTING_LIT_MEDIUM}
      counts.total  <= {SUPPORTING_LIT_MAX}

    ## Forbidden
    - Do NOT write any BibTeX. The next step fetches BibTeX with proper validation.
    - Do NOT guess an arxiv_id. Setting it to null is the correct fallback.
    - Do NOT include papers already present in paper_index.json (deduplicate first).
    - Do NOT write prose for the proposal body.
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

```bash
test -s {OUTPUT_DIR}/supporting_queue.json || exit 1
python3 -m json.tool < {OUTPUT_DIR}/supporting_queue.json > /dev/null || exit 1
```

---

### Step 4b: Fetch BibTeX for Every Paper (main agent, shell loop)

For every paper in `paper_index.json` AND every claim in `supporting_queue.json`, run `bibtex_fetch.py fetch` with the expected metadata. No reading required — the JSONs are the contract.

```bash
python3 - <<'PY'
import json, subprocess, sys
from pathlib import Path

OUTPUT_DIR = "{OUTPUT_DIR}"
bib_path = f"{OUTPUT_DIR}/references.bib"
Path(bib_path).touch()

# Combine deep-index papers + supporting queue into a unified fetch list
fetch_list = []
for p in json.loads(Path(f"{OUTPUT_DIR}/paper_index.json").read_text())["papers"]:
    fetch_list.append({
        "arxiv_id": p.get("arxiv_id"),
        "doi": p.get("doi"),
        "title": p.get("title"),
        "expected_year": p.get("year"),
        "expected_first_author": p.get("first_author_surname"),
        "expected_title_tokens": (p.get("title") or "").split()[:5],
        "priority": "DEEP",
    })

for q in json.loads(Path(f"{OUTPUT_DIR}/supporting_queue.json").read_text())["queue"]:
    fetch_list.append({
        "arxiv_id": q.get("arxiv_id"),
        "doi": q.get("doi"),
        "title": q.get("search_query"),
        "expected_year": q.get("expected_year"),
        "expected_first_author": q.get("expected_first_author"),
        "expected_title_tokens": q.get("expected_title_tokens", []),
        "priority": q.get("priority", "MEDIUM"),
    })

failures = []
for item in fetch_list:
    cmd = ["python3", "tools/bibtex_fetch.py", "fetch",
           "--strategy", "auto", "--append-to", bib_path]
    if item["arxiv_id"]:           cmd += ["--arxiv-id", item["arxiv_id"]]
    if item["doi"]:                cmd += ["--doi", item["doi"]]
    if item["title"]:              cmd += ["--title", item["title"]]
    if item["expected_year"]:      cmd += ["--expected-year", str(item["expected_year"])]
    if item["expected_first_author"]:
        cmd += ["--expected-first-author", item["expected_first_author"]]
    if item["expected_title_tokens"]:
        cmd += ["--expected-title-tokens", *item["expected_title_tokens"]]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        failures.append({"item": item, "stderr": r.stderr, "stdout": r.stdout})

# Surface failures for the user; HIGH-priority failures are blocking.
high_fail = [f for f in failures if f["item"]["priority"] in ("DEEP", "HIGH")]
if high_fail:
    print("HIGH-priority BibTeX fetches FAILED — review these manually:")
    for f in high_fail:
        print(json.dumps(f, indent=2, ensure_ascii=False))
    Path(f"{OUTPUT_DIR}/bibtex_fetch_failures.json").write_text(
        json.dumps(failures, indent=2, ensure_ascii=False))
PY
```

If `bibtex_fetch_failures.json` exists and contains HIGH-priority entries: surface to user and ask whether to (a) retry with corrected metadata, (b) accept `\needfix{}` placeholders, or (c) abort.

---

### Step 4c: Build `bib_index.json` (main agent, one command)

```bash
python3 tools/bibtex_fetch.py build-index \
    --bib {OUTPUT_DIR}/references.bib \
    --out {OUTPUT_DIR}/bib_index.json
test -s {OUTPUT_DIR}/bib_index.json
```

---

### Step 4d: Dedup `references.bib` (main agent, one command)

Prefer `@inproceedings` / `@article` over `@misc` / `@unpublished` when the same key appears twice:

```bash
python3 - <<'PY'
import re
from pathlib import Path
bib = Path("{OUTPUT_DIR}/references.bib").read_text(encoding="utf-8")
entries = re.findall(r"(@\w+\{[^@]+?\n\})", bib, re.DOTALL)
by_key, rank = {}, {"inproceedings": 0, "article": 0, "book": 0, "misc": 1, "unpublished": 2}
for e in entries:
    typ = re.match(r"@(\w+)", e).group(1).lower()
    key = re.search(r"@\w+\{([^,]+),", e).group(1)
    if key not in by_key or rank.get(typ, 3) < rank.get(re.match(r"@(\w+)", by_key[key]).group(1).lower(), 3):
        by_key[key] = e
Path("{OUTPUT_DIR}/references.bib").write_text("\n".join(by_key.values()) + "\n", encoding="utf-8")
PY

# Rebuild the index after dedup
python3 tools/bibtex_fetch.py build-index \
    --bib {OUTPUT_DIR}/references.bib \
    --out {OUTPUT_DIR}/bib_index.json
```

---

### Step 5: Draft Proposal Body (Subagent D — the big one)

> Main agent does NOT draft any prose. Subagent D produces 9 body files.

#### Main agent prepares the inline context (small JSONs only)

```bash
UPSTREAM_JSON=$(cat {OUTPUT_DIR}/upstream_metadata.json)
BIB_INDEX_JSON=$(cat {OUTPUT_DIR}/bib_index.json)
PAPER_INDEX_JSON=$(cat {OUTPUT_DIR}/paper_index.json)
CONSISTENCY_NOTES=$(cat {OUTPUT_DIR}/CONSISTENCY_NOTES.md)
DEEP_ANALYSIS_PATHS=$(python3 -c "import json; print('\n'.join(p['deep_analysis_path'] for p in json.load(open('{OUTPUT_DIR}/paper_index.json'))['papers']))")
```

These are small structured files; reading them does NOT violate the boundary protocol.

#### Launch Subagent D (Pattern 1)

```yaml
Agent:
  description: "Draft research proposal body"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You are an academic proposal drafter. Write LaTeX body content for a
    dissertation-style research proposal (10–20 pages, 8 sections + abstract).

    ## File handling rules
    - Do NOT run any image-conversion tools. All figures are already PNG.
    - Do NOT call ReadMediaFile. You write prose, not visual analysis.
    - Do NOT fetch BibTeX or write BibTeX from memory. All entries are already
      in {OUTPUT_DIR}/references.bib and indexed in bib_index.json (inlined below).
    - You MAY read the deep_analysis.md files listed under "Deep analyses to consult".

    ## Output language
    Output language: {output_language}
    Write all narrative prose in this language. Keep the following in English
    regardless of language setting: paper titles, author names, venue names,
    BibTeX keys, file paths, math, LaTeX commands.

    ## Required reading BEFORE drafting
    1. shared-references/citation-discipline.md
    2. shared-references/writing-principles.md
       Apply to Abstract and Introduction specifically:
       - five-sentence abstract formula
       - 2–4 concrete contribution bullets in intro
       - NO generic "Large language models have achieved remarkable success" openings
       - Related Work organized by method family, NOT paper-by-paper
       - Self-contained figure captions
    3. shared-references/output-language.md
    4. CONSISTENCY_NOTES (inlined below) — acknowledge or resolve every tension;
       never silently paper over.

    ## Ground-truth metadata you MUST use (anti-fabrication)

    The bibliography is built and the index below is authoritative.
    You MUST look up every author surname, year, and venue from `bib_index.json`
    instead of writing them from memory.

    bib_index.json content:
    {BIB_INDEX_JSON}

    Forbidden patterns:
    - "Vaswani et al. (2017)" written from memory.
    - "introduced at NeurIPS 2017" written from memory.
    - "Devlin and colleagues showed in 2019" written from memory.
    Required pattern:
    - For every author/year/venue mention, identify the cite key, look up the
      entry in bib_index.json, and copy the exact `first_author_surname`,
      `year`, `venue` strings.

    If a claim has no matching entry in bib_index.json:
    - DO NOT invent a citation.
    - DO NOT invent author/year/venue.
    - Write \needfix{Need citation for: <exact claim>} instead.

    ## Numerical-rigor rules (anti-fabrication for numbers, not just citations)

    Citation keys + years are gate-checked, but specific numbers in prose
    (AUC 0.500–0.501, FID 9.96, "from 0.04 to 0.87", "25% of the energy",
    "49,152 dimensions", "two orders of magnitude", "achieves 86.4% on MMLU")
    are the most fabrication-prone vector that survives the cite-key check.

    ### Number-provenance ladder (search in this order)

    For EVERY specific numerical value you write in narrative prose, locate
    it via this priority chain BEFORE typing it:

      1. **Primary — the ORIGINAL TeX source of the cited paper.** The
         upstream pipeline downloaded the authors' raw arXiv source into
         `paper_index[k].tex_source_dir` (when available). This is the
         authoritative ground truth — exactly what the authors wrote.
         Use the Grep tool:
            Grep("9\\.96",   path=tex_source_dir, glob="**/*.tex")
            Grep("0\\.500",  path=tex_source_dir, glob="**/*.tex")
         Look for both literal forms (`9.96`) and LaTeX-wrapped forms
         (`$9.96$`, `\num{9.96}`, `9{.}96` etc. — be flexible with the regex).
         If the number is in a table, you'll see it inside `\\begin{tabular}`
         or `\\begin{table}` blocks.

      2. **Secondary — the deep_analysis.md summary.** Used only as a
         fallback if `tex_source_dir` is null (the paper was indexed from PDF,
         not arXiv source) OR if grep on the TeX returned no match (the
         number might be in a figure caption the deep_analysis copied).
         Grep("9.96", path=deep_analysis_path)

      3. **Tertiary — upstream_metadata.json or CONSISTENCY_NOTES.**
         Numbers may originate in the survey reports (e.g. gap-statement
         deltas computed during landscape).

    A number NOT found in any of (1), (2), (3) is unverified. Do NOT type
    it. Choose ONE of:

      a. REWRITE qualitatively:
           "discriminator AUCs dropped from 0.98 to 0.52"
         → "discriminator AUCs dropped substantially"
           "FID of 9.96 on 512×512"
         → "competitive FID at high resolution"

      b. ATTRIBUTE to your own preliminary estimate:
           "we estimate ≥30% reduction (based on the AMPT/UrQMD gap reported
            in landscape-report §...)"

      c. MARK with \needfix (qualitative form — see next section).

    ### Why the TeX source matters more than deep_analysis.md

    `deep_analysis.md` is a subagent-written summary of the paper. Subagents
    sometimes round, paraphrase, or simply miss numbers — especially when
    they live inside `\\begin{tabular}` blocks. The original TeX is what the
    authors signed off on. If the number is in the TeX source but not in the
    deep_analysis, the number is real; the analysis just missed it. If the
    number is in the deep_analysis but not in the TeX source, treat the
    deep_analysis as suspect for that number and seek confirmation.

    ### Self-derived target numbers

    Your own success criteria (e.g. "≥30% Wasserstein reduction") MUST be
    motivated in-line: either by a physics anchor or by referring to a
    precedent in the cited literature. Bare target numbers without
    justification are equivalent to fabrication from a reviewer's standpoint.

    ## \needfix{} content rules

    \needfix{} must contain ONLY a qualitative description of what needs
    citation. Numbers inside \needfix{} look like "I half-remembered this
    detail" and are nearly as bad as fabricating a full citation.

    WRONG  →  \needfix{Need citation for: PILD residual errors ~10^-3}
    WRONG  →  \needfix{Need citation for: CSB error explodes from 0.04 to 4.04}
    WRONG  →  \needfix{Need citation for: AUC drops from 0.98 to 0.52}
    RIGHT  →  \needfix{Need citation for: PILD residual-error magnitude}
    RIGHT  →  \needfix{Need citation for: CSB error sensitivity to graph misspecification}
    RIGHT  →  \needfix{Need citation for: post-calibration discriminator AUC near chance}

    ## Cross-reference discipline

    The master template provides EXACTLY these section labels — use these and
    only these in \ref / \autoref / \Cref:

      sec:introduction       sec:related-work      sec:objectives
      sec:methodology        sec:innovation        sec:feasibility
      sec:timeline           sec:expected-results

    Equation and figure labels you define yourself must follow:
      eq:<short_name>    fig:<short_name>

    For every \ref / \autoref you write, verify the label exists in this list
    (or is one of your own eq:/fig: labels in the same file). A typo →
    LaTeX prints "??" → committee notices.

    ## Inputs (all inlined; no need to read upstream reports)

    Upstream metadata (from CONSISTENCY_NOTES + Subagent A):
    {UPSTREAM_JSON}

    Consistency notes (acknowledge or resolve in prose):
    {CONSISTENCY_NOTES}

    Paper index (figures already copied to {FIGURES_DIR}/):
    {PAPER_INDEX_JSON}

    Deep analyses to consult for Related Work synthesis:
    {DEEP_ANALYSIS_PATHS}

    Read these `deep_analysis.md` files directly when drafting Section 2.

    ## Figure embedding template

    \begin{figure}[t]
      \centering
      \includegraphics[width=\linewidth]{figures/paperN_figM.png}
      \caption{Self-contained caption — what is shown AND what the reader
               should notice. From \cite{key}.}
      \label{fig:paperN_figM}
    \end{figure}

    ## Equation embedding template

    \begin{equation}
      <latex>
      \label{eq:short_name}
    \end{equation}

    Introduce the intuition for every equation BEFORE the equation itself
    (per writing-principles.md §Mathematical Writing).

    ## Your deliverable: 9 files under {BODY_DIR}/

    Write EXACTLY these files. Each contains ONLY the body of its section
    (no \section{...}, no \begin{document}, no preamble):

      {BODY_DIR}/abstract.tex            — 200–300 words, five-sentence formula
      {BODY_DIR}/sec1_introduction.tex   — 2–3 pages
      {BODY_DIR}/sec2_related_work.tex   — 4–6 pages, the KEY section
      {BODY_DIR}/sec3_objectives.tex     — 1 page
      {BODY_DIR}/sec4_methodology.tex    — 2–3 pages
      {BODY_DIR}/sec5_innovation.tex     — zh: 0.5–1 page (REQUIRED for 开题报告);
                                           en: 0.5 page or single sentence
      {BODY_DIR}/sec6_feasibility.tex    — 1–2 pages (reuse feasibility content)
      {BODY_DIR}/sec7_timeline.tex       — 0.5 page (Gantt-style description)
      {BODY_DIR}/sec8_expected.tex       — 0.5 page

    Plus ONE text file:
      {BODY_DIR}/proposal_title.txt      — the proposal title (one line)

    ## Related Work section is the star
    Allocate the most attention to sec2_related_work.tex:
    - Organize by technical route, not paper-by-paper.
    - For each paper: core method, key result, AND the gap that motivates
      our work to differ from it.
    - Embed top-relevance figures with self-contained captions.
    - Embed key equations with intuition BEFORE the math.
    - Every cited paper MUST be in bib_index.json.

    ## When you finish
    Before writing your final file, skim your own output and verify:
    - Every "(YYYY)" in prose matches the year field of the nearest \cite key
      in bib_index.json. If not, fix it.
    - Every \cite{...} key appears in bib_index.json.
    - Every figure / equation reference resolves.

    The main agent will run an automated `verify-tex` after you finish.
    Output that fails verification will require a retry — get it right the
    first time.
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

```bash
EXPECTED_FILES="abstract sec1_introduction sec2_related_work sec3_objectives \
                sec4_methodology sec5_innovation sec6_feasibility \
                sec7_timeline sec8_expected"
MISSING=""
for f in $EXPECTED_FILES; do
    test -s "{BODY_DIR}/$f.tex" || MISSING="$MISSING $f.tex"
done
test -s "{BODY_DIR}/proposal_title.txt" || MISSING="$MISSING proposal_title.txt"

if [ -n "$MISSING" ]; then
    echo "Missing body files: $MISSING"
    # Retry Subagent D with prompt narrowed to: "produce only these missing files"
fi
```

---

### Step 6: Rigor Audit (Subagent E) — MANDATORY, runs BEFORE Step 7

> Audits the draft for **scientific rigor only**. Does NOT touch language /
> style / phrasing — Step 7 is for that. Runs sequentially after Subagent D.

🚫 **FORBIDDEN**: launching Step 6 and Step 7 in parallel. Step 7 must
read the OUTPUT of Step 6, not the original draft from Step 5. Running
language polishing on un-corrected rigor is wasted work AND can entrench
half-true prose with prettier wording. **Sequential is the only correct order.**

#### Main agent prepares inline context (small JSONs only)

```bash
BIB_INDEX_JSON=$(cat {OUTPUT_DIR}/bib_index.json)
PAPER_INDEX_JSON=$(cat {OUTPUT_DIR}/paper_index.json)
UPSTREAM_JSON=$(cat {OUTPUT_DIR}/upstream_metadata.json)
CONSISTENCY_NOTES=$(cat {OUTPUT_DIR}/CONSISTENCY_NOTES.md)
mkdir -p {BODY_DIR}/.archive/draft
```

#### Launch Subagent E (Pattern 1)

```yaml
Agent:
  description: "Rigor audit of proposal draft"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You audit a research-proposal draft for SCIENTIFIC RIGOR ONLY. You do
    NOT edit for language quality, style, sentence flow, or phrasing — the
    next subagent (Subagent F) handles that. Make changes ONLY when a
    rigor concern requires them.

    ## File handling
    - Read each file under {BODY_DIR}/ (abstract.tex, sec1_introduction.tex,
      sec2_related_work.tex, ..., sec8_expected.tex).
    - Before overwriting, save originals to {BODY_DIR}/.archive/draft/<filename>.
    - You MAY read the deep_analysis.md files listed in paper_index.json to
      verify specific numerical claims and find missing citations.
    - Do NOT call ReadMediaFile.

    ## Inputs (inlined)
    bib_index.json:
    {BIB_INDEX_JSON}

    paper_index.json (paths to deep_analysis files for fact-checking):
    {PAPER_INDEX_JSON}

    upstream_metadata.json:
    {UPSTREAM_JSON}

    Consistency notes from Subagent A:
    {CONSISTENCY_NOTES}

    ## Rigor checks (apply each pass to every section file)

    ### Check 1 — Numerical-claim provenance

    For every specific number in prose (AUC, FID, percentages, dimensions,
    sample counts, latencies, "X orders of magnitude"), apply the
    **number-provenance ladder**:

      1. **Primary — the ORIGINAL TeX source.** Look up
         `paper_index[k].tex_source_dir` (it's a directory like
         `literature-deep/paper_xxx/1706.03762_src/`). Use the Grep tool:
            Grep("9\\.96",  path=tex_source_dir, glob="**/*.tex")
         Be flexible about LaTeX wrapping: try both `9.96` and
         `\\$9.96\\$` / `\\num{9.96}` / `9{.}96` patterns. Numbers in tables
         live inside `\\begin{tabular}` blocks — grep finds them just fine.

      2. **Secondary — deep_analysis.md.** Only if (1) gave no match OR
         `tex_source_dir` is null:
            Grep("9.96", path=deep_analysis_path)

      3. **Tertiary — upstream_metadata.json, CONSISTENCY_NOTES.md.**

    If a number is NOT found via (1), (2), or (3), it is unverified.
    REPLACE with qualitative phrase, ATTRIBUTE to "our preliminary
    estimate", or wrap in \needfix{...}. Log the resolution under Check 1
    in the audit report:

      sec2_related_work.tex L?? — "FID of 9.96"
        → primary grep: hit in tex_source_dir/main.tex L142 ("$9.96$")
        → KEPT verbatim

      sec2_related_work.tex L?? — "AUC drop from 0.98 to 0.52"
        → primary grep: no match in tex_source_dir
        → secondary grep: no match in deep_analysis.md
        → REWROTE as "AUC drop to near chance"

    The TeX source is more authoritative than deep_analysis.md because
    the latter is a subagent's summary that may have rounded, paraphrased,
    or skipped numbers (especially numbers inside `\\begin{tabular}`).

    ### Check 2 — \needfix{} hygiene
    For every \needfix{} from the draft:
      - Strip any specific numerical value inside it.
      - Keep only the qualitative description of what needs citation.
      WRONG  → \needfix{... residual errors ~10^-3}
      RIGHT  → \needfix{... residual-error magnitude}

    ### Check 3 — Cross-reference correctness
    Allowed labels: sec:introduction, sec:related-work, sec:objectives,
    sec:methodology, sec:innovation, sec:feasibility, sec:timeline,
    sec:expected-results, eq:*, fig:* (where eq:/fig: were defined in the
    same draft).

    For every \ref / \autoref / \Cref: if the label is not in this list,
    fix the label OR remove the reference. Never leave a typo to compile
    as "??".

    ### Check 4 — Hedge calibration
    For every success criterion of the form "we will achieve X%" or
    "≥X reduction" or "increase by a factor of N":
      - If no precedent number is locatable, add a hedge AND a justification:
          "we will achieve ≥30% Wasserstein reduction"
        → "we will measure the Wasserstein reduction; based on the v₂ gap
           between AMPT and UrQMD reported in landscape-report §X, a target
           of ≥30% represents..."
      - If neither precedent nor physics anchor exists, downgrade:
          "we will achieve X" → "we will report the magnitude of X without
           assuming a predetermined gain."

    ### Check 5 — Methodology specificity
    For Section 4 (sec4_methodology.tex):
      - Every "Level N" or "Approach N" that promises a mathematical
        formulation must contain at least one \begin{equation}...\end{equation}
        or pseudocode block.
      - If a paragraph promises math but does not deliver, EITHER:
        (a) add the math (drawing on cited paper's deep_analysis), OR
        (b) downgrade the claim ("we will investigate" / "we will explore"
            instead of "we modify the objective to...").

    ### Check 6 — Related Work synthesis (Section 2)
    Identify subsections that read as paper-by-paper enumeration:
      "X et al. did A. Y et al. did B. Z et al. did C."
    Rewrite the section opener to state the research question driving that
    subsection. Group papers by approach or by failure mode, not by
    chronology. Each paragraph should answer one of:
      - what is the dominant approach in this subarea?
      - what is its failure mode?
      - what gap does our work address that none of these works do?

    ### Check 7 — Claim-evidence coupling
    For every contribution bullet in sec1_introduction.tex and every
    Innovation point in sec5_innovation.tex:
      - Identify which Objective (sec3) and which Methodology subsection
        (sec4) it corresponds to.
      - If a claim has no corresponding methodology, FLAG in the audit
        report (do NOT auto-fix — the user must decide whether to drop the
        claim or add the methodology).

    ## STRICT scope discipline

    DO NOT make language / style changes that are not required by a rigor
    check. The next subagent handles:
      - LLM-shaped phrases ("first-class citizen", "bridge two communities")
      - Sentence-level clarity (Gopen-Swan principles)
      - Vague-to-specific word replacement
      - Hedging removal

    If you spot a language issue, leave it for Subagent F. Touching it here
    either wastes effort (Subagent F may rewrite the same sentence) or
    anchors the language pass on prematurely-polished prose.

    ## Deliverables

    1. Overwrite each {BODY_DIR}/<file>.tex with the rigor-revised version,
       after archiving the original to {BODY_DIR}/.archive/draft/<file>.tex.

    2. Write an audit trail to {OUTPUT_DIR}/rigor_audit.md with the structure:
       ```markdown
       # Rigor Audit Report
       Generated: <ISO timestamp>

       ## Check 1: Numerical-claim provenance
       - sec2_related_work.tex L?? — "AUC 0.500–0.501"
         Found in deep_analyses/paper_xxx/deep_analysis.md → KEPT
         OR not found → REWROTE as "AUC near chance"

       ## Check 2: \needfix hygiene
       - sec6_feasibility.tex L?? — stripped number "~10^-3" from \needfix

       ## Check 3-7: ...

       ## Flagged but not auto-fixed (require human decision)
       - sec1_introduction.tex: Contribution bullet 4 has no corresponding
         methodology in sec4. Either drop the bullet or add a §4.X.
       ```

    The audit report is the trail the user reads to decide whether to accept
    your edits or run Subagent E again with different guidance.
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

```bash
test -s {OUTPUT_DIR}/rigor_audit.md || exit 1
# Every body file must still exist and be non-empty after revision
for f in $EXPECTED_FILES; do
    test -s "{BODY_DIR}/$f.tex" || { echo "MISSING after rigor: $f.tex"; exit 1; }
done
# Archive of original drafts must exist
ls {BODY_DIR}/.archive/draft/*.tex > /dev/null 2>&1 || exit 1
```

If audit fails or the rigor report shows unresolved HIGH-severity issues,
surface to user before launching Step 7.

---

### Step 7: Language Audit (Subagent F) — runs STRICTLY AFTER Step 6

> Audits the rigor-corrected draft for **language quality only**. Numbers,
> citations, and claims are settled by this point — Subagent F MUST NOT
> change any of them.

🚫 **FORBIDDEN — restate for emphasis**:
- Launching Subagent E and F in parallel.
- Launching Subagent F before Subagent E has completed AND its audit has
  passed file-system checks.
- Skipping Subagent E "because the draft already looks fine".

#### Main agent prepares inline context

```bash
mkdir -p {BODY_DIR}/.archive/after_rigor
WRITING_PRINCIPLES=$(cat skills/shared-references/writing-principles.md)
```

`writing-principles.md` is ~25 KB — inlining it into the subagent prompt
is the contract for this audit. The whole point of Subagent F is to apply
this document. Reading it inside the subagent rather than as inline context
would be acceptable too, but inline-context guarantees the subagent cannot
"forget" to consult it.

#### Launch Subagent F (Pattern 1)

```yaml
Agent:
  description: "Language audit of rigor-corrected draft"
  subagent_type: "paper-editor"
  run_in_background: true
  timeout: 3600
  prompt: |
    You audit a research-proposal draft for LANGUAGE QUALITY ONLY. By the
    time you run, the previous subagent (Subagent E) has already corrected
    all citations, numerical claims, cross-references, and methodology
    specificity. Your scope is strictly: clarity, flow, word choice,
    LLM-shaped phrasing, and adherence to writing-principles.md.

    ## You MUST NOT
    - Change any \cite{key} key.
    - Change any numerical value (percentages, AUCs, FIDs, dimensions, ...).
    - Remove or change content of any \needfix{...}.
    - Add, remove, or rephrase technical claims.
    - Restructure section boundaries or section ordering.
    - Touch math content (equations, variable definitions).

    If you spot a rigor issue that Subagent E missed, do NOT fix it. Log
    it in the language_audit.md report under "OUT-OF-SCOPE: rigor concern
    observed". The user decides whether to re-run rigor.

    ## You SHOULD
    - Rewrite sentences for clarity (Gopen-Swan seven principles).
    - Remove LLM-shaped phrases: "first-class optimization citizens",
      "bridge two disjoint communities", "leverage", "delve into",
      "tapestry", "in this paper, we", "it is worth noting that",
      "Importantly,", "Notably,", "remarkable success", "groundbreaking".
    - Replace vague terms with specific ones per the writing-principles
      table (performance → accuracy/F1; large → 1B parameters; etc.).
    - Tighten the abstract per the five-sentence formula.
    - Tighten the introduction per the contribution-bullet rules
      (2–4 concrete, falsifiable bullets).
    - Enforce terminology consistency (don't mix "model" / "network" /
      "architecture" for the same concept).
    - Replace passive constructions with active where it doesn't change
      meaning.

    ## File handling
    - Read each file under {BODY_DIR}/.
    - Before overwriting, save the rigor-corrected version to
      {BODY_DIR}/.archive/after_rigor/<filename>.
    - Do NOT call ReadMediaFile.

    ## Required reading (FULL CONTENT inlined)

    The following is the complete writing-principles.md. Apply every
    applicable rule. Pay particular attention to:
      - The Narrative Principle (one-sentence contribution test)
      - Time Allocation and Reviewer Reading Order
      - How to Write the Abstract (five-sentence formula)
      - Introduction Structure (contribution bullets, opening hook)
      - Sentence-Level Clarity (Gopen-Swan seven principles)
      - Micro-Level Writing Tactics (ambiguous pronouns, low-info fillers)
      - Word Choice and Precision (vague→specific table, hedging removal,
        vocabulary signaling)
      - Mathematical Writing (intuition before formal statement)
      - Figure Design (self-contained captions)
      - Common Mistakes tables

    {WRITING_PRINCIPLES}

    ## Deliverables

    1. Overwrite each {BODY_DIR}/<file>.tex with the language-revised version,
       after archiving the rigor-corrected version to
       {BODY_DIR}/.archive/after_rigor/<file>.tex.

    2. Write an audit trail to {OUTPUT_DIR}/language_audit.md with notable
       rewrites grouped by writing-principles.md section:

       ```markdown
       # Language Audit Report
       Generated: <ISO timestamp>

       ## Abstract — five-sentence formula
       - Old: "We propose a physics-constrained Schrödinger Bridge..."
         New: "..."
         Reason: opening sentence merged two ideas; split for clarity.

       ## Introduction — contribution bullets
       - Old bullet 3: "Quantified systematic-bias reduction..."
         New bullet 3: "We measure the magnitude of systematic-bias reduction..."
         Reason: original was a methodology choice phrased as a claim.

       ## LLM-shaped phrase removal
       - sec5_innovation.tex L?? — "first-class optimization citizens" → removed
       - sec5_innovation.tex L?? — "bridge two currently disjoint communities" →
         rewritten as "address heavy-ion calibration using SB methods, which
         have not previously been applied in this context"

       ## Out-of-scope rigor concerns observed (NOT fixed)
       - sec2_related_work.tex L?? — number "0.500–0.501" still appears
         without grep-verification (Subagent E may have missed this).

       ## Sentence-clarity rewrites
       [...]
       ```

    The audit trail is the user's view of what changed and why.
```

#### Apply polling (Pattern 2) and audit (Pattern 3)

```bash
test -s {OUTPUT_DIR}/language_audit.md || exit 1
for f in $EXPECTED_FILES; do
    test -s "{BODY_DIR}/$f.tex" || { echo "MISSING after language: $f.tex"; exit 1; }
done
ls {BODY_DIR}/.archive/after_rigor/*.tex > /dev/null 2>&1 || exit 1
```

Optional sanity check — confirm Subagent F didn't violate the no-rigor-change
rule:

```bash
# Did any \cite{} key disappear or change?
diff <(grep -ohE '\\cite[a-zA-Z]*\*?\{[^}]+\}' {BODY_DIR}/.archive/after_rigor/*.tex | sort -u) \
     <(grep -ohE '\\cite[a-zA-Z]*\*?\{[^}]+\}' {BODY_DIR}/*.tex | sort -u) \
  | head -20  # show any drift; non-empty output is a soft warning
```

---

### Step 8: Assemble `main.tex` from Template (main agent, sed)

```bash
TITLE_TEXT=$(cat {BODY_DIR}/proposal_title.txt 2>/dev/null || echo "{TITLE}")
AUTHOR_TEXT="${AUTHOR:-\\needfix{Add author name}}"
DATE_TEXT="\\today"

if [ "{output_language}" = "zh" ]; then
    PREAMBLE='\usepackage{ctex}'
    SEC_TITLES=( "研究背景与意义" "国内外研究现状综述" "研究目标与内容" "研究方法与技术路线" "研究特色与创新之处" "可行性分析" "研究计划与进度安排" "预期成果与影响" )
    BIB_TITLE="参考文献"
else
    PREAMBLE='\usepackage[utf8]{inputenc}\usepackage[T1]{fontenc}\usepackage{lmodern}'
    SEC_TITLES=( "Introduction and Motivation" "Related Work and Literature Review" "Research Objectives" "Methodology and Technical Approach" "Innovation Points" "Feasibility Analysis" "Timeline and Milestones" "Expected Results and Impact" )
    BIB_TITLE="References"
fi

cp templates/RESEARCH_PROPOSAL_TEMPLATE.tex {OUTPUT_DIR}/main.tex
esc() { printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'; }

sed -i.bak \
    -e "s|<<LANGUAGE_PREAMBLE>>|$(esc "$PREAMBLE")|" \
    -e "s|<<TITLE>>|$(esc "$TITLE_TEXT")|" \
    -e "s|<<AUTHOR>>|$(esc "$AUTHOR_TEXT")|" \
    -e "s|<<DATE>>|$(esc "$DATE_TEXT")|" \
    -e "s|<<SEC1_TITLE>>|$(esc "${SEC_TITLES[0]}")|" \
    -e "s|<<SEC2_TITLE>>|$(esc "${SEC_TITLES[1]}")|" \
    -e "s|<<SEC3_TITLE>>|$(esc "${SEC_TITLES[2]}")|" \
    -e "s|<<SEC4_TITLE>>|$(esc "${SEC_TITLES[3]}")|" \
    -e "s|<<SEC5_TITLE>>|$(esc "${SEC_TITLES[4]}")|" \
    -e "s|<<SEC6_TITLE>>|$(esc "${SEC_TITLES[5]}")|" \
    -e "s|<<SEC7_TITLE>>|$(esc "${SEC_TITLES[6]}")|" \
    -e "s|<<SEC8_TITLE>>|$(esc "${SEC_TITLES[7]}")|" \
    -e "s|<<BIB_TITLE>>|$(esc "$BIB_TITLE")|" \
    {OUTPUT_DIR}/main.tex
rm -f {OUTPUT_DIR}/main.tex.bak

# Abstract is multi-line; sed-escaping is painful, so use Python.
python3 - <<PYEOF
from pathlib import Path
p = Path("{OUTPUT_DIR}/main.tex")
abstract = Path("{BODY_DIR}/abstract.tex").read_text(encoding="utf-8")
p.write_text(p.read_text(encoding="utf-8").replace("<<ABSTRACT>>", abstract), encoding="utf-8")
PYEOF

# Sanity: zero residual placeholders
grep "<<" {OUTPUT_DIR}/main.tex && { echo "ERROR: unsubstituted placeholders"; exit 1; } || echo "OK"
```

---

### Step 9: Compile (main agent, shell) — optional

```bash
if [ "{output_language}" = "zh" ] && ! kpsewhich ctex.sty > /dev/null 2>&1; then
    echo "ctex.sty not installed — skipping compile. Upload main.tex to Overleaf."
else
    cd {OUTPUT_DIR}
    xelatex -interaction=nonstopmode main.tex > /dev/null 2>&1
    biber main > /dev/null 2>&1
    xelatex -interaction=nonstopmode main.tex > /dev/null 2>&1
    xelatex -interaction=nonstopmode main.tex
    if [ ! -s main.pdf ]; then
        echo "Compile failed. Last 30 log lines:"
        tail -n 30 main.log
    fi
fi
```

Do NOT block on compilation failure — `.tex` source is the primary deliverable.

---

### Step 10: Final Verification (main agent, multi-check) — MANDATORY

Citation integrity is necessary but not sufficient — the previous test runs
showed two additional failure modes that survived `verify-tex`: undefined
`\ref{}` labels (rendered as "Section ??" in the PDF) and group-author
mis-parsing ("Collaboration (2025)"). The final verification combines:

```bash
# Check A — Citation integrity (every \cite{} resolved, every "(YYYY)" matches)
python3 tools/bibtex_fetch.py verify-tex \
    --tex {OUTPUT_DIR}/main.tex {OUTPUT_DIR}/body/*.tex \
    --bib {OUTPUT_DIR}/references.bib \
    --bib-index {OUTPUT_DIR}/bib_index.json
VERIFY_TEX_RC=$?

# Check B — Undefined LaTeX cross-references (the "Section ??" symptom)
# Only meaningful if compilation succeeded.
if [ -s {OUTPUT_DIR}/main.log ]; then
    UNDEF_REFS=$(grep -cE "Reference \`[^']+' on page [0-9]+ undefined" {OUTPUT_DIR}/main.log || echo 0)
    if [ "$UNDEF_REFS" -gt 0 ]; then
        echo "❌ $UNDEF_REFS undefined LaTeX reference(s) — \"Section ??\" will appear:"
        grep -E "Reference \`[^']+' on page [0-9]+ undefined" {OUTPUT_DIR}/main.log
    fi
fi

# Check C — Compiled PDF must not contain literal "??" (belt-and-suspenders)
if [ -s {OUTPUT_DIR}/main.pdf ] && command -v pdftotext > /dev/null; then
    pdftotext {OUTPUT_DIR}/main.pdf - | grep -nE "Section \?\?|Equation \?\?|Figure \?\?" \
        && { echo "❌ PDF contains unresolved cross-reference"; FINAL_RC=1; }
fi

# Check D — Group-author parse artifacts ("Collaboration (YYYY)" without prefix)
# A surname that is exactly "Collaboration" / "Group" / "Team" / "Consortium"
# in prose is a parsing bug, not a real author.
GROUP_ARTIFACT=$(grep -hE '\b(Collaboration|Group|Team|Consortium) \([0-9]{4}\)' \
    {OUTPUT_DIR}/main.tex {OUTPUT_DIR}/body/*.tex)
if [ -n "$GROUP_ARTIFACT" ]; then
    echo "❌ Group-author parse artifact — should read e.g. 'ATLAS Collaboration (YYYY)':"
    echo "$GROUP_ARTIFACT"
fi

# Aggregate result
if [ "$VERIFY_TEX_RC" -ne 0 ] || [ "$UNDEF_REFS" -gt 0 ] \
   || [ -n "$GROUP_ARTIFACT" ]; then
    echo
    echo "❌ Final verification FAILED. Run is NOT complete."
    echo "   Surface the above violations and let the user decide:"
    echo "   - re-run Subagent E (rigor) with targeted patch prompts, or"
    echo "   - re-run Subagent F (language) with the failing files only, or"
    echo "   - accept the violations and finalize manually."
    exit 1
fi

echo "✅ Final verification PASSED: citations, cross-references, and"
echo "   group-author rendering are all clean."
```

Do NOT claim success until ALL four checks pass OR the user explicitly waives
the violations.

---

## Output Structure

```
proposal/
├── main.tex                     # Master document (assembled in Step 8)
├── body/
│   ├── abstract.tex             # Final (after Subagents D → E → F)
│   ├── sec1_introduction.tex
│   ├── sec2_related_work.tex
│   ├── sec3_objectives.tex
│   ├── sec4_methodology.tex
│   ├── sec5_innovation.tex
│   ├── sec6_feasibility.tex
│   ├── sec7_timeline.tex
│   ├── sec8_expected.tex
│   ├── proposal_title.txt
│   └── .archive/
│       ├── draft/               # Subagent D's original output
│       └── after_rigor/         # Subagent E's output (= Subagent F's input)
├── figures/
│   ├── paper1_fig1.png
│   └── ...
├── supporting_papers/           # PDFs of supporting literature (optional)
├── references.bib               # Verified BibTeX (Step 4)
├── bib_index.json               # Ground-truth metadata lookup (Step 4)
├── upstream_metadata.json       # From Subagent A
├── paper_index.json             # From Subagent B
├── supporting_queue.json        # From Subagent C
├── CONSISTENCY_NOTES.md         # From Subagent A
├── rigor_audit.md               # From Subagent E — what rigor changes were made
├── language_audit.md            # From Subagent F — what language changes were made
├── bibtex_fetch_failures.json   # If any HIGH fetches failed
└── main.pdf                     # If compilation succeeded
```

---

## Key Rules Summary

1. **Main agent only orchestrates and audits.** Never reads paper files, never drafts prose, never writes BibTeX. See "Main Agent Boundary Protocol".
2. **Zero-fabrication tolerance.** Every author/year/venue/cite key comes from `bib_index.json`. Every BibTeX entry comes from `tools/bibtex_fetch.py`. Every specific number in prose must be grep-traceable to a deep_analysis.md.
3. **Every reading-heavy step is delegated** — Steps 1, 2, 4a, 5, 6, 7 are subagent calls. Steps 0, 3, 4b–d, 8, 9, 10 are pure shell.
4. **Every subagent launch uses the polling protocol** (Phase 1–4) and is followed by a file-system audit.
5. **`paper-editor` is the only `subagent_type` used** — task differentiation comes from the prompt, mirroring `idea-landscape`.
6. **Rigor audit (Step 6) and language audit (Step 7) are STRICTLY SEQUENTIAL.** Never parallel; never reverse-ordered; never skipped. Polishing un-corrected rigor is worse than skipping the polish entirely — it entrenches half-true prose with prettier wording. Subagent F reads Subagent E's output, not Subagent D's draft.
7. **HIGH-priority supporting citations must succeed** (or be explicitly `\needfix{}` with qualitative content only). MEDIUM-priority may silently fall back.
8. **\needfix{} content is qualitative.** Specific numerical values inside `\needfix{}` are equivalent to fabrication and are stripped by Subagent E (Check 2).
9. **arXiv IDs are HEAD-probed.** `bibtex_fetch.py` rejects entries whose arXiv ID returns 404 on arxiv.org/abs/. Network failure (not 404) is treated as "unknown", not "fail" — flaky connections do not invalidate real citations.
10. **Group authors render correctly.** "ATLAS Collaboration (2025)" — never "Collaboration (2025)". Enforced by `first_author_surname()` group-keyword rule.
11. **Language consistency** — narrative in chosen language; paper metadata stays English.
12. **Compilation is best-effort** — `.tex` is the primary deliverable.
13. **Final verification (Step 10) covers four axes** — citation integrity, undefined LaTeX refs (`Section ??` symptom), unresolved `??` in compiled PDF, group-author parse artifacts. All four must pass.
14. **Never re-run literature survey** — assumes `idea-survey/` exists; fail fast otherwise.
