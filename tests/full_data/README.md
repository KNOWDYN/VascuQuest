# Full-source validation

This directory contains explicit real-source validation that is intentionally excluded from ordinary fast CI.

## Core PWDB v1 Tier-4 validation

`core_release_validation.py` validates the exact source scope claimed by the core-only VascuQuest v1 release candidate under `BUILD_PLAN_CORE_FIRST_AMENDMENT.md`.

The claimed production source artifacts are:

1. `pwdb_model_configs.csv` (`model_configurations`)
2. `pwdb_haemod_params.csv` (`haemodynamic_parameters`)
3. `pwdb_pw_indices.csv` (`pulse_wave_indices`)
4. `pwdb_onset_times.csv` (`onset_times`)
5. `geo.zip` (`geometry`)
6. `PWs_csv.zip` (`common_site_waveforms_csv`)

The harness acquires these files from the canonical Zenodo record `3275625` through VascuQuest's production acquisition layer and verifies each manifest checksum before scientific validation.

The validation then performs:

- exact source-artifact identity and checksum verification;
- exhaustive 4,374-subject alignment across every claimed scalar CSV table;
- mechanical validation that all implemented scalar schema mappings address real source fields;
- exhaustive six-age-group population counts (`729` subjects per age group);
- exhaustive geometry archive subject-member inventory plus deterministic age/configuration-stratified public-API geometry reads;
- exhaustive inventory and subject alignment of all `13 x 4 = 52` declared common-site CSV waveform members;
- deterministic representative public-API waveform reads across age, site and signal classes;
- a real-source integration check of the authoritative built-in `Q = U*A` flow-rate reconstruction;
- software/dataset attribution and Apache-2.0 code-licence boundary checks;
- machine-readable recording of code revision, package/schema/manifest versions, source checksums, platform/library context and validation results.

The deterministic geometry sample is the first, middle and last source subject within each of the six canonical age groups. Expensive waveform numerical parsing is sampled through the public API after every declared waveform file has already undergone exhaustive structural and subject-alignment scanning.

## Explicit exclusions

This core-only Tier-4 gate does **not** validate or claim:

- dense path-resolved waveforms or any path MAT artifact;
- the complete 44.3 GB PWDB archive;
- `pwdb_data.mat`;
- MATLAB or WFDB alternate common-site representations;
- `model_variations`, which is mapped for future expansion but is not an advertised core capability;
- plausibility metadata, which is not exposed or claimed by the current core capability/schema.

Path-resolved support remains governed separately by Batch 8 and Batch 9. Synthetic fixtures, common-site data, or this core release gate must never be used as substitutes for the real path-data Tier-3/Tier-4 requirements.

## Execution

The repository workflow `.github/workflows/core-release-validation.yml` runs this harness separately from ordinary CI and uploads the JSON validation report even when the harness fails.

For a local real-source run, isolate the platformdirs-managed VascuQuest data roots and execute:

```bash
python tests/full_data/core_release_validation.py \
  --report core-release-validation.json \
  --code-revision "$(git rev-parse HEAD)" \
  --repo-root .
```

The run requires network access to the canonical Zenodo record unless the six artifacts are already available in the isolated verified managed cache. A release-critical failure is a hard failure; it must not be converted to `xfail` or silently excluded from the claimed core scope.
