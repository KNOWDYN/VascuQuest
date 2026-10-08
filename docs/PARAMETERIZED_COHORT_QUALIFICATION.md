# Parameterized Virtual Disease cohort qualification

## 1. Purpose

This document defines the qualification boundary for the VascuQuest parameterized Virtual Disease cohort subsystem (`vdc1`).

The subsystem does **not** introduce new disease equations. It plans heterogeneous source-subject/severity assignments and executes them through the already deployed/qualified Virtual Disease reconstruction, causal transforms, and full-network solver.

A parameterized cohort is a **designed counterfactual virtual population**, not an epidemiological population of patients.

## 2. Scientific boundary

```text
EvidenceClass = MODELLED
clinical validation = false
epidemiological representativeness = false
healthy reconstruction gate = METRICS_ONLY_THRESHOLDS_NOT_FROZEN
```

The reconstruction-gate label is retained exactly because it is part of this qualification lineage. It is not a statement that the VascuQuest 1.0 cohort implementation or downstream research platform is unfinished; it records the reconstruction-threshold state attached to the frozen evidence used by this qualified subsystem.

Qualification of the cohort system concerns deterministic planning, subject/severity admissibility, execution identity, persistence, resumability, and integrity. It does not convert Virtual Disease outputs into clinical evidence.

## 3. Contract version

The parameterized cohort contract is versioned independently from the base disease contract. The public Python API exposes the current parameterized-cohort contract constant and frozen plan/request objects.

A persisted plan/bundle must retain the contract/version needed to interpret its identity and assignments.

## 4. Supported source-age design

The cohort request specifies:

- `patients`;
- `age_min`;
- `age_max`;
- disease condition;
- `severity_min`;
- `severity_max`;
- fixed disease parameters;
- deterministic seed.

Age bounds filter **existing source-supported PWDB ages**. The cohort planner does not interpolate synthetic intermediate ages.

## 5. Frozen severity dimensions

Exactly one disease severity parameter varies within one cohort plan:

| Condition | Severity parameter |
|---|---|
| `carotid_stenosis` | `nascet_stenosis` |
| `iliac_stenosis` | `diameter_stenosis` |
| `fusiform_abdominal_aortic_aneurysm` | `maximum_diameter_m` |
| `large_artery_stiffening` | `target_cfpwv_m_per_s` |

All other preset parameters are fixed for that plan.

This preserves an interpretable one-dimensional disease-severity design while allowing source physiology to vary across subjects.

## 6. Deterministic planning qualification

The planner is qualified by contract/tests to perform the following sequence before solver execution:

1. read actual source PWDB ages;
2. retain subjects within the requested source-age interval;
3. rank eligible canonical subject IDs deterministically from the seed;
4. generate deterministic stratified severity assignments within the exact requested interval;
5. assemble each candidate subject's real healthy baseline;
6. call the deployed `transform_disease(...)` on the exact subject/severity;
7. record rejected candidates and exact admissibility reasons;
8. never clamp or repair an inadmissible severity silently;
9. freeze accepted assignments in deterministic canonical order.

The cohort planner therefore delegates anatomical/physics admissibility to the deployed disease transformation rather than duplicating lesion-fit, AAA, or cfPWV rules.

## 7. Plan identity

The frozen plan identity includes the scientific design needed for reproducibility, including:

- parent dataset identity;
- request fields;
- supported source-age information;
- accepted canonical subject IDs;
- exact source ages;
- exact assigned disease parameters/severities;
- rejected candidate records;
- planner/contract version.

A plan is therefore more than a list of subject numbers.

## 8. Planner matching and subject identity

Qualification tests require deterministic source/assignment matching and preservation of canonical PWDB subject IDs.

Healthy/disease relationship:

```text
PWDB:3275625 / subject <ID>
PWDB-VD:<cohort-run-id> / subject <same ID>
```

Subjects are never renumbered to `1..N` inside the cohort merely for convenience.

## 9. Execution model

Generation consumes a previously frozen plan.

