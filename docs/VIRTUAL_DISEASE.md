# Virtual Disease in VascuQuest 1.0

## 1. Purpose

Virtual Disease is VascuQuest's first-party mechanistic counterfactual disease subsystem. It starts from a canonical healthy PWDB virtual subject, applies one explicit causal vascular intervention, solves the resulting one-dimensional cardiovascular model, and materializes a separate `PWDB-VD` modelled population.

A Virtual Disease subject is a **counterfactual simulation state**, not a patient, diagnosis, prognosis, or clinically validated digital twin.

All disease-state outputs have `MODELLED` scientific meaning unless an explicitly documented downstream derivation is calculated from those modelled outputs.

## 2. Frozen v1 disease conditions

Exactly four first-party disease conditions are frozen for the v1 contract:

- `carotid_stenosis`;
- `iliac_stenosis`;
- `fusiform_abdominal_aortic_aneurysm`;
- `large_artery_stiffening`.

Additional disease conditions require a separate scientific definition, implementation, and qualification programme.

## 3. End-to-end pipeline

```text
canonical PWDB DatasetSession
        ↓
deterministic source-subject selection
        ↓
immutable healthy cardiovascular reconstruction
        ↓
DiseaseSpecification
        ↓
causal DiseasePhysicsModel
        ↓
disease-aware 1-D network solve
        ↓
modelled final cardiac cycle
        ↓
runtime P / U / A / Q + supported scalar/geometry outputs
        ↓
PWDB-VD:<content-addressed-run-id>
        ↓
portable bundle / parameterized cohort / HEMOSPACE response / v1 analysis
```

The canonical PWDB source artifacts are never modified.

## 4. Public request model

A disease population request identifies:

- requested subject count;
- source PWDB age group;
- one frozen disease condition/specification;
- explicit disease parameters;
- deterministic subject-selection seed;
- exact parent dataset identity.

Disease specifications contain causal intervention parameters only. They do not contain prescribed output pressure/flow/area waveforms or desired haemodynamic results.

## 5. Deterministic selection

Eligible source subjects are selected from the requested PWDB age group without replacement using deterministic SHA-256 ranking based on the request seed.

Selected subjects retain their canonical PWDB subject numbers. Thus a source and disease subject remain pairable by canonical ID:

```text
PWDB:3275625 / subject 431
PWDB-VD:<run-id> / subject 431
```

The two `SubjectKey` values are not identical because the healthy and disease subjects belong to different dataset identities.

## 6. Healthy reconstruction

Before any disease transformation, VascuQuest reconstructs a solver-ready healthy parent state from verified PWDB source inputs and geometry.

The healthy aortic inflow is preserved from source waveforms through:

```text
Q(t) = U(t) A(t)
```

The reconstruction/forward-solver layer is scientifically separate from disease transforms so disease parameters cannot be used to compensate silently for baseline error.

See [`VIRTUAL_DISEASE_RECONSTRUCTION.md`](VIRTUAL_DISEASE_RECONSTRUCTION.md).

## 7. Causal disease physics

### Carotid stenosis

Supports left/right common or internal carotid targets. A NASCET-style diameter stenosis is imposed as a smooth raised-cosine lumen reduction over an explicit lesion length/location, with an excess stenosis pressure-loss term based on the implemented Young/Seeley formulation.

### Iliac stenosis

Supports left/right common or external iliac targets with the same principle: explicit focal smooth geometric narrowing plus qualified excess pressure-loss behavior.

### Fusiform abdominal aortic aneurysm

Applies a smooth idealized fusiform dilation over the frozen main abdominal-aortic path. The model changes one-dimensional lumen/wall coefficients and recomputes network haemodynamics.

It does not model three-dimensional sac recirculation, intraluminal thrombus, asymmetric wall geometry, rupture, or remodeling.

### Large-artery stiffening

Applies a conduit-wall stiffness transformation targeting a requested model-space carotid-femoral PWV response through the qualified stiffness parameterization.

