# HEMOSPACE Knowledge Closure

HEMOSPACE uses a formal stopping rule for the phrase **comprehensive record**.

A record is not considered comprehensive because it contains many variables. It is considered closed only when every canonical PWDB information source has an explicit disposition and every emitted non-source quantity has a declared derivation.

## Canonical source dispositions

| Artifact | HEMOSPACE disposition |
|---|---|
| `model_configurations` | all numeric subject fields exposed |
| `model_variations` | all numeric fields exposed with design-space semantics; uppercase canonical header supported |
| `haemodynamic_parameters` | all numeric subject fields exposed |
| `pulse_wave_indices` | all numeric subject fields exposed |
| `onset_times` | all numeric subject fields exposed |
| `geometry` | on-demand at geometry/comprehensive depth |
| `common_site_waveforms_csv` | source P/U/A/PPG summarized at comprehensive depth; raw signals remain available through core VascuQuest |
| `common_site_waveforms_matlab` | redundant common-site representation |
| `common_site_waveforms_wfdb` | redundant common-site representation; WFDB export metadata supplies the dataset male population assumption |
| `unified_matlab` | overlapping content represented elsewhere; source physiological-plausibility gate reconstructed; small exporter-only metadata remainder has a declared bounded-access limitation |
| path MAT artifacts | qualified lazy on-demand path mode under `QUALIFIED_AUTHORITATIVE_EXPORTER_CONTRACT` |

## Source field closure

For each scalar source table HEMOSPACE counts:

- fields encountered;
- fields exposed;
- missing values for the selected subject.

`scalar_source_complete=true` means:

```text
source_fields_seen = source_fields_exposed + source_fields_missing
```

It does not mean geometry or waveforms were requested.

## Common-site waveform closure

At comprehensive depth HEMOSPACE expects P/U/A/PPG summaries at each canonical common site. Coverage separately reports expected and summarized source waves.

Reconstructed Q is not counted as a source waveform because its evidence is `RECONSTRUCTED`.

## Geometry closure

At geometry/comprehensive depth the complete canonical subject-specific vascular geometry must be retrievable. Failure is reported in record warnings and keeps the requested closure open.

## Derivation closure

The machine agent contract and closure report enumerate the registered scalar and waveform derivations. Any future derived quantity must declare:

- canonical ID;
- evidence class;
- method/equation;
- units;
- required source inputs;
- assumptions/validity boundary.

Arbitrary feature generation is not part of HEMOSPACE closure.

## Unified MAT limitation

The canonical unified `pwdb_data.mat` is a large legacy MATLAB representation. Most of its scientifically relevant subject content duplicates the lightweight scalar tables, geometry, common-site waveforms and path exports.

HEMOSPACE additionally reconstructs the source physiological-plausibility flag exactly from lightweight haemodynamics.

A small exporter-only metadata remainder (for example desired-characteristic bookkeeping and static network-name metadata) is not whole-file-loaded because the legacy file has no bounded per-subject access path. HEMOSPACE explicitly reports this limitation rather than reading hundreds of megabytes simply to make a formal completeness claim.

Accordingly the normal terminal status can be:

```text
CLOSED_WITH_DECLARED_SOURCE_FORMAT_LIMITATION
```

This means operational scientific knowledge for the requested depth is closed while that source-format limitation remains visible.

## Path reader qualification

The path reader is qualified as:

```text
QUALIFIED_AUTHORITATIVE_EXPORTER_CONTRACT
```

Qualification is anchored to the exact PWDB revised-submission exporter used for this dataset release, the canonical Zenodo path filenames/checksums, MATLAB-v7.3/HDF5 struct/cell object-reference conventions, and an executed regression fixture covering all supported path families including the split aorta→foot P/U/A representation.

This is a reader-contract qualification. It establishes that HEMOSPACE decodes the structure produced by the authoritative generator and that the resulting path quantities are assembled correctly. It does not claim a fresh whole-artifact byte scan or reprocessing of all 4,374 virtual subjects. Canonical artifact identity remains independently protected by VascuQuest manifest/checksum verification.

A publication relying on path-derived quantities should retain the canonical Zenodo DOI and artifact checksum used as ordinary provenance; it does not need a separate multi-gigabyte reader-qualification run.

See `HEMOSPACE_PATH_QUALIFICATION.md` for the qualification certificate and executed test scope.

## Unknowable boundary

Knowledge closure also requires stating what cannot be identified from PWDB alone. HEMOSPACE keeps explicit `NOT_KNOWABLE_FROM_PWDB` entries for categories including:

- smoking/exposure history;
- genetics;
- renal function;
- medications;
- symptoms;
- plaque composition;
- thrombotic state;
- longitudinal life history;
- future clinical-event risk.

The absence of these variables is not a missing-data problem to be filled by an AI agent. They were not encoded in the virtual population.

## Modelled pathology boundary

Virtual Disease outputs extend a HEMOSPACE record with explicitly `MODELLED` counterfactual information. They do not reveal pre-existing hidden pathology in the original healthy PWDB subject.

HEMOSPACE response mode consumes persisted disease outputs and preserves:

- subject identity;
- cohort/disease run identity;
- condition;
- severity parameter/value;
- disease parameters;
- evidence class;
- paired endpoint changes.

No solver is rerun for response analysis.

## Closure command

```bash
vascuquest hemospace closure \
  --subject 2104 \
  --depth comprehensive
```

Agents and humans should run this command before stating that a HEMOSPACE record is comprehensive.
