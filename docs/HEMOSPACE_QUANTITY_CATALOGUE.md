# HEMOSPACE Quantity Catalogue

This catalogue defines the scientific interpretation of the principal HEMOSPACE knowledge families. The machine record remains authoritative for exact source field, unit, location, evidence class and assumptions.

## Source families

### Identity and design

Examples:

- `simulation_age`
- baseline flags from model configuration
- `model_population_sex_assumption`
- age field from model-variation/pulse-wave-index tables

These describe how the virtual simulation is configured. Age is a simulation/design attribute, not a longitudinal observation.

### Generative physiology

Source model configuration includes prescribed HR, SV, LVET, pressure/outflow parameters, viscosity, density, peripheral resistance/compliance and wall-law coefficients where available.

### Generative variation

The ten principal PWDB perturbation axes are:

| Canonical ID | Source | Meaning | Unit |
|---|---|---|---|
| `large_artery_diameter_variation` | DIA | prescribed large-artery diameter deviation | SD from age mean |
| `heart_rate_variation` | HR | prescribed heart-rate deviation | SD from age mean |
| `proximal_aortic_length_variation` | LEN | prescribed proximal-aortic-length deviation | SD from age mean |
| `lvet_variation` | LVET | prescribed LV ejection-time deviation | SD from age mean |
| `mean_blood_pressure_variation` | MBP | prescribed mean-pressure deviation | SD from age mean |
| `peripheral_vascular_compliance_variation` | PVC | prescribed peripheral-compliance deviation | SD from age mean |
| `arterial_stiffness_variation` | PWV | prescribed stiffness/PWV deviation | SD from age mean |
| `reverse_flow_volume_variation` | RFV | prescribed root reverse-flow-volume deviation | SD from age mean |
| `stroke_volume_variation` | SV | prescribed stroke-volume deviation | SD from age mean |
| `peak_flow_time_variation` | PFT | prescribed root peak-flow-time deviation | SD from age mean |

These are model design coordinates, not clinical z-scores.

### Haemodynamic source quantities

HEMOSPACE exposes every numeric field in `pwdb_haemod_params.csv`, including cardiac output/timing, central/peripheral pressure, PWV, diameters, proximal aortic length, peripheral pressure drops and systemic resistance.

### Pulse-wave indices

Every numeric source field in `pwdb_pw_indices.csv` is retained. Recognized families include:

- pressure: SBP, DBP, MBP, PP and waveform points;
- flow: Qmax/Qmin/Qmean/Qtotal;
- velocity: Umax/Umin/Umean;
- area: Amax/Amin/Amean;
- timing: PTT and fiducial-time columns;
- wave reflection: AI/AP;
- PPG morphology: a/b/c/d/e, systolic/diastolic/dicrotic metrics, RI, SI, AGI-mod.

Unknown-but-numeric source columns remain visible under stable source-derived IDs rather than being discarded.

## Scalar reconstructed/derived quantities

### `cardiac_cycle_duration`

Evidence: `DERIVED`

Equation:

```text
T = 60 / HR
```

Unit: seconds.

### `cardiac_output_from_hr_sv`

Evidence: `RECONSTRUCTED`

```text
CO [L/min] = HR [1/min] * SV [mL] / 1000
```

### `cardiac_output_reconstruction_discrepancy`

Evidence: `DERIVED`

```text
100 * (CO_HR×SV - CO_source) / CO_source
```

This is a consistency diagnostic, not a clinical abnormality score.

### `reconstructed_pulse_pressure_*`

Evidence: `RECONSTRUCTED`

```text
PP = SBP - DBP
```

### `mean_systemic_hydraulic_power`

Evidence: `DERIVED`

```text
Power ≈ MBP(Pa) * CO(m³/s)
```

This is a system-level hydraulic approximation, not myocardial metabolic power.

### `pwdb_physiological_plausibility`

Evidence: `RECONSTRUCTED`

HEMOSPACE reconstructs the upstream PWDB source plausibility gate from seven pressure characteristics using the source algorithm's embedded age-dependent McEniery reference distributions and ±2.575 SD bounds.

It reproduces source-generation validation; it is not a clinical screening rule.

## Common-site waveform derivations

HEMOSPACE summarizes source P/U/A/PPG waves and reconstructed Q=U×A.

### Morphology summary

For each available wave:

- minimum;
- maximum;
- mean;
- amplitude;
- time to maximum;
- time to minimum;
- cycle integral.

### Velocity pulsatility index

```text
(Umax - Umin) / |Umean|
```

### Velocity resistive index

```text
(Umax - Umin) / Umax
```

Use as a waveform descriptor only; do not silently map it to a clinical Doppler diagnosis.

### Area strain

```text
(Amax - Amin) / Amin
```

### Local area compliance

```text
(Amax - Amin) / (Pmax - Pmin)
```

Unit: m²/mmHg.

### Local area distensibility

```text
(Amax - Amin) / [Amin * (Pmax - Pmin)]
```

Unit: 1/mmHg.

### Flow pulsatility index

```text
(Qmax - Qmin) / |Qmean|
```

### Cycle flow volumes

```text
forward = ∫ max(Q,0) dt
reverse = -∫ min(Q,0) dt
net = ∫ Q dt
reverse fraction = reverse / forward
```

### Hydraulic power/energy

```text
instantaneous power = P(Pa) * Q(m³/s)
mean hydraulic power = mean(PQ)
energy per cycle = ∫ P Q dt
```

These quantify hydraulic energy transport across the represented section.

### Pressure-flow impedance harmonics

For uniformly sampled aligned P/Q source/reconstructed waves, HEMOSPACE reports harmonics 1–5 of:

```text
Z(f) = FFT(P - mean(P)) / FFT(Q - mean(Q))
```

Each entry includes frequency, magnitude and phase. This is a local frequency-domain pressure-flow relation, not a directly measured clinical impedance spectrum.

## Geometry derivations

From the 116-segment source geometry HEMOSPACE derives:

- segment count;
- total represented segment length;
- endpoint diameter range;
- conical-frustum lumen-volume approximation.

No 3-D surface geometry, wall shear stress, plaque morphology or sac recirculation is implied.

## Path-resolved derivations

Where canonical path artifacts are available:

- pointwise P/U/A source summaries;
- Q=U×A reconstruction;
- apparent path PWV from linear distance-versus-onset-time fit;
- onset-distance regression R²;
- terminal/root pressure-pulse amplification.

The path reader carries an explicit real-source qualification flag because the multi-GB canonical path artifacts are not exercised in normal CI.

## Disease-response quantities

HEMOSPACE response mode aligns the comprehensive healthy record with persisted MODELLED Virtual Disease waveforms for the same canonical subject and reports:

```text
baseline value
disease value
absolute change
relative change (%) when baseline != 0
```

These remain `MODELLED` counterfactual response quantities.

## Explicitly unavailable categories

PWDB alone does not identify smoking history, genetics, renal function, medication history, symptoms, plaque composition, thrombotic state, longitudinal life history or future clinical-event risk.
