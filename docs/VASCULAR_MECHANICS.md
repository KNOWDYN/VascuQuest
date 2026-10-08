# Vascular mechanics

The v1 mechanics layer derives local pressure-area/wall descriptors from existing aligned VascuQuest waveforms. It is deliberately named **vascular mechanics**, not FSI.

## Methods

For local pressure `P(t)` and luminal area `A(t)`:

- Area strain: `(Amax-Amin)/Amin`
- Area compliance: `ΔA/ΔP`
- Area distensibility: `ΔA/(Amin ΔP)`
- Equivalent diameter: `D=sqrt(4A/pi)`
- Peterson modulus: `ΔP / (ΔD/Dd)`
- Beta stiffness: `ln(Ps/Pd)/(ΔD/Dd)`
- Bramwell-Hill wave speed: `c=sqrt(1/(rho*D_A))`
- Pressure-area loop integral: closed-cycle `∮P dA`

A cycle-wise least-squares pressure-area slope is also available and is explicitly not represented as a pressure-independent wall material modulus.

## Unit policy

Qualified pressure inputs: Pa, kPa, mmHg. Qualified area inputs: m², cm², mm². Internal mechanics calculations use SI units.

## No silent resampling

Pressure and area must refer to the same virtual subject, vascular location and aligned time coordinate.

## Scientific references

- Chirinos et al., *JACC* state-of-the-art review on large-artery stiffness, PMID 31466622.
- AHA scientific statement: `10.1161/HYP.0000000000000033`.