For each assignment, the generator constructs the ordinary one-subject Virtual Disease request/run identity and uses the existing subject materialization path. Thus every accepted subject executes:

```text
healthy reconstruction
    ↓
existing transform_disease(...)
    ↓
complete disease network solver
    ↓
periodic-convergence gate
    ↓
persisted subject outputs
```

The parameterized cohort layer does not contain a second or simplified haemodynamic solver.

## 10. Full-network preservation

For every completed cohort subject, the bundle preserves the converged final cardiac cycle over the full 116-segment network.

Per-segment persisted fields include:

- axial coordinate;
- luminal-area history;
- volumetric-flow history;
- pressure history.

A common time coordinate is stored. Mean velocity remains derivable as `U=Q/A`.

This full-network persisted layer is additional to ordinary disease `ScientificResult` outputs at canonical measurement sites.

## 11. Streaming/memory boundary

The cohort generator processes assignments sequentially rather than retaining the entire population's heavy runtime state in memory.

A completed subject is persisted atomically and released before the next assignment proceeds.

This behavior is part of the operational qualification boundary because it allows large designed cohorts to be generated without changing disease physics or requiring population-wide in-memory arrays.

## 12. Bundle structure and integrity

The cohort bundle contains plan/assignment metadata, logs, and per-subject artifacts. The documented structure includes:

```text
manifest.json
plan.json
assignments.json
assignments.csv
logs/
subjects/
  <canonical-subject-id>/
    COMPLETE
    subject_manifest.json
    diagnostics.json
    full_network.npz
    full_network_index.json
    results/*.json
    provenance/*.json
```

Per-subject manifests record scientific identity, assigned parameters, solver diagnostics, network segment count, and SHA-256/size information for persisted artifacts.

The top-level manifest records completed-subject manifest hashes.

## 13. Atomic completion semantics

A subject is considered complete only after its persisted artifacts and completion marker satisfy the bundle contract.

Interrupted/partial writes must not be interpreted as successful scientific results.

The bundle design therefore makes completion state explicit rather than inferring it from the presence of some files.

## 14. Resume qualification

Resume behavior verifies existing completed subject checkpoints before skipping them.

A resume with incompatible execution identity/backend must be rejected rather than combining results generated under inconsistent solver execution descriptors.

This prevents “resume” from silently creating a scientifically heterogeneous bundle.

## 15. Solver execution identity

Scientific cohort-plan identity and numerical execution identity are distinct.

The same scientific plan may in principle be executed with an explicitly selected qualified backend, but the resulting execution descriptor must record the backend/scheme/options and produce the corresponding deterministic solver execution identity.

NumPy remains the reference/default backend. JAX is optional and subject to its separate qualification boundary documented in [`JAX_VIRTUAL_DISEASE_QUALIFICATION.md`](JAX_VIRTUAL_DISEASE_QUALIFICATION.md).

## 16. CLI qualification surface

The public CLI exposes:

```text
vascuquest disease cohort plan
vascuquest disease cohort generate
vascuquest disease cohort inspect
vascuquest disease cohort verify
```

The `plan` command freezes the design without solving haemodynamics.

The `generate` command executes the frozen plan through the complete disease solver and persists the bundle.

The `inspect` command reports request/assignment/progress/scientific-boundary metadata.

The `verify` command verifies identity/completeness/checksum integrity. `verify` is not medical validation.

## 17. Python qualification surface

The public namespace exposes, among other cohort contracts:

- `create_parameterized_cohort_plan(...)`;
- `generate_parameterized_cohort(...)`;
- `inspect_parameterized_cohort_bundle(...)`;
- `verify_parameterized_cohort_bundle(...)`;
- `write_cohort_plan(...)`;
- `read_cohort_plan(...)`.

Python and CLI behavior share the same planner/generator/bundle contracts.

## 18. Regression/contract coverage

Repository tests cover the parameterized-cohort contracts, including dedicated tests for:

- request/plan contract and deterministic planning;
- planner matching and admissibility behavior;
- public CLI surface;
- runtime identity and bundle behavior;
- solver execution identity/resume compatibility.

