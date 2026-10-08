# Virtual Disease public interface

## 1. Status and scientific boundary

Virtual Disease is a complete first-party VascuQuest 1.0 subsystem spanning disease request semantics, deterministic source-subject selection, healthy reconstruction, causal vascular transformation, disease-aware network solving, runtime population materialization, portable bundles, parameterized cohorts, Python access, and CLI access.

The scientific boundary remains:

```text
EvidenceClass = MODELLED
clinical validation = false
population epidemiological representativeness = false
```

A generated Virtual Disease subject is a counterfactual model state, not a clinical observation, diagnosis, prognosis, or validated patient digital twin.

## 2. Public Python namespace

```python
import vascuquest as vq

vq.disease
```

The public namespace exposes:

- frozen disease catalogue/specification helpers;
- `generate_population(...)`;
- deterministic selection contracts;
- runtime disease population/dataset abstractions;
- portable runtime bundle export;
- parameterized cohort request/planning/generation;
- cohort plan read/write;
- cohort bundle inspect/verify helpers.

The public surface does not imply clinical validation.

## 3. Generate a disease population

Example:

```python
population = vq.disease.generate_population(
    patients=5,
    age_group=50,
    condition="carotid_stenosis",
    parameters={
        "side": "left",
        "artery": "common_carotid",
        "nascet_stenosis": 0.60,
        "lesion_length_m": 0.02,
    },
    seed=17,
    source="/path/to/pwdb",
    offline=True,
)
```

Selected subjects retain canonical PWDB subject numbers while belonging to a separate content-addressed `PWDB-VD` dataset identity.

Example pairing:

```text
healthy: PWDB:3275625 / subject 431
disease: PWDB-VD:<run-id> / subject 431
```

The canonical PWDB source artifacts are never modified.

## 4. Frozen presets

The public catalogue exposes exactly four v1 conditions:

```text
carotid_stenosis
iliac_stenosis
fusiform_abdominal_aortic_aneurysm
large_artery_stiffening
```

Use:

```python
vq.disease.presets()
vq.disease.preset(...)
vq.disease.specification(...)
```

or the CLI:

```text
vascuquest disease presets
vascuquest disease describe <CONDITION>
```

Descriptions include parameter names/bounds, assumptions, mechanistic scope, evidence boundary, and citations where implemented.

## 5. Public CLI tree

The current command group is:

```text
vascuquest disease
├── presets
├── describe
├── generate
└── cohort
    ├── plan
    ├── generate
    ├── inspect
    └── verify
```

This is the current v1 public surface; the cohort commands are not future work.

## 6. Inspect the frozen presets

```bash
vascuquest disease presets --format json
```

Inspect one preset:

```bash
vascuquest disease describe carotid_stenosis --format json
```

The CLI reports `MODELLED` scientific status and the absence of clinical validation.

## 7. Generate a population from CLI

Representative carotid-stenosis workflow:

```text
vascuquest disease generate carotid_stenosis \
  --patients 5 \
  --age 50 \
  --param side=left \
  --param artery=common_carotid \
  --param nascet_stenosis=0.60 \
  --param lesion_length_m=0.02 \
  --seed 17 \
  --source /path/to/pwdb \
  --offline
```

Exact options are available through command help. The CLI uses the same disease specification and runtime generation path as the Python API.

## 8. Solver backend selection

The NumPy backend is the frozen/reference default for Virtual Disease execution.

Where the public command/API permits it, the optional JAX backend can be selected explicitly. Backend selection is part of execution identity and does not change the underlying disease condition/specification.

JAX availability requires the optional `jax` installation extra.

## 9. Quantity availability

The runtime dataset explicitly declares the disease-state status of public quantities.

Examples:

```text
pressure                RECOMPUTED
flow_velocity           RECOMPUTED
luminal_area             RECOMPUTED
flow_rate                DERIVED_FROM_RECOMPUTED
photoplethysmogram       NOT_SUPPORTED
age                      UNCHANGED_CAUSAL_INPUT
heart_rate               UNCHANGED_CAUSAL_INPUT
stroke_volume            UNCHANGED_CAUSAL_INPUT
cardiac_output           RECOMPUTED
brachial_systolic_pressure DERIVED_FROM_RECOMPUTED
aortic_pulse_wave_velocity NOT_SUPPORTED
aortic_augmentation_index  NOT_SUPPORTED
pressure_onset_time        NOT_SUPPORTED
vascular_geometry          MODEL_PARAMETER_MODIFIED
```

Unsupported disease-state quantities do not silently fall back to healthy source values.

## 10. Runtime bundle export

The public namespace includes:

```python
vq.disease.write_runtime_bundle(...)
```

Portable bundles retain the generated scientific results and the identity/provenance/checksum/status context required for downstream audit/reuse.

