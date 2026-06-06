# Paper Card Schema (`paper_card.json`)

> Compact, machine-readable distillation of a single `deep_analysis.md`.
> Designed to let the report-writer subagents in `idea-landscape`,
> `idea-novelty`, and `idea-feasibility` skip re-reading the full
> per-paper deep analyses.

## Why this file exists

The three idea-survey skills used to feed every `deep_analysis.md`
(50–150 KB each, ×N papers) directly into the report-writer subagent.
That blew the subagent's context window once N grew past 6–8 papers
and forced compaction, which broke cross-paper consistency in the
final report.

Paper cards are the **progressive-disclosure** layer between the
heavy `deep_analysis.md` files and the report-writer:

```
deep_analysis.md (50–150 KB each)
         │
         ▼
  paper_card.json (3–10 KB each)   ←── report-writer reads these by default
         │
         └── points back to deep_analysis.md when truly needed
```

A paper card is the **same paper, but compressed and structured**.
Every field is a small, named slot the report-writer can scan
without scrolling.

## File location

```
literature-deep/
├── paper_arxiv_2301_07041/
│   ├── deep_analysis.md          ← source of truth (large)
│   ├── paper_card.json           ← THIS file (small, derived)
│   ├── figure_manifest.json
│   └── figures/
└── ...
```

One paper card per paper directory, written alongside the existing
`deep_analysis.md`. Card generation is unconditional across all papers
in `literature-deep/` — see "Generation policy" below.

## Generation policy

The shared "Step 4.5: Paper Card Distillation" in each idea-* skill:

1. Enumerates **every** `literature-deep/paper_*/` directory that
   contains a non-empty `deep_analysis.md` — not just the papers
   referenced in this run's synthesis.
2. For each paper, dispatches one `paper-analyzer` subagent that
   reads only that paper's `deep_analysis.md` and writes
   `paper_card.json` next to it.
3. Subagents are launched in parallel under the standard concurrency
   cap (4).
4. If a `paper_card.json` already exists AND its `provenance.deep_analysis_mtime_utc`
   equals the current mtime of `deep_analysis.md` AND its
   `provenance.card_schema_version` matches the current schema version,
   the card is reused (no subagent dispatched for that paper).
   Otherwise the card is regenerated.

The card-generation step never modifies `deep_analysis.md` itself.

## Schema (version 1.1)

The canonical structure. Fields that don't apply to a specific paper
should be `null`, empty string `""`, or empty array `[]` — never
omitted. This keeps the report-writer's JSON access patterns simple.

