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

### Core execution

The repository workflow `.github/workflows/core-release-validation.yml` runs this harness separately from ordinary CI and uploads the JSON validation report even when the harness fails.

For a local real-source run, isolate the platformdirs-managed VascuQuest data roots and execute:

```bash
python tests/full_data/core_release_validation.py \
  --report core-release-validation.json \
  --code-revision "$(git rev-parse HEAD)" \
  --repo-root .
```

## Batch 8 — Tier-3 path-ingestion gate

`pwdb3275625_ingestion_spike.py` is the mandatory empirical gate before any production path reader is implemented. It is validation tooling, not a backend.

The Batch-8 runner acquires and checksum-verifies these canonical artifacts from Zenodo record `3275625`:

1. `pwdb_model_configs.csv` — explicit subject-index audit;
2. `geo.zip` — subject-specific geometry audit;
3. `PWs_csv.zip` — canonical common-site CSV comparison source;
4. `PWs_wfdb.zip` — real WFDB inspection and cross-representation comparison;
5. `pwdb_data.mat` — conventional MATLAB structural inspection;
6. `pwdb_data_w_aorta_foot_path_p.mat` — real multi-gigabyte path-pressure source.

The decisive path artifact must match canonical MD5 `58a5bfc5eeeb6584652c8238eceba73c` before any path result is accepted.

The corrected Tier-3 harness records:

- canonical checksum and byte size for every required artifact;
- actual source format/hierarchy and indexing semantics;
- exact 1..4374 subject alignment where represented;
- representative geometry structure;
- real WFDB sampling metadata and CSV-vs-WFDB differences using a source-derived bound that combines MATLAB `dlmwrite` five-significant-digit rounding with WFDB quantization;
- conventional `pwdb_data.mat` top-level structure without loading the nested dataset into memory;
- a bounded HDF5/MATLAB-v7.3 read of subject 1 / `aorta_foot` / pressure;
- path-position/distance cardinality when distance metadata is present;
- first and repeated bounded-read timings;
- Linux RSS before/after each bounded path read when available;
- deterministic repeated numeric identity;
- explicit lack of HTTP range/resume claims;
- an evidence-backed canonical path-access candidate for Batch 9.

### Batch-8 gate result

Batch 8 passed on canonical real-source workflow run `32893318886`, code revision `00dd2c1c7d9ec79ee5272707b9fc0b808793599c`.

The run established:

- checksum-verified direct access to the 5.94 GB MATLAB v7.3/HDF5 path artifact;
- subject 1 / `aorta_foot` / pressure resolution without whole-file materialization;
- a 412-sample float64 bounded waveform at one path position;
- 72 waveform positions and 72 distance coordinates with matching cardinality;
- byte-identical repeated bounded reads;
- first bounded access of approximately `100.047 s` with `601,878,528` bytes measured RSS growth;
- repeated bounded access of approximately `94.519 s` with `5,849,088` bytes measured RSS growth.

The machine-readable Tier-3 report therefore selects `DIRECT` as the **canonical access candidate**: the source is scientifically addressable directly and deterministically. The measured latency is also explicit evidence that naive MATLAB-reference traversal is not acceptable as the final public-reader experience.

That performance observation is a Batch-9 engineering requirement, not an additional Batch-8 gate. Batch 9 must implement and test bounded production path-reader semantics, including an optimized persistent lookup/index or equivalent access mechanism, while preserving canonical source identity and prohibiting silent substitution with common-site data. Batch 8 does not require a separate INDEXED-versus-CONVERTED benchmark before closure.

### Batch-8 local/online execution

When the six canonical artifacts are already present in one verified source directory:

```bash
python tests/full_data/pwdb3275625_ingestion_spike_corrected.py /path/to/source \
  --report pwdb3275625-tier3-report.json \
  --code-revision "$(git rev-parse HEAD)"
```

To acquire the six artifacts through VascuQuest's own acquisition layer and then execute the same gate:

```bash
python tests/full_data/run_online_pwdb3275625_ingestion_spike.py /path/to/workspace \
  --report pwdb3275625-tier3-report.json \
  --code-revision "$(git rev-parse HEAD)"
```

The validation environment requires `numpy`, `scipy`, `h5py`, and `wfdb`; these are Batch-8 validation dependencies and are not made unconditional core runtime dependencies merely by this gate.

## Explicit scope boundary

The completed core Tier-4 gate does **not** validate or claim dense path-resolved waveforms. Batch 8 proves real canonical path ingestion and establishes the source-access baseline; it does not implement production path semantics. Synthetic fixtures, common-site data, exporter source inspection, or source-code assumptions must never substitute for the checksum-verified real path-MAT evidence.

Path support remains unavailable until Batch 9 implements the production reader and path-specific Tier-4 validation passes.
