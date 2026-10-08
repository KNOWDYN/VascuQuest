# VascuQuest 1.0 data engineering contract

## 1. Scope

This document governs source identity, acquisition, integrity, storage, bounded access, subject alignment, and data-representation boundaries for VascuQuest 1.0.

The canonical upstream dataset remains the **Pulse Wave DataBase (PWDB)**, Zenodo record `3275625`, DOI `10.5281/zenodo.3275625`. VascuQuest software does not replace, re-host, or relicense PWDB.

## 2. Canonical artifact identity

VascuQuest recognizes the canonical PWDB artifact set through its packaged manifest. Artifact trust is based on explicit identity and checksum verification, not filenames alone.

Canonical artifacts include source tables, geometry, common-site waveform archives, the unified MATLAB file, and dense path-resolved MATLAB artifacts. Local registration and selective acquisition must verify recognized artifacts before they become trusted inputs.

## 3. Core source representations

The primary lightweight source surfaces are:

- `pwdb_model_configs.csv`;
- `pwdb_model_variations.csv`;
- `pwdb_haemod_params.csv`;
- `pwdb_pw_indices.csv`;
- `pwdb_onset_times.csv`;
- `geo.zip`;
- `PWs_csv.zip`.

Alternate waveform representations (`PWs_mat.zip`, `PWs_wfdb.zip`) are source-equivalent representations with their own access/validation considerations.

## 4. Subject identity and ordering

PWDB contains 4,374 virtual simulation instances. Subject identity is canonical and must not depend on row number after filtering, dataframe index, filesystem ordering, or archive iteration order.

Source tables used together must preserve the canonical subject sequence. HEMOSPACE adapters accept the supported subject-number header variants and normalize them to canonical subject IDs.

Any operation combining subject-level values must align by canonical identity. Pairing by array position is forbidden when subject IDs are available.

## 5. Designed population semantics

PWDB is a designed virtual population. Source age groups and generative variation dimensions describe simulation design, not clinical prevalence.

The model-variation axes include diameter, heart rate, proximal aortic length, LVET, mean blood pressure, peripheral vascular compliance, arterial stiffness/PWV, reverse-flow volume, stroke volume, and peak-flow time deviations. These are model-input deviations relative to age-specific design means, not patient clinical z-scores.

`AGE` is a design/grouping field in years and must not be treated as a standard-deviation variation axis.

## 6. Common-site waveforms

Common-site pressure (`P`), flow velocity (`U`), luminal area (`A`), and PPG waveforms are source data. Reconstructed volumetric flow uses:

```text
Q = U * A
```

when the source velocity and area waveforms are aligned. `Q` is reported as `RECONSTRUCTED`, not `SOURCE`, because it is not stored as a canonical source waveform in the same representation.

No interpolation is performed merely to force mismatched waveforms into compatibility.

## 7. Dense path-resolved artifacts

VascuQuest 1.0 supports lazy path access through the HEMOSPACE path reader for:

- `aorta_brain`;
- `aorta_finger`;
- `aorta_foot` (split P/U/A artifacts);
- `aorta_r_subclavian`.

The canonical published path artifacts are sufficiently large that the authoritative PWDB exporter stores them as MATLAB `-v7.3`, i.e. HDF5-backed files. The VascuQuest path reader therefore requires `h5py` and refuses a whole-file fallback for large non-HDF5 MAT files.

The reader follows the exporter representation under `data/path_waves/<path>` and dereferences MATLAB struct/cell object references. It reads path metadata (`dist`, `artery_dist`, `onset_time`, artery identity, segment identity) and available P/U/A signals, reconstructs Q where U/A are available, and computes declared path summaries.

### Qualification status

Path-reader status is:

```text
QUALIFIED_AUTHORITATIVE_EXPORTER_CONTRACT
```

The qualification triangulates canonical artifact identity, the authoritative upstream PWDB exporter, MATLAB-v7.3/HDF5 storage semantics, and an executed exact-layout regression fixture. It is not a claim that VascuQuest freshly scanned every byte of every multi-gigabyte path artifact during the v1.0 build.

See [`HEMOSPACE_PATH_QUALIFICATION.md`](HEMOSPACE_PATH_QUALIFICATION.md).

## 8. Unified `pwdb_data.mat`

The unified legacy MATLAB representation is not used as a reason to perform unbounded whole-file loading. HEMOSPACE knowledge closure records the remaining exporter-only metadata limitation explicitly where bounded subject-level access is unavailable.

This deliberate source-format limitation does not authorize fabrication or substitution from another representation.

## 9. Geometry

Subject-specific vascular geometry remains source-derived and identity-preserving. Geometry consumers must not infer unobserved three-dimensional shape, wall thickness, plaque geometry, or patient-specific material properties unless a separately validated source/model provides them.

Virtual Disease may transform qualified geometric/model parameters as part of a `MODELLED` disease state. Those transformed values belong to the disease dataset identity and must not overwrite healthy PWDB source geometry.

## 10. HEMOSPACE data policy

HEMOSPACE is read-only relative to canonical PWDB artifacts. It can expose, summarize, reconstruct, and derive information, but cannot rewrite source files or silently make source data more complete than they are.

Knowledge closure distinguishes:

- exposed source fields;
- deterministic reconstructions/derivations;
- lazy path access;
- redundant representations;
- source-format limitations;
- information not knowable from PWDB.

## 11. Virtual Disease data policy

Virtual Disease creates a separate modelled dataset identity. Healthy subject IDs are preserved as references, but disease values are not written back into PWDB.

Portable disease bundles retain request identity, checksums, scientific warnings, subject IDs, provenance, quantity-status information, and qualification state.

## 12. Analysis-layer data policy

`vascuquest.analysis`, `stats`, `mechanics`, `spectral`, and `plot` are downstream consumers. They do not own source acquisition or artifact mutation.

External data may enter a canonical analysis only through controlled wrapping that declares:

- values;
- quantity definition;
- unit;
- dimensions/coordinates;
- subject/cohort identity where applicable;
- location where applicable;
- source/provenance context;
- evidence/validity interpretation.

Anonymous arrays may be useful internally but are not sufficient scientific records.

## 13. Time-series alignment

Operations requiring simultaneous waveforms must verify time-coordinate compatibility.

- mechanics and local impedance/wave-separation require compatible co-located time series;
- cross-site spectral relations may use different locations for the same subject when time coordinates align;
- uniformly sampled methods must verify uniform sampling;
- hidden resampling/interpolation is forbidden.

If resampling is introduced in a future release, it must be an explicit named method with provenance and qualification.

## 14. Integrity and failure behavior

VascuQuest must fail explicitly when:

- a required artifact is absent;
- a checksum does not match;
- a source representation is unsupported;
- subject identities do not align;
- required time coordinates are incompatible;
- a large path artifact is not in the supported HDF5 representation;
- an optional dependency required for the chosen method is missing.

Failure must not trigger silent fallback to a scientifically different source or method.

## 15. Acquisition and computation policy

Importing VascuQuest never implies downloading the complete PWDB archive. Acquisition remains selective.

Post-processing functions must operate on already available scientific results and must not rerun expensive disease/network simulations unless the user explicitly requests simulation generation.

## 16. Data and licensing boundary

VascuQuest is Apache-2.0 software. PWDB remains external data with its own source identity and citation requirements. Software citation never replaces dataset citation in research that uses PWDB.
