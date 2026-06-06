# HEP Research Framework: Shared Reference

> This document defines the common orchestration framework for High Energy Physics (HEP) research skills. It abstracts the pipeline structure shared by both phenomenology (hep-ph) and theory (hep-th), so that domain-specific skills can inherit the choreography without duplicating it.
>
> 本文档定义高能物理（HEP）科研 skill 的通用编排框架，抽象了高能唯象（hep-ph）和理论（hep-th）共用的 pipeline 结构，使领域专用 skill 可以继承编排逻辑而不重复。

## Design Philosophy

The original ML skill library assumes:
- Core compute: GPU training (PyTorch/TensorFlow)
- "Experiment": train model → evaluate metric → compare to SOTA
- Results: accuracy/loss curves, ablation tables
- Venues: NeurIPS/ICML/ICLR/CVPR/ACL
- Pilot: small-scale GPU run (30 min–2 hr)

HEP research differs fundamentally:
- **Phenomenology (hep-ph)**: Event generation, cross-section calculation, statistical analysis, comparison with collider data (LHC, FCC, etc.)
- **Theory (hep-th)**: Analytical derivation, formal proof, consistency checks, limiting-case verification
- Both require: deep literature knowledge, rigorous mathematical/physical reasoning, and reproducible calculation chains

## Universal HEP Pipeline (Abstract)

```
/skill:hep-idea-discovery → implement → /skill:hep-calculation-run → /skill:hep-auto-review-loop → /skill:paper-writing (optional)
  ├── Workflow 1 ────────┤         ├─────────── Workflow 2 ─────────────┤ ├── Workflow 3 ──┤
```

This is isomorphic to the ML pipeline, but each stage's meaning is domain-specific:

| Stage | ML Meaning | HEP Pheno Meaning | HEP Theory Meaning |
|-------|-----------|-------------------|-------------------|
| 1. Idea Discovery | Brainstorm + pilot training | Brainstorm + toy MC / analytic estimate | Brainstorm + symmetry/consistency argument |
| 2. Implementation | Write training code | Write calculation scripts / analysis chain | Write derivation notes / formalize arguments |
| 3. Run | Deploy GPU training | Run MC / fitting / numerical integration | Run symbolic checks / limiting cases |
| 4. Review Loop | ML reviewer (experiments, SOTA) | Pheno reviewer (data comparison, systematics) | Theory reviewer (rigor, consistency, novelty) |
| 5. Write | LaTeX paper with results tables | LaTeX paper with plots, limits, significance | LaTeX paper with theorems, proofs, diagrams |

## Key Abstractions

### 1. Compute Environment (`CLAUDE.md` → `HEP_ENV`)

Replace GPU-centric config with HEP-centric config:

```markdown
## HEP Compute Environment
- **type**: local / remote / cluster / cloud
- **tools**: mathematica, python, sympy, form, madgraph, pythia, root
- **cores**: 8
- **memory**: 32GB
- **math_kernel**: /usr/local/bin/math  (Mathematica kernel path)
- **python_env**: conda env `hep-research` (Python 3.11 + sympy + numpy + scipy)
- **code_sync**: rsync / git
```

### 2. "Calculation" Replaces "Experiment"

A HEP "calculation" is the atomic unit of work. Types:

| Calculation Type | Description | Tools | Duration |
|-----------------|-------------|-------|----------|
| **Symbolic** | Derive cross-section, amplitude, or identity | Mathematica, FORM, pen+paper | Hours–days |
| **Numeric** | Integrate, fit, or simulate | Python/C++, MadGraph, Pythia | Minutes–hours |
| **Monte Carlo** | Event generation or MC integration | MadGraph, Sherpa, WHIZARD | Hours–days |
| **Data Analysis** | Compare with experimental data | ROOT, Python + scipy | Hours |
| **Consistency Check** | Verify limits, symmetries, Ward identities | Mathematica, Python | Minutes–hours |
| **Literature Cross-check** | Reproduce known result as sanity check | Any | Minutes–hours |

