# Virtual Disease runtime populations

## PR 4 status

This document describes implementation stage 4 of 5 for the first-party VascuQuest Virtual Disease subsystem.

PR 4 materialises the causal disease models introduced by PR 3 into **in-memory VascuQuest scientific results and virtual-population datasets**. It does not add the public disease-generation CLI; that remains the final PR-5 stage.

The scientific qualification boundary is unchanged. Healthy reconstruction remains `METRICS_ONLY_THRESHOLDS_NOT_FROZEN`, and every disease-state result is `MODELLED` evidence rather than an observation or a validated clinical patient record.

## Runtime pipeline

A runtime population generation executes the following sequence:

```text
canonical PWDB DatasetSession
        |
        | deterministic age-group selection
        v
preserved PWDB subject IDs
        |
        | assemble immutable healthy parent state
        v
DiseasePhysicsModel
        |
        | execute DiseaseOneDSolver to periodic convergence
        v
complete modelled final cardiac cycle
        |
        | materialise supported quantities
        v
PWDB-VD:<content-addressed-run-id>
```

The canonical PWDB source dataset is never modified.

## Dataset and subject identity

Each generated population receives a new exact dataset identity:

```text
dataset_family       = PWDB-VD
record_id            = <DiseaseRunIdentity.run_id>
persistent_identifier = urn:vascuquest:virtual-disease:<run-id>
schema_version       = parent PWDB schema version
```

The `record_id` is therefore the SHA-256 content address already frozen by PR 1 from:

- exact parent PWDB dataset identity;
- selected canonical subject IDs;
- patient count;
- age group;
- selection seed;
- disease condition;
- disease parameters;
- preset/contract version.

The runtime dataset constructor mechanically rejects an identity that is not derived from its `DiseaseRunIdentity`.

### Preserved patient numbers

The selected PWDB subject number is retained exactly:

```text
healthy baseline: PWDB:3275625 / subject 431
runtime disease:  PWDB-VD:<run-id> / subject 431
```

The two `SubjectKey` values are not identical because they belong to different dataset identities, but their `canonical_subject_id` is deliberately identical. This enables direct matched healthy-versus-diseased comparison without modifying or duplicating the source PWDB identity.

## Runtime-only storage

`RuntimeDiseaseStore` is an in-process content-addressed store. It does not write into:

- the PWDB artifacts;
- VascuQuest's canonical source registration;
- a persistent database;
- an implicit disk cache.

A repeated request with the same content-addressed run ID returns the already generated runtime dataset held by that store. A scientifically different request produces a different run ID and therefore a different runtime dataset identity.

PR 5 may expose explicit user-facing save/export behaviour, but PR 4 does not silently persist generated populations.

## VascuQuest data structures

Runtime disease data uses the established VascuQuest domain objects:

- `DatasetIdentity`;
- `SubjectKey`;
- `VirtualSubject`;
- `Cohort`;
- `QuantityDefinition`;
- `ScientificResult`;
- `Waveform`;
- `Coordinate`;
- `ProvenanceRecord`.

`RuntimeDiseaseDataset` provides a read facade aligned with familiar dataset operations:

- `subjects()` / `subject()`;
- `quantities()`;
- `locations()`;
- `get()` for supported scalar/structured quantities;
- `waveform()` for modelled `P/U/A/Q`;
- `geometry()` for the runtime vascular state;
- `provenance()`;
- `quantity_status()` / `quantity_statuses()`.

It is intentionally not installed into the canonical PWDB backend and does not redefine the established `DatasetSession` contract.

## Materialised disease-state quantities

For each selected subject, PR 4 materialises 58 concrete results:

- `P`, `U`, `A`, and `Q` at each of the 13 canonical PWDB common measurement sites: 52 waveforms;
- age;
- heart rate;
- stroke volume;
- cardiac output;
- brachial systolic pressure;
- resolved runtime vascular geometry/model state.

The 13 sites use the same solver-location mapping already frozen for healthy Gate-0 reconstruction:

```text
AorticRoot
ThorAorta
AbdAorta
IliacBif
Carotid
SupTemporal
SupMidCerebral
Brachial
Radial
Digital
CommonIliac
Femoral
AntTibial
```

### Waveforms

The full disease solver runs with its adaptive numerical time steps. Materialised `P/U/A/Q` are then deterministically interpolated onto the selected subject's original PWDB cardiac-cycle time coordinate obtained from the preserved aortic-root source inflow.

This deliberately gives healthy and disease vectors a directly comparable time coordinate while leaving the numerical integration itself adaptive.

Materialised quantities are calculated as:

```text
P = disease-solver pressure converted from Pa to mmHg
A = disease-solver luminal cross-sectional area
Q = disease-solver volumetric flow rate
U = Q / A
```

`Q` therefore remains physically identical to `U*A` after materialisation.

### Scalar values

The following causal cardiac inputs are intentionally retained numerically:

```text
age
heart_rate
stroke_volume
```

They are re-materialised in the counterfactual dataset with `MODELLED` evidence and `UNCHANGED_CAUSAL_INPUT` status. They are not relabelled as new source observations.

Cardiac output is recomputed from the preserved causal inputs:

```text
CO [L/min] = HR [beats/min] * SV [mL/beat] / 1000
```

Brachial systolic pressure is derived from the maximum of the modelled brachial pressure waveform.

## Explicit quantity-status policy

PR 4 records a `DiseaseQuantityStatus` separately from evidence class:

