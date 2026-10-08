"""Qualified vascular-wall and pressure-area mechanics operations."""
from __future__ import annotations

import math
import numpy as np

from vascuquest.analysis import ensure_aligned_waveforms, make_result
from vascuquest.analysis.units import area_m2, pressure_pa
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.result import ScientificResult, Waveform
from vascuquest.errors import AdmissibilityError

_STIFFNESS_CITATIONS = (
    "PMID:31466622",
    "DOI:10.1161/HYP.0000000000000033",
)


def _pressure_area(pressure: Waveform, area: Waveform) -> tuple[np.ndarray, np.ndarray]:
    ensure_aligned_waveforms(pressure, area)
    p = pressure_pa(pressure)
    a = area_m2(area)
    if p.ndim != 1 or a.ndim != 1 or p.size != a.size:
        raise AdmissibilityError("pressure-area mechanics requires aligned one-dimensional waveforms")
    if np.any(a <= 0):
        raise AdmissibilityError("luminal area must be strictly positive")
    return p, a


def _diameter(area_m2_values: np.ndarray) -> np.ndarray:
    return np.sqrt(4.0 * area_m2_values / math.pi)


def area_strain(area: Waveform) -> ScientificResult:
    a = area_m2(area)
    amin, amax = float(np.min(a)), float(np.max(a))
    if amin <= 0:
        raise AdmissibilityError("area strain requires strictly positive luminal area")
    value = (amax - amin) / amin
    return make_result(area, canonical_name="mechanics.area_strain", label="Area strain", description="Pulse-cycle luminal-area strain (Amax-Amin)/Amin.", values=float(value), method_id="vascuquest:mechanics:area-strain-v1", evidence=EvidenceClass.DERIVED, canonical_unit="1", physical_dimension="dimensionless", value_kind="scalar", citations=_STIFFNESS_CITATIONS)


def diameter_strain(area: Waveform) -> ScientificResult:
    a = area_m2(area); d = _diameter(a)
    dmin, dmax = float(np.min(d)), float(np.max(d))
    if dmin <= 0:
        raise AdmissibilityError("diameter strain requires strictly positive luminal diameter")
    value = (dmax - dmin) / dmin
    return make_result(area, canonical_name="mechanics.diameter_strain", label="Equivalent-diameter strain", description="Pulse-cycle equivalent circular-diameter strain inferred from luminal area.", values=float(value), method_id="vascuquest:mechanics:diameter-strain-v1", evidence=EvidenceClass.DERIVED, canonical_unit="1", physical_dimension="dimensionless", value_kind="scalar", citations=_STIFFNESS_CITATIONS)


def area_compliance(pressure: Waveform, area: Waveform) -> ScientificResult:
    p, a = _pressure_area(pressure, area); dp = float(np.max(p) - np.min(p))
    if dp <= 0: raise AdmissibilityError("area compliance requires non-zero pulse pressure")
    value = float((np.max(a) - np.min(a)) / dp)
    return make_result(area, canonical_name="mechanics.area_compliance", label="Area compliance", description="Pulse-cycle area compliance ΔA/ΔP using aligned local pressure and luminal-area waveforms.", values=value, method_id="vascuquest:mechanics:area-compliance-v1", inputs=(pressure, area), evidence=EvidenceClass.DERIVED, canonical_unit="m^2/Pa", physical_dimension="area_per_pressure", value_kind="scalar", citations=_STIFFNESS_CITATIONS)


def area_distensibility(pressure: Waveform, area: Waveform) -> ScientificResult:
    p, a = _pressure_area(pressure, area); dp = float(np.max(p)-np.min(p)); amin=float(np.min(a))
    if dp <= 0 or amin <= 0: raise AdmissibilityError("area distensibility requires positive minimum area and non-zero pulse pressure")
    value=float((np.max(a)-amin)/(amin*dp))
    return make_result(area, canonical_name="mechanics.area_distensibility", label="Area distensibility", description="Pulse-cycle area distensibility ΔA/(Amin ΔP).", values=value, method_id="vascuquest:mechanics:area-distensibility-v1", inputs=(pressure,area), evidence=EvidenceClass.DERIVED, canonical_unit="1/Pa", physical_dimension="inverse_pressure", value_kind="scalar", citations=_STIFFNESS_CITATIONS)


def pressure_area_slope(pressure: Waveform, area: Waveform) -> ScientificResult:
    p,a=_pressure_area(pressure,area)
    if np.ptp(p)<=0: raise AdmissibilityError("pressure-area slope requires varying pressure")
    slope,intercept=np.polyfit(p,a,deg=1); predicted=slope*p+intercept
    ss_res=float(np.sum((a-predicted)**2)); ss_tot=float(np.sum((a-np.mean(a))**2)); r2=1.0-ss_res/ss_tot if ss_tot>0 else 1.0
    return make_result(area, canonical_name="mechanics.pressure_area_slope", label="Pressure-area slope", description="Least-squares effective local pressure-area slope over one aligned pulse cycle.", values={"slope_m2_per_pa":float(slope),"intercept_m2":float(intercept),"r2":float(r2)}, method_id="vascuquest:mechanics:pressure-area-slope-v1", inputs=(pressure,area), evidence=EvidenceClass.DERIVED, canonical_unit="m^2/Pa", physical_dimension="area_per_pressure", value_kind="mapping", citations=_STIFFNESS_CITATIONS, warnings=("This is an effective cycle-wise slope; it does not imply a pressure-independent wall material modulus.",))


