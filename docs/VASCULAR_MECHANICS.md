# Vascular mechanics in VascuQuest 1.0

## 1. Scope

`vascuquest.mechanics` derives local pressure-area and wave-mechanics descriptors from **existing VascuQuest scientific results**. It is a post-processing layer.

It does **not** solve coupled fluid-solid interaction (FSI), does not modify the Virtual Disease solver, and does not infer three-dimensional wall stress/strain fields.

The namespace is deliberately called `mechanics`, not `fsi`.

## 2. Input contract

The canonical inputs are VascuQuest `Waveform` objects.

For pressure-area operations, pressure and area must:

- belong to the same dataset identity;
- represent the same canonical subject;
- refer to the same vascular location;
- have aligned native time coordinates;
- be one-dimensional waveform series;
- contain physically admissible finite values for the chosen operation.

No silent interpolation or resampling is performed.

For area-only strain metrics, only the area waveform is required.

## 3. Unit normalization

The mechanics layer converts supported pressure values to Pa and luminal-area values to m² before applying the mathematical definitions.

Outputs use explicit SI-based canonical units unless the quantity is dimensionless.

## 4. Evidence

Mechanics results are `DERIVED` because they are calculated from existing source/reconstructed/modelled waveform values using declared definitions.

If the input waveforms are `MODELLED` disease outputs, the mechanics quantity is still a derived descriptor of modelled data; it does not become clinical evidence.

## 5. Area strain

Method:

```text
vascuquest:mechanics:area-strain-v1
```

Definition:

```text
area_strain = (Amax - Amin) / Amin
```

Requirements:

- strictly positive luminal area.

Output:

- dimensionless scalar.

This is a pulse-cycle area-change descriptor.

## 6. Equivalent-diameter strain

Method:

```text
vascuquest:mechanics:diameter-strain-v1
```

Equivalent circular diameter is inferred from area:

```text
D = sqrt(4 A / pi)
```

Then:

```text
diameter_strain = (Dmax - Dmin) / Dmin
```

Output:

- dimensionless scalar.

The equivalent circular diameter is a geometric representation derived from the stored area; it is not a claim that the physical cross-section is perfectly circular.

## 7. Area compliance

Method:

```text
vascuquest:mechanics:area-compliance-v1
```

Definition:

```text
C_A = ΔA / ΔP
```

with:

```text
ΔA = Amax - Amin
ΔP = Pmax - Pmin
```

Output unit:

```text
m²/Pa
```

Requirements:

- aligned pressure and area;
- non-zero pulse pressure;
- positive area.

## 8. Area distensibility

Method:

```text
vascuquest:mechanics:area-distensibility-v1
```

Definition:

```text
D_A = ΔA / (Amin ΔP)
```

Output unit:

```text
1/Pa
```

This is the cycle-wise area distensibility definition used by the v1 method. Researchers should not substitute a different baseline area convention without defining another method ID.

## 9. Effective pressure-area slope

Method:

```text
vascuquest:mechanics:pressure-area-slope-v1
```

The method performs a least-squares linear fit:

```text
A = slope * P + intercept
```

over the aligned pulse cycle.

Returned values include:

- slope in m²/Pa;
- intercept in m²;
- coefficient of determination R².

Important boundary:

> This is an effective cycle-wise pressure-area slope. It is not a pressure-independent wall material modulus.

## 10. Peterson elastic modulus

Method:

```text
vascuquest:mechanics:peterson-modulus-v1
```

Using the equivalent circular diameter:

```text
Ep = ΔP / ((Dmax - Dmin)/Dmin)
```

Output unit:

```text
Pa
```

Requirements:

- positive pulse pressure;
- positive diameter strain.

This is a local waveform-derived stiffness descriptor under the adopted definition, not a direct tissue constitutive modulus.

## 11. Beta stiffness index

Method:

```text
vascuquest:mechanics:beta-stiffness-v1
```

Definition:

```text
β = ln(Ps/Pd) / ((Ds-Dd)/Dd)
```

