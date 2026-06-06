# HEP Venues: Journal and Conference Reference

> Reference for `/skill:hep-research-pipeline`, `/skill:hep-auto-review-loop`, and `/skill:paper-writing` when targeting high-energy physics venues.

## Journal Tiers

### Tier 1: Letters (Fast, High Impact, ~4–6 pages)

| Venue | Full Name | Scope | Page Limit | LaTeX Class | Notes |
|-------|-----------|-------|------------|-------------|-------|
| **PhysRevLett** | Physical Review Letters | All physics | 4 pages (main) + refs | `revtex4-2` | PRL, most prestigious physics letter journal |
| **PLB** | Physics Letters B | HEP, NP, Cosmology | ~6 pages | `elsarticle` | Fast turnaround, broad HEP coverage |

### Tier 1: Full Journals (Primary HEP Journals)

| Venue | Full Name | Scope | Typical Length | LaTeX Class | Notes |
|-------|-----------|-------|----------------|-------------|-------|
| **JHEP** | Journal of High Energy Physics | HEP theory + pheno | 10–30+ pages | `jheppub` | Open access, very fast turnaround, no page charges |
| **PhysRevD** | Physical Review D | HEP, gravitation, cosmology | 10–20+ pages | `revtex4-2` | PRD, massive volume, rigorous refereeing |
| **EPJC** | European Physical Journal C | HEP, NP | 10–20+ pages | `svjour3` | Open access (S2I), broad coverage |
| **JCAP** | Journal of Cosmology and Astroparticle Physics | Cosmology, DM, astroparticle | 10–20+ pages | `jcap` | Open access, strong on theory–experiment interface |
| **NPB** | Nuclear Physics B | HEP, formal theory, strings | 15–30+ pages | `elsarticle` | Longer, more formal papers |

### Tier 2: Specialized / Mathematical Physics

| Venue | Full Name | Scope | Typical Length | LaTeX Class | Notes |
|-------|-----------|-------|----------------|-------------|-------|
| **CMP** | Communications in Mathematical Physics | Mathematical physics | 15–40+ pages | `svjour3` | Very high mathematical standards |
| **AnnPhys** | Annals of Physics | Theoretical physics | 15–30+ pages | `elsarticle` | Broad theory coverage |
| **NPPS** | Nuclear Physics B Proceedings Supplements | Conference proceedings | Variable | `elsarticle` | For conference write-ups |

### Preprint

| Venue | Notes |
|-------|-------|
| **hep-arXiv** | Not a journal — preprint server. Categories: hep-ph, hep-th, hep-ex, hep-lat. Most HEP papers appear here first. |

## Conferences (Proceedings)

| Conference | Focus | Proceedings Venue |
|------------|-------|-------------------|
| **ICHEP** | International Conference on HEP | Various |
| **EPS-HEP** | European Physical Society HEP | EPJ Web of Conferences |
| **LHCP** | LHC Physics | J. Phys.: Conf. Ser. |
| **Moriond** | Electroweak / QCD / Cosmology | Various |
| **SUSY** | Supersymmetry / Unification | Various |

## LaTeX Setup by Venue

### JHEP
```latex
\documentclass[a4paper,11pt]{article}
\usepackage{jheppub}
% JHEP provides its own class — download from jhep.sissa.it
```

### Physical Review D / Letters (revtex4-2)
```latex
\documentclass[aps,prd,reprint,superscriptaddress]{revtex4-2}
% For PRL: replace `prd` with `prl`
% For preprint: add `preprint` option
```

### EPJC (Springer)
```latex
\documentclass[twocolumn,epjc3]{svjour3}
\journalname{Eur. Phys. J. C}
```

### JCAP (IOP)
```latex
\documentclass[11pt,a4paper]{article}
\usepackage{jcap}
% Download from jcap.sissa.it
```

### Physics Letters B (Elsevier)
```latex
\documentclass[preprint,12pt]{elsarticle}
\journal{Physics Letters B}
```

## Citation Style

All HEP journals use **numeric citation style** (NOT author-year like `natbib`):

```latex
\usepackage{cite}  % or \usepackage[numbers]{natbib}
% Citations: \cite{key1,key2}
% No \citep or \citet
```

BibTeX entries should include:
- `eprint` field for arXiv preprints: `eprint = "2401.12345", archivePrefix = "arXiv"`
- `doi` when available
- `SLACcitation` for INSPIRE compatibility (optional)

## Venue Selection Guide

| Your Paper Is... | Recommended Venue |
|-----------------|-------------------|
| Fast, high-impact phenomenology result | PhysRevLett or PLB |
| Full phenomenology with detailed analysis | JHEP or PhysRevD |
| Formal theory / amplitudes / strings | JHEP or NPB |
| Cosmology / astroparticle interface | JCAP |
| Mathematical physics with rigor | CMP or JHEP |
| Dark matter model + collider pheno | JHEP or PhysRevD |
| EFT / precision calculations | JHEP or PhysRevD |

## Key Differences from ML Venues

| Aspect | ML (NeurIPS/ICML) | HEP (JHEP/PRD) |
|--------|-------------------|----------------|
| Review time | 1–2 months | 2 weeks–2 months (JHEP very fast) |
| Page limit | 9 pages + refs | No strict limit (typical 10–30) |
| Citation style | Author-year (`\citep`) | Numeric (`\cite`) |
| Double-blind | Yes | No (single-blind or open) |
| Reproducibility | Code submission encouraged | No formal requirement (but expected) |
| Preprint | arXiv (cs.LG) | arXiv (hep-ph/th) — essentially mandatory |
| Open access | Varies | JHEP, JCAP, EPJC are fully OA |
