# JAX Virtual Disease backend qualification gate

## Purpose

PR #20 adds an optional JAX-accelerated execution backend for the frozen Virtual Disease 1-D haemodynamic equations. The NumPy `DiseaseOneDSolver` remains unchanged and remains the default/reference implementation.

The gate does **not** establish clinical validation. It qualifies software/mechanistic equivalence and accelerated execution against canonical PWDB 3275625 while retaining:

```text
EvidenceClass = MODELLED
healthy reconstruction gate = METRICS_ONLY_THRESHOLDS_NOT_FROZEN
clinical validation = false
population interpretation = backend qualification, not epidemiological
```

## Canonical source

Qualification uses the exact Virtual Disease PWDB artifacts:

- `pwdb_model_configs.csv`;
- `geo.zip`;
- `PWs_csv.zip`.

The Colab staging helper checks only the configured `PWDB_3275625` directory, copies existing exact files once to local SSD, verifies them locally, and acquires only missing/invalid canonical artifacts through VascuQuest's checksum-verified acquisition layer.

## Why the repaired JAX backend is required

The first JAX prototype coupled an artificial `500_000`-step cardiac-cycle guard to an all-step final-cycle history buffer. Real focal-stenosis pressure-loss stability can legitimately require more than 500,000 explicit SSP-RK2 steps per cycle under the frozen NumPy stability rule. Increasing that fixed limit would also have increased replay-history memory without bound.

The production JAX backend therefore keeps the same numerical operator and adaptive SSP-RK2 path but changes execution control only:

- a subject/network-specific safety cap is derived from the initial stability `dt`, with a generous nonlinear guard;
- the safety cap is only a scalar loop guard and does not size the output history;
- the final converged cardiac cycle is replayed onto the source aortic-inflow time grid with linear interpolation between the exact adaptive-step states;
- only that bounded sampled history is retained for the 116-segment `ForwardSolution`;
- the adaptive integration path itself is not shortened, coarsened, or replaced by a different disease equation.

The package backend selector routes explicit `backend="jax"` requests to this bounded-replay implementation. NumPy remains the unchanged default.

## One-subject real-PWDB qualification

Preferred notebook:

```text
notebooks/jax_one_subject_qualification_v2_colab.ipynb
```

Runner:

```text
tests/full_data/jax_one_subject_qualification_v2.py
```

The same deterministic canonical PWDB subject is used across all four frozen disease conditions:

1. carotid stenosis;
2. iliac stenosis;
3. fusiform abdominal aortic aneurysm;
4. large-artery stiffening.

For every transformed network, qualification requires NumPy↔JAX equivalence of the RHS, terminal-capacitor derivative and stability operators on the same deterministic non-trivial state. All four conditions must then complete a full periodic JAX solve with exactly 116 segments, finite `A`, `Q`, `P`, finite derived `U=Q/A`, positive area and `converged = true`.

One large-artery-stiffening case additionally runs the frozen NumPy solver end-to-end and compares full-network final-cycle fields after time interpolation. This anchor separates correctness qualification from performance measurement while avoiding four additional slow NumPy solves.

The report records, per JAX case:

- operator-equivalence metrics;
- convergence diagnostics;
- total wall time;
- final-cycle adaptive step count;
- derived per-cycle safety cap;
- initial stability time step;
- bounded output sample count;
- JAX device/platform and X64 status.

## Durable evidence

The preferred Colab notebook writes:

```text
MyDrive/VascuQuest/jax_one_subject_qualification_v2/<code-revision-prefix>/jax-one-subject-qualification.json
```

The v2 failure wrapper preserves any already-completed case records and appends the exception instead of erasing partial evidence.

## GitHub Actions

`.github/workflows/parameterized-cohort-release-validation.yml` is deliberately `workflow_dispatch`-only. It compiles both JAX modules and executes the v2 qualification runner on CPU as an optional reproducibility route. The Colab GPU notebook is the preferred acceleration/performance route.

Ordinary Core CI and the independent PWDB Core Tier-4 real-source regression remain separate gates.

Do not merge PR #20 until the durable v2 report is `PASS` and its operator, convergence, step-count and NumPy/JAX anchor evidence have been inspected. A PASS qualifies the accelerated backend within the current Virtual Disease model context; it does not establish epidemiological representativeness, clinical outcome validity, diagnostic accuracy or patient-specific prediction.