It is not a clinical tonometry procedure or arterial-age diagnostic.

See [`VIRTUAL_DISEASE_PHYSICS.md`](VIRTUAL_DISEASE_PHYSICS.md).

## 8. Solver and backends

The first-party solver represents the full source arterial network using the documented compliant one-dimensional arterial model, disease-aware geometry/wall properties, boundary/junction coupling, terminal beds, and explicit disease losses where required.

The NumPy implementation is the reference/default execution path. An optional JAX backend implements the same declared semidiscrete disease model within its documented qualification boundary.

Backend identity and solver execution identity are part of reproducibility. Availability of a faster backend does not change the scientific disease definition.

## 9. Runtime dataset identity

Each generated disease population receives a separate exact dataset identity:

```text
dataset_family        = PWDB-VD
record_id             = <content-addressed run ID>
persistent_identifier = urn:vascuquest:virtual-disease:<run-id>
schema_version        = parent PWDB schema version
```

The run identity incorporates the parent dataset identity, selected canonical subject IDs, disease request/specification, selection seed, and relevant contract/version information.

See [`VIRTUAL_DISEASE_RUNTIME.md`](VIRTUAL_DISEASE_RUNTIME.md).

## 10. Quantity-status contract

Disease-state availability is explicit. VascuQuest never falls back silently to a healthy source value when the disease state has not been recomputed.

Current v1 status classes are:

- `UNCHANGED_CAUSAL_INPUT`;
- `MODEL_PARAMETER_MODIFIED`;
- `RECOMPUTED`;
- `DERIVED_FROM_RECOMPUTED`;
- `NOT_SUPPORTED`.

The current runtime mapping includes:

| Quantity | Disease-state status |
|---|---|
| pressure | `RECOMPUTED` |
| flow velocity | `RECOMPUTED` |
| luminal area | `RECOMPUTED` |
| flow rate | `DERIVED_FROM_RECOMPUTED` |
| photoplethysmogram | `NOT_SUPPORTED` |
| age | `UNCHANGED_CAUSAL_INPUT` |
| heart rate | `UNCHANGED_CAUSAL_INPUT` |
| stroke volume | `UNCHANGED_CAUSAL_INPUT` |
| cardiac output | `RECOMPUTED` |
| brachial systolic pressure | `DERIVED_FROM_RECOMPUTED` |
| aortic pulse-wave velocity | `NOT_SUPPORTED` |
| aortic augmentation index | `NOT_SUPPORTED` |
| pressure onset time | `NOT_SUPPORTED` |
| vascular geometry / wall state | `MODEL_PARAMETER_MODIFIED` |

A `NOT_SUPPORTED` disease-state quantity must remain unavailable rather than inheriting the healthy value.

## 11. Runtime waveforms

Supported runtime haemodynamic vectors include modelled:

```text
P
U
A
Q = U * A
```

at the 13 canonical common measurement sites where the runtime contract supports them.

Runtime disease-qualified source/vector labels are condition-specific while the canonical scientific quantity identity remains stable.

## 12. Portable runtime bundles

Virtual Disease can export portable bundles containing the scientific results and metadata needed to audit/reuse a generated population, including as applicable:

- run/request identity;
- exact subject IDs;
- result JSON documents;
- provenance records;
- checksums;
- quantity statuses;
- scientific warnings;
- reconstruction/qualification state.

Bundles are intended to support reproducible downstream analysis without rerunning the solver.

## 13. Parameterized disease cohorts

The parameterized cohort engine extends the four frozen disease models into designed counterfactual populations over source-age and disease-severity ranges.

It provides:

- deterministic cohort planning before time integration;
- source-age filtering without interpolation of new ages;
- deterministic severity assignment;
- subject-specific admissibility using the deployed disease transform itself;
- explicit rejection records rather than silent parameter clamping;
- stable cohort-plan identity;
- generation and bundle verification.

