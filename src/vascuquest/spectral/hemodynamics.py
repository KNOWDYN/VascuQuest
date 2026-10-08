"""Pressure-flow impedance, wave separation and wave intensity."""
from __future__ import annotations
import numpy as np
from vascuquest.analysis import ensure_aligned_waveforms, make_result, time_values
from vascuquest.analysis.units import flow_m3s, pressure_pa, velocity_ms
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.result import Coordinate, ScientificResult, Waveform
from vascuquest.errors import AdmissibilityError
from ._shared import _WAVE_CITATIONS, _uniform_signal

def impedance(pressure: Waveform, flow: Waveform, *, n_harmonics: int = 10, min_flow_fraction: float = 1e-9) -> tuple[ScientificResult, ScientificResult]:
    ensure_aligned_waveforms(pressure, flow); _,_,dt=_uniform_signal(pressure); _uniform_signal(flow); p=pressure_pa(pressure); q=flow_m3s(flow); n=p.size
    p_coeff=np.fft.rfft(p-np.mean(p))/n; q_coeff=np.fft.rfft(q-np.mean(q))/n; freq=np.fft.rfftfreq(n,d=dt); stop=min(p_coeff.size,n_harmonics+1); p_coeff,q_coeff=p_coeff[1:stop],q_coeff[1:stop]; harmonic=np.arange(1,stop,dtype=int)
    threshold=max(float(np.max(np.abs(q_coeff)))*min_flow_fraction,np.finfo(float).tiny); valid=np.abs(q_coeff)>threshold; z=np.full(q_coeff.shape,np.nan+1j*np.nan,dtype=complex); z[valid]=p_coeff[valid]/q_coeff[valid]; warnings=() if np.all(valid) else ("One or more harmonics were undefined because flow amplitude was below the declared denominator threshold.",)
    common=dict(inputs=(pressure,flow),parameters={"n_harmonics":n_harmonics,"min_flow_fraction":min_flow_fraction},evidence=EvidenceClass.DERIVED,value_kind="series",dimensions=("harmonic",),coordinates=(Coordinate("harmonic",harmonic,"1"),Coordinate("frequency",freq[1:stop],"Hz")),citations=_WAVE_CITATIONS,warnings=warnings)
    magnitude=make_result(pressure,canonical_name="spectral.input_impedance_magnitude",label="Input impedance magnitude",description="Pressure-flow input-impedance magnitude |P_n/Q_n| from aligned local Fourier coefficients.",values=np.abs(z),method_id="vascuquest:spectral:input-impedance-v1",canonical_unit="Pa*s/m^3",physical_dimension="hydraulic_impedance",**common)
    phase=make_result(pressure,canonical_name="spectral.input_impedance_phase",label="Input impedance phase",description="Pressure-flow input-impedance phase angle arg(P_n/Q_n).",values=np.angle(z),method_id="vascuquest:spectral:input-impedance-v1",canonical_unit="rad",physical_dimension="angle",**common)
    return magnitude,phase

def characteristic_impedance(pressure: Waveform, flow: Waveform, *, harmonic_start: int = 3, harmonic_end: int = 10) -> ScientificResult:
    if harmonic_start<1 or harmonic_end<harmonic_start: raise ValueError("harmonic range must satisfy 1 <= start <= end")
    mag,_=impedance(pressure,flow,n_harmonics=harmonic_end); harmonics=np.asarray(mag.coordinates[0].values,dtype=int); values=np.asarray(mag.values,dtype=float); mask=(harmonics>=harmonic_start)&(harmonics<=harmonic_end)&np.isfinite(values)
    if not np.any(mask): raise AdmissibilityError("no valid impedance harmonics exist in the requested characteristic-impedance range")
    zc=float(np.median(values[mask]))
    return make_result(pressure,canonical_name="spectral.characteristic_impedance_estimate",label="Characteristic impedance estimate",description="Median high-harmonic pressure-flow impedance magnitude over an explicitly declared harmonic range.",values=zc,method_id="vascuquest:spectral:characteristic-impedance-v1",inputs=(pressure,flow),parameters={"harmonic_start":harmonic_start,"harmonic_end":harmonic_end,"estimator":"median"},evidence=EvidenceClass.DERIVED,canonical_unit="Pa*s/m^3",physical_dimension="hydraulic_impedance",value_kind="scalar",citations=_WAVE_CITATIONS,warnings=("This frequency-domain estimate is method-dependent and must not be interpreted as a directly measured material property.",))

