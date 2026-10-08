# VascuQuest 1.0 in-silico research platform

## 1. What changed from 0.1

VascuQuest 0.1 was primarily a rigorously validated scientific access layer over PWDB. VascuQuest 1.0 preserves that core and adds a complete research workflow around it.

The v1 platform can now support this chain:

```text
canonical PWDB source
        ↓
HEMOSPACE phenotype / Virtual Cardiovascular Record
        ↓
cohort selection
        ↓
Virtual Disease counterfactual generation
        ↓
mechanics + spectral/wave characterization
        ↓
qualified statistical inference
        ↓
declarative publication figure
        ↓
reproducible scientific outputs
```

The architectural rule throughout the chain is that downstream analytics consume scientific objects; they do not mutate PWDB, HEMOSPACE, or qualified Virtual Disease physics.

## 2. Installation

Core:

```text
pip install vascuquest
```

Research analysis stack:

```text
pip install "vascuquest[research]"
```

Plotting:

```text
pip install "vascuquest[plot]"
```

Dense HEMOSPACE path access:

```text
pip install "vascuquest[path]"
```

JAX disease backend:

```text
pip install "vascuquest[jax]"
```

All optional runtime capabilities:

```text
pip install "vascuquest[all]"
```

The core package remains lightweight and importing it does not download PWDB or execute simulations.

## 3. Core PWDB access

```python
from pathlib import Path
import vascuquest as vq

session = vq.open_dataset(source=Path("/path/to/pwdb"), offline=True)

age = session.get("age", subjects="1")
pressure = session.waveform(
    "pressure",
    subject="1",
    location=vq.MeasurementSite("AorticRoot"),
)
```

VascuQuest preserves canonical PWDB identity, source semantics, units, evidence, and provenance.

## 4. HEMOSPACE phenotype

```python
from vascuquest.hemospace import open_hemospace

hs = open_hemospace(source="/path/to/pwdb", offline=True)
record = hs.record("2104", depth="comprehensive")
```

The `VirtualCardiovascularRecord` exposes source and defensible derived cardiovascular knowledge for one simulation instance.

Possible uses include:

- baseline phenotype characterization;
- model-design/generative context;
- waveform summaries;
- haemodynamic/geometry summaries;
- local/path physiology;
- explicit knowability/coverage auditing.

## 5. HEMOSPACE dense paths

```python
path = hs.path("2104", "aorta_brain")
```

Supported path families are:

```text
aorta_brain
aorta_finger
aorta_foot
aorta_r_subclavian
```

The reader is lazy and `h5py`-based. Qualification status is `QUALIFIED_AUTHORITATIVE_EXPORTER_CONTRACT`.

This means the reader/storage contract is qualified against the authoritative PWDB exporter and exact MATLAB-v7.3/HDF5 representation. It does not mean every path file is read in full during ordinary use.

## 6. HEMOSPACE cohorts

HEMOSPACE can select deterministic phenotype-driven virtual cohorts using canonical scalar criteria and optional trial profiles.

The cohort records:

- canonical subject IDs;
- normalized criteria;
- profile identity;
- deterministic selection ID;
- designed-population interpretation.

These are research cohorts inside the PWDB design space, not human prevalence samples.

## 7. Virtual Disease

VascuQuest 1.0 includes four qualified mechanistic presets:

1. carotid stenosis;
2. iliac stenosis;
3. fusiform abdominal aortic aneurysm;
4. large-artery stiffening.

Disease outputs are separate `MODELLED` scientific results.

A typical disease study preserves the source subject identity while creating a separate disease dataset identity and result bundle.

The correct interpretation is a modelled counterfactual vascular response, not a diagnosis or clinical treatment effect.

## 8. Common analysis contract

Before analysis, results pass through the semantics in [`ANALYSIS.md`](ANALYSIS.md).

This contract provides:

- exact dataset matching;
- same-subject checks;
- same-location checks where required;
- waveform time alignment;
- canonical cohort subject alignment;
- paired healthy/disease identity checking;
- deterministic analysis provenance references;
- explicit external-data wrapping.

This is what allows individual and cohort analyses to share the same scientific meaning.

## 9. Vascular mechanics

Example:

```python
from vascuquest.mechanics import area_distensibility, bramwell_hill_wave_speed

dist = area_distensibility(pressure, area)
c = bramwell_hill_wave_speed(pressure, area)
```

Available v1 mechanics metrics include:

- area strain;
- equivalent-diameter strain;
- area compliance;
- area distensibility;
- pressure-area slope;
- Peterson modulus;
- beta stiffness index;
- Bramwell-Hill wave-speed estimate;
- pressure-area loop integral.

These are derived pressure-area mechanics, not a coupled FSI solution.

## 10. Spectral and wave analysis

Example:

```python
from vascuquest.spectral import (
    harmonic_amplitude,
    impedance,
    characteristic_impedance,
)

harmonics = harmonic_amplitude(pressure, n_harmonics=10)
z_mag, z_phase = impedance(pressure, flow, n_harmonics=10)
zc = characteristic_impedance(pressure, flow)
```

The v1 spectral layer additionally provides PSD, CSD, coherence, transfer functions, reflection magnitude, wave separation, wave intensity, spectral entropy, harmonic-energy ratios, STFT, CWT, and path-wise harmonic evolution.

No hidden waveform resampling occurs.

## 11. Qualified statistics

Example paired model-response analysis:

```python
from vascuquest.stats import paired_compare

comparison = paired_compare(healthy_endpoint, disease_endpoint)
```

The pairing is validated from canonical cohort subject IDs, not row order.

Other qualified methods include bootstrap/permutation inference, independent comparisons, effect-size methods, diagnostics, correlation/partial correlation, OLS/robust regression, ANOVA/ANCOVA, p-value adjustment, quantiles, and empirical exceedance fractions.

## 12. Publication figures

Example single panel:

```python
from vascuquest.plot import FigureSpec, LayerSpec, PanelSpec, render, write_spec

spec = FigureSpec(
    panels=(
        PanelSpec(
            "A",
            layers=(
                LayerSpec("line", pressure, label="Aortic pressure"),
            ),
            xlabel="Time",
            ylabel="Pressure",
        ),
    )
)

render(spec, "figure.svg")
write_spec(spec, "figure-spec.json")
```

A compound paper figure can contain many panels and insets and combine waveform, mechanics, spectral, and cohort-analysis results.

All legends are placed outside the scientific plotting region and collision-checked against plot geometry.

## 13. Example: phenotype-dependent carotid-stenosis study

A research question:

> Which baseline cardiovascular phenotypes magnify or attenuate the haemodynamic response to an identical modelled carotid stenosis?

A v1 workflow:

```text
1. Open canonical PWDB
2. Build HEMOSPACE records / select phenotype cohort
3. Generate or load qualified carotid-stenosis disease population
4. Extract matched healthy and modelled disease endpoints
5. Compute mechanics/spectral descriptors as required
6. Align healthy/disease subjects canonically
7. Run paired statistics / effect-modifier regression
8. Build publication figure from the resulting ScientificResult objects
9. Export result JSON + figure-spec JSON + figure
```

The scientific conclusion must remain within the mechanistic/modelled domain.

## 14. Example: large-artery stiffness study

Possible workflow:

```text
baseline P(t), A(t)
      ↓
local area distensibility / beta stiffness / BH wave speed
      ↓
modelled large-artery stiffening
      ↓
recomputed disease P(t), A(t)
      ↓
paired change in mechanics
      ↓
pressure-flow impedance / wave-intensity changes
      ↓
cohort effect-modifier analysis
```

This allows a study to connect baseline phenotype, mechanical state, wave behavior, and controlled model response without rerunning unrelated expensive computations.

## 15. Example: dense-path arterial wave research

