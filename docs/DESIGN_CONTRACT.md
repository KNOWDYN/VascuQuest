# VascuQuest 1.0 design contract

## 1. Product identity

VascuQuest is an in-silico vascular research platform for virtual cardiovascular populations. It combines verified PWDB access, HEMOSPACE phenotype/knowledge records, mechanistic Virtual Disease, qualified research analysis, vascular mechanics, spectral/wave analysis, and reproducible scientific plotting.

The platform is designed for scientific research. It is not a clinical product.

## 2. Non-negotiable scientific identity rules

1. A VascuQuest `VirtualSubject` is a simulation instance, not a patient.
2. Subject identity is always scoped to an exact `DatasetIdentity`.
3. Different PWDB ages must not be silently interpreted as longitudinal measurements of one biological individual.
4. A cohort is an ordered deterministic selection of virtual subjects. It is not automatically a representative human population.
5. PWDB frequencies, proportions, and empirical probabilities describe the designed virtual population unless an external population model is explicitly introduced and validated.

## 3. Evidence classes

Every material result remains classifiable as one of:

- `SOURCE` — read from a supported canonical source representation;
- `RECONSTRUCTED` — exactly/deterministically reconstructed from aligned source quantities;
- `DERIVED` — calculated using a declared mathematical/physiological definition;
- `INFERRED` — obtained through a separately validated inference method;
- `MODELLED` — produced by an explicit model/operator.

Evidence class is independent of validity, admissibility, or clinical validation.

Non-source outputs must identify a producing method. No downstream operation may silently upgrade or downgrade evidence semantics.

## 4. Provenance contract

A scientific result must retain enough context to establish:

- dataset identity;
- canonical subject or cohort identity;
- quantity identity and unit;
- vascular location when applicable;
- dimensions and coordinates;
- method identity;
- evidence class;
- validity/warnings;
- provenance reference.

Downstream analysis may add provenance; it must not erase upstream provenance.

## 5. Source fidelity

VascuQuest must not silently:

- substitute common-site data for unavailable dense-path data;
- substitute one artery/location for another;
- interpolate missing path positions;
- resample waveforms without an explicit declared method;
- convert a model-space variable into a clinical measurement without validation;
- fill missing clinical attributes using assumptions;
- infer values from filenames or row positions when canonical identities are available.

## 6. Core PWDB boundary

The core owns source identity, manifest/checksum verification, source readers, stable quantity/location semantics, common-site waveforms, source geometry, `Q=U*A` reconstruction, provenance-aware result objects, export, and reproduction.

The v1 research layers are read-only consumers relative to this scientific boundary.

## 7. HEMOSPACE boundary

HEMOSPACE answers what is scientifically identifiable from supported PWDB source representations and defensible deterministic derivations.

Its stopping rule is:

> HEMOSPACE never asks “what else could we calculate?” It asks “what additional scientifically meaningful information is identifiable from these data?”

HEMOSPACE must explicitly report unavailable/unknowable categories rather than fabricate them. Examples include smoking history, genetics, renal function, medication history, symptoms, plaque composition, thrombotic state, longitudinal life history, and future event risk.

The path reader is qualified against the authoritative PWDB exporter/storage contract and canonical artifact identity. That qualification does not imply a fresh all-byte/all-subject scan of every large path artifact.

## 8. Virtual Disease boundary

Virtual Disease outputs remain `MODELLED`. The disease engine is mechanistic and research-facing, not clinically validated.

Qualified presets remain limited to the implemented model definitions:

- carotid stenosis;
- iliac stenosis;
- fusiform abdominal aortic aneurysm;
- large-artery stiffening.

The v1 analysis program must not modify disease transforms, solver equations, wall/network physics, boundary conditions, or persisted qualification semantics.

## 9. Common analysis contract

`vascuquest.analysis` is the canonical bridge between existing scientific results and v1 analytics.

Requirements:

- preserve dataset/subject/cohort/location identity;
- preserve coordinates and units;
- reject incompatible inputs explicitly;
- align paired data by canonical subject IDs;
- reject anonymous raw arrays from canonical workflows;
- permit external data only through an explicit wrapper that supplies scientific identity and provenance context.

