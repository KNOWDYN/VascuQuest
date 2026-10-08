# Virtual Disease runtime populations

## 1. Purpose

The Virtual Disease runtime layer materializes completed causal disease models into in-memory VascuQuest scientific results and separate virtual-population datasets.

This is a current VascuQuest 1.0 capability. Runtime disease datasets, public generation, portable bundles, and parameterized cohorts are implemented; they are not future stages.

The scientific boundary remains explicit:

```text
EvidenceClass = MODELLED
clinical validation = false
```

A runtime Virtual Disease subject is a counterfactual model state, not a patient observation or diagnosis.

## 2. Runtime pipeline

```text
canonical PWDB DatasetSession
        ↓
deterministic age/source-subject selection
        ↓
immutable healthy parent reconstruction
        ↓
DiseasePhysicsModel
        ↓
DiseaseOneDSolver / qualified backend execution
        ↓
modelled final cardiac cycle
        ↓
materialize supported quantities and geometry state
        ↓
PWDB-VD:<content-addressed-run-id>
```

The canonical PWDB source dataset is never modified.

## 3. Dataset identity

Each generated population receives a new exact dataset identity:

```text
dataset_family        = PWDB-VD
record_id             = <DiseaseRunIdentity.run_id>
persistent_identifier = urn:vascuquest:virtual-disease:<run-id>
schema_version        = parent PWDB schema version
```

The runtime dataset constructor uses the frozen run identity rather than inventing an unrelated identifier.

The content-addressed run identity incorporates the scientific request context, including the parent dataset identity, selected canonical subject IDs, requested population design, disease condition/parameters, and contract/version information.

## 4. Preserved canonical subject numbers

The source PWDB subject number is retained exactly inside the disease dataset:

```text
healthy: PWDB:3275625 / subject 431
disease: PWDB-VD:<run-id> / subject 431
```

The `SubjectKey` objects differ because their dataset identities differ, but the shared canonical subject ID enables explicit matched healthy-versus-disease analysis.

Downstream pairing must use the canonical ID relationship deliberately; it must not pretend the healthy and disease `SubjectKey` objects are the same object.

## 5. Runtime scientific results

Runtime results use the existing VascuQuest scientific result model and preserve:

- disease dataset identity;
- canonical scientific quantity identity;
- canonical subject ID;
- vascular location;
- modelled values;
- method/backend execution context;
- provenance reference;
- warnings and quantity status.

Disease-qualified storage/vector labels do not replace the canonical quantity name. For example, a disease pressure vector remains scientifically `pressure` while the runtime label can encode the disease condition.

## 6. Common-site waveform materialization

The runtime population materializes supported modelled haemodynamic quantities at the 13 canonical common measurement sites.

Supported waveform classes include:

```text
P — pressure
U — flow velocity
A — luminal area
Q — volumetric flow rate
```

`Q` is derived from recomputed modelled velocity and area:

```text
Q = U * A
```

The disease runtime does not reuse the healthy common-site waveform when a quantity is marked as recomputed.

## 7. Quantity-status contract

Every public/runtime disease quantity has one explicit status:

- `UNCHANGED_CAUSAL_INPUT`;
- `MODEL_PARAMETER_MODIFIED`;
- `RECOMPUTED`;
- `DERIVED_FROM_RECOMPUTED`;
- `NOT_SUPPORTED`.

Current v1 mapping:

| Quantity | Status |
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
| vascular geometry / retained wall state | `MODEL_PARAMETER_MODIFIED` |

The purpose of this map is to prevent silent fallback to a healthy source value when the disease state cannot compute the corresponding quantity.

## 8. Geometry state

Runtime disease geometry is a structured model-state output associated with the disease dataset.

`vascular_geometry` is marked `MODEL_PARAMETER_MODIFIED` for every frozen preset because the runtime state retains the geometry and wall-mechanical coefficients needed to reproduce the disease solver state.

For large-artery stiffening, radii may remain unchanged while wall `beta` stiffness changes; the geometry/model-state status therefore still records the modification.

## 9. Runtime store

`RuntimeDiseaseStore` and the runtime dataset abstractions provide content-addressed access to generated populations/results without rewriting the canonical source dataset.

