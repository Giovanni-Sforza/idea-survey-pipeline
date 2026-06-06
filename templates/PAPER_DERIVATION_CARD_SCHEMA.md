# Paper Derivation Card Schema (`derivation_card.json`)

> A compact, machine-readable distillation of how one anchor paper
> contributes to a SPECIFIC target derivation. Extends `paper_card.json`
> (see [PAPER_CARD_SCHEMA.md](PAPER_CARD_SCHEMA.md)) with derivation-chain
> bookkeeping fields.

## Why a separate schema?

`paper_card.json` is **topic-agnostic**: it records "what this paper says,
generically". The `analytic-derivation` skill needs an additional layer:
"what this paper contributes to the chain `beta_2 -> ... -> Var(P_z)`".

Concretely, the report-writer and the `theory-synthesizer` subagent need to
know, per paper:

1. Which equations in this paper are CANDIDATE input / intermediate / output
   nodes of the target derivation chain.
2. Under what regime / approximation those equations hold (so the assumption
   ladder is honest).
3. How this paper's notation maps to the chosen unified notation (so steps
   can be assembled without symbol clashes).
4. Which formulas the subagent flagged as "non-trivial enough that we should
   independently verify them via literature search" (Step 4b in SKILL.md).

`paper_card.json` will still be produced for every anchor paper (so other
skills can reuse it). `derivation_card.json` lives **alongside** it inside
the per-run output directory `analytic-derivation/<run_slug>/cards/` —
NOT inside `literature-deep/paper_*/`, because cards are run-specific
(they depend on the chosen target observable).

## File location

```
analytic-derivation/<run_slug>/
├── derivation-target.md             ← user-filled
├── cards/
│   ├── paper_arxiv_2106_08768.json  ← THIS file
│   ├── paper_arxiv_2109_00604.json
│   └── ...
├── chain_sketch.md                  ← Step 2 output
├── notation_table.{md,json}         ← Step 3 output
├── assumption_ladder.{md,json}      ← Step 4 output (post Step 4b verification)
├── verification/                    ← Step 4b per-item subagent outputs
│   ├── lit_check_{item_id}.json
│   └── ...
├── derivation_script.json           ← Step 5 input to symbolic_derive.py
├── derivation_trace.json            ← Step 5 output from symbolic_derive.py
├── derivation_steps.md              ← Step 5 prose
├── verification_report.md           ← Step 6 hep-theory-reviewer output
└── derivation-report.md             ← Step 7 final report
```

## Schema (version 1)

```json
{
  "schema_version": "1",
  "card_kind": "derivation_card",

  "paper_key": "paper_arxiv_2106_08768",
  "paper_card_path": "literature-deep/paper_arxiv_2106_08768/paper_card.json",

  "metadata": {
    "title": "Verbatim paper title",
    "first_author": "Surname",
    "year": 2021,
    "venue": "Phys. Rev. C",
    "arxiv_id": "2106.08768",
    "url": "https://arxiv.org/abs/2106.08768"
  },

  "role_in_target_chain": {
    "expected_role": "input | intermediate | output | bridging_assumption | sanity_anchor",
    "expected_role_confidence": "high | medium | low",
    "what_chain_segment_it_covers": "One sentence, e.g. 'maps the shockwave parameter rho_2 onto the initial-state quadrupole deformation beta_2.'",
    "alternative_role_if_chain_changes": "One sentence."
  },

  "candidate_equations": [
    {
      "local_eq_id": "this_paper_eq3",
      "deep_analysis_anchor": "Equation 3 in deep_analysis.md",
      "latex_verbatim": "\\rho_2 = c_\\rho \\beta_2 + O(\\beta_2^2)",
      "what_it_expresses": "Leading-order proportionality of shockwave rho_2 to nuclear deformation.",
      "role_in_chain": "bridging_assumption",
      "inputs":  ["beta_2"],
      "outputs": ["rho_2"],
      "validity_regime": "Small beta_2; ignores higher harmonics; central collisions only.",
      "approximations_used": ["linearization in beta_2", "neglect of rho_3"],
      "confidence_in_extraction": "high | medium | low",
      "needs_independent_verification": false,
      "verification_reason": null
    }
  ],

  "notation_local_to_paper": [
    {
      "local_symbol": "\\rho_2",
      "physical_meaning": "Quadrupole modulation of initial entropy density.",
      "proposed_unified_symbol": "rho_2",
      "clash_warning": "Other anchor papers may use rho_2 for the matter density 2-point function. Disambiguate before substitution."
    }
  ],

  "stated_assumptions": [
    {
      "assumption": "Boost-invariant longitudinal expansion (Bjorken).",
      "source_in_paper": "§2, just before Eq.(1).",
      "consequences_for_chain": "Pz_long depends only on transverse coordinates.",
      "confidence_in_extraction": "high"
    }
  ],

  "limiting_cases_demonstrated": [
    {
      "case": "beta_2 -> 0",
      "stated_result": "rho_2 -> 0 (trivially)",
      "where_in_paper": "§3 last paragraph"
    }
  ],

  "numerical_anchors": [
    {
      "quantity": "rho_2 at beta_2 = 0.28 (Au)",
      "value": "~0.06",
      "where_in_paper": "Figure 4 caption",
      "use_in_chain": "magnitude sanity-check for Step 6 verification"
    }
  ],

  "items_for_literature_verification": [
    {
      "item_id": "verify_rho2_beta2_proportionality",
      "claim": "rho_2 = c_rho * beta_2 to leading order, with c_rho ~ 0.2 for Au+Au at top RHIC energy.",
      "why_uncertain": "Paper states this without derivation; cites a 2018 review for the c_rho value.",
      "suggested_search_terms": [
        "shockwave rho_2 nuclear deformation beta_2",
        "Glauber initial-state quadrupole deformation Au+Au",
        "proportionality coefficient initial eccentricity beta_2"
      ],
      "what_would_count_as_confirmation": "At least one independent paper (different first author, different year) that states either the same proportionality or the same numerical value for c_rho.",
      "what_would_count_as_refutation": "A paper showing the relation is non-linear in the relevant beta_2 range, OR that c_rho has the opposite sign."
    }
  ],

  "provenance": {
    "extracted_from": "literature-deep/paper_arxiv_2106_08768/deep_analysis.md",
    "extracted_at_utc": "2026-05-24T08:15:00Z",
    "derivation_target_spec_hash": "sha256:...",
    "extractor_subagent": "theory-synthesizer",
    "card_schema_version": "1"
  }
}
```

