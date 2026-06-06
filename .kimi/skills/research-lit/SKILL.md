---
name: research-lit
description: Search and analyze research papers, find related work, summarize key ideas. Use when user says "find papers", "related work", "literature review", "what does this paper say", or needs to understand academic papers.
argument-hint: [paper-topic-or-url]
---

# Research Literature Review

Research topic: $ARGUMENTS

## Constants


- **REVIEWER_BACKEND = `agent`** — Default: Agent subagent. See `shared-references/reviewer-routing.md`.
- **PAPER_LIBRARY** — Local directory containing user's paper collection (PDFs). Check these paths in order:
  1. `papers/` in the current project directory
  2. `literature/` in the current project directory
  3. Custom path specified by user in `CLAUDE.md` under `## Paper Library`
- **MAX_LOCAL_PAPERS = 20** — Maximum number of local PDFs to scan (read first 3 pages each). If more are found, prioritize by filename relevance to the topic.
- **ARXIV_DOWNLOAD = false** — When `true`, download top N most relevant arXiv PDFs to PAPER_LIBRARY after search. When `false` (default), only fetch metadata via arXiv API — no files are downloaded.
- **ARXIV_DOWNLOAD_SOURCE = false** — When `true` (and `ARXIV_DOWNLOAD = true`), download the TeX source tarball instead of the PDF. Contains original figures (PNG/JPG/PDF/EPS), `.tex` files, and BibTeX.
- **ARXIV_MAX_DOWNLOAD = 5** — Maximum number of PDFs/source tarballs to download when `ARXIV_DOWNLOAD = true` **and** `DEEP_ANALYZE = false`. **Ignored when `DEEP_ANALYZE = true`** — see `DEEP_ANALYZE_MAX` below.
- **DEEP_ANALYZE = false** — When `true`, perform per-paper deep analysis with dedicated subagents. Automatically downloads source materials (TeX or PDF) for the top-N relevant papers, extracts figures/tables, and generates figure-by-figure interpretation.
- **DEEP_ANALYZE_MAX = 5** — Number of papers to deep-analyze (and therefore download source for) when `DEEP_ANALYZE = true`. This single parameter controls **both** how many papers are analyzed **and** how many sources are downloaded. No separate download limit is needed.
- **DEEP_ANALYZE_SOURCE = true** — When `true`, prefer downloading TeX source for figure extraction. When `false`, use PDF image extraction only (faster but lower quality).
- **DEEP_ANALYZE_OUTPUT_DIR = `literature-deep/`** — Output directory for deep analysis artifacts.
- **MAX_CONCURRENT_SUBAGENTS = 3** — Maximum number of parallel subagents for deep analysis to avoid overwhelming system resources.
- **OUTPUT_LANGUAGE = "auto"** — Output language for summaries and deep analysis. `"auto"` detects from `CLAUDE.md` language field or user message language (see `shared-references/output-language.md`). Explicit overrides: `zh`, `en`.

> 💡 Overrides:
> - `/skill:research-lit "topic" — paper library: ~/my_papers/` — custom local PDF path
> - `/skill:research-lit "topic" — sources: zotero, local` — only search Zotero + local PDFs
> - `/skill:research-lit "topic" — sources: zotero` — only search Zotero
> - `/skill:research-lit "topic" — sources: web` — only search the web (skip all local)
> - `/skill:research-lit "topic" — sources: web, semantic-scholar` — also search Semantic Scholar for published venue papers (IEEE, ACM, etc.)
> - `/skill:research-lit "topic" — sources: deepxiv` — only search via DeepXiv progressive retrieval
> - `/skill:research-lit "topic" — sources: all, deepxiv` — use default sources plus DeepXiv
> - `/skill:research-lit "topic" — arxiv download: true` — download top 5 arXiv PDFs (no deep analysis)
> - `/skill:research-lit "topic" — arxiv download: true, source` — download TeX source tarballs instead of PDFs (no deep analysis)
> - `/skill:research-lit "topic" — deep analyze: true` — enable per-paper deep analysis (default: analyze and download top 5 papers)
> - `/skill:research-lit "topic" — deep analyze: true, max: 10` — deep-analyze top 10 papers (also downloads 10 sources)
> - `/skill:research-lit "topic" — deep analyze: true, source: false` — deep-analyze using PDF fallback (no TeX download)
> - `/skill:research-lit "topic" — deep analyze: true, max: 3, source: false` — deep-analyze 3 papers via PDF only
> - `/skill:research-lit "topic" — language: zh` — output summaries and deep analysis in Chinese

