# HEMOSPACE

**HEMOSPACE is a first-class VascuQuest operation mode for constructing and interrogating provenance-aware Virtual Cardiovascular Records from PWDB.**

HEMOSPACE does not create a synthetic medical chart and does not turn a PWDB simulation into a real patient. Its purpose is narrower and more rigorous:

> expose what is explicitly known about a PWDB virtual subject, reconstruct what follows deterministically, derive scientifically defined cardiovascular quantities, attach Virtual Disease counterfactual responses when available, and state what remains unknowable.

## 1. Scientific object

A HEMOSPACE `VirtualCardiovascularRecord` describes one canonical PWDB simulation instance. Every emitted `KnowledgeItem` carries:

- canonical ID;
- scientific label;
- section/domain;
- value;
- unit;
- evidence class;
- source artifact/field where applicable;
- vascular location where applicable;
- method/equation for reconstructed or derived quantities;
- assumptions;
- interpretive notes.

Evidence classes are strict:

- `SOURCE`: explicitly encoded in a canonical PWDB source or source-export metadata;
- `RECONSTRUCTED`: deterministic recovery from aligned source quantities;
- `DERIVED`: explicit mathematical/physiological calculation;
- `INFERRED`: estimate from a separately qualified inference method;
- `MODELLED`: output of an explicit VascuQuest disease/research model.

HEMOSPACE never silently promotes reconstructed, derived, inferred, or modelled values to source truth.

## 2. Record depths

### Scalar

```bash
vascuquest hemospace record --subject 2104 --depth scalar
```

Uses all numeric per-subject fields from:

- `pwdb_model_configs.csv`;
- `pwdb_model_variations.csv`;
- `pwdb_haemod_params.csv`;
- `pwdb_pw_indices.csv`;
- `pwdb_onset_times.csv`.

The source adapter explicitly supports PWDB's canonical uppercase `SUBJECT NUMBER` header in `pwdb_model_variations.csv` without relaxing the core VascuQuest CSV contract.

The generative-variation fields `DIA`, `HR`, `LEN`, `LVET`, `MBP`, `PVC`, `PWV`, `RFV`, `SV`, and `PFT` are represented as prescribed deviations from the age-specific mean of the PWDB design space. They are not clinical z-scores measured in a real person.

`AGE` in the variation table is treated as a grouping/design field, not as an SD variation axis.

### Geometry

```bash
vascuquest hemospace record --subject 2104 --depth geometry
```

Adds the complete subject-specific 116-segment vascular geometry plus deterministic summaries:

- segment count;
- summed represented segment length;
- minimum/maximum endpoint diameter;
- approximate represented lumen volume using conical-frustum geometry.

The lumen-volume value is a geometric approximation, not measured circulating blood volume.

### Comprehensive

```bash
vascuquest hemospace record --subject 2104 --depth comprehensive
```

Adds common-site P/U/A/PPG waveform summaries and reconstructed Q summaries. Where source alignment permits, HEMOSPACE additionally derives:

- velocity pulsatility and resistive indices;
- area strain;
- local area compliance;
- local area distensibility;
- flow pulsatility;
- forward/reverse/net cycle volume;
- reverse-flow fraction;
- hydraulic power;
- hydraulic energy per cycle;
- first pressure-flow impedance harmonics.

These are cardiovascular signal/haemodynamic descriptors, not diagnoses.

## 3. Dataset assumptions and quality information

The upstream PWDB exporter writes `<sex>: male` into every WFDB record description. HEMOSPACE therefore exposes:

`model_population_sex_assumption = male`

as a source model-population assumption. This is not treated as an observed characteristic of a real patient.

HEMOSPACE also reconstructs the PWDB source physiological-plausibility gate from the lightweight haemodynamic fields. This reproduces the source algorithm that compares seven pressure characteristics against age-dependent 99% literature ranges. The resulting flag describes PWDB source-generation plausibility; it is not a clinical screening score.

## 4. Path-resolved physiology

PWDB includes canonical path-resolved MAT artifacts for:

- aorta → brain;
- aorta → finger;
- aorta → foot;
- aorta → right subclavian.

HEMOSPACE provides lazy path access:

```bash
vascuquest hemospace path \
  --subject 2104 \
  --path aorta_brain
```

Path mode returns source spatial coordinates, artery/segment identity, onset times, signal summaries, Q=U×A summaries where available, apparent path PWV from distance-versus-onset-time regression, and terminal/root pressure-pulse amplification.

Path access requires the optional `h5py` dependency:

```bash
pip install 'vascuquest[path]'
```

The reader is bounded and refuses a whole-file fallback for a large non-HDF5 MATLAB artifact. It is qualified as `QUALIFIED_AUTHORITATIVE_EXPORTER_CONTRACT`: the implementation was checked against the exact revised-submission PWDB exporter, the canonical Zenodo filenames/checksums, MATLAB-v7.3/HDF5 struct/cell reference conventions, and an executed regression fixture covering all four HEMOSPACE path families including the split aorta→foot P/U/A representation. This qualification establishes reader correctness without requiring a fresh multi-gigabyte artifact download or full-population rerun. Canonical artifact identity is still enforced independently by VascuQuest checksums.

See `HEMOSPACE_PATH_QUALIFICATION.md` for the qualification certificate and boundary.

## 5. Phenotype-driven virtual cohorts

HEMOSPACE can select reproducible cohorts directly from source phenotype variables:

```bash
vascuquest hemospace cohort select \
  --criterion 'arterial_stiffness_variation>=1' \
  --criterion 'large_artery_diameter_variation<=0' \
  --profile carotid-stenosis \
  --describe
```

The resulting cohort records:

- exact canonical subject IDs;
- exact numeric selection rules;
- optional study profile;
- deterministic SHA-256 selection identity;
- designed-population interpretation.

HEMOSPACE cohorts are mechanistic virtual cohorts, not epidemiological samples. Counts or frequencies must not be reported as disease prevalence or population incidence.

Built-in study profiles:

- `carotid-stenosis`;
- `iliac-stenosis`;
- `aaa`;
- `large-artery-stiffening`.

Each profile documents recommended covariates, effect modifiers, source endpoints, modelled response endpoints, and forbidden clinical claims.

## 6. Healthy → disease response records without solver recomputation

HEMOSPACE consumes an existing complete parameterized Virtual Disease cohort bundle and pairs its persisted MODELLED outputs with the healthy PWDB record for the same canonical subject:

```bash
vascuquest hemospace response \
  --subject 2104 \
  --bundle ./cohort-run
```

The operation verifies the bundle/subject manifests and scientific-result checksums. It then calculates aligned endpoint changes:

- healthy baseline;
- modelled disease value;
- absolute change;
- relative change where mathematically defined.

HEMOSPACE does **not** rerun the Virtual Disease solver. This is deliberate: response analysis should consume qualified persisted outputs instead of spending new solver compute.

A response record is a paired counterfactual model response. It is not a clinical treatment effect and not evidence of patient-specific efficacy.

## 7. Knowledge closure

```bash
vascuquest hemospace closure --subject 2104 --depth comprehensive
```

The closure report audits every canonical PWDB artifact and assigns an explicit disposition such as:

- exposed;
- on-demand;
- redundant representation;
- reconstructed;
- qualified lazy path access;
- declared source-format limitation.

Closure also checks scalar-source coverage and requested geometry/common-site-waveform coverage.

The unified 701.7 MB legacy MAT representation contains a small exporter-only metadata remainder for which there is no bounded per-subject access path. HEMOSPACE reports this explicitly rather than loading the complete legacy MAT file simply to make a completeness claim. Consequently, closure can report `CLOSED_WITH_DECLARED_SOURCE_FORMAT_LIMITATION` when operational coverage is complete but this bounded-access limitation remains.

Downstream mechanics, spectral analysis, statistics, or plotting do not change this closure state. They may derive new research outputs from information already available, but they do not turn absent PWDB information into source knowledge.

## 8. What HEMOSPACE refuses to invent

The record explicitly marks categories that PWDB alone cannot identify, including:

- smoking/exposure history;
- genetics;
- renal function;
- medication history;
- clinical symptoms;
- plaque composition;
- thrombotic state;
- longitudinal life history;
- future clinical event risk.

Age groups are not repeated observations of the same biological individual.

HEMOSPACE also does not infer rupture risk, clinical stroke risk, plaque vulnerability, thrombosis, wall shear stress, or 3-D recirculation from the one-dimensional source/disease representation.

## 9. VascuQuest 1.0 research-analysis integration

HEMOSPACE is the comprehensive phenotype/knowledge layer, while the v1 research namespaces are downstream analytical layers:

```text
HEMOSPACE/core ScientificResult or Waveform
        ↓
vascuquest.analysis
        ↓
vascuquest.mechanics and/or vascuquest.spectral
        ↓
vascuquest.stats
        ↓
vascuquest.plot
```

This division prevents HEMOSPACE from becoming an unbounded feature generator.

Use `vascuquest.mechanics` when the study requires standardized v1 pressure-area/wave-mechanics method IDs and assumptions beyond the concise HEMOSPACE record summaries. Use `vascuquest.spectral` for configurable harmonics, impedance, wave separation, wave intensity, coherence, transfer functions, STFT, or wavelets.

For cohort research, compute subject-level derived endpoints while preserving canonical subject IDs, then perform statistical analysis on the aligned cohort vector. Time samples or frequency bins from one subject must not be treated as independent subjects.

Publication figures should be generated from explicit scientific/statistical results. `vascuquest.plot` does not silently recompute statistics or thin cohorts.

## 10. Python API

```python
from vascuquest.hemospace import open_hemospace

hs = open_hemospace(source="/path/to/pwdb", offline=True)

record = hs.record("2104", depth="comprehensive")
cohort = hs.select_cohort(
    ["arterial_stiffness_variation>=1"],
    profile_id="carotid-stenosis",
)
summary = hs.describe_cohort(cohort)
path = hs.path("2104", "aorta_brain")
response = hs.response("./cohort-run", "2104")
closure = hs.closure("2104")
```

## 11. Reproducibility requirements

A HEMOSPACE analysis should retain at minimum:

- PWDB persistent identifier `10.5281/zenodo.3275625`;
- canonical subject IDs;
- HEMOSPACE schema version;
- record depth;
- cohort criteria/profile and `selection_id` where applicable;
- disease condition/severity/run identity for MODELLED results;
- evidence class of reported quantities;
- relevant warnings/assumptions;
- closure status when claiming comprehensive knowledge;
- downstream analysis method IDs/parameters where applicable;
- statistical seeds/resample counts where applicable;
- figure-spec JSON when a publication figure is produced;
- VascuQuest version.

See also:

- `HEMOSPACE_QUANTITY_CATALOGUE.md`
- `HEMOSPACE_ENDOVASCULAR_PROTOCOLS.md`
- `HEMOSPACE_KNOWLEDGE_CLOSURE.md`
- `HEMOSPACE_PATH_QUALIFICATION.md`
- `HEMOSPACE_AGENT.md`
- `ANALYSIS.md`
- `STATS.md`
- `VASCULAR_MECHANICS.md`
- `SPECTRAL_ANALYSIS.md`
- `PLOTTING.md`