def wave_separation(pressure: Waveform, flow: Waveform, *, characteristic_impedance_pa_s_m3: float) -> tuple[ScientificResult, ScientificResult]:
    if characteristic_impedance_pa_s_m3<=0: raise ValueError("characteristic_impedance_pa_s_m3 must be positive")
    ensure_aligned_waveforms(pressure,flow); p=pressure_pa(pressure); q=flow_m3s(flow); pp=p-np.mean(p); qp=q-np.mean(q); zc=characteristic_impedance_pa_s_m3; forward=.5*(pp+zc*qp); backward=.5*(pp-zc*qp); coords=(Coordinate("time",time_values(pressure),pressure.time_coordinate.unit),)
    common=dict(inputs=(pressure,flow),parameters={"characteristic_impedance_pa_s_m3":zc,"mean_handling":"pulsatile_components"},evidence=EvidenceClass.DERIVED,canonical_unit="Pa",physical_dimension="pressure",value_kind="waveform",dimensions=("time",),coordinates=coords,citations=_WAVE_CITATIONS)
    return make_result(pressure,canonical_name="spectral.forward_pressure_wave",label="Forward pressure wave",description="Pulsatile forward-travelling pressure component from pressure-flow wave separation.",values=forward,method_id="vascuquest:spectral:wave-separation-v1",**common), make_result(pressure,canonical_name="spectral.backward_pressure_wave",label="Backward pressure wave",description="Pulsatile backward-travelling pressure component from pressure-flow wave separation.",values=backward,method_id="vascuquest:spectral:wave-separation-v1",**common)

def reflection_magnitude(pressure: Waveform, flow: Waveform, *, characteristic_impedance_pa_s_m3: float) -> ScientificResult:
    forward,backward=wave_separation(pressure,flow,characteristic_impedance_pa_s_m3=characteristic_impedance_pa_s_m3); pf=np.asarray(forward.values,dtype=float); pb=np.asarray(backward.values,dtype=float); af=float(np.max(np.abs(pf))); ab=float(np.max(np.abs(pb)))
    if af<=0: raise AdmissibilityError("forward pressure-wave amplitude is zero; reflection magnitude is undefined")
    return make_result(pressure,canonical_name="spectral.reflection_magnitude",label="Reflection magnitude",description="Ratio of maximum absolute backward to forward pulsatile pressure components after explicit-Zc wave separation.",values=ab/af,method_id="vascuquest:spectral:reflection-magnitude-v1",inputs=(pressure,flow),parameters={"characteristic_impedance_pa_s_m3":characteristic_impedance_pa_s_m3,"amplitude_definition":"maximum_absolute_pulsatile_component"},evidence=EvidenceClass.DERIVED,canonical_unit="1",physical_dimension="dimensionless",value_kind="scalar",citations=_WAVE_CITATIONS,warnings=("Reflection magnitude is method-dependent and inherits the supplied characteristic-impedance assumption.",))

def wave_intensity(pressure: Waveform, velocity: Waveform, *, wave_speed_m_s: float, blood_density: float = 1060.0) -> tuple[ScientificResult, ScientificResult, ScientificResult]:
    if wave_speed_m_s<=0 or blood_density<=0: raise ValueError("wave speed and blood density must be positive")
    t=ensure_aligned_waveforms(pressure,velocity); p=pressure_pa(pressure); u=velocity_ms(velocity); dpdt=np.gradient(p,t); dudt=np.gradient(u,t); rho_c=blood_density*wave_speed_m_s; net=dpdt*dudt; forward=((dpdt+rho_c*dudt)**2)/(4.0*rho_c); backward=-((dpdt-rho_c*dudt)**2)/(4.0*rho_c); coords=(Coordinate("time",t,pressure.time_coordinate.unit),)
    common=dict(inputs=(pressure,velocity),parameters={"wave_speed_m_s":wave_speed_m_s,"blood_density_kg_m3":blood_density,"derivative":"numpy_gradient_native_time"},evidence=EvidenceClass.DERIVED,canonical_unit="W/m^2/s^2",physical_dimension="wave_intensity_rate",value_kind="waveform",dimensions=("time",),coordinates=coords,citations=_WAVE_CITATIONS,warnings=("Wave-intensity rate is derivative-sensitive; interpretation requires adequate temporal resolution.",))
    return make_result(pressure,canonical_name="spectral.net_wave_intensity",label="Net wave intensity",description="Net wave-intensity rate dP/dt*dU/dt.",values=net,method_id="vascuquest:spectral:wave-intensity-v1",**common), make_result(pressure,canonical_name="spectral.forward_wave_intensity",label="Forward wave intensity",description="Separated forward wave-intensity rate.",values=forward,method_id="vascuquest:spectral:wave-intensity-v1",**common), make_result(pressure,canonical_name="spectral.backward_wave_intensity",label="Backward wave intensity",description="Separated backward wave-intensity rate.",values=backward,method_id="vascuquest:spectral:wave-intensity-v1",**common)
