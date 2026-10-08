# VascuQuest 1.0 CLI contract

## 1. Purpose

The VascuQuest CLI is a thin Typer interface over the same scientific behavior exposed by the Python API. CLI formatting, file paths, and shell ergonomics must never alter scientific definitions, evidence classes, pairing rules, units, provenance, or validity semantics.

Machine-readable output belongs on stdout. Operational diagnostics and errors belong on stderr. Domain errors retain stable exit-code mapping.

## 2. Global invocation

```text
vascuquest [GLOBAL OPTIONS] COMMAND ...
```

Global options include:

- `--version` — print package version and exit;
- `--debug` — include chained diagnostic tracebacks;
- `--quiet` — suppress nonessential human diagnostics.

For the v1.0 release candidate:

```text
vascuquest --version
1.0.0
```

## 3. Top-level command surface

VascuQuest 1.0 retains the established core command groups/commands and adds first-class research-platform groups.

Core surface includes dataset/source inspection, subject selection, quantities, locations, direct value access, waveforms, derivations, models/discovery, plugins, export, and reproduction.

First-class v1 research groups are:

```text
vascuquest disease ...
vascuquest hemospace ...
vascuquest stats ...
vascuquest mechanics ...
vascuquest spectral ...
vascuquest plot ...
```

The CLI surface is additive relative to the existing core contract.

## 4. Core data commands

Core commands continue to expose canonical PWDB data and methods through the shared application services. Typical operations include:

```text
vascuquest dataset info
vascuquest dataset status
vascuquest dataset register <PATH>
vascuquest dataset acquire --artifact <ID> --yes
vascuquest dataset verify

vascuquest subjects ...
vascuquest quantities ...
vascuquest locations ...

vascuquest get <QUANTITY> --subject <ID> ...
vascuquest waveform <SIGNAL> --subject <ID> --location <SITE> ...
vascuquest derive <METHOD-ID> --subject <ID> --location <SITE> ...

vascuquest export ...
vascuquest reproduce ...
vascuquest plugins list
vascuquest plugins describe <QUALIFIED-ID>
```

Unsupported capabilities fail explicitly; they are not silently remapped to another source representation, location, or method.

## 5. `disease` group

The Virtual Disease CLI remains the interface to the qualified mechanistic disease subsystem.

Principal commands include:

```text
vascuquest disease presets
vascuquest disease describe <CONDITION>
vascuquest disease generate <CONDITION> ...
vascuquest disease cohort ...
```

Disease outputs remain `MODELLED`. CLI use does not imply clinical validation.

The CLI must preserve the same immutable disease request, subject-selection, physics, solver, quantity-status, and provenance behavior as the Python namespace.

## 6. `hemospace` group

HEMOSPACE exposes Virtual Cardiovascular Records, coverage, path physiology, cohorts, and documented operation semantics.

Representative commands include:

```text
vascuquest hemospace explain
vascuquest hemospace record --subject <ID> --depth scalar
vascuquest hemospace record --subject <ID> --depth geometry
vascuquest hemospace record --subject <ID> --depth comprehensive
vascuquest hemospace coverage --subject <ID>
vascuquest hemospace path --subject <ID> --path aorta_brain
```

Path access is lazy and requires the optional path dependency (`h5py`). The CLI must report the reader qualification status honestly and must not imply a fresh whole-artifact scan.

## 7. `stats` group

`vascuquest stats` operates on **native VascuQuest JSON scientific-result exports**. The CLI does not accept anonymous arrays as canonical research inputs.

Implemented commands:

```text
vascuquest stats describe <RESULT.json>
vascuquest stats bootstrap <RESULT.json> [--confidence ...] [--resamples ...] [--seed ...]
vascuquest stats compare <A.json> <B.json> [--paired] [--method ...]
vascuquest stats correlate <X.json> <Y.json> [--method pearson|...]
vascuquest stats partial-correlate <X.json> <Y.json> <CONTROL.json>...
vascuquest stats regress <RESPONSE.json> <PREDICTOR.json>... [--standardized]
vascuquest stats robust-regress <RESPONSE.json> <PREDICTOR.json>... [--huber-delta ...]
vascuquest stats normality <RESULT.json> [--method shapiro|...]
vascuquest stats variance <A.json> <B.json> [--center median|...]
vascuquest stats permutation <A.json> <B.json> [--paired] [--resamples ...] [--seed ...]
vascuquest stats quantiles <RESULT.json>
vascuquest stats exceedance <RESULT.json> <THRESHOLD> [--inclusive/--no-inclusive]
```

### Pairing rule

`--paired` is valid only when the inputs preserve identical canonical subject alignment. The command must not pair values merely because arrays have the same length.

### Reproducibility rule

Randomized methods expose explicit seeds. Given the same inputs, method parameters, and seed, results must be reproducible within the method's numerical contract.

### Designed-population rule

`exceedance` and cohort summaries describe the selected virtual design space. They are not clinical risk probabilities or epidemiological prevalence.

## 8. `mechanics` group