Relevant test modules include:

```text
tests/disease/cohort/test_contract_and_planner.py
tests/disease/cohort/test_planner_matching.py
tests/disease/cohort/test_parameterized_cohort_cli_surface.py
tests/disease/cohort/test_runtime_identity_and_bundle.py
tests/disease/cohort/test_solver_execution_identity.py
```

Full-data staging tools may extend execution evidence but are not a reason to rerun an expensive whole cohort for every downstream documentation/analysis change.

## 19. Relationship to underlying disease qualification

The cohort layer inherits—not replaces—the scientific qualification of:

- healthy reconstruction;
- the four disease transforms;
- NumPy reference solver;
- optional JAX backend within its separate certificate.

Changing disease equations/physics would require re-evaluating that upstream qualification; it cannot be justified by cohort-planner tests alone.

## 20. HEMOSPACE consumption

HEMOSPACE can consume complete cohort bundles and compute verified paired healthy-to-modelled response records without rerunning the solver.

This downstream use depends on bundle identity/checksum integrity established by the cohort persistence contract.

## 21. VascuQuest 1.0 downstream analytics

The completed v1 analysis stack is outside the cohort qualification boundary but is designed to consume qualified persisted cohort outputs:

```text
verified cohort bundle
        ↓
HEMOSPACE response / ScientificResult loading
        ↓
vascuquest.analysis
        ↓
vascuquest.mechanics / vascuquest.spectral
        ↓
vascuquest.stats
        ↓
vascuquest.plot
```

This downstream analysis does not widen the cohort qualification claim and does not require a solver rerun merely to calculate deterministic post-processing quantities.

For cohort inference:

- preserve canonical subject IDs;
- compute subject-level mechanics/spectral descriptors before statistical analysis;
- use paired methods for matched healthy/disease results;
- do not treat time samples/frequency bins as independent subjects;
- do not interpret designed-cohort empirical frequencies as epidemiological probability.

## 22. Population interpretation

The cohort system guarantees a deterministic designed experiment over source-supported virtual subjects and requested severity ranges.

It explicitly does **not** guarantee that:

- source-age frequencies match real populations;
- severity distribution matches clinical prevalence;
- disease/physiology joint distributions match humans;
- cohort frequency can be reported as incidence/prevalence;
- modelled endpoint distributions are clinical outcome distributions.

Any epidemiological weighting would require an external sourced and separately versioned population model.

## 23. Non-claims

Parameterized cohort qualification does not establish:

- clinical validation;
- diagnostic/prognostic accuracy;
- patient-specific prediction;
- treatment efficacy;
- epidemiological representativeness;
- support for disease-state quantities marked `NOT_SUPPORTED`;
- GPU microbatch equivalence or population-throughput guarantees.

## 24. Documentation/evidence precedence

This human-readable document describes the qualified cohort boundary in the current VascuQuest 1.0 documentation set. Frozen machine-readable evidence and historical closure/audit material retain their original revision-specific wording.

Current platform capabilities should be read from `docs/README.md` and the governing v1 contracts; frozen evidence should be used for the exact qualification claim it records.

## 25. Related documentation

- [`VIRTUAL_DISEASE_COHORTS.md`](VIRTUAL_DISEASE_COHORTS.md)
- [`VIRTUAL_DISEASE.md`](VIRTUAL_DISEASE.md)
- [`VIRTUAL_DISEASE_RUNTIME.md`](VIRTUAL_DISEASE_RUNTIME.md)
- [`VIRTUAL_DISEASE_RECONSTRUCTION.md`](VIRTUAL_DISEASE_RECONSTRUCTION.md)
- [`JAX_VIRTUAL_DISEASE_QUALIFICATION.md`](JAX_VIRTUAL_DISEASE_QUALIFICATION.md)
- [`HEMOSPACE.md`](HEMOSPACE.md)
- [`ANALYSIS.md`](ANALYSIS.md)
- [`STATS.md`](STATS.md)
