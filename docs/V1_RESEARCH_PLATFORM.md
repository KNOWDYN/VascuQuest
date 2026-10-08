# VascuQuest 1.0 research-platform contract

## Purpose

VascuQuest 1.0 supports a complete mechanistic in-silico cardiovascular workflow over existing VascuQuest scientific objects:

`PWDB → HEMOSPACE phenotype → cohort → Virtual Disease response → mechanics/spectral analysis → statistics → publication figure`

## Frozen architectural rule

New analysis functionality analyzes existing VascuQuest scientific objects. It does not mutate the PWDB core, HEMOSPACE semantics, or qualified Virtual Disease physics.

## Native-first data model

All canonical operations consume `ScientificResult`/`Waveform` objects. The controlled external-data entry point is `vascuquest.analysis.wrap_external(...)`, which requires explicit dataset identity, quantity definition, units/context and provenance.

## Subject/cohort invariants

- A `VirtualSubject` is a simulation instance, not a patient.
- Canonical subject identity is never replaced by row position.
- Paired analyses require identical subject IDs in identical deterministic order.
- Independent cohort analyses retain their separate cohort identities.
- PWDB is a designed virtual population, not an epidemiological sample.

## Evidence

Analysis outputs use existing VascuQuest evidence classes. Pure deterministic transforms are normally `DERIVED`; inferential statistics are `INFERRED`; Virtual Disease outputs remain `MODELLED`.

## Compute policy

V1 analysis qualification must be achievable with small deterministic fixtures. No new full-network disease solver qualification, all-subject rerun, or complete 44.3-GB PWDB revalidation is implied.
