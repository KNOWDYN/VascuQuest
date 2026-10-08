# VascuQuest build and validation plan

**Status:** Governing release boundary for VascuQuest 1.0  
**Repository:** `KNOWDYN/VascuQuest`  
**Canonical dataset:** PWDB Zenodo record `3275625`  
**Software DOI:** `10.13140/RG.2.2.26784.96004`

This document defines the current v1.0 release boundary. Earlier batch plans and core-first amendments remain under `docs/history/` for traceability only.

## 1. Governing principles

1. Canonical source identity, checksums, units, scientific meaning, evidence class, provenance, validity state, and explicit capability boundaries must remain visible.
2. A `VirtualSubject` is a simulation instance, never a patient.
3. New v1 analysis functionality consumes existing VascuQuest scientific objects; it does not mutate PWDB core semantics, HEMOSPACE semantics, or qualified Virtual Disease physics.
4. Source, reconstructed, derived, inferred, and modelled quantities must never be silently conflated.
5. Subject and cohort identity must survive every transformation. Paired analyses use canonical subject identity, not row position.
6. No method may silently interpolate, resample, downsample, remap locations, substitute unavailable source data, or manufacture missing clinical information.
7. The designed PWDB population is not epidemiological. Frequencies and empirical probabilities are properties of the virtual design space unless explicitly supported otherwise.
8. Core installation remains lightweight. SciPy/PyWavelets, Matplotlib, JAX, and HDF5 support remain optional extras.
9. Expensive full-network computations are not required to qualify deterministic post-processing methods when manufactured/analytical reference cases can establish correctness.
10. Validation claims are scope-specific and must identify exactly what was tested.
11. Current documentation is part of the release contract: README, governing docs, subsystem docs, API/CLI docs, and qualification-boundary wording must agree with the implemented release candidate.

## 2. VascuQuest 1.0 platform scope

The v1.0 release integrates the following first-class layers:

### Core PWDB

- canonical dataset identity and manifest;
- selective checksum-verified acquisition and local registration;
- 4,374 canonical virtual-subject identities;
- scalar source tables, geometry, onset/fiducial quantities, pulse-wave indices;
- common-site `P`, `U`, `A`, and `PPG` waveforms;
- `Q = U*A` flow-rate reconstruction with `RECONSTRUCTED` evidence;
- JSON/CSV export and provenance-aware reproduction;
- Python 3.11–3.14 support.

### HEMOSPACE

- provenance-aware Virtual Cardiovascular Records;
- source-table semantic normalization;
- deterministic physiological derivations;
- plausibility reconstruction;
- phenotype-driven cohort selection;
- disease-response characterization from qualified persisted bundles;
- source-coverage/knowledge-closure audit;
- lazy dense path access for `aorta_brain`, `aorta_finger`, `aorta_foot`, and `aorta_r_subclavian`;
- path-reader status `QUALIFIED_AUTHORITATIVE_EXPORTER_CONTRACT`.

The HEMOSPACE path qualification is an authoritative exporter/storage-contract qualification. It does not imply a fresh whole-artifact byte scan of every multi-gigabyte path file.

### Virtual Disease

- healthy baseline reconstruction;
- mechanistic disease transformations;
- full-network disease solver and optional JAX backend;
- four frozen presets: carotid stenosis, iliac stenosis, fusiform abdominal aortic aneurysm, and large-artery stiffening;
- deterministic disease populations and parameterized cohorts;
- portable bundles and explicit quantity-status semantics;
- outputs remain `MODELLED` and are not clinically validated.

Virtual Disease is the sole owner of disease-state generation. The v1 analysis stack consumes already materialized results; it does not modify disease equations, geometry transforms, boundary conditions, numerical schemes, or qualification states.

### Qualified research analysis

`vascuquest.analysis` provides the shared native analysis contract. `vascuquest.stats` provides a qualified statistical core including descriptive statistics, confidence intervals, bootstrap/permutation inference, paired and independent comparisons, effect sizes, diagnostic tests, correlation/partial correlation, regression, ANOVA/ANCOVA, FDR correction, and empirical exceedance probabilities.

External arrays are admitted only through an explicit controlled wrapping step that declares quantity, units, coordinates, identity, and provenance context.

### Vascular mechanics

`vascuquest.mechanics` derives pressure-area and wave-mechanics quantities from aligned existing VascuQuest results. v1.0 includes area/diameter strain, compliance, distensibility, pressure-area slope, hysteresis/loop area, Peterson-type modulus, beta stiffness, and qualified Bramwell-Hill-type wave-speed descriptors.

This subsystem is not an FSI solver and makes no three-dimensional wall-stress or fluid-solid coupling claim.

### Spectral and wave analysis