## Language Determination

Before starting analysis, determine `output_language`:

1. **Parse `$ARGUMENTS` for `— language:` override.** If `zh` or `cn` is specified, set `output_language = "zh"`. If `en` is specified, set `output_language = "en"`.
2. **If no override:** Follow the **[Output Language Protocol](../shared-references/output-language.md)**:
   - Check `CLAUDE.md` for `language: zh` or `language: cn` under `## Pipeline Status`
   - If the user's most recent message is in Chinese, use Chinese
   - Default: English
3. **Propagate `output_language`** to all subagent prompts and the orchestrator (`--language` flag).

## Data Sources

This skill checks multiple sources **in priority order**. All are optional — if a source is not configured or not requested, skip it silently.

### Source Selection

Parse `$ARGUMENTS` for a `— sources:` directive:
- **If `— sources:` is specified**: Only search the listed sources (comma-separated). Valid values: `zotero`, `obsidian`, `local`, `web`, `semantic-scholar`, `deepxiv`, `exa`, `all`.
- **If not specified**: Default to `all` — search every available source in priority order (`semantic-scholar`, `deepxiv`, and `exa` are **excluded** from `all`; they must be explicitly listed).

Examples:
```
/skill:research-lit "diffusion models"                                    → all (default, no S2)
/skill:research-lit "diffusion models" — sources: all                     → all (default, no S2)
/skill:research-lit "diffusion models" — sources: zotero                  → Zotero only
/skill:research-lit "diffusion models" — sources: zotero, web             → Zotero + web
/skill:research-lit "diffusion models" — sources: local                   → local PDFs only
/skill:research-lit "topic" — sources: obsidian, local, web               → skip Zotero
/skill:research-lit "topic" — sources: web, semantic-scholar              → web + S2 API (IEEE/ACM venue papers)
/skill:research-lit "topic" — sources: deepxiv                            → DeepXiv only
/skill:research-lit "topic" — sources: all, deepxiv                       → default sources + DeepXiv
/skill:research-lit "topic" — sources: all, semantic-scholar              → all + S2 API
/skill:research-lit "topic" — sources: exa                               → Exa only (broad web + content extraction)
/skill:research-lit "topic" — sources: all, exa                          → default sources + Exa web search
```

### Source Table

| Priority | Source | ID | How to detect | What it provides |
|----------|--------|----|---------------|-----------------|
| 1 | **Zotero** (via MCP) | `zotero` | Try calling any `mcp__zotero__*` tool — if unavailable, skip | Collections, tags, annotations, PDF highlights, BibTeX, semantic search |
| 2 | **Obsidian** (via MCP) | `obsidian` | Try calling any `mcp__obsidian-vault__*` tool — if unavailable, skip | Research notes, paper summaries, tagged references, wikilinks |
| 3 | **Local PDFs** | `local` | `Glob: papers/**/*.pdf, literature/**/*.pdf` | Raw PDF content (first 3 pages) |
| 4 | **Web search** | `web` | Always available (WebSearch) | arXiv, Semantic Scholar, Google Scholar |
| 5 | **Semantic Scholar API** | `semantic-scholar` | `tools/semantic_scholar_fetch.py` exists | Published venue papers (IEEE, ACM, Springer) with structured metadata: citation counts, venue info, TLDR. **Only runs when explicitly requested** via `— sources: semantic-scholar` or `— sources: web, semantic-scholar` |
| 6 | **DeepXiv CLI** | `deepxiv` | `tools/deepxiv_fetch.py` and installed `deepxiv` CLI | Progressive paper retrieval: search, brief, head, section, trending, web search. **Only runs when explicitly requested** via `— sources: deepxiv` or `— sources: all, deepxiv` |
| 7 | **Exa Search** | `exa` | `tools/exa_search.py` and installed `exa-py` SDK | AI-powered broad web search with content extraction (highlights, text, summaries). Covers blogs, docs, news, companies, and research papers beyond arXiv/S2. **Only runs when explicitly requested** via `— sources: exa` or `— sources: all, exa` |