### 3. "Pilot" Replaces "Pilot Training"

A HEP pilot is a minimal calculation that tests the core idea:

- **Pheno pilot**: Single parameter point, small statistics, simplified model
- **Theory pilot**: Derive the simplest nontrivial case, check limiting behavior
- **Max duration**: 2 hours (same as ML) — but measured in CPU time, not GPU time
- **Budget**: 8 CPU-hours total (parallelizable across cores)

### 4. Results Artifacts

Replace ML artifacts with HEP artifacts:

| ML Artifact | HEP Pheno Artifact | HEP Theory Artifact |
|-------------|-------------------|---------------------|
| `results.json` (metrics) | `results.yaml` / `hist.root` (cross-sections, limits, significances) | `DERIVATION_PACKAGE.md`, `PROOF_PACKAGE.md` |
| `wandb` logs | Custom logging (no standard HEP equivalent) | N/A |
| Learning curves | Kinematic distributions, exclusion plots | N/A |
| Ablations | Systematic variation tables | Limiting-case checks, assumption relaxation |

### 5. Venues

Replace ML venues with HEP venues:

| Type | Venues |
|------|--------|
| **Letters** (fast, 4–6 pages) | Phys. Rev. Lett., Phys. Lett. B |
| **Journals** (full, 10–30+ pages) | Phys. Rev. D, JHEP, EPJC, JCAP, NPB |
| **Reviews** | Phys. Rept., RMP |
| **Preprint** | arXiv (hep-ph, hep-th, hep-ex) |
| **Conferences** | EPS-HEP, ICHEP, LHCP, Moriond |

## Constants (HEP Defaults)

These constants apply across all HEP skills unless overridden:

- **HEP_TYPE = "pheno"** — `"pheno"` or `"theory"`. Controls whether stages default to numeric or symbolic.
- **AUTO_PROCEED = true** — Same semantics as ML pipeline.
- **ARXIV_DOWNLOAD = false** — Same semantics.
- **HUMAN_CHECKPOINT = false** — Same semantics.
- **REVIEWER_DIFFICULTY = medium** — Same semantics.
- **AUTO_WRITE = false** — Same semantics.
- **VENUE = JHEP** — Default target venue.
- **PILOT_MAX_HOURS = 2** — Max CPU time per pilot calculation.
- **PILOT_TIMEOUT_HOURS = 3** — Hard timeout per pilot.
- **MAX_PILOT_IDEAS = 3** — Max parallel pilot calculations.
- **MAX_TOTAL_CPU_HOURS = 8** — Total CPU budget for all pilots.
- **LITERATURE_SOURCES = "arxiv, inspire-hep"** — Primary literature sources for HEP.

## Literature Sources (HEP-Specific)

Replace ML-focused sources with HEP-focused sources:

| Priority | Source | ID | Detection | What it provides |
|----------|--------|----|-----------|-----------------|
| 1 | **INSPIRE-HEP** | `inspire` | WebSearch or direct API | Author profiles, citation graphs, collaboration networks, linked arXiv ID |
| 2 | **arXiv (hep-ph/th/ex)** | `arxiv` | arxiv_fetch.py | Preprints with categories, abstract, author list |
| 3 | **Local PDFs** | `local` | Glob papers/**/*.pdf | User's personal paper collection |
| 4 | **Web search** | `web` | WebSearch | General web + arXiv + Google Scholar |
| 5 | **Zotero** | `zotero` | MCP zotero | User's curated library (if configured) |

### INSPIRE-HEP Query Patterns

```
# Search by topic
https://inspirehep.net/api/literature?q=title:"dark matter"+and+subject:hep-ph

# Search by author
https://inspirehep.net/api/literature?q=author:"S. Weinberg"

# Citation count
https://inspirehep.net/api/literature?q=refersto:recid:XXXXXX

# Recent in category
https://inspirehep.net/api/literature?q=subject:hep-th+and+date:2025--2026
```

De-duplication: INSPIRE record contains `external_system_identifiers` including arXiv ID. Match by arXiv ID first, then by normalized title.

