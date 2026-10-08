# VascuQuest

**In-silico vascular research platform for virtual cardiovascular populations.**

VascuQuest 1.0 is a Python package and CLI for provenance-aware cardiovascular research over the Pulse Wave DataBase (PWDB), qualified Virtual Disease models, HEMOSPACE virtual cardiovascular records, and native statistical/mechanics/spectral/visualization workflows.

The canonical PWDB source remains Zenodo record `3275625` (DOI `10.5281/zenodo.3275625`). VascuQuest does not re-host or relicense PWDB.

## What v1.0 provides

VascuQuest began as a research-grade PWDB access layer. Version 1.0 retains that validated core and adds a complete in-silico research stack:

- **HEMOSPACE** — comprehensive, provenance-aware Virtual Cardiovascular Records; phenotype-driven cohorts; qualified lazy dense-path access; explicit knowledge closure.
- **Virtual Disease** — mechanistic carotid stenosis, iliac stenosis, fusiform abdominal-aortic aneurysm, and large-artery stiffening over preserved canonical virtual subjects.
- **Common analysis contract** — exact dataset/subject/cohort/location/time alignment and controlled external-data wrapping.
- **Qualified statistics** — subject-aligned descriptive/inferential analyses, bootstrap/permutation methods, correlation/partial correlation, regression, diagnostics, ANOVA/ANCOVA, multiplicity correction, and designed-cohort empirical probabilities.
- **Vascular mechanics** — pressure-area compliance, distensibility, strain, stiffness, Bramwell-Hill wave-speed estimate, and pressure-area loop quantities.
- **Spectral and wave analysis** — harmonics, PSD/CSD/coherence, transfer functions, pressure-flow impedance, characteristic-impedance estimates, wave separation, reflection magnitude, wave intensity, STFT, CWT, and path-wise harmonic evolution.
- **Scientific visualization** — declarative multi-panel figures, insets, large-cohort rendering, reproducible figure specs, and automatic collision-free exterior legends.

A VascuQuest `VirtualSubject` is a simulation instance, **not a patient**. Virtual Disease outputs are mechanistic `MODELLED` quantities, not clinical predictions.

## Scientific evidence remains explicit

Every scientific result is classified as one of:

- `SOURCE`
- `RECONSTRUCTED`
- `DERIVED`
- `INFERRED`
- `MODELLED`

Evidence status is separate from validity. Results retain dataset identity, quantity meaning, units, subject/cohort context, vascular location, method identity, warnings, and provenance references.

## Core research workflow

```python
import vascuquest as vq

session = vq.open_dataset(source="/path/to/pwdb", offline=True)

# Existing PWDB / HEMOSPACE / Virtual Disease operations remain available.
# New v1 analysis modules consume ScientificResult objects directly.
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

The canonical scientific flow is:

```text
PWDB / HEMOSPACE / persisted Virtual Disease / explicitly wrapped external result
        ↓
ScientificResult / Waveform
        ↓
identity + alignment checks
        ↓
mechanics / spectral derivations as required
        ↓
qualified statistics
        ↓
declarative publication figure
```

Downstream analysis never silently regenerates Virtual Disease state or changes upstream evidence semantics.

## CLI

The original dataset, disease, and HEMOSPACE commands remain available. V1 adds:

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
vascuquest mechanics compute area_distensibility area.json pressure.json
vascuquest spectral impedance pressure.json flow.json --harmonics 10
vascuquest plot series pressure.json flow.json --output figure.svg --spec-output figure-spec.json
```

The analysis CLI consumes native JSON documents exported by VascuQuest. It does not silently reinterpret arbitrary CSV columns as scientific quantities.

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

Dense HEMOSPACE paths:

```bash
python -m pip install ".[path]"
```

JAX backend:

```bash
python -m pip install ".[jax]"
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
- Virtual Disease remains the owner of disease-state generation and physics.
- Statistics never erase canonical subject alignment.
- Mechanics and spectral operations never silently resample waveforms.
- Plotting never becomes the scientific source of truth.
- Large-cohort rendering may rasterize graphics but never silently drop observations.
- Any aggregation, density estimation, or transformation used for visualization is explicit in the figure specification.
- Legends are always outside scientific axes and are placed with collision checks against axes, labels, titles, insets, and neighboring panels.

## Validation philosophy

V1 analysis qualification is intentionally inexpensive. It relies on deterministic/manufactured signals and analytical identities rather than rerunning the expensive disease solver or downloading multi-gigabyte source artifacts merely to test post-processing algebra:

- known statistical reference cases;
- manufactured pressure-area cycles;
- exact sinusoidal spectra and phases;
- known pressure-flow impedance;
- manufactured wave-intensity inputs;
- deterministic plotting geometry and legend-collision assertions.

The core PWDB real-source evidence, HEMOSPACE path-reader contract qualification, and Virtual Disease qualification remain separate upstream evidence chains.

## Documentation

The current VascuQuest 1.0 documentation has been synchronized against the integrated release candidate. Start at [`docs/README.md`](docs/README.md), which defines documentation precedence and distinguishes current contracts from frozen qualification/history records.

Key references:

- [`docs/V1_RESEARCH_PLATFORM.md`](docs/V1_RESEARCH_PLATFORM.md)
- [`docs/ANALYSIS.md`](docs/ANALYSIS.md)
- [`docs/STATS.md`](docs/STATS.md)
- [`docs/VASCULAR_MECHANICS.md`](docs/VASCULAR_MECHANICS.md)
- [`docs/SPECTRAL_ANALYSIS.md`](docs/SPECTRAL_ANALYSIS.md)
- [`docs/PLOTTING.md`](docs/PLOTTING.md)
- [`docs/HEMOSPACE.md`](docs/HEMOSPACE.md)
- [`docs/HEMOSPACE_AGENT.md`](docs/HEMOSPACE_AGENT.md)
- [`docs/HEMOSPACE_ENDOVASCULAR_PROTOCOLS.md`](docs/HEMOSPACE_ENDOVASCULAR_PROTOCOLS.md)
- [`docs/VIRTUAL_DISEASE.md`](docs/VIRTUAL_DISEASE.md)
- [`docs/VIRTUAL_DISEASE_COHORTS.md`](docs/VIRTUAL_DISEASE_COHORTS.md)
- [`docs/TEST_VALIDATION_CONTRACT.md`](docs/TEST_VALIDATION_CONTRACT.md)

Frozen qualification labels are retained where they belong to historical evidence lineage; they must not be generalized into unrelated claims about the current v1.0 platform.

## Citation and licence

VascuQuest software is Apache-2.0 licensed. Cite VascuQuest with DOI `10.13140/RG.2.2.26784.96004` and cite PWDB separately whenever PWDB source data are used.