The runtime layer is responsible for keeping healthy-source identity and disease-run identity distinct.

## 10. Solver execution identity

A materialized runtime result retains enough execution identity to distinguish scientifically relevant backend/scheme choices.

The NumPy implementation is the reference/default. Optional JAX execution is separate and must remain within its documented qualification evidence.

A backend choice does not change the disease specification itself.

## 11. Portable runtime bundle

`write_runtime_bundle(...)` exports a portable disease population representation containing, as applicable:

- run identity;
- parent/source identity;
- disease request/specification;
- canonical subject IDs;
- scientific result JSON documents;
- provenance records;
- content checksums;
- quantity statuses;
- runtime/model warnings;
- reconstruction/qualification state.

The purpose is to make downstream analysis reproducible without requiring the network solver to be rerun.

## 12. Bundle integrity

A consumer should treat the bundle manifests/checksums as part of the scientific contract. A result whose checksum or subject/run identity fails verification must not be silently accepted or paired with a healthy record.

HEMOSPACE response analysis explicitly verifies the persisted disease bundle/result identity before computing healthy-to-disease changes.

## 13. Parameterized cohort runtime

The parameterized-cohort layer plans a designed disease population before solver execution and then materializes the accepted assignments through the same deployed disease physics/runtime stack.

The planner records rejected subject/severity combinations explicitly rather than clamping invalid disease requests.

See:

- [`VIRTUAL_DISEASE_COHORTS.md`](VIRTUAL_DISEASE_COHORTS.md)
- [`PARAMETERIZED_COHORT_QUALIFICATION.md`](PARAMETERIZED_COHORT_QUALIFICATION.md)

## 14. Public generation

The runtime is available through:

```python
vq.disease.generate_population(...)
```

and:

```text
vascuquest disease generate ...
```

The same runtime contracts apply to Python and CLI execution.

## 15. HEMOSPACE response consumption

HEMOSPACE can consume a complete persisted parameterized cohort bundle for a canonical subject and calculate:

- healthy endpoint;
- modelled disease endpoint;
- absolute change;
- relative change where defined.

This operation does not rerun the solver.

The correct interpretation is a paired counterfactual model response, not a clinical treatment effect.

## 16. V1 post-processing integration

Once runtime results exist, they can be consumed by:

- `vascuquest.analysis` for identity/alignment;
- `vascuquest.mechanics` for derived pressure-area descriptors;
- `vascuquest.spectral` for impedance/wave/spectral descriptors;
- `vascuquest.stats` for subject/cohort inference;
- `vascuquest.plot` for reproducible figures.

These downstream layers must not mutate the runtime dataset or recompute disease physics implicitly.

## 17. Reproducibility checklist

A persisted/runtime experiment should retain:

- parent PWDB identity;
- run ID;
- disease condition and full parameter mapping;
- canonical selected subject IDs;
- selection seed/design;
- backend/solver execution identity;
- quantity statuses;
- provenance records;
- warnings/qualification state;
- result/bundle checksums;
- VascuQuest version.

## 18. Non-claims

Runtime materialization does not establish:

- clinical patient equivalence;
- patient-specific diagnosis/prognosis;
- epidemiological representativeness;
- treatment efficacy;
- support for quantities marked `NOT_SUPPORTED`;
- three-dimensional CFD/FSI fidelity;
- biological disease progression/remodeling.

## 19. Related documentation

- [`VIRTUAL_DISEASE.md`](VIRTUAL_DISEASE.md)
- [`VIRTUAL_DISEASE_RECONSTRUCTION.md`](VIRTUAL_DISEASE_RECONSTRUCTION.md)
- [`VIRTUAL_DISEASE_PHYSICS.md`](VIRTUAL_DISEASE_PHYSICS.md)
- [`VIRTUAL_DISEASE_PUBLIC.md`](VIRTUAL_DISEASE_PUBLIC.md)
- [`VIRTUAL_DISEASE_COHORTS.md`](VIRTUAL_DISEASE_COHORTS.md)
- [`HEMOSPACE.md`](HEMOSPACE.md)
