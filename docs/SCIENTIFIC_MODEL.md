# VascuQuest 1.0 scientific model

## 1. Scientific object of the platform

VascuQuest operates on **virtual cardiovascular simulation instances**. A `VirtualSubject` is not a patient, not a clinical record, and not a longitudinal biological individual.

The platform combines source data, deterministic reconstructions, derived quantities, explicit inference methods, and mechanistic models while preserving the distinction between them.

## 2. Dataset identity

Every subject/result belongs to an exact `DatasetIdentity`. Dataset identity is independent of local path, cache location, filename, or runtime object identity.

For canonical PWDB source data:

- dataset family: PWDB;
- canonical record: Zenodo `3275625`;
- persistent identifier: `10.5281/zenodo.3275625`.

Virtual Disease populations carry their own modelled dataset identity and must not be confused with the source PWDB dataset.

## 3. Subject and cohort semantics

A `SubjectKey` identifies one canonical simulation instance within one dataset identity.

A `Cohort` is an ordered, reproducible selection of canonical subject IDs plus its normalized selection metadata. Cohort order is explicit and reproducible; row order is not a substitute for identity.

HEMOSPACE also defines `HemospaceCohort` selections and stable `selection_id` values for phenotype-driven studies. These remain designed virtual populations, not epidemiological samples.

## 4. Evidence model

VascuQuest uses five evidence classes:

### `SOURCE`

Read from a supported canonical source representation without scientific transformation beyond decoding/unit normalization that is part of the source contract.

### `RECONSTRUCTED`

Deterministically recovered from aligned source quantities or authoritative source-generation logic. Example: `Q = U*A` from aligned source velocity and area waveforms.

### `DERIVED`

Calculated using a declared mathematical or physiological definition from available quantities. Examples include compliance, distensibility, spectral harmonics, hydraulic power, and statistical summaries.

### `INFERRED`

Produced by a separately identified inference method whose validity must be established for its declared domain.

### `MODELLED`

Produced by an explicit simulation/model operator. Virtual Disease outputs are `MODELLED`.

Evidence does not itself imply correctness, clinical validity, or representativeness.

## 5. Validity and availability

`ScientificResult` separates evidence from availability/validity.

Availability states include present, missing, unavailable, and not applicable. Validity states distinguish valid, valid-with-warning, out-of-domain, invalid input, numerical failure, and not evaluated.

This separation prevents statements such as “SOURCE therefore clinically valid” or “MODELLED therefore invalid.”

## 6. Quantity definitions

A `QuantityDefinition` describes scientific meaning independently of the observed value. It carries:

- canonical name;
- human label;
- description;
- value kind;
- schema version;
- physical dimension;
- canonical unit;
- allowed source units;
- applicable contexts;
- aliases;
- default evidence;
- known source issues;
- citations.

Derived/analysis quantities should use equally explicit definitions or result-level metadata so units and meaning are not lost.

## 7. Locations

VascuQuest distinguishes:

- `MeasurementSite` — canonical named measurement site;
- `SegmentLocation` — canonical arterial segment;
- `PathPosition` — one source-supported indexed position along a canonical arterial path.

A `PathPosition` identifies a stored/supportable position; it does not imply interpolation between positions.

## 8. ScientificResult

`ScientificResult` is the central storage-independent result contract. It couples values to:

- dataset identity;
- quantity definition;
- dimensions;
- coordinate values;
- source unit/label;
- subject and/or cohort context;
- vascular location;
- evidence class;
- availability state;
- validity state;
- warnings;
- method ID;
- provenance reference.

The v1 analysis layers use this existing contract rather than create parallel anonymous data models.

## 9. Waveform

`Waveform` extends `ScientificResult` with a mandatory explicit time coordinate and subject/location context.

Methods using multiple waveforms must verify the relationships they require:

- same subject where a paired local physiological relation is assumed;
- same location where a co-located pressure-flow/pressure-area relation is assumed;
- aligned time coordinates for simultaneous analysis;
- uniform sampling where required by the spectral method.

## 10. Core PWDB quantities

Core VascuQuest exposes source-supported:

- model configuration/design quantities;
- model variation quantities;
- haemodynamic parameters;
- pulse-wave indices;
- onset/fiducial timings;
- vascular geometry;
- common-site P/U/A/PPG waveforms;
- deterministic `Q = U*A` reconstruction.

The source does not become a clinical patient phenotype merely because the variables resemble clinical measurements.

## 11. HEMOSPACE scientific model

HEMOSPACE produces a `VirtualCardiovascularRecord` for one virtual subject. The record contains atomic `KnowledgeItem` entries with explicit evidence, source artifact/field, location, method, assumptions, and notes.

HEMOSPACE has three principal depth concepts:

- scalar;
- geometry;
- comprehensive.

It also records knowledge coverage and explicit `NOT_KNOWABLE_FROM_PWDB` information.

