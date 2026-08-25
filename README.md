# VascuQuest

Scientific exploration and discovery for virtual vascular populations.

VascuQuest is a Python package and command-line interface for working with the canonical **Pulse Wave DataBase (PWDB) Zenodo record 3275625** through explicit scientific identities, units, evidence classes, provenance, integrity checks, and registered scientific components.

The current package is **pre-release (`0.1.0.dev0`)**. Its implemented core scope is intentionally narrower than the complete PWDB archive: scalar subject quantities, source-supported geometry, common-site waveforms, one validated flow-rate reconstruction, JSON/CSV result export, provenance-aware reproduction, plugin inspection, and matching Python/CLI application flows. Dense path-resolved waveforms are not currently claimed or silently substituted.

## Installation

VascuQuest supports Python **3.11, 3.12, 3.13, and 3.14**.

From a source checkout:

```bash
python -m pip install .
```

For development and tests:

```bash
python -m pip install ".[dev]"
```

The package installs the `vascuquest` console command and also supports:

```bash
python -m vascuquest --version
```

## Canonical dataset

VascuQuest binds the built-in PWDB backend to the canonical record:

- Zenodo record: `3275625`
- DOI: `10.5281/zenodo.3275625`

The package manifest records canonical artifact filenames and checksums. Data are acquired or registered explicitly; importing VascuQuest does not download data.

Inspect the canonical manifest without acquiring artifacts:

```bash
vascuquest dataset info --format json
```

Register an existing local directory containing canonical PWDB artifacts:

```bash
vascuquest dataset register /path/to/pwdb
```

Registration verifies recognized local artifacts against the canonical manifest before accepting the source. To acquire an explicit artifact through the managed data layer:

```bash
vascuquest dataset acquire --artifact model_configurations --yes
```

Acquisition prints its plan to stderr, verifies the canonical checksum before promotion, and respects `--offline`. Large or unknown-size transfers require explicit confirmation; non-interactive use requires `--yes`.

## Minimal Python use

Dataset identity and capability status are available without downloading source data:

```python
import vascuquest as vq

session = vq.open_dataset(offline=True)
print(session.identity)
print(session.status())
```

After registering or supplying a directory containing the required verified artifacts:

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

The built-in flow-rate reconstruction computes volumetric flow rate from aligned source flow-velocity and luminal-area waveforms using the authoritative PWDB identity `Q = U*A`. It produces `RECONSTRUCTED` evidence in `m^3/s`; it does not interpolate mismatched inputs or substitute path-resolved data.

## Minimal CLI use

The CLI is a thin adapter over the same application services used by the Python API.

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

Use `vascuquest --help` and subcommand `--help` for the frozen v1 command surface. Machine-readable JSON/JSONL output is kept on stdout; progress, plans, warnings, and operational errors are directed to stderr.

## Evidence and provenance

Scientific results distinguish how values came into being using five evidence classes:

- `SOURCE`
- `RECONSTRUCTED`
- `DERIVED`
- `INFERRED`
- `MODELLED`

Evidence class is separate from validity/admissibility state. Material results retain canonical dataset/quantity identity, units, coordinates, subject/cohort/location context where applicable, provenance references, and producing method identity where required.

JSON and constrained CSV exporters preserve the result metadata required for round-trip reconstruction. CSV export uses a mandatory metadata sidecar rather than discarding scientific context.

## Plugin model

VascuQuest has five explicit plugin categories:

- dataset backend;
- derivation;
- research operator;
- discovery method;
- result exporter.

Inspect available components without acquiring dataset artifacts:

```bash
vascuquest plugins list --format jsonl
vascuquest plugins describe vascuquest:flow-rate-reconstruction --format json
```

Unavailable or incompatible components fail explicitly; the CLI does not simulate missing scientific methods.

## Validation status and limitations

The current core implementation has passed its unit, contract, adapter, scientific, exporter, CLI, integration, packaging, and non-full-data regression tests through Batch 13. Batch 14 adds the permanent supported-platform CI and package build/install gate.

This is **not yet a release-validation claim**. Core-source release validation is a separate Batch-15 gate and must execute against the exact canonical artifacts required by the capabilities claimed by the release candidate.

Current limitations are explicit:

- dense path-resolved PWDB waveform support is unavailable pending the real-source Batch-8 ingestion gate and subsequent Batch-9 production reader;
- a path request is never remapped to a common measurement site;
- VascuQuest does not currently claim validation against the complete 44.3 GB PWDB archive;
- only scientific components that have passed their authoritative-definition and method-validation gates are shipped as built-ins;
- optional MATLAB/HDF5/WFDB reader dependencies are not imposed on the lightweight core solely for unvalidated path functionality.

## Citation

For the canonical dataset, cite the PWDB Zenodo record:

- Pulse Wave DataBase, Zenodo record 3275625, DOI `10.5281/zenodo.3275625`.

The built-in flow-rate reconstruction also records the authoritative PWDB article citation:

- DOI `10.1152/ajpheart.00218.2019`.

Component-specific citations are exposed by `vascuquest plugins describe` where applicable.

## Licence

VascuQuest software is distributed under the **Apache License 2.0**; see [`LICENSE`](LICENSE).

The PWDB dataset is external to this software repository and remains governed by the terms attached to its canonical Zenodo record. VascuQuest does not relicense the source dataset.
