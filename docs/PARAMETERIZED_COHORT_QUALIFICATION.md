# Structure-preserving JAX Virtual Disease qualification gate

## Purpose

PR #20 adds an optional accelerated numerical backend for Virtual Disease and wires that backend into the parameterized cohort runtime. The frozen NumPy `DiseaseOneDSolver` remains unchanged and remains the default/reference implementation.

The accelerated numerical scheme is:

```text
jax-exact-loss-rkc2-voigt-ssprk2-v1
```

It preserves the deployed disease transformations, 116-segment spatial model, PWDB wall coefficients, HLL/MUSCL transport, characteristic junction coupling, root inflow and terminal RCR physics. It changes time integration so avoidable source stiffness does not force the whole network to take the smallest explicit source time step.

This gate does **not** establish clinical validation. All outputs retain:

```text
EvidenceClass = MODELLED
healthy reconstruction gate = METRICS_ONLY_THRESHOLDS_NOT_FROZEN
clinical validation = false
population interpretation = numerical/backend qualification, not epidemiological
```

## Numerical architecture

Each outer step is a symmetric second-order composition:

```text
exact Young-Seeley focal-loss half step
        ↓
globally coupled Voigt RKC2 half step
        ↓
existing hyperbolic/network SSP-RK2 full step
        ↓
globally coupled Voigt RKC2 half step
        ↓
exact Young-Seeley focal-loss half step
```

The outer step is selected from the existing wave CFL (`cfl = 0.45`). The solver still computes and records the explicit-equivalent Voigt and focal-loss limits, but those limits do not automatically shrink the whole-network outer time step.

### Exact focal-loss source

Virtual Disease v1 focal stenosis adds the distributed Young-Seeley excess loss

```text
dP = L Q + K Q |Q|
```

and explicitly sets added inertance to zero. During a source-only substep, area is fixed and the local momentum source reduces to

```text
dQ/dt = -a Q - b Q |Q|.
```

That scalar ODE is integrated analytically. The update preserves zero flow and flow sign and is dissipative. Non-zero added focal-loss inertance is rejected by the accelerated scheme because it changes the momentum mass factor and therefore requires a separately qualified formulation.

### Voigt wall source

The PWDB Voigt source remains globally coupled through the same boundary/junction states used by the deployed semidiscrete model. It is not solved independently vessel-by-vessel. A damped second-order Runge-Kutta-Chebyshev (RKC2) stage sequence stabilizes this diffusion-like operator while retaining explicit tensor execution in JAX.

The solver records the total and maximum RKC stage burden for the final cardiac cycle. A hard RKC stage ceiling is a numerical safety guard; exceeding it is a failure, not a silent reduction in accuracy.

### Hyperbolic/network operator

The JAX implementation reuses the already checked full semidiscrete JAX operator and derives the non-Voigt/non-focal part by subtracting independently reconstructed Voigt and focal-loss operators. For deployed vd1 (zero excess inertance), this decomposition is exact. The network step therefore retains the existing:

- perturbation MUSCL reconstruction;
- HLL-type interface flux;
- PWDB beta wall elasticity;
- ordinary distributed friction;
- characteristic internal junction coupling;
- prescribed aortic-root inflow;
- three-element Windkessel terminal coupling;
- SSP-RK2 network integration.

## Limiter attribution

The original explicit solver selects

```text
dt = min(dt_wave, dt_voigt, dt_loss)
```

and focal stenosis also refines the affected artery to approximately `lesion_length / 24`, which can make the explicit Voigt limit very small because the diffusion-like restriction scales approximately with `dx^2`.

The accelerated qualification therefore records, for every disease case:

- minimum wave-CFL time step;
- minimum explicit-equivalent Voigt time step;
- minimum explicit-equivalent focal-loss time step;
- which operator would have controlled the old explicit solver;
- old explicit-equivalent steps per cardiac cycle;
- actual accelerated outer steps per cycle;
- resulting outer-step reduction factor;
- RKC stage total and maximum stage count;
- exact focal-loss update count.

No performance claim is made until these quantities are measured on the real PWDB qualification subject.

## Canonical source