```json
{
  "schema_version": "1.1",

  "paper_key": "paper_arxiv_2301_07041",

  "metadata": {
    "title": "Full paper title verbatim",
    "authors": ["Author One", "Author Two"],
    "year": 2023,
    "venue": "NeurIPS 2023",
    "arxiv_id": "2301.07041",
    "doi": null,
    "url": "https://arxiv.org/abs/2301.07041"
  },

  "one_line_thesis": "A single declarative sentence: what this paper does and what it shows.",

  "method_summary": "Two to four sentences of prose. Enough for the report-writer to write a paragraph about this paper without opening deep_analysis.md.",

  "core_contributions": [
    "Contribution 1 in one sentence.",
    "Contribution 2 in one sentence."
  ],

  "core_claims": [
    {
      "claim": "A specific, falsifiable statement the paper demonstrates.",
      "category": "Method",
      "evidence_pointer": "Figure 3 + Table 2"
    }
  ],

  "technical_route": {
    "route_label": "Short noun phrase, e.g. 'Per-layer learned sparse-attention gating'",
    "problem_addressed": "One sentence on the problem this route attacks.",
    "method_family": "e.g. 'Mixture-of-experts attention', 'Diffusion model', 'Equivariant GNN'"
  },

  "experimental_setting": {
    "task": "e.g. 'Causal language modeling on long documents'",
    "datasets": ["PG-19", "arXiv-Math"],
    "compute_reported": "8x A100 80GB, 7 days",
    "scale_reported": "1.3B parameters, 300B tokens",
    "code_available": true,
    "data_available": true
  },

  "quantitative_results": [
    {
      "metric": "FID",
      "value": "9.96",
      "setting": "CIFAR-10, DDPM, 1000 steps",
      "is_headline": true,
      "source_in_deep_analysis": "Table 2"
    }
  ],

  "novelty_signals": {
    "specific_mechanism": "What the paper actually does, at the level needed for an exact-delta comparison with another method.",
    "setting_constraints": "Under what conditions the result holds.",
    "what_authors_claim_is_novel": "Verbatim or paraphrased — what the authors themselves frame as their contribution."
  },

  "feasibility_signals": {
    "demonstrated_to_work_when": ["specific setting 1", "specific setting 2"],
    "demonstrated_to_fail_when": ["specific failure mode 1"],
    "reported_failure_modes": ["instabilities, edge cases, etc."],
    "implementation_cost_qualitative": "medium",
    "engineering_complexity_qualitative": "medium"
  },

  "gap_signals": [
    "Verbatim or paraphrased statement from the paper's Limitations / Future Work / Discussion about what is left undone."
  ],

  "limitations_acknowledged": [
    "What the authors themselves admit."
  ],
  "limitations_observed": [
    "What the deep_analysis subagent flagged but the authors did not admit."
  ],

  "key_figures": [
    {
      "figure_id": "fig3",
      "caption_excerpt": "First ~120 chars of the figure caption.",
      "relative_path": "figures/fig3.png",
      "why_matters": "One sentence on which claim or contribution this figure embodies."
    }
  ],

  "key_equations": [
    {
      "equation_id": "eq5",
      "latex": "\\mathcal{L}(\\theta) = \\mathbb{E}_{x,t}[\\|\\epsilon - \\epsilon_\\theta(x_t,t)\\|^2]",
      "what_it_expresses": "Plain-language meaning of the equation.",
      "why_matters": "Which claim this equation supports."
    }
  ],

  "key_tables": [
    {
      "table_id": "tab2",
      "what_compared": "Method A vs Method B vs Ours on CIFAR-10.",
      "headline_numbers": [
        {"row": "Ours", "metric": "FID", "value": "9.96"}
      ]
    }
  ],

  "relevance_at_first_analysis": {
    "topic": "The user_research_topic active when deep_analysis.md was first written (copy verbatim from deep_analysis.md if it records this).",
    "direct_relevance": "Core",
    "reusable_elements": ["model component", "evaluation protocol"],
    "gaps_left_for_user": ["aspects this paper did not address that were relevant to the original user's work"],
    "note": "This block is a snapshot of relevance to the FIRST project that analyzed this paper. Downstream consumers (e.g. report-writer subagents in a different project) MUST re-evaluate relevance against the current project's topic; treat this block as informational only."
  },

  "provenance": {
    "deep_analysis_path": "literature-deep/paper_arxiv_2301_07041/deep_analysis.md",
    "deep_analysis_mtime_utc": "2026-05-22T10:30:00Z",
    "deep_analysis_status": "Completed",
    "card_generated_at_utc": "2026-05-23T08:15:00Z",
    "card_schema_version": "1.1",
    "distiller_notes": "Free-form short notes from the distiller subagent — e.g. 'truncated reading of section 6 due to ReadFile 1000-line cap'."
  }
}
```

## Field-level rules for the distiller subagent

1. **Never fabricate.** If a field can't be supported from `deep_analysis.md`,
   set it to `null` / `""` / `[]`. Half-remembered details are worse
   than empty slots.

2. **Quote sparingly.** `evidence_pointer`, `source_in_deep_analysis`,
   `gap_signals` and `what_authors_claim_is_novel` may contain short
   verbatim phrases (≤25 words). Everything else is paraphrase.

3. **`one_line_thesis` ≤ 1 sentence.** This is what shows up in
   report-writer table cells.

