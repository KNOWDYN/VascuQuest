# VascuQuest

**Scientific exploration and discovery for virtual vascular populations.**

[![Core CI](https://github.com/KNOWDYN/VascuQuest/actions/workflows/ci.yml/badge.svg)](https://github.com/KNOWDYN/VascuQuest/actions/workflows/ci.yml)
[![Python 3.11–3.14](https://img.shields.io/badge/Python-3.11%E2%80%933.14-blue.svg)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-green.svg)](LICENSE)
[![Version: 0.1.0](https://img.shields.io/badge/version-0.1.0-blue.svg)](CHANGELOG.md)
[![PWDB source DOI](https://img.shields.io/badge/PWDB-10.5281%2Fzenodo.3275625-blue.svg)](https://doi.org/10.5281/zenodo.3275625)

VascuQuest is a Python package and command-line interface for **research-grade access to the Pulse Wave DataBase (PWDB)**. The canonical PWDB Zenodo record [`3275625`](https://zenodo.org/records/3275625) remains the upstream source of truth; VascuQuest provides a verified scientific interface around it.

VascuQuest does **not** replace, re-host or silently modify PWDB. It adds explicit dataset identity, selective checksum-verified acquisition, stable quantity and location semantics, evidence classes, provenance, reproducible exports, and matching Python/CLI application flows.

> **Validated 0.1.0 scope:** scalar subject quantities, source-supported vascular geometry, common-site waveforms, validated volumetric-flow reconstruction, JSON/CSV export, provenance-aware reproduction and plugin inspection. Dense path-resolved waveforms are deliberately outside the 0.1.0 public capability set.

## Why VascuQuest?

PWDB contains 4,374 virtual haemodynamic simulation instances distributed across heterogeneous canonical files. A researcher who works directly with those files must otherwise solve source identification, acquisition, checksums, field naming, units, waveform locations, evidence status, provenance and reproducibility independently.

VascuQuest turns the supported PWDB scope into one scientific interface while preserving the distinction between **source data** and **computed results**.

Typical questions include:

- Which virtual subjects satisfy a physiological or model condition?
- Which canonical quantities are available for a subject or cohort?
- What source waveform is available at a named vascular measurement site?
- What geometry is associated with a virtual subject?
- Was a result read from PWDB, reconstructed, derived, inferred or modelled?
- Which exact source artifact, method, units and coordinates produced a result?

A VascuQuest `VirtualSubject` is a simulation instance, **not a patient**.

## Validated capability map

| Capability | Status | Canonical source / method |
|---|---|---|
| Dataset identity and capability inspection | **Available** | Packaged PWDB manifest |
| Subject/model scalar access | **Available** | `pwdb_model_configs.csv` |
| Haemodynamic parameters | **Available** | `pwdb_haemod_params.csv` |
| Pulse-wave indices | **Available** | `pwdb_pw_indices.csv` |
| Onset/fiducial timing quantities | **Available** | `pwdb_onset_times.csv` |
| Subject-specific vascular geometry | **Available** | `geo.zip` |
| Common-site `P`, `U`, `A`, `PPG` waveforms | **Available** | `PWs_csv.zip` |
| Volumetric flow rate `Q` | **RECONSTRUCTED** | validated `Q = U*A` |
| JSON result export | **Available** | VascuQuest result model |
| CSV result export | **Available** | values + metadata sidecar |
| Provenance-aware reproduction | **Available** | recorded dataset/result lineage |
| Plugin discovery and inspection | **Available** | five explicit component categories |
| Dense path-resolved waveforms | **Not in 0.1.0** | optional future capability |

## Scientific evidence stays visible

VascuQuest uses five evidence classes:

- `SOURCE` — read from a supported canonical PWDB source representation;
- `RECONSTRUCTED` — deterministically reconstructed from aligned source quantities;
- `DERIVED` — produced by a declared scientific derivation;
- `INFERRED` — produced by an inference/discovery method where scientifically warranted;
- `MODELLED` — produced by an explicit research model/operator.

Evidence class is separate from validity. Material results carry provenance sufficient to identify source artifacts, quantities, units, coordinates and methods.

## Installation

VascuQuest 0.1.0 supports Python **3.11–3.14**.

From a source checkout or source release:

```bash
python -m pip install .
```

For development and tests:

```bash
python -m pip install ".[dev]"
```

The lightweight runtime depends on NumPy, platformdirs and Typer. Optional large-format readers are not imposed on the core installation merely because alternate PWDB representations exist.

Verify the installation:

```bash
vascuquest --version
vascuquest dataset info --format json
```

Importing VascuQuest does not automatically download PWDB artifacts.

## First use

Inspect local capability status:

```bash
vascuquest dataset status --format json
```

Register an existing directory containing canonical PWDB files:

```bash
vascuquest dataset register /path/to/pwdb
```

Recognised artifacts are checked against the packaged canonical manifest before they are trusted.

Acquire one explicit artifact when needed:

```bash
vascuquest dataset acquire --artifact model_configurations --yes
```

Acquisition is selective and checksum-verified; using VascuQuest does not imply downloading the complete PWDB archive.

## Python example

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

flow_rate = session.derive(
    "vascuquest:flow-rate-reconstruction",
    subjects="1",
    location=vq.MeasurementSite("AorticRoot"),
)
```

The built-in flow-rate reconstruction computes volumetric flow rate from aligned source flow-velocity and luminal-area waveforms using `Q = U*A`. It returns `RECONSTRUCTED` evidence in `m^3/s`; it does not interpolate mismatched inputs or substitute unavailable path data.

## CLI example

```bash
vascuquest get age \
  --subject 1 \
  --source /path/to/pwdb \
  --offline \
  --format json

vascuquest waveform pressure \
  --subject 1 \
  --location AorticRoot \
  --source /path/to/pwdb \
  --offline \
  --format json

vascuquest derive vascuquest:flow-rate-reconstruction \
  --subject 1 \
  --location AorticRoot \
  --source /path/to/pwdb \
  --offline \
  --format json
```

The CLI is a thin adapter over the same application services used by the Python API. Machine-readable output is written to stdout; operational messages are kept on stderr.

## Export and reproducibility

VascuQuest exports scientific results rather than unlabeled arrays. JSON preserves structured metadata directly. CSV uses a mandatory metadata sidecar where the table cannot carry the complete scientific context.

Strict reproduction fails rather than silently replacing an unavailable source or scientific method.

## Validation

The **core PWDB v1 scope passed real-source Tier-4 release validation**.

The release-validation harness uses the exact six canonical artifacts required by the public 0.1.0 capability set:

1. `pwdb_model_configs.csv`
2. `pwdb_haemod_params.csv`
3. `pwdb_pw_indices.csv`
4. `pwdb_onset_times.csv`
5. `geo.zip`
6. `PWs_csv.zip`

The recorded validation established, among other checks:

- canonical checksums for all six claimed artifacts;
- exact subject sequence/alignment across all 4,374 simulation identities in the scalar source tables;
- six age groups of 729 subjects each;
- complete inventory of all 4,374 geometry members;
- complete inventory and subject alignment of all 52 declared common-site waveform members;
- representative public-API waveform reads across the six source age groups;
- real-source `Q = U*A` flow-rate reconstruction with `RECONSTRUCTED` evidence;
- Python/CLI and packaging regression across the supported platform/Python matrix.

Batch-8 separately demonstrated that canonical dense path data are ingestible from the real MATLAB-v7.3/HDF5 source. That experiment does **not** constitute a public path-resolved capability in 0.1.0.

## Scope boundary

VascuQuest 0.1.0 deliberately does not claim:

- dense path-resolved PWDB waveform access;
- validation against the complete 44.3 GB PWDB archive;
- clinical interpretation of virtual subjects;
- support for source representations or scientific methods that have not passed their own implementation and validation gates.

A request for an unsupported capability fails explicitly; it is never silently remapped to a different vascular location or evidence class.

## Citation

For the software, use the repository citation metadata in [`CITATION.cff`](CITATION.cff). If the release later receives an archival software DOI, that DOI supersedes the repository URL as the preferred software identifier.

Research using PWDB source data should also cite the canonical upstream dataset:

- **Pulse Wave DataBase**, Zenodo record `3275625`, DOI [`10.5281/zenodo.3275625`](https://doi.org/10.5281/zenodo.3275625).

The built-in flow-rate reconstruction records the authoritative PWDB article citation, DOI [`10.1152/ajpheart.00218.2019`](https://doi.org/10.1152/ajpheart.00218.2019).

Do not replace the PWDB citation with the VascuQuest software citation when reporting research that uses the source dataset; they identify different scholarly objects.

## Licence and data boundary

VascuQuest software is distributed under the **Apache License 2.0**; see [`LICENSE`](LICENSE).

PWDB is external data. VascuQuest does not bundle or re-host the canonical PWDB source artifacts and **does not relicense the source dataset**.

## Documentation

Detailed scientific and implementation contracts live under [`docs/`](docs/):

- [`SCIENTIFIC_MODEL.md`](docs/SCIENTIFIC_MODEL.md) — quantities, locations, evidence and provenance;
- [`DATA_ENGINEERING.md`](docs/DATA_ENGINEERING.md) — source identity, acquisition and integrity;
- [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) — package architecture;
- [`API_PLUGIN_CONTRACT.md`](docs/API_PLUGIN_CONTRACT.md) — Python API and plugin contracts;
- [`CLI_CONTRACT.md`](docs/CLI_CONTRACT.md) — command-line contract;
- [`TEST_VALIDATION_CONTRACT.md`](docs/TEST_VALIDATION_CONTRACT.md) — testing and release-validation rules;
- [`BUILD_PLAN.md`](docs/BUILD_PLAN.md) — current development/release boundary.

Release-facing changes are recorded in [`CHANGELOG.md`](CHANGELOG.md).