## 10. Statistics design contract

`vascuquest.stats` is a qualified research layer, not an unrestricted statistics toolbox.

The v1 contract includes:

- descriptive statistics;
- confidence intervals;
- bootstrap inference;
- permutation tests;
- paired and independent comparisons;
- effect sizes;
- normality and variance diagnostics;
- correlation and partial correlation;
- ordinary and robust regression where qualified;
- ANOVA/ANCOVA;
- multiple-comparison correction;
- empirical exceedance probabilities.

Statistical operations must understand subject/cohort semantics. They must not infer pairing from row order. They must expose assumptions and fail on invalid designs such as rank-deficient regressions.

## 11. Mechanics design contract

The mechanics namespace is called **vascular mechanics**, not FSI.

It may derive quantities supported by aligned existing waveform/results, including area/diameter strain, compliance, distensibility, pressure-area slope, loop/hysteresis properties, Peterson-type modulus, beta stiffness, and qualified pressure-area wave-speed relations.

It must not claim:

- full fluid-solid interaction;
- three-dimensional wall stress/strain fields;
- plaque mechanics;
- patient-specific material properties;
- validated clinical stiffness indices beyond the implemented mathematical definitions.

## 12. Spectral design contract

Spectral methods must freeze and document:

- time-coordinate requirements;
- uniform-sampling requirements;
- DC/detrending conventions;
- FFT normalization;
- one-sided/two-sided representation;
- harmonic indexing;
- phase convention;
- pressure/flow units;
- impedance denominator guards;
- window/STFT parameters;
- wavelet definition and edge handling;
- wave-separation assumptions.

Local pressure-flow analysis requires co-located signals. Cross-site coherence/CSD/transfer may use different arterial locations for the same subject only when time bases are aligned.

No hidden interpolation/resampling is permitted.

## 13. Plotting design contract

Scientific plotting is declarative and reproducible.

A figure is composed from figure, panel, layer, inset, and legend specifications. The figure specification records the transformations needed to reproduce the visual result.

Hard invariants:

1. Legends must be outside the scientific plotting region.
2. Legend placement must avoid collision with axes, tick labels, axis labels, titles, insets, and neighboring panels.
3. Exterior legend distance should be compact—neither excessively far nor visually colliding.
4. Large cohorts must not be silently sampled/thinned.
5. Rasterization may reduce rendering cost but must not discard observations.
6. Binning, density estimation, quantiles, mean/CI, or any other aggregation must be explicit.
7. Plots are representations of scientific results, never the authoritative source of values.

## 14. Python/CLI parity

The CLI is an adapter over the same scientific contracts used by Python APIs. A CLI command may choose formatting and file destinations; it must not change scientific definitions, defaults, pairing, evidence, or provenance behavior.

Top-level v1 research groups are `disease`, `hemospace`, `stats`, `mechanics`, `spectral`, and `plot`, alongside the established core command surface.

## 15. Dependency and performance contract

Core runtime remains lightweight: NumPy, platformdirs, Typer.

Optional extras isolate heavier capabilities:

- `path`: h5py;
- `jax`: JAX;
- `research`: SciPy + PyWavelets;
- `plot`: Matplotlib;
- `all`: complete optional runtime.

No import should trigger source downloads, solver runs, or other expensive computations.

Post-processing qualification should use deterministic/manufactured reference cases whenever that is scientifically sufficient; full-network reruns are not a default release gate for analysis code.

## 16. Documentation contract

The root README and all files listed as governing in `docs/README.md` must describe the current release, not historical capability. Qualification certificates and `docs/history/**` are immutable records and may retain historical versions/dates by design.

Subsystem documentation must clearly distinguish implementation, qualification, assumptions, and non-claims.

## 17. Release claim

A VascuQuest 1.0 release may be described as an **in-silico vascular research platform** only while retaining the boundaries above. It must not be marketed as a clinical digital twin, diagnostic system, epidemiological population, or validated patient-specific simulator.
