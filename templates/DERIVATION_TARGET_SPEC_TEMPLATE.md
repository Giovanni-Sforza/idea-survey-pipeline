<!--
DERIVATION_TARGET_SPEC_TEMPLATE.md
==================================

This file is the USER-FILLED entry point for the `analytic-derivation` skill.

When the skill is invoked and `derivation-target.md` does not exist in the
current project, the skill copies this template into place and STOPS, asking
you to fill it in.

Why a separate target-spec instead of a one-line CLI argument?
  Because cross-paper symbolic derivation has more degrees of freedom than a
  prose query can capture: target observable, control parameter, anchor papers,
  user-given bridging hypotheses, physical picture, validity regime, and the
  acceptable forms of the final answer. Putting these on the command line
  guarantees they will be vague; putting them in a structured file forces them
  to be explicit before any compute is spent.

The skill consumes only the sections marked `MUST FILL`. The `OPTIONAL`
sections improve quality (especially the verification step) but are not gating.

──────────────────────────────────────────────────────────────────────────
WHAT IS SACRED IN THIS SPEC (read this carefully — it changed in v2)
──────────────────────────────────────────────────────────────────────────

In v1 of this template, the user-given items in §3 were treated as
INVIOLABLE axioms. Empirical experience (notably the spin-pol-fluctuation
case study) showed that this often locks the harness into the wrong
mechanistic framing of the user's actual research question, because the
correct functional form is exactly what literature reading is supposed to
discover.

In v2, the sacred object is the **causal graph endpoints** declared in §1A
and §1B — i.e. the **classes** of physical quantities being related, not
the specific functional forms that connect them. Concretely:

  PROTECTED (the skill / refine-loop will NEVER auto-revise):
    - §1A source endpoint (the control-parameter CLASS)
    - §1B sink   endpoint (the observable        CLASS)
    - §1C required intermediate nodes (if any)
    - §1D forbidden detours

  REVISABLE (the refine-loop's axiom-explorer may propose alternatives,
             test them with sister-derivations, and if a candidate
             survives, promote it into the next round):
    - §3 initial bridging hypotheses (the EDGES of the graph)
    - all tier-2 / tier-3 assumptions added later

