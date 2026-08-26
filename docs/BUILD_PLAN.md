# VascuQuest build and validation plan

**Status:** Governing release boundary for VascuQuest 0.1.0  
**Repository:** `KNOWDYN/VascuQuest`  
**Canonical dataset:** PWDB Zenodo record `3275625`  

This file consolidates the operative effect of the original build plan and the approved core-first amendment. Historical planning records remain under `docs/history/` for traceability.

## 1. Governing principles

1. Canonical source identity, checksums, scientific meaning, units, evidence class, provenance and explicit capability boundaries are never weakened to advance a release.
2. Production functionality ships only after its targeted tests, ordinary regression, audit and explicit validation gate pass.
3. Real-source requirements cannot be replaced by mocks, previews, common-site substitutes or metadata-only checks.
4. Unsupported path-resolved requests must never be silently remapped to common measurement sites.
5. Scientific methods ship only after authoritative-definition and method-validation gates pass.
6. Core operation remains lightweight; optional large-format dependencies are introduced only for separately implemented capabilities that require them.
7. Validation claims are scope-specific: VascuQuest may ship a validated core release without claiming support for the complete 44.3 GB PWDB archive.

## 2. VascuQuest 0.1.0 release scope

The core-first amendment separated the validated lightweight core from the optional dense path-resolved extension.

The 0.1.0 release scope is the completed core track:

`Batches 0–7 → Batch 10 → Batch 11 → Batch 12 → Batch 13 → Batch 14 → Batch 15`

The validated core includes:

- canonical PWDB identity, manifest and schema;
- evidence, validity, provenance and result contracts;
- selective acquisition, local registration and checksum verification;
- deterministic virtual-subject and cohort access;
- canonical scalar quantities from the supported PWDB CSV sources;
- source-supported vascular geometry;
- common-site `P`, `U`, `A` and `PPG` waveforms from the canonical CSV waveform archive;
- validated volumetric-flow reconstruction `Q = U*A` with `RECONSTRUCTED` evidence;
- JSON and CSV exporters;
- public Python application services and facade;
- the frozen v1 CLI with API/CLI parity;
- explicit plugin contracts and unavailable-component failure semantics;
- package build/install validation across the supported Python/platform matrix;
- core Tier-4 real-source release validation.

The 0.1.0 release does **not** claim dense path-resolved waveform support.

## 3. Core release evidence

Batch 15 passed real-source Tier-4 validation for the core scope against the exact six canonical artifacts used by the public release:

1. `pwdb_model_configs.csv`
2. `pwdb_haemod_params.csv`
3. `pwdb_pw_indices.csv`
4. `pwdb_onset_times.csv`
5. `geo.zip`
6. `PWs_csv.zip`

The recorded gate checked canonical checksums, exhaustive 4,374-subject scalar alignment, complete 4,374-member geometry inventory, complete 52-member common-site waveform inventory/alignment, representative public-API waveform reads across all six source age groups, and the real-source `Q = U*A` reconstruction.

The supported Linux/macOS/Windows and Python 3.11–3.14 package matrix also passed, including wheel/sdist build-install checks.

The exact 0.1.0 release candidate must rerun Core CI and the core real-source Tier-4 gate before publication.

## 4. Optional dense path-resolved track

Batch 8 passed its real-source Tier-3 ingestion gate against the canonical MATLAB-v7.3/HDF5 path data and established a direct-access baseline. That proves the canonical path source can be ingested; it does not create a public path capability.

Batch 9 is **deferred optional R&D** and is not on the VascuQuest 0.1.0 release critical path. Experimental PR #12 was closed without merge after release reassessment.

Any future path-resolved release must independently justify its production architecture and pass path-specific validation confirming:

- exact subject/path/signal/spatial-coordinate identity;
- exact or explicitly source-equivalent numerical fidelity;
- deterministic bounded access;
- Python/CLI parity;
- provenance and integrity preservation;
- acceptable production access and memory behaviour;
- explicit failure for unavailable or unsupported path capabilities.

No future optimization may alter scientific values, interpolate unobserved path positions, or replace path data with common-site data for convenience.

## 5. Current release state

- Core implementation: **complete**.
- Core real-source Tier-4 validation: **passed on the validated development candidate; must be rerun on the exact 0.1.0 release candidate**.
- Batch 8 path ingestion: **passed**.
- Dense path-resolved production support: **not part of 0.1.0**.
- Release candidate version: **0.1.0**.
- Publication: **not yet authorized**.

## 6. Historical records

For auditability only:

- [`history/BUILD_PLAN_LEGACY.md`](history/BUILD_PLAN_LEGACY.md)
- [`history/BUILD_PLAN_CORE_FIRST_AMENDMENT.md`](history/BUILD_PLAN_CORE_FIRST_AMENDMENT.md)

These files preserve the original planning record and the formal reasoning that established the core-first release boundary.