## Review Standards (HEP-Specific)

### Phenomenology Review Criteria

A phenomenology reviewer (Phys. Rev. D / JHEP level) evaluates:

1. **Physics motivation**: Is the problem timely and well-motivated?
2. **Methodological correctness**: Are calculations technically correct?
3. **Experimental relevance**: Is there a clear path to experimental test?
4. **Systematics**: Are uncertainties estimated honestly?
5. **Comparison**: Is the result placed in context of existing work?
6. **Novelty**: Does it add something beyond known results?

### Theory Review Criteria

A theory reviewer (JHEP / NPB / CMP level) evaluates:

1. **Mathematical rigor**: Are definitions precise? Are proofs complete?
2. **Physical consistency**: Does it respect known symmetries/conservation laws?
3. **Novelty**: Is the result new? Is the technique new?
4. **Generality**: Does the result apply broadly or is it overly specialized?
5. **Clarity**: Is the derivation/argument easy to follow?
6. **Significance**: Does it open new directions or solve an important problem?

## Output Protocols (Same as ML)

- **[Output Versioning Protocol](output-versioning.md)**
- **[Output Manifest Protocol](output-manifest.md)**
- **[Output Language Protocol](output-language.md)**

## File Naming Conventions

| Stage | File | Location |
|-------|------|----------|
| Idea discovery | `IDEA_REPORT.md` | `idea-stage/` |
| Calculation plan | `CALCULATION_PLAN.md` | `calc-stage/` |
| Calculation tracker | `CALCULATION_TRACKER.md` | `calc-stage/` |
| Auto review | `AUTO_REVIEW.md` | `review-stage/` |
| Review state | `REVIEW_STATE.json` | `review-stage/` |
| Narrative report | `NARRATIVE_REPORT.md` | Project root |
| Derivation package | `DERIVATION_PACKAGE.md` | Project root |
| Proof package | `PROOF_PACKAGE.md` | Project root |
| Proof audit | `PROOF_AUDIT.md` | Project root |
| Pipeline report | `PIPELINE_REPORT.md` | Project root |

## Key Differences from ML Pipeline

| Aspect | ML | HEP |
|--------|-----|-----|
| Compute unit | GPU | CPU (symbolic) or CPU/GPU (numeric) |
| Experiment duration | Hours–days | Minutes–days (highly variable) |
| Reproducibility | Fixed seed + code | Fixed parameter file + seed + code |
| Error bars | Statistical (std over seeds) | Statistical + systematic |
| Baselines | Prior SOTA methods | Known analytical limits, previous MC results |
| Primary artifacts | Weights, metrics | Formulas, histograms, limits |
| Validation | Hold-out test set | Limiting cases, conservation laws, unitarity |

## Transition Guide for Skill Authors

When porting an ML skill to HEP:

1. Replace all `GPU` references with `CPU` or `compute`.
2. Replace `train`/`fit`/`model` language with `calculate`/`derive`/`simulate`.
3. Replace `accuracy`/`loss`/`F1` with `cross-section`/`significance`/`limit`/`agreement`.
4. Replace ML venues with HEP venues.
5. Replace `wandb` with custom logging or omit.
6. Add theory-specific stages (derivation, proof, consistency check) where relevant.
7. Replace `nvidia-smi` with load/memory checks appropriate to the compute type.

## Composing Skills

```
# Full phenomenology pipeline
/skill:hep-research-pipeline "dark matter at HL-LHC" — type: pheno, venue: PhysRevD

# Full theory pipeline
/skill:hep-research-pipeline "amplitudes in N=4 SYM" — type: theory, venue: JHEP

# Individual skills
/skill:hep-idea-discovery "topic" — type: pheno
/skill:hep-calculation-run "calculation command"
/skill:hep-auto-review-loop "topic" — type: theory, difficulty: hard
/skill:formula-derivation "derive diphoton cross-section"
/skill:proof-checker "verify unitarity proof in paper.tex"
/skill:paper-write "NARRATIVE_REPORT.md" — venue: JHEP
```
