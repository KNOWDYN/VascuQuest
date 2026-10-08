# HEMOSPACE Agent Contract

This document is for AI agents operating VascuQuest on behalf of human researchers. The machine-readable HEMOSPACE contract is emitted by:

```bash
vascuquest hemospace agent-contract
```

This human-readable contract additionally explains how HEMOSPACE participates in the completed VascuQuest 1.0 analysis stack.

## 1. Core interpretation rule

A HEMOSPACE record describes a **virtual cardiovascular simulation instance**. It is never a real patient record.

Do not silently convert simulated values into diagnoses, prognosis, treatment recommendations, epidemiological prevalence, or unencoded life history.

## 2. Evidence handling

Interpret evidence exactly:

- `SOURCE` — direct canonical PWDB source value or source-export metadata;
- `RECONSTRUCTED` — deterministic recovery from aligned source quantities;
- `DERIVED` — calculation from an explicit declared method;
- `INFERRED` — estimate from a separately qualified inference method;
- `MODELLED` — output of an explicit disease/research model.

Never promote `RECONSTRUCTED`, `DERIVED`, `INFERRED`, or `MODELLED` to `SOURCE` in summaries.

A downstream statistic or figure does not change the evidence status of the physiological/model input. For example, a p-value derived from `MODELLED` disease responses is a derived statistic about modelled counterfactuals, not clinical evidence.

## 3. Record schema

Records use:

```text
kind = vascuquest.hemospace.virtual_cardiovascular_record
schema_version = hemospace-1
```

Top-level fields:

```text
dataset
subject_id
depth
sections
coverage
unavailable_information
warnings
```

Each knowledge item contains:

```text
canonical_id
label
section
value
unit
evidence
source_artifact
source_field
location
method
assumptions
notes
```

## 4. Generative-variation semantics

`DIA`, `HR`, `LEN`, `LVET`, `MBP`, `PVC`, `PWV`, `RFV`, `SV`, and `PFT` from `pwdb_model_variations.csv` are **prescribed PWDB design-space deviations from the age-specific mean**. Unit:

```text
SD_from_age_specific_mean
```

They are not clinical z-scores.

`AGE` in that table is a grouping/design value in years and must not be interpreted as an SD axis.

## 5. Population sex assumption

PWDB's upstream WFDB exporter labels every virtual recording as `male`. HEMOSPACE exposes this as `model_population_sex_assumption`.

Interpretation:

- dataset/model-population assumption;
- not an observed biological attribute of a real participant;
- do not use it to infer sex-specific clinical outcomes.

## 6. Unknown source fields

HEMOSPACE retains numeric PWDB fields under stable source-derived IDs even when their semantic promotion is incomplete.

If unit/meaning is not documented:

1. preserve source field and value;
2. do not guess a unit;
3. do not invent clinical meaning;
4. consult authoritative PWDB documentation before promoting the semantic definition.

## 7. Depth selection

Use `scalar` for cohort screening, generative physiology and source haemodynamics.

Use `geometry` only when network anatomy/geometry is needed.

Use `comprehensive` when common-site waveform morphology, flow integrals, energetics, HEMOSPACE-native mechanics, or local impedance summaries are relevant.

Use `hemospace path` only when canonical path-resolved source data are necessary. Path mode may acquire multi-GB artifacts and requires the optional `path` dependency.

Do not request deeper records or path artifacts merely because they exist. Use the least expensive source depth that answers the scientific question.

## 8. Cohort selection

CLI:

```bash
vascuquest hemospace cohort select \
  -c 'arterial_stiffness_variation>=1' \
  -c 'large_artery_diameter_variation<=0' \
  --profile carotid-stenosis \
  --describe
```

Criteria are exact numeric comparisons against canonical HEMOSPACE IDs.

Do not infer population prevalence from cohort counts. PWDB is a designed virtual population.

Built-in profiles are research scaffolds, not clinical protocols:

- carotid stenosis;
- iliac stenosis;
- fusiform AAA;
- large-artery stiffening.

Always read the profile's `forbidden_claims` before interpreting results.

## 9. Disease response

`hemospace response` consumes persisted Virtual Disease cohort bundles. It must not rerun the disease solver.

A response item contains healthy baseline, modelled disease value, absolute change and relative change when defined.

Interpret all disease response items as `MODELLED` counterfactual effects.

Never call them:

- treatment efficacy;
- clinical outcome;
- patient response;
- event-risk reduction.

## 10. Path-mode qualification

Path access uses bounded HDF5 reads against the canonical MATLAB-v7.3 structure. The reader is qualified as:

```text
reader_qualification = QUALIFIED_AUTHORITATIVE_EXPORTER_CONTRACT
```

The qualification was established from the exact PWDB revised-submission exporter, canonical Zenodo filenames/checksums, MATLAB-v7.3 struct/cell object-reference conventions, and an executed regression fixture covering all four supported path families, including the split aorta→foot P/U/A files.

