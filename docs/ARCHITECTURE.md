# VascuQuest 1.0 architecture

## 1. Purpose

VascuQuest 1.0 is an in-silico vascular research platform. Its architecture is intentionally layered so source access, scientific identity, mechanistic modeling, post-processing, statistical inference, and visualization remain separable and auditable.

The central dependency rule is:

> Downstream research layers consume existing VascuQuest scientific objects. They do not mutate PWDB core semantics, HEMOSPACE semantics, or qualified Virtual Disease physics.

## 2. System map

```text
VascuQuest
├── Core PWDB access
│   ├── canonical dataset identity / manifest
│   ├── acquisition + integrity
│   ├── scalar quantities
│   ├── geometry
│   ├── common-site waveforms
│   ├── evidence / validity / provenance
│   └── ScientificResult / Waveform / Cohort
│
├── Virtual Disease
│   ├── healthy reconstruction
│   ├── mechanistic transforms
│   ├── network solver
│   ├── optional JAX backend
│   ├── disease populations
│   └── parameterized cohorts / portable bundles
│
├── HEMOSPACE
│   ├── Virtual Cardiovascular Record
│   ├── source semantic normalization
│   ├── deterministic derivations
│   ├── plausibility reconstruction
│   ├── phenotype cohorts
│   ├── disease-response characterization
│   ├── knowledge closure
│   └── qualified lazy dense-path access
│
├── analysis
│   ├── native ScientificResult adapters
│   ├── subject/cohort alignment
│   ├── controlled external-data wrapping
│   └── analysis-result metadata
│
├── stats
│   └── qualified individual/cohort inference
│
├── mechanics
│   └── pressure-area / wave-mechanics derivations
│
├── spectral
│   └── frequency, wave, impedance, and time-frequency analysis
│
└── plot
    └── declarative publication-grade figures
```

## 3. Stable scientific domain

The stable scientific domain lives under `vascuquest.domain`. Its key value objects include:

- `DatasetIdentity` — exact source/dataset identity;
- `SubjectKey` — canonical subject identity within one dataset;
- `VirtualSubject` — identity-centric simulation instance;
- `Cohort` — deterministic ordered subject selection;
- `QuantityDefinition` — scientific quantity semantics and units;
- `MeasurementSite`, `SegmentLocation`, `PathPosition` — vascular location vocabulary;
- `ScientificResult` — storage-independent result with quantity, values, subject/cohort, location, evidence, validity, method, warnings, and provenance reference;
- `Waveform` — a time-resolved `ScientificResult` with explicit time coordinate.

These objects are the common language between source access and the v1 analysis layers. New post-processing code should extend behavior around these objects rather than add raw fields to `VirtualSubject`.

## 4. Evidence and provenance direction

The five evidence classes are:

- `SOURCE`;
- `RECONSTRUCTED`;
- `DERIVED`;
- `INFERRED`;
- `MODELLED`.

Evidence is not validity. A `MODELLED` output can be numerically valid within its declared model domain without being clinically validated. A `SOURCE` value can still carry a source warning.

Every non-source result identifies the producing method. Provenance must remain traceable to the source dataset/result context and must not be erased by statistics, mechanics, spectral analysis, or plotting.

## 5. Core PWDB layer

The core layer owns:

- canonical PWDB identity (`10.5281/zenodo.3275625`);
- artifact manifest/checksums;
- selective acquisition and registration;
- source readers;
- quantity/location semantics;
- common-site waveform access;
- source geometry;
- source/reconstructed result creation;
- JSON/CSV export;
- reproducibility behavior.

No v1 analytical package may modify these responsibilities.

## 6. HEMOSPACE layer

HEMOSPACE is a first-class operation mode, not a replacement backend. It consumes core PWDB access and produces a `VirtualCardiovascularRecord` for one virtual subject, plus cohort and response abstractions.

HEMOSPACE owns:

- semantic normalization of source tables;
- comprehensive source exposure;
- deterministic physiological derivations;
- explicit unavailable/unknowable categories;
- phenotype-driven cohorts;
- qualified dense-path reading;
- source-coverage and knowledge-closure accounting.

