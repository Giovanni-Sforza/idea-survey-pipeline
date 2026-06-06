<!--
AXIOM_CANDIDATES_TEMPLATE.md
============================

This template documents the OUTPUT of an `axiom-explorer` subagent
invocation, dispatched from `derivation-refine-loop` Step 3.5.

When a refinement-router decides that a reviewer's CRITICAL issue
targets a tier-1 bridging hypothesis (in v2 these are no longer
sacred — only the §1A / §1B / §1C endpoint declarations are sacred),
it issues a `route: axiom_explore` instruction with one or more
hypothesis IDs to challenge. The axiom-explorer then produces this
file: a structured catalog of K alternative axiom sets, each of which:

  1. preserves the user's source endpoint (§1A) and sink endpoint (§1B)
  2. preserves any required intermediate nodes (§1C)
  3. avoids forbidden detours (§1D)
  4. is grounded in independent literature (NOT the anchor papers,
     same rule as lit-verifier)
  5. comes with a one-line provenance and a one-line predicted impact
     on the final equation

Downstream:
  - Step 3.6 dispatches K parallel sister-derivations, one per
    candidate, using theory-synthesizer Call type J.
  - Step 3.7 dispatches sister-comparator to compare the K sister
    final equations against the main, flagging qualitative
    differences (sign change / parametric-order change / dimension
    change).
  - Promotion to next round is gated by §3.X "AXIOM_AUTO_PROMOTE" in
    derivation-target.md.
-->

# Axiom Candidates — output of axiom-explorer

**Schema version**: `1`

## Header (JSON sidecar mirrors these as top-level fields)

| Field | Type | Value |
|---|---|---|
| `episode_id` | string | e.g. `R2-AE01` — round + axiom-explore index |
| `triggered_by_issue` | string | the CRITICAL issue id (e.g. `R2-I04`) |
| `target_hypothesis_ids` | list[str] | the §3 hypothesis IDs being challenged (e.g. `["A1"]`) |
| `source_endpoint_node` | string | from §1A `node_name` (verbatim, isomorphism anchor) |
| `sink_endpoint_node` | string | from §1B `node_name` (verbatim, isomorphism anchor) |
| `required_intermediates` | list[str] | from §1C (verbatim) |
| `n_candidates_returned` | int | length of `candidates[]` |
| `n_candidates_searched` | int | total candidates considered before isomorphism filtering |
| `wall_clock_minutes` | int | budget used |

## §1. Endpoint isomorphism guard (mandatory)

For every candidate returned, axiom-explorer MUST certify that the
candidate's implied derivation chain passes the isomorphism test:

```
chain_source_class ≡ source_endpoint_node.physical_class  (semantic identity)
chain_sink_class   ≡ sink_endpoint_node.physical_class
every node in required_intermediates appears in the chain
no node belongs to any family listed in forbidden_detours
```

If any candidate fails this guard, it is REJECTED at the explorer
stage and never appears in `candidates[]`. Rejected candidates are
listed in `rejected[]` below with the reason, for audit transparency.

## §2. Per-candidate schema (one block per candidate)

```yaml
candidate_id: "C1"                              # local id within this episode
short_label: "vector-eps2 + Jia second-moment scaling"

# The replacement: a complete axiom set that supersedes the targeted
# tier-1 hypothesis. May change MULTIPLE original hypotheses at once
# if they are entangled (e.g. swapping A1 may force a different A3).
replaces:
  - hypothesis_id: "A1"                         # from spec §3
    old_statement: "rho_2 = C_rho * beta_2"
    new_statement: "<eps_2^2> = a_prime + b_prime * beta_2^2"
    new_latex: "Eq(<eps_2**2>, a_prime + b_prime * beta_2**2)"

# Optional: additional NEW hypotheses introduced by this candidate
adds:
  - new_id: "C1.A_new1"
    statement: "eps_2 is a complex vector aligned with the participant plane"
    latex: "Eq(eps_2_vec, |eps_2| * exp(I * 2 * Phi_2))"

# Endpoint isomorphism certification (mandatory; failing this disqualifies)
isomorphism_check:
  source_endpoint_preserved: true
  sink_endpoint_preserved: true
  required_intermediates_satisfied: ["hydrodynamic_response"]   # if §1C non-empty
  forbidden_detours_avoided: true
  reasoning: "Candidate's chain starts at beta_2 (axisymmetric quadrupole, §1A
    allowed parametrization 'scalar β_2 with random orientation', still in
    the §1A class) and ends at Var(P_z) (§1B allowed instantiation). The
    intermediate ε_2 is reformulated from scalar to complex vector — this
    is an EDGE change, not an endpoint change, so isomorphism holds."

# Literature provenance (NOT from anchor papers — same rule as lit-verifier)
provenance:
  - paper_title: "Probing triaxial deformation of atomic nuclei in high-energy heavy-ion collisions: anisotropic flow"
    first_author: "Jia"
    year: 2021
    arxiv_id: "2106.08768"
    venue: "PRC"
    equation_or_section: "Eq. (5)"
    relevance: "Source of the <eps_2^2> = a' + b' β_2^2 scaling that
      replaces the linear ρ_2 = C_ρ β_2 axiom."
  - paper_title: "Probing triaxial deformation ... cumulant scaling"
    first_author: "Jia"
    year: 2021
    arxiv_id: "2109.00604"
    venue: "PRC"
    equation_or_section: "Eq. (2)"
    relevance: "Provides the linear-order expansion eps_2_vec = eps_0 + p_2 beta_2
      with Euler-angle averaging that the candidate uses to re-derive
      the second moment."

# Predicted impact on the target equation
predicted_impact:
  on_final_equation: "Var(P_z) gains a leading-order β_2^2 dependence
    (instead of being entirely σ_β_2 driven). Specifically:
    Var(P_z) → A_0 + B β_2^2 with B ∝ b'_2."
  qualitative_difference_from_main: true
  difference_category: "parametric_dependence_order"
  # one of: sign_change | parametric_dependence_order |
  #         dimension_change | regime_of_applicability_change |
  #         none_minor_quantitative_only

# Confidence
confidence_score: 0.85                          # in [0, 1]
confidence_basis: "Two independent papers cite this scaling; the
  challenged hypothesis A1 is internally inconsistent under random-
  orientation ensemble (the issue R2-I04 actually flags)."

# What it would take to falsify this candidate (forward-looking)
falsifier: "A paper demonstrating that <eps_2^2> is NOT quadratic in
  β_2 in the spherical-nucleus limit (i.e. b'_2 = 0 to leading order)
  would refute this candidate. None found in this episode."
```