Parameterized cohorts remain `MODELLED` designed populations, not epidemiological samples.

See [`VIRTUAL_DISEASE_COHORTS.md`](VIRTUAL_DISEASE_COHORTS.md) and [`PARAMETERIZED_COHORT_QUALIFICATION.md`](PARAMETERIZED_COHORT_QUALIFICATION.md).

## 14. Public Python API

```python
import vascuquest as vq

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

The namespace also exposes preset/specification inspection, deterministic selection, runtime bundle export, parameterized cohort planning/generation, and cohort bundle inspection/verification.

See [`VIRTUAL_DISEASE_PUBLIC.md`](VIRTUAL_DISEASE_PUBLIC.md).

## 15. Public CLI

Main group:

```text
vascuquest disease
```

Core commands include:

```text
vascuquest disease presets
vascuquest disease describe <CONDITION>
vascuquest disease generate <CONDITION> ...
vascuquest disease cohort ...
```

CLI behavior is an adapter over the same public disease contracts used by Python.

## 16. HEMOSPACE integration

HEMOSPACE can consume an existing complete parameterized Virtual Disease bundle and pair persisted disease outputs with the matching healthy PWDB record.

It verifies bundle/result identity/checksums and calculates endpoint changes without rerunning the solver.

The correct interpretation is:

```text
paired_counterfactual_model_response_not_clinical_treatment_effect
```

## 17. VascuQuest 1.0 analysis integration

The new v1 analysis layers are downstream only:

```text
Virtual Disease ScientificResult / Waveform
        ↓
vascuquest.analysis identity/alignment checks
        ↓
vascuquest.mechanics / spectral
        ↓
vascuquest.stats
        ↓
vascuquest.plot
```

They do not alter disease geometry, loss models, solver equations, boundary conditions, or qualification state.

Examples include:

- paired healthy/disease pressure or flow response statistics;
- mechanics descriptors derived from modelled pressure/area waveforms;
- pressure-flow impedance changes;
- wave-intensity changes;
- publication figures from persisted modelled results.

## 18. Scientific qualification boundary

Virtual Disease is a mechanistic research model. Its qualification evidence establishes behavior only within the explicitly tested numerical/model domain.

It does not claim:

- clinical validation;
- patient-specific prediction;
- epidemiological representativeness;
- treatment efficacy;
- plaque vulnerability;
- thrombosis/stroke/rupture risk;
- three-dimensional flow or wall mechanics;
- intraluminal thrombus or remodeling in the AAA preset.

## 19. Reproducibility requirements

A reported Virtual Disease experiment should retain:

- parent PWDB identity;
- canonical subject IDs;
- disease condition/specification/parameters;
- selection seed;
- run/execution identity;
- backend/scheme identity where material;
- quantity statuses;
- result provenance/warnings;
- bundle checksums/identity if persisted;
- VascuQuest version;
- relevant method/source citations.

## 20. Related documentation

- [`VIRTUAL_DISEASE_RECONSTRUCTION.md`](VIRTUAL_DISEASE_RECONSTRUCTION.md)
- [`VIRTUAL_DISEASE_PHYSICS.md`](VIRTUAL_DISEASE_PHYSICS.md)
- [`VIRTUAL_DISEASE_RUNTIME.md`](VIRTUAL_DISEASE_RUNTIME.md)
- [`VIRTUAL_DISEASE_PUBLIC.md`](VIRTUAL_DISEASE_PUBLIC.md)
- [`VIRTUAL_DISEASE_COHORTS.md`](VIRTUAL_DISEASE_COHORTS.md)
- [`PARAMETERIZED_COHORT_QUALIFICATION.md`](PARAMETERIZED_COHORT_QUALIFICATION.md)
- [`HEMOSPACE.md`](HEMOSPACE.md)
- [`V1_RESEARCH_PLATFORM.md`](V1_RESEARCH_PLATFORM.md)