where systolic/diastolic pressure and equivalent-diameter extrema are taken from the aligned cycle.

Output:

- dimensionless scalar.

Requirements:

- positive diastolic pressure;
- Ps > Pd;
- Ds > Dd > 0.

Important warning:

> Beta stiffness remains pressure dependent and must not be interpreted as a universal pressure-independent material constant.

## 12. Bramwell-Hill wave-speed estimate

Method:

```text
vascuquest:mechanics:bramwell-hill-v1
```

Using area distensibility:

```text
c = sqrt(1 / (ρ D_A))
```

Default blood density:

```text
ρ = 1060 kg/m³
```

Output unit:

```text
m/s
```

The density can be supplied explicitly.

Important interpretation boundary:

> This is a local pressure-area wave-speed estimate under Bramwell-Hill assumptions. It is not a clinical transit-time PWV measurement.

## 13. Pressure-area loop integral

Method:

```text
vascuquest:mechanics:pressure-area-loop-v1
```

Definition:

```text
∮ P dA
```

implemented as the signed closed-cycle integral of pressure with respect to area.

Output unit:

```text
Pa·m² = N
```

The force unit is equivalent to work per unit axial length under the one-dimensional interpretation.

Important boundary:

> This is not a full three-dimensional wall-energy calculation and does not constitute FSI.

## 14. Metric dispatcher

Python convenience:

```python
from vascuquest.mechanics import compute

result = compute(
    "area_distensibility",
    pressure=pressure_waveform,
    area=area_waveform,
)
```

Area-only metrics:

```text
area_strain
diameter_strain
```

Pressure+area metrics:

```text
area_compliance
area_distensibility
pressure_area_slope
peterson_modulus
beta_stiffness_index
bramwell_hill_wave_speed
pressure_area_loop_integral
```

Unknown metric names fail explicitly.

## 15. CLI

List available metrics:

```text
vascuquest mechanics list
```

Compute an area-only metric:

```text
vascuquest mechanics compute area_strain area.json
```

Compute a pressure-area metric:

```text
vascuquest mechanics compute area_distensibility area.json pressure.json
```

For Bramwell-Hill wave speed:

```text
vascuquest mechanics compute bramwell_hill_wave_speed area.json pressure.json --blood-density 1060
```

Inputs are native VascuQuest waveform JSON exports.

## 16. Individual and cohort use

Mechanics functions operate on waveform objects. For one virtual subject/location, the result is one local mechanics descriptor.

For cohort research, the correct pattern is:

```text
for each canonical subject
    ↓
compute local mechanics descriptor
    ↓
preserve subject ID
    ↓
assemble aligned ScientificResult/cohort vector
    ↓
vascuquest.stats
```

The cohort-level statistic is not computed by losing individual identity first.

## 17. Healthy vs disease mechanics

A common v1 study can compare mechanics descriptors derived from healthy and matched `MODELLED` disease waveforms.

Example interpretation:

> change in local area distensibility under the specified modelled large-artery stiffening intervention

not:

> measured treatment response in patients

## 18. Path-wise use

Where HEMOSPACE provides pressure/area signals at supported path positions, the same local definitions can be applied position-by-position if the required aligned waveform inputs are available.

Any spatial profile remains a collection of local derived descriptors. VascuQuest must not interpolate unstored path positions merely to create a smooth field.

## 19. Scientific references

The v1 mechanics implementation records arterial-stiffness/wave-mechanics references including:

- PMID `31466622`;
- DOI `10.1161/HYP.0000000000000033`.

Researchers should cite the methodological literature appropriate to the specific quantity they report, as well as VascuQuest/PWDB where applicable.

## 20. Non-claims

The mechanics layer does not claim:

- full fluid-solid interaction;
- finite-element wall mechanics;
- 3D stress/strain fields;
- wall shear stress;
- plaque stress or vulnerability;
- aneurysm rupture risk;
- patient-specific material properties;
- clinical PWV equivalence for the Bramwell-Hill estimate;
- clinical validation of disease-state mechanics.