Examples of information that must not be invented include smoking, genetics, renal function, medication history, symptoms, plaque composition, thrombotic state, longitudinal life history, and future clinical event risk.

The model-population sex assumption can be exposed only with its actual source meaning; it is not an observed patient sex.

## 12. HEMOSPACE derivations

HEMOSPACE can produce defensible deterministic derivations such as:

- cycle duration;
- cardiac output consistency calculations;
- pulse pressure;
- pressure/flow/area waveform summaries;
- velocity/flow pulsatility and resistance descriptors;
- area strain/compliance/distensibility;
- forward/reverse/net cycle volumes;
- reverse-flow fraction;
- hydraulic power/energy;
- pressure-flow impedance harmonics;
- path PWV regression and fit quality where onset/distance data support it.

The mere mathematical calculability of a quantity does not automatically make it scientifically meaningful or part of HEMOSPACE.

## 13. Virtual Disease scientific model

Virtual Disease creates controlled mechanistic counterfactuals from healthy virtual subjects. Its outputs remain `MODELLED`.

The currently qualified presets are:

- carotid stenosis;
- iliac stenosis;
- fusiform abdominal aortic aneurysm;
- large-artery stiffening.

A disease population is a designed counterfactual population. It is not a clinical treatment cohort or epidemiological disease population.

## 14. Healthy vs disease pairing

When the same canonical source subject underlies healthy and disease results, the analysis relation is paired by identity. Statistical comparisons must preserve this pairing and may not infer it from row position.

The appropriate interpretation is a **paired counterfactual model response**, not a clinical treatment effect.

## 15. Analysis scientific model

`vascuquest.analysis` creates the common semantic bridge from scientific results to analytical operations.

An analytical input retains:

- values;
- quantity/units;
- subject/cohort identities;
- location;
- coordinates;
- evidence and validity;
- method/provenance context.

Controlled external data can be wrapped into this model only after its scientific identity is explicitly declared.

## 16. Statistical semantics

`vascuquest.stats` is designed around VascuQuest identity/experiment semantics.

Qualified operations include descriptive summaries, confidence intervals, bootstrap/permutation inference, paired/independent tests, effect sizes, diagnostics, correlation/partial correlation, regression, ANOVA/ANCOVA, FDR correction, and empirical exceedance probability.

Important interpretation rules:

- paired healthy/disease data are paired by canonical subject ID;
- selected cohorts are not automatically random human samples;
- empirical probabilities are probabilities within the represented virtual design, not population risk estimates;
- regression association is not causal inference unless the experimental design supplies that interpretation;
- p-values do not transform modelled outputs into clinically validated outcomes.

## 17. Vascular mechanics semantics

`vascuquest.mechanics` operates on existing aligned pressure/area waveforms and returns `DERIVED` quantities.

The namespace is not FSI. Quantities such as compliance, distensibility, stiffness indices, loop area, and qualified pressure-area wave speed are local mathematical/physiological descriptors under declared assumptions.

No three-dimensional stress field, wall shear stress, plaque mechanics, or patient-specific material property is implied.

## 18. Spectral and wave semantics

`vascuquest.spectral` treats frequency/wave outputs as derived representations of existing waveforms.

- Fourier coefficients/harmonics depend on declared normalization and phase convention;
- PSD/CSD/coherence depend on sampling and window definitions;
- pressure-flow impedance requires pressure and flow at a common location;
- wave separation/intensity requires declared characteristic/wave-speed assumptions;
- cross-site transfer/coherence describes signal relationships, not necessarily causal transmission;
- time-frequency outputs depend on explicit STFT/wavelet parameters.

No hidden interpolation or resampling is permitted.

## 19. Plot semantics

A scientific figure is a reproducible representation of scientific results and explicit transformations. A plot never becomes the authoritative data source.

For large cohorts, plotting may change rendering strategy (for example rasterizing a layer) without changing the observations. Aggregation, binning, KDE/density, quantiles, or confidence intervals are scientific transformations and therefore must be explicit.

## 20. Units and dimensions

Units are part of scientific meaning. Operations must either require compatible canonical units or perform explicit documented conversions.

Dimensionless quantities use explicit unit `1` where appropriate rather than absence of unit metadata.

## 21. Numerical conventions

Numerical operations must reject invalid/non-finite values where the method requires finite input. Methods requiring uniform sampling must verify it. Regression designs must reject rank deficiency. Divisions such as impedance must guard denominators according to the method contract rather than produce silent infinities.

## 22. Scope boundaries

VascuQuest 1.0 does not convert PWDB into a human clinical dataset. It does not support claims of diagnosis, prognosis, future event risk, treatment efficacy, epidemiological prevalence, patient-specific rupture risk, or other clinical endpoints without separate validated evidence.

The platform’s scientific strength is explicit separation of what is sourced, reconstructed, derived, inferred, and modelled.
