# Case Study: Spin Polarization Variance vs. β₂

This document maps our hand-driven four-round refinement of the
$\Var(P_z)$ derivation onto the formal structure of
`/skill:derivation-refine-loop`. It serves three purposes:

1. **Empirical anchor**: validates that 4 rounds × 4 reviewer roles is
   the right default — that is exactly the sequence that a senior
   physicist drove on this derivation.
2. **Regression test**: future changes to the skill can be replayed
   against this case study to check that the loop still converges
   on the same answer.
3. **Teaching aid**: shows the user what a "good run" looks like.

The original derivation lives at:
`analytic-derivation/derive-spin-polarization-fluctuation-as-function-of-beta-2-0524-1616/`

The target observable is
$\Var(P_z) \equiv \langle P_z^2 \rangle - \langle P_z \rangle^2$
as a function of $\beta_2$.

The anchor papers are arXiv:2106.08768, 2109.00604, 2411.17285,
2509.00796.

---

## Round 0 — baseline (the analytic-derivation output)

The original derivation, before any refinement, produced
$$
\Var(P_z) \;=\; C_\rho^2 \alpha^2 \sigma_{\beta_2}^2,
$$
a result that depends on a hypothetical Gaussian fluctuation of
$\beta_2$ rather than on the deformation itself. This is the
input the loop consumes.

---

## Round 1 — recover the Glauber scaling

