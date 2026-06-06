# Project State (项目当前状态)

<!--
USAGE:
  - This file is the AMBIENT CONTEXT for `/skill:research-debug` and the
    interactive helpers. It is NOT a one-off questionnaire — keep it alive
    and update it whenever the project shifts.
  - Fill every section. If a section is genuinely N/A, write "N/A — reason".
    Do NOT delete sections — empty sections lose their disambiguating value.
  - English keys (`process:`, `observables:`, …) stay in English so tools can
    grep them. Values can be Chinese, English, or LaTeX as you prefer.
  - Recommended update cadence: whenever you (a) finish a meaningful run,
    (b) change architecture or loss, (c) discover a new failure mode, or
    (d) write a new section in idea-survey/.
  - This file is read VERBATIM by subagents. Be concrete; avoid vague phrases
    like "我们做的是物理 ML"。要写清"在 sNN=200 GeV Au+Au 上用 GNN 重建径迹"这种程度。
-->

---

## 0. Identity

- **project_title**:                  <!-- e.g. "PINN-calibrated Schrödinger Bridge for Au+Au @ 200 GeV initial state" -->
- **one_line_summary**:               <!-- 一句话能让外人 30 秒判断这是啥的描述 -->
- **stage**:                          <!-- one of: scoping / idea-survey / prototyping / pilot-running / scaling / writing-up -->
- **last_updated**:                   <!-- YYYY-MM-DD -->
- **author**:                         <!-- your name / 课题组 -->

### Cross-links (if they exist)

- `idea-survey/landscape-report.md`:  <!-- present? path or "not yet run" -->
- `idea-survey/novelty-report.md`:    <!-- 同上 -->
- `idea-survey/feasibility-report.md`:<!-- 同上 -->
- `proposal/main.tex`:                <!-- present? path or "not yet run" -->
- code repo:                          <!-- git URL or local path -->

---

## 1. Physics Context (物理侧)

> Anything a hep-ph / hep-ex / nucl-th / nucl-ex referee would need to know to follow the project. Be specific — "QGP" alone is not enough.

- **subfield**:                       <!-- e.g. heavy-ion phenomenology / lattice / spin physics / hadron structure / EIC physics / neutrino oscillations -->
- **process**:                        <!-- e.g. "Au+Au inclusive charged hadron production"; "ep DIS at small-x"; "pp → tt̄H, H → bb̄" -->
- **collision_system_and_energy**:    <!-- e.g. "Au+Au, √sNN = 200 GeV (RHIC top)"; "Pb+Pb, √sNN = 5.02 TeV (LHC Run 2)"; "ep, √s = 105 GeV (EIC YR)" -->
- **kinematic_region**:               <!-- pT, η, x, Q² ranges actually used -->
- **observables**:                    <!-- 你正在算或正在拟合的可观测量: v_n(pT), R_AA, jet substructure, GPDs, ... -->
- **theory_framework**:               <!-- one or more of: hydrodynamics / Boltzmann transport / pQCD / lattice QCD / EFT / SCET / CGC / TMD / nPDF / hadronic cascade -->
- **simulators_or_codes_in_loop**:    <!-- iEBE-VISHNU / MUSIC / SMASH / PYTHIA / Herwig / MadGraph / Pythia8 / JEWEL / TRENTO / IP-Glasma / EPOS / GENESIS / FLUKA / GEANT4 / lattice code / your own -->
- **experimental_dataset**:           <!-- collaboration & dataset id, e.g. "STAR Au+Au 200 GeV Run-14 v2{4}"; "ATLAS Run-2 Z+jet 139 fb⁻¹"; "HotQCD lattice Nτ=12" -->
- **systematics_we_care_about**:      <!-- e.g. "shear viscosity η/s prior, freeze-out T_FO, hadron cascade scattering rate" -->
- **physics_constraints_or_priors**:  <!-- unitarity, causality, gauge invariance, isospin, chiral symmetry, sum rules — what MUST the model respect -->

### Key physics quantities currently being tracked

