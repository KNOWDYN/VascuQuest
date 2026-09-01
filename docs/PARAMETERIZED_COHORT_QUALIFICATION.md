# JAX Virtual Disease split-solver qualification gate

## Purpose

PR #20 adds an optional structure-preserving JAX execution backend for the frozen Virtual Disease 1-D haemodynamic model and wires that backend into the Parameterized Virtual Disease Cohort Engine.

The NumPy `DiseaseOneDSolver` remains unchanged and remains the default/reference implementation. JAX is additive, lazy and optional. No disease preset, causal disease transformation, PWDB interpretation, clinical boundary or scientific cohort-plan identity is changed.

The accelerated numerical scheme is:

```text
jax-exact-loss-rkc2-voigt-ssprk2-v1
```

with the symmetric composition:

```text
exact Young–Seeley focal-loss half step
→ globally coupled Voigt RKC2 half step
→ frozen hyperbolic/network SSP-RK2 full step
→ globally coupled Voigt RKC2 half step
→ exact Young–Seeley focal-loss half step
```

The deployed Virtual Disease v1 focal stenosis contract has zero excess Young–Seeley inertance; the exact focal-loss propagator therefore integrates the linear/quadratic local loss analytically without changing the disease equation. The outer physical time step is wave-CFL-limited. The explicit-equivalent Voigt and focal-loss limits are retained as diagnostic telemetry rather than global step restrictions.

Scientific boundary remains:

```text
EvidenceClass = MODELLED
healthy reconstruction gate = METRICS_ONLY_THRESHOLDS_NOT_FROZEN
clinical validation = false
population interpretation = designed/modelled counterfactual, not epidemiological
```

## Canonical source

Qualification uses the canonical PWDB 3275625 artifacts required by Virtual Disease:

- `pwdb_model_configs.csv`;
- `geo.zip`;
- `PWs_csv.zip`.

The Colab staging helper checks only the configured `PWDB_3275625` directory, copies available exact files once to local SSD, verifies them locally, and acquires only missing/invalid canonical artifacts through VascuQuest's checksum-verified acquisition layer. It never recursively scans all of Google Drive.

## Exact focal-loss gate

The analytical focal-loss propagator has unit tests requiring:

- identity for zero duration and zero resistance;
- preservation of zero flow;
- preservation of flow sign;
- monotone dissipation of `|Q|`;
- agreement with the pure-linear exponential limit;
- agreement with the pure-quadratic rational limit;
- semigroup consistency;
- rejection of negative coefficients;
- rejection of nonzero excess inertance.

## One-subject four-disease real-PWDB gate

Preferred notebook:

```text
notebooks/jax_split_one_subject_qualification_colab.ipynb
```

Main runner:

```text
tests/full_data/jax_split_one_subject_qualification.py
```

The same deterministic canonical PWDB subject is used across all four frozen disease conditions:

1. carotid stenosis;
2. iliac stenosis;
3. fusiform abdominal aortic aneurysm;
4. large-artery stiffening.

For every transformed network, qualification first preserves the strongest invariant from the original JAX prototype: NumPy↔JAX equivalence of the complete semidiscrete RHS, terminal-capacitor derivative and original stability operators on an identical deterministic non-trivial state.

All four conditions must then complete a periodic accelerated JAX solve with:

- `converged = true`;
- exactly 116 segment identities in canonical order;
- finite `A`, `Q`, `P` and derived `U=Q/A`;
- strictly positive area;
- finite and monotone output time coordinate;
- preserved disease specification and modified-segment identity.

Per disease the report records:

- accelerated wall time;
- final-cycle wave-CFL outer-step count;
- total and maximum RKC stage load;
- exact focal-loss update count;
- minimum measured wave-CFL `dt`;
- minimum explicit-equivalent Voigt `dt`;
- minimum explicit-equivalent focal-loss `dt`;
- the original explicit limiting operator;
- estimated old explicit steps per cardiac cycle;
- measured accelerated outer steps;
- implied outer-step reduction factor;
- solver convergence diagnostics;
- JAX platform/device and X64 state.

Large-artery stiffening additionally runs the frozen NumPy solver end-to-end as the full-network reference anchor and compares the final periodic `A`, `Q`, and `P` fields after time interpolation. This condition is used because it does not contain the focal Young–Seeley source and therefore isolates the network/wall integration path.

## Temporal-order gate

Runner:

```text
tests/full_data/jax_split_temporal_refinement.py
```

After the main four-disease gate passes, the identical selected subject and carotid-stenosis model are rerun with fixed spatial discretization and progressively halved outer wave-CFL values:

```text
0.40 → 0.20 → 0.10
```

The final periodic solutions are compared over the complete 116-segment fields. The observed self-convergence order for:

- area;
- flow;
- pressure

must each be at least `1.50`. This is deliberately below the ideal asymptotic value 2.0 but high enough to reject a first-order implementation while allowing real-network boundary/splitting effects and finite convergence tolerances.

The resulting temporal-refinement evidence is appended to the same durable qualification JSON. A four-disease PASS without a temporal-order PASS is not sufficient for PR #20.

## Cohort integration and execution identity

The public cohort API and CLI support explicit backend selection while NumPy remains the default:

```python
generate_parameterized_cohort(..., solver_backend="jax")
```

```text
vascuquest disease cohort generate ... --solver-backend jax
```

The scientific cohort `run_id` continues to identify the counterfactual design. Numerical execution is recorded separately using a `solver_execution_id` derived from:

- backend;
- numerical scheme ID;
- float precision;
- solver options;
- execution-contract version.

Bundle resume requires an exact execution-descriptor match. NumPy output therefore cannot be silently resumed as JAX output or vice versa. Subject manifests and disease provenance retain the execution identity.

## Deliberate scope boundary

PR #20 does not yet claim GPU cohort micro-batching as qualified production behavior. The first release gate qualifies the scalar accelerated solver and the backend-aware native cohort path. Padded/shape-bucketed GPU micro-batching is added only after the scalar solver passes all numerical gates, and it must then demonstrate scalar↔batch equivalence before becoming a production optimization.

PR #20 does not introduce:

- new disease coefficients;
- new junction physics;
- nonuniform lesion meshing;
- relaxed CFL or periodicity tolerance;
- float32 execution;
- reduced spatial lesion resolution;
- clinical or epidemiological claims.

## Durable evidence

The preferred Colab notebook writes:

```text
MyDrive/VascuQuest/jax_split_one_subject_qualification/<code-revision-prefix>/jax-split-one-subject-qualification.json
```

The main qualification runner persists partial evidence after every completed disease. The temporal-refinement gate appends its evidence to the same file.

## GitHub Actions

`.github/workflows/parameterized-cohort-release-validation.yml` is deliberately `workflow_dispatch`-only. It compiles and can execute the same one-subject/four-disease and temporal-refinement gates on CPU as a reproducibility route. Colab GPU is the preferred performance qualification route.

Ordinary Core CI and the independent real-PWDB Core Tier-4 regression remain separate mandatory regression gates.

Do not merge PR #20 until:

1. Core CI passes;
2. Core Tier-4 passes or any external-source outage is explicitly resolved and rerun successfully;
3. the durable split-solver report is `PASS`;
4. the four-disease operator/convergence/limiter evidence has been inspected;
5. the NumPy full-network anchor passes;
6. the temporal-refinement gate passes.

A PASS qualifies the accelerated numerical backend within the current Virtual Disease model context. It does not establish clinical validation, epidemiological representativeness, diagnostic accuracy, prognosis or patient-specific clinical prediction.