Implemented commands:

```text
vascuquest mechanics list
vascuquest mechanics compute <METRIC> <AREA.json> [PRESSURE.json] [--blood-density ...]
```

Canonical v1 metrics listed by the CLI include:

- `area_strain`;
- `diameter_strain`;
- `area_compliance`;
- `area_distensibility`;
- `pressure_area_slope`;
- `peterson_modulus`;
- `beta_stiffness_index`;
- `bramwell_hill_wave_speed`;
- `pressure_area_loop_integral`.

Inputs must be native `Waveform` JSON results. Metrics requiring pressure require aligned pressure and area waveforms for the same subject/location/time basis. No silent interpolation is performed.

The mechanics CLI does not run FSI or the disease solver.

## 9. `spectral` group

Implemented commands include:

```text
vascuquest spectral harmonics <WAVEFORM.json> [--count N] [--phase]
vascuquest spectral psd <WAVEFORM.json>
vascuquest spectral csd <X.json> <Y.json> [--phase] [--nperseg ...]
vascuquest spectral coherence <X.json> <Y.json> [--nperseg ...]
vascuquest spectral transfer <INPUT.json> <OUTPUT.json> [--phase] [--nperseg ...]
vascuquest spectral impedance <PRESSURE.json> <FLOW.json> [--harmonics N] [--phase]
vascuquest spectral characteristic-impedance <PRESSURE.json> <FLOW.json> [--start ...] [--end ...]
vascuquest spectral wave-separation <PRESSURE.json> <FLOW.json> <ZC> [--backward]
vascuquest spectral wave-intensity <PRESSURE.json> <VELOCITY.json> <WAVE-SPEED> [--component net|forward|backward] [--density ...]
vascuquest spectral stft <WAVEFORM.json> [--nperseg ...] [--noverlap ...]
vascuquest spectral entropy <WAVEFORM.json>
vascuquest spectral harmonic-energy-ratio <WAVEFORM.json> [--low-end ...] [--high-start ...] [--high-end ...]
vascuquest spectral reflection-magnitude <PRESSURE.json> <FLOW.json> <ZC>
```

Uniform sampling is enforced where required. Hidden resampling is forbidden.

Local pressure/flow methods require co-location. Cross-site CSD/coherence/transfer may compare different arteries for the same virtual subject only when time coordinates align.

## 10. `plot` group

Implemented convenience commands:

```text
vascuquest plot series <RESULT.json>... --output <FIGURE.svg|pdf|png> [--title ...] [--spec-output <SPEC.json>]
vascuquest plot scatter <X.json> <Y.json> --output <FIGURE.svg|pdf|png> [--title ...] [--spec-output <SPEC.json>]
```

The Python plotting API supports richer compound figures than these convenience commands, including multi-panel layouts and insets.

CLI plotting obeys these invariants:

- no silent cohort thinning/downsampling;
- rasterization may change rendering cost but not observations;
- legends remain outside the scientific plotting region;
- legend bounding boxes must not collide with axes, tick labels, axis labels, titles, insets, or neighboring panels;
- optional figure-spec output records the declarative recipe.

## 11. Native result-file boundary

The v1 research CLI groups use VascuQuest's portable JSON result representation as their file boundary. Loading a result reconstructs scientific metadata and values rather than importing an unlabeled table.

This preserves:

- quantity identity;
- subject/cohort identity;
- location;
- evidence;
- dimensions/coordinates;
- provenance reference;
- warnings/validity metadata supported by the result format.

CSV remains useful for tabular exchange but cannot silently replace the native result contract for methods that depend on full scientific context.

## 12. Output behavior

Machine-readable commands emit parseable output without decorative prose on stdout.

Human diagnostics, warnings that are not part of a machine result, and errors belong on stderr where the existing command implementation supports that distinction.

Commands writing files must fail rather than silently overwrite or reinterpret scientific content outside their declared behavior.

## 13. Stable domain exit codes

VascuQuest keeps the centralized exit mapping:

- `3` — dataset/capability unavailable;
- `4` — integrity failure;
- `5` — schema/unit/selection failure;
- `6` — admissibility/numerical-method failure;
- `7` — plugin compatibility/plugin failure;
- `8` — reproducibility failure;
- `70` — unexpected/internal software failure.

Click/Typer usage errors retain their normal command-line usage semantics.

## 14. API/CLI equivalence

For a given method, data, and parameters, CLI and Python behavior must agree scientifically. The CLI may serialize results differently for shell use, but it may not introduce different scientific defaults or bypass identity/alignment checks.

## 15. Dependency behavior

Commands requiring optional dependencies must fail explicitly with installation guidance/capability information. They must never silently choose a different method solely because SciPy, PyWavelets, Matplotlib, h5py, or JAX is absent.

## 16. Non-claims

CLI availability does not imply that a method is clinically validated. Commands operating on modelled disease results remain analyses of modelled counterfactuals. Commands operating on designed PWDB cohorts do not produce epidemiological risk or prevalence estimates.