HEMOSPACE path signals can support:

- path-wise pressure/flow/area evolution;
- local Q reconstruction;
- onset-distance PWV regression;
- pressure pulse amplification;
- path-wise spectral harmonic evolution;
- local mechanics where aligned P/A waveforms exist.

Only stored source-supported path positions are used. VascuQuest does not silently interpolate a continuous field from unstored positions.

## 16. Native result exchange

VascuQuest's portable JSON exporter preserves scientific result metadata and is the preferred file boundary for the new analysis CLI groups.

This lets a workflow separate steps cleanly:

```text
simulation/source step
    ↓ JSON result
analysis step
    ↓ JSON result
plot step
    ↓ SVG/PDF/PNG + FigureSpec JSON
```

CSV remains available where tabular exchange is appropriate, with metadata sidecars as required by the existing exporter contract.

## 17. CLI workflow

The v1 command tree now includes:

```text
vascuquest disease
vascuquest hemospace
vascuquest stats
vascuquest mechanics
vascuquest spectral
vascuquest plot
```

Examples:

```text
vascuquest stats compare healthy.json disease.json --paired
vascuquest mechanics compute area_distensibility area.json pressure.json
vascuquest spectral impedance pressure.json flow.json --harmonics 10
vascuquest plot series aortic.json carotid.json --output waves.svg --spec-output waves.json
```

See [`CLI_CONTRACT.md`](CLI_CONTRACT.md) for the exact current command surface.

## 18. Reproducibility bundle concept

A complete v1 research record should retain, as applicable:

- source dataset identity/checksum information;
- cohort selection ID and criteria;
- disease request/execution/bundle identity;
- native scientific result JSON;
- analysis method IDs/parameters/seeds;
- mechanics/spectral assumptions;
- warnings/validity states;
- figure-spec JSON;
- rendered figure;
- VascuQuest version;
- citations for VascuQuest, PWDB, and method literature.

## 19. Computational-cost philosophy

The platform separates **generation** from **analysis**.

Generating new disease populations can be computationally expensive. Once results exist, statistics, mechanics, spectral transforms, and plotting are inexpensive post-processing and must not trigger solver reruns.

Qualification follows the same principle: manufactured signals with known answers are preferred over expensive full-population computation when they directly test the mathematical method.

## 20. External data

VascuQuest 1.0 can accept external research data through `vascuquest.analysis.wrap_external(...)` when the caller explicitly supplies dataset identity, quantity, unit, coordinates, provenance, and subject/cohort/location context as applicable.

This enables comparison/extension workflows without pretending external observations are native PWDB source data.

## 21. Scientific boundaries

VascuQuest 1.0 does not claim:

- patient digital twins;
- clinical diagnosis/prognosis;
- treatment recommendations;
- epidemiological representativeness;
- recovery of absent clinical variables from PWDB;
- patient-specific wall material properties;
- three-dimensional CFD/FSI;
- plaque/ILT/rupture/thrombotic modeling unless explicitly introduced by a separately validated future model.

## 22. Documentation map

Start with:

- [`README.md`](README.md) — documentation index;
- [`ANALYSIS.md`](ANALYSIS.md) — common analysis semantics;
- [`STATS.md`](STATS.md) — statistical research layer;
- [`VASCULAR_MECHANICS.md`](VASCULAR_MECHANICS.md) — pressure-area mechanics;
- [`SPECTRAL_ANALYSIS.md`](SPECTRAL_ANALYSIS.md) — arterial spectral/wave analysis;
- [`PLOTTING.md`](PLOTTING.md) — scientific figure engine;
- [`HEMOSPACE.md`](HEMOSPACE.md) — phenotype/knowledge operation mode;
- [`VIRTUAL_DISEASE.md`](VIRTUAL_DISEASE.md) — mechanistic counterfactual disease platform.

VascuQuest 1.0 should be understood as one integrated research platform whose layers remain epistemically separated and provenance connected.