## §3. Rejected-candidates log (for audit)

Each entry: candidate considered but failed the isomorphism guard or
provenance bar.

```yaml
rejected:
  - short_label: "skip ε_2 entirely; map β_2 directly to v_2"
    rejection_reason: "Violates §1C required_intermediate 'hydrodynamic_response'
      because it bypasses the ε_2 → v_2 = k_2 ε_2 step."

  - short_label: "use β_3 (octupole) instead of β_2"
    rejection_reason: "Endpoint violation: §1A disallowed parametrizations
      explicitly excludes β_3."

  - short_label: "phenomenological P_z ∝ exp(-β_2^2 / 2σ²)"
    rejection_reason: "No literature provenance found; would be a
      fresh hypothesis with same confidence as the original A1."
```

## §4. Summary block (for refinement-router consumption)

```json
{
  "schema_version": "1",
  "episode_id": "...",
  "n_candidates_promoted_to_sister_derivation": <int>,
  "candidate_ids_to_run_as_sisters": ["C1", "C2", "C3"],
  "next_step_for_orchestrator": "dispatch_sister_derivations",
  "explorer_verdict": "candidates_found | no_viable_candidates | endpoint_underspecified"
}
```

Possible `explorer_verdict` values:

| Value | Meaning | Consequence in skill |
|---|---|---|
| `candidates_found` | ≥ 1 candidate passes isomorphism + provenance | Step 3.6 runs K sister derivations |
| `no_viable_candidates` | searched literature, nothing passes the bars | Issue is marked `axiom_explore_exhausted`; surfaces to user, no sister stage |
| `endpoint_underspecified` | the §1A or §1B declaration is too loose for isomorphism check to be meaningful | Skill HALTS, asks user to tighten §1A/B |

---

## Output file location

`${ROUND_DIR}/.axiom_explore/${EPISODE_ID}.json` (machine-actionable mirror)
`${ROUND_DIR}/.axiom_explore/${EPISODE_ID}.md`   (human-readable, follows this template)

Both written by the `axiom-explorer` subagent in the same invocation.

---

## Output language

Match `output_language` field of the input. Paper titles / authors /
venues stay in English. LaTeX stays in LaTeX.

---

## Common axiom-explorer pitfalls (read before authoring this output)

| Pitfall | How to avoid |
|---|---|
| Returning a candidate that is "just A1 with different symbol names" | Cosmetic renaming is not an alternative axiom. Require `difference_category != none_minor_quantitative_only`, OR explicit literature provenance showing the renaming reflects a different community convention. |
| Skipping the isomorphism guard "because the candidate looks fine" | The guard is mandatory and machine-checked downstream. A candidate without explicit `isomorphism_check.reasoning` is rejected by Step 3.6. |
| Using anchor papers as provenance | Forbidden, same rule as lit-verifier. Anchor papers are by definition not independent evidence — they are where A1 came from. |
| Returning 10 candidates that are all variations of the same alternative | Cap at `AXIOM_EXPLORE_MAX_CANDIDATES` (default 3); pick the K most-different ones for maximum diagnostic power. The point is to test a SPACE of alternatives, not enumerate it. |
| Inventing fresh phenomenological alternatives without literature support | Same standard as lit-verifier `partial` / `not_found`: if no paper says it, do not propose it as a candidate. Add it to `rejected[]` with reason "no provenance". |
