# PWDB Tier-3 empirical ingestion validation

This directory contains validation tooling that is intentionally separate from ordinary fixture/contract tests.

## Current Batch 8 status

**Gate status: NOT PASSED in the current execution workspace.**

The Batch 8 harness is implemented, but this workspace has no byte-level network access to the Zenodo artifacts and no local copy of the multi-gigabyte canonical files. The Zenodo record and archive previews can establish record identity and visible archive layout, but they cannot substitute for checksum verification or the required bounded read from a real large path MAT file.

Accordingly, `path_reader.py` must not be implemented or declared production-ready from this branch until the harness produces a successful report against verified files from Zenodo record `3275625`.

## Canonical artifacts used by the spike

The harness deliberately uses the minimum set that covers every required source class plus a cross-representation waveform comparison:

- `pwdb_model_configs.csv`
- `geo.zip`
- `PWs_csv.zip`
- `PWs_wfdb.zip`
- `pwdb_data.mat`
- `pwdb_data_w_aorta_foot_path_p.mat`

The final item is selected because it is one of the smaller canonical path artifacts (reported by Zenodo as 5.9 GB) and contains the aorta-to-foot pressure path required for a bounded subject/path/signal test.

All six artifacts are verified against the checksums in the packaged canonical manifest before any empirical conclusion is accepted.

## Reader dependencies for the spike

The build plan already identifies these reader candidates:

```text
scipy >=1.17,<2
h5py >=3.15,<4
wfdb >=4.3,<5
```

They remain spike dependencies rather than newly declared mandatory package dependencies until the empirical results justify the final packaging choice.

## Running the gate

From the repository root, with the six exact canonical files in one local directory:

```bash
python tests/full_data/pwdb3275625_ingestion_spike.py /path/to/pwdb3275625 \
  --report pwdb3275625_ingestion_spike_report.json
```

Exit code `0` and report status `"passed"` are required before Batch 8 can close.

The report records:

- checksum verification and observed byte size for every required artifact;
- metadata CSV columns, explicit subject IDs, coverage, and ordering;
- geometry subject-file mapping and representative source fields;
- the exact 13-site x 4-signal common-site CSV archive layout;
- WFDB record-to-subject mapping, sample frequency, signal/unit metadata, and a bounded real record read;
- CSV-versus-WFDB numerical differences, with tolerance tied to the selected WFDB channel's ADC quantization step rather than an arbitrary global tolerance;
- `pwdb_data.mat` container format and top-level MATLAB variable structure using SciPy;
- the large path MAT HDF5 hierarchy actually observed by h5py;
- one subject-1/aorta-foot/pressure waveform read through MATLAB object references without whole-file materialization;
- subject/path distance alignment for that bounded path read;
- first and repeated bounded-read timings, approximate Linux RSS change when available, and deterministic repeated-read identity;
- the resulting DIRECT/INDEXED/CONVERTED decisions;
- resume/range status. Current VascuQuest acquisition does not claim resumable/range downloads, so the spike does not invent such a claim.

## Evidence already established without closing the gate

The live Zenodo record `https://zenodo.org/records/3275625` identifies the canonical dataset as DOI `10.5281/zenodo.3275625`, reports the 44.3 GB file set, and exposes the checksums represented in the VascuQuest manifest.

The Zenodo preview of `PWs_csv.zip` exposes the expected common-site CSV naming layout, while the `geo.zip` preview exposes subject-specific `pwdb_geo_####.csv` members. These observations support the spike harness, but they are not treated as Tier-3 substitutes for reading checksum-verified local artifacts.

## Hard boundary

A failed or unavailable spike report is a recorded validation limitation, not permission to choose a path-storage strategy by inference. Batch 9 begins only after the real-source report passes and its measured results are reviewed.