| Symbol | Meaning | Current value / range | Source |
|---|---|---|---|
| <!-- η/s --> | <!-- specific shear viscosity --> | <!-- 0.08–0.20 --> | <!-- prior from Bayesian analysis 2306.xxxxx --> |
| | | | |
| | | | |

---

## 2. ML Context (深度学习侧)

> Anything a NeurIPS/ICML/ICLR reviewer (or a physics-aware ML reviewer at MLST/PRSL/Phys.Rev.Research) would need.

- **task_formulation**:               <!-- classification / regression / generation / inverse problem / surrogate model / posterior estimation (SBI/NPE/SNPE) / RL / contrastive -->
- **why_ML_here**:                    <!-- 一句话: 为什么不用传统方法？吞吐量？反问题不可解析？高维条件分布？ -->
- **input_modality**:                 <!-- event-level features / per-track sequence / 2D calorimeter image / 3D point cloud / graph (nodes=particles, edges=…) / spectrum / histogram / parameter vector -->
- **output_modality**:                <!-- scalar regression / vector / image / distribution (CNF/NF/diffusion) / posterior over θ / classification logits -->
- **architecture_family**:            <!-- Transformer / GNN (which? GIN/EGNN/SE(3)-equivariant) / NF (RealNVP/MAF/NSF) / diffusion (score / DDPM / Schrödinger Bridge) / VAE / PINN / DeepSet / EquivNN / hybrid -->
- **physics_inductive_biases_used**:  <!-- e.g. Lorentz equivariance (LorentzNet); SO(3) equivariance (EGNN); permutation invariance; energy-momentum conservation as hard / soft constraint; Boltzmann-style symmetries -->
- **loss_function**:                  <!-- MSE / NLL / Wasserstein / score-matching / KL to MC / posterior NPE loss / physics-residual penalty / multi-term — write the formula or schematic -->
- **training_data**:                  <!-- e.g. "10^6 events from iEBE-VISHNU at 8 parameter points"; "ATLAS Open Data Z+jets 13 TeV"; "lattice configurations, 200 ensembles" -->
- **train_val_test_split**:           <!-- 比例 + 是否按事件 / 按参数点 / 按 collision-system 划分 — 注意 DR vs IID -->
- **scale**:                          <!-- model params (M); training events; epochs; wall-clock; GPU type -->
- **infrastructure**:                 <!-- 单卡 A100 / 多卡 / 集群 / Slurm / 学校的 HPC / 课题组的 workstation / 云 -->
- **frameworks_used**:                <!-- PyTorch / JAX / TF / awkward / coffea / uproot / hist / zfit / ROOT / Pythia bindings / Mathematica -->

### Current best results (实测，不是论文目标)

| Metric | Value | Baseline | Run ID / commit | Comment |
|---|---|---|---|---|
| | | | | |
| | | | | |

---

## 3. Cross-Domain Bridge (跨学科衔接)

> The most error-prone questions ("为什么我搜不到") almost always live HERE — at the seam between physics and ML. Be VERY explicit about how the two halves connect.

- **what_ML_replaces**:                <!-- e.g. "replaces the 4-D Cooper-Frye integral with a learned amortized surrogate" -->
- **what_ML_adds**:                    <!-- e.g. "yields a posterior over (η/s, T_FO, T_sw) instead of a single point fit" -->
- **physics_to_ML_data_pipeline**:     <!-- 一行流程: simulator → event format → features → tensor → model. Include data sizes per step. -->
- **ML_to_physics_decoding**:          <!-- model output → physical observable. Any post-processing? Calibration? Unfolding? -->
- **known_distribution_shifts**:       <!-- e.g. "train on TRENTO, deploy on IP-Glasma"; "train on Pythia8, test on Sherpa"; "train at √s=200, deploy at √s=5020" -->
- **identifiability_known_issues**:    <!-- e.g. "η/s and T_FO are degenerate at the v2 level — need v4 to break degeneracy" -->

---