If you really do want §3 treated as sacred (e.g. "I want to see exactly
what falls out of THIS axiom set, not what the literature would have
preferred"), set §3.X "lock_to_user_axiom: true" on the affected row.

Delete every <!-- comment --> line before re-invoking the skill, or just
leave them — the skill ignores HTML comments.
-->

# Derivation Target Spec (v2)

## 1. Research-question definition — MUST FILL

<!-- v2 separates the SACRED endpoint declaration (§1A–§1D) from the
     REVISABLE specific functional forms (§3). See the "WHAT IS SACRED"
     block above. -->

### 1A. Source endpoint (control-parameter CLASS) — MUST FILL

<!-- This is one node of the minimal causal graph the derivation must
     traverse. It is SACRED: the refine-loop's axiom-explorer will reject
     any candidate axiom set that does not start at a quantity of this
     class. -->

- **Node name**: {short identifier, e.g. `nuclear_quadrupole_deformation`}
- **Physical class** (one sentence):
  {e.g. "Ground-state axisymmetric quadrupole deformation of the
   colliding nucleus."}
- **Allowed parametrizations** (what counts as the same class — these are
  all permitted instantiations that the axiom-explorer may swap in):
  - {e.g. "scalar β_2"}
  - {e.g. "β_2 with Euler-angle orientation DOF (vector form)"}
  - {e.g. "β_2 + β_2,γ triaxial parameters"}
  - {e.g. "ground-state shape parameters of the nuclear density profile
     in the standard rotational-invariant expansion"}
- **Disallowed parametrizations** (would change the research question):
  - {e.g. "β_3 (octupole) — a different deformation order"}
  - {e.g. "nuclear charge radius — different physical quantity"}
- **Ontology tag** (machine-readable): `physics/nuclear-structure/deformation/quadrupole`

### 1B. Sink endpoint (observable CLASS) — MUST FILL

<!-- The other end of the causal graph. Also SACRED. -->

- **Node name**: {e.g. `event_variance_of_longitudinal_Lambda_polarization`}
- **Physical class** (one sentence):
  {e.g. "Event-by-event fluctuation of the longitudinal Λ polarization
   in ultra-relativistic heavy-ion collisions."}
- **Allowed statistical functionals** (instantiations the axiom-explorer
  may swap between when refining the derivation):
  - {e.g. "Var(P_z) = <P_z²> - <P_z>²"}
  - {e.g. "<P_z²> (second moment)"}
  - {e.g. "<|P_z(φ_p) sin(2(φ_p-Ψ_2))|²> Fourier-projected second moment"}
- **Disallowed instantiations** (would change the research question):
  - {e.g. "<P_z> alone (just the mean — a different question)"}
  - {e.g. "P_y (a different polarization component)"}
- **Ontology tag** (machine-readable): `physics/heavy-ion/polarization/longitudinal/fluctuation`

### 1C. Required intermediate nodes — OPTIONAL

<!-- If the user insists the derivation must pass through specific
     intermediate physics (e.g. "I want to see hydrodynamic response
     explicitly"), declare them here. The axiom-explorer will reject
     candidates that bypass any required intermediate. -->

- {e.g. "hydrodynamic response v_2 = k_2 · ε_2 (the chain must explicitly
   go through linear hydro response)" — leave empty if you don't want
   to constrain this}

### 1D. Forbidden detours — OPTIONAL

<!-- Physics families to keep out of the chain. -->

- {e.g. "no QED / EM-field contributions to the polarization"}
- {e.g. "no contributions beyond Standard Model"}

### 1E. Target observable — MATH FORM — MUST FILL

<!-- The synthesizer's first SymPy goal. This may be refined later by
     axiom-explorer (e.g. swapped from Var(P_z) to <P_z²> if literature
     suggests it) but must be one of the allowed §1B instantiations. -->

**Math form (LaTeX, single expression on each side of `=`):**
$$
\text{Var}(P_z) \;\equiv\; \langle P_z^2 \rangle - \langle P_z \rangle^2 \;=\; f(\beta_2, \ldots)
$$

**Control parameter (free variable on the RHS):** `beta_2`

**Other variables the answer is allowed to depend on:** `sigma_beta_2`, `C_rho`, …

---

## 2. Anchor papers — MUST FILL

<!-- Provide 2–5 arXiv IDs (preferred), DOIs, or paper titles. The skill will
     reuse `literature-deep/paper_*/` if already present, otherwise download
     and deep-analyze. -->

| # | arXiv ID (or DOI / title) | Suspected role in the derivation chain |
|---|---|---|
| 1 | `arXiv:2106.08768v4` | {e.g. "shockwave model: rho_2 ~ beta_2"} |
| 2 | `arXiv:2109.00604v2` | {e.g. "vorticity from rho_2 + epsilon"} |
| 3 | `arXiv:2411.17285v1` | {e.g. "Pz from omega"} |
| 4 | `arXiv:2509.00796v2` | {e.g. "event-by-event variance machinery"} |

---

## 3. Initial bridging hypotheses (REVISABLE) — MUST FILL

<!-- v2 NAMING CHANGE: these were called "user-given bridging assumptions"
     in v1 and treated as sacred. In v2 they are EDGES of the causal
     graph — initial hypotheses that the refine-loop may propose
     alternatives to, run sister-derivations under, and (if the
     alternative is robustly supported by literature AND survives sister
     comparison) PROMOTE into the next round.

     If you want a specific row treated as sacred (no alternative
     exploration), set its `lock_to_user_axiom` column to `true`. -->

| ID | Statement | LaTeX form | Provenance | lock_to_user_axiom |
|---|---|---|---|---|
| A1 | rho_2 of the shockwave model is proportional to beta_2 | `Eq(rho_2, C_rho * beta_2)` | {paper X eq Y, or "phenomenological"} | false |
| A2 | The shockwave model parameter epsilon is set to zero | `Eq(epsilon, 0)` | {…} | false |
| {A3} | … | … | … | false |

<!-- Provenance hints help the axiom-explorer when it goes looking for
     alternative formulations. If an assumption is "phenomenological", the
     explorer treats it as low-confidence; if it cites a specific paper
     section, the explorer checks whether the paper actually says that
     before proposing alternatives. -->

---

## 4. Physical-picture sketch — MUST FILL

<!-- 2–6 sentences. Describe the chain of physics you expect to traverse, so
     the skill can verify its own chain sketch against your intent in
     Checkpoint #1. NO equations here — just the picture. -->

{e.g. "The colliding nuclei carry a quadrupole deformation beta_2 in their
intrinsic shape. In the shockwave model, this maps onto a quadrupole
modulation rho_2 of the initial deposited energy density. The resulting
fireball generates a longitudinal vorticity component omega_z that is linear
in rho_2 to leading order. Lambda hyperons inherit a polarization Pz
proportional to omega_z (spin-vorticity coupling). When beta_2 itself
fluctuates event-to-event around zero (or some mean), Pz fluctuates with it,
and the fluctuation <Pz^2>-<Pz>^2 carries an analytic signature of the
beta_2 distribution."}

---

## 5. Validity regime — MUST FILL

<!-- Under what conditions should the answer be expected to hold? -->

- Collision system: {e.g. "Au+Au or U+U at sqrt(s_NN) >= 200 GeV"}
- Centrality window: {e.g. "0–10% central, where rho_2 is the dominant initial-state geometric anisotropy"}
- Approximation order: {e.g. "Leading order in beta_2 — series expansion to 4th order is acceptable"}
- Assumed distribution of beta_2 (if any): {e.g. "Gaussian about a mean beta_2^0 with width sigma_beta_2"}

---

## 6. Desired form of the final answer — MUST FILL

<!-- Tells the synthesizer when it is "done". Allowed values are listed in the
     skill's Constants section. -->

- **Form:** `closed_form_polynomial` / `closed_form_series_in_beta2` / `closed_form_with_named_constants` / `numerical_estimate_only`
- **Smallest acceptable retention order in beta_2:** {e.g. "2 (so beta_2^2 term must appear)"}
- **Named constants the final answer may invoke without further derivation:** {e.g. "C_rho (the shockwave proportionality), kappa_pol (the spin-vorticity coupling), tau_fb (fireball lifetime)"}

---

## 7. Verification budget — OPTIONAL (defaults applied if omitted)

<!-- Controls the Step 4b literature verification stage AND the
     axiom-explorer stage in derivation-refine-loop. -->

- Maximum number of unverified equations to web-search per run: `LIT_VERIFY_MAX` (default `6`)
- Concurrency cap for `lit-verifier` subagents: `LIT_VERIFY_CONCURRENCY` (default `3`)
- Skip literature verification entirely and trust the anchor papers only: `false`
- Maximum number of axiom-explorer candidates per refine round: `AXIOM_EXPLORE_MAX_CANDIDATES` (default `3`)
- Maximum number of sister derivations to run per axiom-explore episode: `SISTER_DERIVATION_MAX` (default `3`)
- Auto-promote a sister candidate to next round if (a) it survives SymPy, (b) qualitative agreement with main, AND (c) at least 2 independent papers confirm it: `AXIOM_AUTO_PROMOTE` (default `false`; safer to surface and let the human pick)

---

## 8. Known landmines — OPTIONAL but recommended

<!-- Help the synthesizer NOT chase the wrong rabbit hole. -->

- Confusable terminology: {e.g. "rho_2 (shockwave) is NOT the same object as
  the elliptic flow coefficient v_2; do not substitute them."}
- Papers to avoid quoting: {e.g. "any paper that uses 'beta_2' for the EM
  field tilt angle in QED vacuum birefringence — different physics."}
- Known wrong intuitions to skip: {e.g. "Naive guess `<Pz^2>-<Pz>^2 ∝ beta_2^4`
  is what the chain reduces to under specific assumptions A1+A2; do not also
  pull in a separate v_2^2 factor."}

---

## 9. Acceptance criteria — OPTIONAL but recommended

<!-- The `hep-theory-reviewer` subagent will check these at the verification
     step. Each criterion must be falsifiable. -->

- [ ] Dimensional analysis: `[Var(P_z)] == 1` (Pz is dimensionless)
- [ ] Limit `beta_2 -> 0` gives `Var(P_z) -> 0` (assuming beta_2 is the only
      source of fluctuation, i.e. sigma_beta_2 plays no independent role)
- [ ] Magnitude estimate at `beta_2 ~ 0.3` (Au-like) lands within an order
      of magnitude of {e.g. "STAR's measured Lambda Pz variance"}
- [ ] Result respects parity / time-reversal as expected for `<Pz>` (i.e. odd
      under parity if Pz is longitudinal w.r.t. beam axis)

---

<!-- END OF TEMPLATE. The skill will not start until at least sections
     1A–1B, 1E, 2, 3, 4, 5, 6 are non-default. Run:

         /skill:analytic-derivation "derive <Pz^2>-<Pz>^2 from beta_2"

     after filling this file in. -->
