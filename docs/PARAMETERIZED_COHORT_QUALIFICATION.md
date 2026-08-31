# JAX-accelerated Virtual Disease qualification gate

## Purpose

PR #19 introduced the Parameterized Virtual Disease Cohort Engine. PR #20 now adds an optional JAX/XLA execution backend for the same frozen Virtual Disease numerical model and defines the real-source qualification gate that must pass before that backend is merged and shipped.

The existing NumPy `DiseaseOneDSolver` remains the default and reference implementation. PR #20 does not change the Virtual Disease presets, causal disease transformations, PWDB interpretation, or scientific boundary.

```text
EvidenceClass = MODELLED
healthy reconstruction gate = METRICS_ONLY_THRESHOLDS_NOT_FROZEN
clinical validation = false
population interpretation = backend qualification, not epidemiological
```

## Backend contract

The JAX backend must preserve the frozen NumPy mechanics:

- canonical 116-segment arterial network;
- PWDB beta wall law and characteristic wave speed;
- second-order MUSCL reconstruction;
- HLL-type interface flux in perturbation variables;
- explicit PWDB Voigt-wall momentum source;
- characteristic internal-junction coupling;
- prescribed periodic aortic-root flow boundary;
- terminal three-element Windkessel/RCR coupling;
- focal stenosis pressure-loss terms when present;
- adaptive SSP-RK2 time stepping;
- configured CFL, diffusion, area-floor and periodicity controls;
- the same `ForwardSolution`, `SegmentSolution`, and `SolverDiagnostics` public value objects.

JAX is an optional dependency. Core VascuQuest installs continue to work without it. X64 is enabled for qualification against the NumPy reference.

## Real-source scope

Qualification uses the exact canonical PWDB artifacts required by Virtual Disease:

- `pwdb_model_configs.csv`;
- `geo.zip`;
- `PWs_csv.zip`.

The Colab route copies exact existing Drive files once to local SSD and verifies their canonical manifest checksums. Missing files are acquired through VascuQuest's canonical artifact layer. It does not recursively scan mounted Google Drive.

## One-subject qualification design

The preferred gate uses **one deterministic canonical PWDB subject** for all four frozen Virtual Disease conditions:

1. carotid stenosis;
2. iliac stenosis;
3. fusiform abdominal aortic aneurysm;
4. large-artery stiffening.

The subject is selected deterministically from source ages 45 or 55 and must be individually admissible for all four interventions. The same subject identity is retained throughout the gate.

### Q1 — NumPy↔JAX numerical-operator equivalence

For every transformed disease network, construct the same deterministic non-trivial `A,Q` state and terminal capacitor pressures. Evaluate both backends without advancing time and compare:

- full 116-segment finite-volume RHS;
- terminal capacitor-pressure derivatives;
- adaptive stability time step;
- maximum hyperbolic/CFL rate;
- maximum explicit Voigt diffusion rate;
- disease pressure-loss stability bound where applicable.

Qualification tolerances are intentionally tight because this gate compares the same discrete operator in float64 rather than independent clinical models.

### Q2 — complete JAX execution for all four diseases

For all four conditions, require the JAX solver to:

- complete the full 116-segment network;
- reach the existing periodic-convergence criterion;
- return a finite, strictly increasing final-cycle time coordinate;
- return finite `A(t,x)`, `Q(t,x)` and `P(t,x)` on every segment;
- retain positive lumen area everywhere;
- produce finite derived cross-sectional mean velocity `U=Q/A`;
- report the existing numerical diagnostics.

### Q3 — end-to-end NumPy↔JAX anchor

One large-artery-stiffening case is additionally executed to convergence by the frozen NumPy solver. Large-artery stiffening is used as the full-solve anchor because it retains the ordinary source mesh while changing the large-conduit beta coefficients, avoiding the extra lesion-specific mesh refinement cost of stenosis and AAA.

The full final cycle is compared across all 116 segments after interpolation to a common temporal grid. Qualification requires bounded relative L2 differences in:

- lumen area;
- volumetric flow;
- pressure.

The NumPy and JAX solver diagnostics are retained in the machine-readable report.

### Q4 — benchmark evidence

Timing is evidence, not a correctness criterion. Record separately:

- JAX first-cycle compile-plus-execute time;
- subsequent compiled-cycle execution time;
- final-cycle replay/history construction time;
- full JAX wall time for each disease;
- full NumPy anchor wall time;
- NumPy/JAX anchor speed ratio;
- actual JAX platform/device and X64 state.

This prevents JIT compilation cost from being confused with steady compiled execution performance.

## Preferred execution route

Open:

```text
notebooks/jax_one_subject_qualification_colab.ipynb
```

The notebook:

- mounts Google Drive;
- clones the exact PR #20 branch and records the commit SHA;
- installs VascuQuest with the optional `[jax]` extra;
- reports the active JAX device;
- stages/verifies canonical PWDB artifacts to local SSD;
- runs `tests/full_data/jax_one_subject_qualification.py`;
- persists failure evidence if any gate fails;
- writes the durable PASS/FAIL report to:

```text
MyDrive/VascuQuest/jax_one_subject_qualification/<code-revision-prefix>/jax-one-subject-qualification.json
```

## GitHub Actions route

`.github/workflows/parameterized-cohort-release-validation.yml` remains `workflow_dispatch`-only. It exists as a reproducible manual CI route; the Colab notebook is preferred when GPU hardware is required or interactive diagnostics are useful.

Ordinary Core CI and the existing PWDB Core Tier-4 real-source regression remain independent gates and must continue to pass.

## Merge rule

PR #20 must remain unmerged until:

1. ordinary Core CI passes;
2. existing PWDB Core Tier-4 regression passes;
3. `jax-one-subject-qualification.json` reports `PASS` for the exact PR head being merged;
4. all four operator-equivalence gates pass;
5. all four JAX disease solves converge with complete finite 116-segment output;
6. the full NumPy↔JAX anchor passes its field-equivalence tolerances.

A passing report qualifies the JAX backend as a software/mechanistic execution backend for the current Virtual Disease model. It does **not** establish epidemiological representativeness, clinical outcome validity, diagnostic performance, patient-specific prediction, or equivalence to clinical tonometry/Doppler measurements.