def peterson_modulus(pressure: Waveform, area: Waveform) -> ScientificResult:
    p,a=_pressure_area(pressure,area); d=_diameter(a); dp=float(np.max(p)-np.min(p)); dmin,dmax=float(np.min(d)),float(np.max(d)); strain=(dmax-dmin)/dmin if dmin>0 else 0.0
    if dp<=0 or strain<=0: raise AdmissibilityError("Peterson modulus requires positive pulse pressure and diameter strain")
    return make_result(area, canonical_name="mechanics.peterson_modulus", label="Peterson elastic modulus", description="Pressure increment divided by equivalent-diameter fractional strain.", values=float(dp/strain), method_id="vascuquest:mechanics:peterson-modulus-v1", inputs=(pressure,area), evidence=EvidenceClass.DERIVED, canonical_unit="Pa", physical_dimension="pressure", value_kind="scalar", citations=_STIFFNESS_CITATIONS)


def beta_stiffness_index(pressure: Waveform, area: Waveform) -> ScientificResult:
    p,a=_pressure_area(pressure,area); d=_diameter(a); ps,pd=float(np.max(p)),float(np.min(p)); dmax,dmin=float(np.max(d)),float(np.min(d))
    if pd<=0 or ps<=pd or dmin<=0 or dmax<=dmin: raise AdmissibilityError("beta stiffness requires positive diastolic pressure and positive pressure/diameter pulsation")
    value=math.log(ps/pd)/((dmax-dmin)/dmin)
    return make_result(area, canonical_name="mechanics.beta_stiffness_index", label="Beta stiffness index", description="Dimensionless beta stiffness index ln(Ps/Pd)/((Ds-Dd)/Dd) using equivalent circular diameter.", values=float(value), method_id="vascuquest:mechanics:beta-stiffness-v1", inputs=(pressure,area), evidence=EvidenceClass.DERIVED, canonical_unit="1", physical_dimension="dimensionless", value_kind="scalar", citations=_STIFFNESS_CITATIONS, warnings=("Beta stiffness is pressure dependent and must not be interpreted as a pressure-independent material constant.",))


def bramwell_hill_wave_speed(pressure: Waveform, area: Waveform, *, blood_density: float = 1060.0) -> ScientificResult:
    if blood_density<=0: raise ValueError("blood_density must be positive")
    dist=area_distensibility(pressure,area); value=float(1.0/math.sqrt(blood_density*float(dist.values)))
    return make_result(area, canonical_name="mechanics.bramwell_hill_wave_speed", label="Bramwell-Hill wave speed", description="Local wave-speed estimate c=sqrt(1/(rho*D_A)) from area distensibility.", values=value, method_id="vascuquest:mechanics:bramwell-hill-v1", inputs=(pressure,area), parameters={"blood_density_kg_m3":blood_density}, evidence=EvidenceClass.DERIVED, canonical_unit="m/s", physical_dimension="velocity", value_kind="scalar", citations=_STIFFNESS_CITATIONS, warnings=("Bramwell-Hill assumptions apply; this is a local pressure-area estimate, not a clinical transit-time PWV measurement.",))


def pressure_area_loop_integral(pressure: Waveform, area: Waveform) -> ScientificResult:
    p,a=_pressure_area(pressure,area); p_closed=np.concatenate([p,p[:1]]); a_closed=np.concatenate([a,a[:1]]); value=float(np.trapezoid(p_closed,x=a_closed))
    return make_result(area, canonical_name="mechanics.pressure_area_loop_integral", label="Pressure-area loop integral", description="Signed closed-cycle integral ∮P dA. Its unit is force (N), equivalent to work per unit axial length.", values=value, method_id="vascuquest:mechanics:pressure-area-loop-v1", inputs=(pressure,area), evidence=EvidenceClass.DERIVED, canonical_unit="N", physical_dimension="force", value_kind="scalar", citations=_STIFFNESS_CITATIONS, warnings=("The integral is not a full three-dimensional wall-energy calculation and does not constitute FSI.",))


def compute(metric: str, *, pressure: Waveform | None = None, area: Waveform | None = None, blood_density: float = 1060.0) -> ScientificResult:
    metric=metric.strip().lower().replace("-","_"); area_only={"area_strain":area_strain,"diameter_strain":diameter_strain}
    if metric in area_only:
        if area is None: raise ValueError(f"{metric} requires area waveform")
        return area_only[metric](area)
    if pressure is None or area is None: raise ValueError(f"{metric} requires pressure and area waveforms")
    mapping={"area_compliance":area_compliance,"area_distensibility":area_distensibility,"pressure_area_slope":pressure_area_slope,"peterson_modulus":peterson_modulus,"beta_stiffness_index":beta_stiffness_index,"pressure_area_loop_integral":pressure_area_loop_integral}
    if metric=="bramwell_hill_wave_speed": return bramwell_hill_wave_speed(pressure,area,blood_density=blood_density)
    try: return mapping[metric](pressure,area)
    except KeyError as exc: raise ValueError(f"unknown mechanics metric {metric!r}; choose from {sorted((*area_only,*mapping,'bramwell_hill_wave_speed'))!r}") from exc

__all__=["area_compliance","area_distensibility","area_strain","beta_stiffness_index","bramwell_hill_wave_speed","compute","diameter_strain","peterson_modulus","pressure_area_loop_integral","pressure_area_slope"]
