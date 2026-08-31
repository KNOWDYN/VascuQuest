# Parameterized Virtual Disease cohorts

## Status and scientific boundary

The parameterized cohort engine is an additive Virtual Disease capability. It does not replace or change `generate_population(...)`, the four frozen vd1 presets, disease transformations, `DiseaseOneDSolver`, the ordinary `PWDB-VD` runtime dataset, or `vascuquest disease generate`.

A parameterized cohort is a **designed counterfactual virtual population**, not an epidemiological sample of patients.

```text
EvidenceClass = MODELLED
healthy reconstruction gate = METRICS_ONLY_THRESHOLDS_NOT_FROZEN
clinical validation = false
population epidemiological representativeness = false
```

## Cohort contract

`vdc1` adds three population-level controls around the existing vd1 disease models:

- source age interval: `age_min`, `age_max`;
- disease severity interval: `severity_min`, `severity_max`;
- requested cohort size: `patients`.

Age bounds filter the source ages that actually exist in PWDB. The engine does **not** interpolate new virtual ages.

Exactly one scientifically defined parameter varies for each frozen disease condition:

| Condition | vdc1 severity parameter |
|---|---|
| `carotid_stenosis` | `nascet_stenosis` |
| `iliac_stenosis` | `diameter_stenosis` |
| `fusiform_abdominal_aortic_aneurysm` | `maximum_diameter_m` |
| `large_artery_stiffening` | `target_cfpwv_m_per_s` |

All other preset parameters are fixed for one cohort plan.

## Deterministic planning

Planning occurs before any disease time integration.

1. Read the source PWDB age vector and retain only source subjects whose actual age lies within the requested interval.
2. Rank eligible canonical PWDB subject IDs deterministically using SHA-256 and the cohort seed.
3. Produce one deterministic stratified-uniform severity value per requested subject across the requested interval.
4. Starting from the lowest designed severity, assemble each candidate subject's real PWDB healthy baseline.
5. Call the existing vd1 `transform_disease(...)` with that exact subject and exact candidate severity.
6. If the transform rejects the combination, record the subject ID, source age and exact admissibility reason and continue to the next ranked source subject.
7. Never clamp, repair or silently change a requested severity.
8. Preserve accepted subjects in canonical PWDB order in the frozen plan.

The planner therefore uses the deployed disease-physics implementation itself as the subject-specific admissibility authority. It does not duplicate lesion-fit, AAA geometry or cfPWV admissibility rules.

The plan hash includes the parent dataset identity, request, supported source ages, exact canonical subject IDs, exact source ages, exact assigned disease parameters, rejected candidates and planner/contract versions.

## Python API

```python
import vascuquest as vq

plan = vq.disease.create_parameterized_cohort_plan(
    patients=200,
    age_min=45,
    age_max=75,
    condition="carotid_stenosis",
    severity_min=0.30,
    severity_max=0.80,
    fixed_parameters={
        "side": "left",
        "artery": "common_carotid",
        "lesion_length_m": 0.020,
        "lesion_center_fraction": 0.50,
    },
    seed=42,
    source="/path/to/pwdb",
    offline=True,
)

vq.disease.write_cohort_plan(plan, "cohort-plan.json")

bundle = vq.disease.generate_parameterized_cohort(
    plan,
    destination="./cohort-run",
    source="/path/to/pwdb",
    offline=True,
    resume=True,
)

vq.disease.verify_parameterized_cohort_bundle(bundle)
```

## CLI

The additive command group is:

```text
vascuquest disease cohort
├── plan
├── generate
├── inspect
└── verify
```

Plan a cohort without solving haemodynamics:

```bash
vascuquest disease cohort plan carotid_stenosis \
  --patients 200 \
  --age-min 45 \
  --age-max 75 \
  --severity-min 0.30 \
  --severity-max 0.80 \
  --param side=left \
  --param artery=common_carotid \
  --param lesion_length_m=0.020 \
  --seed 42 \
  --source /path/to/pwdb \
  --offline \
  --plan cohort-plan.json \
  --format json
```

Generate the frozen plan:

```bash
vascuquest disease cohort generate \
  --plan cohort-plan.json \
  --bundle ./cohort-run \
  --source /path/to/pwdb \
  --offline
```

Resume an interrupted cohort:

```bash
vascuquest disease cohort generate \
  --plan cohort-plan.json \
  --bundle ./cohort-run \
  --source /path/to/pwdb \
  --offline \
  --resume
```

Inspect metadata and progress:

```bash
vascuquest disease cohort inspect ./cohort-run --format json
```

Verify persisted integrity:

```bash
vascuquest disease cohort verify ./cohort-run --format json
```

`verify` means content/identity/checksum verification. It is not medical validation.

## Streaming execution

The heterogeneous generator does not accumulate the whole cohort in memory.

For every frozen assignment it:

1. creates an ordinary one-subject vd1 `DiseasePopulationRequest` and `DiseaseRunIdentity` using the exact assigned specification;
2. calls the existing `materialize_subject(...)` implementation unchanged;
3. therefore assembles the subject's healthy PWDB causal state, executes `transform_disease(...)`, and runs the complete `DiseaseOneDSolver`;
4. requires the existing periodic-convergence gate;
5. writes the subject atomically to the cohort bundle;
6. releases the heavy runtime state before moving to the next subject.

This preserves the deployed disease equations and solver as the sole haemodynamic implementation.

## Preserved subject identity

Canonical PWDB numbers are never renumbered.

```text
PWDB:3275625 / subject 431
PWDB-VD:<cohort-run-id> / subject 431
```

`assignments.json`, `assignments.csv`, each subject manifest and all scientific results retain the canonical subject number.

## Full 116-segment solution preservation

The existing solver computes the complete network. The cohort bundle preserves the **final converged cardiac cycle** for all 116 segments for every completed subject.

For each segment it stores:

- axial coordinate `x_m`;
- luminal area history `area_m2`;
- volumetric-flow history `flow_m3_per_s`;
- pressure history `pressure_pa`.

The common time coordinate is stored as `time_s`. Mean velocity remains exactly derivable as `U=Q/A`.

This full-network layer is additional to the ordinary Virtual Disease materialized scientific results at the 13 canonical measurement sites.

## Bundle structure

```text
manifest.json
plan.json
assignments.json
assignments.csv
logs/
  run.log
  errors.jsonl                # only present after an error
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

Each completed subject is written atomically. `subject_manifest.json` records the exact age, disease parameters, assigned severity, per-subject vd1 run ID, solver diagnostics, full-network segment count and SHA-256/size for every persisted scientific artifact.

The top-level manifest records the parameterized cohort run ID and the SHA-256 of each completed subject manifest. Resume verifies existing subject checkpoints before skipping them.

## Interpretation

The engine guarantees that each accepted virtual subject:

- originates from a real source-supported PWDB simulation instance;
- retains its original canonical PWDB subject number and healthy causal configuration;
- lies within the requested source age interval;
- receives a severity within the exact requested range;
- passes the existing subject-specific disease transformation without parameter clamping;
- undergoes a complete 116-segment disease solve;
- is persisted with deterministic assignment and solver provenance.

It does **not** claim that the frequency of ages or severities reproduces the prevalence or joint distribution of disease in living human populations. Such epidemiological weighting would require an explicitly sourced and separately versioned external population model.