| Quantity | Runtime status |
|---|---|
| pressure | `RECOMPUTED` |
| flow_velocity | `RECOMPUTED` |
| luminal_area | `RECOMPUTED` |
| flow_rate | `DERIVED_FROM_RECOMPUTED` |
| age | `UNCHANGED_CAUSAL_INPUT` |
| heart_rate | `UNCHANGED_CAUSAL_INPUT` |
| stroke_volume | `UNCHANGED_CAUSAL_INPUT` |
| cardiac_output | `RECOMPUTED` |
| brachial_systolic_pressure | `DERIVED_FROM_RECOMPUTED` |
| vascular_geometry | `MODEL_PARAMETER_MODIFIED` |
| photoplethysmogram | `NOT_SUPPORTED` |
| aortic_pulse_wave_velocity | `NOT_SUPPORTED` |
| aortic_augmentation_index | `NOT_SUPPORTED` |
| pressure_onset_time | `NOT_SUPPORTED` |

The structured runtime vascular-state payload retains the resolved axial radius/area profile and the wall-mechanical coefficients required to reproduce the solver state. For large-artery stiffening, lumen geometry is unchanged but wall beta is modified; consequently the combined runtime vascular-state result is classified `MODEL_PARAMETER_MODIFIED` rather than falsely declared unchanged.

## Unsupported quantities are not copied from health

PR 4 deliberately does **not** populate a healthy source value where the disease state lacks an implemented recomputation model.

In particular:

- PPG is not regenerated from the disease haemodynamics;
- aortic PWV is not substituted by the PR-3 model-space cfPWV target or by the healthy source value;
- augmentation index is not copied from the healthy parent;
- pressure-onset times are not copied from the healthy parent.

Requests for these quantities fail explicitly as `NOT_SUPPORTED`.

This prevents a runtime disease patient from containing internally inconsistent healthy-derived metrics.

## Disease-qualified vector names

Canonical scientific quantity identities remain unchanged. The runtime/source label carries the disease suffix frozen in PR 1.

Examples for carotid stenosis are:

```text
pressure       -> P__vd_carotid_stenosis
flow_velocity  -> U__vd_carotid_stenosis
luminal_area   -> A__vd_carotid_stenosis
flow_rate      -> Q__vd_carotid_stenosis
age            -> age__vd_carotid_stenosis
heart_rate     -> HR__vd_carotid_stenosis
stroke_volume  -> SV__vd_carotid_stenosis
cardiac_output -> CO__vd_carotid_stenosis
```

Thus a runtime pressure waveform remains canonical quantity `pressure`; only its runtime vector label records the disease condition.

## Runtime vascular geometry/model state

A source PWDB geometry row stores segment endpoints, length, inlet/outlet radii, and terminal R/C values. That representation cannot faithfully preserve an internal focal stenosis or fusiform aneurysm because those diseases vary inside a source segment.

PR 4 therefore materialises `RuntimeGeometrySegment` values containing the resolved one-dimensional solver state:

- source segment ID and topology;
- source segment length;
- axial solver coordinate;
- resolved reference radius profile;
- resolved reference area profile;
- resolved beta wall stiffness;
- source Voigt gamma profile;
- terminal resistance/compliance.

Arrays are copied and made read-only. The parent source geometry remains available through the immutable healthy baseline retained by `RuntimeSubjectState`.

## Provenance

Every materialised runtime result has deterministic `MODELLED` provenance identifying:

- exact runtime dataset identity and run ID;
- exact parent PWDB dataset identity;
- preserved parent canonical subject ID;
- frozen disease condition and parameters;
- preset/contract version;
- disease quantity status;
- modified source segment IDs;
- solver options and final diagnostics;
- population selection seed and deterministic SHA-256 ranking algorithm;
- canonical PWDB model-configuration, geometry, and common-site-waveform artifact checksums;
- disease-physics assumptions and citations;
- runtime method/component version;
- output identity and scientific warnings.

The existing provenance v1 model permits direct provenance inputs only within the same dataset identity. PR 4 therefore does not falsify a cross-dataset input edge. Parent PWDB identity and source artifact checksums are encoded explicitly as immutable provenance facts.

## Evidence and validity

All runtime disease results use:

```text
evidence = MODELLED
```

This includes quantities that are intentionally numerically invariant, such as age, because the result belongs to a counterfactual runtime dataset rather than the source dataset.

Runtime results also carry warnings that:

- the values are modelled and not clinical observations; and
- healthy reconstruction acceptance thresholds remain unfrozen.

PR 4 does not promote these results to `SOURCE`, `RECONSTRUCTED`, or clinically validated evidence.

## Numerical failure policy

Population materialisation requires each subject's disease solver to reach its configured periodic-convergence criterion. A non-converged subject causes generation to fail rather than materialising a partial or silently questionable patient state.

Likewise, unsupported quantities fail explicitly instead of falling back to healthy values.

## PR 4 non-goals

PR 4 contains no:

- public `vascuquest disease ...` CLI command;
- automatic persistent population save;
- new source PWDB dataset registration;
- modification of the canonical PWDB backend or schema resource;
- synthetic PPG model;
- disease-state augmentation-index algorithm;
- disease-state onset-time algorithm;
- clinical tonometry simulation;
- Doppler-ultrasound simulation;
- clinical diagnostic classification;
- clinical-validation claim.

## Gate for PR 5

After PR 4 is manually reviewed and merged, PR 5 may expose the completed subsystem through the public command line. The final CLI must allow users to choose at least:

- patient count;
- age group;
- one of the four frozen disease conditions;
- the condition parameters;
- deterministic selection seed.

It may then expose the generated runtime dataset identity, preserved subject IDs, quantity statuses, supported retrieval/export pathways, and explicit scientific warnings without altering the canonical PWDB source dataset.