| Reviewer role | Issues raised |
|---|---|
| `physics` | **CRITICAL (×3)**: A3 wrong ensemble (β₂ as random); A1 wrong mapping ($ρ_2$ as deterministic function of $β_2$); A4 oversimplification ($P_z = α ω_z$ is a scalar approximation that hides the $\sin(2\phi_p)$ structure). |
| `physics` | **CRITICAL**: A2 sets $ε = 0$ but the two $ε$'s in the chain are distinct objects (Glauber vs. blast-wave). |
| `literature` | **MAJOR**: Missing the canonical $\langle ε_2^2 \rangle = a' + b' β_2^2$ scaling from Jia 2106.08768. |
| `rigor` | (clean — there's no algebra to audit yet because the chain is too short.) |
| `adversarial` | (clean — the original target form is too restrictive to admit alternative diagnostics.) |

| Router routing (v2) | |
|---|---|
| `route: axiom_explore` | A1, A3 → dispatched to axiom-explorer (Step 3.5); literature search returns Jia's $\langle ε_2^2 \rangle = a' + b' β_2^2$ as a candidate alternative axiom. Sister-derivation (Step 3.6) under the candidate gives the qualitatively-different $\Var(P_z) = A_0 + B β_2^2$. Sister-comparator (Step 3.7) marks `main_axiom_suspect`, surfaces (or, in `— axiom-auto-promote: true` mode, promotes) the candidate into round 2's main derivation. |
| `route: expansion` | Add Jia's $\langle ε_2^2 \rangle$ scaling as a new derivation chain step (this is the path taken in round 2 once the alternative axiom is promoted). |
| `route: alg` | Re-derive $P_z$ from $P^z(\phi_p)$ via Fourier projection, not as a scalar substitution. |

> **v1 vs v2 note**: In v1 this round routed A1, A3 to `route: scope`
> with a `user_axiom_locked` flag — the harness recognised the problem
> but had no machinery to do anything about it, so the loop locked
> and required human intervention. v2 replaces that route with
> `axiom_explore`, which is the closest analog of what a human
> advisor does: "OK, the literature has a standard formulation that
> differs from your A1 — let me show you what the answer would be
> under that alternative, and you can decide whether to switch."

**Outcome** (in v2 with `— axiom-auto-promote: true`):

The axiom-explore episode `R1-AE01` returned 3 candidates with
provenance from Jia 2106.08768 / 2109.00604; the
`vector-eps2 + Jia second-moment scaling` candidate (C1) ran a
successful sister-derivation; sister-comparator marked
`overall_verdict: main_axiom_suspect` with
`category_histogram[parametric_dependence_order] == 2 of 3 sisters`,
and since two independent provenance papers cited the alternative,
the auto-promote gate fired. Call-H (Step 5) consumed
`.pending_promotions.jsonl` and replaced A1 + A3 with the candidate's
`replaces[]` / `adds[]` edits in the round-1 master script. The
chain went from
$\beta_2 \to^{A1} \rho_2 \to^{A4} P_z$
to
$\beta_2 \to^{Jia} \langle ε_2^2 \rangle \to^{k_2} \langle v_2^2 \rangle \to^{BW} \langle \rho_2^2 \rangle \to^{BW} \langle (P_z^{evt})^2 \rangle$,
yielding
$$
\Var(P_z) \;=\; \tfrac{1}{2}(K_{BW}^{(\rho)} C_\rho)^2 (a'_2 + b'_2 \beta_2^2).
$$

Convergence: not yet. Router reports `new_fatal=0`, `new_critical=4`,
`endpoint_violation_count=0`, `open_axiom_explore_count=0` (the
single axiom-explore episode was actioned by Call H in the same
round, so it does not stay open) → continue.

**Outcome** (in v2 with default `— axiom-auto-promote: false`):

The axiom-explore episode runs identically, sister-comparator
returns the same verdict, but the recommendation is
`surface_to_user_with_top_alternative` instead of auto-promotion.
The loop's convergence-state writeout sets
`convergence_headline = paused_pending_axiom_review` and stops
after round 1. The user reviews §7 of the audit, decides whether
to accept C1, and re-invokes the loop either with
`— axiom-auto-promote: true` to let it proceed automatically, or
edits §3 of `derivation-target.md` by hand and resumes. The
remainder of this case study assumes the auto-promote path so the
loop proceeds end-to-end without user intervention.

---

## Round 2 — clean up the mean/fluctuation conflation

| Reviewer role | Issues raised |
|---|---|
| `rigor` | **CRITICAL**: $\rho_2$ vs. $\delta\rho_2$ mixed. Constant offset $\bar\rho_2$ is dropped without splitting. |
| `rigor` | **CRITICAL**: $\rho_2$ used as real scalar in some steps, then promoted to $\Re[\rho_2 e^{-i2\Psi_2}]$ — implicit real→complex bait-and-switch. |
| `physics` | **CRITICAL**: The $\tfrac{1}{2}$ factor assumes zero-mean isotropic complex variable, but at non-central centrality $\langle ε_2 \rangle \neq 0$. |
| `literature` | (clean — Jia scaling now properly cited.) |
| `adversarial` | (clean — wait for round 3.) |

| Router routing (v2) | |
|---|---|
| `route: alg` | Promote $\rho_2$ to a complex vector $\vec\rho_2 = C_\rho \vec\eps_2 + \rho_{\rm off} e^{i2\Psi_{\rm RP}}$; carry the offset to the end and show it drops only in $\Var$. |
| `route: scope` | Tighten the Var formula's validity: introduce $a'_{\rm var} = a'_2 - \bar\eps_{2,\rm RP}^2$ as the spherical-limit variance; reduce to $a'_2$ in UCC. |

> **Why no `axiom_explore` this round**: these CRITICALs target the
> *derivation chain itself* (how $\rho_2$ is propagated through the
> Fourier projection), not a tier-1 bridging hypothesis from §3.
> The router correctly routes them to `alg`/`scope`, the standard
> v1+v2 fixers. v2's axiom-routing rule only fires when the issue
> targets a tier-1 hypothesis AND is CRITICAL/FATAL.

**Outcome**: Round 2 yields the version that survives the
mean/fluctuation cleanup:
$$
\Var(P_z) \;=\; \tfrac{1}{2}(K_{BW}^{(\rho)} C_\rho)^2 (a'_{\rm var} + b'_2 \beta_2^2),
$$
with $\langle P_z \rangle$ explicitly containing three constants
($K_{BW}^{(\rho)} C_\rho \bar\eps_{2,RP}, K_{BW}^{(\rho)} \rho_{\rm off}, P_{\rm off}$).

Convergence: not yet. Router reports `new_fatal=0, new_critical=3,
endpoint_violation_count=0, open_axiom_explore_count=0` → continue.

---

## Round 3 — flag the linearisation and the single-channel attribution

| Reviewer role | Issues raised |
|---|---|
| `rigor` | **MAJOR**: $\rho_2 = C_\rho \eps_2$ is only leading-order; $\mathcal{O}(\eps_2^2)$ corrections induce $\beta_2^4$ in Var. Not flagged. |
| `physics` | **CRITICAL**: $P_z$ is treated as if $\eps_2$-driven only. In reality $\omega_z$ receives hot-spot, longitudinal-rapidity, initial-shear contributions. The "direct probe" claim is overstated. |
| `adversarial` | **MAJOR**: There is a free universality ratio. $\Var(P_z)/\langle v_2^2\rangle$ has the deformation dependence cancelled. Propose this as a separate observable. |
| `literature` | (clean — but flags `route: lit` for "hot-spot ω_z contributions" claim, which round 4 will verify.) |

| Router routing (v2) | |
|---|---|
| `route: scope` | Soften "direct probe" → "leading-order $\beta_2$-sensitive contribution"; note $\Var(P_z)$ is the $\eps_2$ channel only. |
| `route: expansion` | Add multi-channel decomposition section; explicitly show $B \propto b'_2$ is unmodified by other channels. |
| `route: expansion` | Add ratio observable $R_P$ to the experimental-extraction section. |
| `route: ignore` | NLO correction paragraph kept but soft. |

> **Why no `axiom_explore` this round**: the physics CRITICAL is a
> SCOPE issue ("the claim is overstated; the model only captures one
> channel"), not an attack on a tier-1 hypothesis. The router
> correctly routes it to `scope`, which weakens the claim wording
> without challenging the underlying axiom set. Compare with Round 1:
> there, the physics CRITICAL said "the axiom itself is wrong" → that
> routes to `axiom_explore`. Here it says "the axiom is fine but the
> conclusion overclaims" → that routes to `scope`.

**Outcome**: Round 3 adds the multi-channel formula
$\Var(P_z) \approx \sum_n \tfrac{1}{2}(K_n C_n)^2 \langle|\delta\vec\eps_n|^2\rangle + \Var(P_z)|_{\rm non-eps}$
and introduces the ratio observable $R_P = (K_{BW}^{(\rho)} C_\rho)^2/(2 k_2^2)$.

Convergence: not yet. Router reports `new_fatal=0, new_critical=1,
new_major=2, endpoint_violation_count=0, open_axiom_explore_count=0`
→ continue.

---

## Round 4 — fix the NLO dimensional inconsistency, weaken $\delta_{mn}$, push $R_P$

| Reviewer role | Issues raised |
|---|---|
| `rigor` | **MINOR**: The NLO $\beta_2^4$ estimate $\sim \lambda^2 k_2^2 C_\rho^2 b'_2 \beta_2^2$ is dimensionally inconsistent. Should be $b'_2^2$, not $b'_2$. |
| `physics` | **MAJOR**: $\langle\delta\eps_m \delta\eps_n^*\rangle \propto \delta_{mn}$ is too strong; nonlinear couplings like $\eps_4 \supset \chi_{4,22}\eps_2^2$ produce residual mixed terms. |
| `adversarial` | **OBSERVATION**: Substituting $C_\rho \propto k_2$ into $R_P$ cancels $k_2$ entirely. $R_P$ becomes a pure freeze-out quantity, sharper universality prediction. |
| `literature` | (verified the $\chi_{4,22}$ claim via lit-verifier search — `confirmed` against Bhalerao et al.) |

| Router routing (v2) | |
|---|---|
| `route: scope` | Drop the bogus numerical estimate, write "subleading $\mathcal{O}(\beta_2^4)$ corrections with coefficient controlled jointly by $(b'_2)^2$ and unknown blast-wave non-linear couplings; neglected throughout". |
| `route: scope` | Weaken $\delta_{mn}$ to "approximately, with residual mixed contributions explicitly noted". |
| `route: expansion` | Re-derive $R_P$ with $C_\rho = (2R/\beta_T)(N_{v0}/N_{v2}) k_2$ substituted; show $k_2$ cancels; reduce $R_P$ to $\tfrac{1}{2}(K_{BW}^{(\rho)})^2 (2R/\beta_T)^2 (N_{v0}/N_{v2})^2$ as a universality prediction. |

> **Why no `axiom_explore` this round either**: rigor MINOR is a
> dimensional bug, physics MAJOR is a wording tightening, adversarial
> OBSERVATION is a derivation extension. None of them say "the axiom
> set itself is wrong" — they say "the chain built ON TOP of the
> axiom set has problems X, Y, Z". Standard `alg`/`scope`/`expansion`
> routes handle these.

**Outcome**: Round 4 yields the final form. The new $R_P$ formula is
verified by SymPy as $k_2$-independent.

Convergence: **yes**. Router reports `new_fatal=0, new_critical=0,
new_major=0, endpoint_violation_count=0, open_axiom_explore_count=0`
(the round-4 MAJOR was demoted to MINOR during routing because the
literature reviewer's `lit_check` confirmed the underlying claim).
The single axiom-explore episode from round 1 was actioned and
closed; there are no episodes from later rounds. All four
convergence conditions hold → `convergence_recommendation: "stop"`,
`convergence_headline: "converged"`. Loop exits.

---

## How this maps to the skill's defaults

Empirical observations from this case study informed the skill's
defaults:

| Setting | Value | Justification |
|---|---|---|
| `MAX_ROUNDS = 4` | 4 | This case converged at round 4 with no earlier signal of saturation. |
| `REVIEWER_ROLES = [rigor, physics, literature, adversarial]` | all four | All four roles caught distinct issues; removing any one would have missed at least one class. |
| `LIT_VERIFY_BUDGET_PER_ROUND = 3` | 3 | Only one round (4) actually needed a lit-verifier; budget of 3 leaves headroom for harder derivations. |
| `CONVERGENCE_DELTA = 0` | 0 | A single re-stated CRITICAL would have signalled that round 3's adversarial expansion was incompletely absorbed; we wanted strict zero. |
| `AXIOM_EXPLORE_BUDGET = 2` (v2) | 2 | Round 1 triggered exactly 1 axiom-explore episode covering A1+A3 (entangled). Budget of 2 leaves headroom; raising it without need wastes the most expensive route. |
| `SISTER_DERIVATION_MAX = 3` (v2) | 3 | Three sister candidates were sufficient diagnostic power on this case: one in `parametric_dependence_order`, one in `regime_of_applicability_change`, one in `chain_incompatible_with_candidate`. |
| `AXIOM_AUTO_PROMOTE = false` (v2 default) | depends on use | With `false` (default, safest), Round 1 in v2 pauses with `paused_pending_axiom_review` and the user actions the promotion manually. With `true` (unattended), Round 1 auto-promotes and the loop reaches the same Round 4 convergence as v1. The case study above assumes `true` for clarity; switch to `false` for production / publication-quality runs. |
| Issue heat map | rigor=6, physics=6, literature=3, adversarial=3 | balanced; no role dominates. |

---

## Files generated by a hypothetical replay

Were the user to run

```bash
/skill:derivation-refine-loop \
    "analytic-derivation/derive-spin-polarization-fluctuation-as-function-of-beta-2-0524-1616"
```

the on-disk layout would be:

```
analytic-derivation/derive-spin-polarization-fluctuation-as-function-of-beta-2-0524-1616/
├── derivation-report.md          ← original analytic-derivation output (unchanged)
├── derivation_trace.json         ← original (unchanged)
├── derivation_steps.md           ← original (unchanged)
├── derivation_script.json
├── assumption_ladder.md
├── notation_table.md
├── verification_report.md
├── cards/
├── verification/
└── refine/
    ├── convergence_state.json     ← rounds: [], converged: true after run
    ├── refinement_audit.md         ← final consolidated audit
    ├── current → round_4/          ← symlink advances each round
    ├── round_0/                    ← symlinks to original artifacts
    ├── round_1/
    │   ├── reviews/
    │   │   ├── rigor_review.{md,json}
    │   │   ├── physics_review.{md,json}
    │   │   ├── literature_review.{md,json}
    │   │   └── adversarial_review.{md,json}
    │   ├── router_decision.{md,json}
    │   ├── .fixer_outputs/
    │   │   ├── R1-I01_{script,trace,fix}.json
    │   │   ├── R1-I02_lit_check.json
    │   │   └── ...
    │   ├── derivation_script.json   ← Call H output
    │   ├── derivation_trace.json
    │   ├── derivation_steps.md
    │   ├── assumption_ladder.{md,json}
    │   ├── verification/
    │   └── refinement_audit_round.md
    ├── round_2/  ... (same structure)
    ├── round_3/  ... (same structure)
    └── round_4/  ← final round; convergence reached
```

In v2 with `— axiom-auto-promote: true`, `round_1/` additionally contains:

```
round_1/
├── .axiom_explore/
│   ├── R1-AE01_input.json         ← payload prepared by Step 3.5 inline Python
│   ├── R1-AE01.json               ← axiom-explorer output (3 candidates)
│   ├── R1-AE01.md                 ← human-readable; follows AXIOM_CANDIDATES_TEMPLATE.md
│   ├── R1-AE01_comparison.json    ← sister-comparator verdict
│   ├── R1-AE01_comparison.md
│   └── .pending_promotions.jsonl  ← consumed by Call H
├── .sister_outputs/
│   ├── R1-AE01_C1_script.json     ← per-sister; Call J
│   ├── R1-AE01_C1_trace.json
│   ├── R1-AE01_C1_sister.md
│   ├── R1-AE01_C2_{script,trace,sister}.*
│   └── R1-AE01_C3_{script,trace,sister}.*    (this one failed → chain_incompatible_with_candidate)
└── (other v1-shared files: reviews/, .fixer_outputs/, etc.)
```

Total wall-clock estimate for kimi:
- 4 rounds × (4 reviewers × ~10 min + router ~5 min + ~3 fixers × ~15 min + merge ~10 min)
- ≈ 4 × (40 + 5 + 45 + 10) = 4 × 100 = ~7 hours.

The skill is designed for overnight runs; the user starts it before
sleeping and reviews the round-by-round audit in the morning.

---

## What this case study does NOT prove

- It does not prove the loop converges for every derivation. Some
  derivations may oscillate or hit `MAX_ROUNDS` without convergence.
  For those, the `halt_for_human` path is the safety net.
- It does not prove four reviewer roles are necessary for every
  derivation. For shorter / simpler derivations, two roles
  (`rigor + physics`) may suffice; the user can override via
  `— reviewers: rigor,physics`.
- It does not prove the chosen reviewer roles are exhaustive. Future
  reviewer roles (e.g. `numerical-magnitude`, `experimental-feasibility`)
  may be added as the framework grows. The current four were chosen
  based on the empirical error classes seen here.

---

*This case study can be regenerated as a regression test once the
skill is fully implemented: re-run the loop on the same input and
diff `refine/refinement_audit.md` against the snapshot stored here.*
