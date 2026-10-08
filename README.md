# VascuQuest

**In-silico vascular research platform for virtual cardiovascular populations.**

VascuQuest 1.0 is a Python package and CLI for provenance-aware cardiovascular research over the Pulse Wave DataBase (PWDB), qualified Virtual Disease models, and HEMOSPACE virtual cardiovascular records.

The canonical PWDB source remains Zenodo record `3275625` (DOI `10.5281/zenodo.3275625`). VascuQuest does not re-host or relicense PWDB.

## What v1.0 adds

VascuQuest began as a research-grade PWDB access layer. Version 1.0 retains that validated core and adds a complete in-silico research stack:

- **HEMOSPACE** — comprehensive, provenance-aware Virtual Cardiovascular Records; phenotype-driven cohorts; qualified lazy dense-path access; explicit knowledge closure.
- **Virtual Disease** — mechanistic carotid stenosis, iliac stenosis, fusiform abdominal-aortic aneurysm, and large-artery stiffening over preserved canonical virtual subjects.
- **Qualified statistics** — subject-aligned descriptive, inferential, correlation, bootstrap and regression operations.
- **Vascular mechanics** — pressure-area compliance, distensibility, strain, stiffness, Bramwell-Hill wave speed and pressure-area loop quantities.
- **Spectral and wave analysis** — harmonics, PSD, coherence, pressure-flow impedance, characteristic-impedance estimates, wave separation, wave intensity, STFT, CWT and path-wise harmonic evolution.
- **Scientific visualization** — declarative multi-panel figures, insets, large-cohort rendering and automatic collision-free exterior legends.

A VascuQuest `VirtualSubject` is a simulation instance, **not a patient**. Virtual Disease outputs are mechanistic `MODELLED` quantities, not clinical predictions.

## Scientific evidence remains explicit

Every scientific result is classified as one of:

- `SOURCE`
- `RECONSTRUCTED`
- `DERIVED`
- `INFERRED`
- `MODELLED`

Evidence status is separate from validity. Results retain dataset identity, quantity meaning, units, subject/cohort context, vascular location, method identity, warnings and provenance references.

## Core research workflow

```python
import vascuquest as vq

session = vq.open_dataset(source="/path/to/pwdb", offline=True)

# Existing PWDB / HEMOSPACE / Virtual Disease operations remain unchanged.
# New v1 analysis modules consume their ScientificResult objects directly:
summary = vq.stats.describe(result)
mechanics = vq.mechanics.area_distensibility(pressure_waveform, area_waveform)
harmonics = vq.spectral.harmonic_amplitude(pressure_waveform, n_harmonics=10)

figure = vq.plot.FigureSpec(
    panels=(
        vq.plot.PanelSpec(
            "A",
            layers=(vq.plot.LayerSpec("line", pressure_waveform, label="Pressure"),),
        ),
    )
)
vq.plot.render(figure, "figure.svg")
```

## CLI

The original dataset, disease and HEMOSPACE commands remain available. V1 adds:

```text
vascuquest stats ...
vascuquest mechanics ...
vascuquest spectral ...
vascuquest plot ...
```

Examples:

```bash
vascuquest stats describe result.json
vascuquest stats compare healthy.json disease.json --paired --method ttest
vascuquest mechanics compute area_distensibility area.json --pressure pressure.json
vascuquest spectral impedance pressure.json flow.json --harmonics 10
vascuquest plot series pressure.json flow.json --output figure.svg
```

The analysis CLI consumes native JSON documents previously exported by VascuQuest. It does not silently reinterpret arbitrary CSV columns as scientific quantities.

## Installation

Core installation remains lightweight:

```bash
python -m pip install .
```

Research analysis:

```bash
python -m pip install ".[research]"
```

Publication plotting:

```bash
python -m pip install ".[plot]"
```

Everything:

```bash
python -m pip install ".[all]"
```

Python 3.11–3.14 is supported.

## Architectural invariants

VascuQuest 1.0 follows one strict extension rule:

> New analysis functionality consumes existing VascuQuest scientific objects; it does not mutate the PWDB core, HEMOSPACE semantics, or qualified Virtual Disease physics.

Consequences:

- `VirtualSubject` remains identity-centric.
- HEMOSPACE remains the comprehensive phenotype/knowledge layer.
- Virtual Disease physics and qualification are not modified by analysis modules.
- Statistics never erase canonical subject alignment.
- Mechanics and spectral operations never silently resample waveforms.
- Plotting never becomes the scientific source of truth.
- Large-cohort rendering may rasterize graphics but never silently drop observations.
- Any aggregation, density estimation or transformation used for visualization is explicit in the figure specification.
- Legends are always outside scientific axes and are placed with collision checks against axes, labels, titles, insets and neighboring panels.

## Qualified v1 mechanics

The canonical pressure-area layer includes:

- area strain;
- equivalent-diameter strain;
- area compliance;
- area distensibility;
- cycle-wise pressure-area slope;
- Peterson modulus;
- beta stiffness index;
- Bramwell-Hill local wave-speed estimate;
- signed pressure-area loop integral.

These are **vascular mechanics**, not a claim that VascuQuest solves full fluid-structure interaction.

## Qualified v1 spectral/wave analysis

The canonical spectral layer includes:

- harmonic amplitude and phase;
- periodogram PSD;
- magnitude-squared coherence;
- pressure-flow input impedance;
- explicit-range characteristic-impedance estimates;
- pressure-flow wave separation with explicit `Zc`;
- net/forward/backward wave-intensity rate with explicit wave speed;
- STFT;
- continuous wavelet transform when PyWavelets is installed;
- path-wise harmonic evolution.

Native time coordinates must be uniformly sampled for spectral methods. VascuQuest fails rather than silently resampling.

## Validation philosophy

V1 analysis qualification is intentionally inexpensive. It relies on deterministic synthetic signals and analytical identities rather than rerunning the expensive disease solver or downloading multi-gigabyte source artifacts merely to test algebra:

- known statistical reference cases;
- manufactured pressure-area cycles;
- exact sinusoidal spectra and phases;
- known pressure-flow impedance;
- manufactured wave-intensity inputs;
- deterministic plotting geometry and legend-collision assertions.

The validated v0.1 PWDB core, HEMOSPACE path-reader contract qualification, and qualified Virtual Disease evidence remain separate upstream evidence chains.

## Documentation

- `docs/V1_RESEARCH_PLATFORM.md`
- `docs/STATS.md`
- `docs/VASCULAR_MECHANICS.md`
- `docs/SPECTRAL_ANALYSIS.md`
- `docs/PLOTTING.md`
- `docs/HEMOSPACE.md`
- `docs/VIRTUAL_DISEASE.md`

## Citation and licence

VascuQuest software is Apache-2.0 licensed. Cite VascuQuest with DOI `10.13140/RG.2.2.26784.96004` and cite PWDB separately whenever PWDB source data are used.