> **Graceful degradation**: If no MCP servers are configured, the skill works exactly as before (local PDFs + web search). Zotero and Obsidian are pure additions.

## Workflow

### Step 0a: Search Zotero Library (if available)

**Skip this step entirely if Zotero MCP is not configured.**

Try calling a Zotero MCP tool (e.g., search). If it succeeds:

1. **Search by topic**: Use the Zotero search tool to find papers matching the research topic
2. **Read collections**: Check if the user has a relevant collection/folder for this topic
3. **Extract annotations**: For highly relevant papers, pull PDF highlights and notes — these represent what the user found important
4. **Export BibTeX**: Get citation data for relevant papers (useful for `/skill:paper-write` later)
5. **Compile results**: For each relevant Zotero entry, extract:
   - Title, authors, year, venue
   - User's annotations/highlights (if any)
   - Tags the user assigned
   - Which collection it belongs to

> 📚 Zotero annotations are gold — they show what the user personally highlighted as important, which is far more valuable than generic summaries.

### Step 0b: Search Obsidian Vault (if available)

**Skip this step entirely if Obsidian MCP is not configured.**

Try calling an Obsidian MCP tool (e.g., search). If it succeeds:

1. **Search vault**: Search for notes related to the research topic
2. **Check tags**: Look for notes tagged with relevant topics (e.g., `#diffusion-models`, `#paper-review`)
3. **Read research notes**: For relevant notes, extract the user's own summaries and insights
4. **Follow links**: If notes link to other relevant notes (wikilinks), follow them for additional context
5. **Compile results**: For each relevant note:
   - Note title and path
   - User's summary/insights
   - Links to other notes (research graph)
   - Any frontmatter metadata (paper URL, status, rating)

> 📝 Obsidian notes represent the user's **processed understanding** — more valuable than raw paper content for understanding their perspective.

### Step 0c: Scan Local Paper Library

Before searching online, check if the user already has relevant papers locally:

1. **Locate library**: Check PAPER_LIBRARY paths for PDF files
   ```
   Glob: papers/**/*.pdf, literature/**/*.pdf
   ```

2. **De-duplicate against Zotero**: If Step 0a found papers, skip any local PDFs already covered by Zotero results (match by filename or title).

3. **Filter by relevance**: Match filenames and first-page content against the research topic. Skip clearly unrelated papers.

4. **Summarize relevant papers**: For each relevant local PDF (up to MAX_LOCAL_PAPERS):
   - Read first 3 pages (title, abstract, intro)
   - Extract: title, authors, year, core contribution, relevance to topic
   - Flag papers that are directly related vs tangentially related

5. **Build local knowledge base**: Compile summaries into a "papers you already have" section. This becomes the starting point — external search fills the gaps.