Its dense path reader is qualified against the authoritative PWDB exporter/storage contract. Path access remains lazy and optional through `h5py`.

## 7. Virtual Disease layer

Virtual Disease owns disease-state model construction and solving. It consumes healthy PWDB-derived baselines and produces separate disease dataset identities and `MODELLED` results.

The qualified presets are:

1. carotid stenosis;
2. iliac stenosis;
3. fusiform abdominal aortic aneurysm;
4. large-artery stiffening.

Post-processing layers must not alter disease geometry transforms, wall/network physics, boundary conditions, solver schemes, quantity-status rules, or qualification states.

## 8. Analysis contract

`vascuquest.analysis` is the integration seam for v1 research analytics. It provides:

- native conversion/validation of `ScientificResult` values;
- subject/cohort vector alignment;
- paired identity checking;
- time-coordinate checking;
- compatibility checking for dataset, subject, location, and units;
- controlled external-data admission.

Anonymous raw arrays are not canonical VascuQuest research objects. External data can enter only after explicit wrapping declares scientific quantity, coordinate, unit, identity/provenance context, and interpretation.

## 9. Statistics

`vascuquest.stats` is a strict qualified core, not a generic mirror of SciPy/statsmodels. Its methods are constrained by VascuQuest semantics.

Examples:

- paired healthy/disease results must be aligned by canonical subject ID;
- independent cohorts remain independent;
- cohort frequencies are not epidemiological prevalence;
- rank-deficient regression designs fail explicitly;
- method parameters and assumptions remain recordable.

## 10. Vascular mechanics

`vascuquest.mechanics` consumes existing aligned waveform/results. It does not solve fluid-solid interaction.

Local pressure-area operations require compatible subject, location, and time bases. No silent interpolation or location remapping is allowed.

## 11. Spectral and wave analysis

`vascuquest.spectral` consumes existing waveforms.

- FFT/PSD/impedance/time-frequency methods require explicit, uniformly sampled time coordinates where mathematically necessary.
- local pressure-flow impedance and wave separation require co-location;
- CSD/coherence/transfer operations may compare different arterial locations for the same subject if time coordinates are aligned;
- hidden resampling is forbidden.

## 12. Plotting

`vascuquest.plot` is a presentation layer over scientific results and declared transformations. It never becomes the authoritative source of scientific values.

The figure model is declarative:

```text
FigureSpec
├── PanelSpec
│   ├── LayerSpec
│   └── InsetSpec
└── LegendSpec
```

Large cohorts are not silently thinned. Rasterization may optimize rendering while retaining all observations. Any binning, density estimation, aggregation, confidence interval, or summary is an explicit scientific transformation.

Legends must remain outside the plotting region and collision-free with axes, labels, titles, insets, and neighboring panels.

## 13. CLI architecture

The CLI is a thin Typer adapter over the same scientific behavior exposed by Python APIs. Current first-class groups include core commands plus:

- `disease`;
- `hemospace`;
- `stats`;
- `mechanics`;
- `spectral`;
- `plot`.

CLI formatting must not change scientific behavior.

## 14. Dependency policy

Core VascuQuest remains lightweight: NumPy, platformdirs, and Typer.

Optional capabilities are isolated:

- `path` → h5py;
- `jax` → JAX;
- `research` → SciPy + PyWavelets;
- `plot` → Matplotlib;
- `all` → all optional runtime layers.

Optional packages must fail explicitly when a missing dependency is required; they must not degrade silently to a different method.

## 15. Architectural non-goals

VascuQuest 1.0 is not:

- a patient record system;
- a clinical decision-support system;
- an epidemiological database;
- a generic dataframe/statistics framework;
- a generic plotting wrapper;
- a three-dimensional CFD/FSI platform;
- a mechanism for inventing variables absent from PWDB.

## 16. Change rule

Any future feature that needs to alter core PWDB semantics, HEMOSPACE semantics, or qualified Virtual Disease physics is **not** a downstream v1 analysis extension. It requires a separately reviewed scientific change with its own validation gate.
