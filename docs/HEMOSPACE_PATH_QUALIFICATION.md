# HEMOSPACE path-reader qualification

Status: **QUALIFIED_AUTHORITATIVE_EXPORTER_CONTRACT**

Date: 2026-10-08

This certificate qualifies the HEMOSPACE reader for the canonical PWDB path-resolved MATLAB files without downloading the multi-gigabyte artifacts. The qualification is a source-contract and format qualification, not a claim that every byte of every path artifact was reprocessed.

## Canonical target

The target is PWDB Zenodo record `3275625` / DOI `10.5281/zenodo.3275625`, version 0.2.0. The VascuQuest manifest records the same canonical filenames and MD5 checksums as the published Zenodo record:

- `pwdb_data_w_aorta_brain_path.mat` — `132c52b9962d83bfa672ff2bc96de6ac`
- `pwdb_data_w_aorta_finger_path.mat` — `801dbfc7927dc951a87034ebb40ff12f`
- `pwdb_data_w_aorta_foot_path_p.mat` — `58a5bfc5eeeb6584652c8238eceba73c`
- `pwdb_data_w_aorta_foot_path_u.mat` — `bc00c1cc9c9ddef5d5070123be4b0f44`
- `pwdb_data_w_aorta_foot_path_a.mat` — `01f6f7c079ccbd245d44996ad95ff58f`
- `pwdb_data_w_aorta_rsubclavian_path.mat` — `85052a34c42b847af397e42bd6300fc7`

VascuQuest acquisition verifies canonical artifact identity/checksum before HEMOSPACE receives a local artifact path.

## Authoritative generator contract

Qualification is anchored to the upstream PWDB v0.1 exporter at commit `5a0d472706b5f87fa1962fa5d1b8412f4e432315`. The upstream README states that v0.1 contains the algorithms used in the revised submission corresponding to this PWDB release.

`pwdb_v0.1/export_pwdb.m` establishes the exact path contract used by HEMOSPACE:

1. subjects are stored in simulation order (`sim_no`), matching canonical subject numbering;
2. each path stores `P`, `U`, and `A` at every represented path point;
3. each path stores `dist`, `artery`, `segment_no`, `artery_dist`, and `onset_time`;
4. pressure is converted to mmHg before storage; `U` and `A` are stored without scaling;
5. the aorta-to-foot export is split into separate P/U/A files by removing the other two signal fields from copies of the same `orig_data`, so subject/path-point alignment is preserved by construction;
6. the right-subclavian structure name is `aorta_r_subclavian`, while the published filename uses `rsubclavian`; the HEMOSPACE mapping matches this distinction;
7. large path variables are saved with MATLAB `-v7.3` when they exceed 1.8 GB. The published path artifacts are 5.9–8.2 GB, therefore the canonical path files are necessarily MATLAB-v7.3/HDF5 files.

MathWorks documents MAT-file v7.3 as HDF5-based. MATLAB struct arrays are represented as struct groups whose fields contain per-element HDF5 object references; MATLAB cell arrays likewise contain HDF5 object references, with strings represented as UTF-16 character arrays. These are the representations read by `vascuquest.hemospace.path`.

## Executed reader-contract test

The current HEMOSPACE reader was exercised in the development backend against an HDF5 fixture reproducing the canonical MATLAB-v7.3 representation:

- nested `data/path_waves/<path>` struct hierarchy;
- 1×N subject field-reference arrays;
- MATLAB-style object-reference cell arrays;
- numeric `dist`, `artery_dist`, and `onset_time` arrays;
- UTF-16 artery-name datasets;
- referenced scalar segment numbers;
- referenced P/U/A waveform arrays;
- combined path files;
- split aorta-to-foot P/U/A files.

All four public HEMOSPACE path families passed:

| Path | Signals recovered | Metadata recovered | Q=U×A | path PWV | pressure amplification |
|---|---|---|---|---|---|
| `aorta_brain` | P/U/A | yes | pass | pass | pass |
| `aorta_finger` | P/U/A | yes | pass | pass | pass |
| `aorta_foot` | split P/U/A | yes | pass | pass | pass |
| `aorta_r_subclavian` | P/U/A | yes | pass | pass | pass |

The fixture used a known linear onset-distance relation corresponding to 5 m/s; HEMOSPACE recovered 5 m/s with R² = 1.0 for every path family. The split-foot reader reconstructed Q at every path point from the independently stored U and A files.

A permanent regression fixture is kept in `tests/hemospace/test_path_reader_contract.py`.

## Source metadata quirk

The upstream exporter assigns `data.waves.units.A = 'm3'` in one MATLAB units structure. This is an upstream metadata typo: `A` is explicitly the luminal-area signal elsewhere in the exporter/model and is used as area in `Q = U .* A`. HEMOSPACE does not consume that erroneous units string; it reads the numeric A signal and treats it according to the canonical VascuQuest luminal-area definition.

## Qualification boundary

This qualification establishes that the HEMOSPACE reader matches the authoritative generator and MATLAB-v7.3 storage contract of the canonical path artifacts. It does **not** claim a fresh full-artifact byte scan or recomputation of all 4,374 subjects.

That distinction is intentional. Canonical artifact identity is enforced independently through the VascuQuest manifest and checksums; reader qualification concerns whether the reader correctly decodes the structure produced by the authoritative exporter.

Therefore publication/reproducibility reports should continue to record the canonical Zenodo DOI and artifact checksum used, but no additional multi-gigabyte reader-qualification run is required merely to use HEMOSPACE path mode.