`vascuquest.spectral` includes Fourier harmonics, PSD, CSD, coherence, transfer functions, pressure-flow impedance, characteristic-impedance descriptors, forward/backward wave separation, wave intensity, STFT, and wavelet transforms.

Local pressure-flow methods require co-located signals. Cross-site spectral relations may compare different arterial locations for the same subject when their native time coordinates are aligned. Uniform sampling is required; hidden resampling is forbidden.

### Scientific plotting

`vascuquest.plot` provides declarative figure/panel/layer/inset specifications for publication-grade output. Large cohorts are never silently thinned. Rasterization is a rendering choice only. Any binning, density estimate, summary statistic, or other data transformation must be explicit in the figure specification.

All legends must remain outside the scientific plotting region and be collision-checked against axes, tick labels, axis labels, titles, insets, and neighboring panels.

## 3. Canonical v1 research workflow

```text
canonical PWDB / wrapped external result / persisted Virtual Disease result
        ↓
ScientificResult / Waveform
        ↓
HEMOSPACE phenotype and/or cohort context
        ↓
mechanics and spectral derivations as required
        ↓
qualified statistics
        ↓
declarative figure specification
        ↓
result JSON + figure-spec JSON + SVG/PDF/PNG
```

The ordering is conceptual rather than mandatory: a study may use only the layers it needs. The invariant is that downstream layers consume scientific objects and never silently regenerate or rewrite upstream state.

## 4. Release qualification strategy

VascuQuest 1.0 uses the least expensive scientifically sufficient qualification mechanism for each layer:

- core source access retains the established real-source validation evidence;
- path reading retains the dedicated exporter/storage-contract qualification certificate;
- Virtual Disease retains its existing physics/reconstruction/cohort qualification evidence;
- statistics use deterministic and analytical reference cases;
- mechanics use manufactured pressure-area signals with known results;
- spectral methods use manufactured harmonic/phase/impedance cases;
- plotting uses deterministic layout/figure-spec tests, including inset and legend collision checks;
- ordinary core regression verifies that new namespaces do not break existing API/CLI behavior;
- documentation changes are validated by cross-document contract consistency rather than expensive numerical reruns.

No v1.0 release gate requires rerunning the entire 4,374-subject disease solver merely to validate post-processing or documentation changes.

## 5. Dependency policy

Core runtime dependencies remain:

- NumPy;
- platformdirs;
- Typer.

Optional extras:

- `research`: SciPy and PyWavelets;
- `plot`: Matplotlib;
- `path`: h5py;
- `jax`: JAX;
- `all`: all optional runtime capabilities.

Importing VascuQuest must not automatically download PWDB artifacts or trigger expensive computation.

## 6. v1.0 release state

For the `feature/v1-platform` candidate represented by PR #25:

- core PWDB layer: **preserved**;
- HEMOSPACE: **complete, including qualified lazy path access**;
- Virtual Disease: **preserved and qualified within its declared mechanistic scope**;
- analysis/statistics: **implemented**;
- vascular mechanics: **implemented**;
- spectral/wave analysis: **implemented**;
- declarative plotting: **implemented**;
- Python/CLI integration: **implemented**;
- package version: **1.0.0**;
- documentation consolidation/synchronization: **complete for the release candidate**;
- merge policy: **manual merge only**.

The current documentation index is [`README.md`](README.md) in this directory. Historical and machine-readable evidence records remain intentionally separate from current design prose.

## 7. Explicit non-claims

VascuQuest 1.0 does not claim:

- patient digital-twin status;
- clinical diagnosis, treatment recommendation, prognosis, rupture/stroke/thrombosis risk, or epidemiological prevalence;
- recovery of absent smoking, genetics, renal disease, medication, plaque composition, symptoms, or future events from PWDB;
- longitudinal interpretation of different PWDB ages as one biological person;
- full three-dimensional CFD/FSI, wall shear stress, plaque mechanics, or thrombus modeling;
- validation beyond the specific scope documented for each subsystem.

## 8. Qualification evidence rule

Human-readable qualification documents and files under `docs/evidence/` preserve the exact evidence boundary of the qualified subsystem. Frozen labels, revisions, dates, or exclusions in those records must not be rewritten merely to make them sound more current.

Conversely, a frozen qualification label must not be misread as the current status of unrelated downstream v1.0 capabilities. Current product behavior is defined by the governing documents and current code; frozen evidence defines the scope of the evidence it records.

## 9. Historical records

The following are retained for auditability only and are superseded by this v1.0 plan:

- [`history/BUILD_PLAN_LEGACY.md`](history/BUILD_PLAN_LEGACY.md)
- [`history/BUILD_PLAN_CORE_FIRST_AMENDMENT.md`](history/BUILD_PLAN_CORE_FIRST_AMENDMENT.md)

Historical text must not be used to infer the current v1.0 capability boundary.