Qualification uses the exact Virtual Disease PWDB artifacts:

- `pwdb_model_configs.csv`;
- `geo.zip`;
- `PWs_csv.zip`.

The Colab staging helper checks only the configured source directory, copies existing exact files once to local SSD, verifies them locally, and acquires only missing/invalid canonical artifacts through VascuQuest's checksum-verified acquisition layer. It does not recursively scan Google Drive.

## Definitive one-subject real-PWDB qualification

Preferred notebook:

```text
notebooks/jax_split_one_subject_qualification_colab.ipynb
```

Runner:

```text
tests/full_data/jax_split_one_subject_qualification.py
```

The same deterministic canonical PWDB subject is used across all four frozen disease conditions:

1. carotid stenosis;
2. iliac stenosis;
3. fusiform abdominal aortic aneurysm;
4. large-artery stiffening.

For every transformed network the gate first retains the frozen NumPy↔JAX equivalence check of the complete semidiscrete RHS, terminal-capacitor derivative and stability operators on an identical deterministic non-trivial state.

All four disease cases must then complete a full accelerated periodic solve with:

- `converged = true`;
- exactly 116 segment outputs;
- finite positive `A`;
- finite `Q` and `P`;
- finite derived `U = Q/A`;
- bounded final-cycle output on the source inflow grid;
- complete timing/limiter telemetry;
- exact focal-loss updates present only for carotid/iliac stenosis.

Large-artery stiffening additionally runs the frozen NumPy solver end-to-end and compares all 116 final-cycle fields after time alignment. Current anchor relative-L2 ceilings are inherited from the pre-split JAX qualification:

```text
A: 0.005
Q: 0.010
P: 0.005
```

They are numerical/software qualification limits, not clinical accuracy limits.

## Cohort runtime and execution identity

The public API now supports:

```python
generate_parameterized_cohort(..., solver_backend="numpy")  # default/reference
generate_parameterized_cohort(..., solver_backend="jax")    # accelerated backend
```

The CLI exposes the corresponding `--solver-backend numpy|jax` option.

The scientific cohort plan/run ID remains independent of numerical backend. Separately, every newly generated cohort bundle records a SHA-256 `solver_execution_id` over:

- backend;
- numerical scheme ID;
- float64 precision contract;
- frozen solver options.

Resume requires an exact execution descriptor match. A NumPy checkpoint therefore cannot be silently resumed as a JAX run or vice versa.

Runtime provenance separately records backend, numerical scheme and precision while preserving the same Virtual Disease intervention identity.

## Cohort batching boundary

PR #20 first qualifies the accelerated scalar solver. Padded/masked JAX micro-batching is deliberately gated behind that scalar numerical qualification; batching an unqualified time integrator would multiply numerical ambiguity. After the scalar report passes and is inspected, the next optimization is shape/workload-bucketed micro-batching with scalar↔batch equivalence tests. Until then, `solver_backend="jax"` executes subjects sequentially but with the accelerated per-subject solver.

## Durable evidence

The Colab notebook writes:

```text
MyDrive/VascuQuest/jax_split_one_subject_qualification/<code-revision-prefix>/jax-split-one-subject-qualification.json
```

The runner preserves completed case records if a later gate fails, then appends the exception and traceback.

## GitHub Actions

`.github/workflows/parameterized-cohort-release-validation.yml` is deliberately `workflow_dispatch`-only. It executes the same split-solver qualification on a CPU runner as an optional reproducibility route. The Colab GPU notebook is the preferred acceleration/performance route.

Ordinary Core CI and the independent PWDB Core Tier-4 regression remain separate gates. A Tier-4 failure caused solely by an upstream artifact-acquisition error (for example an HTTP gateway timeout) is operationally distinct from a package regression and must be reported as such rather than reclassified as a pass.

Do not merge PR #20 until the durable split-solver report is `PASS`, its operator/convergence/limiter/RKC/anchor evidence has been inspected, and ordinary package regression gates are clean. A PASS qualifies the accelerated backend within the current Virtual Disease model context; it does not establish epidemiological representativeness, clinical outcome validity, diagnostic accuracy or patient-specific prediction.
