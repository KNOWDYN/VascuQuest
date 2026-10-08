# JAX Virtual Disease qualification closure

## 1. Status

The optional scalar JAX Virtual Disease backend is accepted within the bounded evidence contract recorded by:

```text
docs/evidence/JAX_SCALAR_QUALIFICATION.json
```

This document is the current human-readable location for that qualification. The machine-readable certificate remains the authoritative frozen evidence record.

The qualification changes neither the disease model nor the NumPy reference solver.

## 2. Frozen evidence boundary

The certificate records:

```text
frozen production revision:
  d68708aab538003c29ae619417cdaf8345fc2b93

trusted execution evidence revision:
  19c6a24d5ec571946440927344801d3a0a40e78d

numerical scheme:
  jax-exact-loss-rkc2-voigt-ssprk2-v1
```

The retained evidence is reused only within the explicit numerical/scientific lineage rules defined by the qualification closure.

## 3. Scientific boundary

The certificate preserves:

```text
EvidenceClass = MODELLED
healthy reconstruction gate = METRICS_ONLY_THRESHOLDS_NOT_FROZEN
clinical validation = false
population interpretation = designed modelled counterfactual, not epidemiological
```

The JAX qualification is not a clinical validation claim.

## 4. What the qualification establishes

The frozen certificate records the following as established:

- disease physics is preserved;
- NumPy/JAX semidiscrete operator equivalence was checked within the qualification harness;
- exact focal-loss analytical/invariant tests passed;
- retained real-network execution evidence covers all four frozen disease conditions;
- complete 116-segment execution was required by the retained gate;
- solver execution identity is preserved;
- the frozen production candidate passed core CI and core release validation at the recorded revision;
- numerical-lineage reuse guards are present.

The current VascuQuest 1.0 analytical extensions do not modify the protected Virtual Disease numerical/scientific paths and do not broaden these claims.

## 5. Scheme structure

The qualified scalar JAX backend uses the structure-preserving scheme:

```text
jax-exact-loss-rkc2-voigt-ssprk2-v1
```

with symmetric composition:

1. exact Young/Seeley focal-loss half step;
2. globally coupled PWDB Voigt RKC2 half step;
3. hyperbolic/network SSP-RK2 full step;
4. globally coupled PWDB Voigt RKC2 half step;
5. exact Young/Seeley focal-loss half step.

The NumPy `DiseaseOneDSolver` remains the scientific semidiscrete reference.

## 6. Retained execution evidence

The trusted evidence revision records successful accelerated real-network execution for:

- carotid stenosis;
- iliac stenosis;
- fusiform abdominal aortic aneurysm;
- large-artery stiffening.

The qualification gate required a complete 116-segment result, finite area/flow/pressure, strictly positive area, finite derived velocity, periodic convergence, preserved disease specification, and the recorded NumPy/JAX operator checks.

## 7. Execution identity

Backend choice is separate from scientific cohort identity.

The execution descriptor records, as applicable:

- backend;
- numerical scheme;
- float precision;
- solver options;
- deterministic `solver_execution_id`.

A NumPy/JAX resume mismatch is rejected rather than silently mixing backend provenance inside one persisted cohort.

## 8. Exact focal-loss qualification

The focal stenosis excess-loss propagator has independent analytical/invariant coverage including:

- identity behavior;
- zero-flow behavior;
- sign preservation;
- strict dissipation;
- semigroup consistency;
- pure-linear exact limit;
- pure-quadratic exact limit;
- coefficient validation;
- rejection of unsupported nonzero excess inertance.

## 9. What is explicitly not claimed

The certificate explicitly does **not** claim:

- empirical complete-network temporal order ≥ 1.5;
- clinical validation;
- diagnostic accuracy;
- prognostic accuracy;
- patient-specific clinical prediction;
- epidemiological representativeness;
- GPU padded/shape-bucketed microbatch equivalence;
- population-scale throughput guarantees.

These exclusions remain binding in VascuQuest 1.0 documentation.

## 10. Extended numerical characterization

The following tools remain optional research/benchmark utilities rather than release blockers:

- `tests/full_data/jax_split_one_subject_qualification.py`;
- `tests/full_data/jax_split_temporal_refinement.py`;
- `notebooks/jax_split_one_subject_qualification_colab.ipynb`.

They may extend numerical evidence when a specific scientific/performance question justifies the compute.

Their absence is not evidence of a failed qualification, and no unexecuted convergence result may be claimed.

## 11. Heavy workflow retirement

The superseded long-running parameterized-cohort/JAX release-validation workflow was deliberately retired so it would not remain an operational release requirement or consume Actions minutes accidentally.

The underlying full-data scripts/evidence were retained; retirement of the workflow did not delete scientific evidence.

## 12. Static closure audit

Historical qualification lineage can be inspected with:

```text
python tools/audit_pr20_qualification_closure.py
```

That audit performs Git/JSON lineage checks only. It does not import JAX, read PWDB, or execute a solver.

Because the repository has evolved since the frozen closure—including the completed VascuQuest 1.0 platform—the audit should be interpreted as a historical closure-lineage tool, not as a general assertion that current HEAD is byte-identical to the old frozen production revision.

## 13. Relationship to v1 research analytics

`vascuquest.analysis`, `stats`, `mechanics`, `spectral`, and `plot` are downstream consumers of persisted/modelled results. They do not change the qualified JAX disease equations or widen the backend evidence claim.

No new JAX/full-network run is required merely to validate post-processing mathematics.

## 14. Source of truth

For exact machine-readable qualification fields, use:

- [`evidence/JAX_SCALAR_QUALIFICATION.json`](evidence/JAX_SCALAR_QUALIFICATION.json)

Related scientific/runtime references:

- [`VIRTUAL_DISEASE.md`](VIRTUAL_DISEASE.md)
- [`VIRTUAL_DISEASE_RECONSTRUCTION.md`](VIRTUAL_DISEASE_RECONSTRUCTION.md)
- [`VIRTUAL_DISEASE_PHYSICS.md`](VIRTUAL_DISEASE_PHYSICS.md)
- [`VIRTUAL_DISEASE_RUNTIME.md`](VIRTUAL_DISEASE_RUNTIME.md)