Interpretation rule:

- the reader contract is qualified;
- canonical artifact identity is still established at acquisition time by the VascuQuest manifest/checksum;
- no fresh whole-artifact byte scan or 4,374-subject reprocessing is implied by the qualification;
- continue reporting the actual canonical artifact DOI/checksum used in a study.

See `HEMOSPACE_PATH_QUALIFICATION.md`.

## 11. Knowledge closure

Before claiming a subject record is comprehensive, run:

```bash
vascuquest hemospace closure --subject <ID> --depth comprehensive
```

`CLOSED_WITH_DECLARED_SOURCE_FORMAT_LIMITATION` means operational scalar/geometry/common-wave coverage is closed, but a bounded-access limitation remains for exporter-only metadata in the legacy unified MAT representation.

Do not omit this qualifier when making completeness claims.

The v1 analysis stack does not change HEMOSPACE knowledge closure. Statistics, mechanics, spectral analysis and plotting can derive new research outputs from known data, but they do not make previously unknowable PWDB information knowable.

## 12. Forbidden gap filling

Never invent or infer from PWDB alone:

- smoking history;
- genetics;
- renal function;
- medications;
- symptoms;
- plaque composition;
- thrombotic state;
- longitudinal life events;
- future clinical event risk.

Do not infer from the 1-D disease engine alone:

- wall shear stress;
- 3-D recirculation;
- aneurysm rupture risk;
- plaque vulnerability;
- clinical stroke risk;
- thrombosis probability.

## 13. VascuQuest 1.0 downstream-analysis rule

HEMOSPACE is the phenotype/knowledge layer. The new research namespaces are downstream consumers:

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

Use only the stages required by the question.

Hard rules for agents:

1. Never strip a HEMOSPACE/core result to anonymous arrays before checking dataset, subject/cohort, location, unit and coordinate compatibility.
2. Never pair healthy and disease values by row number when canonical subject IDs exist.
3. Never silently resample misaligned waveforms.
4. Never call the disease solver from a downstream analysis merely because a persisted disease result is available.
5. Never treat many time samples or frequency bins from one subject as independent subjects.
6. Never infer epidemiological probability from a designed virtual cohort.
7. Never let plotting recompute hidden statistics; statistical annotations must originate from explicit analytical results.
8. Never silently thin a large cohort for plotting; rasterization is allowed because it changes rendering, not observations.

## 14. Mechanics and spectral ownership

HEMOSPACE includes selected deterministic waveform summaries such as area compliance/distensibility and first pressure-flow impedance harmonics as part of the Virtual Cardiovascular Record.

For a dedicated research analysis requiring standardized v1 method identities, configurable parameters, subject-level cohort propagation, advanced pressure-area mechanics, impedance, wave separation, wave intensity, coherence, transfer functions, STFT or wavelets, use:

- `vascuquest.mechanics`;
- `vascuquest.spectral`.

Do not assume that similarly named HEMOSPACE summary fields and dedicated research-method outputs are interchangeable unless their definitions, units and assumptions match exactly.

## 15. Recommended agent workflow

```text
1. Read agent-contract and the relevant subsystem documentation.
2. Define the scientific question and required evidence class before requesting data.
3. Select a built-in HEMOSPACE study profile if appropriate.
4. Build scalar records or a phenotype cohort.
5. Inspect coverage and unavailable_information.
6. Escalate to geometry only if anatomy is needed.
7. Escalate to comprehensive only if waveform/energetics endpoints are needed.
8. Request a path artifact only for a genuinely path-specific question.
9. If disease results already exist, use persisted bundle/response mode; never rerun them just to calculate paired changes.
10. Convert required native results into the common analysis contract without losing identity/alignment metadata.
11. Apply mechanics/spectral operations only when their assumptions are satisfied.
12. Apply statistics using the correct paired/independent/design semantics.
13. Build figures from explicit scientific/statistical results; keep all legends outside scientific axes and preserve all cohort observations.
14. Preserve evidence class, units, source identity, method IDs, assumptions and model-run identity.
15. Run closure before using the word comprehensive.
```

## 16. Required reporting

For every downstream scientific result retain, as applicable:

- PWDB DOI/record identity;
- canonical subject IDs;
- HEMOSPACE schema version;
- record depth;
- cohort criteria/profile and selection ID;
- evidence class;
- source artifact/source field for SOURCE items;
- method and assumptions for reconstructed/derived items;
- disease run/condition/severity for MODELLED items;
- analysis method ID and parameters;
- statistical seed/resample count where applicable;
- waveform sampling and spectral/mechanics assumptions where applicable;
- relevant HEMOSPACE warnings;
- knowledge-closure status when applicable;
- figure-spec JSON when a publication figure is generated;
- VascuQuest version.

## 17. Documentation precedence

For current product behavior, follow `docs/README.md` and the governing v1.0 contracts. Machine-readable qualification evidence and historical documents retain their original scope and wording and must not be generalized beyond that scope.
