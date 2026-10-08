# Changelog

All notable release-facing changes to VascuQuest are recorded here.

## 1.0.0 — 2026-10-08

VascuQuest becomes an in-silico vascular research platform while preserving the validated PWDB core.

### Research-analysis foundation

- Added `vascuquest.analysis` as the common analysis contract over existing `ScientificResult` objects.
- Added an explicit external-data wrapper requiring dataset identity, quantity semantics, units and provenance.
- Analysis methods never mutate PWDB, HEMOSPACE or Virtual Disease state.

### Qualified statistics

- Added `vascuquest.stats` with descriptive statistics, empirical probabilities/quantiles, reproducible bootstrap and permutation inference, paired/independent tests, correlation/partial correlation, OLS/standardized/robust regression, ANOVA/ANCOVA, diagnostics and Benjamini-Hochberg correction.
- Paired analyses require identical canonical subject IDs in identical deterministic order.
- Cohort statistics retain the designed-virtual-population boundary and do not claim epidemiological prevalence.
- Added `vascuquest stats` CLI.

### Vascular mechanics

- Added `vascuquest.mechanics` for area and equivalent-diameter strain, area compliance, area distensibility, effective pressure-area slope, Peterson modulus, beta stiffness index, Bramwell-Hill wave speed and pressure-area loop integral.
- Pressure-area mechanics requires aligned local waveforms and performs no silent resampling.
- Added `vascuquest mechanics` CLI.

### Spectral and wave analysis

- Added `vascuquest.spectral` for harmonic amplitude/phase, PSD/entropy, coherence/CSD/transfer functions, pressure-flow impedance, characteristic-impedance estimates, wave separation/reflection, wave intensity, STFT, CWT and path-wise harmonic evolution.
- Frequency-domain methods require explicit native uniform sampling and fail rather than silently resample.
- Local pressure-flow methods require co-location; cross-site spectral relations still require the same subject and aligned time base.
- Wave separation requires explicit characteristic impedance; wave-intensity separation requires explicit wave speed.
- Added `vascuquest spectral` CLI.

### Publication-grade scientific visualization

- Added `vascuquest.plot` declarative figure specifications with panels, layers and insets.
- Supports line, step, scatter, histogram, heatmap, ECDF and hexbin layers.
- Large scatter layers may be rasterized for vector-output efficiency without dropping observations.
- Legends are always outside scientific axes; placement measures the rendered legend and checks collisions against normal and inset axes.
- Figure specifications can be serialized separately from rendered PDF/SVG/PNG output.
- Added `vascuquest plot` CLI.

### HEMOSPACE and Virtual Disease consolidated into v1

- HEMOSPACE provides Virtual Cardiovascular Records, cohort planning, physiological derivations, knowledge closure, disease-response characterization and qualified lazy path access.
- The HEMOSPACE dense-path reader is qualified as `QUALIFIED_AUTHORITATIVE_EXPORTER_CONTRACT`.
- Virtual Disease provides four mechanistic presets: carotid stenosis, iliac stenosis, fusiform abdominal-aortic aneurysm and large-artery stiffening.
- Existing qualified disease physics and evidence remain unchanged by the v1 analysis stack.
- Parameterized disease cohorts provide deterministic plan/generate/inspect/verify workflows over source-supported ages and explicit severity ranges.
- The scalar JAX disease-backend qualification remains bounded by `docs/evidence/JAX_SCALAR_QUALIFICATION.json`; current human-readable JAX and parameterized-cohort qualification documents are now separated correctly.

### Documentation consolidation

- Rebuilt the governing build, design, architecture, data-engineering, scientific-model, API/plugin, CLI and validation contracts around the actual v1.0 platform.
- Added a dedicated `ANALYSIS.md` contract and expanded statistics, vascular-mechanics, spectral/wave-analysis and plotting references with definitions, assumptions, failure conditions, CLI/API use and interpretation boundaries.
- Replaced obsolete staged-PR Virtual Disease documentation with present-tense reconstruction, physics, runtime, public-interface and cohort qualification references.
- Synchronized HEMOSPACE agent guidance, quantity ownership and endovascular protocols with the final `analysis → mechanics/spectral → stats → plot` research workflow.
- Clarified that frozen qualification labels such as `METRICS_ONLY_THRESHOLDS_NOT_FROZEN` belong to their recorded evidence lineage and must not be generalized into an “unfinished platform” claim.
- Upgraded parameterized-cohort/reconstruction documentation to distinguish current VascuQuest 1.0 capability from immutable revision-specific qualification evidence.
- Preserved `docs/history/**` and machine-readable qualification evidence as historical/immutable records rather than rewriting them to match current release prose.
- Added explicit documentation precedence and maintenance rules so future scientific/API changes must update their corresponding current documentation in the same development cycle.

### Release engineering

- Version advanced from 0.1.0 to 1.0.0.
- Core installation remains lightweight; research and plotting dependencies are optional extras.
- Added inexpensive analytical/synthetic tests for the new v1 layers; no full-network solver rerun or multi-gigabyte path download is required for their qualification.

## 0.1.0 — 2026-08-26

First public research-software release for the validated PWDB core scope: canonical dataset identity, 4,374 virtual subjects, scalar source quantities, geometry, common-site P/U/A/PPG waveforms, validated Q=U*A reconstruction, provenance-aware results, JSON/CSV export and strict reproduction.