4. **`method_summary` 2–4 sentences.** No math, no figure references.
   Read aloud: it should sound like a paragraph from the report.

5. **`specific_mechanism` is the precision dial.** This is where
   `idea-novelty` will look to write "They do X, you do Y." Be as
   technically specific as the deep_analysis allows. If the deep_analysis
   is itself vague here, mark it `"underspecified in source"` rather
   than guessing.

6. **`technical_route.route_label` should be a noun phrase, not a
   sentence.** It will be used as a table row label by `idea-landscape`.

7. **`relevance_at_first_analysis.topic` is sticky.**
   If `deep_analysis.md` records the topic under which it was
   analyzed (most do, via "Topic:" line under "Relevance to Research
   Topic"), copy that string verbatim. If not, set to `null`. Do
   NOT substitute the current run's user topic — the card is a
   record of what was *first* analyzed, and the relevance block is
   shared across all projects that reuse this card.

8. **`provenance.deep_analysis_mtime_utc`** is read by the main agent
   to decide whether to re-distill. Use the exact mtime of
   `deep_analysis.md` at the time of distillation, in ISO-8601 UTC.

9. **Keep total card size under ~10 KB.** If a card balloons past
   that, the distiller is being too verbose — re-summarize.

10. **Schema version is hard-coded.** Always emit
    `"schema_version": "1.1"` and `"card_schema_version": "1.1"` for
    the current revision. A future schema change must bump this and
    invalidate all existing cards.

## Consumer rules (report-writer subagents)

1. **Read paper cards by default.** Glob
   `literature-deep/paper_*/paper_card.json`, parse them all into memory.
   Even 30 cards is well under 300 KB. Cards may be symlinked into the
   project from a shared `~/aris/papers-pool/` — symlinks resolve
   transparently and require no special handling.

2. **Read `deep_analysis.md` only on demand.** Allowed only when:
   - A specific verbatim quote longer than what's in the card is required,
     OR
   - The card explicitly marks a field as `"underspecified in source"`
     and the report-writer's section requires that detail.
   When this happens, open a single `deep_analysis.md` via `ReadFile`
   with a targeted `line_offset` — do not read the whole file.

3. **Never read `deep_analysis.md` "just to be safe."** If the report
   needs information not in the card, that is a signal to either
   (a) leave a `[NEEDFIX]` marker in the report and continue, or
   (b) request a one-off card-field upgrade for that paper. It is
   NEVER a signal to fall back to reading all deep analyses.

4. **Treat `relevance_at_first_analysis` as a HINT, not ground truth.**
   When the current project's topic differs from
   `relevance_at_first_analysis.topic`, the cached `direct_relevance`,
   `reusable_elements`, and `gaps_left_for_user` may not apply. The
   report-writer is responsible for re-evaluating relevance against
   the current project's topic and writing a fresh assessment in the
   report's "Position of Your Inspiration" / "Relevance" section.
   The cached block is useful as a starting point and as
   cross-project signal (e.g. "this paper was Core for an adjacent
   topic, worth scrutinizing"), but it does NOT pre-decide the
   verdict for the current report. Paper-intrinsic fields
   (`core_claims`, `novelty_signals.specific_mechanism`,
   `quantitative_results`, `feasibility_signals`, `gap_signals`,
   `experimental_setting`, `limitations_*`) ARE project-agnostic and
   should be consumed as-is.

## Out-of-scope

This schema does NOT cover:
- The figure images themselves (those stay under `figures/` and are
  referenced by `relative_path`).
- The full TeX source (still under `*_src/`, used only by
  `research-proposal`'s rigor audit).
- Cross-paper synthesis (routes, gaps, claim assessment) — that
  is the report-writer's job, not the card's.

---

*Schema version 1.1 · introduced 2026-05. Changes from 1.0: renamed
`relevance_to_topic` → `relevance_at_first_analysis` to reflect that
cards may be shared across projects via the paper pool; added
consumer rule 4 on cross-project relevance handling.*
