# HEMOSPACE Agent Contract

This document is for AI agents operating VascuQuest on behalf of human researchers.

## Core rule

A HEMOSPACE record describes a **virtual cardiovascular simulation instance**, never a real patient. Do not silently convert simulated quantities into diagnoses, treatment recommendations, prognosis, or claims about an unencoded life history.

## Record kind

Machine-readable records use:

```text
kind = vascuquest.hemospace.virtual_cardiovascular_record
schema_version = hemospace-1
```

The top-level object contains:

```text
dataset
subject_id
depth
sections
coverage
unavailable_information
warnings
```

## Knowledge-item contract

Every item contains:

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

Interpret `evidence` exactly:

- `SOURCE`: direct canonical PWDB source value.
- `RECONSTRUCTED`: deterministic recovery from aligned source quantities.
- `DERIVED`: calculation from an explicit definition.
- `INFERRED`: estimate from a separately qualified inference method.
- `MODELLED`: output of an explicit research model/operator.

Never promote `RECONSTRUCTED`, `DERIVED`, `INFERRED`, or `MODELLED` to `SOURCE` in summaries.

## Generative-variation semantics

Items in section `generative_variation` originate from `pwdb_model_variations.csv`.

Their unit is:

```text
SD_from_age_specific_mean
```

This means prescribed deviation of a **model input** from the age-specific mean used to construct the virtual population. It does not mean a clinical z-score measured from a real person.

## Unknown source fields

HEMOSPACE deliberately retains unknown-but-numeric PWDB source columns using stable source-derived identifiers. If a field lacks documented unit or meaning:

1. report the raw source identity and value;
2. do not guess the unit;
3. do not infer clinical meaning;
4. consult authoritative PWDB documentation before proposing semantic promotion.

## Coverage

Before claiming that a record is comprehensive, inspect `coverage`.

`scalar_source_complete=true` means every scalar source field encountered for the subject was either exposed or explicitly missing. It does **not** mean geometry or waveforms were included.

Check:

```text
geometry_included
waveform_summaries_included
```

as separate completeness dimensions.

## Depth selection

Use `scalar` for lightweight cohort screening and physiological characterization.

Use `geometry` when anatomy or vascular-network structure matters.

Use `comprehensive` only when waveform morphology, local P/U/A/PPG behaviour, or reconstructed Q summaries are relevant. Comprehensive mode may require acquisition of the canonical common-site waveform archive.

## Forbidden gap filling

Never invent values for entries listed in `unavailable_information`.

Examples include smoking, genetics, medications, symptoms, plaque composition, thrombotic state, renal function, longitudinal life history, and future clinical-event risk.

If a research task requires one of these concepts, explicitly state that PWDB alone cannot answer it and that an external dataset or separately declared model is required.

## Endovascular research use

Appropriate HEMOSPACE uses include:

- physiological cohort enrichment;
- effect-modifier analysis;
- disease-response stratification;
- worst-case/boundary-case exploration within the represented PWDB design space;
- endpoint selection;
- mechanistic subgroup analysis;
- source-coverage audits.

Do not claim clinical treatment efficacy from HEMOSPACE records alone.

## Recommended agent sequence

```text
1. hemospace record --depth scalar
2. inspect coverage + unavailable_information
3. identify relevant source/derived phenotype dimensions
4. escalate to --depth geometry only if anatomy is needed
5. escalate to --depth comprehensive only if waveform-level evidence is needed
6. preserve evidence class in all downstream analyses
7. cite the exact subject IDs, dataset record, selection rules, and disease specification
```

## Reproducibility

For any reported result retain:

- PWDB record identity `3275625`;
- HEMOSPACE schema version;
- canonical subject ID(s);
- record depth;
- source artifact/source field for `SOURCE` items;
- method and assumptions for reconstructed/derived quantities;
- disease specification and solver execution identity when modelled pathology is introduced elsewhere in VascuQuest.