Use persisted bundles when repeated downstream analysis is needed; statistics, mechanics, spectral analysis, plotting, and HEMOSPACE response calculations should not rerun the disease solver merely to reproduce already persisted model outputs.

## 11. Parameterized cohorts

Parameterized disease cohorts define heterogeneous designed counterfactual populations across source-age and severity intervals while retaining the four frozen disease models.

### Python

Representative public functions include:

```python
plan = vq.disease.create_parameterized_cohort_plan(...)
path = vq.disease.generate_parameterized_cohort(...)
summary = vq.disease.inspect_parameterized_cohort_bundle(path)
verification = vq.disease.verify_parameterized_cohort_bundle(path)
```

Plans can also be persisted/reloaded with the public plan read/write helpers.

### CLI plan

```text
vascuquest disease cohort plan <CONDITION> \
  --patients <N> \
  --age-min <AGE> \
  --age-max <AGE> \
  --severity-min <VALUE> \
  --severity-max <VALUE> \
  --plan cohort-plan.json \
  ...
```

Planning freezes source-supported subjects and subject-specific executable severities **without solving the population**.

### CLI generate

```text
vascuquest disease cohort generate \
  --plan cohort-plan.json \
  --bundle cohort-run \
  --solver-backend numpy \
  ...
```

Generation executes the frozen plan through the complete disease solver and persists the cohort bundle. Resume behavior is available through the documented CLI option.

### CLI inspect/verify

```text
vascuquest disease cohort inspect cohort-run
vascuquest disease cohort verify cohort-run
```

Verification checks plan identity, subject completeness, and bundle SHA-256 integrity.

## 12. Cohort scientific interpretation

A parameterized cohort is explicitly:

```text
designed_counterfactual_not_epidemiological
```

Age filtering uses source PWDB ages only. New ages are not interpolated.

Subject-specific disease-transform admissibility is respected. Invalid severity/subject combinations are rejected explicitly rather than silently repaired or clamped.

See [`VIRTUAL_DISEASE_COHORTS.md`](VIRTUAL_DISEASE_COHORTS.md).

## 13. HEMOSPACE response analysis

A complete parameterized disease bundle can be consumed by HEMOSPACE:

```python
response = hs.response("./cohort-run", "2104")
```

or through the corresponding HEMOSPACE CLI.

The response layer verifies persisted scientific-result identity/checksums and reports healthy baseline, modelled disease value, and change without rerunning the solver.

Interpretation:

```text
paired_counterfactual_model_response_not_clinical_treatment_effect
```

## 14. VascuQuest 1.0 analysis stack

Runtime disease results can be consumed by the new v1 research layers:

```python
vq.stats
vq.mechanics
vq.spectral
vq.plot
```

These namespaces analyze existing `ScientificResult`/`Waveform` objects. They do not mutate Virtual Disease physics or invoke a new solver run implicitly.

## 15. Errors and admissibility

Public APIs/commands fail explicitly for invalid requests, unavailable source data, anatomically inadmissible disease parameters, integrity failures, unsupported quantities, or missing optional capabilities.

The system must not:

- clamp an invalid disease request silently;
- swap arteries;
- substitute healthy output for unsupported disease output;
- infer clinical meaning from a model parameter;
- continue after bundle/checksum inconsistency as if the result were valid.

## 16. Reproducibility

A reusable disease experiment should retain:

- parent dataset identity;
- condition and complete parameters;
- selected canonical subject IDs;
- seed/planning identity;
- run or cohort-plan identity;
- solver backend/execution identity;
- quantity statuses;
- result provenance/warnings;
- bundle checksums;
- VascuQuest version.

## 17. Non-claims

The public interface does not claim:

- patient-specific clinical prediction;
- diagnosis/prognosis;
- treatment/device efficacy;
- epidemiological disease prevalence;
- clinical cfPWV equivalence;
- plaque/ILT/thrombosis/rupture modeling;
- three-dimensional CFD or FSI;
- support for disease-state quantities marked `NOT_SUPPORTED`.

## 18. Related documentation

- [`VIRTUAL_DISEASE.md`](VIRTUAL_DISEASE.md)
- [`VIRTUAL_DISEASE_RECONSTRUCTION.md`](VIRTUAL_DISEASE_RECONSTRUCTION.md)
- [`VIRTUAL_DISEASE_PHYSICS.md`](VIRTUAL_DISEASE_PHYSICS.md)
- [`VIRTUAL_DISEASE_RUNTIME.md`](VIRTUAL_DISEASE_RUNTIME.md)
- [`VIRTUAL_DISEASE_COHORTS.md`](VIRTUAL_DISEASE_COHORTS.md)
- [`PARAMETERIZED_COHORT_QUALIFICATION.md`](PARAMETERIZED_COHORT_QUALIFICATION.md)
- [`HEMOSPACE.md`](HEMOSPACE.md)
- [`V1_RESEARCH_PLATFORM.md`](V1_RESEARCH_PLATFORM.md)
