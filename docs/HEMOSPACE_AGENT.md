# HEMOSPACE Agent Contract

This document is for AI agents operating VascuQuest on behalf of human researchers. The machine-readable version is emitted by:

```bash
vascuquest hemospace agent-contract
```

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

Use `comprehensive` when common-site waveform morphology, vascular mechanics, flow integrals, energetics or local impedance descriptors are relevant.

Use `hemospace path` only when continuous canonical path data are necessary. Path mode may acquire multi-GB artifacts and requires the optional `path` dependency.

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

## 13. Recommended agent workflow

```text
1. Read agent-contract.
2. Select a built-in study profile if appropriate.
3. Build scalar records or a phenotype cohort.
4. Inspect coverage and unavailable_information.
5. Escalate to geometry only if anatomy is needed.
6. Escalate to comprehensive only if waveform/mechanics/energetics endpoints are needed.
7. Request a path artifact only for a path-specific question.
8. If disease results already exist, use response mode; never rerun them just to calculate paired changes.
9. Preserve evidence class, units, source identity, assumptions and model-run identity.
10. Run closure before using the word comprehensive.
```

## 14. Required reporting

For every downstream scientific result retain:

- PWDB DOI/record identity;
- canonical subject IDs;
- HEMOSPACE schema version;
- record depth;
- cohort criteria/profile and selection ID;
- evidence class;
- source artifact/source field for SOURCE items;
- method and assumptions for reconstructed/derived items;
- disease run/condition/severity for MODELLED items;
- relevant HEMOSPACE warnings;
- knowledge-closure status when applicable.
