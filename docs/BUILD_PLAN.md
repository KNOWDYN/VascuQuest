# VascuQuest build and validation plan

**Status:** Current governing build sequence  
**Repository:** `KNOWDYN/VascuQuest`  
**Canonical v1 dataset:** PWDB Zenodo record `3275625`  

This file consolidates the operative effect of the original `BUILD_PLAN.md` and the later core-first amendment. The original texts are retained in `docs/history/` for traceability but are non-governing.

## 1. Governing principles

1. Canonical source identity, checksums, scientific meaning, units, evidence class, provenance, and explicit capability boundaries are never weakened to advance a batch.
2. Production functionality advances only after its targeted tests, ordinary regression, audit, and explicit validation gate pass.
3. Real-source requirements cannot be replaced by mocks, previews, common-site substitutes, or metadata-only checks.
4. Path-resolved requests must never be silently remapped to common measurement sites.
5. Scientific methods ship only after authoritative-definition and method-validation gates pass.
6. Core operation remains lightweight; optional MATLAB/HDF5/WFDB dependencies are introduced only where the implemented path capability requires them.
7. Each development batch is implemented on a dedicated branch/PR and merged before the next batch begins.

## 2. Resolved sequencing

The core-first amendment separated the lightweight core release track from the optional path-resolved track.

### Core track — completed

`Batches 0–7 → Batch 10 → Batch 11 → Batch 12 → Batch 13 → Batch 14 → Batch 15`

The completed core scope includes:

- canonical dataset identity, schema, provenance, evidence and result contracts;
- acquisition/integrity infrastructure and PWDB backend foundations;
- Python application services and facade;
- the validated built-in flow-rate reconstruction `Q = U*A`;
- JSON/CSV exporters;
- the frozen v1 CLI;
- package/CI/readme integration across supported Python/platform combinations;
- core Tier-4 real-source release validation.

The core track does **not** claim dense path-resolved waveform support.

### Path-resolved track

`Batch 8 → Batch 9 → path-specific Tier-4/release validation`

#### Batch 8 — completed

Batch 8 performed the mandatory real-source Tier-3 ingestion gate using the canonical PWDB artifacts, including the 5.94 GB `pwdb_data_w_aorta_foot_path_p.mat` artifact.

The passed evidence established:

- checksum-verified acquisition of the canonical path source;
- MATLAB v7.3/HDF5 structure and real hierarchy/indexing semantics;
- bounded subject 1 / `aorta_foot` / pressure access without whole-file materialization;
- a 412-sample float64 waveform at one path position;
- 72 path positions aligned with 72 distance coordinates;
- byte-identical repeated bounded reads;
- measured direct-access performance of approximately 100.047 s first access and 94.519 s repeated access.

`DIRECT` is therefore the proven canonical source-access baseline. The measured latency is an engineering input to Batch 9, not a reason to reopen Batch 8.

#### Batch 9 — next

Batch 9 implements production path-resolved support from the proven canonical baseline. It must:

- preserve canonical PWDB source identity and checksums;
- provide bounded subject/path/signal/position retrieval;
- eliminate naive repeated MATLAB-reference traversal from the public-reader experience through a persistent lookup/index or an equivalently justified mechanism;
- preserve exact waveform and spatial-coordinate identity;
- expose explicit Python/API and CLI path semantics without common-site substitution;
- keep optional reader dependencies isolated from the lightweight core where practical;
- record provenance that distinguishes canonical source data from any derived indexing/storage aid;
- benchmark first and repeated production access, memory behavior, and failure modes;
- pass targeted tests, ordinary regression, and audit before path-specific Tier-4 validation begins.

Batch 9 does not gain permission to alter scientific values, interpolate unobserved path positions, or replace canonical path data with common-site data for performance convenience.

#### Path-specific Tier-4 / release validation — after Batch 9

The final path gate must validate the production reader against checksum-verified canonical path artifacts and confirm:

- exact subject/path/signal/spatial-coordinate identity;
- exact or explicitly source-equivalent numerical fidelity;
- deterministic bounded access;
- public Python/CLI parity;
- provenance/integrity preservation;
- acceptable production access and memory behavior;
- explicit failure for unavailable or unsupported path capabilities.

Only after this gate passes may VascuQuest advertise validated path-resolved support or validation against the corresponding path portion of PWDB.

## 3. Current repository state

- Core implementation and core Tier-4 validation: **passed**.
- Batch 8 real-source Tier-3 path ingestion: **passed**.
- Production path reader: **not yet implemented**.
- Path-specific Tier-4 validation: **not yet passed**.
- Package version remains pre-release until a separate release-publication decision is made.

## 4. Historical records

For auditability only:

- [`history/BUILD_PLAN_LEGACY.md`](history/BUILD_PLAN_LEGACY.md)
- [`history/BUILD_PLAN_CORE_FIRST_AMENDMENT.md`](history/BUILD_PLAN_CORE_FIRST_AMENDMENT.md)

These historical files preserve the original planning record. This consolidated file is the current governing sequence.
