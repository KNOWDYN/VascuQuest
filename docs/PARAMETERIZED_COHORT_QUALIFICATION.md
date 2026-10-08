# JAX Virtual Disease qualification closure

## Decision

The scalar JAX Virtual Disease backend is accepted for merge on the evidence boundary defined in this document. This closure changes the qualification contract only. It does not change the disease model, PWDB baseline reconstruction, NumPy reference solver, JAX solver, cohort planner, runtime materialisation, provenance, execution identity, public API, CLI, package metadata, or any production source file.

Frozen production candidate:

`d68708aab538003c29ae619417cdaf8345fc2b93`

Retained execution-evidence revision:

`19c6a24d5ec571946440927344801d3a0a40e78d`

Machine-readable certificate:

`docs/evidence/JAX_SCALAR_QUALIFICATION.json`

Static closure audit:

`tools/audit_pr20_qualification_closure.py`

## Why the gate changed

The previous PR #20 gate coupled software acceptance to an additional full-network temporal-refinement experiment. That experiment is useful numerical characterisation, but it is not required to establish the narrower release claim made here: that the optional JAX backend implements the frozen Virtual Disease semidiscrete model, preserves the disease transformations and execution identity, and has already executed the four frozen disease cases on the real 116-segment PWDB network.

The temporal-refinement experiment is therefore retained as optional extended numerical characterisation. Its absence is not a failed test and is not represented as evidence of second-order convergence on the complete PWDB network.

## Qualification layers

### A. Scientific-model integrity

The scientific model remains frozen. Existing disease tests cover anatomical targeting and the four supported disease families: carotid stenosis, iliac stenosis, fusiform abdominal aortic aneurysm, and large-artery stiffening. No disease coefficient, target artery, geometry transform, wall-mechanics relation, PWDB interpretation, or clinical boundary is changed by this closure.

The healthy reconstruction qualification state also remains unchanged:

`METRICS_ONLY_THRESHOLDS_NOT_FROZEN`

All generated Virtual Disease outputs remain `MODELLED` counterfactual haemodynamics. This qualification does not establish clinical validation, diagnostic accuracy, prognosis, epidemiological representativeness, or patient-specific prediction.

### B. Mathematical implementation integrity

The frozen NumPy `DiseaseOneDSolver` remains the scientific semidiscrete reference. The optional JAX backend uses the structure-preserving scheme:

`jax-exact-loss-rkc2-voigt-ssprk2-v1`

with symmetric composition:

1. exact Young–Seeley focal-loss half step;
2. globally coupled PWDB Voigt RKC2 half step;
3. hyperbolic/network SSP-RK2 full step;
4. globally coupled PWDB Voigt RKC2 half step;
5. exact Young–Seeley focal-loss half step.

The existing qualification harness compares NumPy and JAX on the complete semidiscrete RHS, terminal-capacitor derivatives, stability timestep, hyperbolic CFL rate, and Voigt diffusion rate on identical non-trivial states.

The exact focal-loss propagator is independently covered by analytical/invariant tests for identity, zero flow, sign preservation, strict dissipation, semigroup consistency, pure-linear and pure-quadratic exact limits, coefficient validation, and rejection of nonzero excess inertance.

The retained qualification evidence at revision `19c6a24d5ec571946440927344801d3a0a40e78d` records all four accelerated disease solves and operator gates as passed. The current qualification code additionally enforces a Git-diff lineage check before such evidence can be reused.

### C. Software-system integrity

Backend choice is separate from scientific cohort identity. NumPy remains the default/reference backend; JAX is optional. The execution descriptor records backend, numerical scheme, float precision, and solver options in a deterministic `solver_execution_id`.

Existing regression tests require that:

- NumPy and JAX execution identities differ while the scientific plan remains unchanged;
- execution IDs are deterministic and solver-option-sensitive;
- runtime provenance uses the canonical execution descriptor;
- an execution-aware subject is not complete without its matching descriptor;
- a NumPy/JAX resume mismatch is rejected before mutating the bundle.

The frozen production candidate `d68708aab538003c29ae619417cdaf8345fc2b93` passed ordinary Core CI and independent real-PWDB Core release validation before this documentation-only closure.

### D. Existing empirical execution evidence

The retained evidence boundary establishes real-network execution for the same frozen scalar JAX backend across:

- carotid stenosis;
- iliac stenosis;
- fusiform abdominal aortic aneurysm;
- large-artery stiffening.

The qualification harness requires a complete 116-segment result, finite area/flow/pressure, strictly positive area, finite derived velocity, periodic convergence, preserved disease specification, and current NumPy/JAX operator equivalence.

The current production candidate may rely on retained execution evidence only when the numerical/scientific implementation paths are unchanged. The closure audit makes that lineage requirement explicit and also proves that this closure itself changes no `src/` file or `pyproject.toml` relative to the frozen production candidate.

## Acceptance claim

The accepted claim is deliberately bounded:

> The optional scalar JAX backend is a qualified implementation of the frozen Virtual Disease v1 semidiscrete model for the four supported disease transformations, with preserved execution/provenance identity and retained successful real-network execution evidence.

The following claims are explicitly **not** made by this qualification:

- empirical temporal convergence order >= 1.5 on the complete 116-artery PWDB problem;
- clinical validation or patient-specific clinical prediction;
- epidemiological representativeness;
- diagnostic or prognostic accuracy;
- GPU padded/shape-bucketed cohort micro-batch equivalence;
- population-scale throughput or performance guarantees.

## Extended numerical characterisation

The following files remain useful research/benchmark tools but are no longer release blockers:

- `tests/full_data/jax_split_one_subject_qualification.py`;
- `tests/full_data/jax_split_temporal_refinement.py`;
- `notebooks/jax_split_one_subject_qualification_colab.ipynb`.

They may be run later when a numerical-research or performance question justifies the compute. Their results can extend the evidence record but are not needed to merge the scalar disease engine.

## Heavy workflow retirement

The dedicated `parameterized-cohort-release-validation.yml` workflow is removed by the closure commit. This prevents the superseded 180-minute PWDB/JAX qualification route from being treated as an operational release requirement or consuming Actions minutes accidentally.

The underlying full-data scripts and notebook are retained. No scientific evidence is deleted.

## Static closure audit

The zero-compute audit performs only Git and JSON checks. It does not import JAX, open PWDB, execute a solver, or access the network. It verifies:

1. the frozen production and retained-evidence revisions exist;
2. protected numerical/scientific paths are unchanged between the retained evidence revision and frozen production revision;
3. `src/` and `pyproject.toml` are unchanged between the frozen production revision and the closure HEAD;
4. the machine-readable certificate names the exact revisions and bounded claims;
5. the retired heavy workflow is absent from the closure HEAD.

Run locally, if desired:

```bash
python tools/audit_pr20_qualification_closure.py
```

A `PASS` from that script is a provenance/lineage audit, not a new numerical experiment.

## Merge boundary

This closure is ready for manual merge when its diff from `d68708aab538003c29ae619417cdaf8345fc2b93` contains no production-source or package-metadata changes and the certificate/audit agree with this document.

After merge, the scalar Virtual Disease engine should be treated as the completed development boundary for this sprint. GPU micro-batching remains deferred until demonstrated user throughput needs justify a separate optimisation effort.
