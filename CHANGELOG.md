# Changelog

All notable release-facing changes to VascuQuest are recorded here.

## 0.1.0 — 2026-08-26

First public research-software release candidate for the validated PWDB core scope.

### Research capabilities

- Canonical PWDB identity bound to Zenodo record `3275625`.
- Deterministic virtual-subject and cohort access across 4,374 simulation instances.
- Canonical scalar quantities from verified PWDB source tables.
- Subject-specific vascular geometry from the canonical geometry archive.
- Common-site pressure (`P`), flow-velocity (`U`), luminal-area (`A`) and photoplethysmogram (`PPG`) waveforms.
- Validated volumetric-flow reconstruction using `Q = U*A`, reported as `RECONSTRUCTED` evidence.
- Structured evidence classes, provenance and strict reproduction semantics.
- JSON and CSV export with scientific metadata preservation.
- Shared Python API and command-line application services.
- Explicit plugin contracts for backends, derivations, research operators, discovery methods and exporters.

### Validation

The core PWDB scope passed real-source Tier-4 validation against the six canonical artifacts used by the release, including exhaustive subject alignment, complete geometry and common-site waveform inventories, representative public-API reads across source age groups, and real-source flow-rate reconstruction. The supported Python/platform package matrix also passed wheel/sdist build-install testing.

### Scope boundary

Dense path-resolved PWDB waveform support is not part of VascuQuest 0.1.0. Its real-source ingestion was investigated separately, but no public path-resolved capability is claimed. VascuQuest 0.1.0 does not claim validation against the complete 44.3 GB PWDB archive.

### Data and licensing

VascuQuest does not bundle, re-host or relicense PWDB. The software is Apache-2.0 licensed; upstream PWDB data remain external and retain their own source identity and citation requirements.