> 📚 If no local papers are found, skip to Step 1. If the user has a comprehensive local collection, the external search can be more targeted (focus on what's missing).

### Step 1: Search (external)
- Use WebSearch to find recent papers on the topic
- Check arXiv, Semantic Scholar, Google Scholar
- Focus on papers from last 2 years unless studying foundational work
- **De-duplicate**: Skip papers already found in Zotero, Obsidian, or local library

**arXiv API search** (always runs, no download by default):

Locate the fetch script and search arXiv directly:
```bash
# Try to find arxiv_fetch.py
SCRIPT=$(find tools/ -name "arxiv_fetch.py" 2>/dev/null | head -1)
# If not found, check ARIS install
[ -z "$SCRIPT" ] && SCRIPT=$(find ~/.kimi/skills/arxiv/ -name "arxiv_fetch.py" 2>/dev/null | head -1)

# Search arXiv API for structured results (title, abstract, authors, categories)
python3 "$SCRIPT" search "QUERY" --max 10
```

If `arxiv_fetch.py` is not found, fall back to WebSearch for arXiv (same as before).

The arXiv API returns structured metadata (title, abstract, full author list, categories, dates) — richer than WebSearch snippets. Merge these results with WebSearch findings and de-duplicate.

**Semantic Scholar API search** (only when `semantic-scholar` is in sources):

When the user explicitly requests `— sources: semantic-scholar` (or `— sources: web, semantic-scholar`), search for published venue papers beyond arXiv:

```bash
S2_SCRIPT=$(find tools/ -name "semantic_scholar_fetch.py" 2>/dev/null | head -1)
[ -z "$S2_SCRIPT" ] && S2_SCRIPT=$(find ~/.kimi/skills/semantic-scholar/ -name "semantic_scholar_fetch.py" 2>/dev/null | head -1)

# Search for published CS/Engineering papers with quality filters
python3 "$S2_SCRIPT" search "QUERY" --max 10 \
  --fields-of-study "Computer Science,Engineering" \
  --publication-types "JournalArticle,Conference"
```

If `semantic_scholar_fetch.py` is not found, skip silently.

**Why use Semantic Scholar?** Many IEEE/ACM journal papers are NOT on arXiv. S2 fills the gap for published venue-only papers with citation counts and venue metadata.

**De-duplication between arXiv and S2**: Match by arXiv ID (S2 returns `externalIds.ArXiv`):
- If a paper appears in both: check S2's `venue`/`publicationVenue` — if it has been published in a journal/conference (e.g. IEEE TWC, JSAC), use S2's metadata (venue, citationCount, DOI) as the authoritative version, since the published version supersedes the preprint. Keep the arXiv PDF link for download.
- If the S2 match has no venue (still just a preprint indexed by S2): keep the arXiv version as-is.
- S2 results without `externalIds.ArXiv` are **venue-only papers** not on arXiv — these are the unique value of this source.

**DeepXiv search** (only when `deepxiv` is in sources):

When the user explicitly requests `— sources: deepxiv` (or includes `deepxiv` in a combined source list), use the DeepXiv adapter for progressive retrieval:

```bash
python3 tools/deepxiv_fetch.py search "QUERY" --max 10
```

Then deepen only for the most relevant papers:

```bash
python3 tools/deepxiv_fetch.py paper-brief ARXIV_ID
python3 tools/deepxiv_fetch.py paper-head ARXIV_ID
python3 tools/deepxiv_fetch.py paper-section ARXIV_ID "Experiments"
```

If `tools/deepxiv_fetch.py` or the `deepxiv` CLI is unavailable, skip this source gracefully and continue with the remaining requested sources.

**Why use DeepXiv?** It is useful when a broad search should be followed by staged reading rather than immediate full-paper loading. This reduces unnecessary context while still surfacing structure, TLDRs, and the most relevant sections.

**De-duplication against arXiv and S2**:
- Match by arXiv ID first, DOI second, normalized title third
- If DeepXiv and arXiv refer to the same preprint, keep one canonical paper row and record `deepxiv` as an additional source
- If DeepXiv overlaps with S2 on a published paper, prefer S2 venue/citation metadata in the final table, but keep DeepXiv-derived section notes when they add value

**Exa search** (only when `exa` is in sources):

When the user explicitly requests `— sources: exa` (or includes `exa` in a combined source list), use the Exa tool for broad AI-powered web search with content extraction:

```bash
EXA_SCRIPT=$(find tools/ -name "exa_search.py" 2>/dev/null | head -1)

# Search for research papers with highlights
python3 "$EXA_SCRIPT" search "QUERY" --max 10 --category "research paper" --content highlights

# Search for broader web content (blogs, docs, news)
python3 "$EXA_SCRIPT" search "QUERY" --max 10 --content highlights
```

If `tools/exa_search.py` or the `exa-py` SDK is unavailable, skip this source gracefully and continue with the remaining requested sources.

**Why use Exa?** Exa provides AI-powered search across the broader web (blogs, documentation, news, company pages) with built-in content extraction. It fills a gap between academic databases (arXiv, S2) and generic WebSearch by returning richer content with each result.

**De-duplication against arXiv, S2, and DeepXiv**:
- Match by URL first, then normalized title
- If Exa returns an arXiv paper already found by arXiv/S2, prefer the structured metadata from those sources
- Exa results from non-academic domains (blogs, docs, news) are unique value not covered by other sources

**Optional download** (only when `ARXIV_DOWNLOAD = true` **and** `DEEP_ANALYZE = false`):

> When `DEEP_ANALYZE = true`, downloads are handled automatically by Step 1.5 using `DEEP_ANALYZE_MAX`. This optional download step is skipped.

After all sources are searched and papers are ranked by relevance:

If `source` is **not** specified (default):
```bash
# Download top N most relevant arXiv PDFs
python3 "$SCRIPT" download ARXIV_ID --dir papers/
```

If `source` **is** specified:
```bash
# Download TeX source tarball (contains original figures, .tex files, BibTeX)
python3 "$SCRIPT" download-source ARXIV_ID --dir papers/
```

Rules for both modes:
- Only download papers ranked in the top `ARXIV_MAX_DOWNLOAD` by relevance
- Skip papers already in the local library
- 1-second delay between downloads (rate limiting)
- Verify each PDF > 10 KB, or each tarball > 1 KB

### Step 1.5: Source Download for Deep Analysis (Optional)

**Skip entirely if `DEEP_ANALYZE = false`.**

After all sources are searched and papers are ranked by relevance:

For each paper in the top `DEEP_ANALYZE_MAX` by relevance:

1. **Create workspace**: `mkdir -p literature-deep/paper_<safe_id>/`

2. **If paper has arXiv ID and `DEEP_ANALYZE_SOURCE = true`**:
   ```bash
   # Download TeX source
   python3 "$SCRIPT" download-source ARXIV_ID --dir literature-deep/paper_<safe_id>/
   ```
   If download succeeds:
   ```bash
   # Parse TeX source to extract figure/table metadata
   python3 tools/latex_source_parser.py literature-deep/paper_<safe_id>/ARXIV_ID_src/ \
       --output literature-deep/paper_<safe_id>/figure_manifest.json
   ```
   If download-source fails or no source is available:
   - Fallback: download the PDF, then go to **Step 1.5.3** (PDF path).

3. **If paper has no arXiv ID, or `DEEP_ANALYZE_SOURCE = false`, or the user supplied a local PDF directly** (common for non-arXiv physics journals like PRL/PRD/PRC/PRB, ATLAS/CMS/ALICE collaboration notes, national-lab tech reports, Chinese-language journals, conference proceedings):

   Do **NOT** call `pdf_figure_extractor.py` directly. Use the orchestrator with `--pdf-path`; it auto-selects the **MinerU-driven `pdf_full_parser.py`** when MinerU is installed (figures + tables + equations + caption attribution) and falls back to the legacy image-only extractor otherwise.

   ```bash
   python3 tools/paper_analyzer_orchestrator.py prepare \
       --pdf-path PDF_PATH \
       --output-dir literature-deep/paper_<safe_id>/ \
       --paper-info '{"title":"...","authors":"...","year":2024,"venue":"...","abstract":"..."}' \
       --language {output_language} \
       --pdf-parser auto              # auto = full (MinerU) if installed else legacy
       # Force MinerU explicitly:    --pdf-parser full --mineru-lang en
       # Disable pix2tex fallback:   --no-pix2tex
       # Chinese-language paper:     --mineru-lang zh
   ```

   After the run, **briefly inspect `literature-deep/paper_<safe_id>/parse_log.json`** if it exists: every figure whose `caption_provenance` is not `mineru_native` and every equation flagged `mineru_low_confidence` is listed there. These are the items that may need human review later. Do **NOT** block the pipeline on these — they are advisory.

4. **TeX-source branch only — run orchestrator** to build analysis context (the PDF branch above already does this internally):
   ```bash
   python3 tools/paper_analyzer_orchestrator.py prepare \
       --arxiv-id ARXIV_ID \
       --source-dir literature-deep/paper_<safe_id>/ARXIV_ID_src/ \
       --output-dir literature-deep/paper_<safe_id>/ \
       --paper-info '{"title":"...","authors":"...","year":2024,"venue":"...","abstract":"..."}' \
       --language {output_language}
   ```

   **Schema parity guarantee.** Whether the workspace was built from TeX source or from a PDF (MinerU path), `figure_manifest.json` has the same top-level shape: `figures[]`, `tables[]`, `equations[]`, `unmatched_images[]`, `image_stats`, plus per-item `caption`, `image_paths`, `context_paragraphs`. Paper-analyzer subagents consume both transparently — do **not** branch logic by source kind when invoking them.

5. **Rate limiting**: 1-second delay between consecutive source downloads.

### Step 2: Analyze Each Paper
For each relevant paper (from all sources), extract:
- **Problem**: What gap does it address?
- **Method**: Core technical contribution (1-2 sentences)
- **Results**: Key numbers/claims
- **Relevance**: How does it relate to our work?
- **Source**: Where we found it (Zotero/Obsidian/local/web) — helps user know what they already have vs what's new

### Step 2.5: Per-Paper Deep Analysis (Optional)

**Skip entirely if `DEEP_ANALYZE = false`.**

For each paper prepared in Step 1.5, launch a dedicated subagent to perform figure-by-figure deep interpretation.

**Parallel Execution Strategy:**

To maximize efficiency, launch subagents concurrently using `run_in_background=true`:

```yaml
# Launch all analysis subagents in parallel (up to MAX_CONCURRENT_SUBAGENTS at a time)
Agent:
  description: "Deep analyze: {short_title}"
  subagent_type: "paper-analyzer"
  run_in_background: true
  prompt: |
    You are an expert academic paper analyst. Perform a deep reading of the following paper.

    ## Paper Metadata
    - Title: {title}
    - Authors: {authors}
    - Year: {year}
    - Venue: {venue}
    - arXiv/DOI: {id}
    - Abstract: {abstract}
    - Research topic: {topic}
    - Output language: {output_language}

    ## Extracted Figures, Tables & Equations
    Read the figure manifest: {figure_manifest_path}
    Image directory: {figures_dir}

    ### Figure Analysis — VISION-FIRST MANDATE
    For **every figure** in the manifest:
    1. **Use `ReadMediaFile` to view the actual image file directly.** Do not rely solely on filenames or captions to infer content. You must look at the pixels.
    2. **Analyze the actual visual content**: axes, curves, architecture diagrams, color maps, data trends, labels, annotations. Describe what you see literally.
    3. **Correlate visual observations with text claims**: Does the image support what the caption and surrounding text claim? If the visual content contradicts the text, note it explicitly.
    4. **Explain WHY it matters**: Which core claim or contribution does this figure support? Is it the main architecture? The key result? A motivating example?
    5. **Explain BEFORE/AFTER context**: What text leads into this figure? How do the authors discuss it afterward?
    6. **If quantitative, extract key numbers** and interpret them in context.

    The caption provides context, but **the image itself is the primary evidence**. Do not perform figure analysis from the TeX source — always read the actual image file.

    ### Table Analysis
    For each table in the manifest:
    1. Describe the structure: rows, columns, what is being compared, units.
    2. Explain which claim it supports (baseline comparison? ablation study?).
    3. Extract key data points and highlight the main advantage.
    4. Connect to surrounding text.

    ### Equation Analysis
    For each important equation in the manifest:
    1. **Explain the mathematical meaning** in plain language.
    2. **Define every variable and symbol**: build a glossary.
    3. **Explain how it connects to the method or claims**: Is it the loss function? The model update rule? A physical constraint? A theoretical bound?
    4. **Identify assumptions or approximations** embedded in the formula.
    5. Use the provided LaTeX source as the canonical representation, but cross-check with any rendered page images if available.

    ## TeX Source — AUXILIARY USE ONLY
    If TeX source is available, read the main `.tex` file **ONLY** for:
    - Understanding narrative structure (what text comes before/after a figure or equation)
    - Reading captions and labels
    - Extracting the precise LaTeX of equations

    **Do NOT perform figure analysis from the TeX source.** Figures must be analyzed by direct visual inspection of the image files.

    Prioritize sections:
    - Introduction (problem motivation)
    - Method section (how the approach works)
    - Experiments section (what results show)
    - Related Work (how authors position their work)

    ## Output
    Write a structured Markdown file to: {output_path}

    Follow the template in templates/PAPER_DEEP_ANALYSIS_TEMPLATE.md.

    Rules:
    - Every figure/table/equation in the manifest MUST be analyzed
    - Use `ReadMediaFile` for each image — do not skip visual inspection
    - Connect each visual element to specific claims in the text
    - Be precise about numbers, methods, and comparisons
    - If an image is unclear or low-quality, note it explicitly
    - Write output in {output_language}. If the language is Chinese, translate section headings, analysis, and commentary into Chinese. Keep paper titles, author names, venue names, BibTeX, file paths, and JSON keys in English.
```

**Synchronization:**

After launching all subagents, monitor active tasks with `TaskList` until all background subagents complete. Then proceed to Step 3.

If a subagent fails (timeout or error), log the failure in the deep analysis manifest and continue. The main table will show "Analysis failed" or omit the link for that paper.

### Step 3: Synthesize
- Group papers by approach/theme
- Identify consensus vs disagreements in the field
- Find gaps that our work could fill
- If Obsidian notes exist, incorporate the user's own insights into the synthesis

### Step 4: Output
Present as a structured literature table:

If `DEEP_ANALYZE = false` (original format):
```
| Paper | Venue | Method | Key Result | Relevance to Us | Source |
|-------|-------|--------|------------|-----------------|--------|
```

If `DEEP_ANALYZE = true` (with deep analysis links):
```
| # | Paper | Venue | Year | Method | Key Result | Relevance | Source | Deep Analysis |
|---|-------|-------|------|--------|------------|-----------|--------|---------------|
| 1 | Paper Title | NeurIPS | 2024 | Transformer | BLEU 28.4 | High | arXiv | [Details](literature-deep/paper_2301.07041/deep_analysis.md) |
```

Plus a narrative summary of the landscape (3-5 paragraphs).

**Language:** All summaries, analysis, and commentary respect `output_language`. Paper titles, author names, venue names, BibTeX, file paths, and JSON keys remain in English regardless of language setting.

If Zotero BibTeX was exported, include a `references.bib` snippet for direct use in paper writing.

### Step 5: Save (if requested)
- Save paper PDFs to `literature/` or `papers/`
- Update related work notes in project memory
- If Obsidian is available, optionally create a literature review note in the vault

**If `DEEP_ANALYZE = true`**, also save the deep analysis manifest:

```json
{
  "topic": "diffusion models",
  "timestamp": "2025-01-15T10:30:00",
  "total_papers_found": 15,
  "deep_analyzed_count": 5,
  "papers": [
    {
      "rank": 1,
      "title": "...",
      "arxiv_id": "2301.07041",
      "deep_analysis_path": "literature-deep/paper_2301.07041/deep_analysis.md",
      "figure_count": 8,
      "table_count": 3,
      "source_type": "tex"
    }
  ]
}
```

Save this to `literature-deep/deep_analysis_manifest.json`.

### Step 6: Update Research Wiki (if active)

**This step is optional and automatic.** Skip entirely if `research-wiki/` does not exist in the project.

```
if research-wiki/ directory exists:
    for each top relevant paper found (up to 8-12):
        1. Generate slug: python3 tools/research_wiki.py slug "<title>" --author "<last>" --year <year>
        2. Create page: research-wiki/papers/<slug>.md with structured schema
           (node_id, title, authors, year, venue, tags, one-line thesis, problem/gap,
            method, key results, limitations, reusable ingredients, open questions)
        3. Add edges to graph/edges.jsonl for relationships to existing wiki papers:
           python3 tools/research_wiki.py add_edge research-wiki/ --from "paper:<slug>" --to "<target>" --type <type> --evidence "<text>"
        4. Update gap_map.md if new gaps are identified
    Rebuild query pack:
        python3 tools/research_wiki.py rebuild_query_pack research-wiki/
    Log:
        python3 tools/research_wiki.py log research-wiki/ "research-lit ingested N papers"
else:
    skip — no wiki, no action, no error
```

## Key Rules
- Always include paper citations (authors, year, venue)
- Distinguish between peer-reviewed and preprints
- Be honest about limitations of each paper
- Note if a paper directly competes with or supports our approach
- **Never fail because a MCP server is not configured** — always fall back gracefully to the next data source
- Zotero/Obsidian tools may have different names depending on how the user configured the MCP server (e.g., `mcp__zotero__search` or `mcp__zotero-mcp__search_items`). Try the most common patterns and adapt.