## 4. Current Implementation State (当前实现状况)

- **what_is_working**:                 <!-- bullet-style; concrete; "✅ EGNN forward pass + train loop on 50k events; loss decreases monotonically" -->
- **what_is_broken**:                  <!-- "❌ NLL diverges after epoch 12 with bs=512 on multi-GPU; bs=64 single GPU is stable" -->
- **what_is_untested**:                <!-- "⏸ haven't tried equivariant data augmentation; haven't tried gradient clipping" -->
- **most_recent_commit_or_run**:       <!-- date, commit hash or run ID, one-line change -->
- **next_concrete_step_in_user_head**: <!-- 你接下来打算做的事，一句话 — 这是消除歧义最关键的一行 -->

---

## 5. Recent Experimental Observations (最近的实验观察)

> The 3–5 most recent results / failures / surprises. Order: newest first. KEEP THIS LIVE — older items move to a project log or get deleted.

### Observation #1 — <!-- YYYY-MM-DD --> <!-- 一句标题 -->
- **what_happened**:                   <!-- 一两句 -->
- **expected**:                        <!-- 我以为会发生 X -->
- **actual**:                          <!-- 实际是 Y -->
- **my_hypothesized_cause**:           <!-- 我猜是因为 Z（写出 1–3 个备选） -->
- **artifacts**:                       <!-- log file path, plot path, run ID -->

### Observation #2 — ...

### Observation #3 — ...

---

## 6. Current Open Questions / Blockers (当前卡点)

> 1–3 things you are actively stuck on. This is the section `research-debug` reads FIRST. Be honest about what you don't know.

### Q1: <!-- 一句话写明你的问题 -->
- **why_this_matters_for_the_project**:<!-- 不解决会怎么样 -->
- **what_I_have_already_tried**:       <!-- 三个 bullet 以内 -->
- **what_I_think_the_answer_might_be**:<!-- 你猜的方向，1–3 句 -->
- **type_of_help_I_need**:             <!-- one of: literature-precedent / mechanism-explanation / SOTA-pointer / experimental-suggestion / debug-strategy / sanity-check -->

### Q2: ...

### Q3: ...

---

## 7. Glossary & Disambiguation (术语澄清)

> The single highest-ROI section for AI-assisted search. Anywhere a domain term is ambiguous OR overloaded, define what YOU mean in YOUR project.

| Term in your writing | What it means in this project | What it does NOT mean here |
|---|---|---|
| <!-- "flow" --> | <!-- collective anisotropic flow v_n in HIC --> | <!-- normalizing flow (NN), or fluid flow in CFD --> |
| <!-- "background" --> | <!-- non-flow combinatorial bg in v2{2} --> | <!-- physics background process in BSM searches --> |
| <!-- "transport" --> | <!-- hadronic Boltzmann transport (SMASH) --> | <!-- transport coefficient, or Optimal Transport --> |
| <!-- "calibration" --> | <!-- Bayesian model-parameter calibration --> | <!-- detector energy calibration --> |
| | | |
| | | |

> 💡 If `research-debug` runs into your question and finds an ambiguous term, it will write the disambiguation back here in a later run.

---

## 8. Constraints (项目约束)

- **compute_budget**:                  <!-- "一张 A100 共享 + 课题组 8 卡集群每周 24 小时" -->
- **wall_clock_to_milestone**:         <!-- "毕业答辩 2026-12; 投稿 PRL 计划 2026-09" -->
- **data_access**:                     <!-- collaboration NDA? STAR/PHENIX internal only? open data? -->
- **code_publishability**:             <!-- "需要内部审核才能开源" / "MIT" / "未决定" -->
- **language_for_output**:             <!-- zh / en — 用于报告产出 -->

---

## 9. Project Log (Optional Long Tail)

> Moved-out old "Observation #N" entries can live here. Newest at top. Free-form.

<!-- 2026-MM-DD: ... -->

---

<!-- ARIS_GUIDANCE_START -->
<!-- ARIS_GUIDANCE_END -->