## Field-level rules for the `theory-synthesizer` subagent

1. **`candidate_equations[].latex_verbatim` must be byte-for-byte from the
   paper.** If the LaTeX is reconstructed from a figure caption or printed
   image (no TeX source), set `confidence_in_extraction: "medium"` and add
   the equation to `items_for_literature_verification` with reason
   `"latex_reconstructed_from_image"`.

2. **`needs_independent_verification` defaults to `false`.** Flip to `true`
   when the equation:
   - Is presented in the paper without proof and with a vague citation
     (e.g. "as is well known", "see Ref. [12]"), OR
   - Looks like a curve fit rather than a derivation, OR
   - Couples two quantities that the paper's own validity regime does
     not unambiguously cover (e.g. extrapolation beyond the cited window).
   Every such equation MUST get a corresponding entry in
   `items_for_literature_verification`.

3. **`items_for_literature_verification[].claim` is the atomic, falsifiable
   statement to be checked.** It must be readable as a search query
   target, not as a paragraph. The Step 4b `lit-verifier` subagent will
   take this claim plus `suggested_search_terms` and run arxiv +
   Semantic Scholar + web search; it MUST be able to render YES /
   PARTIAL / NO from independent literature.

4. **`role_in_chain` for each candidate equation is what the
   chain-sketch step will consume.** Reserve `output` for equations that
   could plausibly BE the target observable's analytic form (rare; usually
   no anchor paper has it explicitly — that's the whole reason we're
   deriving). Most equations are `input` or `intermediate`.

5. **Maximum recommended size: ~15 KB per card.** If the paper contributes
   more than ~10 candidate equations, restrict to those most likely on the
   target chain — others can be added later by a re-run if needed.

6. **The card never invents content not in `deep_analysis.md`.** When the
   deep analysis genuinely does not say something the synthesizer wishes it
   said, the synthesizer either (a) flags it in
   `items_for_literature_verification` with reason
   `"not_in_deep_analysis"` so Step 4b can patch it, or (b) marks the
   field as `null`. The synthesizer NEVER falls back to its own model
   knowledge to fill the field silently.

## Consumer rules

- **`theory-synthesizer` (Step 3 — notation table):** reads all cards'
  `notation_local_to_paper[]`, merges, surfaces clashes.
- **`theory-synthesizer` (Step 4a — assumption ladder):** reads all cards'
  `stated_assumptions[]`, adds the user-supplied bridging assumptions,
  and produces the ladder.
- **`lit-verifier` (Step 4b — literature verification):** reads
  `items_for_literature_verification[]` ONLY (not the rest of the card).
- **`theory-synthesizer` (Step 5 — derivation script):** consumes
  `candidate_equations[]` and the unified notation table to build the
  `symbolic_derive.py` input JSON.
- **Report-writer (Step 7):** reads the whole card for the "Per-paper
  contribution" section of the final report.

---

*Schema version 1 · introduced 2026-05.*
