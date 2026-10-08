# VascuQuest 1.0 Python API and extension contract

## 1. Purpose

This document defines the stable public Python surface and extension boundaries for VascuQuest 1.0.

The core rule is:

> Extensions may consume or add behavior around VascuQuest scientific objects, but they must not silently alter canonical PWDB semantics, HEMOSPACE semantics, qualified Virtual Disease physics, evidence classes, or provenance rules.

## 2. Public package surface

The package-level API exposes the established core objects/services plus the v1 research namespaces:

```python
import vascuquest as vq

vq.open_dataset(...)
vq.register_source(...)

vq.disease
vq.hemospace
vq.analysis
vq.stats
vq.mechanics
vq.spectral
vq.plot
vq.plugins
```

Core public scientific objects include:

- `DatasetSession`;
- `DatasetIdentity`;
- `SubjectKey`;
- `VirtualSubject`;
- `Cohort`;
- `QuantityDefinition`;
- `ScientificResult`;
- `Waveform`;
- `Coordinate`;
- `MeasurementSite`;
- `SegmentLocation`;
- `PathPosition`;
- `EvidenceClass`;
- `ProvenanceRecord`.

## 3. Core session contract

`open_dataset(...)` returns a `DatasetSession` over a trusted registered/acquired source. The session is responsible for supported source reads/derivations; importing the package or constructing the session must not automatically download the entire dataset or execute expensive simulations.

Core operations retain explicit source identity, quantity identity, units, evidence, location, and provenance.

## 4. Scientific result contract

All first-party research methods should accept/return `ScientificResult`, `Waveform`, or explicit result-like domain objects where practical.

A result must preserve:

- dataset identity;
- quantity identity and unit;
- subject/cohort context;
- vascular location where applicable;
- dimensions/coordinates;
- evidence class;
- availability/validity state;
- warnings;
- method identity;
- provenance reference.

Downstream packages may add method metadata but may not erase upstream scientific context.

## 5. HEMOSPACE API

Primary entry:

```python
from vascuquest.hemospace import open_hemospace

hs = open_hemospace(source="/path/to/pwdb", offline=True)
record = hs.record("2104", depth="comprehensive")
cohort = hs.select_cohort([...])
path = hs.path("2104", "aorta_brain")
```

HEMOSPACE returns provenance-aware virtual cardiovascular knowledge and cohort/path products. The path API is lazy and requires the optional `path` extra (`h5py`).

## 6. Virtual Disease API

The `vascuquest.disease` namespace owns disease specification, generation, runtime populations, cohort planning/execution, and bundle behavior.

Disease results are `MODELLED`. Analysis packages may compare/analyze them, but must not modify the disease solver or silently reinterpret modelled output as clinical observation.

## 7. Analysis API

`vascuquest.analysis` is the canonical v1 integration layer for analytical consumers.

It provides result/value extraction, identity/alignment checks, time-coordinate checks, compatibility checks, and controlled external-data wrapping.

### External data rule

A raw external array is not automatically a VascuQuest scientific object. External data must be wrapped with explicit scientific context before canonical analysis. The wrapper must declare enough information to determine quantity, unit, coordinates, identity, and provenance/interpretation.

This prevents generic arrays from bypassing VascuQuest's scientific contracts.

## 8. Statistics API

`vascuquest.stats` exposes a **qualified core**, not all possible functions from SciPy/statsmodels.

First-party categories include:

- descriptive statistics and intervals;
- bootstrap and permutation methods;
- paired/independent comparisons;
- effect sizes;
- normality/variance diagnostics;
- correlation/partial correlation;
- OLS/robust regression;
- ANOVA/ANCOVA;
- multiplicity correction;
- empirical exceedance probability.

Methods must preserve or explicitly validate subject/cohort alignment. Paired APIs may not pair observations by row position when canonical subject IDs exist.

Future statistical methods should be added through the same qualified method contract rather than exposing an unbounded generic function passthrough.

## 9. Mechanics API

`vascuquest.mechanics` consumes aligned VascuQuest waveform/results and returns derived vascular-mechanics descriptors.

The API must enforce the location/time compatibility required by the definition. It must not silently interpolate or call the Virtual Disease solver.

The namespace is intentionally `mechanics`, not `fsi`.

## 10. Spectral API

`vascuquest.spectral` exposes:

- harmonics/Fourier transforms;
- PSD/CSD;
- coherence;
- transfer functions;
- pressure-flow impedance;
- characteristic-impedance descriptors;
- wave separation/intensity;
- STFT;
- wavelet analysis.

Frequency-domain operations requiring uniform sampling must validate it. Local haemodynamic relations enforce co-location. Cross-site spectral relationships may use distinct locations for the same subject only when their time bases align.

## 11. Plot API

`vascuquest.plot` is declarative. Figure construction uses specification objects describing panels, layers, insets, and legends rather than storing scientific meaning only in imperative plotting calls.

The renderer must preserve the no-silent-downsampling and exterior-collision-free-legend contracts documented in `PLOTTING.md`.

Exports may include SVG, PDF, PNG, and a serializable figure specification.

## 12. Plugin model

The established plugin system remains available for explicit extension categories such as backends, derivations, research operators, discovery methods, and exporters.

A plugin descriptor must identify:

- component kind;
- qualified ID;
- implementation/protocol versions;
- distribution identity/version;
- human summary;
- required inputs/parameters where applicable;
- output semantics;
- validation scope/citations where applicable.

Plugins must fail explicitly if incompatible with the supported protocol or if a required capability is unavailable.

## 13. Extension rules

An extension must not:

- replace one vascular location with another without an explicit method;
- erase subject/cohort identity;
- reclassify evidence silently;
- remove units/coordinates/provenance;
- infer missing clinical information;
- perform automatic network simulation as a side effect of a post-processing call;
- reinterpret designed PWDB cohorts as epidemiological samples.

An extension that changes upstream disease physics or source semantics requires a dedicated scientific review/qualification; it is not a normal analytics plugin.

## 14. Method identity

Every non-source result requires a method identity. First-party methods should use stable qualified method IDs where persistence/reproduction matters.

Method parameters affecting scientific results must be serializable or otherwise explicitly recordable. Randomized methods must accept/control a random seed/state when reproducibility is expected.

## 15. Error behavior

Public API errors must be explicit and domain-relevant. Existing VascuQuest exception classes remain the stable application error vocabulary, including capability, integrity, schema, unit, selection, admissibility, numerical-method, plugin, and reproducibility errors.

A missing optional dependency should result in an explicit capability error or import guidance for that capability, not an unannounced fallback to a different scientific method.

## 16. API/CLI parity

The Python API is the scientific source of behavior; the CLI is an adapter. CLI commands should map to the same method definitions/defaults/validation rules.

Machine-readable CLI output must remain clean on stdout while operational diagnostics/errors use stderr according to the existing contract.

## 17. Versioning

VascuQuest 1.0 identifies the integrated research-platform API surface. Future incompatible changes to stable scientific contracts require a major-version decision; additive qualified methods may be introduced compatibly if they preserve existing semantics.

## 18. Non-goals

The public API does not promise:

- arbitrary dataframe compatibility without wrapping;
- unrestricted generic statistics/plotting passthrough;
- clinical decision support;
- patient-specific digital twins;
- unqualified third-party science merely because it conforms syntactically to a plugin protocol.
